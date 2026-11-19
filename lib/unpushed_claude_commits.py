"""計算本地 `.claude/` 有多少 commit 尚未推送到 framework canonical。

修復在來源端驗證通過，並不代表已經推到 canonical；consumer 要等推送後才拿得到。
這裡只計數、不阻擋，結果列在推送與發版的決策點（sync-push dry-run、
version-release check），不放在 SessionStart：本 repo 在兩次發版之間恆有未推
commit，每個 session 都提醒會變成噪音。

錨點：本地 git 中最後一次寫入 `.claude/sync-base.json` 的 commit。push 與 pull
成功後都會 commit 這個檔，所以它標記「上次與 canonical 同步」的位置；用 git
歷史而非本機狀態檔，任何 clone 都算得出來，也不需要連網。
計數：錨點之後、動到 `.claude/` 的非 merge commit，不含 sync-base.json 本身。

skill 套件（如 version-release）不 import 框架 lib，該處另有一份同義實作；
本檔判準變更時兩處一起改。
"""

import subprocess
from pathlib import Path
from typing import NamedTuple

SYNC_BASE_PATH = ".claude/sync-base.json"


class UnpushedCount(NamedTuple):
    count: int | None  # None 表示無法計算，原因見 reason
    anchor: str | None
    reason: str | None


def _git(project_root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=project_root, capture_output=True, text=True
    )


def count_unpushed_claude_commits(project_root: Path) -> UnpushedCount:
    """回傳錨點之後動到 `.claude/` 的非 merge commit 數（不含 sync-base.json）。"""
    if not Path(project_root).is_dir():
        return UnpushedCount(None, None, f"{project_root} 不存在")
    anchor = _git(project_root, "log", "-1", "--format=%H", "--", SYNC_BASE_PATH)
    if anchor.returncode != 0:
        return UnpushedCount(None, None, f"git log 失敗：{anchor.stderr.strip()}")
    anchor_sha = anchor.stdout.strip()
    if not anchor_sha:
        return UnpushedCount(None, None, f"git 歷史中沒有 {SYNC_BASE_PATH}（尚未同步過）")
    counted = _git(
        project_root,
        "rev-list", "--count", "--no-merges", f"{anchor_sha}..HEAD",
        "--", ".claude/", f":(exclude){SYNC_BASE_PATH}",
    )
    if counted.returncode != 0:
        return UnpushedCount(None, anchor_sha, f"git rev-list 失敗：{counted.stderr.strip()}")
    return UnpushedCount(int(counted.stdout.strip() or 0), anchor_sha, None)


def format_unpushed_line(result: UnpushedCount) -> str:
    """把計數結果寫成一行輸出；無法計算時說明原因。"""
    if result.count is None:
        return f"未推送的 .claude/ commit：無法計算（{result.reason}）"
    anchor = (result.anchor or "")[:9]
    if result.count == 0:
        return f"未推送的 .claude/ commit：0 個（自上次同步 {anchor} 之後）"
    return (
        f"未推送的 .claude/ commit：{result.count} 個（自上次同步 {anchor} 之後），"
        "consumer 尚未取得這些變更，直到下一次 sync-push"
    )
