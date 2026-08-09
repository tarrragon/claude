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
"""
from __future__ import annotations

import os
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
