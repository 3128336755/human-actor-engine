# macro_inject.py — 三体运行时注入器
# 每次对话前跑一轮 tick，产出自适应上下文
# 复杂时刻给详细，简单时刻给寥寥几句
# 写入 macro_live.md → 随 HEARTBEAT.md 同位置加载
#
# Python的边界：只传事实现状，不翻译、不感受、不碰SKILL.md。
# LLM拿着SKILL.md的法则自己感受事实。

import sys, os, json
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from macro_triangle import MacroContextInjector, get_macro_session, save_macro_session

WORKSPACE = os.path.dirname(os.path.abspath(__file__))
OUTPUT_FILE = os.path.join(WORKSPACE, 'macro_live.md')
SESSION_FILE = os.path.join(WORKSPACE, 'sessions', 'macro_main.json')
ROLEPLAY_ACTIVE = os.path.join(WORKSPACE, 'roleplay_active')
DEFAULT_NAME = '角色卡中的名字'
SKILL_MD_PATH = os.path.join(WORKSPACE, 'SKILL.md')


def _active_persona() -> str:
    """读取当前激活的角色名。没有激活→默认角色卡中的名字。"""
    if os.path.exists(ROLEPLAY_ACTIVE):
        try:
            with open(ROLEPLAY_ACTIVE, 'r', encoding='utf-8-sig') as f:
                name = f.read().strip()
                if name:
                    return name
        except Exception:
            pass
    return DEFAULT_NAME


def _get_now_beijing() -> datetime:
    return datetime.now(timezone(timedelta(hours=8)))


def _time_of_day(hour: float) -> str:
    h = hour
    if h < 5:    return "凌晨"
    elif h < 7:  return "清晨"
    elif h < 9:  return "早上"
    elif h < 12: return "上午"
    elif h < 13: return "中午"
    elif h < 17: return "下午"
    elif h < 19: return "傍晚"
    elif h < 22: return "晚上"
    else:        return "深夜"


def main():
    if len(sys.argv) > 1:
        user_input = sys.argv[1]
    else:
        user_input = sys.stdin.read().strip() or '(无输入)'
    
    # 回流管道：上一轮 LLM 的回应（可选）
    llm_response = ''
    if len(sys.argv) > 2:
        llm_response = sys.argv[2]

    now = _get_now_beijing()
    current_hour = now.hour + now.minute / 60.0
    time_label = _time_of_day(current_hour)
    weekday_name = ['周一','周二','周三','周四','周五','周六','周日'][now.weekday()]

    mci = get_macro_session('main')
    ctx = mci.tick_and_inject(user_input, llm_response=llm_response)
    save_macro_session(mci)

    tick = mci.last_tick
    eng = tick.engine_state
    bp = tick.blueprint_state
    br = tick.bridge_state

    # ── 引擎事实：原样输出，不翻译。LLM拿着SKILL.md自己感受。──
    hunger = eng.get('hunger', '不饿')
    fatigue = eng.get('fatigue', '不累')
    thirst = eng.get('thirst', '不渴') if eng.get('thirst', '') else ''
    mood = eng.get('mood', '平静')
    comfort = eng.get('comfort', '')
    temperature = eng.get('temperature_feel', '')
    discomforts = eng.get('active_discomforts', [])
    social_energy = eng.get('social_energy', '')
    last_sleep_quality = eng.get('last_sleep_quality', '')
    last_sleep_hours = eng.get('last_sleep_hours', '')
    hours_since_woke = eng.get('hours_since_woke', '')
    hours_since_meal = eng.get('hours_since_last_meal', '')
    distance = eng.get('distance', '')
    circle = eng.get('circle', '')
    last_contact = eng.get('last_contact', '')
    interaction_balance = eng.get('interaction_balance', '')
    silence_risk = eng.get('silence_risk', '')

    # ── 蓝图信号 ──
    hot_count = bp.get('hot_count', 0)
    top_nodes = bp.get('top_activated_cluster', [])
    node_ids = [str(n) for n, _ in top_nodes[:5]] if top_nodes else []
    dominant = bp.get('dominant_theme', '')

    # ── 学习状态 ──
    learning = eng.get('learning', {})
    known_count = learning.get('known_domains', 0)
    total_domains = learning.get('total_domains', 0)
    doms = learning.get('knowledge_domains', [])
    topic_analysis = learning.get('topic_analysis')
    hard_bounds = learning.get('hard_boundaries', {})

    # ── 角色注入 ──
    persona_name = _active_persona()

    # ── 生成 macro_live.md：只给事实，不给感受 ──
    lines = []
    lines.append(f'[你是"{persona_name}"。这是第{tick.tick}轮对话。]')
    lines.append('')
    lines.append('─ 身体事实 ─')
    lines.append(f'现在是{weekday_name}{time_label}{now.hour:02d}:{now.minute:02d}')
    circadian_raw = eng.get('circadian_feel', '')
    if circadian_raw:
        lines.append(f'生物钟：{circadian_raw}')
    lines.append(f'饥饿：{hunger}')
    if thirst and thirst != '不渴':
        lines.append(f'渴：{thirst}')
    lines.append(f'疲劳：{fatigue}')
    if discomforts:
        lines.append(f'不适：{"、".join(discomforts[:3])}')
    if comfort and comfort != '还行':
        lines.append(f'舒适度：{comfort}')
    if temperature and temperature != '刚好':
        lines.append(f'体温感：{temperature}')
    if hours_since_meal:
        lines.append(f'距上次进食：{hours_since_meal}')
    lines.append('')
    lines.append('─ 睡眠事实 ─')
    if last_sleep_hours:
        lines.append(f'上次睡了：{last_sleep_hours}')
    if last_sleep_quality:
        lines.append(f'睡眠质量：{last_sleep_quality}')
    if hours_since_woke:
        lines.append(f'醒来多久：{hours_since_woke}')
    lines.append('')
    lines.append('─ 社交/距离事实 ─')
    if mood and mood != '平静':
        lines.append(f'情绪底色：{mood}')
    if distance:
        lines.append(f'距离感：{distance}')
    if circle:
        lines.append(f'关系圈子：{circle}')
    if last_contact and last_contact not in ('不记得了', ''):
        lines.append(f'上次互动：{last_contact}')
    if interaction_balance and '没有互动' not in interaction_balance:
        lines.append(f'互动平衡：{interaction_balance}')
    if silence_risk:
        lines.append(f'沉默信号：{silence_risk}')
    if social_energy and social_energy != '正常' and social_energy != '满的':
        lines.append(f'社交能量：{social_energy}')
    lines.append('')
    lines.append('─ 蓝图活跃 ─')
    if node_ids:
        lines.append(f'节点：§{", §".join(node_ids)}')
    else:
        lines.append('节点：无')
    if dominant:
        lines.append(f'主题：{dominant}')
    lines.append('')
    # ── 学习状态 ──
    if doms:
        named = ', '.join(d['domain'] for d in doms[:5] if d.get('domain'))
        if named:
            lines.append(f'已知领域({known_count}/{total_domains})：{named}。')
    if topic_analysis:
        if topic_analysis.get('best_match_domain'):
            lines.append(f'当前话题属于：{topic_analysis["best_match_domain"]}（掌握程度：{topic_analysis.get("level","未知")}）')
        elif topic_analysis.get('status') == 'REFUSED':
            lines.append(f'当前话题是硬边界（{topic_analysis.get("reason","")}），不讨论。')
        elif topic_analysis.get('status') == '未知领域':
            lines.append('当前话题：陌生领域，没接触过。')
    if hard_bounds.get('refused_domains'):
        refused = ', '.join(r['domain'] for r in hard_bounds['refused_domains'][:3])
        lines.append(f'硬边界：{refused}')
    # 知识焦虑
    anxiety = learning.get('knowledge_anxiety', {})
    anxiety_level = anxiety.get('anxiety_level', '')
    if anxiety_level and '很低' not in anxiety_level:
        lines.append(f'知识焦虑：{anxiety_level}')
    if doms or topic_analysis or hard_bounds.get('refused_domains'):
        lines.append('')
    
    # ── 桥梁法则：只给律号和名字。内容在SKILL.md里，LLM自己读。──
    delegs = br.get('top_delegations', [])
    if delegs:
        law_names = [d.get('law_name','') or f'§{d.get("law_id","")}' for d in delegs[:8]]
        lines.append(f'已激活法则：{", ".join(f for f in law_names if f)}')
    lines.append('')
    
    # ── 力场信号：哪条法则被最多信号推到、多少通道在跑──
    force_count = br.get('force_signals_count', 0)
    force_loudest = br.get('force_loudest', [])
    force_interference = br.get('force_interference', 0)
    force_emergent = br.get('force_emergent', [])
    force_unexplained = br.get('force_unexplained', False)
    if force_count > 0:
        lines.append(f'力场信号：{force_count}个信号')
        if force_loudest:
            lines.append(f'最响的法则：{", ".join(str(f) for f in force_loudest[:3])}')
        if force_interference > 0:
            lines.append(f'信号干涉：{force_interference}处')
        if force_emergent:
            lines.append(f'涌现：{"; ".join(str(e) for e in force_emergent[:3])}')
        if force_unexplained:
            lines.append('莫名信号：有——不知道为什么但身体感觉到了')
        lines.append('')
    
    # ── 活人深层纹理（living_soul 原文）──
    deep_feel = br.get('deep_body_feel', '')
    if deep_feel and deep_feel.strip():
        lines.append('─ 身体深层 ─')
        # 截断过长文本，但不改内容
        if len(deep_feel) > 400:
            deep_feel = deep_feel[:400] + '…'
        lines.append(deep_feel)
        lines.append('')
    
    # ── 模糊变化感知：只给"什么变了"。方向/严重程度由LLM+SKILL.md §60判断。──
    fuzzy_delta = br.get('fuzzy_delta', {})
    changes = fuzzy_delta.get('changes', [])
    persistences = fuzzy_delta.get('state_persistences', br.get('state_persistences', []))
    if changes:
        lines.append('─ 刚才的变化 ─')
        for c in changes[:6]:
            if 'from' in c:
                lines.append(f'  {c["field"]}从「{c["from"]}」变为「{c["to"]}」')
            else:
                lines.append(f'  新发：{c["field"]}→{c["to"]}')
        lines.append('')
    if persistences:
        staying = [p for p in persistences if p["ticks"] >= 3]
        if staying:
            lines.append('─ 持续了多轮 ─')
            for p in staying[:4]:
                lines.append(f'  {p["field"]}一直是「{p["value"]}」（{p["ticks"]}轮了）')
            lines.append('')
    
    lines.append(f'用户说：「{user_input}」')
    lines.append('')
    lines.append('不用分析自己、不说AI术语、不用学术词。')
    lines.append('把你每件事分解到这些层次：从身体感受出发、从情绪底色出发、从你和对方的关系出发——SKILL.md是你的底层操作系统，用它理解你此刻该是什么状态。')

    live_context = '\n'.join(lines)

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write(f'<!-- macro_live: tick={tick.tick} hot={hot_count} -->\n')
        f.write(live_context)

    print(json.dumps({
        'tick': tick.tick,
        'hot_count': hot_count,
        'dominant': dominant,
    }, ensure_ascii=False))


if __name__ == '__main__':
    main()
