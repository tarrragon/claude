#!/usr/bin/env python3
"""框架 issue 工作流共用模組：gh CLI 前置檢查與優雅降級。

設計目標：將 `gh` 不可用的三種狀態（未安裝 / 未登入 / 目標 repo Issues
停用）轉為清楚的 stderr 提示與非零 exit code，避免 subprocess 例外直接
向使用者拋出 traceback（可觀測性規則 4：異常須對使用者可見且不 crash）。
"""

import shutil
import subprocess
import sys

# 框架 canonical repo（所有 consumer 專案的 issue 集中於此）
FRAMEWORK_REPO = "tarrragon/claude.git"

# 降級時的 exit code（與一般失敗 1 區分，便於測試與上層判讀）
EXIT_DEGRADED = 3


def emit_degraded(reason: str, hint: str) -> int:
    """將降級原因寫入 stderr（使用者可見）並回傳降級 exit code。

    reason 描述偵測到的狀態，hint 給出使用者下一步修復動作。
    """
    sys.stderr.write(f"[framework-issue] 無法執行：{reason}\n")
    sys.stderr.write(f"[framework-issue] 建議：{hint}\n")
    return EXIT_DEGRADED


def check_gh_available() -> bool:
    """gh 是否已安裝於 PATH。"""
    return shutil.which("gh") is not None


def check_gh_authenticated() -> bool:
    """gh 是否已登入（gh auth status exit 0 視為已登入）。"""
    try:
        result = subprocess.run(
            ["gh", "auth", "status"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        return result.returncode == 0
    except (OSError, subprocess.SubprocessError):
        # gh 二進位異常時視為未認證，由上層降級提示處理
        return False


def preflight() -> int:
    """執行 gh 可用性與認證前置檢查。

    回傳 0 代表可繼續；非零代表已降級（呼叫端應直接回傳此值）。
    """
    if not check_gh_available():
        return emit_degraded(
            "gh CLI 未安裝",
            "安裝 GitHub CLI（https://cli.github.com/）後重試",
        )
    if not check_gh_authenticated():
        return emit_degraded(
            "gh CLI 未登入",
            "執行 `gh auth login` 完成認證後重試",
        )
    return 0


def run_gh(args: list, success_msg: str = "") -> int:
    """執行 gh 子命令，將失敗轉為降級提示而非未捕捉例外。

    args 為傳給 gh 的完整參數（不含 "gh" 本身）。stdout 原樣輸出，
    stderr 在失敗時加上 framework-issue 降級提示（含 Issues 停用情境）。
    """
    try:
        result = subprocess.run(
            ["gh", *args],
            capture_output=True,
            text=True,
            timeout=60,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return emit_degraded(
            f"gh 執行失敗：{exc}",
            "確認 gh CLI 安裝完整且網路可用後重試",
        )

    if result.stdout:
        sys.stdout.write(result.stdout)

    if result.returncode != 0:
        stderr = result.stderr or ""
        sys.stderr.write(stderr)
        # 偵測目標 repo Issues 停用（gh 訊息含 "Issues" 與 disabled 語意）
        if "disabled" in stderr.lower() and "issue" in stderr.lower():
            return emit_degraded(
                f"目標 repo {FRAMEWORK_REPO} 的 Issues 功能已停用",
                "於 repo Settings 啟用 Issues，或聯絡 repo 管理者",
            )
        return emit_degraded(
            "gh 命令回報錯誤（見上方 stderr）",
            "檢查上方 gh 錯誤訊息並修正參數或權限",
        )

    if success_msg:
        sys.stderr.write(f"[framework-issue] {success_msg}\n")
    return 0
