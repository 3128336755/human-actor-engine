# -*- coding: utf-8 -*-
"""
活人系统 · 独立入口
用法: python run_human_engine.py "<用户说的话>"
输出: macro_live.md（LLM 可读的上下文）

不依赖特定平台环境变量，只需要：
  - Python 3.9+
  - workspace 下有完整的 engine/ + soul_bridge.py + macro_triangle.py + ...
"""
import sys, os, json, time, traceback

WORKSPACE = os.path.dirname(os.path.abspath(__file__))
ENGINE_DIR = os.path.join(WORKSPACE, 'engine')
sys.path.insert(0, WORKSPACE)

# ============================================================
# 1. 验证文件完整性
# ============================================================
REQUIRED = [
    'engine/body_core.py',
    'engine/distance_ledger.py',
    'engine/memory_law34.py',
    'engine/learning_engine.py',
    'engine/complexity_engine.py',
    'engine/engine_hub.py',
    'engine/human_topology.py',
    'soul_bridge.py',
    'living_soul.py',
    'triangle_runtime.py',
    'macro_triangle.py',
    'macro_inject.py',
    'roleplay/active',
]

missing = []
for f in REQUIRED:
    if not os.path.exists(os.path.join(WORKSPACE, f)):
        missing.append(f)

if missing:
    print("ERROR: 缺少文件:")
    for m in missing:
        print(f"  - {m}")
    sys.exit(1)

# ============================================================
# 2. 获取用户输入
# ============================================================
if len(sys.argv) < 2:
    print("用法: python run_human_engine.py \"<用户说的话>\"")
    sys.exit(1)

user_input = ' '.join(sys.argv[1:])

# ============================================================
# 3. 初始化引擎
# ============================================================
print("[活人引擎] 冷启动...")

try:
    import macro_triangle as mt
    mci = mt.get_macro_session('live')
    print(f"[活人引擎] 初始化完成")
except Exception as e:
    print(f"[活人引擎] 初始化失败: {e}")
    traceback.print_exc()
    sys.exit(1)

# ============================================================
# 4. 运行全链路
# ============================================================
print(f"[活人引擎] 输入: {user_input[:50]}...")

try:
    t0 = time.time()
    mci.tick_and_inject(user_input)
    elapsed = time.time() - t0
    tick = mci.last_tick
    print(f"[活人引擎] tick={tick.tick} | {elapsed:.3f}s")
except Exception as e:
    print(f"[活人引擎] 运行失败: {e}")
    traceback.print_exc()
    sys.exit(1)

# ============================================================
# 5. 输出 macro_live.md
# ============================================================
live_path = os.path.join(WORKSPACE, 'macro_live.md')
if os.path.exists(live_path):
    with open(live_path, 'r', encoding='utf-8') as f:
        content = f.read()
    print("\n" + "=" * 60)
    print("  MACRO_LIVE.MD")
    print("=" * 60)
    for line in content.split('\n'):
        if line.strip() and not line.strip().startswith('<!--'):
            print(f"  {line}")
    print("=" * 60)
else:
    print("ERROR: macro_live.md 未生成")
    sys.exit(1)

# ============================================================
# 6. 诊断输出（可选）
# ============================================================
if '--debug' in sys.argv:
    eng = tick.engine_state
    print("\n[DEBUG] engine_state keys:", sorted(eng.keys()))
    for ns in ['hunger','fatigue','mood','social_energy','last_sleep_hours',
               'distance_signals','interaction_balance','silence_risk']:
        print(f"  {ns} = {eng.get(ns, 'N/A')}")
    
    learn = eng.get('learning', {})
    print(f"\n[DEBUG] learning:")
    for k, v in learn.items():
        if isinstance(v, list):
            print(f"  {k}: [{len(v)} items]")
        else:
            print(f"  {k}: {v}")
    
    bp = tick.blueprint_state
    print(f"\n[DEBUG] blueprint: hot_count={bp.get('hot_count')}, "
          f"theme={bp.get('dominant_theme','')[:40]}")
