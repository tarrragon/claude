#!/usr/bin/env python3
"""framework-issue create：包裝 `gh issue create` 於框架 canonical repo。

用途：在框架 repo（tarrragon/claude.git）建立標準化 framework issue，作為
provenance 錨點 / error-pattern canonical key / 跨 consumer 修復追蹤源頭。
"""

import argparse
import sys

from gh_common import FRAMEWORK_REPO, preflight, run_gh


def build_args(title: str, body: str, labels: list) -> list:
    """組裝傳給 gh issue create 的參數清單。"""
    args = ["issue", "create", "--repo", FRAMEWORK_REPO, "--title", title]
    if body:
        args += ["--body", body]
    for label in labels:
        args += ["--label", label]
    return args


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="framework-issue create",
        description="於框架 canonical repo 建立 framework issue",
    )
    parser.add_argument("--title", required=True, help="issue 標題")
    parser.add_argument("--body", default="", help="issue 內文（選填）")
    parser.add_argument(
        "--label",
        action="append",
        default=[],
        help="標籤（可重複指定）",
    )
    parsed = parser.parse_args(argv)

    gate = preflight()
    if gate != 0:
        return gate

    return run_gh(
        build_args(parsed.title, parsed.body, parsed.label),
        success_msg="issue 已建立",
    )


if __name__ == "__main__":
    sys.exit(main())
