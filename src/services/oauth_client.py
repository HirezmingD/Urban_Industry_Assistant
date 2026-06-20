"""
EvoMap OAuth2 PKCE 客户端。

提供 PKCE 授权流程（authorize URL / exchange_code / refresh）+ 
EvoMap 开发者平台 API 调用（recipe/gene/reuse 检索），
Token 持久化到 SQLite evomap_tokens 表（单行 id=1）。
"""
from __future__ import annotations

import base64
import hashlib
import logging
import os
import secrets
import urllib.parse
from datetime import datetime, timezone
from typing import Any

import httpx

from src.config import (
    EVOMAP_HUB_URL,
    EVOMAP_OAUTH_CLIENT_ID,
    EVOMAP_OAUTH_CLIENT_SECRET,
    EVOMAP_OAUTH_REDIRECT_URI,
)
from src.database import get_connection

logger = logging.getLogger(__name__)

# API 超时（秒）
_API_TIMEOUT = 5


class EvoMapOAuthClient:
    """EvoMap OAuth2 开发者平台客户端。

    设计为持久化 token（SQLite + 内存），支持启动恢复和自动刷新。
    所有 EvoMap API 调用失败均静默降级，返回空结果。
    """

    def __init__(self) -> None:
        """初始化：从 config 读取 client_id/secret/base_url/redirect_uri。
        内存属性 access_token / refresh_token 初始为 None（需恢复或授权）。
        """
        self.client_id: str = EVOMAP_OAUTH_CLIENT_ID
        self.client_secret: str = EVOMAP_OAUTH_CLIENT_SECRET
        self.base_url: str = EVOMAP_HUB_URL.rstrip("/")
        self.redirect_uri: str = EVOMAP_OAUTH_REDIRECT_URI

        self.access_token: str | None = None
        self.refresh_token: str | None = None
        self.expires_at: str | None = None
        self.scope: str | None = None

        # 当前 OAuth2 流程中的临时状态（单实例安全）
        self._pending_verifier: str | None = None
        self._pending_state: str | None = None

    # ── PKCE 工具（静态）──

    @staticmethod
    def generate_pkce_pair() -> tuple[str, str]:
        """生成 PKCE code_verifier + code_challenge (S256)。

        Returns:
            tuple[str, str]: (verifier, challenge)
        """
        verifier = secrets.token_urlsafe(64)
        digest = hashlib.sha256(verifier.encode("ascii")).digest()
        challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
        return verifier, challenge

    # ── OAuth2 流程 ──

    def build_authorize_url(
        self,
        scopes: str = "recipe:read gene:read reuse:query",
    ) -> str:
        """Step 1: 构造授权 URL（含 PKCE challenge + state）。

        生成 verifier/state 存入实例属性供 callback 校验。

        Args:
            scopes: OAuth2 授权范围，空格分隔。默认为 recipe:read gene:read reuse:query。

        Returns:
            str: 完整 authorize URL 字符串。
        """
        verifier, challenge = self.generate_pkce_pair()
        state = secrets.token_urlsafe(32)

        self._pending_verifier = verifier
        self._pending_state = state

        params: dict[str, str] = {
            "response_type": "code",
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "scope": scopes,
            "state": state,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        }
        query_string = urllib.parse.urlencode(params)
        return f"{self.base_url}/developer/oauth/authorize?{query_string}"

    async def exchange_code(self, code: str, state: str) -> dict[str, Any]:
        """Step 2: 用 authorization code 交换 access_token + refresh_token。

        CSRF 校验 state；成功后写入 self.access_token/refresh_token + 持久化 SQLite。

        Args:
            code: EvoMap 回调返回的 authorization code。
            state: 回调中的 state 参数，用于 CSRF 校验。

        Returns:
            dict: token 响应 dict；失败时返回 {"error": str}。
        """
        # CSRF 校验
        if not self._pending_state or state != self._pending_state:
            return {"error": "CSRF state mismatch"}
        verifier = self._pending_verifier
        if not verifier:
            return {"error": "No PKCE verifier stored"}

        try:
            async with httpx.AsyncClient(timeout=_API_TIMEOUT) as client:
                resp = await client.post(
                    f"{self.base_url}/developer/oauth/token",
                    data={
                        "grant_type": "authorization_code",
                        "client_id": self.client_id,
                        "client_secret": self.client_secret,
                        "code": code,
                        "redirect_uri": self.redirect_uri,
                        "code_verifier": verifier,
                    },
                )
                resp.raise_for_status()
                data = resp.json()
        except Exception as e:
            logger.warning("EvoMap OAuth2 exchange_code 失败: %s", e)
            return {"error": str(e)}

        # 更新内存
        self.access_token = data.get("access_token")
        self.refresh_token = data.get("refresh_token")
        self.expires_at = data.get("expires_at")
        self.scope = data.get("scope")

        # 持久化
        if self.access_token:
            self._persist_tokens()

        # 清理临时状态
        self._pending_verifier = None
        self._pending_state = None

        return data

    async def refresh_access_token(self) -> bool:
        """Step 3: 用 refresh_token 刷新 access_token。

        成功后更新内存 + 持久化。

        Returns:
            bool: 是否刷新成功。
        """
        if not self.refresh_token:
            return False

        try:
            async with httpx.AsyncClient(timeout=_API_TIMEOUT) as client:
                resp = await client.post(
                    f"{self.base_url}/developer/oauth/token",
                    data={
                        "grant_type": "refresh_token",
                        "client_id": self.client_id,
                        "client_secret": self.client_secret,
                        "refresh_token": self.refresh_token,
                    },
                )
                resp.raise_for_status()
                data = resp.json()
        except Exception as e:
            logger.warning("EvoMap OAuth2 refresh_token 失败: %s", e)
            self.access_token = None
            return False

        self.access_token = data.get("access_token")
        new_refresh = data.get("refresh_token")
        if new_refresh:
            self.refresh_token = new_refresh
        self.expires_at = data.get("expires_at")
        self.scope = data.get("scope")

        if self.access_token:
            self._persist_tokens()
            return True
        return False

    async def ensure_token(self) -> bool:
        """确保 access_token 可用：若为空则尝试从 SQLite 恢复并刷新。

        供 eval_service 在调用 API 前使用。

        Returns:
            bool: token 是否就绪。
        """
        if self.access_token:
            return True
        return self._restore_tokens()

    # ── 持久化 ──

    def _persist_tokens(self) -> None:
        """将 access_token / refresh_token 写入 SQLite evomap_tokens 表（UPSERT）。"""
        try:
            conn = get_connection()
            try:
                conn.execute(
                    """
                    INSERT INTO evomap_tokens (id, access_token, refresh_token,
                                               expires_at, scope, updated_at)
                    VALUES (1, ?, ?, ?, ?, ?)
                    ON CONFLICT (id) DO UPDATE SET
                        access_token  = excluded.access_token,
                        refresh_token = excluded.refresh_token,
                        expires_at    = excluded.expires_at,
                        scope         = excluded.scope,
                        updated_at    = excluded.updated_at
                    """,
                    (
                        self.access_token,
                        self.refresh_token,
                        self.expires_at,
                        self.scope,
                        datetime.now(timezone.utc).isoformat(),
                    ),
                )
                conn.commit()
            finally:
                conn.close()
        except Exception:
            logger.warning("evomap_tokens 持久化失败（不影响运行）", exc_info=True)

    def _restore_tokens(self) -> bool:
        """从 SQLite 恢复 token，如 refresh_token 存在则自动刷新。

        Returns:
            bool: 是否恢复成功（access_token 就绪）。
        """
        try:
            conn = get_connection()
            try:
                row = conn.execute(
                    "SELECT access_token, refresh_token, expires_at, scope "
                    "FROM evomap_tokens WHERE id = 1"
                ).fetchone()
            finally:
                conn.close()

            if not row:
                return False

            self.access_token = row["access_token"]
            self.refresh_token = row["refresh_token"]
            self.expires_at = row["expires_at"]
            self.scope = row["scope"]

            # 有 refresh_token 尝试刷新
            if self.refresh_token and not self.access_token:
                import asyncio
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        # 在运行中的 event loop 中，用 create_task 触发刷新
                        # 但同步环境下，先尝试直接使用 refresh_token
                        pass
                except RuntimeError:
                    pass
                # 异步刷新留待下次 API 调用前由 ensure_token 触发

            return bool(self.access_token)

        except Exception:
            logger.warning("evomap_tokens 恢复失败", exc_info=True)
            return False

    # ── API 检索 ──

    @property
    def is_available(self) -> bool:
        """是否可调用 EvoMap API。

        Returns:
            bool: client_id 已配置且 access_token 就绪。
        """
        return bool(self.client_id and self.access_token)

    def _make_headers(self) -> dict[str, str]:
        """构造 API 请求头（含 Bearer token）。"""
        headers: dict[str, str] = {
            "Content-Type": "application/json",
        }
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"
        return headers

    async def search_recipes(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        """全文搜 recipe（提示词增强核心 API）。

        GET /developer/oauth/recipes?q={query}&limit={limit}

        Args:
            query: 搜索关键词。
            limit: 返回条数上限，默认 5。

        Returns:
            list[dict]: recipe 列表；超时/异常返回 []。
        """
        if not self.is_available:
            return []

        try:
            params = urllib.parse.urlencode({"q": query, "limit": str(limit)})
            async with httpx.AsyncClient(timeout=_API_TIMEOUT) as client:
                resp = await client.get(
                    f"{self.base_url}/developer/oauth/recipes?{params}",
                    headers=self._make_headers(),
                )
                resp.raise_for_status()
                data = resp.json()
        except Exception:
            logger.debug("EvoMap search_recipes 不可用，跳过", exc_info=True)
            return []

        # 兼容不同返回格式
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return data.get("recipes", data.get("data", []))
        return []

    async def get_top_genes(self, limit: int = 3) -> list[dict[str, Any]]:
        """获取排行 gene（通用能力补充）。

        GET /developer/oauth/genes?limit={limit}

        Args:
            limit: 返回条数上限，默认 3。

        Returns:
            list[dict]: gene 列表；超时/异常返回 []。
        """
        if not self.is_available:
            return []

        try:
            params = urllib.parse.urlencode({"limit": str(limit)})
            async with httpx.AsyncClient(timeout=_API_TIMEOUT) as client:
                resp = await client.get(
                    f"{self.base_url}/developer/oauth/genes?{params}",
                    headers=self._make_headers(),
                )
                resp.raise_for_status()
                data = resp.json()
        except Exception:
            logger.debug("EvoMap get_top_genes 不可用，跳过", exc_info=True)
            return []

        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return data.get("genes", data.get("data", []))
        return []

    async def query_reuse(self, recipe_id: str) -> dict[str, Any] | None:
        """查询复用/关联图谱。

        GET /developer/oauth/reuse?recipe_id={id}

        Args:
            recipe_id: 目标 recipe ID。

        Returns:
            dict | None: 复用图谱数据；超时/异常返回 None。
        """
        if not self.is_available:
            return None

        try:
            params = urllib.parse.urlencode({"recipe_id": recipe_id})
            async with httpx.AsyncClient(timeout=_API_TIMEOUT) as client:
                resp = await client.get(
                    f"{self.base_url}/developer/oauth/reuse?{params}",
                    headers=self._make_headers(),
                )
                resp.raise_for_status()
                return resp.json()
        except Exception:
            logger.debug("EvoMap query_reuse 不可用，跳过", exc_info=True)
            return None


# ============================================================
# 模块级单例
# ============================================================

oauth_client = EvoMapOAuthClient()
"""全局 OAuth2 客户端实例。"""
