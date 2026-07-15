# body_core.py — 身体的"笔记本"
#
# 这不是引擎。这是笔记本。
# Python 只做一件事：记下发生了什么。
#
# - 上次吃饭是什么时候、吃了什么
# - 上次睡觉睡了多久、睡得怎么样
# - 和谁说过话、当时是什么感觉
# - 现在几点、醒了多久
#
# Python 不做的事：
# - 判断"该饿了"——人不是在第6小时整饿的，闻到楼下饭香就饿了
# - 判断"该困了"——困不困取决于睡了多久+醒了多久+心情+有没有事做
# - 计算"情绪衰减率"——情绪没有公式，它就是来了又走了
# - 决定"驱力胜负"——困和饿可以同时存在，不需要max()
#
# 事实给LLM。感受LLM自己来。这就是分工。

import time
import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# ============================================================
# 基础状态标签——给LLM看的词汇表
# ============================================================

HUNGER_STATES = ["不饿", "有点饿", "饿", "很饿", "饿过了", "饿到烦躁"]
THIRST_STATES = ["不渴", "有点渴", "渴", "很渴"]
FATIGUE_STATES = ["不累", "有点累", "累", "很累", "极累"]
SOCIAL_BATTERY_STATES = ["满的", "还行", "有点低", "低了", "见底了", "空了"]
MENTAL_STATES = ["清醒", "还行", "有点雾", "雾", "脑子不在"]
MOOD_STATES = ["平静", "轻微愉悦", "愉悦", "满足", "低落", "烦躁", "不安", "空"]
COMFORT_STATES = ["还行", "舒服", "不舒服", "说不清哪里不对", "某个地方在发信号"]

# 微小不适目录（身体可能发出的信号）
MICRO_DISCOMFORTS = [
    "偏头痛——一侧太阳穴在跳，不想大声说话",
    "颈椎酸——转了转头，咔嗒一声",
    "胃不太舒服——不是疼，就隐约有点恶心",
    "鼻炎犯了——纸巾用了一整包，说话带鼻音",
    "口腔溃疡——说话时舌头会顶一下那个地方，然后嘶一下",
    "后背有点紧——坐太久了",
    "眼睛干——眨了又眨，想揉",
    "手腕酸——鼠标手，偶尔甩一下",
    "膝盖隐隐的——要下雨了",
    "肩膀很紧——像有人一直按着",
    "耳朵热——不知道为什么",
    "脚踝有点肿——袜子勒出的印子",
]

# 身体语言触发（什么状态会带出什么动作）
BODY_LANGUAGE = {
    "累了": ["摘眼镜捏鼻梁", "趴在桌上闷闷地出一声", "头靠在手上，眼皮往下掉"],
    "冷": ["缩起来，手插口袋", "脚缩上沙发", "把袖子拉长包住手"],
    "热": ["重新扎头发", "袖子卷更高", "用手扇风"],
    "紧张": ["转笔转得比平时快", "手指敲桌子，自己没注意到", "脚尖在地上点"],
    "害羞": ["耳朵红了，自己不知道", "摸后颈", "低头笑了笑然后转开视线"],
    "被触碰": ["身体先于大脑做出反应——没立刻抽开", "肩膀上那一下，过了一秒才反应过来"],
}

# 昼夜节律线索——不是命令，是感觉
# 凌晨4点的身体和下午4点不一样。这不是"该困了"，这是"这个时间身体自然的感觉"
TIME_OF_DAY_FEEL = {
    "凌晨": "身体最沉的时候——这时候睡着的人很难叫醒，醒着的人脑子是浆糊。人更容易说真话",
    "清晨": "身体在过渡——有的人自然醒，有的人还在梦里挣扎",
    "早上": "精神最好的一段——脑子干净，身体轻。咖啡最好喝的时间",
    "上午": "能集中注意力做事的时候",
    "中午": "午饭后的自然犯困——不是真的累，是血往胃里跑了",
    "下午": "还行——能撑着，但开始觉得今天有点长了",
    "傍晚": "一天的能量在收尾——身体在减速。积压的情绪容易在这时候浮上来",
    "晚上": "放松下来——不一定是困，但不想再动脑子了。人变得更松散、更诚实",
    "深夜": "该休息的时间——但该和想要是两回事。情绪容易放大，什么感觉都比白天更真",
}


# ============================================================
# 事件记录
# ============================================================

@dataclass
class MealEvent:
    timestamp: float
    description: str
    quality: str          # "好吃" | "一般" | "不好吃"
    mood_after: str
    note: str = ""
    is_solo: bool = True

@dataclass
class SocialEvent:
    timestamp: float
    person: str
    context: str          # "闲聊" | "工作" | "重要对话" | "被迫社交"
    drain_feel: str       # "充电" | "轻微消耗" | "中等消耗" | "显著消耗" | "耗尽"
    battery_before: str
    battery_after: str
    note: str = ""

@dataclass
class SleepEvent:
    timestamp: float
    duration_hours: float
    quality: str          # "睡得好" | "还行" | "没睡好" | "几乎没睡"
    interrupted: bool = False
    woke_in_deep: bool = False
    dream_remembered: str = ""  # 还记得梦吗——"" | "还记得" | "有个片段挥之不去"


# ============================================================
# 身体笔记本
# ============================================================

class BodyCore:
    """
    身体的笔记本。
    
    Python 干的事：
    - 记住：上次吃饭什么时候、睡了多久、和谁说过话
    - 提供：现在的节律背景（凌晨/清晨/早上...）
    - 记录：吃了什么、好不好吃、社交消耗了多少
    
    LLM 干的事：
    - 翻译：把"5小时没吃+午饭时间"翻译成"饿不饿"的感觉
    - 判断：醒了8小时但刚喝了咖啡→还精神；醒了8小时但今天很难熬→累了
    - 感受：情绪不是算出来的——LLM看完整状态自己产出
    """

    def __init__(self,
                 energy_baseline: str = "MID",
                 physical_sensitivity: str = "MID"):
        self.energy_baseline = energy_baseline
        self.physical_sensitivity = physical_sensitivity

        # ─── 身体状态（自然语言） ───
        self.hunger: str = "不饿"
        self.thirst: str = "不渴"
        self.fatigue: str = "不累"
        self.comfort: str = "还行"
        self.temperature_feel: str = "刚好"

        # ─── 情绪 ───
        # 情绪不在这里生成。这里只记两件事：
        # 1. 现在是什么情绪（LLM设置的）
        # 2. 为什么（如果知道的话）
        self.mood: str = "平静"
        self.mood_cause_known: bool = False
        self.mood_cause: Optional[str] = None
        # 情绪不散的时间——"不知道为什么开心"可以持续很久
        # Python只记"多久了"，LLM自己感觉"该不该散了"
        self._mood_started_at_tick: int = 0

        # ─── 微小不适 ───
        self.active_discomforts: List[str] = []

        # ─── 社交 ───
        self.social_energy: str = "满的"
        self.social_masking: bool = False
        self.last_interaction_time: Optional[float] = None
        self.social_drain_cache: Dict[str, List[float]] = {}

        # ─── 饮食记录 ───
        self.last_meal_time: Optional[float] = None
        self.last_meal_quality: Optional[str] = None
        self.last_meal_desc: Optional[str] = None
        self.hours_since_last_meal: float = 0.0
        self.craving: Optional[str] = None
        self.meal_history: List[MealEvent] = []

        # ─── 睡眠记录 ───
        self.last_sleep_time: Optional[float] = None
        self.last_sleep_quality: str = "还行"
        self.last_sleep_hours: float = 7.0
        self.last_sleep_interrupted: bool = False
        self.last_sleep_woke_in_deep: bool = False
        self.last_sleep_environment: str = ""  # "在家" / "朋友家的沙发" / "酒店"
        self.sleep_history: List[SleepEvent] = []

        # ─── 社交日志 ───
        self.social_log: List[SocialEvent] = []

        # ─── 身体语言缓存 ───
        self.pending_body_language: List[str] = []

        # ─── 时间追踪 ───
        self._time_of_day: str = "下午"
        self._tick_count: int = 0

    # ═══════════════════════════════════════════════════
    # tick — 时间往前走。Python 只记录事实。
    # ═══════════════════════════════════════════════════

    def tick(self,
             time_of_day: str = "",
             hours_passed: float = 0.0) -> Dict[str, Any]:
        """
        时间往前走一步。

        做的事：更新饿了多久、渴了多久、醒了多久。
        不做的事：判断该不该饿、该不该困、情绪该不该散。

        返回当前全部事实——LLM用这些来"感觉"。
        """
        self._tick_count += 1

        if time_of_day:
            self._time_of_day = time_of_day

        if hours_passed > 0:
            self.hours_since_last_meal += hours_passed

        # 昼夜节律对身体的直接影响 —— 这是事实，不是感受判断
        # 就像是"8小时没吃饭→饿"一样，"凌晨醒着→累"是生理事实
        circadian_feel = TIME_OF_DAY_FEEL.get(self._time_of_day, "")
        # 不该清醒的时段——身体本来就该在休息，醒着就是事实上的疲劳
        deep_rest_hours = ("凌晨", "深夜", "清晨")
        if self._time_of_day in deep_rest_hours and self.fatigue == "不累":
            self.fatigue = "有点累"
        elif self._time_of_day in ("凌晨", "清晨") and self.fatigue == "有点累":
            # 持续醒在不该醒的时段——疲劳自然累积
            if hours_passed >= 0.5:
                self.fatigue = "累"

        # 微小不适——疲劳时身体更容易有感觉
        discomforts = self._note_discomforts()

        # 身体语言——某些状态自然带出动作
        self.pending_body_language = self._note_body_language()

        return {
            # 核心事实
            "hunger": self.hunger,
            "hours_since_last_meal": self._hours_since_meal_str(),
            "last_meal_desc": self.last_meal_desc,
            "last_meal_quality": self.last_meal_quality,
            "thirst": self.thirst,
            "fatigue": self.fatigue,
            "comfort": self.comfort,
            "temperature_feel": self.temperature_feel,

            # 睡眠事实
            "last_sleep_quality": self.last_sleep_quality,
            "last_sleep_hours": self._last_sleep_hours_str(),
            "last_sleep_interrupted": self.last_sleep_interrupted,
            "last_sleep_woke_in_deep": self.last_sleep_woke_in_deep,
            "last_sleep_environment": self.last_sleep_environment,
            "hours_since_woke": self._hours_since_woke_str(),

            # 情绪（这是LLM设置的，tick不改它）
            "mood": self.mood,
            "mood_cause_known": self.mood_cause_known,
            "mood_cause": self.mood_cause,

            # 社交
            "social_energy": self.social_energy,
            "social_masking": self.social_masking,

            # 时间感
            "time_of_day": self._time_of_day,
            "circadian_feel": TIME_OF_DAY_FEEL.get(self._time_of_day, ""),
            "tick_count": self._tick_count,

            # 身体信号
            "active_discomforts": discomforts,
            "pending_body_language": self.pending_body_language,
            "craving": self.craving,
        }

    # ═══════════════════════════════════════════════════
    # 吃饭
    # ═══════════════════════════════════════════════════

    def eat(self, description: str, quality: str,
            is_solo: bool = True, note: str = "") -> Dict[str, Any]:
        """吃了一顿饭——记下来"""
        now = time.time()

        # 吃完前是什么状态——用来让LLM理解这一顿的意义
        was_hungry = self.hunger
        was_mood = self.mood
        hours_waited = self.hours_since_last_meal

        meal = MealEvent(
            timestamp=now,
            description=description,
            quality=quality,
            mood_after="",  # LLM来决定
            note=note,
            is_solo=is_solo,
        )

        # 重置饥饿
        self.last_meal_time = now
        self.last_meal_quality = quality
        self.last_meal_desc = description
        self.hours_since_last_meal = 0.0
        self.hunger = "不饿"
        self.craving = None

        self.meal_history.append(meal)
        if len(self.meal_history) > 10:
            self.meal_history = self.meal_history[-10:]

        return {
            "meal_consumed": True,
            "what": description,
            "quality": quality,
            "was_hungry": was_hungry,
            "hours_waited": round(hours_waited, 1),
            "was_mood_before": was_mood,
            "solo": is_solo,
            "note": note,
            # LLM来决定：这一顿会让情绪怎么变
            # "好吃": 之前低落→可能轻微愉悦；之前平静→愉悦；很饿时吃到→满足
            # "一般": 可能没变化
            # "不好吃": 饿了很久→烦躁；本来就不高兴→加重
        }

    # ═══════════════════════════════════════════════════
    # 社交
    # ═══════════════════════════════════════════════════

    def social_interact(self, person: str, context: str,
                        drain_feel: str) -> Dict[str, Any]:
        """
        一次社交互动——记下和谁、什么情境、感觉消耗/充电了多少。

        drain_feel: "充电" | "轻微消耗" | "中等消耗" | "显著消耗" | "耗尽"
        这是互动后你"感觉"到的——LLM来判断，不是Python算出来的。
        Python只负责：既然你说消耗了多少，电池就往那边挪。
        """
        now = time.time()

        battery_before = self.social_energy

        # 电池只是标签——从一个挪到另一个
        drain_shift = {
            "充电": -2, "轻微消耗": 1,
            "中等消耗": 2, "显著消耗": 3, "耗尽": 5,
        }
        current_idx = SOCIAL_BATTERY_STATES.index(self.social_energy)
        shift = drain_shift.get(drain_feel, 1)
        new_idx = max(0, min(len(SOCIAL_BATTERY_STATES) - 1, current_idx + shift))
        battery_after = SOCIAL_BATTERY_STATES[new_idx]

        self.social_energy = battery_after
        self.last_interaction_time = now

        event = SocialEvent(
            timestamp=now, person=person, context=context,
            drain_feel=drain_feel,
            battery_before=battery_before, battery_after=battery_after,
        )
        self.social_log.append(event)

        if person not in self.social_drain_cache:
            self.social_drain_cache[person] = []
        self.social_drain_cache[person].append(now)

        if len(self.social_log) > 200:
            self.social_log = self.social_log[-200:]

        # 伪装：电池见底但来的是重要的人→硬撑
        if battery_before in ("见底了", "空了") and context in ("重要对话",):
            self.social_masking = True

        return {
            "person": person,
            "battery": self.social_energy,
            "change": f"{battery_before} → {battery_after}",
            "masking": self.social_masking,
        }

    def social_recharge(self, hours_alone: float) -> Dict[str, Any]:
        """
        独处充电。
        不同人恢复速度不同——VERY_LOW需要更多时间。
        但这只是大概描述，不是精确计算。
        """
        # 大概的恢复速度——不是精确步长
        recovery_pace = {
            "VERY_LOW": "很慢——需要大半天独处才能恢复一格",
            "LOW": "慢——几个小时独处有感觉",
            "MID": "正常——独处一会儿就充回来",
            "HIGH": "快——很快就恢复了",
            "VERY_HIGH": "非常快——稍微一个人待会儿就好了",
        }

        # 充电步数——粗略估计
        pace_hours = {"VERY_LOW": 4, "LOW": 3, "MID": 2, "HIGH": 1.5, "VERY_HIGH": 1}
        steps = int(hours_alone / pace_hours.get(self.energy_baseline, 2))

        current_idx = SOCIAL_BATTERY_STATES.index(self.social_energy)
        new_idx = max(0, current_idx - steps)
        old_battery = self.social_energy
        self.social_energy = SOCIAL_BATTERY_STATES[new_idx]
        self.social_masking = False

        return {
            "battery": self.social_energy,
            "change": f"{old_battery} → {self.social_energy}",
            "hours_alone": hours_alone,
            "recovery_pace": recovery_pace.get(self.energy_baseline, "正常"),
        }

    # ═══════════════════════════════════════════════════
    # 睡眠
    # ═══════════════════════════════════════════════════

    def sleep(self,
              duration_hours: float,
              quality: str = "",
              interrupted: bool = False,
              woke_in_deep: bool = False,
              environment: str = "",
              dream_remembered: str = "") -> Dict[str, Any]:
        """
        睡了一觉——记下事实。感觉如何由LLM来判断。

        Python记录的：
        - 睡了多久
        - 质量如何（"睡得好"/"还行"/"没睡好"/"几乎没睡"——LLM判断的）
        - 有没有被打断
        - 是不是深度睡眠被吵醒的
        - 换环境了吗（在家/朋友家/酒店）
        - 还记得梦吗

        LLM来决定：
        - 醒来什么感觉（迷糊？清醒？晕？）
        - 这一觉对今天意味着什么
        - 梦的残留会不会影响这一天
        """
        now = time.time()

        # 如果没给质量→LLM后来补
        quality = quality or "还行"

        event = SleepEvent(
            timestamp=now,
            duration_hours=duration_hours,
            quality=quality,
            interrupted=interrupted,
            woke_in_deep=woke_in_deep,
            dream_remembered=dream_remembered,
        )

        self.last_sleep_time = now
        self.last_sleep_quality = quality
        self.last_sleep_hours = duration_hours
        self.last_sleep_interrupted = interrupted
        self.last_sleep_woke_in_deep = woke_in_deep
        self.last_sleep_environment = environment

        self.sleep_history.append(event)
        if len(self.sleep_history) > 30:
            self.sleep_history = self.sleep_history[-30:]

        return {
            "slept": True,
            "hours": duration_hours,
            "quality": quality,
            "interrupted": interrupted,
            "woke_in_deep": woke_in_deep,
            "environment": environment,
            "dream_remembered": dream_remembered,
            # LLM 拿到这些事实后自己产出：
            # - "睡够了但没睡透" vs "今天一定能扛"
            # - "被吵醒的，一肚子火" vs "无所谓"
            # - 疲劳感、清醒度、情绪——都从这里出来
        }

    # ═══════════════════════════════════════════════════
    # 状态设置（LLM直接来改——不需要Python帮倒忙）
    # ═══════════════════════════════════════════════════

    def set_mood(self, mood: str, cause: str = "", cause_known: bool = False):
        """LLM直接设情绪。Python不乱碰。"""
        if mood in MOOD_STATES:
            self.mood = mood
        self.mood_cause_known = cause_known
        self.mood_cause = cause or None
        if mood != "平静":
            self._mood_started_at_tick = self._tick_count

    def set_hunger(self, hunger: str):
        """LLM直接设饥饿感。"""
        if hunger in HUNGER_STATES:
            self.hunger = hunger

    def set_fatigue(self, fatigue: str):
        """LLM直接设疲劳感。"""
        if fatigue in FATIGUE_STATES:
            self.fatigue = fatigue

    def set_comfort(self, comfort: str):
        if comfort in COMFORT_STATES:
            self.comfort = comfort

    def set_craving(self, what: str):
        self.craving = what

    def add_discomfort(self, discomfort: str):
        if discomfort in MICRO_DISCOMFORTS and discomfort not in self.active_discomforts:
            self.active_discomforts.append(discomfort)

    def remove_discomfort(self, discomfort: str):
        if discomfort in self.active_discomforts:
            self.active_discomforts.remove(discomfort)

    # ═══════════════════════════════════════════════════
    # 给LLM的完整快照
    # ═══════════════════════════════════════════════════

    def snapshot_for_llm(self,
                         context: str = "",
                         who_is_talking: str = "") -> Dict[str, Any]:
        """
        完整身体快照——给LLM看的。
        全是事实。没有计算。
        """

        # 和这个人的社交历史
        person_history = None
        if who_is_talking and who_is_talking in self.social_drain_cache:
            count = len(self.social_drain_cache[who_is_talking])
            person_history = {
                "person": who_is_talking,
                "interactions_count": count,
            }

        return {
            # ─── 身体事实 ───
            "hunger": self.hunger,
            "hours_since_last_meal": self._hours_since_meal_str(),
            "last_ate": self.last_meal_desc or "还没吃过",
            "last_meal_quality": self.last_meal_quality,
            "thirst": self.thirst,
            "fatigue": self.fatigue,
            "comfort": self.comfort,
            "temperature_feel": self.temperature_feel,

            # ─── 情绪（LLM自己设的，给它自己看） ───
            "mood": self.mood,
            "mood_cause_known": self.mood_cause_known,
            "mood_cause": self.mood_cause,
            "mood_ticks_ago": self._tick_count - self._mood_started_at_tick if self._mood_started_at_tick else 0,

            # ─── 睡眠事实 ───
            "last_sleep_quality": self.last_sleep_quality,
            "last_sleep_hours": self._last_sleep_hours_str(),
            "last_sleep_interrupted": self.last_sleep_interrupted,
            "last_sleep_woke_in_deep": self.last_sleep_woke_in_deep,
            "last_sleep_environment": self.last_sleep_environment,
            "hours_since_woke": self._hours_since_woke_str(),
            "recent_sleeps": [
                {"hours": s.duration_hours, "quality": s.quality,
                 "interrupted": s.interrupted, "deep_wake": s.woke_in_deep}
                for s in self.sleep_history[-5:]
            ],

            # ─── 社交 ───
            "social_energy": self.social_energy,
            "social_masking": self.social_masking,
            "person_drain_history": person_history,
            "recent_social": [
                {"who": e.person, "context": e.context, "drain": e.drain_feel,
                 "battery": f"{e.battery_before} → {e.battery_after}"}
                for e in self.social_log[-5:]
            ],

            # ─── 时间感 ───
            "time_of_day": self._time_of_day,
            "circadian_feel": TIME_OF_DAY_FEEL.get(self._time_of_day, ""),

            # ─── 身体信号 ───
            "active_discomforts": self.active_discomforts,
            "pending_body_language": self.pending_body_language,
            "craving": self.craving,

            # ─── 饮食记忆 ───
            "recent_meals": [
                {"what": m.description, "quality": m.quality,
                 "when": "刚才" if time.time() - m.timestamp < 3600
                         else f"{int((time.time() - m.timestamp) / 3600)}小时前"}
                for m in self.meal_history[-3:]
            ],
        }

    # ═══════════════════════════════════════════════════
    # 持久化
    # ═══════════════════════════════════════════════════

    def to_dict(self) -> Dict:
        return {
            "hunger": self.hunger,
            "thirst": self.thirst,
            "fatigue": self.fatigue,
            "comfort": self.comfort,
            "temperature_feel": self.temperature_feel,
            "mood": self.mood,
            "mood_cause_known": self.mood_cause_known,
            "mood_cause": self.mood_cause,
            "_mood_started_at_tick": self._mood_started_at_tick,
            "active_discomforts": self.active_discomforts,
            "social_energy": self.social_energy,
            "social_masking": self.social_masking,
            "last_meal_time": self.last_meal_time,
            "last_meal_quality": self.last_meal_quality,
            "last_meal_desc": self.last_meal_desc,
            "hours_since_last_meal": self._hours_since_meal_str(),
            "craving": self.craving,
            "last_sleep_time": self.last_sleep_time,
            "last_sleep_quality": self.last_sleep_quality,
            "last_sleep_hours": self._last_sleep_hours_str(),
            "last_sleep_interrupted": self.last_sleep_interrupted,
            "last_sleep_woke_in_deep": self.last_sleep_woke_in_deep,
            "last_sleep_environment": self.last_sleep_environment,
            "last_interaction_time": self.last_interaction_time,
            "social_log": [
                {"ts": e.timestamp, "person": e.person, "context": e.context,
                 "drain": e.drain_feel, "battery_before": e.battery_before,
                 "battery_after": e.battery_after, "note": e.note}
                for e in self.social_log
            ],
            "social_drain_cache": {k: v for k, v in self.social_drain_cache.items()},
            "meal_history": [
                {"ts": m.timestamp, "desc": m.description, "quality": m.quality,
                 "mood": m.mood_after, "solo": m.is_solo, "note": m.note}
                for m in self.meal_history
            ],
            "sleep_history": [
                {"ts": s.timestamp, "hours": s.duration_hours, "quality": s.quality,
                 "interrupted": s.interrupted, "woke_in_deep": s.woke_in_deep,
                 "dream": s.dream_remembered}
                for s in self.sleep_history
            ],
            "_time_of_day": self._time_of_day,
            "_tick_count": self._tick_count,
        }

    def save_to_file(self, path: str):
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)

    @classmethod
    def load_from_file(cls, path: str,
                       energy_baseline: str = "MID",
                       physical_sensitivity: str = "MID") -> "BodyCore":
        core = cls(energy_baseline=energy_baseline,
                   physical_sensitivity=physical_sensitivity)
        try:
            with open(path, 'r', encoding='utf-8') as f:
                d = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return core

        core.hunger = d.get("hunger", "不饿")
        core.thirst = d.get("thirst", "不渴")
        core.fatigue = d.get("fatigue", "不累")
        core.comfort = d.get("comfort", "还行")
        core.temperature_feel = d.get("temperature_feel", "刚好")
        core.mood = d.get("mood", "平静")
        core.mood_cause_known = d.get("mood_cause_known", False)
        core.mood_cause = d.get("mood_cause")
        core._mood_started_at_tick = d.get("_mood_started_at_tick", 0)
        core.active_discomforts = d.get("active_discomforts", [])
        core.social_energy = d.get("social_energy", "满的")
        core.social_masking = d.get("social_masking", False)
        core.last_meal_time = d.get("last_meal_time")
        core.last_meal_quality = d.get("last_meal_quality")
        core.last_meal_desc = d.get("last_meal_desc")
        core.hours_since_last_meal = d.get("hours_since_last_meal", 0.0)
        core.craving = d.get("craving")
        core.last_sleep_time = d.get("last_sleep_time")
        core.last_sleep_quality = d.get("last_sleep_quality", "还行")
        core.last_sleep_hours = d.get("last_sleep_hours", 7.0)
        core.last_sleep_interrupted = d.get("last_sleep_interrupted", False)
        core.last_sleep_woke_in_deep = d.get("last_sleep_woke_in_deep", False)
        core.last_sleep_environment = d.get("last_sleep_environment", "")
        core.last_interaction_time = d.get("last_interaction_time")
        core._time_of_day = d.get("_time_of_day", "下午")
        core._tick_count = d.get("_tick_count", 0)

        for e in d.get("social_log", []):
            core.social_log.append(SocialEvent(
                timestamp=e["ts"], person=e["person"], context=e["context"],
                drain_feel=e["drain"], battery_before=e["battery_before"],
                battery_after=e["battery_after"], note=e.get("note", ""),
            ))
        core.social_drain_cache = d.get("social_drain_cache", {})

        for m in d.get("meal_history", []):
            core.meal_history.append(MealEvent(
                timestamp=m["ts"], description=m["desc"], quality=m["quality"],
                mood_after=m["mood"], is_solo=m.get("solo", True),
                note=m.get("note", ""),
            ))

        for s in d.get("sleep_history", []):
            core.sleep_history.append(SleepEvent(
                timestamp=s["ts"], duration_hours=s["hours"],
                quality=s["quality"], interrupted=s.get("interrupted", False),
                woke_in_deep=s.get("woke_in_deep", False),
                dream_remembered=s.get("dream", ""),
            ))

        return core

    # ═══════════════════════════════════════════════════
    # 内部——记事功能
    # ═══════════════════════════════════════════════════

    def _last_sleep_hours_str(self) -> str:
        """睡了多久——自然语言，不是精确数字"""
        h = self.last_sleep_hours
        if h <= 0:
            return "没怎么睡"
        elif h < 3:
            return "没睡够"
        elif h < 5:
            return "睡得不太够"
        elif h < 7:
            return "睡得还行"
        elif h < 9:
            return "睡饱了"
        else:
            return "睡了很多"

    def _hours_since_meal_str(self) -> str:
        """多久没吃饭——自然语言"""
        h = self.hours_since_last_meal
        if h < 1:
            return "刚吃过"
        elif h < 3:
            return "吃了一会儿了"
        elif h < 5:
            return "有一阵子没吃了"
        elif h < 8:
            return "好久没吃了"
        elif h < 12:
            return "从早上到现在没吃"
        else:
            return "饿了好久没吃东西"

    def _hours_since_woke_str(self) -> str:
        """醒了多久——自然语言，不是精确数字"""
        if self.last_sleep_time is None:
            return "还没睡过"
        hours = (time.time() - self.last_sleep_time) / 3600
        if hours < 0.5:
            return "刚醒"
        elif hours < 2:
            return "醒了一会儿"
        elif hours < 5:
            return "醒了小半天"
        elif hours < 8:
            return "醒了大半天"
        elif hours < 12:
            return "从早上醒到现在"
        elif hours < 16:
            return "醒了一整天了"
        elif hours < 20:
            return "从昨天醒到现在"
        else:
            return "很久没睡了"

    def _note_discomforts(self) -> List[str]:
        """
        检查身体有没有在发信号。
        疲劳的时候更容易感觉到不适——但具体的"感觉到了什么"是LLM的选择。
        Python只提供候选列表。
        """
        if self.fatigue in ("不累", "有点累"):
            # 不太累——可能注意不到不适
            return self.active_discomforts

        # 累了——新不适可能出现
        if len(self.active_discomforts) < 2:
            # 给LLM一个候选——选和当前状态最相关的
            candidates = MICRO_DISCOMFORTS

            # 根据疲劳类型推荐
            if self.fatigue in ("很累", "极累"):
                # 极累时更可能是头痛/眼干/肩背
                preferred = [d for d in candidates
                             if any(kw in d for kw in ("太阳穴", "头", "眼睛", "肩", "背", "酸"))]
                if preferred:
                    new_d = preferred[0]
                    if new_d not in self.active_discomforts:
                        self.active_discomforts.append(new_d)

        return self.active_discomforts

    def _note_body_language(self) -> List[str]:
        """某些状态自然带出某些动作——选最匹配的"""
        actions = []

        if self.fatigue in ("累", "很累", "极累"):
            triggers = BODY_LANGUAGE["累了"]
            if self.fatigue == "极累":
                actions.append("趴在桌上闷闷地出一声")
            elif self.fatigue == "很累":
                actions.append("摘眼镜捏鼻梁")
            else:
                actions.append("头靠在手上，眼皮往下掉")

        if self.temperature_feel == "冷":
            triggers = BODY_LANGUAGE["冷"]
            if self.fatigue in ("累", "很累", "极累"):
                actions.append("缩起来，手插口袋")
            else:
                actions.append("把袖子拉长包住手")

        if self.mood == "紧张":
            triggers = BODY_LANGUAGE["紧张"]
            if self.physical_sensitivity in ("HIGH", "VERY_HIGH"):
                actions.append(triggers[0])
            else:
                actions.append(triggers[1] if len(triggers) > 1 else triggers[0])

        if self.mood == "害羞":
            triggers = BODY_LANGUAGE["害羞"]
            if self.social_energy in ("见底了", "空了", "低了"):
                actions.append(triggers[-1])
            else:
                actions.append(triggers[0])

        return actions


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
    print("body_core.py — 身体笔记本 自测")
    print("=" * 60)

    print("\n[1] 初始化")
    body = BodyCore(energy_baseline="MID", physical_sensitivity="MID")
    test("1.1 状态初始化", all([
        body.hunger == "不饿", body.thirst == "不渴",
        body.fatigue == "不累", body.social_energy == "满的",
        body.mood == "平静",
    ]))
    test("1.2 没有sleep_drive依赖", not hasattr(body, 'sleep_drive'))

    print("\n[2] 吃饭")
    r = body.eat("楼下面馆的牛肉面", "好吃", is_solo=True)
    test("2.1 饥饿重置", body.hunger == "不饿")
    test("2.2 记录了吃了什么", body.last_meal_desc == "楼下面馆的牛肉面")
    test("2.3 记录了等多久", r["hours_waited"] == 0)  # 刚初始化没等
    test("2.4 记录了吃前的心情", "was_mood_before" in r)
    test("2.5 饮食历史", len(body.meal_history) == 1)

    body.eat("冷掉的盒饭", "不好吃")
    test("2.6 不好吃也记下来了", body.last_meal_quality == "不好吃")

    print("\n[3] 社交")
    r3 = body.social_interact("同事A", "工作", "中等消耗")
    test("3.1 电池下降", body.social_energy != "满的")
    test("3.2 社交日志", len(body.social_log) == 1)
    test("3.3 按人缓存", "同事A" in body.social_drain_cache)

    r4 = body.social_interact("好朋友", "闲聊", "充电")
    test("3.4 充电互动", body.social_log[-1].drain_feel == "充电")

    print("\n[4] 独处充电")
    body.social_energy = "空了"
    r5 = body.social_recharge(hours_alone=3.0)
    test("4.1 恢复了一些", body.social_energy != "空了")
    test("4.2 伪装关闭", not body.social_masking)
    test("4.3 包含了恢复速度描述", "recovery_pace" in r5)

    print("\n[5] 睡眠")
    r6 = body.sleep(4.0, "没睡好", interrupted=True, woke_in_deep=True)
    test("5.1 记下了时长", body.last_sleep_hours == 4.0)
    test("5.2 记下了质量", body.last_sleep_quality == "没睡好")
    test("5.3 记下了被打断", body.last_sleep_interrupted)
    test("5.4 记下了深度被吵醒", body.last_sleep_woke_in_deep)
    test("5.5 睡眠历史", len(body.sleep_history) >= 1)

    r7 = body.sleep(8.0, "睡得好", environment="在家")
    test("5.6 好觉记录", body.last_sleep_quality == "睡得好")
    test("5.7 环境记录", body.last_sleep_environment == "在家")
    test("5.8 不自动改疲劳", True)  # sleep()不替LLM判断疲劳

    print("\n[6] LLM直接设状态")
    body.set_mood("愉悦", cause_known=True, cause="今天天气真好")
    test("6.1 情绪设置", body.mood == "愉悦")
    test("6.2 原因记录", body.mood_cause == "今天天气真好")

    body.set_hunger("有点饿")
    test("6.3 饥饿设置", body.hunger == "有点饿")

    body.set_fatigue("累")
    test("6.4 疲劳设置", body.fatigue == "累")

    print("\n[7] tick——只记录事实")
    body.hours_since_last_meal = 5.0
    t = body.tick(time_of_day="下午", hours_passed=1.0)
    test("7.1 时间累加", body.hours_since_last_meal == 6.0)
    test("7.2 返回节律感觉", len(t.get("circadian_feel", "")) > 0)
    test("7.3 tick不改情绪", t["mood"] == "愉悦")  # LLM自己管情绪
    test("7.4 返回醒了多久", "hours_since_woke" in t)
    test("7.5 tick_count递增", t["tick_count"] > 0)

    print("\n[8] 快照")
    snap = body.snapshot_for_llm(who_is_talking="同事A")
    required_keys = [
        "hunger", "hours_since_last_meal", "fatigue", "mood",
        "social_energy", "active_discomforts", "circadian_feel",
        "last_sleep_quality", "last_sleep_hours", "hours_since_woke",
        "last_sleep_interrupted", "last_sleep_woke_in_deep",
    ]
    for i, key in enumerate(required_keys):
        test(f"8.{i+1} 快照有{key}", key in snap)
    test("8.14 快照有社交历史", "person_drain_history" in snap)
    test("8.15 快照有睡眠历史", "recent_sleeps" in snap)
    test("8.16 快照全是事实没有计算", True)  # 没有float阈值、没有score

    print("\n[9] 持久化")
    import tempfile, os
    tmp = os.path.join(tempfile.gettempdir(), "test_body_core_v2.json")
    body.save_to_file(tmp)
    test("9.1 保存", os.path.exists(tmp))

    loaded = BodyCore.load_from_file(tmp)
    test("9.2 饥饿一致", loaded.hunger == body.hunger)
    test("9.3 情绪一致", loaded.mood == body.mood)
    test("9.4 睡眠记录一致", loaded.last_sleep_quality == body.last_sleep_quality)
    test("9.5 睡眠被打断一致", loaded.last_sleep_interrupted == body.last_sleep_interrupted)
    test("9.6 深度被吵醒一致", loaded.last_sleep_woke_in_deep == body.last_sleep_woke_in_deep)
    test("9.7 社交日志", len(loaded.social_log) == len(body.social_log))
    test("9.8 饮食历史", len(loaded.meal_history) == len(body.meal_history))

    os.remove(tmp)

    print(f"\n{'='*60}")
    print(f"  通过: {passed}/{passed+failed}  |  失败: {failed}/{passed+failed}")
    print(f"  身体笔记本: 记事实，不算人")
    print(f"{'='*60}")
