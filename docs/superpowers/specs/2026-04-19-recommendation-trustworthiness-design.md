# Recommendation Trustworthiness Design

## 背景

`Stock Pilot` 已经具备推荐、推荐日志、推荐复盘和个股诊断能力，但“推荐结果更可信”这件事还没有形成统一合同。当前系统已经开始区分 `demo/live`，复盘也会优先使用真实样本，不过用户仍然很容易在三个层面产生疑问：

- 当前推荐为什么推，证据是否足够具体
- 这条推荐基于示例数据还是真实同步数据
- 复盘页展示的“命中率 / 平均收益”到底统计了什么，样本是否已经成熟

这会带来两个直接问题：

- 用户无法快速判断当前结论是“可重点参考”还是“先当流程演示看”
- 运行中样本、演示样本、正式复盘样本的口径容易被混在一起理解

## 目标

这一轮不重写选股算法，而是先把推荐链路升级成一个“会自证其依据”的系统。完成后，用户在推荐页、复盘页、个股详情页都应该能明确回答四个问题：

1. 为什么推这只票
2. 基于什么数据推这只票
3. 历史统计到底统计了什么
4. 当前这些统计是否已经成熟到足以判断真实效果

## 非目标

本轮不包含以下工作：

- 重做信号引擎和评分算法
- 引入回测引擎、滑点、手续费、基准超额收益
- 建立完整前端单元测试体系
- 扩展到多市场或实盘交易链路

## 方案对比

### 方案 A：只补说明文案

优点：

- 改动最小
- 风险最低

缺点：

- 可信度提升主要停留在展示层
- 后端没有形成稳定字段合同，后续容易继续漂移

### 方案 B：直接重做评分算法

优点：

- 长期上限更高
- 能直接提升推荐质量

缺点：

- 改动深、验证成本高
- 即使算法变好，用户仍可能看不懂当前结论能不能信

### 方案 C：端到端可信度改造

优点：

- 同时解决“解释不透明、数据口径不清、复盘成熟度不明”三类问题
- 风险明显低于直接重做算法
- 能为后续算法升级提供稳定的接口和页面承载层

缺点：

- 需要同时修改后端 schema、服务层、前端展示和 API 测试

推荐采用方案 C。

## 当前问题归纳

### 1. 当前推荐解释力度不足

推荐列表现在主要暴露总分、thesis、risk、事件摘要、涨跌归因摘要，但缺少对“最核心证据”的结构化表达。用户看到一张卡片后，仍然要自己推断：

- 这只票是技术面强还是资金面强
- 当前是因为真实同步数据被推出来，还是示例数据演示出来
- 系统自己是否认为这条推荐只能谨慎参考

### 2. 推荐页顶部统计容易与正式复盘混淆

推荐页顶部的“最近命中率 / 平均当前收益 / 最佳记录”是按当前价格回看推荐日志得到的浮动快照，不等于正式复盘结论。如果样本尚未走完预期持有窗口，这组统计会天然偏早，容易被误读为系统已经完成验证。

### 3. 复盘页缺少样本成熟度表达

复盘页已经能够区分 `demo/live` 并且优先使用真实样本，但当前还缺少：

- 每个窗口的成熟样本数
- 未成熟样本数
- 复盘结果的整体信任等级
- 为什么现在应该谨慎参考或可以重点参考

### 4. 推荐页、复盘页、个股详情页尚未形成统一口径

个股详情页能解释“为什么推 / 为什么没推”，复盘页能展示历史统计，推荐页能展示当前候选，但三者之间缺少一套统一的可信度字段和文案规则。

## 设计原则

- 所有“可信度”表达都必须来源于后端显式字段，不依赖前端硬编码猜测
- `demo/live` 必须贯穿当前推荐、推荐日志和复盘结果
- 运行中样本与成熟样本必须分开统计
- 推荐页负责“当前可不可以重点看”，复盘页负责“历史上有没有被验证”，个股详情页负责“单票为什么推或没推”
- 先建立稳定合同，再考虑后续算法升级

## 目标架构

### 一、当前推荐增加轻量可信度合同

`GET /api/recommendations` 继续返回当前候选池，但每条推荐补充可信度表达字段：

- `data_mode`
  说明当前候选来自 `demo` 还是 `live`
- `snapshot_updated_at`
  当前快照更新时间
- `strongest_signals`
  推荐卡片上最值得看的前两项强项摘要
- `primary_risk`
  当前最主要的一个风险点
- `confidence_score`
  一个轻量 0-100 可信度分，表达“当前这条推荐结论的可参考程度”
- `confidence_notice`
  一条简短说明，例如“当前基于真实快照，但仍需继续观察持有窗口兑现情况”

这里的 `confidence_score` 不等于选股分数，它表达的是“当前解释和样本状态是否足够支撑用户重点关注”，而不是“股票未来一定会涨”的概率。

### 二、推荐日志补齐跟踪状态

`GET /api/recommendations/journal` 在现有日志字段上补充：

- `days_since_publish`
  当前距离推荐发出已过去多少个自然日
- `tracking_status`
  枚举值建议为 `tracking` / `matured`
- `is_matured_for_expected_window`
  是否已经走完预期持有窗口对应的交易日窗口

这里明确约定：

- `days_since_publish` 只用于前端提示“这条推荐发出多久了”
- `is_matured_for_expected_window` 必须按价格序列中是否已经走完 `expected_holding_days` 个交易日来判断，不能按自然日替代

这些字段用于把推荐页顶部统计明确限定为“运行中跟踪快照”，而不是正式复盘结论。

### 三、复盘接口补齐成熟度和信任等级

`GET /api/recommendations/review` 在现有基础上补充：

- `trust_level`
  枚举值建议为 `low` / `medium` / `high`
- `trust_reasons`
  一组直接说明当前信任等级来源的文案
- `maturity_breakdown`
  按窗口返回样本成熟度

`maturity_breakdown` 的最小结构：

- `window_days`
- `total_samples`
- `matured_samples`
- `immature_samples`

这样复盘页不仅知道“总样本数是多少”，还知道“真正已经走完窗口、可用于判断这个窗口效果的样本数是多少”。

### 四、页面层形成统一可信度体验

#### 推荐页

- 推荐卡片新增“强项摘要 / 主要风险 / 数据模式”
- 顶部三张统计卡明确改为“运行中跟踪快照”
- 当日志样本多数未成熟时，给出保守提示
- 如果存在 `demo` 样本但当前已有 `live` 样本，继续明确示例样本不纳入当前统计

#### 复盘页

- 第一屏优先展示 `evaluation_mode`、`trust_level`、`trust_reasons`
- 每个 5/10/20 日窗口明确展示成熟样本数和未成熟样本数
- 让用户先理解“能不能信”，再去看命中率、平均收益、最佳样本和最差样本

#### 个股详情页

- 不重做整体结构
- 增加小型“推荐可信度说明”区块
- 将 `signal_breakdown`、`recommendation_diagnosis`、`risk_notes` 串起来，统一成与推荐页一致的口径

## 字段计算建议

### `strongest_signals`

来源于现有 `signal_breakdown`，按分值倒序取前两项，保留维度和摘要。

### `primary_risk`

优先取现有 `risk_notes[0]`，没有时回退到 `risk`。

### `data_mode`

当前规则保持不变：

- `source` 以 `sample` 开头时视为 `demo`
- 其他视为 `live`

### `confidence_score`

本轮采用保守的启发式规则，而不是重新训练或重写选股逻辑。为避免实现漂移，先约定一个固定计算框架：

- `signal_base`
  取前两项 strongest signal 的平均分；如果不足两项，则回退到已有项平均值
- `mode_bonus`
  `live` 加 10 分，`demo` 减 10 分
- `risk_penalty`
  存在 `primary_risk` 时减 8 分
- `final_score`
  `signal_base * 0.7 + mode_bonus - risk_penalty`，最终再限制在 `20-95`

`confidence_score` 只表达“这条当前推荐结论的可参考程度”，不引用复盘全局成熟度，避免让推荐列表和复盘服务形成过深耦合。

### `trust_level`

可由复盘整体条件决定，并在本轮先固定为下面的阈值规则：

- `high`
  `evaluation_mode = live`，且 `20 日窗口 matured_samples >= 16`
- `medium`
  `evaluation_mode = live`，且 `20 日窗口 matured_samples` 在 `6-15`
- `low`
  其余所有情况，包括仍主要依赖示例样本，或真实样本极少，或 `20 日窗口 matured_samples < 6`

### `trust_reasons`

必须是具体、可读、能解释约束的语句，例如：

- “当前 20 日窗口成熟真实样本不足，暂时更适合把结果当作方向参考”
- “当前复盘已切换到真实样本统计，示例样本仅保留做流程演示”
- “多数样本仍在跟踪中，推荐页顶部统计不应视为正式命中率”

每次返回至少 2 条 `trust_reasons`，其中一条必须解释样本来源，另一条必须解释成熟度约束。

## 后端改造范围

### Schema

扩展：

- `RecommendationItem`
- `RecommendationJournalItem`
- `RecommendationReviewResponse`

新增必要的子结构，例如：

- `RecommendationConfidenceSignal`
- `RecommendationReviewMaturityMetric`

### Service

重点修改：

- `backend/app/services/market_store.py`
  为推荐列表注入可信度字段
- `backend/app/services/recommendation_service.py`
  计算日志成熟度字段
- `backend/app/services/recommendation_review_service.py`
  计算复盘信任等级与窗口成熟度
- `backend/app/services/recommendation_diagnosis_service.py`
  在不改变原职责的前提下复用现有解释能力

## 前端改造范围

重点修改：

- `frontend/src/types/market.ts`
  与后端 schema 对齐
- `frontend/src/views/RecommendationView.vue`
  呈现推荐级别可信度和运行中跟踪快照
- `frontend/src/views/ReviewView.vue`
  呈现复盘信任等级、成熟度和原因
- `frontend/src/views/StockDetailView.vue`
  呈现单票可信度说明

## 测试策略

### 后端测试

必须新增或补强：

- 推荐接口返回新可信度字段
- 推荐日志能正确区分 `tracking` / `matured`
- 复盘接口能正确返回 `trust_level`、`trust_reasons`、`maturity_breakdown`
- `live` 优先而 `demo` 不混算的规则继续有效

### 前端验证

本轮不引入新的前端测试框架，先用当前仓库已有的验证手段收敛风险：

- 后端 API 测试
- 前端 TypeScript 构建
- 必要的源码断言测试

## 成功标准

本轮完成后，至少满足以下结果：

1. 用户在推荐页能看懂“为什么推、基于什么数据推、哪里需要谨慎”
2. 用户在推荐页不会把运行中跟踪快照误解为正式复盘结论
3. 用户在复盘页能看懂不同窗口到底成熟了多少样本
4. 用户能通过 `trust_level` 和 `trust_reasons` 判断当前复盘结论的可参考程度
5. 推荐页、复盘页、个股详情页对同一只票的解释口径保持一致

## 风险与约束

- `confidence_score` 属于启发式可信度分，不应被表述为收益概率
- 当前仓库前端尚无完整单测基建，本轮以前后端接口验证和构建校验为主
- 若后续要继续提高“推荐本身的有效性”，仍需在下一轮单独进入算法、样本和评估方法升级

## 下一步

在该 spec 被确认后，进入 implementation plan，按如下顺序执行：

1. 先锁定 schema 和 response contract
2. 再补 service 计算逻辑
3. 再调整推荐页、复盘页、个股详情页
4. 最后补齐测试并做全量回归
