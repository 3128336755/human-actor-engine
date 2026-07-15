# distance_ledger.py — SKILL.md §40(关系距离法则) + §41(存在信号法则) + §47(人际网络法则) 的Python副手
#
# 船长：SKILL.md 原文
# 副手：Python引擎 — 精确时间追踪、互动计数、信号模式识别、双曲线记账
#
# Python做的事：
# - 追踪每段关系的精确互动次数、距上次互动天数
# - 记录每次互动后的距离变化方向（近/远/不变）
# - 双曲线情感记账——最近互动权重远高于久远互动
# - 铃铛契约的触发条件检测
# - 存在信号的发送频率和退化模式
# - 圈层边界——内圈/外圈互动频率差异
#
# Python不做的事：
# - 判断"现在应该用什么距离信号"——那是船长的判断
# - 决定"铃铛契约在这个人身上具体是什么"——船长定义，副手响应
# - 解释"他为什么三天没发消息"——船长翻译，副手提供精确天数

import time
import json
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Tuple
from collections import defaultdict


# ============================================================
# 基础定义
# ============================================================

# 距离档位（来自 SKILL.md §42.2）
DISTANCE_LEVELS = ["远", "远-中之间", "中", "中-近之间", "近", "最近"]

# 距离信号（来自 SKILL.md §42.2）
DISTANCE_SIGNALS = {
    "远": {
        "name_use": "全名/职称",
        "tone": "正经语气",
        "punctuation": "句尾无波浪号",
        "body": "身体不朝向",
        "response_speed": "可能延迟",
    },
    "中": {
        "name_use": "昵称/名字",
        "tone": "正常语气",
        "punctuation": "偶尔波浪号",
        "body": "偶尔吐槽",
    },
    "近": {
        "name_use": "外号/只叫名字最后那个字",
        "tone": "吐槽多",
        "punctuation": "波浪号多",
        "body": "主动碰触",
    },
    "最近": {
        "name_use": "叫名字的语气不一样",
        "tone": "话变少但动作变多",
        "punctuation": "敢沉默",
        "body": "不需要填满每句话之间的空隙",
    },
}

# 圈层
CIRCLE_LEVELS = ["外圈", "外-中之间", "中圈", "内-中之间", "内圈"]


# ============================================================
# 关系账本条目
# ============================================================

@dataclass
class InteractionRecord:
    """一次互动——无论大小"""
    timestamp: float
    context: str              # "闲聊" / "重要对话" / "吵架" / "存在信号" / "见面"
    distance_after: str       # 互动结束时的距离
    distance_movement: str    # "拉近" / "推远" / "没变"
    key_moment: Optional[str] = None  # 值得记的事——"他说了那句话""沉默了很久"
    emotional_weight: float = 1.0     # 双曲线权重因子（默认=1，重要事件>1）


@dataclass 
class BellContract:
    """铃铛契约——关系中压倒一切的信号"""
    signal: str               # "句号" / "感叹号" / "一个表情" / "特定的词"
    meaning: str              # "我需要你" / "我今天不太好" / "无论发生什么"
    priority: str = "ABSOLUTE"  # 压倒所有其他规则
    active: bool = True
    last_ring: Optional[float] = None   # 上次触发时间
    ring_count: int = 0


@dataclass
class PresenceSignal:
    """一次存在信号的记录"""
    timestamp: float
    signal_type: str          # "纯信号" / "表情" / "点赞" / "沉默共处" / "句号"
    energy_level_at_time: str # 发送信号时的社交能量
    responded: bool = False   # 对方回应了吗
    response_time: Optional[float] = None


# ============================================================
# 单人关系档案
# ============================================================

@dataclass
class PersonEntry:
    """一个人的完整关系档案"""
    person_id: str            # 唯一标识
    display_name: str         # 怎么称呼
    
    # ── 距离核心 ──
    distance: str = "中"      # 当前距离
    distance_history: List[Tuple[float, str]] = field(default_factory=list)
    
    # ── 互动记录 ──
    interactions: List[InteractionRecord] = field(default_factory=list)
    first_interaction: Optional[float] = None
    last_interaction: Optional[float] = None
    total_interactions: int = 0
    
    # ── 双曲线情感记账 ──
    # 核心思想：最近的互动对关系影响远大于久远的互动
    # Python 按时间衰减计算每个互动的当前权重，LLM 用这些权重做判断
    emotional_balance: float = 0.0   # 正=亲近感积累, 负=疏远感积累
    hyperbolic_decay_half_life: float = 7.0  # 7天后权重降至一半（可调）
    
    # ── 铃铛契约 ──
    bell_contracts: List[BellContract] = field(default_factory=list)
    
    # ── 圈层 ──
    circle: str = "外圈"
    
    # ── 存在信号 ──
    presence_signals: List[PresenceSignal] = field(default_factory=list)
    last_presence_signal: Optional[float] = None
    presence_signal_streak: int = 0       # 连续存在信号天数
    silence_days: float = 0.0             # 距最后一次任何互动
    
    # ── 对方模型（角色对对方的感知）──
    perceived_mood: str = "未知"         # 角色觉得对方现在什么心情
    perceived_interest: str = "未知"     # 角色觉得对方对自己有没有兴趣
    
    # ── 元数据 ──
    tags: List[str] = field(default_factory=list)  # "同事"/"老友"/"前任"/"暗恋对象"


# ============================================================
# 距离引擎本体
# ============================================================

class DistanceLedger:
    """
    关系距离与双曲线记账引擎。
    
    船长：SKILL.md §40（关系距离）+ §41（存在信号）+ §47（人际网络）
    副手：精确的时间、计数、衰减、模式检测
    """
    
    def __init__(self):
        self.people: Dict[str, PersonEntry] = {}  # person_id -> entry
        self.current_focus: Optional[str] = None  # 当前正在和谁互动
    
    # ============================================================
    # 人物管理
    # ============================================================
    
    def ensure_person(self, 
                      person_id: str,
                      display_name: str = "",
                      initial_distance: str = "远",
                      initial_circle: str = "外圈",
                      tags: List[str] = None) -> PersonEntry:
        """确保一个人存在于关系网络中，不存在则创建"""
        if person_id not in self.people:
            entry = PersonEntry(
                person_id=person_id,
                display_name=display_name or person_id,
                distance=initial_distance,
                circle=initial_circle,
                tags=tags or [],
            )
            self.people[person_id] = entry
        return self.people[person_id]
    
    def has_person(self, person_id: str) -> bool:
        return person_id in self.people
    
    def get_person(self, person_id: str) -> Optional[PersonEntry]:
        return self.people.get(person_id)
    
    # ============================================================
    # 互动记录
    # ============================================================
    
    def record_interaction(self,
                           person_id: str,
                           context: str,
                           distance_movement: str,
                           key_moment: str = "",
                           emotional_weight: float = 1.0,
                           display_name: str = "",
                           perceived_mood: str = "",
                           perceived_interest: str = "") -> Dict[str, Any]:
        """
        记录一次互动。
        
        Python做的事：精确记录时间、更新计数器、重新计算情感余额
        LLM的事：判断这次互动的 emotional_weight 应该是多少
        """
        now = time.time()
        entry = self.ensure_person(person_id, display_name=display_name)
        
        # 计算新的距离
        old_distance = entry.distance
        new_distance = self._apply_distance_movement(old_distance, distance_movement)
        
        # 创建记录
        record = InteractionRecord(
            timestamp=now,
            context=context,
            distance_after=new_distance,
            distance_movement=distance_movement,
            key_moment=key_moment if key_moment else None,
            emotional_weight=emotional_weight,
        )
        
        entry.interactions.append(record)
        entry.total_interactions += 1
        entry.last_interaction = now
        entry.silence_days = 0.0
        
        if entry.first_interaction is None:
            entry.first_interaction = now
        
        # 更新距离
        entry.distance = new_distance
        entry.distance_history.append((now, new_distance))
        
        # 更新对方感知
        if perceived_mood:
            entry.perceived_mood = perceived_mood
        if perceived_interest:
            entry.perceived_interest = perceived_interest
        
        # 重新计算双曲线情感余额
        self._recalculate_emotional_balance(entry)
        
        # 保持最近200条互动
        if len(entry.interactions) > 200:
            entry.interactions = entry.interactions[-200:]
        
        return {
            "person": entry.display_name,
            "distance": new_distance,
            "distance_movement": distance_movement,
            "change": f"{old_distance} → {new_distance}",
            "total_interactions": entry.total_interactions,
            "interaction_balance": self._interaction_balance_summary(entry),
            "circle": entry.circle,
        }
    
    def record_presence_signal(self,
                               person_id: str,
                               signal_type: str,
                               energy_level: str,
                               display_name: str = "",
                               responded: bool = False) -> Dict[str, Any]:
        """记录一次存在信号（来自 SKILL.md §41）"""
        now = time.time()
        entry = self.ensure_person(person_id, display_name=display_name)
        
        signal = PresenceSignal(
            timestamp=now,
            signal_type=signal_type,
            energy_level_at_time=energy_level,
            responded=responded,
        )
        
        entry.presence_signals.append(signal)
        entry.last_presence_signal = now
        entry.silence_days = 0.0
        
        # 更新信号连续天数
        if entry.presence_signals and len(entry.presence_signals) > 1:
            prev = entry.presence_signals[-2]
            days_since_last = (now - prev.timestamp) / 86400
            if days_since_last <= 1.5:
                entry.presence_signal_streak += 1
            else:
                entry.presence_signal_streak = 1
        else:
            entry.presence_signal_streak = 1
        
        # 保持最近100条
        if len(entry.presence_signals) > 100:
            entry.presence_signals = entry.presence_signals[-100:]
        
        return {
            "person": entry.display_name,
            "signal_type": signal_type,
            "energy_level": energy_level,
            "streak": entry.presence_signal_streak,
            "total_signals": len(entry.presence_signals),
        }
    
    # ============================================================
    # 铃铛契约
    # ============================================================
    
    def add_bell_contract(self,
                          person_id: str,
                          signal: str,
                          meaning: str,
                          display_name: str = "") -> Dict[str, Any]:
        """添加铃铛契约"""
        entry = self.ensure_person(person_id, display_name=display_name)
        
        contract = BellContract(signal=signal, meaning=meaning)
        entry.bell_contracts.append(contract)
        
        return {
            "person": entry.display_name,
            "signal": signal,
            "meaning": meaning,
            "contract_count": len(entry.bell_contracts),
        }
    
    def check_bell_trigger(self,
                           person_id: str,
                           incoming_message: str) -> Optional[Dict[str, Any]]:
        """
        检查对方发的消息是否触发了铃铛契约。
        
        Python 检测精确匹配，LLM 负责在匹配后立即调整响应优先级。
        """
        entry = self.people.get(person_id)
        if not entry or not entry.bell_contracts:
            return None
        
        triggered = []
        for bc in entry.bell_contracts:
            if bc.active and bc.signal in incoming_message:
                bc.last_ring = time.time()
                bc.ring_count += 1
                triggered.append({
                    "signal": bc.signal,
                    "meaning": bc.meaning,
                    "ring_count": bc.ring_count,
                })
        
        return {"triggered": triggered} if triggered else None
    
    # ============================================================
    # 圈层
    # ============================================================
    
    def move_circle(self,
                    person_id: str,
                    direction: str,  # "拉近" / "推远"
                    display_name: str = "") -> Dict[str, Any]:
        """移动圈层"""
        entry = self.ensure_person(person_id, display_name=display_name)
        old_circle = entry.circle
        
        current_idx = CIRCLE_LEVELS.index(entry.circle) if entry.circle in CIRCLE_LEVELS else 2
        if direction == "拉近":
            new_idx = min(len(CIRCLE_LEVELS) - 1, current_idx + 1)
        elif direction == "推远":
            new_idx = max(0, current_idx - 1)
        else:
            new_idx = current_idx
        
        entry.circle = CIRCLE_LEVELS[new_idx]
        
        return {
            "person": entry.display_name,
            "circle": entry.circle,
            "change": f"{old_circle} → {entry.circle}",
        }
    
    # ============================================================
    # 时间流逝
    # ============================================================
    
    def tick(self) -> Dict[str, Any]:
        """
        时间流逝——所有关系的沉默天数都在增加。
        双曲线衰减也在持续进行。
        """
        now = time.time()
        updates = []
        
        for entry in self.people.values():
            if entry.last_interaction:
                entry.silence_days = (now - entry.last_interaction) / 86400
            
            # 重新计算情感余额（时间改变了双曲线权重）
            if entry.interactions:
                old_balance = entry.emotional_balance
                self._recalculate_emotional_balance(entry)
                if abs(entry.emotional_balance - old_balance) > 0.01:
                    updates.append(f"{entry.display_name}: 情感余额 {old_balance:.1f}→{entry.emotional_balance:.1f}")
        
        # 检查存在信号的退化——连续没有信号的关系
        degrades = []
        for entry in self.people.values():
            if entry.silence_days > 0 and entry.last_presence_signal:
                days_since_signal = (now - entry.last_presence_signal) / 86400
                if days_since_signal > 2 and entry.presence_signal_streak > 0:
                    degrades.append({
                        "person": entry.display_name,
                        "days_since_last_signal": round(days_since_signal, 1),
                        "streak_broken": entry.presence_signal_streak > 0,
                        "warning": "存在信号中断——对方可能在感知层面感觉到'这个人不在了'",
                    })
                    entry.presence_signal_streak = 0
        
        return {
            "balance_updates": updates,
            "signal_degrades": degrades,
        }
    
    # ============================================================
    # 双曲线情感记账
    # ============================================================
    
    def _interaction_balance_summary(self, entry) -> str:
        """最近互动的方向计数——纯事实，不带感受标签。
        Python数数，LLM感受。代替 emotional_balance float 对 LLM 的暴露。"""
        if not entry.interactions:
            return '还没有互动记录'
        recent = entry.interactions[-20:]
        pull = sum(1 for r in recent if r.distance_movement == '拉近')
        push = sum(1 for r in recent if r.distance_movement == '推远')
        neutral = sum(1 for r in recent if r.distance_movement == '没变')
        return f'最近{len(recent)}次互动：拉近{pull}次，推远{push}次，没变{neutral}次'

    def _recalculate_emotional_balance(self, entry: PersonEntry):
        """
        重新计算双曲线情感余额。内部使用，不暴露给 LLM。
        
        每条互动的权重 = 1 / (1 + days_since / half_life)
        - 今天的互动权重≈1.0, 7天前的≈0.5, 一个月前的≈0.19
        - 正向互动（拉近）贡献正余额，负向（推远）贡献负余额
        """
        now = time.time()
        total = 0.0
        
        for record in entry.interactions:
            days_ago = (now - record.timestamp) / 86400
            recency_weight = 1.0 / (1.0 + days_ago / entry.hyperbolic_decay_half_life)
            if record.distance_movement == "拉近":
                total += record.emotional_weight * recency_weight
            elif record.distance_movement == "推远":
                total -= record.emotional_weight * recency_weight
        
        entry.emotional_balance = total
    
    def _apply_distance_movement(self, current: str, movement: str) -> str:
        """根据移动方向改变距离"""
        if movement == "没变":
            return current
        
        if current not in DISTANCE_LEVELS:
            return "中" if movement == "拉近" else "远"
        
        current_idx = DISTANCE_LEVELS.index(current)
        
        if movement == "拉近":
            new_idx = min(len(DISTANCE_LEVELS) - 1, current_idx + 1)
        elif movement == "推远":
            new_idx = max(0, current_idx - 1)
        else:
            new_idx = current_idx
        
        return DISTANCE_LEVELS[new_idx]
    
    # ============================================================
    # 快照（给 LLM 船长）
    # ============================================================
    
    def snapshot_for_llm(self,
                         who_is_talking: str = "",
                         context: str = "") -> Dict[str, Any]:
        """
        给 LLM 船长的完整关系状态快照。
        不暴露任何浮点数——只给自然语言事实。
        """
        now = time.time()
        
        # ─── 关系总览 ───
        all_people = []
        for entry in self.people.values():
            days_since_last = (now - entry.last_interaction) / 86400 if entry.last_interaction else None
            
            # 最近5次互动的摘要（不含浮点数）
            recent = []
            for r in entry.interactions[-5:]:
                days_ago = (now - r.timestamp) / 86400
                when = "今天" if days_ago < 1 else ("昨天" if days_ago < 2 else f"{int(days_ago)}天前")
                recent.append({
                    "when": when,
                    "context": r.context,
                    "movement": r.distance_movement,
                    "hint": "关键时刻" if r.key_moment else "",
                })
            
            # 时间——不用浮点数，用自然语言
            if days_since_last is None:
                since = "从未互动"
            elif days_since_last < 0.5:
                since = "今天"
            elif days_since_last < 1.5:
                since = "昨天"
            elif days_since_last < 3:
                since = "两三天前"
            elif days_since_last < 7:
                since = "前几天"
            elif days_since_last < 14:
                since = "一周多前"
            else:
                since = "好一阵子了"
            
            # 沉默——只给事实（天数），LLM自己感受
            if entry.silence_days >= 1:
                silence = f"沉默了{int(entry.silence_days)}天"
            else:
                silence = "今天有互动"
            
            all_people.append({
                "person": entry.display_name or entry.person_id,
                "distance": entry.distance,
                "circle": entry.circle,
                "total_interactions": entry.total_interactions,
                "last_interaction_time": since,
                "interaction_balance": self._interaction_balance_summary(entry),
                "presence_signal_streak": f"连续{entry.presence_signal_streak}天" if entry.presence_signal_streak else "近期无信号",
                "silence": silence,
                "bell_contracts": [{"signal": bc.signal, "meaning": bc.meaning, "active": bc.active} 
                                   for bc in entry.bell_contracts],
                "perceived_mood": entry.perceived_mood,
                "perceived_interest": entry.perceived_interest,
                "tags": entry.tags,
                "recent_interactions": recent,
            })
        
        # ─── 当前焦点人物详情 ───
        focus_person = None
        if who_is_talking and who_is_talking in self.people:
            entry = self.people[who_is_talking]
            days_since_last = (now - entry.last_interaction) / 86400 if entry.last_interaction else 999
            
            # 最近互动摘要——自然语言时间
            recent_highlights = []
            for r in entry.interactions[-10:]:
                days_ago = (now - r.timestamp) / 86400
                if days_ago < 1:
                    time_label = "今天"
                elif days_ago < 2:
                    time_label = "昨天"
                elif days_ago < 7:
                    time_label = "前几天"
                else:
                    time_label = "前一阵子"
                recent_highlights.append({
                    "time": time_label,
                    "context": r.context,
                    "movement": r.distance_movement,
                    "hint": "刻骨铭心" if r.key_moment else "",
                })
            
            # 存在信号模式
            signal_pattern = self._analyze_signal_pattern(entry)
            
            # 时间感——自然语言
            if days_since_last < 0.5:
                since = "刚刚还在说话"
            elif days_since_last < 1.5:
                since = "昨天还在联系"
            elif days_since_last < 3:
                since = "两三天前还有联系"
            elif days_since_last < 7:
                since = "前几天有联系"
            elif days_since_last < 14:
                since = "一周多没联系了"
            elif days_since_last < 30:
                since = "有段时间没联系了"
            else:
                since = "很久没有联系了"
            
            focus_person = {
                "person": entry.display_name,
                "distance": entry.distance,
                "distance_signals": DISTANCE_SIGNALS.get(entry.distance, {}),
                "circle": entry.circle,
                "total_interactions": entry.total_interactions,
                "last_contact": since,
                "interaction_balance": self._interaction_balance_summary(entry),
                "recent_highlights": recent_highlights,
                "bell_contracts": [{"signal": bc.signal, "meaning": bc.meaning, "active": bc.active, "ring_count": bc.ring_count}
                                   for bc in entry.bell_contracts],
                "presence_signals": {
                    "total": len(entry.presence_signals),
                    "streak": f"连续{entry.presence_signal_streak}天" if entry.presence_signal_streak else "近期无信号",
                    "pattern": signal_pattern,
                    "degradation_warning": f"存在信号中断——距上次信号{days_since_last}天" if days_since_last > 2 and entry.presence_signal_streak == 0 else None,
                },
                "silence_risk": f"上次互动距今{int(days_since_last)}天，最近{'有持续信号' if entry.presence_signal_streak else '信号中断'}",
                "perceived_mood": entry.perceived_mood,
                "perceived_interest": entry.perceived_interest,
                "tags": entry.tags,
            }
        
        # ─── 人际网络分析 ───
        network_analysis = self._analyze_network()
        
        # ─── 船长指令 ───
        return {
            "all_people": all_people,
            "total_relationships": len(self.people),
            "focus_person": focus_person,
            "network_analysis": network_analysis,
            "current_focus": self.people[who_is_talking].display_name if who_is_talking and who_is_talking in self.people else None,
        }
    
    def _analyze_signal_pattern(self, entry: PersonEntry) -> Dict[str, Any]:
        """分析存在信号模式"""
        if not entry.presence_signals:
            return {"pattern": "无记录", "note": "还没发过存在信号"}
        
        signals = entry.presence_signals
        total = len(signals)
        
        # 信号类型分布
        type_counts = defaultdict(int)
        for s in signals:
            type_counts[s.signal_type] += 1
        
        # 能量分布——发信号时的社交能量
        energy_counts = defaultdict(int)
        for s in signals:
            energy_counts[s.energy_level_at_time] += 1
        
        # 退化模式检测
        degradation = None
        if len(signals) >= 3:
            last_three_types = [s.signal_type for s in signals[-3:]]
            # 检测退化：从内容→表情→纯信号→消失
            if set(last_three_types) in [{"纯信号", "句号"}, {"纯信号"}]:
                degradation = "存在信号正在退化——可能进入'发不出信号→对方以为消失'的危险循环"
        
        return {
            "total": total,
            "type_distribution": dict(type_counts),
            "energy_distribution": dict(energy_counts),
            "degradation": degradation,
            "streak": entry.presence_signal_streak,
        }
    
    def _analyze_network(self) -> Dict[str, Any]:
        """人际网络分析"""
        if not self.people:
            return {"empty": True, "note": "还没有任何人际关系"}
        
        # 按圈层分组
        by_circle = defaultdict(list)
        by_distance = defaultdict(list)
        
        for entry in self.people.values():
            by_circle[entry.circle].append(entry.display_name)
            by_distance[entry.distance].append(entry.display_name)
        
        # 可能的关系碰撞检测
        collisions = []
        if len(self.people) >= 2:
            names = list(self.people.values())
            for i in range(len(names)):
                for j in range(i+1, len(names)):
                    a, b = names[i], names[j]
                    # 同一圈层但距离不同→可能出现角色切换摩擦
                    if a.circle == b.circle and a.distance != b.distance:
                        collisions.append({
                            "type": "角色切换摩擦",
                            "between": [a.display_name, b.display_name],
                            "detail": f"对{a.display_name}距离是'{a.distance}'但对{b.display_name}是'{b.distance}'——同圈不同距，同时在场时可能尴尬",
                        })
        
        return {
            "by_circle": {k: v for k, v in by_circle.items()},
            "by_distance": {k: v for k, v in by_distance.items()},
            "potential_collisions": collisions[:5],
            "circle_overview": {
                "内圈人数": len(by_circle.get("内圈", []) + by_circle.get("内-中之间", [])),
                "外圈人数": len(by_circle.get("外圈", []) + by_circle.get("外-中之间", [])),
                "中间人数": len(by_circle.get("中圈", [])),
            },
        }
    
    # ============================================================
    # 序列化
    # ============================================================
    
    def to_dict(self) -> Dict:
        people_data = {}
        for pid, entry in self.people.items():
            people_data[pid] = {
                "person_id": entry.person_id,
                "display_name": entry.display_name,
                "distance": entry.distance,
                "distance_history": [(ts, d) for ts, d in entry.distance_history],
                "circle": entry.circle,
                "first_interaction": entry.first_interaction,
                "last_interaction": entry.last_interaction,
                "total_interactions": entry.total_interactions,
                "emotional_balance": entry.emotional_balance,
                "interactions": [
                    {
                        "ts": r.timestamp,
                        "context": r.context,
                        "distance_after": r.distance_after,
                        "movement": r.distance_movement,
                        "key": r.key_moment,
                        "weight": r.emotional_weight,
                    } for r in entry.interactions
                ],
                "bell_contracts": [
                    {
                        "signal": bc.signal,
                        "meaning": bc.meaning,
                        "active": bc.active,
                        "last_ring": bc.last_ring,
                        "ring_count": bc.ring_count,
                    } for bc in entry.bell_contracts
                ],
                "presence_signals": [
                    {
                        "ts": s.timestamp,
                        "type": s.signal_type,
                        "energy": s.energy_level_at_time,
                        "responded": s.responded,
                    } for s in entry.presence_signals
                ],
                "last_presence_signal": entry.last_presence_signal,
                "presence_signal_streak": entry.presence_signal_streak,
                "silence_days": entry.silence_days,
                "perceived_mood": entry.perceived_mood,
                "perceived_interest": entry.perceived_interest,
                "tags": entry.tags,
            }
        
        return {
            "people": people_data,
            "current_focus": self.current_focus,
        }
    
    def save_to_file(self, path: str):
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)
    
    @classmethod
    def load_from_file(cls, path: str) -> 'DistanceLedger':
        ledger = cls()
        try:
            with open(path, 'r', encoding='utf-8') as f:
                d = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return ledger
        
        ledger.current_focus = d.get("current_focus")
        
        for pid, pd in d.get("people", {}).items():
            entry = PersonEntry(
                person_id=pd["person_id"],
                display_name=pd["display_name"],
                distance=pd["distance"],
                circle=pd["circle"],
                first_interaction=pd.get("first_interaction"),
                last_interaction=pd.get("last_interaction"),
                total_interactions=pd.get("total_interactions", 0),
                emotional_balance=pd.get("emotional_balance", 0.0),
                last_presence_signal=pd.get("last_presence_signal"),
                presence_signal_streak=pd.get("presence_signal_streak", 0),
                silence_days=pd.get("silence_days", 0.0),
                perceived_mood=pd.get("perceived_mood", "未知"),
                perceived_interest=pd.get("perceived_interest", "未知"),
                tags=pd.get("tags", []),
            )
            
            # 恢复距离历史
            entry.distance_history = [(ts, d) for ts, d in pd.get("distance_history", [])]
            
            # 恢复互动记录
            for r in pd.get("interactions", []):
                entry.interactions.append(InteractionRecord(
                    timestamp=r["ts"],
                    context=r["context"],
                    distance_after=r["distance_after"],
                    distance_movement=r["movement"],
                    key_moment=r.get("key"),
                    emotional_weight=r.get("weight", 1.0),
                ))
            
            # 恢复铃铛契约
            for bc in pd.get("bell_contracts", []):
                entry.bell_contracts.append(BellContract(
                    signal=bc["signal"],
                    meaning=bc["meaning"],
                    active=bc.get("active", True),
                    last_ring=bc.get("last_ring"),
                    ring_count=bc.get("ring_count", 0),
                ))
            
            # 恢复存在信号
            for s in pd.get("presence_signals", []):
                entry.presence_signals.append(PresenceSignal(
                    timestamp=s["ts"],
                    signal_type=s["type"],
                    energy_level_at_time=s["energy"],
                    responded=s.get("responded", False),
                ))
            
            ledger.people[pid] = entry
        
        return ledger


# ============================================================
# 自测
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
    print("distance_ledger.py 自测 — SKILL.md §40+§41+§47")
    print("=" * 60)
    
    # ─── 1. 初始化 ───
    print("\n[1] 初始化")
    ledger = DistanceLedger()
    test("1.1 引擎创建", ledger is not None)
    test("1.2 初始无人", len(ledger.people) == 0)
    
    # ─── 2. 添加人 ───
    print("\n[2] 人物管理")
    
    ledger.ensure_person("a", "阿明", initial_distance="中", tags=["同事"])
    ledger.ensure_person("b", "小杰", initial_distance="近", tags=["老友"])
    ledger.ensure_person("c", "陌生人", initial_distance="远", tags=["新认识"])
    test("2.1 添加成功", len(ledger.people) == 3)
    test("2.2 重复确保不重复创建", len(ledger.people) == 3)
    test("2.3 has_person", ledger.has_person("a"))
    test("2.4 初始距离", ledger.people["a"].distance == "中")
    test("2.5 初始圆圈", ledger.people["b"].circle == "外圈")
    
    # ─── 3. 互动记录与距离变化 ───
    print("\n[3] 互动记录（Law 40）")
    
    r1 = ledger.record_interaction("a", "闲聊", "拉近", key_moment="他笑了")
    test("3.1 拉近后距离改变", r1["distance"] != "中", f"distance={r1['distance']}")
    test("3.2 互动计数", ledger.people["a"].total_interactions == 1)
    test("3.3 记录key_moment", ledger.people["a"].interactions[0].key_moment == "他笑了")
    
    # 继续拉近几次
    for i in range(5):
        ledger.record_interaction("a", "重要对话", "拉近", emotional_weight=1.5)
    test("3.4 多次拉近→距离持续推进", ledger.people["a"].distance == "最近", 
         f"distance={ledger.people['a'].distance}")
    
    # 推远
    ledger.record_interaction("a", "吵架", "推远", emotional_weight=2.0)
    test("3.5 推远后距离减小", ledger.people["a"].distance != "最近", 
         f"distance={ledger.people['a'].distance}")
    
    # ─── 4. 双曲线情感记账 ───
    print("\n[4] 双曲线情感记账")
    
    # 正向互动多→余额为正
    test("4.1 正向余额", ledger.people["a"].emotional_balance > 0,
         f"balance={ledger.people['a'].emotional_balance:.2f}")
    
    # 制造负向关系
    ledger.record_interaction("c", "被迫社交", "推远", emotional_weight=0.5)
    ledger.record_interaction("c", "被冷漠对待", "推远", emotional_weight=2.0)
    test("4.2 负向余额", ledger.people["c"].emotional_balance < 0,
         f"balance={ledger.people['c'].emotional_balance:.2f}")
    
    # ─── 5. 铃铛契约 ───
    print("\n[5] 铃铛契约（Law 40.3）")
    
    ledger.add_bell_contract("b", "。", "无论发生什么，秒回", display_name="小杰")
    test("5.1 铃铛添加", len(ledger.people["b"].bell_contracts) == 1)
    
    # 检测触发
    trigger = ledger.check_bell_trigger("b", "我今天不太好。")
    test("5.2 铃铛触发检测", trigger is not None and len(trigger["triggered"]) > 0)
    test("5.3 铃铛计数", ledger.people["b"].bell_contracts[0].ring_count == 1)
    
    # 不触发
    no_trigger = ledger.check_bell_trigger("b", "你好")
    test("5.4 不触发", no_trigger is None)
    
    # 添加第二个契约
    ledger.add_bell_contract("b", "出事了", "紧急——立刻回应")
    trigger2 = ledger.check_bell_trigger("b", "我出事了")
    test("5.5 多契约", len(trigger2["triggered"]) == 1)
    
    # ─── 6. 存在信号 ───
    print("\n[6] 存在信号（Law 41）")
    
    ledger.record_presence_signal("b", "表情", "有点低", display_name="小杰")
    test("6.1 信号记录", len(ledger.people["b"].presence_signals) == 1)
    test("6.2 信号连续天数", ledger.people["b"].presence_signal_streak == 1)
    
    # 连续信号
    for i in range(5):
        # 手动调整时间戳让它们在同一天
        s = PresenceSignal(
            timestamp=time.time() - (5-i)*3600,
            signal_type="表情",
            energy_level_at_time="有点低",
        )
        ledger.people["b"].presence_signals.append(s)
    ledger.people["b"].presence_signal_streak = 5
    test("6.3 连续信号", ledger.people["b"].presence_signal_streak == 5)
    
    # 退化检测——让这个人也"消失"了
    ledger.people["b"].last_interaction = time.time() - 4*86400
    ledger.people["b"].last_presence_signal = time.time() - 4*86400  # 4天前
    tick_result = ledger.tick()
    test("6.4 信号退化警告", any("小杰" in str(d) for d in tick_result.get("signal_degrades", [])),
         f"degrades={tick_result['signal_degrades']}")
    
    # ─── 7. 圈层 ───
    print("\n[7] 圈层（Law 47）")
    
    r_circle1 = ledger.move_circle("a", "拉近")
    test("7.1 拉近圈层", ledger.people["a"].circle != "外圈")
    
    r_circle2 = ledger.move_circle("a", "推远")
    test("7.2 推远圈层", ledger.people["a"].circle == "外圈")
    
    # ─── 8. 网络分析 ───
    print("\n[8] 人际网络分析")
    
    ledger.move_circle("b", "拉近")
    ledger.move_circle("b", "拉近")
    ledger.move_circle("b", "拉近")
    ledger.move_circle("b", "拉近")  # 内圈
    
    snap = ledger.snapshot_for_llm()
    test("8.1 全人列表", len(snap["all_people"]) == 3)
    test("8.2 网络分析存在", "network_analysis" in snap)
    test("8.3 圈层概览", "by_circle" in snap["network_analysis"])
    
    # ─── 9. 聚焦人物 ───
    print("\n[9] 聚焦人物快照")
    
    # 先给B足够的互动
    ledger.record_interaction("b", "重要对话", "拉近")
    ledger.record_interaction("b", "见面", "拉近")
    
    focus = ledger.snapshot_for_llm(who_is_talking="b")
    test("9.1 接收人详情", focus["focus_person"] is not None)
    test("9.2 距离信号包含", "distance_signals" in focus["focus_person"])
    test("9.3 最近互动", len(focus["focus_person"]["recent_highlights"]) > 0)
    test("9.4 铃铛契约存在", len(focus["focus_person"]["bell_contracts"]) > 0)
    test("9.5 存在信号存在", focus["focus_person"]["presence_signals"]["total"] > 0)
    test("9.6 快照含人物列表", "all_people" in focus)
    
    # ─── 10. 时间流逝 ───
    print("\n[10] 时间流逝影响")
    
    # 把a的所有互动时间戳推到10天前
    for r in ledger.people["a"].interactions:
        r.timestamp -= 10*86400
    ledger.people["a"].last_interaction = time.time() - 10*86400
    ledger.tick()
    test("10.1 沉默天数更新", ledger.people["a"].silence_days >= 9.9)
    
    # 双曲线衰减——10天后的互动权重极小
    ledger._recalculate_emotional_balance(ledger.people["a"])
    balance_after_decay = ledger.people["a"].emotional_balance
    test("10.2 久远互动权重衰减", abs(balance_after_decay) < 4.0, 
         f"balance after 10 days decay={balance_after_decay:.2f}")
    
    # ─── 11. 序列化 ───
    print("\n[11] 序列化持久化")
    
    import tempfile, os
    tmp = os.path.join(tempfile.gettempdir(), "test_distance_ledger.json")
    ledger.save_to_file(tmp)
    test("11.1 保存", os.path.exists(tmp))
    
    loaded = DistanceLedger.load_from_file(tmp)
    test("11.2 加载后人数一致", len(loaded.people) == len(ledger.people))
    test("11.3 加载后距离一致", 
         loaded.people["a"].distance == ledger.people["a"].distance)
    test("11.4 加载后铃铛契约一致", 
         len(loaded.people["b"].bell_contracts) == len(ledger.people["b"].bell_contracts))
    test("11.5 加载后存在信号一致",
         len(loaded.people["b"].presence_signals) == len(ledger.people["b"].presence_signals))
    
    os.remove(tmp)
    
    # ─── 12. 边界条件 ───
    print("\n[12] 边界条件")
    
    # 不存在的铃铛触发
    test("12.1 陌生人铃铛不触发", ledger.check_bell_trigger("zzz", "。") is None)
    # 不存在的聚焦
    test("12.2 陌生人聚焦", ledger.snapshot_for_llm(who_is_talking="zzz")["focus_person"] is None)
    # 网络为空时
    empty = DistanceLedger()
    test("12.3 空网络快照不崩溃", empty.snapshot_for_llm() is not None)
    
    # ─── 总结 ───
    total = passed + failed
    print(f"\n{'='*60}")
    print(f"  通过: {passed}/{total}  |  失败: {failed}/{total}")
    print(f"  关系距离引擎: §40距离+§41存在信号+§47人际网络")
    print(f"{'='*60}")
