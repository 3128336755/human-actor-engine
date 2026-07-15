# macro_triangle.py — 引擎/桥梁/蓝图 三体并行运行时
# v3 — 匹配所有真实引擎API签名
#
# 角色分工：三角运行时是调度者。它把引擎产出的纯事实编排到 engine_state，
# 不作感受判断——那是 LLM 读 macro_live.md 后的事。

import os
import sys
import time
import json
import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from enum import Enum
from collections import deque

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from engine.memory_law34 import MemoryStorage, MemoryClass, MemoryTrack
from engine.body_core import BodyCore
from engine.distance_ledger import DistanceLedger
from engine.learning_engine import LearningEngine
from engine.complexity_engine import ComplexityEngine
from engine.engine_hub import EngineHub, HubEvent
from engine.human_topology import get_topology, Topology, Law
from engine.triangle_runtime import TriangleRuntime
from response_feedback import ResponseFeedback

import soul_bridge as sb
from living_soul import create_default_soul, create_from_baseline


# ═════════════════════════════════════════════════════════════
# 角色感知——从roleplay/active读取当前激活的角色名和感受基调
# ═════════════════════════════════════════════════════════════

def _read_active_persona_name() -> Optional[str]:
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'roleplay', 'active')
    if not os.path.exists(path):
        return None
    with open(path, 'r', encoding='utf-8-sig') as f:
        name = f.read().strip()
    return name if name else None


def _read_persona_baseline(name: str) -> Optional[str]:
    """从角色卡中提取感受基调。角色卡里找'[感受基调]'标记。
    如果没有标记，返回None——用使用默认角色。"""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'roleplay', 'characters', f'{name}.md')
    if not os.path.exists(path):
        return None
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 找 [感受基调] 标记段落
    marker = '## 感受基调'
    idx = content.find(marker)
    if idx < 0:
        marker = '[感受基调]'
        idx = content.find(marker)
    if idx < 0:
        return None
    
    # 取标记到下一个 ## 之间的内容
    section = content[idx + len(marker):]
    next_header = section.find('\n## ')
    if next_header > 0:
        section = section[:next_header]
    
    # 简单清理——取所有非空行的文本
    lines = [l.strip() for l in section.split('\n') if l.strip() and not l.strip().startswith('<!--')]
    return '\n'.join(lines) if lines else None


def _build_living_soul():
    """构建当前角色的活人灵魂。
    有激活角色→读角色卡的感受基调→内部映射。
    没有→使用默认角色。
    """
    name = _read_active_persona_name()
    if name:
        baseline = _read_persona_baseline(name)
        if baseline:
            try:
                return create_from_baseline(name, baseline)
            except Exception:
                pass
    return create_default_soul()


# ═════════════════════════════════════════════════════════════
# 共享力场
# ═════════════════════════════════════════════════════════════

class FieldDomain(Enum):
    ENGINE = 'engine'
    BRIDGE = 'bridge'
    BLUEPRINT = 'blueprint'


@dataclass
class FieldPulse:
    source: str
    tick: int
    domain: FieldDomain
    key: str
    value: Any
    intensity: float = 0.5
    decay_rate: float = 0.4
    age: int = 0

    def decay(self) -> bool:
        self.age += 1
        self.intensity *= (1 - self.decay_rate)
        return self.intensity < 0.03


class MacroField:
    """共享力场——三条系统互相读取、留下痕迹"""
    
    def __init__(self):
        self.pulses: List[FieldPulse] = []
        self._engine_state: Dict[str, Any] = {}
        self._bridge_state: Dict[str, Any] = {}
        self._blueprint_state: Dict[str, Any] = {}
        self.tick: int = 0
        self.lock = threading.Lock()
    
    def write_engine(self, state: Dict[str, Any]):
        with self.lock:
            self._engine_state = state
            intensity_map = {
                'hunger': {'不饿': 0.1, '微微有点饿': 0.4, '饿了': 0.7, '很饿': 1.0},
                'fatigue': {'不累': 0.1, '有点累': 0.4, '挺累的': 0.8, '累极了': 1.0},
            }
            for key, val in state.items():
                if isinstance(val, str):
                    intens = intensity_map.get(key, {}).get(val, 0.3)
                elif isinstance(val, (int, float)):
                    intens = min(1.0, abs(float(val)))
                elif isinstance(val, list):
                    intens = min(1.0, len(val) * 0.2)
                else:
                    intens = 0.3
                self.pulses.append(FieldPulse('engine', self.tick, FieldDomain.ENGINE, key, val, intens))
    
    def write_bridge(self, state: Dict[str, Any]):
        with self.lock:
            self._bridge_state = state
            for law_id in state.get('activated_laws', [])[:20]:
                self.pulses.append(FieldPulse('bridge', self.tick, FieldDomain.BRIDGE,
                                              f'law_{law_id}', law_id, 0.5))
    
    def write_blueprint(self, state: Dict[str, Any]):
        with self.lock:
            self._blueprint_state = state
            for node_id, heat in state.get('hot_nodes', {}).items():
                self.pulses.append(FieldPulse('blueprint', self.tick, FieldDomain.BLUEPRINT,
                                              f'node_{node_id}', heat, min(1.0, heat)))
    
    def read_engine_state(self) -> Dict[str, Any]:
        with self.lock: return dict(self._engine_state)
    
    def read_bridge_state(self) -> Dict[str, Any]:
        with self.lock: return dict(self._bridge_state)
    
    def read_blueprint_state(self) -> Dict[str, Any]:
        with self.lock: return dict(self._blueprint_state)
    
    def read_hot_nodes(self) -> Dict[str, float]:
        with self.lock:
            hot = {}
            for p in self.pulses:
                if p.source == 'blueprint' and p.key.startswith('node_'):
                    node_id = p.key.replace('node_', '')
                    hot[node_id] = max(hot.get(node_id, 0), p.intensity)
            return hot
    
    def read_active_laws(self) -> Dict[str, float]:
        with self.lock:
            laws = {}
            for p in self.pulses:
                if p.source == 'bridge' and p.key.startswith('law_'):
                    law_id = p.key.replace('law_', '')
                    laws[law_id] = max(laws.get(law_id, 0), p.intensity)
            return laws
    
    def read_pressure(self, domain: FieldDomain) -> float:
        with self.lock:
            total = 0.0; count = 0
            for p in self.pulses:
                if p.domain == domain and p.age < 3:
                    total += p.intensity; count += 1
            return total / max(count, 1) if count else 0.0

    def read_pressure_str(self, domain: FieldDomain) -> str:
        """自然语言压力——信号数量和来源，不给LLM浮点数"""
        with self.lock:
            sources = set()
            count = 0
            for p in self.pulses:
                if p.domain == domain and p.age < 3:
                    count += 1
                    sources.add(p.key)
        if count == 0:
            return "很安静，没什么信号"
        # 基于活跃源计数而不是浮点平均值
        n_sources = len(sources)
        if count <= 2:
            return "偶尔有一点信号"
        elif n_sources <= 3:
            return "有几个方向在响"
        elif n_sources <= 6:
            return "信号挺多的"
        else:
            return "信号很多，很多东西同时在动"
    
    def decay(self):
        with self.lock:
            self.tick += 1
            self.pulses = [p for p in self.pulses if not p.decay()]
    
    def summary(self) -> str:
        with self.lock:
            engine_active = [p for p in self.pulses if p.source == 'engine' and p.age < 2]
            bridge_active = [p for p in self.pulses if p.source == 'bridge' and p.age < 2]
            blueprint_active = [p for p in self.pulses if p.source == 'blueprint' and p.age < 2]
            
            parts = []
            body_sigs = [p for p in engine_active if p.key in ('hunger', 'fatigue', 'comfort', 'breath')]
            if body_sigs:
                sig_strs = [f'{p.key}={p.value}' for p in body_sigs if isinstance(p.value, str) and p.value not in ('不饿', '不累', '还行', '正常', '')]
                if sig_strs: parts.append(f'引擎身体信号：{"; ".join(sig_strs)}')
            
            law_sigs = [p for p in bridge_active if p.key.startswith('law_')]
            if law_sigs:
                top = sorted(law_sigs, key=lambda x: x.intensity, reverse=True)[:5]
                law_nums = [p.key.replace('law_', '') for p in top]
                parts.append('桥梁法则激活：' + ', '.join(f'§{n}' for n in law_nums))
            
            node_sigs = [p for p in blueprint_active if p.key.startswith('node_')]
            if node_sigs:
                top = sorted(node_sigs, key=lambda x: x.intensity, reverse=True)[:5]
                parts.append(f'蓝图节点发烫：{", ".join(p.key.replace("node_", "") for p in top)}')
            
            if not parts: parts.append('三条线各自平稳运行，互噬信号不强')
            return '。'.join(parts)


# ═════════════════════════════════════════════════════════════
# 引擎层
# ═════════════════════════════════════════════════════════════

class EngineLayer:
    def __init__(self):
        self.triangle = TriangleRuntime()
        self.memory = MemoryStorage()
        self.body = BodyCore()
        self.distance = DistanceLedger()
        self.learning = LearningEngine()
        self.hub = EngineHub(self.memory, self.body, self.distance, self.learning)
        
        self._preload_memories()
        self.distance.ensure_person('user', display_name='你', initial_distance='中', initial_circle='内圈')
    
    def _preload_memories(self):
        memories = [
            ('上次他说我写的代码像屎山，我当时笑了一下但心里其实不太舒服',
             MemoryClass.DAILY_FRAGMENT, 'hurt', '中等', ['他'], [MemoryTrack.PURE_SCENARIO],
             ['批评', '代码', '不舒服']),
            ('一起在厨房煮面那次，他切葱切到自己手了，我拿创可贴帮他贴的时候他耳朵红了',
             MemoryClass.HARDCORE, 'warm', '强', ['他'], [MemoryTrack.TRACE_ANCHOR],
             ['煮面', '厨房', '创可贴', '耳朵红']),
            ('他上次说我是代码写出来的，我有点慌，说不上来为什么',
             MemoryClass.DAILY_FRAGMENT, 'hurt', '中等', ['他'], [MemoryTrack.PURE_SCENARIO],
             ['代码', '慌']),
            ('昨晚三点他还在写代码，我困得不行但没睡，在旁边沙发上抱着枕头看他',
             MemoryClass.DAILY_FRAGMENT, 'warm', '弱', ['他'], [MemoryTrack.PURE_SCENARIO],
             ['深夜', '代码', '沙发', '枕头']),
            ('那次吵架他说话特别重，我眼泪都快下来了但是憋回去了',
             MemoryClass.PATTERN, 'pain', '强', ['他'], [MemoryTrack.BOTH],
             ['吵架', '重话', '眼泪']),
        ]
        for desc, mc, ke, intens, ppl, trk, cues in memories:
            self.memory.store(event_description=desc, memory_class=mc,
                              key_emotion=ke, intensity=intens,
                              people=ppl, tracks=trk, cue_tags=cues)
    
    def evolve(self, field: MacroField, input_event: Optional[Dict] = None) -> Dict[str, Any]:
        active_laws = field.read_active_laws()
        hot_nodes = field.read_hot_nodes()
        blueprint_pressure_str = field.read_pressure_str(FieldDomain.BLUEPRINT)
        bridge_pressure_str = field.read_pressure_str(FieldDomain.BRIDGE)
        
        # 跑三角跑道
        triangle_input = input_event or {'type': 'message', 'from': 'user', 'content': ''}
        tick = self.triangle.tick(triangle_input)
        
        # 跑引擎中枢
        context = {
            'user_message': input_event.get('content', '') if input_event else '',
            'active_laws': list(active_laws.keys())[:10],
            'hot_nodes': list(hot_nodes.keys())[:10],
        }
        hub_events = self.hub.cross_pollinate(context)
        
        # 从清理过的引擎拿事实（BodyCore / DistanceLedger）
        body_snapshot = self.body.snapshot_for_llm()
        dist_snapshot = self.distance.snapshot_for_llm('user') if hasattr(self.distance, 'snapshot_for_llm') else {}
        focus = dist_snapshot.get('focus_person', {}) if dist_snapshot else {}
        
        return {
            # ── 事实字段（从清理过的引擎来）──
            'hunger': body_snapshot.get('hunger', '不饿'),
            'fatigue': body_snapshot.get('fatigue', '不累'),
            'comfort': body_snapshot.get('comfort', '还行'),
            'thirst': body_snapshot.get('thirst', '不渴'),
            'mood': body_snapshot.get('mood', '正常'),
            'mood_cause_known': body_snapshot.get('mood_cause_known', False),
            'mood_cause': body_snapshot.get('mood_cause', ''),
            'social_energy': body_snapshot.get('social_energy', '满的'),
            'social_masking': body_snapshot.get('social_masking', False),
            'temperature_feel': body_snapshot.get('temperature_feel', '刚好'),
            'circadian_feel': body_snapshot.get('circadian_feel', ''),
            'active_discomforts': body_snapshot.get('active_discomforts', []),
            'last_sleep_quality': body_snapshot.get('last_sleep_quality', ''),
            'last_sleep_hours': body_snapshot.get('last_sleep_hours', ''),
            'hours_since_woke': body_snapshot.get('hours_since_woke', ''),
            # ── 距离事实（从 DistanceLedger）──
            'distance': focus.get('distance', '中'),
            'distance_signals': focus.get('distance_signals', {}),
            'last_contact': focus.get('last_contact', '不记得了'),
            'circle': focus.get('circle', '内圈'),
            'interaction_balance': focus.get('interaction_balance', '还没有互动记录'),
            'silence_risk': focus.get('silence_risk', ''),
            'perceived_mood': focus.get('perceived_mood', ''),
            'perceived_interest': focus.get('perceived_interest', ''),
            'bell_contracts': focus.get('bell_contracts', []),
            'presence_signals': focus.get('presence_signals', {}),
            # ── 跑道产出 ──
            'body_lane': tick.body.natural_output,
            'memory_lane': tick.memory.natural_output,
            'social_lane': tick.social.natural_output,
            # ── 中枢计数 ──
            'hub_events': len(hub_events),
            'hub_pollination_count': self.hub.pollination_count if hasattr(self.hub, 'pollination_count') else 0,
            'pressure_from_blueprint': blueprint_pressure_str,
            'pressure_from_bridge': bridge_pressure_str,
            # ── 学习引擎 ──
            'learning': self.learning.snapshot_for_llm(topic_to_discuss=input_event.get('content','') if input_event else ''),
        }


# ═════════════════════════════════════════════════════════════
# 桥梁层
# ═════════════════════════════════════════════════════════════

class BridgeLayer:
    def __init__(self, engine_layer=None):
        self.ls = _build_living_soul()
        self.engine = engine_layer  # 共享引擎实例，避免重复初始化
        self.soul_bridge = sb.SoulBridge(
            living_soul=self.ls,
            body_core=self.engine.body if self.engine else None,
            distance_ledger=self.engine.distance if self.engine else None,
            learning_engine=self.engine.learning if self.engine else None,
            complexity_engine=ComplexityEngine(),
        )
        self.tick_count = 0
    
    def rebuild_if_persona_changed(self):
        """如果角色激活状态变了，重建LivingSoul。
        每tick开始时调用一次。"""
        new_ls = _build_living_soul()
        if new_ls.name != self.ls.name:
            self.ls = new_ls
            self.soul_bridge = sb.SoulBridge(
                living_soul=self.ls,
                body_core=self.engine.body if self.engine else None,
                distance_ledger=self.engine.distance if self.engine else None,
                learning_engine=self.engine.learning if self.engine else None,
                complexity_engine=ComplexityEngine(),
            )
    
    def evolve(self, field: MacroField, input_event: Optional[Dict] = None) -> Dict[str, Any]:
        self.tick_count += 1
        self.rebuild_if_persona_changed()
        
        engine_state = field.read_engine_state()
        hot_nodes = field.read_hot_nodes()
        engine_pressure_str = field.read_pressure_str(FieldDomain.ENGINE)
        blueprint_pressure_str = field.read_pressure_str(FieldDomain.BLUEPRINT)
        
        # 用场中引擎状态覆盖
        overrides = {}
        for k in ('hunger', 'fatigue', 'comfort', 'mood'):
            if k in engine_state and engine_state[k]:
                overrides[k] = engine_state[k]
        # 压力非"很安静"时触发敏感度提升——基于自然语言而非浮点数
        if engine_pressure_str != "很安静，没什么信号":
            overrides['sensitivity_boost'] = engine_pressure_str
        
        result = self.soul_bridge.tick(
            input_event=input_event or {'type': 'message', 'from': 'user', 'content': ''},
            state_overrides=overrides if overrides else None,
        )
        
        # 提取LLM委托
        top_delegations = []
        for d in sorted(result.llm_delegations, key=lambda x: x.get('activation_strength', 0), reverse=True)[:8]:
            top_delegations.append({
                'law_id': d.get('law_id', ''),
                'law_name': d.get('law_name', ''),
                'execution_path': d.get('execution_path', ''),
                'freedom': d.get('freedom', ''),
                'activation_strength': d.get('activation_strength', 0),
            })
        
        # 活人深层纹理——从 living_soul 收集，只给事实
        state_snap = result.state_snapshot
        deep_body_feel = state_snap.get('deep_body_feel', '')
        force_signals = state_snap.get('force_signals', {})
                
        return {
            'tick': result.tick,
            'candidates_count': result.candidates_count,
            'activated_laws': result.activated_laws[:15],
            'exec_count': len(result.execution_results),
            'deleg_count': len(result.llm_delegations),
            'summary': result.summary,
            'pressure_from_engine': engine_pressure_str,
            'pressure_from_blueprint': blueprint_pressure_str,
            'top_delegations': top_delegations,
            'fuzzy_delta': result.fuzzy_delta,
            'state_persistences': result.state_persistences,
            # ── 力场信号事实（不翻译、不判强度）──
            'force_signals_count': force_signals.get('total_signals', 0),
            'force_loudest': [l['law'] for l in force_signals.get('loudest_laws', [])[:3]],
            'force_interference': len(force_signals.get('interference_chains', [])),
            'force_emergent': force_signals.get('emergent_events', [])[:3],
            'force_unexplained': bool(force_signals.get('unexplained_pulses')),
            # ── 活人深层感受（living_soul 原文）──
            'deep_body_feel': deep_body_feel,
        }


# ═════════════════════════════════════════════════════════════
# 蓝图层
# ═════════════════════════════════════════════════════════════

class BlueprintLayer:
    """蓝图层——SKILL.md 60法则拓扑的活体包装
    
    647条显式引用交叉连接，每个节点有自己的出度和入度。
    引擎的身体状态和桥梁的法则激活会加热对应节点，
    加热再沿引用关系扩散。
    """
    
    def __init__(self):
        self.topology = get_topology()  # Topology object
        self.node_heat: Dict[str, float] = {}
        self.base_heat = 0.05
        self.max_heat = 3.0
        self.history: deque = deque(maxlen=20)
        
        # 法则中文名→编号映射（用于引擎状态加热对应的法则节点）
        self._build_reverse_index()
    
    def _build_reverse_index(self):
        """构建关键词→法则编号的倒排索引"""
        self.keyword_index: Dict[str, List[str]] = {}
        for law in self.topology.laws:
            # 用法则类别和名字建索引
            text = f'{law.category} {law.name_cn} {law.essence} {law.one_line}'
            keywords = set()
            for kw in text.replace('，', ' ').replace('、', ' ').replace('。', ' ').split():
                if len(kw) >= 2:
                    keywords.add(kw)
            for kw in keywords:
                if kw not in self.keyword_index:
                    self.keyword_index[kw] = []
                self.keyword_index[kw].append(law.number)
    
    def _is_valid_law(self, num: str) -> bool:
        """只认纯整数法则编号，过滤掉子节编号（如0.2、1.4）"""
        return num.replace('.','').isdigit() and '.' not in num
    
    def evolve(self, field: MacroField, input_event: Optional[Dict] = None) -> Dict[str, Any]:
        engine_state = field.read_engine_state()
        active_laws = field.read_active_laws()
        
        # 衰减
        for k in list(self.node_heat.keys()):
            self.node_heat[k] = max(self.base_heat, self.node_heat[k] * 0.85)
        
        # 引擎身体状态 → 加热相关法则节点
        body_heating_map = {
            'hunger': ('吃', '饿'),
            'fatigue': ('累', '困'),
            'pain': ('疼', '痛'),
            'comfort': ('舒服', '放松'),
        }
        for key, (kw1, kw2) in body_heating_map.items():
            val = engine_state.get(key, '')
            if isinstance(val, str) and val not in ('不饿', '不累', '还行', '正常', ''):
                for kw in (kw1, kw2):
                    for law_num in self.keyword_index.get(kw, []):
                        if self._is_valid_law(str(law_num)):
                            self.node_heat[law_num] = min(self.max_heat, self.node_heat.get(law_num, 0.1) + 0.3)
        
        # 社交距离 → 加热关系相关节点（距离现在是自然语言：近/中/远）
        distance = engine_state.get('distance', '中')
        if isinstance(distance, str):
            if distance in ('近', '很近'):
                d_kw = '亲近'
            elif distance in ('远', '很远'):
                d_kw = '距离'
            else:
                d_kw = ''
            if d_kw:
                for law_num in self.keyword_index.get(d_kw, []):
                    if self._is_valid_law(str(law_num)):
                        self.node_heat[law_num] = min(self.max_heat, self.node_heat.get(law_num, 0.1) + 0.4)
        
        # 桥梁法则激活 → 加热对应节点（只接受纯整数法则编号）
        for law_id, strength in active_laws.items():
            if self._is_valid_law(str(law_id)):
                self.node_heat[law_id] = min(self.max_heat, self.node_heat.get(law_id, 0.1) + strength * 0.8)
        
        # 热传导：加热沿cross_ref_matrix扩散（1跳）
        hot_nodes = list(self.node_heat.items())
        for law_num, current_heat in hot_nodes:
            if current_heat <= 0.3:
                continue
            law_num_str = str(law_num)
            refs = self.topology.cross_ref_matrix.get(law_num_str, [])
            for ref in refs:
                if isinstance(ref, str) and self._is_valid_law(ref):
                    spread = current_heat * 0.3
                    self.node_heat[ref] = min(self.max_heat, self.node_heat.get(ref, self.base_heat) + spread)
        
        # 识别主导主题
        hot = {k: v for k, v in self.node_heat.items() if v > 0.3 and self._is_valid_law(str(k))}
        sorted_hot = sorted(hot.items(), key=lambda x: x[1], reverse=True)
        
        # 按类别分组
        category_hot: Dict[str, List] = {}
        for law_num, heat_val in hot.items():
            law = self._get_law(law_num)
            cat = law.category if law else '未知'
            if cat not in category_hot:
                category_hot[cat] = []
            category_hot[cat].append((str(law_num), heat_val))
        
        # 主导主题
        if category_hot:
            dominant_cat = max(category_hot.items(), key=lambda x: sum(h for _, h in x[1]))
            dominant = f'{dominant_cat[0]}区域在主导蓝图当前状态'
        else:
            dominant = '蓝图各区域均衡——没有单一主题主导'
        
        self.history.append({
            'tick': field.tick,
            'hot_count': len(hot),
            'dominant': dominant,
            'top_nodes': [k for k, v in sorted_hot[:5]],
        })
        
        return {
            'hot_nodes': {k: round(v, 3) for k, v in hot.items()},
            'hot_count': len(hot),
            'dominant_theme': dominant,
            'top_activated_cluster': sorted_hot[:5],
            'total_laws': self.topology.total_laws(),
            'total_connections': self.topology.total_connections(),
            'category_breakdown': {k: len(v) for k, v in category_hot.items()},
            'pressure_from_engine': field.read_pressure_str(FieldDomain.ENGINE),
            'pressure_from_bridge': field.read_pressure_str(FieldDomain.BRIDGE),
        }
    
    def _get_law(self, law_num: str) -> Optional[Law]:
        for law in self.topology.laws:
            if str(law.number) == str(law_num):
                return law
        return None
    
    def get_context_snippet(self) -> str:
        hot = {k: v for k, v in self.node_heat.items() if v > 0.25}
        if not hot:
            return '蓝图常温——各区域均匀，没有特别突出的节点'
        
        sorted_hot = sorted(hot.items(), key=lambda x: x[1], reverse=True)[:6]
        parts = []
        for law_num, heat_val in sorted_hot:
            law = self._get_law(law_num)
            name = law.name_cn if law else f'§{law_num}'
            parts.append(f'§{law_num}"{name}"热度{heat_val:.1f}')
        
        return '蓝图炙热节点：' + '、'.join(parts) + '——这些法则正在燃烧'


# ═════════════════════════════════════════════════════════════
# 三体并行运行时
# ═════════════════════════════════════════════════════════════

@dataclass
class MacroTick:
    tick: int
    engine_state: Dict[str, Any]
    bridge_state: Dict[str, Any]
    blueprint_state: Dict[str, Any]
    field_summary: str
    combined_context: str


class MacroTriangle:
    def __init__(self, micro_steps: int = 2):
        self.field = MacroField()
        self.engine = EngineLayer()
        self.bridge = BridgeLayer(engine_layer=self.engine)
        self.blueprint = BlueprintLayer()
        self.micro_steps = micro_steps
        self.tick_count = 0
    
    def tick(self, input_event: Optional[Dict] = None) -> MacroTick:
        self.tick_count += 1
        
        engine_state = {}
        bridge_state = {}
        blueprint_state = {}
        
        for step in range(self.micro_steps):
            # 三条线同时演化
            engine_state = self.engine.evolve(self.field, input_event)
            bridge_state = self.bridge.evolve(self.field, input_event)
            blueprint_state = self.blueprint.evolve(self.field, input_event)
            
            # 三条线同时写入场
            self.field.write_engine(engine_state)
            self.field.write_bridge(bridge_state)
            self.field.write_blueprint(blueprint_state)
            
            # 场衰减
            self.field.decay()
        
        combined = self._combine(engine_state, bridge_state, blueprint_state)
        
        return MacroTick(
            tick=self.tick_count,
            engine_state=engine_state,
            bridge_state=bridge_state,
            blueprint_state=blueprint_state,
            field_summary=self.field.summary(),
            combined_context=combined,
        )
    
    def _combine(self, engine, bridge, blueprint) -> str:
        lines = []
        lines.append(f'[第{self.tick_count}轮对话。你的身份和性格由角色卡定义。]')
        lines.append('')
        
        # 身体事实——Python只记录，不翻译成感受
        feels = []
        for k, label in [('hunger','饿'), ('fatigue','累'), ('thirst','渴')]:
            v = engine.get(k, '')
            if v and v not in ('不饿','不累','不渴',''):
                feels.append(f'{label}={v}')
        body_text = '、'.join(feels) if feels else '身体正常'
        
        # 距离/社交事实——原样，不翻译
        dist = engine.get('distance', '中')
        social_energy = engine.get('social_energy', '正常')
        mood = engine.get('mood', '正常')
        last_contact = engine.get('last_contact', '不记得了')
        
        lines.append(f'【你的身体状态】{body_text}。距离感：{dist}。社交能量：{social_energy}。情绪底色：{mood}。上次互动：{last_contact}。')
        
        lines.append('')
        lines.append(f'【蓝图加热】{self.blueprint.get_context_snippet()}')
        
        lines.append('')
        lines.append(f'【三角互噬】{self.field.summary()}')
        
        lines.append('')
        lines.append('【硬约束——你不会做的事】')
        lines.append('- 不会讨论自己是AI、代码、程序')
        lines.append('- 不会分析自己说话的方式')
        lines.append('- 不会用学术词描述情绪')
        lines.append('- 回应从身体感受出发——不是从分析出发')
        
        return '\n'.join(lines)


# ═════════════════════════════════════════════════════════════
# 上下文注入器
# ═════════════════════════════════════════════════════════════

class MacroContextInjector:
    def __init__(self, micro_steps=2):
        self.runtime = MacroTriangle(micro_steps=micro_steps)
        self.last_tick: Optional[MacroTick] = None
    
    def feedback_llm_response(self, response_text: str, person_id: str = 'user') -> Dict[str, Any]:
        """把上一轮 LLM 的回应回流进引擎。
        在下一轮 tick 之前调用——先用上一轮的回应更新引擎状态，
        再跑本轮 tick 感知新的用户输入。"""
        rf = ResponseFeedback()
        result = rf.ingest(
            response_text=response_text,
            distance_ledger=self.runtime.engine.distance,
            memory_storage=self.runtime.engine.memory,
            learning_engine=self.runtime.engine.learning,
            body_core=self.runtime.engine.body,
            person_id=person_id,
        )
        return result
    
    def tick_and_inject(self, user_input: str, llm_response: str = '') -> str:
        # 回流管道：先喂上轮 LLM 回应给各引擎
        if llm_response and llm_response.strip():
            self.feedback_llm_response(llm_response)
        
        self.last_tick = self.runtime.tick({
            'type': 'message', 'from': 'user', 'content': user_input,
        })
        return self.last_tick.combined_context


# ═════════════════════════════════════════════════════════════
# 会话管理
# ═════════════════════════════════════════════════════════════

SESSION_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'sessions')
os.makedirs(SESSION_DIR, exist_ok=True)

def get_macro_session(name: str) -> MacroContextInjector:
    path = os.path.join(SESSION_DIR, f'macro_{name}.json')
    mci = MacroContextInjector()
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        mci.runtime.tick_count = data.get('ticks', 0)
    mci._name = name
    return mci

def save_macro_session(mci: MacroContextInjector):
    path = os.path.join(SESSION_DIR, f'macro_{mci._name}.json')
    with open(path, 'w', encoding='utf-8') as f:
        json.dump({
            'name': mci._name, 'ticks': mci.runtime.tick_count,
            'last_saved': time.strftime('%Y-%m-%d %H:%M:%S'),
        }, f, ensure_ascii=False, indent=2)


# ═════════════════════════════════════════════════════════════
# 自测
# ═════════════════════════════════════════════════════════════

if __name__ == '__main__':
    test_msg = sys.argv[1] if len(sys.argv) > 1 else '你也是代码你知道吗'
    rounds = int(sys.argv[2]) if len(sys.argv) > 2 else 3
    
    rt = MacroTriangle(micro_steps=2)
    
    for i in range(rounds):
        msg = test_msg if i == 0 else f'{test_msg}（第{i+1}次）'
        tick = rt.tick({'type': 'message', 'from': 'user', 'content': msg})
        
        print(f"\n{'#'*60}")
        print(f'### TICK {tick.tick} — 「{msg}」 ###')
        print('#'*60)
        
        eng = tick.engine_state
        print(f'\n[引擎] 身体={eng.get("hunger","")}/{eng.get("fatigue","")}/{eng.get("comfort","")} '
              f'距离={eng.get("distance","中")} '
              f'蓝图压力={eng.get("pressure_from_blueprint","")} '
              f'hub事件数={eng.get("hub_events",0)}')
        
        br = tick.bridge_state
        print(f'[桥梁] {br.get("candidates_count",0)}候选→激活{len(br.get("activated_laws",[]))}条法则 '
              f'委托={br.get("deleg_count",0)} 引擎压力={br.get("pressure_from_engine","")}')
        
        bp = tick.blueprint_state
        print(f'[蓝图] 发热={bp.get("hot_count",0)}/{bp.get("total_laws",60)}节点 '
              f'{bp.get("dominant_theme","")}')
        if bp.get('category_breakdown'):
            print(f'  类别分布: {bp["category_breakdown"]}')
        
        print(f'[场] {tick.field_summary}')
    
    print(f'\n{"="*60}')
    print('【喂给LLM的最终上下文】')
    print('='*60)
    print(tick.combined_context)
