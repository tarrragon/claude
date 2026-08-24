#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml"]
# ///
"""
Workspace Wipe Guard Hook - PreToolUse Hook

功能: 偵測全工作區破壞性 git 操作（stash 建立 / checkout 丟棄整個工作區 /
      reset --hard / clean -f / restore 丟棄整個工作區），符合下列任一
      條件即 DENY 阻擋（exit 2，stderr 訊息，含安全替代方案）：
        (a) 並行派發中（dispatch-active.json 有活躍記錄）
        (b) 主 repo 有未提交的 tracked 變更（無論是否並行）
      兩者皆否（非並行期且主 repo 乾淨）僅 WARN 提醒（exit 0）。

Hook Event: PreToolUse
Matcher: Bash
Decision: DENY（exit 2，stderr 訊息）| WARN（exit 0，stderr 訊息）| allow（無輸出）

============================================================
背景（2026-08 某次多代理人並行派發 wave 期間近失事件）
============================================================
某次並行派發 wave 執行期間，一個實作代理人為量測修復前後的測試通過數
基線而執行 `git stash`。該操作清空整個工作區，含當時另外兩個並行代理人
尚未 commit 的變更。本次 stash pop 完整還原、零遺失，屬近失事件而非
事故——但成立與否取決於時序運氣：若 pop 之前任一代理人寫入檔案，或 pop
失敗、或 session 中斷，未 commit 工作即遺失且無 reflog 可救。

同一 wave 內第二次：另一個實作代理人也用 `git stash` 做失敗歸屬鑑別
（確認多筆失敗與自身變更無關）。兩次用途不同（基線對照 / 歸因鑑別），
但都源於同一動機——並行環境下想隔離觀測。這代表 stash 不是個別代理人的
習慣，是並行環境的自然反射：**攔截而不給替代只會讓下一個人找別的危險
方法**，故本守衛的 DENY 訊息必須列出安全替代（git worktree、單檔 diff
對照），不能只攔截不給路。

既有 bare-commit-guard-hook.py 已依 dispatch-active.json 攔截並行期無
pathspec 的裸 git commit，但涵蓋範圍限於 commit。裸 commit 只是把他人
staged 檔案一併提交（內容仍在版本裡，可 revert）；本守衛涵蓋的五種操作
是把「未 commit 的內容」從工作區移除或覆寫，無版本可還原——嚴重度更高，
守衛涵蓋卻是空白（守衛擋住了較輕的、放行了較重的）。

============================================================
背景（2026-08：DENY 條件擴充，PC-019 事故鏈第四步覆蓋缺口）
============================================================
PC-019 的資料丟失發生於實作代理人「完成之後」——此時 dispatch-active.json
已清空，若 DENY 條件仍綁定「是否有派發活躍」，守衛在事故實際發生的時點
（PM 執行 stash + checkout + stash drop）恰好降級為 WARN 放行，防護在
最需要的時刻失效。本守衛防的資產是「主 repo 未提交的內容」，不是「派發
是否進行中」——兩者在事故當下不同步，故 DENY 條件由「僅綁派發活躍狀態」
擴充為「並行期 OR 主 repo 有未提交 tracked 變更」，兩條件為 OR 關係，任一
成立即 DENY。「tracked」限定：僅 tracked 檔案的未提交變更（modified /
staged 等）計入，未追蹤新檔案（`??`）不計入——後者本就不受 git 版本控制
保障，風險模型與本守衛聚焦的「無版本可還原」場景不同。

============================================================
涵蓋範圍
============================================================
1. git stash（建立形式：裸 stash / push / save，含 -u｜--include-untracked；
   排除 pop / apply / list / show / drop / clear / branch 等不清空工作區
   的子命令）
2. git checkout 丟棄整個工作區：`git checkout -- .`、`git checkout .`，
   含帶 ref 前綴形式（如 `git checkout HEAD -- .`、`git checkout main -- .`）
3. git reset --hard（--hard 不支援 pathspec，任一形式一律視為破壞全工作區）
4. git clean -f（含 -fd 等任意 force 旗標組合，不要求同時有 -d——單獨
   -f 已足以刪除未追蹤檔案，仍屬全工作區破壞性操作）
5. git restore 丟棄整個工作區：`git restore .`（預設即動 working tree）、
   含明示 `--worktree`／`--source=<ref>` 者。**例外**：`git restore
   --staged .`（僅 `--staged`，未同時帶 `--worktree`）只動 index、不動
   working tree——與其餘四種操作的風險模型不同（unstage 是可逆操作，
   `git add` 即可復原，不會遺失任何檔案內容），故不列入偵測範圍。

豁免：帶 `--` pathspec 的 stash / clean 形式（判準與 bare-commit-guard-hook
的 `_PATHSPEC_RE` 一致：`--` 前後皆為空白或字串邊界）；checkout / restore
僅在目標為獨立 `.` token（整個工作區）時觸發，指定特定檔案的形式（如
`git checkout -- src/foo.py`、`git restore -- src/foo.py`）從不匹配偵測
規則，不需額外豁免判斷。

============================================================
範疇邊界（刻意不做，非遺漏）
============================================================
- `git restore --staged .`（純 index 操作）刻意排除，理由見上「涵蓋範圍」
  第 5 項的風險模型說明。
- 與 bare-commit-guard-hook 相同：僅偵測 cwd 隱含形式與 `-C <path>` 形式，
  不解析子 shell `cd` 形式的目標 repo；dispatch 狀態與主 repo 未提交狀態
  一律讀取專案根目錄（get_project_root()，經 CLAUDE_PROJECT_DIR 恆指主
  repo，不隨 worktree 內執行時的實際 cwd 改變）。
"""

import json
import logging
import re
import sys
from pathlib import Path
from typing import Optional, Tuple

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib import setup_hook_logging, run_hook_safely, read_json_from_stdin
from lib.dispatch_tracker import get_active_dispatches
from lib.git_command_parse import strip_heredoc_bodies
from lib.git_utils import FileStatus, get_project_root, get_uncommitted_files


# 同 bare-commit-guard-hook 的 pathspec 判準：`--` 前後皆為空白或字串邊界
_PATHSPEC_RE = re.compile(r"(?:^|\s)--(?:\s|$)")

# 目標為整個工作區的獨立 `.` token（前方為空白/字串起點，後方為空白/字串
# 終點或命令鏈接符），checkout / restore 共用
_TRAILING_DOT_RE = re.compile(r"(?:^|\s)\.\s*(?:$|[;&|)])")

# 1. git stash（建立形式）
_STASH_KEYWORD_RE = re.compile(r"\bgit\s+(?:-C\s+\S+\s+)?stash\b")
_STASH_SAFE_SUBCOMMAND_RE = re.compile(
    r"\bgit\s+(?:-C\s+\S+\s+)?stash\s+(?:pop|apply|list|show|drop|clear|branch)\b"
)

# 2. git checkout -- . / git checkout .（丟棄整個工作區，含帶 ref 前綴形式）
_CHECKOUT_KEYWORD_RE = re.compile(r"\bgit\s+(?:-C\s+\S+\s+)?checkout\b")

# 3. git reset --hard
_RESET_RE = re.compile(r"\bgit\s+(?:-C\s+\S+\s+)?reset\b")
_HARD_FLAG_RE = re.compile(r"(?:^|\s)--hard\b")

# 4. git clean -f（force 旗標任意組合，含 --force；不要求同時有 -d）
_CLEAN_RE = re.compile(r"\bgit\s+(?:-C\s+\S+\s+)?clean\b")
_CLEAN_FORCE_FLAG_RE = re.compile(r"(?:^|\s)(?:--force|-[a-zA-Z]*f[a-zA-Z]*)(?:\s|$)")

# 5. git restore .（丟棄整個工作區，`--staged` 且未帶 `--worktree` 時排除）
_RESTORE_KEYWORD_RE = re.compile(r"\bgit\s+(?:-C\s+\S+\s+)?restore\b")
_STAGED_FLAG_RE = re.compile(r"(?:^|\s)(?:--staged|-[a-zA-Z]*S[a-zA-Z]*)(?:\s|$)")
_WORKTREE_FLAG_RE = re.compile(r"(?:^|\s)(?:--worktree|-[a-zA-Z]*W[a-zA-Z]*)(?:\s|$)")


def _has_pathspec_exemption(command: str) -> bool:
    """`--` pathspec 豁免（stash / clean 適用，判準與 bare-commit-guard 一致）。"""
    return bool(_PATHSPEC_RE.search(command))


def _has_whole_tree_target(command: str, keyword_re: "re.Pattern") -> bool:
    """偵測 keyword 命令是否命中 + 目標為整個工作區（末端獨立 `.` token）。

    checkout / restore 共用：兩者的破壞範圍判準相同——是否有具體 pathspec，
    只差在旗標語意（restore 另需判斷 --staged/--worktree，見 `_is_restore_wipe`）。
    """
    if not keyword_re.search(command):
        return False
    return bool(_TRAILING_DOT_RE.search(command))


def _is_stash_wipe(command: str) -> bool:
    """偵測建立形式 git stash（清空工作區），排除 pop/apply/list/show/drop/clear/branch。"""
    if not _STASH_KEYWORD_RE.search(command):
        return False
    if _STASH_SAFE_SUBCOMMAND_RE.search(command):
        return False
    return not _has_pathspec_exemption(command)


def _is_checkout_wipe(command: str) -> bool:
    """偵測 `git checkout -- .`（含帶 ref 前綴形式）（丟棄整個工作區未 commit 變更）。"""
    return _has_whole_tree_target(command, _CHECKOUT_KEYWORD_RE)


def _is_reset_hard(command: str) -> bool:
    """偵測 `git reset --hard`。--hard 不支援 pathspec，任一形式皆視為破壞全工作區。"""
    return bool(_RESET_RE.search(command) and _HARD_FLAG_RE.search(command))


def _is_clean_force(command: str) -> bool:
    """偵測 `git clean -f`（force 旗標任意組合，含 -fd；不要求同時有 -d）。"""
    if not _CLEAN_RE.search(command):
        return False
    if not _CLEAN_FORCE_FLAG_RE.search(command):
        return False
    return not _has_pathspec_exemption(command)


def _is_restore_wipe(command: str) -> bool:
    """偵測 `git restore .`（丟棄整個工作區）。

    `--staged` 且未同時帶 `--worktree` 時排除：該形式只動 index，working
    tree 內容不受影響，風險模型與其餘四種操作不同（見檔案頂端「涵蓋範圍」
    第 5 項）。
    """
    if not _has_whole_tree_target(command, _RESTORE_KEYWORD_RE):
        return False
    has_staged = bool(_STAGED_FLAG_RE.search(command))
    has_worktree = bool(_WORKTREE_FLAG_RE.search(command))
    if has_staged and not has_worktree:
        return False
    return True


# 操作名稱 -> (偵測函式, 安全形式提示｜None 表示無 pathspec 安全形式)
_OPERATIONS = [
    ("git stash", _is_stash_wipe, 'git stash push -- <file>   # 只 stash 指定檔案'),
    ("git checkout -- .", _is_checkout_wipe, 'git checkout -- <file>     # 只還原指定檔案'),
    ("git reset --hard", _is_reset_hard, None),
    ("git clean -f", _is_clean_force, 'git clean -fd -- <dir>     # 只清理指定目錄'),
    (
        "git restore .",
        _is_restore_wipe,
        'git restore -- <file>      # 只還原指定檔案\n'
        'git restore --staged .     # 僅動 index，不動 working tree，風險不同',
    ),
]


def _detect_operation(command: str) -> Optional[Tuple[str, Optional[str]]]:
    """依序檢查五種全工作區破壞性操作，回傳 (操作名稱, 安全形式提示) 或 None。

    偵測前先剝離 heredoc 本體（`strip_heredoc_bodies`，與 bare-commit-guard-hook
    透過 `find_git_invocations` 間接套用的判準一致）：本守衛對命令的「可執行
    部分」做子字串比對，heredoc 內文屬 CLI 引數的資料（如 ticket append-log
    引用一段含操作名稱的日誌原文），不是實際要執行的命令，不應觸發偵測。
    """
    if not command:
        return None
    executable_command = strip_heredoc_bodies(command)
    for name, detector, safe_hint in _OPERATIONS:
        if detector(executable_command):
            return name, safe_hint
    return None


def _get_active_dispatch_count(
    project_root: Path, logger: logging.Logger
) -> Optional[int]:
    """取得目前活躍派發數。

    讀取失敗（JSON 損毀、檔案不可讀等）時回傳 None，代表「無法判定並行
    狀態」。呼叫端須採保守處理（視為並行期阻擋），不得 fallback 為非並行
    期放行——讀檔失敗與「確實無並行派發」是兩種不同狀態，若把前者當成
    後者，等同讀檔失敗即靜默降級為不設防，與本守衛防止資料遺失的目的
    相悖。
    """
    try:
        return len(get_active_dispatches(project_root))
    except Exception:
        logger.warning(
            "讀取 dispatch-active.json 失敗，無法判定並行狀態，保守視為並行期",
            exc_info=True,
        )
        return None


def _has_main_repo_uncommitted_tracked_changes(
    project_root: Path, logger: logging.Logger
) -> Optional[bool]:
    """檢查主 repo 是否有未提交的 tracked 檔案變更（不含未追蹤新檔案）。

    僅計入 tracked 檔案的未提交變更（modified / staged 等），未追蹤新檔案
    （`??`）不計入——理由見檔案頂端「背景」章節「tracked」限定說明。

    讀取失敗（git status 執行異常等）時回傳 None，代表「無法判定」，呼叫端
    須採保守處理（視為有未提交變更、阻擋），理由同 `_get_active_dispatch_
    count`：讀檔失敗與「確實乾淨」是兩種不同狀態，若把前者當成後者，等同
    讀檔失敗即靜默降級為不設防，與本守衛防止資料遺失的目的相悖。
    """
    try:
        files = get_uncommitted_files(cwd=str(project_root))
    except Exception:
        logger.warning(
            "讀取主 repo git status 失敗，無法判定是否有未提交變更，保守視為有變更",
            exc_info=True,
        )
        return None
    return any(not f.is_untracked for f in files)


def _build_deny_message(
    op_name: str,
    safe_hint: Optional[str],
    dispatch_count: Optional[int],
    main_repo_dirty: Optional[bool],
) -> str:
    """組出 DENY 訊息：操作名稱 + 觸發理由（可多條）+ 安全替代。

    觸發理由為 OR 關係，成立的每一條都要出現在訊息中，不虛構未成立的理由
    （如僅主 repo 髒污觸發時，訊息不得聲稱「並行派發中」）。dispatch_count /
    main_repo_dirty 為 None 代表對應狀態讀取失敗，訊息改為說明「保守阻擋」
    而非引用不存在的數值。
    """
    reasons = []
    if dispatch_count is None:
        reasons.append(
            "並行派發中：無法讀取並行派發記錄（.claude/dispatch-active.json 讀取"
            "失敗），保守視為並行期阻擋"
        )
    elif dispatch_count > 0:
        reasons.append(
            f"並行派發中：目前有 {dispatch_count} 個實作代理人正在派發中"
            "（.claude/dispatch-active.json 有活躍記錄）"
        )
    if main_repo_dirty is None:
        reasons.append(
            "主 repo 有未提交變更：無法讀取主 repo 的 git status（讀取失敗），"
            "保守視為有未提交變更"
        )
    elif main_repo_dirty:
        reasons.append(
            "主 repo 有未提交變更：主 repo 存在未提交的 tracked 檔案變更"
        )
    reason_block = "\n".join(f"  - {r}" for r in reasons)

    if safe_hint:
        indented = "\n".join(f"  {line}" for line in safe_hint.splitlines())
        safe_hint_block = f"{indented}\n\n"
    else:
        safe_hint_block = ""
    return (
        f"[全工作區破壞性操作被阻擋：{op_name}]\n\n"
        f"理由：\n{reason_block}\n\n"
        "此操作會影響整個工作區，移除或覆寫尚未 commit 的變更——且無版本"
        "可還原（不同於裸 commit，stash/checkout/reset/clean/restore 動到"
        "的是未進版本控制的內容，reflog 也救不了）。\n\n"
        f"{safe_hint_block}"
        "若目的是隔離觀測（如量測修復前後基線、失敗歸因鑑別），改用不影響"
        "共用工作區的方式：\n"
        "  git worktree add ../baseline-check <ref>   # 獨立工作區跑基線對照\n"
        "  git diff -- <file>                          # 單檔 diff 對照，免動工作區\n\n"
        "確需執行本操作（刻意行為，且已確認不影響其他代理人）時，先確認"
        "主 repo 已無未提交變更（git status 乾淨），且 dispatch-active.json"
        "目前無活躍記錄或已等待其他代理人完成後再執行。\n"
    )


def _build_warn_message(op_name: str) -> str:
    """組出「非並行期且主 repo 乾淨」時的 WARN 提醒訊息（exit 0，不阻擋）。"""
    return (
        f"[提醒] 偵測到全工作區破壞性操作：{op_name}。"
        "目前無並行派發活躍記錄且主 repo 無未提交變更，本次放行；建議並行"
        "派發期間改用 git worktree 或單檔 diff 對照，避免誤動他人未 commit "
        "的變更。\n"
    )


def main() -> int:
    """Hook 主邏輯：並行期 OR 主 repo 有未提交 tracked 變更 -> DENY，兩者皆否 -> WARN。"""
    logger = setup_hook_logging("workspace-wipe-guard")

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
    command = tool_input.get("command", "") or ""

    detected = _detect_operation(command)
    if detected is None:
        logger.debug("命令不含全工作區破壞性操作，放行")
        return 0

    op_name, safe_hint = detected
    project_root = get_project_root()
    dispatch_count = _get_active_dispatch_count(project_root, logger)
    main_repo_dirty = _has_main_repo_uncommitted_tracked_changes(project_root, logger)

    is_parallel = dispatch_count is None or dispatch_count > 0
    is_main_repo_dirty = main_repo_dirty is None or main_repo_dirty

    if is_parallel or is_main_repo_dirty:
        logger.warning(
            "全工作區破壞性操作被阻擋（操作=%s，活躍派發數=%s，主 repo 未提交變更=%s）",
            op_name,
            "未知(讀取失敗，保守阻擋)" if dispatch_count is None else dispatch_count,
            "未知(讀取失敗，保守阻擋)" if main_repo_dirty is None else main_repo_dirty,
        )
        print(
            _build_deny_message(op_name, safe_hint, dispatch_count, main_repo_dirty),
            file=sys.stderr,
        )
        return 2

    logger.info("非並行期且主 repo 乾淨，全工作區破壞性操作 WARN 放行（操作=%s）", op_name)
    print(_build_warn_message(op_name), file=sys.stderr)
    return 0


if __name__ == "__main__":
    # fail_closed=True：本守衛防的是不可逆資料遺失，執行期異常時應保守 DENY
    # （exit 2）而非 fail-open 放行（見 lib.hook_logging.run_hook_safely）。
    sys.exit(run_hook_safely(main, "workspace-wipe-guard", fail_closed=True))
