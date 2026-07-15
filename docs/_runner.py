# -*- coding: utf-8 -*-
"""validate_living 的子进程 runner

用法: python _runner.py "用户输入"
结果写入 _runner_result.json（不通过 stdout，避开 complexity_engine 的打印）
"""

import sys, os, json

def main():
    if len(sys.argv) < 2:
        json.dump({'error': 'No input'}, open('_runner_result.json', 'w', encoding='utf-8'))
        sys.exit(1)
    
    user_input = sys.argv[1]
    engine_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    sys.path.insert(0, engine_root)
    sys.path.insert(0, os.path.join(engine_root, 'engine'))
    
    # Setup minimal runtime
    rp_dir = os.path.join(engine_root, 'roleplay', 'characters')
    os.makedirs(rp_dir, exist_ok=True)
    os.makedirs(os.path.join(engine_root, 'sessions'), exist_ok=True)
    with open(os.path.join(engine_root, 'roleplay', 'active'), 'w', encoding='utf-8') as f:
        f.write('默认角色\n')
    with open(os.path.join(rp_dir, '默认角色.md'), 'w', encoding='utf-8') as f:
        f.write('# 默认角色\n## 感受基调\n温和友善\n')
    
    try:
        from macro_inject import main as inject_main
        sys.argv = ['macro_inject.py', user_input]
        inject_main()
        
        live_path = os.path.join(engine_root, 'macro_live.md')
        if not os.path.exists(live_path):
            result = {'error': 'macro_live.md not generated'}
        else:
            with open(live_path, 'r', encoding='utf-8') as f:
                content = f.read()
            result = {'content': content, 'size': len(content)}
            # Clean up
            os.remove(live_path)
    except Exception as e:
        result = {'error': f'{type(e).__name__}: {e}'}
    
    out_path = os.path.join(engine_root, '_runner_result.json')
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False)

if __name__ == '__main__':
    main()
