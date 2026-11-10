#!/usr/bin/env python3
"""framework-issue close：包裝 gh issue close，依關閉原因檢查追溯載體。

兩種關閉各有前置條件：

- `completed`（或省略 `--reason`）：必須已有 `fix_version.py` 寫入的版本號
  註記（非空 fix-versions 區段），否則其他 consumer 專案 sync-pull 後無法
  判斷該同步還是接續排查新徵狀。缺少註記時降級報錯（exit 3），提示先執行
  sync-push 取得框架版本號並以 fix-version 註記。
- `not planned`（過時、非框架、重複等不修關閉）：不經修復版本表——表內只
  放修好的版本，混入「不修」列會讓讀者以表判斷「哪一版修好」時誤讀。改為
  `--comment` 必填（判定理由），工具自動在關閉留言附上本地 `.claude/VERSION`
  作為判定所依據的框架版本；理由空白或版本讀不到時 exit 3。

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
from fix_version import fetch_body, has_fix_versions, read_framework_version

# gh issue close --reason 合法值（省略時 gh 預設為 completed）
CLOSE_REASONS = ("completed", "not planned")
NOT_PLANNED = "not planned"


def _not_planned_comment(reason_text: str) -> str:
    """不修關閉的留言：判定理由 + 判定所依據的框架版本；理由空白或版本讀不到時拋 ValueError。"""
    if not reason_text.strip():
        raise ValueError("--reason \"not planned\" 須以 --comment 寫明不修的判定理由")
    try:
        version = read_framework_version()
    except (OSError, ValueError) as exc:
        raise ValueError(f"讀取本地 .claude/VERSION 失敗，無法記錄判定依據的框架版本：{exc}") from exc
    return f"{reason_text.strip()}\n\n不修關閉，判定依據框架版本：{version}"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="framework-issue close",
        description=(
            "關閉 framework issue。completed（或省略 --reason）須已有修復版本號註記；"
            "not planned 須給 --comment 判定理由，工具自動附上判定依據的框架版本，不經修復版本表"
        ),
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
        help="關閉時附加留言（completed 選填；not planned 必填，寫判定理由）",
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

    comment = parsed.comment
    if parsed.reason == NOT_PLANNED:
        try:
            comment = _not_planned_comment(parsed.comment)
        except ValueError as exc:
            return emit_degraded(
                f"不修關閉前置檢查失敗：{exc}",
                "以 --comment 寫明判定理由（過時／非框架／重複等），並確認 .claude/VERSION 可讀後重試",
            )
    else:
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
                "先執行 sync-push 取得框架版本號，再用 fix-version 命令註記後重試；"
                "不修關閉改用 --reason \"not planned\" --comment \"判定理由\"",
            )

    args = ["issue", "close", issue_ref, "--repo", FRAMEWORK_REPO]
    if parsed.reason:
        args += ["--reason", parsed.reason]
    if comment:
        args += ["--comment", comment]
    return run_gh(args, success_msg=f"已關閉 {issue_ref}")


if __name__ == "__main__":
    sys.exit(main())
