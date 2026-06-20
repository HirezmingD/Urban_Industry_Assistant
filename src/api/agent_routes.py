"""
对话评估 REST 端点。

提供 POST /api/agent/chat 接口，接收用户自然语言输入，
返回结构化评估结果。
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request

from src.config import CHAT_MAX_LENGTH
from src.schemas import AgentReply, ChatRequest
from src.services import eval_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/agent", tags=["agent"])


@router.post("/chat", response_model=AgentReply)
async def chat(req: ChatRequest, request: Request) -> dict:
    """对话评估。

    接收用户输入（可附带框选范围），返回 Agent 结构化评估结果。

    Args:
        req: ChatRequest（含 message / role / bbox / context）。

    Returns:
        AgentReply: 含 summary / items / policy_citations / risks / candidate_grids。

    Raises:
        HTTPException: message 为空或超长 400；role 不合法 400。
    """
    # 校验 message
    if not req.message or not req.message.strip():
        raise HTTPException(status_code=400, detail="message 不能为空")
    if len(req.message) > CHAT_MAX_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=f"message 超长（最大 {CHAT_MAX_LENGTH} 字符）",
        )

    # 校验 role
    role_lower = req.role.lower()
    if role_lower not in ("government", "gov", "enterprise", "enterprise"):
        raise HTTPException(
            status_code=400,
            detail=f"无效的 role: {req.role}，仅接受 government 或 enterprise",
        )

    # 构造 user_id（IP + role）用于去重
    client_ip = request.client.host if request.client else "127.0.0.1"
    user_id = f"{client_ip}|{role_lower}"

    # 调 eval_service
    try:
        result = await eval_service.chat(
            message=req.message.strip(),
            role=role_lower,
            context=req.context,
            bbox=req.bbox,
            user_id=user_id,
        )
    except Exception as e:
        logger.exception("eval_service.chat 异常")
        raise HTTPException(status_code=500, detail=str(e))

    # 将 dict 转为 AgentReply 兼容格式
    return {
        "summary": result.get("summary", ""),
        "items": result.get("items", []),
        "policy_citations": result.get("policy_citations", []),
        "risks": result.get("risks", []),
        "candidate_grids": result.get("candidate_grids", []),
    }
