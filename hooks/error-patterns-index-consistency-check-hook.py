#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
Error Patterns Index Consistency Check Hook - README 索引與目錄一致性檢查

觸發時機: SessionStart
模式: 提醒為主（不阻擋操作，比照 file-size-guardian-hook.py）

掃描 .claude/error-patterns/ 各分類目錄的實際檔案清單，比對 README.md
「現有模式」章節各分類表格的 ID 欄位，做三項比對：

1. 目錄 -> 索引：檔名推出的 ID 不在 README（新模式未入索引）
2. 索引 -> 目錄：README 列出的 ID 無對應檔案（過時條目）
3. 檔案 -> ID 唯一性：同一 ID 對應 2+ 個檔案（ID 碰撞，索引無法完整表達）

第 3 項是本 hook 的關鍵設計約束：只做 1、2 會複製既有盲區——多個檔案共用
同一 ID 前綴時，ID 集合差集為零但實質上有檔案完全不在索引涵蓋範圍內。

來源: error-patterns README 索引與目錄一致性機械檢查（實測：曾發生 148/379 筆漂移）
"""

import re
import sys
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

# 檔名 ID 抽取：前綴 + 可選中段（大寫字母/數字，破折號分隔）+ 數字序號
# 命中範例：PC-166 / PC-BAL-001 / IMP-V1-006 / PC-SCLK-004 / TEST-MON-001
FILENAME_ID_PATTERN = re.compile(
    r"^(?P<id>(?:PC|IMP|DOC|ARCH|TEST|PROC|CQ)-(?:[A-Z0-9]+-)?[0-9]+)-"
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

    # frozen_error 只在真的有碰撞需要分流判斷時才報出，避免無碰撞情境下的無意義雜訊
    show_frozen_error = bool(frozen_error and collisions)

    if not (missing or stale or collisions or unrecognized or registered_collisions or show_frozen_error):
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
    except Exception as exc:  # noqa: BLE001 — 失敗安全：檢查異常不阻擋 session
        sys.stderr.write(f"[error-patterns-index-consistency-check] 檢查異常: {exc}\n")
        logger.error("檢查異常: %s", exc, exc_info=True)

    return 0


if __name__ == "__main__":
    sys.exit(run_hook_safely(main, "error-patterns-index-consistency-check"))
