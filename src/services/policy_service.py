"""
政策匹配服务。

提供七维评估权重计算、政策引用匹配、中国东南某县产业供地偏好查询。
所有政策数据硬编码为 Python dict，方便后续修改，不引入外部依赖。

数据来源：tonglu_policy_research.md（四级政策体系：国家→省→市→县）。
"""
from __future__ import annotations

# ============================================================
# 七维评估权重（静态基线，后续可根据 land_type/town/industry 微调）
# ============================================================

# TODO[BatchD]: 根据 land_type/town/industry 动态微调权重
#   例如：位于主要河流山健康城 → 环境约束权重 +0.05
#        位于中国东南某县经济开发区 → 基础设施权重 +0.05
#        产业为高碳排 → 环境约束权重 +0.10

BASE_WEIGHTS: dict[str, float] = {
    "用地合规性": 0.15,
    "新质生产力适配": 0.10,
    "产业适配度": 0.25,
    "经济效益（亩均）": 0.15,
    "环境约束（碳+生态）": 0.20,
    "基础设施配套": 0.05,
    "政策红利": 0.10,
}
"""七维评估权重（静态基线，基于 tonglu_policy_research.md §七）。"""

# ============================================================
# 政策引用库（核心 10+ 条，覆盖四级体系）
# ============================================================

POLICY_LIBRARY: dict[str, str] = {
    # --- 国家层 ---
    "national_15_5": "国家十五五规划纲要（2026-2030）：发展新质生产力，优先保障战略性新兴产业用地",
    "national_stock_priority": "国家十五五规划纲要：严控新增建设用地规模，优先盘活存量低效用地",
    "national_carbon_dual": "国家十五五规划纲要：全面绿色转型，碳双控（总量+强度），高碳排放新增用地受限",
    "national_county_urban": "国家十五五规划纲要：以县城为重要载体的新型城镇化",
    # --- 浙江省层 ---
    "zhejiang_15_5": "浙江省十五五规划纲要：全球先进制造业基地 + 共同富裕示范区 + 大花园",
    "zhejiang_516x": "浙江省516X先进制造业集群体系：智能装备、生物医药等为核心赛道",
    "zhejiang_mu_jun": "浙江省亩均论英雄：D类企业2年出清，亩均税收低于全县均值1/3则强烈建议盘活",
    "zhejiang_standard_land_3": "浙江省标准地改革3.0：出让须满足固投强度+亩均税收+容积率+碳效共5项指标",
    "zhejiang_mountain_26": "浙江省山区26县高质量发展政策2.0：产业飞地、科创飞地、省级资金配套",
    "zhejiang_digital_2": "浙江省数字经济'一号工程'2.0：向县域延伸，智慧物流SaaS等业态",
    # --- 省会城市层 ---
    "hangzhou_15_5": "省会城市十五五规划纲要：中国东南某县为省会都市圈西部生态经济核心区",
    "hangzhou_lifecycle": "省会城市工业用地全生命周期管理：标准地+亩均评价+达产复核+退出机制四位一体",
    "hangzhou_low_efficiency": "省会城市低效用地再开发专项行动方案：十五五目标较十四五翻倍",
    "hangzhou_m0": "省会城市M0新型产业用地管理办法：核心区位可申请，容积率2.0-4.0，配套比例≤30%",
    "hangzhou_iot": "省会城市智能物联产业生态圈建设方案：向中国东南某县延伸，快递物流智能装备为核心组件",
    # --- 中国东南某县层 ---
    "tonglu_industrial_baseline": "中国东南某县工业用地最低出让价：十一等 10.2万元/亩（国家规定最低价）",
    "tonglu_preference_logistics": "中国东南某县供地偏好：快递物流装备——优先供地（最具识别度的产业标签）",
    "tonglu_preference_health": "中国东南某县供地偏好：大健康（医疗器械/生物制造）——优先供地（主要河流山健康城专项指标）",
}
"""政策引用库，key 用于内部匹配，value 为完整引用语句。"""

# ============================================================
# 中国东南某县产业供地偏好矩阵
# ============================================================

TONGLU_INDUSTRY_PREFERENCE: dict[str, str] = {
    "快递物流装备": "优先供地",
    "智能物流装备": "优先供地",
    "物流无人机": "优先供地",
    "智慧物流": "优先供地",
    "现代物流": "优先供地",
    "大健康": "优先供地",
    "医疗器械": "优先供地",
    "生物制造": "优先供地",
    "康养": "优先供地",
    "精密制造": "优先供地",
    "智能制造": "优先供地",
    "快递物流数据服务": "优先供地",
    "数字经济": "正常供地",
    "智能装备": "正常供地",
    "新能源": "正常供地",
    "文旅康养": "正常供地",
    "食品加工": "正常供地",
    "电商直播": "正常供地",
    "数据标注": "正常供地",
    "智慧物流SaaS": "正常供地",
    "传统服装": "限制新供地",
    "针织服装": "限制新供地",
    "轻工制造": "限制新供地",
    "制笔文具": "限制新供地",
    "高碳排化工": "禁止新供地",
    "高排放制造": "禁止新供地",
}
"""中国东南某县各产业供地偏好矩阵（基于 tonglu_policy_research.md §五 供地偏好矩阵）。"""

# ============================================================
# 产业→政策映射（用于 get_policy_refs 命中）
# ============================================================

# 产业关键词 → 应返回的政策 key 列表
_INDUSTRY_POLICY_MAP: dict[str, list[str]] = {
    # 快递物流装备
    "物流": [
        "national_15_5", "zhejiang_15_5", "zhejiang_516x",
        "hangzhou_15_5", "hangzhou_iot", "tonglu_preference_logistics",
    ],
    "快递": [
        "national_15_5", "zhejiang_15_5", "zhejiang_516x",
        "hangzhou_15_5", "hangzhou_iot", "tonglu_preference_logistics",
    ],
    # 大健康
    "大健康": [
        "national_15_5", "zhejiang_15_5", "zhejiang_516x",
        "hangzhou_15_5", "tonglu_preference_health",
    ],
    "医疗": [
        "national_15_5", "zhejiang_15_5", "zhejiang_516x",
        "hangzhou_15_5", "tonglu_preference_health",
    ],
    "生物": [
        "national_15_5", "zhejiang_15_5", "zhejiang_516x",
        "hangzhou_15_5", "tonglu_preference_health",
    ],
    "康养": [
        "national_15_5", "national_county_urban", "zhejiang_15_5",
        "hangzhou_15_5",
    ],
    # 智能制造
    "智能": [
        "national_15_5", "zhejiang_15_5", "zhejiang_516x",
        "hangzhou_15_5", "hangzhou_low_efficiency", "hangzhou_m0",
    ],
    "制造": [
        "national_15_5", "zhejiang_15_5", "zhejiang_516x",
        "zhejiang_mu_jun", "zhejiang_standard_land_3",
    ],
    "精密": [
        "national_15_5", "zhejiang_15_5", "zhejiang_516x",
        "hangzhou_15_5", "zhejiang_standard_land_3",
    ],
    # 数字经济
    "数字": [
        "national_15_5", "zhejiang_15_5", "zhejiang_digital_2",
        "hangzhou_15_5", "hangzhou_m0",
    ],
    "数据": [
        "national_15_5", "zhejiang_digital_2", "hangzhou_m0",
    ],
    "电商": [
        "national_15_5", "zhejiang_digital_2", "hangzhou_m0",
    ],
    # 新能源/绿色
    "新能源": [
        "national_carbon_dual", "zhejiang_15_5", "hangzhou_15_5",
    ],
    "绿色": [
        "national_carbon_dual", "zhejiang_15_5",
    ],
    # 通用（始终引用）
    "_default": [
        "national_15_5", "national_stock_priority", "national_carbon_dual",
        "zhejiang_mu_jun", "zhejiang_standard_land_3",
        "hangzhou_lifecycle", "tonglu_industrial_baseline",
    ],
}


# ============================================================
# 公开函数
# ============================================================

def calculate_weights(
    land_type: str,
    town: str,
    industry: str,
) -> dict[str, float]:
    """计算七维评估权重。

    当前返回静态基线权重。
    TODO[BatchD]: 根据 land_type/town/industry 动态微调。
      例如：生态敏感区 → 环境约束权重 +0.05；开发区 → 基础设施权重 +0.03。

    Args:
        land_type: 用地类型（如"工业用地"）。
        town: 所属乡镇（如"街道一"）。
        industry: 推荐产业（如"精密制造"）。

    Returns:
        dict[str, float]: 七维权重，键为中文维度名。
    """
    return dict(BASE_WEIGHTS)


def get_policy_refs(
    industry: str,
    land_type: str,
    town: str,
) -> list[str]:
    """获取与该产业+地块+区位匹配的政策引用列表。

    基于产业关键词匹配 POLICY_LIBRARY，返回 policy key 列表。
    前端用 key 渲染完整引用语句。

    Args:
        industry: 推荐产业名称。
        land_type: 用地类型。
        town: 所属乡镇。

    Returns:
        list[str]: 匹配的政策 key 列表。
    """
    matched_keys: set[str] = set()

    # 1. 产业关键词匹配
    for keyword, keys in _INDUSTRY_POLICY_MAP.items():
        if keyword == "_default":
            continue
        if keyword in industry:
            matched_keys.update(keys)

    # 2. 通用底线政策（始终引用）
    matched_keys.update(_INDUSTRY_POLICY_MAP.get("_default", []))

    # 3. 用地类型特殊规则
    # TODO[BatchD]: 根据 land_type 细化（如"水田"→强调农地保护、"低效工业"→强调盘活）
    _ = land_type  # 当前未使用，留待后续批次

    # 4. 乡镇特殊规则
    # TODO[BatchD]: 根据 town 细化（如"城镇一"→强调健康城特殊政策）
    _ = town  # 当前未使用，留待后续批次

    return sorted(matched_keys)


def get_tonglu_industry_preference(industry: str) -> str:
    """返回中国东南某县对该产业的供地偏好级别。

    优先精确匹配，否则模糊匹配，未命中返回"未知"。

    Args:
        industry: 产业名称（如"精密制造"）。

    Returns:
        str: 优先供地 | 正常供地 | 限制新供地 | 禁止新供地 | 未知
    """
    # 1. 精确匹配
    if industry in TONGLU_INDUSTRY_PREFERENCE:
        return TONGLU_INDUSTRY_PREFERENCE[industry]

    # 2. 模糊匹配：检查产业名是否包含关键词
    for key, pref in TONGLU_INDUSTRY_PREFERENCE.items():
        if key in industry or industry in key:
            return pref

    return "未知"
