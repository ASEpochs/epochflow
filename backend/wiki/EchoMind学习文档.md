# EchoMind 学习文档

这是一份把项目定位、业务流程、关键代码、使用方式和技术亮点合并后的学习文档。内容基于当前代码实现重写，尽量按“先看懂系统，再看懂代码，最后能跑起来”的顺序组织。

## 1. 项目定位

EchoMind 是一个面向复杂客服任务的多 Agent 客服编排运行时。

它解决的不是“能聊天”，而是这类真实问题：

- 用户一次说多个诉求，既有技术问题也有账单问题
- 用户信息不完整，需要系统先追问再处理
- 用户要转人工或场景紧急，系统要能升级
- 知识库要能接入真实业务规则，而不是只靠模型记忆
- 系统要能评测、监控、降权、回归，形成闭环

从工程上看，它的目标不是单纯堆一个更强的模型，而是把客服系统里最容易出问题的几层拆开处理：

- 先判断“这句话到底在问什么”
- 再判断“该谁来处理”
- 再判断“需不需要查知识库”
- 再判断“要不要补充信息、要不要升级”
- 最后把结果写回记忆和监控系统

这类拆分的意义在于，客服系统真正难的地方往往不是生成回复，而是前面的判断链条。如果前面几步错了，后面模型再强也会答偏。

## 2. 总体架构

```text
用户请求
  -> /chat
  -> MemoryManager 读取工作记忆、情景记忆、用户画像、摘要
  -> IntentRecognizer 三路融合识别细粒度意图、紧急度、实体
  -> 按意图决定是否触发知识库检索
  -> AgentOrchestrator 生成结构化路由决策
     - primary_agent
     - supporting_agents
     - routing_reason
     - routing_confidence
  -> 调用对应 Agent
  -> 注入记忆、知识库、结构化实体、Skills
  -> LLM 生成回复
  -> 写回工作记忆
  -> 异步更新用户画像
  -> Monitor 和 Evaluator 形成观测与评测闭环
```

### 2.1 为什么是这个顺序

这个顺序对应的是客服系统最常见的依赖关系：

1. **记忆先行**：没有上下文，很多问题会被误判成新问题。
2. **意图优先**：只有先知道用户大概在问什么，才能决定要不要查知识库。
3. **知识库前置**：业务类问题如果完全靠模型回忆，容易出现事实错误。
4. **路由决策**：不同领域的问题要交给不同 Agent，避免一个 prompt 处理所有场景。
5. **记忆回写**：系统每轮都要把新信息沉淀回去，否则多轮就失真。
6. **监控评测闭环**：没有闭环，系统只能“看起来能用”，不能持续优化。

### 2.2 这个架构和普通 Chatbot 的区别

普通 chatbot 往往是：

```text
用户消息 -> 单一 LLM -> 回复
```

EchoMind 是：

```text
用户消息 -> 记忆 -> 意图 -> 知识库 -> 路由 -> 工具 -> 回复 -> 回写 -> 评测 -> 监控
```

差别不只是多了几个模块，而是把“回答能力”拆成了几个可治理的能力层。

## 3. 核心业务流程

### 3.1 `/chat` 主链路

入口在 [api/main.py](/Users/xiao_xiong/Desktop/code/EchoMind/api/main.py)。

当前链路是：

1. 读取 Redis 工作记忆、ChromaDB 情景记忆和用户画像
2. 构造最近对话历史，供意图识别使用
3. 先做三路融合意图识别
4. 根据意图判断是否调用知识库
5. 生成路由决策
6. 调用主 Agent 或主辅 Agent
7. 写回记忆，并异步更新画像

这里有两个关键细节：

- **意图识别在 Agent 之前**，因为它决定是否需要知识库、是否需要澄清、是否应该直接升级。
- **画像更新是异步的**，因为它属于“延后沉淀”，不应该拖慢用户当前请求。

### 3.2 什么时候切 Agent

- 技术类问题 -> `TechnicalAgent`
- 账单、退款、发票、支付异常 -> `BillingAgent`
- 普通咨询 -> `GeneralAgent`
- 明确要求人工、或高风险升级 -> `EscalationAgent`

这背后的原则是“按风险和职责切分”：

- 通用 Agent 负责第一层接待，不承担深排障和资金处理责任
- 技术 Agent 专注于错误码、环境、版本、复现路径
- 账单 Agent 专注于订单、金额、支付、退款、发票
- 升级 Agent 则负责把已知信息整理干净，交给人工继续处理

这样做的好处是每个 Agent 的 prompt 更短，工具边界更清楚，风险更容易控制。

### 3.3 什么时候并行协作

当一个请求同时命中多个领域时，会同时派发多个 Agent，然后由编排器合并结果。

例如：

```text
登录一直 401，而且刚才还重复扣款了
```

可能会得到：

- 主 Agent：`technical`
- 辅助 Agent：`billing`

这种“主辅协作”比“简单多路并发回复”更像真实业务协作：

- 主 Agent 负责给出主结论
- 辅助 Agent 负责补充另一个领域的证据或限制
- 最终由编排器统一成一段可读回复

它的价值在于，用户不需要自己理解“这是两个模型说的话”，系统会替用户整理成一个结果。

### 3.4 什么时候降级

- 专业 Agent 不可用
- 置信度不足
- 请求超出当前角色边界

此时会降级到 `GeneralAgent` 或升级到 `EscalationAgent`。

这一步很重要，因为它避免系统“硬答”：

- 不够确定时，先问必要字段
- 风险太高时，直接交给人工
- 专业 Agent 掉线或失败时，先保底返回通用接待逻辑

比起让系统在不确定场景下胡说，明确降级反而更符合客服场景的生产要求。

### 3.5 什么时候压缩记忆

当工作记忆超过阈值时，旧消息会被压缩成摘要：

- 旧消息 -> LLM 摘要
- 摘要写入 Redis
- 旧消息写入 ChromaDB 情景记忆
- 工作记忆只保留最近少量消息

当前实现里，用户画像也改成了按用户稳定存储，避免按会话漂移。

压缩的真正目的不是“省一点字数”，而是防止上下文膨胀之后把高价值信息冲掉。  
客服场景里，最近几轮消息通常最重要，但前面的历史也不能全丢，所以才有“摘要 + 最近若干轮 + 长期画像”的组合。

## 4. 关键模块

### 4.1 意图识别

文件：`core/intent_recognizer.py`

EchoMind 的意图识别不是单模型分类，而是三路融合：

- LLM 语义理解
- Embedding 相似度
- Pattern 关键词匹配

输出包括：

- `intent`
- `intent_group`
- `confidence`
- `source_scores`
- `urgency`
- `entities`

#### 代码里是怎么做的

`recognize()` 里会同时启动：

- `llm_task`
- `emb_task`
- 同步的 pattern 识别

然后用 `_vote()` 融合结果。这样做的好处是：  
LLM 负责语义理解，Embedding 负责模板相似度，Pattern 负责即时兜底，三者互补。

#### 为什么这样设计

- LLM 负责复杂语义
- Embedding 负责模板相似度
- Pattern 负责零延迟兜底
- 三路并行，减少串行耗时

更具体一点：

- 只有 LLM 时，成本高且容易受提示词波动影响
- 只有 Pattern 时，覆盖窄，稍微换个说法就失效
- 只有 Embedding 时，对细粒度业务边界不够稳定

三路融合的价值不是“多路总比一路强”，而是让不同错误类型互相纠正。

#### 置信度和降级

识别结果不会无条件相信最高分，而是有阈值控制：

- 分数够高，保留细粒度意图
- 分数不足，回退成 `OTHER`
- 模型失败时，优先由 Embedding 或 Pattern 接管

这保证了系统不会因为某一路抖动就误路由到错误 Agent。

#### 支持的细粒度意图

| 意图 | 示例 |
|---|---|
| `order_status` | 订单现在到哪了 |
| `logistics` | 快递什么时候到 |
| `refund` | 退款多久到账 |
| `invoice` | 帮我开发票 |
| `payment_issue` | 为什么重复扣款 |
| `technical_login` | 登录一直报 401 |
| `technical_crash` | 应用一直崩溃 |
| `human_handoff` | 我要找人工客服 |

#### 实体提取

当前实体提取是规则优先，不是每轮都让模型抽：

- `order_id`
- `date`
- `amount`
- `error_code`

这样做的原因很现实：

- 这些实体非常结构化，规则提取更稳
- 不需要额外 LLM 成本
- 后续路由和工具调用都能直接复用

#### 紧急度

紧急度分四级：

- `LOW`
- `MEDIUM`
- `HIGH`
- `CRITICAL`

它不只是展示字段，而是会影响是否升级、是否优先转人工、是否提高路由保守程度。

### 4.2 Agent 编排

文件：`agents/agent_orchestrator.py`

编排器负责：

- 识别意图
- 计算领域分数
- 选择主 Agent 和辅助 Agent
- 执行单 Agent 或并行多 Agent
- 合并响应
- 记录路由原因和路由置信度

#### 路由不是黑盒

`RoutingDecision` 会明确记录：

- 主 Agent 是谁
- 有没有辅助 Agent
- 为什么这样路由
- 当前路由置信度多高

这点在面试里很好讲，因为它说明系统不是“碰运气选了个模型”，而是有可解释的路由层。

#### 当前角色设计

| Agent | 职责 |
|---|---|
| `GeneralAgent` | 通用分诊与澄清 |
| `TechnicalAgent` | 技术排障 |
| `BillingAgent` | 账单核验 |
| `EscalationAgent` | 人工升级交接 |

#### 角色契约

每个 Agent 都有自己的 `AgentProfile`，包含：

- `role`
- `mission`
- `workflow`
- `input_contract`
- `output_contract`
- `handoff_conditions`
- `tool_scope`

这比只靠 prompt 区分角色更可控。

#### Agent 里真正差异化的东西

现在的 Agent 差异不只是 system prompt：

- 输入契约不同
- 输出契约不同
- 工具白名单不同
- 需要的风险边界不同
- temperature 和 max_tokens 也不同

也就是说，它们已经不是“同一个模型换个提示词”，而是不同职责的运行时角色。

### 4.3 工具系统

文件：`agents/tools.py`

工具已集中管理，并按角色白名单暴露：

- 通用工具
- 技术工具
- 账单工具
- 升级工具
- 共享 RAG 工具

#### 典型工具

- `inspect_request_context`
- `suggest_required_fields`
- `lookup_error_code`
- `build_diagnostic_plan`
- `check_billing_fields`
- `compare_amounts`
- `create_handoff_summary`
- `search_knowledge_base`

#### 设计要点

- 工具参数有 JSON Schema
- 编排器会做参数校验
- 工具只暴露白名单
- RAG 是所有 Agent 共享能力

#### 为什么要集中到一个文件

工具集中后有三个好处：

1. **更容易审计**：一眼能看到每个工具能做什么
2. **更容易复用**：共享 RAG 不用在多个 Agent 里重复写
3. **更容易控制风险**：不会出现某个 Agent 误调用不该有的能力

#### 工具设计原则

- 工具必须确定性强
- 工具必须尽量可解释
- 工具不伪造外部系统结果
- 工具只返回“可以确认的事实”或“明确的降级结果”

这和客服场景是匹配的，因为客服最怕的是“模型编了一个看似合理但实际不对的操作结果”。

### 4.4 三级记忆

文件：`memory/conversation_memory.py`

当前是三层记忆：

| 记忆层 | 存储 | 作用 |
|---|---|---|
| 工作记忆 | Redis | 当前会话最近消息 |
| 情景记忆 | ChromaDB | 历史对话摘要，支持语义检索 |
| 用户画像 | ChromaDB | 长期偏好和关键实体 |

#### 当前实现特点

- 工作记忆超过阈值会压缩
- 摘要采用合并更新，不再无限拼接
- 情景记忆检索优先当前会话，再回退到同用户全局检索
- 用户画像按 `user_id` 稳定存储
- `to_prompt_text()` 只拼最近少量消息，避免上下文过长

#### 为什么要分三层

如果只保留最近对话，系统会忘记用户长期偏好。  
如果只保留长期画像，系统会失去当前上下文。  
如果把所有历史全塞进 prompt，又会触发上下文爆炸。

所以三层记忆本质上是在做“时间尺度分离”：

- 工作记忆管当前轮
- 情景记忆管跨会话线索
- 用户画像管长期偏好

#### 现在的优化方向

当前这层已经比最初稳定很多，但后续还可以继续做：

- 摘要更结构化，显式记录“待办、风险、实体、结论”
- 检索加入时间衰减
- 画像按字段合并，而不是整块重写
- 对高价值实体做显式索引

这些都能进一步减少“记住了，但没记对”的问题。

### 4.5 知识库与 RAG

文件：`mcp/tool_manager.py`、`mcp/knowledge_base.py`

知识库链路包括：

1. 查询改写
2. 并行召回
3. 合并去重
4. LLM 重排
5. Top-K 注入上下文

知识库不是独立演示功能，而是接入了 `/chat` 主链路。

#### 为什么要先看意图再查知识库

不是所有请求都值得检索：

- 问候、反馈、转人工不需要查
- 明确的技术排障需要查技术文档
- 账单问题需要查政策和流程

如果所有问题都盲目检索，系统会：

- 增加延迟
- 引入无关上下文
- 让模型被噪声干扰

所以这里做了“意图驱动检索”，而不是“见词就搜”。

#### 工具可靠性设计

RAG 工具不是直接查一下就完了，还加了：

- 参数校验
- 缓存
- 超时
- 熔断
- fallback

这是很典型的生产化处理方式，因为检索系统也会坏，不能把主对话链路一起拖垮。

### 4.6 Skills 动态注入

文件：`core/skill_loader.py`

Skills 用于把客服规范、处理边界、角色约束动态注入到 Agent 的 system prompt。

适合表达：

- 技术 Agent 如何排障
- 账单 Agent 不能承诺退款
- 通用 Agent 先澄清再处理

支持热加载，不需要重启服务。

#### Skills 和工具的区别

- **工具**解决“能做什么”
- **Skills**解决“应该怎么做”

比如：

- 工具可以检查账单字段是否齐全
- Skills 会告诉账单 Agent 不能承诺退款到账时间

这个分层很重要，因为它让业务规范可以独立更新，而不必改代码。

### 4.7 Monitor 与降权

文件：`monitor/performance_monitor.py`

Monitor 会采集：

- Agent 成功率
- Agent 平均延迟
- 工具成功率
- 工具平均延迟

并把异常反馈给路由层，影响后续 `routing_score()`。

#### 路由为什么要吃监控结果

因为静态路由不够现实。  
一个 Agent 即使逻辑上最适合，实际在线上也可能出现：

- 成功率下降
- 延迟变高
- 工具依赖异常

Monitor 的作用就是把“运行时健康度”纳入路由，让系统能绕开状态变差的节点。

### 4.8 端到端评测

文件：`evaluation/evaluator.py`

评测包括：

- 意图识别 Accuracy
- Macro-F1
- LLM-as-Judge 四维评分
- 回归检测
- 优化建议

LLM-as-Judge 评分维度：

- 相关性
- 准确性
- 完整性
- 有用性

#### 为什么要做这个

如果没有评测，系统优化会变成纯感觉：

- 你可能觉得 prompt 更好了
- 但实际意图识别可能更差了
- 你可能觉得回复更长了
- 但用户体验反而更糟

所以评测是为了把“感觉”变成“指标”。

#### 适合面试怎么说

可以说：

> 我不仅做了多 Agent 编排，还把意图识别和回复质量都接进了评测链路，支持 Accuracy、Macro-F1 和 LLM-as-Judge 四维评分，能做回归检测。

## 5. 重点代码阅读顺序

建议按这个顺序看：

1. [api/main.py](/Users/xiao_xiong/Desktop/code/EchoMind/api/main.py)
2. [core/intent_recognizer.py](/Users/xiao_xiong/Desktop/code/EchoMind/core/intent_recognizer.py)
3. [agents/agent_orchestrator.py](/Users/xiao_xiong/Desktop/code/EchoMind/agents/agent_orchestrator.py)
4. [agents/tools.py](/Users/xiao_xiong/Desktop/code/EchoMind/agents/tools.py)
5. [memory/conversation_memory.py](/Users/xiao_xiong/Desktop/code/EchoMind/memory/conversation_memory.py)
6. [mcp/tool_manager.py](/Users/xiao_xiong/Desktop/code/EchoMind/mcp/tool_manager.py)
7. [mcp/knowledge_base.py](/Users/xiao_xiong/Desktop/code/EchoMind/mcp/knowledge_base.py)
8. [core/skill_loader.py](/Users/xiao_xiong/Desktop/code/EchoMind/core/skill_loader.py)
9. [monitor/performance_monitor.py](/Users/xiao_xiong/Desktop/code/EchoMind/monitor/performance_monitor.py)
10. [evaluation/evaluator.py](/Users/xiao_xiong/Desktop/code/EchoMind/evaluation/evaluator.py)

### 5.1 为什么这个顺序最省力

这个顺序是从“请求入口”往“支撑系统”走：

- 先看入口，知道系统怎么收请求
- 再看识别，知道系统怎么理解问题
- 再看编排，知道系统怎么决定谁来处理
- 再看工具和记忆，知道系统怎么补上下文
- 再看知识库和 Skills，知道系统怎么带业务规则
- 最后看监控和评测，知道系统怎么持续变好

## 6. 使用指南

### 6.1 项目结构

```text
api/            HTTP 入口
agents/         Agent、路由、工具
core/           意图识别、Skills、LLM 工具
memory/         三级记忆
mcp/            知识库和工具管理
monitor/        在线监控
evaluation/     评测
skills/         动态技能文档
wiki/           项目文档
```

这套结构本身也适合在面试时解释：

- `core` 是“理解层”
- `agents` 是“决策和执行层”
- `memory` 是“上下文层”
- `mcp` 是“外部知识和工具层”
- `monitor` 和 `evaluation` 是“治理层”

### 6.2 环境准备

核心依赖：

- Anthropic API Key
- Redis
- ChromaDB
- Python 运行环境

启动前通常需要配置 `.env`，至少包含：

- `ANTHROPIC_API_KEY`
- `ANTHROPIC_MODEL`
- `REDIS_URL`
- `CHROMA_HOST`
- `CHROMA_PORT`

如果是本地跑，最先需要确认的是：

- Anthropic Key 是否可用
- Redis 是否连通
- ChromaDB 是否启动
- `.env` 是否被加载

因为这几个组件任何一个缺失，都会影响主链路。

### 6.3 启动方式

项目支持两种常见方式：

- Docker Compose 全栈启动
- 本地开发模式运行 API

如果是学习代码，建议先本地跑 API；如果是验证完整链路，再用 Docker Compose。

### 6.4 常用接口

| 接口 | 作用 |
|---|---|
| `GET /health` | 健康检查 |
| `POST /chat` | 主对话接口 |
| `GET /skills` | 查看 Skills |
| `POST /skills/reload` | 热加载 Skills |
| `GET /monitor` | 查看监控状态 |
| `GET /metrics` | Prometheus 指标 |
| `POST /search` | 知识库检索 |
| `POST /knowledge/add` | 添加知识库文档 |
| `POST /knowledge/upload` | 上传文件进知识库 |
| `GET /knowledge/stats` | 知识库统计 |
| `POST /eval/run` | 运行端到端评测 |

其中最值得重点关注的是：

- `/chat`：真实业务主链路
- `/eval/run`：质量评测闭环
- `/skills/reload`：业务规则热更新
- `/monitor`：运行健康状态

### 6.5 `/chat` 是怎么走的

一次请求里，`/chat` 的关键动作其实是：

1. 先从 memory 拿上下文
2. 再从 intent recognizer 得到结构化判断
3. 再由 orchestrator 决定主辅 Agent
4. 再按需查知识库
5. 再让 Agent 生成回复
6. 再把本轮信息写回 memory

这条链路的重点是：**每一步都可插拔、可观测、可回放**。

### 6.6 调试记忆

如果要排查上下文问题，优先看：

- Redis 工作记忆
- Redis summary
- ChromaDB `episodic`
- ChromaDB `user_profile`

一般排障顺序是：

1. 先看工作记忆有没有写进去
2. 再看摘要有没有生成
3. 再看情景记忆有没有存成功
4. 最后看画像是否更新

这样能快速判断问题是在写入、压缩还是检索。

### 6.7 调试知识库

如果 `/chat` 没有触发知识库：

- 先看意图是否属于业务类
- 再看 `_should_use_knowledge()` 的判断
- 最后看 `knowledge_search` 是否成功返回结果

如果知识库结果不准，通常排查这几个点：

- 查询改写是否偏题
- 召回是否太少
- 重排是否把关键文档压下去了
- 注入上下文时是否截断过多

### 6.8 调试路由

如果 Agent 选错了，通常看三处：

- `intent_group` 是否正确
- `RoutingDecision` 的 `routing_reason`
- `AgentStats.routing_score()` 是否被降权影响

这比单看最终回复更有用，因为路由问题通常不是在生成阶段出现的。

### 6.9 评测建议

建议优先跑：

1. 意图识别用例
2. 对话质量用例
3. 回归基线

这样能比较快定位问题是出在识别、路由还是回复质量。

如果是拿来面试，最好能讲出：

- 哪个指标代表识别能力
- 哪个指标代表生成质量
- 哪个指标代表系统稳定性
- 哪个指标代表回归风险

这样面试官会觉得你不是只会“调一个能跑的系统”，而是真的懂怎么衡量它。

## 7. 面试可讲亮点

如果你要拿这个项目去面试，可以优先讲这几句：

- 我做的是一个多 Agent 客服编排系统，不是单一聊天机器人。
- 意图识别用了 LLM、Embedding 和 Pattern 三路融合。
- Agent 不只是 prompt 不同，还做了角色契约和工具白名单。
- 记忆分成工作记忆、情景记忆和用户画像三层。
- 系统有知识库、监控、评测和路由降权闭环。
- 多 Agent 支持主辅协作，不是简单命中一个模型就结束。

如果面试官继续追问，你可以进一步展开：

- 为什么要三路意图融合，而不是只用一个模型
- 为什么要把工具抽到统一文件里
- 为什么要把记忆分成三层
- 为什么要让知识库进入主链路
- 为什么要让监控结果反馈到路由

这些问题都能自然地把项目讲深。

## 8. 常见问题

### 8.1 为什么不是直接用一个大模型回答

因为真实客服场景里，单模型容易：

- 分流不准
- 上下文断裂
- 无法约束业务边界
- 没法做评测和治理

### 8.2 为什么要有多个 Agent

因为不同业务域的输入、风险边界和工具都不同。

### 8.3 为什么不是把所有能力都塞进一个大 Prompt

因为那样会出现三个问题：

- 角色边界不清
- 工具权限不清
- 出错后难定位

拆成多个 Agent 后，每个角色都可以独立调优、独立评测、独立降权。

### 8.4 为什么要做三层记忆

因为单轮历史不够，长期用户信息也不能每次都塞进 prompt。

### 8.5 为什么要做评测

因为没有评测，就很难知道是模型、路由、知识库还是工具出了问题。

### 8.6 为什么要做监控

因为线上系统不是静态的。模型、工具、知识库、延迟、失败率都会变化，必须有运行时治理。

## 9. 一句话总结

EchoMind 的核心不是“会聊天”，而是把客服系统里最关键的几件事工程化了：

- 识别问题
- 分配角色
- 调用工具
- 维护记忆
- 接入知识库
- 监控质量
- 量化评测

如果再压缩成一句面试话术，可以说：

> 我做的是一个可观测、可评测、可降级的多 Agent 客服编排系统，把意图识别、路由、知识检索、记忆、Skills、监控和评测串成了完整闭环。

