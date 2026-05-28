#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///

"""
Session Start Gitignore Check Hook

SessionStart 事件觸發時，檢查專案 .gitignore 是否涵蓋 .claude/ runtime state
必要 entry，並用 git ls-files 偵測已被 tracked 但應 ignore 的檔案。

設計動機（PC-019 死循環）：
- commit 後 AUQ 觸發 hook 寫入 runtime state（pm-status.json/dispatch-active.json/
  hook-state/logs/），檔案若被 git tracked → 阻擋 worktree fork（dirty tree）。
- 治本方法：.gitignore 補齊 + `git rm --cached`。
- 本 hook 預先警示避免跨專案/新環境重蹈。

設計要點：
- 非阻擋（不 exit 2），WARN 等級
- 等效 broader pattern 接受（如 `logs/` 等效於 `.claude/logs/`）
- 失敗降級為靜默（不阻塞 session 啟動）

來源 Ticket：0.19.0-W3-077
"""

import json
import subprocess
import sys
from pathlib import Path
from typing import List, Dict, Any, Set, Tuple

# 加入 hook_utils 路徑
sys.path.insert(0, str(Path(__file__).parent))
from hook_utils import (  # noqa: E402
    setup_hook_logging,
    run_hook_safely,
    read_json_from_stdin,
    get_project_root,
)

EXIT_SUCCESS = 0

# 必要 .gitignore entry 清單（.claude/ runtime state + logs + coverage）
REQUIRED_GITIGNORE_ENTRIES = {
    # Runtime state markers
    ".claude/ARCHITECTURE_REVIEW_REQUIRED",
    ".claude/TASK_AVOIDANCE_FIX_MODE",
    ".claude/PM_INTERVENTION_REQUIRED",
    # Runtime state files
    ".claude/pm-status.json",
    ".claude/dispatch-active.json",
    ".claude/dispatch-active.lock",
    # Runtime state dirs
    ".claude/hook-state/",
    ".claude/state/",
    # logs / coverage
    ".claude/logs/",
    "coverage/",
}

# 等效 broader pattern：若 gitignore 含這些 pattern，視為已覆蓋對應的必要 entry。
# git pattern 不以 / 開頭、結尾斜線會匹配任何層級的同名目錄。
EQUIVALENT_PATTERNS: Dict[str, Set[str]] = {
    ".claude/logs/": {"logs/", "**/logs/"},
    ".claude/hook-logs/": {"hook-logs/", "**/hook-logs/"},
    ".claude/dispatch-active.lock": {"*.lock"},
}

# 偵測「應該 ignore 但已被 tracked」的檔案 pattern（substring 匹配於 git ls-files 輸出）
TRACKED_DETECTION_PATTERNS = [
    ".claude/pm-status.json",
    ".claude/dispatch-active.json",
    ".claude/dispatch-active.lock",
    ".claude/ARCHITECTURE_REVIEW_REQUIRED",
    ".claude/TASK_AVOIDANCE_FIX_MODE",
    ".claude/PM_INTERVENTION_REQUIRED",
    ".claude/hook-state/",
    ".claude/state/",
    ".claude/logs/",
]


def parse_gitignore(gitignore_path: Path, logger) -> Set[str]:
    """讀取 .gitignore，回傳非空非註解行的 set（保留原樣，不展開 pattern）。"""
    if not gitignore_path.exists() or not gitignore_path.is_file():
        return set()
    try:
        text = gitignore_path.read_text(encoding="utf-8")
    except Exception as e:  # noqa: BLE001
        logger.warning("讀取 .gitignore 失敗: %s", e)
        return set()

    entries: Set[str] = set()
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        entries.add(line)
    return entries


def check_missing_entries(gitignore_entries: Set[str], logger) -> List[str]:
    """對 REQUIRED 逐項檢查；缺失且無等效 broader pattern → 加入缺失清單。"""
    missing: List[str] = []
    for required in sorted(REQUIRED_GITIGNORE_ENTRIES):
        if required in gitignore_entries:
            continue
        equivalents = EQUIVALENT_PATTERNS.get(required, set())
        if equivalents & gitignore_entries:
            continue
        missing.append(required)
    logger.info("gitignore-check: missing %d entry(ies)", len(missing))
    return missing


def check_tracked_runtime_state(project_root: Path, logger) -> List[str]:
    """用 git ls-files 偵測應 ignore 但已 tracked 的檔案。"""
    try:
        result = subprocess.run(
            ["git", "ls-files"],
            cwd=str(project_root),
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
        logger.warning("git ls-files 執行失敗（降級為空清單）: %s", e)
        return []
    if result.returncode != 0:
        logger.warning("git ls-files 非零退出: %s", result.stderr.strip())
        return []

    tracked: List[str] = []
    for line in result.stdout.splitlines():
        path = line.strip()
        if not path:
            continue
        for pattern in TRACKED_DETECTION_PATTERNS:
            # 目錄 pattern（結尾斜線）→ prefix 匹配
            if pattern.endswith("/"):
                if path.startswith(pattern):
                    tracked.append(path)
                    break
            else:
                if path == pattern:
                    tracked.append(path)
                    break
    tracked.sort()
    logger.info("gitignore-check: tracked-but-should-ignore %d file(s)", len(tracked))
    return tracked


def build_warning_section(
    missing: List[str],
    tracked: List[str],
    gitignore_exists: bool,
) -> str:
    """組裝 markdown 警告區塊。"""
    lines: List[str] = [
        "## Gitignore 必要 entry 檢查（gitignore-check）",
        "",
    ]
    if not gitignore_exists:
        lines.extend(
            [
                "- [WARNING] gitignore-check: 專案根目錄未偵測到 `.gitignore`，"
                "所有 `.claude/` runtime state 將被 git tracked",
                "  建議建立 `.gitignore` 並加入下列必要 entry。",
                "",
            ]
        )

    if missing:
        lines.append("缺失必要 entry（建議追加到 `.gitignore`）：")
        lines.append("")
        for entry in missing:
            lines.append(f"- [WARNING] gitignore-check: 缺少 `{entry}`")
        lines.append("")
        lines.append("修復建議（追加到 `.gitignore` 末尾）：")
        lines.append("")
        lines.append("```")
        for entry in missing:
            lines.append(entry)
        lines.append("```")
        lines.append("")

    if tracked:
        lines.append("偵測到已被 git tracked 但應 ignore 的 runtime state 檔案：")
        lines.append("")
        for path in tracked:
            lines.append(f"- [WARNING] gitignore-check: `{path}` 已被 git tracked")
        lines.append("")
        lines.append("修復建議（從 git index 移除但保留本地檔案）：")
        lines.append("")
        lines.append("```")
        for path in tracked:
            lines.append(f"git rm --cached {path}")
        lines.append("```")
        lines.append("")

    lines.append(
        "背景：PC-019 死循環——commit 後 AUQ 觸發 hook 寫入 runtime state，"
        "若被 git tracked 會造成 dirty tree 阻擋 worktree fork。"
    )
    return "\n".join(lines)


def build_hook_output(
    missing: List[str],
    tracked: List[str],
    gitignore_exists: bool,
) -> Dict[str, Any]:
    """組裝 SessionStart hook JSON 輸出。"""
    if gitignore_exists and not missing and not tracked:
        return {"suppressOutput": True}
    section = build_warning_section(missing, tracked, gitignore_exists)
    return {
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": section + "\n",
        },
        "suppressOutput": False,
    }


def run_checks(project_root: Path, logger) -> Tuple[List[str], List[str], bool]:
    """執行檢查並回傳 (missing, tracked, gitignore_exists)。"""
    gitignore_path = project_root / ".gitignore"
    gitignore_exists = gitignore_path.exists() and gitignore_path.is_file()
    entries = parse_gitignore(gitignore_path, logger) if gitignore_exists else set()
    missing = (
        check_missing_entries(entries, logger)
        if gitignore_exists
        else sorted(REQUIRED_GITIGNORE_ENTRIES)
    )
    tracked = check_tracked_runtime_state(project_root, logger)
    return missing, tracked, gitignore_exists


def main() -> int:
    """主入口：讀 stdin（可忽略）→ 執行檢查 → 輸出 JSON。"""
    logger = setup_hook_logging("session-start-gitignore-check-hook")
    logger.info("gitignore-check hook 啟動")

    try:
        read_json_from_stdin(logger)
    except Exception as e:  # noqa: BLE001
        logger.warning("讀取 stdin 失敗（忽略）: %s", e)

    try:
        project_root = get_project_root()
    except Exception as e:  # noqa: BLE001
        logger.error("取得 project_root 失敗，降級為靜默: %s", e)
        print(json.dumps({"suppressOutput": True}, ensure_ascii=False))
        return EXIT_SUCCESS

    missing, tracked, gitignore_exists = run_checks(project_root, logger)
    output = build_hook_output(missing, tracked, gitignore_exists)
    print(json.dumps(output, ensure_ascii=False, indent=2))
    logger.info(
        "gitignore-check hook 完成（missing=%d, tracked=%d, gitignore_exists=%s）",
        len(missing),
        len(tracked),
        gitignore_exists,
    )
    return EXIT_SUCCESS


if __name__ == "__main__":
    sys.exit(run_hook_safely(main, "session-start-gitignore-check"))
