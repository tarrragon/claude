#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
Memory Dir Audit Hook - SessionStart 與 Stop 雙掛稽核，偵測本專案 memory
目錄相對上次快照的變化並改道指引（marker 不分 session，同一次變化只提醒
一次，代價見下方）

行為契約：SessionStart 與 Stop 呼叫的是同一份核心邏輯 `_run_audit()`。
marker 記錄的是「候選目錄現在有哪些檔案」，這是目錄的屬性，不是任何事件
或 session 的狀態，兩個事件只是觸發時機不同（一個在 session 開始、一個在
每次助理回合結束），判準完全相同：

1. 以 `resolve_candidate_memory_dirs()` 篩出對應本專案的候選目錄
2. 對每個候選取當前「檔名集合」快照
3. 與 marker 記錄的上一次快照比較，任一候選目錄「非空且與上次快照不同」
   即輸出改道指引（stderr）
4. 不論是否告警，marker 都無條件更新為當前快照

代價：marker 不分 session，若 session B 期間發生的變化已被 session A 的
Stop 記錄過，B 不會再被告知同一次變化。這個代價是刻意接受的——改道提醒是
針對「目錄內容」的冪等建議文字，不是針對某個 session 的義務；同一次變化
少提醒一次，在以反告警疲勞為核心目標的 hook 裡是收益。

零候選（不論哪個事件）交 `_warn_if_comparison_key_may_be_stale()` 判斷是否
為比對鍵過期（僅寫日誌，不外顯 stderr）；非 SessionStart/Stop 的事件直接
跳過，不做任何檢查。

候選目錄的列舉與篩選（layout 表、雙邊正規化比對）見
`resolve_candidate_memory_dirs()` 自身的 docstring。

修改本檔前必須遵守的約束（違反即重現已封閉過的失效形態）：
1. 不得回退為推導 slug；CC 命名規則不可假設，必須列舉加雙邊正規化
2. 正規化必須雙邊；單邊等同重新引入對命名規則的假設
3. 回報範圍必須限縮當前專案；稽核是狀態檢查，全域回報不可行動
4. 兩種 layout 用不同比對鍵：現行位置用完整路徑、legacy 用 basename（識別符語意不同）
5. 比對鍵必須取自 `get_project_root()`；`CLAUDE_PROJECT_DIR` 恆指主 repo，
   不隨 worktree 的實際 cwd 改變
6. SessionStart 與 Stop 皆不使用 deny/block 語意，`main()` 恆回傳
   `EXIT_OK`，稽核結果一律透過 stderr 訊息呈現，不透過 exit code 表達
7. marker 只比對檔名集合，不讀取檔案內容、不比對 mtime；marker 檔案本身
   不得落在被稽核的 memory 目錄內（否則目錄非空即為 marker 自身造成，
   稽核會命中自己寫的 marker，自我實現）；實際存放路徑見下方「marker
   儲存位置」段，此處不重複列出，避免兩處各自漂移
8. 稽核可節流、deny 不可節流：阻擋動作每次都必須擋，節流會使阻擋在特定
   時窗內失效；稽核是提醒，重複提醒同一件事沒有額外資訊量，節流是本檔的
   正確設計而非取巧。修改節流邏輯前，先確認新邏輯是否仍成立於這條差異
9. 效能防護與 fail-open 承諾（見下方對應段落）不得在後續修改中被默默削弱；
   新增或調整行為時，若影響到其中任一項，必須在該段落同步改寫，不可只改
   程式碼留舊文字

Hook 類型: SessionStart + Stop（皆不掛 matcher）。兩事件本身已隱含觸發
時機，不需再依工具類型篩選：任何寫入型工具造成的 memory 目錄變化都會在
下一次 Stop 被看見，涵蓋面與逐工具攔截相同，差別只在發現延遲。memory
寫入本來就罕見——主路徑已被 `memory-write-guard-hook.py` 的 PreToolUse
deny 擋下，即時性的邊際價值低，換取的是不必為每種新增的寫入型工具再補一
個 matcher。

marker 儲存位置：`.claude/hooks/hook-logs/memory-dir-audit-marker.json`
（`.gitignore` 的 `**/hook-logs/` 涵蓋，不進版控、不隨 `.claude/` sync 到
其他專案）；可由環境變數 `MEMORY_DIR_AUDIT_MARKER_FILE` 覆寫，供測試隔離。
結構為 `{目錄路徑: 排序後檔名清單}`，不含 session 維度。

守衛（memory-write-guard，PreToolUse）與稽核（本 hook，SessionStart/Stop）
範圍語意不同，不可互相套用：守衛在寫入發起當下天生綁定該次目標路徑，範圍
無關且零成本；稽核若掃描全域，會繼承並回報其他專案累積的既有狀態，而那些
狀態本專案無法處理，故回報範圍須限縮到本專案。

效能防護：
1. 目錄不存在 -> `_snapshot_candidates()` 內 isdir 短路為 False，快照為
   空清單，不呼叫 listdir
2. 不遞迴掃描 -> 只 os.listdir 頂層一次，不用 os.walk
3. marker 比對只用檔名清單的相等比較，不讀取檔案內容或 mtime

三層 fail-open：
1. `lib` import 失敗 -> stderr 提示 + exit 0
2. stdin 非合法 JSON、空輸入、或非 SessionStart/Stop 事件 -> exit 0
3. `main()` 未預期例外 -> `run_hook_safely` 記錄完整 traceback 到日誌檔 +
   exit 1（兩事件皆無法逆轉已發生的行為，僅影響本次稽核本身是否完成）

參考相關背景決策（matcher 選擇與演進、preToolUse 對應方案、三分流判準）
"""

import glob
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))         # .claude/hooks/
sys.path.insert(0, str(Path(__file__).parent.parent))  # .claude/       (lib.*)

try:
    from lib import (
        get_project_root,
        read_json_from_stdin,
        run_hook_safely,
        setup_hook_logging,
    )
    from lib.memory_triage_messages import MemoryTriageMessages
    from lib.memory_paths import (
        CURRENT_LAYOUT,
        MEMORY_LAYOUTS,
        get_layout_glob_pattern,
        get_layout_identifier,
        get_layout_parent_glob_pattern,
    )
except ImportError as e:
    print(f"[Hook Import Error] {Path(__file__).name}: {e}", file=sys.stderr)
    sys.exit(0)


# === Exit Code ===
# SessionStart 與 Stop 皆無 deny/block 語意，本 hook 恆定 exit 0，
# 稽核結果透過 stderr 訊息呈現，不透過 exit code 表達。
EXIT_OK = 0

_HOME = os.path.expanduser("~")

_HOOK_DIR = Path(__file__).resolve().parent
_DEFAULT_MARKER_FILE = _HOOK_DIR / "hook-logs" / "memory-dir-audit-marker.json"

# 改道指引：與 memory-write-guard-hook.py 的 DENY_REASON 同源
# （EXCLUSION_RATIONALE + THREE_WAY_GUIDANCE 取自 lib/memory_triage_messages.py
# 的 MemoryTriageMessages，0.2.1-W3-196 SSOT，語氣前綴各自獨立不合併）。
# 首句先陳述能力事實——事後稽核、寫入已完成且未被阻擋、需主動處理——區辨
# 事前阻擋的資訊排在最前面；「這不是不能記錄，是換個地方記錄」與 guard
# DENY_REASON 首句幾乎逐字相同，降為補語置於原則之後，避免讀者在注意力
# 前段只讀到與 deny 同構的文字而誤判寫入已被擋下、中止當下任務
# （0.2.1-W3-197，PC-112 self-imposed early stop 形態）。Action 為兩步
# 可執行指令：依判準搬遷內容、搬遷後清空目錄，並說明不清空的後果——舊版
# 「請評估是否需搬遷內容」不是動作，且缺此收尾步驟，會使稽核在後續每次
# SessionStart / Stop 對同一份未清空內容重複告警。
AUDIT_MESSAGE = (
    "[MemoryDirAudit] 稽核偵測到 memory 目錄有內容，寫入已完成且未被阻擋，"
    "需要你主動處理——這不是不能記錄，是換個地方記錄。\n"
    + MemoryTriageMessages.EXCLUSION_RATIONALE
    + "\n\n"
    "Action：依下方三個目的地判準將內容搬遷至對應載體，搬遷完成後清空本"
    "目錄；不清空則同一份內容會在下次稽核再次觸發告警。\n"
    "\n" + MemoryTriageMessages.THREE_WAY_GUIDANCE
)


def _normalize_for_comparison(value: str) -> str:
    """移除所有非英數字元並轉小寫，作為雙邊正規化比對的標準形式。

    Why 雙邊而非單邊：若只正規化其中一側（例如把當前工作目錄依猜測的
    CC slug 規則轉換成 `-Users-mac-eric-...` 形式後，再跟真實目錄名逐字
    比對），比對結果仍完全依賴那份猜測規則是否正確——這正是舊版
    `resolve_memory_dir()` 犯的錯誤，CC 命名規則變動時，猜測會再次過期，
    而過期的形態與這次完全相同（查不到等同沒東西，不會走錯誤路徑）。

    雙邊都正規化到「移除所有非英數字元、轉小寫」這個與 CC 命名規則無關的
    最小公分母後，比對就不再依賴任何一方對 CC 規則的假設：只要兩邊描述
    的是同一個絕對路徑，正規化後必然逐字相等，不論 CC 中間把 `/`、`_`、
    `.` 換成什麼字元、換了幾種、或日後改變換法。
    """
    return re.sub(r"[^0-9a-zA-Z]", "", value).lower()


def resolve_candidate_memory_dirs() -> list:
    """列舉候選 memory 目錄，依 layout 表逐列比對，回傳對應本專案者。

    兩種 layout 的識別符語意不同，比對鍵不可共用一把：現行位置的識別符
    （slug）是完整路徑的另一種編碼，比對鍵用 `get_project_root()` 的完整
    路徑正規化；legacy 位置的識別符是純專案名稱，比對鍵須用 basename
    正規化——沿用完整路徑鍵去比對純專案名恆不相等，該分支會變成死碼
    （查不到等同沒東西，外部無法區分「目錄不存在」與「比對鍵錯了」）。
    兩把鍵是本質差異，layout 的差異必須編碼為資料而非控制流。

    走訪 `lib/memory_paths.MEMORY_LAYOUTS`（不得只 import 具名常數後自行
    重排一張表——那會在新增第三種 layout 時造成本函式與
    memory-write-guard-hook.py 覆蓋範圍不對稱，0.2.1-W3-194 修過的同型
    缺陷）；glob pattern 與識別符取法（哪一段是 `*`）皆由 `memory_paths`
    的 layout 定義推導，本函式只負責「哪種 identifier_kind 對應哪把
    comparison_key」這個 audit 特有的判定邏輯，以及 `_normalize_for_comparison`
    相等比較。

    比對鍵一律取自 `get_project_root()`（worktree-aware），不可讀
    `CLAUDE_PROJECT_DIR` 環境變數或 `os.getcwd()`——`CLAUDE_PROJECT_DIR`
    恆指主 repo，不隨 worktree 的實際 cwd 改變，直接讀取會在 worktree
    session 查錯目標。

    效能：`projects/` 下條目數為個位數到數十，一次 glob 掃描 + 正規化
    比對成本可忽略。
    """
    project_root = str(get_project_root())
    normalized_root = os.path.normpath(project_root)
    project_path_key = _normalize_for_comparison(normalized_root)
    project_name_key = _normalize_for_comparison(os.path.basename(normalized_root))

    # identifier_kind（memory_paths 定義的結構知識）到本函式比對鍵的對照，
    # 屬 audit 特有判定邏輯，不屬於共用結構知識，故留在此處。glob_pattern
    # 一律傳入本函式當下的 `_HOME`（可能被測試 monkeypatch）——memory_paths
    # 模組本身不持有、不快取 home，任何 home 都須由呼叫端每次傳入，這是
    # 該模組刻意的設計（見 memory_paths.py docstring），非本函式繞過快取。
    comparison_key_by_identifier_kind = {
        "full_path": project_path_key,
        "project_name": project_name_key,
    }

    matched = []
    for layout in MEMORY_LAYOUTS:
        glob_pattern = get_layout_glob_pattern(layout, _HOME)
        comparison_key = comparison_key_by_identifier_kind[layout["identifier_kind"]]
        for candidate_dir in glob.glob(glob_pattern):
            name = get_layout_identifier(layout, candidate_dir)
            if _normalize_for_comparison(name) == comparison_key:
                matched.append(candidate_dir)

    return matched


def _snapshot_candidates(candidates: list) -> dict:
    """對每個候選目錄取「檔名集合」快照，回傳 {目錄路徑: 排序後檔名清單}。

    只呼叫 `os.listdir()` 讀頂層一次，不讀取檔案內容、不比對 mtime——
    marker 比對必須廉價，事件式判準不能讓每次比對的成本疊加在對話節奏上。
    isdir 為 False 時直接記空清單、不呼叫 listdir，是本檔目前唯一的效能
    短路點。目錄不存在與存在但為空在快照上刻意不區分，兩者對「是否有內容
    需要提醒」這個問題的答案相同，皆為否。
    """
    snapshot = {}
    for candidate_dir in candidates:
        if os.path.isdir(candidate_dir):
            snapshot[candidate_dir] = sorted(os.listdir(candidate_dir))
        else:
            snapshot[candidate_dir] = []
    return snapshot


def _marker_file() -> Path:
    """marker 檔案路徑，可由環境變數覆寫供測試隔離（不觸碰開發者本機
    真實 marker 檔，測試不因此互相污染或依賴殘留狀態）。"""
    override = os.environ.get("MEMORY_DIR_AUDIT_MARKER_FILE")
    return Path(override) if override else _DEFAULT_MARKER_FILE


def _load_marker(marker_file: Path) -> dict:
    """讀 marker（{目錄路徑: 檔名清單}，不含 session 維度）。檔案不存在或
    內容非法時回傳空 dict，不拋例外——marker 遺失的後果只是「這次當成沒有
    基準線」，不影響 hook 的 fail-open 承諾。"""
    try:
        if not marker_file.is_file():
            return {}
        data = json.loads(marker_file.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _save_marker(marker_file: Path, snapshot: dict, logger) -> None:
    """寫 marker。失敗僅記錄日誌，不阻斷主流程（marker 是節流用的
    輔助狀態，寫入失敗最壞後果是退化回『下次可能重複提醒』，不影響稽核
    本身的正確性）。"""
    try:
        marker_file.parent.mkdir(parents=True, exist_ok=True)
        marker_file.write_text(
            json.dumps(snapshot, ensure_ascii=False), encoding="utf-8"
        )
    except Exception as exc:
        logger.warning(f"寫入 marker 失敗（不影響本次稽核結果）: {exc}")


def _warn_if_comparison_key_may_be_stale(logger) -> None:
    """`resolve_candidate_memory_dirs()` 回傳零候選時的可觀測性檢查。

    「零候選」與「本專案 memory 乾淨」是兩件不同的事——前者是比對鍵沒有
    命中任何 `~/.claude/projects/*/memory` 目錄（本身應存在，因為 CC 執行
    本 hook 前已為當前呼叫的專案建立該條目），後者是命中了但目錄為空。
    只有後者才是真正「乾淨」；前者代表比對鍵假設可能已經過期，形態與舊版
    `resolve_memory_dir()` 的原始 bug 完全相同（查不到等同沒東西，不會走
    錯誤路徑，只是這次連候選都列不出來）。

    僅在 `~/.claude/projects/` 底下確實存在其他條目（代表 CC 的專案目錄
    機制本身正常運作）而本專案零候選時才告警——避免在 `~/.claude/projects/`
    尚未建立任何條目的全新環境（例如首次執行、CI）誤報。告警走
    `logger.warning`（僅寫入檔案，`STREAM_HANDLER_LEVEL_NORMAL` 為
    CRITICAL，不會外顯為 stderr「hook error」），符合本框架 catch 區塊
    可觀測性規範對「已預期但需追蹤」情況的分級。
    """
    other_entries = glob.glob(get_layout_parent_glob_pattern(CURRENT_LAYOUT, _HOME))
    if other_entries:
        logger.warning(
            "resolve_candidate_memory_dirs() 回傳零候選，但 "
            f"~/.claude/projects/ 下有 {len(other_entries)} 個既有條目——"
            "比對鍵可能未命中本專案自己的目錄（假設過期的既知形態，"
            "詳見 ARCH-BAL-012），非單純『memory 乾淨』，建議排查"
            "resolve_candidate_memory_dirs() 的比對鍵是否仍與實際"
            "命名規則一致。"
        )


def _run_audit(logger, marker_file: Path) -> int:
    """核心稽核邏輯，SessionStart 與 Stop 共用同一份判準（見檔案頂端行為
    契約）：取當前候選目錄快照，與 marker 記錄的上一次快照比較，任一候選
    目錄「非空且與上次不同」即告警，並無條件更新 marker 為當前快照。
    """
    candidates = resolve_candidate_memory_dirs()
    if not candidates:
        _warn_if_comparison_key_may_be_stale(logger)
        return EXIT_OK

    current_snapshot = _snapshot_candidates(candidates)
    baseline_snapshot = _load_marker(marker_file)

    changed_nonempty_dirs = [
        d for d, files in current_snapshot.items()
        if files and files != baseline_snapshot.get(d, [])
    ]

    _save_marker(marker_file, current_snapshot, logger)

    if changed_nonempty_dirs:
        logger.info(f"稽核偵測到 memory 目錄內容變化：{changed_nonempty_dirs}")
        print(AUDIT_MESSAGE, file=sys.stderr)
    else:
        logger.debug(f"稽核：內容相對上次快照無變化（共 {len(candidates)} 個候選）")
    return EXIT_OK


def main() -> int:
    """Hook 主入口。依 `hook_event_name` 判斷是否為 SessionStart / Stop，
    是則呼叫 `_run_audit()`，其餘事件直接跳過。"""
    logger = setup_hook_logging("memory-dir-audit")
    logger.info("Memory Dir Audit Hook 啟動")

    input_data = read_json_from_stdin(logger)
    if not input_data:
        return EXIT_OK

    hook_event_name = input_data.get("hook_event_name", "")
    if hook_event_name not in ("SessionStart", "Stop"):
        logger.debug(f"非 SessionStart/Stop 事件（{hook_event_name}），跳過")
        return EXIT_OK

    return _run_audit(logger, _marker_file())


if __name__ == "__main__":
    sys.exit(run_hook_safely(main, "memory-dir-audit"))
