#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
.claude 資料夾同步腳本 - 推送到獨立 repo

跨平台支援：macOS / Linux / Windows
依賴：Python 3.8+, git

推送內容（C1，0.19.1-W1-029）:
  - .claude/ 內 **git tracked** 的檔案（以 git archive HEAD -- .claude 取得 tracked
    樹，非從磁碟 walk）。tracked 但須排除者（如 settings.local.json、.sync-state.json、
    憑證）仍經 should_exclude 過濾擋下。
  - project-templates/FLUTTER.md

不推送內容:
  - 根目錄 CLAUDE.md（專案特定配置）
  - 任何 untracked / gitignored 檔（git archive 只取 tracked 樹，從架構層
    消滅 W1-019 secret-leak 風險——機密檔只要未 git add 就不可能被推上去）

commit-first 行為（M1 根因解，0.19.1-W1-030）:
  push 前以 git status --porcelain --untracked=all -- .claude 取工作區全狀態，
  再以 manifest should_exclude 過濾 local-only / 憑證後判定。過濾後仍有變更時
  abort，要求先 commit。因 push 取的是 git tracked 樹（HEAD），未 commit 的變更
  不會被推送——若不先 commit，推上去的內容會與工作區不一致，故強制 commit-first。
  缺陷 T 修復：未進 .gitignore 的 local-only untracked 檔（如 .zhtw-mcp-skip）
  被 should_exclude 過濾，不再誤判為未提交變更而 abort。

刪除傳播（K，0.19.1-W1-029）:
  本地 git rm 的檔案自然不在 git archive HEAD 的 tracked 樹中 → 遠端 git diff
  顯示 D(elete) → commit 帶刪除，刪除自動傳播到遠端。

VERSION（B3，0.19.1-W1-029）:
  本地 .claude/VERSION 純鏡像上游，永不手動修改（W1-016 B2）。push 流程在 clone
  上 bump 遠端 VERSION，base 錨點由 .sync-state.json 的 last_synced_base_sha 承擔。

commit 訊息生成:
  - 無參數時自動分析 .claude/ 相關 commit 生成結構化摘要
  - 提供參數時使用用戶指定的訊息
  - 自動建議版本遞增幅度（patch/minor/major）

Windows 使用者特別注意:
  Windows NTFS 無 executable bit 概念，git 對新增 .py 檔案的 mode
  預設記為 100644（非 100755），會導致下游 pull 後 hook Permission denied。
  本腳本已內建 restore_executable_bits() safety net 防護，
  完整說明與除錯指南詳見 WINDOWS-NOTES.md。
"""

import io
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
from collections import defaultdict
from datetime import datetime
from pathlib import Path

# 排除分類與 should_exclude / compute_content_hash 由 SSOT manifest 統一提供
# （ARCH-020：消除 push/status 重複定義漂移）。manifest 位於 .claude/hooks/lib/。
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "hooks" / "lib"))
from sync_exclude_manifest import (  # noqa: E402
    should_exclude,
    compute_content_hash as _compute_content_hash,
)

REPO_URL = "https://github.com/tarrragon/claude.git"

# .sync-state.json schema（W1-025）：單一 base 欄位，pull/push 共用。
# 禁雙欄位（H1：對 commit SHA 用 max 會選錯共同祖先）。與 sync-claude-pull.py 對稱。
SYNC_STATE_FILENAME = ".sync-state.json"
BASE_SHA_FIELD = "last_synced_base_sha"

# Push 前強制還原 executable bit 的目錄名（與 sync-claude-pull.py 對稱）
# 確保推上去的 git index mode 為 100755，避免下游 pull 拿到 644。
# 注意：以「目錄名」遞迴比對，覆蓋頂層 hooks/ 與 W10-092 遷移後的
# skills/<name>/hooks/（缺陷 G）。
EXECUTABLE_HOOK_DIR_NAMES = ("hooks",)


def iter_executable_hook_dirs(root: Path):
    """遞迴 yield root 下所有名稱屬 EXECUTABLE_HOOK_DIR_NAMES 的目錄。

    取代舊 `root / subdir` 單層查找，使 skills/<name>/hooks/ 也被涵蓋。
    os.walk 預設 followlinks=False，不跟隨 symlink，避免循環。

    參數:
        root: 起始掃描根目錄（temp_dir / staging 樹）

    產出:
        Path: 每個符合名稱的目錄
    """
    if not root.is_dir():
        return
    for dirpath, dirnames, _filenames in os.walk(root):
        for name in dirnames:
            if name in EXECUTABLE_HOOK_DIR_NAMES:
                yield Path(dirpath) / name

# commit 訊息中需要過濾的專案特定模式
# 獨立 repo 是跨專案通用框架，commit 訊息禁止包含專案版本號/Wave/Ticket 編號
PROJECT_SPECIFIC_PATTERNS = [
    r"\b\d+\.\d+\.\d+-W\d+-\d+\b",  # Ticket ID: 0.2.0-W5-014
    r"\bW\d+-\d+\b",                  # 短格式 Ticket: W5-014
    r"\bv\d+\.\d+\.\d+\b",           # 版本號: v0.2.0
    r"\bWave\s*\d+\b",               # Wave 5
    r"\b0\.\d+\.\d+\b",              # 裸版本: 0.2.0
]

# commit type 分類對應的版本遞增建議
VERSION_BUMP_WEIGHTS = {
    "feat": "minor",
    "refactor": "minor",
    "fix": "patch",
    "docs": "patch",
    "chore": "patch",
    "style": "patch",
    "test": "patch",
    "perf": "minor",
    # revert 視為回退性變更，最低 patch；若同批含 feat/refactor 自動升 minor
    "revert": "patch",
}


def print_color(msg: str, color: str = "yellow") -> None:
    """Print colored message (ANSI codes, gracefully degrades on Windows)."""
    colors = {"green": "\033[0;32m", "yellow": "\033[1;33m", "red": "\033[0;31m"}
    nc = "\033[0m"
    if sys.platform == "win32" and not os.environ.get("TERM"):
        print(msg)
    else:
        print(f"{colors.get(color, '')}{msg}{nc}")


def run_git(args: list[str], cwd: str | None = None, check: bool = True) -> subprocess.CompletedProcess:
    """Run a git command and return the result."""
    result = subprocess.run(
        ["git", *args],
        capture_output=True,
        text=True,
        cwd=cwd,
    )
    if check and result.returncode != 0:
        print_color(f"git {' '.join(args)} 失敗: {result.stderr}", "red")
        sys.exit(1)
    return result


def find_project_root() -> Path:
    """Find the project root by looking for .claude/ directory upward."""
    current = Path.cwd()
    while current != current.parent:
        if (current / ".claude").is_dir():
            return current
        current = current.parent
    print_color("找不到 .claude 目錄，請在專案根目錄執行此腳本", "red")
    sys.exit(1)


def read_base_sha(claude_dir: Path) -> str | None:
    """讀取 .sync-state.json 中的 last_synced_base_sha（W1-025 schema，與 pull 對稱）。

    無檔案 / 無欄位 / 解析失敗皆回傳 None（向後相容：無 base 時 fallback）。

    參數:
        claude_dir: .claude 目錄路徑

    傳回:
        str | None: 上次同步的上游 base commit SHA，無則 None
    """
    state_file = claude_dir / SYNC_STATE_FILENAME
    if not state_file.exists():
        return None
    try:
        data = json.loads(state_file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    sha = data.get(BASE_SHA_FIELD)
    return sha if isinstance(sha, str) and sha else None


def write_base_sha(claude_dir: Path, base_sha: str) -> None:
    """push 成功後將遠端 HEAD SHA 寫入 .sync-state.json 的 last_synced_base_sha。

    保留既有欄位（last_push_hash / version / time），僅覆寫單一 base SHA 欄位
    （H1：禁雙欄位，禁對 commit SHA 用 max）。與 sync-claude-pull.py::write_base_sha
    寫同一欄位，確保 pull/push 共用單一 base 錨點。

    參數:
        claude_dir: .claude 目錄路徑
        base_sha: 本次 push 後遠端 HEAD 的 commit SHA
    """
    state_file = claude_dir / SYNC_STATE_FILENAME
    data: dict = {}
    if state_file.exists():
        try:
            data = json.loads(state_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            data = {}
    data[BASE_SHA_FIELD] = base_sha
    state_file.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def ensure_committed(project_root: Path) -> bool:
    """確認 .claude/ 已全數 commit（M1 根因解，0.19.1-W1-030）。

    push 取的是 git tracked 樹（HEAD，見 stage_tracked_tree）；若 .claude/ 有未
    commit 的「會被推送的」變更，推上去的內容會與工作區不一致。故 push 前強制
    commit-first。

    M1 根因解（缺陷 T）：改用 `git status --porcelain --untracked=all -- .claude`
    取工作區全狀態（含 untracked），再以 manifest should_exclude 過濾掉
    local-only / 憑證後判定。

    Why：舊版用 `git diff --quiet` 只看 tracked 檔的 unstaged/staged 變更，完全
    忽略 untracked。這造成兩個反向問題：
      - 缺陷 T 的對稱風險：若改用未過濾的 porcelain，未進 .gitignore 的
        local-only untracked 檔（如 .zhtw-mcp-skip）會被誤判為「未提交變更」
        而 abort——但這類檔本就不會被 push（git archive 只取 tracked 樹），
        不應阻擋 push。
      - 真正的 untracked 框架檔（如新增的 rule.md 尚未 git add）會被舊 git diff
        靜默漏過，使 push 推出與工作區不一致的內容。

    Consequence：未做此修復時，push clean-check 會在「local-only untracked 存在」
    時誤 abort（缺陷 T），且在「真正 untracked 框架檔存在」時靜默放行不一致內容。

    Action：以 porcelain 取全狀態 + should_exclude 過濾。過濾後仍有任何條目
    （tracked 的 unstaged/staged 變更、或非 local-only 的 untracked 檔）即回 False
    要求先 commit；過濾後乾淨才回 True。

    參數:
        project_root: 專案根目錄（含 .claude/ 與 .git/）

    傳回:
        bool: True 表示無「會被推送的」未提交變更，可安全 push
    """
    result = run_git(
        ["status", "--porcelain", "--untracked=all", "--", ".claude"],
        cwd=str(project_root),
        check=False,
    )
    if result.returncode != 0:
        # git status 失敗時保守視為「不乾淨」，避免推出未知狀態
        return False
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        # porcelain 格式：XY<space>path（rename 為 "orig -> new"，取末段判定）
        path_field = line[3:] if len(line) > 3 else line
        if " -> " in path_field:
            path_field = path_field.split(" -> ", 1)[1]
        path_field = path_field.strip().strip('"')
        # path 相對 project_root（含 .claude/ 前綴）；should_exclude 契約要求相對
        # claude_dir，故 strip 前綴
        rel_str = path_field
        prefix = ".claude/"
        if rel_str.startswith(prefix):
            rel_str = rel_str[len(prefix):]
        if not rel_str:
            continue
        if should_exclude(Path(rel_str)):
            continue
        # 過濾後仍存在的變更 → 真的需要先 commit
        return False
    return True


def stage_tracked_tree(project_root: Path, staging_dir: Path) -> int:
    """以 git archive HEAD -- .claude 取本地 git tracked 樹解到 staging_dir（C1）。

    取代舊 copy_filtered 的磁碟 walk。git archive 只含 tracked 檔案，帶來兩個
    架構層保證：
      - 安全（消滅 W1-019）：untracked / gitignored 機密檔不在 tracked 樹中，
        不可能被推上公開 repo，無需 detect_secret_leak_risk interim 防護。
      - 刪除傳播（K）：git rm 的檔自然不在 archive，下游 git diff 顯示 D(elete)。

    archive 內路徑帶 `.claude/` 前綴，解壓時 strip 該層，使 staging_dir 直接對應
    .claude/ 內容（與舊 copy_filtered(claude_dir, temp_dir) 的目標結構一致）。

    注意：本函式只負責「取 tracked 樹」，should_exclude 過濾由
    copy_filtered_from_staging 在複製到遠端 temp_dir 時施加（M1：tracked 但須
    排除者如 settings.local.json / .sync-state.json / 憑證仍要擋）。

    參數:
        project_root: 專案根目錄（含 .claude/ 與 .git/）
        staging_dir: 解壓目的地（呼叫端建立的暫存目錄）

    傳回:
        int: 解出的檔案數
    """
    staging_dir.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        ["git", "archive", "--format=tar", "HEAD", "--", ".claude"],
        cwd=str(project_root),
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        print_color(
            f"git archive 失敗: {result.stderr.decode('utf-8', 'replace')}", "red"
        )
        sys.exit(1)

    count = 0
    prefix = ".claude/"
    with tarfile.open(fileobj=io.BytesIO(result.stdout), mode="r:") as tar:
        for member in tar.getmembers():
            if not member.isfile():
                continue
            name = member.name
            if not name.startswith(prefix):
                continue
            rel = name[len(prefix):]  # strip .claude/ 前綴
            if not rel:
                continue
            dest = staging_dir / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            extracted = tar.extractfile(member)
            if extracted is None:
                continue
            dest.write_bytes(extracted.read())
            count += 1
    return count


def copy_filtered_from_staging(src: Path, dst: Path) -> int:
    """從 staging（git tracked 樹）複製到遠端 temp_dir，施加 should_exclude 過濾（M1）。

    git archive 取的是 tracked 全部；tracked 但屬 local-only / 憑證者（如誤被
    commit 的 settings.local.json）仍須在此被 should_exclude 擋下，避免外洩至
    公開 repo。should_exclude 契約要求相對 claude_dir 的路徑，故傳 item 相對
    src 的路徑判定。

    參數:
        src: staging_dir（已 strip .claude/ 前綴，內容對應 .claude/）
        dst: 遠端 repo 本地暫存根目錄（temp_dir）

    傳回:
        int: 實際複製的檔案數
    """
    count = 0
    for item in sorted(src.rglob("*")):
        if not item.is_file():
            continue
        rel = item.relative_to(src)  # 相對 .claude/ 的路徑
        if should_exclude(rel):
            continue
        dest_item = dst / rel
        dest_item.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(item, dest_item)
        count += 1
    return count


def restore_executable_bits(root: Path) -> int:
    """對所有 hooks/ 目錄下的 .py 檔案強制加入 filesystem executable bit。

    呼叫時機：copy_filtered_from_staging 把 tracked 樹複製到 temp_dir 後、git add -A 前。
    在 POSIX 環境有效（macOS/Linux）；Windows NTFS 無 exec bit 概念，此操作無效果，
    但不會失敗或污染狀態。

    遞迴覆蓋頂層 hooks/ 與 W10-092 遷移後的 skills/<name>/hooks/（缺陷 G）。

    與 sync-claude-pull.py::restore_executable_bits 對稱（pull 端 safety net）。

    跨平台治本方案見 git_update_index_chmod()（在 git add 後呼叫）。

    參數:
        root: 遠端 repo 的本地暫存根目錄（temp_dir）

    傳回:
        int: 實際變更 mode 的檔案數
    """
    count = 0
    for target_dir in iter_executable_hook_dirs(root):
        for py_file in target_dir.rglob("*.py"):
            if not py_file.is_file():
                continue
            mode = py_file.stat().st_mode
            new_mode = mode | 0o111
            if new_mode != mode:
                py_file.chmod(new_mode)
                count += 1
    return count


def git_update_index_chmod(root: Path) -> int:
    """對所有 hooks/ 目錄下的 .py 檔案的 git index mode 設為 100755。

    Windows NTFS 無 executable bit 概念，filesystem chmod 對 git index 無作用；
    `git update-index --chmod=+x` 直接寫入 git index，不依賴 filesystem 語意，
    跨平台一致。這是 W16-004.3 的治本方案，覆蓋 restore_executable_bits 在
    Windows 上的盲點。

    遞迴覆蓋頂層 hooks/ 與 W10-092 遷移後的 skills/<name>/hooks/（缺陷 G）。
    與 W1-029 git-archive push 流程相容：archive 解出的 tracked 樹保留目錄結構，
    本函式仍以 git update-index --chmod=+x 顯式校正 index mode。

    呼叫時機：`git add -A` 之後（檔案已 tracked），`git commit` 之前。

    背景：IMP-067 v1.36.2 事件——Windows push 使 379 個新 .py 檔案 mode
    在 remote 記為 100644；需此函式顯式確保 index mode 正確。

    參數:
        root: 遠端 repo 的本地暫存根目錄（temp_dir）

    傳回:
        int: 成功設定 mode 的檔案數
    """
    count = 0
    for target_dir in iter_executable_hook_dirs(root):
        for py_file in target_dir.rglob("*.py"):
            if not py_file.is_file():
                continue
            rel = py_file.relative_to(root).as_posix()
            result = run_git(
                ["update-index", "--chmod=+x", rel],
                cwd=str(root),
                check=False,
            )
            if result.returncode == 0:
                count += 1
    return count


def strip_project_specific_info(text: str) -> str:
    """Remove project-specific info (Ticket IDs, version numbers, Wave refs) from text.

    The independent repo is a cross-project framework.
    Commit messages must focus on framework functionality, not project-specific progress.
    """
    result = text
    for pattern in PROJECT_SPECIFIC_PATTERNS:
        result = re.sub(pattern, "", result)
    # Clean up leftover artifacts: multiple spaces, trailing colons, empty parens
    result = re.sub(r"\(\s*\)", "", result)
    result = re.sub(r":\s*$", "", result, flags=re.MULTILINE)
    result = re.sub(r"  +", " ", result)
    return result.strip()


def parse_commit_type(subject: str) -> tuple[str, str]:
    """Parse conventional commit subject into (type, description).

    Returns (type, description) where type is feat/fix/refactor/docs/chore/etc.
    If no conventional prefix, returns ("other", full_subject).

    Special handling: git 原生 `Revert "..."` 格式（無 conventional prefix）
    一律歸類為 "revert" type，description 為被 revert 的原 subject 內容。
    """
    # git 原生 revert message: `Revert "<original subject>"`
    revert_match = re.match(r'^Revert\s+"(.+)"\s*$', subject)
    if revert_match:
        return "revert", revert_match.group(1).strip()

    match = re.match(r"^(\w+)(?:\([^)]*\))?:\s*(.+)", subject)
    if match:
        return match.group(1).lower(), match.group(2).strip()
    return "other", subject.strip()


def parse_revert_info(subject: str) -> tuple[str, str] | None:
    """Parse revert commit subject and return (original_subject, original_ref).

    支援三種 revert 格式：
      1. `revert(scope): <original subject>` — conventional revert
      2. `revert: <original subject>` — conventional revert without scope
      3. `Revert "<original subject>"` — git default revert message

    傳回 (original_subject, original_ref)：
      - original_subject: 被 revert 的原 commit subject（已 strip 引號）
      - original_ref: 從原 subject 萃取的引用（W14-xxx 或裸 hash 或 ""）

    若 subject 非 revert 格式則回傳 None。
    """
    original = None

    # 格式 3: git default `Revert "<subject>"`
    m = re.match(r'^Revert\s+"(.+)"\s*$', subject)
    if m:
        original = m.group(1).strip()
    else:
        # 格式 1/2: conventional revert
        m = re.match(r"^revert(?:\([^)]*\))?:\s*(.+)", subject)
        if m:
            original = m.group(1).strip()
            # 若內層仍包 quotes，剝一層
            inner = re.match(r'^"(.+)"\s*$', original)
            if inner:
                original = inner.group(1).strip()

    if original is None:
        return None

    # 萃取引用：優先 Ticket ID（含 Wave 編號），其次 7+ hex 短 hash
    ref = ""
    ticket_match = re.search(r"\b(\d+\.\d+\.\d+-W\d+-\d+|W\d+-\d+)\b", original)
    if ticket_match:
        ref = ticket_match.group(1)
    else:
        hash_match = re.search(r"\b([0-9a-f]{7,40})\b", original)
        if hash_match:
            ref = hash_match.group(1)

    return original, ref


def get_last_sync_timestamp(remote_repo_dir: str) -> str | None:
    """Get the timestamp of the latest commit in the remote repo.

    This represents when the last sync-push happened.
    """
    result = run_git(
        ["log", "-1", "--format=%aI"],
        cwd=remote_repo_dir,
        check=False,
    )
    if result.returncode == 0 and result.stdout.strip():
        return result.stdout.strip()
    return None


def collect_claude_commits(project_root: str, since: str | None) -> list[str]:
    """Collect commit subjects that touch .claude/ since the given timestamp.

    Returns list of commit subject lines.
    """
    args = ["log", "--format=%s", "--no-merges", "--", ".claude/"]
    if since:
        args.insert(2, f"--since={since}")
    result = run_git(args, cwd=project_root, check=False)
    if result.returncode != 0 or not result.stdout.strip():
        return []
    return [line for line in result.stdout.strip().split("\n") if line.strip()]


def _normalize_subject_for_match(subject: str) -> str:
    """正規化 commit subject 用於 revert 配對比對。

    移除 conventional prefix（type(scope):）後 strip + lower，
    讓 `chore(W14-031): migrate X` 與 `revert(W14-031): migrate X`
    的 description 可正確配對。
    """
    # 剝 conventional prefix
    m = re.match(r"^\w+(?:\([^)]*\))?:\s*(.+)", subject)
    body = m.group(1).strip() if m else subject.strip()
    # 剝外圍引號
    inner = re.match(r'^"(.+)"\s*$', body)
    if inner:
        body = inner.group(1).strip()
    return body.lower()


def categorize_commits(subjects: list[str]) -> dict[str, list[str]]:
    """Categorize commit subjects by conventional commit type.

    淨效應邏輯：若同批 commits 同時含 X 與 revert(X)（X 為任意 type），
    則 X 不列入 categories（被 revert 抵銷），僅保留 revert 行並在
    description 末尾標註被撤回的原 commit。

    Returns dict mapping type -> list of descriptions.
    """
    # Step 1: 先掃描所有 revert，建立 (normalized_original) -> revert_index map
    reverted_originals: dict[str, str] = {}  # normalized_subject -> original_ref
    revert_entries: list[tuple[str, str, str]] = []  # (original_subject, original_ref, raw_subject)
    non_revert_subjects: list[tuple[str, str]] = []  # (commit_type, description) for non-revert

    for subject in subjects:
        info = parse_revert_info(subject)
        if info is not None:
            original_subject, original_ref = info
            revert_entries.append((original_subject, original_ref, subject))
            reverted_originals[_normalize_subject_for_match(original_subject)] = original_ref
        else:
            commit_type, description = parse_commit_type(subject)
            non_revert_subjects.append((commit_type, description))

    categories: dict[str, list[str]] = defaultdict(list)

    # Step 2: 加入 non-revert，跳過被 revert 抵銷的
    for commit_type, description in non_revert_subjects:
        norm = _normalize_subject_for_match(f"{commit_type}: {description}")
        if norm in reverted_originals:
            # 被同批 revert 抵銷，跳過
            continue
        cleaned = strip_project_specific_info(description)
        if cleaned:
            categories[commit_type].append(cleaned)

    # Step 3: 加入 revert 行，附註原 commit ref
    for original_subject, original_ref, _raw in revert_entries:
        cleaned_original = strip_project_specific_info(original_subject)
        # original_ref 通常是專案特定（W14-xxx），strip 後可能為空，
        # 但 revert 摘要需保留 ref 以利追溯，故 ref 不經 strip
        if original_ref:
            desc = f"{cleaned_original} (原 commit: {original_ref})" if cleaned_original else f"revert {original_ref}"
        else:
            desc = cleaned_original if cleaned_original else "revert (原 commit 細節省略)"
        categories["revert"].append(desc)

    return dict(categories)


def suggest_version_bump(categories: dict[str, list[str]]) -> str:
    """Suggest version bump level based on commit types.

    Returns "major", "minor", or "patch".
    """
    has_minor = False
    for commit_type in categories:
        bump = VERSION_BUMP_WEIGHTS.get(commit_type, "patch")
        if bump == "major":
            return "major"
        if bump == "minor":
            has_minor = True
    return "minor" if has_minor else "patch"


def generate_commit_summary(categories: dict[str, list[str]], bump_suggestion: str) -> str:
    """Generate a structured commit message from categorized commits.

    The first line is always a descriptive summary suitable for git commit subject.
    Additional detail lines follow after a blank line.
    """
    display_order = ["revert", "feat", "refactor", "fix", "docs", "chore", "style", "test", "perf", "other"]

    # Collect all unique descriptions with their types, preserving order
    all_items: list[tuple[str, str]] = []
    for t in display_order:
        if t not in categories:
            continue
        for desc in dict.fromkeys(categories[t]):
            all_items.append((t, desc))

    total_count = len(all_items)

    # First line: descriptive summary (not just counts)
    # Few commits (1-3): list actual descriptions joined by "; "
    # Many commits (4+): highlight top items with count context
    MAX_SUBJECT_ITEMS = 3
    if total_count <= MAX_SUBJECT_ITEMS:
        subject_parts = [f"{t}: {desc}" for t, desc in all_items]
        summary_line = "; ".join(subject_parts)
    else:
        # Show first few items + count of remaining
        shown_parts = [f"{t}: {desc}" for t, desc in all_items[:MAX_SUBJECT_ITEMS]]
        remaining = total_count - MAX_SUBJECT_ITEMS
        summary_line = "; ".join(shown_parts) + f" (+{remaining} more)"

    # Build detail lines for body (all items)
    details: list[str] = []
    for t, desc in all_items:
        details.append(f"- {t}: {desc}")

    # Stats line for context
    type_counts = []
    for t in display_order:
        if t in categories:
            type_counts.append(f"{len(categories[t])} {t}")
    stats = ", ".join(type_counts)

    body_parts = [f"Changes: {stats}"]
    if details:
        body_parts.append("")
        body_parts.extend(details)

    return f"{summary_line}\n\n" + "\n".join(body_parts)


def extract_version_string(content: str) -> str:
    """從可能包含多行或註解的 VERSION 檔案內容中提取版本號。

    跳過空行和 # 開頭的註解行，取第一行有效內容並移除 v 前綴。
    移除 UTF-8 BOM（Windows 環境 VERSION 檔案可能含 BOM，
    若未 strip 會導致 bump_version 正規式 parse 失敗 fallback 至 1.0.1）。
    """
    for line in content.split("\n"):
        line = line.strip().lstrip("\ufeff")
        if line and not line.startswith("#"):
            return line.lstrip("v")
    return ""


def validate_version_bump(remote_version: str, new_version: str) -> None:
    """驗證新版號相對 remote 的跳躍幅度是否合理。

    合法 bump 型態（恰好滿足一種）：
      - major: X+1.0.0
      - minor: X.Y+1.0
      - patch: X.Y.Z+1

    任何其他跳躍（如 1.17.0 → 1.36.2 共 19 個 minor）屬異常，
    可能成因：local VERSION 污染、encoding 陷阱、bump 邏輯錯誤、
    手動編輯後未同步。此時 fail-fast 而非靜默 push 出異常版號。

    背景：W16-004.2 追蹤的 v1.17.0 → v1.36.2 事件即缺此防護所致。
    """
    r_match = re.match(r"(\d+)\.(\d+)\.(\d+)", remote_version)
    n_match = re.match(r"(\d+)\.(\d+)\.(\d+)", new_version)
    if not r_match or not n_match:
        print_color(
            f"版本格式無法解析: remote={remote_version!r}, new={new_version!r}",
            "red",
        )
        sys.exit(1)

    r_maj, r_min, r_pat = (int(x) for x in r_match.groups())
    n_maj, n_min, n_pat = (int(x) for x in n_match.groups())

    valid_major = n_maj == r_maj + 1 and n_min == 0 and n_pat == 0
    valid_minor = n_maj == r_maj and n_min == r_min + 1 and n_pat == 0
    valid_patch = n_maj == r_maj and n_min == r_min and n_pat == r_pat + 1

    if not (valid_major or valid_minor or valid_patch):
        print_color(
            f"[FAIL] 版號跳躍異常: remote=v{remote_version} -> new=v{new_version}",
            "red",
        )
        print_color(
            "預期三種合法 bump: major+1/0/0、major/minor+1/0、或 major/minor/patch+1",
            "red",
        )
        print_color(
            "可能原因: 本地 .claude/VERSION 被其他來源污染、UTF-8 BOM、"
            "bump 邏輯錯誤、或手動編輯未同步。",
            "yellow",
        )
        print_color(
            "建議操作: 檢查本地 .claude/VERSION 是否等於 remote（加 1 patch 內）；"
            "若已異常，手動設為 remote + 1 patch 再重試。",
            "yellow",
        )
        sys.exit(1)


def bump_version(version: str, bump_level: str) -> str:
    """Increment version based on bump level (major/minor/patch)."""
    match = re.match(r"(\d+)\.(\d+)\.(\d+)", version)
    if not match:
        return "1.0.1"
    major, minor, patch = int(match.group(1)), int(match.group(2)), int(match.group(3))
    if bump_level == "major":
        return f"{major + 1}.0.0"
    if bump_level == "minor":
        return f"{major}.{minor + 1}.0"
    return f"{major}.{minor}.{patch + 1}"


def bump_patch_version(version: str) -> str:
    """Increment the patch version number."""
    return bump_version(version, "patch")


def update_changelog(repo_dir: Path, new_version: str, commit_message: str, old_content: str = "") -> None:
    """Update CHANGELOG.md with a new version entry, preserving old entries."""
    changelog_path = repo_dir / "CHANGELOG.md"
    current_date = datetime.now().strftime("%Y-%m-%d")

    new_entry = f"## [{new_version}] - {current_date}\n\n### Summary\n{commit_message}\n\n---\n\n"

    if old_content:
        match = re.search(r"^## \[", old_content, re.MULTILINE)
        if match:
            updated = new_entry + old_content[match.start():]
        else:
            updated = new_entry + old_content
    else:
        updated = f"# CHANGELOG\n\n{new_entry}"

    changelog_path.write_text(updated, encoding="utf-8")


def check_no_change_early_exit(
    claude_dir: Path,
    project_root: Path,
) -> tuple[bool, str]:
    """偵測 .claude/ 自上次推送後是否無實質變更，回傳是否應 early-exit。

    雙重訊號設計：
      - hash 訊號：當前 .claude/ 內容指紋與 .sync-state.json `last_push_hash` 相符
      - commit 訊號：自 `last_push_time` 之後無新的 .claude/ commit

    兩個訊號同時為「無變更」才回傳 should_exit=True（保守設計）。

    邊界處理：
      - .sync-state.json 不存在 → 首次推送 → (False, ...)
      - JSON 解析失敗 / 欄位缺失 → 視為狀態未知，正常流程 → (False, ...)

    回傳值：(should_exit, reason)
      - should_exit=True 時 reason 為 abort 訊息
      - should_exit=False 時 reason 為「為何不 abort」說明（含診斷資訊）
    """
    state_path = claude_dir / ".sync-state.json"
    if not state_path.exists():
        return False, "首次推送（.sync-state.json 不存在）"

    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        return False, f".sync-state.json 解析失敗（{exc}），走正常流程"

    last_hash = state.get("last_push_hash")
    last_time = state.get("last_push_time")
    if not last_hash or not last_time:
        return False, ".sync-state.json 缺欄位，走正常流程"

    current_hash = _compute_content_hash(claude_dir)
    hash_unchanged = current_hash == last_hash

    new_commits = collect_claude_commits(str(project_root), last_time)
    no_new_commits = len(new_commits) == 0

    if hash_unchanged and no_new_commits:
        return True, (
            f"無實質變更可推送（hash={current_hash} 與上次推送相同，"
            f"自 {last_time} 以來無新 .claude/ commit）"
        )

    diag = (
        f"hash {'相同' if hash_unchanged else '不同'}"
        f"（current={current_hash} last={last_hash}）；"
        f"自上次推送有 {len(new_commits)} 個新 commit"
    )
    return False, diag


def clean_stale_files(temp_dir: Path, reference_dir: Path) -> int:
    """刪除 clone 目錄中存在但 reference_dir（git tracked 樹 staging）沒有的過時檔案。

    C1 後 reference_dir 改為 git archive 解出的 tracked 樹（staging），而非本地磁碟
    .claude/，使刪除傳播（K）對齊 git tracked 狀態：git rm 的檔不在 staging → 從
    遠端刪除。

    排除 .git 目錄、CHANGELOG.md、VERSION 等遠端獨有檔案；另對 should_exclude
    命中的檔（local-only / 憑證）不刪除（這類檔本就不該被本腳本管理，可能是其他
    專案推送內容）。

    回傳已刪除的檔案數量。
    """
    CLEAN_EXCLUDE = {".git", "CHANGELOG.md", "VERSION", "README.md", "LICENSE", ".gitignore"}
    deleted_count = 0

    for file_path in sorted(temp_dir.rglob("*")):
        if not file_path.is_file():
            continue
        rel = file_path.relative_to(temp_dir)
        # 排除 .git 目錄下的檔案和遠端獨有檔案
        if any(part in CLEAN_EXCLUDE for part in rel.parts):
            continue
        if rel.name in CLEAN_EXCLUDE:
            continue
        # should_exclude 命中者不刪除（local-only / 憑證，可能屬其他專案）
        if should_exclude(rel):
            continue
        # 檢查 tracked 樹 staging 是否有對應檔案
        if not (reference_dir / rel).exists():
            print(f"   刪除過時檔案: {rel}")
            file_path.unlink()
            deleted_count += 1

    # 清理空目錄（反向排序以支援巢狀目錄）
    for dir_path in sorted(
        temp_dir.rglob("*"),
        key=lambda p: len(p.parts),
        reverse=True,
    ):
        if not dir_path.is_dir():
            continue
        if any(part in CLEAN_EXCLUDE for part in dir_path.relative_to(temp_dir).parts):
            continue
        try:
            if not any(dir_path.iterdir()):
                dir_path.rmdir()
                deleted_count += 1
        except OSError:
            pass

    return deleted_count


def run_dry_run() -> None:
    """Dry-run 模式：只分析自上次推送以來的 commits 並輸出 auto-generated commit
    message，不 clone、不 push、不修改 VERSION/CHANGELOG。

    用於本地驗證分類邏輯（特別是 revert 處理）。
    依然需要 clone 遠端以取得 last-sync timestamp，但失敗時 fallback 至全歷史。
    """
    print_color("[DRY-RUN] 僅生成 commit message，不執行 push", "yellow")
    project_root = find_project_root()
    last_sync: str | None = None
    temp_dir = Path(tempfile.mkdtemp())
    try:
        clone_result = run_git(["clone", "--depth=1", REPO_URL, str(temp_dir)], check=False)
        if clone_result.returncode == 0:
            last_sync = get_last_sync_timestamp(str(temp_dir))
            print_color(f"   上次推送時間: {last_sync}", "green")
        else:
            print_color("   clone 失敗，使用全歷史", "yellow")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

    subjects = collect_claude_commits(str(project_root), last_sync)
    print_color(f"   找到 {len(subjects)} 個相關 commit", "green")
    if not subjects:
        print_color("   無 commit 可分析", "yellow")
        return
    categories = categorize_commits(subjects)
    bump_suggestion = suggest_version_bump(categories)
    commit_message = generate_commit_summary(categories, bump_suggestion)
    print_color("--- 自動生成的 commit 摘要 ---")
    print(commit_message)
    print_color("--- 摘要結束 ---")
    print_color(f"建議版本 bump: {bump_suggestion}", "green")


def main() -> None:
    # 解析 --dry-run：只生成 commit message 不 push
    if "--dry-run" in sys.argv:
        sys.argv.remove("--dry-run")
        run_dry_run()
        return

    # 解析 --clean 參數：啟用時清理遠端過時檔案
    clean_mode = "--clean" in sys.argv
    if clean_mode:
        sys.argv.remove("--clean")
    # 解析 --force 參數：跳過 no-change early-exit 檢查
    force_mode = "--force" in sys.argv
    if force_mode:
        sys.argv.remove("--force")
    # commit message is now optional - auto-generated when not provided
    user_message = sys.argv[1] if len(sys.argv) >= 2 else None

    print_color("開始推送 .claude 資料夾到獨立 repo...")

    # 1. Find project root
    project_root = find_project_root()
    claude_dir = project_root / ".claude"

    # 2. commit-first 檢查（M1 根因解，0.19.1-W1-030）：push 取 git tracked 樹（HEAD），
    # 未 commit 的「會被推送的」變更不會反映到遠端。clean-check 改用 git status
    # --porcelain 全狀態 + should_exclude 過濾：local-only / 憑證 untracked 檔
    # （如 .zhtw-mcp-skip）不再誤判為未提交變更而 abort（缺陷 T），但真正未 commit
    # 的 tracked 變更與非 local-only untracked 框架檔仍被攔截。
    print_color("檢查 .claude 資料夾狀態（commit-first）...")
    if not ensure_committed(project_root):
        print_color("警告: .claude 有未提交的變更（會被推送但未 commit）", "red")
        print("push 取的是 git tracked 樹（HEAD）；請先 git add .claude && git commit")
        sys.exit(1)
    # 安全說明（C1）：push 改以 git archive HEAD 取 tracked 樹，untracked / gitignored
    # 機密檔不在 tracked 樹中，從架構層消滅 W1-019 secret-leak 風險，故無需 interim
    # detect_secret_leak_risk 防護（已隨 C1 移除）。

    # 2.5. No-change early-exit（W3-075）：避免空 commit 污染歷史
    # 跳過條件：user 提供 commit message（明確意圖）或 --force 旗標
    if not user_message and not force_mode:
        should_exit, reason = check_no_change_early_exit(claude_dir, project_root)
        if should_exit:
            print_color(f"Early-exit: {reason}", "yellow")
            print_color("如需強制推送，請使用 --force 旗標或提供 commit message")
            return
        else:
            print_color(f"   no-change 檢查通過：{reason}", "green")

    # 3. Clone remote repo (preserve history)
    print_color("Clone 遠端 repo（保留歷史）...")
    temp_dir = Path(tempfile.mkdtemp())
    try:
        run_git(["clone", REPO_URL, str(temp_dir)])

        # 4. Read remote version
        print_color("讀取遠端版本號...")
        version_file = temp_dir / "VERSION"
        if version_file.exists():
            remote_version = extract_version_string(version_file.read_text(encoding="utf-8"))
            print_color(f"   遠端版本: v{remote_version}", "green")
        else:
            remote_version = "1.0.0"
            print_color("   遠端無版本檔案，使用預設 v1.0.0")

        # 5. Auto-analyze commits since last sync
        bump_suggestion = "patch"
        if user_message:
            commit_message = user_message
            print_color(f"使用用戶指定的 commit 訊息: {commit_message}")
        else:
            print_color("分析自上次推送以來的 .claude/ 變更...")
            last_sync = get_last_sync_timestamp(str(temp_dir))
            if last_sync:
                print_color(f"   上次推送時間: {last_sync}", "green")

            subjects = collect_claude_commits(str(project_root), last_sync)
            if subjects:
                print_color(f"   找到 {len(subjects)} 個相關 commit", "green")
                categories = categorize_commits(subjects)
                bump_suggestion = suggest_version_bump(categories)
                commit_message = generate_commit_summary(categories, bump_suggestion)
                print_color("--- 自動生成的 commit 摘要 ---")
                print(commit_message)
                print_color("--- 摘要結束 ---")
            else:
                print_color("   未找到新的 .claude/ commit，使用預設訊息")
                commit_message = "sync .claude configuration"

        # Save CHANGELOG content before cleaning
        changelog_path = temp_dir / "CHANGELOG.md"
        saved_changelog = changelog_path.read_text(encoding="utf-8") if changelog_path.exists() else ""

        # 6. Merge 模式：不清空遠端內容，直接增量覆蓋
        # 保留遠端獨有的檔案（其他專案推送的內容）

        # 7. 取 git tracked 樹（C1）→ staging → should_exclude 過濾後複製到遠端 temp_dir
        # git archive HEAD 只含 tracked 檔案：untracked / gitignored 機密檔不可能外洩，
        # git rm 的檔自然不在 archive（K：刪除傳播）。
        print_color("取 .claude git tracked 樹（git archive HEAD）...")
        staging_dir = Path(tempfile.mkdtemp(prefix="claude-push-staging-"))
        try:
            staged_count = stage_tracked_tree(project_root, staging_dir)
            print_color(f"   git archive 取得 {staged_count} 個 tracked 檔案", "green")
            file_count = copy_filtered_from_staging(staging_dir, temp_dir)
            print_color(f"   過濾後複製 {file_count} 個檔案（should_exclude 已套用）", "green")
            print_color("   注意: CLAUDE.md 不再同步（專案特定配置）")

            # 7.5. 清理遠端過時檔案（僅 --clean 模式）。
            # 以 staging（tracked 樹）為基準：git rm 的檔不在 staging → 從遠端刪除（K）。
            if clean_mode:
                print_color("清理遠端過時檔案（對齊 git tracked 樹）...")
                deleted = clean_stale_files(temp_dir, staging_dir)
                print_color(f"   已清理 {deleted} 個遠端過時檔案", "green")
        finally:
            shutil.rmtree(staging_dir, ignore_errors=True)

        # 7.6. 還原 hook 檔案 executable bit（防止 push 出損壞 mode 到遠端）
        restored = restore_executable_bits(temp_dir)
        if restored:
            print_color(f"   已還原 {restored} 個 hook 檔案的執行權限（push 前 safety net）", "green")

        # 8. Calculate new version (use bump suggestion for auto-generated messages)
        new_version = bump_version(remote_version, bump_suggestion)

        # 8.5. Sanity check: 版號跳躍幅度防護（W16-004.2）
        # v1.17.0 -> v1.36.2 事件即缺此防護，Windows 環境下意外推出跳躍 19 minor 的版號
        validate_version_bump(remote_version, new_version)

        (temp_dir / "VERSION").write_text(new_version + "\n", encoding="utf-8")

        # 9. Update CHANGELOG (use full commit message for detailed history)
        update_changelog(temp_dir, new_version, commit_message, saved_changelog)
        print_color(f"版本: v{new_version} ({bump_suggestion} bump)", "green")

        # 10. Commit and push
        # For git commit, use only the summary line to keep it clean
        commit_summary = commit_message.split("\n")[0] if "\n" in commit_message else commit_message
        commit_msg = f"v{new_version}: {commit_summary}"
        print_color("提交變更...")
        run_git(["add", "-A"], cwd=str(temp_dir))

        # 10.5. 跨平台 hook mode 治本（W16-004.3）：直接寫 git index mode 為 100755
        # Windows NTFS 無 exec bit，filesystem chmod 對 git index 無效；
        # 此處 git update-index --chmod=+x 不依賴 filesystem，跨平台一致
        index_fixed = git_update_index_chmod(temp_dir)
        if index_fixed:
            print_color(f"   git index mode 設定 {index_fixed} 個 hook 檔案為 100755", "green")

        # Check if there are actual changes
        diff_result = run_git(["diff", "--cached", "--quiet"], cwd=str(temp_dir), check=False)
        if diff_result.returncode == 0:
            print_color("沒有變更需要推送")
            return

        run_git(["commit", "-m", commit_msg], cwd=str(temp_dir))

        # 推送前版本衝突檢測：確認遠端版本未被其他人變更
        print_color("檢查遠端版本是否變更...")
        fetch_result = run_git(["fetch", "origin"], cwd=str(temp_dir), check=False)
        if fetch_result.returncode != 0:
            print_color("警告: fetch 失敗，跳過版本衝突檢測（網路問題？）", "yellow")
        else:
            current_remote_result = run_git(
                ["show", "origin/main:VERSION"], cwd=str(temp_dir), check=False
            )
            if current_remote_result.returncode == 0:
                current_remote = extract_version_string(current_remote_result.stdout)
                if current_remote != remote_version:
                    print_color(
                        f"遠端版本已變更（{remote_version} → {current_remote}），請先 pull 再 push",
                        "red",
                    )
                    sys.exit(1)
            else:
                print_color(
                    f"   警告: 無法讀取遠端 VERSION（{current_remote_result.stderr.strip()}），跳過版本衝突檢測",
                    "yellow",
                )

        print_color("推送到獨立 repo...")
        push_result = run_git(
            ["push", "--force-with-lease", "origin", "main"],
            cwd=str(temp_dir),
            check=False,
        )
        if push_result.returncode != 0:
            if "stale info" in push_result.stderr or "rejected" in push_result.stderr:
                print_color(
                    "推送被拒絕：遠端已有更新的變更。請先執行 sync-pull 再重試。",
                    "red",
                )
            else:
                print_color(f"推送失敗: {push_result.stderr}", "red")
            sys.exit(1)

        # 計算內容指紋並寫入 .sync-state.json（保留 last_synced_base_sha，禁覆蓋遺失）
        content_hash = _compute_content_hash(claude_dir)
        sync_state_path = claude_dir / ".sync-state.json"
        existing_state: dict = {}
        if sync_state_path.exists():
            try:
                existing_state = json.loads(sync_state_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                existing_state = {}
        existing_state.update({
            "last_push_hash": content_hash,
            "last_push_version": new_version,
            "last_push_time": datetime.now().isoformat(timespec="seconds"),
        })
        sync_state_path.write_text(
            json.dumps(existing_state, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        # 寫入單一 last_synced_base_sha（W1-025 schema）：push 成功後遠端 HEAD 即
        # 新 base 錨點，供下次 pull/push 三方合併使用（H1：禁雙欄位）。
        head_result = run_git(
            ["rev-parse", "HEAD"], cwd=str(temp_dir), check=False
        )
        if head_result.returncode == 0 and head_result.stdout.strip():
            base_sha = head_result.stdout.strip()
            write_base_sha(claude_dir, base_sha)
            print_color(f"已更新同步狀態 (hash: {content_hash}, base: {base_sha[:12]})", "green")
        else:
            print_color(
                f"已更新同步狀態 (hash: {content_hash})；警告：無法取得遠端 HEAD SHA，"
                "未寫入 last_synced_base_sha",
                "yellow",
            )

        print_color("成功推送 .claude 到獨立 repo！", "green")
        print_color(f"Remote: {REPO_URL}", "green")
        print_color("遠端 commit 歷史已保留", "green")
        print_color("注意: 根目錄 CLAUDE.md 未被推送（專案特定配置）")

    except subprocess.TimeoutExpired:
        print_color("git 操作超時，請檢查網路連線", "red")
        sys.exit(1)
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
