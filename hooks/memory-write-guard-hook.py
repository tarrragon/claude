#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
Memory Write Guard Hook - PreToolUse deny，攔截 Write/Edit 系工具對 memory
目錄的寫入並改道正規化路徑（Bash 不在攔截範圍，見下方豁免範圍）

本框架排除 Claude Code 原生 memory 作為知識載體（0.2.1-W3-082 用戶裁示）：
memory 存於使用者 home 目錄的專案層級儲存，不納入專案 git、不隨 .claude/
sync 到其他專案，與「經驗須跨專案複用」的框架目標根本衝突。捕獲時分流的
判斷時機本身正確——memory 被觸發的那一刻正是判定「值得跨 session 保存」
的時刻，錯的只是目的地，故本 hook 攔截該時機並改道，而非單純禁止寫入。

前身為 memory-upgrade-reminder-hook.py（PostToolUse 事後提醒，比對條件為
feedback_*.md 檔名前綴，對現行 kebab-case slug + frontmatter type 欄位的
memory 格式命中率 0/6，且寫入已發生才提醒）。本版改為 PreToolUse deny，
比對條件改為「路徑落在 memory 目錄」，不比對檔名，避免隨命名慣例變動失效。

Hook 類型: PreToolUse (matcher: Write|Edit|MultiEdit|NotebookEdit)
觸發條件: Write/Edit/MultiEdit 為 tool_input.file_path、NotebookEdit 為
          tool_input.notebook_path，正規化後落在 memory 目錄
          （~/.claude/projects/<project>/memory/ 或 legacy ~/auto-memory/<project>/，
          皆錨定至使用者 home 目錄，大小寫不敏感，`./` `../` 已收斂）
行為: 命中 → deny (exit 2) 並附三分流改道指引；未命中 → allow (exit 0)
無節流：deny 是保護動作，節流會使阻擋在特定時窗內失效（既有 hook 的 30 分鐘
節流對「提醒」合理，對「阻擋」是漏洞）。

豁免範圍（誠實揭露現況，非設計目標——本 hook 不是滴水不漏的沙箱）：
- matcher 僅涵蓋 Write/Edit/MultiEdit/NotebookEdit，不含 Bash：Bash 可用
  heredoc（`cat > memory/x.md <<'EOF' ... EOF`，`bash-tool-usage-rules` 規則五
  明文鼓勵此寫法傳長文字）完全繞過本 hook。排除 Bash 是刻意的，為避免擋住
  0.2.1-W3-085 用 `rm`/`git rm` 清空 memory 目錄的路徑；但這個排除是全稱的，
  同時也放行了寫入，不只放行刪除。此缺口由 `memory-dir-audit-hook.py`
  的 SessionStart+Stop 事後稽核承接（演變史見該檔開頭），Bash 寫入本身
  仍不受本 hook 阻擋，但會在下一次 Stop 前被稽核偵測到
- NotebookEdit 已於 0.2.1-W3-092 併入本 matcher（與 Write 同構：明確
  `notebook_path` 欄位可直接比對，無命令解析風險）

三層 fail-open（沿用框架既有慣例，非本 hook 專屬設計，於此明文記錄）：
1. `lib` import 失敗 -> stderr 提示 + exit 0（放行）
2. stdin 非合法 JSON（`read_json_from_stdin` 回傳 None）-> exit 0（放行）
3. `main()` 未預期例外 -> `run_hook_safely` 記錄完整 traceback 到日誌檔 +
   exit 1（非 2，故不阻擋工具呼叫——exit 1 屬 CC 平台「hook crash 不應
   誤傷正常操作」慣例，非本 hook 專屬繞道）

deny 訊息須讓 agent 讀出「換地方記錄」而非「不能記錄」——單純的拒絕容易被
誤判為能力限制而中止任務或放棄記錄整個經驗（PC-112 self-imposed early
stop 模式），比寫進 memory 更糟。

參考: pm-quality-baseline 規則 7 + PC-061 + PC-112（deny 訊息設計依據）
"""

import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))         # .claude/hooks/
sys.path.insert(0, str(Path(__file__).parent.parent))  # .claude/       (lib.*)

try:
    from lib import (
        emit_hook_output,
        read_json_from_stdin,
        run_hook_safely,
        setup_hook_logging,
    )
    from lib.memory_triage_messages import MemoryTriageMessages
    from lib.memory_paths import get_anchored_memory_dir_pattern
except ImportError as e:
    print(f"[Hook Import Error] {Path(__file__).name}: {e}", file=sys.stderr)
    sys.exit(0)


# === Exit Code ===
EXIT_ALLOW = 0
EXIT_BLOCK = 2

# 比對「路徑落在 memory 目錄」，不比對檔名——命名慣例變動（feedback_* 前綴
# -> kebab-case slug + frontmatter type 欄位）不應使 hook 失效。
# 兩種形式皆錨定至使用者 home 目錄（避免誤判非 home 下同名目錄，如
# /tmp/x/auto-memory/y/z.md 或專案內 auto-memory/foo/ 皆不應命中），
# 並以 re.IGNORECASE 涵蓋大小寫變體（macOS APFS 預設大小寫不敏感，
# Memory/MEMORY 與 memory 是同一個實體目錄）。
# 完整 pattern（含錨定至 home、已 escape）取自 lib/memory_paths.py
# 的 get_anchored_memory_dir_pattern()（0.2.1-W3-196 SSOT，與
# memory-dir-audit-hook.py 共用同一份結構知識，不共用判定邏輯）——錨定至
# home 是結構知識的一部分，不在本 hook 內組裝。
_HOME = os.path.expanduser("~")
MEMORY_DIR_PATTERN = re.compile(
    get_anchored_memory_dir_pattern(_HOME),
    re.IGNORECASE,
)

# deny 訊息：權威來源為 pm-quality-baseline.md 規則 7（三分流判準 + 升級路徑
# 表），本訊息只放判別問句 + 三個目的地摘要 + 指向權威檔的路徑，不逐字複製
# 該檔表格——複製的副本會隨權威檔改寫而漂移（已實測發生：多一逗號、
# 「下方」被誤植為「完整」），單一事實來源才不會漂移。三分流判準本體取自
# lib/memory_triage_messages.py 的 MemoryTriageMessages（0.2.1-W3-196 SSOT，
# 與 memory-dir-audit-hook.py 共用；語氣前綴各自獨立不合併——本段是拒絕
# 語氣，對應 audit 的偵測語氣）。
DENY_REASON = (
    "[MemoryWriteGuard] 這不是不能記錄，是換個地方記錄。\n"
    + MemoryTriageMessages.EXCLUSION_RATIONALE
    + "記錯地方可以搬，不記錄就永久遺失。\n"
    "\n" + MemoryTriageMessages.THREE_WAY_GUIDANCE
)


def is_memory_path(file_path: str) -> bool:
    """判斷路徑是否落在 memory 目錄（不比對檔名，只比對目錄結構）。

    正規化順序：expanduser（展開 ~）-> normpath（字串層級收斂 `./` `../`，
    不觸及檔案系統，故不用 realpath）-> 交由大小寫不敏感的正則比對。
    """
    if not file_path:
        return False
    expanded = os.path.expanduser(file_path)
    normalized = os.path.normpath(expanded)
    return bool(MEMORY_DIR_PATTERN.search(normalized))


def main() -> int:
    """Hook 主入口。"""
    logger = setup_hook_logging("memory-write-guard")
    logger.info("Memory Write Guard Hook 啟動")

    input_data = read_json_from_stdin(logger)
    if not input_data:
        return EXIT_ALLOW

    tool_name = input_data.get("tool_name", "")
    if tool_name not in ("Write", "Edit", "MultiEdit", "NotebookEdit"):
        logger.debug(f"非 Write/Edit/MultiEdit/NotebookEdit 工具（{tool_name}），跳過")
        return EXIT_ALLOW

    tool_input = input_data.get("tool_input") or {}
    # NotebookEdit 的路徑欄位是 notebook_path，非 file_path（W3-092 併入）
    if tool_name == "NotebookEdit":
        file_path = tool_input.get("notebook_path", "")
    else:
        file_path = tool_input.get("file_path", "")

    if not is_memory_path(file_path):
        logger.debug(f"非 memory 路徑（{file_path}），放行")
        return EXIT_ALLOW

    logger.info(f"攔截 memory 目錄寫入：{file_path}")
    emit_hook_output(
        "PreToolUse",
        permission_decision="deny",
        permission_decision_reason=DENY_REASON,
    )
    return EXIT_BLOCK


if __name__ == "__main__":
    sys.exit(run_hook_safely(main, "memory-write-guard"))
