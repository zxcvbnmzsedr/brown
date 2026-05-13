# Brown 项目 Agent 指令

这份文件是后续 agent 进入本仓库时必须遵守的项目约定。
在修改产品边界、数据模型、目录结构、接口或 UI 之前，先按这里的规则判断。

## 产品方向

Brown 是一个 Web/PWA 形态的个人投资资产统计工具，核心使用场景是永久组合类资产管理。
当前项目处于硬切开发阶段，暂时没有生产用户。
除非用户明确要求迁移旧数据，否则不要为了兼容旧桌面端、Electron 或旧本地数据结构增加兼容层。

当前产品分为两个前端：

- `app/`：用户端资产工作台。
- `admin/`：运营后台基础数据维护。

后端是一个 FastAPI 服务，位于 `server/`。
同一个后端服务内区分两套认证域：用户认证和管理员认证。

## 已确认的产品边界

运营后台只给运营使用：

- 后台只需要登录拦截。
- 后台不需要注册功能。
- 管理员账号来自环境变量：
  - `ADMIN_EMAIL`
  - `ADMIN_PASSWORD`
  - `ADMIN_JWT_SECRET`
- 后台只维护全局基础数据：
  - `instruments`：标的库
  - `instrument_prices`：标的价格
  - `trading_platforms`：交易平台

用户端用于资产统计和日常投资记录：

- 用户端需要注册和登录。
- 用户维护自己的组合、投资账户、现金账户、配置标的、买入/卖出流水。
- 用户数据必须按 `user_id` 隔离。

现金不是标的：

- 不要在 `instruments` 里创建现金记录。
- 不要把现金建模成可交易标的。
- 现金放在 `cash_accounts` 中，作为现金账户余额快照。
- 买入/卖出流水可以选择现金账户。
- 如果流水选择了现金账户，新增、修改、删除流水时必须自动应用或回滚现金余额影响。
- 如果流水没有选择现金账户，只记录投资交易，不调整现金余额。

持仓来自真实交易流水：

- 不要重新引入 `positions` 表。
- 不要重新引入 `opening_positions`。
- 不要重新引入 `initial` 交易类型。
- 当前持仓必须由真实 `buy` / `sell` 交易流水聚合得出。

## 目录约定

当前目录结构是有意设计的：

- `server/`：FastAPI 应用、SQLAlchemy 模型、路由、服务、测试、CLI。
- `app/`：用户端 Web/PWA，使用 React/Vite。
- `admin/`：运营后台，使用 React/Vite 和 Ant Design。
- `alembic/`：硬切后的数据库迁移。

以下旧目录已经被有意移除：

- `backend/`
- `renderer/`
- `electron/`

不要再往这些旧目录里添加代码。
除非用户明确反向确认，否则不要恢复 Electron。

## 数据模型规则

全局基础库由后台维护：

- `instruments`
- `instrument_prices`
- `trading_platforms`

用户侧数据包括：

- `users`
- `portfolios`
- `portfolio_buckets`
- `portfolio_groups`
- `investment_accounts`
- `cash_accounts`
- `user_assets`
- `transactions`
- `snapshot_history`

新增或修改接口时必须遵守：

- 校验组合归属，确保 `portfolio` 属于当前 `user_id`。
- 校验投资账户、现金账户、组合分组属于同一个用户和同一个组合。
- 用户配置标的或记录交易前，必须确认标的是启用状态。
- 管理员 JWT 和用户 JWT 必须分开。后台接口必须拒绝用户 token。

## 交互与 UI 方向

用户端应该是紧凑的资产工作台，不是营销页。
优先服务真实录入和资产查看流程：

- 创建现金账户并查看余额。
- 创建投资账户。
- 配置可交易标的。
- 记录买入/卖出流水。
- 查看资产桶、组合汇总和现金仓位。

运营后台应该直接、克制、偏工具化：

- 未登录时只展示登录页。
- 登录后展示基础库维护入口。
- 除非用户明确要求，否则不要加入用户注册或用户管理。

交互参考方向已经确认可以借鉴“慢慢变富”：

- 快速真实录入。
- 账户、资产、交易流水清晰分离。
- 现金以账户余额处理，不作为标的处理。

## 本地运行

安装依赖：

```bash
pnpm install
pnpm --prefix app install
pnpm --prefix admin install
python3 -m venv .venv
.venv/bin/pip install -r server/requirements.txt
```

复制环境变量：

```bash
cp .env.example .env
```

启动服务：

```bash
just server
just app
just admin
```

默认访问地址：

- 用户端：`http://127.0.0.1:5174`
- 运营后台：`http://127.0.0.1:5175`
- 后端 API：`http://127.0.0.1:8765`
- API 文档：`http://127.0.0.1:8765/docs`

## 验证命令

代码变更后优先使用这些检查：

```bash
pnpm test:server
pnpm lint
pnpm build
pnpm lint:admin
pnpm build:admin
```

`pnpm build:admin` 可能出现 Vite chunk 体积提醒，主要来自 Ant Design。
除非用户要求优化包体积，否则这个提醒不是阻塞问题。

浏览器验证至少覆盖：

- 后台登录页没有注册入口。
- 后台可以创建和查看标的、价格、交易平台。
- 用户可以注册和登录。
- 用户端能看到后台创建的标的和交易平台。
- 用户可以创建现金账户，并且现金计入现金仓位。
- 用户可以创建投资账户。
- 用户可以配置标的。
- 买入/卖出选择现金账户后，现金余额和交易流水会同步更新。

## 开发护栏

- 当前是硬切 schema，优先重建迁移，不要默认兼容旧表。
- 不要为了旧 Electron 或本地桌面行为加兼容代码，除非用户明确要求。
- 不要把现金当成标的处理。
- 不要用伪造历史交易表达初始持仓。
- 不要给运营后台做注册。
- 不要把运营基础库维护和用户资产统计混在一起。
- 后台接口必须走管理员认证。
- 用户资产接口必须走用户认证。
- 优先沿用现有 `server/`、`app/`、`admin/` 的实现模式，不要随意引入新框架或大抽象。

