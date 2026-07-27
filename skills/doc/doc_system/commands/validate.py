"""validate 子命令 — 依 frontmatter subdomain 分派章節 schema 驗證。

目前僅實作 subdomain: data-contract 的驗證（可攜性邊界原則節 / A.1-A.6 /
B.1-B.3 / 適用判準節兩旗標非空）。非 data-contract 文件明確路由至
`/spec validate`，避免誤報。
"""

import argparse
import re
import sys
from pathlib import Path

from doc_system.commands.create import DOC_TYPE_CONFIG, _get_templates_dir
from doc_system.core.file_locator import FileLocator
from doc_system.core.frontmatter_parser import parse_frontmatter


# 錨點關鍵字：容忍章節標題的合理變體（如「A.1 表/欄位語意」「A.1：xxx」等），
# 以子字串比對 header 行是否含此關鍵字，不要求完全比對整行標題。
DATA_CONTRACT_ANCHORS: list[tuple[str, str]] = [
    ("可攜性邊界原則", r"可攜性邊界原則"),
    ("A.1", r"A\.1"),
    ("A.2", r"A\.2"),
    ("A.3", r"A\.3"),
    ("A.4", r"A\.4"),
    ("A.5", r"A\.5"),
    ("A.6", r"A\.6"),
    ("B.1", r"B\.1"),
    ("B.2", r"B\.2"),
    ("B.3", r"B\.3"),
    ("適用判準", r"適用判準"),
]

# 適用判準節內兩個必填旗標的表格列關鍵字
FLAG_ROW_KEYWORDS = ["契約文件", "migration 治理"]

# 判定「旗標未填」的佔位符樣式（模板留白），非空但仍視為未填
_PLACEHOLDER_PATTERN = re.compile(r"^\{.*\}$")


def _extract_headers(text: str) -> list[str]:
    """取出所有 Markdown 標題行（# 開頭），保留原文供錨點比對。"""
    return [line for line in text.splitlines() if line.lstrip().startswith("#")]


def _find_missing_anchors(headers: list[str]) -> list[str]:
    """回傳未在任何標題行中命中的錨點名稱清單。"""
    missing = []
    for anchor_name, pattern in DATA_CONTRACT_ANCHORS:
        if not any(re.search(pattern, header) for header in headers):
            missing.append(anchor_name)
    return missing


def _extract_section(text: str, section_pattern: str) -> str | None:
    """擷取指定章節標題後、下一個同層或更高層標題前的內容。

    以「適用判準」錨點所在標題行為起點，擷取到下一個 `##` 標題（不含）
    為止；找不到起點時回傳 None。
    """
    lines = text.splitlines()
    start = None
    start_level = None
    for i, line in enumerate(lines):
        stripped = line.lstrip()
        if stripped.startswith("#") and re.search(section_pattern, line):
            start = i
            start_level = len(stripped) - len(stripped.lstrip("#"))
            break
    if start is None:
        return None

    end = len(lines)
    for j in range(start + 1, len(lines)):
        stripped = lines[j].lstrip()
        if stripped.startswith("#"):
            level = len(stripped) - len(stripped.lstrip("#"))
            if level <= start_level:
                end = j
                break
    return "\n".join(lines[start:end])


def _flag_value_filled(row_line: str) -> bool:
    """判斷「適用判準」表格列的判定欄位是否已填寫（非空、非模板佔位符）。

    row_line 格式：`| 旗標 | 判定 | 理由 |`，取第二個 cell 作為判定欄。
    """
    cells = [cell.strip() for cell in row_line.strip().strip("|").split("|")]
    if len(cells) < 2:
        return False
    judgment = cells[1].strip("*")  # 容忍 **不要** 等強調語法
    if not judgment:
        return False
    return not _PLACEHOLDER_PATTERN.match(judgment)


def _find_empty_flags(applicability_section: str | None) -> list[str]:
    """回傳「適用判準」節中判定欄仍空白/佔位符的旗標名稱清單。"""
    if applicability_section is None:
        # 章節本身缺失時，由 _find_missing_anchors 報告，這裡不重複報
        return []

    empty = []
    for keyword in FLAG_ROW_KEYWORDS:
        row_lines = [
            line
            for line in applicability_section.splitlines()
            if line.strip().startswith("|") and keyword in line
        ]
        if not row_lines:
            empty.append(keyword)
            continue
        if not any(_flag_value_filled(line) for line in row_lines):
            empty.append(keyword)
    return empty


def _validate_data_contract(text: str) -> list[str]:
    """驗證 data-contract 章節 schema，回傳缺失項清單（空清單代表通過）。"""
    headers = _extract_headers(text)
    missing = _find_missing_anchors(headers)

    applicability_section = _extract_section(text, r"適用判準")
    empty_flags = _find_empty_flags(applicability_section)
    missing.extend(f"適用判準旗標未填：{name}" for name in empty_flags)

    return missing


def execute(args: argparse.Namespace) -> None:
    """依 frontmatter subdomain 分派章節 schema 驗證。"""
    doc_id = args.doc_id
    locator = FileLocator(FileLocator.get_project_root())

    file_path = locator.resolve_file(doc_id)
    if file_path is None:
        print(f"找不到文件: {doc_id}")
        sys.exit(2)

    frontmatter = parse_frontmatter(file_path)
    if frontmatter is None:
        print(f"無法解析 frontmatter: {file_path}")
        sys.exit(2)

    subdomain = frontmatter.get("subdomain")
    if subdomain != "data-contract":
        print(f"非 data-contract 文件，請用 /spec validate（subdomain={subdomain!r}）")
        sys.exit(0)

    with open(file_path, encoding="utf-8-sig") as f:
        text = f.read()

    missing = _validate_data_contract(text)
    if not missing:
        print(f"通過: {doc_id} 符合 data-contract 章節 schema")
        sys.exit(0)

    print(f"驗證失敗: {doc_id} 缺少以下項目")
    for item in missing:
        print(f"  - {item}")
    sys.exit(1)


def _unique_prefix_targets() -> list[tuple[str, str]]:
    """從 DOC_TYPE_CONFIG 取出去重後的 (target_dir, id_prefix) 組合。

    多個 doc type 可能共用同一 target_dir + id_prefix（如 spec 與
    data-contract 皆為 docs/spec + SPEC），去重避免重複掃描同一檔案。
    """
    seen: set[tuple[str, str]] = set()
    for config in DOC_TYPE_CONFIG.values():
        seen.add((config["target_dir"], config["id_prefix"]))
    return sorted(seen)


def _fixed_name_exemptions() -> set[str]:
    """回傳框架約定的固定命名文件檔名清單（豁免檔名慣例檢查）。

    來源與 `templates/` 下的 `*-spec-template.md` 命名對應，而非另手維護
    獨立名單——獨立名單會重演配號器 allowlist 判準與成員脫節問題
    （見 ARCH-BAL-003）。命名規則：模板檔 `{name}-template.md` 對應的
    固定命名文件即為 `{name}.md`（如 `component-library-spec-template.md`
    -> `component-library-spec.md`）。

    這類文件由 doc SKILL.md 明文指示以 `cp` 建立（非透過 `doc create`
    配號流程），且被其他 SKILL.md（如 version-bootstrap）直接以固定路徑
    引用，因此刻意不進 `{PREFIX}-{數字}` 編號空間。
    """
    templates_dir = _get_templates_dir()
    if not templates_dir.is_dir():
        return set()

    exemptions = set()
    for template_file in templates_dir.glob("*-spec-template.md"):
        fixed_name = template_file.name.removesuffix("-template.md") + ".md"
        exemptions.add(fixed_name)
    return exemptions


def _check_filename_conventions(project_root: Path) -> tuple[list[str], list[str]]:
    """掃描各 doc type 目錄，回傳 (違規訊息清單, 已豁免檔案清單)。

    配號器 `_next_id`（create.py）僅辨識以 `{PREFIX}-{數字}` 開頭的檔名，
    不符此慣例的檔案對配號器隱形，會導致號碼重複配發（book W11-004）。
    本檢查讓這類檔案顯性化：
    - 檔名不符 `^{PREFIX}-\\d+` 前綴 -> 配號器盲區（框架約定固定命名文件除外）
    - 檔名前綴 ID 與 frontmatter id 不一致 -> 潛在誤植

    豁免項不可靜默略過（本命令存在的理由正是防止靜默盲區），故以第二個
    回傳值顯性回報，由呼叫端以 INFO 級列出。
    """
    violations: list[str] = []
    exempted: list[str] = []
    fixed_name_exemptions = _fixed_name_exemptions()

    for target_dir_rel, prefix in _unique_prefix_targets():
        target_dir = Path(project_root) / target_dir_rel
        if not target_dir.exists():
            continue

        pattern = re.compile(rf"^{prefix}-(\d+)", re.IGNORECASE)
        for item in sorted(target_dir.rglob("*.md")):
            if item.name.endswith("-template.md"):
                continue

            match = pattern.match(item.stem)
            if match is None:
                if item.name in fixed_name_exemptions:
                    exempted.append(str(item))
                    continue
                violations.append(
                    f"檔名不符慣例（配號器盲區）: {item} "
                    f"（應以 {prefix}-數字 開頭）"
                )
                continue

            frontmatter = parse_frontmatter(str(item))
            if frontmatter is None:
                continue
            frontmatter_id = frontmatter.get("id")
            filename_id = f"{prefix}-{match.group(1)}"
            if frontmatter_id and str(frontmatter_id) != filename_id:
                violations.append(
                    f"frontmatter id 與檔名不一致: {item} "
                    f"（檔名={filename_id}, frontmatter.id={frontmatter_id}）"
                )

    return violations, exempted


def execute_filenames(args: argparse.Namespace) -> None:
    """掃描 doc type 目錄，驗證檔名慣例與 frontmatter id 一致性。"""
    project_root = FileLocator.get_project_root()
    violations, exempted = _check_filename_conventions(project_root)

    if exempted:
        print(f"INFO: 已豁免 {len(exempted)} 項（框架約定固定命名文件）")
        for item in exempted:
            print(f"  - {item}")

    if not violations:
        print("通過: 所有文件檔名符合配號器慣例")
        sys.exit(0)

    print("驗證失敗: 發現檔名慣例違規")
    for item in violations:
        print(f"  - {item}")
    sys.exit(1)
