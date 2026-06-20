"""
EvoMap 服务门面（批次 D 拆分：原 evo_service.py 拆为 evo_client + evo_stats）。

保持向后兼容，外部 import 路径不变。
"""
from .evo_client import EvomapClient, evo_client  # noqa: F401
from .evo_stats import get_evolution_stats  # noqa: F401
from .oauth_client import EvoMapOAuthClient, oauth_client  # noqa: F401
from .gene_service import (  # noqa: F401
    get_latest_gene,
    save_gene_snapshot,
    compare_genes,
    apply_feedback,
    get_gene_history,
)
