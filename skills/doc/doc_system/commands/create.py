"""create 子命令 — 從模板建立新文件（proposal/spec/usecase）。"""

import argparse
import re
import sys
from datetime import date
from pathlib import Path

import yaml

from doc_system.core.file_locator import FileLocator
from doc_system.core.frontmatter_parser import parse_frontmatter
from doc_system.core.tracking_schema import GRAPH_NODE_TYPES, PROPOSALS_TRACKING_SCHEMA


# type 到模板檔名和目標子目錄的對應
DOC_TYPE_CONFIG = {
    "proposal": {
        "template": "proposal-template.md",
        "target_dir": "docs/proposals",
        "id_prefix": "PROP",
        "requires_domain": False,
    },
    "spec": {
        "template": "spec-template.md",
        "target_dir": "docs/spec",
        "id_prefix": "SPEC",
        "requires_domain": True,
    },
    "usecase": {
        "template": "usecase-template.md",
        "target_dir": "docs/usecases",
        "id_prefix": "UC",
        "requires_domain": False,
    },
    "data-contract": {
        "template": "data-contract-template.md",
        "target_dir": "docs/spec",
        "id_prefix": "SPEC",
        "requires_domain": True,
    },
    "event": {
        "template": "event-template.md",
        "target_dir": "docs/events",
        "id_prefix": "EVT",
        "requires_domain": True,
        # EVT 配號依 domain 分桶（如 EVT-LIBRARY-001），非全域平坦編號：
        # 全域正則 `^EVT-(\d+)` 無法辨識 domain-scoped ID，見 _next_id。
        "domain_scoped_id": True,
    },
}

VALID_PROPOSAL_STATUSES = ("draft", "discussing", "confirmed", "implemented", "withdrawn")


# id_pattern 中序號段的位數量詞，如 `\d{3}`、`\d{2,}`、`[0-9]{3}`。
_DIGIT_QUANTIFIER_RE = re.compile(r"(?:\\d|\[0-9\])\{(\d+)")


def _declared_digit_width(node_type: str) -> int:
    """取 tracking_schema 對該型別宣告的序號最少位數（id_pattern 最後一個數字量詞的下限）。"""
    widths = _DIGIT_QUANTIFIER_RE.findall(GRAPH_NODE_TYPES[node_type]["id_pattern"])
    if not widths:
        raise ValueError(f"tracking_schema 的 {node_type} id_pattern 未宣告序號位數，無法配號")
    return int(widths[-1])


def _existing_numbers(target_dir: Path, prefix: str) -> list[str]:
    """收集目錄內既有序號字串（保留前導零以取位數），來源為檔名開頭與 frontmatter id 兩者聯集。

    只看檔名會漏掉以 slug 命名、ID 寫在 frontmatter 的檔（如 SPEC），只看
    frontmatter 會漏掉 frontmatter 不可解析的檔；取聯集使兩種情況都不會配出重號。
    """
    if not target_dir.exists():
        return []
    stem_re = re.compile(rf"^{re.escape(prefix)}-(\d+)", re.IGNORECASE)
    id_re = re.compile(rf"^{re.escape(prefix)}-(\d+)$", re.IGNORECASE)
    numbers: list[str] = []
    for item in target_dir.rglob("*.md"):
        stem_match = stem_re.match(item.stem)
        if stem_match:
            numbers.append(stem_match.group(1))
        frontmatter = parse_frontmatter(str(item))
        fm_id = str((frontmatter or {}).get("id") or "")
        id_match = id_re.match(fm_id.strip())
        if id_match:
            numbers.append(id_match.group(1))
    return numbers


def _next_id(project_root: Path, doc_type: str, domain: str | None = None) -> str:
    """掃描現有文件分配下一個序號 ID；create、next-id、batch-init 共用此唯一配號實作。

    位數規則：目錄已有編號時沿用最大號的位數（UC-06 之後配 UC-07，UC-005
    之後配 UC-006）；沒有既有編號時取 tracking_schema id_pattern 宣告的位數
    （UC 兩位、PROP／SPEC／EVT 三位），本函式不寫死位數。

    domain-scoped 型別（見 DOC_TYPE_CONFIG["domain_scoped_id"]，如 EVT）以
    `{prefix}-{DOMAIN}-{NNN}` 分桶編號，各 domain 序列互不干擾；一般型別
    仍沿用全域平坦編號 `{prefix}-{NNN}`。

    Known limitation: TOCTOU — no file lock, parallel calls may allocate same ID.
    Acceptable for single-user CLI; existing ID check in execute() catches collision.
    """
    config = DOC_TYPE_CONFIG[doc_type]
    node_type = config["id_prefix"]
    prefix = node_type
    if config.get("domain_scoped_id") and domain:
        prefix = f"{prefix}-{domain.upper()}"
    target_dir = Path(project_root) / config["target_dir"]

    numbers = _existing_numbers(target_dir, prefix)
    if numbers:
        max_number = max(numbers, key=int)
        width = len(max_number)
        next_num = int(max_number) + 1
    else:
        width = _declared_digit_width(node_type)
        next_num = 1
    return f"{prefix}-{next_num:0{width}d}"


def execute_next_id(args: argparse.Namespace) -> None:
    """唯讀查詢下一個可分配的 ID（不建立檔案）。"""
    doc_type = args.type
    if doc_type not in DOC_TYPE_CONFIG:
        print(f"不支援的文件類型: {doc_type}")
        sys.exit(1)

    domain = getattr(args, "domain", None)
    config = DOC_TYPE_CONFIG[doc_type]
    if config.get("domain_scoped_id") and not domain:
        print(f"{doc_type} 類型必須指定 --domain 參數")
        sys.exit(1)

    project_root = FileLocator.get_project_root()
    print(_next_id(project_root, doc_type, domain))


def _suggest_domain_from_tracking(project_root: Path, doc_id: str) -> str | None:
    """若 docs/spec/ 只有一個 domain 子目錄，自動選用。"""
    spec_dir = Path(project_root) / "docs" / "spec"
    if spec_dir.exists():
        domains = [d.name for d in spec_dir.iterdir() if d.is_dir()]
        if len(domains) == 1:
            return domains[0]
    return None


def _slugify(title: str) -> str:
    """將標題轉為 URL-safe slug（小寫、連字號分隔）。"""
    slug = title.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"-+", "-", slug)
    return slug.strip("-")


def _get_templates_dir() -> Path:
    """取得 templates/ 目錄路徑（W1-013 修復：不依賴原始碼樹與安裝目錄的相對位置）。

    依序嘗試兩個候選位置，取第一個實際存在者：
    1. 套件內建（`doc_system/templates/`）：`uv tool install` 後由 pyproject.toml
       的 force-include 打包進安裝版，為主要路徑
    2. 原始碼樹（skill 根目錄下 `templates/`）：僅在直接於原始碼樹執行時存在
       （目前 doc CLI 僅支援 `uv tool install` 安裝後使用，此為防禦性 fallback）

    舊實作以 `__file__` 上溯固定 3 層推算路徑，該假設僅在原始碼樹成立；
    安裝後 `doc_system` 落在 site-packages/ 下，同樣的相對層數指向不存在的路徑，
    導致 doc create 全數類型皆 FileNotFoundError（W1-013 根因）。
    """
    package_bundled = Path(__file__).resolve().parent.parent / "templates"
    if package_bundled.is_dir():
        return package_bundled

    source_tree = Path(__file__).resolve().parent.parent.parent / "templates"
    if source_tree.is_dir():
        return source_tree

    return package_bundled


def _read_template(template_name: str) -> str:
    """讀取模板檔案內容。"""
    template_path = _get_templates_dir() / template_name
    if not template_path.is_file():
        raise FileNotFoundError(f"找不到模板: {template_path}")
    return template_path.read_text(encoding="utf-8")


def _replace_frontmatter_id(content: str, new_id: str) -> str:
    """替換模板 frontmatter 中的 id 欄位值。"""
    return re.sub(r"^(id:\s*).*$", rf"\g<1>{new_id}", content, count=1, flags=re.MULTILINE)


def _replace_frontmatter_date(content: str) -> str:
    """替換模板 frontmatter 中的日期佔位符。"""
    today = date.today().isoformat()
    content = re.sub(
        r'(proposed_date:\s*)"YYYY-MM-DD"',
        rf'\g<1>"{today}"',
        content,
        count=1,
    )
    content = re.sub(
        r'(created:\s*)"YYYY-MM-DD"',
        rf'\g<1>"{today}"',
        content,
        count=1,
    )
    content = re.sub(
        r'(updated:\s*)"YYYY-MM-DD"',
        rf'\g<1>"{today}"',
        content,
        count=1,
    )
    return content


def _add_tracking_entry(tracking_file: str, prop_id: str, title: str) -> None:
    """在 proposals-tracking.yaml 新增 proposal entry。"""
    path = Path(tracking_file)
    if not path.is_file():
        # 建立基礎結構（對齊真實 proposals-tracking.yaml schema：僅 proposals/usecases/specs 三區塊）
        data = {
            "proposals": [],
            "usecases": [],
            "specs": [],
        }
    else:
        raw = path.read_text(encoding="utf-8")
        data = yaml.safe_load(raw) or {}

    proposals = data.setdefault("proposals", [])
    if any(entry.get("id") == prop_id for entry in proposals if isinstance(entry, dict)):
        # 已存在，不重複新增
        return

    confirm_field = PROPOSALS_TRACKING_SCHEMA["confirm_date_field"]
    proposals.append(
        {
            "id": prop_id,
            "title": title,
            "status": "draft",
            "proposed": date.today().isoformat(),
            confirm_field: None,
            "target_version": None,
            "source": "",
            "spec_refs": [],
            "usecase_refs": [],
            "ticket_refs": [],
            "checklist": [],
        }
    )

    path.write_text(
        yaml.dump(data, allow_unicode=True, default_flow_style=False, sort_keys=False),
        encoding="utf-8",
    )


def execute(args: argparse.Namespace) -> None:
    """建立新文件：從模板複製並替換 ID。"""
    doc_type = args.type
    doc_id = getattr(args, "id", None)
    title = getattr(args, "title", None) or ""
    domain = getattr(args, "domain", None)

    config = DOC_TYPE_CONFIG.get(doc_type)
    if config is None:
        print(f"不支援的文件類型: {doc_type}")
        sys.exit(1)

    project_root = FileLocator.get_project_root()

    # domain 解析（domain-scoped ID 型別的 ID 分配依賴 domain，須先於配號）
    if config["requires_domain"] and not domain:
        if config.get("domain_scoped_id"):
            print(f"{doc_type} 類型必須指定 --domain 參數")
            sys.exit(1)
        suggested = _suggest_domain_from_tracking(project_root, doc_id)
        if suggested:
            domain = suggested
            print(f"[建議] domain: {domain}")
        else:
            spec_dir = Path(project_root) / "docs" / "spec"
            if spec_dir.exists():
                domains = sorted(d.name for d in spec_dir.iterdir() if d.is_dir())
                if domains:
                    print(f"[提示] 可用 domain: {', '.join(domains)}")
            print("spec 類型必須指定 --domain 參數")
            sys.exit(1)

    # ID 自動分配
    if not doc_id:
        doc_id = _next_id(project_root, doc_type, domain)
        print(f"[自動分配] ID: {doc_id}")

    locator = FileLocator(project_root)

    # 檢查 ID 是否已存在
    existing = locator.resolve_file(doc_id)
    if existing is not None:
        print(f"ID 已存在: {doc_id} -> {existing}")
        sys.exit(1)

    # 讀取模板
    template_content = _read_template(config["template"])

    # 替換 frontmatter 中的 id 和日期
    content = _replace_frontmatter_id(template_content, doc_id)
    content = _replace_frontmatter_date(content)

    # 決定目標路徑
    slug = _slugify(title) if title else ""
    filename = f"{doc_id}-{slug}.md" if slug else f"{doc_id}.md"

    target_dir = Path(project_root) / config["target_dir"]
    if config["requires_domain"] and domain:
        target_dir = target_dir / domain

    target_dir.mkdir(parents=True, exist_ok=True)
    target_file = target_dir / filename

    target_file.write_text(content, encoding="utf-8")

    # proposal 自動新增 tracking entry
    if doc_type == "proposal":
        _add_tracking_entry(locator.tracking_file, doc_id, title or doc_id)

    print(f"已建立: {target_file}")
