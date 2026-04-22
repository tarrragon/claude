#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///

"""
Session Start Sync Exclusion Check Hook

SessionStart 事件觸發時，掃描 .claude/ 根目錄的 .json/.yaml/.yml 檔案，
若發現不在已知排除清單（KNOWN_EXCLUDED）且非框架設定（framework-config）
的檔案，則輸出 WARNING 提醒加入 sync 排除清單。

設計要點：
- KNOWN_EXCLUDED 硬編碼與 sync-claude-push.py 的 EXCLUDE_PATTERNS 對齊
  （本 Hook 為 uv script dependencies=[]，不引入 import 依賴，選擇硬編副本）
- 偵測到未排除檔案時以 [WARNING] 輸出到 additionalContext；
  無異常時靜默（suppressOutput=True），不干擾正常 session 啟動
- 失敗模式：任何 I/O 或解析異常 → logger 紀錄 + 靜默降級，
  不阻塞 session 啟動（遵循 SessionStart Hook 原則）

適用 Ticket：0.18.0-W17-045.3
來源：W17-045 ANA — 框架新增 runtime state 機制時無 sync 評估強制點的結構性缺口
"""

import json
import sys
from pathlib import Path
from typing import List, Dict, Any

# 加入 hook_utils 路徑
sys.path.insert(0, str(Path(__file__).parent))
from hook_utils import (  # noqa: E402
    setup_hook_logging,
    run_hook_safely,
    read_json_from_stdin,
    get_project_root,
)

EXIT_SUCCESS = 0

# 已知必須排除的 .claude/ 根目錄檔案名稱（與 sync-claude-push.py 對齊）
#
# 類型 A - Runtime state（本 session 執行期狀態）
#   dispatch-active.json, pm-status.json
#
# 類型 B - Local-only settings（各專案個別設定）
#   settings.local.json, .sync-state.json, sync-preserve.yaml
#
# 類型 X - Framework config（正常 sync，不警告）
#   settings.json（框架 Hook 註冊表，跨專案共用）
KNOWN_EXCLUDED = {
    # 類型 A - Runtime state
    "dispatch-active.json",
    "pm-status.json",
    # 類型 B - Local-only settings
    "settings.local.json",
    ".sync-state.json",
    "sync-preserve.yaml",
    # 類型 X - Framework config（需正常 sync，加入此集合代表掃描時略過不警告）
    "settings.json",
}

# 掃描副檔名清單
SCAN_SUFFIXES = {".json", ".yaml", ".yml"}


def scan_unexcluded_files(claude_dir: Path, logger) -> List[str]:
    """掃描 .claude/ 根目錄，回傳不在 KNOWN_EXCLUDED 的 .json/.yaml/.yml 檔案名稱。

    Args:
        claude_dir: .claude/ 目錄路徑
        logger: 日誌物件

    Returns:
        未排除檔案名稱列表（可能為空）；掃描失敗降級回空列表
    """
    if not claude_dir.exists() or not claude_dir.is_dir():
        logger.warning(".claude 目錄不存在或不是目錄: %s", claude_dir)
        return []

    unexcluded: List[str] = []
    try:
        for entry in claude_dir.iterdir():
            if not entry.is_file():
                continue
            if entry.suffix.lower() not in SCAN_SUFFIXES:
                continue
            if entry.name in KNOWN_EXCLUDED:
                continue
            unexcluded.append(entry.name)
    except Exception as e:  # noqa: BLE001 — 掃描失敗降級不阻塞 session
        logger.warning("掃描 .claude/ 根目錄失敗: %s", e)
        return []

    unexcluded.sort()
    logger.info(
        "sync-exclusion-check scan: found %d unexcluded file(s)", len(unexcluded)
    )
    return unexcluded


def build_warning_section(unexcluded: List[str]) -> str:
    """將未排除檔案清單格式化為 markdown 警告區塊。"""
    lines: List[str] = [
        "## Sync 排除清單檢查（sync-exclusion-check）",
        "",
        "偵測到 `.claude/` 根目錄存在未納入 sync 排除清單的檔案。",
        "若該檔為 runtime state / local-only settings，跨專案 sync 會造成狀態污染。",
        "",
    ]
    for name in unexcluded:
        lines.append(
            f"- [WARNING] sync-exclusion-check: {name} 未在 sync 排除清單 "
            "→ 請加入 EXCLUDE_PATTERNS 和 LOCAL_ONLY"
        )
    lines.append("")
    lines.append(
        "建議動作：編輯 `.claude/scripts/sync-claude-push.py` 的 `EXCLUDE_PATTERNS`，"
        "並依分類（Runtime state / Local-only settings / Session-bound log / 敏感憑證）"
        "補上；若為框架正常設定則忽略本提醒。"
    )
    return "\n".join(lines)


def build_hook_output(unexcluded: List[str]) -> Dict[str, Any]:
    """組裝 SessionStart hook 的 JSON 輸出。

    無未排除檔案時回傳 suppressOutput=True（靜默）；
    有未排除檔案時輸出 additionalContext 警告區塊。
    """
    if not unexcluded:
        return {"suppressOutput": True}

    section = build_warning_section(unexcluded)
    return {
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": section + "\n",
        },
        "suppressOutput": False,
    }


def main() -> int:
    """主入口：讀 stdin（可忽略）→ 掃描未排除檔案 → 輸出 JSON。"""
    logger = setup_hook_logging("session-start-sync-exclusion-check-hook")
    logger.info("sync-exclusion-check hook 啟動")

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

    claude_dir = project_root / ".claude"
    unexcluded = scan_unexcluded_files(claude_dir, logger)
    output = build_hook_output(unexcluded)
    print(json.dumps(output, ensure_ascii=False, indent=2))
    logger.info(
        "sync-exclusion-check hook 完成（unexcluded_count=%d）", len(unexcluded)
    )
    return EXIT_SUCCESS


if __name__ == "__main__":
    sys.exit(run_hook_safely(main, "session-start-sync-exclusion-check"))
