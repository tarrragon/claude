#!/usr/bin/env python3
"""framework-issue list：包裝 `gh issue list` 於框架 canonical repo。

用途：列出框架 repo（tarrragon/claude.git）的 framework issue，供查詢既有
canonical issue 是否已存在（去重）或追蹤修復狀態。
"""

import argparse
import sys

from gh_common import FRAMEWORK_REPO, preflight, run_gh


def build_args(state: str, label: str, limit: int, search: str) -> list:
    """組裝傳給 gh issue list 的參數清單。"""
    args = ["issue", "list", "--repo", FRAMEWORK_REPO, "--state", state]
    if label:
        args += ["--label", label]
    if limit:
        args += ["--limit", str(limit)]
    if search:
        args += ["--search", search]
    return args


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="framework-issue list",
        description="列出框架 canonical repo 的 framework issue",
    )
    parser.add_argument(
        "--state",
        default="open",
        choices=["open", "closed", "all"],
        help="篩選狀態（預設 open）",
    )
    parser.add_argument("--label", default="", help="依標籤篩選（選填）")
    parser.add_argument("--limit", type=int, default=30, help="最多列出筆數（預設 30）")
    parser.add_argument("--search", default="", help="搜尋字串（選填，用於去重查詢）")
    parsed = parser.parse_args(argv)

    gate = preflight()
    if gate != 0:
        return gate

    return run_gh(build_args(parsed.state, parsed.label, parsed.limit, parsed.search))


if __name__ == "__main__":
    sys.exit(main())
