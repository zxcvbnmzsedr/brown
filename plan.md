# Brown — 永久组合投资管理工具

> 让躺平投资者在不关注市场的情况下，保持投资组合始终在正轨上。

---

## 技术栈

| 层 | 技术 | 说明 |
|----|------|------|
| 桌面壳 | Electron | 跨平台，负责窗口/通知/生命周期 |
| 前端 | React + TypeScript + Vite | 渲染层 UI |
| 后端 | Python + FastAPI | 本地 HTTP 服务，业务逻辑 |
| 数据库 | SQLite + SQLAlchemy | 本地存储，无需部署 |
| 通信 | localhost HTTP | Electron renderer ↔ Python backend |
| 样式 | Tailwind CSS | |

---

## 项目结构

```
brown/
├── electron/                   # Electron 主进程
│   ├── main.ts                 # 应用入口，启动 Python 子进程，创建窗口
│   ├── preload.ts              # 安全桥接 renderer 与 main
│   └── notifier.ts             # 系统通知（再平衡触发）
│
├── renderer/                   # React 前端
│   ├── pages/
│   │   ├── Dashboard.tsx       # 首页：组合圆环 + 总资产 + 今日涨跌
│   │   ├── Ledger.tsx          # 账单页：所有交易记录，可筛选
│   │   ├── Rebalance.tsx       # 再平衡操作台：偏离详情 + 操作建议
│   │   └── Assets.tsx          # 标的管理：注册/编辑标的
│   ├── components/
│   │   ├── AllocationRing.tsx  # 双圆环组件（目标 vs 实际）
│   │   ├── TransactionForm.tsx # 录入交易表单
│   │   ├── AssetForm.tsx       # 新增/编辑标的表单
│   │   └── PriceTag.tsx        # 单个标的涨跌展示
│   ├── api/
│   │   └── client.ts           # axios 封装，统一调用 Python backend
│   └── store/
│       └── portfolio.ts        # 全局状态（持仓快照、价格缓存）
│
├── backend/                    # Python FastAPI 后端
│   ├── main.py                 # FastAPI 入口，注册路由，启动定时任务
│   ├── db.py                   # SQLite 连接，SQLAlchemy session
│   │
│   ├── models/                 # 数据库模型（ORM）
│   │   ├── asset.py            # 标的表：id, name, type, code, exchange
│   │   ├── transaction.py      # 交易表：id, date, asset_id, type, qty, price, fee, note
│   │   ├── portfolio_config.py # 组合配置表：asset_id, target_weight
│   │   └── price_cache.py      # 价格缓存表：asset_id, date, price
│   │
│   ├── routers/                # API 路由
│   │   ├── assets.py           # GET/POST/PUT/DELETE /assets
│   │   ├── transactions.py     # GET/POST/DELETE /transactions
│   │   ├── portfolio.py        # GET /portfolio/snapshot（持仓快照+偏离度）
│   │   ├── rebalance.py        # GET /rebalance/suggestion（再平衡建议）
│   │   └── prices.py           # POST /prices/refresh（手动触发价格更新）
│   │
│   └── services/
│       ├── price_fetcher.py    # 行情拉取（东方财富/Yahoo Finance）
│       ├── rebalancer.py       # 再平衡计算引擎
│       └── scheduler.py        # 定时任务：每日收盘后自动刷新价格
│
└── package.json                # monorepo 入口，管理 electron + renderer 脚本
```

---

## 数据模型

### asset（标的注册表）
```sql
id           INTEGER PRIMARY KEY
name         TEXT NOT NULL          -- 显示名称，如"工银黄金"
type         TEXT NOT NULL          -- stock | fund | money_market | cash | crypto
code         TEXT                   -- 基金/股票代码，type=cash 时为空
exchange     TEXT                   -- SH | SZ | NASDAQ | NYSE | HK，type=cash 时为空
created_at   DATETIME
```

### transaction（交易账单）
```sql
id           INTEGER PRIMARY KEY
date         DATE NOT NULL
asset_id     INTEGER FK → asset.id
type         TEXT NOT NULL          -- buy | sell
qty          DECIMAL NOT NULL       -- 数量（份/股）
price        DECIMAL NOT NULL       -- 成交单价
fee          DECIMAL DEFAULT 0      -- 手续费
note         TEXT                   -- 备注：建仓/定投/再平衡
created_at   DATETIME
```

### portfolio_config（目标配比）
```sql
id           INTEGER PRIMARY KEY
asset_id     INTEGER FK → asset.id
target_weight DECIMAL NOT NULL      -- 目标占比，如 0.25
```

### price_cache（价格缓存）
```sql
id           INTEGER PRIMARY KEY
asset_id     INTEGER FK → asset.id
date         DATE NOT NULL
price        DECIMAL NOT NULL
fetched_at   DATETIME
```

---

## 核心业务逻辑

### 持仓快照计算（`/portfolio/snapshot`）
```
对每个标的：
  持仓数量 = SUM(buy.qty) - SUM(sell.qty)
  持仓成本 = SUM(buy.qty × buy.price + buy.fee) - SUM(sell.qty × sell.price - sell.fee)
  当前价值 = 持仓数量 × 最新价格（来自 price_cache）
  成本均价 = 持仓成本 / 持仓数量

汇总：
  总资产   = SUM(各标的当前价值)
  实际占比 = 各标的当前价值 / 总资产
  偏离度   = 实际占比 - 目标占比
```

### 再平衡建议计算（`/rebalance/suggestion`）
```
触发条件：任意标的 |偏离度| >= 0.15

目标价值   = 总资产 × 目标占比
当前价值   = 持仓数量 × 当前价格
差额       = 目标价值 - 当前价值

差额 > 0 → 买入该标的（差额 / 当前价格 = 建议买入份数）
差额 < 0 → 卖出该标的（|差额| / 当前价格 = 建议卖出份数）
```

### 行情拉取路由（`price_fetcher.py`）
```
exchange = SH / SZ  → 东方财富基金净值 API
exchange = NASDAQ   → Yahoo Finance API（yfinance）
exchange = HK       → 待扩展
type = cash         → 跳过，价格固定 1.0
```

---

## API 接口清单

| Method | Path | 说明 |
|--------|------|------|
| GET | `/assets` | 获取所有已注册标的 |
| POST | `/assets` | 新增标的 |
| PUT | `/assets/:id` | 编辑标的 |
| DELETE | `/assets/:id` | 删除标的 |
| GET | `/transactions` | 获取账单列表（支持筛选 type/asset/date range）|
| POST | `/transactions` | 录入一笔交易 |
| DELETE | `/transactions/:id` | 删除一笔交易 |
| GET | `/portfolio/snapshot` | 当前持仓快照（含偏离度） |
| GET | `/rebalance/suggestion` | 再平衡操作建议 |
| POST | `/prices/refresh` | 手动触发所有标的价格更新 |

---

## 开发阶段

### Phase 1 — 核心骨架
- [ ] Electron + React + Python 工程跑通
- [ ] SQLite 初始化，模型建表
- [ ] 标的管理页（CRUD）
- [ ] 账单录入页（买入/卖出）

### Phase 2 — 持仓可视化
- [ ] 持仓快照 API（`/portfolio/snapshot`）
- [ ] 双圆环组件（目标 vs 实际）
- [ ] Dashboard 首页（总资产 + 各标的当前值）

### Phase 3 — 行情接入
- [ ] 东方财富 API 接入（国内基金净值）
- [ ] Yahoo Finance 接入（美股）
- [ ] 定时任务：每日收盘后自动刷新（16:30）
- [ ] 价格缓存机制

### Phase 4 — 再平衡引擎
- [ ] 偏离度计算
- [ ] 再平衡建议 API
- [ ] 再平衡操作台页面
- [ ] 触发时系统通知推送

### Phase 5 — 增强（可选）
- [ ] 收益曲线（对比永久组合基准）
- [ ] 历史再平衡记录回溯
- [ ] wechat-cli 接入：自动提取群里大佬实盘数据
