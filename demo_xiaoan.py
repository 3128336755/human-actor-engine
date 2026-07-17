# -*- coding: utf-8 -*-
"""
Demo: 让小安和用户聊三轮，展示引擎状态变化。
"""
import os, sys

WORKSPACE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, WORKSPACE)

import macro_triangle as mt

mci = mt.get_macro_session('live')

dialogue = [
    ("今天店里人不多。", "用户开启话题"),
    ("你好像有点累。", "用户观察并靠近"),
    ("那我先走了，你好好休息。", "用户离开"),
]

out_lines = ['# Human Actor Engine Demo：小安', '', '**角色**：小安，23岁，咖啡馆常客。', '**性格**：话少，怕吵，也怕被丢下。', '**目的**：演示同一引擎如何根据用户输入改变角色状态。', '']

for i, (user_input, note) in enumerate(dialogue, 1):
    print(f"\n{'='*60}")
    print(f"第 {i} 轮 · {note}")
    print(f"[用户] {user_input}")
    ctx = mci.tick_and_inject(user_input)
    tick = mci.last_tick

    out_lines += [f"## 第 {i} 轮：{note}", '', f"**[用户]** {user_input}", '', '```', ctx, '```', '']

    print("  ── 小安此刻的状态（节选）──")
    capture = False
    printed = 0
    for line in ctx.splitlines():
        if '─ 身体事实' in line:
            capture = True
        if capture and line.strip() and not line.startswith('<!--'):
            print(f"  {line}")
            printed += 1
        if printed >= 45:
            break

print(f"\n{'='*60}")
print("Demo 结束。完整记录已保存到 demo_output.md")

with open('demo_output.md', 'w', encoding='utf-8') as f:
    f.write('\n'.join(out_lines))
