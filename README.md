# Brown

Brown 是一个 Web/PWA 形态的永久组合资产统计工具，分为用户端和运营后台。

## 架构

- `server/`：FastAPI 服务端。
- `app/`：用户端 Web/PWA，用于注册登录、现金账户、投资账户、交易流水和资产统计。
- `admin/`：运营后台，用 `.env` 管理员账号登录，只维护全局基础数据。

Electron 已移除。

## 数据边界

- 运营后台维护全局 `instruments`、`instrument_prices`、`trading_platforms`。
- 用户端维护 `portfolios`、`investment_accounts`、`cash_accounts`、`user_assets`、`transactions`。
- 现金不是标的，不进入 `instruments`。
- 持仓不单独落 `positions` 表，由真实 `buy/sell` 交易流水聚合。
- 买入/卖出选择现金账户时，会自动修正现金余额；未选择现金账户时只记录投资交易。

## 本地开发

首次安装：

```bash
pnpm install
pnpm --prefix app install
pnpm --prefix admin install
python3 -m venv .venv
.venv/bin/pip install -r server/requirements.txt
```

配置：

```bash
cp .env.example .env
```

启动：

```bash
just server
just app
just admin
```

访问：

- 用户端：http://127.0.0.1:5174
- 运营后台：http://127.0.0.1:5175
- 服务端：http://127.0.0.1:8765
- API 文档：http://127.0.0.1:8765/docs

## 数据库

当前是开发期硬切 schema，不兼容旧数据库。需要重建本地库后执行：

```bash
just migrate
```

## 验证

```bash
just test-server
just lint
just build
```
