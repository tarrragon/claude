#!/usr/bin/env python3
"""framework-issue create：包裝 `gh issue create` 於框架 canonical repo。

用途：在框架 repo（tarrragon/claude）建立標準化 framework issue，作為
provenance 錨點 / error-pattern canonical key / 跨 consumer 修復追蹤源頭。

環境資訊自動收集：每個 issue body 自動附加 OS / Claude Code 版本 / Python
版本，以標記區段 `<!-- env-info -->...<!-- /env-info -->` 包裹，供跨環境
排查時區分徵狀差異是否源於環境不同（0.2.1-W3-295）。任一項收集失敗降級為
unknown，不阻擋 issue 建立。
"""

import argparse
import platform
import subprocess
import sys

from gh_common import FRAMEWORK_REPO, preflight, run_gh

ENV_INFO_BEGIN = "<!-- env-info -->"
ENV_INFO_END = "<!-- /env-info -->"
UNKNOWN = "unknown"


def get_os_info() -> str:
    """取得作業系統資訊；`platform` 呼叫異常時降級為 unknown。

    刻意不用 `platform.platform()`：該函式在部分平台會內部呼叫
    `subprocess`（透過 `file` 指令判斷執行檔位元數），與測試對
    `gh_common.subprocess.run` 的 mock 共用同一 subprocess 模組物件而
    互相干擾。改以不涉及 subprocess 的欄位組裝，行為等價且可獨立測試。
    """
    try:
        return f"{platform.system()} {platform.release()} ({platform.machine()})"
    except OSError:
        return UNKNOWN


def get_claude_code_version() -> str:
    """執行 `claude --version` 取得 Claude Code 版本；不可用時降級為 unknown。"""
    try:
        result = subprocess.run(
            ["claude", "--version"],
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (OSError, subprocess.SubprocessError):
        return UNKNOWN
    if result.returncode != 0:
        return UNKNOWN
    return result.stdout.strip() or UNKNOWN


def get_python_version() -> str:
    """取得目前執行的 Python 版本；解析失敗時降級為 unknown。"""
    try:
        return platform.python_version()
    except OSError:
        return UNKNOWN


def collect_env_info() -> dict:
    """收集環境資訊字典；每一項各自獨立降級，不互相影響。"""
    return {
        "OS": get_os_info(),
        "Claude Code 版本": get_claude_code_version(),
        "Python 版本": get_python_version(),
    }


def render_env_info(info: dict) -> str:
    """把環境資訊字典渲染為含標記區段的 markdown，供機器解析。"""
    lines = [ENV_INFO_BEGIN]
    lines += [f"- {key}: {value}" for key, value in info.items()]
    lines.append(ENV_INFO_END)
    return "\n".join(lines)


def append_env_info(body: str) -> str:
    """把環境資訊區段附加到 issue body 末尾（body 為空時直接回傳區段本身）。"""
    section = render_env_info(collect_env_info())
    if not body:
        return section
    separator = "\n\n" if not body.endswith("\n") else "\n"
    return f"{body}{separator}{section}"


def build_args(title: str, body: str, labels: list) -> list:
    """組裝傳給 gh issue create 的參數清單（body 一律附加環境資訊區段）。"""
    args = [
        "issue", "create",
        "--repo", FRAMEWORK_REPO,
        "--title", title,
        "--body", append_env_info(body),
    ]
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
