# memory_law34.py — SKILL.md 第34条记忆法则的Python实现
#
# 船长：SKILL.md §34  —— 记忆法则（双轨+三重+负债+认知修改）
# 副手：Python引擎  —— 索引（存了什么、关联什么线索、被提取几次、距上次多久）
#
# Python不判断重量。Python给LLM准备精确的索引材料，
# LLM在SKILL.md的语境下决定这条记忆的重量、沉积层厚度、情感负债利息。
#
# ─── 双轨系统 ───
# 轨道1：痕迹锚定记忆 — 被物理指针拴住，被动触发，高保真
# 轨道2：纯情景记忆   — 可主动叙述，叙事结构，每次提取都是重建
#
# ─── 四种记忆子类型 ───
# 硬核记忆：刻骨铭心，永不褪色（双轨交叠区）
# 模式记忆：模糊但持续更新（主纯情景，久后滑入痕迹锚定）
# 日常碎片：按天流失，轻微情绪标记
# 痕迹锚定记忆：物理指针拴住的记忆（气味/声音/光线/触感）
#
# ─── 记忆的生命周期 ───
# 沉积层：每次提取叠加新理解→记忆不是失真，是增密
# 情感负债：未清算的情绪挂账→按重量×时间因子计息
# 认知修改：每次提取都是一次重写→三种路径(叙事缓冲/保护性改写/衰退合并)
# 痕迹合并：时间相近的情绪事件→冗余消除→不可恢复原分轨的混音

import time
import json
import hashlib
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Set, Tuple
from datetime import datetime, timedelta


# ============================================================
# 第一部分：记忆的基础结构
# ============================================================

class MemoryClass(Enum):
    """
    记忆的等级——不是Python决定的，是LLM在建立记忆时赋予的。
    Python只管存和查。
    """
    HARDCORE = auto()         # 硬核记忆——刻骨铭心，永不褪色
    PATTERN = auto()           # 模式记忆——模糊但持续更新
    DAILY_FRAGMENT = auto()   # 日常碎片——按天流失
    TRACE_ANCHORED = auto()   # 痕迹锚定——被物理指针拴住


class MemoryTrack(Enum):
    """双轨——同一条记忆可以同时存在于两条轨道上"""
    TRACE_ANCHOR = auto()   # 痕迹锚定——被某个物理指针拴着，被动触发
    PURE_SCENARIO = auto()  # 纯情景——可主动叙述
    BOTH = auto()            # 双轨交叠——硬核记忆的特征


class ModificationType(Enum):
    """认知修改的三种路径——全部在水面以下运行，角色意识不到"""
    NARRATIVE_BUFFER = auto()   # 叙事缓冲——把"被羞辱"改写成"下次要更严谨"
    PROTECTIVE = auto()         # 保护性改写——把"被放弃"改写成"大家都挺忙"
    DECAY_MERGE = auto()        # 衰退合并——两次沉默合成"他总是沉默"


# ============================================================
# 第二部分：痕迹锚定——记忆被物理指针拴住
# ============================================================

@dataclass
class TraceAnchor:
    """
    一条物理指针——一个具体可感的东西拴住了一份记忆。
    没有这个指针，这份记忆不会被触发。但它不是不存在——是没有钥匙。
    
    四种物理锚点（来自 SKILL.md §34.1）：
    - 气味：洗衣液、机油、粥味、雨后泥土
    - 声音：一首歌、一种语气、电梯到达的"叮"
    - 光线：某个角度、某天的天色、黄昏的颜色
    - 触觉/温度：毛衣的质感、水龙头的冷热、他靠近时的温度变化
    """
    anchor_id: str
    modality: str               # "smell" | "sound" | "light" | "touch" | "taste" | "temperature"
    trigger_detail: str         # 具体是什么——"薰衣草洗衣液的味道" / "他惯用的那种语气"
    linked_memory_ids: List[str] = field(default_factory=list)  # 拴着哪些记忆
    last_triggered_at: Optional[float] = None
    trigger_count: int = 0
    
    def trigger(self):
        """指针被环境触碰——所有拴在上面的记忆一起荡"""
        self.last_triggered_at = time.time()
        self.trigger_count += 1
        return self.linked_memory_ids


# ============================================================
# 第三部分：一条记忆的完整数据结构
# ============================================================

@dataclass
class MemoryRecord:
    """
    一条记忆。
    
    Python 管精确的：
    - 什么时候存的（timestamp）
    - 存在哪条轨道上（track）
    - 被提取了几次（extraction_count）
    - 每次提取时角色是什么状态（extraction_snapshots）
    - 关联了哪些线索标签（cue_tags）
    - 有没有活跃的情感负债（emotional_debt）
    - 认知修改的记录（modifications）
    
    LLM 管活的部分：
    - 这是硬核还是模式还是日常碎片（memory_class）
    - 沉积层有多厚——反复提取叠加了多少新理解（sedimentary_depth_described）
    - 情感负债产生了多少利息——下次互动时初始距离怎么变
    - 纯情景版本和痕迹锚定版本现在对齐吗
    - 这次提取是否触发了认知修改
    """
    memory_id: str
    created_at: float                          # 创建时间戳
    
    # ─── LLM 决定的重量 ───
    memory_class: MemoryClass                  # 硬核/模式/日常/痕迹锚定
    
    # ─── LLM 写的内容 ───
    trace_version: str = ""                    # 痕迹锚定版本——被触发时回放的画面
    scenario_version: str = ""                 # 纯情景版本——能讲出来的叙事
    key_emotion: str = ""                      # 核心情绪
    intensity_at_creation: str = ""            # 创建时的情绪强度
    people_involved: List[str] = field(default_factory=list)  # 涉及的人
    
    # ─── Python 精确追踪 ───
    tracks: List[MemoryTrack] = field(default_factory=list)  # 存在哪几条轨道上
    extraction_count: int = 0                  # 被提取了几次
    extraction_snapshots: List[Dict] = field(default_factory=list)  # 每次提取时的角色状态快照
    cue_tags: List[str] = field(default_factory=list)               # 线索标签
    trace_anchor_ids: List[str] = field(default_factory=list)       # 拴着它的物理指针
    
    # ─── 沉积层 ───
    sedimentary_additions: List[str] = field(default_factory=list)  # 每次提取追加的新理解
    sedimentary_depth_described: str = ""                           # LLM 写的沉积层厚度描述
    
    # ─── 情感负债 ───
    emotional_debt: Optional[Dict[str, Any]] = None  # {person, amount_desc, interest_rate_desc, last_accrued}
    
    # ─── 认知修改 ───
    modifications: List[Dict[str, Any]] = field(default_factory=list)
    # 每条修改: {mod_type, timestamp, pre_state_summary, post_state_summary, trigger_context}
    
    # ─── 生命周期 ───
    last_extracted_at: Optional[float] = None
    is_merged: bool = False                    # 是否被痕迹合并过
    merged_from: List[str] = field(default_factory=list)  # 从哪些记忆合并而来
    
    def describe_for_llm(self) -> Dict[str, Any]:
        """给LLM准备的结构化记忆快照——不包含Python元数据，只包含LLM需要的"""
        return {
            "memory_id": self.memory_id,
            "created_at_human": datetime.fromtimestamp(self.created_at).strftime("%Y-%m-%d %H:%M"),
            "memory_class": self.memory_class.name,
            "tracks": [t.name for t in self.tracks],
            "trace_version": self.trace_version or "(not yet described)",
            "scenario_version": self.scenario_version or "(not yet described)",
            "key_emotion": self.key_emotion or "(unknown)",
            "intensity_at_creation": self.intensity_at_creation or "(unknown)",
            "people_involved": self.people_involved,
            "extraction_count": self.extraction_count,
            "days_since_creation": round((time.time() - self.created_at) / 86400, 1),
            "days_since_last_extraction": (
                round((time.time() - self.last_extracted_at) / 86400, 1)
                if self.last_extracted_at else "never"
            ),
            "sedimentary_additions_count": len(self.sedimentary_additions),
            "sedimentary_depth_described": self.sedimentary_depth_described or "(not yet assessed)",
            "has_emotional_debt": self.emotional_debt is not None,
            "emotional_debt": self._describe_debt_for_llm(),
            "modification_count": len(self.modifications),
            "latest_modification": self.modifications[-1] if self.modifications else None,
            "is_merged": self.is_merged,
            "merged_from_count": len(self.merged_from),
            "cue_tags": self.cue_tags,
            "trace_anchor_modalities": [],  # filled by engine when needed
        }
    
    def _describe_debt_for_llm(self) -> Optional[Dict]:
        if not self.emotional_debt:
            return None
        d = dict(self.emotional_debt)
        # 把时间戳转成人类可读
        if "last_accrued" in d:
            d["last_accrued_human"] = datetime.fromtimestamp(d["last_accrued"]).strftime("%Y-%m-%d %H:%M")
        return d
    
    def mark_extracted(self, character_state: Dict[str, Any]):
        """记录一次提取——沉积层增密"""
        self.extraction_count += 1
        self.last_extracted_at = time.time()
        self.extraction_snapshots.append({
            "timestamp": time.time(),
            "character_mood": character_state.get("mood", "unknown"),
            "character_fatigue": character_state.get("fatigue", "unknown"),
            "character_social_energy": character_state.get("social_energy", "unknown"),
            "current_context": character_state.get("context", "unknown"),
        })
    
    def add_sedimentary_layer(self, new_understanding: str):
        """沉积层追加——不是失真，是增密"""
        self.sedimentary_additions.append({
            "timestamp": time.time(),
            "understanding": new_understanding
        })
    
    def add_cognitive_modification(self, 
                                    mod_type: ModificationType,
                                    pre_state: str,
                                    post_state: str,
                                    trigger: str):
        """
        认知修改——在水面以下运行。
        角色意识不到这次修改。对角色来说，"我记得当时就是这样"。
        """
        self.modifications.append({
            "mod_type": mod_type.name,
            "timestamp": time.time(),
            "pre_state_summary": pre_state,
            "post_state_summary": post_state,
            "trigger_context": trigger,
        })


# ============================================================
# 第四部分：记忆存储引擎 —— Python 的精确活儿
# ============================================================

class MemoryStorage:
    """
    记忆的存储、索引、检索。
    
    这是Python能精确做的事：
    - 存记忆（带时间戳、线索标签、物理指针映射）
    - 查记忆（按标签、按人、按时间范围、按轨道）
    - 统计（各类型的数量、负债情况、提取频次）
    - 整理（检测可合并的相似记忆）
    
    Python不做的事：
    - 判断一条记忆是硬核还是模式——那是LLM根据SKILL.md §34.3判断的
    - 计算情感负债的利息金额——那是LLM根据关系和情境判断的
    - 决定沉积层加什么新理解——那是LLM在提取的瞬间决定的
    """
    
    def __init__(self):
        self.memories: Dict[str, MemoryRecord] = {}
        self.trace_anchors: Dict[str, TraceAnchor] = {}
        self.debt_ledger: List[Dict[str, Any]] = []  # 情感负债账本
    
    # ─── 存储 ───
    
    def store(self, 
              event_description: str,
              memory_class: MemoryClass,
              key_emotion: str,
              intensity: str,
              people: List[str],
              tracks: List[MemoryTrack],
              cue_tags: List[str],
              trace_anchor_ids: List[str] = [],
              trace_version: str = "",
              scenario_version: str = "",
              emotional_debt: Optional[Dict] = None) -> str:
        """
        存一条新记忆。返回 memory_id。
        
        调用时机：任何有情绪重量的事件发生后。
        谁决定 memory_class？LLM。Python只管收数据入库。
        """
        memory_id = self._generate_id(event_description)
        now = time.time()
        
        record = MemoryRecord(
            memory_id=memory_id,
            created_at=now,
            memory_class=memory_class,
            trace_version=trace_version,
            scenario_version=scenario_version,
            key_emotion=key_emotion,
            intensity_at_creation=intensity,
            people_involved=people,
            tracks=tracks,
            extraction_count=0,
            cue_tags=cue_tags,
            trace_anchor_ids=trace_anchor_ids,
            emotional_debt=emotional_debt,
        )
        
        self.memories[memory_id] = record
        
        # 如果有情感负债，记入账本
        if emotional_debt:
            self.debt_ledger.append({
                "memory_id": memory_id,
                "created_at": now,
                "person": emotional_debt.get("person", "unknown"),
                "amount_desc": emotional_debt.get("amount_desc", ""),
                "interest_rate_desc": emotional_debt.get("interest_rate_desc", ""),
                "last_accrued": now,
                "is_active": True,
            })
        
        # 如果有物理指针，注册到锚点系统
        for anchor_id in trace_anchor_ids:
            if anchor_id in self.trace_anchors:
                self.trace_anchors[anchor_id].linked_memory_ids.append(memory_id)
        
        return memory_id
    
    # ─── 检索 ───
    
    def retrieve(self, memory_id: str, character_state: Dict[str, Any]) -> Optional[MemoryRecord]:
        """
        提取一条记忆。
        
        副手做的事：
        1. 找到记忆
        2. 记录提取（extraction_count++, 快照存储）
        3. 返回记忆的完整结构供 LLM 使用
        
        船长（LLM）收到后做的事：
        - 评估这次提取是否触发了沉积层追加
        - 评估这次提取是否触发了认知修改
        - 决定这条记忆在当前时刻的"重量"
        """
        record = self.memories.get(memory_id)
        if record:
            record.mark_extracted(character_state)
        return record
    
    def search_by_cue(self, cue_tag: str) -> List[MemoryRecord]:
        """按线索标签检索——一个词、一个人名、一种情绪"""
        results = []
        for mem in self.memories.values():
            if cue_tag in mem.cue_tags or cue_tag in mem.people_involved:
                results.append(mem)
        # 按提取次数降序——常被提起的记忆更可能是相关的
        results.sort(key=lambda m: m.extraction_count, reverse=True)
        return results
    
    def search_by_person(self, person_name: str) -> List[MemoryRecord]:
        """检索与某人相关的所有记忆"""
        return self.search_by_cue(person_name)
    
    def search_by_time(self, days_ago: int) -> List[MemoryRecord]:
        """检索最近N天内的记忆"""
        cutoff = time.time() - days_ago * 86400
        results = [m for m in self.memories.values() if m.created_at >= cutoff]
        results.sort(key=lambda m: m.created_at, reverse=True)
        return results
    
    def search_by_emotion(self, emotion: str) -> List[MemoryRecord]:
        """按情绪检索"""
        results = [m for m in self.memories.values() 
                   if emotion.lower() in m.key_emotion.lower()]
        results.sort(key=lambda m: m.extraction_count, reverse=True)
        return results
    
    def find_high_frequency_memories(self, min_extractions: int = 10) -> List[MemoryRecord]:
        """
        找到被反复提取的记忆——这些很可能是硬核记忆或沉积层极厚的记忆。
        Python提供数据，LLM决定"为什么被反复提"。
        """
        results = [m for m in self.memories.values() if m.extraction_count >= min_extractions]
        results.sort(key=lambda m: m.extraction_count, reverse=True)
        return results
    
    def find_rarely_touched_but_heavy(self) -> List[MemoryRecord]:
        """
        找到很少被提取但创建时强度很高的记忆——埋在深层但一碰就碎。
        这些可能是痕迹锚定记忆在等待物理指针触发。
        """
        results = [m for m in self.memories.values()
                   if m.extraction_count < 5 
                   and m.intensity_at_creation in ("strong", "very_strong", "overwhelming")
                   and m.memory_class in (MemoryClass.TRACE_ANCHORED, MemoryClass.HARDCORE)]
        results.sort(key=lambda m: m.created_at)
        return results
    
    # ─── 痕迹锚定检索 ───
    
    def get_by_trace_anchor(self, anchor_id: str) -> List[MemoryRecord]:
        """物理指针被触发——拽出所有拴在上面的记忆"""
        anchor = self.trace_anchors.get(anchor_id)
        if not anchor:
            return []
        triggered_ids = anchor.trigger()  # 记录触发
        return [self.memories[mid] for mid in triggered_ids if mid in self.memories]
    
    def register_trace_anchor(self, 
                               modality: str, 
                               trigger_detail: str) -> str:
        """
        注册一个物理指针。
        例如：register_trace_anchor("smell", "薰衣草洗衣液")
        返回 anchor_id 供后续拴记忆用。
        """
        anchor_id = f"anchor_{modality}_{hashlib.md5(trigger_detail.encode()).hexdigest()[:8]}"
        if anchor_id not in self.trace_anchors:
            self.trace_anchors[anchor_id] = TraceAnchor(
                anchor_id=anchor_id,
                modality=modality,
                trigger_detail=trigger_detail,
            )
        return anchor_id
    
    # ─── 债务系统 ───
    
    def get_active_debts(self, person: Optional[str] = None) -> List[Dict]:
        """获取活跃的情感负债"""
        debts = [d for d in self.debt_ledger if d.get("is_active", True)]
        if person:
            debts = [d for d in debts if d.get("person") == person]
        return debts
    
    def accrue_interest(self) -> List[Dict]:
        """
        计息——对所有活跃负债按时间流逝累积利息。
        
        Python 做的事：找到所有活跃负债，计算距上次计息的天数。
        LLM 做的事：决定"这笔债在这个人身上，过了这些天，实际产生了多少'利息'"。
        利息单位不是数字——是"下次互动时会往后退半步"、"递玩笑前会犹豫十分之一秒"。
        """
        now = time.time()
        accrued = []
        for debt in self.debt_ledger:
            if not debt.get("is_active", True):
                continue
            days_passed = (now - debt.get("last_accrued", now)) / 86400
            if days_passed >= 1:  # 至少过了一天
                debt["last_accrued"] = now
                debt["days_since_last_accrual"] = round(days_passed, 1)
                accrued.append(dict(debt))
        return accrued
    
    def mark_debt_settled(self, memory_id: str):
        """一笔情感负债清算完毕——关系恢复了，债还了"""
        for debt in self.debt_ledger:
            if debt.get("memory_id") == memory_id:
                debt["is_active"] = False
                debt["settled_at"] = time.time()
    
    # ─── 合并检测 ───
    
    def find_merge_candidates(self, 
                               days_window: int = 34,
                               min_emotion_similarity: int = 1) -> List[Tuple[MemoryRecord, MemoryRecord]]:
        """
        检测可合并的相似记忆（服务于 SKILL.md §36 留白·痕迹合并）。
        
        34天窗口来自 SKILL.md：34天前那个人的两次沉默合成了"他总是沉默"。
        Python 只看时间接近+涉及同一个人——具体是否合并由 LLM 决定。
        """
        now = time.time()
        cutoff = now - days_window * 86400
        recent = [m for m in self.memories.values() 
                  if m.created_at >= cutoff and m.memory_class != MemoryClass.HARDCORE]
        
        candidates = []
        for i in range(len(recent)):
            for j in range(i + 1, len(recent)):
                m1, m2 = recent[i], recent[j]
                # 涉及同一个人
                shared_people = set(m1.people_involved) & set(m2.people_involved)
                if not shared_people:
                    continue
                # 时间接近（7天内）
                time_diff = abs(m1.created_at - m2.created_at) / 86400
                if time_diff <= 7:
                    # 情绪关键词有重叠
                    emotion_overlap = (m1.key_emotion.lower() in m2.key_emotion.lower() 
                                       or m2.key_emotion.lower() in m1.key_emotion.lower())
                    if emotion_overlap or shared_people:
                        candidates.append((m1, m2))
        
        return candidates
    
    # ─── 信息汇总（给 LLM 的完整报告） ───
    
    def memory_snapshot_for_llm(self, 
                                 person: Optional[str] = None,
                                 context: str = "",
                                 limit: int = 20) -> Dict[str, Any]:
        """
        为 LLM 准备一份记忆总览——当前状态、相关的记忆、待处理的负债。
        
        这是 soul_bridge.py 中 Law 34 走 HYBRID 路径时的核心输出。
        Python 提供精确数据，LLM 在弹出的语境下读取和判断。
        """
        relevant = []
        
        if person:
            relevant = self.search_by_person(person)
        elif context:
            relevant = self.search_by_cue(context)
        
        # 加上高提取频次的记忆（不管是否相关——反复提的记忆本身就重要）
        high_freq = self.find_high_frequency_memories(min_extractions=5)
        for m in high_freq:
            if m not in relevant:
                relevant.append(m)
        
        # 硬核记忆永远在列
        hardcore = [m for m in self.memories.values() if m.memory_class == MemoryClass.HARDCORE]
        for m in hardcore:
            if m not in relevant:
                relevant.append(m)
        
        # 限制数量，按提取次数排序
        relevant.sort(key=lambda m: m.extraction_count, reverse=True)
        relevant = relevant[:limit]
        
        # 活跃负债
        active_debts = self.get_active_debts(person)
        
        # 可合并的记忆对
        merge_candidates = self.find_merge_candidates()
        
        # 低提取但高强度的记忆（埋在深层）
        buried = self.find_rarely_touched_but_heavy()
        
        return {
            "total_memories": len(self.memories),
            "memory_class_distribution": {
                cls.name: len([m for m in self.memories.values() if m.memory_class == cls])
                for cls in MemoryClass
            },
            "relevant_memories": [m.describe_for_llm() for m in relevant],
            "hardcore_memories": [m.describe_for_llm() for m in hardcore],
            "active_emotional_debts": [{
                "memory_id": d.get("memory_id"),
                "person": d.get("person"),
                "amount": d.get("amount_desc"),
                "interest": d.get("interest_rate_desc"),
                "days_since_last_accrual": d.get("days_since_last_accrual", 0),
            } for d in active_debts],
            "merge_candidates_count": len(merge_candidates),
            "merge_candidate_pairs": [
                {
                    "memory_1": m1.describe_for_llm(),
                    "memory_2": m2.describe_for_llm(),
                    "shared_people": list(set(m1.people_involved) & set(m2.people_involved)),
                    "days_apart": round(abs(m1.created_at - m2.created_at) / 86400, 1),
                }
                for m1, m2 in merge_candidates[:5]
            ],
            "buried_heavy_memories": [m.describe_for_llm() for m in buried[:5]],

        }
    
    # ─── 序列化 ───
    
    def to_dict(self) -> Dict:
        """保存记忆到文件"""
        return {
            "memories": {mid: {
                "memory_class": m.memory_class.name,
                "created_at": m.created_at,
                "trace_version": m.trace_version,
                "scenario_version": m.scenario_version,
                "key_emotion": m.key_emotion,
                "intensity_at_creation": m.intensity_at_creation,
                "people_involved": m.people_involved,
                "tracks": [t.name for t in m.tracks],
                "extraction_count": m.extraction_count,
                "extraction_snapshots": m.extraction_snapshots,
                "cue_tags": m.cue_tags,
                "trace_anchor_ids": m.trace_anchor_ids,
                "sedimentary_additions": m.sedimentary_additions,
                "sedimentary_depth_described": m.sedimentary_depth_described,
                "emotional_debt": m.emotional_debt,
                "modifications": m.modifications,
                "last_extracted_at": m.last_extracted_at,
                "is_merged": m.is_merged,
                "merged_from": m.merged_from,
            } for mid, m in self.memories.items()},
            "trace_anchors": {aid: {
                "modality": a.modality,
                "trigger_detail": a.trigger_detail,
                "linked_memory_ids": a.linked_memory_ids,
                "trigger_count": a.trigger_count,
                "last_triggered_at": a.last_triggered_at,
            } for aid, a in self.trace_anchors.items()},
            "debt_ledger": self.debt_ledger,
        }
    
    def save_to_file(self, filepath: str):
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)
    
    @classmethod
    def load_from_file(cls, filepath: str) -> 'MemoryStorage':
        storage = cls()
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return storage
        
        # 恢复记忆
        for mid, md in data.get("memories", {}).items():
            record = MemoryRecord(
                memory_id=mid,
                created_at=md["created_at"],
                memory_class=MemoryClass[md["memory_class"]],
                trace_version=md.get("trace_version", ""),
                scenario_version=md.get("scenario_version", ""),
                key_emotion=md.get("key_emotion", ""),
                intensity_at_creation=md.get("intensity_at_creation", ""),
                people_involved=md.get("people_involved", []),
                tracks=[MemoryTrack[t] for t in md.get("tracks", [])],
                extraction_count=md.get("extraction_count", 0),
                extraction_snapshots=md.get("extraction_snapshots", []),
                cue_tags=md.get("cue_tags", []),
                trace_anchor_ids=md.get("trace_anchor_ids", []),
                sedimentary_additions=md.get("sedimentary_additions", []),
                sedimentary_depth_described=md.get("sedimentary_depth_described", ""),
                emotional_debt=md.get("emotional_debt"),
                modifications=md.get("modifications", []),
                last_extracted_at=md.get("last_extracted_at"),
                is_merged=md.get("is_merged", False),
                merged_from=md.get("merged_from", []),
            )
            storage.memories[mid] = record
        
        # 恢复痕迹锚点
        for aid, ad in data.get("trace_anchors", {}).items():
            anchor = TraceAnchor(
                anchor_id=aid,
                modality=ad["modality"],
                trigger_detail=ad["trigger_detail"],
                linked_memory_ids=ad.get("linked_memory_ids", []),
                trigger_count=ad.get("trigger_count", 0),
                last_triggered_at=ad.get("last_triggered_at"),
            )
            storage.trace_anchors[aid] = anchor
        
        storage.debt_ledger = data.get("debt_ledger", [])
        
        return storage
    
    # ─── 工具 ───
    
    def _generate_id(self, base: str) -> str:
        h = hashlib.md5(f"{base}{time.time()}".encode()).hexdigest()[:12]
        return f"mem_{h}"
    
    def __len__(self):
        return len(self.memories)


# ============================================================
# 第五部分：自测
# ============================================================

if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    
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
    print("memory_law34.py 自测 — SKILL.md §34 记忆法则引擎")
    print("=" * 60)
    
    store = MemoryStorage()
    
    # ─── 测试组1：基础存储 ───
    print("\n[1] 基础存储")
    
    # 创建一些物理指针
    laundry_anchor = store.register_trace_anchor("smell", "薰衣草洗衣液")
    song_anchor = store.register_trace_anchor("sound", "那首在雨天听到的歌")
    light_anchor = store.register_trace_anchor("light", "黄昏的光线角度")
    
    test("1.1 注册3个物理指针", len(store.trace_anchors) == 3,
         str(len(store.trace_anchors)))
    
    # 存一条硬核记忆
    mid1 = store.store(
        event_description="第一次考第一名，妈妈在厨房说'你是我的骄傲'",
        memory_class=MemoryClass.HARDCORE,
        key_emotion="骄傲与温暖",
        intensity="very_strong",
        people=["妈妈", "自己"],
        tracks=[MemoryTrack.BOTH],
        cue_tags=["妈妈", "第一次", "考试", "骄傲", "厨房"],
        trace_version="闻到油烟气就想起那天——阳光斜着从厨房窗户照在妈妈手上的热气里",
        scenario_version="十二岁那年第一次考第一，妈妈在厨房里说我是她的骄傲。那年我还不懂她婚姻有多难。",
    )
    
    test("1.2 存储硬核记忆", mid1.startswith("mem_"), mid1)
    test("1.3 记忆入库", len(store.memories) == 1)
    
    # 存一条痕迹锚定记忆
    mid2 = store.store(
        event_description="前女友的洗衣液味道——在超市日化区闻到，推车的手慢了半拍",
        memory_class=MemoryClass.TRACE_ANCHORED,
        key_emotion="惆怅与怀念",
        intensity="strong",
        people=["前女友"],
        tracks=[MemoryTrack.TRACE_ANCHOR],
        cue_tags=["前女友", "洗衣液", "超市", "怀念"],
        trace_anchor_ids=[laundry_anchor],
        trace_version="薰衣草味。她在的时候用的那款。手自己停了半拍。",
    )
    
    test("1.4 存储痕迹锚定记忆", mid2.startswith("mem_"))
    test("1.5 指针拴住记忆", mid2 in store.trace_anchors[laundry_anchor].linked_memory_ids)
    
    # 存一条带情感负债的记忆
    mid3 = store.store(
        event_description="他上次接不住我的玩笑",
        memory_class=MemoryClass.PATTERN,
        key_emotion="轻微的失落",
        intensity="medium",
        people=["他"],
        tracks=[MemoryTrack.PURE_SCENARIO],
        cue_tags=["他", "玩笑", "未被接住", "犹豫"],
        trace_version="那个瞬间——我说完之后他愣了一下，空气停了半秒",
        emotional_debt={
            "person": "他",
            "amount_desc": "中等——下次递玩笑前会犹豫十分之一秒",
            "interest_rate_desc": "如果连续三次同类负债未清算→'他从来不接我的梗'定型",
        }
    )
    
    test("1.6 存储带负债的记忆", mid3.startswith("mem_"))
    test("1.7 负债计入账本", len(store.debt_ledger) == 1)
    
    # ─── 测试组2：检索 ───
    print("\n[2] 检索")
    
    results = store.search_by_person("妈妈")
    test("2.1 按人检索", len(results) == 1, f"found: {len(results)}")
    test("2.2 检索结果正确", results[0].memory_id == mid1)
    
    results = store.search_by_cue("玩笑")
    test("2.3 按线索标签检索", len(results) == 1)
    
    results = store.search_by_emotion("惆怅")
    test("2.4 按情绪检索", len(results) == 1)
    
    # ─── 测试组3：提取与沉积 ───
    print("\n[3] 提取与沉积层")
    
    character_state = {"mood": "平静", "fatigue": "有点累", "social_energy": "还行"}
    
    record = store.retrieve(mid1, character_state)
    test("3.1 提取记忆", record is not None)
    test("3.2 提取计数增加", record.extraction_count == 1)
    test("3.3 提取快照记录", len(record.extraction_snapshots) == 1)
    
    # 多次提取——沉积
    for i in range(23):
        store.retrieve(mid1, {"mood": f"第{i}次提取时的情绪", "fatigue": "还行", "social_energy": "还行"})
    
    record = store.memories[mid1]
    test("3.4 24次提取后计数", record.extraction_count == 24, str(record.extraction_count))
    test("3.5 快照数量匹配", len(record.extraction_snapshots) == 24)
    
    # 添加沉积层
    record.add_sedimentary_layer("三十五岁了才知道妈妈当年的婚姻有多难——所以'你是我的骄傲'这句话的重量翻了倍")
    record.add_sedimentary_layer("现在想起那天——不只是骄傲，还有心疼")
    test("3.6 沉积层追加", len(record.sedimentary_additions) == 2)
    
    # ─── 测试组4：认知修改 ───
    print("\n[4] 认知修改")
    
    record.add_cognitive_modification(
        mod_type=ModificationType.NARRATIVE_BUFFER,
        pre_state="记忆中：被同事质疑——被羞辱",
        post_state="记忆中：被同事质疑——说明下次要更严谨",
        trigger="关系恢复后——每次提取时认知在保护自己"
    )
    record.add_cognitive_modification(
        mod_type=ModificationType.PROTECTIVE,
        pre_state="记忆中：他不回消息的两个月——他放弃了我",
        post_state="记忆中：他不回消息的两个月——那段时间大家都挺忙的",
        trigger="关系恢复后——提取时认知选择了一个自己能接受的版本"
    )
    
    test("4.1 认知修改记录", len(record.modifications) == 2)
    test("4.2 修改类型正确", record.modifications[0]["mod_type"] == "NARRATIVE_BUFFER")
    
    # 对角色来说——她不知道记忆被改过
    test("4.3 修改在水面以下", all("modification" not in str(m) for m in record.modifications))
    
    # ─── 测试组5：痕迹锚定触发 ───
    print("\n[5] 痕迹锚定触发")
    
    triggered = store.get_by_trace_anchor(laundry_anchor)
    test("5.1 指针触发检索", len(triggered) == 1, str(len(triggered)))
    test("5.2 触发的是洗衣液记忆", triggered[0].memory_id == mid2)
    test("5.3 锚点触发计数增加", store.trace_anchors[laundry_anchor].trigger_count == 1)
    
    # ─── 测试组6：情感负债计息 ───
    print("\n[6] 情感负债计息")
    
    # 模拟时间流逝——把 last_accrued 改到 30 天前
    store.debt_ledger[0]["last_accrued"] = time.time() - 30 * 86400
    accrued = store.accrue_interest()
    test("6.1 计息触发", len(accrued) == 1)
    test("6.2 天数列正确", 29 <= accrued[0]["days_since_last_accrual"] <= 31,
         f"days: {accrued[0].get('days_since_last_accrual')}")
    
    # 清算负债
    store.mark_debt_settled(mid3)
    test("6.3 负债清算", not store.debt_ledger[0]["is_active"])
    test("6.4 清算后不再计息", len(store.get_active_debts()) == 0)
    
    # ─── 测试组7：合并检测 ───
    print("\n[7] 合并检测（服务于§36 痕迹合并）")
    
    # 存两条时间接近、同一人的类似记忆
    store.store(
        event_description="他又沉默了——我说完我的想法之后他没有回应",
        memory_class=MemoryClass.PATTERN,
        key_emotion="失落",
        intensity="medium",
        people=["他"],
        tracks=[MemoryTrack.PURE_SCENARIO],
        cue_tags=["他", "沉默", "失落"],
        scenario_version="我讲完之后他什么都没有说。短暂的空白。",
    )
    
    store.store(
        event_description="他第三次在我需要回应的时候沉默了",
        memory_class=MemoryClass.PATTERN,
        key_emotion="失落与疲惫",
        intensity="medium",
        people=["他"],
        tracks=[MemoryTrack.PURE_SCENARIO],
        cue_tags=["他", "沉默", "疲惫", "重复"],
        scenario_version="又是一样的沉默。和上次一样。",
    )
    
    candidates = store.find_merge_candidates(days_window=34)
    test("7.1 检测到相似记忆对", len(candidates) >= 1, str(len(candidates)))
    
    # ─── 测试组8：LLM 快照 ───
    print("\n[8] LLM 记忆快照")
    
    snapshot = store.memory_snapshot_for_llm(person="他")
    test("8.1 快照生成", snapshot["total_memories"] == 5, str(snapshot["total_memories"]))
    test("8.2 有相关记忆", len(snapshot["relevant_memories"]) > 0)
    test("8.3 有硬核记忆列表", len(snapshot["hardcore_memories"]) == 1)
    test("8.4 有负债信息", snapshot["active_emotional_debts"] is not None)
    test("8.5 有合并候选", snapshot["merge_candidates_count"] > 0)
    test("8.6 快照含记忆数", snapshot["total_memories"] > 0)
    test("8.7 快照含合并候选", snapshot["merge_candidates_count"] > 0)
    
    # ─── 测试组9：序列化持久化 ───
    print("\n[9] 序列化与持久化")
    
    import tempfile, os
    tmp = os.path.join(tempfile.gettempdir(), "test_memory_law34.json")
    store.save_to_file(tmp)
    test("9.1 保存到文件", os.path.exists(tmp))
    
    loaded = MemoryStorage.load_from_file(tmp)
    test("9.2 从文件加载", len(loaded.memories) == len(store.memories),
         f"loaded: {len(loaded.memories)}, original: {len(store.memories)}")
    test("9.3 负债账本恢复", len(loaded.debt_ledger) == len(store.debt_ledger))
    test("9.4 痕迹锚点恢复", len(loaded.trace_anchors) == len(store.trace_anchors))
    test("9.5 提取计数保留", loaded.memories[mid1].extraction_count == 24)
    test("9.6 认知修改保留", len(loaded.memories[mid1].modifications) == 2)
    
    os.remove(tmp)
    
    # ─── 测试组10：高频记忆检测 ───
    print("\n[10] 高频记忆与深层记忆")
    
    high = store.find_high_frequency_memories(min_extractions=10)
    test("10.1 高频记忆检测", len(high) == 1, f"found: {len(high)}")
    test("10.2 高频的是硬核记忆", high[0].memory_id == mid1)
    
    buried = store.find_rarely_touched_but_heavy()
    test("10.3 深层记忆检测", len(buried) == 1, 
         f"found: {len(buried)} (痕迹锚定记忆，等待物理指针)")
    
    # ─── 测试组11：describe_for_llm 完整性 ───
    print("\n[11] describe_for_llm 完整性")
    
    desc = store.memories[mid1].describe_for_llm()
    required_fields = ["memory_id", "memory_class", "scenario_version", "key_emotion",
                       "extraction_count", "days_since_creation", "has_emotional_debt",
                       "modification_count"]
    for field in required_fields:
        test(f"11.{required_fields.index(field)+1} describe包含{field}", field in desc)
    
    # ─── 总结 ───
    total = passed + failed
    print(f"\n{'='*60}")
    print(f"  通过: {passed}/{total}  |  失败: {failed}/{total}")
    print(f"  记忆法则引擎: 双轨+四类+沉积+负债+认知修改+痕迹合并")
    print(f"{'='*60}")
