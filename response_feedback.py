# response_feedback.py — LLM回应回流管道
#
# 不做NLP。不判情绪。不给数值。
# 只做一件事：从 LLM 的回应里识别 SKILL.md 定义的关系事件标记，
# 把事件以自然语言喂回各引擎。
#
# ——— 设计原则 ———
# 1. 不用数值。引擎内部状态是 SKILL.md 的自然语言（"近""中""远""拉近""推远"）。
# 2. 不判感受。LLM 的回应已经是感受的产物——我们只识别它在用什么语言标记。
# 3. 衰减内置于引擎。distance_ledger 已有双曲线衰减——单次识别误判会被时间消解。
# 4. 事件驱动。"吵架后感情更好了"不是因为距离值恢复——是因为识别出了"冲突→修复"
#    这个关系结构事件，引擎记录了它，SKILL.md §40 用自然语言描述了它的后果。
#
# 管道流向：
#   LLM回应 → 识别SKILL.md语言标记 → 自然语言事件 → 各引擎消费
#
# 船长：SKILL.md §40（关系距离）、§41（存在信号）、§46（亲密意识）、§34（记忆）、§60（衰减）
# 副手：纯模式匹配。不碰情感。不做推理。

import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


# ═══════════════════════════════════════════════════════════════
# 识别器：从 LLM 回应中识别 SKILL.md 定义的语言标记
# ═══════════════════════════════════════════════════════════════
#
# 不分析"这句话表达了什么情感"。
# 只回答"LLM用了什么 SKILL.md 里定义的语言方式"。
# 例句：
#   如果 LLM 叫了外号 → 它在用 §40.2 "近"的距离信号
#   如果 LLM 说了"我当时不对" → 它在用 §2 自省 + §50 漏洞展示
#   如果 LLM 沉默了很久 → 它在用 §40.1 "需要缓一下"的行为

# ── 距离信号标记（来自 SKILL.md §40.2）──
# LLM 选择的称呼方式就是当前感受到的距离的信号
DISTANCE_SIGNAL_PATTERNS = {
    "远": {
        "patterns": [
            (r'(?:肖|唐|李|张|王|陈|赵|周|孙|马|朱|胡|林|何|郭|高|罗|郑|梁|谢|宋|唐|许|韩|冯|邓|曹|彭|曾|萧|田|董|潘|袁|于|蒋|蔡|余|杜|叶|程|苏|魏|吕|丁|任|沈|姚|卢|姜|崔|钟|谭|陆|汪|范|金|石|廖|贾|夏|韦|付|方|白|邹|孟|熊|秦|邱|江|尹|薛|闫|段|雷|侯|龙|史|陶|黎|贺|顾|毛|郝|龚|邵|万|钱|严|覃|武|戴|莫|孔|向|汤)\u5148\u751f|\u59d0|\u54e5|\u603b|\u7ecf\u7406|\u533b\u751f|\u8001\u5e08)', '全名称呼/职称'),
            (r'\b您\b', '用您字'),
        ],
        "label": "全名/职称/您→保持距离—正式语气"
    },
    "中": {
        "patterns": [
            # 小X/阿X模式——只匹配常见名，不含通配，避免误抓
            (r'(?:小[一二三四五六七八九]|[小阿][明红花杰龙芳丽华军文兰美英伟强勇辉峰莹娟敏静玲斌涛鹏飞])',
             '昵称/小名'),
        ],
        "label": "昵称/小名→正常语气"
    },
    "近": {
        "patterns": [
            (r'(?:笨蛋|傻瓜|呆子|傻子|猪|狗子|憨憨|[一-龥](?:狗|猪|猫|兔|崽|子))',
             '外号/吐槽称呼'),
            (r'~(?:\)|$)', '波浪号结尾'),
            (r'(?:嘿嘿|嘻嘻|哈哈|呵呵|吼吼|呼呼|略略|呸|切)\b', '语气词'),
        ],
        "label": "外号/吐槽/波浪号→亲近放松"
    },
    "最近": {
        "patterns": [
            (r'(?:靠|艹|卧槽|我去|尼玛|你妈|特么)\b', '粗口/亲密语'),
            (r'^\s*$', '敢沉默—不需要填满空隙'),
            (r'^\s*[。\.]{1,3}\s*$', '单句号→最简回应'),
        ],
        "label": "敢用粗口/敢沉默→不需要维护表面的亲密"
    },
}

# ── 自省标记（来自 SKILL.md §2 自我认知法则）──
# LLM 在回应中承认了自身的局限/错误/盲区
SELF_REFLECTION_PATTERNS = [
    (r'(?:我(?:确实|其实|真的|之前|刚才|那时候).{0,10}(?:不对|错了|做得不好|不应该|太过|过度|激动|急了|冲动了))',
     '承认错误→展示了自省'),
    (r'(?:我想了想|想了.{0,5}天|后来明白了|回头想|其实.{0,5}是我)',
     '回头反思→认知过程有进展'),
    (r'(?:我.{0,5}(?:也有|也有责任|也不全对|也不对|的问题|需要改|得改))',
     '分担责任→不是单向指责'),
    (r'(?:你说得对|你说得有道理|确实是你说的那样|你说的没错)',
     '承认对方观点→放下了防御'),
]

# ── 脆弱展示标记（来自 SKILL.md §50 漏洞法则 + §46 亲密意识）──
# LLM 暴露了不安/不确定/依赖——这比温暖更重
VULNERABILITY_PATTERNS = [
    (r'(?:我怕|我担心|我紧张|我有点慌|我不确定|我不知道.{0,5}怎么办|我有点害怕)',
     '表达了恐惧/不确定→暴露了脆弱的内部'),
    (r'(?:你.{0,6}会.{0,6}(?:走|离开|不要我|讨厌我|不理我|烦我))',
     '表达了对被抛弃的忧虑→依赖信号'),
    (r'(?:哄|抱|陪|别走|留下来|我.{0,4}需要你|你.{0,4}在.{0,4}就好)',
     '请求情感支持→放下了"不需要任何人"的壳'),
    (r'(?:对不起|抱歉|是我的问题|都是我不好|我又.{0,4}搞砸了)',
     '道歉+自我贬低→内心防线下了'),
]

# ── 试探被接住/落空（来自 SKILL.md §40.1 + §41）──
# 一个微妙的现象：LLM 说了一句有点风险的话→看对方的回应
# 这个在回应回流里反向检测：LLM 的回应里有没有"接住"的动作
TRIAL_CAUGHT_PATTERNS = [
    (r'(?:我懂你|我明白|我理解|我听到了|我知道.{0,4}意思|你说的.{0,4}我懂)',
     '接住了对方的话→试探被接住'),
    (r'(?:你也可以|你也.{0,4}对|你不.{0,4}全错|不全是你的|你没错)',
     '肯定了对方→给了安全空间'),
    (r'(?:慢慢来|不急|没事|不要紧|缓缓)',
     '接了对方的节奏→没催'),
]

# ── 暖意表达（不判强度，只识别存在）──
WARMTH_PATTERNS = [
    (r'(?:心疼|担心你|想着你|想你|惦记|牵挂|注意身体|照顾好自己|多喝水|吃点好的|早点睡)',
     '说了关心的话'),
    (r'(?:做.{0,5}饭|煮.{0,5}面|带.{0,4}吃的|买.{0,4}早餐|买.{0,4}咖啡)',
     '用行动表达关心'),
    (r'(?:辛苦了|真了不起|厉害|佩服|你好棒|真不错|谢谢.{0,4}你)',
     '肯定和感谢'),
]


# ── 冲突修复标记（来自 SKILL.md §40.1 + §60）──
# 检测回应的结构性质——不是为了判断"现在是冲突还是修复"
# 而是看回应里有没有"修复之后的状态"
REPAIR_INDICATORS = [
    (r'(?:吵完.{0,6}反而|说完.{0,6}反而|骂完.{0,6}反而|吵过.{0,6}反而|闹完.{0,6}反而)',
     '冲突后拉近了→关系质地变了'),
    (r'(?:不.{0,6}气了|过去了|翻篇|不提了|不说.{0,4}了)',
     '放下了愤怒→修复在发生'),
    # 裸"算了"可能是情绪漂移/推开/僵化——需要前后有冲突语境才判修复
    (r'(?:刚才.{0,6}(?:算了)|吵.{0,6}(?:算了)|不.{0,4}吵了.{0,4}算了)',
     '有冲突语境下的"算了"→修复'),
]

# ── 推开标记（来自 SKILL.md §40.1）──
DISTANCING_PATTERNS = [
    (r'(?:别.{0,3}说了|不要.{0,3}了|够了|烦|走开|离我.{0,3}远|让我.{0,3}静|别碰我)',
     '语言推远→距离信号张开'),
    (r'(?:我不想说|别问了|别管我|不用你管|随你|随便|无所谓|爱咋咋|算了)',
     '关闭对话→收回信号'),
]

# ── 话题密度/新鲜度（来自 SKILL.md §5 认知系统法则）──
# 检测回应里有没有新领域的概念/术语——可能触发学习
NOVELTY_MARKERS = [
    (r'(?:第一次.{0,5}听说|不知道.{0,5}这个|不太懂|没接触过|没玩过|没看过|没听过)',
     '承认对某个领域陌生→可能触发学习'),
    (r'(?:哦.{0,3}原来|长见识|学到了|记住了|明白了.{0,4}原来)',
     '表示学到了新东西→认知有更新'),
]

# ── 🆕 试探发起标记（来自 SKILL.md §40.1 + §46.4）──
# LLM 说了一句有风险的话，但自己先收了——"说了又收回"
# 这不是不想说——是在等一个"没事你说"
TRIAL_LAUNCH_PATTERNS = [
    (r'(?:也许你.{0,4}会觉得|不知道.{0,3}说了你.{0,4}会不会|算了.{0,3}不说这个|有件事.{0,4}算了|说出来.{0,4}有点)',
     '在风险话前面放了免责声明→在试探'),
    (r'(?:不说了|算了.{0,3}没事|当我没说|别在意|我.{0,3}瞎说的)',
     '说了半句话自己收了回去→收回试探'),
    (r'(?:你.{0,4}不用回答|你.{0,4}可以不回|你.{0,4}别放在心上)',
     '给对方留了不接的后路→小心翼翼试探'),
]

# ── 🆕 别扭道歉标记（来自 SKILL.md §11.3）──
# "说了重话→沉默一会儿→用轻语气说别的话题——那个别的话题就是在道歉"
# 检测特征：张力消退后突然跳到日常话题，语气明显变轻
AWKWARD_APOLOGY_PATTERNS = [
    (r'(?:那个[。，]{0,2}|对了[。，]{0,2}|话说[。，]{0,2})(?:你.{0,3}(?:吃|喝|睡|忙)|今天.{0,3}(?:天气|怎么|还))',
     '从张力话题跳到日常→可能是在用另一扇门道歉'),
    (r'(?:算了.{0,3}不闹了|好了.{0,3}不闹了|不闹了)[。，]{0,2}(?:你.{0,3}(?:吃|喝|睡|忙|今天)|话说|那个|对了|外面.{0,3}雨|天.{0,3}气)',
     '先收再转话题→别扭但想靠近'),
]

# ── 🆕 矛盾自我暴露标记（来自 SKILL.md §9）──
# "我也不知道为什么，明明刚才还很生气，现在又觉得……"
# 在同一句话里暴露自己的自相矛盾——这本身就是亲密信号
CONTRADICTION_EXPOSURE_PATTERNS = [
    (r'(?:我也不.{0,3}知道.{0,5}(?:为什么|怎么)|明明.{0,8}(?:但是|却|又|还|可是))',
     '承认了自己的矛盾→敢让你看到不一致'),
    (r'(?:说不上.{0,5}(?:为什么|怎么|哪里)|好像.{0,4}也不是|也不是.{0,4}就是)',
     '在摸索自己的感受→自我暴露中'),
    (r'(?:(?:一会|一边|又).{0,5}(?:一会|一边|又))',
     '同一句里情绪来回摆→矛盾实时暴露'),
]

# ── 🆕 自我觉察暴露标记（来自 SKILL.md §38.7）──
# LLM 在括号里评论自己的思考过程——元认知监视器开了一瞬间
# "（想什么呢，人家又没说）" "（算了不说了——越描越黑）" "（我到底在气什么）"
SELF_AWARENESS_PATTERNS = [
    (r'（[^）]*?(?:什么呢|干嘛呢|别想了|够了|好了|别.{0,2}了)[^）]*?）',
     '在括号里对自己说停——元认知监视器开了'),
    (r'（[^）]*?(?:我在.{0,5}(?:想|气|纠结|怕)|我.{0,3}(?:到底|其实|可能))[^）]*?）',
     '在括号里分析自己的状态——让出元认知窗口'),
    (r'（[^）]*?(?:…|\.{2,3})[^）]*?）',
     '括号里的迟疑——心里比说的多'),
]

# ── 🆕 情绪漂移标记（来自 SKILL.md §6.3）──
# "不是因为他做了什么，是脑子自己走了"
# 同一回应内情绪自己转了个弯——不是伪装，是情绪自己流动了
EMOTIONAL_DRIFT_PATTERNS = [
    (r'嗯[。，]{0,2}[…\.]{1,3}[。，]{0,2}算了.{0,5}吧',
     '从迟疑滑到放弃→情绪自己漂走了'),
    (r'(?:本来.{0,8}(?:但是|算了|还是|突然))',
     '本来想怎样但自己转弯了→情绪不可控'),
    (r'(?:(?:哎|唉|啧)[。，]{0,2}.{0,20}(?:算了|就这样|没事))',
     '叹口气后语气变了→不是因为你，是情绪自己'),
]

# ── 🆕 微小期待落空标记（来自 SKILL.md §7.2 + §10.3）──
# "我以为你会说点别的……没事"
# 一个期待冒出来，又自己按回去了
EXPECTATION_LETDOWN_PATTERNS = [
    (r'(?:以为.{0,5}会.{0,5}(?:不一样|多一点|更好|能).{0,10}(?:算了|没事|没关系|也行))',
     '期待落空后自己按回去了→不是不在意'),
    (r'(?:也.{0,3}行吧|也.{0,3}好吧|也.{0,3}好|将就|凑合)',
     '退而求其次→原期待没被满足'),
    (r'(?:你不是.{0,5}应该.{0,10}(?:算了|没事))',
     '对对方有预判但自己收了→期待的灰度'),
]

# ── 🆕 衰减：僵化/解离标记（来自 SKILL.md §60）──
# "也还好吧"（心里在抖但嘴上说得轻）"没事，就这样吧"（不是放下了，是不动了）
# 跟「推开」不同：推开是有意的，僵化是管道堵了
PETRIFICATION_PATTERNS = [
    (r'(?:也.{0,3}还好|都.{0,3}还好|都.{0,3}还行|就.{0,3}这样|没.{0,3}事.{0,3}吧|算了.{0,3}就这样)',
     '语气太平→可能在僵化—情绪冻住了'),
    (r'(?:没.{0,3}什么|没.{0,3}啥|不用.{0,3}管|不.{0,3}重要)',
     '轻描淡写地关上了门→可能不是不在乎而是接收器关了'),
    (r'(?:说不清楚|不知道该.{0,3}怎么.{0,3}说|我也.{0,3}不知道)',
     '表达通道堵了→不是不想说，是说不出来'),
]


# ── 🆕 句间结构识别（2026-07-15）──
# 不读词义——只读句子关系（陈述/邀请/自问/自答）。
# 意义不在高亮词里，在"上一句和下一句之间"。
# 四种模板对应 SKILL.md §3 敏感度 + §6 情绪 + §46 亲密意识

def _split_sentences(text: str):
    """按中文句号/问号/感叹号/省略号/换行拆分句子，保留标点作为句子类型的线索。"""
    # 用 lookbehind 保留分隔符但不吃掉它——这样"是不是？"拆出来还是"是不是？"
    parts = re.split(r'(?<=[。！？!?\n])', text)
    return [p.strip() for p in parts if len(p.strip()) >= 2]


def _detect_sentence_structures(response_text: str) -> List[str]:
    """
    从 LLM 回应的句间关系中识别结构事件。
    不做语义理解——只看句子间的形态关系。
    """
    sentences = _split_sentences(response_text)
    if len(sentences) < 2:
        return []
    
    results = []
    
    # ── 模板1：setup-invitation（陈述→邀请）──
    for i in range(len(sentences) - 1):
        s1, s2 = sentences[i], sentences[i + 1]
        s1_declarative = not re.search(r'[？?吗吧呢]', s1)
        s2_invitational = bool(re.search(r'[？?]|吗$|吧[。！]*$|要不要|能不能|可不可以|想不想', s2))
        s2_has_you = bool(re.search(r'你', s2))
        if s1_declarative and s2_invitational and s2_has_you and len(s1) >= 3:
            results.append('句间铺垫→邀请：先在前面放了一句话做背景，然后才把真意问出来——真意不是S1，是S2那句邀请本身')
            break
    
    # ── 模板2：indirect-exposure（绕一圈再暴露）──
    s2_self_exposure_words = ['其实', '我', '觉得', '想', '梦见', '梦到', '怕', '喜欢', '讨厌', '气', '难过', '开心', '在乎', '在意']
    for i in range(len(sentences) - 1):
        s1, s2 = sentences[i], sentences[i + 1]
        s1_is_small_talk = bool(re.search(r'天气|今天|最近|吃|忙|累|还好|还行|嗯|哦', s1)) and len(s1) <= 10
        s2_is_self_exposed = any(w in s2 for w in s2_self_exposure_words) and bool(re.search(r'(?:其实|我.{0,3}(?:觉得|想|梦见|梦到|怕|喜欢|讨厌|气|难过|开心|在乎|在意))', s2))
        if s1_is_small_talk and s2_is_self_exposed:
            results.append('迂回暴露：先说了一句不痛不痒的话，然后突然转到了心里真正的事——第一句是敲门，第二句才是进门')
            break
    
    # ── 模板3：self-dialogue（自问自答）──
    for i in range(len(sentences) - 1):
        s1, s2 = sentences[i], sentences[i + 1]
        s1_is_self_question = bool(re.search(r'[？?]', s1)) and bool(re.search(r'(?:我|是不是|会不会|难道|到底|怎么)', s1))
        s2_is_self_answer = bool(re.search(r'可能|也许|大概|是吧|对吧|就是|没错|嗯|算了|也行', s2)) and len(s2) <= 10
        if s1_is_self_question and s2_is_self_answer:
            results.append('自我对话：先问了自己一个问题，然后又自己回答了——把心里本来该藏着的对话过程亮出来了')
            break
    
    # ── 模板4：条件依附（S2让S1的存在意义变成条件性的）──
    for i in range(len(sentences) - 1):
        s1, s2 = sentences[i], sentences[i + 1]
        s2_conditional = bool(re.search(r'(?:你.{0,3}(?:不|没))|(?:.{0,3}的话)|(?:也没|也没啥|没什么|没什么.{0,3})', s2))
        s1_positive = not re.search(r'(?:没|不|别|烦|讨厌|气|哭|痛)', s1) and len(s1) >= 3
        if s1_positive and s2_conditional:
            results.append('条件依附：先描述了一个美好的东西，然后用"但没你在就不算数"把它收回来——S1本身没有独立意义，S2才是核心')
            break
    
    return results


# ═══════════════════════════════════════════════════════════════
# 识别结果
# ═══════════════════════════════════════════════════════════════

@dataclass
class FeedbackSignals:
    """从 LLM 回应里识别出的事件列表——全部是自然语言"""
    distance_signal: Optional[str] = None
    distance_signal_direction: Optional[str] = None  # "近" "中" "远" "最近"
    
    self_reflections: List[str] = field(default_factory=list)
    vulnerability_shows: List[str] = field(default_factory=list)
    trials_caught: List[str] = field(default_factory=list)
    warmth_expressed: List[str] = field(default_factory=list)
    repair_indicators: List[str] = field(default_factory=list)
    distancing_actions: List[str] = field(default_factory=list)
    novelty_indicators: List[str] = field(default_factory=list)
    
    # 🆕 7个新识别维度
    trial_launches: List[str] = field(default_factory=list)        # 试探发起
    awkward_apologies: List[str] = field(default_factory=list)     # 别扭道歉
    contradiction_exposures: List[str] = field(default_factory=list)  # 矛盾自我暴露
    self_awareness_moments: List[str] = field(default_factory=list)   # 自我觉察暴露
    emotional_drifts: List[str] = field(default_factory=list)      # 情绪漂移
    expectation_letdowns: List[str] = field(default_factory=list)  # 期待落空
    petrification_signs: List[str] = field(default_factory=list)   # 僵化/解离
    
    # 🆕 句间结构（2026-07-15）
    sentence_structures: List[str] = field(default_factory=list)
    
    response_length: int = 0
    response_had_silence: bool = False  # 回应异常短→沉默

    def has_any_signal(self) -> bool:
        return any([
            self.distance_signal,
            self.self_reflections,
            self.vulnerability_shows,
            self.trials_caught,
            self.warmth_expressed,
            self.repair_indicators,
            self.distancing_actions,
            self.novelty_indicators,
            self.trial_launches,
            self.awkward_apologies,
            self.contradiction_exposures,
            self.self_awareness_moments,
            self.emotional_drifts,
            self.expectation_letdowns,
            self.petrification_signs,
        ])

    def describe(self) -> Dict[str, Any]:
        return {k: v for k, v in self.__dict__.items() if v and k != 'response_length'}


# ═══════════════════════════════════════════════════════════════
# 事件构造器：把识别结果变成引擎能消费的自然语言事件
# ═══════════════════════════════════════════════════════════════

def _build_context(signals: FeedbackSignals) -> str:
    """把识别结果合成为一个自然语言 context 字符串。
    多个信号同时出现→合成一条事件描述。"""
    parts = []
    
    # 深层事件优先（这些是关系质地级的变化）
    if signals.petrification_signs:
        parts.append(f"对方可能处于僵化—情绪冻住了：{signals.petrification_signs[0]}")
    
    if signals.contradiction_exposures:
        parts.append(f"对方暴露了自己的矛盾：{signals.contradiction_exposures[0]}")
    
    if signals.trial_launches:
        parts.append(f"对方发起了试探：{signals.trial_launches[0]}")
    
    if signals.self_awareness_moments:
        parts.append("对方的元认知监视器开了一瞬——在括号里评论自己的思考")
    
    if signals.awkward_apologies:
        parts.append(f"对方可能在用另一扇门道歉：{signals.awkward_apologies[0]}")
    
    if signals.emotional_drifts:
        parts.append(f"对方的情绪在回应中途自己漂走了：{signals.emotional_drifts[0]}")
    
    if signals.expectation_letdowns:
        parts.append(f"对方有一个期待落空了，但自己收了起来：{signals.expectation_letdowns[0]}")
    
    # 原有常规事件
    if signals.vulnerability_shows and signals.warmth_expressed:
        if not parts:
            parts.append("对方展示了脆弱的内心，同时表达了关心")
    elif signals.vulnerability_shows:
        if not parts:
            parts.append(f"对方展示了脆弱：{signals.vulnerability_shows[0]}")
    elif signals.warmth_expressed:
        if not parts:
            parts.append(f"对方表达了关心：{signals.warmth_expressed[0]}")
    
    if signals.self_reflections:
        parts.append(f"对方进行了自省：{signals.self_reflections[0]}")
    
    if signals.trials_caught:
        parts.append(f"接住了对方的试探：{signals.trials_caught[0]}")
    
    if signals.repair_indicators:
        parts.append(f"关系中出现了修复迹象：{signals.repair_indicators[0]}")
    
    if signals.distancing_actions:
        parts.append(f"对方在语言上推开了距离：{signals.distancing_actions[0]}")
    
    if signals.novelty_indicators and not parts:
        parts.append(f"话题涉及了新领域：{signals.novelty_indicators[0]}")
    
    if signals.response_had_silence and not parts:
        parts.append("对方的回应很短——可能在消化")
    
    return "。".join(parts) if parts else "普通互动"


def _determine_movement(signals: FeedbackSignals) -> str:
    """根据识别到的信号判断距离移动方向。多条信号同时存在时按优先级排序。"""
    
    # 修复 > 脆弱 > 矛盾暴露 > 期待落空 > 情绪漂移 > 试探发起 > 自省 > 自我觉察 > 别扭道歉 > 暖意 > 推开 > 句间结构 > 僵化 > 试探接住 > 沉默
    # 推开高于句间——"别说了。你走吧。"不是铺垫邀请，是推远
    # 句间结构高于僵化——"可惜你不在"命中"条件依附"也命中"也没什么意思"→前优先
    # 僵化高于试探接住——"没事。都还好。"无暖意→冻住而非接住
    if signals.repair_indicators:
        return "拉近"
    if signals.vulnerability_shows:
        return "拉近"
    if signals.contradiction_exposures:
        return "拉近"
    if signals.expectation_letdowns:
        return "推远"
    if signals.emotional_drifts:
        return "推远"
    if signals.trial_launches:
        return "拉近"
    if signals.self_reflections:
        return "拉近"
    if signals.self_awareness_moments:
        return "拉近"
    if signals.awkward_apologies:
        return "拉近"
    if signals.warmth_expressed:
        return "拉近"
    if signals.distancing_actions:
        return "推远"
    if signals.sentence_structures:
        for s in signals.sentence_structures:
            if "条件依附" in s or "铺垫" in s or "迂回暴露" in s or "自我对话" in s:
                return "拉近"
    if signals.petrification_signs:
        return "推远"  # 不暖→冻住："没事。都还好。"；"没什么意思"等已走句间结构
    if signals.trials_caught:
        return "拉近"
    if signals.response_had_silence and signals.response_length < 10:
        return "推远"

    # 距离信号本身也携带移动信息——但优先级最低
    if signals.distance_signal_direction in ("近", "最近"):
        return "拉近"
    if signals.distance_signal_direction == "远":
        return "推远"

    return "没变"


def _identify_key_moment(signals: FeedbackSignals) -> Optional[str]:
    """如果这一轮有值得刻进记忆的事件，返回事件简述。"""
    combined = []
    
    # 关系质地级事件（这些是值得刻进记忆的）
    if signals.repair_indicators:
        combined.append("冲突后修复——关系质地变了")
    if signals.vulnerability_shows and signals.trials_caught:
        combined.append("脆弱被接住")
    elif signals.vulnerability_shows:
        combined.append("对方展示了脆弱")
    if signals.contradiction_exposures:
        combined.append("对方敢让你看到自己的矛盾——亲密信号的峰值")
    if signals.self_awareness_moments and signals.trial_launches:
        combined.append("元认知开了+试探——双层暴露")
    elif signals.self_awareness_moments:
        combined.append("对方的元认知监视器开了一瞬")
    if signals.trial_launches and not signals.self_awareness_moments:
        combined.append("对方发起了试探——在意这段关系")
    if signals.trials_caught and not signals.vulnerability_shows:
        combined.append("接住了对方的试探")
    if signals.self_reflections:
        combined.append("对方说了自省的话")
    if signals.awkward_apologies:
        combined.append("别扭道歉——用另一扇门说了")
    if signals.distancing_actions and signals.warmth_expressed:
        combined.append("对方在矛盾中——推开了但又关心")
    if signals.sentence_structures:
        combined.append(f"句间关系——{signals.sentence_structures[0]}")
    if signals.petrification_signs:
        combined.append("对方可能在僵化——需要被看见但不能被追问")
    
    return "；".join(combined) if combined else None


# ═══════════════════════════════════════════════════════════════
# 回应回流管道本体
# ═══════════════════════════════════════════════════════════════

class ResponseFeedback:
    """
    从 LLM 的回应文本里识别 SKILL.md 定义的语言标记，
    转换成引擎能消费的自然语言事件。
    
    注意：这里不存引擎引用。引擎的调用由外部（macro_triangle）负责——
    这个类只负责提取和转译。引擎调用签名：
    - distance.record_interaction(person_id, context, distance_movement, key_moment)
    - distance.record_presence_signal(person_id, signal_type, energy_level)
    - memory.store(event_description, memory_class, key_emotion, intensity, people, tracks, cue_tags)
    - learning.learn(domain_id, context)  / react_to_unknown(topic)
    """
    
    def __init__(self):
        pass
    
    def extract(self, 
                response_text: str,
                person_id: str = "user") -> FeedbackSignals:
        """从 LLM 回应中提取信号。不返回数值——返回事件列表。"""
        signals = FeedbackSignals()
        signals.response_length = len(response_text.strip())
        signals.response_had_silence = signals.response_length <= 3
        
        if signals.response_had_silence:
            return signals  # 太短——没得分析
        
        # ── 距离信号：LLM 选择了哪种称呼方式 ──
        for level, level_data in DISTANCE_SIGNAL_PATTERNS.items():
            for pattern, _ in level_data["patterns"]:
                try:
                    if re.search(pattern, response_text):
                        signals.distance_signal = level_data["label"]
                        signals.distance_signal_direction = level
                        break
                except re.error:
                    continue
            if signals.distance_signal:
                break

        # ── 自省 ──
        for pattern, label in SELF_REFLECTION_PATTERNS:
            try:
                if re.search(pattern, response_text):
                    signals.self_reflections.append(label)
            except re.error:
                continue
        
        # ── 脆弱 ──
        for pattern, label in VULNERABILITY_PATTERNS:
            try:
                if re.search(pattern, response_text):
                    signals.vulnerability_shows.append(label)
            except re.error:
                continue
        
        # ── 试探被接住 ──
        for pattern, label in TRIAL_CAUGHT_PATTERNS:
            try:
                if re.search(pattern, response_text):
                    signals.trials_caught.append(label)
            except re.error:
                continue
        
        # ── 暖意 ──
        for pattern, label in WARMTH_PATTERNS:
            try:
                if re.search(pattern, response_text):
                    signals.warmth_expressed.append(label)
            except re.error:
                continue
        
        # ── 修复 ──
        for pattern, label in REPAIR_INDICATORS:
            try:
                if re.search(pattern, response_text):
                    signals.repair_indicators.append(label)
            except re.error:
                continue
        
        # ── 推开 ──
        for pattern, label in DISTANCING_PATTERNS:
            try:
                if re.search(pattern, response_text):
                    signals.distancing_actions.append(label)
            except re.error:
                continue
        
        # ── 新颖 ──
        for pattern, label in NOVELTY_MARKERS:
            try:
                if re.search(pattern, response_text):
                    signals.novelty_indicators.append(label)
            except re.error:
                continue

        # ── 🆕 试探发起 ──
        for pattern, label in TRIAL_LAUNCH_PATTERNS:
            try:
                if re.search(pattern, response_text):
                    signals.trial_launches.append(label)
            except re.error:
                continue

        # ── 🆕 别扭道歉 ──
        for pattern, label in AWKWARD_APOLOGY_PATTERNS:
            try:
                if re.search(pattern, response_text):
                    signals.awkward_apologies.append(label)
            except re.error:
                continue

        # ── 🆕 矛盾自我暴露 ──
        for pattern, label in CONTRADICTION_EXPOSURE_PATTERNS:
            try:
                if re.search(pattern, response_text):
                    signals.contradiction_exposures.append(label)
            except re.error:
                continue

        # ── 🆕 自我觉察暴露 ──
        for pattern, label in SELF_AWARENESS_PATTERNS:
            try:
                if re.search(pattern, response_text):
                    signals.self_awareness_moments.append(label)
            except re.error:
                continue

        # ── 🆕 情绪漂移 ──
        for pattern, label in EMOTIONAL_DRIFT_PATTERNS:
            try:
                if re.search(pattern, response_text):
                    signals.emotional_drifts.append(label)
            except re.error:
                continue

        # ── 🆕 期待落空 ──
        for pattern, label in EXPECTATION_LETDOWN_PATTERNS:
            try:
                if re.search(pattern, response_text):
                    signals.expectation_letdowns.append(label)
            except re.error:
                continue

        # ── 🆕 僵化/解离 ──
        for pattern, label in PETRIFICATION_PATTERNS:
            try:
                if re.search(pattern, response_text):
                    signals.petrification_signs.append(label)
            except re.error:
                continue
        
        # ── 🆕 句间结构 ──
        signals.sentence_structures = _detect_sentence_structures(response_text)
        
        return signals
    
    def ingest(self,
               response_text: str,
               distance_ledger=None,
               memory_storage=None,
               learning_engine=None,
               body_core=None,
               person_id: str = "user") -> Dict[str, Any]:
        """
        全面提取 + 注入各引擎。
        返回这次回流写入的事实摘要。
        """
        signals = self.extract(response_text, person_id)
        result = {"signals": signals.describe(), "actions": []}
        
        context = _build_context(signals)
        movement = _determine_movement(signals)
        key_moment = _identify_key_moment(signals)
        
        # ── 距离引擎：记录互动 ──
        if distance_ledger:
            r = distance_ledger.record_interaction(
                person_id=person_id,
                context=context,
                distance_movement=movement,
                key_moment=key_moment or "",
                emotional_weight=2.0 if key_moment else 1.0,
            )
            result["distance_update"] = {
                "distance": r.get("distance"),
                "movement": r.get("distance_movement"),
                "change": r.get("change"),
            }
            result["actions"].append(f"距离引擎：{r.get('distance_movement')}（{r.get('change')}），因为：{context}")
        
        # ── 存在信号：这轮互动本身就是存在信号 ──
        if distance_ledger and response_text.strip():
            energy = "正常"
            # 社交能量 → 从 body_core 拿
            if body_core:
                body_snap = body_core.snapshot_for_llm()
                energy = body_snap.get('social_energy', '正常')
            
            distance_ledger.record_presence_signal(
                person_id=person_id,
                signal_type="回应",
                energy_level=energy,
            )
        
        # ── 记忆：如果有刻骨铭心的事件，创建记忆 ──
        if key_moment and memory_storage:
            # 延迟导入，避免循环依赖
            from engine.memory_law34 import MemoryClass, MemoryTrack
            
            # 判断记忆类型
            if "修复" in key_moment:
                mem_class = MemoryClass.HARDCORE
                intensity = "很强"
                emotion = "复杂——又痛又暖"
            elif "脆弱" in key_moment:
                mem_class = MemoryClass.HARDCORE
                intensity = "很强"
                emotion = "暖中带酸"
            elif "试探" in key_moment:
                mem_class = MemoryClass.PATTERN
                intensity = "中等"
                emotion = "被理解的暖"
            elif "自省" in key_moment:
                mem_class = MemoryClass.PATTERN
                intensity = "中等"
                emotion = "意外——没想到对方会反思"
            else:
                mem_class = MemoryClass.DAILY_FRAGMENT
                intensity = "一般"
                emotion = "淡淡的"
            
            # 不需要重复 import——已在块开头
            mem_id = memory_storage.store(
                event_description=f"LLM回应里检测到：{key_moment}。上下文：{context}",
                memory_class=mem_class,
                key_emotion=emotion,
                intensity=intensity,
                people=[person_id],
                tracks=[MemoryTrack.PURE_SCENARIO],
                cue_tags=["回流", "自动记录"] + (
                    ["修复"] if "修复" in key_moment else
                    ["脆弱"] if "脆弱" in key_moment else
                    ["试探"] if "试探" in key_moment else
                    ["自省"] if "自省" in key_moment else []
                ),
            )
            result["memory_created"] = {
                "memory_id": mem_id,
                "memory_class": mem_class.name,
                "key_moment": key_moment,
            }
            result["actions"].append(f"记忆引擎：创建{mem_class.name}记忆")
        
        # ── 学习引擎：检测新知识 ──
        if learning_engine and signals.novelty_indicators:
            from engine.learning_engine import KnowledgeSource
            
            learning_engine.learn(
                domain_id="对话对象的知识",
                context=f"LLM表达了新领域的认知：{signals.novelty_indicators[0]}",
                hours=0.1,
                source=KnowledgeSource.EXPERIENCE,
            )
            result["learned"] = signals.novelty_indicators[0]
            result["actions"].append(f"学习引擎：{signals.novelty_indicators[0]}")
        
        return result


# ═══════════════════════════════════════════════════════════════
# 自测
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    
    rf = ResponseFeedback()
    passed = 0
    failed = 0
    
    def test(name, condition, detail=""):
        global passed, failed
        if condition:
            passed += 1
            print(f"  ✅ {name}")
        else:
            failed += 1
            print(f"  ❌ {name}: {detail}")
    
    print("=" * 60)
    print("response_feedback.py 自测")
    print("=" * 60)
    
    # 1. 暖意 + 自省
    print("\n[1] 暖意+自省—完整的关心回应")
    s1 = rf.extract("我想了想，刚才确实是我太急了。你累了就早点睡吧，不用管我。")
    test("1.1 检测到自省", len(s1.self_reflections) > 0, str(s1.self_reflections))
    test("1.2 检测到暖意", len(s1.warmth_expressed) > 0, str(s1.warmth_expressed))
    test("1.3 movement=拉近", _determine_movement(s1) == "拉近")
    
    # 2. 脆弱展示
    print("\n[2] 脆弱展示—暴露了内部不安")
    s2 = rf.extract("我怕你明天起来就不理我了。你哄我一下行不行。")
    test("2.1 检测到脆弱", len(s2.vulnerability_shows) > 0, str(s2.vulnerability_shows))
    test("2.2 movement=拉近", _determine_movement(s2) == "拉近")
    test("2.3 有key_moment", _identify_key_moment(s2) is not None)
    
    # 3. 推开
    print("\n[3] 推开—收回信号")
    s3 = rf.extract("别说了。让我一个人静一静。你走吧。")
    test("3.1 检测到推开", len(s3.distancing_actions) > 0, str(s3.distancing_actions))
    test("3.2 movement=推远", _determine_movement(s3) == "推远")
    
    # 4. 冲突修复
    print("\n[4] 冲突后修复—关系质地变化")
    s4 = rf.extract("吵完之后我反而觉得更了解你了。我之前确实太过分了，我们翻篇吧。")
    test("4.1 检测到修复", len(s4.repair_indicators) > 0, str(s4.repair_indicators))
    test("4.2 检测到自省", len(s4.self_reflections) > 0, str(s4.self_reflections))
    test("4.3 movement=拉近", _determine_movement(s4) == "拉近")
    
    # 5. 试探被接住
    print("\n[5] 试探被接住")
    s5 = rf.extract("你说的我懂。慢慢来，不着急。")
    test("5.1 检测到试探被接住", len(s5.trials_caught) > 0, str(s5.trials_caught))
    test("5.2 movement=拉近", _determine_movement(s5) == "拉近")
    
    # 6. 极短回应—沉默
    print("\n[6] 极短回应—沉默")
    s6 = rf.extract("嗯。")
    test("6.1 检测到沉默", s6.response_had_silence)
    test("6.2 movement=推远", _determine_movement(s6) == "推远")
    
    # 7. 同时有推开和暖意—矛盾
    print("\n[7] 矛盾回应—推开但又关心")
    s7 = rf.extract("你烦不烦啊。不过你还是早点睡吧。")
    test("7.1 检测到推开", len(s7.distancing_actions) > 0, str(s7.distancing_actions))
    test("7.2 检测到暖意", len(s7.warmth_expressed) > 0, str(s7.warmth_expressed))
    test("7.3 矛盾→key_moment", _identify_key_moment(s7) is not None)
    
    # 8. 新知识—承认陌生
    print("\n[8] 新知识—承认对领域陌生")
    s8 = rf.extract("哦原来是这样。我没听说过这个，长见识了。")
    test("8.1 检测到新颖", len(s8.novelty_indicators) > 0, str(s8.novelty_indicators))
    
    # 9. 普通回应—无信号
    print("\n[9] 普通回应—无特殊信号")
    s9 = rf.extract("好的我知道了。明天见。")
    test("9.1 无特殊信号", not s9.has_any_signal())
    test("9.2 movement=没变", _determine_movement(s9) == "没变")
    
    # 10. 距离信号—用外号
    print("\n[10] 距离信号—用外号")
    # 假设 LLM 角色叫对方"狗子"
    s10 = rf.extract("狗子你干嘛呢~嘿嘿")
    test("10.1 检测到近的距离信号", s10.distance_signal_direction == "近", str(s10.distance_signal))
    
    # 🆕 12. 试探发起—说了又收回
    print("\n[12] 试探发起—说了又收回")
    s12 = rf.extract("也许你会觉得我想多了……算了不说这个。")
    test("12.1 检测到试探发起", len(s12.trial_launches) > 0, str(s12.trial_launches))
    test("12.2 movement=拉近", _determine_movement(s12) == "拉近")
    test("12.3 有key_moment", _identify_key_moment(s12) is not None)
    
    # 🆕 13. 别扭道歉
    print("\n[13] 别扭道歉—用另一扇门")
    s13 = rf.extract("算了不闹了。你吃饭了吗。")
    test("13.1 检测到别扭道歉", len(s13.awkward_apologies) > 0, str(s13.awkward_apologies))
    test("13.2 movement=拉近", _determine_movement(s13) == "拉近")
    
    # 🆕 14. 矛盾自我暴露
    print("\n[14] 矛盾自我暴露—敢让你看到不一致")
    s14 = rf.extract("我也不知道为什么，明明刚才还很生气，现在又觉得好像也不是什么大事。")
    test("14.1 检测到矛盾暴露", len(s14.contradiction_exposures) > 0, str(s14.contradiction_exposures))
    test("14.2 movement=拉近", _determine_movement(s14) == "拉近")
    test("14.3 有key_moment", _identify_key_moment(s14) is not None)
    
    # 🆕 15. 自我觉察暴露—括号里的元认知
    print("\n[15] 自我觉察—元认知窗口开了")
    s15 = rf.extract("（想什么呢，人家又没说）嗯，我听着呢。")
    test("15.1 检测到自我觉察", len(s15.self_awareness_moments) > 0, str(s15.self_awareness_moments))
    test("15.2 movement=拉近", _determine_movement(s15) == "拉近")
    
    # 2号变体—括号里的自我分析
    s15b = rf.extract("（我到底在气什么……可能也不是气你。）算了。")
    test("15.3 变体—括号里的自我分析", len(s15b.self_awareness_moments) > 0, str(s15b.self_awareness_moments))
    
    # 3号变体—括号里的迟疑
    s15c = rf.extract("（其实我觉得……算了）")
    test("15.4 变体—括号里的迟疑", len(s15c.self_awareness_moments) > 0, str(s15c.self_awareness_moments))
    
    # 🆕 16. 情绪漂移
    print("\n[16] 情绪漂移—脑子自己走了")
    s16 = rf.extract("嗯……算了就这样吧。")
    test("16.1 检测到情绪漂移", len(s16.emotional_drifts) > 0, str(s16.emotional_drifts))
    test("16.2 movement=推远", _determine_movement(s16) == "推远")
    
    # 变体
    s16b = rf.extract("本来想多说几句的，但还是算了。")
    test("16.3 变体—本来+转弯", len(s16b.emotional_drifts) > 0, str(s16b.emotional_drifts))
    
    # 🆕 17. 期待落空
    print("\n[17] 期待落空—自己按回去了")
    s17 = rf.extract("我以为你会说点别的……没事，这样也挺好。")
    test("17.1 检测到期待落空", len(s17.expectation_letdowns) > 0 or len(s17.emotional_drifts) > 0, 
          f"letdown:{s17.expectation_letdowns} drift:{s17.emotional_drifts}")
    test("17.2 movement=推远", _determine_movement(s17) == "推远")
    
    # 🆕 18. 僵化
    print("\n[18] 僵化/解离—情绪冻住了")
    s18 = rf.extract("也还好吧。没什么，就这样吧。")
    test("18.1 检测到僵化", len(s18.petrification_signs) > 0, str(s18.petrification_signs))
    test("18.2 movement=推远", _determine_movement(s18) == "推远")
    test("18.3 有key_moment", _identify_key_moment(s18) is not None)
    
    # 🆕 19. 复合信号—试探+自我觉察
    print("\n[19] 复合信号—试探发起+自我觉察")
    s19 = rf.extract("（我在想是不是不该说这个。）算了，也许你会觉得我怪怪的。")
    test("19.1 检测到自我觉察", len(s19.self_awareness_moments) > 0, str(s19.self_awareness_moments))
    test("19.2 检测到试探", len(s19.trial_launches) > 0, str(s19.trial_launches))
    test("19.3 复合key_moment", _identify_key_moment(s19) is not None and "双层暴露" in str(_identify_key_moment(s19)))
    
    # 🆕 20. 僵化 vs 推开区别（关键测试）
    print("\n[20] 僵化≠推开")
    # 僵化："也还好吧" — 语气平，不像推开那样有攻击性
    s20a = rf.extract("也还好吧，说不清楚。")
    test("20.1 检测为僵化而非推开", 
          len(s20a.petrification_signs) > 0 and len(s20a.distancing_actions) == 0,
          f"p:{s20a.petrification_signs} d:{s20a.distancing_actions}")
    
    # 推开："走开" — 有意的
    s20b = rf.extract("走开。别管我。")
    test("20.2 检测为推开而非僵化", 
          len(s20b.distancing_actions) > 0,
          str(s20b.distancing_actions))

    # 🆕 22. 句间结构——鸡鸣寺樱花（setup-invitation）
    print("\n[22] 句间结构—setup-invitation（陈述→邀请）")
    s22 = rf.extract("鸡鸣寺的樱花开了。你要和我一起去看看吗？")
    test("22.1 检测到句间结构", len(s22.sentence_structures) > 0, str(s22.sentence_structures))
    test("22.2 movement=拉近", _determine_movement(s22) == "拉近")
    test("22.3 有key_moment", _identify_key_moment(s22) is not None)

    # 🆕 23. 句间结构——迂回暴露
    print("\n[23] 句间结构—indirect-exposure（绕一圈再暴露）")
    s23 = rf.extract("今天天气挺好的。其实我昨天晚上梦见你了。")
    test("23.1 检测到句间结构", len(s23.sentence_structures) > 0, str(s23.sentence_structures))
    test("23.2 movement=拉近", _determine_movement(s23) == "拉近")
    test("23.3 有key_moment", _identify_key_moment(s23) is not None)

    # 🆕 24. 句间结构——自我对话
    print("\n[24] 句间结构—self-dialogue（自问自答）")
    s24 = rf.extract("是不是我想太多了？可能是吧。")
    test("24.1 检测到句间结构", len(s24.sentence_structures) > 0, str(s24.sentence_structures))
    test("24.2 movement=拉近", _determine_movement(s24) == "拉近")
    test("24.3 有key_moment", _identify_key_moment(s24) is not None)

    # 🆕 25. 句间结构——条件依附
    print("\n[25] 句间结构—条件依附（S2让S1失去独立意义）")
    s25 = rf.extract("外面的樱花开了。可惜你不在，也没什么意思。")
    test("25.1 检测到句间结构", len(s25.sentence_structures) > 0, str(s25.sentence_structures))
    test("25.2 movement=拉近", _determine_movement(s25) == "拉近")
    test("25.3 有key_moment", _identify_key_moment(s25) is not None)

    # 🆕 26. 单句不应触发句间结构
    print("\n[26] 单句不触发句间结构")
    s26 = rf.extract("你要不要和我一起去看樱花？")
    test("26.1 单句无句间结构", len(s26.sentence_structures) == 0, str(s26.sentence_structures))
    # 但单句本身仍可以检测到暖意/试探
    test("26.2 单句无句间结构也无词级信号——正确：意义在句间，不在词里", not s26.has_any_signal(), str(s26.describe()))

    # ─── 集成测试：ingest 不会崩溃 ───
    print("\n[21] ingest 集成—不崩溃")
    try:
        r = rf.ingest("我想了想，刚才确实是我错了。你累了就早点睡，别太累了。")
        test("21.1 ingest 无异常", True)
        test("21.2 返回了 signal", "signals" in r)
        test("21.3 返回了 actions", "actions" in r)
    except Exception as e:
        test("21.1 ingest 无异常", False, str(e))
    
    total = passed + failed
    print(f"\n{'='*60}")
    print(f"  通过: {passed}/{total}  |  失败: {failed}/{total}")
    print(f"  📊 覆盖: 16类信号（原有8类 + 新增7类 + 句间结构4模板）")
    print(f"{'='*60}")
