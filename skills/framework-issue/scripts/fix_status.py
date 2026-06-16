#!/usr/bin/env python3
"""framework-issue fix-status：跨 consumer 修復追蹤矩陣（軸 C）。

framework issue body 作修復狀態 SSOT：以標記區段
`<!-- fix-matrix -->...<!-- /fix-matrix -->` 內嵌 markdown 表格
`| consumer | status |`，記錄哪些 consumer 修了該壞 change（flat-base 號
無狀態無法追蹤，此為 framework issue 的獨有價值）。

命令：
- `fix-status <issue-ref>`（view）：gh issue view --json body 取 body，
  解析矩陣區段顯示各 consumer 修復狀態。
- `fix-status <issue-ref> --mark-fixed`：把「本 consumer」列標為 fixed，
  gh issue edit --body-file 回寫；矩陣不存在則初始化後寫入本 consumer 列。

consumer 自我識別：沿用 `_project-registry.yaml` + git toplevel basename
（同 error-pattern allocator 的 identify_project_code），不要求手動傳 consumer
名，避免人為填錯前綴。

降級：沿用 gh_common.preflight()，gh 不可用 / 未登入 / Issues 停用時優雅降級
（exit 3），不拋 traceback、不真打 GitHub API（測試以 mock 攔截 subprocess）。
"""

import argparse
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from gh_common import (
    FRAMEWORK_REPO,
    emit_degraded,
    preflight,
    run_gh,
)

# 修復矩陣標記區段（issue body 內嵌；read 解析、write 替換此段）
MATRIX_BEGIN = "<!-- fix-matrix -->"
MATRIX_END = "<!-- /fix-matrix -->"
# 矩陣表頭（初始化與重建時使用）
MATRIX_HEADER = "| consumer | status |\n|----------|--------|"
# 偵測整個矩陣區段（含標記）以便整段替換
MATRIX_SECTION_RE = re.compile(
    re.escape(MATRIX_BEGIN) + r".*?" + re.escape(MATRIX_END),
    re.DOTALL,
)
# 解析矩陣內的資料列：`| <consumer> | <status> |`（跳過表頭與分隔線）
MATRIX_ROW_RE = re.compile(r"^\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*$")

# 專案代號 SSOT（與 error-pattern allocator 共用同一註冊表）
REGISTRY_PATH = (
    Path(__file__).resolve().parent.parent.parent.parent
    / "error-patterns"
    / "_project-registry.yaml"
)

FIXED_STATUS = "fixed"


def get_git_toplevel() -> str:
    """取得目前 git repo 的 toplevel 路徑（basename 用於 registry 反查）。"""
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        timeout=15,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "git rev-parse 失敗")
    return result.stdout.strip()


def identify_consumer(registry_path, repo_toplevel) -> str:
    """以 git toplevel basename 反查 registry `dir` 取得本 consumer 代號 `code`。

    與 error-pattern allocator identify_project_code 同源邏輯：tooling 零
    project-local 設定即可自我識別。basename 未登錄時拋 ValueError，避免靜默
    產生錯誤 consumer 名。
    """
    import yaml

    data = yaml.safe_load(Path(registry_path).read_text(encoding="utf-8")) or {}
    basename = Path(repo_toplevel).name
    for proj in data.get("projects", []):
        if proj.get("dir") == basename:
            return proj["code"]
    raise ValueError(
        f"專案目錄 '{basename}' 未登錄於 {registry_path}。"
        "新 consumer 首次標記修復前須先登錄 code + dir（見 numbering methodology）。"
    )


def parse_matrix(body: str) -> dict:
    """從 issue body 解析修復矩陣，回傳 {consumer: status} 有序字典。

    矩陣區段不存在或無資料列時回傳空 dict（由上層判斷初始化 / 顯示空）。
    """
    section = MATRIX_SECTION_RE.search(body or "")
    if not section:
        return {}
    rows = {}
    for line in section.group().splitlines():
        match = MATRIX_ROW_RE.match(line)
        if not match:
            continue
        consumer, status = match.group(1).strip(), match.group(2).strip()
        # 跳過表頭列與分隔線列（consumer 欄字面為 "consumer" 或全為 - 符號）
        if consumer.lower() == "consumer" or set(consumer) <= {"-"}:
            continue
        rows[consumer] = status
    return rows


def render_matrix(rows: dict) -> str:
    """把 {consumer: status} 渲染為含標記的完整矩陣區段字串。"""
    lines = [MATRIX_BEGIN, MATRIX_HEADER]
    for consumer, status in rows.items():
        lines.append(f"| {consumer} | {status} |")
    lines.append(MATRIX_END)
    return "\n".join(lines)


def upsert_matrix(body: str, rows: dict) -> str:
    """把渲染後矩陣寫回 body：既有區段整段替換，否則 append 於 body 末。"""
    rendered = render_matrix(rows)
    body = body or ""
    if MATRIX_SECTION_RE.search(body):
        return MATRIX_SECTION_RE.sub(lambda _: rendered, body, count=1)
    separator = "\n\n" if body and not body.endswith("\n") else "\n"
    return f"{body}{separator}{rendered}\n"


def fetch_body(issue_ref: str) -> str:
    """以 gh issue view --json body 取 issue body（mock 攔截點，不真打 API）。"""
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


def view_matrix(issue_ref: str) -> int:
    """view 模式：取 body、解析矩陣、以表格形式印至 stdout。"""
    try:
        body = fetch_body(issue_ref)
    except (OSError, subprocess.SubprocessError, RuntimeError, ValueError) as exc:
        return emit_degraded(
            f"讀取 issue {issue_ref} 失敗：{exc}",
            "確認 issue ref 正確且 gh 可存取該 repo 後重試",
        )

    rows = parse_matrix(body)
    if not rows:
        sys.stdout.write(
            f"[framework-issue] {issue_ref} 尚無修復矩陣"
            "（用 --mark-fixed 初始化）\n"
        )
        return 0

    sys.stdout.write(f"修復矩陣 @ {issue_ref}\n")
    sys.stdout.write(f"{MATRIX_HEADER}\n")
    for consumer, status in rows.items():
        sys.stdout.write(f"| {consumer} | {status} |\n")
    return 0


def mark_fixed(issue_ref: str, consumer: str) -> int:
    """mark-fixed 模式：把本 consumer 標為 fixed 並回寫 issue body。"""
    try:
        body = fetch_body(issue_ref)
    except (OSError, subprocess.SubprocessError, RuntimeError, ValueError) as exc:
        return emit_degraded(
            f"讀取 issue {issue_ref} 失敗：{exc}",
            "確認 issue ref 正確且 gh 可存取該 repo 後重試",
        )

    rows = parse_matrix(body)
    rows[consumer] = FIXED_STATUS  # 矩陣不存在時等同初始化本 consumer 列
    new_body = upsert_matrix(body, rows)

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
            success_msg=f"已標記 consumer={consumer} 為 {FIXED_STATUS} @ {issue_ref}",
        )
    finally:
        Path(body_file).unlink(missing_ok=True)
    return rc


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="framework-issue fix-status",
        description="查詢 / 更新 framework issue 的跨 consumer 修復矩陣",
    )
    parser.add_argument(
        "issue_ref",
        help="framework issue ref（如 tarrragon/claude#42 或純號 42）",
    )
    parser.add_argument(
        "--mark-fixed",
        action="store_true",
        help="把本 consumer 標記為已修復並回寫 issue body",
    )
    parsed = parser.parse_args(argv)

    gate = preflight()
    if gate != 0:
        return gate

    if not parsed.mark_fixed:
        return view_matrix(parsed.issue_ref)

    # mark-fixed 需自我識別本 consumer（不接受手動傳入）
    try:
        toplevel = get_git_toplevel()
        consumer = identify_consumer(REGISTRY_PATH, toplevel)
    except (OSError, subprocess.SubprocessError, RuntimeError, ValueError) as exc:
        return emit_degraded(
            f"無法識別本 consumer：{exc}",
            "確認位於已登錄於 _project-registry.yaml 的 git repo 內後重試",
        )
    return mark_fixed(parsed.issue_ref, consumer)


if __name__ == "__main__":
    sys.exit(main())
