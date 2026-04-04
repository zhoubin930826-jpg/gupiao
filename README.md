# Stock Pilot

一个面向个人本地使用的股票分析系统 MVP，采用前后端分离架构，目标是先把“数据可拉取、页面可操作、推荐可解释、结果可追踪”这一整条链路跑通。

当前项目更适合你作为本地研究台来使用，而不是直接拿去做实盘自动交易。它现在已经能完成：

- 页面化查看市场看板、提醒中心、股票列表、个股详情、推荐中心、推荐复盘、交易计划、组合持仓、自选池、策略配置、数据任务
- 本地保存业务配置、任务记录、推荐历史、交易计划、提醒事件、组合持仓、自选池、行情快照和价格序列
- 在 `demo` 模式下即开即用
- 在 `AKShare` 模式下拉取 A 股快照、前复权日线和财务摘要，并带基础重试与多来源兜底
- 根据技术面、基本面、资金面、情绪面四个维度给股票打分
- 保存每次推荐结果，并在页面里回看当前收益、命中率和历史表现

如果你是第一次真正使用这套系统，建议先读：

- [docs/BEGINNER_GUIDE.md](/Users/zhoubin/work/ideaWorkSpace/zhou/gupiao/docs/BEGINNER_GUIDE.md)

## 项目定位

这个项目当前是一个“可运行、可继续演进”的本地研究系统，不是完整量化平台。

适合的场景：

- 你个人在本机搭建自己的 A 股研究后台
- 你想先把数据采集、策略筛选、推荐展示和结果追踪串起来
- 你希望后面继续往自选池、回测、因子分析、更多数据源扩展

当前不包含：

- 登录鉴权和多用户体系
- 自动下单、券商接口、实盘交易
- 完整回测引擎
- 稳定的生产级多数据源容灾

## 当前技术栈

- 前端：`Vue 3` + `Vite` + `TypeScript` + `Element Plus` + `Pinia` + `Vue Router` + `ECharts`
- 后端：`FastAPI` + `SQLAlchemy`
- 业务库：`SQLite`
- 行情分析库：`DuckDB`
- 数据采集：`AKShare` + 第三方公开站点兜底
- 测试：`pytest`

之所以默认使用 `SQLite + DuckDB`，是为了让你在本机几乎零门槛就能启动。等你后面需要更强的业务库能力时，可以把业务库切到 PostgreSQL。

## 已实现能力

### 页面能力

- 市场看板
  - 市场概览指标
  - 市场温度曲线
  - 行业热度榜
  - 今日高分候选池
  - 待处理提醒预览
- 提醒中心
  - 汇总计划触发、止损风险、目标接近、仓位过重和自选池转强提醒
  - 支持按状态、优先级、来源筛选
  - 支持手动重新评估提醒
  - 支持把提醒标记为已处理或已解决
- 股票列表
  - 按代码或名称搜索
  - 按板块筛选
  - 查看最新价、涨跌幅、换手率、PE、评分、标签和一句话结论
- 个股详情
  - K 线和均线
  - 四维评分拆解
  - 推荐逻辑和风险提示
  - 财务快照与简要财务解读
- 推荐中心
  - 当前推荐卡片
  - 推荐理由、风险、标签、关注窗口、预计持有天数
  - 近 5 日、近 20 日表现
  - 推荐历史记录表
  - 最近命中率、平均当前收益、最佳记录
- 推荐复盘
  - 按 5 日、10 日、20 日窗口复盘历史推荐收益
  - 查看按推荐批次汇总后的平均表现
  - 查看最佳样本、最差样本和逐条推荐明细
- 交易计划
  - 新建计划中、持有中、已平仓、已取消四种状态的交易记录
  - 记录计划价、实际入场价、实际离场价、止损价、目标价和计划仓位
  - 自动联动最新价、计划偏差、浮动收益、已实现收益和盈亏比
  - 支持从推荐中心和个股详情直接加入交易计划
- 组合持仓
  - 维护组合账户名称、初始资金、基准和备注
  - 录入持有中、已平仓两种状态的持仓记录
  - 自动计算预计总资产、预计现金、仓位利用率、浮动盈亏、已实现盈亏和组合收益
  - 查看单只持仓的成本、市值、权重、止损距离、目标距离和标签
  - 支持从交易计划一键转入组合持仓
- 自选池
  - 从股票列表、个股详情、推荐中心加入或移出自选
  - 查看加入价、最新价、当前收益、评分和标签
  - 切换观察中、持有中、已归档三种跟踪状态
  - 记录观察备注
- 策略配置
  - 技术面、基本面、资金面、情绪面权重
  - 调仓周期
  - 最低换手率
  - 最少上市天数
  - 是否排除 ST
  - 是否排除次新股
- 数据任务
  - 查看任务状态
  - 手动提交市场同步
  - 后台异步执行同步
  - 前端自动轮询运行中任务

### 后端能力

- 应用启动时自动初始化数据库和示例数据
- 提供 REST API 给前端调用
- 维护业务库中的策略配置、任务记录、推荐历史、复盘样本、交易计划、提醒事件、组合持仓和自选池
- 维护 DuckDB 中的股票快照、历史价格、行业热度、市场温度、推荐结果
- 支持 `demo` 和 `AKShare` 两种数据模式
- 真实同步内置快照、历史、财务三段采集链，并带超时、重试和来源兜底
- AKShare 同步失败时自动回退到示例数据

### 数据能力

- 示例模式下自动生成一套可浏览、可测试的市场数据
- 真实模式下可拉取：
  - A 股实时快照
  - 前复权日线历史
  - 财务摘要快照
- 基于真实或示例数据统一生成：
  - 股票池快照
  - 价格序列
  - 推荐结果
  - 市场温度
  - 行业热度

## 当前架构

### 前后端拆分

- `frontend` 提供可视化页面
- `backend` 提供 API、数据同步、评分逻辑和本地存储

### 存储拆分

- `SQLite`
  - 策略配置
  - 数据任务记录
  - 推荐历史日志
  - 交易计划与持仓记录
  - 提醒事件
  - 组合账户与组合持仓
  - 自选池
- `DuckDB`
  - 股票快照
  - 股票历史价格
  - 行业热度
  - 市场温度
  - 当前推荐结果
  - 同步元数据

### 数据流

1. 前端在页面上触发“提交同步”
2. 后端创建 `market-sync` 任务并进入 `running`
3. 如果开启 `AKShare`，后端抓取 A 股快照、历史日线和财务摘要
4. 快照优先走东方财富，失败时切到新浪；历史优先走东方财富，失败时切腾讯，再兜底新浪
5. 根据信号引擎计算四维评分、推荐理由、风险提示和标签
6. 刷新 DuckDB 中的快照、价格、行业热度、市场温度、推荐结果
7. 如果同步成功，把当前推荐结果写入推荐历史表
8. 复盘页会基于推荐历史和价格序列计算窗口收益
9. 你可以把高分候选进一步写成交易计划，记录计划价、止损价、目标价和执行状态
10. 同步完成后，系统会自动评估提醒，把计划触发、止损风险、目标接近、仓位过重和自选池异动写入提醒中心
11. 你可以把交易计划进一步转成组合持仓，跟踪仓位利用率、持仓盈亏和组合集中度
12. 你可以把关心的标的加入自选池，并继续维护跟踪状态和备注
13. 前端轮询任务状态并刷新页面

## 目录结构

```text
.
├── backend
│   ├── app
│   │   ├── api
│   │   │   └── routes
│   │   ├── core
│   │   ├── db
│   │   ├── models
│   │   ├── schemas
│   │   └── services
│   ├── data
│   ├── requirements.txt
│   └── tests
├── frontend
│   ├── src
│   │   ├── api
│   │   ├── components
│   │   ├── layouts
│   │   ├── router
│   │   ├── stores
│   │   ├── types
│   │   └── views
│   └── package.json
├── docker-compose.yml
└── README.md
```

## 快速启动

### 1. 启动后端

```bash
cd /Users/zhoubin/work/ideaWorkSpace/zhou/gupiao
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
cp backend/.env.example backend/.env
uvicorn app.main:app --reload --app-dir backend
```

后端默认地址：

- `http://127.0.0.1:8000`
- Swagger 文档：`http://127.0.0.1:8000/docs`

### 2. 启动前端

```bash
cd /Users/zhoubin/work/ideaWorkSpace/zhou/gupiao/frontend
npm install
npm run dev
```

前端默认地址：

- `http://127.0.0.1:5173`

### 3. 默认行为

首次启动时，系统会自动初始化：

- `backend/data/stockpilot.db`
- `backend/data/market.duckdb`

如果当前是 `demo` 模式，系统会自动写入示例数据，所以你启动后就能直接浏览页面。

## 运行模式

### `demo` 模式

适合先把页面、接口和交互都跑通。

特点：

- 不依赖外部数据源
- 启动稳定
- 适合开发和测试
- 页面会有完整示例数据

注意：

- 当前代码会在检测到数据源是 `sample` 时重新刷新示例数据，以确保示例结构和最新 schema 保持一致

### `AKShare` 模式

适合把系统从“静态原型”推进到“本地真实研究工具”。

开启方式：

1. 打开 [backend/.env.example](/Users/zhoubin/work/ideaWorkSpace/zhou/gupiao/backend/.env.example) 对应复制出的 `backend/.env`
2. 把 `ENABLE_AKSHARE_SYNC=false` 改成 `true`
3. 重新启动后端
4. 在“数据任务”页面点击“提交同步”

当前 AKShare 模式会做这些事：

- 拉取 A 股实时快照
- 按策略过滤候选股票
- 为候选股票补前复权日线
- 为候选股票补财务摘要快照
- 计算四维评分、标签、推荐理由和风险提示
- 刷新本地行情库
- 同步成功后写入推荐历史

当前真实采集链路的兜底顺序：

- 快照：东方财富轻量接口 -> 新浪快照接口 -> AKShare 默认东财快照
- 历史日线：东方财富日线 -> 腾讯日线 -> 新浪日线
- 财务摘要：同花顺财务摘要

为了降低外部站点波动带来的失败概率，当前后端已经加入：

- 请求超时控制
- 固定次数重试
- 重试间隔退避
- 失败后自动回退到示例数据

实测提醒：

- 真实同步已经可以成功落到 `akshare-live`
- 当 `AKSHARE_STOCK_LIMIT=60`、`AKSHARE_MAX_WORKERS=4` 时，单次同步通常需要几分钟，属于正常现象
- 如果你更关注手动触发时的体验，可以先把候选数调到 `20` 或 `30`

当前 `demo` 模式还会自动回填一批历史推荐样本，方便你直接查看复盘页面，而不需要先手动累计很多天的数据。

如果真实同步失败：

- 任务状态会显示 `warning`
- 系统会自动回退到示例数据

## 环境变量

当前项目支持的核心环境变量如下：

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `APP_MODE` | `demo` | 应用模式标记，只用于标识当前运行模式 |
| `ENABLE_TASK_SCHEDULER` | `true` | 是否启用 APScheduler 自动调度 |
| `SCHEDULER_MARKET_HOUR` | `18` | 市场同步任务小时 |
| `SCHEDULER_MARKET_MINUTE` | `10` | 市场同步任务分钟 |
| `SCHEDULER_SIGNAL_HOUR` | `18` | 因子刷新任务小时 |
| `SCHEDULER_SIGNAL_MINUTE` | `20` | 因子刷新任务分钟 |
| `SCHEDULER_PUBLISH_HOUR` | `18` | 推荐发布任务小时 |
| `SCHEDULER_PUBLISH_MINUTE` | `30` | 推荐发布任务分钟 |
| `ENABLE_AKSHARE_SYNC` | `false` | 是否启用 AKShare 真实同步 |
| `AKSHARE_REQUEST_TIMEOUT` | `20` | 第三方行情请求超时时间，单位秒 |
| `AKSHARE_RETRY_ATTEMPTS` | `3` | 快照、日线、财务请求失败后的重试次数 |
| `AKSHARE_RETRY_DELAY_MS` | `1200` | 重试间隔，单位毫秒 |
| `AKSHARE_STOCK_LIMIT` | `80` | 单次同步最多处理多少只候选股票 |
| `AKSHARE_HISTORY_DAYS` | `180` | 用于控制单只股票的目标历史窗口 |
| `AKSHARE_MAX_WORKERS` | `6` | 历史和财务抓取线程数 |
| `CORS_ORIGINS` | `["http://127.0.0.1:5173","http://localhost:5173"]` | 前端允许跨域来源 |
| `BUSINESS_DATABASE_URL` | `sqlite:///.../backend/data/stockpilot.db` | 业务库连接串，默认指向项目内的 SQLite 文件 |
| `MARKET_DATABASE_PATH` | `.../backend/data/market.duckdb` | DuckDB 数据文件路径，默认指向项目内的数据文件 |
| `APP_TIMEZONE` | `Asia/Shanghai` | 任务时间和时间戳使用的时区 |

当前示例环境文件在 [backend/.env.example](/Users/zhoubin/work/ideaWorkSpace/zhou/gupiao/backend/.env.example)。
当前这台机器已经切到真实模式，实际运行中的配置文件在 [backend/.env](/Users/zhoubin/work/ideaWorkSpace/zhou/gupiao/backend/.env)。

## 页面说明

### 市场看板

对应路由：`/`

用途：

- 先看市场概况
- 快速扫行业热度
- 看系统当日高分候选
- 看今天有哪些提醒值得优先处理

页面数据来源：

- `/api/dashboard/summary`
- `/api/alerts/overview`

### 提醒中心

对应路由：`/alerts`

展示内容：

- 待处理、高优先级、已处理、最近评估时间
- 提醒列表
- 优先级、状态、来源、提醒内容、当前值和阈值

支持操作：

- 手动重新评估提醒
- 按状态、优先级、来源筛选
- 打开个股详情或来源页面
- 把提醒标记为已处理或已解决

当前提醒规则包含：

- 交易计划接近买点
- 交易计划触及止损或接近目标
- 持仓触及止损
- 持仓接近目标位
- 单票仓位偏重
- 持仓回撤扩大
- 自选池进入高分观察区
- 自选池异动转强

页面数据来源：

- `GET /api/alerts/overview`
- `POST /api/alerts/evaluate`
- `PUT /api/alerts/{id}`

### 股票列表

对应路由：`/stocks`

用途：

- 按条件圈定股票池
- 从列表进入个股详情

支持：

- 代码/名称关键字搜索
- 板块筛选
- 固定每页 50 条

页面数据来源：

- `/api/stocks`

### 个股详情

对应路由：`/stocks/:symbol`

展示内容：

- 最新价格和涨跌幅
- K 线与均线
- 技术面、基本面、资金面、情绪面评分拆解
- 推荐逻辑与风险提示
- 财务快照

当前财务快照字段：

- 报告期
- 营收同比
- 净利润同比
- 扣非净利润同比
- ROE
- 毛利率
- 资产负债率
- EPS
- 每股经营现金流

页面数据来源：

- `/api/stocks/{symbol}`

### 推荐中心

对应路由：`/recommendations`

展示内容：

- 当前推荐卡片
- 推荐理由、风险、标签、预计持有天数
- 当前最新价
- 近 5 日和近 20 日表现
- 推荐历史记录
- 最近命中率、平均当前收益、最佳记录

说明：

- 当前推荐收益是用“当前最新价”相对于“发布价”计算
- 推荐历史会在每次成功同步后追加写入
- 当前每次成功发布会记录前 8 只推荐股票

页面数据来源：

- `/api/recommendations`
- `/api/recommendations/journal`

### 推荐复盘

对应路由：`/review`

展示内容：

- 5 日、10 日、20 日窗口的命中率和平均收益
- 按推荐批次汇总后的评分和预期收益
- 最佳样本和最差样本
- 推荐明细表

说明：

- 复盘收益基于推荐历史和 `stock_price` 历史价格序列计算
- `5 / 10 / 20 日收益` 使用交易日窗口，不是自然日
- `预期窗口收益` 使用推荐时记录的 `expected_holding_days` 作为近似交易日窗口

页面数据来源：

- `GET /api/recommendations/review`

### 交易计划

对应路由：`/trade-plans`

展示内容：

- 计划总数、计划中数量、持有中平均浮盈、已平仓胜率
- 交易计划列表与状态筛选
- 计划价、入场价、止损价、目标价、计划仓位
- 计划偏差、浮动收益、已实现收益、盈亏比
- 交易逻辑与备注

支持操作：

- 手动新建交易计划
- 从推荐中心、个股详情直接加入交易计划
- 从交易计划一键转成组合持仓
- 把状态切换为计划中、持有中、已平仓、已取消
- 编辑计划价、止损价、目标价、入场价、离场价和备注
- 删除交易计划

页面数据来源：

- `GET /api/trade-plans`
- `POST /api/trade-plans`
- `PUT /api/trade-plans/{id}`
- `DELETE /api/trade-plans/{id}`

### 组合持仓

对应路由：`/portfolio`

展示内容：

- 预计总资产、预计现金、持仓市值、仓位利用率
- 浮动盈亏、已实现盈亏、组合总收益、最大持仓权重
- 组合账户设置
- 持仓状态筛选
- 单只持仓的成本、市值、浮盈、实盈、权重和风控距离

支持操作：

- 设置账户名称、初始资金、基准和备注
- 手动录入持仓
- 从交易计划一键转入组合持仓
- 把持仓切换为持有中、已平仓
- 编辑数量、成本、平仓价、止损价、目标价、逻辑和备注
- 删除持仓记录

页面数据来源：

- `GET /api/portfolio/overview`
- `GET /api/portfolio/profile`
- `PUT /api/portfolio/profile`
- `POST /api/portfolio/positions`
- `PUT /api/portfolio/positions/{id}`
- `DELETE /api/portfolio/positions/{id}`

### 自选池

对应路由：`/watchlist`

展示内容：

- 自选股票总览
- 观察中、持有中、已归档状态筛选
- 加入价、最新价、当前收益
- 当前评分、标签、推荐结论
- 观察备注

支持操作：

- 从股票列表、个股详情、推荐中心加入或移出自选池
- 在自选池页面切换跟踪状态
- 编辑观察备注
- 跳转到个股详情

页面数据来源：

- `GET /api/watchlist`
- `POST /api/watchlist`
- `PUT /api/watchlist/{symbol}`
- `DELETE /api/watchlist/{symbol}`

### 策略配置

对应路由：`/strategy`

支持配置：

- 技术面权重
- 基本面权重
- 资金面权重
- 情绪面权重
- 调仓周期
- 最低换手率
- 最少上市天数
- 排除 ST
- 排除次新股

约束：

- 四个权重之和必须等于 `100`

页面数据来源：

- `GET /api/strategies/default`
- `PUT /api/strategies/default`

### 数据任务

对应路由：`/tasks`

当前能力：

- 查看任务记录
- 手动提交市场同步
- 查看任务状态、计划时间、最近运行、数据源和消息

默认会初始化三条任务记录：

- `market-sync`
- `signal-rescore`
- `recommendation-publish`

说明：

- 提交同步后，真正的采集与计算在后端后台执行
- 默认已经接入 APScheduler，后端启动后会按计划自动执行市场同步
- 页面会每 8 秒轮询一次运行中的任务
- 如果把 `ENABLE_TASK_SCHEDULER` 设为 `false`，系统会退回手动调度模式
- `signal-rescore` 和 `recommendation-publish` 仍然作为任务阶段展示，当前由市场同步流程联动刷新

页面数据来源：

- `GET /api/tasks`
- `POST /api/tasks/sync-market`

## API 一览

### 健康检查

- `GET /api/health`

返回：

- 应用状态
- 应用名称
- 当前模式
- 自动调度是否开启
- 行情库路径
- 业务库存储位置

### 提醒

- `GET /api/alerts/overview`
- `POST /api/alerts/evaluate`
- `PUT /api/alerts/{id}`

### 市场看板

- `GET /api/dashboard/summary`

返回：

- 看板标题
- 更新时间
- 市场概览卡片
- 行业热度
- 市场温度
- 高分推荐
- 风险提示

### 股票

- `GET /api/stocks`
  - 查询参数：`keyword`、`board`、`page`、`page_size`
- `GET /api/stocks/{symbol}`

### 推荐

- `GET /api/recommendations`
- `GET /api/recommendations/journal`
- `GET /api/recommendations/review`

### 交易计划

- `GET /api/trade-plans`
- `POST /api/trade-plans`
- `PUT /api/trade-plans/{id}`
- `DELETE /api/trade-plans/{id}`

### 组合持仓

- `GET /api/portfolio/overview`
- `GET /api/portfolio/profile`
- `PUT /api/portfolio/profile`
- `POST /api/portfolio/positions`
- `PUT /api/portfolio/positions/{id}`
- `DELETE /api/portfolio/positions/{id}`

### 自选池

- `GET /api/watchlist`
- `POST /api/watchlist`
- `PUT /api/watchlist/{symbol}`
- `DELETE /api/watchlist/{symbol}`

### 策略

- `GET /api/strategies/default`
- `PUT /api/strategies/default`

### 任务

- `GET /api/tasks`
- `POST /api/tasks/sync-market`

## 推荐评分逻辑

当前信号引擎不是黑盒模型，而是“规则计算 + 权重加总”的第一版实现。

### 四个维度

- 技术面
  - 近 20 日收益
  - 当前价格相对 MA20
  - MA5 和 MA20 关系
  - 距离 60 日高点位置
- 基本面
  - 动态 PE 粗估
  - 市值体量
  - 营收、利润、扣非利润增速
  - ROE、毛利率、资产负债率、每股经营现金流
- 资金面
  - 换手率
  - 量比
  - 近 5 日成交额相对近 20 日均值
- 情绪面
  - 当日涨跌幅
  - 近 5 日收益
  - 接近阶段高点程度

### 输出结果

系统会基于分数生成：

- 综合评分
- 标签
- 一句话推荐结论
- 推荐理由拆解
- 风险提示
- 关注窗口
- 预计持有天数

### 当前推荐记录逻辑

- 每次市场同步成功后，会把当前推荐结果中的前 8 条写入业务库
- 推荐历史记录包含发布价、当前价、当前收益、推荐理由和风险提示
- 复盘页面会在推荐历史基础上，进一步计算 5 / 10 / 20 日和预期窗口收益
- 交易计划会基于最新快照自动计算计划偏差、浮动收益、已实现收益和盈亏比
- 提醒中心会基于最新快照、交易计划、组合持仓和自选池持续生成待处理事件
- 组合持仓会基于账户初始资金和持仓记录估算总资产、现金、仓位和单票权重
- 自选池收益使用加入时价格和当前最新价做静态回看

## 数据存储说明

### 业务库

默认文件：

- [backend/data/stockpilot.db](/Users/zhoubin/work/ideaWorkSpace/zhou/gupiao/backend/data/stockpilot.db)

当前主要保存：

- `strategy_profiles`
- `sync_tasks`
- `recommendation_journal`
- `trade_plan_items`
- `alert_events`
- `portfolio_profiles`
- `portfolio_positions`
- `watchlist_items`

### 行情分析库

默认文件：

- [backend/data/market.duckdb](/Users/zhoubin/work/ideaWorkSpace/zhou/gupiao/backend/data/market.duckdb)

当前主要保存：

- `stock_snapshot`
- `stock_price`
- `industry_heat`
- `market_pulse`
- `recommendation_item`
- `sync_metadata`

## PostgreSQL 可选支持

如果你后面希望把业务库从 `SQLite` 切到 PostgreSQL，可以先启动本地数据库：

```bash
cd /Users/zhoubin/work/ideaWorkSpace/zhou/gupiao
docker compose up -d
```

然后把 `BUSINESS_DATABASE_URL` 改成 PostgreSQL 连接串即可。

注意：

- 当前 `docker-compose.yml` 只提供 PostgreSQL
- 前端和后端仍然建议你本地分别启动

## 开发与验证

### 后端测试

```bash
cd /Users/zhoubin/work/ideaWorkSpace/zhou/gupiao
source .venv/bin/activate
pytest backend/tests -q
```

当前测试覆盖了这些核心场景：

- 健康检查
- 股票列表
- 个股详情含财务快照
- 推荐接口含近 5 日表现
- 推荐历史接口
- 推荐复盘接口
- 交易计划增删改查
- 提醒中心评估与状态变更
- 组合持仓增删改查
- 自选池增删改查
- 策略读写
- 任务接口

### 前端构建

```bash
cd /Users/zhoubin/work/ideaWorkSpace/zhou/gupiao/frontend
npm run build
```

## 当前限制

这部分很重要，避免把现在的 MVP 当成完整生产系统。

- 当前更适合个人本地研究，不适合直接用于实盘自动交易
- AKShare 属于第三方数据封装，稳定性受外部站点和接口变化影响
- 当前行业热度主要基于现有快照聚合，行业板块映射还不算完整
- 当前财务快照来自同花顺财务摘要接口，不是完整财务因子库
- 当前自动调度依赖应用进程常驻运行，不是独立任务系统
- 当前推荐收益是静态回看，不是完整回测结果
- 当前提醒规则仍然是第一版规则系统，适合做研究提醒，不等于自动交易信号
- 当前没有用户体系、外部通知渠道和交易执行链路
- 当前股票列表仍是第一页固定 50 条的 MVP 交互

## 下一步建议

如果继续往下做，优先级建议如下：

1. 补更多基本面字段、行业板块映射和资金流数据
2. 把提醒中心继续扩展到企业微信、邮件或桌面通知
3. 把复盘从静态窗口收益推进到完整回测
4. 把自动调度从应用内调度升级成更稳的独立任务体系
5. 把业务库切到 PostgreSQL，方便后续做更多配置和日志管理

## 关键文件

如果你后面想继续改这个系统，这几个文件最值得先看：

- 后端入口：[backend/app/main.py](/Users/zhoubin/work/ideaWorkSpace/zhou/gupiao/backend/app/main.py)
- API 路由：[backend/app/api/router.py](/Users/zhoubin/work/ideaWorkSpace/zhou/gupiao/backend/app/api/router.py)
- 行情存储：[backend/app/services/market_store.py](/Users/zhoubin/work/ideaWorkSpace/zhou/gupiao/backend/app/services/market_store.py)
- 数据采集：[backend/app/services/akshare_collector.py](/Users/zhoubin/work/ideaWorkSpace/zhou/gupiao/backend/app/services/akshare_collector.py)
- 评分逻辑：[backend/app/services/signal_engine.py](/Users/zhoubin/work/ideaWorkSpace/zhou/gupiao/backend/app/services/signal_engine.py)
- 推荐历史：[backend/app/services/recommendation_service.py](/Users/zhoubin/work/ideaWorkSpace/zhou/gupiao/backend/app/services/recommendation_service.py)
- 推荐复盘：[backend/app/services/recommendation_review_service.py](/Users/zhoubin/work/ideaWorkSpace/zhou/gupiao/backend/app/services/recommendation_review_service.py)
- 交易计划服务：[backend/app/services/trade_plan_service.py](/Users/zhoubin/work/ideaWorkSpace/zhou/gupiao/backend/app/services/trade_plan_service.py)
- 提醒服务：[backend/app/services/alert_service.py](/Users/zhoubin/work/ideaWorkSpace/zhou/gupiao/backend/app/services/alert_service.py)
- 组合持仓服务：[backend/app/services/portfolio_service.py](/Users/zhoubin/work/ideaWorkSpace/zhou/gupiao/backend/app/services/portfolio_service.py)
- 自选池服务：[backend/app/services/watchlist_service.py](/Users/zhoubin/work/ideaWorkSpace/zhou/gupiao/backend/app/services/watchlist_service.py)
- 调度服务：[backend/app/services/scheduler_service.py](/Users/zhoubin/work/ideaWorkSpace/zhou/gupiao/backend/app/services/scheduler_service.py)
- 提醒中心页面：[frontend/src/views/AlertCenterView.vue](/Users/zhoubin/work/ideaWorkSpace/zhou/gupiao/frontend/src/views/AlertCenterView.vue)
- 推荐中心页面：[frontend/src/views/RecommendationView.vue](/Users/zhoubin/work/ideaWorkSpace/zhou/gupiao/frontend/src/views/RecommendationView.vue)
- 推荐复盘页面：[frontend/src/views/ReviewView.vue](/Users/zhoubin/work/ideaWorkSpace/zhou/gupiao/frontend/src/views/ReviewView.vue)
- 交易计划页面：[frontend/src/views/TradePlanView.vue](/Users/zhoubin/work/ideaWorkSpace/zhou/gupiao/frontend/src/views/TradePlanView.vue)
- 组合持仓页面：[frontend/src/views/PortfolioView.vue](/Users/zhoubin/work/ideaWorkSpace/zhou/gupiao/frontend/src/views/PortfolioView.vue)
- 个股详情页面：[frontend/src/views/StockDetailView.vue](/Users/zhoubin/work/ideaWorkSpace/zhou/gupiao/frontend/src/views/StockDetailView.vue)
- 自选池页面：[frontend/src/views/WatchlistView.vue](/Users/zhoubin/work/ideaWorkSpace/zhou/gupiao/frontend/src/views/WatchlistView.vue)
