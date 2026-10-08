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
from doc_system.core.tracking_schema import (
    EVT_REQUIRED_FIELDS,
    NON_DOMAIN_PATHS_FILE,
    NonDomainPathsFormatError,
    check_path_pattern_format,
    find_non_domain_path_problems,
    read_non_domain_paths,
    read_path_patterns,
    extract_bundle_dependencies,
    find_dangling_bundle_dependencies,
    find_missing_completeness_fields,
    find_missing_path_patterns,
    find_path_pattern_problems,
    find_undeclared_domain_names,
)
from doc_system.core.uc_registry import _extract_structured_flow_steps


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

# EVT 型別必填 frontmatter 欄位改讀 tracking_schema.EVT_REQUIRED_FIELDS
# （單一 SSOT，見 #99 第三項裁決：完整性集合語意為「欄位必須存在，值可
# 為 null 或 []」）。category 值域維持本檔獨立常數，不在本票範圍調整。
EVENT_VALID_CATEGORIES = ("domain_event", "process_event")


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


def _validate_event(frontmatter: dict) -> list[str]:
    """驗證 EVT frontmatter，回傳缺失項清單（空清單代表通過）。

    完整性（欄位存在）與值非空是兩條獨立規則（#99 第三項裁決）：
    `find_missing_completeness_fields` 只判斷欄位是否存在，id/name/
    canonical_name/category 這四個識別/顯示欄位額外要求值非空——這是
    EVT 型別的附加規則，不屬圖譜 schema 的通用完整性語意（該語意允許
    FlowStep 等型別的欄位為 null/[]）。producers/consumers 同屬附加規則，
    是本型別的核心價值：缺任一端代表事件的發送方或接收方未被記錄，交叉
    驗證正是為了在文件層攔截這類缺口。
    """
    missing: list[str] = []

    missing_fields = find_missing_completeness_fields(EVT_REQUIRED_FIELDS, frontmatter)
    missing.extend(f"缺少必填欄位: {field}" for field in sorted(missing_fields))

    empty_fields = sorted(
        field
        for field in EVT_REQUIRED_FIELDS - missing_fields
        if not frontmatter.get(field)
    )
    missing.extend(f"必填欄位值不可為空: {field}" for field in empty_fields)

    category = frontmatter.get("category")
    if category and category not in EVENT_VALID_CATEGORIES:
        missing.append(
            f"category 值不合法: {category}（須為 {' 或 '.join(EVENT_VALID_CATEGORIES)}）"
        )

    if not frontmatter.get("producers"):
        missing.append("缺少 producer：EVT 必須至少一個 producer")
    if not frontmatter.get("consumers"):
        missing.append("缺少 consumer：EVT 必須至少一個 consumer")

    return missing


def _execute_event_validation(project_root: str, doc_id: str) -> None:
    """EVT 型別的 validate 分派路徑（獨立於 data-contract 的章節錨點驗證）。"""
    file_path_str = FileLocator(project_root).find_event(doc_id)
    if file_path_str is None:
        print(f"找不到文件: {doc_id}")
        sys.exit(2)
    file_path = Path(file_path_str)

    frontmatter = parse_frontmatter(str(file_path))
    if frontmatter is None:
        print(f"無法解析 frontmatter: {file_path}")
        sys.exit(2)

    missing = _validate_event(frontmatter)
    if not missing:
        print(f"通過: {doc_id} 符合 EVT schema")
        sys.exit(0)

    print(f"驗證失敗: {doc_id} 缺少以下項目")
    for item in missing:
        print(f"  - {item}")
    sys.exit(1)


def _scan_domain_bundles(project_root: str) -> dict[str, tuple[Path, dict]]:
    """掃描所有 domain-map 檔，回傳 bundle id → (實際載體路徑, frontmatter)。"""
    root = Path(project_root)
    paths = [root / "docs" / "domain-map.md", *sorted(root.glob("docs/spec/*/domain-map.md"))]
    bundles: dict[str, tuple[Path, dict]] = {}
    for path in paths:
        if not path.is_file():
            continue
        frontmatter = parse_frontmatter(str(path))
        if frontmatter and frontmatter.get("id"):
            bundles[str(frontmatter["id"])] = (path, frontmatter)
    return bundles


def _load_domain_bundles(project_root: str) -> dict[str, dict]:
    """回傳 bundle id → frontmatter。"""
    return {bid: fm for bid, (_, fm) in _scan_domain_bundles(project_root).items()}


def _find_duplicate_domains(project_root: str) -> dict[str, list[Path]]:
    """回傳 domain 值 → 宣告該值的 bundle 載體路徑（僅含出現兩次以上者）。"""
    by_domain: dict[str, list[Path]] = {}
    for path, fm in _scan_domain_bundles(project_root).values():
        if fm.get("domain"):
            by_domain.setdefault(str(fm["domain"]), []).append(path)
    return {d: paths for d, paths in by_domain.items() if len(paths) > 1}


def _format_duplicate_domain(domain: str, paths: list[Path]) -> str:
    return f"domain {domain!r} 被多份 DomainBundle 宣告: " + "、".join(str(p) for p in paths)


def _find_reachable_cycles(graph: dict[str, list[str]], start: str) -> list[list[str]]:
    """自 start 深度優先走訪，回傳遇到的環（每個環為首尾同節點的路徑）。

    只沿 graph 內存在的節點走；指向不存在節點的邊不屬於環，由其他檢查負責。
    """
    cycles: list[list[str]] = []
    done: set[str] = set()

    def visit(node: str, trail: list[str]) -> None:
        if node in trail:
            cycles.append(trail[trail.index(node):] + [node])
            return
        if node in done or node not in graph:
            return
        for target in graph[node]:
            visit(target, trail + [node])
        done.add(node)

    visit(start, [])
    return cycles


def _find_bundle_dependency_cycles(bundles: dict[str, dict], doc_id: str) -> list[str]:
    """回傳自 doc_id 可達的 depends_on_bundles 成環路徑（空清單代表通過）。"""
    graph = {bid: extract_bundle_dependencies(fm) for bid, fm in bundles.items()}
    return [" -> ".join(cycle) for cycle in _find_reachable_cycles(graph, doc_id)]


def _execute_domain_bundle_validation(project_root: str, doc_id: str) -> None:
    """DomainBundle 的 validate 分派路徑：depends_on_bundles 出邊目標須存在且不成環。"""
    bundles = _load_domain_bundles(project_root)
    if doc_id not in bundles:
        print(f"找不到文件: {doc_id}")
        sys.exit(2)

    targets = find_dangling_bundle_dependencies(bundles).get(doc_id, [])
    cycles = _find_bundle_dependency_cycles(bundles, doc_id)
    path_problems = _collect_path_pattern_problems(project_root, bundles, doc_id)
    own_path = _scan_domain_bundles(project_root)[doc_id][0]
    duplicates = [
        _format_duplicate_domain(d, paths)
        for d, paths in _find_duplicate_domains(project_root).items()
        if own_path in paths
    ]
    if not targets and not cycles and not path_problems and not duplicates:
        print(f"通過: {doc_id} 的 depends_on_bundles 出邊、path_patterns 與 domain 唯一性皆有效")
        sys.exit(0)

    if duplicates:
        print(f"驗證失敗: {doc_id} 的 domain 與其他 DomainBundle 重複")
        for item in duplicates:
            print(f"  - {item}")

    if cycles:
        print(f"驗證失敗: {doc_id} 的 depends_on_bundles 成環")
        for item in cycles:
            print(f"  - {item}")
    if targets:
        print(f"驗證失敗: {doc_id} 的 depends_on_bundles 指向不存在的 bundle")
        for target in targets:
            print(f"  - {target}")
    if path_problems:
        print(f"驗證失敗: {doc_id} 的 path_patterns 無效")
        for item in path_problems:
            print(f"  - {item}")
    sys.exit(1)


def _collect_path_pattern_problems(project_root: str, bundles: dict[str, dict], doc_id: str) -> list[str]:
    """回傳該 bundle 的 path_patterns 問題（格式、重複、路徑不存在），含檔案位置。"""
    root = Path(project_root)
    frontmatter = bundles[doc_id]
    location = str(_scan_domain_bundles(project_root)[doc_id][0])
    problems = find_path_pattern_problems(bundles).get(doc_id, [])
    missing = find_missing_path_patterns(frontmatter, lambda v: _path_matches_kind(root, v))
    problems += [f"path_patterns 值 {v!r}: 專案根目錄下不存在對應的目錄或檔案" for v in missing]
    return [f"{location}: {item}" for item in problems]


def _path_matches_kind(root: Path, pattern: str) -> bool:
    """`/` 結尾的前綴須為目錄，否則須為檔案。"""
    target = root / pattern
    return target.is_dir() if pattern.endswith("/") else target.is_file()


def _collect_all_path_problems(project_root: str) -> list[str]:
    """全部 DomainBundle 的 path_patterns 問題，加上非 domain 路徑清單檔的問題。"""
    root = Path(project_root)
    scanned = _scan_domain_bundles(project_root)
    bundles = {bid: fm for bid, (_, fm) in scanned.items()}
    problems = []
    for bid in bundles:
        problems += _collect_path_pattern_problems(project_root, bundles, bid)
    bundle_patterns = {
        bid: raw for bid, fm in bundles.items() if isinstance(raw := read_path_patterns(fm), list)
    }
    location = str(root / NON_DOMAIN_PATHS_FILE)
    try:
        values = read_non_domain_paths(root)
    except NonDomainPathsFormatError as exc:
        return problems + [f"{location}: {exc}"]
    if values is None:
        return problems
    found = find_non_domain_path_problems(values, bundle_patterns)
    found += [
        f"non_domain_path_patterns 值 {v!r}: 專案根目錄下不存在對應的目錄或檔案"
        for v in values
        if isinstance(v, str) and check_path_pattern_format(v) is None and not _path_matches_kind(root, v)
    ]
    return problems + [f"{location}: {item}" for item in found]


def execute_paths(args: argparse.Namespace) -> None:
    """doc validate-paths：一次檢查全部 path_patterns 與非 domain 路徑清單檔（供 CI）。"""
    project_root = FileLocator.get_project_root()
    duplicates = [
        _format_duplicate_domain(d, paths) for d, paths in _find_duplicate_domains(project_root).items()
    ]
    problems = duplicates + _collect_all_path_problems(project_root)
    if not problems:
        print("通過: 全部 path_patterns、非 domain 路徑清單與 domain 唯一性皆有效")
        sys.exit(0)
    print("驗證失敗: path_patterns／非 domain 路徑清單／domain 唯一性無效")
    for item in problems:
        print(f"  - {item}")
    sys.exit(1)


def _as_name_list(value) -> list[str]:
    """frontmatter／flow 欄位值正規化為字串清單（缺失或 None 為空）。"""
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    return [str(item) for item in value]


def _collect_domain_references(doc_id: str, file_path: str, frontmatter: dict) -> list[tuple[str, str]]:
    """回傳文件內的 (欄位位置, domain 名稱) 引用；僅 UC 與 SPEC 帶此類欄位。"""
    prefix = doc_id.upper()
    if prefix.startswith("SPEC-"):
        names = _as_name_list(frontmatter.get("depends_on_domains"))
        return [("depends_on_domains", name) for name in names]
    if prefix.startswith("UC-"):
        with open(file_path, encoding="utf-8") as f:
            steps = _extract_structured_flow_steps(f.read().splitlines()) or []
        return [
            (f"flow[{step.get('id')}].traverses", name)
            for step in steps
            if isinstance(step, dict)
            for name in _as_name_list(step.get("traverses"))
        ]
    return []


def _declared_domains(project_root: str) -> set[str]:
    """所有 DomainBundle 宣告的 domain 名稱；空集合代表語料沒有宣告來源。"""
    return {
        str(fm["domain"]) for fm in _load_domain_bundles(project_root).values() if fm.get("domain")
    }


def _find_undeclared_domain_references(
    project_root: str, doc_id: str, file_path: str, frontmatter: dict
) -> list[str]:
    """回傳未被任何 DomainBundle 宣告的 domain 引用（空清單代表通過）。

    語料沒有任何 DomainBundle 時不檢查（舊版語料沒有宣告來源可比對）。
    """
    declared = _declared_domains(project_root)
    if not declared:
        return []
    references = _collect_domain_references(doc_id, file_path, frontmatter)
    undeclared = set(find_undeclared_domain_names([name for _, name in references], declared))
    return [
        f"{file_path}: {location} 值 {name!r} 不是已宣告的 domain"
        for location, name in references
        if name in undeclared
    ]


def _fail_on_undeclared_domains(project_root: str, doc_id: str, file_path: str, frontmatter: dict) -> None:
    """有未宣告的 domain 引用時列出位置並 exit 1。"""
    problems = _find_undeclared_domain_references(project_root, doc_id, file_path, frontmatter)
    if not problems:
        return
    print(f"驗證失敗: {doc_id} 引用了未宣告的 domain（須為 DomainBundle 的 domain）")
    for item in problems:
        print(f"  - {item}")
    sys.exit(1)


def _read_flow_steps(file_path: str) -> list:
    """讀取 UC 結構化 flow 區塊的步驟；沒有 flow 區塊回傳空清單。"""
    with open(file_path, encoding="utf-8") as f:
        return _extract_structured_flow_steps(f.read().splitlines()) or []


def _find_flow_order_problems(steps: list) -> list[str]:
    """主線步驟（branch_from 為空）的 next 須等於清單中下一個主線步驟（末步為空）。

    分支步的 next 不受限。回傳問題描述清單（空清單代表通過）。
    """
    mainline = [s for s in steps if isinstance(s, dict) and not s.get("branch_from")]
    problems: list[str] = []
    for index, step in enumerate(mainline):
        expected = [str(mainline[index + 1].get("id"))] if index + 1 < len(mainline) else []
        actual = _as_name_list(step.get("next"))
        if actual != expected:
            problems.append(f"flow[{step.get('id')}].next 為 {actual}，依清單順序應為 {expected}")
    return problems


def _find_branch_from_problems(steps: list) -> list[str]:
    """branch_from 須指向 flow 內存在的其他步驟，且沿 branch_from 不成環。

    回傳問題描述清單（空清單代表通過）；自指與成環分開描述。
    """
    dict_steps = [s for s in steps if isinstance(s, dict)]
    ids = {str(s.get("id")) for s in dict_steps}
    graph: dict[str, list[str]] = {}
    problems: list[str] = []
    for step in dict_steps:
        step_id, parent = str(step.get("id")), step.get("branch_from")
        if not parent:
            continue
        location = f"flow[{step_id}].branch_from"
        if str(parent) == step_id:
            problems.append(f"{location} 自指（{step_id}）")
        elif str(parent) not in ids:
            problems.append(f"{location} 指向不存在的步驟 {str(parent)!r}")
        else:
            graph[step_id] = [str(parent)]
    reported: set[frozenset] = set()
    for step_id in graph:
        for cycle in _find_reachable_cycles(graph, step_id):
            if frozenset(cycle) not in reported:
                reported.add(frozenset(cycle))
                problems.append("branch_from 成環：" + " -> ".join(cycle))
    return problems


def _fail_on_branch_from_structure(doc_id: str, file_path: str) -> None:
    """UC 結構化 flow 區塊 branch_from 懸空、自指或成環時列出位置並 exit 1。"""
    if not doc_id.upper().startswith("UC-"):
        return
    problems = _find_branch_from_problems(_read_flow_steps(file_path))
    if not problems:
        return
    print(f"驗證失敗: {doc_id} 的 branch_from 結構無效")
    for item in problems:
        print(f"  - {file_path}: {item}")
    sys.exit(1)


def _fail_on_flow_order(doc_id: str, file_path: str) -> None:
    """UC 結構化 flow 區塊主線 next 與清單順序不一致時列出位置並 exit 1。"""
    if not doc_id.upper().startswith("UC-"):
        return
    problems = _find_flow_order_problems(_read_flow_steps(file_path))
    if not problems:
        return
    print(f"驗證失敗: {doc_id} 主線 next 與 flow 清單順序不一致")
    for item in problems:
        print(f"  - {file_path}: {item}")
    sys.exit(1)


def _report_non_data_contract_pass(project_root: str, doc_id: str, file_path: str, subdomain) -> None:
    """非 data-contract 文件通過時：依文件型別列出實際執行的檢查，再列略過與不適用項。

    「通過」只列真正檢查過內容的項目；前提不成立而未檢查的項目列為「略過」。
    只有 SPEC 印 /spec validate 路由提示，UC 與其他型別都不印。
    """
    prefix = doc_id.upper()
    is_uc, is_spec = prefix.startswith("UC-"), prefix.startswith("SPEC-")
    if not (is_uc or is_spec):
        print(f"通過: {doc_id} 沒有適用的檢查（doc validate 的內容檢查僅涵蓋 UC／SPEC／EVT／DOMAIN-MAP）")
        return
    field = "flow 的 traverses" if is_uc else "depends_on_domains"
    passed: list[str] = []
    skipped: list[str] = []
    if _declared_domains(project_root):
        passed.append(f"domain 引用宣告（{field}）")
    else:
        skipped.append(f"domain 引用宣告（{field}）：語料沒有 DomainBundle，無宣告來源可比對")
    if is_uc:
        if _read_flow_steps(file_path):
            passed += ["flow branch_from 結構", "flow 主線 next 與清單順序"]
        else:
            skipped.append("flow branch_from 結構、主線 next 順序：文件沒有結構化 flow 區塊")
    print(f"已執行的檢查: {doc_id}")
    for item in passed:
        print(f"通過: {item}")
    for item in skipped:
        print(f"略過: {item}")
    if is_uc:
        print("不適用: data-contract 章節 schema（僅適用 subdomain 為 data-contract 的 SPEC）")
        return
    print(f"不適用: UC flow 檢查（僅適用 UC）；data-contract 章節 schema（subdomain={subdomain!r}）")
    print("SPEC 章節驗證請用 /spec validate")


def execute(args: argparse.Namespace) -> None:
    """依 frontmatter subdomain 分派章節 schema 驗證。"""
    doc_id = args.doc_id
    project_root = FileLocator.get_project_root()

    if doc_id.startswith("DOMAIN-MAP-"):
        _execute_domain_bundle_validation(project_root, doc_id)
        return

    if doc_id.upper().startswith("EVT-"):
        _execute_event_validation(project_root, doc_id)
        return

    locator = FileLocator(project_root)

    file_path = locator.resolve_file(doc_id)
    if file_path is None:
        print(f"找不到文件: {doc_id}")
        sys.exit(2)

    frontmatter = parse_frontmatter(file_path)
    if frontmatter is None:
        print(f"無法解析 frontmatter: {file_path}")
        sys.exit(2)

    _fail_on_undeclared_domains(project_root, doc_id, file_path, frontmatter)
    _fail_on_branch_from_structure(doc_id, file_path)
    _fail_on_flow_order(doc_id, file_path)

    subdomain = frontmatter.get("subdomain")
    if subdomain != "data-contract":
        _report_non_data_contract_pass(project_root, doc_id, file_path, subdomain)
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


# 無對應模板的固定命名文件（doc SKILL.md 直接指名路徑，非透過模板 cp 建立）。
# 純模板推導機制對這類檔案天生盲區——沒有模板可推導，必須顯式宣告。
# 新增固定命名文件且無模板時，於此補上檔名（見 doc SKILL.md 文件類型定義）。
_NON_TEMPLATE_FIXED_NAME_EXEMPTIONS: set[str] = {
    "uc-numbering-convention.md",  # doc SKILL.md 指名 docs/spec/uc-numbering-convention.md
}


def _fixed_name_exemptions() -> set[str]:
    """回傳框架約定的固定命名文件檔名清單（豁免檔名慣例檢查）。

    兩個來源聯集：
    1. `templates/` 下 `*-template.md` 命名推導——模板檔 `{name}-template.md`
       對應的固定命名文件即為 `{name}.md`（如 `component-library-spec-template.md`
       -> `component-library-spec.md`、`domain-map-template.md` -> `domain-map.md`）。
       不限 `*-spec-template.md`，涵蓋所有模板類型（DomainMap 等非 spec 命名文件）。
    2. `_NON_TEMPLATE_FIXED_NAME_EXEMPTIONS` 顯式清單——涵蓋無對應模板、
       純模板推導機制天生盲區的固定命名文件（如 uc-numbering-convention.md）。

    不另手維護一份完整獨立名單，避免重演配號器 allowlist 判準與成員脫節
    問題（見 ARCH-BAL-003）；顯式清單僅補模板推導覆蓋不到的缺口。

    這類文件由 doc SKILL.md 明文指示以 `cp` 建立或直接指名路徑（非透過
    `doc create` 配號流程），且被其他 SKILL.md（如 version-bootstrap）直接
    以固定路徑引用，因此刻意不進 `{PREFIX}-{數字}` 編號空間。
    """
    templates_dir = _get_templates_dir()
    exemptions = set(_NON_TEMPLATE_FIXED_NAME_EXEMPTIONS)

    if not templates_dir.is_dir():
        return exemptions

    for template_file in templates_dir.glob("*-template.md"):
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
