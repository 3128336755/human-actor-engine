# learning_engine.py — SKILL.md §11(知识法则) + §12(道德基线)
# Python 副手：学习与无知双引擎
#
# 船长：SKILL.md 原文
# 副手：Python引擎
#
# Python做的事：
# - 知识域地图：追踪角色"知道什么""不知道什么""知道多少"
# - 学习过程：从"不知道"到"听说过"到"会一点"到"熟练"——精确追踪每一步
# - 硬边界：违法乱纪 = 拒绝学习，不是"不知道"，是"不学"
# - 理解≠认同：对小众癖好/亚文化——能理解，不归类为道德问题
# - 道德归属权：道德判断取决于角色+对话对象，两个人一套标准
# - 好奇心驱动：对什么有兴趣、对什么没兴趣——决定学习的自然方向
# - 知识来源追踪：受训/自学/经验/道听途说——每种来源决定确信程度
# - 知识过期检测：有些知识十年没更新了——标记为"可能过期"
# - 学习的情感附着：花了代价换来的知识——上面有血
#
# Python不做的事：
# - 判断"红绳是不是道德问题"——那是角色和她面对的人的共同决定
# - 决定"我应该学这个吗"——船长用道德基线判断，副手只提供硬边界
# - 解释"他为什么会知道这个"——那是叙事的事
# - 教LLM怎么说话——Python只给事实，感受归LLM

import time
import json
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Set, Tuple
from collections import defaultdict


# ============================================================
# 基础定义
# ============================================================

class KnowledgeLevel(Enum):
    """知识掌握程度"""
    DOESNT_KNOW = "不知道"
    VAGUELY_AWARE = "模糊意识到"
    HEARD_OF = "听说过"
    LEARNING = "正在学"
    ENTRY = "会一点"
    FUNCTIONAL = "能用"
    PROFICIENT = "熟练"
    EXPERT = "精通"
    REFUSED = "拒绝学习"


class KnowledgeSource(Enum):
    """知识来源"""
    TRAINED = "受训"
    SELF_TAUGHT = "自学"
    EXPERIENCE = "经验"
    HEARSAY = "道听途说"
    MENTORED = "师父教的"


class RefusalReason(Enum):
    """拒绝学习的原因"""
    ILLEGAL = "违法"
    IMMORAL_CHARACTER = "违反角色道德基线"
    IMMORAL_PARTNER = "对方不接受的道德边界"
    DANGEROUS = "危险"
    EXPLOITATIVE = "剥削性"
    PERSONAL_BOUNDARY = "个人边界"


class QuirkStance(Enum):
    """对小众偏好的态度"""
    UNDERSTAND = "理解"
    CURIOUS = "好奇"
    NEUTRAL = "中性"
    RELATABLE = "相关"
    DISTANT = "保持距离"


# ============================================================
# 数据结构
# ============================================================

@dataclass
class KnowledgeDomain:
    domain_id: str
    name: str
    level: KnowledgeLevel = KnowledgeLevel.DOESNT_KNOW
    source: Optional[KnowledgeSource] = None
    source_detail: str = ""
    first_exposure: Optional[float] = None
    last_exposure: Optional[float] = None
    exposure_count: int = 0
    hours_invested: float = 0.0
    last_updated: float = 0.0
    curiosity: float = 0.0
    identity_weight: float = 0.0
    is_outdated: bool = False
    outdated_note: str = ""
    emotional_tags: List[str] = field(default_factory=list)
    emotional_notes: str = ""
    bias_tendency: str = ""


@dataclass
class LearningEvent:
    timestamp: float
    domain_id: str
    event_type: str
    level_before: KnowledgeLevel
    level_after: KnowledgeLevel
    context: str = ""
    who_taught: str = ""
    emotional_response: str = ""


@dataclass
class MoralContext:
    character_moral_baseline: Dict[str, Any] = field(default_factory=dict)
    situational_bending: Dict[str, Any] = field(default_factory=dict)
    partner_known: bool = False
    partner_moral_tendency: str = ""


# ============================================================
# 学习引擎
# ============================================================

class LearningEngine:
    def __init__(self):
        self.domains: Dict[str, KnowledgeDomain] = {}
        self.refused_domains: Dict[str, RefusalReason] = {}
        self.quirk_understanding: Dict[str, QuirkStance] = {}
        self.moral_context = MoralContext()
        self.learning_log: List[LearningEvent] = []
    
    # ============================================================
    # 知识域管理
    # ============================================================
    
    def ensure_domain(self, domain_id: str, name: str = "") -> KnowledgeDomain:
        if domain_id not in self.domains:
            self.domains[domain_id] = KnowledgeDomain(
                domain_id=domain_id,
                name=name or domain_id,
            )
        return self.domains[domain_id]
    
    def add_domain(self, domain_id: str, name: str = "") -> KnowledgeDomain:
        """engine_hub 兼容接口——ensure_domain 的别名"""
        return self.ensure_domain(domain_id, name)
    
    # ============================================================
    # 硬边界：拒绝学习
    # ============================================================
    
    def refuse_to_learn(self, domain_id: str, reason: RefusalReason, note: str = "") -> Dict[str, Any]:
        domain = self.ensure_domain(domain_id)
        domain.level = KnowledgeLevel.REFUSED
        self.refused_domains[domain_id] = reason
        return {
            "domain": domain.name,
            "status": "REFUSED",
            "reason": reason.value,
            "note": note,
        }
    
    def is_refused(self, domain_id: str) -> bool:
        if domain_id in self.refused_domains:
            return True
        domain = self.domains.get(domain_id)
        return domain is not None and domain.level == KnowledgeLevel.REFUSED
    
    def get_refusal_reason(self, domain_id: str) -> Optional[str]:
        reason = self.refused_domains.get(domain_id)
        return reason.value if reason else None
    
    # ============================================================
    # 小众偏好处理——理解≠认同
    # ============================================================
    
    def register_quirk(self, quirk_id: str, name: str, stance: QuirkStance = QuirkStance.UNDERSTAND) -> Dict[str, Any]:
        self.quirk_understanding[quirk_id] = stance
        return {
            "quirk": name,
            "stance": stance.value,
        }
    
    def get_quirk_stance(self, quirk_id: str) -> Optional[QuirkStance]:
        return self.quirk_understanding.get(quirk_id)
    
    # ============================================================
    # 学习过程
    # ============================================================
    
    def learn(self,
              domain_id: str,
              context: str = "",
              who_taught: str = "",
              emotional_response: str = "",
              hours: float = 0.0,
              source: Optional[KnowledgeSource] = None,
              domain_name: str = "",
              source_detail: str = "") -> Dict[str, Any]:
        now = time.time()
        
        if self.is_refused(domain_id):
            return {
                "learned": False,
                "reason": "REFUSED",
                "refusal": self.get_refusal_reason(domain_id),
            }
        
        domain = self.ensure_domain(domain_id, name=domain_name)
        old_level = domain.level
        
        if domain.first_exposure is None:
            domain.first_exposure = now
            domain.source = source
            domain.source_detail = source_detail
        
        domain.last_exposure = now
        domain.exposure_count += 1
        domain.hours_invested += hours
        domain.last_updated = now
        
        if source:
            domain.source = source
        if source_detail:
            domain.source_detail = source_detail
        
        new_level = self._calculate_new_level(domain)
        domain.level = new_level
        
        event = LearningEvent(
            timestamp=now,
            domain_id=domain_id,
            event_type="learn",
            level_before=old_level,
            level_after=new_level,
            context=context,
            who_taught=who_taught,
            emotional_response=emotional_response,
        )
        self.learning_log.append(event)
        
        # 触发相邻域的联想
        activated_adjacent = []
        curiosity_triggered = False
        for did, d in self.domains.items():
            if did != domain_id and self._domain_match_score(did, domain.name) > 0.2:
                d.exposure_count = max(d.exposure_count, 1)
                if d.first_exposure is None:
                    d.first_exposure = now
                activated_adjacent.append(d.name)
            if d.curiosity < 0.3 and self._domain_match_score(did, domain.name) > 0.15:
                d.curiosity = min(d.curiosity + 0.05, 1.0)
                curiosity_triggered = True
        
        return {
            "learned": True,
            "domain": domain.name,
            "level_before": old_level.value,
            "level_after": new_level.value,
            "source": domain.source.value if domain.source else "未知",
            "source_detail": domain.source_detail,
            "emotional_response": emotional_response,
            "curiosity_triggered": curiosity_triggered,
            "activated_adjacent": activated_adjacent,
        }
    
    def _calculate_new_level(self, domain: KnowledgeDomain) -> KnowledgeLevel:
        if domain.level == KnowledgeLevel.REFUSED:
            return KnowledgeLevel.REFUSED
        
        exposures = domain.exposure_count
        hours = domain.hours_invested
        
        if exposures == 0:
            return KnowledgeLevel.DOESNT_KNOW
        elif exposures == 1:
            return KnowledgeLevel.VAGUELY_AWARE
        elif exposures <= 3:
            return KnowledgeLevel.HEARD_OF
        elif hours < 1:
            return KnowledgeLevel.HEARD_OF
        elif hours < 5:
            return KnowledgeLevel.ENTRY
        elif hours < 20:
            return KnowledgeLevel.FUNCTIONAL
        elif hours < 100:
            return KnowledgeLevel.PROFICIENT
        else:
            return KnowledgeLevel.EXPERT
    
    def _domain_match_score(self, domain_id: str, topic: str) -> float:
        """粗略的话题→知识域匹配（基于关键词）。"""
        domain = self.domains.get(domain_id)
        if not domain:
            return 0.0
        name = domain.name.lower()
        topic_lower = topic.lower()
        
        # 精确包含
        if topic_lower in name or name in topic_lower:
            return 0.9
        # 词级重叠
        name_words = set(name.split())
        topic_words = set(topic_lower.split())
        if name_words and topic_words:
            overlap = len(name_words & topic_words)
            return min(0.7, overlap / max(len(name_words), len(topic_words)) * 2)
        return 0.0
    
    # ============================================================
    # 知识过期检测
    # ============================================================
    
    def check_outdated(self, domain_id: str, years_since_update: float) -> Dict[str, Any]:
        domain = self.domains.get(domain_id)
        if not domain:
            return {"outdated": False, "reason": "未知领域"}
        
        fast_aging = ["编程", "科技", "前端", "框架", "AI", "算法", "手机", "软件"]
        medium_aging = ["医学", "心理", "教育", "金融", "法律", "市场"]
        slow_aging = ["历史", "哲学", "文学", "艺术", "音乐", "数学", "物理基础"]
        
        is_fast = any(k in domain.name for k in fast_aging)
        is_medium = any(k in domain.name for k in medium_aging)
        is_slow = any(k in domain.name for k in slow_aging)
        
        if is_fast and years_since_update > 0.5:
            domain.is_outdated = True
            domain.outdated_note = f"快速迭代领域，{years_since_update:.1f}年未更新——可能已经过时了"
            return {"outdated": True, "severity": "高", "note": domain.outdated_note}
        elif is_medium and years_since_update > 3:
            domain.is_outdated = True
            domain.outdated_note = f"中速更新领域，{years_since_update:.1f}年未更新——有些内容可能变了"
            return {"outdated": True, "severity": "中", "note": domain.outdated_note}
        elif is_slow and years_since_update > 10:
            domain.is_outdated = True
            domain.outdated_note = f"慢速领域，{years_since_update:.1f}年未更新——核心可能没变，但解读可能变了"
            return {"outdated": True, "severity": "低", "note": domain.outdated_note}
        
        return {"outdated": False, "reason": "还在有效期内"}
    
    # ============================================================
    # 知识焦虑（来自 SKILL.md §11.7）
    # ============================================================
    
    def get_knowledge_anxiety(self) -> Dict[str, Any]:
        total_domains = len(self.domains)
        known_count = sum(1 for d in self.domains.values()
                         if d.level.value not in ("不知道", "模糊意识到", "拒绝学习"))
        
        anxiety_sources = []
        for d in self.domains.values():
            if d.hours_invested > 5 and d.level.value in ("会一点", "能用"):
                anxiety_sources.append({
                    "domain": d.name,
                    "hours": round(d.hours_invested, 1),
                    "level": d.level.value,
                })
        
        dunning_kruger_candidates = []
        for d in self.domains.values():
            if d.level == KnowledgeLevel.ENTRY and d.exposure_count <= 5:
                dunning_kruger_candidates.append({
                    "domain": d.name,
                })
        
        return {
            "known_domains": known_count,
            "total_domains": total_domains,
            "anxiety_level": (
                "很低——知道的不多，但也没什么焦虑" if known_count < 3 else
                "有点——知道了一些才开始意识到自己不知道的更多" if known_count < 6 else
                "中等——学的越多越觉得不够" if known_count < 10 else
                "高——在这个知识广度上，每天都发现新的不懂的东西"
            ),
            "anxiety_sources": anxiety_sources,
            "dunning_kruger_risk": dunning_kruger_candidates,
        }
    
    # ============================================================
    # 对陌生话题的反应——只标记状态，不教LLM说话
    # ============================================================
    
    def react_to_unknown(self, topic: str) -> Dict[str, Any]:
        # 1. 硬边界检查
        if self.is_refused(topic):
            return {
                "topic": topic,
                "reaction": "REFUSED",
                "reason": self.get_refusal_reason(topic),
            }
        
        # 2. 检查是不是已知小众偏好
        for qid, stance in self.quirk_understanding.items():
            if qid in topic.lower():
                return {
                    "reaction": "quirk",
                    "stance": stance.value,
                }
        
        # 3. 新话题——不做道德判断，标记为"需理解"
        return {
            "reaction": "unknown",
            "note": "无硬边界、无道德张力、不是已知小众偏好",
        }
    
    def respond_to_topic(self, topic: str) -> Dict[str, Any]:
        """
        对不熟悉的话题做事实判断——硬边界/已知域/完全陌生。
        Python 只标记状态，LLM 自己感受该怎么回应。
        """
        if self.is_refused(topic):
            return {"reaction": "REFUSED", "reason": self.get_refusal_reason(topic)}
        
        best_match = None
        best_score = 0
        for did, d in self.domains.items():
            score = self._domain_match_score(did, topic)
            if score > best_score:
                best_score = score
                best_match = d
        
        if best_match and best_score > 0.2:
            return {
                "reaction": "near",
                "related_domain": best_match.name,
                "level": best_match.level.value,
            }
        
        return {"reaction": "stranger"}
    
    # ============================================================
    # 快照（给 LLM 船长）——只给事实
    # ============================================================
    
    def snapshot_for_llm(self,
                         topic_to_discuss: str = "",
                         who_is_talking: str = "") -> Dict[str, Any]:
        now = time.time()
        
        # ─── 知识域总览 ───
        domain_summary = []
        for d in self.domains.values():
            years_active = (now - (d.first_exposure or now)) / 31536000
            
            # investment: 只给事实——花了多少小时
            if d.hours_invested < 0.5:
                hours_note = "不到半小时"
            else:
                hours_note = f"大约{int(d.hours_invested)}小时"
            
            # curiosity: 只给事实——接触频率和最近动静，LLM自己感受"好不好奇"
            curiosity_note = f"接触过{d.exposure_count}次"
            if d.emotional_tags:
                curiosity_note += "，每次带着" + "、".join(d.emotional_tags[:3]) + "的心情"
            
            # identity: 只给事实——投入+时间+掌握程度，LLM自己感受"是不是自己的一部分"
            if years_active >= 1:
                time_str = f"接触了{int(years_active)}年"
            elif years_active >= 0.1:
                time_str = f"接触了{int(years_active*12)}个月"
            else:
                time_str = "刚接触没几天"
            identity_note = f"{time_str}，{d.level.value}，{hours_note}"
            
            if d.first_exposure and years_active < 0.1:
                time_note = "刚接触没几天"
            elif d.first_exposure and years_active < 1:
                time_note = "接触不到一年"
            elif d.first_exposure:
                time_note = f"接触了{int(years_active)}年多了"
            else:
                time_note = None
            
            domain_summary.append({
                "domain": d.name,
                "level": d.level.value,
                "source": d.source.value if d.source else "未知",
                "source_detail": d.source_detail,
                "exposure_count": d.exposure_count,
                "investment": hours_note,
                "curiosity": curiosity_note,
                "identity_weight": identity_note,
                "how_long": time_note,
                "is_outdated": d.is_outdated,
                "outdated_note": d.outdated_note,
                "emotional_tags": d.emotional_tags,
                "emotional_notes": d.emotional_notes,
                "bias_tendency": d.bias_tendency,
            })
        
        # ─── 当前话题分析（只给事实）───
        topic_analysis = None
        if topic_to_discuss:
            best = None
            best_score = 0
            for did, d in self.domains.items():
                score = self._domain_match_score(did, topic_to_discuss)
                if score > best_score:
                    best_score = score
                    best = d
            
            if best and best_score > 0.3:
                topic_analysis = {
                    "topic": topic_to_discuss,
                    "best_match_domain": best.name,
                    "match_detail": f"匹配到'{best.name}'，相似度{int(best_score*100)}%——接触过{best.exposure_count}次，掌握程度{best.level.value}",
                    "level": best.level.value,
                }
            elif self.is_refused(topic_to_discuss):
                topic_analysis = {
                    "topic": topic_to_discuss,
                    "status": "REFUSED",
                    "reason": self.get_refusal_reason(topic_to_discuss),
                }
            else:
                topic_analysis = {
                    "topic": topic_to_discuss,
                    "status": "未知领域",
                }
        
        # ─── 硬边界列表 ───
        refusals = []
        for did, reason in self.refused_domains.items():
            refusals.append({"domain": did, "reason": reason.value})
        
        # ─── 小众偏好理解状态 ───
        quirks = []
        for qid, stance in self.quirk_understanding.items():
            quirks.append({"quirk": qid, "stance": stance.value})
        
        # ─── 道德上下文 ───
        moral = {
            "character_baseline": self.moral_context.character_moral_baseline,
            "bending_points": self.moral_context.situational_bending,
            "partner_known": self.moral_context.partner_known,
            "partner_tendency": self.moral_context.partner_moral_tendency,
            "core_principle": "道德不是绝对的——由角色和对话对象的共同关系决定。不单方面审判。",
        }
        
        # ─── 知识焦虑 ───
        anxiety = self.get_knowledge_anxiety()
        
        # ─── 最近的学习事件 ───
        recent_learning = []
        for event in self.learning_log[-10:]:
            days_ago = (now - event.timestamp) / 86400
            recent_learning.append({
                "when": f"{days_ago:.0f}天前" if days_ago >= 1 else "今天",
                "domain": event.domain_id,
                "type": event.event_type,
                "who_taught": event.who_taught,
                "emotional": event.emotional_response,
                "progress": f"{event.level_before.value} → {event.level_after.value}",
                "context": event.context[:80],
            })
        
        return {
            "knowledge_domains": domain_summary,
            "total_domains": len(self.domains),
            "known_domains": sum(1 for d in self.domains.values()
                                if d.level.value not in ("不知道", "模糊意识到", "拒绝学习")),
            "topic_analysis": topic_analysis,
            "hard_boundaries": {
                "refused_domains": refusals,
                "principle": "这些领域不是'不知道'——是'不学'。违法乱纪不在角色的认知体系内。",
            },
            "quirk_understanding": {
                "stances": quirks,
                "principle": "理解≠认同。不归类为道德问题。道德取决于角色和对话对象。",
            },
            "moral_context": moral,
            "knowledge_anxiety": anxiety,
            "recent_learning": recent_learning,
        }
    
    # ============================================================
    # 序列化
    # ============================================================
    
    def to_dict(self) -> Dict:
        domains_data = {}
        for did, d in self.domains.items():
            domains_data[did] = {
                "domain_id": d.domain_id,
                "name": d.name,
                "level": d.level.value,
                "source": d.source.value if d.source else None,
                "source_detail": d.source_detail,
                "first_exposure": d.first_exposure,
                "last_exposure": d.last_exposure,
                "exposure_count": d.exposure_count,
                "hours_invested": d.hours_invested,
                "last_updated": d.last_updated,
                "curiosity": d.curiosity,
                "identity_weight": d.identity_weight,
                "is_outdated": d.is_outdated,
                "outdated_note": d.outdated_note,
                "emotional_tags": d.emotional_tags,
                "emotional_notes": d.emotional_notes,
                "bias_tendency": d.bias_tendency,
            }
        return {
            "domains": domains_data,
            "refused_domains": {k: v.value for k, v in self.refused_domains.items()},
            "quirk_understanding": {k: v.value for k, v in self.quirk_understanding.items()},
            "moral_context": {
                "character_moral_baseline": self.moral_context.character_moral_baseline,
                "situational_bending": self.moral_context.situational_bending,
                "partner_known": self.moral_context.partner_known,
                "partner_moral_tendency": self.moral_context.partner_moral_tendency,
            },
            "learning_log": [{
                "timestamp": e.timestamp,
                "domain_id": e.domain_id,
                "event_type": e.event_type,
                "level_before": e.level_before.value,
                "level_after": e.level_after.value,
                "context": e.context,
                "who_taught": e.who_taught,
                "emotional_response": e.emotional_response,
            } for e in self.learning_log],
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'LearningEngine':
        engine = cls()
        for did, dd in data.get("domains", {}).items():
            d = KnowledgeDomain(
                domain_id=dd["domain_id"],
                name=dd["name"],
                level=KnowledgeLevel(dd["level"]),
                source=KnowledgeSource(dd["source"]) if dd.get("source") else None,
                source_detail=dd.get("source_detail", ""),
                first_exposure=dd.get("first_exposure"),
                last_exposure=dd.get("last_exposure"),
                exposure_count=dd.get("exposure_count", 0),
                hours_invested=dd.get("hours_invested", 0),
                last_updated=dd.get("last_updated", 0),
                curiosity=dd.get("curiosity", 0),
                identity_weight=dd.get("identity_weight", 0),
                is_outdated=dd.get("is_outdated", False),
                outdated_note=dd.get("outdated_note", ""),
                emotional_tags=dd.get("emotional_tags", []),
                emotional_notes=dd.get("emotional_notes", ""),
                bias_tendency=dd.get("bias_tendency", ""),
            )
            engine.domains[did] = d
        
        for did, reason_val in data.get("refused_domains", {}).items():
            engine.refused_domains[did] = RefusalReason(reason_val)
        
        for qid, stance_val in data.get("quirk_understanding", {}).items():
            engine.quirk_understanding[qid] = QuirkStance(stance_val)
        
        mc = data.get("moral_context", {})
        engine.moral_context = MoralContext(
            character_moral_baseline=mc.get("character_moral_baseline", {}),
            situational_bending=mc.get("situational_bending", {}),
            partner_known=mc.get("partner_known", False),
            partner_moral_tendency=mc.get("partner_moral_tendency", ""),
        )
        
        for ed in data.get("learning_log", []):
            engine.learning_log.append(LearningEvent(
                timestamp=ed["timestamp"],
                domain_id=ed["domain_id"],
                event_type=ed["event_type"],
                level_before=KnowledgeLevel(ed["level_before"]),
                level_after=KnowledgeLevel(ed["level_after"]),
                context=ed.get("context", ""),
                who_taught=ed.get("who_taught", ""),
                emotional_response=ed.get("emotional_response", ""),
            ))
        
        return engine
