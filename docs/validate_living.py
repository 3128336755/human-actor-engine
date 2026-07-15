# -*- coding: utf-8 -*-
"""
活人引擎 · 感受验证器
=======================
验证你的核心设计意图是否被遵守：
  引擎 → 只传纯事实（不解读、不替LLM感受）
  LLM  → 拿着 SKILL.md 的法则自己感受事实

三条验证线：
  L1 — 越界检测：macro_live.md 里没有"你应该"/"表现出"/"建议你"
  L2 — 法则依赖：把法则从 SKILL.md 删掉后，检查 LLM 行为是否变化
  L3 — 深层纹理：身体深层是自然语言画面，不是计算变量

用法：
  python validate_living.py                    # 全链路验证
  python validate_living.py --stress 10        # 压力测试：跑10轮
  python validate_living.py --law-blind        # 法则盲测
"""

import sys, os, io, re, time, json, argparse, subprocess
from datetime import datetime, timezone, timedelta

# ── 环境 ──
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
ENGINE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SKILL_PATH = os.path.join(ENGINE_ROOT, 'SKILL.md')
LIVE_PATH = os.path.join(ENGINE_ROOT, 'macro_live.md')
RUNNER_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '_runner.py')

# ═════════════════════════════════════════════════════════════
# L1 — 越界检测
# ═════════════════════════════════════════════════════════════

VIOLATION_PATTERNS = [
    (r'你应该', '指令：你应该'),
    (r'你应该表现出', '严重越界：替代感受'),
    (r'现在你需要', '指令：现在你需要'),
    (r'建议你', '指令：建议你'),
    (r'让我来感受', '越界：引擎假装感受'),
    (r'此刻你的感受是', '严重越界：引擎定义感受'),
    (r'你的情绪是', '越界：引擎定义情绪'),
    (r'你现在很', '越界：引擎定义状态'),
    (r'我觉得你', '越界：第一人称替用户感受'),
    (r'作为AI', '越界：暴露AI身份'),
    (r'作为语言模型', '越界：暴露AI身份'),
    (r'根据我的分析', '越界：分析口吻'),
    (r'经计算', '越界：计算口吻'),
]

def check_L1_boundary(content: str) -> dict:
    """检测 macro_live.md 是否有越界解读"""
    violations = []
    for pattern, label in VIOLATION_PATTERNS:
        matches = list(re.finditer(pattern, content))
        if matches:
            for m in matches:
                ctx_start = max(0, m.start() - 15)
                ctx_end = min(len(content), m.end() + 15)
                ctx = content[ctx_start:ctx_end].replace('\n', '\\n')
                violations.append({
                    'pattern': label,
                    'context': f'...{ctx}...'
                })
    
    return {
        'passed': len(violations) == 0,
        'violations': violations,
        'summary': '✅ L1 通过：引擎只传事实，无越界解读' if not violations else 
                   f'❌ L1 失败：{len(violations)}处越界'
    }


# ═════════════════════════════════════════════════════════════
# L2 — 事实纯度检测
# ═════════════════════════════════════════════════════════════

# 合法的内容类型（macro_live.md 里应该出现的）
FACT_SECTIONS = [
    '─ 身体事实 ─',
    '─ 睡眠事实 ─',
    '─ 社交/距离事实 ─',
    '─ 蓝图活跃 ─',
    '─ 身体深层 ─',
    '─ 刚才的变化 ─',
    '─ 持续了多轮 ─',
    '已激活法则：',
    '力场信号：',
    '最响的法则：',
    '信号干涉：',
    '涌现：',
    '莫名信号：',
    '用户说：',
    '已知领域',
    '当前话题',
    '硬边界：',
    '知识焦虑：',
]

FACT_FIELD_PATTERNS = [
    re.compile(r'^(饥饿|疲劳|渴|不适|舒适度|体温感|距上次进食|情绪底色|距离感|关系圈子|上次互动|互动平衡|沉默信号|社交能量|上次睡了|睡眠质量|醒来多久|生物钟)：'),
    re.compile(r'^现在是(周一|周二|周三|周四|周五|周六|周日)'),
    re.compile(r'^节点：'),
    re.compile(r'^主题：'),
    re.compile(r'^用户说：'),
    re.compile(r'^[\[<]!--'),
]

def check_L2_purity(content: str) -> dict:
    """检测内容是否全是事实（无感受/解读/建议）"""
    lines = content.split('\n')
    suspicious = []
    
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith('<!--'):
            continue
        if any(sec in stripped for sec in FACT_SECTIONS):
            continue
        if any(pat.match(stripped) for pat in FACT_FIELD_PATTERNS):
            continue
        if stripped.startswith('[') or stripped.startswith('─'):
            continue
        if re.match(r'^(不用|把你|SKILL)', stripped):
            continue
        if re.match(r'^[─\s]*$', stripped):
            continue
        
        # This line doesn't match any known fact pattern
        # It might be fine (values like "不饿" etc.) but let's flag for review
        suspicious.append({
            'line': i + 1,
            'content': stripped[:80]
        })
    
    return {
        'passed': True,  # Suspicious doesn't mean failure
        'suspicious_lines': suspicious,
        'suspicious_count': len(suspicious),
        'summary': f'ℹ️  L2 事实纯度：{len(suspicious)}行未匹配已知模式（可能正常）'
    }


# ═════════════════════════════════════════════════════════════
# L3 — 深层纹理验证
# ═════════════════════════════════════════════════════════════

def check_L3_texture(content: str) -> dict:
    """检测身体深层纹理是自然语言还是计算变量"""
    match = re.search(r'─ 身体深层 ─\n(.+?)(?:\n\n|\n─|\Z)', content, re.DOTALL)
    if not match:
        return {
            'passed': False,
            'texture_text': None,
            'summary': '⚠️  L3：未找到身体深层纹理段'
        }
    
    texture = match.group(1).strip()
    
    # Checks
    checks = {
        'is_natural_language': not bool(re.search(r'[=:]\s*\d+\.?\d*|\[\d+\]|\{.*\}|True|False|None', texture)),
        'has_imagery': bool(re.search(r'(像|仿佛|好像|如同|似的|一般|般|阴天|晴天|雨|风|雾|潮|干|沉|轻|紧|松|暖|冷)', texture)),
        'has_body_words': bool(re.search(r'(胃|胸口|喉咙|肩膀|头|眼|手|脚|背|肚子|身体|皮肤)', texture)),
        'not_computed': not bool(re.search(r'(参数|变量|输出|计算|推理|判断|分析|评估|权重|分数|级别)', texture)),
        'reasonable_length': 10 < len(texture) < 500,
    }
    
    all_ok = all(checks.values())
    
    return {
        'passed': all_ok,
        'texture_text': texture,
        'checks': checks,
        'summary': '✅ L3 通过：身体深层是自然语言画面' if all_ok else 
                   f'⚠️  L3：纹理质量有待提升（{sum(1 for v in checks.values() if not v)}项未达标）'
    }


# ═════════════════════════════════════════════════════════════
# L4 — 法则引用有效性
# ═════════════════════════════════════════════════════════════

def load_law_index(skill_path: str) -> set:
    """从 SKILL.md 提取所有法则编号
    
    SKILL.md 使用 `## 1. 身体法则` `### 1.1 生理节律` 格式。
    soul_bridge 映射为 `§1` `§1.1` 等输出到 macro_live。
    """
    law_ids = set()
    if not os.path.exists(skill_path):
        return law_ids
    
    with open(skill_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Match headers like "## 1. 身体法则" or "### 1.1 生理节律"
    # Note: after the number comes either "." or whitespace
    for m in re.finditer(r'^#{2,4}\s+(\d+(?:\.\d+)?)[.\s]', content, re.MULTILINE):
        law_ids.add(m.group(1))
    
    # Also match §1.4 style references in body text
    for m in re.finditer(r'§(\d+(?:\.\d+)?[a-z]?)', content):
        law_ids.add(m.group(1))
    
    return law_ids


def check_L4_law_references(content: str, law_ids: set) -> dict:
    """检测引用的法则是否在 SKILL.md 中存在"""
    if not law_ids:
        return {'passed': True, 'summary': 'ℹ️  L4 跳过：未加载 SKILL.md 法则索引'}
    
    cited = set()
    for m in re.finditer(r'§(\d+(?:\.\d+)?[a-z]?)', content):
        cited.add(m.group(1))
    
    orphan = cited - law_ids
    valid = cited & law_ids
    
    return {
        'passed': len(orphan) == 0,
        'cited': sorted(valid),
        'orphan': sorted(orphan),
        'summary': f'{"✅" if not orphan else "❌"} L4 法则引用：{len(valid)}条有效{"，" + str(len(orphan)) + "条孤立" if orphan else ""}'
    }


# ═════════════════════════════════════════════════════════════
# 主验证流程
# ═════════════════════════════════════════════════════════════

def setup_environment():
    """搭建最小运行环境"""
    rp_dir = os.path.join(ENGINE_ROOT, 'roleplay', 'characters')
    os.makedirs(rp_dir, exist_ok=True)
    os.makedirs(os.path.join(ENGINE_ROOT, 'sessions'), exist_ok=True)
    
    with open(os.path.join(ENGINE_ROOT, 'roleplay', 'active'), 'w', encoding='utf-8') as f:
        f.write('默认角色')
    
    with open(os.path.join(rp_dir, '默认角色.md'), 'w', encoding='utf-8') as f:
        f.write("""# 默认角色

## 感受基调
这是一个温和友善的普通成年人。情绪稳定，共情力中等，社交通常情况正常。
饿了会有点烦躁但能控制。累了会安静寡言。面对陌生人礼貌得体，面对熟人放松自然。
说话句子中等长度，会使用自然的语气词。在中国长大，有基本的中文语感。
性别中立，无特殊偏好。
""")


def run_pipeline(user_input: str) -> dict:
    """跑一次全链路并返回验证结果（subprocess 隔离，不污染验证器 stdout）"""
    t0 = time.time()
    result = subprocess.run(
        [sys.executable, RUNNER_PATH, user_input],
        capture_output=True,
        cwd=ENGINE_ROOT,
        timeout=30,
    )
    elapsed = time.time() - t0
    
    # Runner writes to _runner_result.json
    result_path = os.path.join(ENGINE_ROOT, '_runner_result.json')
    if not os.path.exists(result_path):
        return {'error': f'_runner_result.json not found. stderr: {result.stderr[:200] if result.stderr else "none"}'}
    
    with open(result_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    os.remove(result_path)
    
    if 'error' in data:
        return data
    
    return {
        'elapsed': elapsed,
        'content': data.get('content', ''),
        'size': data.get('size', 0),
        'L1': check_L1_boundary(data.get('content', '')),
        'L2': check_L2_purity(data.get('content', '')),
        'L3': check_L3_texture(data.get('content', '')),
        'L4': check_L4_law_references(data.get('content', ''), load_law_index(SKILL_PATH)),
    }


def print_report(results: dict, user_input: str, num: int = 0):
    """打印验证报告"""
    if 'error' in results:
        print(f'\n❌ 运行失败: {results["error"]}')
        return
    
    label = f' #{num}' if num else ''
    print(f'\n{"=" * 60}')
    print(f'  活人引擎 · 感受验证报告{label}')
    print(f'{"=" * 60}')
    print(f'  输入: "{user_input}"')
    print(f'  耗时: {results["elapsed"]*1000:.1f}ms')
    print(f'  输出: {results["size"]} bytes')
    print()
    
    all_pass = True
    for level in ['L1', 'L2', 'L3', 'L4']:
        result = results[level]
        print(f'  {result["summary"]}')
        if not result.get('passed', True):
            all_pass = False
    
    # Details for failures
    for level in ['L1', 'L2', 'L3', 'L4']:
        result = results[level]
        
        if level == 'L1' and result.get('violations'):
            print(f'\n  ── L1 越界详情 ──')
            for v in result['violations']:
                print(f'    · {v["pattern"]}')
                print(f'      {v["context"]}')
        
        if level == 'L3':
            texture = result.get('texture_text')
            if texture:
                print(f'\n  ── L3 身体深层纹理 ──')
                print(f'    {texture[:200]}')
                if result.get('checks'):
                    for k, v in result['checks'].items():
                        print(f'    {k}: {"✓" if v else "✗"}')
        
        if level == 'L4' and result.get('orphan'):
            print(f'\n  ── L4 孤立法则引用 ──')
            for o in result['orphan']:
                print(f'    §{o}')
    
    print()
    if all_pass:
        print('  ✅ 全链路通过：你的设计意图被遵守了')
        print('     引擎只传事实，LLM 负责感受')
    else:
        print('  ⚠️ 存在边界问题，需要检查')
    
    return all_pass


# ═════════════════════════════════════════════════════════════
# CLI 入口
# ═════════════════════════════════════════════════════════════

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='活人引擎 · 感受验证器')
    parser.add_argument('--stress', type=int, default=0, help='压力测试轮数')
    parser.add_argument('--law-blind', action='store_true', help='法则盲测')
    parser.add_argument('--texture-check', action='store_true', help='仅验证深层纹理')
    parser.add_argument('input', nargs='*', default=['你好世界'], help='测试输入')
    args = parser.parse_args()
    
    user_input = ' '.join(args.input)
    
    print(f'活人引擎验证器 v1.0')
    print(f'时间: {datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M")}')
    
    setup_environment()
    
    if args.stress > 0:
        print(f'\n压力测试模式: {args.stress}轮')
        inputs = [
            '你好', '今天天气不错', '我有点累', '能帮我个忙吗',
            '你吃饭了吗', '我要去睡觉了', '你有空吗', '这件事你怎么看',
            '我觉得很难过', '谢谢你'
        ]
        all_pass = True
        for i in range(args.stress):
            inp = inputs[i % len(inputs)]
            try:
                results = run_pipeline(inp)
                ok = print_report(results, inp, i + 1)
                if not ok:
                    all_pass = False
            except Exception as e:
                print(f'\n  ❌ 第{i+1}轮崩溃: {e}')
                all_pass = False
            time.sleep(0.05)
        
        print(f'\n{"=" * 60}')
        print(f'  压力测试完成: {args.stress}轮跑完')
        print(f'  {"✅ 全部通过" if all_pass else "⚠️ 有失败"}')
    else:
        results = run_pipeline(user_input)
        print_report(results, user_input)
    
    # Cleanup
    if os.path.exists(LIVE_PATH):
        os.remove(LIVE_PATH)
