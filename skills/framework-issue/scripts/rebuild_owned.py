#!/usr/bin/env python3
"""framework-issue rebuild-owned：明示重建本專案的 owned-issues 登記檔。

SessionStart 的 issue 檢查只讀登記檔，登記檔不存在時不發任何 gh 命令。
登記檔平常由 section_comment.py 的 init／add／update／transfer-owner 在寫入
GitHub 成功後自動登記；以下情況要用本命令補登：
- 新 clone 的專案
- 本功能上線前就擁有區段的 issue
- 繞過 CLI 直接以 gh api 寫的區段

本命令會把 owner 前綴（預設為專案目錄名）送到 GitHub 搜尋。送出前先印出
將送出的資料；`--dry-run` 只印出、不送出。

步驟：
1. 以 `gh search issues --match comments "owner <前綴>"` 找候選 issue。
2. 逐張讀 comments 的首行，區段標記的 owner 以 `<前綴>-` 開頭者視為本專案擁有。
3. 以結果整份覆寫登記檔；查無時寫入空清單，之後的 SessionStart 不再發 gh 命令。
"""

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from typing import Callable, List, Optional

from gh_common import FRAMEWORK_REPO, emit_degraded, preflight
import owned_issues_registry as registry

DEFAULT_LIMIT = 30
SECTION_MARKER_RE = re.compile(r"^<!-- section: (?P<name>.+?) owner: (?P<owner>.+?) -->")

GhRunner = Callable[[List[str]], str]


class RebuildError(Exception):
    """gh 呼叫失敗；訊息給使用者看。"""


def default_prefix() -> str:
    """owner 前綴預設值：共用狀態根（主倉庫）的目錄名，底線改連字號。"""
    return registry.get_shared_state_root().name.replace("_", "-")


def default_gh(args: List[str]) -> str:
    try:
        result = subprocess.run(["gh", *args], capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError) as exc:
        raise RebuildError(f"gh 執行失敗：{exc}") from exc
    if result.returncode != 0:
        raise RebuildError(f"gh {' '.join(args[:2])} 失敗：{result.stderr.strip()}")
    return result.stdout


def outbound_description(prefix: str, limit: int) -> str:
    """送出前印給使用者看的資料清單。"""
    return "\n".join([
        f"[rebuild-owned] 將送到 GitHub（{FRAMEWORK_REPO}）的資料：",
        f"  - 搜尋字串：\"owner {prefix}\"（gh search issues --match comments，最多 {limit} 筆）",
        "  - 候選 issue 的編號（逐張讀取 comments 以驗證 owner）",
    ])


def search_candidates(prefix: str, limit: int, gh: GhRunner) -> List[int]:
    out = gh([
        "search", "issues", "--repo", FRAMEWORK_REPO, "--match", "comments",
        "--json", "number", "--limit", str(limit), "--", f"owner {prefix}",
    ])
    return [hit["number"] for hit in json.loads(out or "[]")]


def owner_of(number: int, prefix: str, gh: GhRunner) -> Optional[str]:
    """issue 中第一個 owner 以 `<prefix>-` 開頭的區段標記的 owner；沒有回傳 None。"""
    out = gh([
        "api", "--paginate", f"repos/{FRAMEWORK_REPO}/issues/{number}/comments",
        "--jq", '.[] | .body | split("\\n")[0]',
    ])
    for line in out.splitlines():
        match = SECTION_MARKER_RE.match(line.strip())
        if match and match.group("owner").startswith(f"{prefix}-"):
            return match.group("owner")
    return None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="framework-issue rebuild-owned",
        description="明示重建本專案的 owned-issues 登記檔（會把 owner 前綴送到 GitHub 搜尋）",
    )
    parser.add_argument("--owner-prefix", default="", help="owner 前綴（預設為專案目錄名，底線改連字號）")
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT, help=f"候選上限（預設 {DEFAULT_LIMIT}）")
    parser.add_argument("--dry-run", action="store_true", help="只印出將送出的資料，不送出、不寫檔")
    return parser


def main(argv=None, gh: GhRunner = default_gh) -> int:
    args = build_parser().parse_args(argv)
    prefix = args.owner_prefix or default_prefix()
    print(outbound_description(prefix, args.limit))
    if args.dry_run:
        print("[rebuild-owned] --dry-run：未送出，登記檔未變更")
        return 0

    gate = preflight()
    if gate != 0:
        return gate

    try:
        entries = []
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        for number in search_candidates(prefix, args.limit, gh):
            owner = owner_of(number, prefix, gh)
            if owner:
                entries.append({"number": number, "owner": owner, "updated_at": now})
    except (RebuildError, json.JSONDecodeError, KeyError) as exc:
        return emit_degraded(f"重建中止，登記檔未變更：{exc}", "確認 gh 已登入且網路可用後重試")

    try:
        path = registry.write_registry(entries)
    except OSError as exc:
        sys.stderr.write(f"[framework-issue] 登記檔寫入失敗：{exc}\n")
        return 1

    numbers = ", ".join(f"#{e['number']}（{e['owner']}）" for e in entries) or "無"
    print(f"[rebuild-owned] 已寫入 {path}")
    print(f"[rebuild-owned] 本專案擁有的 issue：{numbers}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
