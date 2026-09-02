"""
格式解析模組

提供 Markdown frontmatter 解析、Ticket 檔案載入和儲存功能。
支援 Markdown（含 frontmatter）和 YAML 格式。
"""
import os
import pickle
import re
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

from ticket_system import constants as _enum_constants
from .paths import get_ticket_path, get_ticket_state_root


# ============================================================================
# 自訂異常
# ============================================================================

class YAMLParseError(Exception):
    """
    YAML 解析錯誤異常

    用於區分 YAML 解析失敗和檔案不存在。
    呼叫端可以捕獲此異常並顯示詳細的錯誤訊息給使用者。
    """
    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)


class EnumGateViolation(Exception):
    """枚舉驗證閘違規（deny 模式）：非法枚舉值或非法狀態轉移被拒絕落盤。

    violations 為 (field, old_value, new_value, valid_values, kind) tuple 清單
    （kind 為 "enum" 枚舉成員違規 / "transition" 狀態轉移違規），
    供呼叫端組錯誤訊息或測試斷言。
    """

    def __init__(self, violations: List[tuple]):
        self.violations = violations
        detail = "; ".join(
            _format_violation(field, old, new, valid, kind)
            for field, old, new, valid, kind in violations
        )
        super().__init__(f"枚舉驗證閘拒絕落盤：{detail}")


def _format_violation(field, old, new, valid, kind) -> str:
    """組單筆違規的人讀訊息（stderr / 例外共用）。"""
    if kind == "transition":
        allowed = ", ".join(sorted(valid)) if valid else "無（終態）"
        return f"{field} 轉移 {old!r} -> {new!r} 非法（{old} 合法出邊：{allowed}）"
    return f"{field} 值 {new!r} 不在正典（{', '.join(sorted(valid))}）"


class CharsetGateViolation(Exception):
    """字元驗證閘違規：欄位值含 emoji 或孤立 UTF-16 代理碼位被拒絕落盤
    （language-constraints 規則 3 的寫入端防線）。

    violations 為 (field_path, char, codepoint, kind) tuple 清單
    （kind 為 "surrogate" 孤立代理碼位 / "emoji" emoji 字元），
    供呼叫端組錯誤訊息或測試斷言。
    """

    def __init__(self, violations: List[tuple]):
        self.violations = violations
        detail = "; ".join(
            _format_charset_violation(field_path, char, code, kind)
            for field_path, char, code, kind in violations
        )
        super().__init__(f"字元驗證閘拒絕落盤：{detail}")


def _format_charset_violation(field_path: str, char: str, code: int, kind: str) -> str:
    """組單筆字元違規的人讀訊息（stderr / 例外共用）。

    label 中英文交界補空格（中文排版慣例：CJK 與英文緊鄰時需空格分隔）——
    「孤立 UTF-16 代理碼位」開頭為中文字元不需額外空格，「emoji 字元」開頭為
    英文字母則需要空格（修正原輸出「含emoji 字元」缺空格的排版問題）。
    """
    label = "孤立 UTF-16 代理碼位" if kind == "surrogate" else "emoji 字元"
    separator = " " if kind == "emoji" else ""
    msg = f"{field_path} 含{separator}{label} {char!r} (U+{code:04X})"
    if kind == "emoji":
        from ticket_system import constants as _charset_constants

        msg += f"，違反 {_charset_constants.CHARSET_GATE_RULE_REFERENCE}"
    return msg


# ============================================================================
# Process-scoped ticket cache
# ============================================================================

# 使用完整路徑作為 key，避免版本號正規化問題
# 每次 CLI 執行時自動清空（process 結束即失效）
_ticket_cache: Dict[str, Optional[Dict[str, Any]]] = {}


# ============================================================================
# 跨 CLI 呼叫的 frontmatter 磁碟快取（2026-09-02 新增）
# ============================================================================
#
# Why：conflicts --for/--among 對全票池逐票呼叫 load_ticket()，實測 YAML
# frontmatter 解析（yaml.safe_load）占 list_tickets() 總耗時約八成（另一項
# 主導成本——get_ticket_state_root() 的 git subprocess——已由該函式自身的
# 程序內快取解決，見 paths.py）。frontmatter 解析結果與檔案內容一一對應，
# 以 (mtime, size) 作為失效鍵快取至磁碟，可讓後續 CLI 呼叫跳過重複解析。
#
# 鍵值選擇：mtime + size 而非 ticket ID 單獨當鍵——並行 session 會改票面，
# 純 ID 鍵無法偵測內容變更；mtime+size 是內容變更的可靠代理（save_ticket
# 寫入時必然更新 mtime，且另於 save_ticket 顯式失效同一 cache_key，見下）。
#
# 測試隔離：僅在生產路徑（TICKET_SYSTEM_TEST_ISOLATION 未設）啟用，pytest
# 環境（conftest.py 的 `_isolate_project_root` autouse fixture 一律設此旗標）
# 完全略過磁碟快取，行為與快取加入前一致，避免 tmp_path 快速覆寫時 mtime
# 精度不足導致的假命中風險，且不需在測試層額外處理快取失效。
_frontmatter_disk_cache: Optional[Dict[str, Dict[str, Any]]] = None
_frontmatter_disk_cache_dirty = False
_FRONTMATTER_CACHE_FILENAME = "ticket-frontmatter-cache.pkl"


def _frontmatter_disk_cache_enabled() -> bool:
    """僅生產路徑啟用磁碟快取；測試隔離旗標存在時一律停用（見上方模組註解）。"""
    return os.environ.get("TICKET_SYSTEM_TEST_ISOLATION") != "1"


def _frontmatter_cache_path() -> Path:
    """磁碟快取檔位置：主倉庫 .claude/hook-logs/ 下（該目錄已於 .gitignore 排除）。"""
    return get_ticket_state_root() / ".claude" / "hook-logs" / _FRONTMATTER_CACHE_FILENAME


def _load_frontmatter_disk_cache() -> Dict[str, Dict[str, Any]]:
    """惰性載入磁碟快取（同一 process 內僅讀取一次）。

    快取檔損毀或不存在時回傳空 dict，不阻斷主流程（quality-baseline 規則 4：
    catch 後 return 預設值需記錄警告）。

    安全性：本快取檔僅由 `flush_frontmatter_disk_cache()` 寫入，內容來源是
    本機 ticket 票面經 `parse_frontmatter()` 解析後的結果，非外部/網路輸入；
    寫入端為同一使用者本機 process，非跨信任邊界資料，`pickle.load` 於此
    情境不構成任意程式碼執行風險（風險模型與 CPython 標準函式庫
    `functools.lru_cache` 的行程內快取相同：僅信任自己寫入的資料）。
    """
    global _frontmatter_disk_cache
    if _frontmatter_disk_cache is not None:
        return _frontmatter_disk_cache
    path = _frontmatter_cache_path()
    try:
        with open(path, "rb") as f:
            loaded = pickle.load(f)
        _frontmatter_disk_cache = loaded if isinstance(loaded, dict) else {}
    except FileNotFoundError:
        _frontmatter_disk_cache = {}
    except (OSError, pickle.UnpicklingError, EOFError, AttributeError) as e:
        sys.stderr.write(
            f"[parser] frontmatter 磁碟快取載入失敗（{type(e).__name__}: {e}），"
            "改為全量重新解析\n"
        )
        _frontmatter_disk_cache = {}
    return _frontmatter_disk_cache


def flush_frontmatter_disk_cache() -> None:
    """將記憶體中的磁碟快取寫回檔案（供 list_tickets 批次載入後呼叫）。

    原子寫入（暫存檔 + os.replace）避免並行 CLI 寫入同一快取檔時損毀既有
    內容；寫入失敗僅 stderr 警告，不阻斷主流程（下次呼叫仍會重新解析）。
    """
    global _frontmatter_disk_cache_dirty
    if not _frontmatter_disk_cache_dirty or _frontmatter_disk_cache is None:
        return
    path = _frontmatter_cache_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
        try:
            with os.fdopen(fd, "wb") as f:
                pickle.dump(_frontmatter_disk_cache, f)
            os.replace(tmp_name, path)
        finally:
            if os.path.exists(tmp_name):
                os.remove(tmp_name)
    except OSError as e:
        sys.stderr.write(
            f"[parser] frontmatter 磁碟快取寫回失敗（{type(e).__name__}: {e}），"
            "下次呼叫仍會重新解析\n"
        )
    else:
        _frontmatter_disk_cache_dirty = False


def _invalidate_frontmatter_disk_cache_entry(cache_key: str) -> None:
    """save_ticket 寫入票面後同步失效磁碟快取（與既有 _ticket_cache.pop 同一時機）。

    雖然 mtime 變更本身足以讓下次讀取判定快取過期（見鍵值選擇說明），此處
    顯式移除是防禦性加強：避免 stale entry 在快取檔內無限期殘留占用空間。
    """
    if _frontmatter_disk_cache is not None:
        _frontmatter_disk_cache.pop(cache_key, None)


# 特殊欄位常數
SPECIAL_FIELDS = ["chain", "decision_tree_path", "created"]

# Frontmatter 邊界標記：要求 --- 獨占一行（允許行尾空白），錨定於行首。
# 舊實作用純文字子字串搜尋定位邊界，frontmatter 欄位值內任意位置出現
# 連續三個減號（表格分隔列、diff hunk 標記、em-dash 序列）皆會被誤判為
# 邊界。改用逐行錨定比對後，僅獨占一行的 --- 才視為邊界，欄位值中間出現
# 的 --- 子字串不受影響。
_FRONTMATTER_BOUNDARY_RE = re.compile(r"^---[ \t]*(?:\r\n|\n|\Z)", re.MULTILINE)

# 枚舉閘載入時快照欄位名（_ 前綴：僅存在於記憶體 dict，save 時剝除不序列化）
ENUM_SNAPSHOT_FIELD = "_loaded_enum_snapshot"

# 枚舉閘關注欄位（名稱固定；合法值集合於呼叫時讀 constants 模組屬性，
# 使測試可 monkeypatch VALID_* / ENUM_GATE_MODE）
_ENUM_GATE_FIELD_NAMES = ("type", "priority", "status")

# PyYAML 雙引號純量的 \uXXXX 逸出序列不會像 JSON 一樣自動組合合法 UTF-16
# 代理對（已實測驗證：合法配對逸出，PyYAML 仍保留為兩個獨立的孤立代理碼
# 位），也不拒絕不成對的孤立代理碼位。這些 U+D800-U+DFFF 碼位一旦進入
# Python str，任何後續 UTF-8 編碼（含檔案寫入）都會拋 UnicodeEncodeError；
# 且該字元本身不影響 raw 檔案掃描（檔案內容是 ASCII 逸出序列，不是實際
# 代理碼位），只有在 yaml.safe_load 解析後才存在，故需在解析完成當下立即
# 修正，而非依賴下游各處自行防禦。
_SURROGATE_PAIR_RE = re.compile("[\ud800-\udbff][\udc00-\udfff]")
_LONE_SURROGATE_RE = re.compile("[\ud800-\udfff]")


def _combine_surrogate_pair(match: "re.Match[str]") -> str:
    """將一組合法配對的高低代理碼位組合為單一星面字元（UTF-16 解碼公式）。"""
    high, low = (ord(c) for c in match.group(0))
    code_point = 0x10000 + (high - 0xD800) * 0x400 + (low - 0xDC00)
    return chr(code_point)


def _sanitize_surrogates(value: str) -> str:
    """修正字串中 PyYAML \\u 逸出殘留的代理碼位（合法配對組合，孤立者替換）。

    孤立代理碼位無法被 UTF-8 編碼，替換為 U+FFFD 並寫 stderr 警告
    （quality-baseline 規則 4：異常不可靜默）——這是資料層面的損毀修正，
    使用者應可見，而非悄悄改寫內容。
    """
    if not any("\ud800" <= c <= "\udfff" for c in value):
        return value
    combined = _SURROGATE_PAIR_RE.sub(_combine_surrogate_pair, value)
    if any("\ud800" <= c <= "\udfff" for c in combined):
        sys.stderr.write(
            "[parser] 偵測到孤立 UTF-16 代理碼位（YAML \\u 逸出未正確配對或"
            "不成對），已替換為 U+FFFD 避免寫入時 UnicodeEncodeError\n"
        )
        combined = _LONE_SURROGATE_RE.sub("�", combined)
    return combined


def _sanitize_surrogates_deep(value: Any) -> Any:
    """遞迴套用 `_sanitize_surrogates` 至巢狀結構（dict/list/str）。"""
    if isinstance(value, str):
        return _sanitize_surrogates(value)
    if isinstance(value, list):
        return [_sanitize_surrogates_deep(x) for x in value]
    if isinstance(value, dict):
        return {k: _sanitize_surrogates_deep(v) for k, v in value.items()}
    return value


# 字元閘載入時快照欄位名（_ 前綴：僅存在於記憶體 dict，save 時剝除不序列化）。
# 與 ENUM_SNAPSHOT_FIELD 分開持有：枚舉閘只關注 3 個固定欄位，字元閘需涵蓋
# 任意欄位的字串葉值，快照結構（扁平路徑 -> 字串值）不同，合併會混淆兩者的
# changed-fields-only 比對基準。
CHARSET_SNAPSHOT_FIELD = "_loaded_charset_snapshot"


# 頂層識別性欄位不納入字元閘：id 已由 validate_ticket_id 限制字元集，
# created/updated 為系統產生的日期字串，皆非使用者自由輸入的文字欄位；
# 且每張票 id 必然互異，若納入快照會使不同 ticket 的快照恆不相等，讓
# 「內容相同的兩張票」誤判為快照有別（既有 topic 選取測試已驗證此邊界）。
_CHARSET_SNAPSHOT_EXCLUDED_KEYS = frozenset({"id", "created", "updated"})


def _flatten_text_fields(data: Dict[str, Any], prefix: str = "") -> Dict[str, str]:
    """遞迴攤平 ticket frontmatter 中的字串葉值，供字元閘 changed-fields-only 比對。

    跳過 `_` 前綴的內部欄位（`_body` / `_path` / 兩個快照欄位本身），避免
    快照自我巢狀或把 body 全文誤納入寫入端字元檢查（body 範圍屬 append-log
    等既有機制，非本閘職責）。頂層 id/created/updated 另行排除（見
    `_CHARSET_SNAPSHOT_EXCLUDED_KEYS`）。

    Args:
        data: ticket 資料字典（或巢狀 dict）
        prefix: 遞迴時的路徑前綴（頂層呼叫免填）

    Returns:
        Dict[str, str]：{欄位路徑: 字串值}，路徑格式 "who.current"、
        "where.files[0]" 等，供比對與違規訊息定位使用
    """
    flat: Dict[str, str] = {}
    for key, value in data.items():
        if isinstance(key, str) and key.startswith("_"):
            continue
        if not prefix and key in _CHARSET_SNAPSHOT_EXCLUDED_KEYS:
            continue
        path = f"{prefix}{key}"
        if isinstance(value, str):
            flat[path] = value
        elif isinstance(value, dict):
            flat.update(_flatten_text_fields(value, prefix=f"{path}."))
        elif isinstance(value, list):
            for idx, item in enumerate(value):
                if isinstance(item, str):
                    flat[f"{path}[{idx}]"] = item
                elif isinstance(item, dict):
                    flat.update(_flatten_text_fields(item, prefix=f"{path}[{idx}]."))
    return flat


def _find_charset_violations(value: str) -> List[Tuple[str, int, str]]:
    """掃描單一字串值的孤立代理碼位與 emoji 違規（寫入端防線）。

    合法配對逸出（高低代理位相鄰成對）先組合為單一星面字元，避免誤判為
    代理位違規；組合後落在 emoji 範圍者計為 "emoji" 違規（不再重複計代理
    位違規）。組合後仍落單的代理位（無法配對）計為 "surrogate" 違規。

    Args:
        value: 待檢查的字串值

    Returns:
        List[(char, codepoint, kind)]：kind 為 "surrogate" 或 "emoji"；
        同碼位僅回報一次（去重）
    """
    combined = _SURROGATE_PAIR_RE.sub(_combine_surrogate_pair, value)
    violations: List[Tuple[str, int, str]] = []
    seen = set()
    for char in combined:
        code = ord(char)
        if code in seen:
            continue
        if 0xD800 <= code <= 0xDFFF:
            violations.append((char, code, "surrogate"))
            seen.add(code)
            continue
        for start, end in _enum_constants.EMOJI_RANGES:
            if start <= code <= end:
                violations.append((char, code, "emoji"))
                seen.add(code)
                break
    return violations


def _collect_charset_violations(
    ticket: Dict[str, Any],
    snapshot: Optional[Dict[str, str]],
) -> List[tuple]:
    """收集字元違規：只驗「相對載入快照有變更」的欄位值（changed-fields-only）。

    Why（化石豁免 / Never break userspace）：語料存在含 emoji 的化石票
    （曾有子票 why 欄位混入 emoji 字元），全票驗證會讓任何不相關寫入
    （append-log / 改其他欄位）對化石票炸錯。以載入快照比對，欄位值未被
    本次操作改動即跳過；無快照（新建票，未經 load_ticket）→ 全欄位驗證。

    Returns:
        List[tuple]: (field_path, char, codepoint, kind)
    """
    current = _flatten_text_fields(ticket)
    violations: List[tuple] = []
    for field_path, value in current.items():
        if snapshot is not None and value == snapshot.get(field_path):
            continue  # 未被本次操作改動 → 化石豁免
        for char, code, kind in _find_charset_violations(value):
            violations.append((field_path, char, code, kind))
    return violations


def _log_charset_violations(
    violations: List[tuple],
    ticket: Dict[str, Any],
    ticket_path: Path,
) -> None:
    """違規寫入 hook-logs/charset-gate.log（quality-baseline 規則 4：業務邏輯拒絕日誌必須）。"""
    try:
        from .paths import get_project_root
        log_dir = get_project_root() / ".claude" / "hook-logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        entry_id = ticket.get("id", ticket_path.stem)
        with open(log_dir / "charset-gate.log", "a", encoding="utf-8") as f:
            for field_path, char, code, kind in violations:
                f.write(
                    f"{timestamp}\t{kind}\t{entry_id}\t{field_path}\t{char!r}\tU+{code:04X}\n"
                )
    except OSError as e:
        # 量測日誌失敗不阻斷主流程（deny 已由呼叫端 raise 完成）；
        # stderr 保留可觀測性（雙通道要求）
        sys.stderr.write(
            f"[charset-gate] 日誌寫入失敗（{type(e).__name__}: {e}），僅 stderr 警告\n"
        )


def _enforce_charset_gate(
    ticket: Dict[str, Any],
    snapshot: Optional[Dict[str, str]],
    ticket_path: Path,
) -> None:
    """save_ticket 落盤前的字元驗證閘：拒絕含 emoji 或孤立代理碼位的欄位值
    （language-constraints 規則 3 的寫入端防線）。

    無 warn 過渡期，直接 deny：本閘防的是規則 3 已明文禁止的內容，非需經
    量測誤報率才能收斂邊界的既有正典枚舉；化石票已由 changed-fields-only
    比對豁免（見 `_collect_charset_violations`），不需額外量測期。
    """
    violations = _collect_charset_violations(ticket, snapshot)
    if not violations:
        return
    _log_charset_violations(violations, ticket, ticket_path)
    entry_id = ticket.get("id", ticket_path.stem)
    for field_path, char, code, kind in violations:
        sys.stderr.write(
            f"[charset-gate] {entry_id} 拒絕落盤："
            f"{_format_charset_violation(field_path, char, code, kind)}\n"
        )
    raise CharsetGateViolation(violations)


def _snapshot_enum_fields(data: Dict[str, Any]) -> Dict[str, Any]:
    """擷取枚舉閘關注欄位的載入時快照（changed-fields-only 比對基準）。"""
    return {field: data.get(field) for field in _ENUM_GATE_FIELD_NAMES}


def _collect_enum_violations(
    ticket: Dict[str, Any],
    snapshot: Optional[Dict[str, Any]],
) -> List[tuple]:
    """收集枚舉違規：只驗「相對載入快照有變更」的欄位。

    Why（化石豁免 / Never break userspace）：語料存在正典外化石值
    （type 12 / priority 24 / status 6 筆），全票驗證會讓任何不相關寫入
    （append-log / set-what）對化石票炸警告。以載入快照比對，欄位值未被
    本次操作改動即跳過；無快照（新建票，未經 load_ticket）→ 全欄位驗證。

    邊界：欄位缺席或為 None 不列違規——必填性屬 checklist / auditor 職責，
    本閘只守「有值時必須是正典值」。非字串值（list/dict 誤塞）視為違規。

    Returns:
        List[tuple]: (field, old_value, new_value, valid_values, "enum")
    """
    gate_fields = {
        "type": _enum_constants.VALID_TICKET_TYPES,
        "priority": _enum_constants.VALID_PRIORITIES,
        "status": _enum_constants.VALID_STATUSES,
    }
    violations = []
    for field, valid_values in gate_fields.items():
        if field not in ticket:
            continue
        new_value = ticket.get(field)
        if new_value is None:
            continue
        if snapshot is not None and new_value == snapshot.get(field):
            continue  # 未被本次操作改動 → 化石豁免
        if not isinstance(new_value, str) or new_value not in valid_values:
            violations.append(
                (field, snapshot.get(field) if snapshot else None, new_value, valid_values, "enum")
            )
    return violations


def _collect_transition_violations(
    ticket: Dict[str, Any],
    snapshot: Optional[Dict[str, Any]],
) -> List[tuple]:
    """收集狀態轉移違規：status 變更時查 STATUS_TRANSITIONS[old] 是否含 new。

    邊界（不重複計、化石容忍）：
    - 無快照（新建票）→ 無「轉移」概念，跳過。
    - 舊態非正典（skipped 等化石）→ 跳過：無法從未知狀態斷言邊合法性，
      且矯正化石票回正典狀態不應被阻擋。
    - 新態非正典 → 跳過：已由枚舉成員違規計入，避免同一寫入雙重告警。

    Returns:
        List[tuple]: (field, old, new, allowed_targets, "transition")
    """
    if snapshot is None:
        return []
    old_value = snapshot.get("status")
    new_value = ticket.get("status")
    if new_value is None or new_value == old_value:
        return []
    transitions = getattr(_enum_constants, "STATUS_TRANSITIONS", {})
    if not isinstance(old_value, str) or old_value not in transitions:
        return []
    if not isinstance(new_value, str) or new_value not in transitions:
        return []
    if new_value in transitions[old_value]:
        return []
    return [("status", old_value, new_value, transitions[old_value], "transition")]


def _log_enum_violations(
    violations: List[tuple],
    ticket: Dict[str, Any],
    ticket_path: Path,
    mode: str,
) -> None:
    """違規寫入 hook-logs/enum-gate.log（warn 期誤報率量測資料源）。"""
    try:
        from .paths import get_project_root
        log_dir = get_project_root() / ".claude" / "hook-logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        entry_id = ticket.get("id", ticket_path.stem)
        with open(log_dir / "enum-gate.log", "a", encoding="utf-8") as f:
            for field, old, new, _valid, kind in violations:
                f.write(f"{timestamp}\t{mode}\t{kind}\t{entry_id}\t{field}\t{old!r}\t{new!r}\n")
    except OSError as e:
        # 量測日誌失敗不阻斷落盤主流程；stderr 保留可觀測性（雙通道要求）
        sys.stderr.write(
            f"[enum-gate] 日誌寫入失敗（{type(e).__name__}: {e}），僅 stderr 警告\n"
        )


def _enforce_enum_gate(
    ticket: Dict[str, Any],
    snapshot: Optional[Dict[str, Any]],
    ticket_path: Path,
) -> None:
    """save_ticket 落盤前的枚舉驗證閘（31 個寫入呼叫點的單點防線）。

    warn 模式：stderr 警告 + enum-gate.log 記錄後照常落盤（量測期預設）。
    deny 模式：raise EnumGateViolation，呼叫端不落盤。
    模式讀 constants.ENUM_GATE_MODE（切 deny 須經 warn 期誤報率量測裁定）。
    """
    violations = _collect_enum_violations(ticket, snapshot)
    violations += _collect_transition_violations(ticket, snapshot)
    if not violations:
        return
    mode = getattr(_enum_constants, "ENUM_GATE_MODE", "warn")
    _log_enum_violations(violations, ticket, ticket_path, mode)
    entry_id = ticket.get("id", ticket_path.stem)
    for field, old, new, valid, kind in violations:
        sys.stderr.write(
            f"[enum-gate:{mode}] {entry_id} {_format_violation(field, old, new, valid, kind)}\n"
        )
    if mode == "deny":
        raise EnumGateViolation(violations)


def _backup_special_fields(existing_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    備份現有 Ticket 的特殊欄位

    Ticket 中有些欄位（如 chain、decision_tree_path、created）在儲存時
    應該被保留。此函式將這些特殊欄位從現有資料中備份出來。

    Args:
        existing_data: 現有的 Ticket 資料字典

    Returns:
        Dict[str, Any]: 包含所有特殊欄位的備份字典（只含在 existing_data 中存在的欄位）

    Examples:
        >>> data = {"chain": "0.31.0-W4-001", "id": "test"}
        >>> backup = _backup_special_fields(data)
        >>> backup
        {'chain': '0.31.0-W4-001'}
    """
    return {
        field: existing_data[field]
        for field in SPECIAL_FIELDS
        if field in existing_data
    }


def _restore_special_fields(
    new_data: Dict[str, Any],
    backup: Dict[str, Any]
) -> Dict[str, Any]:
    """
    恢復特殊欄位到新資料

    在更新 Ticket 資料後，可能需要恢復某些特殊欄位（如果它們不在新資料中）。
    這確保了特殊欄位的完整性。

    Args:
        new_data: 新的 Ticket 資料字典
        backup: 備份的特殊欄位字典

    Returns:
        Dict[str, Any]: 包含恢復後欄位的結果字典

    Examples:
        >>> new_data = {"id": "test"}
        >>> backup = {"chain": "0.31.0-W4-001"}
        >>> result = _restore_special_fields(new_data, backup)
        >>> result
        {'id': 'test', 'chain': '0.31.0-W4-001'}
    """
    result = new_data.copy()
    for field, value in backup.items():
        if field not in result:
            result[field] = value
    return result


def parse_frontmatter(content: str) -> Tuple[Dict[str, Any], str]:
    """
    解析 Markdown frontmatter

    分離 YAML frontmatter 和 body。Frontmatter 必須在檔案開頭，由獨占一行
    的 --- 分隔（欄位值內任意位置出現的 --- 子字串不影響邊界判定）。
    使用 Guard Clause 模式快速返回異常情況。

    演算法:
    1. 檢查內容是否以 --- 開頭，否則無 frontmatter
    2. 以逐行錨定比對找出開頭與結尾兩條 --- 邊界線
    3. 驗證兩條邊界線皆存在
    4. 嘗試解析 YAML，失敗時丟出 YAMLParseError

    Args:
        content: 完整檔案內容（可能包含 frontmatter）

    Returns:
        Tuple[Dict, str]: (frontmatter_dict, body_text)
                         frontmatter_dict 為空時表示無 frontmatter

    Raises:
        YAMLParseError: YAML 解析失敗時丟出

    Examples:
        >>> content = '---\\ntitle: test\\n---\\nBody content'
        >>> fm, body = parse_frontmatter(content)
        >>> fm['title']
        'test'
        >>> body.strip()
        'Body content'
        >>> parse_frontmatter('No frontmatter')
        ({}, 'No frontmatter')
    """
    # Guard Clause 1：內容不以 --- 開頭 → 無 frontmatter
    if not content.startswith("---"):
        return {}, content

    # 找開頭邊界線（必須從檔案第一行開始）
    start_match = _FRONTMATTER_BOUNDARY_RE.match(content)
    if start_match is None:
        return {}, content

    # 找結尾邊界線（開頭邊界線之後第一條獨占一行的 ---）
    end_match = _FRONTMATTER_BOUNDARY_RE.search(content, start_match.end())

    # Guard Clause 2：找不到結尾邊界線 → 格式錯誤
    if end_match is None:
        return {}, content

    try:
        yaml_text = content[start_match.end():end_match.start()]
        body = content[end_match.end():].strip()
        frontmatter = yaml.safe_load(yaml_text)
        # 如果 YAML 解析為 None，返回空字典，否則返回解析結果（先修正孤立
        # 代理碼位，避免下游任何 UTF-8 編碼操作拋 UnicodeEncodeError）
        return _sanitize_surrogates_deep(frontmatter) or {}, body
    except yaml.YAMLError as e:
        # YAML 解析失敗時，丟出 YAMLParseError 傳遞錯誤訊息
        error_msg = str(e).strip()
        raise YAMLParseError(error_msg)


def load_ticket(version: str, ticket_id: str) -> Optional[Dict[str, Any]]:
    """
    載入 Ticket 資料

    支援 Markdown（含 frontmatter）和 YAML 格式。使用 Guard Clause 快速返回失敗情況。
    返回的字典包含特殊欄位：
    - _body: Markdown body 內容（Markdown 格式）
    - _path: Ticket 檔案路徑（絕對路徑字串）
    - _yaml_error: 若有 YAML 解析錯誤，包含錯誤訊息

    實作 process-scoped 記憶體快取，避免同一 process 內重複讀取相同 ticket。

    演算法:
    1. 取得 Ticket 檔案路徑
    2. 檢查快取（命中則直接返回）
    3. 檢查檔案是否存在
    4. 讀取檔案內容（支援 UTF-8 編碼）
    5. 根據副檔名選擇解析策略：
       - .md: 解析 frontmatter（YAML）和 body，捕獲 YAMLParseError
       - 其他: 直接解析為 YAML，捕獲 yaml.YAMLError
    6. 附加元資料、更新快取並返回；若有解析錯誤則在字典中記錄

    Args:
        version: 版本號（如 "0.31.0" 或 "v0.31.0"）
        ticket_id: Ticket ID（如 "0.31.0-W4-001"）

    Returns:
        Optional[Dict]: 完整的 Ticket 資料字典。
                       若 YAML 解析失敗，返回包含 _yaml_error 欄位的字典。
                       若檔案不存在或無法讀取，返回 None。

    Raises:
        無，所有異常都安全處理

    Examples:
        >>> ticket = load_ticket("0.31.0", "0.31.0-W4-001")
        >>> ticket is not None and ticket['id'] == '0.31.0-W4-001'
        True
        >>> load_ticket("0.31.0", "nonexistent")
        None
        >>> ticket = load_ticket("0.31.0", "broken-yaml")
        >>> ticket is not None and '_yaml_error' in ticket
        True
    """
    # Guard Clause 1：檔案不存在
    ticket_path = get_ticket_path(version, ticket_id)
    cache_key = str(ticket_path)

    # Guard Clause 1.5：檢查快取
    if cache_key in _ticket_cache:
        return _ticket_cache[cache_key]

    try:
        file_stat = ticket_path.stat()
    except FileNotFoundError:
        return None
    except OSError:
        return None

    # Guard Clause 1.7：磁碟快取命中（僅生產路徑，見模組層說明）——
    # (mtime, size) 與快取記錄相符時，直接沿用已解析結果，跳過檔案讀取與
    # yaml.safe_load（frontmatter 解析為 list_tickets() 逐票呼叫時的主導耗時，
    # 見模組層 Why）。
    disk_cache_key = None
    if ticket_path.suffix == ".md" and _frontmatter_disk_cache_enabled():
        disk_cache_key = str(ticket_path)
        disk_cache = _load_frontmatter_disk_cache()
        cached_entry = disk_cache.get(disk_cache_key)
        if (
            cached_entry is not None
            and cached_entry.get("mtime") == file_stat.st_mtime
            and cached_entry.get("size") == file_stat.st_size
        ):
            frontmatter = dict(cached_entry["frontmatter"])
            frontmatter["_body"] = cached_entry["body"]
            frontmatter["_path"] = str(ticket_path)
            frontmatter[ENUM_SNAPSHOT_FIELD] = _snapshot_enum_fields(frontmatter)
            frontmatter[CHARSET_SNAPSHOT_FIELD] = _flatten_text_fields(frontmatter)
            _ticket_cache[cache_key] = frontmatter
            return frontmatter

    # 嘗試讀取檔案內容（Guard Clause 2：讀取失敗）
    try:
        with open(ticket_path, "r", encoding="utf-8") as f:
            content = f.read()
    except (IOError, OSError):
        return None

    # 根據副檔名選擇解析策略
    if ticket_path.suffix == ".md":
        # Markdown 格式：含 YAML frontmatter 和 body
        try:
            frontmatter, body = parse_frontmatter(content)
        except YAMLParseError as e:
            # 若 YAML 解析失敗，返回包含錯誤訊息的字典（並快取）
            result = {
                "id": ticket_id,
                "_path": str(ticket_path),
                "_yaml_error": e.message
            }
            _ticket_cache[cache_key] = result
            return result

        # Guard Clause 3：frontmatter 為空（無 frontmatter）
        if not frontmatter:
            return None

        # 寫入磁碟快取（快取未含衍生欄位的原始 frontmatter + body，衍生欄位
        # 每次讀取時重新計算，成本低廉，避免快取內容與計算邏輯脫鉤）
        if disk_cache_key is not None:
            global _frontmatter_disk_cache_dirty
            _load_frontmatter_disk_cache()[disk_cache_key] = {
                "mtime": file_stat.st_mtime,
                "size": file_stat.st_size,
                "frontmatter": dict(frontmatter),
                "body": body,
            }
            _frontmatter_disk_cache_dirty = True

        # 附加元資料：body 內容和檔案路徑
        frontmatter["_body"] = body
        frontmatter["_path"] = str(ticket_path)
        # 枚舉閘載入時快照（save 時 changed-fields-only 比對基準）
        frontmatter[ENUM_SNAPSHOT_FIELD] = _snapshot_enum_fields(frontmatter)
        # 字元閘載入時快照（save 時 changed-fields-only 比對基準；先於快照
        # 欄位本身寫入，_flatten_text_fields 跳過 `_` 前綴故順序不影響結果）
        frontmatter[CHARSET_SNAPSHOT_FIELD] = _flatten_text_fields(frontmatter)
        # 更新快取
        _ticket_cache[cache_key] = frontmatter
        return frontmatter
    else:
        # YAML 格式：純 YAML 或 { ticket: {...} } 包裝格式
        try:
            ticket_content = _sanitize_surrogates_deep(yaml.safe_load(content))

            # Guard Clause 4：YAML 解析為空
            if not ticket_content:
                return None

            # 附加檔案路徑
            ticket_content["_path"] = str(ticket_path)

            # 支援包裝格式：如果 YAML 頂層有 'ticket' 欄位，
            # 則使用該欄位值作為實際 Ticket 資料
            if "ticket" in ticket_content:
                ticket_content = ticket_content["ticket"]
                ticket_content["_path"] = str(ticket_path)

            # 枚舉閘載入時快照（save 時 changed-fields-only 比對基準）
            ticket_content[ENUM_SNAPSHOT_FIELD] = _snapshot_enum_fields(ticket_content)
            # 字元閘載入時快照（save 時 changed-fields-only 比對基準）
            ticket_content[CHARSET_SNAPSHOT_FIELD] = _flatten_text_fields(ticket_content)

            # 更新快取
            _ticket_cache[cache_key] = ticket_content
            return ticket_content
        except yaml.YAMLError as e:
            # YAML 解析失敗時，返回包含錯誤訊息的字典（並快取）
            error_msg = str(e).strip()
            result = {
                "id": ticket_id,
                "_path": str(ticket_path),
                "_yaml_error": error_msg
            }
            _ticket_cache[cache_key] = result
            return result


def _atomic_write_text(path: Path, content: str) -> None:
    """原子寫入文字檔：先寫暫存檔再 os.replace，寫入失敗時原檔案不受影響。

    `open(path, "w")` 在呼叫當下即截斷既有檔案；若隨後 `f.write()` 失敗
    （如內容含孤立代理碼位觸發 UnicodeEncodeError），檔案會停在截斷後的
    0 byte 狀態，且此失敗發生在呼叫端的 try/except 之外的更早階段，呼叫
    端就算捕獲例外也救不回已被截斷的原內容。改為寫暫存檔成功後才以
    `os.replace` 原子取代目標檔案：寫入失敗時暫存檔案被清除、目標檔案
    完全不受影響；寫入成功時 `os.replace` 是 POSIX/Windows 皆保證的原子
    操作，其他行程讀到的內容只會是完整舊版或完整新版，不會讀到半寫狀態。
    暫存檔建立於目標檔案的同一目錄（確保與目標同一檔案系統，`os.replace`
    跨檔案系統不保證原子性）。
    """
    tmp_fd, tmp_name = tempfile.mkstemp(
        dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp"
    )
    try:
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(tmp_name, path)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def save_ticket(ticket: Dict[str, Any], ticket_path: Path) -> None:
    """
    儲存 Ticket 資料

    根據檔案副檔名自動決定格式（Markdown 或 YAML）。
    自動備份和恢復特殊欄位（_body、_path、chain、decision_tree_path）
    以保持傳入的 ticket 物件完整性。
    寫入成功後失效快取以確保後續讀取取得最新資料。

    演算法:
    1. 備份元資料欄位（_body、_path）
    2. 備份特殊欄位（chain、decision_tree_path、created）
    3. 建立目標目錄
    4. 根據副檔名選擇格式序列化
    5. 寫入檔案
    6. finally 區塊恢復所有備份欄位到 ticket 物件
    7. 寫入成功後失效對應的快取 entry

    Args:
        ticket: Ticket 資料字典（會被臨時修改但最終會恢復）
        ticket_path: 目標檔案路徑（副檔名決定格式）

    Raises:
        IOError: 檔案寫入失敗
        OSError: 目錄建立或無寫入權限

    Examples:
        >>> ticket = {'id': 'test-001', 'status': 'pending', '_body': '# Content'}
        >>> save_ticket(ticket, Path('/tmp/test.md'))
        >>> ticket['_body']  # 已恢復
        '# Content'
    """
    # 備份元資料欄位（Markdown 格式需要，YAML 格式不需要儲存）
    body = ticket.pop("_body", "")
    path_str = ticket.pop("_path", None)
    # 枚舉閘快照：剝除避免序列化進 frontmatter；deny raise 時由 finally 恢復
    enum_snapshot = ticket.pop(ENUM_SNAPSHOT_FIELD, None)
    # 字元閘快照：剝除避免序列化進 frontmatter；deny raise 時由 finally 恢復
    charset_snapshot = ticket.pop(CHARSET_SNAPSHOT_FIELD, None)

    # 備份特殊欄位（需要在儲存時保留但不序列化）
    # 這些欄位代表 Ticket 的內部狀態，由系統自動管理
    special_fields_backup = _backup_special_fields(ticket)

    # 建立目標目錄（父目錄），必要時遞迴建立
    ticket_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        # 枚舉驗證閘：置於 try 內使 deny 模式 raise 時 finally 仍恢復備份欄位
        _enforce_enum_gate(ticket, enum_snapshot, ticket_path)
        # 字元驗證閘：拒絕含 emoji / 孤立代理碼位的欄位值（同上，raise 時
        # finally 仍恢復備份欄位）
        _enforce_charset_gate(ticket, charset_snapshot, ticket_path)

        if ticket_path.suffix == ".md":
            # Markdown 格式：YAML frontmatter + body
            # 序列化 frontmatter 為 YAML
            # width=1000（過渡措施，非根治）：僅消除長字串欄位折行，避免
            # hooks 端手寫 YAML parser 誤判斷點空白。型別三類落差（巢狀
            # 列表成字串、空 dict 成字串、bool/null/int 成字串）不因此
            # 解決，且防護依賴後續新增 dump 點時的紀律而非機制。
            frontmatter_yaml = yaml.dump(
                ticket,
                allow_unicode=True,
                default_flow_style=False,
                sort_keys=False,
                width=1000,
            )
            # 組合 frontmatter 和 body：---\nYAML\n---\n\nbody
            content = f"---\n{frontmatter_yaml}---\n\n{body}"
        else:
            # YAML 格式：用 { ticket: {...} } 包裝
            # 支援包裝格式以提高相容性
            # width=1000（過渡措施，理由同上）
            content = yaml.dump(
                {"ticket": ticket},
                allow_unicode=True,
                default_flow_style=False,
                sort_keys=False,
                width=1000,
            )

        # 保留檔尾單一換行（W9-005 / issue #1 問題5）：load 不保證 body 帶
        # 檔尾換行，直接寫回會讓 claim/release roundtrip 吃掉檔尾換行，產生
        # 「No newline at end of file」git diff 雜訊。僅在缺換行時補一個，
        # 不動既有換行（避免改動帶尾換行的 body）。
        if not content.endswith("\n"):
            content += "\n"

        # 寫入檔案（UTF-8 編碼，原子寫入）
        _atomic_write_text(ticket_path, content)

    finally:
        # 必須恢復所有備份欄位，確保 ticket 物件完整性
        # 即使寫入失敗也要恢復，保持傳入物件的狀態
        ticket.update(special_fields_backup)
        if body:
            ticket["_body"] = body
        if path_str:
            ticket["_path"] = path_str
        if enum_snapshot is not None:
            ticket[ENUM_SNAPSHOT_FIELD] = enum_snapshot
        if charset_snapshot is not None:
            ticket[CHARSET_SNAPSHOT_FIELD] = charset_snapshot

    # 寫入成功後失效快取，確保後續讀取取得最新資料
    # 注意：這行在 try-finally 後執行，只有寫入成功才到達
    _ticket_cache.pop(str(ticket_path), None)
    _invalidate_frontmatter_disk_cache_entry(str(ticket_path))

    # 落盤成功後刷新快照為當前值：同一 dict 再次 save 時不對已持久化的
    # 變更重複告警（快照語意 = 「相對最後一次成功落盤」）
    ticket[ENUM_SNAPSHOT_FIELD] = _snapshot_enum_fields(ticket)
    ticket[CHARSET_SNAPSHOT_FIELD] = _flatten_text_fields(ticket)


if __name__ == "__main__":
    from ticket_system.lib.messages import print_not_executable_and_exit
    print_not_executable_and_exit()
