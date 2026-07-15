#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""
UC Reference Validation Hook - PreToolUse Hook

功能：
  Write/Edit/MultiEdit 目標為程式碼檔（.dart/.js/.ts/.py）時，掃描新增內容中的
  UC-XX token，比對 docs/app-use-cases.md 動態解析的白名單（SSOT），
  命中未定義編號時輸出 stderr WARNING（含合法清單提示）。

  首版為 WARNING-only（業界調研 + WRAP 決策修訂定案）：一律 exit 0 放行，
  不 deny。是否升級為 deny 由後續觀察期票評估。

  白名單解析、豁免判定複用 doc_system.core.uc_registry（uc CLI 交付的
  共用模組），避免 hook 與 doc uc CLI 各自實作導致規則漂移。規則來源：
  docs/spec/uc-numbering-convention.md。

攔截邊界（寫入端防線非全覆蓋，已知邊界如下）：
  - MultiEdit：已涵蓋——聚合 edits[] 各項 new_string 逐一掃描（見
    `_extract_new_text`）。
  - NotebookEdit：暫豁免不掃描。本專案（Flutter/Dart）無 .ipynb 檔案，
    ScannableExtensions 亦不含 notebook 副檔名，評估結論為低風險暫緩；
    若未來引入 notebook 工作流，須另開票補上此分支。
  - Bash heredoc / here-string 寫入（如 `cat > file.dart <<EOF`）：
    不受本 hook 攔截。PreToolUse 僅能匹配工具名稱（Write/Edit/MultiEdit），
    無法解析 Bash 命令內部產生的檔案寫入語意，屬平台層限制，非本 hook
    可修復範圍。此邊界對應 UC 治理規範 §2.2（四項禁止的寫入端防線，已知殘留缺口）。

Hook 類型：PreToolUse
匹配工具：Edit, Write, MultiEdit
退出碼：一律 0（WARNING-only，不阻擋）
"""

import sys
from pathlib import Path

_HOOKS_DIR = Path(__file__).resolve().parent
_CLAUDE_DIR = _HOOKS_DIR.parent
_DOC_SKILL_DIR = _CLAUDE_DIR / "skills" / "doc"

sys.path.insert(0, str(_CLAUDE_DIR))  # for `from lib import ...`
sys.path.insert(0, str(_DOC_SKILL_DIR))  # for `from doc_system.core.uc_registry import ...`

from lib import (  # noqa: E402
    setup_hook_logging,
    run_hook_safely,
    read_json_from_stdin,
    extract_tool_input,
    get_project_root,
)

WARNING_TEMPLATE = """[uc-reference-validation] 偵測到未定義的 UC 編號：{tokens}

檔案：{file_path}
規則來源：docs/spec/uc-numbering-convention.md

合法 UC 編號清單：
{valid_list}

若為新用例，請先於 docs/app-use-cases.md 新增對應標題行（## UC-XX: 標題）後再引用；
若為設計模式標註，改用非 UC- 前綴命名空間（見規範第 4 節子流程表達）。
本提示為首版 WARNING-only，不阻擋本次操作。
"""


def _extract_new_text(tool_name: str, tool_input: dict) -> str:
    """取出 Write/Edit/MultiEdit 新增的文字內容。

    Write 用 content，Edit 用 new_string，MultiEdit 聚合 edits[] 各項
    new_string（換行串接後整體掃描，任一段落含未定義 UC token 即觸發）。
    """
    if tool_name == "Write":
        return tool_input.get("content") or ""
    if tool_name == "Edit":
        return tool_input.get("new_string") or ""
    if tool_name == "MultiEdit":
        edits = tool_input.get("edits") or []
        return "\n".join(edit.get("new_string") or "" for edit in edits)
    return ""


def _format_valid_list(valid: dict) -> str:
    """格式化合法 UC 清單供 WARNING 訊息顯示。"""
    if not valid:
        return "  （SSOT 未解析出任何合法 UC，請確認 docs/app-use-cases.md 存在）"
    return "\n".join(f"  {uc_id}: {title}" for uc_id, title in sorted(valid.items()))


def main() -> int:
    """Hook 主邏輯。"""
    logger = setup_hook_logging("uc-reference-validation")

    try:
        from doc_system.core.uc_registry import (
            HOOK_SCANNABLE_EXTENSIONS,
            find_uc_tokens_in_text,
            get_valid_uc_map,
            is_exempt_path,
            is_violation_token,
            normalize_token,
        )
    except ImportError as exc:
        # fail-open：共用模組不可用時不可阻擋一般 Write/Edit 操作
        # （quality-baseline 規則 4：異常必須 stderr + 日誌雙通道可見）
        message = f"[uc-reference-validation-hook] uc_registry 模組載入失敗，本次跳過驗證：{exc}"
        sys.stderr.write(message + "\n")
        logger.warning(message)
        return 0

    input_data = read_json_from_stdin(logger)
    if not input_data:
        return 0

    tool_name = input_data.get("tool_name", "")
    if tool_name not in ("Write", "Edit", "MultiEdit"):
        return 0

    tool_input = extract_tool_input(input_data, logger)
    file_path = tool_input.get("file_path", "")
    if not file_path or not file_path.lower().endswith(HOOK_SCANNABLE_EXTENSIONS):
        return 0

    project_root = str(get_project_root())

    if is_exempt_path(file_path, project_root):
        logger.debug("路徑豁免，跳過驗證：%s", file_path)
        return 0

    new_text = _extract_new_text(tool_name, tool_input)
    if not new_text:
        return 0

    tokens = find_uc_tokens_in_text(new_text)
    if not tokens:
        return 0

    valid = get_valid_uc_map(project_root)
    violations = sorted(
        {normalize_token(token) for token, _lineno in tokens if is_violation_token(token, valid)}
    )
    if not violations:
        logger.info("通過：%s 新增內容 UC token 皆合法或豁免", file_path)
        return 0

    message = WARNING_TEMPLATE.format(
        tokens=", ".join(violations),
        file_path=file_path,
        valid_list=_format_valid_list(valid),
    )
    sys.stderr.write(message)
    logger.warning("WARNING：%s 含未定義 UC token：%s", file_path, violations)
    return 0


if __name__ == "__main__":
    sys.exit(run_hook_safely(main, "uc-reference-validation"))
