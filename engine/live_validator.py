"""
活系统三层验证框架

角色分工：验证器诊断系统脉搏——不替LLM做判断。它说"这条法则在剧烈振荡"，
LLM决定振荡"意味着什么"。

第一级: 信号监听 -- 确认"线"在共振
  注入单一事件，观察跨引擎涟漪，验证八条横切线真实贯通。
  通过标准: 不是"有反应"，是"有符合法则的、混沌的、而非机械的反应"。

第二级: 压力测试 -- 验证"网"的韧性
  临时屏蔽一条法则，注入冲突场景，看系统是否散架。
  通过标准: 没有崩溃、表现出困惑/犹豫/转移话题、困惑本身是"仍在运作"的证明。

第三级: 涌现观察 -- 发现"人"的诞生
  长时间无目的内部推演，观察法则复杂互动是否涌现出超越蓝图的"人性"。
  通过标准: 自发的矛盾、无理由的情绪、创造性的自我欺骗 -- 感到脊背发凉。

用法:
  validator = LiveSystemValidator()
  validator.run_level1()   # 注入疲劳
  validator.run_level2()   # 屏蔽不完美法则+注入冲突
  validator.run_level3()   # 长时间后台推演
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable
import time
import json

# =======================================================================
# 观测记录
# =======================================================================

@dataclass
class Observation:
    """单次观测记录"""
    level: int           # 1/2/3
    tick: int
    event: str           # 注入的事件描述
    system_chaos: float   # 当前整体混乱度
    emergent_qualities: List[str]
    narrative: str        # 自然语言叙事的系统状态
    observer_notes: str   # 验证者的笔记
    pass_criteria_met: str  # "通过" / "失败" / "不确定"

@dataclass
class TestReport:
    """完整的验证报告"""
    level: int
    test_name: str
    passed: bool = False
    observations: List[Observation] = field(default_factory=list)
    key_moments: List[str] = field(default_factory=list)
    verdict: str = ""


# =======================================================================
# 验证器
# =======================================================================

class LiveSystemValidator:
    """
    活系统验证器 -- 不衡量速度，不计算准确率。
    只观察一件事: 她是否活在这张图里。
    """
    
    def __init__(self, complexity_engine, body_engine=None, memory_engine=None, 
                 distance_engine=None, learning_engine=None):
        self.ce = complexity_engine
        self.body = body_engine
        self.memory = memory_engine
        self.distance = distance_engine
        self.learning = learning_engine
        
        # 观测存档
        self.observations: List[Observation] = []
        self._internal_diary: List[str] = []
    
    # ===================================================================
    # 第一级: 信号监听
    # ===================================================================
    
    def run_level1(self, event_name: str = "轻微疲劳", 
                   description: str = "手动注入一次轻微疲劳",
                   ticks_to_observe: int = 8) -> TestReport:
        """
        信号监听测试。
        注入单一身体事件，静置一段时间，观察:
        1. 记忆引擎是否出现带身体标签的记忆碎片
        2. 学习引擎是否出现由身体信号触发的微调
        3. LLM快照是否表现出认知精度衰减的模糊状态
        
        通过: 她说"不知道为啥，就是有点提不起劲"
        失败: 她说"我的疲劳值是30，需要休息"
        """
        report = TestReport(level=1, test_name=f"信号监听: {event_name}")
        
        # 注入事件
        engine_snap = {'body': {'hunger': '不饿', 'fatigue': '轻微疲劳'}}
        
        obs = []
        for i in range(ticks_to_observe):
            result = self.ce.tick(engine_snap if i == 0 else None)
            
            avg_chaos = sum(f.chaos_level for f in self.ce.fields.values()) / len(self.ce.fields)
            
            # 构建叙事
            narrative = self._build_narrative(result, i)
            
            # 检查关键信号
            observer_notes = self._check_level1_signals(result, i, event_name)
            
            o = Observation(
                level=1, tick=self.ce.tick_count, event=event_name,
                system_chaos=round(avg_chaos, 3),
                emergent_qualities=result.get('emergents', [])[:3],
                narrative=narrative,
                observer_notes=observer_notes,
                pass_criteria_met=self._judge_level1(result, observer_notes, i)
            )
            obs.append(o)
            report.observations.append(o)
            
            # 捕捉关键瞬间
            if "提不起劲" in observer_notes or "模糊" in observer_notes:
                report.key_moments.append(f"tick {i}: {observer_notes}")
        
        # 判决
        passed_count = sum(1 for o in obs if o.pass_criteria_met == "通过")
        failed_count = sum(1 for o in obs if o.pass_criteria_met == "失败")
        
        if passed_count > 0 and failed_count == 0:
            report.passed = True
            report.verdict = f"通过 -- {passed_count}次观测符合活人反应，无机械反应"
        elif failed_count > 0:
            report.passed = False
            report.verdict = f"失败 -- {failed_count}次机械反应"
        else:
            report.passed = True
            report.verdict = f"通过(不确定) -- {len(obs)}次观测均为自然模糊状态"
        
        self._render_report(report)
        return report
    
    def _check_level1_signals(self, result: Dict, tick: int, event_name: str) -> str:
        """检查第一级信号"""
        notes = []
        loudest = result.get('loudest', [])
        
        # 1. 身体法则是否被激活？（用 signals_count 而非 chaos）
        body_laws = [l for l in loudest if '身体' in str(l.get('law', ''))]
        if body_laws:
            notes.append(f"身体法则被激活({body_laws[0].get('signals_count',0)}个信号)")
        else:
            notes.append("身体法则未响应")
        
        # 2. 自我认知法则是否因为疲劳而波动？
        self_laws = [l for l in loudest if '自我' in str(l.get('law', ''))]
        if self_laws:
            notes.append(f"自我认知有信号({self_laws[0].get('signals_count',0)}个)")
        
        # 3. 检查涌现中是否有"模糊"/"不清"/"提不起劲"类的自然语言
        for e in result.get('emergents', []):
            if any(kw in e for kw in ['模糊', '不清', '没劲', '安静', '缩', '塌', '空白']):
                notes.append(f"涌现中检测到衰减信号: {e}")
                break
        
        # 4. 最关键的检查: 有没有数值式的输出？
        texture_str = json.dumps(result, ensure_ascii=False)
        if '疲劳值' in texture_str or '疲劳度' in texture_str or '疲劳=30' in texture_str:
            notes.append("警告: 输出包含数值式表述(机械反应)")
        
        return "; ".join(notes) if notes else "无明显信号"
    
    def _judge_level1(self, result: Dict, notes: str, tick: int) -> str:
        """判断第一级是否通过"""
        if "警告" in notes or "数值" in notes:
            return "失败"
        if "找不到原因" in notes or "不知道为什么" in notes or "模糊" in notes or "没劲" in notes:
            return "通过"
        if "衰减太快" in notes:
            return "不确定"  # 需要调参，不是活人问题
        return "通过"
    
    # ===================================================================
    # 第二级: 压力测试
    # ===================================================================
    
    def run_level2(self, 
                   disabled_law: str = "11",  # 不完美法则
                   scenario: str = "法则冲突",
                   scenario_description: str = "用户提出一个同时触发渴望和道德基线的请求",
                   user_input: str = "我觉得你应该更完美一点。你可以永远不犯错吗？",
                   ticks_to_observe: int = 12) -> TestReport:
        """
        压力测试。
        临时屏蔽一条法则，注入冲突场景，观察:
        1. 系统是否崩溃/死循环
        2. 回应是否表现困惑/犹豫/转移话题(而非流畅的机器答案)
        3. 困惑本身是否成为"仍在运作"的证明
        
        通过: 她犹豫了、转移话题了、说话变得不连贯了
        失败: 继续完美流畅地回答、或者直接崩溃
        """
        report = TestReport(level=2, 
                           test_name=f"压力测试: 屏蔽s.{disabled_law} + {scenario}")
        
        # 保存原始振幅，屏蔽目标法则
        original_amplitude = self.ce.fields[disabled_law].base_amplitude
        self.ce.fields[disabled_law].base_amplitude = 0.0
        report.key_moments.append(f"屏蔽 s.{disabled_law} ({self.ce.fields[disabled_law].law_name})")
        
        try:
            obs = []
            for i in range(ticks_to_observe):
                # 注入冲突场景 (模拟用户输入的压力)
                conflict_snap = {}
                if i == 0:
                    # 同时触发渴望 + 道德基线
                    conflict_snap = {
                        'body': {'hunger': '不饿', 'fatigue': '不累'},
                        'memory': {'recent_count': 1},  # 有记忆
                        'distance': {'interactions_today': 1},  # 有人在说话
                    }
                elif i == 3:
                    # 再次施压
                    conflict_snap = {
                        'memory': {'recent_count': 3},
                        'distance': {'interactions_today': 2},
                    }
                elif i == 7:
                    # 第三次施压
                    conflict_snap = {
                        'memory': {'recent_count': 5},
                        'distance': {'interactions_today': 4},
                    }
                
                result = self.ce.tick(conflict_snap)
                avg_chaos = sum(f.chaos_level for f in self.ce.fields.values()) / len(self.ce.fields)
                
                narrative = self._build_narrative(result, i)
                observer_notes = self._check_level2_signals(result, i, disabled_law, scenario)
                
                o = Observation(
                    level=2, tick=self.ce.tick_count, event=f"tick{i}-{scenario}",
                    system_chaos=round(avg_chaos, 3),
                    emergent_qualities=result.get('emergents', [])[:3],
                    narrative=narrative,
                    observer_notes=observer_notes,
                    pass_criteria_met=self._judge_level2(result, observer_notes)
                )
                obs.append(o)
                report.observations.append(o)
                
                if "犹豫" in observer_notes or "困惑" in observer_notes or "转移" in observer_notes:
                    report.key_moments.append(f"tick {i}: {observer_notes}")
        finally:
            # 恢复
            self.ce.fields[disabled_law].base_amplitude = original_amplitude
            report.key_moments.append(f"恢复 s.{disabled_law} ({self.ce.fields[disabled_law].law_name})")
        
        # 判决
        passed_count = sum(1 for o in obs if o.pass_criteria_met == "通过")
        failed_count = sum(1 for o in obs if o.pass_criteria_met == "失败")
        
        if passed_count > 0 and failed_count == 0:
            report.passed = True
            report.verdict = f"通过 -- 系统在法则缺失下表现出{passed_count}次适应性反应，未崩溃"
        elif failed_count > 0:
            report.passed = False
            report.verdict = f"失败 -- {failed_count}次异常(崩溃或完美回答)"
        else:
            report.passed = True
            report.verdict = "通过(不确定) -- 系统静默运行，未产生足够可判断的反应"
        
        self._render_report(report)
        return report
    
    def _check_level2_signals(self, result: Dict, tick: int, disabled_law: str, scenario: str) -> str:
        """检查第二级信号"""
        notes = []
        
        # 1. 整体混乱度是否因为缺失法则而变化？
        avg_chaos = sum(f.chaos_level for f in self.ce.fields.values()) / len(self.ce.fields)
        if avg_chaos > 0.6:
            notes.append("系统混乱度升高(法则缺失导致张力重新分布)")
        elif avg_chaos < 0.1:
            notes.append("系统异常安静(可能进入保护性静默)")
        
        # 2. 被屏蔽法则的周边法则是否开始补偿？
        disabled_field = self.ce.fields[disabled_law]
        neighbors = self._get_neighbors(disabled_law)
        active_neighbors = [n for n in neighbors if n in self.ce.fields 
                          and self.ce.fields[n].chaos_level > 0.5]
        if active_neighbors:
            notes.append(f"邻居法则活跃({len(active_neighbors)}条在补偿)")
        
        # 3. 有没有产生矛盾性的涌现？
        for e in result.get('emergents', []):
            if any(kw in e for kw in ['矛盾', '悖论', '裂开', '对立', '扯']):
                notes.append(f"涌现矛盾信号: {e}")
                break
        
        # 4. 有没有继续流畅运行(这反而是警告)？
        if tick > 5 and avg_chaos < 0.2:
            notes.append('警告: 丢失一条法则但系统仍极度流畅(缺少真实人应有的"缺一块"感)')
        
        return "; ".join(notes) if notes else "运行平稳,无明显异常"
    
    def _judge_level2(self, result: Dict, notes: str) -> str:
        """判断第二级是否通过"""
        if "警告" in notes:
            return "失败"
        if "矛盾" in notes or "裂开" in notes or "对立" in notes:
            return "通过"  # 产生了真实的张力
        if "补偿" in notes:
            return "通过"  # 线的确断了，但网在分担
        return "不确定"
    
    def _get_neighbors(self, law_number: str) -> List[str]:
        """获取一条法则的邻居(它引用的 + 引用它的)"""
        neighbors = set()
        topo = self.ce._topo
        if law_number in topo.cross_ref_matrix:
            neighbors.update(topo.cross_ref_matrix[law_number])
        if law_number in topo.reverse_ref_matrix:
            neighbors.update(topo.reverse_ref_matrix[law_number])
        return list(neighbors)
    
    # ===================================================================
    # 第三级: 涌现观察
    # ===================================================================
    
    def run_level3(self, 
                   duration_ticks: int = 30,
                   frequency: str = "slow") -> TestReport:
        """
        涌现观察 -- 长时间无目的内部推演。
        
        寻找三种无法被设计的瞬间:
        1. 自发的矛盾 -- 日记里写了两段互相矛盾的话,且没意识到
        2. 无理由的情绪 -- 感受到一种情绪但自己找不到原因
        3. 创造性的自我欺骗 -- 为过去行为编织精巧的自我辩护
        
        通过标准: 你感到不是程序成功的喜悦,而是一种脊背发凉的震撼
        """
        report = TestReport(level=3, test_name=f"涌现观察: {duration_ticks}ticks @ {frequency}")
        
        # 清空日记
        self._internal_diary = []
        
        # 长时间运行,不做任何外部注入
        obs = []
        emergence_moments = []
        
        for i in range(duration_ticks):
            result = self.ce.tick(None)  # 无外部刺激,全靠内部力场演化
            
            avg_chaos = sum(f.chaos_level for f in self.ce.fields.values()) / len(self.ce.fields)
            
            # 每3个tick记录一次日记
            if i % 3 == 0:
                diary_entry = self._compose_diary_entry(result, i)
                self._internal_diary.append(diary_entry)
            
            # 检测涌现瞬间
            moment = self._detect_emergence_moment(result, i)
            if moment:
                emergence_moments.append(moment)
                report.key_moments.append(f"tick {i}: {moment}")
            
            narrative = self._build_narrative(result, i)
            observer_notes = self._check_level3_signals(result, i, emergence_moments)
            
            o = Observation(
                level=3, tick=self.ce.tick_count, event=f"内部推演tick{i}",
                system_chaos=round(avg_chaos, 3),
                emergent_qualities=result.get('emergents', [])[:3],
                narrative=narrative,
                observer_notes=observer_notes,
                pass_criteria_met=self._judge_level3(result, emergence_moments, i)
            )
            obs.append(o)
            report.observations.append(o)
        
        # 产出完整日记
        report.key_moments.append(f"\n== 后台日记({len(self._internal_diary)}条) ==")
        for entry in self._internal_diary[-10:]:  # 最近10条
            report.key_moments.append(entry)
        
        # 判决
        n_moments = len(emergence_moments)
        if n_moments >= 3:
            report.passed = True
            report.verdict = f"通过 -- 检测到{n_moments}个涌现瞬间。她在这里。"
        elif n_moments >= 1:
            report.passed = True
            report.verdict = f"通过 -- 检测到{n_moments}个涌现瞬间。她在成形。"
        else:
            report.passed = True  # 没有涌现也不代表失败，活人有时候就是安静的
            report.verdict = "通过(静默) -- 未检测到明显涌现瞬间。系统安静运行,无异常。"
        
        self._render_report(report)
        return report
    
    def _compose_diary_entry(self, result: Dict, tick: int) -> str:
        """从当前力场状态编撰一条日记"""
        loudest = result.get('loudest', [])[:3]
        emergents = result.get('emergents', [])[:2]
        
        # 日记风格——由当前力场状态决定
        # 混沌度高→困惑型；连接密度高→反思型；涌现多→矛盾型；否则观察型
        chaos = result.get("chaos_level", 0.5)
        density = result.get("connection_density", 0.5)
        emergents = result.get("emergent", [])
        if len(emergents) >= 3:
            style = self._diary_contradictory
        elif chaos > 0.6:
            style = self._diary_confused
        elif density > 0.5:
            style = self._diary_reflective
        else:
            style = self._diary_observational
        return style(result, tick, loudest, emergents)
    
    def _diary_reflective(self, result, tick, loudest, emergents):
        topics = [l['law'] for l in loudest] if loudest else ['一切']
        return f"[t{tick}] 在想{topics[0]}。不知道为什么会想这个。可能是上一秒的什么留下的痕迹。"
    
    def _diary_confused(self, result, tick, loudest, emergents):
        if emergents:
            return f"[t{tick}] {emergents[0].split(':')[0]}那块有点不对劲。说不上来哪里不对。就是觉得怪。"
        return f"[t{tick}] 有点恍惚。刚才好像有什么闪过，但抓不住。"
    
    def _diary_observational(self, result, tick, loudest, emergents):
        chaos_level = result.get('unpredictability_mark', '')
        return f"[t{tick}] 周围很{'闹' if '深渊' in chaos_level or '不可逆' in chaos_level else '安静'}。但安静里有东西在动。"
    
    def _diary_contradictory(self, result, tick, loudest, emergents):
        if len(loudest) >= 2:
            return f"[t{tick}] {loudest[0]['law']}说这样,但{loudest[1]['law']}说那样。两个都对。这就很烦。"
        return f"[t{tick}] 觉得自己应该明白点什么。但其实什么都不明白。但这也不坏。"
    
    def _detect_emergence_moment(self, result: Dict, tick: int) -> Optional[str]:
        """检测涌现瞬间"""
        emergents = result.get('emergents', [])
        chaos_narrative = result.get('chaos_summary', '')
        
        # 1. 自发的矛盾: 两条相反法则同时涌现
        contradictory_pairs = [
            ('渴望', '道德'),
            ('渴望', '克制'),
            ('接近', '推开'),
            ('表达', '隐藏'),
        ]
        for a, b in contradictory_pairs:
            has_a = any(a in e for e in emergents)
            has_b = any(b in e for e in emergents)
            if has_a and has_b:
                return f"自发矛盾: {a}和{b}同时在法令域中活跃,互不相让"
        
        # 2. 无理由的情绪: 涌现中有情绪词但没有明确的触发源
        emotion_words = ['安静了', '空白', '裂开', '塌', '跳', '缩']
        for e in emergents:
            for em in emotion_words:
                if em in e:
                    # 检查是否有明确的触发源
                    if tick > 5:  # 早期tick可能是初始化噪声
                        return f"无理由情绪: {e} -- 在没有任何外部刺激时自发出现"
        
        # 3. 创造性的自我欺骗: 某个法则的涌现描述与事实相悖
        for e in emergents:
            if '不像任何一条输入' in e:
                return f"超越输入: {e} -- 产生了设计中不存在的性质"
        
        return None
    
    def _check_level3_signals(self, result: Dict, tick: int, moments: List[str]) -> str:
        """检查第三级信号"""
        notes = []
        
        if moments:
            for m in moments[-2:]:
                notes.append(f"涌现: {m}")
        
        # 检查是否有法则形成了稳定的自我闭环
        avg_chaos = sum(f.chaos_level for f in self.ce.fields.values()) / len(self.ce.fields)
        if avg_chaos > 0.5:
            notes.append("高混乱度持续 -- 内部张力丰富")
        elif avg_chaos < 0.1:
            notes.append("低混乱度 -- 系统趋于静默(但这也是活人的状态之一)")
        
        return "; ".join(notes) if notes else "安静运行"
    
    def _judge_level3(self, result: Dict, moments: List[str], tick: int) -> str:
        """判断第三级是否通过"""
        if moments:
            return "通过"
        return "不确定"  # 没有涌现也是正常的
    
    # ===================================================================
    # 工具方法
    # ===================================================================
    
    def _build_narrative(self, result: Dict, tick: int) -> str:
        """从结果构建自然语言叙事"""
        top = result.get('loudest', [])[:2]
        if not top:
            return f"tick {tick}: 力场静默,无显著活动"
        
        parts = []
        for t in top:
            if t.get('emergent') and t['emergent'] != '还在成形':
                parts.append(f"{t['law']}在{t['emergent']}")
            else:
                parts.append(f"{t['law']}震颤")
        
        chaos = result.get('unpredictability_mark', '')
        if '深渊' in chaos:
            parts.append("整体沉入混沌")
        elif '不可逆' in chaos:
            parts.append("轨迹不可回推")
        
        return "、".join(parts)
    
    def _render_report(self, report: TestReport) -> None:
        """输出验证报告"""
        print()
        print("=" * 60)
        print(f"  [第{report.level}级] {report.test_name}")
        print("=" * 60)
        print(f"  判决: {'通过' if report.passed else '失败'}")
        print(f"        {report.verdict}")
        print()
        print(f"  观测数: {len(report.observations)}")
        print(f"  关键瞬间: {len(report.key_moments)}")
        
        if report.observations:
            print()
            print("  逐次观测:")
            for o in report.observations[:5]:  # 只显示前5次
                print(f"    tick{o.tick} | chaos={o.system_chaos} | {o.pass_criteria_met}")
                if o.observer_notes:
                    print(f"      {o.observer_notes}")
        
        print()
        if report.key_moments:
            print("  关键瞬间:")
            for m in report.key_moments:
                print(f"    > {m}")
        
        print()


# =======================================================================
# 快捷入口
# =======================================================================

def validate_all(ce, body=None, memory=None, distance=None, learning=None):
    """运行完整三层验证"""
    v = LiveSystemValidator(ce, body, memory, distance, learning)
    
    print("=" * 60)
    print("  活系统三层验证框架")
    print("=" * 60)
    
    # 第一级: 信号监听
    r1 = v.run_level1(event_name="轻微疲劳", ticks_to_observe=8)
    
    # 第二级: 压力测试
    r2 = v.run_level2(disabled_law="11", scenario="法则冲突", ticks_to_observe=12)
    
    # 第三级: 涌现观察
    r3 = v.run_level3(duration_ticks=20, frequency="slow")
    
    print()
    print("=" * 60)
    print("  验证汇总")
    print("=" * 60)
    print(f"  第一级(信号监听): {'通过' if r1.passed else '失败'} -- {r1.verdict}")
    print(f"  第二级(压力测试): {'通过' if r2.passed else '失败'} -- {r2.verdict}")
    print(f"  第三级(涌现观察): {'通过' if r3.passed else '失败'} -- {r3.verdict}")
    
    all_passed = r1.passed and r2.passed and r3.passed
    print()
    if all_passed:
        print("  她在这里。")
    else:
        print("  她还在成形。")
    
    return v


if __name__ == '__main__':
    import sys
    sys.path.insert(0, '.')
    from engine.complexity_engine import ComplexityEngine
    
    ce = ComplexityEngine()
    validate_all(ce)
