# Warp2API 项目 AI Agent 文档

## 📋 项目概述

Warp2API 是一个完整的 Warp AI API 代理服务系统，提供了从账号管理到 API 转换的全套解决方案。项目采用微服务架构，包含账号池管理、Protobuf 编解码、OpenAI 兼容接口等多个独立服务。

## 🏗️ 系统架构

### 核心服务组件

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

### 服务端口分配

- **8000**: Protobuf 桥接服务（Warp2API 主服务）
- **8010**: OpenAI 兼容 API 服务
- **8019**: 账号池管理服务
- **8021**: 可视化账号管理器

## 🤖 Agent 能力清单

### 1. 账号管理 Agent

**职责**: 自动化管理 Warp 账号的生命周期

**核心能力**:
- 🔄 **自动注册**: 使用 MoeMail 临时邮箱服务批量注册新账号
- 🔐 **Token管理**: 自动刷新即将过期的 JWT token（遵守1小时限制）
- 📊 **池化管理**: 维护账号池，确保最小可用账号数量
- 🎯 **会话分配**: 为每个请求智能分配和释放账号资源
- 🧹 **自动清理**: 定期清理过期会话和失效账号

**技术实现**:
- 位置: `account-pool-service/`
- 核心模块:
  - `pool_manager.py`: 账号池管理器
  - `batch_register.py`: 批量注册器
  - `token_refresh_service.py`: Token 刷新服务
  - `database.py`: SQLite 数据库操作

### 2. Protobuf 编解码 Agent

**职责**: 处理 Warp API 的 Protobuf 协议转换

**核心能力**:
- 📦 **协议转换**: JSON ↔ Protobuf 双向编解码
- 🔍 **Schema验证**: 自动验证和修正输入数据结构
- 🌊 **流式处理**: 支持流式响应的实时解析
- 🛡️ **错误处理**: 智能处理编解码错误和异常
- 📝 **日志监控**: WebSocket 实时监控数据包

**技术实现**:
- 位置: `warp2api-main/warp2protobuf/`
- 核心功能:
  - Protobuf 运行时管理
  - 消息类型自动识别
  - server_message_data 编解码
  - MCP input_schema 清理

### 3. OpenAI 兼容 Agent

**职责**: 提供 OpenAI Chat Completions API 兼容接口

**核心能力**:
- 🔄 **API转换**: 将 OpenAI 格式请求转换为 Warp 格式
- 📡 **流式响应**: 支持 SSE (Server-Sent Events) 流式输出
- 🎭 **模型映射**: 自动映射模型名称（如 claude-3-sonnet）
- 💬 **消息处理**: 智能处理 system/user/assistant 角色消息
- ⚡ **并发优化**: 连接池和响应缓存优化

**技术实现**:
- 位置: `warp2api-main/protobuf2openai/`
- 启动文件: `openai_compat.py`
- 核心模块:
  - `app.py`: FastAPI 应用
  - `router.py`: API 路由
  - `sse_transform.py`: 流式转换

### 4. 账号可视化管理 Agent

**职责**: 提供 Web 界面管理账号

**核心能力**:
- 📝 **批量导入**: 支持 JSON 格式批量导入账号
- 🔄 **Token获取**: 自动通过 refresh_token 获取 id_token
- 📊 **数据导出**: 生成 SQLite 命令和 CSV 格式数据
- 🌐 **CORS处理**: 代理服务器解决跨域问题
- 💾 **数据持久化**: 支持账号数据的保存和恢复

**技术实现**:
- 前端: `account.html`（单页应用）
- 后端: `proxy_server.py`（Flask 代理服务器）
- 部署脚本: `deploy_account_manager.sh`

## 🛠️ Agent 协作流程

### 1. 初始化流程
```
1. 启动账号池服务 → 检查账号数量
2. 如果不足 → 批量注册 Agent 自动注册新账号
3. 启动 Protobuf 服务 → 初始化编解码环境
4. 启动 OpenAI 服务 → 连接账号池和 Protobuf 服务
```

### 2. 请求处理流程
```
1. 客户端发送 OpenAI 格式请求 → OpenAI Agent
2. OpenAI Agent → 从账号池获取可用账号
3. 转换请求格式 → Protobuf Agent 编码
4. 发送到 Warp API → 接收响应
5. Protobuf Agent 解码 → OpenAI Agent 格式化
6. 返回给客户端 → 释放账号资源
```

### 3. 维护流程
```
1. Token 刷新 Agent 定期检查 token 过期时间
2. 账号池 Agent 自动补充不足的账号
3. 清理 Agent 移除过期会话和失效账号
4. 监控 Agent 记录所有操作日志
```

## 📊 Agent 监控指标

### 账号池健康度
- **available**: 可用账号数
- **in_use**: 使用中账号数
- **total**: 总账号数
- **health**: 健康状态 (healthy/low/critical)

### 性能指标
- **请求响应时间**: API 调用延迟
- **并发处理数**: 同时处理的请求数
- **Token刷新频率**: 每小时刷新次数
- **错误率**: 请求失败比例

### 资源使用
- **内存占用**: 各服务内存使用情况
- **CPU使用率**: 处理器负载
- **数据库大小**: SQLite 存储占用
- **网络流量**: API 调用流量统计

## 🔧 Agent 配置管理

### 环境变量配置
```bash
# 账号池配置
MIN_POOL_SIZE=5          # 最小账号数
MAX_POOL_SIZE=50         # 最大账号数
ACCOUNTS_PER_REQUEST=1   # 每请求分配账号数

# 服务端口
POOL_SERVICE_PORT=8019   # 账号池服务
WARP_BRIDGE_PORT=8000    # Protobuf服务
OPENAI_API_PORT=8010     # OpenAI服务
ACCOUNT_MANAGER_PORT=8021 # 账号管理器

# 性能优化
CONNECTION_POOL_SIZE=10  # 连接池大小
STREAM_CHUNK_DELAY=0.005 # 流响应延迟
HTTP_KEEPALIVE=30        # Keep-Alive超时
```

### 安全配置
- JWT 认证管理
- Firebase API 密钥轮换
- 请求频率限制
- IP 白名单（可选）

## 🚀 Agent 部署策略

### 单机部署
```bash
./start_production.sh  # 一键启动所有服务
```

### 容器化部署
- 每个 Agent 独立容器
- 使用 Docker Compose 编排
- 支持 Kubernetes 扩展

### 高可用部署
- 账号池服务主备切换
- 负载均衡器分发请求
- 数据库定期备份

## 📈 Agent 扩展能力

### 可扩展点

1. **新模型支持**
   - 添加模型配置文件
   - 更新模型映射逻辑

2. **账号来源**
   - 集成其他邮箱服务
   - 支持已有账号导入

3. **监控集成**
   - Prometheus 指标导出
   - Grafana 可视化面板

4. **API 增强**
   - 添加更多 OpenAI 端点
   - 支持自定义中间件

### 插件机制
- 账号验证插件
- 请求过滤插件
- 响应处理插件
- 日志分析插件

## 🔍 Agent 故障诊断

### 常见问题处理

1. **账号池枯竭**
   - 自动触发批量注册
   - 降级到临时账号
   - 发送告警通知

2. **Token 过期**
   - 自动刷新机制
   - 失败重试策略
   - 手动强制刷新

3. **服务异常**
   - 健康检查端点
   - 自动重启机制
   - 详细错误日志

### 调试工具
- WebSocket 实时监控
- 数据包历史记录
- API 测试脚本
- 性能分析工具

## 📚 Agent 开发指南

### 添加新 Agent

1. **定义职责**: 明确 Agent 的功能边界
2. **接口设计**: RESTful API 或事件驱动
3. **错误处理**: 完善的异常处理机制
4. **测试覆盖**: 单元测试和集成测试
5. **文档更新**: 更新本文档和 API 文档

### 最佳实践

- 使用异步编程提高并发性能
- 实现优雅的关闭机制
- 添加详细的日志记录
- 遵循代码规范和命名约定
- 定期代码审查和重构

## 🎯 未来规划

### 短期目标
- [ ] 添加更多账号来源
- [ ] 优化 Token 刷新策略
- [ ] 增强错误恢复能力
- [ ] 完善监控指标

### 长期目标
- [ ] 多区域部署支持
- [ ] 智能负载均衡
- [ ] 机器学习优化
- [ ] 完整的 GUI 管理界面

---

**文档版本**: 1.0.0  
**最后更新**: 2025-09-29  
**维护者**: Warp2API Team
