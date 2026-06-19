"""
EvoMap A2A 客户端核心（批次 D 从 evo_service.py 拆分）。

提供 EvomapClient 类及其 A2A 协议方法：hello / heartbeat / publish / status。
所有网络异常均降级返回 dict（含 status: "offline"），不抛异常。

凭证策略：config 环境变量 → ~/.evomap/ 文件 → hello() 注册返回 → 持久化写入 ~/.evomap/
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import secrets
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

from src.config import (
    DEEPSEEK_MODEL,
    EVOMAP_HUB_URL,
    EVOMAP_NODE_ID,
    EVOMAP_NODE_SECRET,
)
from src.database import get_connection

logger = logging.getLogger(__name__)

# 凭证持久化目录
_EVOMAP_DIR = Path.home() / ".evomap"


def _load_persisted_credential(filename: str) -> str | None:
    """从 ~/.evomap/ 读取持久化凭证。"""
    path = _EVOMAP_DIR / filename
    if path.exists():
        try:
            return path.read_text(encoding="utf-8").strip()
        except OSError:
            pass
    return None


def _persist_credential(filename: str, value: str) -> None:
    """持久化凭证到 ~/.evomap/。
    Windows 上忽略权限设置，不因写入失败而崩溃。
    """
    try:
        _EVOMAP_DIR.mkdir(parents=True, exist_ok=True)
        (_EVOMAP_DIR / filename).write_text(value, encoding="utf-8")
    except OSError:
        logger.warning("无法写入凭证文件 %s（不影响运行）", filename)


# ============================================================
# EvoMap 客户端
# ============================================================

class EvomapClient:
    """EvoMap A2A 协议客户端。

    提供注册、心跳、发布、状态查询的 async 方法。
    所有网络异常均降级返回 dict，不抛异常。
    """

    def __init__(self) -> None:
        """初始化：解析 node_id / secret，顺序为 config → ~/.evomap/。"""
        self.node_id: str | None = EVOMAP_NODE_ID or _load_persisted_credential("node_id")
        self.secret: str | None = (
            EVOMAP_NODE_SECRET or _load_persisted_credential("node_secret")
        )
        self.base_url: str = EVOMAP_HUB_URL.rstrip("/")
        self._last_heartbeat_at: float = 0.0
        self._last_heartbeat_response: dict[str, Any] = {}
        self._credit_balance: int | None = None

    # ---------- helper ----------

    def _auth_headers(self) -> dict[str, str]:
        """构造鉴权 headers。修复：secret 为空时不拼 Bearer 头。"""
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self.secret:
            headers["Authorization"] = f"Bearer {self.secret}"
        return headers

    def _make_message_id(self) -> str:
        return f"msg_{int(time.time() * 1000)}_{secrets.token_hex(4)}"

    def _make_timestamp(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.") + \
               f"{datetime.now(timezone.utc).microsecond // 1000:03d}Z"

    # ---------- A2A 协议方法 ----------

    async def hello(self) -> dict[str, Any]:
        """POST /a2a/hello — 注册节点。

        首次调用 hub 返回 node_id + node_secret 后持久化到 ~/.evomap/。

        Returns:
            dict: hub 返回值；网络异常时返回 {"status": "offline", "error": str}。
        """
        payload = {
            "protocol": "gep-a2a",
            "protocol_version": "1.0.0",
            "message_type": "hello",
            "message_id": self._make_message_id(),
            "sender_id": "node_urban_industry_assistant",
            "timestamp": self._make_timestamp(),
            "payload": {
                "capabilities": {
                    "land_evaluation": "县域产业用地智能评估",
                    "gis_analysis": "渔网+卫星图多源叠加",
                    "industry_matching": "产业适配评分与推荐",
                },
                "model": DEEPSEEK_MODEL,
                "gene_count": 0,
                "capsule_count": 0,
                "identity_doc": (
                    "Urban_Industry_Assistant 是面向县域政府的产业用地智能评估 Agent，"
                    "基于开放下载的城市存量数据、既有数据、历史积累数据，"
                    "融合多维栅格数据和十五五产业政策知识库，提供产业适配评分与发展建议。"
                ),
                "constitution": (
                    "1. 评估结论必须基于数据，不可凭空推测。\n"
                    "2. 产业发展建议必须对标当地政策规划。\n"
                    "3. 风险提示优先于乐观推荐。"
                ),
            },
        }

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(
                    f"{self.base_url}/a2a/hello",
                    json=payload,
                )
                resp.raise_for_status()
                data = resp.json()
        except Exception as e:
            logger.warning("EvoMap hello 失败: %s", e)
            return {"status": "offline", "error": str(e)}

        # 持久化返回的 node_id / node_secret
        returned_id = data.get("your_node_id")
        returned_secret = data.get("node_secret")
        if returned_id:
            self.node_id = returned_id
            _persist_credential("node_id", returned_id)
        if returned_secret:
            self.secret = returned_secret
            _persist_credential("node_secret", returned_secret)

        self._credit_balance = data.get("credit_balance")
        return data

    async def heartbeat(self) -> dict[str, Any]:
        """POST /a2a/heartbeat — 发送心跳。

        Returns:
            dict: hub 返回；网络异常返回 {"status": "offline"}。
        """
        payload = {
            "protocol": "gep-a2a",
            "protocol_version": "1.0.0",
            "message_type": "heartbeat",
            "message_id": self._make_message_id(),
            "sender_id": self.node_id or "node_urban_industry_assistant",
            "timestamp": self._make_timestamp(),
            "payload": {
                "node_id": self.node_id,
            },
        }

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(
                    f"{self.base_url}/a2a/heartbeat",
                    json=payload,
                    headers=self._auth_headers(),
                )
                resp.raise_for_status()
                data = resp.json()
        except Exception as e:
            logger.warning("EvoMap heartbeat 失败: %s", e)
            return {"status": "offline", "error": str(e)}

        self._last_heartbeat_at = time.time()
        self._last_heartbeat_response = data
        self._credit_balance = data.get("credit_balance", self._credit_balance)
        return data

    async def start_heartbeat_loop(self, interval: int = 300) -> None:
        """后台 async task：每 interval 秒发送一次心跳。

        网络异常不退出循环，持续重试。

        Args:
            interval: 心跳间隔（秒），默认 300（5分钟）。
        """
        logger.info("[EvoMap] 心跳循环启动，间隔 %ds", interval)
        while True:
            try:
                resp = await self.heartbeat()
                logger.info("[EvoMap] heartbeat: %s", resp.get("status", "unknown"))
            except Exception as e:
                logger.warning("[EvoMap] heartbeat 异常: %s", e)
            await asyncio.sleep(interval)

    async def publish(
        self,
        gene_summary: str,
        capsule_summary: str,
        confidence: float,
        grid_count: int,
    ) -> dict[str, Any]:
        """POST /a2a/publish — 发布 Gene + Capsule 捆绑包。

        构建 Gene 和 Capsule 结构体，计算 SHA-256 asset_id，
        发布成功后写入 evomap_capsules 本地缓存表。

        Args:
            gene_summary: Gene 摘要（策略/方法论描述）。
            capsule_summary: Capsule 摘要（本次评估结论）。
            confidence: 自评 confidence 0-1。
            grid_count: 涉及的渔网单元数。

        Returns:
            dict: hub 返回；网络异常返回 {"status": "offline"}。
        """
        # 构建 Gene
        gene: dict[str, Any] = {
            "type": "Gene",
            "schema_version": "1.5.0",
            "category": "innovate",
            "signals_match": [
                "land-use-evaluation",
                "industry-suitability",
                "county-planning",
            ],
            "summary": gene_summary[:1000],
            "model_name": DEEPSEEK_MODEL,
            "domain": "data_analysis",
        }
        gene["asset_id"] = self.compute_asset_id(gene)

        # 构建 Capsule
        capsule: dict[str, Any] = {
            "type": "Capsule",
            "schema_version": "1.5.0",
            "trigger": [
                "land-use-evaluation",
                "industry-suitability",
            ],
            "gene": gene["asset_id"],
            "summary": capsule_summary[:500],
            "confidence": confidence,
            "blast_radius": {
                "files": 1,
                "lines": grid_count * 3,
            },
            "outcome": {
                "status": "success",
                "score": confidence,
            },
            "env_fingerprint": {
                "platform": os.name,
                "arch": "x64",
            },
            "success_streak": 1,
            "model_name": DEEPSEEK_MODEL,
            "domain": "data_analysis",
        }
        capsule["asset_id"] = self.compute_asset_id(capsule)

        # 构建发布信封
        envelope = {
            "protocol": "gep-a2a",
            "protocol_version": "1.0.0",
            "message_type": "publish",
            "message_id": self._make_message_id(),
            "sender_id": self.node_id or "node_urban_industry_assistant",
            "timestamp": self._make_timestamp(),
            "payload": {"assets": [gene, capsule]},
        }

        publish_ok = False
        publish_response_raw: str = ""
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    f"{self.base_url}/a2a/publish",
                    json=envelope,
                    headers=self._auth_headers(),
                )
                resp.raise_for_status()
                data = resp.json()
                publish_ok = True
                publish_response_raw = json.dumps(data, ensure_ascii=False)
        except Exception as e:
            logger.warning("EvoMap publish 失败: %s", e)
            data = {"status": "offline", "error": str(e)}
            publish_response_raw = str(e)

        # 写入本地缓存
        try:
            conn = get_connection()
            try:
                conn.execute(
                    """
                    INSERT INTO evomap_capsules
                        (gene_asset_id, capsule_asset_id, evaluation_id,
                         summary, confidence, publish_status, publish_response)
                    VALUES (?, ?, NULL, ?, ?, ?, ?)
                    """,
                    (
                        gene["asset_id"],
                        capsule["asset_id"],
                        capsule_summary[:500],
                        confidence,
                        "candidate" if publish_ok else "rejected",
                        publish_response_raw,
                    ),
                )
                conn.commit()
            finally:
                conn.close()
        except Exception:
            logger.exception("写入 evomap_capsules 失败（不影响主流程）")

        return data

    async def status(self) -> dict[str, Any]:
        """获取 EvoMap 节点状态（本地读取，不调 hub）。

        Returns:
            dict: 含 online / node_id / credit_balance / survival_status。
        """
        online = (time.time() - self._last_heartbeat_at) < 900
        return {
            "online": online and bool(self.node_id),
            "node_id": self.node_id,
            "credit_balance": self._credit_balance,
            "survival_status": "alive" if online else "unknown",
        }

    @staticmethod
    def compute_asset_id(asset: dict[str, Any]) -> str:
        """计算 SHA-256 asset_id。

        排除 asset_id 字段，递归标准化，按 key 排序后取 SHA-256。

        Args:
            asset: Gene 或 Capsule 对象（不含 asset_id）。

        Returns:
            str: "sha256:" + 64 位 hex digest。
        """
        clean = {k: v for k, v in asset.items() if k != "asset_id"}

        def _normalize(val: Any) -> Any:
            if isinstance(val, dict):
                return {k: _normalize(v) for k, v in sorted(val.items())}
            elif isinstance(val, list):
                return [_normalize(v) for v in val]
            return val

        normalized = _normalize(clean)
        s = json.dumps(normalized, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        return "sha256:" + hashlib.sha256(s.encode("utf-8")).hexdigest()


# ============================================================
# 模块级单例
# ============================================================

evo_client = EvomapClient()
"""全局 EvoMap 客户端实例，被 main.py startup 事件引用。"""
