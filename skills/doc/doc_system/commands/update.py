"""update 子命令 — 更新文件的 frontmatter 狀態。"""

import argparse
import re
import sys
from datetime import date
from pathlib import Path

import yaml

from doc_system.core.file_locator import FileLocator
from doc_system.core.frontmatter_parser import parse_frontmatter


VALID_STATUSES = ("draft", "discussing", "confirmed", "implemented", "withdrawn")


def _update_frontmatter_status(file_path: str, new_status: str) -> bool:
    """更新 Markdown 檔案 frontmatter 中的 status 欄位。

    回傳是否成功更新。
    """
    path = Path(file_path)
    content = path.read_text(encoding="utf-8")

    updated = re.sub(
        r"^(status:\s*).*$",
        rf"\g<1>{new_status}",
        content,
        count=1,
        flags=re.MULTILINE,
    )

    if updated == content:
        return False

    path.write_text(updated, encoding="utf-8")
    return True


def _sync_tracking_yaml(tracking_file: str, prop_id: str, new_status: str) -> bool:
    """同步更新 proposals-tracking.yaml 中對應 proposal 的 status。

    回傳是否成功更新。
    """
    path = Path(tracking_file)
    if not path.is_file():
        return False

    raw = path.read_text(encoding="utf-8")
    data = yaml.safe_load(raw)
    if not isinstance(data, dict):
        return False

    proposals = data.get("proposals", {})
    if prop_id not in proposals:
        return False

    proposals[prop_id]["status"] = new_status

    # 如果是 confirmed，填入 confirmed 日期
    if new_status == "confirmed" and proposals[prop_id].get("confirmed") is None:
        proposals[prop_id]["confirmed"] = date.today().isoformat()

    data["last_updated"] = date.today().isoformat()

    path.write_text(
        yaml.dump(data, allow_unicode=True, default_flow_style=False, sort_keys=False),
        encoding="utf-8",
    )
    return True


def execute(args: argparse.Namespace) -> None:
    """更新文件的 status 欄位。"""
    doc_id = args.id
    new_status = args.status

    if new_status not in VALID_STATUSES:
        print(f"無效狀態: {new_status}")
        print(f"有效值: {', '.join(VALID_STATUSES)}")
        sys.exit(1)

    project_root = FileLocator.get_project_root()
    locator = FileLocator(project_root)

    file_path = locator.resolve_file(doc_id)
    if file_path is None:
        print(f"找不到文件: {doc_id}")
        sys.exit(1)

    # 讀取當前狀態
    frontmatter = parse_frontmatter(file_path)
    old_status = frontmatter.get("status", "unknown") if frontmatter else "unknown"

    # 更新 frontmatter
    updated = _update_frontmatter_status(file_path, new_status)
    if not updated:
        print(f"更新失敗: 檔案 {file_path} 中找不到 status 欄位")
        sys.exit(1)

    print(f"已更新: {doc_id} ({old_status} -> {new_status})")

    # 如果是 proposal，同步 tracking.yaml
    if doc_id.upper().startswith("PROP"):
        synced = _sync_tracking_yaml(locator.tracking_file, doc_id, new_status)
        if synced:
            print(f"已同步 tracking.yaml: {doc_id}")
        else:
            print(f"tracking.yaml 無對應 entry: {doc_id}（略過同步）")
