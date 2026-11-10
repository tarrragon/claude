"""
bare-commit-guard 的阻擋與提醒訊息

自 bare-commit-guard-hook.py 依職責抽出。本模組只組字串，不做任何判定、
不讀檔案、不呼叫 git；DENY／WARN 的決策在 hook 檔 main()，範圍判定在
staged_scope.py。純函式，無失敗路徑。
"""

from collections import OrderedDict
from typing import Dict, List, Optional

from lib.git_command_parse import explain_parse_cause
from lib.git_operation_state import (
    _OP_CHERRY_PICK,
    _OP_MERGE,
    _OP_REBASE,
    _OP_REVERT,
    _OP_UNRESOLVABLE,
)

_UNASSIGNED_LABEL = "未宣告範圍"

_SEQUENTIAL_EXECUTION_NOTICE = (
    "以下每行須逐條分開送出執行，不可用 `&&` 或分號串成一個命令一次執行"
    "——本 hook 為 PreToolUse，依整個命令執行前的 index 狀態判斷，串接"
    "執行時看不到同一命令內尚未發生的 add／restore，前段動作不會真的"
    "執行，被擋下時容易誤以為前面步驟已經做過"
)


def _build_merge_in_progress_deny_message() -> str:
    """組出 MERGE_HEAD 存在時的 DENY 訊息。"""
    return (
        "[合併進行中，裸 commit 被阻擋]\n\n"
        "理由：偵測到 MERGE_HEAD（有未收尾的合併），裸 `git commit` 會把"
        "該合併收尾成 merge commit，若該合併非本人發起，會連同他方內容"
        "一併提交。\n\n"
        "若合併是你發起的，請改用（git merge --continue 不接受任何引數，"
        "-m／--no-edit 皆會 fatal；無 tty 環境須以 GIT_EDITOR=true 略過編輯器）：\n"
        "  GIT_EDITOR=true git merge --continue\n"
        "自訂合併訊息：先寫入 `git rev-parse --git-path MERGE_MSG` 所指的檔案，"
        "再執行上一行。\n\n"
        "若合併非你發起：請停手並回報 PM，不要自行收尾或放棄該合併。\n"
    )


def _build_unresolvable_override_deny_message() -> str:
    """GIT_DIR／--git-dir 覆寫值含變數或 ~ 時的 DENY 訊息。"""
    return (
        "[覆寫目標無法靜態解析，裸 commit 被阻擋]\n\n"
        "理由：GIT_DIR／--git-dir（或 --work-tree）的值含變數、命令替換或 ~，"
        "守衛無法在執行前得知實際目標倉庫，無法確認該處是否有未收尾的"
        "合併、cherry-pick、revert 或 rebase，保守視同有進行中操作。\n\n"
        "請把變數或 ~ 展開成字面絕對路徑後重下命令，例如：\n"
        "  GIT_DIR=/abs/path/to/repo/.git GIT_WORK_TREE=/abs/path/to/repo git commit ...\n"
        "字面路徑會逐一檢查該倉庫的進行中狀態，乾淨則放行。\n"
    )


_CONTINUE_HINTS = {
    _OP_CHERRY_PICK: ("CHERRY_PICK_HEAD", "cherry-pick", "git cherry-pick --continue", "`git rev-parse --git-path MERGE_MSG` 所指的檔案"),
    _OP_REVERT: ("REVERT_HEAD", "revert", "git revert --continue", "`git rev-parse --git-path MERGE_MSG` 所指的檔案"),
    _OP_REBASE: ("rebase-merge／rebase-apply 目錄（rebase 在衝突或中斷處停下）", "rebase", "git rebase --continue", "`git rev-parse --git-path rebase-merge/message` 所指的檔案"),
}


def _build_pending_operation_deny_message(op: str) -> str:
    """cherry-pick／revert／rebase 進行中時的 DENY 訊息；合併走原訊息。"""
    if op == _OP_MERGE:
        return _build_merge_in_progress_deny_message()
    if op == _OP_UNRESOLVABLE:
        return _build_unresolvable_override_deny_message()
    marker, noun, cont, msg_what = _CONTINUE_HINTS[op]
    return (
        f"[{noun} 進行中，裸 commit 被阻擋]\n\n"
        f"理由：偵測到 {marker}（有未收尾的 {noun}），裸 `git commit` 會把"
        f"目前 index 內容（可能含他方已 stage 的內容）併成單一 commit、"
        f"以本次 -m 取代原訊息，且{noun} 的狀態可能被清除或歷史被改寫。\n\n"
        f"若 {noun} 是你發起的，請改用（無 tty 環境須以 GIT_EDITOR=true "
        f"略過編輯器）：\n"
        f"  GIT_EDITOR=true {cont}\n"
        f"自訂訊息：先把訊息寫入 {msg_what}，再執行上一行。\n\n"
        f"若 {noun} 非你發起：請停手並回報 PM，不要自行收尾或放棄。\n"
    )


def _build_rebase_edit_warn_message() -> str:
    """rebase edit 停下時的 WARN 訊息（放行）。"""
    return (
        "[提醒] 偵測到 rebase 在 edit 停下（rebase-merge/amend 存在）。"
        "此狀態下新增 commit 是分拆 commit 的正常用法，本次放行；但該 commit "
        "會成為 rebase 歷史的一部分，若非你發起的 rebase，請確認這是你要的"
        "位置。\n"
    )


def _map_files_to_dispatches(
    content_files: List[str], dispatches: List[Dict]
) -> "OrderedDict[str, List[str]]":
    """依 content_files 逐一比對 dispatches 的 `files` 宣告，回傳
    `{ticket_id 或 未宣告範圍: [files]}`（依 content_files 原始順序分組，
    未宣告範圍固定排最後），供 DENY 訊息呈現「檔案 → 派發」映射表用。

    多個派發同時宣告同一檔案時取第一個命中者；本函式僅供訊息呈現，不
    影響 `_staged_scope_is_safe_for_bare_commit` 本身的安全性判定。
    """
    mapping: "OrderedDict[str, List[str]]" = OrderedDict()
    for f in content_files:
        owner = None
        for d in dispatches:
            if f in (d.get("files") or []):
                owner = d.get("ticket_id") or "未知票號"
                break
        key = owner or _UNASSIGNED_LABEL
        mapping.setdefault(key, []).append(f)
    if _UNASSIGNED_LABEL in mapping:
        unassigned_files = mapping.pop(_UNASSIGNED_LABEL)
        mapping[_UNASSIGNED_LABEL] = unassigned_files
    return mapping


def _build_dispatch_mapping_block(mapping: "OrderedDict[str, List[str]]") -> str:
    """組出「ticket_id: 檔案」逐行對照表文字，供 DENY 訊息呈現。"""
    lines = [
        f"  {ticket_id}: {f}" for ticket_id, files in mapping.items() for f in files
    ]
    return "\n".join(lines) if lines else "  （無內容）"


def _commit_instruction_line(ticket_key: str) -> str:
    """組出單一範圍的裸 commit 指令行。未宣告範圍的檔案改附人工核對提醒
    （其與已知範圍的關係——不相交放行路徑或他人尚未登記的隱性範圍——
    無法由本 hook 自動判定）。
    """
    if ticket_key == _UNASSIGNED_LABEL:
        return '  git commit -m "你的訊息"   # 未宣告範圍，請人工核對後再提交'
    return f'  git commit -m "<{ticket_key} 的訊息>"'


def _build_split_commit_instructions(mapping: "OrderedDict[str, List[str]]") -> str:
    """依映射表組出分次提交指令序列：先移除非首組範圍、確保首組已 add，
    提交首組；再逐組 add + commit。

    `git add` 對已 staged 的檔案為 no-op，`git restore --staged` 對未
    staged 的檔案亦為 no-op，故此序列對「純 staged」（裸 commit DENY）與
    「staged ∪ unstaged-tracked」（-a／--all DENY）兩種來源集合皆安全
    可用，不需依來源分兩套指令。
    """
    groups = list(mapping.items())
    if not groups:
        return "  （無內容可拆分）"

    lines: List[str] = []
    first_key, first_files = groups[0]
    other_files = [f for _, files in groups[1:] for f in files]
    for f in other_files:
        lines.append(f"  git restore --staged {f}")
    for f in first_files:
        lines.append(f"  git add {f}")
    lines.append(_commit_instruction_line(first_key))
    for key, files in groups[1:]:
        for f in files:
            lines.append(f"  git add {f}")
        lines.append(_commit_instruction_line(key))
    return "\n".join(lines)


def _known_scope_dispatch_counts(dispatches: List[Dict]) -> "tuple[int, int]":
    """回傳 (有宣告範圍的派發數, 範圍未知的派發數)。

    DENY 訊息呈現的代理人數須與 `_staged_scope_is_safe_for_bare_commit`
    判定實際採用的 `known_scope_sets`（濾掉 `files` 為空者）口徑一致，
    不可直接用 `len(dispatches)`——否則訊息宣稱的集合與判定依據的集合
    不是同一個（見 hook 檔 docstring「七修正」段）。
    """
    known = sum(1 for d in dispatches if d.get("files"))
    return known, len(dispatches) - known


def _dispatch_count_clause(dispatches: List[Dict]) -> str:
    """組出 DENY 訊息開頭「目前有 N 個實作代理人正在派發中」的敘述片段，
    N 取有宣告範圍的派發數；範圍未知者另行標示於括號內，不併入主要數字
    （見 `_known_scope_dispatch_counts`）。
    """
    known_count, unknown_count = _known_scope_dispatch_counts(dispatches)
    unknown_note = (
        f"（另有 {unknown_count} 筆派發記錄範圍未知，未計入判定）"
        if unknown_count
        else ""
    )
    return f"{known_count} 個實作代理人正在派發中{unknown_note}"


def _build_deny_message(staged_files: List[str], dispatches: List[Dict]) -> str:
    """組出裸 commit 的 DENY 訊息：staged 清單未落在任一活躍派發宣告範圍內、
    也與所有活躍派發宣告範圍相交（見 `_staged_scope_is_safe_for_bare_commit`
    兩條放行路徑），列出每個 staged 檔案的歸屬派發 ticket_id，並給出依
    範圍拆分的具體分次 commit 指令。
    """
    dispatch_count_clause = _dispatch_count_clause(dispatches)
    if staged_files:
        mapping = _map_files_to_dispatches(staged_files, dispatches)
        mapping_block = _build_dispatch_mapping_block(mapping)
        instructions_block = _build_split_commit_instructions(mapping)
    else:
        mapping_block = "  （無法讀取，可能不在 git repo 或無 staged 變更）"
        instructions_block = "  （無 staged 內容可拆分）"

    return (
        "[並行派發期間裸 commit 被阻擋]\n\n"
        f"理由：目前有 {dispatch_count_clause}"
        "（.claude/dispatch-active.json 有活躍記錄），且目前 staged 內容"
        "既非任一活躍派發宣告檔案範圍的子集，也與所有活躍派發宣告範圍的"
        "聯集相交，裸 git commit 會把共用 git index 中可能屬於其他人的"
        "staged 檔案一併提交，造成跨 ticket 汙染。\n\n"
        "當前 staged 檔案與其歸屬派發範圍：\n"
        f"{mapping_block}\n\n"
        "建議依範圍拆分為多次裸 commit（各自皆會通過放行路徑一，"
        f"{_SEQUENTIAL_EXECUTION_NOTICE}）：\n"
        f"{instructions_block}\n\n"
        "核對指令：\n"
        "  git diff --cached --name-only            # 核對 index 實際範圍\n"
        "  git restore --staged <非本票檔案>          # 逐一移除非本票內容\n\n"
        "（不要改用 `-- <pathspec>` / `--only` / `-o`——那會丟棄 index、"
        "改讀 working tree 全文，同樣會吸入他人未 stage 的編輯，危害更大；"
        "也不建議用 `git commit -a` 繞過拆分——並行期 `-a` 同樣套用本節"
        "內容安全性驗證，範圍仍需落在單一派發宣告內才會放行）\n"
    )


def _build_all_flag_deny_message(content_files: List[str], dispatches: List[Dict]) -> str:
    """組出 `-a`／`--all` commit 在並行期內容不安全時的 DENY 訊息。驗證
    對象是 `-a` 實際會提交的完整集合（staged ∪ unstaged-tracked），非僅
    staged（見 hook 檔 docstring「六修正」段：並行期收窄為與裸 commit 相同的
    內容安全性驗證）。
    """
    dispatch_count_clause = _dispatch_count_clause(dispatches)
    if content_files:
        mapping = _map_files_to_dispatches(content_files, dispatches)
        mapping_block = _build_dispatch_mapping_block(mapping)
        instructions_block = _build_split_commit_instructions(mapping)
    else:
        mapping_block = "  （無法讀取，可能不在 git repo）"
        instructions_block = "  （無內容可拆分）"

    return (
        "[並行派發期間 -a／--all commit 被阻擋]\n\n"
        f"理由：目前有 {dispatch_count_clause}"
        "（.claude/dispatch-active.json 有活躍記錄）。`git commit -a` 會"
        "提交 staged 與未 staged 的所有已追蹤檔案修改，這個完整集合可能"
        "跨越多個派發宣告範圍，等同裸 commit 的跨 ticket 汙染風險，故並行"
        "期改套用與裸 commit 相同的內容安全性驗證，不再無條件豁免。\n\n"
        "-a 實際會提交的檔案與其歸屬派發範圍：\n"
        f"{mapping_block}\n\n"
        "建議改用精確 add + 裸 commit，依範圍拆分為多次提交（不要用 -a"
        f"一次提交，各自皆會通過放行路徑一，{_SEQUENTIAL_EXECUTION_NOTICE}）：\n"
        f"{instructions_block}\n"
    )


def _build_warn_message() -> str:
    """組出非並行期裸 commit 的 WARN 提醒訊息（exit 0，不阻擋）。"""
    return (
        "[提醒] 偵測到裸 git commit。目前無並行派發活躍記錄，本次放行；"
        "建議養成「commit 前先核對 staged 範圍」的習慣，以防未來並行期"
        "誤觸跨 ticket 汙染（不要用 `-- <pathspec>` / `--only` / `-o` 限縮"
        "範圍，那會丟棄 index 改讀 working tree 全文，風險更高）：\n"
        "  git diff --cached --name-only   # 核對 index 只含你的檔案\n"
    )


def _build_index_discarding_deny_message(dispatch_count: int) -> str:
    """組出 index-discarding form（pathspec / --only / -o）的 DENY 訊息。

    `dispatch_count` 直接取全部活躍派發記錄數（不濾掉 `files` 為空者）：
    本函式的觸發判準是「`dispatch_count > 0` 即一律阻擋」，並未經
    `known_scope_sets` 過濾，訊息數字與判定依據本就是同一個集合，與
    裸 commit／`-a` 兩則訊息的口徑不一致問題無關（見 hook 檔 docstring
    「七修正」段）。
    """
    return (
        "[並行派發期間 pathspec/--only/-o commit 被阻擋]\n\n"
        f"理由：目前有 {dispatch_count} 個實作代理人正在派發中"
        "（.claude/dispatch-active.json 有活躍記錄）。`git commit -- "
        "<pathspec>` 與 `--only`/`-o` 會丟棄既有 index，改以指定路徑當下的"
        "working tree 內容重建臨時 index 後提交——不是從 index 挑選子集，"
        "而是完全繞過 index。並行環境下這會吸入同路徑上其他派發代理人"
        "尚未 stage 的編輯，且無法像裸 commit 一樣用 staged 快照驗證安全性"
        "（提交當下才讀 working tree），故一律阻擋，不提供例外。\n\n"
        f"請改用精確 add + 核對 + 裸 commit（{_SEQUENTIAL_EXECUTION_NOTICE}）：\n"
        "  git add <你的確切檔案>\n"
        "  git diff --cached --name-only   # 核對 index 只含你的檔案\n"
        '  git commit -m "你的訊息"        # 裸 commit（不帶 pathspec）\n\n'
        "若裸 commit 仍被本 hook 阻擋，代表 index 混入非本票內容，先用"
        "`git restore --staged <path>` 移除後再重試。\n"
    )


def _build_parse_failure_deny_message(dispatch_count: int, cause: Optional[str] = None) -> str:
    """組出「命令含 git 字樣但無法安全解析」的 DENY 訊息（並行期）。

    無法安全解析時（`find_git_invocations` 回傳 None，見共用模組「失敗
    語意」段），本 hook 無從確認該命令是否為裸 commit 或其安全性，並行
    期間保守阻擋，非並行期改 WARN（見 `_build_parse_failure_warn_message`）。
    """
    return (
        "[並行派發期間裸 commit 被阻擋（命令無法安全解析）]\n\n"
        f"理由：目前有 {dispatch_count} 個實作代理人正在派發中"
        "（.claude/dispatch-active.json 有活躍記錄），且本次命令含 git"
        "字樣，但無法安全解析其結構，無法確認是否為"
        "裸 commit 或其安全性，故保守阻擋。\n\n"
        f"{explain_parse_cause(cause)}修正後重試。\n"
    )


def _build_parse_failure_warn_message(cause: Optional[str] = None) -> str:
    """組出「命令含 git 字樣但無法安全解析」的 WARN 訊息（非並行期）。"""
    return (
        "[提醒] 本次命令含 git 字樣，但無法安全解析其結構。"
        "目前無並行派發活躍記錄，本次放行。"
        f"{explain_parse_cause(cause)}"
        "並行期同類命令會被阻擋。\n"
    )


def _build_index_discarding_warn_message() -> str:
    """組出非並行期 index-discarding form 的 WARN 訊息（exit 0，不阻擋）。"""
    return (
        "[提醒] 偵測到 `git commit -- <pathspec>` / `--only` / `-o`。"
        "此語法會丟棄既有 index、改讀指定路徑當下的 working tree 內容"
        "提交，不是「從 index 挑選子集」；目前無並行派發活躍記錄，本次"
        "放行，但不建議養成此習慣（未來並行期會吸入他人未 stage 的編輯，"
        "且並行期間本 hook 會直接阻擋此語法）。建議改用：\n"
        "  git add <你的確切檔案>\n"
        "  git diff --cached --name-only   # 核對 index 只含你的檔案\n"
        '  git commit -m "你的訊息"        # 裸 commit\n'
    )
