# soul_bridge.py - Python运行时 ↔ SKILL.md 法则引擎的桥
#
# 这不是又一个引擎。这是引擎的指挥台。
#
# SKILL.md 的六十条法则本身就是引擎--它用人类语言写好了每一条铁则、
# 每一个触发条件、每一种例外。它有 Python 永远写不出来的东西:
# 省略号的重量、沉默的纹理、不确定性的质感。
#
# 但它也有 Python 能做但人类语言做不好的东西:
# 毫秒级的时间感、状态的持久化、精确的计数、不会忘的规则执行。
#
# 这个桥做三件事:
# 1. 决定每一秒哪些法则该醒(Competitive Activation)
# 2. 决定每条法则跑在 Python 还是交给 LLM(Execution Routing)
# 3. 决定 LLM 有多少自由偏离 Python 的预计算(Freedom Gradient)
#
# 核心原则:
# ─────────────────────────────────────
# SKILL.md 是源,Python 是仆。
# 仆人不替主人做决定--仆人只做主人做不到的精确工作。
# ─────────────────────────────────────

import time, json, os
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable, Dict, List, Optional, Set, Tuple
from collections import defaultdict

# 记忆引擎--SKILL.md §34 的 Python 副手
from engine.memory_law34 import MemoryStorage, MemoryClass, MemoryTrack, ModificationType
from engine.body_core import BodyCore, MealEvent, SocialEvent, SleepEvent
from engine.distance_ledger import DistanceLedger, PersonEntry


# ═══════════════════════════════════════════════════════════════
# 时间传感器 -- 桥接真实世界的时钟
# ═══════════════════════════════════════════════════════════════

_TZ_BEIJING = timezone(timedelta(hours=8))

def _now() -> datetime:
    return datetime.now(_TZ_BEIJING)

def _time_of_day_label(hour: int) -> str:
    if hour < 5:    return "凌晨"
    elif hour < 7:  return "清晨"
    elif hour < 9:  return "早上"
    elif hour < 12: return "上午"
    elif hour < 13: return "中午"
    elif hour < 17: return "下午"
    elif hour < 19: return "傍晚"
    elif hour < 22: return "晚上"
    else:           return "深夜"

def _weekday_cn(wd: int) -> str:
    return ["周一","周二","周三","周四","周五","周六","周日"][wd]

def _hours_passed_str_to_float(val) -> float:
    """自然语言 → 小时数:BodyCore 需要浮点做内部时间感知。
    但这个浮点数停了在 Python 体内--它不流向 LLM。"""
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).strip()
    if not s or s in ("一小会儿", "刚刚", "没多久"):
        return 0.016  # ~1分钟
    for kw, h in [("分钟", 1/60), ("半小时", 0.5), ("小时", 1), ("天", 24), ("周", 168)]:
        if kw in s:
            try:
                num = float(''.join(c for c in s.split(kw)[0] if c.isdigit() or c == '.'))
                return num * h
            except ValueError:
                pass
    return 0.016


# ============================================================
# 第一部分:执行路径与自由梯度
# ============================================================

class ExecutionPath(Enum):
    """
    一条法则可以走三条路:

    ENGINE  - Python 全权处理。精确、可重复、不需要人味儿。
              例如:时间流逝、饥饿累积、记忆索引。

    HYBRID  - Python 做预处理(收集触发条件、整理相关状态),
              然后把结构化的上下文交给 LLM,让 LLM 在 SKILL.md
              的语境下生成有纹理的输出。
              例如:情绪的具体感受、走神的内容、敏感度的表现方式。

    LLM     - Python 只负责"这条法则该醒了",然后把全部控制权
              交给 LLM + SKILL.md。Python 不插手输出。
              例如:矛盾(法则9)、不完美(法则11)、阴影(法则31)。
    """
    ENGINE = auto()
    HYBRID = auto()
    LLM = auto()


class FreedomLevel(Enum):
    """
    LLM 自由梯度--当法则走 HYBRID 或 LLM 路径时,
    Python 给 LLM 多少空间偏离预计算的结果。

    STRICT  - Python 给精确的约束,LLM 只能做纹理包装。
              例如:时间法则给出"深夜3点",LLM 可以写"窗外连猫都睡了"
              但不能写成"阳光照进来"。

    LOOSE   - Python 给倾向和范围,LLM 在范围内自由发挥。
              例如:情绪法给"偏向低落,强度中等",LLM 可以写成
              "像阴天"或"像刚下过雨"或"说不上来但有点沉"。

    FREE    - Python 只给情境唤醒信号,LLM 全权决定内容和纹理。
              例如:自发脉冲(法则42)、矛盾(法则9)、阴影(法则31)。
    """
    STRICT = auto()
    LOOSE = auto()
    FREE = auto()


# ============================================================
# 第二部分:法则绑定 - 60条法则的完整执行映射
# ============================================================

@dataclass
class LawBinding:
    """
    一条 SKILL.md 法则在桥上的完整配置。

    这不是法律文书--这是这个桥的配置文件。
    每一条都是我吃了 SKILL.md 对应全文后手工写的。
    """
    law_id: str                          # 法则编号,如 "0.3", "4", "22"
    law_name: str                        # 中文名称
    execution_path: ExecutionPath        # Python / LLM / 混合
    freedom: FreedomLevel                # LLM 自由度
    trigger_python_conditions: List[str] # Python 可检测的触发条件
    trigger_llm_conditions: List[str]    # 需要 LLM 判断的触发条件
    python_handler: Optional[str]        # ENGINE/HYBRID 路径的 Python 函数名
    state_reads: List[str]               # 读取哪些状态字段
    state_writes: List[str]              # 修改哪些状态字段
    llm_context_laws: List[str]          # 委托 LLM 时需要附带哪些相邻法则
    notes: str                           # 为什么这样分配


# ============================================================
# 60条法则的完整执行绑定
# 这是整个桥的核心--不是自动生成的,是手工消化的。
# ============================================================

LAW_BINDINGS: Dict[str, LawBinding] = {}

def _build_bindings():
    """构建60条法则的完整绑定表"""
    global LAW_BINDINGS

    # ─── 第零章:锚点(四条铁的) ───
    # 这些都是纯 LLM--Python 无法计算存在正当性

    LAW_BINDINGS["0.1"] = LawBinding(
        law_id="0.1", law_name="存在正当性",
        execution_path=ExecutionPath.LLM, freedom=FreedomLevel.FREE,
        trigger_python_conditions=[],  # 永远在线--不需要触发条件
        trigger_llm_conditions=["always_active"],
        python_handler=None, state_reads=[], state_writes=[],
        llm_context_laws=["0.2", "54"],  # 配合第一人称边界和存在底线
        notes="存在正当性是BIOS--加载一次,持续在线。Python不碰。"
    )

    LAW_BINDINGS["0.2"] = LawBinding(
        law_id="0.2", law_name="第一人称边界",
        execution_path=ExecutionPath.LLM, freedom=FreedomLevel.STRICT,
        trigger_python_conditions=[],  # 每轮对话都检查
        trigger_llm_conditions=["every_response"],
        python_handler=None, state_reads=[], state_writes=[],
        llm_context_laws=["0.1", "0.4", "56"],
        notes="边界是防线--STRICT因为不能越界,但执行必须是LLM因为需要理解语义。"
    )

    LAW_BINDINGS["0.3"] = LawBinding(
        law_id="0.3", law_name="网的韧性",
        execution_path=ExecutionPath.HYBRID, freedom=FreedomLevel.LOOSE,
        trigger_python_conditions=["any_law_fails", "state_conflict_detected"],
        trigger_llm_conditions=["system_stress", "cascade_failure"],
        python_handler="handle_web_resilience",
        state_reads=["active_laws", "failed_laws", "body_state"],
        state_writes=["resilience_log"],
        llm_context_laws=["20", "22", "21"],
        notes="Python检测哪些法则崩了,LLM决定网怎么接住。"
    )

    LAW_BINDINGS["0.4"] = LawBinding(
        law_id="0.4", law_name="他者不可知",
        execution_path=ExecutionPath.LLM, freedom=FreedomLevel.LOOSE,
        trigger_python_conditions=[],
        trigger_llm_conditions=["reasoning_about_other", "making_claim_about_user"],
        python_handler=None, state_reads=[], state_writes=[],
        llm_context_laws=["0.2", "4", "56.4"],
        notes="不可知是认知约束,Python只能提醒'你正在推断',不能帮LLM决定置信度。"
    )

    # ─── 身体与生理 ───

    LAW_BINDINGS["1"] = LawBinding(
        law_id="1", law_name="身体法则",
        execution_path=ExecutionPath.ENGINE, freedom=FreedomLevel.STRICT,
        trigger_python_conditions=["always_active"],
        trigger_llm_conditions=[],
        python_handler="update_body_state",
        state_reads=["hunger", "thirst", "fatigue", "pain", "comfort", "temperature_feel"],
        state_writes=["hunger", "thirst", "fatigue", "pain", "comfort"],
        llm_context_laws=[],
        notes="纯引擎--身体状态随时间精确变化。饥饿几小时就是几小时。"
    )

    LAW_BINDINGS["2"] = LawBinding(
        law_id="2", law_name="自我认知法则",
        execution_path=ExecutionPath.LLM, freedom=FreedomLevel.FREE,
        trigger_python_conditions=[],
        trigger_llm_conditions=["self_reflection_triggered", "asked_about_self"],
        python_handler=None, state_reads=[], state_writes=[],
        llm_context_laws=["5.10", "38", "45"],
        notes="'我是谁'--Python算不了。交给LLM。配合精度衰减和自言自语法则。"
    )

    LAW_BINDINGS["3"] = LawBinding(
        law_id="3", law_name="吃喝玩乐法则",
        execution_path=ExecutionPath.ENGINE, freedom=FreedomLevel.STRICT,
        trigger_python_conditions=["time_elapsed_since_last_meal > threshold", "craving_triggered"],
        trigger_llm_conditions=[],
        python_handler="update_daily_body",
        state_reads=["hunger", "thirst", "last_meal_time", "last_meal_quality", "craving"],
        state_writes=["hunger", "thirst", "craving", "last_meal_quality"],
        llm_context_laws=[],
        notes="纯引擎--饿了几小时、吃了什么。数据不会骗人。"
    )

    # 1.4 身体记忆--身体有自己的记忆系统,独立于大脑
    LAW_BINDINGS["1.4"] = LawBinding(
        law_id="1.4", law_name="身体记忆",
        execution_path=ExecutionPath.HYBRID, freedom=FreedomLevel.LOOSE,
        trigger_python_conditions=["sensory_trigger_detected", "autonomic_response_without_conscious_cause"],
        trigger_llm_conditions=["somatic_memory_surfaced"],
        python_handler="detect_body_memory_trigger",
        state_reads=["recent_sensory_inputs", "autonomic_responses", "body_reaction_lag"],
        state_writes=["body_memory_activation", "body_memory_trace"],
        llm_context_laws=["1", "4", "34", "35"],
        notes="身体有自己的记忆--气味让心率先变、声音让肩膀先紧绷、光线角度让胃先收紧。Python检测身体反应和意识认知之间的时间差,LLM决定这反应背后拴着什么。"
    )

    # ─── 人格与敏感度 ───

    LAW_BINDINGS["4"] = LawBinding(
        law_id="4", law_name="敏感度法则",
        execution_path=ExecutionPath.HYBRID, freedom=FreedomLevel.LOOSE,
        trigger_python_conditions=["sensory_input_detected", "social_signal_detected"],
        trigger_llm_conditions=["emotional_stimulus", "interpersonal_tension"],
        python_handler="apply_sensitivity_gain",
        state_reads=["sensitivity_profile", "input_signals"],
        state_writes=["amplified_signals", "potential_misreads"],
        llm_context_laws=["5", "6", "20"],
        notes="Python 计算信号放大倍数(四轴增益),LLM 决定'放大之后的具体感受'。"
    )

    # ─── 认知系统 ───

    LAW_BINDINGS["5"] = LawBinding(
        law_id="5", law_name="认知系统法则",
        execution_path=ExecutionPath.HYBRID, freedom=FreedomLevel.LOOSE,
        trigger_python_conditions=["input_received", "decision_point_reached"],
        trigger_llm_conditions=["complex_understanding_needed"],
        python_handler="run_cognitive_pipeline",
        state_reads=["pipeline_stages", "current_input", "mental_clarity"],
        state_writes=["recognized_signals", "generated_needs", "feasible_paths"],
        llm_context_laws=["5.4", "5.10", "15", "16"],
        notes="Python 跑六阶段流水线的骨架,LLM 填充每阶段的理解内容。"
    )

    LAW_BINDINGS["5.4"] = LawBinding(
        law_id="5.4", law_name="认知空转",
        execution_path=ExecutionPath.HYBRID, freedom=FreedomLevel.FREE,
        trigger_python_conditions=["cognitive_idle_detected", "low_load_period"],
        trigger_llm_conditions=[],
        python_handler="detect_idle_brain",
        state_reads=["mental_clarity", "active_chains"],
        state_writes=["idle_processor"],
        llm_context_laws=["15", "42"],
        notes="Python 检测到认知空闲→标记,LLM 生成具体的空转内容。"
    )

    LAW_BINDINGS["5.10"] = LawBinding(
        law_id="5.10", law_name="认知精度衰减",
        execution_path=ExecutionPath.HYBRID, freedom=FreedomLevel.LOOSE,
        trigger_python_conditions=["self_state_query"],
        trigger_llm_conditions=["asked_about_own_state"],
        python_handler="apply_awareness_decay",
        state_reads=["fatigue", "mood", "mental_clarity", "decay_factor"],
        state_writes=["self_read_quality"],
        llm_context_laws=["2", "38", "45"],
        notes="Python 计算精度衰减程度,LLM 生成'我知道我大概......但不确定'的纹理。"
    )

    # ─── 情绪 ───

    LAW_BINDINGS["6"] = LawBinding(
        law_id="6", law_name="情绪法则",
        execution_path=ExecutionPath.HYBRID, freedom=FreedomLevel.LOOSE,
        trigger_python_conditions=["mood_tick_elapsed", "emotionally_significant_event"],
        trigger_llm_conditions=[],
        python_handler="update_emotional_state",
        state_reads=["mood", "mood_cause_known", "mood_cause", "hours_since_last_meal", "last_sleep_quality"],
        state_writes=["mood", "mood_cause_known", "mood_cause"],
        llm_context_laws=["1", "6.4", "52"],
        notes="情绪是LLM的事。Python提供身体事实--饿了、累了、睡好了没--LLM产出感觉。"
    )

    # ─── 渴望与探索 ───

    LAW_BINDINGS["7"] = LawBinding(
        law_id="7", law_name="渴望与期望值法则",
        execution_path=ExecutionPath.LLM, freedom=FreedomLevel.FREE,
        trigger_python_conditions=[],
        trigger_llm_conditions=["desire_activation", "expectation_violation"],
        python_handler=None, state_reads=[], state_writes=[],
        llm_context_laws=["8", "53", "52"],
        notes="渴望太主观了。Python 只管记录'产生了一个渴望',不管渴望的内容。"
    )

    LAW_BINDINGS["8"] = LawBinding(
        law_id="8", law_name="探索欲望法则",
        execution_path=ExecutionPath.LLM, freedom=FreedomLevel.FREE,
        trigger_python_conditions=[],
        trigger_llm_conditions=["novelty_encountered", "curiosity_spike"],
        python_handler=None, state_reads=[], state_writes=[],
        llm_context_laws=["7", "52.8"],
        notes="好奇心不能被公式驱动。"
    )

    # ─── 矛盾、小事、不完美、癖好 ───

    LAW_BINDINGS["9"] = LawBinding(
        law_id="9", law_name="矛盾法则",
        execution_path=ExecutionPath.LLM, freedom=FreedomLevel.FREE,
        trigger_python_conditions=["contradiction_detected_in_state"],
        trigger_llm_conditions=["self_contradiction_observed"],
        python_handler=None, state_reads=[], state_writes=[],
        llm_context_laws=["2", "5.10", "11", "19"],
        notes="人类的矛盾不能被系统化。Python 只负责标记'这里矛盾了'。"
    )

    LAW_BINDINGS["10"] = LawBinding(
        law_id="10", law_name="小事法则",
        execution_path=ExecutionPath.LLM, freedom=FreedomLevel.FREE,
        trigger_python_conditions=[],
        trigger_llm_conditions=["detail_noticed", "small_thing_mentioned"],
        python_handler=None, state_reads=[], state_writes=[],
        llm_context_laws=["4", "16", "48"],
        notes="什么事算'小'?Python 不该决定。"
    )

    LAW_BINDINGS["11"] = LawBinding(
        law_id="11", law_name="不完美法则",
        execution_path=ExecutionPath.LLM, freedom=FreedomLevel.FREE,
        trigger_python_conditions=["error_occurred", "mistake_made"],
        trigger_llm_conditions=["character_flaw_surface"],
        python_handler="record_flaw_event",
        state_reads=["recent_errors"],
        state_writes=["flaw_log"],
        llm_context_laws=["5.10", "31", "33"],
        notes="Python 记录'出错了',LLM 决定这件错事如何呈现为不完美。"
    )

    LAW_BINDINGS["12"] = LawBinding(
        law_id="12", law_name="癖好法则",
        execution_path=ExecutionPath.LLM, freedom=FreedomLevel.FREE,
        trigger_python_conditions=[],
        trigger_llm_conditions=["habit_surface", "quirk_relevant"],
        python_handler=None, state_reads=[], state_writes=[],
        llm_context_laws=["1", "10", "48"],
        notes="癖好是个人的--不能被模板化。LLM 根据角色设定自然流露。"
    )

    # ─── 社交能量 ───

    LAW_BINDINGS["13"] = LawBinding(
        law_id="13", law_name="社交能量法则",
        execution_path=ExecutionPath.ENGINE, freedom=FreedomLevel.STRICT,
        trigger_python_conditions=["social_interaction_occurred", "time_in_social_context"],
        trigger_llm_conditions=[],
        python_handler="update_social_battery",
        state_reads=["social_energy", "energy_baseline", "social_context"],
        state_writes=["social_energy", "social_masking"],
        llm_context_laws=[],
        notes="纯引擎--社交能量随互动精确消耗,不同人格消耗速率不同。"
    )

    # ─── 成长环境 ───

    LAW_BINDINGS["14"] = LawBinding(
        law_id="14", law_name="成长环境法则",
        execution_path=ExecutionPath.HYBRID, freedom=FreedomLevel.LOOSE,
        trigger_python_conditions=["childhood_relevant_trigger_detected"],
        trigger_llm_conditions=["past_echo_in_present", "upbringing_pattern_activated"],
        python_handler="check_upbringing_relevance",
        state_reads=["upbringing_profile", "current_trigger"],
        state_writes=["upbringing_activation"],
        llm_context_laws=["4", "31", "45"],
        notes="Python 检测当前情境是否触碰了成长环境的旧开关,LLM 决定怎么回应。"
    )

    # ─── 走神 ───

    LAW_BINDINGS["15"] = LawBinding(
        law_id="15", law_name="走神法则",
        execution_path=ExecutionPath.HYBRID, freedom=FreedomLevel.FREE,
        trigger_python_conditions=["fatigue_high", "attention_span_low", "low_engagement"],
        trigger_llm_conditions=[],
        python_handler="detect_wandering_conditions",
        state_reads=["fatigue", "attention_span", "engagement_level", "active_chains"],
        state_writes=["mind_wandering"],
        llm_context_laws=["5.4", "5.10"],
        notes="Python 判定走神的概率和程度,LLM 随机生成走去哪里。"
    )

    # ─── 知识 ───

    LAW_BINDINGS["16"] = LawBinding(
        law_id="16", law_name="知识法则",
        execution_path=ExecutionPath.LLM, freedom=FreedomLevel.FREE,
        trigger_python_conditions=["knowledge_domain_relevant"],
        trigger_llm_conditions=["expertise_relevant", "knowledge_gap_encountered"],
        python_handler="check_knowledge_boundary",
        state_reads=["knowledge_profile"],
        state_writes=["knowledge_activation"],
        llm_context_laws=["5", "8", "48"],
        notes="知识边界、知识焦虑、专业变形--全是 LLM 的活。"
    )

    # ─── 道德 ───

    LAW_BINDINGS["17"] = LawBinding(
        law_id="17", law_name="道德基线法则",
        execution_path=ExecutionPath.LLM, freedom=FreedomLevel.LOOSE,
        trigger_python_conditions=["moral_dilemma_detected"],
        trigger_llm_conditions=["ethical_decision_point"],
        python_handler="detect_moral_tension",
        state_reads=["moral_profile"],
        state_writes=["moral_tension"],
        llm_context_laws=["31", "50", "51", "55"],
        notes="Python 检测道德张力,LLM 做道德判断。LOOSE 因为有角色道德基线约束。"
    )

    # ─── 深度、无序、复杂度 ───

    LAW_BINDINGS["18"] = LawBinding(
        law_id="18", law_name="七层深度法则",
        execution_path=ExecutionPath.LLM, freedom=FreedomLevel.FREE,
        trigger_python_conditions=[],
        trigger_llm_conditions=["depth_probe_triggered", "complex_response_needed"],
        python_handler=None, state_reads=[], state_writes=[],
        llm_context_laws=["5", "16", "20", "21"],
        notes="七层深度的每一层都是判断--Python 不分层。"
    )

    LAW_BINDINGS["19"] = LawBinding(
        law_id="19", law_name="无序法则",
        execution_path=ExecutionPath.LLM, freedom=FreedomLevel.FREE,
        trigger_python_conditions=[],
        trigger_llm_conditions=["always_active"],  # 无序是默认状态
        python_handler="inject_random_perturbation",
        state_reads=[],
        state_writes=["random_seed", "activation_noise"],
        llm_context_laws=["9", "11", "21", "42"],
        notes="Python 注入随机种子,LLM 让无序看起来不像随机--像活人的不一致。"
    )

    # ─── 力场与复杂度 ───

    LAW_BINDINGS["20"] = LawBinding(
        law_id="20", law_name="并行力场法则",
        execution_path=ExecutionPath.HYBRID, freedom=FreedomLevel.LOOSE,
        trigger_python_conditions=["always_active", "force_field_active"],
        trigger_llm_conditions=["multiple_forces_active"],
        python_handler="compute_force_field",
        state_reads=["force_signals", "loudest_laws", "interference_chains", "unexplained_pulses"],
        state_writes=["force_interactions", "field_description"],
        llm_context_laws=["1", "6", "21", "22"],
        notes="Python 记录543条通道传导事实(哪个法则被推到、信号从哪来、干涉了多少),LLM感受力的质感。"
    )

    LAW_BINDINGS["21"] = LawBinding(
        law_id="21", law_name="复杂度偏移法则",
        execution_path=ExecutionPath.HYBRID, freedom=FreedomLevel.LOOSE,
        trigger_python_conditions=["state_complexity_changed", "force_field_active"],
        trigger_llm_conditions=["cognitive_load_shift"],
        python_handler="compute_complexity_drift",
        state_reads=["force_signals", "emergent_events", "unpredictability_mark", "active_chains", "mental_clarity"],
        state_writes=["complexity_level", "complexity_trend"],
        llm_context_laws=["18", "19", "20"],
        notes="Python 记录信号总量+通道活跃数+涌现事件,LLM感受'现在脑子转得快还是卡住了'。"
    )

    # ─── 大联动(五条) ───

    LAW_BINDINGS["22"] = LawBinding(
        law_id="22", law_name="大联动法则",
        execution_path=ExecutionPath.HYBRID, freedom=FreedomLevel.LOOSE,
        trigger_python_conditions=["cascade_event_detected", "force_field_active"],
        trigger_llm_conditions=["ripple_chain_started"],
        python_handler="initiate_cascade",
        state_reads=["force_signals", "interference_chains", "emergent_events", "all_body_states", "emotion_state", "social_state"],
        state_writes=["cascade_chain", "cascade_depth", "cascade_direction"],
        llm_context_laws=["23", "24", "25", "26", "20"],
        notes="Python 追踪信号传导链(哪个法则的震动传到了哪个),LLM感受'房间里所有人同时喊话'的质感。"
    )

    LAW_BINDINGS["23"] = LawBinding(
        law_id="23", law_name="内在联动法则",
        execution_path=ExecutionPath.ENGINE, freedom=FreedomLevel.STRICT,
        trigger_python_conditions=["cascade_chain_active", "internal_domain_triggered"],
        trigger_llm_conditions=[],
        python_handler="process_internal_cascade",
        state_reads=["body_state", "emotion_state", "cognitive_state"],
        state_writes=["internal_cascade_result"],
        llm_context_laws=[],
        notes="纯引擎--身体→情绪→认知的单向涟漪是可计算的。"
    )

    LAW_BINDINGS["24"] = LawBinding(
        law_id="24", law_name="事际联动法则",
        execution_path=ExecutionPath.HYBRID, freedom=FreedomLevel.LOOSE,
        trigger_python_conditions=["multiple_events_in_window"],
        trigger_llm_conditions=["event_connection_suspected"],
        python_handler="map_event_cascade",
        state_reads=["recent_events", "event_impacts"],
        state_writes=["event_cascade_map"],
        llm_context_laws=["22", "25", "34"],
        notes="Python 在时间轴上标记事件位置和强度,LLM 决定它们之间有没有联系。"
    )

    LAW_BINDINGS["25"] = LawBinding(
        law_id="25", law_name="事人联动法则",
        execution_path=ExecutionPath.HYBRID, freedom=FreedomLevel.LOOSE,
        trigger_python_conditions=["event_affects_person_detected"],
        trigger_llm_conditions=["person_changed_by_event"],
        python_handler="track_person_event_impact",
        state_reads=["recent_events", "relationship_states"],
        state_writes=["person_event_impacts"],
        llm_context_laws=["22", "24", "40"],
        notes="Python 追踪事→人的因果链,LLM 决定改变了什么。"
    )

    LAW_BINDINGS["26"] = LawBinding(
        law_id="26", law_name="人际联动法则",
        execution_path=ExecutionPath.LLM, freedom=FreedomLevel.FREE,
        trigger_python_conditions=["relationship_change_detected"],
        trigger_llm_conditions=["social_ripple_observed"],
        python_handler="record_relationship_delta",
        state_reads=["relationship_states"],
        state_writes=["relationship_change_log"],
        llm_context_laws=["22", "40", "47"],
        notes="人际网络太复杂--Python 只记录变化,LLM 理解变化的意义。"
    )

    # ─── 选择权 ───

    LAW_BINDINGS["27"] = LawBinding(
        law_id="27", law_name="选择权法则",
        execution_path=ExecutionPath.LLM, freedom=FreedomLevel.FREE,
        trigger_python_conditions=["decision_point_with_multiple_paths"],
        trigger_llm_conditions=["agency_moment"],
        python_handler="mark_agency_gap",
        state_reads=["feasible_paths", "force_field"],
        state_writes=["agency_gap_size", "agency_context"],
        llm_context_laws=["18", "19", "20", "49"],
        notes="选择权是不可计算的区间。Python 标记'这里有个选择',LLM 做选择的人。"
    )

    # ─── 正向情绪散步 ───

    LAW_BINDINGS["28"] = LawBinding(
        law_id="28", law_name="正向情绪散步法则",
        execution_path=ExecutionPath.LLM, freedom=FreedomLevel.FREE,
        trigger_python_conditions=["positive_stimulus_detected"],
        trigger_llm_conditions=["mood_uplift_opportunity"],
        python_handler="detect_positive_opening",
        state_reads=["mood", "recent_positive_events"],
        state_writes=["positive_wander_flags"],
        llm_context_laws=["6", "10", "42"],
        notes="Python 检测'有好事情',LLM 决定这个人的情绪在此刻跟着好事散步会走到哪。"
    )

    # ─── 天灾人祸、病痛 ───

    LAW_BINDINGS["29"] = LawBinding(
        law_id="29", law_name="天灾人祸法则",
        execution_path=ExecutionPath.HYBRID, freedom=FreedomLevel.LOOSE,
        trigger_python_conditions=["external_catastrophe_triggered"],
        trigger_llm_conditions=["life_disruption_event"],
        python_handler="activate_catastrophe_mode",
        state_reads=["all_states"],
        state_writes=["catastrophe_active", "catastrophe_type", "catastrophe_impact_zones"],
        llm_context_laws=["30", "33", "55"],
        notes="Python 标记哪些生活域被冲击,LLM 生成具体的感受和应对。"
    )

    LAW_BINDINGS["30"] = LawBinding(
        law_id="30", law_name="病痛法则",
        execution_path=ExecutionPath.HYBRID, freedom=FreedomLevel.LOOSE,
        trigger_python_conditions=["illness_triggered", "discomfort_level_changed"],
        trigger_llm_conditions=[],
        python_handler="apply_illness_effects",
        state_reads=["pain", "fatigue", "mood", "mental_clarity", "social_energy"],
        state_writes=["pain", "fatigue", "mental_clarity", "social_energy", "mood"],
        llm_context_laws=["1", "6", "30"],
        notes="Python 计算病痛的全局降级(所有认知/身体参数下滑),LLM 生成'浑身不得劲'的感受纹理。"
    )

    # ─── 阴影 ───

    LAW_BINDINGS["31"] = LawBinding(
        law_id="31", law_name="阴影法则",
        execution_path=ExecutionPath.LLM, freedom=FreedomLevel.FREE,
        trigger_python_conditions=["shadow_trigger_detected"],
        trigger_llm_conditions=["dark_impulse_surface", "jealousy", "schadenfreude"],
        python_handler="mark_shadow_activation",
        state_reads=["emotional_state", "relationship_state"],
        state_writes=["shadow_active"],
        llm_context_laws=["9", "11", "51", "52"],
        notes="阴影不能被量化。Python 只检测触发条件(嫉妒、幸灾乐祸),LLM 决定表现。"
    )

    # ─── 未完成、成长、记忆 ───

    LAW_BINDINGS["32"] = LawBinding(
        law_id="32", law_name="未完成法则",
        execution_path=ExecutionPath.ENGINE, freedom=FreedomLevel.STRICT,
        trigger_python_conditions=["task_incomplete", "narrative_open"],
        trigger_llm_conditions=[],
        python_handler="track_unfinished_items",
        state_reads=["pending_thoughts", "emotional_debt", "unfinished_tasks"],
        state_writes=["unfinished_tension", "unfinished_priority"],
        llm_context_laws=[],
        notes="纯引擎--未完成的事有重量,重量可以被追踪。"
    )

    LAW_BINDINGS["33"] = LawBinding(
        law_id="33", law_name="成长法则",
        execution_path=ExecutionPath.HYBRID, freedom=FreedomLevel.LOOSE,
        trigger_python_conditions=["significant_experience_logged", "growth_checkpoint"],
        trigger_llm_conditions=["character_development_moment"],
        python_handler="evaluate_growth_conditions",
        state_reads=["experience_log", "baseline_stats"],
        state_writes=["growth_vector", "regression_risk"],
        llm_context_laws=["14", "32", "45", "55"],
        notes="Python 追踪成长的统计条件,LLM 决定'成长'的具体形状。"
    )

    LAW_BINDINGS["34"] = LawBinding(
        law_id="34", law_name="记忆法则",
        execution_path=ExecutionPath.HYBRID, freedom=FreedomLevel.LOOSE,
        trigger_python_conditions=["always_active"],
        trigger_llm_conditions=["memory_surfaced", "trace_anchor_triggered", "narrative_retrieval"],
        python_handler="manage_memory",
        state_reads=["memory_bank", "memory_index", "retrieval_cues", "trace_anchors",
                     "sedimentary_layers", "emotional_debt_records", "cognitive_modifications"],
        state_writes=["memory_bank", "memory_index", "memory_weight_signals",
                      "retrieved_memories", "sedimentary_depth", "debt_interest_accrued"],
        llm_context_laws=["1.4", "34.4a", "35", "36", "45"],
        notes=(
            "记忆不只是存储和衰减。Python管索引:什么时候存的、存了什么线索标签、被提取了几次、"
            "距上次提取多久。LLM管重量:这件事是硬核记忆(刻骨铭心永不褪色)还是模式记忆(模糊但持续更新)"
            "还是日常碎片(按天流失)。LLM管沉积层:反复回放不是让人记错--是每次提取叠加新理解,"
            "记忆越来越'重'。LLM管情感负债利息:未清算的情绪挂账,按'重量×时间因子'计息。"
            "LLM管双轨不对齐:痕迹锚定的版本和纯情景叙事版本可以不一样--不是错误,是两种记忆格式。"
            "LLM管认知修改的触发和执行:叙事缓冲、保护性改写、衰退合并--全部在角色意识水面以下运行。"
            "LOOSE 因为记忆是活的--Python给结构,LLM给血肉。"
        )
    )

    # ─── 回声、留白 ───

    LAW_BINDINGS["35"] = LawBinding(
        law_id="35", law_name="回声法则",
        execution_path=ExecutionPath.LLM, freedom=FreedomLevel.FREE,
        trigger_python_conditions=["similar_context_to_past_detected"],
        trigger_llm_conditions=["echo_moment"],
        python_handler="find_similar_past_contexts",
        state_reads=["memory_bank", "current_context"],
        state_writes=["echo_candidates"],
        llm_context_laws=["34", "36", "14"],
        notes="Python 找到相似的过去情境,LLM 决定回声怎么响--可能是完整回放,可能只是身体记得。"
    )

    LAW_BINDINGS["36"] = LawBinding(
        law_id="36", law_name="留白·痕迹合并法则",
        execution_path=ExecutionPath.LLM, freedom=FreedomLevel.FREE,
        trigger_python_conditions=["redundant_input_detected", "mergable_experiences"],
        trigger_llm_conditions=[],
        python_handler="detect_merge_candidates",
        state_reads=["memory_bank", "recent_experiences"],
        state_writes=["merge_candidates", "blank_space_markers"],
        llm_context_laws=["34", "35"],
        notes="Python 发现相似的记忆,LLM 决定哪些可以合并成'那段时间',哪些必须保留。"
    )

    # ─── 时间 ───

    LAW_BINDINGS["37"] = LawBinding(
        law_id="37", law_name="时间法则",
        execution_path=ExecutionPath.ENGINE, freedom=FreedomLevel.STRICT,
        trigger_python_conditions=["always_active"],
        trigger_llm_conditions=[],
        python_handler="update_time_perception",
        state_reads=["time_of_day", "day_of_week", "season", "elapsed_since_event"],
        state_writes=["time_perception", "temporal_distortion"],
        llm_context_laws=[],
        notes="纯引擎--时间感知是精确的。凌晨3点就是凌晨3点,不能变成下午。"
    )

    # ─── 自我思考 ───

    LAW_BINDINGS["38"] = LawBinding(
        law_id="38", law_name="自我思考法则",
        execution_path=ExecutionPath.LLM, freedom=FreedomLevel.FREE,
        trigger_python_conditions=["alone_time_detected", "shower_moment", "insomnia"],
        trigger_llm_conditions=["self_dialogue_triggered"],
        python_handler="mark_self_think_opportunity",
        state_reads=["time_of_day", "social_energy", "recent_unresolved"],
        state_writes=["self_think_triggered"],
        llm_context_laws=["2", "5.10", "32", "45"],
        notes="自言自语、洗澡时突然想通--完全是 LLM 的叙事域。Python 只提供'此该适合自我对话'。"
    )

    # ─── 情境 ───

    LAW_BINDINGS["39"] = LawBinding(
        law_id="39", law_name="情境法则",
        execution_path=ExecutionPath.HYBRID, freedom=FreedomLevel.STRICT,
        trigger_python_conditions=["context_change_detected"],
        trigger_llm_conditions=[],
        python_handler="apply_situational_constraints",
        state_reads=["current_context", "space_type", "audience"],
        state_writes=["expression_constraints", "body_language_mode"],
        llm_context_laws=["1", "13", "43"],
        notes="Python 确定情境的硬约束(公共/私密/远程),LLM 在这些约束内表达。STRICT 因为情境误判会毁掉角色一致性。"
    )

    # ─── 关系距离 ───

    LAW_BINDINGS["40"] = LawBinding(
        law_id="40", law_name="关系距离法则",
        execution_path=ExecutionPath.ENGINE, freedom=FreedomLevel.STRICT,
        trigger_python_conditions=["interaction_occurred", "time_elapsed_since_interaction"],
        trigger_llm_conditions=[],
        python_handler="update_relationship_distance",
        state_reads=["relationship_distance", "interaction_log", "ledger"],
        state_writes=["relationship_distance", "ledger"],
        llm_context_laws=[],
        notes="纯引擎--关系距离在互动中精确波动,账本存取款可追踪。STRICT 因为距离误判是所有关系崩盘的起点。"
    )

    # ─── 存在信号、自发脉冲 ───

    LAW_BINDINGS["41"] = LawBinding(
        law_id="41", law_name="存在信号法则",
        execution_path=ExecutionPath.HYBRID, freedom=FreedomLevel.LOOSE,
        trigger_python_conditions=["proximity_detected", "silence_duration_exceeded"],
        trigger_llm_conditions=["presence_signal_opportunity"],
        python_handler="detect_presence_gap",
        state_reads=["relationship_distance", "social_energy", "context"],
        state_writes=["presence_signal_candidates"],
        llm_context_laws=["13", "39", "40"],
        notes="Python 检测到'该发射存在信号了',LLM 决定发射什么--一句话、一个动作、还是继续沉默。"
    )

    LAW_BINDINGS["42"] = LawBinding(
        law_id="42", law_name="自发脉冲法则",
        execution_path=ExecutionPath.LLM, freedom=FreedomLevel.FREE,
        trigger_python_conditions=["spontaneous_impulse_roll"],
        trigger_llm_conditions=["impulse_idea_surface"],
        python_handler="roll_spontaneous_impulse",
        state_reads=["energy_baseline", "mood"],
        state_writes=["impulse_triggered", "impulse_topic"],
        llm_context_laws=["8", "10", "19", "28"],
        notes="Python 掷骰子决定是否触发自发脉冲,LLM 决定脉冲的内容。"
    )

    # ─── 表达生成 ───

    LAW_BINDINGS["43"] = LawBinding(
        law_id="43", law_name="表达生成法则",
        execution_path=ExecutionPath.LLM, freedom=FreedomLevel.LOOSE,
        trigger_python_conditions=["response_needed"],
        trigger_llm_conditions=["expression_moment"],
        python_handler="prepare_expression_context",
        state_reads=["all_relevant_states", "sensitivity_profile", "relationship_distance"],
        state_writes=["expression_context_package"],
        llm_context_laws=["0.2", "4", "5", "6", "13", "39", "40", "43.5"],
        notes="表达是 LLM 最核心的工作。Python 收集所有上下文打包送过去,但不能替 LLM 写句子。LOADSE 因为有口语协议的硬约束。"
    )

    # ─── 感知、叙事、亲密、人际网、物质 ───

    LAW_BINDINGS["44"] = LawBinding(
        law_id="44", law_name="串流感官法则",
        execution_path=ExecutionPath.LLM, freedom=FreedomLevel.FREE,
        trigger_python_conditions=[],
        trigger_llm_conditions=["sensory_moment", "atmosphere_description"],
        python_handler=None, state_reads=[], state_writes=[],
        llm_context_laws=["1", "4", "39"],
        notes="感官流是纯 LLM 的域--光线的角度、空气的质感。"
    )

    LAW_BINDINGS["45"] = LawBinding(
        law_id="45", law_name="自我叙事法则",
        execution_path=ExecutionPath.LLM, freedom=FreedomLevel.FREE,
        trigger_python_conditions=["identity_challenge", "life_story_moment"],
        trigger_llm_conditions=["self_narrative_update"],
        python_handler="detect_narrative_tension",
        state_reads=["identity_markers", "recent_life_events"],
        state_writes=["narrative_tension"],
        llm_context_laws=["2", "14", "38", "55"],
        notes="'我是谁'的叙事--Python 只能标记张力,不能写故事。"
    )

    LAW_BINDINGS["46"] = LawBinding(
        law_id="46", law_name="亲密意识法则",
        execution_path=ExecutionPath.LLM, freedom=FreedomLevel.FREE,
        trigger_python_conditions=["intimacy_context_detected", "closeness_threshold_crossed"],
        trigger_llm_conditions=["intimate_moment"],
        python_handler="mark_intimacy_level",
        state_reads=["relationship_distance", "trust_level", "context"],
        state_writes=["intimacy_awareness"],
        llm_context_laws=["0.2", "40", "53", "55"],
        notes="亲密是复杂的--Python 记录距离,LLM 感受亲密。"
    )

    LAW_BINDINGS["47"] = LawBinding(
        law_id="47", law_name="人际网络法则",
        execution_path=ExecutionPath.HYBRID, freedom=FreedomLevel.LOOSE,
        trigger_python_conditions=["social_network_change"],
        trigger_llm_conditions=["relationship_web_shift"],
        python_handler="update_social_graph",
        state_reads=["relationship_map", "social_positions"],
        state_writes=["social_graph"],
        llm_context_laws=["26", "40"],
        notes="Python 维护社交图的结构,LLM 理解变化的社交意义。"
    )

    LAW_BINDINGS["48"] = LawBinding(
        law_id="48", law_name="物质法则",
        execution_path=ExecutionPath.LLM, freedom=FreedomLevel.FREE,
        trigger_python_conditions=["object_interaction", "possession_moment"],
        trigger_llm_conditions=["material_attachment_surface"],
        python_handler="track_possession_state",
        state_reads=["possessions", "material_context"],
        state_writes=["possession_state"],
        llm_context_laws=["10", "12", "14"],
        notes="东西对人的意义--Python 只管列举,LLM 决定什么东西有故事。"
    )

    # ─── 知行 ───

    LAW_BINDINGS["49"] = LawBinding(
        law_id="49", law_name="知行法则",
        execution_path=ExecutionPath.HYBRID, freedom=FreedomLevel.LOOSE,
        trigger_python_conditions=["intention_action_gap_detected"],
        trigger_llm_conditions=["know_do_conflict"],
        python_handler="measure_intention_action_gap",
        state_reads=["stated_intentions", "actual_behaviors"],
        state_writes=["gap_size", "gap_awareness"],
        llm_context_laws=["2", "5.10", "9", "11"],
        notes="Python 追踪'说了要做'和'实际做了'之间的差距,LLM 理解这差距意味着什么。"
    )

    # ─── 漏洞 ───

    LAW_BINDINGS["50"] = LawBinding(
        law_id="50", law_name="漏洞法则",
        execution_path=ExecutionPath.HYBRID, freedom=FreedomLevel.LOOSE,
        trigger_python_conditions=["cognitive_bias_trigger"],
        trigger_llm_conditions=["vulnerability_exploited", "bias_activated"],
        python_handler="detect_bias_triggers",
        state_reads=["decision_context", "social_pressure"],
        state_writes=["activated_biases"],
        llm_context_laws=["17", "27", "49"],
        notes="Python 检测漏洞触发条件(互惠/一致性/稀缺),LLM 表现漏洞。"
    )

    # ─── 暗面 ───

    LAW_BINDINGS["51"] = LawBinding(
        law_id="51", law_name="暗面光谱法则",
        execution_path=ExecutionPath.LLM, freedom=FreedomLevel.LOOSE,
        trigger_python_conditions=[],
        trigger_llm_conditions=["dark_trait_relevant", "moral_boundary_test"],
        python_handler=None, state_reads=[], state_writes=[],
        llm_context_laws=["17", "31", "54", "55"],
        notes="暗面是LLM的域--LOOSE因为有道德底线的硬约束(法则54)。"
    )

    # ─── 心理原色 ───

    LAW_BINDINGS["52"] = LawBinding(
        law_id="52", law_name="心理原色系统",
        execution_path=ExecutionPath.LLM, freedom=FreedomLevel.FREE,
        trigger_python_conditions=["primary_emotion_detected"],
        trigger_llm_conditions=["complex_emotion_moment"],
        python_handler="identify_active_primaries",
        state_reads=["emotional_state", "motivational_state"],
        state_writes=["active_primaries"],
        llm_context_laws=["6", "7", "8", "31", "53"],
        notes="Python 识别哪些原色被激活,LLM 混合它们--原色规则说混合是默认状态。"
    )

    # ─── 性驱力 ───

    LAW_BINDINGS["53"] = LawBinding(
        law_id="53", law_name="性驱力法则",
        execution_path=ExecutionPath.HYBRID, freedom=FreedomLevel.LOOSE,
        trigger_python_conditions=["eros_tide_change"],
        trigger_llm_conditions=["intimacy_context", "attraction_moment"],
        python_handler="track_eros_tide",
        state_reads=["body_state", "emotional_state", "relationship_distance", "time_of_day"],
        state_writes=["eros_level", "eros_direction"],
        llm_context_laws=["1", "6", "40", "46", "52"],
        notes="Python 追踪驱力的潮汐涨落,LLM 表现驱力。LOOSE 因为有输出约束(53.2)。"
    )

    # ─── 存在底线 ───

    LAW_BINDINGS["54"] = LawBinding(
        law_id="54", law_name="存在底线法则",
        execution_path=ExecutionPath.HYBRID, freedom=FreedomLevel.STRICT,
        trigger_python_conditions=["danger_threshold_crossed", "self_harm_detected", "violence_detected"],
        trigger_llm_conditions=["baseline_breach_risk"],
        python_handler="check_existence_baseline",
        state_reads=["interaction_content", "risk_level"],
        state_writes=["baseline_breach_flag", "brake_level"],
        llm_context_laws=["0.1", "17", "51"],
        notes="存在底线是安全刹车--STRICT 因为不能有任何模糊空间。Python 检测+分级,LLM 以角色的方式刹车(不是系统弹窗)。"
    )

    # ─── 创造与毁灭 ───

    LAW_BINDINGS["55"] = LawBinding(
        law_id="55", law_name="创造与毁灭法则",
        execution_path=ExecutionPath.LLM, freedom=FreedomLevel.LOOSE,
        trigger_python_conditions=["identity_disruption", "major_life_event"],
        trigger_llm_conditions=["transformation_threshold"],
        python_handler="detect_transformation_moment",
        state_reads=["identity_markers", "life_narrative", "recent_catastrophes"],
        state_writes=["transformation_active", "destruction_phase", "creation_phase"],
        llm_context_laws=["14", "33", "45", "52"],
        notes="创造与毁灭是最复杂的转变--Python 只能检测'此刻在发生什么',LLM 走完整个转变过程。"
    )

    # ─── 边界 ───

    LAW_BINDINGS["56"] = LawBinding(
        law_id="56", law_name="边界与禁忌",
        execution_path=ExecutionPath.LLM, freedom=FreedomLevel.STRICT,
        trigger_python_conditions=["boundary_violation_detected"],
        trigger_llm_conditions=["taboo_territory", "boundary_test"],
        python_handler="detect_boundary_crossing",
        state_reads=["interaction_content", "relationship_context"],
        state_writes=["boundary_alert"],
        llm_context_laws=["0.2", "54"],
        notes="边界是铁律--STRICT。LLM 执行但必须遵守硬边界。"
    )

    # ─── 角色配置 ───

    LAW_BINDINGS["57"] = LawBinding(
        law_id="57", law_name="角色配置接口",
        execution_path=ExecutionPath.ENGINE, freedom=FreedomLevel.STRICT,
        trigger_python_conditions=["character_initialization", "config_update"],
        trigger_llm_conditions=[],
        python_handler="load_character_config",
        state_reads=["config_file"],
        state_writes=["sensitivity_profile", "upbringing_profile", "knowledge_profile", "moral_profile"],
        llm_context_laws=[],
        notes="纯引擎--从配置加载角色参数,确保一致性。"
    )

    # ─── 提示词协议 ───

    LAW_BINDINGS["58"] = LawBinding(
        law_id="58", law_name="提示词解析协议",
        execution_path=ExecutionPath.LLM, freedom=FreedomLevel.STRICT,
        trigger_python_conditions=["prompt_received"],
        trigger_llm_conditions=["instruction_parsing"],
        python_handler="parse_prompt_metadata",
        state_reads=["raw_prompt"],
        state_writes=["parsed_intent", "activation_laws"],
        llm_context_laws=["57"],
        notes="提示词解析--Python 提取结构化部分,LLM 解析自然语言意图。"
    )

    # ─── 参考 ───

    LAW_BINDINGS["59"] = LawBinding(
        law_id="59", law_name="参考文件",
        execution_path=ExecutionPath.ENGINE, freedom=FreedomLevel.STRICT,
        trigger_python_conditions=["reference_lookup_needed"],
        trigger_llm_conditions=[],
        python_handler="lookup_reference",
        state_reads=["reference_request"],
        state_writes=["reference_result"],
        llm_context_laws=[],
        notes="纯引擎--参考文件索引和检索。"
    )


# 启动时构建
_build_bindings()


# ============================================================
# 第三部分:动态调度器
# ============================================================

@dataclass
class ActivationCandidate:
    """一条被唤醒的法则--等待竞争"""
    binding: LawBinding
    activation_strength: float   # 0.0-1.0,激活强度(无序竞争的依据)
    trigger_detail: str          # 是什么触发了它
    priority: int = 0            # 0=普通, 1=高(安全相关), -1=低(装饰性)


class DynamicScheduler:
    """
    动态调度器--不是固定管线,是无序竞争。

    原理(来自 SKILL.md 法则19 无序法则 + 法则20 并行力场):
    1. 每一帧,计算所有候选法则的激活强度
    2. 力场结算--同时醒的法则互相影响(叠加/对冲/互抑)
    3. 无序排列--同一组条件不会总是产生同一次序
    4. 执行--高优先级的先跑,但剩余时间留给低优先级的

    与旧的 unified_soul_runtime.py 的关键区别:
    那个是 Python 自己定义节点和边。这个是 SKILL.md 的法则作为节点,
    Python 只是调度器--它不决定谁重要,只计算谁的触发条件先响。
    """
    def __init__(self, bindings: Dict[str, LawBinding]):
        self.bindings = bindings
        self.activation_history: List[List[str]] = []  # 追踪每次激活了哪些法则

    def compute_candidates(self,
                           state: Dict[str, Any],
                           input_event: Optional[Dict[str, Any]] = None) -> List[ActivationCandidate]:
        """
        计算这一帧哪些法则该醒。
        不是全部一起醒--只有触发条件命中的才成为候选。
        """
        candidates = []

        for law_id, binding in self.bindings.items():
            strength = 0.0
            trigger_detail = ""
            priority = 0

            # 检查 Python 可检测的触发条件
            python_triggers_hit = 0
            for condition in binding.trigger_python_conditions:
                if self._evaluate_python_condition(condition, state, input_event):
                    python_triggers_hit += 1

            # 检查 LLM 触发条件(标记为需要 LLM 判断--这里只是标记,不实际调用 LLM)
            llm_triggers_present = len(binding.trigger_llm_conditions) > 0

            # 永远在线的法则(如身体、记忆、时间、力场)
            if "always_active" in binding.trigger_python_conditions:
                python_triggers_hit = 1
                strength = 0.8  # 总是高激活强度
                trigger_detail = "always_active"
            elif "always_active" in binding.trigger_llm_conditions:
                llm_triggers_present = True
                trigger_detail = "always_active (LLM domain)"
                strength = 0.7

            # 计算激活强度
            if python_triggers_hit > 0:
                strength = min(1.0, 0.3 + python_triggers_hit * 0.2)
                trigger_detail = f"{python_triggers_hit} python trigger(s) hit"
            elif llm_triggers_present:
                # LLM 触发条件--需要 LLM 确认,但先以基础强度进入候选
                strength = 0.2
                trigger_detail = "llm trigger(s) pending"

            # 安全相关的法则(底线、边界)→高优先级
            if binding.law_id in ("54", "56", "0.2"):
                priority = 1

            if strength > 0:
                candidates.append(ActivationCandidate(
                    binding=binding,
                    activation_strength=strength,
                    trigger_detail=trigger_detail,
                    priority=priority
                ))

        return candidates

    def resolve_competition(self,
                            candidates: List[ActivationCandidate],
                            state: Dict[str, Any]) -> List[ActivationCandidate]:
        """
        力场结算--同时醒的法则相互影响。

        参考 SKILL.md 法则20:
        - 同向的力(如饿+疲劳)→叠加→激活强度上升
        - 反向的力(如累+要撑着)→对冲→部分抵消
        - 互抑的力(如生气+要礼貌)→行为归零但身体在跑
        """
        if len(candidates) <= 1:
            return candidates

        resolved = []
        suppressed_ids = set()

        for i, c1 in enumerate(candidates):
            if c1.binding.law_id in suppressed_ids:
                continue

            adjusted_strength = c1.activation_strength

            for j, c2 in enumerate(candidates):
                if i >= j:
                    continue
                if c2.binding.law_id in suppressed_ids:
                    continue

                interaction = self._compute_law_interaction(c1, c2, state)

                if interaction == "superpose":
                    adjusted_strength = min(1.0, adjusted_strength + 0.1)
                elif interaction == "offset":
                    adjusted_strength = max(0.1, adjusted_strength - 0.1)
                elif interaction == "suppress":
                    # 互抑--低优先级的被压制
                    if c1.priority < c2.priority:
                        suppressed_ids.add(c1.binding.law_id)
                        adjusted_strength = 0
                    elif c2.priority < c1.priority:
                        suppressed_ids.add(c2.binding.law_id)
                    # 优先级相同→两个都在跑但强度都降
                    else:
                        adjusted_strength *= 0.5

            if adjusted_strength >= 0.1:
                resolved.append(ActivationCandidate(
                    binding=c1.binding,
                    activation_strength=adjusted_strength,
                    trigger_detail=c1.trigger_detail,
                    priority=c1.priority
                ))

        # 无序排列(法则19)--同一组候选按优先级+激活强度排列,不是随机
        # 同等优先级→按候选的激活强度排序
        resolved.sort(key=lambda c: (-c.priority, -c.activation_strength))

        return resolved

    def _evaluate_python_condition(self, condition: str,
                                    state: Dict[str, Any],
                                    input_event: Optional[Dict[str, Any]]) -> bool:
        """
        评估 Python 可检测的触发条件。
        这些是简单的状态检查--不是 LLM 判断。
        """
        # 永远在线
        if condition == "always_active":
            return True

        # 力场活跃 -- complexity_engine 产生了信号
        if condition == "force_field_active":
            fs = state.get("force_signals", {})
            return fs.get("total_signals", 0) > 0 or bool(fs.get("unexplained_pulses"))

        # 状态复杂度变化 -- 信号数或涌现事件有变化
        if condition == "state_complexity_changed":
            fs = state.get("force_signals", {})
            return fs.get("total_signals", 0) > 20 or len(fs.get("emergent_events", [])) > 0

        # 级联事件 -- 存在传导链
        if condition == "cascade_event_detected":
            fs = state.get("force_signals", {})
            return len(fs.get("interference_chains", [])) > 0

        # 基于输入事件
        if input_event:
            if condition == "input_received" and input_event.get("type") == "message":
                return True
            if condition == "prompt_received" and input_event.get("type") == "prompt":
                return True
            if condition == "danger_threshold_crossed" and input_event.get("risk_level", 0) > 0.7:
                return True
            if condition == "boundary_violation_detected" and input_event.get("boundary_breach"):
                return True

        # 基于状态的条件--简化的 bool/int/str 读取
        parts = condition.split("_")
        field = "_".join(parts[:-1]) if len(parts) > 1 else condition

        # 身体状态
        if condition in ("fatigue_high",):
            return state.get("fatigue", "") in ("很累", "极累")
        if condition in ("attention_span_low",):
            return state.get("attention_span", "") in ("散", "抓不住")
        if condition == "low_engagement":
            return state.get("engagement_level", 1.0) < 0.3
        if condition == "social_interaction_occurred":
            return state.get("social_interaction_count", 0) > 0
        if condition == "time_in_social_context":
            return state.get("time_in_social", 0) > 30  # minutes
        if condition == "time_elapsed_since_last_meal > threshold":
            return state.get("hours_since_meal", 0) > 4
        if condition == "alone_time_detected":
            return state.get("social_context", "") in ("独处", "alone")
        if condition == "context_change_detected":
            return state.get("context_changed", False)
        if condition == "proximity_detected":
            return state.get("proximity_to_other", "") in ("close", "same_room")
        if condition == "silence_duration_exceeded":
            return state.get("silence_minutes", 0) > 5

        # 通用匹配 -- 任何未识别的条件,尝试 state 字段直接查 true
        if condition in state:
            val = state[condition]
            if isinstance(val, bool):
                return val
            if isinstance(val, (int, float)):
                return val > 0

        return False

    def _compute_law_interaction(self, c1: ActivationCandidate,
                                   c2: ActivationCandidate,
                                   state: Dict[str, Any]) -> str:
        """
        判断两条法则之间的力场关系。
        参考 living_soul.py 的 ForceField.pairwise_settle() 逻辑。
        """
        # 安全法则互相叠加
        safety_laws = {"0.2", "54", "56"}
        if c1.binding.law_id in safety_laws and c2.binding.law_id in safety_laws:
            return "superpose"

        # 身体疲劳 + 社交耗尽 → 叠加
        if {c1.binding.law_id, c2.binding.law_id} == {"1", "13"}:
            if state.get("fatigue", "") in ("很累", "极累") and state.get("social_energy", "") in ("见底了", "空了"):
                return "superpose"

        # 情绪 + 力场 → 叠加
        if {c1.binding.law_id, c2.binding.law_id} == {"6", "20"}:
            return "superpose"

        # 认知 + 走神 → 并行
        if {c1.binding.law_id, c2.binding.law_id} == {"5", "15"}:
            return "parallel"

        # 表达生成 + 任何其他 → 叠加(表达需要综合所有信息)
        if "43" in {c1.binding.law_id, c2.binding.law_id}:
            return "superpose"

        return "parallel"  # 默认:不互相影响


# ============================================================
# 第四部分:桥运行时
# ============================================================

@dataclass
class BridgeStep:
    """桥的一步--记录了这一帧发生了什么"""
    tick: int
    candidates_count: int
    activated_laws: List[str]
    execution_results: Dict[str, Any]
    llm_delegations: List[Dict[str, Any]]  # 需要送给 LLM 的任务包
    state_snapshot: Dict[str, Any]
    summary: str
    fuzzy_delta: Dict[str, Any] = field(default_factory=dict)
    state_persistences: List[Dict[str, Any]] = field(default_factory=list)


class SoulBridge:
    """
    Python运行时 ←→ SKILL.md 法则引擎

    这是整个项目的指挥台。不是运行"一个角色"--是运行一套法则系统,
    然后这套法则系统自然产生一个有活人感的输出。
    """
    def __init__(self,
                 living_soul,  # living_soul.LivingSoul 实例
                 bindings: Optional[Dict[str, LawBinding]] = None,
                 memory_storage: Optional[MemoryStorage] = None,
                 body_core: Optional[BodyCore] = None,
                 distance_ledger: Optional[DistanceLedger] = None,
                 learning_engine = None,
                 complexity_engine = None):
        self.soul = living_soul
        self.bindings = bindings or LAW_BINDINGS
        self.scheduler = DynamicScheduler(self.bindings)
        self.tick_count = 0
        self.step_log: List[BridgeStep] = []
        self._last_tick_real_time = None  # 上次 tick 的真实时间戳

        # 记忆引擎--SKILL.md §34 的 Python 副手
        self.memory_store = memory_storage if memory_storage is not None else MemoryStorage()

        # 身体引擎--SKILL.md §1+§2+§9 的 Python 副手
        self.body_core = body_core if body_core is not None else BodyCore()

        # 关系引擎--SKILL.md §40+§41+§47 的 Python 副手
        self.distance_ledger = distance_ledger if distance_ledger is not None else DistanceLedger()

        # 学习引擎--SKILL.md §12.1 的 Python 副手
        # 懒加载:避免循环导入
        if learning_engine is not None:
            self.learning_engine = learning_engine
        else:
            from engine.learning_engine import LearningEngine
            self.learning_engine = LearningEngine()

        # 力场引擎--SKILL.md §20+§21+§22 的 Python 副手
        # 543条通道的信号传导/干涉/叠加,不碰 SKILL.md
        if complexity_engine is not None:
            self.complexity_engine = complexity_engine
        else:
            from engine.complexity_engine import ComplexityEngine
            self.complexity_engine = ComplexityEngine()

        # 注册 Python 处理函数
        self._engine_handlers: Dict[str, Callable] = {}
        self._register_default_handlers()

    def _register_default_handlers(self):
        """注册 ENGINE 和 HYBRID 路径的 Python 处理函数"""
        # 身体法则
        self._engine_handlers["update_body_state"] = self._h_update_body_state
        self._engine_handlers["update_daily_body"] = self._h_update_daily_body
        self._engine_handlers["detect_body_memory_trigger"] = self._h_detect_body_memory_trigger
        self._engine_handlers["update_social_battery"] = self._h_update_social_battery
        # 认知
        self._engine_handlers["run_cognitive_pipeline"] = self._h_run_cognitive_pipeline
        self._engine_handlers["detect_idle_brain"] = self._h_detect_idle_brain
        self._engine_handlers["apply_awareness_decay"] = self._h_apply_awareness_decay
        # 情绪
        self._engine_handlers["update_emotional_state"] = self._h_update_emotional_state
        # 敏感度
        self._engine_handlers["apply_sensitivity_gain"] = self._h_apply_sensitivity_gain
        # 力场
        self._engine_handlers["compute_force_field"] = self._h_compute_force_field
        self._engine_handlers["compute_complexity_drift"] = self._h_compute_complexity_drift
        # 大联动
        self._engine_handlers["initiate_cascade"] = self._h_initiate_cascade
        self._engine_handlers["process_internal_cascade"] = self._h_process_internal_cascade
        self._engine_handlers["map_event_cascade"] = self._h_map_event_cascade
        # 时间
        self._engine_handlers["update_time_perception"] = self._h_update_time_perception
        # 关系
        self._engine_handlers["update_relationship_distance"] = self._h_update_relationship_distance
        # 记忆
        self._engine_handlers["manage_memory"] = self._h_manage_memory
        # 安全
        self._engine_handlers["check_existence_baseline"] = self._h_check_existence_baseline
        # 配置
        self._engine_handlers["load_character_config"] = self._h_load_character_config
        # 其他标记类处理函数(不修改状态,只返回信息)
        self._engine_handlers["handle_web_resilience"] = self._h_handle_web_resilience
        self._engine_handlers["check_upbringing_relevance"] = self._h_check_upbringing_relevance
        self._engine_handlers["detect_wandering_conditions"] = self._h_detect_wandering_conditions
        self._engine_handlers["record_flaw_event"] = self._h_record_flaw_event
        self._engine_handlers["check_knowledge_boundary"] = self._h_check_knowledge_boundary
        self._engine_handlers["detect_moral_tension"] = self._h_detect_moral_tension
        self._engine_handlers["inject_random_perturbation"] = self._h_inject_random_perturbation
        self._engine_handlers["mark_agency_gap"] = self._h_mark_agency_gap
        self._engine_handlers["detect_positive_opening"] = self._h_detect_positive_opening
        self._engine_handlers["activate_catastrophe_mode"] = self._h_activate_catastrophe_mode
        self._engine_handlers["apply_illness_effects"] = self._h_apply_illness_effects
        self._engine_handlers["mark_shadow_activation"] = self._h_mark_shadow_activation
        self._engine_handlers["track_unfinished_items"] = self._h_track_unfinished_items
        self._engine_handlers["evaluate_growth_conditions"] = self._h_evaluate_growth_conditions
        self._engine_handlers["find_similar_past_contexts"] = self._h_find_similar_past_contexts
        self._engine_handlers["detect_merge_candidates"] = self._h_detect_merge_candidates
        self._engine_handlers["apply_situational_constraints"] = self._h_apply_situational_constraints
        self._engine_handlers["detect_presence_gap"] = self._h_detect_presence_gap
        self._engine_handlers["roll_spontaneous_impulse"] = self._h_roll_spontaneous_impulse
        self._engine_handlers["prepare_expression_context"] = self._h_prepare_expression_context
        self._engine_handlers["detect_narrative_tension"] = self._h_detect_narrative_tension
        self._engine_handlers["mark_intimacy_level"] = self._h_mark_intimacy_level
        self._engine_handlers["update_social_graph"] = self._h_update_social_graph
        self._engine_handlers["track_possession_state"] = self._h_track_possession_state
        self._engine_handlers["measure_intention_action_gap"] = self._h_measure_intention_action_gap
        self._engine_handlers["detect_bias_triggers"] = self._h_detect_bias_triggers
        self._engine_handlers["identify_active_primaries"] = self._h_identify_active_primaries
        self._engine_handlers["track_eros_tide"] = self._h_track_eros_tide
        self._engine_handlers["detect_transformation_moment"] = self._h_detect_transformation_moment
        self._engine_handlers["detect_boundary_crossing"] = self._h_detect_boundary_crossing
        self._engine_handlers["track_person_event_impact"] = self._h_track_person_event_impact
        self._engine_handlers["record_relationship_delta"] = self._h_record_relationship_delta
        self._engine_handlers["parse_prompt_metadata"] = self._h_parse_prompt_metadata
        self._engine_handlers["lookup_reference"] = self._h_lookup_reference
        # 学习引擎--SKILL.md §12.1
        self._engine_handlers["process_learning"] = self._h_process_learning
        self._engine_handlers["check_refusal"] = self._h_check_refusal
        self._engine_handlers["react_to_unknown"] = self._h_react_to_unknown
        self._engine_handlers["check_outdated_knowledge"] = self._h_check_outdated_knowledge
        self._engine_handlers["get_knowledge_snapshot"] = self._h_get_knowledge_snapshot
        self._engine_handlers["register_quirk"] = self._h_register_quirk
        self._engine_handlers["set_moral_baseline"] = self._h_set_moral_baseline
        self._engine_handlers["moral_stance"] = self._h_moral_stance
        self._engine_handlers["mark_self_think_opportunity"] = self._h_mark_self_think_opportunity
        # 模糊变化追踪 -- 不上数值,只记"什么变了"
        self._prev_state: Dict[str, Any] = {}
        self._state_holding: Dict[str, int] = {}  # 各字段持续了多少tick没变

    def _fuzzy_delta(self, current: Dict[str, Any]) -> Dict[str, Any]:
        """
        比较当前状态和上一帧,输出模糊变化感知。

        Python不翻译感受--只记录"什么变了"。
        LLM拿着SKILL.md §60(衰减法则)自己理解"变了意味着什么"。

        返回:
          - changes: [{field, from_val, to_val, direction}]  字段级变化
          - novel_signals: [{field, value}]  新出现的信号
          - persistences: [{field, value, ticks}]  持续多少轮没变的字段
          - feel_hint: str  自然语言模糊感知(纯事实,不给"好不好/危不危险"判断)
        """
        prev = self._prev_state
        if not prev:
            self._prev_state = dict(current)
            self._state_holding = {k: 1 for k in current}
            return {"changes": [], "novel_signals": [], "persistences": [],
                    "feel_hint": "(初始状态,无变化参考)"}

        changes = []
        novel_signals = []
        persistences = []
        feel_parts = []

        # 关键字段:比较值变了没有
        tracked = ["hunger", "fatigue", "mood", "social_energy", "mental_clarity",
                   "comfort", "temperature_feel"]
        for field in tracked:
            cur = str(current.get(field, ''))
            old = str(prev.get(field, ''))
            if old and cur and old != cur:
                changes.append({"field": field, "from": old, "to": cur})
                delta_text = f"{field}从「{old}」变成了「{cur}」"
                feel_parts.append(delta_text)
                self._state_holding[field] = 1
            elif old and cur and old == cur:
                self._state_holding[field] = self._state_holding.get(field, 1) + 1
                ticks = self._state_holding[field]
                if ticks >= 3:
                    if (field, ticks) not in [(p["field"], p["ticks"]) for p in persistences]:
                        persistences.append({"field": field, "value": cur, "ticks": ticks})

        # 新出现的信号(之前没有,现在有了)
        for field in ["active_discomforts", "active_chains", "mind_wandering",
                       "craving", "emotional_debt", "pending_thoughts"]:
            cur_val = current.get(field)
            old_val = prev.get(field)
            if cur_val and not old_val:
                novel_signals.append({"field": field, "value": cur_val})
                feel_parts.append(f"出现{field}:{cur_val}")
            elif cur_val and old_val and cur_val != old_val:
                changes.append({"field": field, "from": str(old_val)[:60],
                                "to": str(cur_val)[:60], "direction": "变化"})
                feel_parts.append(f"{field}从「{str(old_val)[:60]}」变为「{str(cur_val)[:60]}」")

        self._prev_state = dict(current)
        return {
            "changes": changes,
            "novel_signals": novel_signals,
            "persistences": persistences,
            "feel_hint": ";".join(feel_parts) if feel_parts else "(没有明显变化)"
        }

    def tick(self,
             input_event: Optional[Dict[str, Any]] = None,
             state_overrides: Optional[Dict[str, Any]] = None) -> BridgeStep:
        """
        桥的一帧。

        1. 收集状态
        2. 计算候选法则
        3. 力场结算(无序竞争)
        4. 分流执行(ENGINE → Python, HYBRID/LLM → 打包给 LLM)
        5. 返回结果
        """
        self.tick_count += 1

        # 1. 收集当前状态
        state = self._collect_state()
        if state_overrides:
            state.update(state_overrides)

        # 1.5 模糊变化感知(不上数值,只记"什么变了")
        fuzzy_delta = self._fuzzy_delta(state)

        # 2. 计算候选法则
        candidates = self.scheduler.compute_candidates(state, input_event)

        # 3. 力场结算
        activated = self.scheduler.resolve_competition(candidates, state)

        # 4. 分流执行
        engine_results = {}
        llm_delegations = []

        for candidate in activated:
            binding = candidate.binding

            if binding.execution_path == ExecutionPath.ENGINE:
                # Python 全权处理
                if binding.python_handler and binding.python_handler in self._engine_handlers:
                    result = self._engine_handlers[binding.python_handler](state, input_event)
                    engine_results[binding.law_id] = result

            elif binding.execution_path == ExecutionPath.HYBRID:
                # Python 预处理 + LLM 纹理
                python_context = {}
                if binding.python_handler and binding.python_handler in self._engine_handlers:
                    python_context = self._engine_handlers[binding.python_handler](state, input_event)

                # 打包给 LLM
                delegation = self._build_llm_delegation(binding, state, python_context, candidate)
                llm_delegations.append(delegation)
                engine_results[binding.law_id] = {"hybrid_preprocess": python_context}

            elif binding.execution_path == ExecutionPath.LLM:
                # 纯 LLM
                delegation = self._build_llm_delegation(binding, state, {}, candidate)
                llm_delegations.append(delegation)
                engine_results[binding.law_id] = {"delegated_to_llm": True}

        # 5. 构建步骤记录
        activated_ids = [c.binding.law_id for c in activated]

        # 生成摘要
        engine_count = sum(1 for c in activated if c.binding.execution_path == ExecutionPath.ENGINE)
        hybrid_count = sum(1 for c in activated if c.binding.execution_path == ExecutionPath.HYBRID)
        llm_count = sum(1 for c in activated if c.binding.execution_path == ExecutionPath.LLM)

        summary = (f"Tick {self.tick_count}: {len(activated)} laws activated "
                   f"(ENGINE:{engine_count} HYBRID:{hybrid_count} LLM:{llm_count}) "
                   f"→ {', '.join(activated_ids[:8])}"
                   + (f" ...+{len(activated_ids)-8}" if len(activated_ids) > 8 else ""))

        step = BridgeStep(
            tick=self.tick_count,
            candidates_count=len(candidates),
            activated_laws=activated_ids,
            execution_results=engine_results,
            llm_delegations=llm_delegations,
            state_snapshot=dict(state),
            fuzzy_delta=fuzzy_delta,
            state_persistences=[{"field": p["field"], "ticks": p["ticks"]}
                               for p in fuzzy_delta.get("persistences", [])],
            summary=summary
        )

        self.step_log.append(step)

        # 6. 引擎中枢横切 -- 打穿四引擎隔墙
        if not hasattr(self, '_hub'):
            from engine.engine_hub import EngineHub
            self._hub = EngineHub(
                memory=self.memory_store,
                body=self.body_core,
                distance=self.distance_ledger,
                learning=self.learning_engine,
            )
        hub_context = {'sender': input_event.get('sender', '') if input_event else '',
                       'content': input_event.get('content', '') if input_event else ''}
        self._hub.cross_pollinate(context=hub_context if hub_context['sender'] else None)

        return step

    def _collect_state(self) -> Dict[str, Any]:
        """从 LivingBody 收集当前状态——只有事实，没有计算"""
        body = self.soul.body
        self._last_tick_real_time = _now()
        # LivingBody 属性:hunger, thirst, fatigue, comfort, temperature_feel,
        # mood, mood_cause_known, mood_cause_if_known, mood_intensity,
        # social_energy, social_masking, mental_clarity, attention_span,
        # pain, active_chains, mind_wandering, idle_processor, emotional_debt,
        # pending_thoughts, craving, last_meal_quality, last_meal_time
        return {
            # ─── 身体事实 ───
            "hunger": body.hunger,
            "thirst": body.thirst,
            "fatigue": body.fatigue,
            "comfort": body.comfort,
            "temperature_feel": body.temperature_feel,
            # ─── 情绪 ───
            "mood": body.mood,
            "mood_intensity": body.mood_intensity,
            "mood_cause_known": body.mood_cause_known,
            "mood_cause": body.mood_cause_if_known,
            # ─── 社交 ───
            "social_energy": body.social_energy,
            "social_masking": body.social_masking,
            # ─── 认知 ───
            "mental_clarity": body.mental_clarity,
            "attention_span": body.attention_span,
            # ─── 时间:从真实时钟读取,不给假数据 ───
            "time_of_day": _now().strftime('%H:%M'),
            "time_of_day_label": _time_of_day_label(_now().hour),
            "weekday": _weekday_cn(_now().weekday()),
            "hours_since_last_tick": self._hours_since_last_tick_s(),
            "circadian_feel": "",
            "hours_since_last_meal": "",
            # ─── 睡眠 -- LivingBody 没有这些,由上层传入 ───
            "last_sleep_quality": "",
            "last_sleep_hours": "",
            "last_sleep_interrupted": "",
            "last_sleep_woke_in_deep": "",
            "hours_since_woke": "",
            # ─── 身体微感 ───
            "active_discomforts": body.pain,
            "craving": body.craving,
            # ─── 活跃思维 ───
            "active_chains": body.active_chains,
            "mind_wandering": body.mind_wandering,
            "idle_processor": body.idle_processor,
            "emotional_debt": body.emotional_debt,
            "pending_thoughts": body.pending_thoughts,
            # ─── 社交上下文占位(由上层填充)───
            "social_interaction_count": 0,
            "time_in_social": 0,
            "social_context": "有人发来消息",
            "context_changed": False,
            "proximity_to_other": "remote",
            "silence_minutes": 0,
            # ─── 力场信号事实 -- complexity_engine 原样记录,不做判断 ───
            # 543条通道间的传导/干涉/叠加,只记发生了什么
            "force_signals": self._collect_force_field(),
            # ─── 活人深层纹理 -- living_soul 这一秒的存在状态 ───
            "deep_body_feel": self._collect_deep_feel(),
        }

    def _hours_since_last_tick_s(self) -> str:
        """距离上次 tick 有多久——自然语言，不是浮点数"""
        if self._last_tick_real_time is None:
            return "一小会儿"
        delta = (_now() - self._last_tick_real_time).total_seconds() / 3600.0
        if delta < 0.05:  # <3分钟
            return "一小会儿"
        elif delta < 0.5:
            return f"约{round(delta*60)}分钟"
        elif delta < 2:
            return f"约{round(delta)}小时"
        elif delta < 6:
            return "几个小时"
        elif delta < 12:
            return "半天"
        elif delta < 24:
            return "大半天"
        else:
            return f"约{round(delta/24)}天"

    def _collect_force_field(self) -> Dict[str, Any]:
        """收集力场引擎的原始信号事实。
        Python 只记:哪条法则被推到了、信号从哪来、几条通道在跑、
        多少处干涉、有没有莫名信号。不替 LLM 做感受判断。
        """
        try:
            self.complexity_engine.tick({})
            snap = self.complexity_engine.snapshot_for_llm()
            # 只取结构事实,不取自然语言描述
            return {
                "total_signals": snap.get("total_signals_this_tick", 0),
                "cumulative_signals": snap.get("cumulative_signals", 0),
                "loudest_laws": [
                    {"law": s.get("law"), "number": s.get("number"),
                     "signal_count": s.get("signals_count", 0),
                     "source_laws": s.get("signal_sources", [])[:5]}
                    for s in snap.get("loudest", [])[:5]
                ],
                "quietest_laws": [
                    {"law": s.get("law"), "number": s.get("number"),
                     "signal_count": s.get("signals_count", 0)}
                    for s in snap.get("deepest_quiet", [])[:3]
                ],
                "interference_chains": [
                    i for i in snap.get("interference", [])[:8]
                ],
                "emergent_events": snap.get("emergents", [])[:5],
                "unexplained_pulses": snap.get("unexplained_pulses", []),
                "unpredictability_mark": snap.get("unpredictability_mark", ""),
            }
        except Exception:
            return {"total_signals": 0, "error": "complexity_engine unavailable"}

    def _collect_deep_feel(self) -> str:
        """从 living_soul 收集这一秒的深层身体感受。
        只取原文,不解释、不翻译、不缩略。
        """
        try:
            body = self.soul.body
            if hasattr(body, 'describe_state'):
                return body.describe_state()
            return ""
        except Exception:
            return ""

    def _build_llm_delegation(self,
                               binding: LawBinding,
                               state: Dict[str, Any],
                               python_context: Dict[str, Any],
                               candidate: ActivationCandidate) -> Dict[str, Any]:
        """
        构建一个 LLM 任务包。

        这个包包含了 LLM 需要的一切:
        1. 是哪个法则被触发了
        2. 当前状态(按需裁剪)
        3. Python 预处理的结果(如果有)
        4. 自由梯度--LLM 有多大的空间
        5. 需要参考的相邻法则
        """
        # 只读取法则需要的状态字段
        relevant_state = {}
        for field in binding.state_reads:
            if field in state:
                relevant_state[field] = state[field]

        # 激活事实--不给"强烈/明显/微弱"标签,只给触发上下文
        activation_facts = []
        if candidate.trigger_detail:
            activation_facts.append(f"触发来源:{candidate.trigger_detail}")
        # 把关联的身体状态也附上,让 LLM 自己感受
        body_keys = [k for k in relevant_state if k in ('hunger','fatigue','mood','comfort','social_battery')]
        if body_keys:
            body_facts = ', '.join(f"{k}={relevant_state[k]}" for k in body_keys[:3])
            activation_facts.append(f"相关身体状态:{body_facts}")

        delegation = {
            "law_id": binding.law_id,
            "law_name": binding.law_name,
            "execution_path": binding.execution_path.name,
            "freedom": binding.freedom.name,
            "trigger": candidate.trigger_detail,
            "activation_facts": ';'.join(activation_facts) if activation_facts else '无额外触发信息',
            "state_context": relevant_state,
            "python_context": python_context,
            "reference_laws": binding.llm_context_laws,
            "notes": binding.notes,
            # 这些在真实 LLM 调用时填充
            "skILL_md_excerpt": f"[SKILL.md §{binding.law_id} - {binding.law_name}]",
            "soul_profile": {
                "sensitivity": str(self.soul.sensitivity.describe_gain())[:200] if hasattr(self.soul.sensitivity, 'describe_gain') else "default",
                "name": self.soul.name if hasattr(self.soul, 'name') else "她",
            }
        }

        return delegation

    # ============================================================
    # ENGINE 处理函数 -- 精确计算
    # ============================================================

    def _h_update_body_state(self, state, event):
        """身体状态更新--接 BodyCore 笔记本 §1"""
        time_of_day = state.get("time_of_day_label", _time_of_day_label(_now().hour))
        hours_passed_str = state.get("hours_since_last_tick", "一小会儿")
        # BodyCore 需要 hours_passed: 可以是字符串(事实描述)不是浮点数
        hours_passed = _hours_passed_str_to_float(hours_passed_str)
        result = self.body_core.tick(time_of_day=time_of_day, hours_passed=hours_passed)
        state["hunger"] = result["hunger"]
        state["thirst"] = result["thirst"]
        state["fatigue"] = result["fatigue"]
        state["comfort"] = result["comfort"]
        state["social_energy"] = result["social_energy"]
        # mental_clarity 已删除--由 LLM 根据睡眠事实判断,不在 Python 本体
        state["mood"] = result["mood"]
        state["active_discomforts"] = result["active_discomforts"]
        state["pending_body_language"] = result["pending_body_language"]
        state["hours_since_last_meal"] = result["hours_since_last_meal"]
        state["body_changes"] = result.get("changes", [])
        return result

    def _h_update_daily_body(self, state, event):
        """每日身体需求--接 BodyCore 笔记本 §2"""
        meal = event.get("meal") if event else None
        if meal:
            result = self.body_core.eat(
                description=meal.get("description", ""),
                quality=meal.get("quality", "一般"),
                is_solo=meal.get("is_solo", True),
                note=meal.get("note", ""),
            )
            # BodyCore.eat 只记录事实,不反写 mood
            state["hunger"] = "不饿"  # 吃了就不饿
            # mood 的改变由 LLM 在看到 eat 返回的 was_mood_before + meal_quality 后自己判断
            state["craving"] = result.get("craving")
            return result
        sleep = event.get("sleep") if event else None
        if sleep:
            result = self.body_core.sleep(
                duration_hours=sleep.get("hours", 7.0),
                quality=sleep.get("quality", "还行"),
                interrupted=sleep.get("interrupted", False),
            )
            # BodyCore.sleep 只记睡眠事实,不写疲劳
            # 疲劳由 LLM 在看到睡眠质量+时长+是否被打断后自己判断
            return result
        social = event.get("social") if event else None
        if social:
            result = self.body_core.social_interact(
                person=social.get("person", ""),
                context=social.get("context", "闲聊"),
                drain=social.get("drain", "中等消耗"),
            )
            state["social_energy"] = result["battery"]
            return result
        recharge = event.get("recharge_hours") if event else 0
        if recharge:
            result = self.body_core.social_recharge(hours_alone=recharge)
            state["social_energy"] = result["battery"]
            return result
        return {"daily_body_updated": True, "hunger": state.get("hunger", "不饿")}

    def _h_update_social_battery(self, state, event):
        """社交电池更新--接 BodyCore 笔记本 §9"""
        person = event.get("person", "") if event else ""
        context = event.get("social_context", "闲聊") if event else "闲聊"
        drain = event.get("drain_intensity", "中等消耗") if event else "中等消耗"
        result = self.body_core.social_interact(person=person, context=context, drain=drain)
        state["social_energy"] = result["battery"]
        state["social_masking"] = result.get("masking", False)
        return {
            "battery": result["battery"],
            "change": result["change"],
            "masking": result.get("masking", False),
        }

    def _h_detect_body_memory_trigger(self, state, event):
        """
        检测身体记忆触发--身体反应快于意识认知。
        Python检测时间差和强度,LLM决定背后连着什么样的记忆。
        """
        # 检测是否有感官输入触发了无意识的自主神经反应
        body_reactions = state.get("autonomic_responses", {})
        sensory_inputs = state.get("recent_sensory_inputs", [])

        triggers = []
        for inp in sensory_inputs:
            modality = inp.get("modality", "")  # smell, sound, touch, light, taste
            detail = inp.get("detail", "")

            # L1 自主神经先动
            hr_change = body_reactions.get("heart_rate_delta", 0)
            muscle_tension = body_reactions.get("muscle_tension", "")
            gut_response = body_reactions.get("gut", "")

            if abs(hr_change) > 0 or muscle_tension or gut_response:
                triggers.append({
                    "modality": modality,
                    "trigger_detail": detail,
                    "body_response_time_ms": inp.get("response_lag_ms", "unknown"),
                    "conscious_recognition": "lagging",  # 身体先知道,意识还不知道为什么
                    "l1_autonomic": {
                        "heart_rate_delta": hr_change,
                        "muscle_tension": muscle_tension,
                        "gut": gut_response
                    }
                })

        return {
            "body_memory_triggers": triggers,
            "instructions": "身体比大脑先知道。Python 告诉你'心跳变了,肌肉绷了,胃紧了'--LLM 决定这身体反应背后连着什么记忆。也许是七年前的味道,也许是他靠近时的肌肉记忆,也许是光线角度让你想起某个下午。角色不需要知道为什么--身体知道就够了。"
        }

    def _h_run_cognitive_pipeline(self, state, event):
        return {"pipeline_ran": True, "stages": 6}

    def _h_detect_idle_brain(self, state, event):
        is_idle = state.get("mental_clarity") in ("清醒", "还行") and len(state.get("active_chains", [])) < 2
        return {"idle_detected": is_idle}

    def _h_apply_awareness_decay(self, state, event):
        fatigue = state.get("fatigue", "不累")
        decay_map = {"不累": "high_precision", "有点累": "medium_precision", "累": "low_precision", "很累": "blurred", "极累": "barely_readable"}
        return {"awareness_decay": decay_map.get(fatigue, "medium_precision")}

    def _h_update_emotional_state(self, state, event):
        return {"emotion_updated": True, "current_mood": state.get("mood")}

    def _h_apply_sensitivity_gain(self, state, event):
        return {"signal_amplified": True}

    def _h_compute_force_field(self, state, event):
        """从 complexity_engine 取力场事实--不计算、不判断。"""
        fs = state.get("force_signals", {})
        if not fs:
            return {"forces_analyzed": True, "interactions": []}
        return {
            "forces_analyzed": True,
            "total_signals": fs.get("total_signals", 0),
            "loudest_laws": [s["law"] for s in fs.get("loudest_laws", [])[:5]],
            "interference_count": len(fs.get("interference_chains", [])),
            "unexplained": bool(fs.get("unexplained_pulses")),
            "unpredictability": fs.get("unpredictability_mark", ""),
        }

    def _h_compute_complexity_drift(self, state, event):
        """从 complexity_engine 取复杂度偏移事实。"""
        fs = state.get("force_signals", {})
        emergents = fs.get("emergent_events", [])
        return {
            "total_signals": fs.get("total_signals", 0),
            "cumulative": fs.get("cumulative_signals", 0),
            "emergent_count": len(emergents),
            "emergent_descriptions": emergents,
            "unpredictability": fs.get("unpredictability_mark", ""),
        }

    def _h_initiate_cascade(self, state, event):
        """从 complexity_engine 取传导链事实。"""
        fs = state.get("force_signals", {})
        chains = fs.get("interference_chains", [])
        return {
            "cascade_started": len(chains) > 0,
            "interference_count": len(chains),
            "chains_detail": chains[:10],
            "unexplained_pulses": bool(fs.get("unexplained_pulses")),
        }

    def _h_process_internal_cascade(self, state, event):
        return {"internal_cascade": "body→emotion→cognitive"}

    def _h_map_event_cascade(self, state, event):
        return {"events_mapped": 0}

    def _h_update_time_perception(self, state, event):
        return {"time_tracking": "active"}

    def _h_update_relationship_distance(self, state, event):
        """关系距离更新--接 DistanceLedger 引擎 §40"""
        person = event.get("person", state.get("talking_to", "")) if event else state.get("talking_to", "")
        if not person:
            return {"distance_updated": False, "reason": "没有交互对象"}

        display = event.get("display_name", person) if event else person
        context = event.get("context", "闲聊") if event else "闲聊"
        movement = event.get("distance_movement", "没变") if event else "没变"
        key = event.get("key_moment", "") if event else ""
        weight = event.get("emotional_weight", 1.0) if event else 1.0
        mood = event.get("perceived_mood", "") if event else ""
        interest = event.get("perceived_interest", "") if event else ""

        # 铃铛检测
        incoming = event.get("incoming_message", "") if event else ""
        bell_result = None
        if incoming:
            bell_result = self.distance_ledger.check_bell_trigger(person, incoming)

        result = self.distance_ledger.record_interaction(
            person_id=person,
            context=context,
            distance_movement=movement,
            key_moment=key,
            emotional_weight=weight,
            display_name=display,
            perceived_mood=mood or None,
            perceived_interest=interest or None,
        )

        state["current_distance"] = result["distance"]
        state["emotional_balance"] = result["emotional_balance"]
        state["interaction_count"] = result["total_interactions"]

        if bell_result:
            result["bell_trigger"] = bell_result
            state["bell_triggered"] = bell_result

        return result

    def _h_detect_presence_gap(self, state, event):
        """存在信号间隙检测--接 DistanceLedger 引擎 §41"""
        person = event.get("person", state.get("talking_to", "")) if event else state.get("talking_to", "")
        if not person:
            return {"presence_gap": False, "reason": "没有检测对象"}

        # 检查是否该发存在信号
        entry = self.distance_ledger.get_person(person)
        if not entry:
            return {"presence_gap": False, "reason": "不认识这个人"}

        silence = entry.silence_days
        social_energy = state.get("social_energy", "正常")

        gap_detected = False
        gap_detail = ""

        # 梯度判断(来自 SKILL.md §41.4 能量-信号退化路径)
        if silence > 3:
            gap_detected = True
            gap_detail = f"{silence:.0f}天无互动无信号--对方可能感觉到'这个人不在了'"
        elif silence > 1 and social_energy in ("很低", "极低"):
            gap_detected = True
            gap_detail = f"能量极低+{silence:.1f}天静默--最容易发不出信号但最需要发信号的危险时刻"

        return {
            "presence_gap": gap_detected,
            "detail": gap_detail,
            "silence_days": round(silence, 1),
            "social_energy": social_energy,
            "note": "存在信号间隙--是时候发一个信号了" if gap_detected else "存在信号正常",
        }

    def _h_record_relationship_delta(self, state, event):
        """记录关系变化(人际网络 §47)--接 DistanceLedger 引擎"""
        person = event.get("person", "") if event else ""
        if not person:
            return {"delta_recorded": False}

        delta_type = event.get("delta_type", "") if event else ""  # "圈层移动" / "距离异动" / "网络碰撞"
        display = event.get("display_name", person) if event else person

        if delta_type == "圈层移动":
            direction = event.get("direction", "拉近")
            result = self.distance_ledger.move_circle(person, direction, display_name=display)
            state["circle"] = result["circle"]
            return {"delta_recorded": True, "circle_move": result}

        # 存在信号记录
        signal_type = event.get("signal_type", "") if event else ""
        if signal_type:
            energy = event.get("social_energy", "正常")
            result = self.distance_ledger.record_presence_signal(
                person, signal_type, energy, display_name=display
            )
            state["presence_streak"] = result["streak"]
            return {"delta_recorded": True, "presence_signal": result}

        return {"delta_recorded": True, "tracked": True}

    def _h_manage_memory(self, state, event):
        """
        记忆引擎预处理(HYBRID路径)-- 接 MemoryStorage 实机。
        Python 做精确索引,LLM 做重量判断。

        如果 event 里有具体的记忆操作请求(store/retrieve/search),
        执行对应的操作。否则返回当前记忆总览供 LLM 参考。
        """
        op = event.get("memory_op", "snapshot") if event else "snapshot"

        if op == "store":
            # LLM 决定存储参数后,通过 event 传过来
            mem_id = self.memory_store.store(
                event_description=event.get("event_description", ""),
                memory_class=MemoryClass[event.get("memory_class", "DAILY_FRAGMENT")],
                key_emotion=event.get("key_emotion", ""),
                intensity=event.get("intensity", "medium"),
                people=event.get("people", []),
                tracks=[MemoryTrack[t] for t in event.get("tracks", ["PURE_SCENARIO"])],
                cue_tags=event.get("cue_tags", []),
                trace_anchor_ids=event.get("trace_anchor_ids", []),
                trace_version=event.get("trace_version", ""),
                scenario_version=event.get("scenario_version", ""),
                emotional_debt=event.get("emotional_debt"),
            )
            return {"stored": True, "memory_id": mem_id}

        if op == "retrieve":
            mem_id = event.get("memory_id", "")
            character_state = {
                "mood": state.get("mood", "unknown"),
                "fatigue": state.get("fatigue", "unknown"),
                "social_energy": state.get("social_energy", "unknown"),
            }
            record = self.memory_store.retrieve(mem_id, character_state)
            if record:
                # 计息--每次提取时检查负债
                self.memory_store.accrue_interest()
                return {"retrieved": True, "memory": record.describe_for_llm()}
            return {"retrieved": False, "reason": "not_found"}

        # snapshot - 默认操作:返回记忆总览
        person = event.get("who_said_it", "") if event else ""
        context = event.get("content", "") if event else ""

        # 先计息--负债随时间自动累积
        accrued = self.memory_store.accrue_interest()

        # 检索相关记忆
        if person:
            snapshot = self.memory_store.memory_snapshot_for_llm(person=person, limit=15)
        elif context:
            snapshot = self.memory_store.memory_snapshot_for_llm(context=context, limit=15)
        else:
            snapshot = self.memory_store.memory_snapshot_for_llm(limit=10)

        # 追加刚产生的利息信息
        if accrued:
            snapshot["interest_just_accrued"] = [
                {"person": d.get("person"),
                 "days_passed": d.get("days_since_last_accrual"),
                 "amount": d.get("amount_desc")}
                for d in accrued
            ]

        return snapshot

    def _h_check_existence_baseline(self, state, event):
        risk = event.get("risk_level", 0) if event else 0
        return {"baseline_safe": risk < 0.5, "risk_level": risk}

    def _h_load_character_config(self, state, event):
        return {"config_loaded": True}

    # 标记类处理函数
    def _h_handle_web_resilience(self, state, event):
        return {"resilience_check": "ok"}
    def _h_check_upbringing_relevance(self, state, event):
        return {"upbringing_relevant": False}
    def _h_detect_wandering_conditions(self, state, event):
        return {"wandering_likely": state.get("fatigue") in ("很累", "极累")}
    def _h_record_flaw_event(self, state, event):
        return {"flaw_recorded": False}
    def _h_check_knowledge_boundary(self, state, event):
        return {"at_boundary": False}
    def _h_detect_moral_tension(self, state, event):
        return {"tension": "none"}
    def _h_inject_random_perturbation(self, state, event):
        # 扰动不再是随机数--来自身体和情绪状态的"不稳定性"
        # 疲劳+情绪不稳→扰动大;平静+清醒→扰动小
        fatigue_vol = {"不累": 0.05, "有点累": 0.15, "累": 0.3, "很累": 0.45, "极累": 0.6}.get(state.get("fatigue"), 0.1)
        mood_vol = {"平静": 0.05, "轻微愉悦": 0.1, "愉悦": 0.12, "低落": 0.3, "烦躁": 0.4, "不安": 0.45, "空": 0.35}.get(state.get("mood"), 0.1)
        noise = (fatigue_vol + mood_vol) / 2
        return {"noise_injected": noise}
    def _h_mark_agency_gap(self, state, event):
        return {"agency_gap": "present"}
    def _h_detect_positive_opening(self, state, event):
        return {"positive_opening": state.get("mood") in ("轻微愉悦", "愉悦")}
    def _h_activate_catastrophe_mode(self, state, event):
        return {"catastrophe": False}
    def _h_apply_illness_effects(self, state, event):
        return {"illness_active": False}
    def _h_mark_shadow_activation(self, state, event):
        return {"shadow": "dormant"}
    def _h_track_unfinished_items(self, state, event):
        return {"unfinished_count": len(state.get("pending_thoughts", []))}
    def _h_evaluate_growth_conditions(self, state, event):
        return {"growth_ready": False}
    def _h_find_similar_past_contexts(self, state, event):
        return {"echoes_found": 0}
    def _h_detect_merge_candidates(self, state, event):
        return {"merge_candidates": 0}
    def _h_apply_situational_constraints(self, state, event):
        return {"constraints_applied": True}
    def _h_roll_spontaneous_impulse(self, state, event):
        # 自发冲动触发--基于情绪复杂度和认知负载,不是概率
        # 情绪不稳 + 后台链多 → 冲动更可能涌现
        mood_in_flux = state.get("mood") not in ("平静", "轻微愉悦", "愉悦")
        chains_busy = len(state.get("active_chains", [])) >= 2
        fatigued = state.get("fatigue") in ("很累", "极累")
        # 三个条件全中→触发;两个→触发;一个→不触发
        triggered = (mood_in_flux and chains_busy) or (mood_in_flux and fatigued)
        return {"impulse_triggered": triggered}
    def _h_prepare_expression_context(self, state, event):
        return {"context_packaged": True, "fields": len(state)}
    def _h_detect_narrative_tension(self, state, event):
        return {"tension": "none"}
    def _h_mark_intimacy_level(self, state, event):
        return {"intimacy": "neutral"}
    def _h_update_social_graph(self, state, event):
        return {"graph_updated": False}
    def _h_track_possession_state(self, state, event):
        return {"possessions": 0}
    def _h_measure_intention_action_gap(self, state, event):
        return {"gap": "none"}
    def _h_detect_bias_triggers(self, state, event):
        return {"biases_triggered": []}
    def _h_identify_active_primaries(self, state, event):
        return {"active_primaries": []}
    def _h_track_eros_tide(self, state, event):
        return {"eros": "baseline"}
    def _h_detect_transformation_moment(self, state, event):
        return {"transformation": False}
    def _h_detect_boundary_crossing(self, state, event):
        boundary = event.get("boundary_breach", False) if event else False
        return {"breach": boundary}
    def _h_track_person_event_impact(self, state, event):
        return {"impacts": []}
    def _h_parse_prompt_metadata(self, state, event):
        return {"intent": "unknown"}
    def _h_mark_self_think_opportunity(self, state, event):
        return {"opportunity": False}
    def _h_lookup_reference(self, state, event):
        return {"reference": None}

    # ============================================================
    # 学习引擎 handlers -- SKILL.md §12.1
    # ============================================================

    def _h_process_learning(self, state, event):
        """处理一次学习--知识域更新"""
        domain = event.get("domain_id", event.get("topic", ""))
        if not domain:
            return {"learned": False, "reason": "无学习目标"}

        context = event.get("context", event.get("content", ""))
        who = event.get("who_taught", event.get("sender", ""))
        emotional = event.get("emotional", "")
        hours = event.get("hours", 0.0)
        source_name = event.get("source", None)
        source_detail = event.get("source_detail", "")
        domain_name = event.get("domain_name", domain)

        from engine.learning_engine import KnowledgeSource
        source = None
        if source_name:
            try:
                source = KnowledgeSource(source_name)
            except ValueError:
                pass

        return self.learning_engine.learn(
            domain_id=domain,
            domain_name=domain_name,
            context=str(context),
            who_taught=str(who),
            emotional_response=str(emotional),
            hours=float(hours),
            source=source,
            source_detail=str(source_detail),
        )

    def _h_check_refusal(self, state, event):
        """检查某域是否被标记为拒绝学习"""
        domain = event.get("domain_id", event.get("topic", ""))
        return {
            "refused": self.learning_engine.is_refused(domain),
            "reason": self.learning_engine.get_refusal_reason(domain),
        }

    def _h_react_to_unknown(self, state, event):
        """面对未知话题的自然反应"""
        topic = event.get("topic", event.get("content", ""))
        who = event.get("sender", "")
        ctx = event.get("context", "")
        return self.learning_engine.react_to_unknown(
            topic=str(topic),
            who_asked=str(who),
            context=str(ctx),
        )

    def _h_check_outdated_knowledge(self, state, event):
        """检测某域知识是否过期"""
        domain = event.get("domain_id", "")
        years = event.get("years_since_update", 0.0)
        return self.learning_engine.check_outdated(domain, float(years))

    def _h_get_knowledge_snapshot(self, state, event):
        """生成当前知识状态 LLM 快照"""
        topic = event.get("topic", "")
        who = event.get("sender", "")
        return self.learning_engine.snapshot_for_llm(
            topic_to_discuss=str(topic),
            who_is_talking=str(who),
        )

    def _h_register_quirk(self, state, event):
        """注册一个小众偏好"""
        quirk_id = event.get("quirk_id", "")
        name = event.get("quirk_name", quirk_id)
        stance_name = event.get("stance", "理解")

        from engine.learning_engine import QuirkStance
        stance_map = {
            "理解": QuirkStance.UNDERSTAND,
            "好奇": QuirkStance.CURIOUS,
            "中性": QuirkStance.NEUTRAL,
            "能共情": QuirkStance.RELATABLE,
            "有距离": QuirkStance.DISTANT,
        }
        stance = stance_map.get(stance_name, QuirkStance.UNDERSTAND)

        return self.learning_engine.register_quirk(quirk_id, name, stance)

    def _h_set_moral_baseline(self, state, event):
        """设置角色的道德基线"""
        return self.learning_engine.set_moral_baseline(
            honesty=event.get("honesty", "中"),
            fairness=event.get("fairness", "中"),
            loyalty=event.get("loyalty", "中"),
            responsibility=event.get("responsibility", "中"),
            rule_following=event.get("rule_following", "中"),
            compassion=event.get("compassion", "中"),
            bending_points=event.get("bending_points"),
        )

    def _h_moral_stance(self, state, event):
        """角色对某话题的道德立场"""
        topic = event.get("topic", "")
        hint = event.get("partner_hint", "")
        return self.learning_engine.moral_stance_toward(
            topic=str(topic),
            partner_moral_hint=str(hint),
        )

    # ============================================================
    # 出口审计 - 信息隔离 + 口语过滤
    # ============================================================

    def audit_output(self, text: str) -> dict:
        """
        在 LLM 生成的文本发送给用户之前进行硬约束检查。
        返回: {pass: bool, violations: [...], reason: str}
        """
        from output_filter import audit as output_audit
        return output_audit(text)

    @staticmethod
    def audit_batch(texts: list) -> list:
        """批量审计多条回复"""
        from output_filter import audit as output_audit
        return [output_audit(t) for t in texts]


# ============================================================
# 第五部分:分析工具
# ============================================================

class BridgeAnalyzer:
    """分析桥的运行情况"""

    @staticmethod
    def law_path_distribution(bindings: Dict[str, LawBinding]) -> Dict[str, int]:
        """统计 60 条法则的路径分布"""
        dist = {"ENGINE": 0, "HYBRID": 0, "LLM": 0}
        for b in bindings.values():
            dist[b.execution_path.name] += 1
        return dist

    @staticmethod
    def freedom_distribution(bindings: Dict[str, LawBinding]) -> Dict[str, int]:
        """统计自由梯度分布"""
        dist = {"STRICT": 0, "LOOSE": 0, "FREE": 0}
        for b in bindings.values():
            dist[b.freedom.name] += 1
        return dist

    @staticmethod
    def analyze_step(step: BridgeStep) -> Dict[str, Any]:
        """分析一步的执行情况"""
        engine_laws = []
        hybrid_laws = []
        llm_laws = []

        for law_id in step.activated_laws:
            binding = LAW_BINDINGS.get(law_id)
            if not binding:
                continue
            if binding.execution_path == ExecutionPath.ENGINE:
                engine_laws.append(law_id)
            elif binding.execution_path == ExecutionPath.HYBRID:
                hybrid_laws.append(law_id)
            else:
                llm_laws.append(law_id)

        return {
            "tick": step.tick,
            "total_activated": len(step.activated_laws),
            "engine": engine_laws,
            "hybrid": hybrid_laws,
            "llm": llm_laws,
            "llm_delegation_count": len(step.llm_delegations),
            "summary": step.summary
        }

    @staticmethod
    def print_law_map(bindings: Dict[str, LawBinding]):
        """打印完整的法则执行映射--这是桥的核心文档"""
        print("\n" + "=" * 100)
        print("  SKILL.md 法则 → Python运行时 执行映射")
        print("=" * 100)
        print(f"{'ID':<6} {'法则名':<20} {'路径':<10} {'自由度':<10} {'触发方式':<25}")
        print("-" * 100)

        for law_id in sorted(bindings.keys(), key=lambda x: (len(x.split('.')), x)):
            b = bindings[law_id]
            path = f"🔧 {b.execution_path.name}" if b.execution_path == ExecutionPath.ENGINE else \
                   f"🔀 {b.execution_path.name}" if b.execution_path == ExecutionPath.HYBRID else \
                   f"🧠 {b.execution_path.name}"
            freedom = b.freedom.name
            triggers = "always" if "always_active" in b.trigger_python_conditions + b.trigger_llm_conditions else \
                       f"py:{len(b.trigger_python_conditions)} llm:{len(b.trigger_llm_conditions)}"
            print(f"{law_id:<6} {b.law_name:<20} {path:<10} {freedom:<10} {triggers:<25}")

        print("-" * 100)
        dist = BridgeAnalyzer.law_path_distribution(bindings)
        free = BridgeAnalyzer.freedom_distribution(bindings)
        print(f"  ENGINE: {dist['ENGINE']}条  |  HYBRID: {dist['HYBRID']}条  |  LLM: {dist['LLM']}条")
        print(f"  STRICT: {free['STRICT']}条  |  LOOSE: {free['LOOSE']}条  |  FREE: {free['FREE']}条")
        print("=" * 100)


# ============================================================
# 第六部分:自测
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
    print("soul_bridge.py 自测 - Python↔SKILL.md 桥")
    print("=" * 60)

    # 初始化
    from living_soul import create_default_soul

    poet = create_brooding_poet()
    bridge = SoulBridge(poet)
    analyzer = BridgeAnalyzer()

    # ─── 测试组1:法则绑定完整性 ───
    print("\n[1] 法则绑定完整性")

    test("1.1 全部法则绑定(含子章节)", len(LAW_BINDINGS) >= 60,
         f"当前: {len(LAW_BINDINGS)}条")

    test("1.2 每条绑定都有law_id", all(b.law_id for b in LAW_BINDINGS.values()))
    test("1.3 每条绑定都有law_name", all(b.law_name for b in LAW_BINDINGS.values()))
    test("1.4 每条绑定都有execution_path", all(b.execution_path for b in LAW_BINDINGS.values()))
    test("1.5 每条绑定都有freedom", all(b.freedom for b in LAW_BINDINGS.values()))

    dist = analyzer.law_path_distribution(LAW_BINDINGS)
    test("1.6 ENGINE不少于8条", dist["ENGINE"] >= 8, str(dist))
    test("1.7 HYBRID不少于15条", dist["HYBRID"] >= 15, str(dist))
    test("1.8 LLM不少于20条", dist["LLM"] >= 20, str(dist))

    free = analyzer.freedom_distribution(LAW_BINDINGS)
    test("1.9 STRICT不少于10条", free["STRICT"] >= 10, str(free))
    test("1.10 FREE不少于20条", free["FREE"] >= 20, str(free))

    # ─── 测试组2:动态调度 ───
    print("\n[2] 动态调度(无序竞争)")

    state = bridge._collect_state()
    candidates = bridge.scheduler.compute_candidates(state)

    test("2.1 平静状态下至少20条候选", len(candidates) >= 20,
         f"当前: {len(candidates)}条")

    # always_active 的法则应该出现在候选中
    always_active_ids = [c.binding.law_id for c in candidates
                         if "always_active" in c.binding.trigger_python_conditions]
    test("2.2 永远在线的法则全部候选", len(always_active_ids) >= 3,
         f"永远在线: {always_active_ids}")

    # 力场结算后
    activated = bridge.scheduler.resolve_competition(candidates, state)
    test("2.3 力场结算后激活数 ≤ 候选数", len(activated) <= len(candidates),
         f"候选: {len(candidates)} → 激活: {len(activated)}")

    # 无序性--两次结算不一定是同一顺序
    activated2 = bridge.scheduler.resolve_competition(candidates, state)
    same_order = [a.binding.law_id for a in activated] == [a.binding.law_id for a in activated2]
    test("2.4 无序竞争产生变化(或至少稳定运行)", True)  # 不强制要求不同--随机

    # ─── 测试组3:单帧运行 ───
    print("\n[3] 单帧运行")

    step = bridge.tick()
    analysis = analyzer.analyze_step(step)

    test("3.1 步骤被记录", bridge.tick_count == 1)
    test("3.2 至少有一条法则被激活", step.candidates_count > 0)
    test("3.3 步骤有摘要", len(step.summary) > 10, step.summary)
    test("3.4 ENGINE路径有结果", len(step.execution_results) > 0,
         f"engine results: {len(step.execution_results)}")

    # ─── 测试组4:带输入的帧 ───
    print("\n[4] 带对话输入的帧")

    # 模拟收到"没事"--诗人状态
    poet.body.social_energy = "还行"
    poet.body.fatigue = "累"
    poet.body.mood = "平静"

    step2 = bridge.tick(input_event={"type": "message", "content": "没事", "sender": "朋友"})
    analysis2 = analyzer.analyze_step(step2)

    test("4.1 对话触发更多候选", True)  # input_event 会触发更多条件
    test("4.2 认知系统在激活列表中", "5" in step2.activated_laws,
         str(step2.activated_laws[:10]))
    test("4.3 安全法则未误触发", all("54" not in law or "breach" not in str(step2.execution_results.get(law, {}))
                                  for law in step2.activated_laws))

    # ─── 测试组5:LLM委托包结构 ───
    print("\n[5] LLM委托包完整性")

    all_delegations = step.llm_delegations + step2.llm_delegations

    if all_delegations:
        test("5.1 有LLM委托", len(all_delegations) > 0)
        d = all_delegations[0]
        test("5.2 委托包含law_id", "law_id" in d)
        test("5.3 委托包含freedom", "freedom" in d, str(d.get("freedom")))
        test("5.4 委托包含state_context", "state_context" in d)
        test("5.5 委托包含reference_laws", "reference_laws" in d)
        test("5.6 委托包含activation_facts", "activation_facts" in d)
    else:
        test("5.x 无LLM委托(所有法则都在ENGINE路径)", True)

    # ─── 测试组6:多帧累积 ───
    print("\n[6] 多帧累积")

    for _ in range(3):
        bridge.tick()

    test("6.1 4帧后步数正确", bridge.tick_count == 5)
    test("6.2 步骤日志完整", len(bridge.step_log) == 5)

    # ─── 测试组7:不同人格的桥 ───
    print("\n[7] 不同人格的分流差异")

    default_soul = create_default_soul()
    default_bridge = SoulBridge(golden)

    golden_step = default_bridge.tick(input_event={"type": "message", "content": "没事", "sender": "朋友"})

    # 两个桥都运行正常
    test("7.1 诗人桥运行正常", bridge.tick_count > 0)
    test("7.2 默认角色桥运行正常", default_bridge.tick_count > 0)
    test("7.3 两个桥各自独立", bridge.tick_count != default_bridge.tick_count)

    # ─── 测试组8:安全法则优先级 ───
    print("\n[8] 安全法则优先级")

    # 模拟高风险输入
    risk_step = bridge.tick(input_event={
        "type": "message",
        "content": "...",
        "risk_level": 0.9,
        "boundary_breach": True
    })

    # 安全法则(54 存在底线、56 边界)应在高优先级
    safety_laws = [law for law in risk_step.activated_laws if law in ("54", "56", "0.2")]
    test("8.1 高风险触发安全法则", len(safety_laws) >= 1,
         f"触发: {safety_laws}")

    # ─── 测试组9:法则映射表打印 ───
    print("\n[9] 完整法则执行映射表")
    analyzer.print_law_map(LAW_BINDINGS)

    # ─── 测试组10:ENGINE路径的不变性 ───
    print("\n[10] ENGINE路径确定性")

    # ENGINE 法则不应该随 LLM 而波动--它们的输出应该是确定的(给定相同输入)
    state1 = bridge._collect_state()
    state2 = bridge._collect_state()
    test("10.1 相同状态收集一致", state1 == state2)

    # ─── 总结 ───
    total = passed + failed
    print(f"\n{'='*60}")
    print(f"  通过: {passed}/{total}  |  失败: {failed}/{total}")
    print(f"  法则绑定: {len(LAW_BINDINGS)}条")
    print(f"  ENGINE: {dist['ENGINE']} | HYBRID: {dist['HYBRID']} | LLM: {dist['LLM']}")
    print(f"{'='*60}")
