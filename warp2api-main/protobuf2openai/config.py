from __future__ import annotations

import os

BRIDGE_BASE_URL = os.getenv("WARP_BRIDGE_URL", "http://127.0.0.1:8000")
FALLBACK_BRIDGE_URLS = [
    BRIDGE_BASE_URL,
    "http://127.0.0.1:8000",
]

WARMUP_INIT_RETRIES = int(os.getenv("WARP_COMPAT_INIT_RETRIES", "10"))
WARMUP_INIT_DELAY_S = float(os.getenv("WARP_COMPAT_INIT_DELAY", "0.5"))
WARMUP_REQUEST_RETRIES = int(os.getenv("WARP_COMPAT_WARMUP_RETRIES", "3"))
WARMUP_REQUEST_DELAY_S = float(os.getenv("WARP_COMPAT_WARMUP_DELAY", "1.5"))

# 429错误处理配置
MAX_429_RETRY_LIMIT = int(os.getenv("MAX_429_RETRY_LIMIT", "3"))
ENABLE_429_AUTO_SWITCH = os.getenv("ENABLE_429_AUTO_SWITCH", "true").lower() == "true"
POOL_SERVICE_URL = os.getenv("POOL_SERVICE_URL", "http://localhost:8019")
USE_POOL_SERVICE = os.getenv("USE_POOL_SERVICE", "true").lower() == "true"

# IP绑定配置
ENABLE_IP_BINDING = os.getenv("ENABLE_IP_BINDING", "true").lower() == "true"  # 是否启用基于IP的会话绑定 