"""機器專屬絕對路徑偵測模組

建票與認領時掃描 ticket 欄位與內文中形如 `/Users/<name>/`、`/home/<name>/`、
`C:\\Users\\<name>\\` 的路徑，命中即輸出警告（不阻擋）。

動機：ticket 以機器專屬絕對路徑記錄實測得到的環境事實，換機（換帳號、換
裝置、換容器）後這些路徑全數解析不到，而失效訊息 `No such file or
directory` 只說路徑不存在，不會說「這是在另一台機器上量的」。接手者讀到
的是一份看似完整、實則前提已消失的操作指示，最省力的解釋是自己打錯路徑，
不是懷疑 ticket——失效因此不自我揭示，只能靠事後人工全量盤點才被發現。

定位為輕量提示而非阻擋（比照 `spec_reference_checker` 與
`acceptance_auditor.detect_srp_violations`）：絕對路徑在少數情境是正當的
（例如逐字引用他人輸出、記錄一次實測的量測值），阻擋會讓這些正當用途無法
寫入；而提示的成本只是一行輸出。

通用佔位符不誤報是本模組的關鍵設計約束：說明文件與規則條文大量使用
`/Users/me`、`/Users/<user>` 這類示例路徑，若逐一觸發警告，該警告會在幾次
建票內被當成雜訊忽略，真正的殘留也跟著被略過。
"""
# 防止直接執行此模組
if __name__ == "__main__":
    from .messages import print_not_executable_and_exit
    print_not_executable_and_exit()


import re
from pathlib import Path
from typing import Any, Dict, List

# 使用者名稱片段：允許英數與 . _ -，但頭尾必須是英數或底線。
#
# 尾端限制的理由：散文中路徑常以 ASCII 句點收尾（`見 /Users/alice.`）。若
# 句點被吃進使用者名，`_is_generic` 取到的是 `me.` 而非 `me`，佔位符白名單
# 直接失效——示例路徑因此誤報，正好打在本模組宣告的關鍵設計約束上。同一
# 機器的 `/Users/alice` 與 `/Users/alice.` 也會去重失敗而列成兩筆。
# 排除尾端 `-` 的理由同構：`/Users/me-<name>` 會取到 `me-` 而繞過白名單。
#
# 副作用（刻意）：`<user>` / `{user}` / `...` 這類角括號、大括號、純句點的
# 佔位形態不含合法起始字元，因此完全不匹配，不需列入白名單——白名單只處理
# 「長得像真實帳號名的代稱」（me / user / dev 等）。
_USER_SEGMENT = r"[A-Za-z0-9_][A-Za-z0-9._-]*[A-Za-z0-9_]|[A-Za-z0-9_]"

# 左界斷言：`/Users` 與 `/home` 須為路徑起點，否則 `x/home/bob/y` 這種
# 相對路徑片段會被誤判為家目錄。
_LEFT_BOUNDARY = r"(?<![A-Za-z0-9._-])"

# POSIX 家目錄前綴（macOS /Users、Linux /home）。
#
# 不要求名稱後緊接分隔符：記錄環境事實最常見的寫法是散文中的裸家目錄
# （「實測在 HOME 為 /Users/alice 的環境完成」），使用者名後面接的是空格或
# 標點。早期版本以 `(?=/)` lookahead 排除「路徑格式為 /Users/ 開頭」這種
# 無使用者名的敘述，卻連帶漏掉上述主要形態——實地認領一張含該形態的 ticket
# 時警告未觸發，才暴露這個結構性漏洞。
#
# 無使用者名的敘述改由 `_USER_SEGMENT` 的「至少一字元」本身排除：`/Users/`
# 後接空格時該片段長度為 0，自然不匹配。
_POSIX_RE = re.compile(rf"{_LEFT_BOUNDARY}(/(?:Users|home)/(?:{_USER_SEGMENT}))")

# Windows 家目錄前綴。單一反斜線分隔，同上不要求尾隨分隔符。
_WINDOWS_RE = re.compile(rf"(C:\\Users\\(?:{_USER_SEGMENT}))")

_GENERIC_PLACEHOLDERS = frozenset(
    {
        "me", "x", "y", "foo", "bar", "baz", "dev", "user", "users",
        "username", "test", "tester", "xxx", "yyy", "you", "youruser",
        "your-user", "your_user", "name", "someone", "example", "sample",
        "path", "placeholder",
    }
)
"""視為示例而非真實機器名的使用者名片段。

Why: 這些值出現在說明文件的範例路徑中，不代表任何實際環境。把它們納入
警告會使誤報淹沒真陽性——規則與 references 目錄內的示例路徑數量遠多於
真實殘留。

新增項目的判準：該名稱是否在本框架的文件中作為「任意使用者」的代稱使用。
是則加入；若是某個真實環境的帳號名，即使只在本專案出現過一次也不加入。
"""

# 掃描的自由文字欄位（與 spec_reference_checker 的 _SCANNED_TEXT_KEYS 同族，
# 但額外納入 how.strategy 與 acceptance——實測路徑最常寫在這兩處）
_SCANNED_TEXT_KEYS = ("title", "what", "when", "why")


def _is_generic(prefix: str) -> bool:
    """判斷路徑前綴的使用者名片段是否為通用佔位符。

    只比對白名單，不另做角括號 / 大括號判斷：那些形態不含 `_USER_SEGMENT`
    的合法起始字元，正則階段即不匹配，永遠到不了這裡。多寫一層會讓維護者
    誤以為佔位符處理有兩道防線而不敢調整正則。
    """
    separator = "\\" if prefix.startswith("C:") else "/"
    name = prefix.rsplit(separator, 1)[-1]
    return name.lower() in _GENERIC_PLACEHOLDERS


def find_machine_specific_paths(text: str) -> List[str]:
    """回傳文字中的機器專屬路徑前綴，依首次出現順序去重。

    只回傳前綴（`/Users/alice`）而非完整路徑：同一台機器的多個路徑共用
    一個前綴，逐條列出完整路徑會讓警告長度與 ticket 內路徑數成正比。
    """
    if not isinstance(text, str) or not text:
        return []

    found: List[str] = []
    for pattern in (_POSIX_RE, _WINDOWS_RE):
        for match in pattern.finditer(text):
            prefix = match.group(1)
            if _is_generic(prefix) or prefix in found:
                continue
            found.append(prefix)
    return found


def _collect_text(ticket_fields: Dict[str, Any]) -> str:
    """從 ticket 欄位字典組合待掃描文字；型別異常一律略過不拋例外。"""
    parts: List[str] = []

    for key in _SCANNED_TEXT_KEYS:
        value = ticket_fields.get(key)
        if isinstance(value, str):
            parts.append(value)

    where = ticket_fields.get("where")
    if isinstance(where, dict):
        layer = where.get("layer")
        if isinstance(layer, str):
            parts.append(layer)
        files = where.get("files")
        if isinstance(files, list):
            parts.extend(item for item in files if isinstance(item, str))

    how = ticket_fields.get("how")
    if isinstance(how, dict):
        strategy = how.get("strategy")
        if isinstance(strategy, str):
            parts.append(strategy)

    acceptance = ticket_fields.get("acceptance")
    if isinstance(acceptance, list):
        parts.extend(item for item in acceptance if isinstance(item, str))

    return "\n".join(parts)


def _build_warning(prefixes: List[str]) -> str:
    """組裝警告文字：現象 + 後果 + 兩條處置路徑。"""
    return (
        f"偵測到機器專屬絕對路徑 {len(prefixes)} 處: {', '.join(prefixes)}\n"
        "   換機（換帳號 / 裝置 / 容器）後這些路徑會全數解析不到，而錯誤訊息"
        "只說路徑不存在，不會揭示這是跨機殘留\n"
        "   處置一（操作指引）：改為 ~ 起頭或專案相對路徑\n"
        "   處置二（實測記錄）：保留原值並標註量測環境（HOME / 平台 / 日期），"
        "改寫會讓記錄宣稱量到了從未量到的值"
    )


def detect_machine_specific_paths(ticket_fields: Dict[str, Any]) -> List[str]:
    """偵測 ticket 欄位中的機器專屬絕對路徑（建票路徑用）。

    Args:
        ticket_fields: ticket 欄位字典（create 的 config 或完整 frontmatter）

    Returns:
        List[str]: 0 或 1 則警告訊息（單則含全部命中前綴）
    """
    if not isinstance(ticket_fields, dict) or not ticket_fields:
        return []

    prefixes = find_machine_specific_paths(_collect_text(ticket_fields))
    return [_build_warning(prefixes)] if prefixes else []


def scan_ticket_file_for_machine_paths(ticket_path: Path) -> List[str]:
    """掃描既有 ticket 檔（frontmatter + body）的機器專屬路徑（認領路徑用）。

    認領時掃全檔而非只掃 frontmatter：實測記錄多寫在 Problem Analysis 與
    Solution 的內文，而接手者要照著操作的正是那些路徑。

    讀取失敗（檔案不存在、權限不足、解碼失敗）一律回傳空清單：本檢查是
    附加提示，不可成為認領中斷的來源。
    """
    try:
        content = Path(ticket_path).read_bytes().decode("utf-8", errors="replace")
    except OSError:
        return []

    prefixes = find_machine_specific_paths(content)
    return [_build_warning(prefixes)] if prefixes else []
