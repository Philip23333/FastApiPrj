"""分页参数标准化工具。"""


def normalize_pagination(page: int, size: int, *, max_size: int = 50) -> tuple[int, int, int]:
    """规范化分页参数，返回 (safe_page, safe_size, offset)。"""
    safe_page = max(1, page)
    safe_size = max(1, min(size, max_size))
    offset = (safe_page - 1) * safe_size
    return safe_page, safe_size, offset
