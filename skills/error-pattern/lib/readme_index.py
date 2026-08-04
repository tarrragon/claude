#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml"]
# ///
"""error-pattern README「現有模式」索引保守 upsert（0.2.1-W3-099）。

背景：0.2.1-W3-041 人工補齊 148 筆缺漏索引後確認 structured-content-generation
三條件全滿足（確定性 schema／多寫入者／歷史格式錯誤），依方法論應 CLI 化，把
README 索引列的寫入從人工步驟改為程式生成，取代 `/error-pattern add` 流程中
「更新 README.md 統計資訊」的文字指示。

接線方式更正（0.2.1-W3-105 取代 0.2.1-W3-102 的全量 sync 結論）：全量 sync
的前提「索引是可全量重算的 derived data」已被本票的全量 dry-run 診斷證偽——
實測 README 230 列填有真實來源版本，但檔案內能找到此資訊者僅 60 檔，170 筆
是索引獨有的一級資料，全量重生成是銷毀而非重算。改為**保守 upsert**：只做
「新增缺漏列」（目錄有檔、索引無列）與「移除死連結列」（索引有列、目錄無檔）
兩件事，既有列一律逐字保留，不重新生成、不補齊既有列的佔位符欄位。

新增列的欄位取值（0.2.1-W3-105 查證 30 檔中 15 檔 frontmatter `severity` 與
內文「風險等級」分歧且內文較準，frontmatter severity 於本模組視為不可信
來源，該問題另由 0.2.1-W3-106 獨立處理）：
- 標題：YAML frontmatter `title` → H1 標題行 → 佔位符 `—`
- 風險：內文「基本資訊」區塊（`**風險等級**` / `**嚴重度**` 等寫法）→
  佔位符 `—`（**不讀 frontmatter `severity`**）
- 來源版本：內文「來源版本」欄位 → 佔位符 `—`（frontmatter 從無此欄位）

寫入範圍：只動「## 現有模式」章節下、標題列符合 `### ... (PREFIX)` 且
PREFIX 為已知分類前綴的表格「資料列」；表格外內容、表頭、分隔線、章節標題、
既有資料列的原始文字一律不動。

模組定位：純模組（同目錄 `allocator.py` 慣例），複用其 `_CATEGORY_DIRS`
分類映射與轉手複用的 `PATTERN_ID_RE`（SSOT: `.claude/lib/pattern_id.py`），
不在本檔複製第二份映射表或 regex。entrypoint 為薄層 `sync` 子命令
（`--dry-run` 預設印 diff 不寫檔，`--write` 才寫入），非套件入口點。

0.2.1-W3-272（併發寫入 lost-update race）：
    `sync()` 為純函式（讀 README → 掃目錄 → 算 upsert 結果，不寫檔），寫檔
    動作原本由 `main()` 的 `--write` 分支單獨執行，兩者之間無鎖——兩個並行
    process 各自呼叫 `sync()` 讀到同一份舊 README、各自算出各自的 upsert
    結果，後寫者覆蓋前寫者剛新增的列（0.2.1-W3-167 查證發現，嚴重度低於
    ID 撞號：遺失的是索引列非 pattern 檔本體，重跑 sync 可補回，但高並行
    情境仍會靜默遺失索引）。修法：新增 `sync_and_write()`，在 `_readme_lock`
    鎖保護下把「讀 → 算 → 寫」收進同一臨界區，`main()` 的 `--write` 分支
    改呼叫此函式。鎖實作比照 `allocator._allocation_lock`：`fcntl.flock`
    目錄級鎖、非 POSIX 平台優雅降級（stderr 警告 + 無鎖續行）。未直接
    import allocator 的私有 `_allocation_lock`——避免跨模組耦合到底線函式
    （非公開 API），本檔的鎖範圍（README.md 讀改寫）與 allocator 的鎖範圍
    （pattern ID 掃描/建檔）本質不同，各自持有各自的鎖檔案更清晰。

0.2.1-W3-275（reserved 佔位檔誤入索引）：
    `scan_category_rows`／`extract_row` 原本純依檔名前綴掃描，不檢查
    frontmatter `status`——`allocator.allocate_and_reserve_pattern_id`
    建立的原子配號佔位檔（`status: reserved`、標題為範本文字）若在填入
    實際內容前執行 sync，佔位標題會被同步進 README 產生空殼列。0.2.1-
    W3-271 已在 SKILL.md 補正確操作順序（先填後同步）作指引層規避，但依
    opinionated-default-design 原則，順序依賴操作紀律不是可靠防線，工具
    預設才是——`extract_row` 對 `status: reserved` 的檔案改回傳 `None`，
    `scan_category_rows` 略過並於 stderr 提示待填數量。填妥內容、移除或
    改變 `status` 後即自然納入，不需額外步驟。
"""

import argparse
import contextlib
import difflib
import re
import sys
import time
from collections import Counter
from pathlib import Path

import yaml

try:
    import fcntl  # POSIX-only；非 POSIX 平台優雅降級（見 _readme_lock）
except ImportError:  # pragma: no cover - 本機開發/CI 皆為 POSIX，缺口僅涵蓋跨平台移植
    fcntl = None

_skill_lib = Path(__file__).resolve().parent
if str(_skill_lib) not in sys.path:
    sys.path.insert(0, str(_skill_lib))

from allocator import _CATEGORY_DIRS, PATTERN_ID_RE  # noqa: E402  複用 SSOT

PLACEHOLDER = "—"

# 風險等級值正規化：frontmatter 與內文皆可能混用中英文、P1 等寫法。
_SEVERITY_MAP = {
    "高": "高",
    "high": "高",
    "中": "中",
    "medium": "中",
    "medium-high": "中",
    "低-中": "中",
    "中-低": "中",
    "p1": "中",
    "低": "低",
    "low": "低",
}

# 「基本資訊」區塊既有兩種欄位標籤寫法：風險等級 / 嚴重度。
_SEVERITY_LABEL = r"(?:風險等級|嚴重度)"
_SEVERITY_PATTERNS = (
    re.compile(rf"^\|\s*{_SEVERITY_LABEL}\s*\|\s*([^|]+?)\s*\|\s*$", re.MULTILINE),
    re.compile(rf"\*\*{_SEVERITY_LABEL}\*\*\s*[:：]\s*([^\n]+)"),
    re.compile(rf"^{_SEVERITY_LABEL}\s*[:：]\s*([^\n]+)", re.MULTILINE),
    re.compile(rf"{_SEVERITY_LABEL}(高|中|低)[:：]"),
)

_VERSION_PATTERNS = (
    re.compile(r"^\|\s*來源版本\s*\|\s*([^|]+?)\s*\|\s*$", re.MULTILINE),
    re.compile(r"\*\*來源版本\*\*\s*[:：]\s*([^\n]+)"),
    re.compile(r"^來源版本\s*[:：]\s*([^\n]+)", re.MULTILINE),
)

_SECTION_HEADING_RE = re.compile(r"^### .*\(([A-Z]+)\)\s*$")


def _first_match(patterns, text):
    """回傳多個 pattern 中最早出現（match.start() 最小）的擷取值；皆無命中回 None。"""
    best = None
    for pattern in patterns:
        match = pattern.search(text)
        if match and (best is None or match.start() < best.start()):
            best = match
    return best.group(1).strip() if best else None


def _normalize_severity(raw):
    """將風險等級原始字串正規化為單一「高／中／低」字元；無法辨識回 None。"""
    if raw is None:
        return None
    raw = str(raw)
    # 去除括號附註（如「高（每次...都可能踩）」）與換行後的補充說明。
    core = re.split(r"[（(\n]", raw, maxsplit=1)[0].strip()
    if not core:
        return None
    return _SEVERITY_MAP.get(core) or _SEVERITY_MAP.get(core.lower())


def _extract_version(body):
    """從內文擷取「來源版本」欄位值；無命中或為範本佔位字面回 None。"""
    raw = _first_match(_VERSION_PATTERNS, body)
    if raw is None:
        return None
    raw = raw.strip()
    if not raw or raw == "{發現時的版本}":
        return None
    return raw


def _extract_title(frontmatter, body, pattern_id):
    """標題來源：frontmatter `title` 優先；否則取 H1 標題行去除 ID 前綴。

    禁止由檔名推測標題（見模組 docstring）——H1 屬文件內容非檔名。
    """
    title = (frontmatter or {}).get("title")
    if title:
        return str(title).strip()
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            text = stripped[2:].strip()
            if text.upper().startswith(pattern_id.upper()):
                text = text[len(pattern_id):].lstrip(" :：-")
            text = text.strip()
            return text or None
    return None


def _parse_frontmatter(text):
    """拆出 YAML frontmatter（有則回 (dict, 內文其餘部分)，無則回 (None, 原文)）。"""
    if not text.startswith("---"):
        return None, text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return None, text
    _, fm_text, rest = parts
    try:
        data = yaml.safe_load(fm_text) or {}
    except yaml.YAMLError:
        data = {}
    if not isinstance(data, dict):
        data = {}
    return data, rest


def _slug_from_stem(stem, pattern_id):
    """從檔名 stem 去除 ID 前綴，取得可區辨同 ID 多檔的 slug。

    一 ID 對多檔（碰撞，0.2.1-W3-117）時 pattern_id 本身無法唯一識別檔案，
    slug 補上檔名中 ID 之後的描述段（如 `worktree-merge-state-loss`）。
    """
    if stem.upper().startswith(pattern_id.upper()):
        return stem[len(pattern_id):].lstrip("-") or stem
    return stem


def _is_reserved_status(frontmatter) -> bool:
    """判斷 frontmatter `status` 是否為原子配號佔位檔的 `reserved`
    （見 `allocator.allocate_and_reserve_pattern_id`，0.2.1-W3-275）。

    大小寫不敏感、允許前後空白（比照配號函式寫入 `status: reserved` 的固定
    小寫值，但不假設呼叫端一定逐字相符）。
    """
    status = (frontmatter or {}).get("status")
    return isinstance(status, str) and status.strip().lower() == "reserved"


def extract_row(path, pattern_id):
    """解析單一 error-pattern 檔案，回傳索引列資料（id/title/severity/source_version/slug）。

    風險等級刻意不讀 frontmatter `severity`——0.2.1-W3-105 查證 frontmatter
    severity 與內文「風險等級」常態性分歧且內文較準，前者於本模組視為不可信
    來源（該資料品質問題另由 0.2.1-W3-106 獨立處理）。標題不受此限，仍以
    frontmatter `title` 優先。

    `slug` 取自檔名（見 `_slug_from_stem`），供 `merge_category_table` 在一 ID
    對多檔的碰撞情境下組成複合鍵區辨各檔案（0.2.1-W3-117）。

    回傳 `None`：frontmatter `status` 為 `reserved` 時視為原子配號佔位檔
    （0.2.1-W3-275）——標題是範本文字（如「(reserved - 內容待補)」），若納入
    索引會產生空殼列。呼叫端（`scan_category_rows`）須略過 `None`；填妥內容
    並移除／改變 `status` 後，本函式自然回傳正常列，下次 sync 即納入。
    """
    text = path.read_text(encoding="utf-8")
    frontmatter, body = _parse_frontmatter(text)

    if _is_reserved_status(frontmatter):
        return None

    title = _extract_title(frontmatter, body, pattern_id) or PLACEHOLDER

    severity = _normalize_severity(_first_match(_SEVERITY_PATTERNS, body))
    severity = severity or PLACEHOLDER

    version = _extract_version(body) or PLACEHOLDER

    return {
        "id": pattern_id,
        "title": title,
        "severity": severity,
        "source_version": version,
        "slug": _slug_from_stem(path.stem, pattern_id),
    }


def scan_category_rows(error_patterns_dir):
    """掃描 `error_patterns_dir` 各分類目錄，回傳 {分類前綴: [索引列, ...]}（依檔名排序）。

    reserved 佔位檔（`extract_row` 回傳 `None`，見該函式 docstring）略過不納
    入索引列；略過數量 > 0 時輸出 stderr 提示待填數量（quality-baseline
    規則 4：非錯誤但值得可見的狀態，走 stderr 而非靜默略過，0.2.1-W3-275）。
    """
    error_patterns_dir = Path(error_patterns_dir)
    rows_by_category = {}
    reserved_count = 0
    for prefix, dirname in _CATEGORY_DIRS.items():
        cat_dir = error_patterns_dir / dirname
        rows = []
        if cat_dir.is_dir():
            for path in sorted(cat_dir.glob("*.md")):
                match = PATTERN_ID_RE.search(path.stem)
                if not match:
                    continue
                pattern_id = match.group(0).upper()
                if not pattern_id.startswith(f"{prefix}-"):
                    continue
                row = extract_row(path, pattern_id)
                if row is None:
                    reserved_count += 1
                    continue
                rows.append(row)
        rows_by_category[prefix] = rows
    if reserved_count:
        sys.stderr.write(
            f"[INFO] readme_index: 略過 {reserved_count} 個 reserved 佔位檔"
            "（原子配號待填內容，見 allocator.allocate_and_reserve_pattern_id）"
            "，填妥內容並移除／改變 status 後將自動納入索引\n"
        )
    return rows_by_category


def _escape_cell(text):
    return str(text).replace("|", r"\|")


def render_row(row, disambiguate=False):
    """渲染單一資料列；`disambiguate=True` 時 ID 儲存格附帶 `(slug)` 後綴，
    用於一 ID 對多檔的碰撞情境區辨各檔案（0.2.1-W3-117）。"""
    id_cell = row["id"]
    if disambiguate:
        slug = row.get("slug", "")
        if slug:
            id_cell = f"{id_cell} ({slug})"
    cells = (id_cell, row["title"], row["severity"], row["source_version"])
    return "| " + " | ".join(_escape_cell(c) for c in cells) + " |"


# ID 儲存格格式：`ID` 或碰撞列的 `ID (slug)`。
_ID_CELL_RE = re.compile(r"^([^\s(]+)(?:\s*\((.*)\))?$")


def _row_key_from_line(line):
    """解析既有資料列的 (id, slug) 識別鍵；非表格列或空 ID 儲存格回傳 (None, None)。

    無 `(slug)` 後綴（現行索引所有既有列皆屬此類）時 slug 為 None，代表該列
    對應哪個實體檔案無法從文字判定（模糊識別）。
    """
    stripped = line.strip()
    if not stripped.startswith("|"):
        return None, None
    cells = [c.strip() for c in stripped.strip("|").split("|")]
    if not cells or not cells[0]:
        return None, None
    match = _ID_CELL_RE.match(cells[0])
    if not match:
        return cells[0], None
    pattern_id, slug = match.groups()
    return pattern_id, (slug.strip() if slug else None)


def _is_separator_row(line):
    stripped = line.strip()
    if not stripped.startswith("|"):
        return False
    inner = stripped.strip("|")
    return bool(inner) and all(ch in "-:| \t" for ch in inner)


def merge_category_table(existing_row_lines, new_rows):
    """保守 upsert：既有列逐字原樣保留（不重新生成內容），只新增「檔案有但
    索引無」的列、移除「索引有但檔案已不存在」的死連結列。

    既有列即使欄位為佔位符也不補齊——索引可能是唯一保有該筆一級資料
    （如來源版本）的載體，補齊/覆寫等同銷毀（見模組 docstring 0.2.1-W3-105）。

    一 ID 對多檔（碰撞）以 (id, slug) 複合鍵區辨，取代舊版以 ID 建 set 的去重
    邏輯——舊邏輯對同 ID 的第二筆 new_rows 永遠判定為「已存在」而漏補（0.2.1-
    W3-117 修復目標）。無 `(slug)` 後綴的既有列（現行 372 筆索引皆屬此類）
    視為模糊識別：只要該 ID 仍有任一檔案存在即保留，避免因無法判定其對應哪個
    實體檔案而誤刪可能獨有的一級資料；帶 `(slug)` 後綴的列則以精確複合鍵判定
    存廢，碰撞雙方其一被刪時只移除對應列，不因同 ID 另一檔仍存在而漏刪。
    """
    id_counts = Counter(row["id"] for row in new_rows)
    new_composite_keys = {(row["id"], row.get("slug", "")) for row in new_rows}

    merged = []
    existing_plain_ids = set()
    existing_composite_keys = set()
    for line in existing_row_lines:
        row_id, slug = _row_key_from_line(line)
        if row_id is None:
            continue
        if slug is None:
            existing_plain_ids.add(row_id)
            if row_id in id_counts:
                merged.append(line)  # 模糊識別：ID 仍有檔案存在，保守保留
            # 否則：ID 已無任何對應檔案（死連結），捨棄該列
        else:
            existing_composite_keys.add((row_id, slug))
            if (row_id, slug) in new_composite_keys:
                merged.append(line)  # 精確識別：對應檔案仍存在，原樣保留
            # 否則：對應檔案已不存在（死連結），捨棄該列

    for row in new_rows:
        slug = row.get("slug", "")
        is_collision = id_counts[row["id"]] > 1
        if is_collision:
            if (row["id"], slug) in existing_composite_keys:
                continue  # 已有精確對應的碰撞列
            merged.append(render_row(row, disambiguate=True))  # 新檔案：附 slug 新增
        else:
            if row["id"] in existing_plain_ids or (row["id"], slug) in existing_composite_keys:
                continue  # 非碰撞：既有列（模糊或精確）已代表此檔案
            merged.append(render_row(row))  # 新檔案：以掃描結果新增一列
    return merged


def sync_readme_text(readme_text, category_rows):
    """對 README 全文做「現有模式」章節資料列的保守 upsert，其餘內容原樣保留。"""
    lines = readme_text.splitlines()
    out = []
    i = 0
    n = len(lines)
    current_category = None

    while i < n:
        line = lines[i]
        heading_match = _SECTION_HEADING_RE.match(line)
        if heading_match and heading_match.group(1) in category_rows:
            current_category = heading_match.group(1)
            out.append(line)
            i += 1
            continue
        if line.startswith("### "):
            current_category = None
            out.append(line)
            i += 1
            continue

        if current_category is not None and line.strip().startswith("| ID"):
            out.append(line)  # 表頭列
            i += 1
            if i < n and _is_separator_row(lines[i]):
                out.append(lines[i])
                i += 1
            existing_rows = []
            while i < n and lines[i].strip().startswith("|"):
                existing_rows.append(lines[i])
                i += 1
            out.extend(merge_category_table(existing_rows, category_rows[current_category]))
            current_category = None  # 表格已處理，避免同分類重複觸發
            continue

        out.append(line)
        i += 1

    result = "\n".join(out)
    if readme_text.endswith("\n"):
        result += "\n"
    return result


def sync(claude_dir):
    """計算保守 upsert 結果；純函式不寫檔，回傳 (現況, 生成後內容, unified diff 字串)。

    非原子操作：讀與算之間、算與後續寫檔之間皆無鎖保護。並行呼叫本函式後
    各自手動寫檔（如舊版 `main()` 的作法）存在 lost-update race，改用
    `sync_and_write()` 取得原子讀改寫保護（0.2.1-W3-272）。
    """
    claude_dir = Path(claude_dir)
    error_patterns_dir = claude_dir / "error-patterns"
    readme_path = error_patterns_dir / "README.md"
    original = readme_path.read_text(encoding="utf-8")

    category_rows = scan_category_rows(error_patterns_dir)
    updated = sync_readme_text(original, category_rows)

    diff = "".join(
        difflib.unified_diff(
            original.splitlines(keepends=True),
            updated.splitlines(keepends=True),
            fromfile="README.md (現況)",
            tofile="README.md (生成)",
        )
    )
    return original, updated, diff


def _warn_readme_lock_degraded(reason: str) -> None:
    """鎖降級警告（quality-baseline 規則 4：失敗必須對用戶可見，走 stderr）。"""
    sys.stderr.write(
        f"[WARNING] readme_index: {reason}；以無鎖模式寫入。並行 sync --write 期間"
        f"請改為序列執行以避免索引列遺失（0.2.1-W3-272）\n"
    )


@contextlib.contextmanager
def _readme_lock(claude_dir):
    """error-patterns 目錄級 blocking 鎖，序列化「讀 README → 算 upsert → 寫回」
    臨界區（0.2.1-W3-272）。

    Why：`sync()` 讀 README 與 `main()` 寫 README 之間原本無鎖，兩個並行
    process 各自讀到同一份舊內容、各自算出各自的新增列，後寫者覆蓋前寫者
    （lost-update race）。本鎖序列化整段 read → compute → write 序列，第二個
    呼叫者的讀取必然發生在第一個呼叫者寫入完成之後，故能看到前者新增的列。

    降級策略：`fcntl` 不可用（非 POSIX 平台）或取鎖失敗時，warn 並以無鎖
    模式續行，不阻斷單 process 呼叫——與 `allocator._allocation_lock` 同一
    降級哲學（未直接複用該函式，理由見模組 docstring）。
    """
    lock_path = Path(claude_dir) / "error-patterns" / ".readme-index.lock"
    if fcntl is None:
        _warn_readme_lock_degraded("fcntl 不可用（非 POSIX 平台）")
        yield
        return
    try:
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        lock_file = open(lock_path, "a+")
    except OSError as exc:
        _warn_readme_lock_degraded(f"lock file 開啟失敗（{exc}）")
        yield
        return
    try:
        fcntl.flock(lock_file, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(lock_file, fcntl.LOCK_UN)
        lock_file.close()


def sync_and_write(claude_dir, *, _pre_write_delay=None):
    """在鎖保護下讀 → 算 → 寫，同一臨界區內完成（0.2.1-W3-272）。

    與 `sync()` 的差異：後者是純函式，讀與寫分離、無鎖保護，並行呼叫後各自
    寫檔會 lost-update；本函式把整段 read-modify-write 收進 `_readme_lock`，
    第二個呼叫者的讀取必然發生在第一個呼叫者寫入完成之後，兩次並行 upsert
    的新增列皆會存活（見對應測試的並行驗證）。

    無變更（`diff` 為空）時不寫檔，與舊版 `main()` 行為一致，避免無謂 mtime
    變動觸發下游 watcher。

    Args:
        _pre_write_delay: 測試專用，於持鎖區間內、算完 diff 後、寫檔前插入
            延遲（秒），供併發測試建構決定性的競爭時序（正式呼叫不應傳入，
            預設 `None` 不延遲）。

    Returns:
        tuple: `(原始內容, 生成後內容, unified diff 字串)`，同 `sync()`。
    """
    claude_dir = Path(claude_dir)
    with _readme_lock(claude_dir):
        original, updated, diff = sync(claude_dir)
        if _pre_write_delay:
            time.sleep(_pre_write_delay)
        if diff:
            readme_path = claude_dir / "error-patterns" / "README.md"
            readme_path.write_text(updated, encoding="utf-8")
    return original, updated, diff


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="readme_index", description="error-pattern README 索引保守 upsert"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    sync_cmd = subparsers.add_parser(
        "sync", help="保守 upsert「現有模式」表格資料列（只新增缺漏列/移除死連結列）"
    )
    write_group = sync_cmd.add_mutually_exclusive_group()
    write_group.add_argument(
        "--dry-run", action="store_true", help="只印 diff，不寫檔（預設行為）"
    )
    write_group.add_argument("--write", action="store_true", help="寫入 README.md")
    sync_cmd.add_argument(
        "--claude-dir", default=".claude", help="claude 目錄路徑（預設 .claude）"
    )

    args = parser.parse_args(argv)
    if args.command != "sync":
        return 1

    if args.write:
        # 讀-算-寫收進同一臨界區（0.2.1-W3-272），避免併發 --write 遺失索引列。
        _original, updated, diff = sync_and_write(args.claude_dir)
        if not diff:
            print("README.md 已與現況一致，無需更新。")
            return 0
        print(diff)
        readme_path = Path(args.claude_dir) / "error-patterns" / "README.md"
        print(f"已寫入 {readme_path}")
        return 0

    # --dry-run（預設）：不寫檔，無需鎖保護。
    _original, _updated, diff = sync(args.claude_dir)
    if not diff:
        print("README.md 已與現況一致，無需更新。")
        return 0
    print(diff)
    print("\n[dry-run] 未寫入檔案，加 --write 執行實際寫入。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
