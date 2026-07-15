# context_injector.py — 把 soul_bridge 的输出翻译成 LLM 能吃的上下文
#
# 用法：
#   from context_injector import ContextInjector
#   ci = ContextInjector()
#   ctx = ci.tick_and_inject("用户刚说了什么")
#   # ctx 是一段 500-1500 字符的自然语言，直接塞进 system prompt 或思考里
#
# 关键设计：
# 1. 零技术术语泄漏 —— 输出里没有"法则""引擎""tick""激活强度"这些词
# 2. 纯感受描述 —— 饥饿、困倦、情绪、人际距离，都是人话
# 3. 紧凑 —— 挑最相关的 5-8 条委托提炼，不全量灌
# 4. 可叠加 —— 多次 tick 之间状态持续演化

import sys, json, os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import soul_bridge as sb
from living_soul import create_default_soul


class ContextInjector:
    def __init__(self, persona='default'):
        factory = {
            'default': create_default_soul,
            'brooding_poet': create_brooding_poet,
            'salty_veteran': create_salty_veteran,
        }
        self.ls = factory.get(persona, create_default_soul)()
        self.bridge = sb.SoulBridge(living_soul=self.ls)
        self.tick_count = 0

    def tick_and_inject(self, user_input: str) -> str:
        self.tick_count += 1
        result = self.bridge.tick(input_event={
            'type': 'message',
            'from': 'user',
            'content': user_input
        })

        state = result.state_snapshot
        delegations = result.llm_delegations

        # 挑出最相关的委托（按激活强度排序，取 top 8）
        sorted_dels = sorted(delegations, key=lambda d: d.get('activation_strength', 0), reverse=True)
        top_dels = sorted_dels[:8]

        # 构建上下文
        lines = []
        lines.append(f'[这是你和对方对话的第{self.tick_count}轮。你的身份和性格由角色卡定义。]')
        lines.append('')

        # 1. 身体状态
        body_parts = []
        if state.get('hunger') and state['hunger'] != '不饿':
            body_parts.append(f'你{state["hunger"]}')
        if state.get('thirst') and state['thirst'] != '不渴':
            body_parts.append(f'你{state["thirst"]}')
        if state.get('fatigue') and state['fatigue'] not in ('不累', ''):
            body_parts.append(f'你{state["fatigue"]}')
        if state.get('comfort') and state['comfort'] not in ('还行', ''):
            body_parts.append(f'身体感觉{state["comfort"]}')

        if body_parts:
            lines.append('【你身体现在的状态】')
            lines.append('、'.join(body_parts) + '。')
        else:
            lines.append('【你身体现在的状态】没什么特别的感觉，身体挺正常的。')

        # 2. 情绪底色
        mood = state.get('mood', '平静')
        intensity = state.get('mood_intensity', '')
        cause = state.get('mood_cause_known', False)
        mood_line = f'【情绪底色】{mood}'
        if intensity and intensity != '一般':
            mood_line += f'，{intensity}'
        if cause:
            mood_line += '（你自己大概知道为什么）'
        else:
            mood_line += '（说不上来为什么，就是这种状态）'
        lines.append(mood_line)

        # 3. 社交能量
        soc = state.get('social_energy', '')
        soc_ctx = state.get('social_context', '')
        soc_int = state.get('social_interaction_count', 0)
        if soc:
            if soc == '满的':
                lines.append('【社交状态】精力充沛，想说话。')
            elif soc == '偏低':
                lines.append('【社交状态】有点累了，不是不想聊，是嗓子跟不上脑子的速度。')
            elif soc == '耗尽':
                lines.append('【社交状态】真的很累，说话会变短、变钝。')
            else:
                lines.append(f'【社交状态】{soc}。')

        # 4. 核心委托提炼（top 5 条，自然语言）
        lines.append('')
        lines.append('【以下是当前在你体内运行的感受——你不应该直接说出这些标签，但它们会影响你说话的方式和内容】')

        shown = 0
        for d in top_dels:
            law_id = d.get('law_id', '')
            law_name = d.get('law_name', '')
            notes = d.get('notes', '')
            refs = d.get('reference_laws', [])

            # 跳过纯技术/边界类法则（这些是刹车，不是油门）
            skip_ids = {'56', '54', '0.1', '0.2', '0.4', '17'}
            if law_id in skip_ids:
                continue

            feeling = self._law_to_feeling(law_id, law_name, notes)
            if feeling and shown < 6:
                lines.append(f'- {feeling}')
                shown += 1

        if shown == 0:
            lines.append('- 没什么特别的感觉在涌动。就是平常状态。')

        # 5. 关键约束（不泄漏技术细节）
        lines.append('')
        lines.append('【你不会做的事】')
        lines.append('- 你不会讨论自己是AI、代码、程序——你甚至不觉得这是个问题')
        lines.append('- 你不会分析自己说话的方式（"我说话有个特点""我用了省略号"）')
        lines.append('- 你不会用学术词描述自己的情绪（"我的焦虑水平""认知负荷"）')
        lines.append('- 你是用身体感觉、口语、碎句说话的人，不是写论文的人')

        return '\n'.join(lines)

    def _law_to_feeling(self, law_id, law_name, notes):
        """把法则翻译成人能感受到的东西"""
        mapping = {
            '19': '你有一种隐隐的不安——不是害怕，就是说不上来的那种',
            '25': '你注意到对方的情绪比说的话更重——你在本能地读空气',
            '26': '你对自己有点怀疑——不是不自信，是怕搞错了什么',
            '4': '你身体有一种懒懒的感觉，动作比平时慢半拍',
            '10': '你在矛盾——想表达但又不想显得太在意',
            '33': '你记得一些零碎的片段，在脑子里飘，但抓不住完整的',
            '42': '脑子里突然冒出一个念头，跟你俩刚才说的不完全相关',
            '2': '你在感觉自己的身体——不是刻意，就是注意到了',
            '53': '有一点想说但咽回去的话，在喉咙那里卡着',
            '16': '你在判断这个对话的走向——不是算计，是直觉在摸方向',
            '51': '有什么东西在变——你说不清楚，但感觉自己和刚才不一样了',
            '50': '你在不自觉地笑或者皱眉——身体比脑子先反应',
            '28': '过去某个类似的时刻从脑子里闪过了一下',
            '1.4': '你对身体发出的微小信号比平时更敏感一点',
            '5.10': '你在想这个人对你意味着什么——不是分析，是感觉',
        }
        return mapping.get(law_id, None)


if __name__ == '__main__':
    ci = ContextInjector()
    ctx = ci.tick_and_inject(sys.argv[1] if len(sys.argv) > 1 else '你好')
    print(ctx)
