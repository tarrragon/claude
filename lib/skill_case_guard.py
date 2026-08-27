"""共用 skill.md 大小寫告警 helper。

沿革：skill-sync 的 `cli.py` 原已建立同型判準（os.scandir 真實 dirent），
後續分析確認 `skill_version_diff.py`（glob 字面）、
`skill-description-length-check-hook.py`（path-concat）、
`skill_residue_detector.py`（rglob + 字串相等）三處掃描點有同型漏掃盲區卻從
未告警。本模組把判準抽成 `.claude/lib/` 共用函式，供四處掃描點呼叫，避免
各自平行維護再度分岔。

判準必須讀取實際目錄項名稱（`os.scandir` 的 `entry.name`），不可用
`Path.exists()` 或 `Path.glob()`：case-insensitive 檔案系統（如 macOS
APFS）上兩者都可能對小寫 `skill.md` 回傳「找到了」，讓判準失效。
`pathlib.Path.glob()` 另有版本邊界——Python 3.13 起在 `case_sensitive`
省略時改為探測實際檔案系統，3.12 及之前固定 case-sensitive 比對；同一份
程式碼在不同 Python 版本會給出不同掃描集合，且兩邊都不報錯。本函式全程走
`os.scandir`，判準與 Python 版本、檔案系統大小寫敏感性無關。

第二判別維度（`check_git_tree_skill_md_case`）：`os.scandir` 讀的是本地
檔案系統的 dirent，`core.ignorecase=true` 環境下 checkout / overlay 只
覆寫既有 dirent 的內容位元組、不覆寫其大小寫，本地列目錄因此看不出遠端
git tree 實際記錄的大小寫是否已分歧。此函式改讀 `git ls-tree` 的 tree
object bytes，供推送前（來源端仍看得見）偵測用，見函式 docstring。
"""
from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path


def find_case_variant(skill_dir: Path) -> str | None:
    """回傳 skill_dir 內非精確大寫 SKILL.md 的大小寫變體檔名，無變體則回傳 None。

    參數:
        skill_dir: 單一 skill 目錄（如 .claude/skills/wrap-decision/）

    傳回:
        str | None: 目錄內若已有精確大寫 `SKILL.md`，或無任何大小寫變體，
        回傳 None；否則回傳實際存在的變體檔名（如 `skill.md`、`Skill.md`）。
        `skill_dir` 不是目錄或無法讀取時回傳 None。

    判準讀取實際目錄項名稱（`os.scandir` 的 `entry.name`），不可用
    `Path.exists()` 或 `Path.glob()`——兩者在 case-insensitive 檔案系統上
    對小寫 `skill.md` 都可能回傳「找到了」，讓判準失效（見本模組頂部說明）。
    """
    try:
        names = [f.name for f in os.scandir(skill_dir) if f.is_file()]
    except OSError:
        return None
    if "SKILL.md" in names:
        return None
    return next((n for n in names if n.lower() == "skill.md"), None)


def warn_skill_md_case_mismatch(base_dir: Path) -> list[str]:
    """對 base_dir 下每個 skill 目錄，若無精確大寫 SKILL.md 但存在其他大小寫變體，回傳告警文字清單。

    參數:
        base_dir: skills 根目錄（如 .claude/skills/）

    傳回:
        list[str]: 每個大小寫不符的 skill 各一則告警文字（不含換行），
        `base_dir` 不存在或無不符項時回傳空清單。呼叫端依各自輸出慣例
        （stderr / logger）自行輸出，本函式不做 I/O。
    """
    warnings: list[str] = []
    if not base_dir.is_dir():
        return warnings
    for entry in sorted(os.scandir(base_dir), key=lambda e: e.name):
        if not entry.is_dir():
            continue
        variant = find_case_variant(Path(entry.path))
        if variant is not None:
            warnings.append(
                f"{entry.name}: 檔名為 '{variant}'，非精確大寫 'SKILL.md'，"  # i18n-exempt
                "不會進入 manifest 掃描（case-sensitive glob 在 Python 3.13 前恆漏，"  # i18n-exempt
                "3.13 起依檔案系統大小寫敏感性而定）"  # i18n-exempt
            )
    return warnings


_GIT_TREE_LOWERCASE_SKILL_MD = re.compile(r"^skills/([^/]+)/skill\.md$")


def check_git_tree_skill_md_case(repo_dir: Path, ref: str = "HEAD") -> list[str]:
    """讀 git tree object（而非本地檔案系統）偵測 skill 目錄的 skill.md 大小寫。

    與 `warn_skill_md_case_mismatch`（讀 `os.scandir` 的本地 dirent 名稱）的
    判別維度不同：本函式讀 `git ls-tree` 回傳的 tree object 條目名稱，是
    version-controlled 的權威記錄，不經任何本地檔案系統正規化。

    Why：`core.ignorecase=true` 的環境把內容更新與檔名更新的可見性拆開——
    checkout / overlay 覆寫既有 dirent 的內容位元組，但保留該 dirent 原有的
    大小寫；本地 `ls` 或 `os.scandir` 因此只會看到「本地既有」的那個大小寫，
    看不出遠端 tree 實際記錄的大小寫是否已分歧。唯有直接讀 tree object 的
    bytes（`git ls-tree`）才能穿透此正規化，在來源端（如 sync-push 推送前）
    偵測遠端 canonical 本身即含錯誤大小寫的檔名。

    Consequence：不檢查 tree object 而只信本地檔案系統列目錄，會讓「來源端
    tree 內大小寫已錯」這類分歧永遠停留在不可見狀態——本地看起來一切正常，
    但下游大小寫敏感檔案系統（多數 Linux 消費端）pull 後，Claude Code 因
    找不到精確大寫 `SKILL.md` 而完全無法載入該 skill。

    參數:
        repo_dir: git repo 的本地路徑（clone 或既有工作目錄）
        ref: 要讀取的 git ref（預設 HEAD）

    傳回:
        list[str]: 每個命中 `skills/<name>/skill.md`（精確小寫）的 skill，
        各一則告警文字（含後果陳述）；repo_dir 非 git repo 或 git 指令失敗
        時回傳空清單（fail-open，不阻擋呼叫端流程）。
    """
    result = subprocess.run(
        ["git", "ls-tree", "-r", "--name-only", ref, "--", "skills"],
        cwd=str(repo_dir),
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return []
    warnings: list[str] = []
    for line in result.stdout.splitlines():
        match = _GIT_TREE_LOWERCASE_SKILL_MD.match(line.strip())
        if match is None:
            continue
        skill_name = match.group(1)
        warnings.append(
            f"{skill_name}: git tree 記錄檔名為 'skill.md'（精確小寫），"  # i18n-exempt
            "非 'SKILL.md'。大小寫敏感檔案系統（多數 Linux 消費端）pull 後，"  # i18n-exempt
            "Claude Code 以精確大寫 SKILL.md 作為載入判準，此 skill 將完全"  # i18n-exempt
            "無法載入"  # i18n-exempt
        )
    return warnings
