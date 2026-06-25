"""create 子命令 — 從模板建立新文件（proposal/spec/usecase）。"""

import argparse
import re
import sys
from datetime import date
from pathlib import Path

import yaml

from doc_system.core.file_locator import FileLocator


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
}

VALID_PROPOSAL_STATUSES = ("draft", "discussing", "confirmed", "implemented", "withdrawn")


def _next_id(project_root: Path, doc_type: str) -> str:
    """掃描現有文件分配下一個序號 ID。

    Known limitation: TOCTOU — no file lock, parallel calls may allocate same ID.
    Acceptable for single-user CLI; existing ID check in execute() catches collision.
    """
    config = DOC_TYPE_CONFIG[doc_type]
    prefix = config["id_prefix"]
    target_dir = Path(project_root) / config["target_dir"]

    max_num = 0
    if target_dir.exists():
        pattern = re.compile(rf"^{prefix}-(\d+)", re.IGNORECASE)
        for item in target_dir.rglob("*.md"):
            m = pattern.match(item.stem)
            if m:
                max_num = max(max_num, int(m.group(1)))

    next_num = max_num + 1
    return f"{prefix}-{next_num:03d}"


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
    """取得 templates/ 目錄路徑。"""
    return Path(__file__).resolve().parent.parent.parent / "templates"


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
        # 建立基礎結構
        data = {
            "version": "1.0",
            "last_updated": date.today().isoformat(),
            "proposals": {},
        }
    else:
        raw = path.read_text(encoding="utf-8")
        data = yaml.safe_load(raw) or {}

    proposals = data.setdefault("proposals", {})
    if prop_id in proposals:
        # 已存在，不重複新增
        return

    proposals[prop_id] = {
        "title": title,
        "status": "draft",
        "proposed": date.today().isoformat(),
        "confirmed": None,
        "target_version": None,
        "source": "",
        "spec_refs": [],
        "usecase_refs": [],
        "ticket_refs": [],
        "checklist": [],
    }
    data["last_updated"] = date.today().isoformat()

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

    # ID 自動分配（0.3.4-W2-002）
    if not doc_id:
        doc_id = _next_id(project_root, doc_type)
        print(f"[自動分配] ID: {doc_id}")

    # spec domain 推導（0.3.4-W2-002）
    if config["requires_domain"] and not domain:
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
