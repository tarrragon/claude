"""sync push 推送前：比對本地記錄的 base 與 canonical HEAD，產生警告訊息。

push 以本地 tracked 樹整樹覆蓋 canonical，同路徑一律以推送方為準。推送方的
副本若落後 canonical（他方在上次同步後推過），推送會把他方的修改蓋回舊版本，
過程沒有任何訊號。本模組只產生訊息、不阻擋：判斷「是否真的會蓋掉他方內容」
需要逐檔比對，不在這裡做。

四種情況：
  - base == canonical HEAD：不輸出。
  - base 是祖先、HEAD 已前進：[WARNING]，列出前進的 commit 數，建議先 sync-pull。
  - base 不在 canonical 歷史中（不存在或已分歧）：[WARNING]。
  - 讀不到 base 或 clone 無法查詢：[INFO] 說明原因，照常推送。
"""

import subprocess
from pathlib import Path


def _git(clone_dir: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=clone_dir, capture_output=True, text=True
    )


def describe_canonical_drift(clone_dir: Path, base_sha: str | None) -> list[str]:
    """回傳要印出的訊息行；空 list 表示 base 與 canonical HEAD 一致。

    參數:
        clone_dir: canonical 的完整 clone（需含歷史，才能判斷祖先關係）
        base_sha: 本地 sync-base.json 記錄的 last_synced_base_sha
    """
    if not base_sha:
        return [
            "[INFO] 讀不到 last_synced_base_sha，略過 canonical 前進檢查，照常推送"
        ]
    head = _git(clone_dir, "rev-parse", "HEAD")
    if head.returncode != 0:
        return [
            f"[INFO] 無法讀取 canonical HEAD（{head.stderr.strip()}），"
            "略過 canonical 前進檢查，照常推送"
        ]
    head_sha = head.stdout.strip()
    if head_sha == base_sha:
        return []

    short_base, short_head = base_sha[:9], head_sha[:9]
    exists = _git(clone_dir, "cat-file", "-e", f"{base_sha}^{{commit}}")
    is_ancestor = (
        exists.returncode == 0
        and _git(clone_dir, "merge-base", "--is-ancestor", base_sha, head_sha).returncode == 0
    )
    if not is_ancestor:
        return [
            f"[WARNING] 本地記錄的 base {short_base} 不在 canonical 歷史中"
            f"（canonical HEAD {short_head}）。",
            "  無法判斷本地副本與 canonical 的先後；推送會以本地內容覆蓋同路徑檔案。",
            "  建議先 sync-pull 對齊 base 再推送；照常推送不受此警告阻擋。",
        ]

    count = _git(clone_dir, "rev-list", "--count", f"{base_sha}..{head_sha}")
    ahead = count.stdout.strip() if count.returncode == 0 else "若干"
    return [
        f"[WARNING] canonical 在本地上次同步（base {short_base}）之後前進了 {ahead} 個 commit"
        f"（canonical HEAD {short_head}）。",
        "  推送會以本地內容覆蓋同路徑檔案，這些 commit 對同路徑的修改會被蓋回。",
        "  建議先 sync-pull 收入再推送；照常推送不受此警告阻擋。",
    ]
