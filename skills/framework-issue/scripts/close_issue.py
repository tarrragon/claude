#!/usr/bin/env python3
"""framework-issue close：包裝 gh issue close，前置檢查修復版本號註記。

close 前必須已有 `fix_version.py` 寫入的版本號註記（非空 fix-versions
區段），否則其他 consumer 專案 sync-pull 後無法判斷該同步還是接續排查
新徵狀。缺少註記時降級報錯（exit 3），提示先執行 sync-push 取得框架
版本號並以 fix-version 註記，避免各專案各自關閉造成同步狀態不一致。

close 後仍可再追加版本號：`fix_version.py` 對 body 的編輯不要求 issue
為 open 狀態，重開或直接編輯 body 皆可（issue 46 第四類徵狀教訓：close
後才發現新徵狀時不必重開即可補註記）。
"""

import argparse
import subprocess
import sys

from gh_common import (
    FRAMEWORK_REPO,
    emit_degraded,
    normalize_issue_ref,
    preflight,
    run_gh,
)
from fix_version import fetch_body, has_fix_versions

# gh issue close --reason 合法值（省略時 gh 預設為 completed）
CLOSE_REASONS = ("completed", "not planned")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="framework-issue close",
        description="關閉 framework issue（前置檢查修復版本號註記存在）",
    )
    parser.add_argument(
        "issue_ref",
        help="framework issue ref（如 tarrragon/claude#42 或純號 42）",
    )
    parser.add_argument(
        "--reason",
        default="",
        choices=("", *CLOSE_REASONS),
        help="關閉原因（選填，同 gh issue close --reason；省略時用 gh 預設）",
    )
    parser.add_argument(
        "--comment",
        default="",
        help="關閉時附加留言（選填）",
    )
    parsed = parser.parse_args(argv)

    gate = preflight()
    if gate != 0:
        return gate

    try:
        issue_ref = normalize_issue_ref(parsed.issue_ref)
    except ValueError as exc:
        return emit_degraded(
            f"issue ref 格式錯誤：{exc}",
            "使用 owner/repo#N、#N 或純數字格式，且 repo 需與"
            f" {FRAMEWORK_REPO} 相符",
        )

    try:
        body = fetch_body(issue_ref)
    except (OSError, subprocess.SubprocessError, RuntimeError, ValueError) as exc:
        return emit_degraded(
            f"讀取 issue {issue_ref} 失敗：{exc}",
            "確認 issue ref 正確且 gh 可存取該 repo 後重試",
        )

    if not has_fix_versions(body):
        return emit_degraded(
            f"issue {issue_ref} 尚無修復版本號註記（fix-versions 區段空或不存在）",
            "先執行 sync-push 取得框架版本號，再用 fix-version 命令註記後重試",
        )

    args = ["issue", "close", issue_ref, "--repo", FRAMEWORK_REPO]
    if parsed.reason:
        args += ["--reason", parsed.reason]
    if parsed.comment:
        args += ["--comment", parsed.comment]
    return run_gh(args, success_msg=f"已關閉 {issue_ref}")


if __name__ == "__main__":
    sys.exit(main())
