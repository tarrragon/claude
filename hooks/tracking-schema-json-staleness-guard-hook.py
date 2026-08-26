#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///

"""tracking-schema-json-staleness-guard-hook.py — 阻擋 tracking_schema.py 語意
改動而 tracking_schema.json 未同步重產的 commit。

背景：tracking_schema.json 隨框架同步供外部 app 消費。JSON 產生器僅在有人
手動跑 doc skill 測試時執行雙向一致性驗證，不隨每次 commit 自動觸發，故
.py 改動但 JSON 未重產的狀態可存活至下一次測試執行為止；期間若發生
sync-push，過期 JSON 會傳播至全部 consumer 且消費端無從察覺。

裁決（method B / 阻擋）：
  - 偵測方式：內容比對（呼叫 `doc schema export --json` 取得依當前
    tracking_schema.py 應產出的內容，與磁碟 tracking_schema.json 比對），
    非檔案存在性檢查。純註解改動不影響 build_schema_dict() 輸出，不觸發，
    避免存在性檢查對純註解改動誤報（要求重產零 diff 的 JSON）。
  - 阻擋層級：exit 2 硬擋 commit。過期 JSON 的受害者在專案外
    （他專案的 app 使用者）且無偵測手段，危害高於一般文件不同步提示情境，
    故採阻擋而非 INFO 提示。

隔離執行環境防護：本 hook **不** import doc_system（避免隔離 venv 下的
import 鏈失效風險）。改以 subprocess 呼叫 `uv run --project
.claude/skills/doc doc schema export --json`——這正是使用者產生 JSON 的
生產路徑本身，非 in-process import 捷徑，故無法有「測試環境有生產環境沒有
的依賴」這種落差可乘（呼叫方與被呼叫方在同一個 uv 隔離環境下執行）。

觸發時機: PreToolUse Bash matcher（git commit 執行前）
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

from lib import setup_hook_logging, run_hook_safely, read_json_from_stdin, get_project_root


SCHEMA_PY_REL_PATH = ".claude/skills/doc/doc_system/core/tracking_schema.py"
SCHEMA_JSON_REL_PATH = ".claude/skills/doc/doc_system/core/tracking_schema.json"
DOC_SKILL_PROJECT_DIR = ".claude/skills/doc"

# 此鍵記錄「產生當下讀到的 .claude/VERSION」，其 bump 時機在 sync-push、晚於
# schema 產生與 commit（見 schema.py docstring）。同一份 tracking_schema.py
# 在兩次不同時間點產生 JSON，此鍵值可能因 VERSION 已變動而不同，屬與
# schema.py 內容無關的正常波動，比對時必須排除，否則會對「schema.py 完全
# 未改動」的 commit 產生誤報。
VOLATILE_KEYS = frozenset({"schema_generated_at_framework_version"})


def _strip_volatile_keys(schema: dict) -> dict:
    return {k: v for k, v in schema.items() if k not in VOLATILE_KEYS}


def is_commit_command(command: str) -> bool:
    """判斷是否為 git commit 命令（排除唯讀/amend 變體）。"""
    if "git commit" not in command:
        return False
    for excluded in ("git commit --amend", "git log", "git show", "git diff"):
        if excluded in command:
            return False
    return True


def get_staged_files(project_root: Path, logger) -> list:
    """取得目前已 staged 的檔案清單（`git diff --cached --name-only`）。"""
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            cwd=str(project_root),
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            logger.warning("git diff --cached 非零退出: %s", result.stderr.strip())
            return []
        return [line.strip() for line in result.stdout.splitlines() if line.strip()]
    except Exception as e:
        logger.warning("取得 staged files 失敗: %s", e)
        return []


def compute_expected_schema(project_root: Path, logger) -> Optional[dict]:
    """以生產路徑（`uv run --project .../doc doc schema export --json`）
    取得依當前 tracking_schema.py 應產出的內容。

    回傳 None 代表呼叫失敗（環境問題），此時 hook 必須 fail-open 並記錄
    明確日誌（禁止靜默 fail-open）。
    """
    try:
        result = subprocess.run(
            ["uv", "run", "--project", DOC_SKILL_PROJECT_DIR, "doc", "schema", "export", "--json"],
            cwd=str(project_root),
            capture_output=True,
            text=True,
            timeout=30,
        )
    except Exception as e:
        logger.warning("呼叫 doc schema export --json 失敗（fail-open）: %s", e)
        return None

    if result.returncode != 0:
        logger.warning(
            "doc schema export --json 非零退出（fail-open）: %s", result.stderr.strip()
        )
        return None

    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as e:
        logger.warning("doc schema export --json 輸出非合法 JSON（fail-open）: %s", e)
        return None


def load_disk_schema(project_root: Path, logger) -> Optional[dict]:
    """讀取磁碟上現有的 tracking_schema.json。"""
    path = project_root / SCHEMA_JSON_REL_PATH
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        logger.info("tracking_schema.json 不存在")
        return None
    except json.JSONDecodeError as e:
        logger.warning("磁碟 tracking_schema.json 非合法 JSON: %s", e)
        return None


def main() -> int:
    logger = setup_hook_logging("tracking-schema-json-staleness-guard-hook")

    input_data = read_json_from_stdin(logger)
    if input_data is None:
        return 0

    if input_data.get("tool_name", "") != "Bash":
        logger.debug("跳過: 非 Bash 工具")
        return 0

    tool_input = input_data.get("tool_input") or {}
    command = tool_input.get("command", "")
    if not is_commit_command(command):
        logger.debug("跳過: 非 git commit 命令")
        return 0

    project_root = get_project_root()

    staged_files = get_staged_files(project_root, logger)
    if SCHEMA_PY_REL_PATH not in staged_files:
        logger.debug("跳過: 本次 commit 未改動 %s", SCHEMA_PY_REL_PATH)
        return 0

    expected = compute_expected_schema(project_root, logger)
    if expected is None:
        # fail-open：無法取得預期內容時不阻擋，但日誌已記錄具體原因（見上）
        logger.warning("無法計算預期 schema，本次 fail-open 放行")
        return 0

    actual = load_disk_schema(project_root, logger)

    if actual is not None and _strip_volatile_keys(actual) == _strip_volatile_keys(expected):
        logger.debug("tracking_schema.json 與 tracking_schema.py 內容一致，放行")
        return 0

    reason = "tracking_schema.json 不存在" if actual is None else "內容與 tracking_schema.py 不一致"
    msg = (
        "[tracking-schema-json-staleness-guard] tracking_schema.json 過期\n\n"
        f"本次 commit 改動了 {SCHEMA_PY_REL_PATH}，但 {SCHEMA_JSON_REL_PATH} "
        f"{reason}。\n\n"
        "過期的 JSON 會隨下次 sync-push 傳播至所有消費該 schema 的外部專案，"
        "且消費端無從察覺。\n\n"
        "請先執行以下指令重新產生後再 commit：\n"
        f"  uv run --project {DOC_SKILL_PROJECT_DIR} doc schema export\n"
    )
    print(msg, file=sys.stderr)
    logger.info("阻擋 commit：tracking_schema.json 過期（%s）", reason)
    return 2


if __name__ == "__main__":
    sys.exit(run_hook_safely(main, "tracking-schema-json-staleness-guard-hook"))
