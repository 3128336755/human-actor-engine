"""
Complexity Engine -- 让拓扑活起来

角色分工：Python 是力场记录者。它追踪信号传导、干涉、叠加——但不替LLM做判断。
Python 说"信号从§12经§34到§56，颠簸了3跳"，LLM决定这个颠簸"意味着什么"。

核心哲学：
  647条链接不是网络 -- 是 647 个力场通道。
  每条链接不是一个"关系" -- 是一个持续运转的传导管道。
  
  信号在通道中流动：
  A -> B -> C -> D -> (反馈回A) -> 新的A != 原来的A
  
  每一轮叠加产生不可逆的新状态。
  因为每一次传导都受当前状态的染色 -- 而当前状态是上一轮叠加的结果。

运行机制：
  1. 每条法则是一个"力场节点" -- 有当前状态
  2. 每条引用是一个"传导通道" -- 有方向、有染色、有衰减
  3. 每个 tick: 稀疏点火 -- 不是所有通道同时被激活
  4. 流动到达目标节点后与目标当前状态混合(叠加、干涉、污染)
  5. 混合后的新状态成为下一轮的起点
  6. 没有"最终状态" -- 只有永不停止的演化
  
产物：
  不是"导航图"。不是"状态报告"。
  是"这一秒的存在纹理" -- 不可预测、不可复现、不可反推。
  前序: 543条通道 x 多轮叠加 = 一个在 N 维空间中持续漂移的活系统
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple, Any
import time

# =======================================================================
# 定性→定量映射表 — 不猜骰子，看结构
# =======================================================================

# 法则类别 → 基础激活度
CATEGORY_BASELINE = {
    "基础锚点": 0.70,
    "个体内部层": 0.55,
    "元系统层": 0.55,
    "传动轴层": 0.50,
    "高阶心理层": 0.50,
    "深度心理层": 0.45,
    "情境与选择层": 0.45,
    "关系与表达层": 0.45,
    "联动层": 0.40,
    "安全与配置层": 0.35,
}

def _ref_density_bonus(ref_count: int, max_ref: int = 60) -> float:
    """引用密度加成——被引得多的法则更容易共振"""
    if ref_count == 0:
        return 0.0
    return (ref_count / max_ref) ** 0.5 * 0.25

def _channel_params(src_cat: str, dst_cat: str, dst_ref_count: int) -> Dict[str, Any]:
    """从拓扑位置推导通道参数——没有两条通道完全一样"""
    latency = 1 if src_cat == dst_cat else 3
    decay = 0.05 + (1.0 / max(1, dst_ref_count)) * 0.25
    decay = min(0.35, decay)
    cat_order = list(CATEGORY_BASELINE.keys())
    si = cat_order.index(src_cat) if src_cat in cat_order else 4
    di = cat_order.index(dst_cat) if dst_cat in cat_order else 4
    phase = (si - di) * 0.1
    return {"latency": latency, "decay": decay, "phase": phase}


# =======================================================================
# 力场通道 -- 比"链接"更准确
# =======================================================================

@dataclass
class ForceChannel:
    """两条法则之间的传导通道 -- 不是"引用"，是"力"的流动"""
    from_law: str          # 源法则编号
    to_law: str            # 目标法则编号
    direction: str         # "outward" | "inward" -- 源->目标是单向力场
    intensity: str         # "loud" | "faint" | "latent" | "reverb"
    latency_ms: int        # 传导延迟: 不同通道不同速度
    decay_rate: float      # 衰减率: 每经过一个中间节点衰减
    phase_shift: float     # 相位偏移: 同输入在不同通道可以产生相反效果
    
    def transmit(self, signal: 'LawSignal', current_tick: int) -> Optional['LawSignal']:
        """沿通道传导信号。传导不是无损的 -- 每经过一条通道，信号被染色、衰减、延迟。"""
        if current_tick < self.latency_ms:
            return None
        
        effective = signal.amplitude * (1.0 - self.decay_rate)
        if effective < 0.001:
            return None
        
        colored_texture = f"{signal.texture};{self.from_law}>{self.to_law}"
        
        colored = LawSignal(
            source_law=self.from_law,
            target_law=self.to_law,
            amplitude=effective * (1.0 + self.phase_shift) if self.phase_shift > 0 else effective,
            texture=colored_texture,
            tick=current_tick,
            hop_count=signal.hop_count + 1,
            path=signal.path + [self.to_law],
            interference_pattern=self._compute_interference(signal, effective)
        )
        
        return colored
    
    def _compute_interference(self, signal: 'LawSignal', amplitude: float) -> str:
        """两股力场到达同一目标时产生的干涉图案
        — 由路径复杂度（长度+跃数+振幅）决定，不是掷骰子。"""
        patterns = [
            "amplified",
            "cancelled",
            "intermediate",
            "harmonic",
            "noise",
        ]
        complexity = len(signal.path) + signal.hop_count + int(amplitude * 5)
        idx = complexity % len(patterns)
        return patterns[idx]


@dataclass
class LawSignal:
    """在力场通道中传导的信号"""
    source_law: str
    target_law: str
    amplitude: float          # 0-1，可超过1(叠加后)
    texture: str              # 信号的"颜色"/"质感" -- 自然语言描述
    tick: int                 # 哪个tick发出的
    hop_count: int            # 经过了多少个中间节点
    path: List[str]           # 完整的传导路径
    interference_pattern: str # 与其他信号干涉的结果类型
    source_traceable: bool = True  # 源头还能追溯吗？hop≥3+多次干涉 → False


@dataclass
class LawField:
    """一条法则的当前力场状态"""
    law_number: str
    law_name: str
    base_amplitude: float           # 基础激活度(引擎给它)
    accumulated_signals: List[LawSignal]  # 从其他法则沿通道到达的信号堆积
    interference_map: Dict[str, str]     # 来自哪些法则、产生了什么干涉
    texture_stack: List[str]             # 被多重信号染色后的纹理堆积
    chaos_level: float                   # 混乱度 -- 信号越多越矛盾越混乱
    emergent_quality: str                # 涌现性质 -- 叠加后的新属性(自然语言)
    
    def absorb(self, signal: LawSignal) -> None:
        """吸收一个信号 -- 不是"处理"，是"被污染" """
        self.accumulated_signals.append(signal)
        self.interference_map[signal.source_law] = signal.interference_pattern
        self.texture_stack.append(signal.texture)
        
        self.chaos_level = min(1.0, len(self.accumulated_signals) / 12.0)
        
        self._emerge()
    
    def _emerge(self) -> None:
        """从堆积的信号纹理中涌现新描述——由纹理本身的结构决定，不是hash取模"""
        if len(self.texture_stack) < 3:
            return
        
        # 分析最近5条纹理的方向冲突度
        recent = self.texture_stack[-5:]
        # 有多少是不同的干涉类型→冲突度
        types = set()
        for s in self.accumulated_signals[-5:]:
            types.add(s.interference_pattern)
        conflict_count = len(types)
        # 信号来源是否分散
        sources = set(s.source_law for s in self.accumulated_signals[-5:])
        source_dispersion = len(sources)
        # 振幅差异
        amps = [s.amplitude for s in self.accumulated_signals[-5:]]
        amp_volatility = max(amps) - min(amps) if amps else 0
        
        # 只给结构事实，不给诗意感受
        if conflict_count >= 4:
            self.emergent_quality = f"冲突密集——{conflict_count}处信号互相矛盾"
        elif source_dispersion >= 4 and amp_volatility < 0.3:
            self.emergent_quality = f"信号拥挤——{source_dispersion}个不同源同时推到同一条法则上"
        elif amp_volatility > 0.5:
            self.emergent_quality = f"叠加后的新东西——振幅差{amp_volatility:.1f}，信号源之间没有直接关系"
        elif self.chaos_level > 0.7:
            self.emergent_quality = f"信号过多——{len(self.accumulated_signals)}个信号压在这条法则上，反馈往内折了"
        elif conflict_count == 2 and self.chaos_level > 0.4:
            self.emergent_quality = f"自振荡——2处冲突在自我反馈，不需要新输入也在跳"
        elif 'cancelled' in types and 'amplified' in types:
            self.emergent_quality = "产生了悖论——两股对立的力场同时在这条法则中成立"
        elif source_dispersion >= 3 and amp_volatility > 0.3:
            self.emergent_quality = "变成了完全不像任何一条输入的东西"
        elif conflict_count == 1 and self.chaos_level < 0.3:
            self.emergent_quality = "安静了——所有信号互相抵消，剩下一种说不清的空白"
        elif self.chaos_level > 0.5:
            self.emergent_quality = "还在成形——太多东西在动了"
        else:
            self.emergent_quality = "还在成形"


# =======================================================================
# 复杂度引擎本身
# =======================================================================

class ComplexityEngine:
    """
    活的复杂度 -- 不是图谱，是力场演化系统
    
    输入: 60条法则 + 543条力场通道
    产出: 每个tick的状态场 -- 不可预测、不可复现
    """
    
    def __init__(self, skill_path: Optional[str] = None):
        from engine.human_topology import get_topology
        self._topo = get_topology(skill_path)
        self.fields: Dict[str, LawField] = {}
        self.channels: List[ForceChannel] = []
        self.tick_count = 0
        self._signal_history: List[LawSignal] = []
        self._unexplained_pulses: List[Dict[str, Any]] = []
        
        self._init_fields()
        self._build_channels()
    
    def _init_fields(self) -> None:
        """初始化每条法则的力场
        基础振幅由法则在拓扑中的结构位置决定——类别和引用密度。"""
        for law in self._topo.laws:
            baseline = CATEGORY_BASELINE.get(law.category, 0.45)
            bonus = _ref_density_bonus(len(law.references))
            amp = baseline + bonus
            self.fields[law.number] = LawField(
                law_number=law.number,
                law_name=law.name_cn,
                base_amplitude=amp,
                accumulated_signals=[],
                interference_map={},
                texture_stack=[],
                chaos_level=0.0,
                emergent_quality="还在成形",
            )
    
    def _build_channels(self) -> None:
        """
        把 543 条链接变成活通道。
        每条通道有独立的传导速度、衰减率、相位偏移。
        没有两条通道完全一样。
        """
        name_to_num = {law.name_cn: law.number for law in self._topo.laws}
        num_to_law = {law.number: law for law in self._topo.laws}
        seen = set()
        for law in self._topo.laws:
            for ref in law.references:
                to_num = ref if ref.isdigit() else name_to_num.get(ref)
                if to_num is None or to_num not in self.fields:
                    continue
                key = f"{law.number}>{to_num}"
                if key not in seen:
                    seen.add(key)
                    dst_law = num_to_law.get(to_num)
                    if dst_law is None:
                        continue
                    params = _channel_params(law.category, dst_law.category, len(dst_law.references))
                    self.channels.append(ForceChannel(
                        from_law=law.number,
                        to_law=to_num,
                        direction="outward",
                        intensity=self._channel_intensity(law.number, to_num),
                        latency_ms=params["latency"],
                        decay_rate=params["decay"],
                        phase_shift=params["phase"],
                    ))
        
        print(f"[复杂度引擎] {len(self.channels)}条活通道已启动")
    
    def _channel_intensity(self, from_num: str, to_num: str) -> str:
        """根据法则在拓扑中的位置决定通道强度"""
        from_conn = len(self._topo.cross_ref_matrix.get(from_num, []))
        to_conn = len(self._topo.reverse_ref_matrix.get(to_num, []))
        total = from_conn + to_conn
        if total > 20:
            return "loud"
        elif total > 8:
            return "faint"
        else:
            return "latent"
    
    def tick(self, engine_snapshot: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        推进一步 -- 稀疏点火: 不是所有法则同时开火。
        只有活跃度超过阈值的才发射信号。每步只有一部分通道在传导。
        
        像真实神经系统: 安静的背景 + 偶尔的火花 + 不可预测的爆发。
        """
        self.tick_count += 1
        
        _name_to_num = {law.name_cn: law.number for law in self._topo.laws}
        
        # -- 1. 稀疏点火: 只有振幅 > 阈值的法则才发射 --
        fire_threshold = 0.55
        signals: List[LawSignal] = []
        for law in self._topo.laws:
            f = self.fields[law.number]
            effective_threshold = max(0.15, fire_threshold - f.chaos_level * 0.4)
            if f.base_amplitude < effective_threshold:
                continue
            refs = law.references
            # 发射数量 = 由引用密度和当前混沌度决定（不掷骰子）
            # 引用少→几乎全发射（边缘法则的小世界）
            # 引用多→稀疏一部分（核心法则的注意力分散）
            chaos_discount = 1.0 - f.chaos_level * 0.4  # 混沌时更分散
            fire_ratio = min(1.0, 0.15 + chaos_discount * 0.25)
            n_fire = max(1, int(len(refs) * fire_ratio))
            # 选哪些引用发射——按引用法则的当前振幅排序，选最活跃的
            ref_tuples = []
            for ref in refs:
                tn = ref if ref.isdigit() else _name_to_num.get(ref)
                if tn is None or tn not in self.fields:
                    continue
                ref_amp = self.fields[tn].base_amplitude
                ref_tuples.append((tn, ref_amp))
            ref_tuples.sort(key=lambda x: x[1], reverse=True)
            fired_refs = [t[0] for t in ref_tuples[:n_fire]]
            for to_num in fired_refs:
                if to_num not in self.fields:
                    continue
                # 振幅 = 源场振幅 * 目标共振率（不是随机）
                target_amp = self.fields[to_num].base_amplitude
                resonance = 0.5 + target_amp * 0.5  # 目标越活跃→信号越强
                signals.append(LawSignal(
                    source_law=law.number,
                    target_law=to_num,
                    amplitude=f.base_amplitude * resonance,
                    texture=f"{law.name_cn}:{self._sample_texture(f)}",
                    tick=self.tick_count,
                    hop_count=0,
                    path=[law.number, to_num],
                    interference_pattern="direct"
                ))
        
        # -- 2. 外部力场注入 --
        if engine_snapshot:
            engine_signals = self._inject_engine_forces(engine_snapshot)
            signals.extend(engine_signals)
        
        # -- 3. 稀疏传导: 通道强度决定是否被激活（不掷骰子） --
        all_signals = list(signals)
        max_hops = 3
        # 强度→传导率：不是概率，是每个通道固定的门控阈值
        INTENSITY_CONDUCTANCE = {'loud': 0.75, 'faint': 0.55, 'latent': 0.35, 'reverb': 0.2}
        
        for hop in range(max_hops):
            next_gen: List[LawSignal] = []
            for sig in all_signals:
                if sig.hop_count > hop:
                    continue
                for ch in self.channels:
                    if ch.from_law != sig.target_law or ch.to_law == sig.source_law:
                        continue
                    conductance = INTENSITY_CONDUCTANCE.get(ch.intensity, 0.3)
                    # 传导判断 = 信号振幅 × 通道传导率 × 相位匹配
                    # 如果振幅不够穿透通道，就不传导——这是物理，不是概率
                    phase_penalty = abs(ch.phase_shift) * 0.5
                    conduction_strength = sig.amplitude * conductance * (1.0 - phase_penalty)
                    if conduction_strength < 0.15:  # 门控阈值
                        continue
                    transmitted = ch.transmit(sig, self.tick_count)
                    if transmitted and transmitted.amplitude > 0.003:
                        next_gen.append(transmitted)
            
            if next_gen:
                all_signals.extend(next_gen[:30])
            else:
                break
        
        # -- 4. 吸收信号 --
        for sig in all_signals:
            if sig.target_law in self.fields:
                self.fields[sig.target_law].absorb(sig)
        
        # -- 4.5. 莫名情绪通道 ——
        # 信号在经过3+跳、经历多次干涉覆盖后，源头纹理被覆盖了。
        # 这些信号撞到情绪法则（法则6及其关联）时，产生"源不明"的情绪脉冲。
        # 身体层收到的是——"说不上来为什么，突然想哭"。
        self._unexplained_pulses: List[Dict[str, Any]] = []
        EMOTION_LAWS = {"6", "7", "8"}  # 情绪、身体情绪、社交情绪
        for sig in all_signals:
            if sig.target_law not in EMOTION_LAWS:
                continue
            # 信号走太远了——路径里干涉类型超过2种→源头丢了
            path_patterns = set()
            for sidx, s2 in enumerate(self._signal_history[-20:]):
                if s2.path and any(p in s2.path for p in sig.path):
                    path_patterns.add(s2.interference_pattern)
            if sig.hop_count >= 2 and len(path_patterns) >= 2:
                sig.source_traceable = False
                # 这个信号变成"莫名情绪脉冲"
                intensity = sig.amplitude * (1.0 + len(path_patterns) * 0.15)
                # 脉冲类型由目标情绪法则和到达时的干涉图案决定
                if sig.interference_pattern in ("cancelled", "intermediate"):
                    pulse_type = "低落"  # 信号被抵消后到达→空落感
                elif sig.interference_pattern == "noise":
                    pulse_type = "烦躁"  # 噪声信号→没来由的烦
                elif sig.interference_pattern == "amplified":
                    pulse_type = "莫名愉悦" if sig.target_law == "6" else "不安"
                else:
                    pulse_type = "空"  # 说不上来
                self._unexplained_pulses.append({
                    "type": pulse_type,
                    "intensity": min(1.0, intensity),
                    "target_law": sig.target_law,
                    "source_traceable": False,
                    "description": self._describe_pulse(pulse_type, intensity),
                })
        
        # 限制莫名脉冲数量——身体一次只能感受到这么多
        if len(self._unexplained_pulses) > 2:
            self._unexplained_pulses.sort(key=lambda p: p["intensity"], reverse=True)
            self._unexplained_pulses = self._unexplained_pulses[:2]
        
        # -- 5. 力场重平衡 --
        for field in self.fields.values():
            # 混沌飘移——取决于堆积信号的"方向"
            # 信号越多→飘移越大，方向由干涉类型决定
            if field.accumulated_signals:
                amplifications = sum(1 for s in field.accumulated_signals if s.interference_pattern == "amplified")
                cancellations = sum(1 for s in field.accumulated_signals if s.interference_pattern == "cancelled")
                pending_signals = len(field.accumulated_signals)
                drift = (amplifications - cancellations) / max(1, pending_signals)
                drift *= field.chaos_level * 0.08
            else:
                drift = 0.0
            field.base_amplitude = max(0.05, min(1.0, field.base_amplitude + drift))
            field.base_amplitude = field.base_amplitude * 0.97 + 0.5 * 0.03
            if len(field.accumulated_signals) > 50:
                field.accumulated_signals = field.accumulated_signals[-30:]
                field.texture_stack = field.texture_stack[-30:]
        
        # -- 6. 产出 --
        self._signal_history.extend(signals)
        if len(self._signal_history) > 500:
            self._signal_history = self._signal_history[-300:]
        
        return self._render_texture()
    
    def _sample_texture(self, field: LawField) -> str:
        """从当前力场中采样纹理 -- 自然语言"""
        if field.emergent_quality and field.emergent_quality != "还在成形":
            return f"涌现:{field.emergent_quality}"
        if field.texture_stack:
            return field.texture_stack[-1].split(';')[-1]
        return field.law_name
    
    def _describe_pulse(self, pulse_type: str, intensity: float) -> str:
        """描述一个源不明情绪脉冲——这就是角色对自己说不清的东西的感受"""
        if pulse_type == "低落":
            if intensity > 0.6:
                return "突然就很难过——说不上来为什么，就是心里往下一沉"
            else:
                return "有一瞬间觉得空荡荡的——也不知道是哪来的"
        elif pulse_type == "烦躁":
            if intensity > 0.6:
                return "没来由地烦——看什么都觉得不对，但说不出谁惹的"
            else:
                return "有点躁——就像房间里多了个声音，但找不到在哪"
        elif pulse_type == "莫名愉悦":
            if intensity > 0.6:
                return "嘴角突然翘了——不知道自己为什么高兴，但就是高兴了"
            else:
                return "有一小片阳光照进来了——也说不上是哪个方向的光"
        elif pulse_type == "不安":
            if intensity > 0.6:
                return "心突然揪了一下——什么都没发生，但身体先反应了"
            else:
                return "说不上来——就是觉得不太对，但又说不出哪里不对"
        elif pulse_type == "空":
            return "有一瞬间什么都感觉不到了——不是平静，是空"
        return "说不上来怎么了——就是不太对劲"
    
    def _inject_engine_forces(self, snapshot: Dict) -> List[LawSignal]:
        """把引擎层的状态注入为法则力场信号"""
        signals = []
        t = self.tick_count
        
        body = snapshot.get('body', {})
        if body.get('hunger') and body['hunger'] != '不饿':
            signals.append(LawSignal(
                source_law='BODY_ENGINE', target_law='1',
                amplitude=0.7, texture=f"身体引擎:饥饿={body['hunger']}",
                tick=t, hop_count=0, path=['BODY->1'],
                interference_pattern='direct'))
            signals.append(LawSignal(
                source_law='BODY_ENGINE', target_law='3',
                amplitude=0.6, texture="身体引擎:想吃东西",
                tick=t, hop_count=0, path=['BODY->3'],
                interference_pattern='direct'))
        if body.get('fatigue') and body['fatigue'] != '不累':
            signals.append(LawSignal(
                source_law='BODY_ENGINE', target_law='1',
                amplitude=0.5, texture=f"身体引擎:疲劳={body['fatigue']}",
                tick=t, hop_count=0, path=['BODY->1'],
                interference_pattern='direct'))
        
        mem = snapshot.get('memory', {})
        recent_memories = mem.get('recent_count', 0)
        if recent_memories > 0:
            signals.append(LawSignal(
                source_law='MEMORY_ENGINE', target_law='34',
                amplitude=0.4 * min(recent_memories/3, 1.5),
                texture=f"记忆引擎:新记忆={recent_memories}条",
                tick=t, hop_count=0, path=['MEMORY->34'],
                interference_pattern='direct'))
            signals.append(LawSignal(
                source_law='MEMORY_ENGINE', target_law='36',
                amplitude=0.3, texture="记忆引擎:痕迹在合并",
                tick=t, hop_count=0, path=['MEMORY->36'],
                interference_pattern='direct'))
        
        dist = snapshot.get('distance', {})
        if dist.get('interactions_today', 0) > 0:
            signals.append(LawSignal(
                source_law='DISTANCE_ENGINE', target_law='40',
                amplitude=0.5,
                texture=f"距离引擎:今日互动={dist['interactions_today']}次",
                tick=t, hop_count=0, path=['DIST->40'],
                interference_pattern='direct'))
        
        learn = snapshot.get('learning', {})
        if learn.get('new_domains', 0) > 0:
            signals.append(LawSignal(
                source_law='LEARN_ENGINE', target_law='16',
                amplitude=0.4,
                texture=f"学习引擎:新知识域={learn['new_domains']}",
                tick=t, hop_count=0, path=['LEARN->16'],
                interference_pattern='direct'))
        
        return signals
    
    def _render_texture(self) -> Dict[str, Any]:
        """
        渲染这一tick的"存在纹理"。
        
        不是导航图。不是状态报告。
        是"这一秒，这个人是什么样的" -- 不完整、有噪声、无法精确复述的现场感。
        """
        active = sorted(
            [f for f in self.fields.values() if len(f.accumulated_signals) > 0],
            key=lambda x: -x.chaos_level
        )
        
        deep = sorted(
            [f for f in self.fields.values() if len(f.accumulated_signals) <= 2 and f.base_amplitude > 0.4],
            key=lambda x: -x.base_amplitude
        )
        
        emergents = [
            f"{f.law_name}: {f.emergent_quality}"
            for f in self.fields.values()
            if f.emergent_quality and f.emergent_quality != "还在成形"
        ]
        
        interference_hotspots = []
        for f in self.fields.values():
            for src, pattern in f.interference_map.items():
                if pattern in ('amplified', 'harmonic', 'cancelled'):
                    src_field = self.fields.get(src)
                    src_name = src_field.law_name if src_field else src
                    interference_hotspots.append(
                        f"s.{src}({src_name}) ==> s.{f.law_number}({f.law_name}): {pattern}"
                    )
        
        return {
            'tick': self.tick_count,
            'total_signals_this_tick': sum(1 for s in self._signal_history if s.tick == self.tick_count),
            'cumulative_signals': len(self._signal_history),
            
            'loudest': [
                {'law': f.law_name, 'number': f.law_number, 
                 'signals_count': len(f.accumulated_signals),
                 'signal_sources': list(set(s.source_law for s in f.accumulated_signals[-10:])),
                 'interference_counts': self._count_interference_types(f),
                 'emergent': f.emergent_quality}
                for f in active[:8]
            ],
            
            'deepest_quiet': [
                {'law': f.law_name, 'number': f.law_number,
                 'signals_count': len(f.accumulated_signals),
                 'signal_sources': list(set(s.source_law for s in f.accumulated_signals)),
                 'emergent': f.emergent_quality}
                for f in deep[:5]
            ],
            
            'emergents': emergents[:8],
            
            'interference': interference_hotspots[:10],
            
            'chaos_summary': self._chaos_narrative(active[:5]),
            
            'unpredictability_mark': self._unpredictability_mark(),
            
            'unexplained_pulses': self._unexplained_pulses,
        }
    
    def _chaos_narrative(self, top_active: List[LawField]) -> str:
        """只给事实——哪条法则收到了多少信号、信号从哪来。"""
        if not top_active:
            return "力场在背景中缓慢流动，没有明显的信号堆积。"
        
        parts = []
        for f in top_active[:5]:
            n = len(f.accumulated_signals)
            sources = set(s.source_law for s in f.accumulated_signals[-10:])
            source_names = ', '.join(sorted(sources)[:3])
            if n > 10:
                parts.append(f"{f.law_name}堆了{n}个信号——主要从{source_names}来的")
            elif n > 3:
                parts.append(f"{f.law_name}积了{n}个信号——来自{source_names}")
            else:
                parts.append(f"{f.law_name}上落了{n}个信号")
        
        return '。'.join(parts) + '。'
        
        
        # 附加涌现描述
        emergent_desc = [
            f"({f.emergent_quality})" 
            for f in top_active[:3] 
            if f.emergent_quality and f.emergent_quality != "还在成形"
        ]
        if emergent_desc:
            parts.extend(emergent_desc)
        
        if not parts:
            return "力场在流动但没有明显的信号堆积。"
        
        return "。".join(parts) + "。"
    
    def _count_interference_types(self, field: LawField) -> Dict[str, int]:
        """统计一个力场上的干涉类型分布——事实，不给感受标签。"""
        counts = {}
        for pattern in field.interference_map.values():
            counts[pattern] = counts.get(pattern, 0) + 1
        return counts
    
    def _unpredictability_mark(self) -> str:
        """这一tick信号通路的基本事实——不替LLM判断"混乱程度"。"""
        chaos_sum = sum(f.chaos_level for f in self.fields.values())
        n = max(len(self.fields), 1)
        avg_chaos = chaos_sum / n
        
        # 给 LLM 的是现象事实，不是结论标签
        total_signals_this_tick = sum(1 for s in self._signal_history if s.tick == self.tick_count)
        active_fields = sum(1 for f in self.fields.values() if len(f.accumulated_signals) > 0)
        interference_count = sum(
            1 for f in self.fields.values() 
            for p in f.interference_map.values() 
            if p in ('amplified', 'cancelled', 'harmonic')
        )
        
        if avg_chaos < 0.1:
            s = f"仅{total_signals_this_tick}个信号，{active_fields}条通道有动静"
        elif avg_chaos < 0.25:
            s = f"{total_signals_this_tick}个信号在跑，{active_fields}条通道参与"
        elif avg_chaos < 0.4:
            s = f"{total_signals_this_tick}个信号在{active_fields}条通道间穿行，{interference_count}处干涉"
        elif avg_chaos < 0.6:
            s = f"{total_signals_this_tick}个信号挤在系统里，{interference_count}处干涉，源头部分丢失"
        else:
            s = f"{total_signals_this_tick}个信号+{interference_count}处干涉，已无单条可追踪路径"
        
        return s
    
    def describe_for_llm(self) -> str:
        """给LLM的存在纹理描述——只呈现现象事实，不替LLM感受。"""
        texture = self._render_texture()
        
        lines = []
        lines.append(f"== 第{texture['tick']}秒的存在纹理 ==")
        lines.append(f"这一秒，{texture['total_signals_this_tick']}股力场在{len(self.fields)}条法则间穿行。")
        lines.append(f"累积传过{texture['cumulative_signals']}个信号——每一个都在法则网上留下了痕迹。")
        lines.append("")
        lines.append(texture['unpredictability_mark'])
        lines.append("")
        
        if texture['loudest']:
            lines.append("信号最密集的节点:")
            for l in texture['loudest'][:5]:
                sources = ', '.join(l.get('signal_sources', [])[:3])
                interference = l.get('interference_counts', {})
                interference_str = ''
                if interference:
                    parts = []
                    for k, v in interference.items():
                        if k == 'amplified': parts.append(f'{v}处放大')
                        elif k == 'cancelled': parts.append(f'{v}处抵消')
                        elif k == 'harmonic': parts.append(f'{v}处共振')
                    if parts:
                        interference_str = f'，{"、".join(parts)}'
                lines.append(f"  s.{l['number']} {l['law']}: 堆了{l['signals_count']}个信号——从{sources}来的{interference_str}")
                if l['emergent'] and l['emergent'] != '还在成形':
                    lines.append(f"    -> {l['emergent']}")
        
        if texture['deepest_quiet']:
            lines.append("")
            lines.append("信号最少但一直没散的节点:")
            for d in texture['deepest_quiet'][:3]:
                sources = ', '.join(d.get('signal_sources', [])[:3])
                lines.append(f"  s.{d['number']} {d['law']}: 只有{d['signals_count']}个信号——来自{sources}")
        
        if texture['emergents']:
            lines.append("")
            lines.append("这一秒在涌现的新东西:")
            for e in texture['emergents'][:5]:
                lines.append(f"  -> {e}")
        
        if texture['interference']:
            lines.append("")
            lines.append("干涉热点:")
            for i in texture['interference'][:5]:
                lines.append(f"  {i}")
        
        lines.append("")
        lines.append(texture['chaos_summary'])
        lines.append("")
        lines.append("== 注意: 这只是这一秒的切片。下一秒完全不同。不需要记住这个状态。它会自己消失。")
        
        return '\n'.join(lines)
    
    def snapshot_for_llm(self) -> Dict[str, Any]:
        return self._render_texture()


# =======================================================================
# 自测: 让复杂度引擎跑起来
# =======================================================================

if __name__ == '__main__':
    print("=" * 60)
    print("复杂度引擎自测 -- 让拓扑活起来")
    print("=" * 60)
    print()
    
    ce = ComplexityEngine()
    print(f"法则: {len(ce.fields)}条")
    print(f"通道: {len(ce.channels)}条")
    print()
    
    for i in range(10):
        engine_snap = {}
        if i == 1:
            engine_snap['body'] = {'hunger': '有点饿', 'fatigue': '不累'}
        if i == 3:
            engine_snap['memory'] = {'recent_count': 2}
        if i == 4:
            engine_snap['body'] = {'hunger': '饿', 'fatigue': '有点累'}
            engine_snap['distance'] = {'interactions_today': 3}
        if i == 6:
            engine_snap['learning'] = {'new_domains': 1}
        if i == 8:
            engine_snap['body'] = {'hunger': '很饿', 'fatigue': '累'}
            engine_snap['memory'] = {'recent_count': 5}
            engine_snap['distance'] = {'interactions_today': 5}
        
        result = ce.tick(engine_snap if engine_snap else None)
        
        if i % 2 == 0 or i == 9:
            print(f"[tick {i}] 信号{result['total_signals_this_tick']}股 "
                  f"混乱top: {'、'.join(l['law'] for l in result['loudest'][:3])}")
            print(f"          {result['unpredictability_mark']}")
    
    print()
    print("=" * 60)
    print("LLM描述样例(最后1个tick):")
    print("=" * 60)
    print(ce.describe_for_llm())
