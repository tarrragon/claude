#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml"]
# ///
"""version-bootstrap 跨提案依賴檢查工具。

在版本規劃波 Step 1（提案確認）時，偵測「本版提案依賴的提案尚未完成或排在
更晚版本」的排序矛盾，讓矛盾在提案確認階段被攔截，而非拖到 W1 中段才靠
用戶手動發現（0.4.0-W1-001 PROP-010 依賴 PROP-011 卻排前的事故）。

使用方式:
  uv run .claude/skills/version-bootstrap/scripts/check_proposal_dependencies.py --version 0.4.0
"""

import argparse
import sys
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.parent
TODOLIST_PATH = PROJECT_ROOT / "docs" / "todolist.yaml"
TRACKING_PATH = PROJECT_ROOT / "docs" / "proposals-tracking.yaml"


def normalize_version(raw: str) -> tuple[int, ...]:
    """把 'v0.4.0' / '0.4.0' 統一轉為可比較的整數 tuple。"""
    stripped = raw.strip().lstrip("vV")
    return tuple(int(part) for part in stripped.split("."))


def load_yaml(path: Path) -> dict:
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def get_version_proposals(todolist: dict, version: str) -> list[str]:
    """取出指定版本在 todolist.yaml 的 proposals 清單。"""
    for entry in todolist.get("versions", []):
        if entry.get("version") == version:
            return entry.get("proposals") or []
    return []


def check_dependencies(todolist: dict, tracking: dict, version: str) -> list[str]:
    """檢查指定版本的提案是否依賴排在更晚版本的提案。

    回傳矛盾描述清單；無矛盾回傳空清單。矛盾定義：提案 A 的 depends_on 含
    提案 B，但 B 的 target_version 晚於 A 的 target_version（B 還沒排入
    A 之前的版本，A 卻已排定）。
    """
    warnings: list[str] = []
    proposals = tracking.get("proposals", {})
    target_proposal_ids = get_version_proposals(todolist, version)

    for prop_id in target_proposal_ids:
        prop = proposals.get(prop_id)
        if prop is None:
            warnings.append(f"{prop_id}：proposals-tracking.yaml 無此提案，無法檢查依賴")
            continue

        depends_on = prop.get("depends_on") or []
        for dep_id in depends_on:
            dep = proposals.get(dep_id)
            if dep is None:
                warnings.append(f"{prop_id} 依賴 {dep_id}，但 proposals-tracking.yaml 無此提案")
                continue

            dep_target = dep.get("target_version")
            prop_target = prop.get("target_version")
            if dep_target is None or prop_target is None:
                continue

            if normalize_version(dep_target) > normalize_version(prop_target):
                warnings.append(
                    f"{prop_id}（排入 {prop_target}）依賴 {dep_id}（排入 {dep_target}），"
                    f"依賴提案排在更晚版本，建議移版或補前置"
                )

    return warnings


def main() -> int:
    parser = argparse.ArgumentParser(description="版本啟動跨提案依賴檢查")
    parser.add_argument("--version", required=True, help="要檢查的版本號，例如 0.4.0")
    args = parser.parse_args()

    todolist = load_yaml(TODOLIST_PATH)
    tracking = load_yaml(TRACKING_PATH)

    warnings = check_dependencies(todolist, tracking, args.version)

    if not warnings:
        print(f"[OK] {args.version} 無跨提案依賴排序矛盾")
        return 0

    print(f"[WARNING] {args.version} 偵測到 {len(warnings)} 項跨提案依賴排序矛盾：")
    for w in warnings:
        print(f"  - {w}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
