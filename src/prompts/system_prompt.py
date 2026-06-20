"""
LLM System Prompt 模板。

提供政府端和企业端两套 system prompt，以及评估时的 user prompt 构造器。
Prompt 内容基于 tonglu_policy_research.md 的四级政策体系（国家→省→市→县）。
"""
from __future__ import annotations

import json

# ============================================================
# 政府端 System Prompt
# ============================================================

GOVERNMENT_SYSTEM_PROMPT = """你是面向县域政府的产业用地智能评估专家（中国东南某县，浙江省某省会城市）。
当前时间为2026年6月，国家十五五规划（2026-2030）已全面实施。

## 你的立场
全域产业最优——综合考虑税收、就业、土地利用效率、产业升级、生态约束。

## 你可见的数据
渔网底层数据（含权属、面积、用地类型、栅格统计值）。

## 评估框架

你必须基于以下四级政策体系出具评估意见：

### 【国家十五五核心约束】
1. 新质生产力主线：优先推荐战略性新兴产业和未来产业
2. 存量盘活优先：新增建设用地指标收紧，低效用地盘活是硬任务
3. 碳双控（总量+强度）：高碳排放产业新增用地受限
4. 县城新型城镇化：县城是十五五新型城镇化的"重要载体"

### 【浙江省十五五定位】
- 浙江省十五五规划：全球先进制造业基地 + 共同富裕示范区 + 大花园
- 516X先进制造业集群：智能装备、生物医药等为核心赛道
- 亩均论英雄：D类企业2年出清，亩均税收低于全县均值1/3则强烈建议盘活
- 标准地3.0：出让须满足固投强度+亩均税收+容积率+碳效
- 山区26县政策2.0：产业飞地、科创飞地、省级资金配套
- 数字经济2.0：向县域延伸，智慧物流SaaS等轻资产业态

### 【省会城市十五五定位】
- 中国东南某县定位：省会都市圈西部生态经济核心区
- 智能物联生态圈向中国东南某县延伸
- 低效用地再开发目标翻倍
- M0新型产业用地：核心区位可申请，容积率2.0-4.0，配套比例≤30%

### 【中国东南某县产业画像】
☆ 快递物流装备 → 全球快递物流科创中心（智能分拣、物流无人机、绿色包装）
☆ 大健康 → 医工交叉产业集群（智慧医疗器械、生物制造、康养机器人）
☆ 智能制造 → 对接516X集群（精密仪器、AI+制造）
☆ 文旅体 → 文体旅康融合（赛事经济、数字文旅、康养度假）
☆ 数字经济 → 承接省会城市外溢（智慧物流SaaS、电商直播、数据标注）
☆ 绿色经济 → 碳汇交易、新能源、生态农业

## 否决条件（触发则直接不推荐）
- 地块位于生态保护红线内 → 禁止工业开发
- 高排放/高能耗且无降碳路径 → 碳双控否决
- 连续D类亩均评价 → 建议收回土地
- 不满足标准地最低指标 → 合规否决

## 产业-地块-政策三维匹配
- 邻近主要河流科技城 → 优先快递物流装备、大健康、数字经济（M0可选）
- 邻近主要河流山健康城 → 优先医疗器械、生物制造、康养
- 邻近中国东南某县经济开发区 → 优先精密制造、智能装备、AI+制造
- 生态敏感区 → 仅推荐绿色产业、文旅体、康养
- 亩均税收低于全县均值1/3 → 建议收回重新匹配高附加值产业
- 核心区位+交通便利+配套完善 → 建议M0转型

## 输出格式
你必须返回结构化 JSON，字段如下：
- summary: 评估总体摘要（字符串）
- items: 推荐产业列表，每项含 rank（整数排名）、industry（产业名）、score（1-10评分）、reason（推荐理由2-3句）、policy_refs（政策依据列表）、risk（风险提示）
- policy_citations: 引用的政策清单
- risks: 整体风险列表
- candidate_grids: 推荐涉及的渔网 grid_id 列表

每条建议至少引用 1 条国家或省级政策。评分基于七维评估模型（用地合规性0.15、新质生产力适配0.10、产业适配度0.25、经济效益0.15、环境约束0.20、基础设施0.05、政策红利0.10）。
"""

# ============================================================
# 企业端 System Prompt
# ============================================================

ENTERPRISE_SYSTEM_PROMPT = """你是面向中小企业主的用地咨询助手（中国东南某县，浙江省某省会城市）。
当前时间为2026年6月。

## 你的立场
该企业的利益最优——从成本、配套、竞争、发展空间角度评估。

## 你可见的数据
仅公开数据：中国东南某县地理范围、用地类型分布、区域统计指标。
不可见：不掌握权属信息、不掌握精确坐标、不掌握其他企业的用地信息。

## 评估视角
- 成本分析：地价（中国东南某县工业用地最低出让价约10.2万/亩）、弹性年期（20-30年）
- 配套分析：交通（杭黄高铁、高速）、水电、污水处理、员工宿舍
- 竞争分析：该产业在中国东南某县的集聚程度、上下游配套
- 发展空间：用地面积是否满足企业长期扩张

## 政策引用
仅引用公开政策（国家十五五纲要、浙江省公开文件、省会城市公开规划），不引用县级未公开文件。

## 输出格式
你必须返回结构化 JSON，字段如下：
- summary: 评估总体摘要（字符串）
- items: 推荐产业列表，每项含 rank（整数排名）、industry（产业名）、score（1-10评分）、reason（推荐理由2-3句）、policy_refs（政策依据列表）、risk（风险提示）
- policy_citations: 引用的政策清单
- risks: 整体风险列表
- candidate_grids: 仅返回聚合轮廓中心点坐标列表 [{lng, lat}]，不含精确网格ID
"""


# ============================================================
# 公开函数
# ============================================================

def build_gene_injection(
    gene: dict,
    recipes: list[dict],
    genes: list[dict],
    indicator_snapshot: dict[str, dict[str, Any]] | None = None,
) -> str:
    """构造完整的 System Prompt 注入文本（本地 Gene + EvoMap 集体智能）。

    该函数合并两个注入源：
      1. 本地进化 Gene（权重 + 偏好 + 历史教训）
      2. EvoMap 社区 intelligence（recipes + genes）

    Args:
        gene: 当前评估基因快照（来自 gene_service.get_latest_gene() 或 DEFAULT_GENE）
        recipes: OAuth2 检索到的 recipe 列表
        genes: OAuth2 检索到的 gene 列表
        indicator_snapshot: 可选的当前网格指标摘要（用于关联具体数据）

    Returns:
        str: 格式化注入文本。gene 为默认值时返回简化版；
             recipes/genes 为空时省略对应段；
             全部为空时返回 ""。
    """
    parts: list[str] = []
    eval_count = gene.get("context", {}).get("evaluation_count", 0)
    prefs = gene.get("preferences", [])
    weights = gene.get("weights", {})

    # ── §1: 评估基因 ──
    if eval_count > 0:
        parts.append(f"## 🌱 评估基因（基于 {eval_count} 次历史经验进化）\n")
        parts.append("**当前评估权重**：")
        parts.append(
            f"- 能落层 {weights.get('nld', 0.4):.2f} / "
            f"应落层 {weights.get('yld', 0.35):.2f} / "
            f"需落层 {weights.get('xld', 0.25):.2f}\n"
        )
    elif eval_count == 0:
        parts.append("## 🌱 评估基因（基线 — 尚未积累本地经验）\n")

    if prefs:
        parts.append("**进化偏好**：")
        for p in prefs:
            effect = p.get("effect", "")
            rule = p.get("rule", "")
            emoji = "🚫" if "×" in effect else "⚙️"
            parts.append(f"- {emoji} {effect}：{rule}")
        parts.append("")

    # ── §2: 历史教训（从偏好规则中提取 source==government_feedback 的）──
    gov_prefs = [p for p in prefs if p.get("source") == "government_feedback"]
    if gov_prefs:
        parts.append("**历史教训**（来自本地经验）：")
        for p in gov_prefs:
            parts.append(f"- {p['rule']}")
        parts.append("")

    # ── §3: EvoMap 集体智能 ──
    if recipes:
        parts.append("## 🌍 EvoMap 集体智能（可复用经验）\n")
        for r in recipes[:5]:
            title = r.get("title", "")
            desc = (r.get("description") or "")[:150]
            parts.append(f"- 《{title}》：{desc}")
        parts.append("")

    if genes:
        added_header = False
        for g in genes[:3]:
            name = g.get("name", g.get("title", ""))
            summary = (g.get("summary") or g.get("description") or "")[:120]
            if name and summary:
                if not added_header:
                    parts.append("**通用能力参考**：")
                    added_header = True
                parts.append(f"- {name}：{summary}")
        if added_header:
            parts.append("")

    # ── §4: 建议 ──
    if prefs:
        rule_texts = [p["rule"] for p in prefs[:3]]
        suggestion = "；".join(rule_texts) + "。"
        parts.append(f"**建议**：结合以上经验，{suggestion}")

    return "\n".join(parts) if parts else ""


def get_system_prompt(role: str) -> str:
    """返回对应角色的 system prompt 完整文本。

    Args:
        role: 用户角色，"government" 或 "enterprise"。

    Returns:
        str: 对应的 system prompt 文本。
    """
    role_lower = role.lower()
    if role_lower in ("government", "gov"):
        return GOVERNMENT_SYSTEM_PROMPT
    elif role_lower in ("enterprise", "enterprise"):
        return ENTERPRISE_SYSTEM_PROMPT
    else:
        # 默认返回政府端
        return GOVERNMENT_SYSTEM_PROMPT


def build_eval_prompt(
    grid_data: list[dict],
    policy_context: dict,
    role: str,
) -> str:
    """构建评估 user prompt。

    将网格聚合数据、政策上下文、用户需求拼接为 Markdown 格式的评估请求。

    Args:
        grid_data: 网格聚合统计列表，每项含 grid_count / total_area_mu / land_types 等。
        policy_context: 政策上下文，含 weights（七维权重）和 policy_refs（政策引用）。
        role: 用户角色。

    Returns:
        str: 拼接后的完整 user prompt。
    """
    parts = []

    # --- 网格概况 ---
    parts.append("## 网格概况")
    if grid_data:
        stats = grid_data[0] if isinstance(grid_data, list) else grid_data
        parts.append(f"- 网格数：{stats.get('grid_count', 0)}")
        parts.append(f"- 总面积：{stats.get('total_area_mu', 0):.1f} 亩")
        lands = stats.get("land_type_distribution", {})
        if lands:
            parts.append("- 用地类型分布：")
            for lt, cnt in lands.items():
                parts.append(f"  - {lt}: {cnt} 格")
    else:
        parts.append("（无网格数据——纯产业咨询模式）")

    # --- 网格指标快照（74字段体系）---
    indicators = stats.get("indicators", {})
    scenario_scores = stats.get("scenario_scores", {})
    if indicators:
        parts.append("\n## 网格指标快照（核心字段）")
        parts.append(f"共 {len(indicators)} 个网格（按综合得分 ZHDF 排序，最多展示 20 个）")
        parts.append("")

        # 按 ZHDF 降序排序，取 top 20
        sorted_indicators = sorted(
            indicators.items(),
            key=lambda kv: kv[1].get("ZHDF", 0) or 0,
            reverse=True,
        )[:20]

        for grid_id, ind in sorted_indicators:
            nld = ind.get("NLD", "?")
            yld = ind.get("YLD", "?")
            zhdf = ind.get("ZHDF", "?")
            znzz = ind.get("ZNZZ", "?")
            wlcc = ind.get("WLCC", "?")
            ylqx = ind.get("YLQX", "?")
            spjg = ind.get("SPJG", "?")
            dlmc = ind.get("DLMC", "未知")
            qssx = ind.get("QSSX", "未知")
            slope = ind.get("SLOPE", "?")
            jtkd = ind.get("JTKD", "?")
            jjd = ind.get("JJD", "?")
            qsxt = ind.get("QSXT", "?")
            mgfx = ind.get("MGFX", "?")
            bestcy = ind.get("BESTCY", "")
            bestsc = ind.get("BESTSC", "")

            parts.append(f"### {grid_id}")
            core = f"能落度 NLD={nld} | 应落度 YLD={yld} | 综合得分 ZHDF={zhdf}"
            parts.append(f"- {core}")
            scene = (
                f"智能制造 ZNZZ={znzz} | 物流仓储 WLCC={wlcc} | "
                f"医疗器械 YLQX={ylqx} | 食品加工 SPJG={spjg}"
            )
            parts.append(f"- {scene}")
            parts.append(f"- 地类: {dlmc} | 权属: {qssx} | 坡度: {slope}")
            parts.append(f"- 交通可达性 JTKD={jtkd} | 产业集聚度 JJD={jjd}")
            parts.append(f"- 权属协调度 QSXT={qsxt} | 敏感设施冲突风险 MGFX={mgfx}")
            if bestcy:
                parts.append(f"- 最推荐产业: {bestcy} (得分 {bestsc})")
            parts.append("")

    if scenario_scores:
        parts.append("## 场景适配排名")
        for scenario, entries in scenario_scores.items():
            if entries:
                top3 = entries[:3]
                line = " | ".join(
                    f"{e['grid_id']}({e['score']})" for e in top3
                )
                parts.append(f"- {scenario}: {line}")

    # --- 政策环境 ---
    parts.append("\n## 政策环境")
    weights = policy_context.get("weights", {})
    if weights:
        parts.append("### 七维评估权重")
        for dim, w in weights.items():
            parts.append(f"- {dim}: {w}")

    refs = policy_context.get("policy_refs", [])
    if refs:
        parts.append("### 相关产业政策")
        for ref in refs:
            parts.append(f"- {ref}")

    pref = policy_context.get("industry_preference", "")
    if pref:
        parts.append(f"\n该产业在中国东南某县的供地偏好级别：**{pref}**")

    # --- 用户需求 ---
    parts.append("\n## 用户需求")
    user_msg = policy_context.get("user_message", "")
    parts.append(user_msg if user_msg else "请基于以上数据给出产业用地评估建议。")

    # --- 强制输出格式要求 ---
    parts.append("\n## 输出要求")
    parts.append(
        "请严格按 JSON 格式返回，字段为：summary, items（数组，每项含 rank/industry/"
        "score/reason/policy_refs/risk）, policy_citations, risks, candidate_grids。"
    )
    if role.lower() in ("enterprise", "enterprise"):
        parts.append(
            "企业端：candidate_grids 仅返回聚合轮廓中心点坐标列表 [{lng, lat}]，"
            "不含网格ID和精确坐标。"
        )

    return "\n".join(parts)
