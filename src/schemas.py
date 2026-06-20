"""
Pydantic 数据模型定义。

定义系统中所有 API 请求/响应的数据结构，以及领域核心实体。
字段类型严格遵守 api.md，命名与架构文档一致。
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


# ============================================================
# 通用
# ============================================================

class Role(str, Enum):
    """用户角色枚举。"""
    GOVERNMENT = "government"
    ENTERPRISE = "enterprise"


class ErrorResponse(BaseModel):
    """统一错误响应格式。

    Args:
        code: 错误码（如 MAP_QUERY_INVALID_BBOX）
        message: 人类可读的错误描述
        detail: 可选的详细错误信息
    """
    code: str = Field(..., description="错误码")
    message: str = Field(..., description="错误描述")
    detail: Optional[str] = Field(None, description="详细错误信息")


# ============================================================
# 渔网相关
# ============================================================

class GridCell(BaseModel):
    """单个渔网单元。

    包含用地属性、权属、几何等完整字段。
    字段对应 land_grid 表的查询投影。

    Args:
        grid_id: 网格唯一标识，格式 grid_{row}_{col}
        land_type: 主导用地类型名称（DLMC，46 类之一）
        land_code: 地类编码（DLBM），用于指标计算/分组
        area_sqm: 网格面积（平方米），100m 网格即 10000 m²
        ownership: 权属：国有 / 集体
        township: 所属乡镇/街道（14 个之一）
        mixed_type: 混合用地标注，纯用地为 None
        extras: 扩展字段（JSON 对象），存储行业评分、政策标签等
        geom_wgs84: WGS84 坐标系下的 Polygon 几何（GeoJSON 坐标数组）
    """
    grid_id: str = Field(..., description="网格唯一标识")
    land_type: str = Field(..., description="主导用地类型名称")
    land_code: str = Field(..., description="地类编码")
    area_sqm: float = Field(..., description="网格面积（平方米）")
    ownership: str = Field(..., description="权属：国有/集体")
    township: str = Field(..., description="所属乡镇/街道")
    mixed_type: Optional[str] = Field(None, description="混合用地标注")
    extras: dict[str, Any] = Field(default_factory=dict, description="扩展字段")
    geom_wgs84: Any = Field(None, description="WGS84 Polygon 几何（GeoJSON 坐标数组）")


class GridSelectRequest(BaseModel):
    """框选查询请求。

    Args:
        bbox: WGS84 边界框 "lng1,lat1,lng2,lat2"，与 polygon 二选一
        polygon: GeoJSON Polygon 坐标数组，与 bbox 二选一
    """
    bbox: Optional[str] = Field(None, description="WGS84 边界框字符串")
    polygon: Optional[list[list[list[float]]]] = Field(
        None, description="GeoJSON Polygon 坐标"
    )


class GridSelectResponse(BaseModel):
    """框选查询响应。

    Args:
        cells: 匹配的渔网单元列表
        total_count: 总匹配数
        total_area: 总面积（平方米）
    """
    cells: list[GridCell] = Field(default_factory=list)
    total_count: int = Field(..., description="总匹配数")
    total_area: float = Field(..., description="总面积（平方米）")


class NineGridRequest(BaseModel):
    """九宫格查询请求。

    Args:
        lng: 鼠标所在经度（WGS84）
        lat: 鼠标所在纬度（WGS84）
    """
    lng: float = Field(..., description="鼠标经度")
    lat: float = Field(..., description="鼠标纬度")


class NineGridResponse(BaseModel):
    """九宫格查询响应。

    Args:
        cells: 中心格 + 周围 8 格（共 ≤9 个），首个为中心格
    """
    cells: list[GridCell] = Field(default_factory=list, description="九宫格单元列表")


# ============================================================
# 评估相关
# ============================================================

class EvaluationRequest(BaseModel):
    """地块评估请求。

    Args:
        grid_ids: 待评估的渔网 grid_id 列表
        intent: 可选的用户意图描述（如"寻找工业用地"）
    """
    grid_ids: list[str] = Field(..., min_length=1, description="待评估网格 ID 列表")
    intent: Optional[str] = Field(None, description="用户意图描述")


class EvaluationResponse(BaseModel):
    """地块评估结果。

    Args:
        summary: 评估总体摘要
        scores: 各推荐产业 → 评分映射
        recommendations: 推荐产业清单（含理由）
        policy_refs: 引用的政策清单
    """
    summary: str = Field(..., description="评估总体摘要")
    scores: dict[str, float] = Field(default_factory=dict, description="产业评分")
    recommendations: list[str] = Field(default_factory=list, description="推荐产业清单")
    policy_refs: list[str] = Field(default_factory=list, description="政策引用清单")


# ============================================================
# 对话相关
# ============================================================

class ChatMessage(BaseModel):
    """单条对话消息。

    Args:
        role: 发送者角色 user / assistant
        content: 消息文本内容
    """
    role: str = Field(..., description="发送者角色", pattern="^(user|assistant)$")
    content: str = Field(..., description="消息内容")


class ChatRequest(BaseModel):
    """对话请求（API /agent/chat 入参）。

    Args:
        message: 用户输入（≤500 字符）
        role: 用户角色 "government" 或 "enterprise"
        bbox: 可选的框选范围 "lng1,lat1,lng2,lat2"
        context: 可选的对话历史，每项含 role/content
    """
    message: str = Field(..., min_length=1, max_length=500, description="用户输入")
    role: str = Field(..., description="用户角色")
    bbox: Optional[str] = Field(None, description="框选范围")
    context: Optional[list[dict[str, str]]] = Field(None, description="对话历史")


class ChatResponse(BaseModel):
    """对话响应。

    Args:
        reply: Agent 回复文本
        structured_result: 可选的结构化评估结果
    """
    reply: str = Field(..., description="Agent 回复文本")
    structured_result: Optional[EvaluationResponse] = Field(
        None, description="结构化评估结果"
    )


# ============================================================
# 企业相关（保留接口，企业端 P3 可砍但 schema 不删）
# ============================================================

class Enterprise(BaseModel):
    """企业画像。

    Args:
        id: 企业唯一 ID
        name: 企业名称
        industry: 所属行业
        industry_code: 行业代码
        employee_count: 员工数量
        annual_revenue: 年营收（万元）
        space_demand: 用地面积需求（亩）
        requirements: 配套设施要求列表
        priority_tags: 优先级标签列表
    """
    id: int = Field(..., description="企业唯一 ID")
    name: str = Field(..., description="企业名称")
    industry: str = Field(..., description="所属行业")
    industry_code: Optional[str] = Field(None, description="行业代码")
    employee_count: Optional[int] = Field(None, description="员工数量")
    annual_revenue: Optional[float] = Field(None, description="年营收（万元）")
    space_demand: Optional[float] = Field(None, description="用地面积需求（亩）")
    requirements: list[str] = Field(default_factory=list, description="配套设施要求")
    priority_tags: list[str] = Field(default_factory=list, description="优先级标签")


class EnterpriseMatchRequest(BaseModel):
    """政府端多企业匹配请求。

    Args:
        enterprise_ids: 选中的企业 ID 列表
        bbox: 可选，当前地图视口 bbox "lng1,lat1,lng2,lat2"，不传则用全县范围
    """
    enterprise_ids: list[str] = Field(..., min_length=1, description="企业 ID 列表")
    bbox: str | None = None


class EnterpriseMatchResponse(BaseModel):
    """企业匹配结果。

    Args:
        matches: 各企业的匹配结果列表
        summary: 匹配总体摘要
    """
    matches: list[dict[str, Any]] = Field(default_factory=list, description="匹配结果")
    summary: str = Field("", description="匹配总体摘要")


# ============================================================
# 自进化展示相关
# ============================================================

class EvolutionStats(BaseModel):
    """自进化统计数据。

    从前端自进化展示面板查询，基于 evaluations 和 evomap_capsules 表聚合计算。

    Args:
        experience_count: 评估记录总数（自进化经验累计数）
        preference_understanding: 偏好理解度 0-100（v1.0 模拟计算值）
        methodology_count: 方法论条目数
        capsule_contributed: 已发布的 Capsule 数量
        radar: 五维能力雷达图数据 {维度名: 评分 0-100}
    """
    experience_count: int = Field(..., description="评估记录总数")
    preference_understanding: float = Field(..., description="偏好理解度 0-100")
    methodology_count: int = Field(..., description="方法论条目数")
    capsule_contributed: int = Field(..., description="已发布 Capsule 数")
    radar: dict[str, float] = Field(default_factory=dict, description="五维能力雷达")


# ============================================================
# API 路由专用模型（对齐 api.md）
# ============================================================

class GridFeature(BaseModel):
    """渔网单元 GeoJSON Feature 属性（API 返回用）。

    v1.1 新增：min_lng/min_lat/max_lng/max_lat（九宫格定位）、
    level/land_type_top3/grid_count_original（聚合表字段）。

    Args:
        grid_id: 网格唯一标识
        level: 金字塔层级 0-5（L0=0, L1=1, ...）
        min_lng/min_lat/max_lng/max_lat: WGS84 bbox
        land_type: 主导用地类型名称
        land_type_top3: 占比前三地类 JSON（L0 返回 "[]"）
        area_sqm: 网格面积（平方米）
        ownership: 权属（企业端返回 None）
        town: 所属乡镇/街道
        mixed_type: 混合用地标注
        nl_mean: 夜间灯光均值
        ndvi_mean: NDVI 均值
        pm25_mean: PM2.5 均值
        grid_count_original: 被合并的 100m 原始网格数
    """
    grid_id: str
    level: int = 0
    min_lng: float = 0.0
    min_lat: float = 0.0
    max_lng: float = 0.0
    max_lat: float = 0.0
    land_type: str
    land_type_top3: str = "[]"
    area_sqm: float = 10000.0
    ownership: Optional[str] = None
    town: str = ""
    mixed_type: Optional[str] = None
    nl_mean: Optional[float] = None
    ndvi_mean: Optional[float] = None
    pm25_mean: Optional[float] = None
    grid_count_original: int = 1


class GridDetailResponse(BaseModel):
    """单网格详情（仅政府端，API /grid/{grid_id} 返回）。

    Args:
        grid_id: 网格唯一标识
        land_type: 主导用地类型名称
        area_mu: 面积（亩）
        ownership: 权属
        town: 所属乡镇/街道
        mixed_type: 混合用地标注
        nl_mean: 夜间灯光均值
        ndvi_mean: NDVI 均值
        pm25_mean: PM2.5 均值
    """
    grid_id: str
    land_type: str
    area_mu: float
    ownership: str
    town: str
    mixed_type: Optional[str] = None
    nl_mean: Optional[float] = None
    ndvi_mean: Optional[float] = None
    pm25_mean: Optional[float] = None


class MapQueryResponse(BaseModel):
    """框选查询响应（API /map/query 返回）。

    Args:
        grid_count: 匹配网格数
        total_area_mu: 总面积（亩）
        land_types: 涉及用地类型列表
        features: 网格属性列表
        geojson: GeoJSON FeatureCollection
        truncated: 是否因超限被截断
    """
    grid_count: int
    total_area_mu: float
    land_types: list[str]
    features: list[GridFeature]
    geojson: dict[str, Any] = Field(default_factory=dict)
    truncated: bool = False


class EvalSummary(BaseModel):
    """评估摘要（API 返回用）—— 未使用，历史遗留，勿删。

    Args:
        grid_count: 涉及网格数
        total_area_mu: 总面积（亩）
        land_types: 用地类型列表
    """
    grid_count: int
    total_area_mu: float
    land_types: list[str] = Field(default_factory=list)


class EvalItem(BaseModel):
    """单条评估结果（API 返回用）。

    Args:
        rank: 排名
        industry: 推荐产业
        score: 评分 1-10
        reason: 推荐理由
        policy_refs: 政策依据列表
        risk: 风险提示
    """
    rank: int
    industry: str
    score: float
    reason: str
    policy_refs: list[str] = Field(default_factory=list)
    risk: Optional[str] = None


class AgentReply(BaseModel):
    """Agent 完整回复（API /agent/chat 返回）。

    Args:
        summary: 评估摘要
        items: 推荐产业列表（按评分降序）
        policy_citations: 政策引用清单
        risks: 风险列表
        candidate_grids: 推荐涉及的网格 ID 列表（前端地图高亮用）
    """
    summary: str = Field(default="", description="评估总体摘要")
    items: list[EvalItem] = Field(default_factory=list)
    policy_citations: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    candidate_grids: list = Field(default_factory=list)


class EnterpriseMatchResult(BaseModel):
    """单企业匹配结果（API 返回用）。

    Args:
        enterprise_id: 企业 ID
        enterprise_name: 企业名称
        candidates: 候选地块列表
    """
    enterprise_id: str
    enterprise_name: str
    candidates: list[dict[str, Any]] = Field(default_factory=list)


class EvoStatusResponse(BaseModel):
    """EvoMap 自进化展示数据（API /evomap/status 返回）。

    Args:
        online: EvoMap Hub 心跳是否正常
        node_id: EvoMap 节点 ID
        credit_balance: 信用积分余额
        capsules_published: 已发布 Capsule 数
        evolution_count: 评估记录总数
        preference_understanding: 偏好理解度 0-100
        radar_values: 五维能力雷达图数据
    """
    online: bool = False
    node_id: Optional[str] = None
    credit_balance: Optional[int] = None
    capsules_published: int = 0
    evolution_count: int = 0
    preference_understanding: float = 0.0
    radar_values: dict[str, float] = Field(default_factory=dict)


# ============================================================
# P1-2 企业匹配增强
# ============================================================

class GridsGeometryRequest(BaseModel):
    """批量查询渔网格几何的请求。"""
    grid_ids: list[str] = Field(..., min_length=1, max_length=200, description="网格 ID 列表")
    role: str = "government"
