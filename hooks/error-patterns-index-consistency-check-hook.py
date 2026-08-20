#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml"]
# ///
"""
Error Patterns Index Consistency Check Hook - README 索引與目錄一致性檢查

觸發時機: SessionStart
模式: 提醒為主（不阻擋操作，比照 file-size-guardian-hook.py）

掃描 .claude/error-patterns/ 各分類目錄的實際檔案清單，比對 README.md
「現有模式」章節各分類表格的 ID 欄位，做四項比對：

1. 目錄 -> 索引：檔名推出的 ID 不在 README（新模式未入索引）
2. 索引 -> 目錄：README 列出的 ID 無對應檔案（過時條目）
3. 檔案 -> ID 唯一性：同一 ID 對應 2+ 個檔案（ID 碰撞，索引無法完整表達）
4. related 雙向性（限同批次）：A 的 frontmatter related（或 related_patterns）
   含 B、B 未回指 A，且兩者 created 日期相差在 SAME_BATCH_WINDOW_DAYS 天內
   （單向引用，讀者從 B 進入時無從得知 A 存在）

第 3 項是本 hook 的關鍵設計約束：只做 1、2 會複製既有盲區——多個檔案共用
同一 ID 前綴時，ID 集合差集為零但實質上有檔案完全不在索引涵蓋範圍內。

第 4 項為純增量：collect_dir_id_map 本來就掃過全部檔案，本項僅額外讀取
frontmatter 解析 related 欄位，不新增掃描範圍。單向引用列 WARNING 不阻擋。

**範圍限縮為同批次（PM 裁決，非原始設計）**：related 欄位在現行 schema 下
承載兩種無法區分的語意——「引註」（新模式引用既有基礎模式做論證依據，單向
合法）與「姊妹關係」（同批次產生、互為對照，應雙向）。全量掃描實測顯示，
若不分辨兩者，全語料庫命中 228 組「單向」，其中絕大多數是引註（例如某基礎
模式被 20+ 則模式引用，要求它逐一回指沒有意義）。故本檢查僅在兩則 created
日期相差 <= SAME_BATCH_WINDOW_DAYS 天時才視為同批次姊妹關係並列入單向引用；
相差更遠或任一方缺 created 欄位一律視為引註不告警。此判準的誤判方向刻意
偏向漏報（放過同批次的引註、跨批次的真姊妹關係）而非誤報（噪音牆讓其他
hook 的訊息被擠出視線，等同於「訊號存在但沒被看到」）。WARNING 輸出另設
行數上限（ONE_WAY_RELATED_DISPLAY_CAP），超出以「另有 N 組未列出」收尾，
避免單一檢查佔滿 SessionStart 共用輸出預算。

來源: error-patterns README 索引與目錄一致性機械檢查（實測：曾發生 148/379 筆漂移）；
related 雙向性擴充來源: 審查發現 6 組單向引用，掛載點已存在（本 hook 每次
SessionStart 皆掃過全部 error-pattern 檔案），加雙向性檢查成本近零；範圍限縮為
同批次（7 天窗口）與行數上限為全量掃描後的 PM 裁決結果
"""

import re
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))
from lib import setup_hook_logging, run_hook_safely, get_project_root

# error-patterns 底下的分類目錄（排除 README.md 本身）
CATEGORY_DIRS = [
    "test",
    "documentation",
    "architecture",
    "implementation",
    "code-quality",
    "process-compliance",
    "process",
]

# 檔名 ID 抽取：前綴 + 可選中段（大寫字母/數字，破折號分隔）+ 數字序號。
# ID 後須緊接 slug 分隔符「-」或直接是副檔名邊界「.md」結尾——後者對應
# allocator.allocate_and_reserve_pattern_id 建立的無 slug 佔位檔（`{id}.md`，
# 見該函式與 SKILL.md「佔位檔檔名（無 slug）即 pattern_id」的既有慣例，
# 建立端為權威，見 tool-output-trust 規則 6）。無此分支時，佔位檔會被
# extract_filename_id 判為無法辨識而歸入 UNRECOGNIZED，使其 ID 從
# dir_ids 集合消失，讀作「README 有列出但目錄無對應檔案」的過時條目誤判
# （PC-BAL-040 入庫實證）。
# 命中範例：PC-166-slug.md / PC-BAL-001-slug.md / IMP-V1-006.md（無 slug）
FILENAME_ID_PATTERN = re.compile(
    r"^(?P<id>(?:PC|IMP|DOC|ARCH|TEST|PROC|CQ)-(?:[A-Z0-9]+-)?[0-9]+)(?:-|\.md$)"
)

# README.md 表格列 ID 抽取：| ID | 標題 | 風險 | 來源版本 |
# ID 欄允許尾隨消歧括號註記（如「PC-010 (pm-skipped-checkpoint-after-ticket-complete)」，
# 見 process-compliance/PC-*-* 碰撞條目），故 ID 後至下個 `|` 前的內容不強制為空。
README_ROW_PATTERN = re.compile(
    r"^\|\s*((?:PC|IMP|DOC|ARCH|TEST|PROC|CQ)-(?:[A-Z0-9]+-)?[0-9]+)(?:[^|]*)\|",
    re.MULTILINE,
)

# 凍結登記表（.claude/methodologies/error-pattern-numbering-methodology.md）
# 章節錨點與資料列格式。用章節標題定位而非行號，避免凍結項增減造成行號位移。
FROZEN_SECTION_HEADING = "### 已知 legacy intra-dir 重號（凍結保留，不重編）"
FROZEN_TABLE_ROW_PATTERN = re.compile(
    r"^\|\s*((?:PC|IMP|DOC|ARCH|TEST|PROC|CQ)-(?:[A-Z0-9]+-)?[0-9]+)\s*"
    r"\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*$",
    re.MULTILINE,
)


def extract_filename_id(filename: str) -> str:
    """從檔名抽取 error-pattern ID，無法辨識時回傳空字串。"""
    match = FILENAME_ID_PATTERN.match(filename)
    return match.group("id") if match else ""


def collect_dir_id_map(error_patterns_root: Path) -> dict:
    """掃描各分類目錄，回傳 {id: [rel_path, ...]}（供唯一性比對用）。"""
    id_map: dict = {}
    for category in CATEGORY_DIRS:
        category_path = error_patterns_root / category
        if not category_path.is_dir():
            continue
        for file_path in sorted(category_path.glob("*.md")):
            if file_path.name == "README.md":
                continue
            file_id = extract_filename_id(file_path.name)
            rel = f"{category}/{file_path.name}"
            if not file_id:
                # 抽取失敗視為未分類，仍記錄以便 WARNING 呈現（key 用檔名本身避免碰撞遮蔽）
                id_map.setdefault(f"UNRECOGNIZED:{rel}", []).append(rel)
                continue
            id_map.setdefault(file_id, []).append(rel)
    return id_map


# related 欄位內 ID 抽取：與 FILENAME_ID_PATTERN 同前綴集合，但不要求緊接
# slug 分隔符或行尾——related 欄位內容可能是 inline flow（`[PC-050, PC-062]`）
# 或 block list（`- PC-055`），ID 前後常接逗號、方括號、換行等分隔符。
RELATED_ID_PATTERN = re.compile(
    r"(?:PC|IMP|DOC|ARCH|TEST|PROC|CQ)-(?:[A-Z0-9]+-)?[0-9]+"
)

# 既有 error-pattern 對「相關項目」欄位有兩種命名習慣（存量統計零重疊，
# 互斥使用），合併掃描以涵蓋兩者。
RELATED_FIELD_NAMES = ("related", "related_patterns")

# frontmatter 區塊抽取：開頭 `---`、結尾 `---`，取兩者之間的文字。
FRONTMATTER_BLOCK_PATTERN = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)

# related 欄位值的終止點：下一個 top-level YAML key（欄位名以字母/底線開頭，
# 無縮排，緊接冒號）。block list 項目（`- ID` 或 `  - ID`）皆不匹配此樣式，
# 故不會被誤判為欄位終止。
_NEXT_TOP_LEVEL_KEY = r"^[A-Za-z_]\S*:"

# created 欄位日期抽取：`created: 2026-08-18`（允許可選引號）。
CREATED_DATE_PATTERN = re.compile(
    r"^created:\s*['\"]?(\d{4}-\d{2}-\d{2})['\"]?\s*$", re.MULTILINE
)

# 同批次判定窗口（天）：兩則的 created 日期相差在此範圍內才視為同批次姊妹
# 關係並要求雙向；超出視為引註，單向合法。PM 裁決值（見本檔頭 docstring）。
SAME_BATCH_WINDOW_DAYS = 7

# related 單向引用 WARNING 輸出行數上限；超出以「另有 N 組未列出」收尾，
# 避免單一檢查佔滿 SessionStart 共用輸出預算。PM 裁決值。
ONE_WAY_RELATED_DISPLAY_CAP = 10


def extract_frontmatter_text(content: str) -> str:
    """抽取檔案內容開頭的 YAML frontmatter 區塊文字（不含前後 `---` 界線）。

    無 frontmatter（如測試 fixture 的 `# stub` 內容）時回傳空字串。
    """
    match = FRONTMATTER_BLOCK_PATTERN.match(content)
    return match.group(1) if match else ""


def parse_related_field(frontmatter_text: str) -> set:
    """從 frontmatter 文字解析 related / related_patterns 欄位的 ID 集合。

    支援 inline flow（`related: [PC-050, PC-062]`）與 block list
    （`related:` 換行後接 `- PC-055`，0 或 2 空格縮排皆可）兩種既有 YAML
    寫法。欄位內非 pattern-ID 格式的項目（如非 error-pattern 命名慣例的
    識別符、方法論 slug `hook-system-design`）不匹配 RELATED_ID_PATTERN，
    自然被忽略——雙向性檢查只對「確實是 error-pattern 的引用」有意義。
    """
    ids: set = set()
    for field_name in RELATED_FIELD_NAMES:
        match = re.search(
            rf"^{field_name}:(.*?)(?={_NEXT_TOP_LEVEL_KEY}|\Z)",
            frontmatter_text,
            re.MULTILINE | re.DOTALL,
        )
        if match:
            ids.update(RELATED_ID_PATTERN.findall(match.group(1)))
    return ids


def extract_created_date(frontmatter_text: str):
    """從 frontmatter 文字解析 created 欄位日期，回傳 date 物件；缺失或格式
    不符時回傳 None（呼叫端須將 None 視為「無法判定批次」，不得臆測日期）。
    """
    match = CREATED_DATE_PATTERN.search(frontmatter_text)
    if not match:
        return None
    try:
        return datetime.strptime(match.group(1), "%Y-%m-%d").date()
    except ValueError:
        return None


def collect_related_map(error_patterns_root: Path) -> dict:
    """掃描各分類目錄，回傳 {id: (related_ids_set, created_date_or_None, rel_path)}。

    與 collect_dir_id_map 共用同一目錄遍歷範圍，額外讀取檔案內容解析
    frontmatter 的 related 與 created 欄位。無法辨識 ID 或讀檔失敗的檔案略過
    （fail-open，不影響其餘檔案的檢查）。
    """
    related_map: dict = {}
    for category in CATEGORY_DIRS:
        category_path = error_patterns_root / category
        if not category_path.is_dir():
            continue
        for file_path in sorted(category_path.glob("*.md")):
            if file_path.name == "README.md":
                continue
            file_id = extract_filename_id(file_path.name)
            if not file_id:
                continue
            try:
                content = file_path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            frontmatter_text = extract_frontmatter_text(content)
            related_ids = parse_related_field(frontmatter_text)
            created = extract_created_date(frontmatter_text)
            rel = f"{category}/{file_path.name}"
            related_map[file_id] = (related_ids, created, rel)
    return related_map


def check_related_bidirectional(related_map: dict) -> list:
    """檢查同批次 related 雙向性，回傳單向引用清單 [(from_id, to_id, from_rel), ...]。

    related 欄位承載兩種無法區分的語意——引註（單向合法）與姊妹關係（同批次
    產生、應雙向）。本函式採機械可判定的近似：僅當兩則 created 日期相差在
    SAME_BATCH_WINDOW_DAYS 天內才視為同批次姊妹關係並列入單向引用；相差更遠
    或任一方缺 created 欄位（extract_created_date 回傳 None）一律跳過不告警
    ——此為 PM 裁決的刻意選擇，誤判方向偏向漏報而非誤報（見本檔頭 docstring）。

    僅檢查 to_id 本身存在於 related_map（即確實是本索引涵蓋的 error-pattern，
    而非其他引用形態）；自我引用不計。回傳結果依 (from_id, to_id) 排序，
    供輸出穩定。
    """
    one_way = []
    for from_id, (related_ids, from_created, from_rel) in related_map.items():
        for to_id in related_ids:
            if to_id == from_id:
                continue
            if to_id not in related_map:
                continue
            back_related, to_created, _ = related_map[to_id]
            if from_id in back_related:
                continue
            if from_created is None or to_created is None:
                continue
            if abs((from_created - to_created).days) > SAME_BATCH_WINDOW_DAYS:
                continue
            one_way.append((from_id, to_id, from_rel))
    return sorted(one_way)


def extract_slug(rel_path: str, file_id: str) -> str:
    """從相對路徑抽取檔名 slug（ID 前綴與副檔名去除後的部分）。"""
    filename = Path(rel_path).name
    prefix = f"{file_id}-"
    if filename.startswith(prefix) and filename.endswith(".md"):
        return filename[len(prefix):-len(".md")]
    return filename[:-len(".md")] if filename.endswith(".md") else filename


def parse_frozen_registry(methodology_path: Path):
    """解析凍結登記表，回傳 (registry, error_reason)。

    registry 格式：{id: {slug_a, slug_b}}；解析失敗時 registry 為 None，
    error_reason 說明失敗原因，呼叫端須 fail-open（全部歸 WARNING）。
    定位方式使用章節標題錨點，不用行號，避免凍結項增減造成行號位移。
    """
    try:
        text = methodology_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return None, f"無法讀取凍結表檔案 {methodology_path}: {exc}"

    heading_index = text.find(FROZEN_SECTION_HEADING)
    if heading_index == -1:
        return None, f"找不到凍結表章節錨點「{FROZEN_SECTION_HEADING}」"

    section_start = heading_index + len(FROZEN_SECTION_HEADING)
    next_heading = text.find("\n### ", section_start)
    if next_heading == -1:
        next_heading = text.find("\n## ", section_start)
    section_text = text[section_start:] if next_heading == -1 else text[section_start:next_heading]

    rows = FROZEN_TABLE_ROW_PATTERN.findall(section_text)
    if not rows:
        return None, "凍結表章節內找不到任何資料列"

    registry: dict = {}
    for file_id, slug_a, slug_b in rows:
        registry[file_id] = {slug_a, slug_b}
    return registry, None


def collect_readme_ids(readme_path: Path) -> set:
    """解析 README.md「現有模式」表格列出的 ID 集合。"""
    try:
        text = readme_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return set()
    return set(README_ROW_PATTERN.findall(text))


def compare(dir_id_map: dict, readme_ids: set, frozen_registry=None) -> dict:
    """三項比對，回傳結構化結果。

    frozen_registry 為 None 時（未提供或解析失敗）採 fail-open：所有碰撞歸
    WARNING（保持既有行為）。提供時，碰撞 ID 若已登記且檔案 slug 組成與登記
    完全相符，歸入 registered_collisions（INFO）；未登記或組成不符者仍為
    WARNING（collisions），且與登記不符的情形不可被靜默吞掉。
    """
    dir_ids = {k for k in dir_id_map if not k.startswith("UNRECOGNIZED:")}
    unrecognized = [v[0] for k, v in dir_id_map.items() if k.startswith("UNRECOGNIZED:")]

    missing_in_readme = sorted(dir_ids - readme_ids)  # 比對 1：目錄有、README 無
    stale_in_readme = sorted(readme_ids - dir_ids)  # 比對 2：README 有、目錄無

    raw_collisions = {
        file_id: paths
        for file_id, paths in dir_id_map.items()
        if not file_id.startswith("UNRECOGNIZED:") and len(paths) > 1
    }  # 比對 3：同一 ID 對應 2+ 檔案

    collisions = {}
    registered_collisions = {}
    for file_id, paths in raw_collisions.items():
        if (
            frozen_registry is not None
            and file_id in frozen_registry
            and len(paths) == 2
            and {extract_slug(p, file_id) for p in paths} == frozen_registry[file_id]
        ):
            registered_collisions[file_id] = paths
        else:
            collisions[file_id] = paths

    return {
        "missing_in_readme": missing_in_readme,
        "stale_in_readme": stale_in_readme,
        "collisions": collisions,
        "registered_collisions": registered_collisions,
        "unrecognized": unrecognized,
    }


def format_report(result: dict, frozen_error: str = None) -> str:
    """組裝 stderr 文字，僅在有發現或凍結表解析失敗時輸出對應段落。"""
    lines = []
    missing = result["missing_in_readme"]
    stale = result["stale_in_readme"]
    collisions = result["collisions"]
    registered_collisions = result.get("registered_collisions", {})
    unrecognized = result["unrecognized"]
    one_way_related = result.get("one_way_related", [])

    # frozen_error 只在真的有碰撞需要分流判斷時才報出，避免無碰撞情境下的無意義雜訊
    show_frozen_error = bool(frozen_error and collisions)

    if not (
        missing or stale or collisions or unrecognized
        or registered_collisions or show_frozen_error or one_way_related
    ):
        return ""

    lines.append("=" * 60)
    lines.append("[Error Patterns Index Consistency] README 索引一致性檢查")
    lines.append("=" * 60)

    if show_frozen_error:
        lines.append(f"\n[WARNING] 凍結登記表解析失敗，已 fail-open 為全部碰撞列 WARNING：{frozen_error}")

    if missing:
        lines.append(f"\n[WARNING] 目錄有 {len(missing)} 個 ID 未列入 README.md：")
        for file_id in missing:
            lines.append(f"  {file_id}")

    if stale:
        lines.append(f"\n[WARNING] README.md 列出 {len(stale)} 個 ID 無對應檔案（過時條目）：")
        for file_id in stale:
            lines.append(f"  {file_id}")

    if collisions:
        lines.append(
            f"\n[WARNING] {len(collisions)} 個 ID 碰撞未登記於凍結表或與登記組成不符（索引無法完整表達）："
        )
        for file_id, paths in sorted(collisions.items()):
            lines.append(f"  {file_id}:")
            for path in paths:
                lines.append(f"    {path}")

    if registered_collisions:
        lines.append(f"\n[INFO] {len(registered_collisions)} 個 ID 碰撞已登記於凍結表（政策允許，非新發現）：")
        for file_id, paths in sorted(registered_collisions.items()):
            lines.append(f"  {file_id}:")
            for path in paths:
                lines.append(f"    {path}")

    if unrecognized:
        lines.append(f"\n[INFO] {len(unrecognized)} 個檔案無法抽取 ID（檔名格式不符規範）：")
        for path in unrecognized:
            lines.append(f"  {path}")

    if one_way_related:
        lines.append(
            f"\n[WARNING] {len(one_way_related)} 組 related 單向引用（不阻擋，建議補回指）："
        )
        for from_id, to_id, from_rel in one_way_related[:ONE_WAY_RELATED_DISPLAY_CAP]:
            lines.append(f"  {from_id} -> {to_id}（{from_rel} 未被 {to_id} 回指）")
        remaining = len(one_way_related) - ONE_WAY_RELATED_DISPLAY_CAP
        if remaining > 0:
            lines.append(f"  ...另有 {remaining} 組未列出")

    lines.append("=" * 60)
    return "\n".join(lines)


def main() -> int:
    logger = setup_hook_logging("error-patterns-index-consistency-check")
    root = get_project_root()

    if not root:
        logger.info("get_project_root() 回傳空值，略過檢查（非標準情境）")
        return 0

    root = Path(root)
    error_patterns_root = root / ".claude" / "error-patterns"
    readme_path = error_patterns_root / "README.md"

    if not error_patterns_root.is_dir() or not readme_path.is_file():
        logger.info("error-patterns 目錄或 README.md 不存在，略過檢查")
        return 0

    methodology_path = root / ".claude" / "methodologies" / "error-pattern-numbering-methodology.md"

    try:
        dir_id_map = collect_dir_id_map(error_patterns_root)
        readme_ids = collect_readme_ids(readme_path)
        frozen_registry, frozen_error = parse_frozen_registry(methodology_path)
        if frozen_error:
            logger.warning("凍結登記表解析失敗，fail-open 為全部碰撞列 WARNING：%s", frozen_error)
        result = compare(dir_id_map, readme_ids, frozen_registry)

        related_map = collect_related_map(error_patterns_root)
        result["one_way_related"] = check_related_bidirectional(related_map)

        report = format_report(result, frozen_error)

        if report:
            sys.stderr.write(report + "\n")
        if result["missing_in_readme"] or result["stale_in_readme"] or result["collisions"]:
            logger.warning(
                "索引不一致：missing=%d stale=%d collisions=%d registered_collisions=%d unrecognized=%d",
                len(result["missing_in_readme"]),
                len(result["stale_in_readme"]),
                len(result["collisions"]),
                len(result["registered_collisions"]),
                len(result["unrecognized"]),
            )
        else:
            logger.info(
                "README 索引與目錄一致，無缺漏/過時/未登記碰撞（已登記重號=%d）",
                len(result["registered_collisions"]),
            )
        if result["one_way_related"]:
            logger.warning("related 單向引用：%d 組", len(result["one_way_related"]))
        else:
            logger.info("related 雙向性檢查：無單向引用")
    except Exception as exc:  # noqa: BLE001 — 失敗安全：檢查異常不阻擋 session
        sys.stderr.write(f"[error-patterns-index-consistency-check] 檢查異常: {exc}\n")
        logger.error("檢查異常: %s", exc, exc_info=True)

    return 0


if __name__ == "__main__":
    sys.exit(run_hook_safely(main, "error-patterns-index-consistency-check"))
