"""
5W1H Checker - 5W1H 欄位完整性檢查

檢查 Ticket frontmatter 的 5W1H 欄位是否仍有「待定義」。
"""

from typing import List


def check_5w1h_completeness(frontmatter: dict, logger) -> List[str]:
    """
    檢查 5W1H 欄位是否仍有「待定義」。

    Args:
        frontmatter: Ticket frontmatter 結構
        logger: 日誌物件

    Returns:
        List[str] - 仍為待定義的欄位名稱列表（空表示全部已填）
    """
    incomplete = []
    fields_to_check = {
        'who': frontmatter.get('who', {}),
        'what': frontmatter.get('what', ''),
        'when': frontmatter.get('when', ''),
        'where': frontmatter.get('where', {}),
        'why': frontmatter.get('why', ''),
        'how': frontmatter.get('how', {}),
    }

    for field_name, value in fields_to_check.items():
        if _is_undefined(value):
            incomplete.append(field_name)

    if incomplete:
        logger.info(f"5W1H 未完成欄位: {incomplete}")
    else:
        logger.info("5W1H 全部已填寫")

    return incomplete


def _is_undefined(value) -> bool:
    """判斷欄位值是否為「待定義」狀態"""
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() in ('', '待定義', 'pending')
    if isinstance(value, dict):
        # who 欄位是 dict，檢查 current 子欄位
        if 'current' in value:
            return _is_undefined(value['current'])
        # where 欄位是 dict，檢查 files 子欄位
        if 'files' in value:
            files = value.get('files', [])
            return not files or all(_is_undefined(f) for f in files)
        # how 欄位是 dict，檢查 strategy 子欄位
        if 'strategy' in value:
            return _is_undefined(value['strategy'])
        # 其他 dict 情況：檢查是否所有值都待定義
        if not value:
            return True
        return all(_is_undefined(v) for v in value.values())
    if isinstance(value, list):
        return len(value) == 0
    return False
