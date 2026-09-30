"""可重複給且可逗號分隔的 CLI 參數展開。"""

from typing import Any


def expand_list_arg(raw: Any) -> list[str]:
    """展開可重複且可逗號分隔的 CLI 參數：去空白、去空項、保序去重。

    接受 None、單一字串（舊寫法）或 append 產生的字串清單。
    """
    if not raw:
        return []
    chunks = [raw] if isinstance(raw, str) else list(raw)
    result: list[str] = []
    for chunk in chunks:
        for item in chunk.split(","):
            item = item.strip()
            if item and item not in result:
                result.append(item)
    return result
