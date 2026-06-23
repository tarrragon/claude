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

import argparse
import importlib
import importlib.util
import io
import json
import os
import pkgutil
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
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from lib.sync_exclude_manifest import (  # noqa: E402
    should_exclude,
    should_exclude_skill,
    _is_skill_path,
    load_sync_skills_config,
    compute_content_hash as _compute_content_hash,
)

REPO_URL = "https://github.com/tarrragon/claude.git"

# .sync-state.json schema（W1-025）：單一 base 欄位，pull/push 共用。
# 禁雙欄位（H1：對 commit SHA 用 max 會選錯共同祖先）。與 sync-claude-pull.py 對稱。
SYNC_STATE_FILENAME = ".sync-state.json"
BASE_SHA_FIELD = "last_synced_base_sha"

# 專案特化檔清單檔名（與 sync-claude-pull.py 對稱）。push 端讀此清單，使
# preserve-listed 的 APP 特化檔不被推上共享框架 repo（v1.48.6 誤推根因）。
PRESERVE_FILENAME = "sync-preserve.yaml"

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


def extract_skill_versions(skills_dir: Path) -> dict[str, str]:
    """掃描 skills/*/SKILL.md 提取各 skill 的版本號。

    參數:
        skills_dir: skills 目錄路徑（如 temp_dir/skills/）

    傳回:
        dict[str, str]: {skill 名稱: 版本號}，無版本號者不列入
    """
    versions: dict[str, str] = {}
    if not skills_dir.is_dir():
        return versions
    for skill_md in sorted(skills_dir.glob("*/SKILL.md")):
        skill_name = skill_md.parent.name
        try:
            text = skill_md.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        m = re.search(r"\*\*Version\*\*:\s*(\S+)", text)
        if not m:
            m = re.search(r"^version:\s*(\S+)", text, re.MULTILINE)
        if m:
            versions[skill_name] = m.group(1)
    return versions


def format_skill_version_diff(
    before: dict[str, str], after: dict[str, str]
) -> str | None:
    """比對前後 skill 版本，產生摘要文字。無變更時回傳 None。

    參數:
        before: 同步前的 {skill: version}
        after: 同步後的 {skill: version}

    傳回:
        str | None: 摘要文字（含換行），無變更時 None
    """
    all_names = sorted(set(before) | set(after))
    new_skills: list[str] = []
    updated_skills: list[str] = []
    removed_skills: list[str] = []
    for name in all_names:
        old_ver = before.get(name)
        new_ver = after.get(name)
        if old_ver is None and new_ver is not None:
            new_skills.append(f"{name} ({new_ver})")
        elif old_ver is not None and new_ver is None:
            removed_skills.append(f"{name} (was {old_ver})")
        elif old_ver != new_ver:
            updated_skills.append(f"{name} {old_ver} -> {new_ver}")
    if not new_skills and not updated_skills and not removed_skills:
        return None
    lines = ["[Skill 變更摘要]"]  # i18n-exempt
    if new_skills:
        lines.append(f"  新增: {', '.join(new_skills)}")  # i18n-exempt
    if updated_skills:
        lines.append(f"  更新: {', '.join(updated_skills)}")  # i18n-exempt
    if removed_skills:
        lines.append(f"  移除: {', '.join(removed_skills)}")  # i18n-exempt
    return "\n".join(lines)


def load_preserve_list(claude_dir: Path) -> set[str]:
    """讀取 sync-preserve.yaml 中的本地特化檔案清單（與 sync-claude-pull.py 對稱）。

    Why：push 用 git archive HEAD 全樹 overlay，僅靠 should_exclude（manifest）
    過濾。但 APP 專案特化檔（skills/wrap-decision/references/project-integration/*
    等）不在 manifest 排除清單，會被推上共享框架 repo（v1.48.6 誤推實證）。
    pull 端已以 sync-preserve.yaml 原地保留這些檔，push 端須對稱地排除，否則
    「保留」與「推送」兩端不一致，本地特化內容反向污染框架。

    Consequence：若不讀 preserve，push 把專案特化檔推上框架，其他專案 pull 後
    收到不屬於自己的特化內容。

    Action：本函式讀清單，由 copy_filtered_from_staging / clean_stale_files /
    detect_uncleaned_deletions 在過濾階段排除。

    無 sync-preserve.yaml 時回傳空集合（合法：專案未定義 preserve）。本環境無
    PyYAML（與 pull 端 fallback 一致），採行掃描解析 "- path" 格式。

    參數:
        claude_dir: .claude 目錄路徑

    傳回:
        set[str]: 需保留（不推送）的相對路徑集合（相對於 .claude/）
    """
    preserve_file = claude_dir / PRESERVE_FILENAME
    if not preserve_file.exists():
        return set()
    content = preserve_file.read_text(encoding="utf-8")
    paths: set[str] = set()
    in_preserve = False
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("#") or not stripped:
            continue
        if stripped == "preserve:":
            in_preserve = True
            continue
        if in_preserve and stripped.startswith("- "):
            paths.add(stripped[2:].strip())
        elif stripped and not stripped.startswith("#"):
            # 非空、非註解行關閉 preserve 區塊
            in_preserve = False
    return paths


def copy_filtered_from_staging(
    src: Path, dst: Path, preserve: set[str] | None = None,
    skills_config: dict | None = None,
) -> int:
    """從 staging（git tracked 樹）複製到遠端 temp_dir，施加 should_exclude + preserve + skills 過濾（M1）。

    git archive 取的是 tracked 全部；tracked 但屬 local-only / 憑證者（如誤被
    commit 的 settings.local.json）仍須在此被 should_exclude 擋下，避免外洩至
    公開 repo。should_exclude 契約要求相對 claude_dir 的路徑，故傳 item 相對
    src 的路徑判定。

    preserve（0.32.0-W1-008）：sync-preserve.yaml 列出的 APP 專案特化檔不推上
    共享框架，與 pull 端原地保留對稱。

    skills_config（1.3.0-W1-054）：sync-skills.yaml 設定，過濾 skills/ 目錄。
    None 時不過濾（向後相容）。

    參數:
        src: staging_dir（已 strip .claude/ 前綴，內容對應 .claude/）
        dst: 遠端 repo 本地暫存根目錄（temp_dir）
        preserve: 不推送的相對路徑集合（None 視為空集合，向後相容）
        skills_config: load_sync_skills_config 回傳值（None 不過濾）

    傳回:
        int: 實際複製的檔案數
    """
    preserve = preserve or set()
    count = 0
    for item in sorted(src.rglob("*")):
        if not item.is_file():
            continue
        rel = item.relative_to(src)  # 相對 .claude/ 的路徑
        if should_exclude(rel):
            continue
        if rel.as_posix() in preserve:
            continue
        if skills_config is not None:
            skill_name = _is_skill_path(rel)
            if skill_name is not None and should_exclude_skill(skill_name, skills_config, "push"):
                continue
        dest_item = dst / rel
        dest_item.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(item, dest_item)
        count += 1
    return count


# settings.json 中提取 hook command 內 .py 路徑的正則（容錯 shell 包裝）
_SKILL_SCRIPT_RE = re.compile(r"\.claude/(skills/[^\s'\"]+?\.py)")


def collect_registered_skill_scripts(root: Path) -> set[Path]:
    """從 settings.json 反查被註冊為 hook command 直接執行的 skill 根目錄 .py。

    與 sync-claude-pull.py::collect_registered_skill_scripts 對稱（W9-007）。

    背景：exec-bit 還原以「目錄名 hooks」為邊界，未涵蓋位於 skill 根目錄（非
    hooks/ 子目錄）但被 settings.json 註冊為執行的腳本，如
    skills/continuous-learning/evaluate-session.py。push 端若不還原，推上去的
    git index mode 會是 100644，下游 pull 拿到 644 → Permission denied。

    採策略 C（settings.json 反查）：command 是「被註冊為執行」的權威來源，可精準
    命中且不誤判未註冊的 shebang 腳本（如 skills/ticket/test_migration_dryrun.py）。

    只解析 settings.json（settings.local.json 不 sync）。command 可能含 shell 包裝，
    以正則容錯提取 .py 路徑。hooks/ 路徑由 iter_executable_hook_dirs 涵蓋，此處排除避重複。

    參數:
        root: 遠端 repo 的本地暫存根目錄（temp_dir），須含 settings.json

    傳回:
        set[Path]: 存在、被註冊執行且非 hooks/ 路徑的 .py 絕對路徑
    """
    settings_path = root / "settings.json"
    if not settings_path.is_file():
        return set()
    try:
        text = settings_path.read_text(encoding="utf-8")
    except OSError as exc:
        print_color(f"   警告: 無法讀取 settings.json: {exc}", "yellow")
        return set()

    scripts: set[Path] = set()
    for match in _SKILL_SCRIPT_RE.finditer(text):
        rel = match.group(1)
        if "/hooks/" in rel:
            continue
        candidate = root / rel
        if candidate.is_file():
            scripts.add(candidate)
    return scripts


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
    targets: set[Path] = set()
    for target_dir in iter_executable_hook_dirs(root):
        for py_file in target_dir.rglob("*.py"):
            if py_file.is_file():
                targets.add(py_file)
    # W9-007：settings.json 註冊的 skill 根目錄執行檔（非 hooks/ 路徑）
    targets |= collect_registered_skill_scripts(root)
    for py_file in targets:
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
    targets: set[Path] = set()
    for target_dir in iter_executable_hook_dirs(root):
        for py_file in target_dir.rglob("*.py"):
            if py_file.is_file():
                targets.add(py_file)
    # W9-007：settings.json 註冊的 skill 根目錄執行檔（非 hooks/ 路徑）
    targets |= collect_registered_skill_scripts(root)
    for py_file in targets:
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


def create_and_push_version_tag(repo_dir: Path, version: str) -> None:
    """對 repo_dir 當前 HEAD 打 annotated tag v<version> 並 push 到 origin。

    tagged-release 機制：每次成功 push 框架更新後，對該版本 commit 打 git tag，
    使下游 consumer 可 pin 至特定版本（tag commit），收斂壞變更的爆炸半徑——壞版
    不再瞬時傳染全部 consumer，consumer 可選擇停留在已知良好的 tag。

    冪等性：tag v<version> 已存在時不重複建立（避免同版重 push 失敗）。本地已有
    tag 但 remote 無時，仍嘗試 push 該 tag。tag push 失敗僅警告不中止整個 push
    流程（main 分支已成功推送，tag 為附加機制）。

    參數:
        repo_dir: 已 push 成功的本地 clone 路徑（含 origin remote）
        version: 純版本號（不含 v 前綴，如 "1.0.1"）
    """
    tag_name = f"v{version}"
    existing = run_git(["tag", "--list", tag_name], cwd=str(repo_dir), check=False)
    if existing.returncode == 0 and tag_name in existing.stdout.split():
        # 本地已有此 tag：確保 remote 也有（容錯前次 tag push 失敗），不重建
        push_existing = run_git(
            ["push", "origin", tag_name], cwd=str(repo_dir), check=False
        )
        if push_existing.returncode != 0:
            print_color(
                f"   警告: 推送既有 tag {tag_name} 失敗: {push_existing.stderr.strip()}",
                "yellow",
            )
        return

    create_result = run_git(
        ["tag", "-a", tag_name, "-m", f"Release {tag_name}"],
        cwd=str(repo_dir),
        check=False,
    )
    if create_result.returncode != 0:
        print_color(
            f"   警告: 建立 tag {tag_name} 失敗: {create_result.stderr.strip()}",
            "yellow",
        )
        return

    push_result = run_git(
        ["push", "origin", tag_name], cwd=str(repo_dir), check=False
    )
    if push_result.returncode != 0:
        print_color(
            f"   警告: 推送 tag {tag_name} 失敗（main 已推送成功）: "
            f"{push_result.stderr.strip()}",
            "yellow",
        )
        return
    print_color(f"   已打並推送版本 tag {tag_name}", "green")


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


def clean_stale_files(
    temp_dir: Path,
    reference_dir: Path,
    preserve: set[str] | None = None,
    lineage_claimed: set[str] | None = None,
    skills_config: dict | None = None,
) -> int:
    """刪除 clone 目錄中存在但 reference_dir（git tracked 樹 staging）沒有的過時檔案。

    C1 後 reference_dir 改為 git archive 解出的 tracked 樹（staging），而非本地磁碟
    .claude/，使刪除傳播（K）對齊 git tracked 狀態：git rm 的檔不在 staging → 從
    遠端刪除。

    排除 .git 目錄、CHANGELOG.md、VERSION 等遠端獨有檔案；另對 should_exclude
    命中的檔（local-only / 憑證）不刪除（這類檔本就不該被本腳本管理，可能是其他
    專案推送內容）。

    preserve（0.32.0-W1-008）：sync-preserve.yaml 列出的專案特化檔不刪除。push
    端不推這些檔（copy_filtered_from_staging 已排除），故它們不在 staging；若不
    在此一併排除，--clean 會把遠端既有的 preserve 副本（可能屬其他專案）誤刪。

    skills_config（1.3.0-W1-054）：被 skills_config 排除的 skill 不視為 stale
    （它們不在 staging 但屬其他專案推送的內容，不應刪除）。

    回傳已刪除的檔案數量。
    """
    preserve = preserve or set()
    lineage_claimed = lineage_claimed or set()
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
        # preserve-listed 檔不刪除（專案特化，push 端刻意不推也不刪）
        if rel.as_posix() in preserve:
            continue
        # 被本地 lineage 重編號檔認領的上游 canonical 不刪除（PC-APP-002 / W1-039）：
        # 本地把上游 PC-<N> 重編為 PC-<M> 後，上游 PC-<N>-<slug> 在本地無同名檔會被
        # 誤列孤兒；其溯源註解明說上游應保留原號供下次 pull 去重，故排除於 --clean。
        if rel.as_posix() in lineage_claimed:
            continue
        # skills_config 排除的 skill 不視為 stale（可能屬其他專案推送）
        if skills_config is not None:
            skill_name = _is_skill_path(rel)
            if skill_name is not None and should_exclude_skill(skill_name, skills_config, "push"):
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


def detect_uncleaned_deletions(
    temp_dir: Path,
    reference_dir: Path,
    preserve: set[str] | None = None,
    lineage_claimed: set[str] | None = None,
    skills_config: dict | None = None,
) -> list[str]:
    """偵測遠端 clone（temp_dir）存在但本地 git tracked 樹（reference_dir）已無的檔案。

    這些檔在本地已 git rm（不在 staging tracked 樹），但因本次 push 未帶 --clean，
    clean_stale_files 不會執行，遠端會殘留為孤兒。回傳這些孤兒的相對路徑清單，供
    main 在結尾輸出 soft 警告（不阻擋、不改 --clean 預設，R2）。

    判定邏輯與 clean_stale_files 對齊（同一組 CLEAN_EXCLUDE + should_exclude 過濾），
    確保「警告的檔」恰為「--clean 會刪的檔」，不多報遠端獨有檔（CHANGELOG/VERSION）
    或他專案推送的 local-only 檔。

    Why：刪除跨專案傳播仰賴 --clean opt-in（預設關，刻意安全設計避免誤刪）。本地
    git rm tracked .claude/ 檔後若 push 未帶 --clean，遠端殘留孤兒，full overlay
    sync 會把孤兒複製回下游（W10-049 / W1-003 根因）。
    Consequence：孤兒長期累積（W1-009 實測遠端殘留 755 孤兒），下游反覆收到應已
    刪除的檔。
    Action：本函式偵測此情境，main 結尾以 stdout soft 警告提示可考慮帶 --clean
    重推以傳播刪除；不阻擋本次 push（避免誤刪風險）。

    參數:
        temp_dir: 遠端 repo 的本地 clone 暫存根目錄
        reference_dir: git archive 解出的本地 tracked 樹（staging）

    傳回:
        list[str]: 遠端存在但本地 tracked 樹已無的檔案相對路徑（已排序），無則空 list
    """
    preserve = preserve or set()
    lineage_claimed = lineage_claimed or set()
    CLEAN_EXCLUDE = {".git", "CHANGELOG.md", "VERSION", "README.md", "LICENSE", ".gitignore"}
    orphans: list[str] = []
    for file_path in sorted(temp_dir.rglob("*")):
        if not file_path.is_file():
            continue
        rel = file_path.relative_to(temp_dir)
        if any(part in CLEAN_EXCLUDE for part in rel.parts):
            continue
        if rel.name in CLEAN_EXCLUDE:
            continue
        # should_exclude 命中者（local-only / 憑證，可能屬其他專案）不算孤兒
        if should_exclude(rel):
            continue
        # preserve-listed 檔（push 端刻意不推）不算孤兒，與 clean_stale_files 對齊
        if rel.as_posix() in preserve:
            continue
        # 被本地 lineage 重編號檔認領的上游 canonical 不算孤兒（PC-APP-002 / W1-039）：
        # 與 clean_stale_files 對齊，確保「警告/可刪的檔」恰為「真孤兒」（含讓位後的
        # native intruder），不誤報受 lineage 保護的上游 canonical。
        if rel.as_posix() in lineage_claimed:
            continue
        if skills_config is not None:
            skill_name = _is_skill_path(rel)
            if skill_name is not None and should_exclude_skill(skill_name, skills_config, "push"):
                continue
        if not (reference_dir / rel).exists():
            orphans.append(str(rel))
    return orphans


def _dry_run_report_pc_collision(claude_dir: Path, upstream_clone: Path) -> None:
    """dry-run 階段列印 PC 撞號對帳計畫，不寫任何檔（規則 3 驗證入口）。

    流程：
      1. snapshot 上游 PC 純態 → plan_upstream_mess_reconciliation 列既存 mess。
      2. 掃本地 error-patterns，對每個 bare PC 檔跑 plan_push_pc_action，分類列出
         排除（artifact）/ 賦 canonical / 原樣推送，模擬實際 push 處置。

    純讀取：只讀檔不寫檔，可安全反覆執行驗證辨識正確性。
    """
    upstream_index = build_upstream_pc_index(upstream_clone)
    reconciliation = plan_upstream_mess_reconciliation(upstream_index)
    print_color("--- PC 撞號對帳預覽（規則 3，dry-run）---", "yellow")
    if reconciliation:
        print_color(f"   上游既存 mess（同 slug 重複號）：{len(reconciliation)} 項")
        for item in reconciliation:
            print_color(
                f"     [重複] slug={item['slug']}"
                f" canonical=PC-{item['canonical_num']}"
                f" / 誤推鏡像=PC-{item['duplicate_num']}（高號該移除）"
            )
    else:
        print_color("   上游無既存 PC mess", "green")

    ep_root = claude_dir / "error-patterns"
    excluded = renumbered = untouched = 0
    reserved: set[int] = set()
    if ep_root.is_dir():
        for path in sorted(ep_root.rglob("PC-*.md")):
            repo_rel = path.relative_to(claude_dir).as_posix()
            if parse_pc_filename(repo_rel) is None:
                continue
            try:
                content = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            plan = plan_push_pc_action(repo_rel, content, upstream_index, reserved)
            if plan["action"] == "exclude_lineage_artifact":
                excluded += 1
                print_color(
                    f"     [排除] {repo_rel}"
                    f"（lineage 上游 PC-{plan['upstream_num']}"
                    f" / 本地 PC-{plan['local_num']}，不外推）"
                )
            elif plan["action"] == "assign_canonical":
                renumbered += 1
                print_color(
                    f"     [賦號] PC-{plan['old_num']} -> PC-{plan['new_num']}"
                    f"（slug={plan['slug']}）"
                )
            else:
                untouched += 1
    print_color(
        f"   本地 PC 處置模擬：排除 {excluded} / 賦 canonical {renumbered}"
        f" / 原樣推送 {untouched}",
        "green",
    )

    # 孤兒辨識預覽（PC-APP-002 / W1-039）：列出「上游有、本地 PC 重編後已無同名檔」
    # 的上游 PC 檔，並標明哪些受 lineage 認領保護（不清）、哪些為真孤兒（讓位後的
    # native intruder，可清）。純讀取，供 step-4 驗證辨識正確性。
    lineage_claimed = compute_lineage_claimed_upstream_files(claude_dir)
    local_pc_rel: set[str] = set()
    if ep_root.is_dir():
        for path in ep_root.rglob("PC-*.md"):
            rel = path.relative_to(claude_dir).as_posix()
            if parse_pc_filename(rel) is not None:
                local_pc_rel.add(rel)
    up_ep = upstream_clone / "error-patterns"
    protected = true_orphans = 0
    if up_ep.is_dir():
        print_color("   上游 PC 孤兒辨識（本地重編後上游殘留）：")
        for path in sorted(up_ep.rglob("PC-*.md")):
            rel = path.relative_to(upstream_clone).as_posix()
            if parse_pc_filename(rel) is None or rel in local_pc_rel:
                continue
            if rel in lineage_claimed:
                protected += 1
                print_color(f"     [保留] {rel}（lineage 認領的框架 canonical）", "green")
            else:
                true_orphans += 1
                print_color(f"     [真孤兒] {rel}（無人認領，--clean 可清）", "yellow")
        print_color(
            f"   孤兒辨識：受 lineage 保護 {protected} / 真孤兒可清 {true_orphans}",
            "green",
        )
    print_color("--- PC 撞號對帳預覽結束 ---", "yellow")


def run_dry_run() -> None:
    """Dry-run 模式：只分析自上次推送以來的 commits 並輸出 auto-generated commit
    message，不 clone、不 push、不修改 VERSION/CHANGELOG。

    用於本地驗證分類邏輯（特別是 revert 處理）。
    依然需要 clone 遠端以取得 last-sync timestamp，但失敗時 fallback 至全歷史。
    """
    print_color("[DRY-RUN] 僅生成 commit message，不執行 push", "yellow")
    project_root = find_project_root()
    claude_dir = project_root / ".claude"
    last_sync: str | None = None
    temp_dir = Path(tempfile.mkdtemp())
    try:
        clone_result = run_git(["clone", "--depth=1", REPO_URL, str(temp_dir)], check=False)
        if clone_result.returncode == 0:
            last_sync = get_last_sync_timestamp(str(temp_dir))
            print_color(f"   上次推送時間: {last_sync}", "green")
            # PC 撞號對帳預覽（規則 3，1.2.0-W1-038）：snapshot 上游 PC 純態 →
            # 列既存 mess 修正計畫；再對本地 PC 檔模擬 push 處置（不寫任何檔）。
            _dry_run_report_pc_collision(claude_dir, temp_dir)
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


# staging 樹（已 strip .claude/ 前綴）內框架核心套件的相對路徑。
# 此套件被全 consumer 直接 import 執行，是「機械缺陷（import 殘留）零審查直推致
# 下游崩潰」最高風險的單點，故作為 push 前 smoke test 的目標。
FRAMEWORK_CORE_PACKAGE_DIR = Path("skills") / "ticket" / "ticket_system"
FRAMEWORK_CORE_PACKAGE_NAME = "ticket_system"

# push 執行環境（uv run --script，零宣告依賴）必然缺席的第三方庫。
# 這些模組缺失屬環境限制，非框架碼缺陷，smoke test 不得據此誤報 abort
# （acceptance：正常 push 零誤報）。框架內部模組（FRAMEWORK_CORE_PACKAGE_NAME.*）
# 的缺失則屬真實 import 殘留缺陷，必須攔截。
SMOKE_TEST_TOLERATED_MISSING = frozenset({
    "filelock",
    "yaml",
    "pyyaml",
    "pytest",
})


def _is_tolerated_import_error(exc: ModuleNotFoundError) -> bool:
    """判定 ModuleNotFoundError 是否屬「環境限制可容忍」而非框架碼缺陷。

    缺席的若是已知第三方庫（push 零依賴環境本就無）→ 容忍；
    缺席的若是框架核心套件自身的子模組（import 殘留，指向已刪除/改名的內部
    模組）→ 不容忍，視為缺陷。

    參數:
        exc: 捕捉到的 ModuleNotFoundError

    傳回:
        bool: True 表示可容忍（環境限制），False 表示屬框架缺陷
    """
    missing = (exc.name or "").split(".")[0]
    if not missing:
        return False
    # 框架核心套件內部的 import 殘留：絕不容忍（此即目標缺陷類別）
    if missing == FRAMEWORK_CORE_PACKAGE_NAME:
        return False
    return missing in SMOKE_TEST_TOLERATED_MISSING


def run_framework_smoke_test(staging_dir: Path) -> None:
    """push / tag 前對 staging 樹的框架核心套件做 import smoke test（C1 生產閘）。

    呼叫時機：stage_tracked_tree() 取得 git tracked 樹後、git push（含版本 tag）
    任何階段「之前」。red 時 sys.exit(1)，與 validate_version_bump 並列為 push 前
    fail-fast 防護，紅燈時不得進入 push / tag。

    Why：機械缺陷（import 殘留——殘留對已刪除/改名內部模組的 import）零審查直推會
    瞬時傳染全部 consumer 致下游崩潰（框架核心套件被全 consumer 直接 import 執行）。
    push 前在 staging 樹實際 import 全模組，可零誤報攔下整個缺陷類別。

    Consequence：缺此閘門時，一次不完整重構（漏改某處 import）即可在無人審查下
    push 出損壞框架，下游 pull 後 ticket 工具整體 import 失敗。

    Action：以 pkgutil.walk_packages 走訪 staging 樹核心套件全子模組逐一 import。
      - 框架內部模組缺失（ModuleNotFoundError name 屬核心套件）/ 語法錯誤
        （SyntaxError）/ 其他 import 期例外 → 視為缺陷 → sys.exit(1)。
      - 已知第三方依賴缺失（SMOKE_TEST_TOLERATED_MISSING，push 零依賴環境本就無）
        → 容忍，不算缺陷（零誤報要求）。
    staging 樹無核心套件時（理論上不會發生）安全略過，不 abort。

    隔離：本函式以獨立 sys.path 前綴 import 並在結束後清理已 import 的核心套件
    模組，避免污染 push 腳本自身的 import 狀態（push 腳本另經 sys.path 載入
    hooks/lib 的 manifest）。

    參數:
        staging_dir: git archive 解出、已 strip .claude/ 前綴的 staging 樹根目錄
    """
    pkg_dir = staging_dir / FRAMEWORK_CORE_PACKAGE_DIR
    if not (pkg_dir / "__init__.py").is_file():
        # staging 樹未含核心套件：無可檢查項，安全略過（不視為缺陷）
        return

    print_color("push 前框架 import smoke test（C1 生產閘）...")
    search_root = str((staging_dir / FRAMEWORK_CORE_PACKAGE_DIR).parent)
    failures: list[str] = []
    inserted = False
    imported_before = set(sys.modules)
    try:
        if search_root not in sys.path:
            sys.path.insert(0, search_root)
            inserted = True
        importlib.invalidate_caches()

        try:
            pkg = importlib.import_module(FRAMEWORK_CORE_PACKAGE_NAME)
        except ModuleNotFoundError as exc:
            if not _is_tolerated_import_error(exc):
                failures.append(f"{FRAMEWORK_CORE_PACKAGE_NAME}: {exc}")
            pkg = None
        except (ImportError, SyntaxError, Exception) as exc:  # noqa: BLE001
            failures.append(f"{FRAMEWORK_CORE_PACKAGE_NAME}: {exc!r}")
            pkg = None

        if pkg is not None:
            for mod in pkgutil.walk_packages(
                pkg.__path__, prefix=f"{FRAMEWORK_CORE_PACKAGE_NAME}."
            ):
                # 測試模組（tests）import pytest 等非生產依賴，不屬下游執行路徑，跳過
                if ".tests" in mod.name or mod.name.endswith(".tests"):
                    continue
                try:
                    importlib.import_module(mod.name)
                except ModuleNotFoundError as exc:
                    if not _is_tolerated_import_error(exc):
                        failures.append(f"{mod.name}: {exc}")
                except (ImportError, SyntaxError, Exception) as exc:  # noqa: BLE001
                    failures.append(f"{mod.name}: {exc!r}")
    finally:
        # 清理：移除本次 import 進來的核心套件模組與 sys.path 前綴，避免污染
        for name in set(sys.modules) - imported_before:
            if name == FRAMEWORK_CORE_PACKAGE_NAME or name.startswith(
                f"{FRAMEWORK_CORE_PACKAGE_NAME}."
            ):
                sys.modules.pop(name, None)
        if inserted and search_root in sys.path:
            sys.path.remove(search_root)
        importlib.invalidate_caches()

    if failures:
        print_color(
            f"[FAIL] 框架 import smoke test 偵測到 {len(failures)} 個模組無法 import：",
            "red",
        )
        for item in failures:
            print_color(f"   - {item}", "red")
        print_color(
            "push 已中止：staging 樹存在 import 殘留 / 語法錯誤等機械缺陷，"
            "若推出會瞬時傳染全部下游。請先修復後重試。",
            "red",
        )
        sys.exit(1)
    print_color("   smoke test 通過：框架核心套件全模組可 import", "green")


# ============================================================================
# PC 編號撞號對稱（push 端，鏡像 sync-claude-pull.py 行 1329+ 的撞號邏輯）
#
# 背景（1.2.0-W1-037 根因）：sync-pull 已有「PC 撞號偵測 + 自動重編號」
# （_next_available_pc_number），把上游 PC 撞本地時重編並注入 lineage 註記。
# sync-push 卻無對稱邏輯——full-overlay 推全部，把本地原生 PC（bare 號）+ pull
# 重編 artifact（含 lineage 的 181/182）一併推上 canonical 上游，製造撞號 + 重複
# mess（GitHub API 實證：上游 PC-177×2 / 178×2 / 181 / 182 共 6 檔）。
#
# 本模組補三規則，方向與 PC-APP-002「於 sync-push 由框架賦予 canonical 編號」一致：
#   1. 辨識 pull 重編 artifact（含 lineage 標記）不外推——canonical 版已在上游。
#   2. 本地原生 bare PC 若號已被上游不同 slug 佔用 → 賦 next-available canonical
#      號、回寫本地 + 注入 lineage 標記（與 pull 重編對稱）。
#   3. 首跑對帳：辨識並修正當前上游既存 mess。
#
# 設計刻意只認 flat 凍結核心格式（PC-NNN），不拓寬至前綴格式（PC-V1-/PC-APP-/
# PC-TUNL-）——前綴格式各專案在自己命名空間累加，天生不參與 flat 整數撞號。
# 與 pull 端 _PC_FILENAME_RE 決策一致（1.0.0-W1-019.2）。
# ============================================================================

# 與 pull 端 _PC_FILENAME_RE 對稱：只匹配 bare PC-<NNN>-<slug>.md（前綴格式回 None）
_PUSH_PC_FILENAME_RE = re.compile(r"^PC-(\d+)-(.+)\.md$")
# 解析本地 lineage 註記（與 pull 的 _build_provenance_note 寫入字面對稱）：
# 「...編號為 PC-<上游號>...重新編號為 PC-<本地號>」。同時抓上游號與本地號。
_PUSH_LINEAGE_RE = re.compile(
    r"編號溯源.*?編號為\s*PC-(\d+).*?重新編號為\s*PC-(\d+)",
    re.DOTALL,
)


def parse_pc_filename(repo_rel: str) -> tuple[int, str] | None:
    """解析 error-patterns 下 bare PC 檔的 (編號, slug)；與 pull 端對稱。

    僅匹配 error-patterns/ 範圍內、檔名形如 PC-<NNN>-<slug>.md 者。
    前綴格式（PC-V1-/PC-APP-/PC-TUNL-）與非 PC 檔（README、IMP/TEST/ARCH）回 None
    ——刻意排除於 flat 撞號子系統（前綴空間各專案獨立累加，零協調防碰撞）。
    """
    parts = repo_rel.split("/")
    if len(parts) < 2 or parts[0] != "error-patterns":
        return None
    m = _PUSH_PC_FILENAME_RE.match(parts[-1])
    if not m:
        return None
    return int(m.group(1)), m.group(2)


def parse_local_lineage(content: str) -> tuple[int, int] | None:
    """從本地 PC 檔內容解析 lineage 標記，回 (上游號, 本地號)；無標記回 None。

    lineage 標記由 sync-pull 撞號重編時注入（_build_provenance_note）。其存在
    即代表此檔是「pull 端撞號產物」——canonical 版本已在上游以「上游號」存在，
    本地版只是重編號的鏡像，push 時不應外推（規則 1）。
    """
    m = _PUSH_LINEAGE_RE.search(content)
    if m is None:
        return None
    return int(m.group(1)), int(m.group(2))


def compute_lineage_claimed_upstream_files(claude_dir: Path) -> set[str]:
    """掃描本地 error-patterns，回傳「被本地 lineage 重編號檔以溯源註解認領」的
    上游 repo 相對路徑集合（form: error-patterns/.../PC-<上游號>-<slug>.md）。

    Why（PC-APP-002 + 1.2.0-W1-039）：detect_uncleaned_deletions / clean_stale_files
    以純檔名比對判孤兒（上游有、本地 tracked 樹無 → 孤兒）。但本地把上游 canonical
    PC-<N> 重編為 PC-<M>（注入 lineage 註解，保留 slug）後，上游的 PC-<N>-<slug>
    在本地已無同名檔，會被誤列孤兒——若帶 --clean 會刪掉上游 canonical（PC-APP-002
    近失）。本函式重建「本地 lineage 檔認領了哪些上游 (號, slug)」，供孤兒偵測排除，
    使框架 canonical 受保護。

    Consequence（不做）：renumber native intruder 讓位後，--clean 無法區分
    「上游 canonical（被 lineage 認領，應保留）」與「上游 native intruder（無人認領，
    應清）」，兩者同列孤兒——保守起見只能整批不清（intruder 永留），或誤刪 canonical。

    Action：對每個本地 bare PC 檔，若含 lineage 註解（上游號, 本地號）且檔名 slug 與
    本地號一致，則認領上游 `error-patterns/<同子目錄>/PC-<上游號>-<slug>.md`。回傳這些
    上游路徑集合。native intruder（如 PC-184-malformed，lineage None）不認領任何上游檔，
    故上游殘留的 PC-177-malformed 仍為真孤兒可清——這正是讓位後欲達成的辨識。

    純讀取：只讀本地檔，不碰網路 / 上游。
    """
    claimed: set[str] = set()
    ep_root = claude_dir / "error-patterns"
    if not ep_root.is_dir():
        return claimed
    for path in sorted(ep_root.rglob("PC-*.md")):
        repo_rel = path.relative_to(claude_dir).as_posix()
        parsed = parse_pc_filename(repo_rel)
        if parsed is None:
            continue
        _local_num, slug = parsed
        try:
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        lineage = parse_local_lineage(content)
        if lineage is None:
            continue
        upstream_num, _ln = lineage
        prefix = repo_rel.rsplit("/", 1)[0]
        claimed.add(f"{prefix}/PC-{upstream_num}-{slug}.md")
    return claimed


def build_upstream_pc_index(upstream_root: Path) -> dict:
    """掃描 clone 下來的上游 error-patterns/ 建立 PC 佔用索引。

    上游現況可能本身有 mess（同號多 slug），故 numbers 對每個號收 slug 集合，
    不假設一號一 slug（與 pull 的 numbers: dict[int,str] 差異——pull 假設本地
    乾淨，push 端面對的上游可能已被先前誤推弄髒，須容納 mess 才能正確對帳）。

    必須在 copy_filtered_from_staging 把本地檔覆蓋上去之前呼叫，否則拿到的是
    覆蓋後的混合樹而非上游純態。

    回傳:
        {
          "numbers": {編號: set(slug, ...)},        # 上游已佔用號 → slug 集合
          "by_slug": {(編號, slug): repo_rel},       # 反查 repo 相對路徑
        }
    """
    numbers: dict[int, set[str]] = defaultdict(set)
    by_slug: dict[tuple[int, str], str] = {}
    ep_root = upstream_root / "error-patterns"
    if not ep_root.is_dir():
        return {"numbers": {}, "by_slug": by_slug}
    for path in ep_root.rglob("PC-*.md"):
        m = _PUSH_PC_FILENAME_RE.match(path.name)
        if not m:
            continue
        num = int(m.group(1))
        slug = m.group(2)
        numbers[num].add(slug)
        rel = path.relative_to(upstream_root).as_posix()
        by_slug[(num, slug)] = rel
    return {"numbers": dict(numbers), "by_slug": by_slug}


def _next_available_canonical_number(
    upstream_numbers: dict, start: int, reserved: set[int] | None = None
) -> int:
    """從 start 起找第一個上游未佔用、且未被本輪 reserved 的 PC 號。

    鏡像 pull 的 _next_available_pc_number，並加上 reserved 集合避免同輪多檔
    撞同一新號。候選取 max(已佔用號 ∪ reserved)+1 與 start+1 的較大者，再往上
    找同時不在 upstream_numbers 與 reserved 的空號。
    upstream_numbers 為 {號: set(slug)}（push 端容納 mess 的形態）。
    """
    reserved = reserved or set()
    occupied = set(upstream_numbers) | reserved
    candidate = max(occupied, default=start - 1) + 1
    candidate = max(candidate, start + 1)
    while candidate in occupied:
        candidate += 1
    return candidate


def _build_push_lineage_note(upstream_num: int, local_num: int) -> str:
    """產生 lineage 註記行（與 pull 的 _build_provenance_note 字面對稱）。

    push 端賦 canonical 號後回寫本地時注入，使本地保留「我重編過」的記憶，
    下次 push 即被規則 1 辨識為 artifact 不再外推（與 pull dedup 對稱）。
    """
    return (
        f"> **編號溯源**：本 pattern 在上游框架 repo（tarrragon/claude.git）"
        f"編號為 PC-{upstream_num}。因本專案 PC-{upstream_num} 已被既有 pattern 佔用，"
        f"於本專案重新編號為 PC-{local_num}。下次 sync-pull 仍會帶回上游 "
        f"PC-{upstream_num}，屆時應辨識為同一 pattern 並去重。\n"
    )


def _inject_lineage_into_local(content: str, upstream_num: int, local_num: int) -> str:
    """把 lineage 註記插入本地 PC 檔內容首行（若尚無 lineage）。

    push 端賦 canonical 號的 local_num 即上游配給的新號；upstream_num 在此語境
    指「本地原檔名的舊號」（被上游佔用而需讓位者）。回寫後本地檔名改為 local_num，
    內文記「曾以 upstream_num 存在、現重編 local_num」，與 pull 重編記憶對稱。
    """
    if _PUSH_LINEAGE_RE.search(content):
        return content
    note = _build_push_lineage_note(upstream_num, local_num)
    return note + "\n" + content


def plan_push_pc_action(
    repo_rel: str,
    local_content: str,
    upstream_index: dict,
    reserved: set[int] | None = None,
) -> dict:
    """對單一本地 PC 檔決定 push 處置（規則 1 + 規則 2）。

    reserved（選填）：本輪已賦給其他撞號檔的新 canonical 號集合。多個本地原生
    撞號同輪賦號時必須傳入，否則每個都算到同一 next-available 號（全部撞 PC-184）。
    本函式賦號後會把新號加入 reserved（就地 mutate），供下一檔避開。

    回傳 dict（action 枚舉）：
      - {"action": "none"}                    非 PC / 無撞號，原樣推送
      - {"action": "exclude_lineage_artifact",
         "upstream_num": int, "local_num": int}
            含 lineage（pull 重編產物）→ 不外推（canonical 版已在上游）
      - {"action": "assign_canonical",
         "old_num": int, "slug": str,
         "new_num": int, "old_repo_rel": str,
         "new_repo_rel": str, "new_content": str}
            本地原生 bare 號被上游不同 slug 佔用 → 賦 next-available canonical 號

    純函式：不碰檔案系統，便於單元測試。實際 IO（改檔名、回寫本地、排除複製）
    由 apply_push_pc_collision orchestrator 依本計畫執行。
    """
    parsed = parse_pc_filename(repo_rel)
    if parsed is None:
        return {"action": "none"}
    num, slug = parsed

    # 規則 1：含 lineage = pull 重編 artifact，canonical 版已在上游 → 不外推
    lineage = parse_local_lineage(local_content)
    if lineage is not None:
        upstream_num, local_num = lineage
        return {
            "action": "exclude_lineage_artifact",
            "upstream_num": upstream_num,
            "local_num": local_num,
        }

    # 規則 2：本地原生 bare 號。檢查上游此號的佔用狀況。
    upstream_numbers: dict = upstream_index.get("numbers", {})
    occupant_slugs = upstream_numbers.get(num, set())
    # 上游無此號 → 本地此 pattern 是該號的 canonical，正常推送。
    if not occupant_slugs:
        return {"action": "none"}
    # 本地 slug 已在上游此號的佔用集合中 → 同一 pattern 已在上游 canonical
    # （含「同號合法多 pattern」設計態：上游 PC-010 兩 slug 與本地兩 slug 一致）。
    # 不視為撞號，原樣推送交三方合併（Never break userspace——不動既有合法配號）。
    if slug in occupant_slugs:
        return {"action": "none"}
    # 上游此號只被「別的 slug」佔、本地此 slug 不在其中 → 真撞號，本地讓位賦新號。
    new_num = _next_available_canonical_number(upstream_numbers, num, reserved)
    if reserved is not None:
        reserved.add(new_num)
    prefix = repo_rel.rsplit("/", 1)[0]
    new_repo_rel = f"{prefix}/PC-{new_num}-{slug}.md"
    new_content = _inject_lineage_into_local(local_content, num, new_num)
    return {
        "action": "assign_canonical",
        "old_num": num,
        "slug": slug,
        "new_num": new_num,
        "old_repo_rel": repo_rel,
        "new_repo_rel": new_repo_rel,
        "new_content": new_content,
    }


def plan_upstream_mess_reconciliation(upstream_index: dict) -> list[dict]:
    """首跑對帳：辨識上游既存 mess 並產出修正計畫（規則 3）。

    mess 的可操作定義（精準，不誤報合法態）：**同一 slug 在上游同時以兩個以上不同
    PC 號存在**——這只可能來自「sync-push 把本地 pull 重編 artifact（如 PC-181=
    上游 PC-177 的重編鏡像）誤推上游」，使同一 pattern 在上游既有 canonical 低號、
    又多一份高號鏡像。高號份應移除（canonical 是低號）。

    刻意**不**把「同一號被多個不同 slug 佔用」列為 mess：上游本就允許同號合法承載
    多個不同 pattern（如 PC-010 同時有 task-tracking-in-memory 與 pm-skipped-...，
    兩者皆 canonical、設計如此）。把它列為 mess 會對合法配號誤報（PC-010/019/020/
    030/105 即此類），故排除。本地原生撞號（本地 slug 不在上游此號）的讓位由 push
    規則 2 per-file 處理，不需在對帳階段重複列舉。

    已知限制（native-already-pushed 模糊性）：若先前不對稱 push 已把本地原生 PC
    （如 PC-177-malformed）推上一個本由框架 canonical 佔用的號，上游此號變成
    「foreign canonical + native intruder」兩 slug。單看上游無法判別哪個是 native
    intruder（需與本地全索引對照才能斷定），故本函式不自動讓位這類已誤推的 native。
    可操作的去重訊號（同 slug 重複號，如 181/182）仍被精準辨識並由規則 1 排除
    本地 artifact + overlay/unlink 移除上游重複份；剩餘 foreign+native 並存的兩
    slug 待人工或後續 ticket 以本地索引對照解（避免誤刪框架 canonical）。

    回傳修正項目 list，每項：
      {"kind": "duplicate_renumbered_slug", "slug": str,
       "canonical_num": int, "duplicate_num": int,
       "canonical_repo_rel": str, "duplicate_repo_rel": str}

    純函式：只讀 upstream_index，不碰網路 / 檔案。輸出供 dry-run 列印與審查。
    """
    plan: list[dict] = []
    by_slug: dict = upstream_index.get("by_slug", {})

    # 偵測同 slug 重複（canonical 低號 + 誤推高號鏡像）——唯一可操作的 mess 訊號
    slug_to_nums: dict[str, list[int]] = defaultdict(list)
    for (num, slug) in by_slug:
        slug_to_nums[slug].append(num)
    for slug, nums in slug_to_nums.items():
        if len(nums) < 2:
            continue
        nums_sorted = sorted(nums)
        canonical_num = nums_sorted[0]
        for dup_num in nums_sorted[1:]:
            plan.append({
                "kind": "duplicate_renumbered_slug",
                "slug": slug,
                "canonical_num": canonical_num,
                "duplicate_num": dup_num,
                "canonical_repo_rel": by_slug[(canonical_num, slug)],
                "duplicate_repo_rel": by_slug[(dup_num, slug)],
            })
    return plan


def apply_push_pc_collision(
    remote_dir: Path,
    upstream_index: dict,
    dry_run: bool = False,
) -> dict:
    """orchestrator：依 plan_push_pc_action 對 remote_dir 內已複製的本地 PC 檔
    施加撞號對稱（規則 1 + 2）。

    時機：copy_filtered_from_staging 之後、git add 之前。此時 remote_dir 含
    上游 clone + 已覆蓋的本地檔；upstream_index 須為 copy 之前快照的上游純態。

    動作（僅作用於 remote_dir，即將推上游的樹）：
      - exclude_lineage_artifact：從 remote_dir 移除該檔（不外推 artifact）
      - assign_canonical：把舊號檔改名為新 canonical 號 + 寫入新內容（含 lineage）

    本地 working tree 的回寫（讓本地檔保留 lineage 記憶）不在此處——由 main 在
    push 成功後依本函式回傳的 renumbered 計畫另行套用至 claude_dir，避免 dry-run
    或 push 失敗時污染本地源（規則 1.5：世界副作用 at-least-once，記憶寫入須晚於
    確認推送成功）。

    回傳統計 dict：{"excluded": [...], "renumbered": [...], "untouched": int}。
    每個 renumbered 項含完整 plan，供 main 套回 working tree。

    注意：本函式只動 error-patterns 下 bare PC 檔；其餘檔案完全不碰
    （Never break userspace——既有 push 行為對非 PC 檔零變更）。
    """
    excluded: list[dict] = []
    renumbered: list[dict] = []
    untouched = 0
    reserved: set[int] = set()  # 本輪已賦的新號，避免多檔撞同一 next-available

    ep_root = remote_dir / "error-patterns"
    if not ep_root.is_dir():
        return {"excluded": excluded, "renumbered": renumbered, "untouched": 0}

    # 收集 remote_dir 內所有 bare PC 檔（這些是「本地剛覆蓋上去的」候選）
    for path in sorted(ep_root.rglob("PC-*.md")):
        repo_rel = path.relative_to(remote_dir).as_posix()
        if parse_pc_filename(repo_rel) is None:
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            untouched += 1
            continue
        plan = plan_push_pc_action(repo_rel, content, upstream_index, reserved)
        action = plan["action"]
        if action == "none":
            untouched += 1
            continue
        if action == "exclude_lineage_artifact":
            # artifact 不外推：從 remote 樹移除（canonical 已在上游）
            if not dry_run:
                path.unlink(missing_ok=True)
            excluded.append({
                "repo_rel": repo_rel,
                "upstream_num": plan["upstream_num"],
                "local_num": plan["local_num"],
            })
            continue
        if action == "assign_canonical":
            new_path = remote_dir / plan["new_repo_rel"]
            if not dry_run:
                # remote：移除舊號檔、寫入新 canonical 號檔（含 lineage）
                path.unlink(missing_ok=True)
                new_path.parent.mkdir(parents=True, exist_ok=True)
                new_path.write_text(plan["new_content"], encoding="utf-8")
            # 完整 plan 帶回，供 push 成功後套回本地 working tree
            renumbered.append(dict(plan))
    return {
        "excluded": excluded,
        "renumbered": renumbered,
        "untouched": untouched,
    }


def writeback_local_canonical_assignments(
    claude_dir: Path, renumbered: list[dict]
) -> int:
    """push 成功後把賦 canonical 號的結果套回本地 working tree。

    對每個 assign_canonical 項：刪本地舊號檔、寫新號檔（含 lineage 註記），使
    本地源保留「已重編」記憶——下次 push 即被規則 1（exclude_lineage_artifact）
    辨識為 artifact 不再外推，達成自癒收斂。

    僅在 push 成功後呼叫（規則 1.5：記憶寫入 at-most-once，須晚於確認世界副作用）。
    回傳實際回寫的檔案數。
    """
    written = 0
    for plan in renumbered:
        old_local = claude_dir / plan["old_repo_rel"]
        new_local = claude_dir / plan["new_repo_rel"]
        if old_local.exists():
            old_local.unlink()
        new_local.parent.mkdir(parents=True, exist_ok=True)
        new_local.write_text(plan["new_content"], encoding="utf-8")
        written += 1
    return written


def parse_args(argv: list[str]) -> argparse.Namespace:
    """以 argparse 解析命令列參數（0.32.0-W1-008，PC-V1-001 防護）。

    Why：舊版手動 `sys.argv[1]` 把任何位置參數當 commit 訊息，導致 --help /
    未知旗標被誤認為 commit message 而觸發真實不可逆推送（v1.48.6 誤推實證）。
    argparse 對 --help 自動 exit 0、對未知旗標 exit 2，兩者都在解析階段中止，
    不進入 clone / push 流程。

    Consequence：缺此防護時，使用者敲 `sync-push --help` 期望看用法，實際推出
    一次以「--help」為 commit 訊息的不可逆框架更新。

    Action：main 改呼叫本函式取結構化參數；--help / 未知旗標經 argparse 攔截。

    參數:
        argv: 不含程式名的參數列（通常為 sys.argv[1:]）

    傳回:
        argparse.Namespace: 含 message / clean / force / dry_run 欄位

    例外:
        SystemExit: --help（code 0）或未知旗標 / 參數錯誤（code 2）時由
            argparse 拋出，呼叫端不應吞掉，使其終止於解析階段不觸發推送。
    """
    parser = argparse.ArgumentParser(
        prog="sync-push",
        description=".claude 資料夾推送到獨立框架 repo（git archive HEAD overlay）",
    )
    parser.add_argument(
        "message",
        nargs="?",
        default=None,
        help="commit 訊息（省略時自動分析 .claude/ commit 生成摘要）",
    )
    parser.add_argument(
        "--clean", action="store_true", help="清理遠端過時檔案（傳播本地刪除）"
    )
    parser.add_argument(
        "--force", action="store_true", help="跳過 no-change early-exit 檢查"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="只生成 commit message，不 clone / push"
    )
    return parser.parse_args(argv)


def main() -> None:
    args = parse_args(sys.argv[1:])

    # --dry-run：只生成 commit message 不 push
    if args.dry_run:
        run_dry_run()
        return

    clean_mode = args.clean
    force_mode = args.force
    # commit message is now optional - auto-generated when not provided
    user_message = args.message

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

    # 偵測「本地已 git rm 但未帶 --clean」的遠端孤兒清單（R2 soft 警告用）。
    # 預設空 list；僅 not clean_mode 時於 staging 比對後填入，push 成功後結尾警告。
    uncleaned_deletions: list[str] = []

    # 3. Clone remote repo (preserve history)
    print_color("Clone 遠端 repo（保留歷史）...")
    temp_dir = Path(tempfile.mkdtemp())
    try:
        run_git(["clone", REPO_URL, str(temp_dir)])

        # 快照遠端 skill 版本（W2-001：push 尾端輸出 skill 版本 diff 摘要）
        skill_versions_before = extract_skill_versions(temp_dir / "skills")

        # 4.0 快照上游 PC 純態（copy 覆蓋前）+ 首跑對帳計畫（規則 3）。
        # 必須在 copy_filtered_from_staging 之前——之後 temp_dir 已被本地覆蓋，
        # 拿到的是混合樹而非上游純態。
        upstream_pc_index = build_upstream_pc_index(temp_dir)
        reconciliation_plan = plan_upstream_mess_reconciliation(upstream_pc_index)
        if reconciliation_plan:
            print_color(
                f"偵測上游既存 PC mess（同 slug 重複號）：{len(reconciliation_plan)} 項待對帳",
                "yellow",
            )
            for item in reconciliation_plan:
                print_color(
                    f"   [重複] slug={item['slug']} canonical=PC-{item['canonical_num']}"
                    f" 誤推鏡像=PC-{item['duplicate_num']}（高號該移除）"
                )

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
            # C1 生產閘：在 push / tag 任何階段之前，於 staging 樹做框架 import
            # smoke test。紅燈時 sys.exit(1)，確保損壞框架不會被 push 或打 tag。
            run_framework_smoke_test(staging_dir)
            # 載入 preserve 清單（0.32.0-W1-008）：APP 專案特化檔不推上共享框架，
            # 與 pull 端原地保留對稱。傳入 copy / clean / detect 全程一致排除。
            preserve = load_preserve_list(claude_dir)
            if preserve:
                print_color(f"   preserve 清單：{len(preserve)} 個專案特化檔不推送", "green")  # i18n-exempt
            skills_config = load_sync_skills_config(claude_dir)
            if skills_config["mode"] != "all" or skills_config["private"]:
                print_color(  # i18n-exempt
                    f"   sync-skills: mode={skills_config['mode']}"
                    + (f", include={skills_config['include']}" if skills_config["mode"] == "select" else "")
                    + (f", private={skills_config['private']}" if skills_config["private"] else ""),
                    "green",
                )
            file_count = copy_filtered_from_staging(staging_dir, temp_dir, preserve, skills_config)
            print_color(  # i18n-exempt
                f"   過濾後複製 {file_count} 個檔案（should_exclude + preserve + skills 已套用）",
                "green",
            )
            print_color("   注意: CLAUDE.md 不再同步（專案特定配置）")

            # 孤兒偵測前重建 lineage 認領集（PC-APP-002 / W1-039）：本地 lineage
            # 重編號檔認領的上游 canonical（如 PC-181 認領上游 PC-177-defensive）不算
            # 孤兒，避免 --clean 誤刪框架 canonical。讓位後的 native intruder（PC-184
            # 等，無 lineage）不認領上游，故上游殘留 PC-177-malformed 仍為真孤兒可清。
            lineage_claimed = compute_lineage_claimed_upstream_files(claude_dir)
            if lineage_claimed:
                print_color(
                    f"   lineage 認領上游 canonical：{len(lineage_claimed)} 個（孤兒偵測排除）",
                    "green",
                )

            # 7.5. 清理遠端過時檔案（僅 --clean 模式）。
            # 以 staging（tracked 樹）為基準：git rm 的檔不在 staging → 從遠端刪除（K）。
            if clean_mode:
                print_color("清理遠端過時檔案（對齊 git tracked 樹）...")
                deleted = clean_stale_files(
                    temp_dir, staging_dir, preserve, lineage_claimed, skills_config
                )
                print_color(f"   已清理 {deleted} 個遠端過時檔案", "green")  # i18n-exempt
            else:
                # 未帶 --clean 時偵測本地已 git rm 但遠端殘留的孤兒（R2 soft 警告，
                # 不阻擋、不改 --clean 預設）。在 staging rmtree 前計算並暫存，
                # 待 push 成功後於結尾輸出提醒。
                uncleaned_deletions = detect_uncleaned_deletions(
                    temp_dir, staging_dir, preserve, lineage_claimed, skills_config
                )
        finally:
            shutil.rmtree(staging_dir, ignore_errors=True)

        # 7.55. PC 編號撞號對稱（規則 1 + 2，1.2.0-W1-038）：對 temp_dir 內剛覆蓋
        # 的本地 PC 檔施加 push 端撞號處置——排除 lineage artifact、本地原生撞號
        # 賦 canonical 號。upstream_pc_index 為 copy 之前快照的上游純態。
        pc_collision_result = apply_push_pc_collision(
            temp_dir, upstream_pc_index, dry_run=False
        )
        if pc_collision_result["excluded"]:
            print_color(
                f"   排除 {len(pc_collision_result['excluded'])} 個 pull 重編 artifact"
                "（不外推，canonical 已在上游）",
                "green",
            )
            for item in pc_collision_result["excluded"]:
                print_color(
                    f"     - {item['repo_rel']}"
                    f"（lineage: 上游 PC-{item['upstream_num']} / 本地 PC-{item['local_num']}）"
                )
        if pc_collision_result["renumbered"]:
            print_color(
                f"   {len(pc_collision_result['renumbered'])} 個本地原生撞號賦 canonical 號",
                "green",
            )
            for item in pc_collision_result["renumbered"]:
                print_color(
                    f"     - PC-{item['old_num']} -> PC-{item['new_num']}（slug={item['slug']}）"
                )

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

        # PC 撞號賦 canonical 後，push 成功才把結果套回本地 working tree（規則 1.5：
        # 記憶寫入須晚於確認世界副作用，避免 push 失敗時本地殘留未實際外推的重編）。
        if pc_collision_result["renumbered"]:
            written = writeback_local_canonical_assignments(
                claude_dir, pc_collision_result["renumbered"]
            )
            if written:
                print_color(
                    f"   已回寫 {written} 個本地 PC 檔（賦 canonical 號 + lineage 記憶），"
                    "請 git add .claude && git commit 持久化",
                    "yellow",
                )

        # tagged-release：push 成功後對本版打 git tag（remote 可見），供下游 pin 特定版。
        create_and_push_version_tag(temp_dir, new_version)

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

        print_color("成功推送 .claude 到獨立 repo！", "green")  # i18n-exempt
        print_color(f"Remote: {REPO_URL}", "green")
        print_color("遠端 commit 歷史已保留", "green")  # i18n-exempt
        print_color("注意: 根目錄 CLAUDE.md 未被推送（專案特定配置）")  # i18n-exempt

        # Skill 版本 diff 摘要（W2-001）
        skill_versions_after = extract_skill_versions(claude_dir / "skills")
        skill_diff = format_skill_version_diff(skill_versions_before, skill_versions_after)
        if skill_diff:
            print_color(skill_diff, "green")

        # R2 soft 警告：本次未帶 --clean，但本地已 git rm 的 tracked .claude/ 檔
        # 在遠端殘留為孤兒。僅提醒（不阻擋、不改 --clean 預設），避免誤刪風險。
        if uncleaned_deletions:
            preview = uncleaned_deletions[:10]
            more = len(uncleaned_deletions) - len(preview)
            print_color(
                f"[提醒] 本次 push 未帶 --clean，偵測到 {len(uncleaned_deletions)} 個"
                "本地已刪除但遠端殘留的 tracked .claude/ 檔（孤兒）：",
                "yellow",
            )
            for rel in preview:
                print_color(f"   - {rel}", "yellow")
            if more > 0:
                print_color(f"   ...（另有 {more} 個）", "yellow")
            print_color(
                "若要將這些刪除傳播到遠端（避免 full overlay sync 把孤兒複製回下游），"
                "請重跑：sync-push --clean",
                "yellow",
            )

    except subprocess.TimeoutExpired:
        print_color("git 操作超時，請檢查網路連線", "red")
        sys.exit(1)
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
