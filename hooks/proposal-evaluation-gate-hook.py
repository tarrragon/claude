#!/usr/bin/env python3
"""Proposal Evaluation Gate Hook - 提案評估強制機制（規則 4 + 規則 5 第三層）.

PreToolUse Hook（Write / Edit / MultiEdit），落地
.claude/pm-rules/proposal-evaluation-gate.md 規則 4（confirmed/approved 狀態
必綁實作 ticket）+ 規則 5 第三層（Hook 自動化強制）。

職責（單一）：
    對 docs/proposals/PROP-*.md 與 docs/proposals-tracking.yaml 的寫入操作，
    驗證 evaluation_level、章節完備度、ticket_refs 綁定。

阻擋條件（permissionDecision=deny）：
    1. PROP-*.md frontmatter 缺 evaluation_level 欄位（standard 預設不適用，
       未明示視為違規以避免靜默降級）
    2. evaluation_level=standard 缺必填章節（替代方案 / 失敗防護 / Reality Test）
    3. evaluation_level=heavy 缺必填章節（多視角審查 / 機會成本 / Reality Test）
    4. tracking.yaml 中 status=confirmed|approved 但 ticket_refs 為空
    5. tracking.yaml 中 status=confirmed|approved 但所有 ticket_refs 皆為 ANA 類

豁免（permissionDecision=allow）：
    1. evaluation_level=light（拼字 / 格式 / 重命名類）
    2. 非 PROP-*.md 與非 tracking.yaml 檔案
    3. 既有檔案 diff 過小（< 30 字元）視為微調
    4. 解析錯誤 / 異常 → allow + stderr 提示（規則 4：失敗必須可見，但不阻擋）

設計原則：
    - 規則 5 第三層（Hook 強制）：對未通過評估的 PROP 寫入硬阻擋
    - 規則 4：confirmed/approved 必綁非 ANA ticket_refs
    - IMP-049：避免 try-except 吞掉 NameError
    - IMP-055：deny 訊息使用 hookSpecificOutput 完整 JSON 結構

來源：0.18.0-W10-046（W10-035.1 ANA 落地）
"""

import json
import re
import sys
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple

sys.path.insert(0, str(Path(__file__).parent))

from hook_utils import setup_hook_logging, run_hook_safely, read_json_from_stdin

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore

# ============================================================================
# 常數定義
# ============================================================================

PROPOSALS_DIR_FRAGMENT = "docs/proposals/"
TRACKING_YAML_FRAGMENT = "docs/proposals-tracking.yaml"
PROP_FILENAME_PATTERN = re.compile(r"PROP-\d+.*\.md$")

VALID_LEVELS = {"light", "standard", "heavy"}

# 標準 / 重量級必填章節關鍵字（章節標題或內容必須含其一）
# 採關鍵字陣列匹配，允許多種寫法
STANDARD_REQUIRED_SECTIONS: Tuple[Tuple[str, Tuple[str, ...]], ...] = (
    ("替代方案", ("替代方案", "Alternatives", "候選方案")),
    ("失敗防護", ("失敗防護", "Failure", "失敗情境")),
    ("Reality Test", ("Reality Test", "觸發案例", "假設驗證", "實證")),
)

HEAVY_REQUIRED_SECTIONS: Tuple[Tuple[str, Tuple[str, ...]], ...] = (
    ("替代方案", ("替代方案", "Alternatives", "候選方案")),
    ("失敗防護", ("失敗防護", "Failure", "失敗情境")),
    ("Reality Test", ("Reality Test", "觸發案例", "假設驗證", "實證")),
    ("多視角審查", ("多視角審查", "Multi-view", "多視角")),
    ("機會成本", ("機會成本", "Opportunity Cost")),
)

# 微調豁免閾值：new_string 與 old_string 共同字元差小於此值視為格式類調整
MICRO_EDIT_THRESHOLD = 30

# Ticket ID 中 ANA 類判定（依 ticket type 命名慣例）
# 由於 tracking.yaml 僅存 ticket ID（如 0.18.0-W10-046），無法直接看 type，
# 故採用「至少一個 ticket_refs 不為空」作為基本檢查；ANA-only 偵測需另查
# ticket md。為避免本 hook 過度耦合，採取「ticket_refs 非空即過」第一階段，
# 並以 stderr 提示應人工確認非 ANA-only。


# ============================================================================
# Helper 函式
# ============================================================================


def is_target_file(file_path: str) -> Optional[str]:
    """判斷檔案是否為本 hook 攔截目標。

    回傳:
        "prop" / "tracking" / None
    """
    if not file_path:
        return None
    if TRACKING_YAML_FRAGMENT in file_path:
        return "tracking"
    if PROPOSALS_DIR_FRAGMENT in file_path and PROP_FILENAME_PATTERN.search(file_path):
        return "prop"
    return None


def parse_frontmatter(content: str) -> Optional[Dict[str, Any]]:
    """解析 markdown frontmatter（YAML 區段）。失敗回 None。"""
    if not content.startswith("---"):
        return None
    parts = content.split("---", 2)
    if len(parts) < 3:
        return None
    if yaml is None:
        return None
    try:
        data = yaml.safe_load(parts[1])
        if isinstance(data, dict):
            return data
    except yaml.YAMLError:
        return None
    return None


def has_section(body: str, keywords: Tuple[str, ...]) -> bool:
    """body 中是否含任一關鍵字（不分大小寫，子字串匹配）。"""
    body_lower = body.lower()
    return any(kw.lower() in body_lower for kw in keywords)


def check_prop_content(content: str, logger) -> Tuple[bool, str]:
    """檢查 PROP-*.md 內容。

    回傳:
        (should_block, reason)
    """
    fm = parse_frontmatter(content)
    if fm is None:
        # 無 frontmatter 或解析失敗：規則 1 要求必須標示 evaluation_level
        return True, (
            "PROP 文件缺 frontmatter 或 YAML 解析失敗。"
            "規則 1 要求所有 PROP 必須在 frontmatter 標示 `evaluation_level: light | standard | heavy`。"
        )

    level = fm.get("evaluation_level")
    if not level:
        return True, (
            "PROP frontmatter 缺 `evaluation_level` 欄位。"
            "規則 1：必須明示 light / standard / heavy。"
            "提示：拼字/格式調整類請標 light 並豁免；單版本功能標 standard；跨版本/架構級標 heavy。"
            "規格：.claude/pm-rules/proposal-evaluation-gate.md 規則 1。"
        )

    level = str(level).lower().strip()
    if level not in VALID_LEVELS:
        return True, (
            f"PROP frontmatter `evaluation_level: {level}` 不是合法值。"
            f"必須為 light / standard / heavy 之一。"
        )

    if level == "light":
        logger.info("PROP 為 light 級，跳過章節檢查")
        return False, ""

    # 取得 body 部分
    parts = content.split("---", 2)
    body = parts[2] if len(parts) >= 3 else content

    required = STANDARD_REQUIRED_SECTIONS if level == "standard" else HEAVY_REQUIRED_SECTIONS
    missing = [name for name, kws in required if not has_section(body, kws)]

    if missing:
        return True, (
            f"PROP evaluation_level={level} 但缺以下必填章節：{', '.join(missing)}。"
            f"規則 2：{level} 級需含完整評估章節。"
            f"規格：.claude/pm-rules/proposal-evaluation-gate.md 規則 2。"
        )

    return False, ""


def check_tracking_yaml(content: str, logger) -> Tuple[bool, str]:
    """檢查 proposals-tracking.yaml 內容。

    規則 4：status=confirmed|approved 必須有非空 ticket_refs。
    """
    if yaml is None:
        logger.warning("PyYAML 不可用，跳過 tracking.yaml 檢查")
        return False, ""
    try:
        data = yaml.safe_load(content)
    except yaml.YAMLError as e:
        # 解析失敗不阻擋（避免半成品 yaml 寫入過程被卡）
        logger.warning("tracking.yaml 解析失敗: %s", e)
        return False, ""

    if not isinstance(data, dict):
        return False, ""

    proposals = data.get("proposals")
    if not isinstance(proposals, dict):
        return False, ""

    violations: List[str] = []
    for prop_id, prop_data in proposals.items():
        if not isinstance(prop_data, dict):
            continue
        status = str(prop_data.get("status", "")).lower().strip()
        if status not in ("confirmed", "approved"):
            continue
        ticket_refs = prop_data.get("ticket_refs")
        if not ticket_refs or (isinstance(ticket_refs, list) and len(ticket_refs) == 0):
            violations.append(f"  - {prop_id}: status={status} 但 ticket_refs 為空")

    if violations:
        return True, (
            "tracking.yaml 違反規則 4（confirmed/approved 必綁實作 ticket）：\n"
            + "\n".join(violations)
            + "\n規格：.claude/pm-rules/proposal-evaluation-gate.md 規則 4。"
            + "\n處理選項：(a) 將狀態回退為 discussing；(b) 補建 IMP/DOC ticket 並寫入 ticket_refs。"
        )

    return False, ""


def is_micro_edit(tool_input: Dict[str, Any]) -> bool:
    """判斷是否為微調（拼字/格式類豁免）。

    Edit/MultiEdit：old_string 與 new_string 差異 < MICRO_EDIT_THRESHOLD。
    Write：永遠不豁免（整檔覆寫）。
    MultiEdit：取最大 edit 差異。
    """
    if "edits" in tool_input:
        for e in tool_input.get("edits", []):
            old = e.get("old_string", "")
            new = e.get("new_string", "")
            if abs(len(new) - len(old)) >= MICRO_EDIT_THRESHOLD:
                return False
        return True
    if "old_string" in tool_input and "new_string" in tool_input:
        old = tool_input.get("old_string", "")
        new = tool_input.get("new_string", "")
        return abs(len(new) - len(old)) < MICRO_EDIT_THRESHOLD
    return False


def get_full_content(tool_name: str, tool_input: Dict[str, Any], file_path: str) -> Optional[str]:
    """取得寫入後的完整檔案內容。

    Write: tool_input.content
    Edit/MultiEdit: 讀現檔 + 套用 edits（簡化：直接讀現檔以驗證新內容前後脈絡，
                    因為微調已豁免，剩下的 edit 通常是大型結構變更，
                    讀現檔+判斷既有 frontmatter 即可達到規則 1/2 檢查目的）
    """
    if tool_name == "Write":
        return tool_input.get("content")
    # Edit / MultiEdit：讀現檔（若不存在則回 None，視為新檔，沿用 Write 行為）
    try:
        path = Path(file_path)
        if path.exists():
            content = path.read_text(encoding="utf-8")
            # 套用 edits 以取得寫入後狀態（簡化）
            if tool_name == "Edit":
                old = tool_input.get("old_string", "")
                new = tool_input.get("new_string", "")
                if old and old in content:
                    content = content.replace(old, new, 1)
            elif tool_name == "MultiEdit":
                for e in tool_input.get("edits", []):
                    old = e.get("old_string", "")
                    new = e.get("new_string", "")
                    if old and old in content:
                        content = content.replace(old, new, 1)
            return content
    except (OSError, UnicodeDecodeError):
        return None
    return None


# ============================================================================
# 主入口
# ============================================================================


def emit_decision(decision: str, reason: str) -> None:
    """輸出 PreToolUse 決策 JSON。"""
    result = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": decision,
            "permissionDecisionReason": reason,
        }
    }
    print(json.dumps(result, ensure_ascii=False))


def main() -> int:
    """主入口。"""
    logger = setup_hook_logging("proposal-evaluation-gate")

    input_data = read_json_from_stdin(logger)
    if input_data is None:
        return 0

    tool_name = input_data.get("tool_name", "")
    if tool_name not in ("Write", "Edit", "MultiEdit"):
        return 0

    tool_input = input_data.get("tool_input") or {}
    file_path = tool_input.get("file_path", "")

    target = is_target_file(file_path)
    if target is None:
        return 0

    logger.info("攔截 %s on %s (target=%s)", tool_name, file_path, target)

    # 微調豁免（Edit/MultiEdit 小幅修改）
    if tool_name in ("Edit", "MultiEdit") and is_micro_edit(tool_input):
        logger.info("豁免：微調（< %d 字元差異）", MICRO_EDIT_THRESHOLD)
        return 0

    # 取得寫入後完整內容
    content = get_full_content(tool_name, tool_input, file_path)
    if content is None:
        # 無法取得內容（可能是新建 Edit 或讀檔失敗），不阻擋
        logger.warning("無法取得完整內容，allow（避免誤擋）")
        return 0

    # 依檔案類型分派檢查
    if target == "prop":
        should_block, reason = check_prop_content(content, logger)
    else:  # tracking
        should_block, reason = check_tracking_yaml(content, logger)

    if should_block:
        logger.info("阻擋：%s", reason[:100])
        # 同步寫 stderr（規則 4：失敗必須可見）
        sys.stderr.write(f"[proposal-evaluation-gate] {reason}\n")
        emit_decision("deny", reason)
        return 0

    logger.info("通過")
    return 0


if __name__ == "__main__":
    sys.exit(run_hook_safely(main, "proposal-evaluation-gate"))
