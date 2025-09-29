#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
号池管理器
负责维护账号池，自动补充账号，处理并发请求的账号分配
"""

import asyncio
import time
import uuid
import threading
from typing import List, Optional, Tuple, Dict, Any
from dataclasses import dataclass
from datetime import datetime, timedelta

from config import config
from utils.logger import logger
from .database import Account, get_database
from .batch_register import get_batch_register
from .token_refresh_service import get_token_refresh_service


@dataclass
class SessionContext:
    """会话上下文"""
    session_id: str
    accounts: List[Account]
    created_at: datetime
    last_used: datetime
    
    def is_expired(self, timeout_seconds: int = None) -> bool:
        """检查会话是否超时"""
        if timeout_seconds is None:
            timeout_seconds = config.SESSION_TIMEOUT
        return datetime.now() - self.last_used > timedelta(seconds=timeout_seconds)


class PoolManager:
    """号池管理器"""
    
    def __init__(self):
        """初始化号池管理器"""
        self.db = get_database()
        self.batch_register = get_batch_register()
        self.token_refresh_service = get_token_refresh_service()
        self._lock = threading.Lock()
        self._sessions: Dict[str, SessionContext] = {}
        self._maintenance_task = None
        self._running = False
        
        # 429错误统计
        self._429_stats = {
            'total_429_errors': 0,
            'deleted_accounts': 0,
            'retry_successes': 0,
            'retry_failures': 0,
            'last_429_time': None,
            'hourly_deletes': []  # 每小时删除数记录
        }
        logger.info("号池管理器初始化完成")
    
    async def start(self):
        """启动号池管理器"""
        with self._lock:
            if self._running:
                logger.warning("号池管理器已在运行")
                return
            
            self._running = True
        
        logger.info("启动号池管理器...")
        
        # 启动维护任务
        self._maintenance_task = asyncio.create_task(self._maintenance_loop())
        
        # 初始化账号池
        await self._ensure_minimum_accounts()
        
        logger.success("号池管理器启动完成")
    
    async def stop(self):
        """停止号池管理器"""
        with self._lock:
            if not self._running:
                return
            
            self._running = False
        
        logger.info("停止号池管理器...")
        
        # 取消维护任务
        if self._maintenance_task:
            self._maintenance_task.cancel()
            try:
                await self._maintenance_task
            except asyncio.CancelledError:
                pass
        
        # 释放所有会话
        await self._release_all_sessions()
        
        logger.info("号池管理器已停止")
    
    async def allocate_accounts_for_request(self, request_id: str = None) -> Optional[List[Account]]:
        """为请求分配账号"""
        if not self._running:
            logger.error("号池管理器未启动")
            return None
        
        # 生成会话ID
        session_id = request_id or f"session_{uuid.uuid4().hex[:8]}_{int(time.time())}"
        
        logger.info(f"为请求分配账号: {session_id}")
        
        # 检查是否已有绑定的账号（基于 IP 的 session 复用）
        with self._lock:
            if session_id in self._sessions:
                # 会话已存在，返回已分配的账号
                session_context = self._sessions[session_id]
                # 更新会话活跃时间
                session_context.last_used = datetime.now()
                logger.info(f"复用已有会话的账号: {session_id}, 账号数: {len(session_context.accounts)}")
                return session_context.accounts
        
        # 检查数据库中是否有该 session 的账号（可能是服务重启后的恢复）
        existing_accounts = self.db.get_accounts_by_session(session_id)
        if existing_accounts:
            logger.info(f"从数据库恢复会话账号: {session_id}, 账号数: {len(existing_accounts)}")
            
            # 检查并刷新过期的token
            refreshed_accounts = await self._check_and_refresh_tokens(existing_accounts)
            if refreshed_accounts:
                existing_accounts = refreshed_accounts
            
            # 创建会话上下文
            session_context = SessionContext(
                session_id=session_id,
                accounts=existing_accounts,
                created_at=datetime.now(),
                last_used=datetime.now()
            )
            with self._lock:
                self._sessions[session_id] = session_context
            return existing_accounts
        
        # 确保有足够的可用账号
        await self._ensure_minimum_accounts()
        
        # 从数据库分配新账号
        accounts = self.db.allocate_accounts_for_session(session_id, config.ACCOUNTS_PER_REQUEST)
        
        if not accounts:
            logger.error(f"无法为请求 {session_id} 分配账号，账号池可能不足")
            # 尝试紧急补充账号
            await self._emergency_replenish()
            accounts = self.db.allocate_accounts_for_session(session_id, config.ACCOUNTS_PER_REQUEST)
            
            if not accounts:
                logger.error(f"紧急补充后仍无法为请求 {session_id} 分配账号")
                return None
        
        # 检查并刷新过期的token
        refreshed_accounts = await self._check_and_refresh_tokens(accounts)
        if refreshed_accounts:
            accounts = refreshed_accounts
        
        # 创建会话上下文
        session_context = SessionContext(
            session_id=session_id,
            accounts=accounts,
            created_at=datetime.now(),
            last_used=datetime.now()
        )
        
        with self._lock:
            self._sessions[session_id] = session_context
        
        logger.success(f"成功为请求 {session_id} 分配 {len(accounts)} 个账号")
        return accounts
    
    async def release_accounts_for_request(self, session_id: str, delete_accounts: bool = False) -> bool:
        """释放请求的账号，可选择删除（429错误时）"""
        action = "删除" if delete_accounts else "释放"
        logger.info(f"{action}请求的账号: {session_id}")
        
        # 从会话记录中移除
        with self._lock:
            if session_id in self._sessions:
                del self._sessions[session_id]
        
        # 在数据库中释放或删除账号
        success = self.db.release_accounts_for_session(session_id, delete_accounts)
        
        # 更新429统计
        if delete_accounts and success:
            with self._lock:
                self._429_stats['total_429_errors'] += 1
                self._429_stats['deleted_accounts'] += 1
                self._429_stats['last_429_time'] = datetime.now()
                
                # 记录每小时删除数
                current_hour = datetime.now().strftime("%Y-%m-%d %H:00")
                self._429_stats['hourly_deletes'].append({
                    'hour': current_hour,
                    'timestamp': datetime.now()
                })
                
                # 只保留最近24小时的记录
                cutoff_time = datetime.now() - timedelta(hours=24)
                self._429_stats['hourly_deletes'] = [
                    record for record in self._429_stats['hourly_deletes']
                    if record['timestamp'] > cutoff_time
                ]
            
            # 检查是否需要补充
            await self._check_and_replenish_pool()
            
            # 检查删除率是否过高
            await self._check_429_alert()
        
        return success
    
    async def get_pool_status(self) -> Dict[str, any]:
        """获取账号池状态"""
        stats = self.db.get_pool_statistics()
        
        with self._lock:
            active_sessions_count = len(self._sessions)
            
            # 计算最近1小时的删除数
            one_hour_ago = datetime.now() - timedelta(hours=1)
            hourly_deletes = len([
                record for record in self._429_stats['hourly_deletes']
                if record['timestamp'] > one_hour_ago
            ])
        
        status = {
            "pool_stats": stats,
            "active_sessions": active_sessions_count,
            "running": self._running,
            "min_pool_size": config.MIN_POOL_SIZE,
            "accounts_per_request": config.ACCOUNTS_PER_REQUEST,
            "health": self._check_pool_health(stats),
            "429_stats": {
                "total_429_errors": self._429_stats['total_429_errors'],
                "deleted_accounts": self._429_stats['deleted_accounts'],
                "hourly_deletes": hourly_deletes,
                "last_429_time": self._429_stats['last_429_time'].isoformat() if self._429_stats['last_429_time'] else None
            }
        }
        
        return status
    
    def _check_pool_health(self, stats: Dict[str, int]) -> str:
        """检查账号池健康状态"""
        available_count = stats.get('available', 0)
        total_count = stats.get('total', 0)
        
        if available_count >= config.MIN_POOL_SIZE * 2:
            return "healthy"
        elif available_count >= config.MIN_POOL_SIZE:
            return "good"
        elif available_count > 0:
            return "low"
        else:
            return "critical"
    
    async def _check_429_alert(self):
        """检查429错误率是否需要告警"""
        # 计算最近1小时的删除数
        one_hour_ago = datetime.now() - timedelta(hours=1)
        hourly_deletes = len([
            record for record in self._429_stats['hourly_deletes']
            if record['timestamp'] > one_hour_ago
        ])
        
        # 如果1小时内删除超过100个账号，发出告警
        if hourly_deletes > 100:
            logger.error(f"⚠️ 429错误率过高！最近1小时删除了 {hourly_deletes} 个账号")
            
        # 如果账号池即将耗尽，发出紧急告警
        stats = self.db.get_pool_statistics()
        if stats.get('available', 0) < 5:
            logger.critical(f"🚨 账号池即将耗尽！仅剩 {stats.get('available', 0)} 个可用账号")
    
    async def _ensure_minimum_accounts(self):
        """确保最少账号数量"""
        available_accounts = self.db.get_available_accounts()
        current_count = len(available_accounts)
        
        if current_count < config.MIN_POOL_SIZE:
            need_count = config.MIN_POOL_SIZE - current_count
            logger.warning(f"账号池不足，当前 {current_count} 个，需要 {need_count} 个")
            await self._replenish_accounts(need_count)
    
    async def _replenish_accounts(self, count: int):
        """补充账号"""
        logger.info(f"开始补充 {count} 个账号...")
        
        try:
            # 使用批量注册器注册新账号（同步调用）
            results = self.batch_register.register_accounts_concurrent(count)
            
            # 统计成功数量
            saved_count = sum(1 for result in results if result['success'])
            
            if saved_count > 0:
                logger.success(f"成功补充 {saved_count}/{count} 个账号")
            else:
                logger.error("补充账号失败")
                
            return saved_count
        except Exception as e:
            logger.error(f"补充账号时发生异常: {e}")
            return 0
    
    async def _emergency_replenish(self):
        """紧急补充账号（小批量快速补充）"""
        logger.warning("执行紧急账号补充...")
        emergency_count = min(5, config.BATCH_REGISTER_SIZE)  # 紧急时只补充少量账号
        await self._replenish_accounts(emergency_count)
    
    async def _maintenance_loop(self):
        """维护循环任务"""
        logger.info("号池维护任务开始运行")
        
        while self._running:
            try:
                await self._maintenance_cycle()
                
                # 等待一定时间后再次检查
                await asyncio.sleep(60)  # 每分钟检查一次
                
            except asyncio.CancelledError:
                logger.info("维护任务被取消")
                break
            except Exception as e:
                logger.error(f"维护任务异常: {e}")
                await asyncio.sleep(30)  # 出错后等待30秒再继续
        
        logger.info("号池维护任务结束")
    
    async def _maintenance_cycle(self):
        """单次维护周期"""
        try:
            # 1. 清理过期会话
            await self._cleanup_expired_sessions()
            
            # 2. 检查账号池是否需要补充
            await self._check_and_replenish_pool()
            
            # 3. 清理过期账号
            self._cleanup_expired_accounts()
            
            # 4. 记录状态
            status = await self.get_pool_status()
            logger.debug(f"账号池状态: {status['pool_stats']}, 健康度: {status['health']}")
            
        except Exception as e:
            logger.error(f"维护周期异常: {e}")
    
    async def _cleanup_expired_sessions(self):
        """清理过期会话"""
        expired_sessions = []
        
        with self._lock:
            for session_id, context in self._sessions.items():
                if context.is_expired():
                    expired_sessions.append(session_id)
        
        # 清理过期会话
        for session_id in expired_sessions:
            logger.info(f"清理过期会话: {session_id}")
            await self.release_accounts_for_request(session_id)
    
    async def _check_and_replenish_pool(self):
        """检查并补充账号池"""
        stats = self.db.get_pool_statistics()
        available_count = stats.get('available', 0)
        
        # 检查是否需要补充
        if available_count < config.MIN_POOL_SIZE:
            need_count = config.MIN_POOL_SIZE - available_count
            await self._replenish_accounts(need_count)
        
        # 如果账号总数过多，可以考虑清理一些旧账号（可选）
        total_count = stats.get('total', 0)
        if total_count > config.MAX_POOL_SIZE:
            logger.info(f"账号总数 {total_count} 超过最大值 {config.MAX_POOL_SIZE}，考虑清理旧账号")
            # 这里可以添加清理逻辑，比如删除最久未使用的账号
    
    def _cleanup_expired_accounts(self):
        """清理过期账号"""
        deleted_count = self.db.cleanup_expired_accounts()
        if deleted_count > 0:
            logger.info(f"清理了 {deleted_count} 个过期账号")
    
    async def _release_all_sessions(self):
        """释放所有会话"""
        with self._lock:
            session_ids = list(self._sessions.keys())
        
        for session_id in session_ids:
            await self.release_accounts_for_request(session_id)
        
        logger.info(f"释放了 {len(session_ids)} 个活跃会话")
    
    # 特殊方法：手动管理
    async def manual_replenish(self, count: int = None) -> int:
        """手动补充账号"""
        if count is None:
            count = config.BATCH_REGISTER_SIZE
        
        logger.info(f"手动补充 {count} 个账号")
        await self._replenish_accounts(count)
        
        # 返回当前可用账号数
        stats = self.db.get_pool_statistics()
        return stats.get('available', 0)
    
    async def refresh_pool(self) -> bool:
        """刷新账号池（清理+补充）"""
        logger.info("刷新账号池")
        
        try:
            # 清理过期账号
            self._cleanup_expired_accounts()
            
            # 确保最少账号数量
            await self._ensure_minimum_accounts()
            
            logger.success("账号池刷新完成")
            return True
        except Exception as e:
            logger.error(f"账号池刷新失败: {e}")
            return False
    
    async def _check_and_refresh_tokens(self, accounts: List[Account]) -> Optional[List[Account]]:
        """检查并刷新过期的tokens——严格遵守1小时限制"""
        refreshed_accounts = []
        need_refresh = False
        
        for account in accounts:
            try:
                # 检查token是否需要刷新（仅在接近过期时）
                success, updated_account, error_msg = self.token_refresh_service.refresh_account_if_needed(
                    account, buffer_minutes=10  # 10分钟缓冲时间
                )
                
                if success and updated_account:
                    refreshed_accounts.append(updated_account)
                    if updated_account != account:  # token实际被刷新了
                        need_refresh = True
                        logger.info(f"✨ 账号token已刷新: {account.email}")
                else:
                    # 刷新失败，但仍然使用原账号
                    refreshed_accounts.append(account)
                    if error_msg and "需要等待" not in error_msg:  # 不是时间限制错误
                        logger.warning(f"⚠️ 账号token刷新失败: {account.email} - {error_msg}")
                
            except Exception as e:
                logger.error(f"检查账号token时异常: {account.email} - {e}")
                refreshed_accounts.append(account)  # 异常时仍然使用原账号
        
        return refreshed_accounts if need_refresh else None
    
    async def refresh_account_tokens_manually(self, email: str = None, force: bool = False) -> Dict[str, Any]:
        """
        手动刷新账号token（管理员功能）
        
        Args:
            email: 指定账号邮箱，为None则刷新所有适合的账号
            force: 是否强制刷新（忽略时间限制）⚠️ 危险
            
        Returns:
            刷新结果统计
        """
        result = {
            "success_count": 0,
            "failed_count": 0,
            "skipped_count": 0,
            "details": []
        }
        
        try:
            if email:
                # 刷新指定账号
                account = self.db.get_account_by_email(email)
                if not account:
                    result["details"].append({"email": email, "status": "not_found"})
                    result["failed_count"] += 1
                    return result
                
                accounts_to_refresh = [account]
            else:
                # 刷新所有可用账号
                accounts_to_refresh = self.db.get_available_accounts()
            
            logger.info(f"开始手动刷新 {len(accounts_to_refresh)} 个账号的token（force={force}）")
            
            for account in accounts_to_refresh:
                try:
                    if force:
                        # 强制刷新模式
                        success, updated_account, error_msg = self.token_refresh_service.refresh_account_token(
                            account, force_refresh=True
                        )
                    else:
                        # 安全刷新模式（遵守1小时限制）
                        success, updated_account, error_msg = self.token_refresh_service.refresh_account_if_needed(
                            account, buffer_minutes=5
                        )
                    
                    if success:
                        if updated_account and updated_account != account:
                            result["success_count"] += 1
                            result["details"].append({
                                "email": account.email,
                                "status": "refreshed",
                                "message": "Token已刷新"
                            })
                        else:
                            result["skipped_count"] += 1
                            result["details"].append({
                                "email": account.email,
                                "status": "skipped",
                                "message": error_msg or "Token仍有效"
                            })
                    else:
                        result["failed_count"] += 1
                        result["details"].append({
                            "email": account.email,
                            "status": "failed",
                            "message": error_msg or "未知错误"
                        })
                        
                except Exception as e:
                    result["failed_count"] += 1
                    result["details"].append({
                        "email": account.email,
                        "status": "error",
                        "message": str(e)
                    })
            
            logger.info(f"手动token刷新完成: 成功 {result['success_count']}, 跳过 {result['skipped_count']}, 失败 {result['failed_count']}")
            return result
            
        except Exception as e:
            logger.error(f"手动刷新token异常: {e}")
            result["details"].append({"error": str(e)})
            return result


# 全局号池管理器实例
_pool_manager_instance = None


def get_pool_manager() -> PoolManager:
    """获取号池管理器实例（单例模式）"""
    global _pool_manager_instance
    if _pool_manager_instance is None:
        _pool_manager_instance = PoolManager()
    return _pool_manager_instance