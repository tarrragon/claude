"""batch-init 子命令 — 批量建立 spec + UC + traceability 骨架。

讀取指定提案的 checklist 項目，推導 spec FR 列表，
批量建立 spec 骨架、UC 骨架和 traceability 映射佔位。
"""

import argparse
import sys
from datetime import date
from pathlib import Path

import yaml

from doc_system.core.file_locator import FileLocator
from doc_system.commands.create import (
    DOC_TYPE_CONFIG,
    _read_template,
    _replace_frontmatter_id,
    _replace_frontmatter_date,
    _slugify,
)


def _load_tracking(tracking_file: str) -> dict:
    path = Path(tracking_file)
    if not path.is_file():
        print(f"找不到 proposals-tracking.yaml: {tracking_file}")
        sys.exit(1)
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _get_proposal_info(tracking: dict, prop_id: str) -> dict | None:
    proposals = tracking.get("proposals", {})
    return proposals.get(prop_id)


def _next_spec_id(project_root: str) -> str:
    spec_dir = Path(project_root) / "docs" / "spec"
    if not spec_dir.exists():
        return "SPEC-001"
    existing = []
    for f in spec_dir.rglob("*.md"):
        content = f.read_text(encoding="utf-8")
        for line in content.split("\n"):
            if line.startswith("id:"):
                sid = line.split(":", 1)[1].strip().strip('"')
                if sid.startswith("SPEC-"):
                    try:
                        existing.append(int(sid.split("-")[1]))
                    except (IndexError, ValueError):
                        pass
    next_num = max(existing, default=0) + 1
    return f"SPEC-{next_num:03d}"


def _next_uc_id(project_root: str) -> str:
    uc_dir = Path(project_root) / "docs" / "usecases"
    if not uc_dir.exists():
        return "UC-01"
    existing = []
    for f in uc_dir.glob("*.md"):
        name = f.stem
        if name.startswith("UC-"):
            try:
                existing.append(int(name.split("-")[1]))
            except (IndexError, ValueError):
                pass
    next_num = max(existing, default=0) + 1
    return f"UC-{next_num:02d}"


def _create_file(template_name: str, doc_id: str, title: str, target_dir: Path) -> Path:
    content = _read_template(template_name)
    content = _replace_frontmatter_id(content, doc_id)
    content = _replace_frontmatter_date(content)

    slug = _slugify(title) if title else ""
    filename = f"{doc_id}-{slug}.md" if slug else f"{doc_id}.md"

    target_dir.mkdir(parents=True, exist_ok=True)
    target_file = target_dir / filename
    target_file.write_text(content, encoding="utf-8")
    return target_file


def _append_traceability(traceability_file: Path, spec_id: str, uc_id: str, title: str) -> None:
    if traceability_file.is_file():
        data = yaml.safe_load(traceability_file.read_text(encoding="utf-8")) or {}
    else:
        data = {"version": "1.0", "mappings": []}

    mappings = data.setdefault("mappings", [])
    mappings.append({
        "spec": spec_id,
        "usecase": uc_id,
        "title": title,
        "scenarios": ["TODO: 填寫場景映射"],
        "tests": [],
    })
    data["last_updated"] = date.today().isoformat()

    traceability_file.write_text(
        yaml.dump(data, allow_unicode=True, default_flow_style=False, sort_keys=False),
        encoding="utf-8",
    )


def execute(args: argparse.Namespace) -> None:
    """批量建立 spec + UC + traceability 骨架。"""
    proposal_ids = [p.strip() for p in args.proposals.split(",")]
    domain = getattr(args, "domain", None)

    project_root = FileLocator.get_project_root()
    locator = FileLocator(project_root)
    tracking = _load_tracking(locator.tracking_file)

    traceability_file = Path(project_root) / "docs" / "traceability.yaml"
    created_files = []
    report = []

    for prop_id in proposal_ids:
        prop_info = _get_proposal_info(tracking, prop_id)
        if prop_info is None:
            print(f"[SKIP] {prop_id}: 在 proposals-tracking.yaml 中找不到")
            continue

        title = prop_info.get("title", prop_id)

        # 建 Spec 骨架
        spec_id = _next_spec_id(project_root)
        spec_config = DOC_TYPE_CONFIG["spec"]
        spec_dir = Path(project_root) / spec_config["target_dir"]
        if domain:
            spec_dir = spec_dir / domain
        spec_file = _create_file(spec_config["template"], spec_id, title, spec_dir)
        created_files.append(str(spec_file))

        # 建 UC 骨架
        uc_id = _next_uc_id(project_root)
        uc_config = DOC_TYPE_CONFIG["usecase"]
        uc_dir = Path(project_root) / uc_config["target_dir"]
        uc_file = _create_file(uc_config["template"], uc_id, title, uc_dir)
        created_files.append(str(uc_file))

        # 建 traceability 映射
        _append_traceability(traceability_file, spec_id, uc_id, title)

        report.append({
            "proposal": prop_id,
            "title": title,
            "spec": spec_id,
            "usecase": uc_id,
            "spec_file": str(spec_file),
            "uc_file": str(uc_file),
        })

    # 輸出報告
    print("\n=== batch-init 建置報告 ===\n")
    print(f"處理 {len(report)} 個提案：\n")
    for r in report:
        print(f"  {r['proposal']} ({r['title']})")
        print(f"    Spec: {r['spec']} → {r['spec_file']}")
        print(f"    UC:   {r['usecase']} → {r['uc_file']}")
        print()

    print(f"Traceability 映射已更新: {traceability_file}")
    print(f"\n共建立 {len(created_files)} 個檔案。")
    print("\n待人工填寫：")
    print("  - 每份 Spec 的 FR 列表和介面定義")
    print("  - 每份 UC 的 GWT 場景")
    print("  - Traceability 中的 scenario 映射（目前為 TODO 佔位）")
