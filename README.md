# Human Actor Engine · 人类行为引擎

> **声明 / Disclaimer**
> 本文档由 AI（DeepSeek）辅助生成。核心思路、架构方向与技术判断均由用户提出；AI 负责整理、结构化呈现与表述优化。文中所有技术观点归用户所有。
> This document was AI-assisted (DeepSeek). All core ideas, architectural direction, and technical judgments were proposed by the user; the AI organized, structured, and refined the presentation. All technical views belong to the user.

---

## 简介 / Introduction

**[中文]**

Human Actor Engine 不是一个"让 AI 模仿人类说话"的工具。它在更深一层——**让系统拥有身体感知、情绪底色、记忆衰减、关系距离和社交能量，从底层往上产生真正有"人味儿"的状态**。

传统方案训练模型模仿人类对话的表面特征。本引擎的做法不同：饿了会烦躁，累了话变少，亲密关系的距离是一个会漂移的连续值而不是二进制开关，557 条力场通道让不同维度的感知互相干涉。语言不是被"生成"的，是经过身体的消化管线之后被"排出"的。

核心技术栈：
- **60 条人类行为法则**（SKILL.md, 140KB）—— 引擎的"底层操作系统"
- **10 个核心引擎模块**：身体引擎、双轨记忆引擎（遗忘曲线+情感加权）、关系距离引擎、三层学习引擎、力场演化引擎（557 通道）、活体验证器（L1/L2/L3）等
- **回流管道**（response_feedback.py, 48KB）：LLM 回应不再是一次性的——回应中的关系信号（暖意/推开/试探/修复等 15 类）被正则识别后回流到关系距离引擎和学习引擎
- **句间结构识别**：不只看词，还看句间关系——铺垫→邀请、迂回暴露、条件依附
- **256/256 单元测试全过**，0 条孤立法则

**[EN]**

Human Actor Engine is not a "make AI sound human" toolkit. It goes deeper — **giving a system body perception, emotional undertone, memory decay, relational distance, and social energy, so genuinely human-like states emerge from the bottom up.**

Conventional approaches train models to mimic surface conversational features. This engine works differently: hunger causes irritability, fatigue shortens sentences, intimacy distance is a drifting continuum rather than a binary switch, and 557 field channels let different perceptual dimensions interfere with each other. Language isn't "generated" — it's "excreted" through the body's digestive pipeline.

Core tech stack:
- **60 Laws of Human Behavior** (SKILL.md, ~140KB) — the engine's "operating system"
- **10 core engine modules**: Body Engine, Dual-Track Memory Engine (forgetting curve + emotional weighting), Relational Distance Engine, Three-Layer Learning Engine, Field Evolution Engine (557 channels), Live Validator (L1/L2/L3), etc.
- **Feedback Loop** (response_feedback.py, ~48KB): LLM responses are no longer one-shot — relational signals (warmth, push-away, trial-initiation, repair, etc. across 15 categories) are regex-detected and fed back into the distance ledger and learning engine
- **Inter-sentence Structure Recognition**: Not just words, but sentence relationships — preamble→invitation, indirect exposure, conditional attachment
- **256/256 unit tests PASS**, 0 orphaned laws

## 架构概览

```
角色卡_xxx.md          ← 用户写，纯自然语言，不需要懂引擎
        │
        ▼
 living_soul.py        ← 自然语言→内部感知参数映射
        │
        ▼
 ┌──────────────────────────────────────┐
 │            Human Actor Engine        │
 │                                      │
 │  body_core.py        身体引擎        │  ← 饿/累/困/痛/精力
 │  distance_ledger.py  关系距离引擎    │  ← 亲疏远近的漂移
 │  memory_law34.py     双轨记忆引擎    │  ← 遗忘曲线 + 情感记忆
 │  learning_engine.py  三层学习引擎    │  ← 习惯形成 + 行为调适
 │  complexity_engine.py 力场演化       │  ← 557 条力场通道联动
 │  contour_tracer.py   轮廓追踪        │  ← 行为轮廓的多层描摹
 │  live_validator.py   活体验证        │  ← L1/L2/L3 三层验证
 │                                      │
 │  engine_hub.py       中枢横切调度    │  ← 各引擎的统一调度入口
 │  human_topology.py   SKILL 解析      │  ← 法则拓扑图的构建与查询
 │  human_translator.py  人类翻译层     │  ← 引擎状态→人类可感描述
 │  output_filter.py    输出过滤        │  ← 语言屏障
 │                                      │
 │  macro_inject.py     状态注入        │  ← 将引擎输出注入 LLM 上下文
 │  context_injector.py 上下文组装      │  ← 构建发给 LLM 的完整提示
 │  soul_bridge.py      Python-LLM 桥   │  ← 执行层映射
 │  macro_triangle.py   三层联动        │  ← 三角形运行时
 │  triangle_runtime.py 三角运行时      │  ← 引擎核心循环
 │                                      │
 │  session_manager.py  会话管理        │  ← 会话状态持久化
 │  living_soul.py     角色卡导入       │  ← 创建/加载角色
 │  run_human_engine.py 入口            │  ← 一键启动
 └──────────────────────────────────────┘
        │
        ▼
     SKILL.md            ← 60 条人类行为法则（引擎的"操作系统"）
```

## 核心设计理念

### 不是"模拟人类"，是"成为人类"

传统方案是让 AI 模仿人类说话的表面特征。Human Actor Engine 的做法是从底层往上建：

- **身体感知** → 饿了会烦躁，累了话变少
- **记忆衰减** → 遗忘曲线 + 情感加权，不是数据库检索
- **关系距离** → 亲疏不是二进制的，是一个会漂移的连续值
- **力场通道** → 557 条通道令不同感知维度之间互相作用（饿了→脾气变差→说话带刺→关系距离微调）

语言不是被"生成"的，是经过身体的消化管线之后被"排出"的。有用吸收，没用排出。排出 = 回应。

### 角色卡与引擎彻底解耦

角色卡是用户写的，纯自然语言。引擎做内部映射。角色卡不需要知道引擎的存在。

## 快速开始

### 1. 创建你的角色卡

复制 `templates/角色卡_模板.md`，填入你的角色信息：

```bash
cp templates/角色卡_模板.md 角色卡_我的角色.md
```

### 2. 激活角色

在项目根目录创建一个 `roleplay_active` 文件，写入角色卡文件名（不含 `.md` 后缀）：

```bash
echo "我的角色" > roleplay_active
```

### 3. 启动引擎

```bash
python run_human_engine.py
```

引擎会：
1. 读取 `roleplay_active` → 找到你的角色卡
2. 将角色卡映射为内部感知参数
3. 启动引擎核心循环
4. 每次对话前自动注入当前引擎状态到 LLM 上下文

## 文件结构

```
human-actor-engine/
├── README.md
├── SOUL.md                    # 运行时哲学：三层分工规则
├── SKILL.md                   # 60 条人类行为法则（引擎操作系统）
├── run_human_engine.py        # 一键启动入口
├── soul_bridge.py             # Python-LLM 执行映射 (104KB)
├── macro_triangle.py          # 三层联动运行时
├── macro_inject.py            # 状态注入器
├── context_injector.py        # 上下文组装器
├── living_soul.py             # 角色卡→内部参数映射
├── output_filter.py           # 语言屏障
├── session_manager.py         # 会话状态管理
├── engine/                    # 核心引擎模块
│   ├── body_core.py           # 身体引擎 (40KB)
│   ├── memory_law34.py        # 双轨记忆引擎 (41KB)
│   ├── distance_ledger.py     # 关系距离引擎 (43KB)
│   ├── learning_engine.py     # 三层学习引擎 (28KB)
│   ├── complexity_engine.py   # 力场演化引擎 (36KB)
│   ├── contour_tracer.py      # 轮廓追踪 (46KB)
│   ├── live_validator.py      # 三层活体验证 (26KB)
│   ├── engine_hub.py          # 中枢横切调度 (16KB)
│   ├── human_topology.py      # SKILL.md 拓扑解析 (32KB)
│   ├── human_translator.py    # 人类翻译层 (42KB)
│   └── triangle_runtime.py    # 三角运行时 (25KB)
├── templates/
│   └── 角色卡_模板.md          # 角色卡空白模板
└── docs/                      # 文档（待补充）
```

## 角色卡怎么写

角色卡是**用你自己的话来描述一个角色**。不需要写代码，不需要了解引擎。引擎会自动把你的自然语言映射到内部参数。

关键要素：
- **基本信息**：名字、年龄、性别
- **性格描述**：脾气、习惯、小动作
- **身体与感受**：敏感度、饿/累的表现
- **情绪与共情**：波动性、共情力
- **社交能量**：内向/外向、独处需求
- **说话方式**：句子长短、口头禅
- **核心矛盾**：驱动角色的内在冲突
- **关系设定**：和用户之间的关系

详见 `templates/角色卡_模板.md`。

## 技术指标

| 指标 | 数值 |
|------|------|
| 行为法则 | 60 条 |
| 力场通道 | 557 条 |
| 活体验证层 | 3 层（信号+压力+涌现） |
| 孤立法则 | 0 条 |
| 单元测试 | 256/256 ALL PASS |

## 依赖

- Python 3.10+
- 无外部 API 依赖
- 无需 GPU

## 许可证

MIT License

---

**Human Actor Engine** — 让机器不只是"会算"，也"会活"。
