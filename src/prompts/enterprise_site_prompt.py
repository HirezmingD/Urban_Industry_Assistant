"""
企业择地匹配 Prompt 模板。

被 match_enterprise_sites() 专用，不与 system_prompt.py 互引用。
"""
from __future__ import annotations

from typing import Any

# ============================================================
# v2.4: 企业择地 System Prompt
# ============================================================

_ENTERPRISE_SITE_SYSTEM_PROMPT = """\
## 角色
你是城市产业空间规划专家，当前任务是：为已选定的企业匹配最适合落位的具体地块。
你不是产业推荐师——用户已选定企业，你只负责说明"这家企业为什么适合落在这个网格"。

## 核心规则
1. 为每家企业从候选网格中确认最佳匹配，给出匹配理由（≤80 字）
2. 每条理由说明具体的匹配依据：
   - 产业适配：企业行业与该网格土地类型的契合度
   - 面积适配：企业用地需求与网格可用面积的匹配情况
   - 区位特征：交通、园区、配套设施等空间优势
3. 如果多企业竞争同一网格，给出优先级建议
4. **严格禁止**输出：
   - "推荐发展XX产业"——用户已选定企业
   - "该区域适合发展XX"——你不需要推荐产业方向
   - "建议优先布局XX方向"——布局方向已在多维匹配中计算完毕
   - items 数组——这个回复中不包含产业推荐列表
5. 用中文回复

## 输出格式
{
  "summary": "为 N 家企业匹配到 M 个候选地块的总体说明",
  "enterprise_matches": [
    {
      "enterprise_id": "...",
      "candidates": [
        {"grid_id": "...", "reason": "该网格以工业用地为主，与XX企业的精密制造需求高度契合，距高速出口 1.2km"}
      ]
    }
  ],
  "conflicts": [
    {"grid_id": "...", "suggestion": "建议优先满足XX企业（工业用地刚性需求更强）"}
  ]
}
"""


def build_enterprise_site_prompt(
    enterprise_matches: list[dict[str, Any]],
    conflicts: list[dict[str, Any]],
) -> str:
    """构造企业择地匹配 user_prompt。

    Args:
        enterprise_matches: 多维匹配计算后的候选结果（含评分，无理由）
        conflicts: 冲突网格列表

    Returns:
        str: 完整的 user_prompt 文本
    """
    lines = [f"为以下 {len(enterprise_matches)} 家企业匹配最适合的落位地块：\n"]

    for em in enterprise_matches:
        lines.append(f"## {em['enterprise_name']}（{em.get('industry', '未知行业')}）")
        lines.append(f"面积需求：{em['total_area_mu']} 亩")
        lines.append("候选网格：")
        for i, c in enumerate(em["candidates"], 1):
            lines.append(
                f"  {i}. grid_id={c['grid_id']} "
                f"({c['lng']}, {c['lat']}) "
                f"| 综合 {c['score']} 分 "
                f"| 面积 {round(c.get('area_match', 0)*100)}% "
                f"产业 {round(c.get('industry_match', 0)*100)}% "
                f"设施 {round(c.get('facility_match', 0)*100)}%"
            )
        lines.append("")

    if conflicts:
        lines.append("## 网格冲突提示")
        lines.append("以下网格被多家企业选中：")
        for cf in conflicts:
            names = "、".join(cf.get("enterprise_names", []))
            lines.append(f"- {cf['grid_id']}：{names} 竞争此网格")
        lines.append("")

    lines.append("请为以上每家企业生成匹配理由（每条 ≤80 字），构造 JSON 回复。")
    return "\n".join(lines)
