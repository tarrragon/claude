#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# ///

"""
Variable Count Literal Guard Hook - PostToolUse Bash Matcher

職責: 偵測 git commit 成功後，新增行中出現「規則 10：可變計數不實例化」
      （.claude/references/reference-stability-rules.md）定義的可變計數字面
      （欄位數、檔數、條數等），限掃描規則/方法論/skill 文件，INFO 級提示、
      不阻擋 commit。

背景: 規則 10 已定義偵測 pattern 與例外表，但僅供人工於權威表增減成員時
      手動掃描，缺 commit-level 提示層。已有多次同型實證：權威集合（表格
      列數、目錄檔數）增減後，文件中先前寫死的計數字面全數靜默失效，且
      每句字面完好、連結有效，人工對帳無法及時發現。本 hook 為 INFO 級
      （不阻擋）——規則 10 例外表（凍結承諾數字、實測記錄）尚新，阻擋級
      會把合法計數擋下，先在提示層累積案例觀察誤報率，是否升級為
      WARNING/阻擋另行評估。

觸發時機: PostToolUse Bash matcher（git commit 成功後）

掃描範圍: .claude/rules/、.claude/references/、.claude/methodologies/、
          .claude/skills/*/SKILL.md（僅本次 commit 新增的行，非全檔）

偵測 pattern（規則 10 原文）:
  [一二三四五六七八九十0-9]+(欄位|檔|條|項|類|步)

例外過濾（規則 10 例外表，逐行啟發式判斷，非完美但降低明顯誤報）:
  - 變更歷史 / footer 版本行（Version**: / Last Updated / 變更歷史 標記）
  - 規則編號本身（如「規則 10」「PC-050」等識別符，非集合大小敘述）
  - 版本號（x.y.z 形式）
  - 量測記錄標記（「量測環境」「實測」等時點標注）

設計骨架參考: skill-cli-sync-check-hook.py（PostToolUse Bash matcher +
      git show 取 commit file list 的既有模式）

行為: 不阻擋（exit 0），僅在 additionalContext 輸出 INFO 提示
"""

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import List, Tuple

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib import (
    setup_hook_logging,
    run_hook_safely,
    read_json_from_stdin,
    get_project_root,
    is_subagent_environment,
)


# ============================================================================
# 常數定義
# ============================================================================

EXIT_SUCCESS = 0

EXCLUDED_COMMAND_PATTERNS = [
    "git log",
    "git show",
    "git diff",
    "git status",
    "git commit --amend",
]

COMMIT_SUCCESS_MARKERS = [
    "files changed",
    "file changed",
    "insertions(+)",
    "deletions(-)",
    "create mode",
]

# 掃描範圍前綴（規則 10「適用情境」表：rules/references/methodologies）
SCOPE_DIR_PREFIXES = (
    ".claude/rules/",
    ".claude/references/",
    ".claude/methodologies/",
)

# skills/*/SKILL.md 樣式（單獨判定，非目錄前綴）
SKILL_MD_PATTERN = re.compile(r"^\.claude/skills/[^/]+/SKILL\.md$")

# 規則 10 偵測 pattern（字元類別逐字沿用原文，補 \s* 容許數字與單位間的排版空格
# ——中文排版常於阿拉伯數字與後接漢字間插入半形空格，如「714 檔」「1607 個」）
COUNT_LITERAL_PATTERN = re.compile(
    r"[一二三四五六七八九十0-9]+\s*(欄位|檔|條|項|類|步)"
)

# 例外過濾：命中即視為豁免，不列入 INFO 提示
EXEMPTION_MARKERS = (
    "變更歷史",
    "Version**:",
    "Last Updated",
    "量測環境",
    "實測",
)

# 版本號樣式（x.y.z 或 x.y），常伴隨計數字元類別誤觸發（如 "3 條" 中的數字
# 若恰好出現在版本號附近）；此處只豁免整行為版本號宣告的情況
VERSION_NUMBER_LINE_PATTERN = re.compile(r"\bv?\d+\.\d+(\.\d+)?\b")

# 規則編號 / error-pattern 識別符樣式（凍結承諾的數字，規則 10 例外表第一類）
RULE_NUMBER_PATTERN = re.compile(r"規則\s*\d+|PC-\d+|IMP-\d+|ARCH-\d+|DOC-[A-Z0-9-]+\d")

# 本 hook 自身路徑（meta 自我引用豁免）
META_SELF_PATH = ".claude/hooks/variable-count-literal-guard-hook.py"

DEFAULT_OUTPUT = {
    "hookSpecificOutput": {
        "hookEventName": "PostToolUse"
    }
}


# ============================================================================
# 判斷邏輯
# ============================================================================


def is_git_commit_command(command: str) -> bool:
    """判斷是否為 git commit 命令（排除 read-only / amend 變體）"""
    if "git commit" not in command:
        return False
    for excluded in EXCLUDED_COMMAND_PATTERNS:
        if excluded in command:
            return False
    return True


def is_commit_successful(stdout: str) -> bool:
    """判斷 commit 是否成功（檢查 git output 標記）"""
    for marker in COMMIT_SUCCESS_MARKERS:
        if marker in stdout:
            return True
    return False


def extract_commit_type(command: str) -> str:
    """從 git commit 命令提取 conventional commit type（供未來擴充；本 hook 目前不依此過濾）"""
    match = re.search(r'-m\s+["\']([a-z]+)(?:\([^)]*\))?:', command)
    if match:
        return match.group(1).lower()
    match = re.search(r'\n\s*([a-z]+)(?:\([^)]*\))?:', command)
    if match:
        return match.group(1).lower()
    return ""


def is_in_scope(file_path: str) -> bool:
    """判斷檔案是否落在規則 10 適用情境的掃描範圍內"""
    if file_path.startswith(SCOPE_DIR_PREFIXES):
        return True
    return bool(SKILL_MD_PATTERN.match(file_path))


def get_commit_files(project_root: Path, logger) -> List[str]:
    """執行 git show --name-only HEAD 取得 commit file list"""
    try:
        result = subprocess.run(
            ["git", "show", "--name-only", "--pretty=format:", "HEAD"],
            cwd=str(project_root),
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            logger.debug("git show 非零退出: %s", result.stderr.strip())
            return []
        return [line.strip() for line in result.stdout.splitlines() if line.strip()]
    except Exception as e:
        logger.warning("取得 commit file list 失敗: %s", e)
        return []


def get_added_lines(project_root: Path, file_path: str, logger) -> List[Tuple[int, str]]:
    """
    取得單一檔案於 HEAD 這次 commit 新增的行（含新檔行號）。

    Returns:
        list[(line_number, line_content)] - 僅含新增行（diff 中以單一 '+' 開頭，
        排除 '+++' 檔頭），失敗時回傳空 list。
    """
    try:
        result = subprocess.run(
            ["git", "show", "--unified=0", "--pretty=format:", "HEAD", "--", file_path],
            cwd=str(project_root),
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            logger.debug("git show diff 非零退出 (%s): %s", file_path, result.stderr.strip())
            return []
    except Exception as e:
        logger.warning("取得 %s 的新增行失敗: %s", file_path, e)
        return []

    added: List[Tuple[int, str]] = []
    current_new_line = 0
    hunk_header = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@")

    for raw_line in result.stdout.splitlines():
        hunk_match = hunk_header.match(raw_line)
        if hunk_match:
            current_new_line = int(hunk_match.group(1))
            continue
        if raw_line.startswith("+++") or raw_line.startswith("---"):
            continue
        if raw_line.startswith("+"):
            added.append((current_new_line, raw_line[1:]))
            current_new_line += 1
        elif raw_line.startswith("-"):
            # 刪除行不佔用新檔行號，略過計數推進
            continue
        else:
            # 非 +/- 的 context 行（--unified=0 理論上不應出現，防禦性處理）
            current_new_line += 1

    return added


def is_exempt_line(line: str) -> bool:
    """
    判斷該行是否落入規則 10 例外表（凍結承諾數字 / 實測記錄 / 版本行等）。

    啟發式判斷，非完美分類——INFO 級提示允許漏放行（false negative），
    但應盡量降低把合法計數判為違規的 false positive。
    """
    for marker in EXEMPTION_MARKERS:
        if marker in line:
            return True
    if RULE_NUMBER_PATTERN.search(line):
        return True
    if VERSION_NUMBER_LINE_PATTERN.search(line):
        return True
    return False


def scan_line_for_count_literal(line: str) -> bool:
    """對單一新增行套用偵測 pattern + 例外過濾，回傳是否應提示"""
    if not COUNT_LITERAL_PATTERN.search(line):
        return False
    if is_exempt_line(line):
        return False
    return True


def collect_findings(
    project_root: Path, files: List[str], logger
) -> List[Tuple[str, int, str]]:
    """
    對範圍內每個檔案的新增行掃描可變計數字面。

    Returns:
        list[(file_path, line_number, line_content)]
    """
    findings: List[Tuple[str, int, str]] = []
    scope_files = [f for f in files if is_in_scope(f)]
    for file_path in scope_files:
        for line_number, content in get_added_lines(project_root, file_path, logger):
            if scan_line_for_count_literal(content):
                findings.append((file_path, line_number, content.strip()))
    return findings


def build_reminder(findings: List[Tuple[str, int, str]]) -> str:
    """組裝 INFO 提示訊息"""
    lines = [
        "=" * 60,
        "[INFO] 可變計數字面偵測（規則 10：可變計數不實例化）",
        "=" * 60,
        "",
        "以下新增行疑似對一個會演進的集合大小做了字面實例化",
        "（欄位數／檔數／條數等）。判準問句：「這個數字在集合增減",
        "一個成員後還對嗎？」答否即應改引用集合的權威名稱，不寫數字。",
        "",
        "已知例外（不需修改）：凍結承諾的數字（規則編號、schema 版本、",
        "API 常數）與實測記錄（標註量測時點的一次性量測結果）。",
        "",
    ]
    for file_path, line_number, content in findings:
        lines.append(f"  {file_path}:{line_number}: {content}")
    lines.extend([
        "",
        "詳見 .claude/references/reference-stability-rules.md 規則 10。",
        "=" * 60,
    ])
    return "\n".join(lines)


# ============================================================================
# 主入口
# ============================================================================


def main() -> int:
    logger = setup_hook_logging("variable-count-literal-guard-hook")

    input_data = read_json_from_stdin(logger)
    if input_data is None:
        print(json.dumps(DEFAULT_OUTPUT, ensure_ascii=False))
        return EXIT_SUCCESS

    tool_name = input_data.get("tool_name", "")
    if tool_name != "Bash":
        logger.debug("跳過: 工具類型為 %s，非 Bash", tool_name)
        print(json.dumps(DEFAULT_OUTPUT, ensure_ascii=False))
        return EXIT_SUCCESS

    if is_subagent_environment(input_data):
        logger.info(
            "偵測到 subagent 環境（agent_id=%s），跳過可變計數提示",
            input_data.get("agent_id"),
        )
        print(json.dumps(DEFAULT_OUTPUT, ensure_ascii=False))
        return EXIT_SUCCESS

    tool_input = input_data.get("tool_input") or {}
    command = tool_input.get("command", "")

    tool_response = input_data.get("tool_response") or {}
    stdout = tool_response.get("stdout", "")

    if not (is_git_commit_command(command) and is_commit_successful(stdout)):
        logger.debug("非 git commit 成功")
        print(json.dumps(DEFAULT_OUTPUT, ensure_ascii=False))
        return EXIT_SUCCESS

    project_root = get_project_root()
    files = get_commit_files(project_root, logger)
    if not files:
        logger.debug("無法取得 commit file list，跳過")
        print(json.dumps(DEFAULT_OUTPUT, ensure_ascii=False))
        return EXIT_SUCCESS

    if META_SELF_PATH in files:
        logger.info("meta 自我引用豁免：commit 含本 hook 自身路徑改動")
        print(json.dumps(DEFAULT_OUTPUT, ensure_ascii=False))
        return EXIT_SUCCESS

    findings = collect_findings(project_root, files, logger)
    if not findings:
        logger.debug("commit 範圍內無可變計數字面命中")
        print(json.dumps(DEFAULT_OUTPUT, ensure_ascii=False))
        return EXIT_SUCCESS

    logger.info("觸發提醒：%d 處疑似可變計數字面", len(findings))
    reminder = build_reminder(findings)
    output = {
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": reminder,
        }
    }
    print(json.dumps(output, ensure_ascii=False))
    return EXIT_SUCCESS


if __name__ == "__main__":
    sys.exit(run_hook_safely(main, "variable-count-literal-guard-hook"))
