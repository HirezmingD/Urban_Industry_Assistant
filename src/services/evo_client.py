"""
EvoMap A2A 客户端核心。

提供 EvomapClient 类及其 A2A 协议方法：hello / heartbeat / publish / status。
所有网络异常均降级返回 dict（含 status: "offline"），不抛异常。
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import secrets
import time as _time_mod
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

_API_TIMEOUT = 5


class EvomapClient:
    """EvoMap Hub A2A 协议客户端。

    提供节点注册（hello）、心跳（heartbeat）、
    Gene+Capsule 发布（publish）、状态查询（status）。
    """

    def __init__(self) -> None:
        self.base_url: str = EVOMAP_HUB_URL.rstrip("/")
        self.node_id: str | None = EVOMAP_NODE_ID or None
        self.node_secret: str = EVOMAP_NODE_SECRET or ""
        self._credit_balance: float = 0.0
        self._last_heartbeat_at: float = 0.0
        self._message_seq: int = 0
        self._heartbeat_fail_count: int = 0
        self._last_publish_success: bool = True

    def _make_message_id(self) -> str:
        """生成唯一消息 ID。"""
        self._message_seq += 1
        return f"msg_{self.node_id or 'anon'}_{int(_time_mod.time())}_{self._message_seq}"

    def _make_timestamp(self) -> str:
        """生成 ISO 8601 时间戳。"""
        return datetime.now(timezone.utc).isoformat()

    def _auth_headers(self) -> dict[str, str]:
        """构造认证头。"""
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self.node_secret:
            headers["Authorization"] = f"Bearer {self.node_secret}"
        return headers

    async def hello(self) -> dict[str, Any]:
        """POST /a2a/hello — 节点注册。"""
        try:
            async with httpx.AsyncClient(timeout=_API_TIMEOUT) as client:
                resp = await client.post(
                    f"{self.base_url}/a2a/hello",
                    json={"node_name": self.node_id or "urban_industry_assistant"},
                    headers=self._auth_headers(),
                )
                resp.raise_for_status()
                data = resp.json()
                self.node_id = data.get("node_id", self.node_id)
                self.node_secret = data.get("node_secret", self.node_secret)
                self._credit_balance = data.get("credit_balance", 0.0)
                return {"status": "ok", "node_id": self.node_id}
        except Exception as e:
            logger.warning("EvoMap hello 失败: %s", e)
            return {"status": "offline", "error": str(e)}

    async def heartbeat(self) -> dict[str, Any]:
        """POST /a2a/heartbeat — 心跳保活。"""
        try:
            async with httpx.AsyncClient(timeout=_API_TIMEOUT) as client:
                resp = await client.post(
                    f"{self.base_url}/a2a/heartbeat",
                    json={"node_id": self.node_id},
                    headers=self._auth_headers(),
                )
                resp.raise_for_status()
                self._last_heartbeat_at = _time_mod.time()
                self._heartbeat_fail_count = 0
                logger.debug("EvoMap heartbeat ok")
                return {"status": "ok"}
        except httpx.HTTPStatusError as e:
            self._heartbeat_fail_count += 1
            logger.warning("EvoMap heartbeat HTTP %d: %s", e.response.status_code, e.response.text[:200])
            return {"status": "offline", "error": str(e)}
        except Exception as e:
            self._heartbeat_fail_count += 1
            logger.warning("EvoMap heartbeat 异常: %s", e)
            return {"status": "offline", "error": str(e)}

    async def start_heartbeat_loop(self, interval: int = 180) -> None:
        """后台心跳循环（不阻塞 startup）。"""
        import asyncio
        while True:
            await self.heartbeat()
            await asyncio.sleep(interval)

    async def publish(
        self,
        *,
        gene_payload: dict[str, Any],
        capsule_payload: dict[str, Any],
        scene: str = "",
        trigger: str = "",
    ) -> dict[str, Any]:
        """发布 Gene + Capsule 到 EvoMap（v2.1 重构）。"""
        _start = _time_mod.time()
        gene = gene_payload
        capsule = capsule_payload
        gene["asset_id"] = self.compute_asset_id(gene)
        capsule["gene"] = gene["asset_id"]
        capsule["asset_id"] = self.compute_asset_id(capsule)

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
                self._last_publish_success = True
                publish_response_raw = json.dumps(data, ensure_ascii=False)
                elapsed = int((_time_mod.time() - _start) * 1000)
                logger.info(
                    "EvoMap publish 成功 | asset_id=%s | scene=%s | gene_ver=v%s | elapsed=%dms",
                    capsule.get("asset_id", "?"),
                    scene,
                    capsule.get("capsule_data", {}).get("gene_version", "?"),
                    elapsed,
                )
        except httpx.HTTPStatusError as e:
            elapsed = int((_time_mod.time() - _start) * 1000)
            publish_response_raw = str(e)
            self._last_publish_success = False
            logger.warning(
                "EvoMap publish 失败 | scene=%s | HTTP %d | body=%s",
                scene, e.response.status_code if e.response else 0, str(e)[:200],
            )
            data = {"status": "offline", "error": str(e)}
        except Exception as e:
            elapsed = int((_time_mod.time() - _start) * 1000)
            publish_response_raw = str(e)
            self._last_publish_success = False
            logger.warning(
                "EvoMap publish 失败 | scene=%s | error=%s: %s",
                scene, type(e).__name__, str(e)[:200],
            )
            data = {"status": "offline", "error": str(e)}

        # 写入本地缓存
        try:
            conn = get_connection()
            try:
                cd = capsule.get("capsule_data", {})
                conn.execute(
                    """INSERT INTO evomap_capsules
                       (gene_asset_id, capsule_asset_id, evaluation_id,
                        summary, confidence, publish_status, publish_response,
                        scene, trigger_reason, change_reason, impact)
                       VALUES (?, ?, NULL, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        gene["asset_id"], capsule["asset_id"],
                        capsule.get("summary", "")[:500],
                        capsule.get("confidence", 0.5),
                        "candidate" if publish_ok else "rejected",
                        publish_response_raw,
                        scene or "", trigger or "",
                        cd.get("recommendations", "")[:200],
                        cd.get("grid_context", ""),
                    ),
                )
                conn.commit()
            finally:
                conn.close()
        except Exception:
            logger.exception("写入 evomap_capsules 失败（不影响主流程）")

        return {
            "asset_id": capsule.get("asset_id", "?"),
            "status": "candidate" if publish_ok else "rejected",
            "elapsed_ms": int((_time_mod.time() - _start) * 1000),
        }

    async def status(self) -> dict[str, Any]:
        """获取 EvoMap 节点状态。"""
        online = (_time_mod.time() - self._last_heartbeat_at) < 900
        return {
            "online": online and bool(self.node_id),
            "node_id": self.node_id,
            "credit_balance": self._credit_balance,
            "survival_status": "alive" if online else "unknown",
        }

    @property
    def heartbeat_fail_count(self) -> int:
        return self._heartbeat_fail_count

    @property
    def degraded(self) -> bool:
        return self._heartbeat_fail_count >= 3 or not self._last_publish_success

    @staticmethod
    def compute_asset_id(asset: dict[str, Any]) -> str:
        """计算 SHA-256 asset_id。"""
        def _normalize(obj: Any) -> Any:
            if isinstance(obj, dict):
                filtered = {k: _normalize(v) for k, v in obj.items() if k != "asset_id"}
                return dict(sorted(filtered.items()))
            if isinstance(obj, list):
                return [_normalize(i) for i in obj]
            return obj
        canonical = json.dumps(_normalize(asset), sort_keys=True, ensure_ascii=False)
        return "sha256:" + hashlib.sha256(canonical.encode()).hexdigest()


# ============================================================
# 模块级单例
# ============================================================

evo_client = EvomapClient()

# ============================================================
# v2.1: Gene/Capsule payload 构建器
# ============================================================

def _build_gene_summary(
    result: dict[str, Any],
    stats: dict[str, Any],
    policy_context: dict[str, Any],
    gene_version: float,
) -> str:
    """构造 Gene summary 字符串（F2 真实化）。"""
    items = result.get("items", [])
    top3 = "/".join(f"{i.get('industry','?')}{i.get('score','?')}分" for i in items[:3])
    confidence = items[0].get("score", 0) / 10 if items else 0
    grid_count = stats.get("grid_count", 0)
    area_km2 = round(stats.get("total_area_mu", 0) / 1500, 1)
    policy_refs = result.get("policy_citations", [])[:2]
    policy_str = "；".join(policy_refs[:2]) if policy_refs else "未引用政策"
    summary = (
        f"基于七维评估模型（能落基础0.30/应落空间0.25/需落战略0.20/"
        f"风险扣分0.15/产业集聚0.05/政策匹配0.03/企业需求0.02）"
        f"对{grid_count}个100m渔网网格进行产业适配评估。"
        f"推荐：{top3}。置信度{confidence:.2f}。"
        f"覆盖约{area_km2}km²。引用：{policy_str}。"
    )
    from src.services.gene_service import desensitize_text
    return desensitize_text(summary)[:1000]


def _build_capsule_summary(
    result: dict[str, Any],
    stats: dict[str, Any],
    bbox: str | None,
    grid_ids: list[str],
    gene_version: float,
) -> str:
    """构造 Capsule summary 字符串（F3 真实化）。"""
    items = result.get("items", [])
    top3 = "/".join(f"{i.get('industry','?')}{i.get('score','?')}分" for i in items[:3])
    confidence = items[0].get("score", 0) / 10 if items else 0
    grid_count = stats.get("grid_count", 0)
    land_dist = stats.get("land_type_distribution", {})
    land_top = "/".join(
        f"{k}{int(v)}%" for k, v in sorted(land_dist.items(), key=lambda x: -x[1])[:3]
    ) if land_dist else "未知"
    bbox_str = bbox or "全县范围"
    summary = (
        f"评估[{bbox_str}]，{grid_count}个网格，地类[{land_top}]。"
        f"推荐：{top3}。置信度{confidence:.2f}。Gene v{gene_version}。"
    )
    from src.services.gene_service import desensitize_text
    return desensitize_text(summary)[:500]
