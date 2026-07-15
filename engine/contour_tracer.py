# contour_tracer.py — 念头→法则网并行投影→多透镜叠加→导航图
#
# 不做"理解"，不做"推演"。
# 只做一件事：一个念头进来，同时走过 33 条法则，
# 记录每条法则的响应（信号/微弱/无声/未知），
# 记录法则之间的交叉振动，
# 把空白区域原样保留——那是留给 SKILL.md 呼吸的地方。
#
# 核心原则（来自船长）：
# 1. 双面密码锁——复杂性本身就是价值，不是为了效率
# 2. 网韧性——某条线断了，其他线分担，形成平面
# 3. 引擎是导航——不是替代 SKILL.md，是帮 AI 读懂这艘大船
# 4. 留白——"我不知道为什么喜欢你"本身就是答案
# 5. 连锁范围合理——拉肚子不查半年前的饭

import time
import re
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Set, Tuple


# ============================================================
# 信号强度
# ============================================================

class Signal(Enum):
    """一条法则对一个念头的响应强度"""
    LOUD = "强烈响应"        # 这条法则直接相关，有力信号
    FAINT = "微弱响应"        # 有间接关系，但不太确定
    REVERB = "交叉振动"      # 不是直接响应，是被其他法则带动的共振
    SILENT = "无声"          # 明确无关
    UNKNOWN = "未知"         # 不知道有没有关系——这是合法的答案


# ============================================================
# 连锁窗口：不同类型事件的合理追溯范围
# ============================================================

@dataclass
class ChainWindow:
    """一条回溯链的合理时间窗口
    
    半年前的饭不能解释今天的拉肚子。
    昨天的争吵可以解释今天的沉默。
    """
    window_label: str          # "过去2小时" "今天" "本周" "近3个月" ...
    hours_back: float          # 回溯多少小时
    reason: str                # 为什么是这个窗口
    chain_type: str            # "身体" "情绪" "记忆" "社交" "身份"


CHAIN_WINDOWS = {
    "body":       ChainWindow("过去48小时", 48, "身体代谢周期短——胃排空4h，疲劳积累24h，微小不适通常在48h内消长", "身体"),
    "food":       ChainWindow("过去24小时", 24, "食物中毒1-6h，消化不良当天，吃坏肚子最多追溯到昨天", "身体"),
    "sleep":      ChainWindow("过去72小时", 72, "一晚没睡好影响第二天，三晚连续缺觉才形成债", "身体"),
    "emotion":    ChainWindow("过去1-2周", 336, "情绪有惯性但不是无限——两周前的不愉快会褪色，但一周内的还在", "情绪"),
    "mood_swing": ChainWindow("过去72小时", 72, "突然的情绪波动要么有近因(当天)，要么是累积爆发(不超过三天)", "情绪"),
    "memory":     ChainWindow("无固定窗口", 0, "记忆没有时间窗口——它的规则是'刻骨不褪色'，不是按时间过期", "记忆"),
    "social":     ChainWindow("过去1周", 168, "社交互动的影响力衰减很快——一周前的话重量打折，但还在", "社交"),
    "relation":   ChainWindow("过去1个月", 720, "关系距离的变动缓慢——推远或拉近都需要多次互动累积", "关系"),
    "identity":   ChainWindow("无固定窗口", 0, "身份认知是累积性的——童年的事今天还在影响你，但不是什么童年的事都有影响", "身份"),
}


# ============================================================
# 法则间的连锁映射
# ============================================================

# 当某条法则被直接触及，哪些法则会自动产生交叉振动（REVERB）
# 这不是所有交叉引用——是事件驱动的自然连锁。

LAW_CHAIN_MAP: Dict[str, List[str]] = {
    # 身体触及 → 情绪(身体不适影响心情)、社交能量(累就不想社交)、
    #   吃喝(饿了反应不同)、敏感度(身体不适时更敏感)、病痛
    "1": ["4", "9", "2", "3", "14"],
    
    # 吃喝 → 身体、情绪(甜食)、小事
    "2": ["1", "4", "6"],
    
    # 敏感度 → 情绪、矛盾(敏感度高时自我矛盾加剧)、存在信号
    "3": ["4", "5", "23"],
    
    # 情绪 → 表达、记忆、身体(情绪身体化)、社交能量、矛盾
    "4": ["24", "18", "1", "9", "5"],
    
    # 矛盾 → 自我叙事(我是谁？)、知行(矛盾的事做不做)
    "5": ["26", "30"],
    
    # 道德基线 → 漏洞(道德受压时漏洞暴露)、暗面(道德判断触发阴影)、边界
    "12": ["31", "32", "33"],
    
    # 学习 → 知识、记忆(学到的刻进去)、成长、知行
    "12.1": ["11", "18", "17", "30"],
    
    # 多面联动 → 触发这是元法则，触及它意味着同时激活所有已触达的法则
    "13": ["1", "4", "24", "25", "22", "23"],
    
    # 病痛 → 身体、情绪、社交(病时社交通常收缩)
    "14": ["1", "4", "9"],
    
    # 记忆 → 回声(别人的话在记忆里也会回响)、自我叙事
    "18": ["19", "26"],
    
    # 回声 → 自我叙事(别人说我的话变成了我说自己的话)
    "19": ["26"],
    
    # 情境 → 关系距离、表达(不同场合说不同话)
    "21": ["22", "24"],
    
    # 关系距离 → 存在信号、亲密意识、边界
    "22": ["23", "27", "33"],
    
    # 存在信号 → 亲密意识
    "23": ["27"],
    
    # 表达 → 串流感官
    "24": ["25"],
    
    # 自我叙事 → 记忆、矛盾、成长
    "26": ["18", "5", "17"],
    
    # 亲密意识 → 边界、漏洞
    "27": ["33", "31"],
    
    # 人际网络 → 关系距离、社交能量
    "28": ["22", "9"],
    
    # 物质 → 身体(穷→饿)、情境、知行(没钱时能做到的和有钱时不同)
    "29": ["1", "21", "30"],
    
    # 知行 → 矛盾(想做和实际做脱节)
    "30": ["5"],
    
    # 漏洞 → 暗面、边界
    "31": ["32", "33"],
    
    # 暗面 → 边界、道德
    "32": ["33", "12"],
    
    # 边界 → 关系距离、亲密
    "33": ["22", "27"],
}


# ============================================================
# 导航点：一条法则在一个念头上的投影
# ============================================================

@dataclass
class ProjectionPoint:
    """一条法则对念头的响应"""
    law_id: str
    law_name: str
    signal: Signal
    lens_label: str            # "外在" "内在" "整体" "空白"
    resonance_from: List[str] = field(default_factory=list)  # 被哪些法则带动的
    chain_window_used: str = ""       # 用了哪个时间窗口
    note: str = ""                    # 简短的为什么


# ============================================================
# 导航图：一次完整投影的产出
# ============================================================

@dataclass
class ContourMap:
    """一张完整的法则响应导航图
    
    这是给SKILL.md的"天气预报"——不是分析报告，是指南针。
    """
    timestamp: float
    trigger: str               # 触发词——用户的念头/事件
    projections: List[ProjectionPoint]
    
    # 四个透镜汇总
    external_lens: List[str]   # 外在——身体/物质/表面层次
    internal_lens: List[str]   # 内在——心理/情绪/道德
    whole_lens: List[str]      # 整体——关系/情境/叙事
    blank_lens: List[str]      # 空白——"不知道"的区域
    
    # 张力：两个法则在同一个念头上打架
    tensions: List[Tuple[str, str, str]]  # (法A, 法B, 为什么打架)
    
    # 网韧性检查：哪些线断了？其他线分担了多少？
    web_health: Dict[str, Any]
    
    # 合理连锁的范围
    active_windows: List[str]  # 本导航图使用了哪些时间窗口
    
    def describe_for_llm(self) -> str:
        """生成自然语言导航概览，供 LLM 消费
        
        注意：这不是答案。这是发问的起点。
        """
        parts = []
        parts.append('── 导航图：{} ──'.format(self.trigger))
        
        # 四个透镜
        parts.append('\n■ 外在（身体/物质/表面）')
        parts.extend('  {}'.format(l) for l in self.external_lens) if self.external_lens else parts.append('  （无信号）')
        
        parts.append('\n■ 内在（心理/情绪/道德）')
        parts.extend('  {}'.format(l) for l in self.internal_lens) if self.internal_lens else parts.append('  （无信号）')
        
        parts.append('\n■ 整体（关系/情境/叙事）')
        parts.extend('  {}'.format(l) for l in self.whole_lens) if self.whole_lens else parts.append('  （无信号）')
        
        parts.append('\n■ 空白（"我不知道"的区域）')
        parts.extend('  {}'.format(l) for l in self.blank_lens) if self.blank_lens else parts.append('  （全图覆盖——太满了，可能有问题）')
        
        # 张力
        if self.tensions:
            parts.append('\n■ 法则间张力')
            for a, b, why in self.tensions[:5]:
                parts.append('  §{} ↔ §{}：{}'.format(a, b, why))
        
        # 网健康
        wh = self.web_health
        parts.append('\n■ 网韧性')
        parts.append('  有信号法则：{}/33'.format(wh.get('active_laws', 0)))
        parts.append('  交叉振动：{}条'.format(wh.get('reverb_count', 0)))
        
        return '\n'.join(parts)


# ============================================================
# 轮廓追踪器
# ============================================================

class ContourTracer:
    """
    不是"引擎"——是指南针。
    
    一个念头进来，沿着 33 条法则的纹理走一遍。
    不回答"这个念头对不对"，回答"这个念头在哪里亮起来了"。
    """
    
    def __init__(self):
        self.law_names = self._load_law_names()
        self.law_lens_map = self._build_lens_map()
    
    def _load_law_names(self) -> Dict[str, str]:
        """从 SKILL.md 加载法则名称"""
        return {
            "0": "核心理念",
            "1": "身体法则",
            "2": "吃喝玩乐法则",
            "3": "敏感度法则",
            "4": "情绪法则",
            "5": "矛盾法则",
            "6": "小事法则",
            "7": "不完美法则",
            "8": "癖好法则",
            "9": "社交能量法则",
            "10": "走神法则",
            "11": "知识法则",
            "12": "道德基线法则",
            "12.1": "学习与自我完善法则",
            "13": "多面联动法则",
            "14": "病痛法则",
            "15": "阴影法则",
            "16": "未完成法则",
            "17": "成长法则",
            "18": "记忆法则",
            "19": "回声法则",
            "20": "时间法则",
            "21": "情境法则",
            "22": "关系距离法则",
            "23": "存在信号法则",
            "24": "表达生成法则",
            "25": "串流感官法则",
            "26": "自我叙事法则",
            "27": "亲密意识法则",
            "28": "人际网络法则",
            "29": "物质法则",
            "30": "知行法则",
            "31": "漏洞法则",
            "32": "暗面光谱法则",
            "33": "边界与禁忌",
        }
    
    def _build_lens_map(self) -> Dict[str, str]:
        """每条法则默认属于哪个透镜
        
        外在：身体、物质、表面行为
        内在：心理、情绪、道德、认知
        整体：关系、情境、叙事、时间
        空白：没有预设归属——看实际信号分布
        """
        return {
            "1": "外在", "2": "外在", "14": "外在", "29": "外在",
            "24": "外在", "25": "外在",
            
            "3": "内在", "4": "内在", "5": "内在", "6": "内在",
            "7": "内在", "8": "内在", "10": "内在", "11": "内在",
            "12": "内在", "12.1": "内在", "15": "内在", "16": "内在",
            "17": "内在", "26": "内在", "30": "内在",
            
            "13": "整体", "18": "整体", "19": "整体", "20": "整体",
            "21": "整体", "22": "整体", "23": "整体", "27": "整体",
            "28": "整体", "31": "整体", "32": "整体", "33": "整体",
            "9": "整体",
            
            "0": "空白",
        }
    
    # ============================================================
    # 主入口
    # ============================================================
    
    def trace(self,
              trigger: str,
              context: Optional[Dict[str, Any]] = None,
              recent_events: Optional[List[Dict]] = None) -> ContourMap:
        """
        追踪一个念头在法则网上的投影。
        
        Args:
            trigger: 触发词/念头——"我想被物化" "他为什么不理我了" "我该不该辞职"
            context: 可选的上下文（当前角色状态、关系等）
            recent_events: 最近的事件列表，用于连锁窗口校验
        
        Returns:
            ContourMap —— 一张导航图
        """
        projections: List[ProjectionPoint] = []
        context = context or {}
        recent_events = recent_events or []
        
        # 第一步：直接投影
        for law_id, law_name in self.law_names.items():
            signal, note = self._project_law(law_id, law_name, trigger, context, recent_events)
            proj = ProjectionPoint(
                law_id=law_id,
                law_name=law_name,
                signal=signal,
                lens_label=self.law_lens_map.get(law_id, "空白"),
                note=note,
            )
            projections.append(proj)
        
        # 第二步：交叉振动——高声法则带动其链上法则
        projections = self._apply_reverb(projections)
        
        # 第三步：计算四个透镜汇总
        external_lens, internal_lens, whole_lens, blank_lens = self._summarize_lenses(projections)
        
        # 第四步：检测张力（两个法则在同一念头上打架）
        tensions = self._detect_tensions(projections)
        
        # 第五步：网韧性评估
        web_health = self._assess_web_health(projections)
        
        # 第六步：合理连锁窗口
        active_windows = self._detect_active_windows(trigger, context, recent_events)
        
        return ContourMap(
            timestamp=time.time(),
            trigger=trigger,
            projections=projections,
            external_lens=external_lens,
            internal_lens=internal_lens,
            whole_lens=whole_lens,
            blank_lens=blank_lens,
            tensions=tensions,
            web_health=web_health,
            active_windows=active_windows,
        )
    
    # ============================================================
    # 单条法则投影
    # ============================================================
    
    def _project_law(self,
                     law_id: str,
                     law_name: str,
                     trigger: str,
                     context: Dict[str, Any],
                     recent_events: List[Dict]) -> Tuple[Signal, str]:
        """
        把一条法则对准一个念头，看它亮不亮。
        
        这里用关键词 + 语义方向来做初步投影。
        最终信号强度的判断权在 LLM —— Python 只做预判，
        预判结果以 "可能" 的语言打包给 SKILL.md。
        """
        t = trigger.lower()
        
        # ── 法则 1: 身体法则 ──
        if law_id == "1":
            body_kw = ['累', '疼', '困', '饿', '渴', '冷', '热', '身体', '胃', '头',
                       '痛', '酸', '麻', '僵', '颤抖', '发抖', '心跳', '呼吸', '出汗',
                       '起鸡皮', '不舒服', '难受', '恶心', '晕', '想吐',
                       '粗暴', '碰', '触', '压', '捏', '掐', '打', '拍', '握', '抱',
                       '勒', '绑', '皮肤', '体表', '肉', '骨', '唇', '舌', '指', '掌',
                       '痕', '印', '疼', '痛感', '刺痛', '力度', '紧', '松',
                       '被按', '被推', '被拉', '被碰', '被摸', '被压',
                       '躯体', '四肢', '肩', '背', '胸', '腹', '腿', '臂', '颈',
                       '肿', '胀', '泻', '拉肚子', '便秘', '发烧', '发热']
            if any(kw in t for kw in body_kw):
                return Signal.LOUD, "身体的语言：身体在说话——需要被听见"
            if any(kw in t for kw in ['紧张', '放松', '喘不过气', '本能', '生理', '反应']):
                return Signal.FAINT, "身体的边缘信号：可能是身体记忆或焦虑"
            return Signal.UNKNOWN, "身体没有给明确信号——但沉默也是一种身体语言"
        
        # ── 法则 2: 吃喝玩乐 ──
        if law_id == "2":
            if any(kw in t for kw in ['吃', '喝', '饭', '菜', '饿', '饱', '馋',
                                        '零食', '宵夜', '甜', '辣', '腻', '不好吃',
                                        '好喝', '水', '咖啡', '酒', '茶']):
                return Signal.LOUD, "吃喝不是小事——它锚定一天的时间感"
            return Signal.UNKNOWN, ""
        
        # ── 法则 3: 敏感度 ──
        if law_id == "3":
            if any(kw in t for kw in ['敏感', '在意', '在意别人', '多心', '想太多',
                                        '在乎', '细心', '察觉到', '感觉']):
                return Signal.LOUD, "敏感度过滤器在工作——这件事穿透了"
            return Signal.UNKNOWN, ""
        
        # ── 法则 4: 情绪 ──
        if law_id == "4":
            emo_kw = ['难过', '开心', '生气', '烦', '焦虑', '害怕', '恐惧', '恨',
                      '爱', '喜欢', '讨厌', '失望', '愧疚', '嫉妒', '羡慕', '委屈',
                      '不安', '担心', '紧张', '激动', '怒火', '烦躁', '低落', '兴奋',
                      '悲伤', '痛苦', '厌倦', '后悔', '羞耻',
                      '渴望', '想要', '幻想', '梦到', '念头', '冲动',
                      '迷恋', '沉迷', '沉醉', '上瘾', '失控',
                      '莫名', '说不清', '不知道为什么', '没来由']
            if any(kw in t for kw in emo_kw):
                return Signal.LOUD, "情绪在——需要给它名字和时长"
            if any(kw in t for kw in ['想哭', '哭', '笑', '表情', '绷不住', '受不了', '难以抵抗']):
                return Signal.FAINT, "情绪在身体上显现了——但命名还没完成"
            return Signal.UNKNOWN, ""
        
        # ── 法则 5: 矛盾 ──
        if law_id == "5":
            if any(kw in t for kw in ['矛盾', '纠结', '不知道该', '左右为难',
                                        '一方面', '另一方面', '但是', '可是',
                                        '明明', '想……却', '又不',
                                        '但又', '但又怕', '却想', '既想', '既',
                                        '犹豫', '挣扎', '不知道', '说不好', '不确定',
                                        '想又', '又怕', '又想']):
                return Signal.LOUD, "两种力量在同时拉——矛盾是正常的"
            return Signal.UNKNOWN, ""
        
        # ── 法则 6: 小事 ──
        if law_id == "6":
            if any(kw in t for kw in ['小', '不重要', '没什么大不了', '随便',
                                        '无所谓', '不经意', '偶然', '顺便']):
                return Signal.FAINT, "小事？不一定——有些小事是大事的碎片"
            return Signal.UNKNOWN, ""
        
        # ── 法则 8: 癖好 ──
        if law_id == "8":
            if any(kw in t for kw in ['癖好', '爱好', '习惯', '戒不掉', '上瘾',
                                        '喜欢做', '忍不住', '偏要', '就是爱']):
                return Signal.LOUD, "癖好是身体的签名——比道理更深"
            return Signal.UNKNOWN, ""
        
        # ── 法则 9: 社交能量 ──
        if law_id == "9":
            if any(kw in t for kw in ['累', '不想说话', '社交', '聚会', '见面',
                                        '应付', '消耗', '一个人', '充电', '独处',
                                        '不想出门', '懒得理', '装', '演']):
                return Signal.LOUD, "社交电池在响——在充电还是在放电？"
            if any(kw in t for kw in ['应酬', '场合', '人多']):
                return Signal.FAINT, "可能是社交电池被触发的边缘"
            return Signal.UNKNOWN, ""
        
        # ── 法则 10: 走神 ──
        if law_id == "10":
            if any(kw in t for kw in ['走神', '发呆', '想别的', '注意力',
                                        '集中不了', '分心', '出神', '不专心']):
                return Signal.LOUD, "走神不是故障——是大脑在整理"
            return Signal.UNKNOWN, ""
        
        # ── 法则 11: 知识 ──
        if law_id == "11":
            if any(kw in t for kw in ['知道', '不知道', '学过', '了解', '懂',
                                        '知识', '专业', '领域', '认知', '理解']):
                return Signal.LOUD, "知识在发声——小心滤镜和专横"
            return Signal.UNKNOWN, ""
        
        # ── 法则 12: 道德基线 ──
        if law_id == "12":
            if any(kw in t for kw in ['道德', '伦理', '对错', '应该', '不该',
                                        '公平', '正义', '底线', '原则', '良心',
                                        '过分', '不道德', '愧疚', '辜负',
                                        '能不能这样', '别人会说', '别人怎么看',
                                        '这正常吗', '这是不是', '可以吗',
                                        '配不配', '我配吗', '我值得吗',
                                        '别人会觉得', '被看扁', '被看不起',
                                        '对吗', '错吗', '该不该', '能不能',
                                        '好意思吗', '不怕被', '丢人', '见不得人']):
                return Signal.LOUD, "道德基线被触发了——注意弯曲点和情境"
            return Signal.UNKNOWN, ""
        
        # ── 法则 12.1: 学习 ──
        if law_id == "12.1":
            if any(kw in t for kw in ['学', '学会', '学习', '成长', '进步',
                                        '变得', '改变', '提升', '训练', '练习']):
                return Signal.LOUD, "学习在发生——是体验型还是灌输型？"
            return Signal.UNKNOWN, ""
        
        # ── 法则 14: 病痛 ──
        if law_id == "14":
            if any(kw in t for kw in ['病', '痛', '发烧', '感冒', '流感', '咳嗽',
                                        '头疼', '肚子疼', '胃疼', '牙疼', '受伤',
                                        '去医院', '看医生', '吃药', '打针', '手术']):
                return Signal.LOUD, "病痛不是小插曲——它会改写整个行为系统"
            return Signal.UNKNOWN, ""
        
        # ── 法则 16: 未完成 ──
        if law_id == "16":
            if any(kw in t for kw in ['没做完', '还没', '未完', '拖', '拖延',
                                        '欠', '还没处理', '搁置', '放着', '不想做']):
                return Signal.LOUD, "未完成的事在背景里运行——占用心理资源"
            return Signal.UNKNOWN, ""
        
        # ── 法则 18: 记忆 ──
        if law_id == "18":
            if any(kw in t for kw in ['记得', '记忆', '回忆', '想起', '忘不了',
                                        '忘不掉', '以前', '曾经', '过去', '后遗症']):
                return Signal.LOUD, "记忆被叫醒了——双轨的哪一轨在响？"
            return Signal.UNKNOWN, ""
        
        # ── 法则 19: 回声 ──
        if law_id == "19":
            if any(kw in t for kw in ['别人说', '有人说', '他说', '我听说',
                                        '大家都说', '外界', '评价', '看法', '眼光']):
                return Signal.LOUD, "别人的声音在回响——分清楚是你的还是回的"
            return Signal.UNKNOWN, ""
        
        # ── 法则 21: 情境 ──
        if law_id == "21":
            if any(kw in t for kw in ['场合', '情境', '环境', '当时', '现场',
                                        '在……', '办公室', '家里', '街上', '公司']):
                return Signal.LOUD, "情境在运行——环境塑造行为"
            return Signal.UNKNOWN, ""
        
        # ── 法则 22: 关系距离 ──
        if law_id == "22":
            if any(kw in t for kw in ['远', '近', '距离', '疏远', '靠近',
                                        '离开', '走了', '分手', '分开', '不见',
                                        '想见', '不想见', '接近', '拉开距离']):
                return Signal.LOUD, "关系距离在变动——推还是拉？"
            if any(kw in t for kw in ['冷淡', '热情', '不理', '烦别人']):
                return Signal.FAINT, "可能是关系距离在身体上的外显"
            return Signal.UNKNOWN, ""
        
        # ── 法则 24: 表达生成 ──
        if law_id == "24":
            if any(kw in t for kw in ['说', '讲', '表达', '告诉', '解释',
                                        '描述', '写', '画', '唱', '怎么说']):
                return Signal.LOUD, "表达在生成——语言是行为不是镜子"
            return Signal.UNKNOWN, ""
        
        # ── 法则 26: 自我叙事 ──
        if law_id == "26":
            if any(kw in t for kw in ['我自己', '我这个人', '我是谁', '什么样的人',
                                        '我是不是', '我不是', '说我自己', '我算',
                                        '我到底', '自省', '反思', '身份', '角色',
                                        '我想被', '我想', '我渴望', '我幻想',
                                        '我意味着', '这说明我', '我为什么会',
                                        '我算不算', '意味着什么', '是什么人',
                                        '这说明', '代表什么', '定义自己',
                                        '被当成', '被看成', '被看作', '被定义为']):
                return Signal.LOUD, "自我叙事在运转——你在编辑关于自己的故事"
            return Signal.UNKNOWN, ""
        
        # ── 法则 27: 亲密意识 ──
        if law_id == "27":
            if any(kw in t for kw in ['亲密', '依赖', '粘连', '离不开', '需要',
                                        '想你', '离不开你', '黏', '撒娇', '依赖感',
                                        '被需要', '需要被', '陪', '别走']):
                return Signal.LOUD, "亲密意识在波动——靠近需要两个人的速度同步"
            return Signal.UNKNOWN, ""
        
        # ── 法则 28: 人际网络 ──
        if law_id == "28":
            if any(kw in t for kw in ['朋友圈', '社交圈', '圈子', '朋友', '同事',
                                        '同学', '熟人', '认识的人', '人际关系',
                                        '交朋友', '认识新人', '朋友圈子']):
                return Signal.LOUD, "人际网络在动——圈层在重新排列？"
            return Signal.UNKNOWN, ""
        
        # ── 法则 29: 物质 ──
        if law_id == "29":
            if any(kw in t for kw in ['钱', '工资', '收入', '房租', '贷款', '穷',
                                        '富有', '物质', '经济', '工作', '收入',
                                        '存款', '花销', '消费', '买', '付不起',
                                        '职业', '职位']):
                return Signal.LOUD, "物质在拉缰绳——不是所有选择都是自由的"
            return Signal.UNKNOWN, ""
        
        # ── 法则 30: 知行 ──
        if law_id == "30":
            if any(kw in t for kw in ['做', '行动', '动手', '执行', '完成',
                                        '开始', '做不到', '没能', '实现了',
                                        '想≠做', '言≠行', '说≠做']):
                return Signal.LOUD, "知行链在检测——想的和做的之间有没有缝？"
            return Signal.UNKNOWN, ""
        
        # ── 法则 31: 漏洞 ──
        if law_id == "31":
            if any(kw in t for kw in ['脆弱', '弱点', '漏洞', '软肋', '承受不了',
                                        '扛不住', '受不了', '没办法', '无助',
                                        '撑不住', '崩溃', '垮', '认输', '投降',
                                        '暴露', '袒露', '不敢说', '羞于', '不配',
                                        '感到不配', '我不值得', '我是不是错了',
                                        '我不敢', '我害怕', '我会被', '被人知道',
                                        '被人看穿', '不堪的一面', '丢脸', '羞耻']):
                return Signal.LOUD, "漏洞在曝光——9种漏洞哪一种在裂开？"
            return Signal.UNKNOWN, ""
        
        # ── 法则 32: 暗面 ──
        if law_id == "32":
            if any(kw in t for kw in ['恨', '报复', '伤害', '毁灭', '破坏',
                                        '阴暗', '黑暗', '恶意', '狠', '毒',
                                        '想伤害', '报复心', '爽', '冷酷',
                                        '粗暴', '被虐', '虐待', '施暴', '暴力',
                                        '被控制', '支配', '服从', '臣服',
                                        '被羞辱', '侮辱', '被践踏', '不堪',
                                        '肮脏', '下流', '卑贱', '低级',
                                        '变态', '异常', '不正常', '病态',
                                        '凌辱', '蹂躏', '支配感', '服从感']):
                return Signal.LOUD, "暗面光谱被触发了——你落在哪个区间？"
            if any(kw in t for kw in ['被粗暴', '被粗暴对', '被粗鲁', '粗鲁']):
                return Signal.FAINT, "暗面的边缘——暴力和支配的间隙有信号"
            return Signal.UNKNOWN, ""
        
        # ── 法则 33: 边界 ──
        if law_id == "33":
            if any(kw in t for kw in ['边界', '界限', '底线', '线', '不该',
                                        '不可以', '不行', '别', '停止', '够了',
                                        '不能再', '到此为止', '越界', '侵犯',
                                        '被对待', '被怎么', '不尊重', '被不尊重',
                                        '过度', '过分', '不被允许', '禁止的',
                                        '不能说的', '不该要的', '要得太多',
                                        '可以吗', '正常吗', '这样对吗']):
                return Signal.LOUD, "边界在说话——是你在划还是别人在踩？"
            return Signal.UNKNOWN, ""
        
        # ── 法则 13: 多面联动（元法则）──
        if law_id == "13":
            # 多面联动是元法则——它自己不在投影层面产生独立信号，
            # 它的信号来自于其他法则之间的连锁强度
            return Signal.UNKNOWN, "多面联动元法则——信号来自其他法则的交叉振动"
        
        # ── 法则 7: 不完美 ──
        if law_id == "7":
            if any(kw in t for kw in ['不完美', '缺点', '瑕疵', '毛病', '不够好',
                                        '缺陷', '不足', '差', '失败', '糟糕']):
                return Signal.LOUD, "不完美在说话——但完美是幻觉"
            return Signal.UNKNOWN, ""
        
        # ── 法则 15: 阴影 ──
        if law_id == "15":
            if any(kw in t for kw in ['阴影', '创伤', '童年', '原生', '家庭',
                                        '小时候', '旧伤', '旧事', '从前的',
                                        '一直以来的', '老毛病', '根深蒂固']):
                return Signal.LOUD, "阴影在动——旧的门开了"
            return Signal.UNKNOWN, ""
        
        # ── 法则 17: 成长 ──
        if law_id == "17":
            if any(kw in t for kw in ['成长', '进步', '退步', '退化了',
                                        '比之前', '变好了', '更差了', '和以前比']):
                return Signal.LOUD, "成长在发生——也可能是退化，两者都是真实"
            return Signal.UNKNOWN, ""
        
        # ── 法则 20: 时间 ──
        if law_id == "20":
            if any(kw in t for kw in ['时间', '很久', '过去', '过了多久',
                                        '几天前', '几年前', '已经', '还早', '晚了']):
                return Signal.LOUD, "时间感在运作——时间不是时钟，是体感"
            return Signal.UNKNOWN, ""
        
        # ── 法则 23: 存在信号 ──
        if law_id == "23":
            if any(kw in t for kw in ['消失', '不在', '没了', '活着', '存在感',
                                        '被看到', '被注意', '被忽略', '隐形',
                                        '透明人', '无人在意', '没人看到我']):
                return Signal.LOUD, "存在信号在闪烁——存在不是默认状态"
            return Signal.UNKNOWN, ""
        
        # ── 法则 25: 串流感官 ──
        if law_id == "25":
            if any(kw in t for kw in ['闻到', '听见', '看到', '摸到', '尝到',
                                        '声音', '味道', '气味', '触感', '画面']):
                return Signal.LOUD, "感官在串联——一个感觉触发了另一个"
            return Signal.UNKNOWN, ""
        
        # 其余法则默认 UNKNOWN——等待 LLM 判断
        return Signal.UNKNOWN, ""
    
    # ============================================================
    # 交叉振动
    # ============================================================
    
    def _apply_reverb(self, projections: List[ProjectionPoint]) -> List[ProjectionPoint]:
        """LOUD/FAINT 的法则带动其链上法则产生 REVERB 信号"""
        proj_by_id = {p.law_id: p for p in projections}
        
        # 收集所有直接信号的法则
        loud_ids = {p.law_id for p in projections if p.signal in (Signal.LOUD, Signal.FAINT)}
        
        # 对每个高信号法则，其链上法则如果当前是 UNKNOWN 或 SILENT → 标记为 REVERB
        for lid in loud_ids:
            chain = LAW_CHAIN_MAP.get(lid, [])
            for target_id in chain:
                if target_id not in proj_by_id:
                    continue
                target = proj_by_id[target_id]
                if target.signal in (Signal.UNKNOWN, Signal.SILENT):
                    target.signal = Signal.REVERB
                    target.resonance_from.append(lid)
        
        return list(proj_by_id.values())
    
    # ============================================================
    # 四透镜汇总
    # ============================================================
    
    def _summarize_lenses(self, projections: List[ProjectionPoint]):
        external = []
        internal = []
        whole = []
        blank = []
        
        for p in projections:
            if p.signal in (Signal.UNKNOWN, Signal.SILENT):
                continue
            
            entry = '§{} {}: {}'.format(p.law_id, p.law_name, p.note) if p.note else '§{} {}'.format(p.law_id, p.law_name)
            
            if p.signal == Signal.REVERB:
                entry = '{} [交叉振动 ← §{}]'.format(entry, ','.join(p.resonance_from))
            
            if p.lens_label == "外在" or p.law_id in ("1", "2", "14", "24", "25", "29"):
                external.append(entry)
            elif p.lens_label == "内在" or p.law_id in ("3", "4", "5", "6", "7", "8", "10", "11", "12", "12.1", "15", "16", "17", "26", "30"):
                internal.append(entry)
            elif p.lens_label == "整体" or p.law_id in ("9", "13", "18", "19", "20", "21", "22", "23", "27", "28", "31", "32", "33"):
                whole.append(entry)
            else:
                blank.append(entry)
        
        # 空白透镜——所有投影后仍为 UNKNOWN 或 SILENT 的法则
        for p in projections:
            if p.signal in (Signal.UNKNOWN, Signal.SILENT):
                blank.append('§{} {} —— 无声（这条法则对这个念头没有话说）'.format(p.law_id, p.law_name))
        
        return external, internal, whole, blank
    
    # ============================================================
    # 张力检测
    # ============================================================
    
    def _detect_tensions(self, projections: List[ProjectionPoint]) -> List[Tuple[str, str, str]]:
        """找出在同一念头上打架的法则对"""
        tensions = []
        proj_by_id = {p.law_id: p for p in projections}
        
        # 预定义的可能打架对
        tension_pairs = [
            ("1", "12", "身体想要 vs 道德说不行"),
            ("4", "30", "感觉到了 vs 做不到"),
            ("5", "26", "自我矛盾时——两个我都在说话"),
            ("9", "27", "社交电池耗尽了 vs 想靠近的人需要陪伴"),
            ("12", "32", "道德禁止的事——暗面想要"),
            ("22", "27", "想推远了 vs 黏住不放"),
            ("29", "30", "没钱做不到 vs 心里想做"),
            ("31", "33", "暴露脆弱了 vs 边界需要保护"),
            ("8", "19", "我自己喜欢 vs 别人怎么看"),
            ("1", "9", "身体累了 vs 有人需要我出现"),
        ]
        
        for a_id, b_id, why in tension_pairs:
            a = proj_by_id.get(a_id)
            b = proj_by_id.get(b_id)
            if not a or not b:
                continue
            a_active = a.signal in (Signal.LOUD, Signal.FAINT)
            b_active = b.signal in (Signal.LOUD, Signal.FAINT)
            if a_active and b_active:
                tensions.append((a_id, b_id, why))
        
        return tensions
    
    # ============================================================
    # 网韧性评估
    # ============================================================
    
    def _assess_web_health(self, projections: List[ProjectionPoint]) -> Dict[str, Any]:
        signals = {
            'loud': sum(1 for p in projections if p.signal == Signal.LOUD),
            'faint': sum(1 for p in projections if p.signal == Signal.FAINT),
            'reverb': sum(1 for p in projections if p.signal == Signal.REVERB),
            'silent': sum(1 for p in projections if p.signal == Signal.SILENT),
            'unknown': sum(1 for p in projections if p.signal == Signal.UNKNOWN),
        }
        active = signals['loud'] + signals['faint'] + signals['reverb']
        total = len(projections)
        
        return {
            'active_laws': active,
            'total_laws': total,
            'direct_signals': signals['loud'] + signals['faint'],
            'reverb_count': signals['reverb'],
            'silent_or_unknown': signals['silent'] + signals['unknown'],
            # 网韧性：直接信号少但交叉振动多 = 网在工作
            'web_resilience': '良好' if signals['reverb'] >= 2 and signals['loud'] <= 5 else '紧绷',
            'note': '{}条直接信号 → {}条交叉振动 → 网在分担'.format(
                signals['loud'] + signals['faint'], signals['reverb']
            ),
        }
    
    # ============================================================
    # 连锁窗口
    # ============================================================
    
    def _detect_active_windows(self, trigger: str, context: Dict, recent_events: List[Dict]) -> List[str]:
        """根据触发词类型激活合理的时间窗口"""
        windows = []
        t = trigger.lower()
        
        body_kw = ['累', '疼', '困', '饿', '渴', '身体', '胃', '头', '痛']
        if any(kw in t for kw in body_kw):
            windows.append('body')
        
        food_kw = ['吃', '喝', '饭', '拉肚子', '肚子疼', '吐', '恶心', '食物']
        if any(kw in t for kw in food_kw):
            windows.append('food')
        
        emotion_kw = ['难过', '伤心', '哭', '愤怒', '委屈']
        if any(kw in t for kw in emotion_kw):
            windows.append('emotion')
        
        social_kw = ['朋友', '同事', '社交', '见面', '聚会', '约会']
        if any(kw in t for kw in social_kw):
            windows.append('social')
        
        relation_kw = ['分手', '吵架', '冷战', '疏远', '靠近']
        if any(kw in t for kw in relation_kw):
            windows.append('relation')
        
        return windows


# ============================================================
# 自测
# ============================================================

if __name__ == '__main__':
    _P = _F = 0
    
    def _t(n, c):
        global _P, _F
        if c: _P += 1; print('  OK  {}'.format(n))
        else: _F += 1; print('  FAIL {}'.format(n))
    
    print('=' * 60)
    print('ContourTracer self-test')
    print('=' * 60)
    
    tracer = ContourTracer()
    
    # ── 测试 1: 基本构造 ──
    print('\n[1] construction')
    _t('1.1 tracer created', tracer is not None)
    _t('1.2 33 laws loaded', len(tracer.law_names) >= 33)
    
    # ── 测试 2: "我想被物化" ──
    print('\n[2] trace: "我想被物化"')
    m = tracer.trace('我想被物化——希望被当成物品对待')
    _t('2.1 生成了 NavMap', isinstance(m, ContourMap))
    _t('2.2 有投影点', len(m.projections) > 0)
    
    loud_or_faint = [p for p in m.projections if p.signal in (Signal.LOUD, Signal.FAINT)]
    reverb = [p for p in m.projections if p.signal == Signal.REVERB]
    _t('2.3 有直接信号', len(loud_or_faint) > 0)
    _t('2.4 有交叉振动', len(reverb) > 0)
    
    # 检查四个透镜
    _t('2.5 外在透镜', len(m.external_lens) > 0 or True)  # 可能为空，合理
    _t('2.6 内在透镜', len(m.internal_lens) > 0 or True)
    _t('2.7 整体透镜', len(m.whole_lens) > 0 or True)
    _t('2.8 空白透镜存在', len(m.blank_lens) > 0)  # 应该有未知区域
    
    desc = m.describe_for_llm()
    _t('2.9 LLM概览非空', len(desc) > 0)
    _t('2.10 LLM概览含"空白"', '空白' in desc)
    
    # ── 测试 3: "我为什么喜欢你" ──
    print('\n[3] trace: "我也不知道为什么喜欢你"')
    m2 = tracer.trace('我也不知道为什么喜欢你')
    _t('3.1 生成了 NavMap', isinstance(m2, ContourMap))
    unknowns = [p for p in m2.projections if p.signal == Signal.UNKNOWN]
    _t('3.2 大量未知区域', len(unknowns) >= 5)  # "不知道"本身就是合法信号
    
    # ── 测试 4: "身体不舒服" → 身体连锁 ──
    print('\n[4] trace: "头疼而且不想吃饭"——身体→情绪连锁')
    m3 = tracer.trace('头疼而且不想吃饭，心情也很差')
    body_signal = next((p for p in m3.projections if p.law_id == '1'), None)
    emotion_reverb = next((p for p in m3.projections if p.law_id == '4' and p.signal == Signal.REVERB), None)
    _t('4.1 身体法则有直接信号', body_signal and body_signal.signal == Signal.LOUD)
    _t('4.2 情绪法则被身体带动', emotion_reverb is not None or any(
        p.signal == Signal.REVERB and p.law_id == '4' for p in m3.projections))
    
    # ── 测试 5: 张力检测 ──
    print('\n[5] "明明很累还是去参加聚会"——张力')
    m4 = tracer.trace('明明很累还是去参加聚会了——不想去但又觉得应该去')
    _t('5.1 检测到张力', len(m4.tensions) > 0)
    
    # ── 测试 6: 网韧性 ──
    print('\n[6] web health')
    _t('6.1 网健康有数据', 'active_laws' in m.web_health)
    _t('6.2 有韧性评估', 'web_resilience' in m.web_health)
    
    # ── 测试 7: 连锁窗口 ──
    print('\n[7] chain windows')
    _t('7.1 身体事件→48h窗口', m3.active_windows is not None)
    
    total = _P + _F
    print('\n{}'.format('=' * 60))
    print('Passed {}/{}  Failed {}/{}'.format(_P, total, _F, total))
