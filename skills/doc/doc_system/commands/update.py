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


def _find_proposal_entry(proposals, prop_id: str) -> dict | None:
    """在 `proposals` 區塊中找出對應 prop_id 的 entry dict。

    相容兩種結構：dict-keyed（{prop_id: {...}}，測試 fixture 慣用寫法）與
    list-based（[{"id": prop_id, ...}, ...]，docs/proposals-tracking.yaml
    實際結構）。回傳的 dict 為原資料結構內的參照，就地修改即會反映到
    `proposals`。
    """
    if isinstance(proposals, dict):
        return proposals.get(prop_id)
    if isinstance(proposals, list):
        return next(
            (item for item in proposals if isinstance(item, dict) and item.get("id") == prop_id),
            None,
        )
    return None


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

    entry = _find_proposal_entry(data.get("proposals", {}), prop_id)
    if entry is None:
        return False

    entry["status"] = new_status

    # 如果是 confirmed，填入 confirmed_at 日期（欄位名對齊真實 schema，
    # 見 docs/proposals-tracking.yaml：PROP-007/015/016 皆用 confirmed_at）
    if new_status == "confirmed" and entry.get("confirmed_at") is None:
        entry["confirmed_at"] = date.today().isoformat()

    path.write_text(
        yaml.dump(data, allow_unicode=True, default_flow_style=False, sort_keys=False),
        encoding="utf-8",
    )
    return True


def _find_proposal_target_version(tracking_file: str, prop_id: str) -> tuple[bool, str | None]:
    """從 proposals-tracking.yaml 找出指定 proposal 的 target_version。

    回傳 (found, target_version)：found 表示是否找到對應 prop_id 的 entry
    （結構相容性見 `_find_proposal_entry`）。
    """
    path = Path(tracking_file)
    if not path.is_file():
        return False, None

    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return False, None

    entry = _find_proposal_entry(data.get("proposals"), prop_id)
    if entry is None:
        return False, None
    return True, entry.get("target_version")


def _registered_todolist_versions(project_root: Path) -> set:
    """讀取 todolist.yaml 已註冊版本號集合（不限 status）。

    判定標準與 version-tracking-consistency-guard-hook 漂移 7
    （detect_unregistered_confirmed_proposals）一致：版本出現於
    todolist.yaml 任一條目即視為已註冊。
    """
    todolist_path = project_root / "docs" / "todolist.yaml"
    if not todolist_path.is_file():
        return set()

    data = yaml.safe_load(todolist_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return set()

    entries = data.get("versions", [])
    if not isinstance(entries, list):
        return set()

    return {
        str(entry["version"]).strip("'\"")
        for entry in entries
        if isinstance(entry, dict) and entry.get("version")
    }


def _print_target_version_guidance(project_root: Path, tracking_file: str, prop_id: str) -> None:
    """confirmed 提案的 target_version 註冊引導（三層防護模型第 1 層，源頭引導）。

    未在 todolist.yaml 註冊時輸出提醒，不阻擋流程（confirm 與版本註冊
    時序可能合理分離）。target_version 為 null 或找不到 entry 時不提示
    ——與 version-tracking-consistency-guard-hook 漂移 7 判定標準一致，
    「提案未指定目標版本」是不同關注點，非本引導職責。
    """
    found, target_version = _find_proposal_target_version(tracking_file, prop_id)
    if not found or not target_version:
        return

    version_token = str(target_version).lstrip("v")
    if version_token in _registered_todolist_versions(project_root):
        return

    print(
        f"提示: {prop_id} target_version v{version_token} 尚未在 "
        f"docs/todolist.yaml 註冊，activate 版本推進將看不到此候選"
    )
    print(
        f"      建議：於 docs/todolist.yaml 補建版本條目"
        f"（version: \"{version_token}\", status: planned）"
    )


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

        # 源頭引導（獨立於 sync 是否成功）：confirmed 時檢查 target_version
        # 是否已在 todolist.yaml 註冊
        if new_status == "confirmed":
            _print_target_version_guidance(Path(project_root), locator.tracking_file, doc_id)
