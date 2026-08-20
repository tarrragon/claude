#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml"]
# ///
"""
Bash Git Add Broad Guard Hook - PreToolUse Hook

功能: 偵測廣域 git add / git stage（`.` / `./` / `:/` / 萬用字元 / 尾斜線
      目錄 / `-A`｜`--all` / `-u`｜`--update` 等無法靜態列舉為具體檔案的
      pathspec），且目前 git index 存在未提交變更時 DENY，阻擋 PC-092 型
      跨 ticket 汙染（廣域 add 把不屬於本次工作、擁有者尚未 commit 的變更
      一併掃入 staged）。

Hook Event: PreToolUse
Matcher: Bash
Decision: DENY（exit 2，stderr 訊息）| allow（無輸出）

Source: PC-092 執行期防線補位（提交側守衛既有裁決的 add 側對稱延伸，
        經多視角審查後修正判準資料選擇與三類漏放）

============================================================
背景與定位（沿用提交側守衛既有裁決，理由同源不重複論證）
============================================================
提交側守衛 bare-commit-guard-hook.py 已對「裸 git commit 併吞他人 staged
檔案」建立完整設計裁決。本 hook 是 add 側的對稱補位：PC-092 壞狀態不只
發生在 commit 當下，廣域 add 本身已把其他人尚未 commit 的變更一併掃進
共用 index，是更早的攔截點——雖非取代提交側守衛，但能在 stage 階段就
攔下風險，不必依賴後續是否有人記得用 path-limited commit 補救。
bash-git-protected-branch-guard-hook.py 雖也解析 `git add`，但目的是保護
分支寫入判定，且該 hook 自陳廣域 add 形式「無法靜態列舉」而不處理（見該
檔 add-and-commit 串接繞道章節）；本 hook 要處理的正是它明文排除的那一類。

============================================================
判準（多視角審查修正：移除並行派發依賴，直接對齊壞狀態定義）
============================================================
壞狀態定義本身沒有「並行派發中」這個條件——「共用 index 中出現不屬於
本次工作、且擁有者尚未提交的變更被置入 staged」，任何時候只要廣域 add
遇上目前已有未提交變更，risk 就成立：即使前一個 agent 已結束派發，只要
其變更仍未 commit，同一命令仍造成一模一樣的汙染。原設計曾以
`.claude/dispatch-active.json` 是否有活躍記錄分級 DENY/WARN，但那是
代理訊號不是不變量，且 WARN 對 AI agent 無約束力已四次實證（見提交側
守衛裁決記錄）。故判準改為：**廣域 add（pathspec 無法靜態列舉為具體
檔案）且目前存在未提交變更 → 一律 DENY，不分並行與否**；無未提交變更
時廣域 add 本身無害（沒有東西可污染），直接放行。移除對
dispatch-active.json 的依賴後，判決分支數不增反減。

「廣域」的判定方式同步修正為「pathspec 是否可靜態列舉為具體檔案」，
不可列舉即視為廣域——取代原本的硬編清單式判斷。硬編清單無法涵蓋
`./`、`:/`、萬用字元、尾斜線目錄（如 `src/`）、`git stage`（官方別名）
等與 `.`/`-A`/`-u` 等價的寫法，見 `_is_literal_pathspec_token`。

豁免通道：worktree 隔離（目標 repo 為 git worktree，擁有獨立 index，
與主 repo 共用 index 無關，PC-092 語意不成立）自然豁免，不設顯式 marker。

============================================================
結構性限制（既有同類 hook 共通探針結論，非本 hook 新增，須明示避免誤判覆蓋範圍）
============================================================
PreToolUse Bash hook 僅檢視 Bash 工具收到的**字面命令字串**
（tool_input.command），不追蹤該命令執行時內部產生的子行程呼叫。CLI 內部
以 Python subprocess 呼叫 `git add` 的路徑對本 hook 結構性不可見，與同類
既有 hook 的偵測模型一致。**Action**：若未來需要覆蓋 CLI 內部呼叫 git add
的路徑，攔截點應設在該 CLI 本身（呼叫 subprocess 前的入口做檢查），不要
為此擴充本檔案的字面命令解析——PreToolUse 時機結構上看不到子行程呼叫，
往這個方向硬做只會不斷追加特例卻不可能真正涵蓋。

============================================================
既有守衛的引用誤報與本 hook 的防範設計（解析層已收斂至共用 lib）
============================================================
派發前實測發現：bare-commit-guard-hook.py 對 heredoc 內文中「描述」提交
命令的文字字面（而非實際要執行的命令）誤判為真實命令，導致寫入操作類
CLI 呼叫被誤擋。成因是該 hook 當時對命令做全字串子字串比對，無法區分
「這是要執行的命令」與「這是在描述命令的文字」。

本 hook 從一開始即避免重演同一缺陷，採 argv 結構解析而非全字串子字串
比對。三個 Bash git 守衛（本檔、bare-commit-guard-hook.py、
bash-git-protected-branch-guard-hook.py）各自解析出的「什麼算一次 git
呼叫」定義曾經互不相同，已收斂至 `.claude/lib/git_command_parse.py` 的
`find_git_invocations()`——本檔不再自行維護 heredoc 剝離、換行正規化、
tokenize、語句切分等解析細節，機制說明見該共用模組 docstring；本檔僅
保留「什麼算廣域 add」的判決邏輯（`_is_broad_add`）。

============================================================
範疇邊界（刻意不做，非遺漏，比照 bare-commit-guard-hook.py 同類邊界）
============================================================
- 僅偵測 cwd 隱含形式的 `git add`（含 `git -C <path> add`），不解析子
  shell `cd <path> && git add` 形式的目標 repo（與 bare-commit-guard-
  hook.py 的既有範疇邊界一致，理由同源）。
- worktree 豁免判定僅依目標 repo（-C 路徑或預設 project_root）當下的
  git-dir / git-common-dir 差異，不解析 `cd` 子 shell 形式切換的工作目錄。
- 短選項組合（如 `-vA`、`-uv`）僅掃描是否含 `A` 或 `u` 字元即視為命中，
  可能對「恰好命中字母但語意不同」的極端組合誤判。方向安全（誤判方向是
  「該擋的沒擋」或「保守多擋」而非放過真正的廣域 add）。
- cwd 判定不解析 `cd` 子 shell（同上）；前綴包裹、引號不平衡失敗語意、
  多語句解析已由共用 lib 層處理，見下方 main() 的處置說明。

============================================================
交互風險（記錄不修）
============================================================
worktree-auto-commit-hook.py 內有現役的廣域 add 呼叫，其安全論證前提是
「無活躍代理人」，與本 hook（原設計）的觸發條件互為鏡像——移除
dispatch-active.json 依賴後，本 hook 已不再共享同一前提失準風險，但
worktree-auto-commit-hook.py 本身的前提仍待該 hook 自身覆核，非本票範圍。
"""

import json
import shlex
import sys
from pathlib import Path
from typing import List, Optional

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib import setup_hook_logging, run_hook_safely, read_json_from_stdin
from lib.git_command_parse import (
    GitInvocation,
    find_git_invocations,
    is_literal_pathspec_token,
)
from lib.git_utils import get_project_root, run_git_command, get_uncommitted_files, FileStatus


# git add/stage 無法靜態列舉的 flag（目錄列舉語意，需實際檔案系統狀態）
_ADD_UNENUMERABLE_FLAGS = {
    "-A", "--all", "-u", "--update", "-i", "--interactive", "-p", "--patch",
    "-e", "--edit", "-N", "--intent-to-add",
}

# 供訊息顯示的廣域 flag 提示（單一來源組出，避免各處手寫重複）
_BROAD_FLAG_HINT = "、".join(
    ["`.`", "`./`", "`:/`", "萬用字元", "尾斜線目錄", "-A/--all", "-u/--update"]
)


def _is_broad_add(entry: GitInvocation) -> bool:
    """判定 git add 呼叫是否為廣域 add：pathspec 是否可靜態列舉為具體檔案，
    不可列舉（含目錄 / 萬用字元 / 特殊 pathspec / 廣域 flag）即視為廣域。"""
    args = entry.args
    saw_pathspec = False
    for arg in args:
        if arg == "--":
            continue
        if arg in _ADD_UNENUMERABLE_FLAGS:
            return True
        if arg.startswith("--"):
            continue  # 其餘長 flag 不影響列舉（如 --verbose --dry-run）
        if arg.startswith("-") and len(arg) > 1:
            if "A" in arg[1:] or "u" in arg[1:]:
                return True
            continue  # 其餘短 flag（如 -v）不影響列舉
        if not is_literal_pathspec_token(arg):
            return True
        saw_pathspec = True
    if not saw_pathspec:
        return True  # 無任何具體 pathspec（如裸 `git add`），視為廣域
    return False


def _is_target_worktree(cwd: Optional[str]) -> bool:
    """判定目標 repo（cwd 或 -C 路徑）是否為 git worktree（非主 repo）。

    在 worktree 中 `git rev-parse --git-dir` 與 `--git-common-dir` 不同
    （前者含 /worktrees/name），在主 repo 中兩者相同。讀取失敗時保守回傳
    False（非 worktree，不豁免，方向安全）。
    """
    success_common, common_dir = run_git_command(
        ["rev-parse", "--git-common-dir"], cwd=cwd
    )
    if not success_common:
        return False
    success_dir, git_dir = run_git_command(["rev-parse", "--git-dir"], cwd=cwd)
    if not success_dir:
        return False
    return Path(common_dir).resolve() != Path(git_dir).resolve()


def _build_pathspec_review_command(uncommitted: List[FileStatus]) -> str:
    """依目前未提交變更組出**待人工篩選**的 add pathspec 骨架（rename 取新路徑）。

    刻意不稱「可直接複製」：hook 無法判斷這些檔案哪些屬於當前工作，若把
    這串路徑包裝成「照做即正確」的命令，讀者字面執行就會把他人未提交的
    變更一併 stage——那正是本 hook 要防的 PC-092 壞狀態本身。此函式只
    負責把 porcelain 轉成骨架文字，是否使用、如何刪減由讀者自行判斷
    （見 _build_deny_message 的措辭）。
    """
    paths: List[str] = []
    for entry in uncommitted:
        path = entry.file_path
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        paths.append(shlex.quote(path))

    if not paths:
        return "git add <你 ticket 相關的檔案>"

    shown = paths[:10]
    skeleton = "git add " + " ".join(shown)
    if len(paths) > 10:
        skeleton += f"  # 另有 {len(paths) - 10} 筆同樣需要判斷歸屬，未列出不代表可略過"
    return skeleton


def _build_deny_message(broad_command: str, uncommitted: List[FileStatus]) -> str:
    """組出 DENY 訊息：被攔截命令優先呈現，接理由，再給待篩選的 pathspec 骨架。

    骨架命令刻意不稱「可直接複製」——見 _build_pathspec_review_command
    docstring：hook 無法知道哪些檔案屬於當前工作，若暗示照做即正確，
    讀者字面執行就會複製出本 hook 要防的壞狀態本身。
    """
    status_lines = [str(entry) for entry in uncommitted]
    status_block = "\n".join(f"  {line}" for line in status_lines[:10])
    if len(status_lines) > 10:
        status_block += f"\n  ...（另 {len(status_lines) - 10} 筆）"

    review_command = _build_pathspec_review_command(uncommitted)

    return (
        "[廣域 git add 被阻擋]\n\n"
        f"被攔截的命令：{broad_command}\n\n"
        "理由：目前 git index 有未提交變更，廣域 add"
        f"（{_BROAD_FLAG_HINT} 等無法靜態列舉為具體檔案的 pathspec）會把"
        "其中不屬於本次工作、且擁有者尚未 commit 的變更一併 stage，造成 "
        "PC-092 型跨 ticket 汙染——此判定不依賴是否有並行派發活躍記錄"
        "（WARN 對 AI agent 無約束力已四次實證，見提交側守衛裁決記錄）。\n\n"
        "目前未提交變更（git status --porcelain）：\n"
        f"{status_block}\n\n"
        "只有以下兩條路徑，沒有第三條：\n"
        "  1. 改用精準 add——下方是目前所有未提交檔案組成的骨架命令，"
        "本 hook 無法判斷哪些屬於你的工作，執行前請逐筆確認並"
        "刪去不屬於本次工作的路徑，不要照原樣執行：\n"
        f"     {review_command}\n"
        "  2. 確需整批加入所有變更，改在 worktree 隔離環境操作"
        "（各自獨立 index，不受本守衛限制）。\n"
    )


def main() -> int:
    """Hook 主邏輯：廣域 add 且目前有未提交變更即 DENY，worktree 豁免。"""
    logger = setup_hook_logging("bash-git-add-broad-guard")

    try:
        input_data = read_json_from_stdin(logger)
    except (json.JSONDecodeError, EOFError):
        logger.warning("無法解析 stdin JSON，放行")
        return 0

    if not input_data:
        return 0

    tool_name = input_data.get("tool_name", "")
    if tool_name != "Bash":
        return 0

    tool_input = input_data.get("tool_input") or {}
    raw_command = tool_input.get("command", "") or ""
    if not raw_command:
        return 0

    invocations = find_git_invocations(raw_command, {"add"})
    if invocations is None:
        # 無法安全 tokenize（未閉合引號等）：既有設計選擇 fail-open——
        # 無法靜態確認時傾向不誤擋非本 hook 意圖攔截的命令，簽名收斂後
        # 明確判斷（不再與「可解析但無命中」的空清單混淆），語意不變。
        logger.debug("命令無法安全解析（未閉合引號等），fail-open 放行")
        return 0
    if not invocations:
        logger.debug("命令不含 git add/stage 呼叫，放行")
        return 0

    broad_entry: Optional[GitInvocation] = None
    for entry in invocations:
        if _is_broad_add(entry):
            broad_entry = entry
            break

    if broad_entry is None:
        logger.debug("命令含 git add 但 pathspec 皆可靜態列舉，放行")
        return 0

    target_cwd = broad_entry.dash_c_path

    if _is_target_worktree(target_cwd):
        logger.debug("目標 repo 為 worktree 隔離環境，豁免放行")
        return 0

    uncommitted = get_uncommitted_files(cwd=target_cwd)
    if not uncommitted:
        logger.debug("廣域 add 但目前無未提交變更，無汙染風險，放行")
        return 0

    broad_command = " ".join(broad_entry.statement)
    logger.warning(
        "廣域 git add 被阻擋（未提交變更數=%d）：%s",
        len(uncommitted), broad_command,
    )
    print(_build_deny_message(broad_command, uncommitted), file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(run_hook_safely(main, "bash-git-add-broad-guard"))
