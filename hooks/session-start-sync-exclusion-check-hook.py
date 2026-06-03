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

sys.path.insert(0, str(Path(__file__).parent / "lib"))
from dispatch_tracker import cleanup_expired  # noqa: E402
from sync_exclude_manifest import (  # noqa: E402
    LOCAL_ONLY_PATTERNS,
    GITIGNORE_EXPECTED,
)

EXIT_SUCCESS = 0

# 掃描 .claude/ 根目錄 .json/.yaml 時略過不警告的檔名集合。
#
# local-only 名稱（類型 A Runtime state + 類型 B Local-only settings）直接取自
# SSOT manifest 的 LOCAL_ONLY_PATTERNS（ARCH-020：避免硬編副本與 push 端漂移）。
#
# 類型 X - Framework config（正常 sync，不警告）：settings.json 為框架 Hook 註冊表，
# 跨專案共用，不屬 local-only，故額外併入 allowlist。
_FRAMEWORK_CONFIG = frozenset({"settings.json"})
KNOWN_EXCLUDED = LOCAL_ONLY_PATTERNS | _FRAMEWORK_CONFIG

# 掃描副檔名清單
SCAN_SUFFIXES = {".json", ".yaml", ".yml"}


def _normalize_gitignore_entry(raw_line: str) -> str:
    """將單一 .gitignore 行正規化為可與 GITIGNORE_EXPECTED 名稱比對的裸名（M2）。

    正規化規則（消除 glob / 目錄 / 檔名三形式的表面差異，避免 false positive）：
      1. 去除前後空白；註解（# 開頭）與空行回傳空字串（呼叫端過濾）
      2. 去除前綴否定符 `!`（gitignore re-include 語法，名稱本體仍須比對）
      3. 去除 `.claude/` 前綴與 `**/` glob 前綴（兩者皆指向 .claude 內同名項）
      4. 去除尾端 `/`（目錄形式 `hook-state/` 與裸名 `hook-state` 視為等效）

    回傳裸名（如 "hook-state"、"pm-status.json"）；無法正規化的行回傳空字串。
    """
    line = raw_line.strip()
    if not line or line.startswith("#"):
        return ""
    if line.startswith("!"):
        line = line[1:]
    if line.startswith("**/"):
        line = line[len("**/"):]
    if line.startswith(".claude/"):
        line = line[len(".claude/"):]
    return line.rstrip("/")


def parse_gitignore_entries(content: str) -> set:
    """解析 .gitignore 內容為正規化裸名集合（忽略註解、空行）。"""
    entries = set()
    for raw_line in content.splitlines():
        normalized = _normalize_gitignore_entry(raw_line)
        if normalized:
            entries.add(normalized)
    return entries


def find_gitignore_drift(gitignore_path: Path) -> List[str]:
    """交叉驗證 .gitignore 是否涵蓋 manifest 的 GITIGNORE_EXPECTED。

    回傳未被 .gitignore 涵蓋的 local-only 名稱（已排序）。
    .gitignore 不存在或讀取失敗時，視為全部缺項（保守警告）。
    """
    try:
        content = gitignore_path.read_text(encoding="utf-8")
    except OSError:
        return sorted(GITIGNORE_EXPECTED)
    covered = parse_gitignore_entries(content)
    return sorted(GITIGNORE_EXPECTED - covered)


def build_gitignore_drift_section(drift: List[str]) -> str:
    """將 gitignore 漂移缺項格式化為 markdown 警告區塊。"""
    lines: List[str] = [
        "## Sync gitignore↔manifest 交叉驗證（gitignore-drift）",
        "",
        "偵測到 `.gitignore` 未涵蓋 sync manifest 的 local-only 名稱"
        "（`GITIGNORE_EXPECTED`）。",
        "未列入 gitignore 的本地檔會被 push 端 clean-check 判為未追蹤而 abort"
        "（W1-024 缺陷 T）。",
        "",
    ]
    for name in drift:
        lines.append(
            f"- [WARNING] gitignore-drift: `{name}` 在 sync manifest 但未被 "
            "`.gitignore` 涵蓋 → 請補上 `.claude/" + name + "` 規則"
        )
    lines.append("")
    lines.append(
        "建議動作：編輯專案根 `.gitignore`，依 `sync_exclude_manifest."
        "GITIGNORE_EXPECTED` 補齊上列名稱（glob / 目錄 / 裸名三形式皆可）。"
    )
    return "\n".join(lines)


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


def build_hook_output(
    unexcluded: List[str], gitignore_drift: List[str] = None
) -> Dict[str, Any]:
    """組裝 SessionStart hook 的 JSON 輸出。

    無任何異常（未排除檔案 + gitignore 漂移皆空）時回傳 suppressOutput=True（靜默）；
    任一異常存在時輸出對應 additionalContext 警告區塊（兩區塊可並存）。
    """
    gitignore_drift = gitignore_drift or []
    if not unexcluded and not gitignore_drift:
        return {"suppressOutput": True}

    sections: List[str] = []
    if unexcluded:
        sections.append(build_warning_section(unexcluded))
    if gitignore_drift:
        sections.append(build_gitignore_drift_section(gitignore_drift))

    return {
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": "\n\n".join(sections) + "\n",
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

    # Housekeeping: GC dispatch-active.json 殘留記錄（TTL 1h）
    # 失敗降級為 logger.warning，不阻塞 session 啟動（W11-024）
    try:
        expired_count = cleanup_expired(project_root, max_age_hours=1)
        if expired_count > 0:
            logger.info("session-start: 已清理 %d 筆超時 dispatch 記錄", expired_count)
    except Exception as e:  # noqa: BLE001
        logger.warning("session-start: dispatch cleanup 失敗（忽略）: %s", e)

    claude_dir = project_root / ".claude"
    unexcluded = scan_unexcluded_files(claude_dir, logger)

    # gitignore↔manifest 交叉驗證（W1-031）：偵測 .gitignore 漏列 local-only 名稱
    try:
        gitignore_drift = find_gitignore_drift(project_root / ".gitignore")
    except Exception as e:  # noqa: BLE001 — 交叉驗證失敗降級不阻塞 session
        logger.warning("gitignore 交叉驗證失敗（忽略）: %s", e)
        gitignore_drift = []

    output = build_hook_output(unexcluded, gitignore_drift)
    print(json.dumps(output, ensure_ascii=False, indent=2))
    logger.info(
        "sync-exclusion-check hook 完成（unexcluded_count=%d, gitignore_drift=%d）",
        len(unexcluded),
        len(gitignore_drift),
    )
    return EXIT_SUCCESS


if __name__ == "__main__":
    sys.exit(run_hook_safely(main, "session-start-sync-exclusion-check"))
