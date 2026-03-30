"""status 子命令 — 顯示文件系統總覽狀態。"""

import argparse

import yaml

from doc_system.core.file_locator import FileLocator


def _load_tracking(tracking_file: str) -> dict | None:
    """讀取 proposals-tracking.yaml，失敗時回傳 None。"""
    try:
        with open(tracking_file, encoding="utf-8") as f:
            return yaml.safe_load(f)
    except (OSError, yaml.YAMLError):
        return None


def execute(args: argparse.Namespace) -> None:
    """讀取 proposals-tracking.yaml，統計各狀態提案數量。"""
    locator = FileLocator(FileLocator.get_project_root())

    tracking = _load_tracking(locator.tracking_file)
    if tracking is None:
        print(f"無法讀取追蹤檔案: {locator.tracking_file}")
        return

    proposals = tracking.get("proposals", {})
    if not proposals:
        print("目前沒有提案。")
        return

    # 統計各狀態數量
    status_counts: dict[str, int] = {}
    for prop_data in proposals.values():
        if not isinstance(prop_data, dict):
            continue
        prop_status = prop_data.get("status", "unknown")
        status_counts[prop_status] = status_counts.get(prop_status, 0) + 1

    total = sum(status_counts.values())

    print("=== 提案追蹤狀態摘要 ===")
    print(f"提案總數: {total}")
    print()

    for status_name, count in sorted(status_counts.items()):
        print(f"  {status_name:<15} {count}")
