# triangle_runtime.py — 三条并行跑道，三角互噬
# v3 — 去随机/去浮点/去感受组装。Python只记录事实。

import time
import json
import os
import sys
import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from collections import deque

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from engine.memory_law34 import MemoryStorage


# ═══════════════════════════════════════
# 共享信号总线
# ═══════════════════════════════════════

@dataclass
class Signal:
    source: str
    target: str
    signal_type: str
    payload: Dict[str, Any] = field(default_factory=dict)
    intensity: float = 0.5
    decay_rate: float = 0.3
    age: int = 0

    def decay(self) -> bool:
        self.age += 1
        self.intensity *= (1 - self.decay_rate)
        return self.intensity < 0.05


class SignalBus:
    def __init__(self, history_size=50):
        self.active: List[Signal] = []
        self.history: deque = deque(maxlen=history_size)
        self.lock = threading.Lock()

    def emit(self, signal: Signal):
        with self.lock:
            self.active.append(signal)
            self.history.append(signal)

    def read(self, target: str, signal_type: Optional[str] = None) -> List[Signal]:
        with self.lock:
            matches = []
            for s in self.active:
                if s.target == target or s.target == '*':
                    if signal_type is None or s.signal_type == signal_type:
                        matches.append(s)
            return matches

    def tick_decay(self):
        with self.lock:
            self.active = [s for s in self.active if not s.decay()]

    def summary(self) -> str:
        with self.lock:
            if not self.active:
                return '信号总线空闲'
            parts = [f'{s.source}→{s.target}[{s.signal_type}]' for s in self.active[:6]]
            return '、'.join(parts)


# ═══════════════════════════════════════
# 跑道基类
# ═══════════════════════════════════════

@dataclass
class LaneSnapshot:
    lane: str
    tick: int
    raw_state: Dict[str, Any]
    signals_emitted: List[Signal]
    signals_received: List[Signal]
    natural_output: str


class BaseLane:
    def __init__(self, name: str, bus: SignalBus):
        self.name = name
        self.bus = bus
        self.tick_count = 0
        self.last_snapshot: Optional[LaneSnapshot] = None

    def tick(self, external_event: Optional[Dict] = None) -> LaneSnapshot:
        self.tick_count += 1
        incoming = self._read_incoming()
        raw_state = self._evolve(incoming, external_event)
        emitted = self._cross_feed(raw_state)
        natural = self._to_natural(raw_state, incoming, emitted)
        snapshot = LaneSnapshot(
            lane=self.name, tick=self.tick_count,
            raw_state=raw_state, signals_emitted=emitted,
            signals_received=incoming, natural_output=natural,
        )
        self.last_snapshot = snapshot
        return snapshot

    def _read_incoming(self) -> List[Signal]:
        return self.bus.read(self.name)

    def _evolve(self, incoming: List[Signal], external_event: Optional[Dict]) -> Dict[str, Any]:
        raise NotImplementedError

    def _cross_feed(self, state: Dict[str, Any]) -> List[Signal]:
        raise NotImplementedError

    def _to_natural(self, state, incoming, emitted) -> str:
        raise NotImplementedError


# ═══════════════════════════════════════
# 跑道一：身体
# ═══════════════════════════════════════

class BodyLane(BaseLane):
    """身体跑道——只追踪事实，不随机、不替角色感受"""

    def __init__(self, bus: SignalBus):
        super().__init__('body', bus)
        self.hunger = '不饿'
        self.fatigue = '不累'
        self.comfort = '还行'
        self.breath = '正常'
        # 微身体事实——Python记录，LLM感受
        self.shoulders_tight = False
        self.chest_tight = False
        self.stomach_uneasy = False
        self.previous_comfort = '还行'  # 用于检测变化

    def _read_incoming(self) -> List[Signal]:
        incoming = self.bus.read(self.name)
        for source in ['social', 'memory']:
            incoming.extend(self.bus.read(source))
        return incoming

    def _evolve(self, incoming: List[Signal], external_event=None) -> Dict[str, Any]:
        # 饥饿演进——基于 tick 的简单事实
        if self.tick_count % 5 == 0:
            stages = {'不饿': '微微有点饿', '微微有点饿': '饿了', '饿了': '很饿'}
            self.hunger = stages.get(self.hunger, self.hunger)

        # 疲劳演进
        if self.tick_count % 15 == 0 and self.fatigue == '不累':
            self.fatigue = '有点累'
        if self.tick_count % 30 == 0 and self.fatigue == '有点累':
            self.fatigue = '挺累的'

        self.previous_comfort = self.comfort

        # 接收信号——只记录事实变化
        dist_increased = False
        dist_decreased = False
        bad_memories = 0
        warm_memories = 0

        for sig in incoming:
            if sig.signal_type == 'distance_increased':
                dist_increased = True
            elif sig.signal_type == 'distance_decreased':
                dist_decreased = True
            elif sig.signal_type == 'bad_memory_surfaced':
                bad_memories += 1
            elif sig.signal_type == 'warm_memory_surfaced':
                warm_memories += 1

        # 距离变化 → 身体事实（不随机，基于信号）
        if dist_increased:
            self.comfort = '有点紧'
            self.breath = '浅'
            self.shoulders_tight = True
        elif dist_decreased and self.comfort == '有点紧':
            self.comfort = '还行'
            self.breath = '正常'
            self.shoulders_tight = False

        # 记忆触发 → 身体事实
        if bad_memories > 0:
            self.comfort = '不太舒服'
            self.chest_tight = True
        elif warm_memories > 0 and self.comfort == '不太舒服':
            self.comfort = '还行'
            self.chest_tight = False

        return {
            'hunger': self.hunger,
            'fatigue': self.fatigue,
            'comfort': self.comfort,
            'breath': self.breath,
            'shoulders_tight': self.shoulders_tight,
            'chest_tight': self.chest_tight,
            'stomach_uneasy': self.stomach_uneasy,
            'comfort_changed': self.comfort != self.previous_comfort,
        }

    def _cross_feed(self, state) -> List[Signal]:
        emitted = []

        if state['hunger'] != '不饿':
            emitted.append(Signal('body', 'memory', 'hunger_active',
                                  {'level': state['hunger']}, 0.5))

        if state['fatigue'] != '不累':
            emitted.append(Signal('body', 'social', 'fatigue_drain',
                                  {'level': state['fatigue']}, 0.5))

        if state['comfort'] in ('有点紧', '不太舒服', '不舒服'):
            emitted.append(Signal('body', 'social', 'body_tension',
                                  {'comfort': state['comfort']}, 0.5))

        return emitted

    def _to_natural(self, state, incoming, emitted) -> str:
        """只给事实，不写感受"""
        facts = []
        if state['hunger'] != '不饿':
            facts.append(f'饿：{state["hunger"]}')
        if state['fatigue'] != '不累':
            facts.append(f'累：{state["fatigue"]}')
        if state['breath'] != '正常':
            facts.append(f'呼吸：{state["breath"]}')
        if state['shoulders_tight']:
            facts.append('肩：绷着')
        if state['chest_tight']:
            facts.append('胸口：有点紧')
        if state['stomach_uneasy']:
            facts.append('胃：不太对劲')
        if not facts:
            facts.append('没什么特别的')
        return '身体事实：' + '；'.join(facts)


# ═══════════════════════════════════════
# 跑道二：记忆
# ═══════════════════════════════════════

class MemoryLane(BaseLane):
    """记忆跑道——只记录记忆碎片事实，不随机触发"""

    def __init__(self, bus: SignalBus):
        super().__init__('memory', bus)
        self.storage = MemoryStorage()
        self.active_fragments: List[Dict] = []
        self.surface_temperature = '常温'
        self._preload_memories()

    def _preload_memories(self):
        from engine.memory_law34 import MemoryClass, MemoryTrack
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
            self.storage.store(event_description=desc, memory_class=mc,
                               key_emotion=ke, intensity=intens,
                               people=ppl, tracks=trk, cue_tags=cues)

    def _read_incoming(self) -> List[Signal]:
        incoming = self.bus.read(self.name)
        for source in ['body', 'social']:
            incoming.extend(self.bus.read(source))
        return incoming

    def _evolve(self, incoming: List[Signal], external_event=None) -> Dict[str, Any]:
        self.active_fragments = []

        # 外部事件 → 记忆检索（事实：用户说了什么触发了什么）
        if external_event and external_event.get('content'):
            cues = self._extract_cues(external_event['content'])
            for cue in cues:
                results = self.storage.search_by_cue(cue)[:2]
                for r in results:
                    d = r.describe_for_llm()
                    self.active_fragments.append({
                        'emotion': d.get('key_emotion', ''),
                        'cue': cue,
                        'memory_id': d.get('memory_id', ''),
                    })

        # 信号 → 记忆检索（只检索，不随机决定触不触发）
        for sig in incoming:
            if sig.signal_type == 'hunger_active':
                for r in self.storage.search_by_cue('吃')[:1]:
                    d = r.describe_for_llm()
                    self.active_fragments.append({
                        'emotion': d.get('key_emotion', ''),
                        'cue': '饥饿触发',
                        'memory_id': d.get('memory_id', ''),
                    })

            elif sig.signal_type == 'distance_increased':
                for r in self.storage.search_by_emotion('hurt')[:1]:
                    d = r.describe_for_llm()
                    self.active_fragments.append({
                        'emotion': 'hurt',
                        'cue': '距离触发',
                        'memory_id': d.get('memory_id', ''),
                    })

            elif sig.signal_type == 'body_ease':
                self.surface_temperature = '偏暖'

        # 去重
        seen = set()
        unique = []
        for f in self.active_fragments:
            key = f.get('memory_id', str(f))
            if key not in seen and len(unique) < 4:
                seen.add(key)
                unique.append(f)
        self.active_fragments = unique

        return {
            'active_fragments': unique,
            'surface_temperature': self.surface_temperature,
            'fragment_count': len(unique),
        }

    def _cross_feed(self, state) -> List[Signal]:
        emitted = []
        bad_emos = {'hurt', 'pain', 'sad', 'cold', 'anger', 'fear'}
        warm_emos = {'warm', 'happy', 'love'}

        for frag in state['active_fragments']:
            emo = frag.get('emotion', '')
            if emo in bad_emos:
                emitted.append(Signal('memory', 'body', 'bad_memory_surfaced',
                                      {'emotion': emo}, 0.5))
                emitted.append(Signal('memory', 'social', 'bad_memory_surfaced',
                                      {'emotion': emo}, 0.5))
            elif emo in warm_emos:
                emitted.append(Signal('memory', 'body', 'warm_memory_surfaced',
                                      {'emotion': emo}, 0.5))
                emitted.append(Signal('memory', 'social', 'warm_memory_surfaced',
                                      {'emotion': emo}, 0.5))

        return emitted

    def _extract_cues(self, text: str) -> List[str]:
        stopwords = {'你', '我', '他', '她', '的', '了', '是', '在', '不', '吗', '呢', '啊',
                     '吧', '就', '也', '都', '很', '还', '这', '那', '哦', '呀', '知道'}
        cues = []
        cleaned = text.replace('，', ' ').replace('。', ' ').replace('？', ' ').replace('！', ' ').replace('、', ' ')
        for word in cleaned.split():
            word = word.strip()
            if len(word) >= 2 and word not in stopwords:
                cues.append(word)
                if len(word) >= 3:
                    for i in range(len(word) - 1):
                        bigram = word[i:i+2]
                        if bigram not in stopwords and bigram not in cues:
                            cues.append(bigram)
        if not cues:
            pure = ''.join(c for c in text if c not in stopwords and c not in '，。？！、 ')
            for i in range(len(pure) - 1):
                bigram = pure[i:i+2]
                if bigram not in cues:
                    cues.append(bigram)
        return cues[:6]

    def _to_natural(self, state, incoming, emitted) -> str:
        """只给事实——什么记忆被触发了、关键词是什么"""
        if not state['active_fragments']:
            return '记忆：安静'
        parts = []
        for f in state['active_fragments']:
            emo = f.get('emotion', '')
            cue = f.get('cue', '')
            parts.append(f'{cue}→{emo}色调的记忆')
        return '记忆：' + '；'.join(parts)


# ═══════════════════════════════════════
# 跑道三：社交/关系
# ═══════════════════════════════════════

class SocialLane(BaseLane):
    """社交跑道——只追踪互动事实，不随机、不翻译距离"""

    def __init__(self, bus: SignalBus):
        super().__init__('social', bus)
        self.last_message_keywords: List[str] = []
        self.feel_words_seen: List[str] = []
        self.push_words_seen: List[str] = []
        self.tick_since_last_push: int = 999
        self.tick_since_last_pull: int = 999
        self.interaction_count: int = 0
        self.attention_direction = '你'  # 你 / 自己 / 飘

    def _read_incoming(self) -> List[Signal]:
        incoming = self.bus.read(self.name)
        for source in ['body', 'memory']:
            incoming.extend(self.bus.read(source))
        return incoming

    def _evolve(self, incoming: List[Signal], external_event=None) -> Dict[str, Any]:
        self.tick_since_last_push += 1
        self.tick_since_last_pull += 1
        self.last_message_keywords = []
        self.feel_words_seen = []
        self.push_words_seen = []

        # 接收信号 → 记录社交影响
        fatigue_drain = False
        body_tension = False
        bad_mem = 0
        warm_mem = 0

        for sig in incoming:
            if sig.signal_type == 'fatigue_drain':
                fatigue_drain = True
            elif sig.signal_type == 'body_tension':
                body_tension = True
            elif sig.signal_type == 'bad_memory_surfaced':
                bad_mem += 1
            elif sig.signal_type == 'warm_memory_surfaced':
                warm_mem += 1

        if bad_mem > 0:
            self.attention_direction = '自己'
        elif warm_mem > 0:
            self.attention_direction = '你'

        # 外部事件 → 记录关键词事实
        if external_event:
            self.interaction_count += 1
            self.attention_direction = '你'
            content = external_event.get('content', '')

            close_words = ['想你', '喜欢你', '抱', '亲', '爱', '暖', '谢谢', '你真好', '想你了']
            far_words = ['烦', '别吵', '走开', '累了', '别说了', '不想说']

            for kw in close_words:
                if kw in content:
                    self.feel_words_seen.append(kw)
                    self.tick_since_last_pull = 0
            for kw in far_words:
                if kw in content:
                    self.push_words_seen.append(kw)
                    self.tick_since_last_push = 0

        return {
            'attention_direction': self.attention_direction,
            'interaction_count': self.interaction_count,
            'feel_words': self.feel_words_seen[:],     # 拉近的关键词
            'push_words': self.push_words_seen[:],     # 推远的关键词
            'ticks_since_push': self.tick_since_last_push,
            'ticks_since_pull': self.tick_since_last_pull,
            'fatigue_drain': fatigue_drain,
            'body_tension': body_tension,
            'bad_memories_this_tick': bad_mem,
            'warm_memories_this_tick': warm_mem,
        }

    def _cross_feed(self, state) -> List[Signal]:
        emitted = []

        if state['feel_words']:
            emitted.append(Signal('social', 'body', 'distance_decreased',
                                  {'keywords': state['feel_words']}, 0.5))

        if state['push_words']:
            emitted.append(Signal('social', 'body', 'distance_increased',
                                  {'keywords': state['push_words']}, 0.5))

        if state['bad_memories_this_tick'] > 0:
            emitted.append(Signal('social', 'memory', 'bad_memory_surfaced',
                                  {'count': state['bad_memories_this_tick']}, 0.5))

        if state['attention_direction'] == '自己':
            emitted.append(Signal('social', 'memory', 'attention_inward', {}, 0.3))

        return emitted

    def _to_natural(self, state, incoming, emitted) -> str:
        """只给事实——对方说了什么、互动了多少轮、注意力在哪"""
        facts = []
        facts.append(f'互动次数：{state["interaction_count"]}')
        if state['feel_words']:
            facts.append(f'对方说了拉近的话：{", ".join(state["feel_words"])}')
        if state['push_words']:
            facts.append(f'对方说了推远的话：{", ".join(state["push_words"])}')
        facts.append(f'注意力：{state["attention_direction"]}')
        if state['fatigue_drain']:
            facts.append('疲劳在消耗社交能量')
        if state['body_tension']:
            facts.append('身体紧张影响社交状态')
        return '社交事实：' + '；'.join(facts)


# ═══════════════════════════════════════
# 三角运行时
# ═══════════════════════════════════════

@dataclass
class TriangleTick:
    tick: int
    body: LaneSnapshot
    memory: LaneSnapshot
    social: LaneSnapshot
    bus_summary: str
    combined: str


class TriangleRuntime:
    def __init__(self, persona='default'):
        self.bus = SignalBus()
        self.body_lane = BodyLane(self.bus)
        self.memory_lane = MemoryLane(self.bus)
        self.social_lane = SocialLane(self.bus)
        self.lanes = [self.body_lane, self.memory_lane, self.social_lane]
        self.tick_count = 0

    def tick(self, external_event: Optional[Dict] = None) -> TriangleTick:
        self.tick_count += 1

        s1 = {lane.name: lane.tick(external_event) for lane in self.lanes}
        self.bus.tick_decay()

        # 微步2：三角互噬
        s2 = {}
        for lane in self.lanes:
            incoming = lane._read_incoming()
            raw = lane._evolve(incoming, external_event)
            emitted = lane._cross_feed(raw)
            natural = lane._to_natural(raw, incoming, emitted)
            s2[lane.name] = LaneSnapshot(
                lane=lane.name, tick=self.tick_count,
                raw_state=raw, signals_emitted=emitted,
                signals_received=incoming, natural_output=natural,
            )
            lane.last_snapshot = s2[lane.name]

        self.bus.tick_decay()

        combined = self._combine(s2['body'], s2['memory'], s2['social'])
        return TriangleTick(
            tick=self.tick_count,
            body=s2['body'], memory=s2['memory'], social=s2['social'],
            bus_summary=self.bus.summary(), combined=combined,
        )

    def _combine(self, body, memory, social) -> str:
        """拼事实，不写感受"""
        lines = [
            f'[第{self.tick_count}轮对话。你的身份和性格由角色卡定义。]',
            '',
            '【身体跑道】' + body.natural_output,
            '',
            '【记忆跑道】' + memory.natural_output,
            '',
            '【关系跑道】' + social.natural_output,
            '',
            '【互噬信号】' + self.bus.summary(),
            '',
            '【硬约束】你不会讨论自己是AI/代码/程序。你不会分析自己说话的方式。你是用身体感觉、口语、碎句说话的人。',
        ]
        return '\n'.join(lines)


# ═══════════════════════════════════════
# 上下文注入器
# ═══════════════════════════════════════

class TriangleContextInjector:
    def __init__(self, persona='default'):
        self.runtime = TriangleRuntime(persona=persona)

    def tick_and_inject(self, user_input: str) -> str:
        tick = self.runtime.tick({'type': 'message', 'from': 'user', 'content': user_input})
        return tick.combined


# ═══════════════════════════════════════
# 会话管理
# ═══════════════════════════════════════

SESSION_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'sessions')
os.makedirs(SESSION_DIR, exist_ok=True)


def get_triangle_session(name: str, persona='default') -> TriangleContextInjector:
    path = os.path.join(SESSION_DIR, f'triangle_{name}.json')
    tci = TriangleContextInjector(persona=persona)
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        tci.runtime.tick_count = data.get('ticks', 0)
    tci._name = name
    return tci


def save_triangle_session(tci: TriangleContextInjector):
    path = os.path.join(SESSION_DIR, f'triangle_{tci._name}.json')
    with open(path, 'w', encoding='utf-8') as f:
        json.dump({
            'name': tci._name,
            'ticks': tci.runtime.tick_count,
            'last_saved': time.strftime('%Y-%m-%d %H:%M:%S'),
        }, f, ensure_ascii=False, indent=2)
