#!/usr/bin/env python3
"""framework-issue fix-version：issue 修復版本號註記（軸 D，供 close 前置檢查）。

多專案共用框架經 sync-push/pull 同步。issue 修復後若未回註框架版本號，
其他 consumer 專案 sync-pull 時無法判斷該直接同步還是接續排查新徵狀
（同一 issue 事後發現第二類徵狀時尤其明顯）。本命令在 issue body 維護
一份版本號註記列表，供 `close_issue.py` 作前置檢查，也供其他 consumer
比對「本地是否已含此修復」。

命令：
- `fix-version <issue-ref> --summary "<徵狀摘要>" [--version X.Y.Z] [--date YYYY-MM-DD]`：
  於 issue body 追加一筆版本號註記；`--version` 省略時讀取本地
  `.claude/VERSION`（即 sync-push 後已同步至框架 repo 的版本號）。

冪等：同版本號重複標記為**更新既有列**（覆蓋日期/摘要），不新增重複列。

標記區段 `<!-- fix-versions -->...<!-- /fix-versions -->` 與既有
`fix-matrix`（軸 C：per-consumer 修復狀態）並存但不混用，各自獨立解析
與回寫，互不覆蓋對方區段。

降級：沿用 gh_common.preflight()，gh 不可用 / 未登入時優雅降級
（exit 3），不拋 traceback、不真打 GitHub API（測試以 mock 攔截
subprocess）。
"""

import argparse
import datetime
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from gh_common import (
    FRAMEWORK_REPO,
    emit_degraded,
    normalize_issue_ref,
    preflight,
    run_gh,
)
from section_table import upsert_section

# 版本號註記標記區段（issue body 內嵌；read 解析、write 替換此段）
VERSIONS_BEGIN = "<!-- fix-versions -->"
VERSIONS_END = "<!-- /fix-versions -->"
# 表頭（初始化與重建時使用）
VERSIONS_HEADER = "| version | date | summary |\n|---------|------|---------|"
# 偵測整個區段（含標記）以便整段替換
VERSIONS_SECTION_RE = re.compile(
    re.escape(VERSIONS_BEGIN) + r".*?" + re.escape(VERSIONS_END),
    re.DOTALL,
)
# 解析區段內的資料列：`| <version> | <date> | <summary> |`（跳過表頭與分隔線）
VERSIONS_ROW_RE = re.compile(
    r"^\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*$"
)

# 本地框架版本號 SSOT（sync-push 後代表已同步至框架 repo 的版本）
FRAMEWORK_VERSION_PATH = (
    Path(__file__).resolve().parent.parent.parent.parent / "VERSION"
)


def read_framework_version(path=FRAMEWORK_VERSION_PATH) -> str:
    """讀取本地框架 VERSION 檔。空檔或不存在時拋例外交由呼叫端降級處理。"""
    text = Path(path).read_text(encoding="utf-8").strip()
    if not text:
        raise ValueError(f"{path} 內容為空")
    return text


def parse_versions(body: str) -> dict:
    """從 issue body 解析 fix-versions 區段，回傳 {version: (date, summary)}。

    區段不存在或無資料列時回傳空 dict（由上層判斷初始化 / 視為未註記）。
    """
    section = VERSIONS_SECTION_RE.search(body or "")
    if not section:
        return {}
    rows = {}
    for line in section.group().splitlines():
        match = VERSIONS_ROW_RE.match(line)
        if not match:
            continue
        version, date, summary = (g.strip() for g in match.groups())
        # 跳過表頭列與分隔線列（version 欄字面為 "version" 或全為 - 符號）
        if version.lower() == "version" or set(version) <= {"-"}:
            continue
        rows[version] = (date, summary)
    return rows


def has_fix_versions(body: str) -> bool:
    """close 前置檢查用：fix-versions 區段存在且至少一筆版本號註記。"""
    return bool(parse_versions(body))


def render_versions(rows: dict) -> str:
    """把 {version: (date, summary)} 渲染為含標記的完整區段字串。"""
    lines = [VERSIONS_BEGIN, VERSIONS_HEADER]
    for version, (date, summary) in rows.items():
        lines.append(f"| {version} | {date} | {summary} |")
    lines.append(VERSIONS_END)
    return "\n".join(lines)


def upsert_versions(body: str, rows: dict) -> str:
    """把渲染後區段寫回 body：既有區段整段替換，否則 append 於 body 末。"""
    return upsert_section(body, VERSIONS_SECTION_RE, render_versions(rows))


def fetch_body(issue_ref: str) -> str:
    """以 gh issue view --json body 取 issue body（mock 攔截點，不真打 API）。

    不要求 issue 為 open 狀態：closed issue 仍可讀 body 供後續追加版本號。
    """
    result = subprocess.run(
        [
            "gh", "issue", "view", issue_ref,
            "--repo", FRAMEWORK_REPO,
            "--json", "body",
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "gh issue view 失敗")
    payload = json.loads(result.stdout or "{}")
    return payload.get("body", "") or ""


def mark_version(issue_ref: str, version: str, summary: str, date: str) -> int:
    """把版本號註記寫入 issue body（同版本覆蓋既有列，不新增重複列）。"""
    try:
        body = fetch_body(issue_ref)
    except (OSError, subprocess.SubprocessError, RuntimeError, ValueError) as exc:
        return emit_degraded(
            f"讀取 issue {issue_ref} 失敗：{exc}",
            "確認 issue ref 正確且 gh 可存取該 repo 後重試",
        )

    rows = parse_versions(body)
    rows[version] = (date, summary)
    new_body = upsert_versions(body, rows)

    # 以暫存檔走 --body-file 回寫，避免長 body / 特殊字元造成參數問題
    with tempfile.NamedTemporaryFile(
        "w", suffix=".md", delete=False, encoding="utf-8"
    ) as handle:
        handle.write(new_body)
        body_file = handle.name
    try:
        rc = run_gh(
            [
                "issue", "edit", issue_ref,
                "--repo", FRAMEWORK_REPO,
                "--body-file", body_file,
            ],
            success_msg=f"已註記版本 {version} @ {issue_ref}",
        )
    finally:
        Path(body_file).unlink(missing_ok=True)
    return rc


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="framework-issue fix-version",
        description="於 issue body 追加修復版本號註記（供 close 前置檢查）",
    )
    parser.add_argument(
        "issue_ref",
        help="framework issue ref（如 tarrragon/claude#42 或純號 42）",
    )
    parser.add_argument(
        "--version",
        default="",
        help="修復版本號（省略時讀取本地 .claude/VERSION，即 sync-push 後的框架版本）",
    )
    parser.add_argument(
        "--summary",
        required=True,
        help="徵狀摘要（本次修復對應的問題描述）",
    )
    parser.add_argument(
        "--date",
        default="",
        help="日期（ISO 格式，省略時為今日；主要供測試固定值使用）",
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

    version = parsed.version
    if not version:
        try:
            version = read_framework_version()
        except (OSError, ValueError) as exc:
            return emit_degraded(
                f"無法讀取框架版本號：{exc}",
                "確認已執行 sync-push 且 .claude/VERSION 存在且非空，"
                "或改用 --version 手動指定",
            )

    date = parsed.date or datetime.date.today().isoformat()
    return mark_version(issue_ref, version, parsed.summary, date)


if __name__ == "__main__":
    sys.exit(main())
