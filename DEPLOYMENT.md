# Warp2API 服务器部署指南

## 🚀 概述

Warp2API是一个集成了账号池管理的Protobuf编码代理服务，支持自动账号注册、管理和负载均衡。

## 🎯 架构

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   用户请求      │───▶│   Warp2API      │───▶│   Warp 官方API  │
│  (带客户端IP)   │    │   (Port 8000)   │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                              │                        │
                              ▼                        │ 429错误
                       ┌─────────────────┐            │
                       │   账号池服务    │←───────────┘
                       │   (Port 8019)   │ (自动切换账号)
                       └─────────────────┘
                              │
                              ▼
                       ┌─────────────────┐
                       │  SQLite 数据库  │
                       │  (accounts.db)  │
                       │ (IP-账号绑定)   │
                       └─────────────────┘
```

## 📋 系统要求

### 硬件要求
- **CPU**: 2核以上
- **内存**: 2GB以上
- **磁盘**: 10GB可用空间
- **网络**: 稳定的互联网连接（需要访问Google服务）

### 软件要求
- **操作系统**: Ubuntu 20.04+ / CentOS 8+ / Debian 10+
- **Python**: 3.8+
- **包管理器**: pip3
- **系统工具**: curl, lsof
- **可选**: systemd（用于服务管理）

## 🛠️ 部署步骤

### 1. 环境准备

```bash
# 更新系统
sudo apt update && sudo apt upgrade -y

# 安装必要软件
sudo apt install -y python3 python3-pip curl lsof git

# 验证Python版本
python3 --version  # 应该是3.8+
```

### 2. 获取代码

```bash
# 克隆仓库
git clone <your-repo-url> warp2api
cd warp2api

# 检查文件结构
ls -la
# 应该看到：
# - account-pool-service/
# - warp2api-main/  
# - config/
# - start_production.sh
# - stop_production.sh
```

### 3. 配置环境

编辑生产环境配置：

```bash
cp config/production.env config/production.local.env
vim config/production.local.env
```

重要配置项：
```bash
# 根据服务器情况调整
POOL_MIN_SIZE=10          # 最小账号池大小
POOL_MAX_SIZE=100         # 最大账号池大小
ACCOUNTS_PER_REQUEST=1    # 每次请求分配的账号数

# 429错误处理（新增 v1.1.0）
MAX_429_RETRY_LIMIT=3     # 最大重试次数
ENABLE_429_AUTO_SWITCH=true # 启用自动切换

# IP会话绑定（新增 v1.2.0）
ENABLE_IP_BINDING=true    # 启用IP绑定
SESSION_TIMEOUT=1800      # 会话超时（秒）

# 安全配置
JWT_SECRET_KEY=your-random-secret-key-here

# 如果需要监控
ENABLE_METRICS=true
METRICS_PORT=9090
```

### 4. 启动服务

```bash
# 使用生产环境脚本启动
./start_production.sh
```

服务启动后会显示：
- ✅ 账号池服务: http://localhost:8019
- ✅ Warp2API服务: http://localhost:8000

### 5. 验证部署

```bash
# 检查服务状态
curl http://localhost:8019/health
curl http://localhost:8000/healthz

# 检查账号池状态
curl http://localhost:8019/api/accounts/status

# 检查认证状态
curl http://localhost:8000/api/auth/status
```

## 🔧 系统服务配置（可选）

### 创建systemd服务

1. 创建账号池服务文件：

```bash
sudo vim /etc/systemd/system/warp-pool.service
```

```ini
[Unit]
Description=Warp Account Pool Service
After=network.target

[Service]
Type=simple
User=your-user
WorkingDirectory=/path/to/warp2api/account-pool-service
ExecStart=/usr/bin/python3 main.py
Restart=always
RestartSec=10
Environment=POOL_SERVICE_URL=http://localhost:8019
Environment=USE_POOL_SERVICE=true

[Install]
WantedBy=multi-user.target
```

2. 创建Warp2API服务文件：

```bash
sudo vim /etc/systemd/system/warp2api.service
```

```ini
[Unit]
Description=Warp2API Service  
After=network.target warp-pool.service
Requires=warp-pool.service

[Service]
Type=simple
User=your-user
WorkingDirectory=/path/to/warp2api/warp2api-main
ExecStart=/usr/bin/python3 server.py
Restart=always
RestartSec=10
Environment=POOL_SERVICE_URL=http://localhost:8019
Environment=USE_POOL_SERVICE=true

[Install]
WantedBy=multi-user.target
```

3. 启用并启动服务：

```bash
sudo systemctl daemon-reload
sudo systemctl enable warp-pool warp2api
sudo systemctl start warp-pool warp2api

# 检查状态
sudo systemctl status warp-pool
sudo systemctl status warp2api
```

## 🔒 安全配置

### 1. 防火墙配置

```bash
# 仅允许必要端口
sudo ufw allow 8000/tcp  # Warp2API
sudo ufw allow 8019/tcp  # 账号池（如果需要外部访问）
sudo ufw enable
```

### 2. 反向代理（推荐）

使用Nginx作为反向代理：

```nginx
server {
    listen 80;
    server_name your-domain.com;
    
    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    
    # 可选：账号池管理接口（仅内部访问）
    location /pool/ {
        proxy_pass http://localhost:8019/;
        allow 127.0.0.1;
        deny all;
    }
}
```

### 3. SSL证书（推荐）

```bash
# 使用Let's Encrypt
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
```

## 📊 监控和日志

### 日志位置
- **Warp2API日志**: `logs/warp2api.log`
- **账号池日志**: `logs/pool-service.log`
- **PID文件**: `data/*.pid`

### 监控命令
```bash
# 实时查看日志
tail -f logs/warp2api.log
tail -f logs/pool-service.log

# 检查服务状态
curl -s http://localhost:8019/api/accounts/status | jq
curl -s http://localhost:8000/api/auth/status | jq

# 查看429错误统计（新增 v1.1.0）
curl -s http://localhost:8019/api/accounts/status | jq '.["429_stats"]'

# 查看IP会话绑定（新增 v1.2.0）
curl -s http://localhost:8019/api/accounts/status | jq '.sessions'

# 查看系统资源使用
top -p $(cat data/warp2api.pid) -p $(cat data/pool-service.pid)
```

### Prometheus监控（可选）
如果启用了指标收集：
```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'warp2api'
    static_configs:
      - targets: ['localhost:9090']
```

## 🔄 维护操作

### 停止服务
```bash
./stop_production.sh
```

### 重启服务
```bash
./stop_production.sh
./start_production.sh
```

### 更新部署
```bash
# 停止服务
./stop_production.sh

# 拉取最新代码
git pull origin main

# 安装依赖
pip3 install -r account-pool-service/requirements.txt
pip3 install -r warp2api-main/requirements.txt

# 重启服务
./start_production.sh
```

### 数据库维护
```bash
# 查看账号统计
sqlite3 account-pool-service/accounts.db "SELECT status, COUNT(*) FROM accounts GROUP BY status;"

# 清理过期账号（谨慎操作）
sqlite3 account-pool-service/accounts.db "DELETE FROM accounts WHERE status='expired';"
```

## ⚠️ 故障排除

### 常见问题

1. **服务无法启动**
   ```bash
   # 检查端口占用
   lsof -i :8000
   lsof -i :8019
   
   # 检查日志
   tail -50 logs/warp2api.log
   tail -50 logs/pool-service.log
   ```

2. **账号注册失败**
   - 检查网络连接到Google服务
   - 验证Firebase API密钥
   - 检查邮箱服务配置

3. **内存使用过高**
   - 调整账号池大小配置
   - 检查是否有内存泄漏
   - 考虑增加服务器内存

4. **认证失败**
   - 检查账号池中是否有可用账号
   - 验证token刷新逻辑
   - 检查Warp API连通性

5. **429错误频繁**（新增 v1.1.0）
   - 检查账号池大小是否充足
   - 查看每小时删除率是否过高
   - 考虑增加 MAX_429_RETRY_LIMIT
   - 检查是否所有账号都被限流

6. **IP绑定异常**（新增 v1.2.0）
   - 检查Nginx配置X-Forwarded-For头
   - 验证客户端IP是否正确获取
   - 调整SESSION_TIMEOUT避免过早释放
   - 可通过ENABLE_IP_BINDING=false禁用

### 紧急恢复

```bash
# 完全重置（会丢失所有账号数据）
./stop_production.sh
rm -f account-pool-service/accounts.db
./start_production.sh
```

## 📞 支持

如有问题，请检查：
1. 系统要求是否满足
2. 网络连接是否正常
3. 日志文件中的错误信息
4. 配置文件是否正确

---

**版本**: 1.0.0  
**更新时间**: 2025-09-19  
**兼容性**: Ubuntu 20.04+, Python 3.8+