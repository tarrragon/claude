#!/usr/bin/env python3
"""framework-issue feedback：列出上一版發版後的回饋（主控方的發版後回饋檢查）。

上一版的界線是它的 tag 時間：本地 `v<版號>` tag 的 commit 時間，本地沒有時改查
框架 repo 的遠端 tag。兩處都查不到時不猜測，exit 非 0 並要求 `--since`。

界線之後的動靜分三類：

- 新開：issue 建立時間在界線之後
- 新觀測：界線之後有帶 observation 標記的留言
- 未標記留言：界線之後只有不帶任何標記的留言；另列，不計入回饋數

區段留言（section 標記）是 owner 維護的整理內容，不屬回饋，三類都不計。
不用 updatedAt 判定：主控方的分診留言也會更新 updatedAt，會被誤判為回饋。

規則依據：`.claude/pm-rules/version-progression.md`〈版本生命週期〉「發版後回饋檢查」。
"""

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, List, Optional

from gh_common import FRAMEWORK_REPO, emit_degraded, preflight

EXIT_NEED_SINCE = 2

PROJECT_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_TODOLIST = PROJECT_ROOT / "docs" / "todolist.yaml"

CATEGORY_NEW = "新開"
CATEGORY_OBSERVATION = "新觀測"
CATEGORY_UNMARKED = "未標記留言"
UNKNOWN = "unknown"

# 標記格式與 section_comment.py、create_issue.py 寫入端一致。
OBSERVATION_MARKER_RE = re.compile(r"^<!-- observation: .+? by .+? -->")
SECTION_MARKER_RE = re.compile(r"^<!-- section: .+? owner: .+? -->")
FRAMEWORK_VERSION_RE = re.compile(r"<!-- framework-version: (?P<version>.+?) -->")
ENV_INFO_RE = re.compile(r"<!-- env-info -->(?P<block>.*?)<!-- /env-info -->", re.S)
ENV_VERSION_RE = re.compile(r"^- 框架版本: (?P<version>.+?)\s*$", re.M)

_VERSION_LINE_RE = re.compile(r'^\s*-\s*version:\s*"?(?P<version>[0-9][^"\s]*)"?\s*$')
_STATUS_LINE_RE = re.compile(r'^\s*status:\s*"?(?P<status>[a-z_]+)"?\s*$')

GhRunner = Callable[[List[str]], str]


class FeedbackError(Exception):
    """無法完成查詢；訊息給使用者看，exit code 由 code 決定。"""

    def __init__(self, message: str, code: int):
        super().__init__(message)
        self.code = code


def parse_time(value: str) -> datetime:
    """解析 ISO 8601 時間（含 `Z` 後綴）；只有日期時視為當天 00:00 UTC。"""
    text = value.strip().replace("Z", "+00:00")
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _version_key(version: str) -> tuple:
    return tuple(int(part) if part.isdigit() else 0 for part in version.split("."))


def last_completed_version(todolist_path: Path) -> Optional[str]:
    """todolist 中版號最高的 completed 版本；檔案缺失或沒有 completed 版本回傳 None。"""
    try:
        lines = todolist_path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        sys.stderr.write(f"[framework-issue] 讀不到 {todolist_path}：{exc}\n")
        return None
    completed = []
    current = None
    for line in lines:
        version_match = _VERSION_LINE_RE.match(line)
        if version_match:
            current = version_match.group("version")
            continue
        status_match = _STATUS_LINE_RE.match(line)
        if status_match and current is not None:
            if status_match.group("status") == "completed":
                completed.append(current)
            current = None
    if not completed:
        return None
    return max(completed, key=_version_key)


def local_tag_time(version: str) -> Optional[str]:
    """本地 `v<版號>` tag 指向 commit 的時間；tag 不存在或 git 失敗回傳 None。"""
    try:
        result = subprocess.run(
            ["git", "-C", str(PROJECT_ROOT), "log", "-1", "--format=%cI", f"refs/tags/v{version}"],
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        sys.stderr.write(f"[framework-issue] git 查本地 tag 失敗：{exc}\n")
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def remote_tag_time(version: str, gh: GhRunner) -> Optional[str]:
    """框架 repo 遠端 `v<版號>` tag 指向 commit 的時間；查不到回傳 None。"""
    try:
        out = gh(["api", f"repos/{FRAMEWORK_REPO}/commits/v{version}", "--jq", ".commit.committer.date"])
    except FeedbackError:
        return None
    return out.strip() or None


def default_gh(args: List[str]) -> str:
    """執行 gh 並回傳 stdout；失敗轉為 FeedbackError（訊息含 gh stderr）。"""
    try:
        result = subprocess.run(["gh", *args], capture_output=True, text=True, timeout=120)
    except (OSError, subprocess.SubprocessError) as exc:
        raise FeedbackError(f"gh 執行失敗：{exc}", 3) from exc
    if result.returncode != 0:
        raise FeedbackError(f"gh {' '.join(args[:2])} 失敗：{result.stderr.strip()}", 3)
    return result.stdout


def resolve_boundary(args, gh: GhRunner) -> dict:
    """決定界線：--since 優先，其次 --since-version，最後 todolist 最後一個 completed。"""
    if args.since:
        return {"version": args.since_version, "since": parse_time(args.since), "source": "--since"}
    version = args.since_version or last_completed_version(Path(args.todolist))
    if not version:
        raise FeedbackError(
            "todolist 沒有 completed 版本，無法決定上一版；請以 --since-version 或 --since 指定",
            EXIT_NEED_SINCE,
        )
    local = local_tag_time(version)
    if local:
        return {"version": version, "since": parse_time(local), "source": "本地 tag"}
    remote = remote_tag_time(version, gh)
    if remote:
        return {"version": version, "since": parse_time(remote), "source": "遠端 tag"}
    raise FeedbackError(
        f"本地與 {FRAMEWORK_REPO} 都找不到 tag v{version}，無法決定界線；"
        "請以 --since <ISO 時間> 指定上一版發版時間",
        EXIT_NEED_SINCE,
    )


def fetch_candidate_issues(since: datetime, limit: int, gh: GhRunner) -> list:
    """界線之後有更新的 issue（updatedAt 只作粗篩，分類另依建立時間與留言標記）。"""
    stamp = since.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    out = gh([
        "issue", "list", "--repo", FRAMEWORK_REPO, "--state", "all",
        "--limit", str(limit), "--search", f"updated:>={stamp}",
        "--json", "number,title,createdAt,labels,body,state",
    ])
    return json.loads(out or "[]")


def fetch_comments_since(number: int, since: datetime, gh: GhRunner) -> list:
    """issue 在界線之後建立的留言（REST since 依 updated_at 過濾，這裡再以 created_at 收斂）。"""
    stamp = since.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    out = gh([
        "api", "--paginate",
        f"repos/{FRAMEWORK_REPO}/issues/{number}/comments?since={stamp}&per_page=100",
        "--jq", ".[] | {created_at, body}",
    ])
    comments = [json.loads(line) for line in out.splitlines() if line.strip()]
    return [c for c in comments if parse_time(c["created_at"]) >= since]


def env_info_version(body: str) -> Optional[str]:
    """issue body 環境資訊區段中的框架版本；沒有區段或沒有該列回傳 None。"""
    block = ENV_INFO_RE.search(body or "")
    if not block:
        return None
    match = ENV_VERSION_RE.search(block.group("block"))
    return match.group("version") if match else None


def classify_issue(issue: dict, comments: list, since: datetime) -> Optional[dict]:
    """把一張 issue 歸入三類之一；界線後沒有新開也沒有任何非區段留言時回傳 None。"""
    observations = [c for c in comments if OBSERVATION_MARKER_RE.match(c.get("body") or "")]
    unmarked = [
        c for c in comments
        if not OBSERVATION_MARKER_RE.match(c.get("body") or "")
        and not SECTION_MARKER_RE.match(c.get("body") or "")
    ]
    observations.sort(key=lambda c: parse_time(c["created_at"]))
    is_new = parse_time(issue["createdAt"]) >= since

    if is_new:
        category = CATEGORY_NEW
    elif observations:
        category = CATEGORY_OBSERVATION
    elif unmarked:
        category = CATEGORY_UNMARKED
    else:
        return None

    version = None
    if observations:
        match = FRAMEWORK_VERSION_RE.search(observations[-1]["body"])
        version = match.group("version") if match else None
    if category == CATEGORY_NEW:
        version = env_info_version(issue.get("body", "")) or version

    return {
        "number": issue["number"],
        "title": issue["title"],
        "category": category,
        "created": issue["createdAt"],
        "last_qualifying_comment": observations[-1]["created_at"] if observations else None,
        "framework_version": version or UNKNOWN,
        "labels": [label["name"] for label in issue.get("labels", [])],
        "unmarked_comments": len(unmarked),
    }


def collect_feedback(since: datetime, limit: int, gh: GhRunner) -> list:
    rows = []
    for issue in fetch_candidate_issues(since, limit, gh):
        comments = fetch_comments_since(issue["number"], since, gh)
        row = classify_issue(issue, comments, since)
        if row:
            rows.append(row)
    order = {CATEGORY_NEW: 0, CATEGORY_OBSERVATION: 1, CATEGORY_UNMARKED: 2}
    rows.sort(key=lambda r: (order[r["category"]], r["number"]))
    return rows


def summarize(rows: list) -> dict:
    new = sum(1 for r in rows if r["category"] == CATEGORY_NEW)
    observed = sum(1 for r in rows if r["category"] == CATEGORY_OBSERVATION)
    unmarked = sum(1 for r in rows if r["category"] == CATEGORY_UNMARKED)
    return {"feedback_count": new + observed, "new": new, "observation": observed, "unmarked": unmarked}


def render_text(boundary: dict, rows: list) -> str:
    counts = summarize(rows)
    label = f"v{boundary['version']}" if boundary.get("version") else "（未指定版本）"
    lines = [
        f"上一版：{label}，界線 {boundary['since'].isoformat()}（來源：{boundary['source']}）",
        f"回饋數：{counts['feedback_count']}（新開 {counts['new']}、新觀測 {counts['observation']}）；"
        f"未標記留言 {counts['unmarked']} 筆另列，不計入",
    ]
    if not rows:
        return "\n".join(lines)
    lines += [
        "",
        "| # | 標題 | 類別 | 建立時間 | 最後合格留言 | 框架版本 | 標籤 |",
        "|---|------|------|----------|--------------|----------|------|",
    ]
    for r in rows:
        lines.append(
            f"| {r['number']} | {r['title']} | {r['category']} | {r['created']} | "
            f"{r['last_qualifying_comment'] or '-'} | {r['framework_version']} | "
            f"{', '.join(r['labels']) or '-'} |"
        )
    return "\n".join(lines)


def render_json(boundary: dict, rows: list) -> str:
    payload = {
        "version": boundary.get("version"),
        "since": boundary["since"].isoformat(),
        "since_source": boundary["source"],
        "summary": summarize(rows),
        "issues": rows,
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="framework-issue feedback",
        description="列出上一版發版後的回饋：新開、新觀測，未標記留言另列不計入",
    )
    parser.add_argument("--since-version", default="", help="上一版版號（預設取 todolist 版號最高的 completed 版本）")
    parser.add_argument("--since", default="", help="直接指定界線時間（ISO 8601），優先於 --since-version")
    parser.add_argument("--todolist", default=str(DEFAULT_TODOLIST), help="版本索引路徑（預設 docs/todolist.yaml）")
    parser.add_argument("--limit", type=int, default=200, help="粗篩 issue 上限（預設 200）")
    parser.add_argument("--json", action="store_true", help="輸出 JSON")
    return parser


def main(argv=None, gh: GhRunner = default_gh) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.since:
            parse_time(args.since)
    except ValueError:
        sys.stderr.write(f"[framework-issue] --since 不是 ISO 8601 時間：{args.since}\n")
        return EXIT_NEED_SINCE

    gate = preflight()
    if gate != 0:
        return gate

    try:
        boundary = resolve_boundary(args, gh)
        rows = collect_feedback(boundary["since"], args.limit, gh)
    except FeedbackError as exc:
        if exc.code == EXIT_NEED_SINCE:
            sys.stderr.write(f"[framework-issue] {exc}\n")
            return exc.code
        return emit_degraded(str(exc), "確認 gh 已登入且網路可用後重試")

    sys.stdout.write((render_json if args.json else render_text)(boundary, rows) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
