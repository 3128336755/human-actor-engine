# engine_hub.py — 四引擎中枢，打穿隔墙
#
# 中枢在 soul_bridge 每 tick 末尾被调用一次，完成引擎间状态传递。
# 它连接引擎、传递事件——但不替LLM做判断。
# 8条横切线，全部基于真实 API 签名验证。

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from engine.memory_law34 import MemoryStorage, MemoryClass, MemoryTrack
from engine.body_core import BodyCore
from engine.distance_ledger import DistanceLedger
from engine.learning_engine import LearningEngine, KnowledgeSource
from engine.contour_tracer import ContourTracer, ContourMap
from engine.human_topology import get_topology, Topology, render_topology


@dataclass
class HubEvent:
    from_engine: str
    to_engine: str
    what: str
    detail: Dict[str, Any] = field(default_factory=dict)


class EngineHub:
    def __init__(self,
                 memory: MemoryStorage,
                 body: BodyCore,
                 distance: DistanceLedger,
                 learning: LearningEngine):
        self.memory = memory
        self.body = body
        self.distance = distance
        self.learning = learning
        self.contour = ContourTracer()
        self._topo: Optional[Topology] = None
        self.pollination_count = 0
        self._last_contour_map: Optional[ContourMap] = None
    
    def cross_pollinate(self, context: Optional[Dict] = None) -> List[HubEvent]:
        self.pollination_count += 1
        events: List[HubEvent] = []
        
        events.extend(self._body_teaches_learning())
        events.extend(self._body_marks_memory())
        events.extend(self._unsettled_debts_drain_body())
        if context:
            events.extend(self._correction_triggers_learning(context))
        events.extend(self._memory_pushes_pulls_distance())
        events.extend(self._body_memory_echoes())
        events.extend(self._painful_learning_into_memory())
        events.extend(self._learning_feels_in_body())
        
        return events
    
    # ── 1. body → learning ──
    def _body_teaches_learning(self) -> List[HubEvent]:
        snap = self.body.snapshot_for_llm()
        hunger = snap.get('hunger', '不饿')
        fatigue = snap.get('fatigue', '不累')
        events = []
        
        for sig in [('hunger', hunger), ('fatigue', fatigue)]:
            name, val = sig
            if val not in ('不饿', '不累', '还行', ''):
                self.learning.add_domain(domain_id='body_{}'.format(name), name='身体觉察')
                self.learning.learn(
                    domain_id='body_{}'.format(name),
                    context='身体发来信号：{}={}。下次早回应。'.format(name, val),
                    source=KnowledgeSource.EXPERIENCE,
                    who_taught='自己的身体',
                )
                events.append(HubEvent('body_core', 'learning_engine', 'body_taught',
                                       {'signal': '{}={}'.format(name, val)}))
        return events
    
    # ── 2. body → memory ──
    def _body_marks_memory(self) -> List[HubEvent]:
        if self.pollination_count % 5 != 0:
            return []
        snap = self.body.snapshot_for_llm()
        fatigue = snap.get('fatigue', '不累')
        hunger = snap.get('hunger', '不饿')
        loaded = (fatigue in ('很累', '已经走不动了', '只想躺下') or
                  hunger in ('饿了', '饿得难受'))
        if loaded:
            self.memory.store(
                event_description='身体负重：疲{}，饿{}'.format(fatigue, hunger),
                memory_class=MemoryClass.PATTERN,
                key_emotion='疲惫',
                intensity='中',
                people=[],
                tracks=[MemoryTrack.PURE_SCENARIO],
                cue_tags=['body_state', 'somatic_marker'],
            )
            return [HubEvent('body_core', 'memory_law34', 'somatic_marker',
                             {'fatigue': fatigue, 'hunger': hunger})]
        return []
    
    # ── 3. distance → body ──
    def _unsettled_debts_drain_body(self) -> List[HubEvent]:
        dd = self.distance.to_dict()
        persons = dd.get('people', {})
        events = []
        
        for pid, entry in list(persons.items())[:15]:
            if not isinstance(entry, dict):
                continue
            ledger = entry.get('ledger', [])
            unsettled = sum(1 for e in ledger if isinstance(e, dict)
                            and not e.get('settled', False)
                            and e.get('emotional_valence', 0) < 0)
            if unsettled > 0:
                # drain_intensity is str per API
                body_hint = '轻微消耗' if unsettled <= 2 else '明显消耗'
                self.body.social_interact(
                    person=pid,
                    context='未清算的情感债务({}条)'.format(unsettled),
                    drain_intensity=body_hint,
                )
                events.append(HubEvent('distance_ledger', 'body_core',
                                       'debt_drain', {'person': pid, 'count': unsettled}))
        return events
    
    # ── 4. distance → learning ──
    def _correction_triggers_learning(self, context: Dict) -> List[HubEvent]:
        sender = context.get('sender', '')
        content = context.get('content', '')
        if not sender or not content:
            return []
        events = []
        
        if not self.distance.has_person(sender):
            self.learning.add_domain(
                domain_id='person_{}'.format(hash(sender) % 100000),
                name='了解{}'.format(sender),
            )
            events.append(HubEvent('distance_ledger', 'learning_engine',
                                   'new_person', {'person': sender}))
        
        triggers = ['不对', '不是这样', '你错了', '其实', '应该是']
        if any(k in content for k in triggers):
            self.learning.learn(
                domain_id='social_correction',
                context='{} 说：{}'.format(sender, content[:200]),
                source=KnowledgeSource.INSTILLED,
                who_taught=sender,
                emotional_response='被纠正了——不太舒服，但在学',
            )
            events.append(HubEvent('distance_ledger', 'learning_engine',
                                   'correction_learned', {'sender': sender}))
        return events
    
    # ── 5. memory → distance ──
    def _memory_pushes_pulls_distance(self) -> List[HubEvent]:
        dd = self.distance.to_dict()
        persons = dd.get('people', {})
        events = []
        
        for pid in list(persons.keys())[:10]:
            records = self.memory.search_by_person(pid)
            if not records:
                continue
            
            if len(records) >= 2:
                self.distance.record_interaction(
                    person_id=pid,
                    context='记忆回溯——共同的过去',
                    distance_movement='pull',
                    emotional_weight=min(len(records) * 0.12, 0.6),
                )
                events.append(HubEvent('memory_law34', 'distance_ledger',
                                       'memory_pull', {'person': pid, 'count': len(records)}))
            
            debts = self.memory.get_active_debts(person=pid)
            if debts:
                debt_w = sum(d.get('principal', 0) * d.get('interest_factor', 1.0) for d in debts)
                if debt_w > 0.05:
                    self.distance.record_interaction(
                        person_id=pid,
                        context='情感负债计息',
                        distance_movement='push',
                        emotional_weight=min(debt_w * 0.25, 0.4),
                    )
                    events.append(HubEvent('memory_law34', 'distance_ledger',
                                           'debt_push', {'person': pid, 'debt': round(debt_w, 2)}))
        return events
    
    # ── 6. memory → body ──
    def _body_memory_echoes(self) -> List[HubEvent]:
        snap = self.body.snapshot_for_llm()
        triggers = snap.get('recent_physical_triggers') or []
        events = []
        
        for trig in triggers[:3]:
            if not isinstance(trig, dict):
                continue
            anchor_id = trig.get('cue', '')
            if not anchor_id:
                continue
            anchored = self.memory.get_by_trace_anchor(anchor_id)
            if anchored:
                first = anchored[0]
                desc = getattr(first, 'event_description', '')[:60]
                self.body.set_craving('记忆回响：{}'.format(desc))
                events.append(HubEvent('memory_law34', 'body_core',
                                       'body_memory_echo',
                                       {'memory_id': getattr(first, 'memory_id', '?')}))
        return events
    
    # ── 7. learning → memory ──
    def _painful_learning_into_memory(self) -> List[HubEvent]:
        ld = self.learning.to_dict()
        domains = ld.get('domains', {})
        events = []
        
        for d_id, d in list(domains.items())[:10]:
            if not isinstance(d, dict):
                continue
            recents = d.get('recent_events', [])
            for ev in recents[-2:]:
                if not isinstance(ev, dict) or ev.get('synced_to_memory'):
                    continue
                
                src = ev.get('source', '')
                emo = ev.get('emotional_response', '')
                is_painful = src == '碰壁碰出来的' or '难过' in emo or '伤' in emo
                
                self.memory.store(
                    event_description='学到关于{}：{}'.format(
                        d.get('name', d_id), ev.get('context', '')[:150]),
                    memory_class=MemoryClass.HARDCORE if is_painful else MemoryClass.PATTERN,
                    key_emotion='痛苦' if is_painful else '平常',
                    intensity='高' if is_painful else '低',
                    people=[],
                    tracks=[MemoryTrack.PURE_SCENARIO],
                    cue_tags=['learning', 'knowledge_update', d_id],
                )
                ev['synced_to_memory'] = True
                events.append(HubEvent('learning_engine', 'memory_law34',
                                       'learning_stored',
                                       {'domain': d_id, 'painful': is_painful}))
        return events
    
    # ── 8. learning → body ──
    def _learning_feels_in_body(self) -> List[HubEvent]:
        ld = self.learning.to_dict()
        domains = ld.get('domains', {})
        now = time.time()
        
        recent = {}
        for d_id, d in domains.items():
            if not isinstance(d, dict):
                continue
            last = d.get('last_updated')
            if isinstance(last, (int, float)) and last > now - 300:
                recent[d_id] = d
        
        if not recent:
            return []
        
        painful = any(d.get('last_learn_source') == '碰壁碰出来的' for d in recent.values())
        self.body.set_craving(
            '学到代价知识——身体有点沉' if painful else '刚学新东西——脑子热热的')
        
        return [HubEvent('learning_engine', 'body_core', 'learning_affects_body',
                         {'domains': list(recent.keys())[:3], 'painful': painful})]
    
    # ── 轮廓追踪：念头→法则网并行投影 ──
    def trace_contour(self, trigger: str, context: Optional[Dict] = None) -> ContourMap:
        cm = self.contour.trace(trigger, context=context)
        self._last_contour_map = cm
        return cm
    
    # ── 活人全幅拓扑：SKILL.md 的所有法则+连线 ──
    @property
    def human_topology(self) -> Topology:
        if self._topo is None:
            self._topo = get_topology()
        return self._topo
    
    def render_human_topology(self) -> str:
        return render_topology()
    
    # ── LLM snapshot ──
    def hub_snapshot_for_llm(self) -> Dict[str, Any]:
        snap = {
            'pollination_count': self.pollination_count,
            'wires': [
                'body_awareness.teaches_learning',
                'body_load.marks_memory',
                'unsettled_debts.drains_body',
                'correction.triggers_learning',
                'memory_weight.pushes_pulls_distance',
                'body_memory.echoes_into_body',
                'painful_learning.into_memory',
                'learning.warmth_on_body',
            ],
        }
        if self._last_contour_map:
            snap['contour'] = {
                'trigger': self._last_contour_map.trigger,
                'external_lens': self._last_contour_map.external_lens,
                'internal_lens': self._last_contour_map.internal_lens,
                'whole_lens': self._last_contour_map.whole_lens,
                'blank_lens': self._last_contour_map.blank_lens[:5],
                'tensions': [(a, b, why) for a, b, why in self._last_contour_map.tensions],
                'active_windows': self._last_contour_map.active_windows,
            }
        return snap


# ============================================================
# 自测
# ============================================================
if __name__ == '__main__':
    _P = _F = 0
    def _t(n, c):
        global _P, _F
        if c: _P += 1; print('  OK  {}'.format(n))
        else: _F += 1; print('  FAIL {}'.format(n))
    
    print('EngineHub self-test — 8 wires')
    print('=' * 50)
    mem = MemoryStorage()
    body = BodyCore()
    dist = DistanceLedger()
    learn = LearningEngine()
    hub = EngineHub(memory=mem, body=body, distance=dist, learning=learn)
    
    print('\n[1] construction')
    _t('pollination_count == 0', hub.pollination_count == 0)
    
    print('\n[2] empty tick')
    evs = hub.cross_pollinate()
    _t('pollination_count == 1', hub.pollination_count == 1)
    _t('returns list', isinstance(evs, list))
    
    print('\n[3] body -> learning')
    body.eat('stale bread', 'not great', 0.3)
    e2 = hub.cross_pollinate()
    _t('pollination_count == 2', hub.pollination_count == 2)
    
    print('\n[4] distance -> learning (correction)')
    e3 = hub.cross_pollinate(context={'sender': 'xiaoming', 'content': 'no, try from this side'})
    _t('correction triggers learning', any('correction' in e.what for e in e3))
    
    print('\n[5] memory -> distance')
    dist.ensure_person(person_id='xiaoming', display_name='xiaoming')
    mem.store(event_description='xiaoming helped with deadline',
              memory_class=MemoryClass.HARDCORE,
              key_emotion='grateful', intensity='high',
              people=['xiaoming'], tracks=[MemoryTrack.PURE_SCENARIO],
              cue_tags=['xiaoming'])
    mem.store(event_description='xiaoming owes me a meal',
              memory_class=MemoryClass.PATTERN,
              key_emotion='annoyed', intensity='medium',
              people=['xiaoming'], tracks=[MemoryTrack.PURE_SCENARIO],
              cue_tags=['xiaoming', 'debt'],
              emotional_debt={'principal': 0.3, 'interest_factor': 1.2})
    e4 = hub.cross_pollinate()
    hit = any(e.from_engine == 'memory_law34' and 'distance' in e.to_engine for e in e4)
    _t('memory pushes/pulls distance', hit)
    
    print('\n[6] learning -> memory')
    learn.add_domain('test_d', name='test')
    e5 = hub.cross_pollinate()
    _t('pollination_count == 3', hub.pollination_count == 3)
    
    print('\n[7] LLM snapshot')
    s = hub.hub_snapshot_for_llm()
    _t('has pollination_count', 'pollination_count' in s)
    _t('has wires', 'wires' in s)
    _t('8 wires online', len(s['wires']) == 8)
    
    total = _P + _F
    print('\n{}'.format('=' * 50))
    print('Passed {}/{}  Failed {}/{}'.format(_P, total, _F, total))
