

# ============================================================
# v2.1: Gene/Capsule payload 构建器
# ============================================================

def _build_gene_summary(
    result: dict[str, Any],
    stats: dict[str, Any],
    policy_context: dict[str, Any],
    gene_version: float,
) -> str:
    """构造 Gene summary 字符串（F2 真实化）。

    拼接：七维权重分布 + 推荐产业 Top-3 + 置信度 + 网格采样 + 政策依据。
    ≤ 1000 字符。
    """
    from src.services.gene_service import desensitize_text

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
        f"覆盖约{area_km2}km²。"
        f"引用：{policy_str}。"
    )
    return desensitize_text(summary)[:1000]


def _build_capsule_summary(
    result: dict[str, Any],
    stats: dict[str, Any],
    bbox: str | None,
    grid_ids: list[str],
    gene_version: float,
) -> str:
    """构造 Capsule summary 字符串（F3 真实化）。

    拼接：bbox/网格数/地类分布 Top-3/推荐产业+评分/置信度/Gene版本。
    ≤ 500 字符。
    """
    from src.services.gene_service import desensitize_text

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
    return desensitize_text(summary)[:500]
