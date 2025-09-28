# Warp2API / Account Pool - AGENTS 概览

面向 AI/Agent 二次开发者的可执行认知模型：定义系统中的“业务代理(Agents)”、它们的职责、接口契约、状态与协作流。阅读本文件即可快速让新 Agent 接入或替换任一环节。

## 1) 系统角色图（Agents）

- 账号池服务 Agent (`AccountPoolService`):
  - FastAPI 服务，端口默认 8019
  - 能力：账号分配/释放、状态查询、手动补充、令牌刷新
  - 数据源：`accounts.db` (SQLite)

- 号池管理器 Agent (`PoolManager` in `account-pool-service`):
  - 内部守护任务，维持最小池、清理会话、紧急补号、严格 Token 刷新
  - 对外通过 REST 由 `AccountPoolService` 暴露

- Token 刷新 Agent (`TokenRefreshService`):
  - 基于 Firebase Secure Token API，通过 `refresh_token` 刷新 `id_token`
  - 严格遵守 1 小时刷新限制（数据库字段 `last_refresh_time` 管控）

- 批量注册 Agent (`BatchRegister`):
  - 并发创建 Warp 账号（依赖临时邮箱、Firebase 登录、Warp GraphQL 激活）
  - 提供补号能力供 `PoolManager` 调用

- Protobuf 桥接 Agent (`WarpBridgeServer`):
  - FastAPI 服务，端口默认 8000
  - 能力：JSON⇆Protobuf 编解码、SSE/WS 调试、直连 Warp API
  - 与账号池联动：在额度不足/过期时，通过 `pool_auth` 申请账号或匿名 token

- OpenAI 兼容 Agent (`OpenAICompatServer`):
  - FastAPI 服务，端口默认 8010
  - 能力：提供 `/v1/chat/completions` 等 OpenAI 兼容接口，底层调用桥接 Agent

- 账号管理器 Agent (`AccountManagerUI + Proxy`):
  - UI: `account.html`（本地浏览器页面）
  - Proxy: `proxy_server.py`（Flask，端口默认 8021）解决 CORS，并提供导入到 SQLite 的简易 API

## 2) 端口与进程

- 8000: Protobuf 桥接 (`warp2api-main/server.py` → mounts `warp2protobuf/api/protobuf_routes.py`)
- 8010: OpenAI 兼容 (`warp2api-main/openai_compat.py` → `protobuf2openai.app`)
- 8019: 账号池服务 (`account-pool-service/main.py`)
- 8021: 账号管理器 UI 代理 (`proxy_server.py` → `account.html`)

## 3) 核心数据契约（简化）

- Account (SQLite 表 `accounts`，由 `account-pool-service/account_pool/database.py` 管理):
  - `email`: string, 唯一
  - `local_id`: string, Firebase UID / Warp UID
  - `id_token`: string, JWT
  - `refresh_token`: string
  - `status`: enum['available','in_use','expired','error']
  - `created_at`, `last_used`, `last_refresh_time`: timestamp
  - `use_count`: int
  - `session_id`: string|null

- AllocateAccountResponse (`/api/accounts/allocate`):
  - `success`: bool
  - `session_id`: string
  - `accounts`: AccountInfo[]（与表结构等价的只读视图）

## 4) 关键 REST 接口（用于编排）

- Account Pool Service (默认 http://localhost:8019)
  - GET `/health`
  - POST `/api/accounts/allocate` → body: `{ session_id?: string, count?: number(1-10) }`
  - POST `/api/accounts/release` → body: `{ session_id: string }`
  - GET `/api/accounts/status`
  - POST `/api/accounts/refresh-tokens` → `{ email?: string, force?: boolean }`
  - POST `/api/accounts/replenish` → `{ count?: number }`

- Protobuf Bridge (默认 http://localhost:8000)
  - POST `/api/encode` JSON→Protobuf (base64)
  - POST `/api/decode` Protobuf(base64)→JSON
  - POST `/api/warp/send` 直连 Warp，返回文本/任务信息
  - POST `/api/warp/send_stream` 同上（含事件解析）
  - POST `/api/warp/send_stream_sse` 直连 Warp，SSE 流
  - GET `/api/auth/status` | POST `/api/auth/refresh` | GET `/v1/models`

- OpenAI 兼容 (默认 http://localhost:8010)
  - POST `/v1/chat/completions`（OpenAI 格式）

- Account Manager Proxy/UI (默认 http://localhost:8021)
  - GET `/account.html`
  - POST `/proxy/warp-token` 代理 Warp Secure Token API（从 refresh_token 获取 id_token/access_token）
  - POST `/api/import-account` 将账号插入指定 SQLite 数据库
  - POST `/api/test-database` 校验 SQLite 文件与表结构

## 5) Agent 协作与控制流

- OpenAI 客户端 → `OpenAICompatServer` → `WarpBridgeServer`：
  - 当需要 JWT 时，`warp2protobuf/core/pool_auth.py` 会：
    1) 优先请求 `AccountPoolService` 分配账号（`/allocate`）
    2) 使用账号 `refresh_token` 调用 Warp token 接口换取 `access_token`/`id_token`
    3) 若账号池不可用或额度不足，则回退到匿名访问 token 流程
  - Warp 请求走 Protobuf 序列化与 SSE 事件解析（必要时）

- 内部维护任务 (`PoolManager`):
  - 定时维护：清理过期会话、根据 `MIN_POOL_SIZE` 自动补号、清理 `expired`
  - 在分配时，若池子不足：尝试紧急补号；对将过期 `id_token` 执行安全刷新（>=1h 间隔）

- 账号管理器 UI：
  - 手动录入或批量导入 `email, uid, refresh_token`
  - 通过代理换取 `id_token`，生成 SQLite/CSV 插入语句，或直接导入 SQLite

## 6) 配置要点（环境变量）

- Account Pool Service
  - `POOL_SERVICE_HOST` `POOL_SERVICE_PORT` `MIN_POOL_SIZE` `MAX_POOL_SIZE` `ACCOUNTS_PER_REQUEST`
  - `DATABASE_PATH`（可选，默认 `account-pool-service/accounts.db`）

- Warp Bridge / OpenAI 兼容
  - `HOST` `PORT`（OpenAI 兼容）
  - `BRIDGE_BASE_URL`（OpenAI→Bridge URL）
  - `POOL_SERVICE_URL` `USE_POOL_SERVICE=true|false`
  - `CLIENT_VERSION` `OS_CATEGORY` `OS_NAME` `OS_VERSION`（Warp 请求头）
  - `WARP_INSECURE_TLS`（true 跳过 TLS 校验，仅测试）

## 7) 最小二次开发指引

- 新增一个“选择账号策略”Agent：
  - 接口：封装到 `warp2protobuf/core/pool_auth.py` 内，对外仍暴露 `acquire_pool_or_anonymous_token()`
  - 可注入策略：按 email 白名单、按使用次数(`use_count`)最少优先等

- 替换 Token 刷新策略：
  - 在 `account-pool-service/account_pool/token_refresh_service.py` 扩展 `refresh_account_if_needed` 缓冲区策略，或更换为内网网关

- 自定义账号来源：
  - 在 `BatchRegister` 增加导入器（CSV/外部服务），`PoolManager._replenish_accounts()` 统一接入

## 8) 重要不变量（防踩坑）

- Token 刷新最短间隔必须 ≥ 1 小时；否则有封号风险
- `allocate` → 使用后必须 `release`；泄露会话将导致池可用数下降
- SQLite 表结构中的 `email` 唯一约束；重复导入需先查重
- 生产建议通过 Nginx 暴露 8000/8010，并限制 8019 对外暴露（或仅内网）

## 9) 示例：典型调用序列

1. 客户端调用 `/v1/chat/completions`
2. OpenAI 兼容层构造 Protobuf 请求 → 发给 Bridge `/api/warp/send_stream_sse`
3. Bridge 需要 JWT → `pool_auth.acquire_pool_or_anonymous_token()`
   - 若 `USE_POOL_SERVICE=true`：
     - 调用 8019 `/api/accounts/allocate` 获得账号
     - 以账号 `refresh_token` 向 Warp 换取 `access_token/id_token`
4. SSE 返回事件 → 组装为 OpenAI 流式响应
5. 会话结束时（进程关闭/显式释放）→ `release_pool_session()` 调用 `/api/accounts/release`

—— 以上约定面向 Agent 友好：每个环节均可被替换为你自己的 Agent，只需保持输入/输出契约。

