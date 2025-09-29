# Warp2API with Account Pool Service

一个完整的Warp AI API代理服务，包含独立的账号池管理系统和可视化账号管理器。

## 🌟 特性

- **账号池服务**: 独立的微服务架构，自动管理Warp账号
- **可视化账号管理器**: Web界面管理账号，支持批量导入和SQLite/CSV导出
- **Protobuf编解码**: 提供JSON与Protobuf之间的转换
- **OpenAI兼容API**: 完全兼容OpenAI Chat Completions API格式
- **自动账号管理**: 自动注册、刷新和维护账号池
- **并发安全**: 支持多进程并发调用，线程安全
- **智能降级**: 账号池不可用时自动降级到临时账号
- **RESTful API**: 标准的HTTP接口，易于集成
- **⚡ 429错误自动处理**: 遇到速率限制时自动切换账号，无需等待（v1.1.0新增）
- **🔗 IP会话绑定**: 同一IP地址自动复用相同账号，提高稳定性（v1.2.0新增）

## 📁 项目结构

```
warp2api-howlife/
├── account-pool-service/          # 账号池服务
│   ├── main.py                   # 服务入口
│   ├── config.py                 # 配置文件
│   └── account_pool/             # 核心模块
├── warp2api-main/                # Warp2API主服务
│   ├── server.py                 # Protobuf桥接服务器
│   ├── main.py                   # OpenAI兼容API服务器
│   └── warp2protobuf/            # Protobuf处理
├── account.html                  # 可视化账号管理器
├── proxy_server.py               # 账号管理器代理服务器
├── start_account_manager.sh      # 账号管理器启动脚本
├── tests/                        # 测试文件
├── logs/                         # 日志目录
├── start_services.sh             # 一键启动脚本
└── stop_services.sh              # 停止脚本
```

## 🚀 快速开始

### 1. 安装依赖

确保已安装 Python 3.8+

```bash
# 安装主服务依赖
pip install -r warp2api-main/requirements.txt
pip install -r account-pool-service/requirements.txt

# 安装账号管理器依赖
pip install flask flask-cors requests
```

### 2. 启动服务

#### 启动主服务（推荐）
```bash
# 一键启动所有核心服务
./start_services.sh
```

#### 启动账号管理器（可选）
```bash
# 启动可视化账号管理器
python3 proxy_server.py
# 或使用启动脚本
./start_account_manager.sh
```

服务将在以下端口运行：
- **Protobuf桥接服务**: http://localhost:8000
- **OpenAI兼容API**: http://localhost:8010
- **账号池服务**: http://localhost:8019
- **账号管理器**: http://localhost:8021

### 3. 停止服务

```bash
./stop_services.sh
```

## 📝 API 使用

### 可视化账号管理器

访问 http://localhost:8021/account.html 使用Web界面：

1. **批量账号管理**: 支持多个账号同时处理
2. **自动Token获取**: 输入refresh_token自动获取id_token
3. **数据导出**: 生成SQLite插入命令和CSV格式数据
4. **一键复制**: 支持复制生成的命令和数据

### OpenAI兼容API

```bash
# 使用OpenAI SDK格式调用
curl -X POST http://localhost:8010/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-api-key" \
  -d '{
    "model": "claude-4-sonnet",
    "messages": [
      {"role": "user", "content": "Hello, how are you?"}
    ],
    "stream": false
  }'
```

### 账号池服务 API

#### 查看账号池状态
```bash
curl http://localhost:8019/api/accounts/status | jq
```

#### 分配账号
```bash
curl -X POST http://localhost:8019/api/accounts/allocate \
  -H "Content-Type: application/json" \
  -d '{"count": 1}'
```

### Protobuf桥接服务

#### Protobuf 编码
```bash
curl -X POST http://localhost:8000/api/encode \
  -H "Content-Type: application/json" \
  -d '{
    "message_type": "warp.multi_agent.v1.AgentRequest",
    "json_data": {
      "version": 7,
      "thread_id": "test_thread",
      "user_message": {
        "content": "Hello!",
        "user_message_type": "USER_MESSAGE_TYPE_CHAT"
      }
    }
  }'
```

## 🧪 测试

### 运行集成测试
```bash
python3 tests/test_integration.py
```

### 运行账号池测试
```bash
python3 tests/test_pool_service.py
```

### 测试OpenAI兼容性
```bash
# 使用OpenAI Python SDK测试
python3 -c "
import openai
client = openai.OpenAI(
    api_key='test-key',
    base_url='http://localhost:8010/v1'
)
response = client.chat.completions.create(
    model='claude-4-sonnet',
    messages=[{'role': 'user', 'content': 'Hello!'}]
)
print(response.choices[0].message.content)
"
```

## 📊 监控

### 查看日志
```bash
# 账号池服务日志
tail -f logs/pool-service.log

# Protobuf桥接服务日志
tail -f logs/warp2api.log

# OpenAI兼容API日志
tail -f logs/openai-api.log

# 账号管理器日志
tail -f logs/account-manager.log

# 查看所有日志
tail -f logs/*.log
```

### 服务状态检查
```bash
# 账号池健康检查
curl http://localhost:8019/health

# Protobuf桥接服务健康检查
curl http://localhost:8000/healthz

# OpenAI兼容API健康检查
curl http://localhost:8010/healthz

# 账号管理器健康检查
curl http://localhost:8021/
```

## ⚙️ 配置

### 环境变量

```bash
# 服务端口配置
export WARP_BRIDGE_PORT="8000"      # Protobuf桥接服务端口
export OPENAI_API_PORT="8010"       # OpenAI兼容API端口
export POOL_SERVICE_PORT="8019"     # 账号池服务端口
export ACCOUNT_MANAGER_PORT="8021"  # 账号管理器端口

# 账号池服务配置
export POOL_SERVICE_URL="http://localhost:8019"
export USE_POOL_SERVICE="true"
export MIN_POOL_SIZE="5"    # 最少账号数
export MAX_POOL_SIZE="50"   # 最大账号数

# 429错误处理配置（新增）
export MAX_429_RETRY_LIMIT="3"      # 最大重试次数
export ENABLE_429_AUTO_SWITCH="true" # 启用自动切换
export ENABLE_IP_BINDING="true"     # 启用IP会话绑定
export SESSION_TIMEOUT="1800"       # 会话超时时间（秒）

# Warp认证配置
export WARP_JWT="your-jwt-token"
export WARP_REFRESH_TOKEN="your-refresh-token"

# 日志级别
export LOG_LEVEL="INFO"
```

### 配置文件

- 账号池服务配置: `account-pool-service/config.py`
- Warp2API配置: `warp2api-main/warp2protobuf/config/`
- 账号管理器配置: `proxy_server.py`

## 🔧 故障排查

### 服务无法启动
1. 检查端口是否被占用:
   ```bash
   lsof -i:8000  # Protobuf桥接服务
   lsof -i:8010  # OpenAI兼容API
   lsof -i:8019  # 账号池服务
   lsof -i:8021  # 账号管理器web
   ```
2. 查看日志文件了解详细错误
3. 确保Python依赖已正确安装

### 账号池为空
- 首次启动时需要1-2分钟注册账号
- 检查日志确认注册是否成功
- 可手动补充账号：
  ```bash
  curl -X POST http://localhost:8019/api/accounts/replenish \
    -d '{"count": 10}'
  ```

### 429错误处理（新增 v1.1.0）
- 系统会自动删除触发429的账号并切换新账号
- 查看429统计信息：
  ```bash
  curl http://localhost:8019/api/accounts/status | jq '.["429_stats"]'
  ```
- 如果删除率过高，系统会自动告警
- 可通过 `MAX_429_RETRY_LIMIT` 调整重试次数

### IP会话绑定（新增 v1.2.0）
- 同一IP地址的请求会自动绑定到相同账号
- 减少账号切换，提高会话稳定性
- 会话超时后自动释放账号供其他IP使用
- 查看当前会话绑定状态：
  ```bash
  curl http://localhost:8019/api/accounts/status | jq '.sessions'
  ```
- 可通过 `ENABLE_IP_BINDING=false` 禁用此功能
### SQLlite命令样式

* 添加账号的命令:
```
sqlite3 account-pool-service/accounts.db "  
INSERT INTO accounts (email, local_id, id_token, refresh_token, status, created_at)   
VALUES   
  ('account1@example.com', 'firebase_uid_1', 'id_token_1', 'refresh_token_1', 'available', datetime('now')),  
  ('account2@example.com', 'firebase_uid_2', 'id_token_2', 'refresh_token_2', 'available', datetime('now')),  
  ('account3@example.com', 'firebase_uid_3', 'id_token_3', 'refresh_token_3', 'available', datetime('now'));  
"
```

* 验证账号是否添加成功
```sqlite3 account-pool-service/accounts.db "SELECT email, status, created_at FROM accounts WHERE email='dd016ea3@frontmi.net';"
```
### Token过期
- 账号池会自动刷新即将过期的Token
- 遵守1小时刷新限制，防止账号被封

### 账号管理器CORS错误
- 确保通过代理服务器访问: `http://localhost:8021/account.html`
- 不要直接打开HTML文件，会遇到跨域问题

## 🏗️ 架构说明

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   OpenAI SDK    │───▶│  OpenAI兼容API  │───▶│  Protobuf桥接   │
│   (客户端)      │    │   (端口8010)    │    │   (端口8000)    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                                       │
                       ┌─────────────────┐            ▼
                       │   账号管理器     │    ┌─────────────────┐
                       │  (端口8021)     │    │    Warp AI      │
                       └─────────────────┘    │      服务       │
                                              └─────────────────┘
                                                       ▲
                       ┌─────────────────┐            │
                       │   账号池服务     │────────────┘
                       │  (端口8019)     │
                       └─────────────────┘
```



## 📚 相关文档

- [账号管理器部署指南](ACCOUNT_MANAGER_DEPLOYMENT.md)
- [API接口文档](docapi.md)
- [项目架构说明](PROJECT_STRUCTURE.md)

## 📄 License

MIT

## 🤝 贡献

欢迎提交Issue和Pull Request！
