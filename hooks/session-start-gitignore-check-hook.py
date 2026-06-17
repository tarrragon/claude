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

# 加入 lib 路徑以 import sync 排除 SOT manifest
sys.path.insert(0, str(Path(__file__).parent / "lib"))
from sync_exclude_manifest import GITIGNORE_EXPECTED  # noqa: E402

EXIT_SUCCESS = 0

# .claude/ runtime state 必要 gitignore 名稱直接 derive 自 sync manifest 的
# GITIGNORE_EXPECTED（SOT），消除「manifest vs 本 hook 各維護一份」的雙 SOT 漂移
# （TASK_AVOIDANCE_FIX_MODE 曾只進本 hook REQUIRED 未進 manifest，即此漂移的實例）。
# 格式：每個裸名加 `.claude/` 前綴，不加目錄尾斜線——check_missing_entries 以正規化
# 裸名比對，`.claude/state` 與 `.claude/state/` 等價，且無斜線版為更寬鬆的合法規則。
_MANIFEST_REQUIRED = frozenset(f".claude/{name}" for name in GITIGNORE_EXPECTED)

# 非 .claude/ 範疇、不屬 sync manifest 的本機產物（專案根層測試覆蓋率報告）。
# 不在 manifest 內故顯式補入，與 derive 來源分離標示。
_EXTRA_REQUIRED = frozenset({"coverage/"})

REQUIRED_GITIGNORE_ENTRIES = _MANIFEST_REQUIRED | _EXTRA_REQUIRED

# 偵測「應 ignore 但已被 git tracked」的純 runtime state（前綴/精確匹配 git ls-files）。
#
# [刻意不 derive 自 GITIGNORE_EXPECTED] manifest 的 sync 排除集是「禁止 git track」的
# 超集：analyses/ migration-backups/ plans/ .version-release.yaml 雖排除 sync，卻在
# 專案 repo 內正常 tracked（專案產物 / 歷史）。若由完整 GITIGNORE_EXPECTED derive，
# 會把這些合法 tracked 檔誤報為「應 ignore 卻被 track」（實測 91 個 false positive）。
# 故本清單為 manifest 的真子集，只列「既不 sync 也絕不該 track」的純 runtime state，
# 與 REQUIRED_GITIGNORE_ENTRIES 是不同概念，刻意手動維護。
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


def _normalize_ignore_token(token: str) -> str:
    """正規化 gitignore 行 / required entry 為可比對裸名。

    去前導 `.claude/` 或 `/`、去 `**/` 前綴、去尾隨 `/`，使
    `.claude/state/`、`state/`、`**/state/`、`.claude/state` 視為等價，
    自動涵蓋舊 EQUIVALENT_PATTERNS 的 logs/ hook-logs/ 寬鬆比對。
    """
    t = token.strip()
    if t.startswith(".claude/"):
        t = t[len(".claude/"):]
    elif t.startswith("/"):
        t = t[1:]
    if t.startswith("**/"):
        t = t[len("**/"):]
    return t.rstrip("/")


def check_missing_entries(gitignore_entries: Set[str], logger) -> List[str]:
    """對 REQUIRED 逐項檢查；正規化後仍未覆蓋 → 加入缺失清單。

    比對採正規化裸名（_normalize_ignore_token），故 .gitignore 用
    `.claude/state/`、`state/`、`**/state/` 任一形式皆視為覆蓋；
    額外保留 `*.lock` 萬用字元等效（normalize 無法收斂 glob）。
    """
    normalized = {_normalize_ignore_token(e) for e in gitignore_entries}
    has_lock_wildcard = "*.lock" in gitignore_entries
    missing: List[str] = []
    for required in sorted(REQUIRED_GITIGNORE_ENTRIES):
        norm = _normalize_ignore_token(required)
        if norm in normalized:
            continue
        if norm.endswith(".lock") and has_lock_wildcard:
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
