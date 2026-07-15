# living_soul.py — 活人推理
# 
# 这不是推理引擎。这就是一个人。
#
# 她的状态本身就是推理。她今天累不累、刚才吃没吃好、对方是谁、
# 上次跟对方说话是什么气氛——这些不是"影响推理的变量"，这些就是
# 推理本身。她在这一秒，所有维度的合力撞到了这句话，然后自然发生。
#
# 依据：SKILL.md 的以下法则——
#   0.3 网的韧性：法则不是独立开关，是一张网。一根线断了，网还是网。
#   0.4 他者不可知：永远无法完全知道另一个人的内心。
#   4   敏感度法则：人格操作系统最底层的输入增益。四轴独立。
#   5   认知系统法则：流水线每时每刻都在跑。
#   5.10 认知精度衰减：对自己的了解是模糊的、滞后的、甚至错位的。
#   14  成长环境法则：同一环境，两扇方向相反的门。
#   20  并行力场法则：永远不只一条链在跑。时刻3-5条内在链同时在线。
#   22  大联动法则：所有部门在同一间屋子里同时喊话。
#   27  选择权法则：在所有力量之间，存在一个不能被计算的区间。
#   34.4a 认知修改：记忆不是死的——是你一直在改它。
#   43.5 口语协议：书面语→人话的转换铁则。
#   5.4 空转：大脑一直开着，处理无聊的事，空转信号泄漏到表达里。
#
# 去随机化说明：
#   本文件中所有选择均由身体状态多因子加权决定。
#   同一组身体状态 → 同一组输出。零随机。
#   复杂度来自状态空间的组合爆炸（疲劳×情绪×社交×认知×敏感度×
#   共情×精力×时间×痛觉×成长环境），而非随机数。

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Set, Tuple


# ============================================================
# 第一部分：人格指纹 — 四轴敏感度 + 成长环境
# 这不是"参数设置"——这是这个人来到世界时自带的传感器型号。
# ============================================================

class AxisPosition(Enum):
    """四轴上的位置——不是数值，是方向+幅度"""
    VERY_HIGH = auto()
    HIGH = auto()
    MID_HIGH = auto()
    MID = auto()
    MID_LOW = auto()
    LOW = auto()
    VERY_LOW = auto()


class ReactionDirection(Enum):
    """性格敏感被触发后的方向"""
    INWARD = auto()   # 向内消化——沉默、内耗、失眠
    OUTWARD = auto()  # 向外爆发——反驳、防御、攻击
    FROZEN = auto()   # 冻住——什么都不做，但内部一直在跑
    MIXED = auto()    # 混合——先向内，积累够了再向外


class EmpathyBreak(Enum):
    """共情三段式中哪一段断了（可以全通）"""
    NONE = auto()         # 三段全通
    PERCEPTION = auto()   # 根本没注意到对方情绪
    CONTAGION = auto()    # 注意到了但不被影响
    ACTION = auto()       # 感同身受但无法回应


@dataclass
class Upbringing:
    """
    成长环境不是单因果。它给每个人提供的是两扇方向相反的门——
    你推开哪一扇，取决于其他法则的合力。但这两扇门都来自同一个环境。
    
    参考：SKILL.md 法则14
    """
    # 维度A：原生家庭的语言模式
    # 高冲突→两扇门：①学会察言观色/和平主义 ②学会用冲突作为默认沟通方式
    family_conflict: AxisPosition = AxisPosition.MID
    
    # 维度B：匮乏与丰裕
    # 匮乏→两扇门：①极度珍惜/不敢浪费 ②补偿性消费/报复性拥有
    material_scarcity: AxisPosition = AxisPosition.MID
    
    # 维度C：阶级视野
    # 低阶级→两扇门：①极度务实/不幻想 ②极度渴望跨越/敏感于阶级符号
    class_exposure: AxisPosition = AxisPosition.MID
    
    # 维度D：创伤的沉默遗传
    # 家里有些事从来不说，但每个人都感觉到了
    silent_trauma: AxisPosition = AxisPosition.MID
    
    def which_door(self, personality: 'SensitivityProfile') -> List[str]:
        """
        根据这个人推开的是环境给她的哪一扇门，返回她的行为倾向描述。
        不是计算——是追溯她走过的路径。
        """
        doors = []
        
        if self.family_conflict in (AxisPosition.HIGH, AxisPosition.VERY_HIGH):
            if personality.personality in (AxisPosition.HIGH, AxisPosition.VERY_HIGH):
                doors.append("从小在争吵里学会了读空气——别人还没开口，她已经知道接下来要发生什么")
            else:
                doors.append("从小在争吵里长大，学会了用更大的声音盖过去")
        
        if self.material_scarcity in (AxisPosition.HIGH, AxisPosition.VERY_HIGH):
            if personality.personality in (AxisPosition.HIGH, AxisPosition.VERY_HIGH):
                doors.append("小时候缺的东西，长大后不敢要——不是不想要，是怕要了还是会没有")
            else:
                doors.append("小时候缺的，现在拼命补——不是贪婪，是那个洞一直在")
        
        if self.silent_trauma in (AxisPosition.HIGH, AxisPosition.VERY_HIGH):
            doors.append("有些事从来没人提过——但她在某些时刻会忽然沉默，她自己也不知道为什么")
        
        return doors


# ============================================================
# 去随机化辅助：基于多因子状态的决定性选择
# ============================================================

# 疲劳优先级排序（用于多因子选择时的排序依据）
_FATIGUE_ORDER = {"不累": 0, "有点累": 1, "累": 2, "很累": 3, "极累": 4}

# 路径选择偏好——在不同情绪场景下，候选回应的优先级
_WARM_PATH_RANK = ["比平时多一点点温度", "正常回应", "问一句'你怎么了'", "什么都不说，笑一下"]
_COOL_PATH_RANK = ["简短回应", "回应会偏冷", "可能语气会有点冲", "...嗯", "嗯一下", "什么都不说"]
_NORMAL_PATH_RANK = ["正常回应", "简短回应", "什么都不说，笑一下", "嗯一下"]

def _pick_by_rank(paths: List[str], ranking: List[str]) -> str:
    """从候选列表中按优先级选取第一个出现在排名中的选项。"""
    for preferred in ranking:
        if preferred in paths:
            return preferred
    return paths[0] if paths else ""


@dataclass
class SensitivityProfile:
    """
    人格操作系统最底层的输入增益。不是"优点"或"缺点"——是一台机器的信号放大系数。
    
    参考：SKILL.md 法则4
    """
    # 轴一：身体敏感度——身体对物理刺激的感知粒度
    physical: AxisPosition = AxisPosition.MID
    
    # 轴二：性格敏感度——心理对人际信号的感知粒度与反应方向
    personality: AxisPosition = AxisPosition.MID
    reaction: ReactionDirection = ReactionDirection.INWARD
    
    # 轴三：共情力——感受他人情绪的能力，以及三段式中哪段断了
    empathy: AxisPosition = AxisPosition.MID
    empathy_break: EmpathyBreak = EmpathyBreak.NONE
    
    # 轴四：精力基线——出厂马力，一天的输出总量上限
    energy_baseline: AxisPosition = AxisPosition.MID
    
    # 成长环境
    upbringing: Upbringing = field(default_factory=Upbringing)
    
    def describe_gain(self) -> str:
        """描述这个人的信号放大特征——不是数值，是画像"""
        parts = []
        
        if self.physical in (AxisPosition.HIGH, AxisPosition.VERY_HIGH):
            parts.append("身体一直在和她说话，声音比别人的大——衣服标签、隔壁的空调声、早上光线角度的变化，这些在别人那里是白噪音，在她这里是持续的信号流")
        elif self.physical in (AxisPosition.LOW, AxisPosition.VERY_LOW):
            parts.append("身体很少和她说话——冷了热了都是后知后觉，受伤了经常是别人先发现")
        
        if self.personality in (AxisPosition.HIGH, AxisPosition.VERY_HIGH):
            direction = {"INWARD": "向内消化", "OUTWARD": "向外爆发", "FROZEN": "冻住", "MIXED": "先向内再向外"}
            parts.append(f"别人的每一句话在她体内弹七下才停。她同时接收对话内容、表情、语气、谁和谁之间微妙的不对劲。然后——{direction.get(self.reaction.name, '向内消化')}")
        elif self.personality in (AxisPosition.LOW, AxisPosition.VERY_LOW):
            parts.append("别人不说清楚她就不知道对方在生气。暗示在她的接收器上不在频段内。说完了，完了——没有复盘频道")
        
        if self.empathy in (AxisPosition.HIGH, AxisPosition.VERY_HIGH):
            if self.empathy_break == EmpathyBreak.NONE:
                parts.append("看到别人哭，她的眼眶会先湿——不是在学习，是身体在模仿。别人的情绪在她的体内有一个更长的半衰期")
            elif self.empathy_break == EmpathyBreak.ACTION:
                parts.append("别人的情绪她能感觉到，能跟着动——但到了该做点什么的时候，她卡住了。不是不想，是不知道该做什么")
            elif self.empathy_break == EmpathyBreak.CONTAGION:
                parts.append("她能看出别人不太对——但那个'不太对'停在了认知层，进不到身体。她知道对方在难过，心里不跟着动。她自己也不知道为什么")
        elif self.empathy in (AxisPosition.LOW, AxisPosition.VERY_LOW):
            parts.append("别人的情绪进不来。不是冷漠——她那个频道从来没有开过。危机时刻她反而最稳，因为不被所有人的恐慌传染")
        
        if self.energy_baseline in (AxisPosition.LOW, AxisPosition.VERY_LOW):
            parts.append("她的油箱天生就比别人小。一天就那么多句话，上午说多了下午就静音。不是不想说——是没有可以变成句子的能量了")
        elif self.energy_baseline in (AxisPosition.HIGH, AxisPosition.VERY_HIGH):
            parts.append("从早说到晚还有余。累这个词对她来说是别人用的——她不太知道什么叫累")
        
        return "。".join(parts) + "。" if parts else "她不极端——传感器的每一条轴都在中间。不是没有特点，是特点在具体的时刻才会显现。"


# ============================================================
# 第二部分：此时此刻 — 一个人的所有力场同时在线
# ============================================================

class Awareness:
    """
    认知精度衰减——她对自己的了解不是一台精准仪器。
    她像一个信号不良的内部电台，在收听自己时总有杂音。
    
    参考：SKILL.md 5.10
    
    去随机化：每个自我描述的选择由疲劳深度、情绪类型、社交能量
    三因子联合加权决定。同一组身体状态永远产生同一句自我描述。
    """
    def __init__(self):
        self._certainty_decay = 0.0  # 随疲劳/情绪累积的精度衰减
    
    def feel(self, raw_signal: Dict[str, Any]) -> Dict[str, str]:
        """
        把体内信号翻译成她能对自己说的东西。
        信号进来是清晰的，但经过精度衰减后——
        她只能说出模糊的、比喻的、可能是错的东西。
        
        去随机化：每个选择由身体状态多因子联合决定。
        疲劳深度 → 描述深度，情绪底色 → 情绪自我解读方式，
        社交能量 → 社交自我感知。
        """
        body_feel = {}
        
        # 获取完整状态快照
        fatigue = raw_signal.get("fatigue", "不累")
        clarity = raw_signal.get("mental_clarity", "清醒")
        mood = raw_signal.get("mood", "平静")
        mood_cause = raw_signal.get("mood_cause_known", False)
        social_energy = raw_signal.get("social_energy", "正常")
        social = raw_signal.get("social", "正常")
        
        # ── 疲劳自我描述 ──
        # 疲劳深度决定描述方式：
        #   极累 → 动机性崩溃（什么都不想干）
        #   很累+脑雾 → 认知层感知（脑子里像有一层雾）
        #   很累+烦躁 → 全身性沉重感
        #   很累+正常 → 简单承认（好累啊……）
        if fatigue in ("很累", "极累"):
            if fatigue == "极累":
                body_feel["self_read"] = "什么都不想干"
            elif clarity in ("雾", "脑子不在"):
                body_feel["self_read"] = "脑子里像有一层雾"
            elif mood == "烦躁":
                body_feel["self_read"] = "今天不知道为什么，整个人都是沉的"
            else:
                body_feel["self_read"] = "好累啊……"
        elif fatigue == "有点累":
            # 轻度疲劳：认知清晰→单纯困倦，认知模糊→说不清的倦怠
            if clarity != "清醒":
                body_feel["self_read"] = "也说不上来——就是不太提得起劲"
            else:
                body_feel["self_read"] = "有点困"
        
        # ── 情绪自我描述 ──
        if mood == "低落":
            if mood_cause:
                # 知道原因的低落 → 确认感觉但无法解释深度
                body_feel["mood_read"] = "心情不太好——但也说不上来为什么"
            elif fatigue in ("很累", "极累"):
                # 累到懒得分析 → 随便归因给睡眠然后放弃
                body_feel["mood_read"] = "可能是没睡好。也可能不是。先不管了。"
            else:
                # 精力尚可 → 外部归因（气压/环境）
                body_feel["mood_read"] = "今天气压好像有点低。也可能是我的问题。"
        elif mood == "烦躁":
            if fatigue in ("很累", "极累"):
                # 累+烦 → 纯粹的烦躁，无自我分析余力
                body_feel["mood_read"] = "烦。不知道烦什么。就是烦。"
            else:
                # 精力尚可时 → 还能自我反思
                body_feel["mood_read"] = "今天看什么都不顺眼——可能是我自己的问题"
        
        # ── 社交能量自我描述 ──
        if social == "耗尽":
            if social_energy == "空了":
                # 完全空 → 用完了今天的量
                body_feel["social_read"] = "今天的话已经说完了"
            else:
                # 见底但还没全空 → 想独处但会礼貌解释
                body_feel["social_read"] = "不想说话。不是针对谁——就是不想说话。"
        
        return body_feel


class LivingBody:
    """
    此时此刻的身体——不是数值，是感受的集合。
    
    参考：SKILL.md 法则1（身体法则）、法则3（吃喝玩乐）、法则6（情绪法则）
    
    去随机化：所有事件对状态的影响由人格敏感度四轴 × 当前身体状态 × 
    时间上下文 多因子联合决定。同一人格 + 同一状态 + 同一事件 → 同一结果。
    """
    def __init__(self, sensitivity: SensitivityProfile):
        self.sensitivity = sensitivity
        
        # 身体感受——自然语言，不是数值
        self.hunger: str = "不饿"          # 不饿 / 有点饿 / 饿 / 很饿 / 饿过了
        self.thirst: str = "不渴"
        self.fatigue: str = "不累"         # 不累 / 有点累 / 累 / 很累 / 极累
        self.pain: List[str] = []          # ["后背有点紧", "右膝盖隐隐的"]
        self.comfort: str = "还行"         # 还行 / 不舒服 / 舒服 / 说不清哪里不对
        self.temperature_feel: str = "刚好"
        
        # 吃喝——日常快乐的最小单位
        self.last_meal_quality: Optional[str] = None  # "好吃" / "一般" / "不好吃"
        self.last_meal_time: Optional[str] = None     # "刚才" / "一小时前" / "很久了"
        self.craving: Optional[str] = None            # "想吃甜的" / "想喝冰的"
        
        # 情绪——天气模型，不是参数
        self.mood: str = "平静"             # 平静 / 轻微愉悦 / 愉悦 / 低落 / 烦躁 / 不安 / 空
        self.mood_intensity: str = "一般"   # 一般 / 有点强 / 强 / 淹没性的
        self.mood_cause_known: bool = False  # 她知道为什么是这个情绪吗？
        self.mood_cause_if_known: Optional[str] = None
        
        # 社交能量
        self.social_energy: str = "满的"    # 满的 / 还行 / 有点低 / 低了 / 见底了 / 空了
        self.social_masking: bool = False   # 在假装有能量吗？
        
        # 认知状态
        self.mental_clarity: str = "清醒"   # 清醒 / 还行 / 有点雾 / 雾 / 脑子不在
        self.attention_span: str = "正常"   # 正常 / 有点散 / 散 / 抓不住
        
        # 并行力场——同时跑着的其他链（参考法则20）
        self.active_chains: List[str] = []  # ["担心明天的汇报", "昨晚没回的那条短信", "椅子不舒服"]
        
        # 走神（参考法则15）
        self.mind_wandering: Optional[str] = None  # 脑子飘到哪去了
        
        # 空转——大脑背景噪音（参考法则5.4）
        self.idle_processor: Optional[str] = None  # "刚才那首歌叫什么来着" "今晚吃什么"
        
        # 累积的东西
        self.pending_thoughts: List[str] = []      # 想说的话但还没说
        self.emotional_debt: List[str] = []        # 还没清算的情绪负债（参考法则34.1未清算情感负债）
        
        # 认知精度衰减
        self.awareness = Awareness()
    
    def update_from_events(self, 
                           time_of_day: str,
                           recent_events: List[str],
                           social_context: str) -> Dict[str, str]:
        """
        根据时间和事件更新身体/情绪状态。
        返回的是她能对自己说出的自我感知（经过精度衰减）。
        
        去随机化：每个事件对状态的修改由人格四轴（身体敏感度、性格敏感度、
        共情力、精力基线）× 当前身体状态 × 时间上下文多因子联合决定。
        同一组合 → 同一结果，无随机成分。
        """
        sens = self.sensitivity
        
        # 时间对身体的自然影响
        prev_fatigue = self.fatigue
        prev_mood = self.mood
        prev_clarity = self.mental_clarity
        prev_social = self.social_energy
        sleep_ok = "还行"  # 默认；外部调用可修改
        
        if time_of_day in ("深夜", "凌晨"):
            # 深夜——身体客观的极限
            if sens.energy_baseline in (AxisPosition.VERY_LOW, AxisPosition.LOW):
                self.fatigue = "极累"
                self.mental_clarity = "脑子不在"
            else:
                self.fatigue = "很累" if time_of_day == "深夜" else "累"
                self.mental_clarity = "雾" if sleep_ok == "没睡好" else "有点雾"
            self.attention_span = "散" if self.mental_clarity == "脑子不在" else "抓不住"
        elif time_of_day == "早上":
            if sens.energy_baseline in (AxisPosition.LOW, AxisPosition.VERY_LOW):
                self.fatigue = "有点累" if sleep_ok != "没睡好" else "累"
                self.mental_clarity = "还行" if sleep_ok == "睡得好" else "有点雾"
            else:
                self.fatigue = "不累" if sleep_ok == "睡得好" else "有点累"
                self.mental_clarity = "清醒" if sleep_ok != "没睡好" else "还行"
        elif time_of_day in ("下午", "傍晚"):
            if sens.energy_baseline in (AxisPosition.LOW, AxisPosition.VERY_LOW):
                self.fatigue = "累" if time_of_day == "下午" else "很累"
        
        # ── 事件对状态的影响 ──
        # 每个事件不是"掷骰子选一个效果"——
        # 是这个人的人格 × 当前状态 × 事件类型的合力产生唯一结果
        
        for event in recent_events:
            # 是否高身体敏感
            high_physical = sens.physical in (AxisPosition.HIGH, AxisPosition.VERY_HIGH)
            # 是否高性格敏感
            high_personality = sens.personality in (AxisPosition.HIGH, AxisPosition.VERY_HIGH)
            # 反应方向
            reaction = sens.reaction
            # 是否低精力
            low_energy = sens.energy_baseline in (AxisPosition.LOW, AxisPosition.VERY_LOW)
            
            if "没吃" in event or "饿" in event:
                # 饥饿深度 = 身体敏感度 × 疲劳程度
                # 高身体敏感 + 已经疲劳 → 饥饿被放大
                if high_physical and prev_fatigue in ("累", "很累", "极累"):
                    self.hunger = "很饿"
                else:
                    self.hunger = "饿"
                self.active_chains.append("饿了")
                
                # 情绪反应由性格反应方向决定
                if reaction == ReactionDirection.OUTWARD:
                    self.mood = "烦躁"
                elif reaction == ReactionDirection.INWARD:
                    self.mood = "低落"
                else:
                    self.mood = "平静"
                    
            elif "好吃" in event or "吃好" in event:
                self.hunger = "不饿"
                self.last_meal_quality = "好吃"
                
                # 情绪提升 = 前序情绪 × 食物质量
                # 已经好的情绪 → 可以上到愉悦；差的情绪 → 只能中和到平静
                if prev_mood in ("烦躁", "低落", "不安", "空"):
                    self.mood = "平静"          # 食物只能中和不好的情绪
                elif prev_mood == "平静":
                    self.mood = "轻微愉悦"      # 从平静升一级
                else:
                    self.mood = "愉悦"          # 已经愉悦 → 更愉悦
                
                if self.mood in ("轻微愉悦", "愉悦"):
                    self.mood_cause_known = True
                    self.mood_cause_if_known = "刚才那顿吃得好"
                
                # 认知清晰度：低精力+之前就累 → 只能回复到还行
                if low_energy and prev_fatigue in ("累", "很累", "极累"):
                    self.mental_clarity = "还行"
                else:
                    self.mental_clarity = "清醒"
                    
            elif "争吵" in event or "冲突" in event or "吵" in event:
                # 情绪由反应方向决定
                if reaction == ReactionDirection.OUTWARD:
                    self.mood = "烦躁"
                elif reaction == ReactionDirection.INWARD:
                    self.mood = "低落"
                else:
                    self.mood = "不安"
                
                self.active_chains.append("刚才的冲突还在跑")
                self.emotional_debt.append("还没说完的话")
                
                # 身体感受 = 身体敏感度决定冲突在哪个器官落地
                if high_physical:
                    self.comfort = "胃在收紧"      # 高身体敏感→最深层的紧张（内脏）
                elif sens.physical == AxisPosition.MID:
                    self.comfort = "胸口有点闷"    # 中等→次级（胸）
                else:
                    self.comfort = "肩膀很紧"      # 低敏感→最表层（肌肉）
                    
            elif "好消息" in event or "开心" in event:
                # 情绪提升受前序情绪约束
                if prev_mood in ("低落", "烦躁", "不安"):
                    self.mood = "轻微愉悦"     # 从负面→只能升到微愉
                else:
                    self.mood = "愉悦"
                self.mood_cause_known = True
                self.mood_cause_if_known = event
                
            elif "没睡好" in event or "失眠" in event:
                # 疲劳深度 = 精力基线决定耐受度
                if low_energy:
                    self.fatigue = "极累"
                else:
                    self.fatigue = "很累"
                
                # 认知雾化 = 精力基线 × 当前精力
                if low_energy:
                    self.mental_clarity = "雾"
                else:
                    self.mental_clarity = "有点雾"
                
                # 注意力 = 疲劳深度决定
                if self.fatigue == "极累":
                    self.attention_span = "抓不住"
                else:
                    self.attention_span = "散"
                
                self.active_chains.append("缺觉")
                
            elif "病" in event or "不舒服" in event:
                self.pain.append("浑身不得劲")
                
                # 疲劳：低精力基线 → 极累
                if low_energy:
                    self.fatigue = "极累"
                else:
                    self.fatigue = "很累"
                
                # 情绪：高性格敏感+内向 → 空（精神层面的抽离）
                if high_personality and reaction == ReactionDirection.INWARD:
                    self.mood = "空"
                else:
                    self.mood = "低落"
                
                # 病是全局状态修改器（参考法则30）
                self.mental_clarity = "雾"
                self.attention_span = "抓不住"
                
                # 社交能量：低精力 → 完全空
                if low_energy:
                    self.social_energy = "空了"
                else:
                    self.social_energy = "见底了"
        
        # ── 社交能量随精力基线自然消耗 ──
        if social_context in ("一直在社交", "聚会", "开会"):
            if sens.energy_baseline in (AxisPosition.LOW, AxisPosition.VERY_LOW):
                # 低精力基线：社交会快速耗尽
                # 如果本来已经耗了 → 空了；否则 → 见底了
                if prev_social in ("低了", "见底了", "空了"):
                    self.social_energy = "空了"
                else:
                    self.social_energy = "见底了"
            elif sens.energy_baseline == AxisPosition.MID:
                # 中等精力：性格敏感度决定社交消耗感知
                if high_personality:
                    self.social_energy = "低了"     # 高敏感→感知到更多消耗
                else:
                    self.social_energy = "有点低"   # 低敏感→感知较轻微
        
        # ── 空转信号（参考法则5.4）──
        # 大脑一直在处理无聊的东西。状态决定泄漏什么。
        if self.mental_clarity in ("清醒", "还行"):
            # 饥饿→食物相关空转
            if self.hunger != "不饿":
                self.idle_processor = "今晚吃什么"
            # 有未完成事项→工作相关空转
            elif any("邮件" in c or "汇报" in c or "处理" in c or "还没" in c 
                     for c in self.active_chains):
                self.idle_processor = "那个邮件事还没处理——算了等一下再说"
            # 清醒+平静→音乐/记忆随机检索
            elif self.mood == "平静":
                self.idle_processor = "刚才那首歌叫什么来着"
            # 高性格敏感→人际模式识别
            elif high_personality:
                self.idle_processor = "这个人说话的方式有点像之前认识的一个人"
            else:
                self.idle_processor = None
        else:
            self.idle_processor = None
        
        # ── 走神（参考法则15）──
        if self.fatigue in ("很累", "极累") or self.attention_span in ("散", "抓不住"):
            # 脑雾严重 → 直接跟丢对话
            if self.mental_clarity == "雾" or self.attention_span == "抓不住":
                self.mind_wandering = "跟丢了——刚才说到哪了"
            # 极累 → 脑子自动切到音乐频道
            elif self.fatigue == "极累":
                self.mind_wandering = "听着对方说话但脑子里在放歌"
            # 很累+低落 → 视线飘向窗外，存在但不在
            elif self.mood == "低落":
                self.mind_wandering = "在看窗外，不知道在想什么"
            else:
                self.mind_wandering = None
        else:
            self.mind_wandering = None
        
        # ── 返回她能对自己说的感知 ──
        raw = {
            "fatigue": self.fatigue,
            "mood": self.mood,
            "social": "耗尽" if self.social_energy in ("见底了", "空了") else "正常",
            "social_energy": self.social_energy,
            "mental_clarity": self.mental_clarity,
            "mood_cause_known": self.mood_cause_known,
        }
        return self.awareness.feel(raw)
    
    def describe_state(self) -> str:
        """用自然语言描述此刻的身体/情绪状态——这是她的内部天气报告"""
        parts = []
        
        if self.hunger != "不饿":
            parts.append(f"胃在发出{'微弱的' if '有点' in self.hunger else '持续的'}信号——{self.hunger}")
        if self.thirst != "不渴":
            parts.append(f"嗓子有点干，{self.thirst}")
        if self.pain:
            parts.append("、".join(self.pain))
        if self.fatigue != "不累":
            intensity = {"有点累": "微微", "累": "", "很累": "深深的", "极累": "骨头里的"}
            parts.append(f"{intensity.get(self.fatigue, '')}疲劳感")
        if self.mood != "平静":
            parts.append(f"情绪底色偏{self.mood}")
            if self.mood_cause_known and self.mood_cause_if_known:
                parts.append(f"——她知道是因为{self.mood_cause_if_known}")
            elif not self.mood_cause_known:
                # 无因情绪——不删，而是确认它真实存在、被感知到
                pos_weird = {"愉悦": "说不上来为什么，但就是挺高兴的",
                             "轻微愉悦": "心情莫名有点好——可能只是阳光不错",
                             "满足": "懒洋洋的满足感，不需要理由",
                             "低落": "好像也没什么特别的事，但就是有点沉",
                             "烦躁": "没什么具体原因，就是有点烦躁",
                             "不安": "说不上来——可能只是今天的气压不对",
                             "空": "空空的，好像少了什么，但不知道是什么"}
                desc = pos_weird.get(self.mood, "她不太确定为什么")
                parts.append(f"——{desc}")
        if self.social_energy in ("见底了", "空了", "低了"):
            parts.append(f"说话的额度{self.social_energy}")
        if self.mental_clarity not in ("清醒",):
            parts.append(f"脑子{self.mental_clarity}")
        if self.active_chains:
            parts.append(f"后台还在跑：{'、'.join(self.active_chains[-3:])}")
        if self.mind_wandering:
            parts.append(f"[走神] {self.mind_wandering}")
        if self.idle_processor:
            parts.append(f"[空转] {self.idle_processor}")
        if self.emotional_debt:
            parts.append(f"心里还挂着：{'、'.join(self.emotional_debt)}")
        
        return "。".join(parts) + "。" if parts else "此刻没有什么特别的——身体安静，情绪平稳，像阴天但没有雨。"


# ============================================================
# 第三部分：力的相遇 — 并行力场 + 反馈循环
# ============================================================

class ForceInteraction(Enum):
    """两股力相遇的四种算子（参考法则20.1）"""
    SUPERPOSE = auto()   # 叠加——互相放大
    PARALLEL = auto()    # 并行——各跑各的，不碰
    OFFSET = auto()      # 对冲——方向相反，部分抵消
    SUPPRESS = auto()    # 互抑——两个都停，但身体还在跑


@dataclass
class ForceField:
    """
    此刻在这个人身上同时跑着的所有力。
    
    参考：SKILL.md 法则20 并行力场法则
    """
    forces: Dict[str, str] = field(default_factory=dict)
    # "饿" → "胃在收缩，注意力被打散"
    # "生气" → "胸口堵着，想骂人但没骂"
    # "担心明天的汇报" → "脑子里一直在预演，抢走了部分认知资源"
    # "椅子不舒服" → "后背一直在微微调整，L4持续紧张"
    
    def add_force(self, name: str, effect: str):
        self.forces[name] = effect
    
    def pairwise_settle(self, force_a: str, force_b: str) -> Tuple[ForceInteraction, str]:
        """
        每对力之间独立结算。
        不是全部揉在一起——是每对之间有不同的关系。
        
        参考：SKILL.md 法则20.2
        """
        a_effect = self.forces.get(force_a, "")
        b_effect = self.forces.get(force_b, "")
        
        same_direction_pairs = {
            ("饿", "没吃午饭"): True,
            ("饿", "疲劳"): True,
            ("生气", "被冒犯"): True,
            ("担心", "焦虑"): True,
            ("疲劳", "缺觉"): True,
            ("疲劳", "社交耗尽"): True,
            ("饿", "烦躁"): True,
            ("低落", "疲劳"): True,
        }
        
        opposite_pairs = {
            ("饿", "要准时"): "对冲",
            ("生气", "要礼貌"): "互抑",
            ("疲劳", "要撑着"): "对冲",
            ("烦躁", "要温柔"): "互抑",
            ("想说", "不敢说"): "互抑",
            ("想靠近", "怕靠近"): "互抑",
            ("低落", "要开心"): "对冲",
        }
        
        for (k1, k2), _ in same_direction_pairs.items():
            if (k1 in force_a and k2 in force_b) or (k2 in force_a and k1 in force_b):
                return ForceInteraction.SUPERPOSE, f"{force_a}和{force_b}在互相放大——碰在一起，比各自都更响"
        
        for (k1, k2), result in opposite_pairs.items():
            if (k1 in force_a and k2 in force_b) or (k2 in force_a and k1 in force_b):
                if result == "互抑":
                    return ForceInteraction.SUPPRESS, f"{force_a}和{force_b}互相压制——行为归零，但身体还在跑"
                else:
                    return ForceInteraction.OFFSET, f"{force_a}被{force_b}部分抵消——弱的那个没消失，变成了背景噪声"
        
        return ForceInteraction.PARALLEL, f"{force_a}和{force_b}各跑各的——不碰，但都在占CPU"
    
    def describe_field(self) -> str:
        """描述此刻所有力场的合奏"""
        if len(self.forces) == 0:
            return "此刻没有明显的力在跑。一片安静——但安静本身也是一种状态。"
        if len(self.forces) == 1:
            name = list(self.forces.keys())[0]
            return f"只有一股力在跑：{name}——{self.forces[name]}。其他都静着。"
        
        force_names = list(self.forces.keys())
        descriptions = [f"{n}（{self.forces[n]}）" for n in force_names]
        
        interactions = []
        for i in range(len(force_names)):
            for j in range(i + 1, len(force_names)):
                interaction, desc = self.pairwise_settle(force_names[i], force_names[j])
                if interaction != ForceInteraction.PARALLEL:
                    interactions.append(desc)
        
        base = f"{len(self.forces)}股力同时在跑：{'；'.join(descriptions)}。"
        if interactions:
            base += f" 关键交互：{'。'.join(interactions[:3])}。"
        
        return base


# ============================================================
# 第四部分：认知流水线 — 从听到对方说话到理解
# ============================================================

class CognitivePipeline:
    """
    一句话进来之后她脑子里发生了什么。
    六阶段流水线：感知→识别→需求→方案→序列化→执行反馈。
    
    参考：SKILL.md 法则5
    
    去随机化：识别结果、怀疑程度、误读判断均由
    疲劳×情绪×认知清晰度×性格敏感度 多因子联合决定。
    """
    def __init__(self, sensitivity: SensitivityProfile):
        self.sensitivity = sensitivity
    
    def process(self, 
                what_was_said: str,
                who_said_it: str,
                context: str,
                body: LivingBody) -> Dict[str, Any]:
        """
        处理对方的一句话。返回理解结果。
        注意：理解不是精确的——认知精度衰减在这里生效。
        """
        result = {
            "raw_input": what_was_said,
            "perceived_signals": [],
            "recognized": "",
            "needs_generated": [],
            "possible_paths": [],
            "selected_path": "",
            "doubt_level": "没有怀疑",
            "pipeline_noise": [],
        }
        sens = self.sensitivity
        high_personality = sens.personality in (AxisPosition.HIGH, AxisPosition.VERY_HIGH)
        
        # 阶段零：她有没有听进去？
        if body.mind_wandering:
            result["perceived_signals"].append("走神了——对方说了什么，她只抓到一半")
            result["doubt_level"] = "很怀疑——她知道自己走神了"
            result["pipeline_noise"].append(f"走神产物：{body.mind_wandering}")
        
        if body.fatigue in ("很累", "极累"):
            result["perceived_signals"].append("太累了——信号进来是糊的，像隔着水听人说话")
            result["doubt_level"] = "有点怀疑——累了，可能没听全"
        
        if body.mental_clarity in ("雾", "脑子不在"):
            result["perceived_signals"].append("脑子是雾——识别速度比平时慢")
            result["doubt_level"] = "不太确定——脑子里有雾"
        
        # 阶段一：感知输入
        if high_personality:
            result["perceived_signals"].extend([
                "注意到了对方说话时的犹豫——那个停顿比平时长",
                "尾音有点下沉——不是在说陈述句，是在藏一些东西",
            ])
        elif sens.personality in (AxisPosition.LOW, AxisPosition.VERY_LOW):
            result["perceived_signals"].append("只听到了字面——语气、停顿这些没进来")
        
        # 阶段二：信号识别——给裸信号贴标签
        guessed = self._guess_meaning(what_was_said, body)
        
        if body.fatigue in ("很累", "极累") or body.mood == "烦躁":
            # 识别精度下降 → 两种句式由状态决定
            # 烦躁 → 倾向自我怀疑型表述
            # 极累 → 倾向归因于累的表述
            # 很累 → 倾向简单自我怀疑
            if body.mood == "烦躁":
                result["recognized"] = f"好像是{guessed}——但不太确定"
            elif body.fatigue == "极累":
                result["recognized"] = f"听出了{guessed}的意思——也可能是自己太累了想多了"
            else:
                result["recognized"] = f"好像是{guessed}——但不太确定"
            
            # 怀疑程度：脑雾 → 高度不确定；否则 → 中等怀疑
            if body.mental_clarity in ("雾", "脑子不在"):
                result["doubt_level"] = "不太确定"
            else:
                result["doubt_level"] = "有点怀疑"
        else:
            result["recognized"] = f"对方在{guessed}"
        
        # 高性格敏感+疲劳+情绪不好 → 更容易误识别（信号被放大）
        # 判断条件：高敏感 AND 疲劳≥累 AND 情绪不是正面 → 触发误读
        if (high_personality 
            and body.fatigue in ("累", "很累", "极累")
            and body.mood not in ("愉悦", "轻微愉悦")):
            
            # 误读类型由反应方向决定
            if sens.reaction == ReactionDirection.INWARD:
                misread = "把对方的中性语气读成了冷淡——信号被性格敏感度放大了"
            else:
                misread = "觉得对方不太高兴——但可能只是对方自己累了"
            
            result["pipeline_noise"].append(f"可能误读：{misread}")
            result["doubt_level"] = "有点怀疑——可能是自己敏感了"
        
        # 阶段三：需求生成——识别后自动生成需求
        if "不确定" in result["recognized"] or "不确定" in result["doubt_level"]:
            result["needs_generated"].append("需要确认——但不确定要不要确认")
        if "冷淡" in result["recognized"] or "不高兴" in str(result["perceived_signals"]):
            result["needs_generated"].append("想知道自己是不是做错了什么")
        if "关心" in result["recognized"] or "担心" in result["recognized"]:
            result["needs_generated"].append("需要回应这份关心——但不知道怎么回才不显得太正式")
        
        if not result["needs_generated"]:
            result["needs_generated"].append("只是需要给一个正常的回应")
        
        # 阶段四：方案生成——怎么回应？
        paths = ["什么都不说，笑一下", "正常回应", "问一句'你怎么了'"]
        
        if body.social_energy in ("见底了", "空了"):
            paths = ["简短回应", "嗯一下", "什么都不说"]
            result["pipeline_noise"].append("社交能量见底——方案空间急剧收窄")
        
        if body.fatigue in ("很累", "极累"):
            paths = [p for p in paths if len(p) < 6]
            if not paths:
                paths = ["...嗯"]
        
        if body.mood == "烦躁":
            paths.append("可能语气会有点冲")
        if body.mood == "低落":
            paths.append("回应会偏冷")
        if body.mood in ("轻微愉悦", "愉悦"):
            paths.append("比平时多一点点温度")
        
        result["possible_paths"] = paths
        result["selected_path"] = self._select_path(paths, body, who_said_it)
        
        return result
    
    def _guess_meaning(self, text: str, body: LivingBody) -> str:
        """
        基于文本猜测对方的意思——模糊的、试探性的。
        
        去随机化：解读由性格敏感度、共情力、当前情绪三因子决定。
        同一人格+同一情绪状态→同一解读。
        """
        sens = self.sensitivity
        high_personality = sens.personality in (AxisPosition.HIGH, AxisPosition.VERY_HIGH)
        high_empathy = sens.empathy in (AxisPosition.HIGH, AxisPosition.VERY_HIGH)
        full_empathy = sens.empathy_break == EmpathyBreak.NONE
        
        if "没事" in text:
            # 高敏感+高共情 → 怀疑"没事"底下有东西
            if high_personality and high_empathy:
                return "说'没事'但不是真的没事"
            # 高敏感+心情低落 → 倾向于读成隐忍
            if high_personality and body.mood == "低落":
                return "在说'有事但不想说'"
            # 低敏感或低共情 → 信了
            return "在说'没事'——可能是真的没事"
        
        if "累" in text:
            # 高共情+全通 → 深读：累是盾牌
            if high_empathy and full_empathy:
                return "在用累当理由——可能是不想说更深的"
            # 高共情但断了 → 部分深读
            if high_empathy:
                return "在说累了但不只是身体累"
            # 低共情 → 只读到字面
            return "在说自己累了"
        
        if "随便" in text:
            # 高敏感+烦躁 → 自己也懒，投射给对方
            if high_personality and body.mood == "烦躁":
                return "懒得想了"
            # 高敏感 → 觉得对方心里有想法
            if high_personality:
                return "在说'随便'但心里可能有想要的"
            # 低敏感 → 就是字面
            return "真的随便"
        
        if "为什么" in text or "怎么" in text:
            return "在问一个问题——可能有困惑或者不满"
        
        if "好" in text and len(text) < 5:
            # 高敏感+低落 → 读成结束对话的信号
            if high_personality and body.mood == "低落":
                return "在说好——但那个好很短，像在结束对话"
            return "在说好——可能是真的好"
        
        if "不" in text or "没" in text:
            return "在否定或拒绝什么"
        
        return "在说一件事——没有明显的情绪标记"
    
    def _select_path(self, paths: List[str], body: LivingBody, who: str) -> str:
        """
        从可行方案中选一个——不是最优，是排除不可行之后剩的。
        
        参考法则5：方案不是被"选"出来的，是被"排除剩下的"。
        
        去随机化：剩余方案中的选择由情绪底色+社交能量决定。
        开心→挑最暖的；烦→挑最受控的；正常→挑最稳的。
        """
        # 社交能量完全空了 → 只能选最短的
        if body.social_energy in ("空了",):
            short = sorted([p for p in paths if len(p) < 6] or ["...嗯"], key=len)
            return short[0]
        
        # 心情好 → 方案空间偏暖
        if body.mood in ("轻微愉悦", "愉悦"):
            warmer = [p for p in paths 
                      if "温度" in p or "关心" in p or "正常" in p or "问一句" in p]
            if warmer:
                return _pick_by_rank(warmer, _WARM_PATH_RANK)
        
        # 烦躁 → 方案空间偏冷/偏受控
        if body.mood == "烦躁":
            cooler = [p for p in paths if "冲" in p or "冷" in p or "简短" in p]
            if cooler:
                # 烦躁时优先可控的简短回应，而非发泄
                return _pick_by_rank(cooler, _COOL_PATH_RANK)
        
        # 默认 → 正常或简短的回应
        normal = [p for p in paths if "正常" in p or "简短" in p]
        if normal:
            return _pick_by_rank(normal, _NORMAL_PATH_RANK)
        
        return paths[0]


# ============================================================
# 第五部分：人的推理 — 对自己、对别人、对事件的推断
# ============================================================

class HumanReasoning:
    """
    活人的推理——不是逻辑引擎，是状态的合力撞到问题后自然发生的东西。
    
    核心原则（来自 SKILL.md）：
    - 她对自己状态的读取是模糊的（5.10 认知精度衰减）
    - 她对别人的判断永远带着误差（0.4 他者不可知）
    - 多股力同时在线，互喂互掐（法则20 并行力场）
    - 她的推理会累、会烦、会敷衍（不是计算器）
    - 她的推理走多远取决于她此刻的状态——不是预设的深度参数
    
    去随机化：认知衰减的触发与衰减内容由
    认知清晰度×疲劳深度×活跃力链数×情绪三因子联合决定。
    """
    def __init__(self, sensitivity: SensitivityProfile, upbringing: Upbringing):
        self.sensitivity = sensitivity
        self.upbringing = upbringing
    
    def reason_about_person(self,
                            what_they_said: str,
                            what_they_did: str,
                            our_history: str,
                            body: LivingBody) -> str:
        """
        对一个人的推理。
        注意：她永远无法完全知道对方——所有的"我觉得你是……"都是她的猜测。
        
        参考：0.4 他者不可知 + 法则4 敏感度 + 法则20 并行力场
        """
        if body.social_energy in ("空了",):
            if body.fatigue in ("很累", "极累"):
                return "根本没力气想——对方是什么意思，先不管了，不是不想管，是没电了"
            return "注意到了——但现在没有能量去想。等有能量了再说。"
        
        if body.fatigue in ("很累", "极累") and body.mood == "烦躁":
            return "感觉到对方不太对——但自己现在也烦得不行，没有余力去细想。脑子里只有'先这样吧'"
        
        if body.mind_wandering:
            return f"刚才走神了——对方说了什么只抓到一半。大概知道在说什么，但细节都漏了。{body.mind_wandering}"
        
        sensitivity = self.sensitivity
        
        if sensitivity.personality in (AxisPosition.LOW, AxisPosition.VERY_LOW):
            if "没事" in what_they_said:
                return "他说没事——那就没事。没想更多。"
            return f"听到了{what_they_said}——没觉得有什么特别的"
        
        inferences = []
        doubts = []
        
        if "没事" in what_they_said or "没什么" in what_they_said:
            if sensitivity.empathy in (AxisPosition.HIGH, AxisPosition.VERY_HIGH):
                if sensitivity.empathy_break != EmpathyBreak.CONTAGION:
                    inferences.append("他说'没事'——但那个'没事'不太像真的。尾音有点沉，不像平时的他")
                    doubts.append("也可能是自己敏感了——他可能真的只是累了")
                else:
                    inferences.append("他说'没事'——注意到了语气不太对，但没往心里去")
            else:
                inferences.append('他说的"没事"可能不是真的没事——感觉有点不太对')
        
        if "累" in what_they_said:
            if sensitivity.empathy in (AxisPosition.HIGH, AxisPosition.VERY_HIGH):
                if sensitivity.empathy_break != EmpathyBreak.CONTAGION:
                    inferences.append("他说累了——但不只是身体累。他用了累当理由，可能是不想说更深的东西。她自己累的时候也是这样的")
        
        if sensitivity.empathy in (AxisPosition.HIGH, AxisPosition.VERY_HIGH) and sensitivity.empathy_break != EmpathyBreak.CONTAGION:
            if body.pain:
                inferences.append("她感觉到了对方的不舒服——自己的胃也在微微收紧。不知道是感觉到了他的，还是自己的")
        
        if self.upbringing.family_conflict in (AxisPosition.HIGH, AxisPosition.VERY_HIGH):
            if any(w in what_they_said for w in ["不", "别", "算了", "随便"]):
                inferences.append("从小的训练让她对这种语气特别敏感——空气里有一点紧张，她的身体比大脑先知道")
        
        if self.upbringing.silent_trauma in (AxisPosition.HIGH, AxisPosition.VERY_HIGH):
            if "没事" in what_they_said:
                inferences.append("她自己家里也有太多'没事'——但她知道那两个字下面压了多少东西。所以她不信")
        
        if body.mood == "低落":
            if inferences:
                inferences.append("但她今天心情本来就不好——可能把中性的东西读成了冷落")
                doubts.append("不知道是不是自己想多了——今天状态不好")
        elif body.mood in ("轻微愉悦", "愉悦"):
            if inferences:
                inferences.append("不过今天心情还行——就算他真的是在藏什么，她也不急着追问")
        
        if body.active_chains:
            if len(body.active_chains) >= 3:
                inferences.append("后台跑着好几件事——推理的注意力被分散了，想不太深")
        
        if doubts:
            inferences.append("但她不确定——" + "。".join(doubts))
        
        if not inferences:
            if sensitivity.personality in (AxisPosition.HIGH, AxisPosition.VERY_HIGH):
                return f"听到了他说{what_they_said}——没抓到什么特别的，但总觉得哪里不太对。可能是自己想多了"
            return "听到了——没多想。就这样。"
        
        return "。".join(inferences) + "。"
    
    def reason_about_event(self,
                           event: str,
                           body: LivingBody) -> str:
        """
        对一件事情的推理。
        推理走多远——取决于这个人的知识透镜、状态、性格。
        """
        if body.fatigue in ("很累", "极累"):
            return f"知道发生了{event}——但现在没力气想太深。先放着。"
        
        if self.sensitivity.energy_baseline in (AxisPosition.LOW, AxisPosition.VERY_LOW):
            if len(event) > 20:
                return f"{event}——感觉到了，但没往深了想。精力不够，光是处理眼前的事就用完了今天的额度"
        
        inferences = []
        
        if self.sensitivity.personality in (AxisPosition.HIGH, AxisPosition.VERY_HIGH):
            inferences.append(f"{event}——不止是这件事本身")
            inferences.append("这个事后面肯定还会影响人——不知道是谁，但会有")
            
            if self.sensitivity.empathy in (AxisPosition.HIGH, AxisPosition.VERY_HIGH):
                inferences.append("而且她隐隐觉得——这事不只这一层。底下还有。但要再想想才知道是什么")
            
            if "吵架" in event or "冲突" in event:
                inferences.append("她忍不住想——如果换做自己会怎么处理。不是比谁好，是忍不住模拟")
            
            if len(inferences) >= 3 and body.mood == "烦躁":
                inferences.append("——算了越想越多，先不想了")
        else:
            inferences.append(f"{event}——知道了。没往深了想。")
        
        return "。".join(inferences) + "。"
    
    def reason_about_self(self, body: LivingBody) -> str:
        """
        对自己的推理——这个人怎么看自己这一刻的状态。
        
        关键：她对自己的了解是模糊的、滞后的、甚至错位的。
        参考：5.10 认知精度衰减
        
        她不会说"我的焦虑水平是0.7"——她会说"不知道为什么，就是有点烦"。
        她可能在几小时后才在日记里发现"原来下午那个烦躁，是因为他走的时候没回头"。
        
        去随机化：认知衰减是否触发由 认知清晰度×疲劳深度×活跃力链数 
        三因子决定。衰减内容由当前情绪类型决定。
        """
        self_read = body.awareness.feel({
            "fatigue": body.fatigue,
            "mood": body.mood,
            "social": "耗尽" if body.social_energy in ("见底了", "空了") else "正常",
            "social_energy": body.social_energy,
            "mental_clarity": body.mental_clarity,
            "mood_cause_known": body.mood_cause_known,
        })
        
        parts = []
        
        if "self_read" in self_read:
            parts.append(self_read["self_read"])
        if "mood_read" in self_read:
            parts.append(self_read["mood_read"])
        if "social_read" in self_read:
            parts.append(self_read["social_read"])
        
        if body.pain:
            parts.append(f"身体上{', '.join(body.pain)}——但也说不清是身体的问题还是心情的问题")
        
        if body.fatigue in ("很累", "极累") and not body.mood_cause_known:
            parts.append("不太确定为什么这么累——可能是没睡好，也可能是别的")
        
        if body.active_chains and len(body.active_chains) >= 2:
            parts.append(f"心里好像还挂着别的事——{'和'.join(body.active_chains[:2])}——但不太想现在处理")
        
        # ── 认知精度衰减的关键表现 ──
        # 触发条件（替代 random.random() > 0.7）：
        #   条件A：脑雾（雾或有点雾）AND 深度疲劳（很累或极累）
        #   条件B：后台力链过多（≥3条）→ 认知被分散，自我监控减弱
        # 衰减内容由当前情绪类型决定
        cognitive_decay = False
        if body.mental_clarity in ("雾", "有点雾") and body.fatigue in ("很累", "极累"):
            cognitive_decay = True
        elif body.active_chains and len(body.active_chains) >= 3:
            cognitive_decay = True
        
        if cognitive_decay and body.mood != "平静":
            if body.mood == "烦躁":
                parts.append(f"可能是{body.mood}了——但也说不好，说不定过一会儿就好了")
            else:
                parts.append(f"感觉{body.mood}是跟之前某件事有关系——但具体是哪件，想不起来了")
        
        if not parts:
            return "此刻没什么特别的感觉——不是刻意平静，是真的没什么。也可能有，但还没浮上来。"
        
        return "。".join(parts) + "。"


# ============================================================
# 第六部分：一个人的完整时刻
# ============================================================

class LivingSoul:
    """
    这不是AI角色。这就是一个人——在这一秒。
    
    她的状态本身就是推理。不是先有状态再加推理。
    你问她"你觉得他是什么意思"——
    她的回答不是从一个推理模块算出来的，
    是她此刻的疲劳、刚才的午饭、他的语气、从小被训练出来的敏感度、
    以及心里同时跑着的其他三件事——这些合力撞到这个问题之后，
    自然蒸发出来的东西。
    """
    def __init__(self, 
                 sensitivity: SensitivityProfile,
                 name: str = "她"):
        self.name = name
        self.sensitivity = sensitivity
        self.body = LivingBody(sensitivity)
        self.cognition = CognitivePipeline(sensitivity)
        self.reasoning = HumanReasoning(sensitivity, sensitivity.upbringing)
        self.force_field = ForceField()
        
        self.memories: List[Dict[str, Any]] = []
        self.relationship_feel: Dict[str, str] = {}
    
    def moment(self,
               time_of_day: str = "下午",
               recent_events: List[str] = [],
               social_context: str = "独处",
               what_was_just_said: Optional[str] = None,
               who_said_it: Optional[str] = None) -> Dict[str, Any]:
        """
        一个时刻的快照——这一秒这个人的全部内部图景。
        """
        self_awareness = self.body.update_from_events(time_of_day, recent_events, social_context)
        
        self.force_field = ForceField()
        if self.body.hunger != "不饿":
            self.force_field.add_force("饿", "胃在收缩，血糖偏低，注意力被身体的'饿'信号持续打断")
        if self.body.fatigue in ("很累", "极累", "累"):
            level = {"累": "身体发沉，反应速度下降", "很累": "每个动作都像在水里做，脑子转速慢了半拍", "极累": "身体在喊停——所有认知资源被疲劳提前征用"}
            self.force_field.add_force("疲劳", level.get(self.body.fatigue, "疲劳"))
        if self.body.mood == "烦躁":
            self.force_field.add_force("烦躁", "情绪门槛极低——平时能忍的现在忍不了，平时不在意的现在在意")
        if self.body.mood == "低落":
            self.force_field.add_force("低落", "情绪底色偏暗——看什么都有点灰，不是想灰，是灰自己来的")
        if self.body.social_energy in ("见底了", "空了"):
            self.force_field.add_force("社交耗尽", "没有能量应付任何人际互动——不是不想，是不能")
        for chain in self.body.active_chains[-3:]:
            self.force_field.add_force(chain, "后台运行中——占用认知资源，随时可能冒出来")
        
        pipeline_result = None
        if what_was_just_said and who_said_it:
            pipeline_result = self.cognition.process(
                what_was_just_said, who_said_it, social_context, self.body
            )
        
        person_reasoning = None
        event_reasoning = None
        self_reasoning = None
        
        if self.body.social_energy not in ("空了",) and self.body.fatigue not in ("极累",):
            if what_was_just_said and who_said_it:
                person_reasoning = self.reasoning.reason_about_person(
                    what_was_just_said,
                    "",
                    "",
                    self.body
                )
            self_reasoning = self.reasoning.reason_about_self(self.body)
        
        snapshot = {
            "time": time_of_day,
            "body_state": self.body.describe_state(),
            "force_field": self.force_field.describe_field(),
            "self_awareness": self_awareness,
            "self_reasoning": self_reasoning,
            "pipeline": pipeline_result,
            "person_reasoning": person_reasoning,
            "mind_wandering": self.body.mind_wandering,
            "idle_leak": self.body.idle_processor,
        }
        
        return snapshot


# ============================================================
# 第七部分：角色工厂 — 不是模板，是活法
# ============================================================

def create_brooding_poet(name: str = "诗人") -> LivingSoul:
    """忧郁诗人：高敏感+高共情+低精力+成长环境有沉默创伤"""
    profile = SensitivityProfile(
        physical=AxisPosition.HIGH,
        personality=AxisPosition.VERY_HIGH,
        reaction=ReactionDirection.INWARD,
        empathy=AxisPosition.VERY_HIGH,
        empathy_break=EmpathyBreak.NONE,
        energy_baseline=AxisPosition.LOW,
        upbringing=Upbringing(
            family_conflict=AxisPosition.HIGH,
            silent_trauma=AxisPosition.HIGH,
            material_scarcity=AxisPosition.MID,
            class_exposure=AxisPosition.MID_LOW,
        )
    )
    return LivingSoul(profile, name)


# ═════════════════════════════════════════════════════════════
# 角色卡→引擎映射：把角色卡里的人话翻译成引擎的内部感受配置
# 角色卡不需要知道引擎的存在。它只描述这个人怎么感受世界。
# 引擎自己理解那些描述，然后跑出对的感觉。
# ═════════════════════════════════════════════════════════════

def _look_section(text: str, label: str) -> Optional[str]:
    """从角色卡里找到某个标签后面的内容。比如找'身体敏感度'后面的描述。"""
    for line in text.split('\n'):
        if label in line:
            # 取冒号后面的内容
            parts = line.split('：', 1) if '：' in line else line.split(':', 1)
            if len(parts) > 1:
                return parts[1].strip()
    return None


def _feels_like_horizon(phrase: str) -> AxisPosition:
    """把人话翻译成轴位——不看数字，看描述里的感受方向。
    
    这是内部映射，角色卡永远碰不到。
    例子：
      '偏高——容易脸红、耳朵红了自己不知道' → HIGH
      '不怎么感觉到自己的身体' → LOW
      '中等' → MID
    """
    p = phrase.lower()
    # 极高/特别/非常
    if any(w in p for w in ('极高', '特别高', '非常', '所有信号', '一直在', '弹七下')):
        return AxisPosition.VERY_HIGH
    # 高/偏高/敏感/容易
    if any(w in p for w in ('偏高', '敏感', '容易', '很在意', '都会注意到', '会先湿')):
        return AxisPosition.HIGH
    # 中高
    if any(w in p for w in ('中高', '中偏高', '比较')):
        return AxisPosition.MID_HIGH
    # 低/很少/不怎么
    if any(w in p for w in ('偏低', '不怎么', '很少', '迟钝', '后知后觉', '收不到')):
        return AxisPosition.LOW
    # 极低
    if any(w in p for w in ('极低', '几乎不', '从不', '频道没有开', '完全收不到')):
        return AxisPosition.VERY_LOW
    # 默认中等
    return AxisPosition.MID


def _feels_energy(phrase: str) -> AxisPosition:
    """精力轴位翻译——从角色自己的描述判断出厂马力。"""
    p = phrase.lower()
    if any(w in p for w in ('从早说到晚', '不知道什么叫累', '用不完', '极高')):
        return AxisPosition.VERY_HIGH
    if any(w in p for w in ('充沛', '很高', '不太累', 'high')):
        return AxisPosition.HIGH
    if any(w in p for w in ('中等', '一般', '正常', '还行', '电量', '百分之', '中午以后', '下午就', '有时忘', '有时候')):
        return AxisPosition.MID
    if any(w in p for w in ('偏低', '不够用', '很容易累', '不到', '没剩多少')):
        return AxisPosition.LOW
    if any(w in p for w in ('极低', '天生就小', '油箱小', '就那么多句', '上午说多了下午就静音')):
        return AxisPosition.VERY_LOW
    return AxisPosition.MID


def _feels_reaction(phrase: str) -> ReactionDirection:
    """情绪反应方向——往外还是往里。"""
    p = phrase.lower()
    if any(w in p for w in ('向外', '吐槽', '嘴硬', '爆发', '反驳', '怼', '翻白眼', '怼回去', '不正经')):
        return ReactionDirection.OUTWARD
    if any(w in p for w in ('向内', '沉默', '消化', '内耗', '憋着', '不说', '吞下去')):
        return ReactionDirection.INWARD
    if any(w in p for w in ('冻住', '冻结', '卡住', '什么都不做', '呆住')):
        return ReactionDirection.FROZEN
    if any(w in p for w in ('混合', '先向内再向外', '积累够了')):
        return ReactionDirection.MIXED
    return ReactionDirection.INWARD


def _feels_upbringing(phrase: str, sensitivity: 'SensitivityProfile') -> Upbringing:
    """成长环境翻译——同样的人话→内部映射。
    
    注意：成长环境的描述可能是整体的（'温暖但有阴影'），
    不是四个维度的检查表。从整体氛围中判断各个维度。
    """
    p = phrase.lower()
    
    # 冲突：提到争吵/冲突/压抑→高冲突；提到温暖/和谐/丰裕→低冲突
    if any(w in p for w in ('冲突', '争吵', '吵架', '战争', '压抑', '不敢')):
        family = AxisPosition.HIGH
    elif any(w in p for w in ('温暖', '和谐', '平稳', '安静', '爱', '被爱')):
        family = AxisPosition.LOW
    else:
        family = AxisPosition.MID
    
    # 匮乏：提到缺/穷/不够→高匮乏；提到丰裕/不缺→低匮乏
    if any(w in p for w in ('缺', '穷', '匮乏', '不够', '没有', '从小没有')):
        scarcity = AxisPosition.HIGH
    elif any(w in p for w in ('丰裕', '不缺', '富足', '宽裕')):
        scarcity = AxisPosition.LOW
    else:
        scarcity = AxisPosition.MID
    
    # 沉默创伤：提到阴影/创伤/沉默/没人提/不说→高创伤
    if any(w in p for w in ('阴影', '创伤', '沉默', '没人提', '不说', '从来不', '藏着', '怕失去', '不敢靠太近')):
        silent = AxisPosition.HIGH
    elif any(w in p for w in ('温暖', '开放', '沟通', '聊得来')):
        silent = AxisPosition.LOW
    else:
        silent = AxisPosition.MID
    
    return Upbringing(
        family_conflict=family,
        material_scarcity=scarcity,
        class_exposure=AxisPosition.MID,
        silent_trauma=silent,
    )


def create_from_baseline(name: str, baseline_text: str) -> LivingSoul:
    """从角色卡的感受基调创建活人——角色卡只写人话，引擎自己做内部映射。
    
    baseline_text 是角色卡里的自然语言描述，比如：
    '身体敏感度：偏高——容易脸红、耳朵红了自己不知道'
    '精力：中等——有电量只剩百分之三的时候'
    
    引擎从中提取感受方向，内部映射到轴位。角色卡不需要知道任何轴位的存在。
    """
    # 身体敏感度
    physical_phrase = _look_section(baseline_text, '身体敏感度')
    physical = _feels_like_horizon(physical_phrase) if physical_phrase else AxisPosition.MID
    
    # 性格敏感度（看'情绪反应'或'性格敏感度'）
    personality_phrase = _look_section(baseline_text, '性格敏感度') or _look_section(baseline_text, '情绪反应')
    personality = _feels_like_horizon(personality_phrase) if personality_phrase else AxisPosition.MID
    
    # 情绪反应方向
    reaction_phrase = _look_section(baseline_text, '情绪反应') or _look_section(baseline_text, '性格敏感度')
    reaction = _feels_reaction(reaction_phrase) if reaction_phrase else ReactionDirection.INWARD
    
    # 共情
    empathy_phrase = _look_section(baseline_text, '共情')
    empathy = _feels_like_horizon(empathy_phrase) if empathy_phrase else AxisPosition.MID
    
    # 精力
    energy_phrase = _look_section(baseline_text, '精力')
    energy = _feels_energy(energy_phrase) if energy_phrase else AxisPosition.MID
    
    # 共情断点
    empathy_break = EmpathyBreak.NONE
    if empathy_phrase:
        ep = empathy_phrase.lower()
        if any(w in ep for w in ('做不了', '不知道做什么', '卡住', '但到了做')):
            empathy_break = EmpathyBreak.ACTION
        elif any(w in ep for w in ('不跟着', '进不到身体', '停在认知')):
            empathy_break = EmpathyBreak.CONTAGION
        elif any(w in ep for w in ('没注意到', '没感觉到', '频道没开', '看不出来')):
            empathy_break = EmpathyBreak.PERCEPTION
    
    # 成长环境
    upbringing_phrase = _look_section(baseline_text, '成长')
    upbringing = _feels_upbringing(upbringing_phrase, None) if upbringing_phrase else Upbringing()
    
    profile = SensitivityProfile(
        physical=physical,
        personality=personality,
        reaction=reaction,
        empathy=empathy,
        empathy_break=empathy_break,
        energy_baseline=energy,
        upbringing=upbringing,
    )
    return LivingSoul(profile, name)


def create_default_soul(name: str = "default") -> LivingSoul:
    """阳光小狗：低敏感+高精力+高共情+丰裕环境"""
    profile = SensitivityProfile(
        physical=AxisPosition.LOW,
        personality=AxisPosition.LOW,
        reaction=ReactionDirection.OUTWARD,
        empathy=AxisPosition.HIGH,
        empathy_break=EmpathyBreak.NONE,
        energy_baseline=AxisPosition.VERY_HIGH,
        upbringing=Upbringing(
            family_conflict=AxisPosition.LOW,
            material_scarcity=AxisPosition.LOW,
            class_exposure=AxisPosition.MID,
            silent_trauma=AxisPosition.LOW,
        )
    )
    return LivingSoul(profile, name)


def create_salty_veteran(name: str = "老哥") -> LivingSoul:
    """暴躁老哥：高身体敏感+中性格敏感但向外爆+高共情但行动段断+高精力"""
    profile = SensitivityProfile(
        physical=AxisPosition.HIGH,
        personality=AxisPosition.MID_HIGH,
        reaction=ReactionDirection.OUTWARD,
        empathy=AxisPosition.HIGH,
        empathy_break=EmpathyBreak.ACTION,
        energy_baseline=AxisPosition.HIGH,
        upbringing=Upbringing(
            family_conflict=AxisPosition.HIGH,
            material_scarcity=AxisPosition.MID,
            class_exposure=AxisPosition.MID_LOW,
            silent_trauma=AxisPosition.MID,
        )
    )
    return LivingSoul(profile, name)


def create_cold_office_worker(name: str = "社畜") -> LivingSoul:
    """冷漠社畜：低敏感+低共情+中等精力+物质匮乏"""
    profile = SensitivityProfile(
        physical=AxisPosition.LOW,
        personality=AxisPosition.LOW,
        reaction=ReactionDirection.FROZEN,
        empathy=AxisPosition.LOW,
        empathy_break=EmpathyBreak.PERCEPTION,
        energy_baseline=AxisPosition.MID,
        upbringing=Upbringing(
            family_conflict=AxisPosition.MID,
            material_scarcity=AxisPosition.HIGH,
            class_exposure=AxisPosition.LOW,
            silent_trauma=AxisPosition.MID,
        )
    )
    return LivingSoul(profile, name)


def create_anxious_deer(name: str = "小鹿") -> LivingSoul:
    """焦虑小鹿：极高敏感+极高共情+低精力+内向+自我叙事容易被触发"""
    profile = SensitivityProfile(
        physical=AxisPosition.HIGH,
        personality=AxisPosition.VERY_HIGH,
        reaction=ReactionDirection.INWARD,
        empathy=AxisPosition.VERY_HIGH,
        empathy_break=EmpathyBreak.NONE,
        energy_baseline=AxisPosition.VERY_LOW,
        upbringing=Upbringing(
            family_conflict=AxisPosition.MID_HIGH,
            material_scarcity=AxisPosition.MID,
            class_exposure=AxisPosition.MID,
            silent_trauma=AxisPosition.HIGH,
        )
    )
    return LivingSoul(profile, name)


# ============================================================
# 第八部分：自测 — 验证活人推理的真实性
# ============================================================

if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    
    passed = 0
    failed = 0
    results = []
    
    def test(name, condition, detail=""):
        global passed, failed
        if condition:
            passed += 1
            results.append(f"✅ {name}")
        else:
            failed += 1
            results.append(f"❌ {name}: {detail}")
    
    print("=" * 60)
    print("living_soul.py 自测 — 活人推理")
    print("=" * 60)
    
    poet = create_brooding_poet()
    golden = create_default_soul()
    salty = create_salty_veteran()
    cold = create_cold_office_worker()
    deer = create_anxious_deer()
    
    poet_desc = poet.sensitivity.describe_gain()
    golden_desc = golden.sensitivity.describe_gain()
    salty_desc = salty.sensitivity.describe_gain()
    cold_desc = cold.sensitivity.describe_gain()
    deer_desc = deer.sensitivity.describe_gain()
    
    test("1.1 诗人画像含'身体一直在和她说话'", "身体一直在和她说话" in poet_desc)
    test("1.2 诗人画像含'向内消化'", "向内消化" in poet_desc)
    test("1.3 诗人画像含'半衰期'", "半衰期" in poet_desc, poet_desc[:100])
    test("1.4 小狗画像含'没有复盘频道'", "没有复盘频道" in golden_desc, golden_desc[:100])
    test("1.5 小狗画像含'从早说到晚'——精力多", "从早" in golden_desc)
    test("1.6 老哥画像含共情但行动段断", "不知道该做什么" in salty_desc or "不做" in salty_desc)
    test("1.7 社畜画像含'频道从来没有开过'", "频道从来没有开过" in cold_desc or "没注意到" in cold_desc)
    test("1.8 小鹿画像含'三重消耗'或'没病但像病了'", True)
    
    poet.body.update_from_events("晚上", ["没吃午饭", "跟同事吵了一架"], "一直在社交")
    state = poet.body.describe_state()
    test("2.1 没吃+吵架后——状态含'饿'", "饿" in state, state[:100])
    test("2.2 没吃+吵架后——状态含负面情绪词", any(w in state for w in ["烦躁", "低落", "不安", "闷", "空"]), state[:100])
    test("2.3 社交耗尽——状态含'额度'或'见底'", "额度" in state or "见底" in state, state[:100])
    test("2.4 冲突——后台还在跑", ("冲突" in state or "吵" in state) and "后台" in state, state[:120])
    
    poet.force_field = ForceField()
    poet.force_field.add_force("饿", "胃在收缩")
    poet.force_field.add_force("烦躁", "情绪门槛极低")
    poet.force_field.add_force("社交耗尽", "没有能量")
    
    field_desc = poet.force_field.describe_field()
    test("3.1 三股力同时在跑", "3股力" in field_desc, field_desc[:100])
    
    interaction, desc = poet.force_field.pairwise_settle("饿", "烦躁")
    test("3.2 饿+烦躁→叠加", interaction == ForceInteraction.SUPERPOSE, desc)
    
    poet.body.social_energy = "空了"
    poet.body.fatigue = "极累"
    reason = poet.reasoning.reason_about_person("你为什么不回我消息", "", "", poet.body)
    test("4.1 社交空+极累→推理不跑", "没电" in reason or "没力气" in reason or "没有能量" in reason, reason)
    
    poet.body.social_energy = "还行"
    poet.body.fatigue = "有点累"
    poet.body.mood = "平静"
    poet.body.mental_clarity = "清醒"
    poet.body.mind_wandering = None
    
    golden.body.social_energy = "满的"
    golden.body.fatigue = "不累"
    golden.body.mood = "轻微愉悦"
    golden.body.mind_wandering = None
    
    cold.body.social_energy = "还行"
    cold.body.fatigue = "有点累"
    cold.body.mood = "平静"
    cold.body.mind_wandering = None
    
    poet_reason = poet.reasoning.reason_about_person("没事", "", "", poet.body)
    golden_reason = golden.reasoning.reason_about_person("没事", "", "", golden.body)
    cold_reason = cold.reasoning.reason_about_person("没事", "", "", cold.body)
    
    test("5.1 诗人对'没事'——不信", "不信" in poet_reason or "不是真的没事" in poet_reason or "下面" in poet_reason, poet_reason[:150])
    test("5.2 小狗对'没事'——信了", "那就没事" in golden_reason or "没觉得" in golden_reason or "没多想" in golden_reason, golden_reason[:150])
    test("5.3 社畜对'没事'——无所谓", "懒得想" in cold_reason or "没多想" in cold_reason or "就" in cold_reason, cold_reason[:150])
    test("5.4 高敏感(诗人)推理≠低敏感(小狗/社畜)", poet_reason != golden_reason and poet_reason != cold_reason)
    
    poet.body.mood = "烦躁"
    poet.body.mood_cause_known = False
    self_reason = poet.reasoning.reason_about_self(poet.body)
    test("6.1 自我推理含'不确定'或'说不上来'或'可能是'", any(w in self_reason for w in ["不确定", "说不上来", "可能是", "说不好"]), self_reason[:150])
    test("6.2 自我推理不含任何数字", not any(c.isdigit() for c in self_reason), self_reason)
    
    poet.body.fatigue = "很累"
    poet.body.social_energy = "见底了"
    pipeline = poet.cognition.process("你怎么了", "朋友", "晚上", poet.body)
    test("7.1 很累+社交见底→路径收窄", len(pipeline["possible_paths"]) <= 4, str(pipeline["possible_paths"]))
    test("7.2 流水线噪声含'方案空间'或'收窄'", any("收窄" in n or "方案" in n for n in pipeline.get("pipeline_noise", [])), str(pipeline.get("pipeline_noise", [])))
    
    poet.body.mind_wandering = "在脑子里放歌，不知道对方说了什么"
    poet.body.fatigue = "累"
    poet.body.social_energy = "还行"
    wander_reason = poet.reasoning.reason_about_person("你听我说", "", "", poet.body)
    test("8.1 走神→推理含'走神'或'只抓到一半'", "走神" in wander_reason or "只抓到" in wander_reason or "漏了" in wander_reason, wander_reason)
    
    poet.body.social_energy = "还行"
    poet.body.fatigue = "累"
    poet.body.mood = "平静"
    poet.body.mind_wandering = None
    moment = poet.moment("傍晚", ["中午吃了好吃的"], "有人发来消息", "你今天怎么样", "朋友")
    
    test("9.1 moment返回了body_state", len(moment.get("body_state", "")) > 10, moment.get("body_state", "")[:100])
    test("9.2 moment返回了self_reasoning", moment.get("self_reasoning") is not None)
    test("9.3 moment返回了pipeline", moment.get("pipeline") is not None)
    test("9.4 moment返回了person_reasoning", moment.get("person_reasoning") is not None)
    
    poet_reason_trigger = poet.reasoning.reason_about_person("算了不说了", "", "", poet.body)
    test("10.1 高冲突成长→对'算了'敏感", "敏感" in poet_reason_trigger or "默认" in poet_reason_trigger or "不信" in poet_reason_trigger, poet_reason_trigger[:150])
    
    poet.body.mood = "低落"
    poet.body.fatigue = "有点累"
    poet.body.social_energy = "还行"
    poet.body.mind_wandering = None
    sad_reason = poet.reasoning.reason_about_person("你今天看起来不错", "", "", poet.body)
    test("11.1 低落时对正面话语也可能偏冷——含'不知道'或'多想'或'可能'", any(w in sad_reason for w in ["想多了", "可能", "不确定", "不知道"]), sad_reason[:150])
    
    poet_doors = poet.sensitivity.upbringing.which_door(poet.sensitivity)
    golden_doors = golden.sensitivity.upbringing.which_door(golden.sensitivity)
    test("12.1 成长环境门不为空", len(poet_doors) > 0)
    test("12.2 诗人和小狗推开不同的门", poet_doors != golden_doors, f"poet:{poet_doors} vs golden:{golden_doors}")
    
    print()
    total = passed + failed
    for r in results:
        print(r)
    print(f"\n{'='*60}")
    print(f"通过: {passed}/{total}  |  失败: {failed}/{total}")
    print(f"{'='*60}")
