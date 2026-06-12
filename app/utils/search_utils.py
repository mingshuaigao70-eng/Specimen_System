"""
统一标本搜索工具。

供以下路由使用:
- main.search       (全局搜索)
- main.specimen_list (分类页搜索)
- admin.manage_specimens (配置平台搜索)
"""
from ..models import Specimen
from ..extensions import db

# 可用于关键词搜索的字段（分类学字段 + 别名）
KEYWORD_SEARCH_FIELDS = [
    'chinese_name',
    'latin_name',
    'alias',
    'phylum',
    'class_name',
    'order_name',
    'family',
    'genus',
    'species',
]


def build_specimen_search_filter(search_text):
    """
    构建标本搜索的 SQLAlchemy filter 表达式。

    规则:
        1. 空字符串 / 纯空白 → 返回 None
        2. 长度 < 2 字符 → 返回 None（拒绝单字符如 "1"、"A"）
        3. 标本编号: ILIKE 完整查询字符串（不拆分），受最小长度保护
        4. 关键词字段（9 个分类学字段）:
           空格分隔 → 各 token 在 9 个字段中 OR 匹配 → token 间 AND
        5. 最终条件: specimen_number 匹配 OR 关键词匹配
        6. 已移除字段: collector, collect_location, appraiser

    Returns:
        SQLAlchemy filter 表达式，或 None（调用方应处理 flash/redirect）
    """
    q = search_text.strip()
    if not q or len(q) < 2:
        return None

    # --- 标本编号：完整查询字符串匹配 ---
    specimen_cond = Specimen.specimen_number.ilike(f'%{q}%')

    # --- 关键词字段：token 化 AND 搜索 ---
    tokens = q.split()
    token_conds = []
    for token in tokens:
        ors = [getattr(Specimen, fn).ilike(f'%{token}%') for fn in KEYWORD_SEARCH_FIELDS]
        token_conds.append(db.or_(*ors))

    if len(token_conds) > 1:
        kw_filter = db.and_(*token_conds)
    else:
        kw_filter = token_conds[0]

    return db.or_(specimen_cond, kw_filter)
