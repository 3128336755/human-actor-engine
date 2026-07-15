# session_manager.py — 角色会话持久化
#
# 用法（手动模式，当前 webchat 环境）：
#   from session_manager import get_session, save_session
#   sess = get_session('xiaonuan')
#   ctx = sess.tick(user_input)  # → 自然语言上下文
#   # ... 我用 ctx 来写回复 ...
#   save_session(sess)

import json, os, sys, time
from dataclasses import dataclass, field

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from context_injector import ContextInjector

SESSION_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'sessions')
os.makedirs(SESSION_DIR, exist_ok=True)


def get_session(name: str, persona: str = 'default'):
    """加载或创建角色会话"""
    path = os.path.join(SESSION_DIR, f'char_{name}.json')
    ci = ContextInjector(persona=persona)
    
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        ci.tick_count = data.get('ticks', 0)
        ci.bridge.tick_number = data.get('ticks', 0)  # sync
        ci.ls = _restore_soul(ci.ls, data.get('soul_state', {}))
    
    ci._name = name
    ci._persona = persona
    return ci


def save_session(ci: ContextInjector):
    """保存角色会话"""
    path = os.path.join(SESSION_DIR, f'char_{ci._name}.json')
    data = {
        'name': ci._name,
        'persona': ci._persona,
        'ticks': ci.tick_count,
        'last_saved': time.strftime('%Y-%m-%d %H:%M:%S'),
        'soul_state': _dump_soul(ci.ls),
    }
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _dump_soul(ls):
    """提取 living_soul 的关键状态"""
    state = {}
    try:
        state['mood'] = ls.moment.get('mood', '')
        state['mood_intensity'] = ls.moment.get('mood_intensity', '')
        state['hunger'] = getattr(ls.body, 'hunger', '')
        state['fatigue'] = getattr(ls.body, 'fatigue', '')
        state['social_energy'] = getattr(ls.body, 'social_energy', '')
    except:
        pass
    
    # 记忆引擎状态
    try:
        mem = ls.memories
        if hasattr(mem, 'to_dict'):
            state['memory_count'] = len(mem.to_dict().get('episodes', []))
    except:
        state['memory_count'] = 0
    
    return state


def _restore_soul(ls, saved):
    """恢复 living_soul 的关键状态"""
    try:
        if 'mood' in saved:
            ls.moment['mood'] = saved['mood']
        if 'mood_intensity' in saved:
            ls.moment['mood_intensity'] = saved['mood_intensity']
        if 'hunger' in saved and hasattr(ls.body, 'hunger'):
            ls.body.hunger = saved['hunger']
        if 'fatigue' in saved and hasattr(ls.body, 'fatigue'):
            ls.body.fatigue = saved['fatigue']
        if 'social_energy' in saved and hasattr(ls.body, 'social_energy'):
            ls.body.social_energy = saved['social_energy']
    except:
        pass
    return ls


if __name__ == '__main__':
    import sys
    name = sys.argv[1] if len(sys.argv) > 1 else 'xiaonuan'
    msg = sys.argv[2] if len(sys.argv) > 2 else '你好'
    
    ci = get_session(name)
    ctx = ci.tick_and_inject(msg)
    print(ctx)
    save_session(ci)
    print(f'\n[Ticks: {ci.tick_count}]')
