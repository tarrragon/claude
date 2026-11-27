#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml"]
# ///

"""
Bash Write Boundary Guard Hook - PreToolUse Hook

main-thread-edit-restriction-hook.py 僅註冊於 PreToolUse 的 Edit/Write/MultiEdit
matcher，禁止主線程（PM）寫入 test/、lib/、*.dart。該限制可被 Bash 寫入操作
（heredoc / cat > / cat >> / tee / sed -i / python 內嵌腳本 open() / cp / mv）
完全繞過，繞過後無留痕、無法事後偵測（來源分析結論：職責邊界執法類 guard，
繞過後不可事後偵測，須以 PreToolUse 層攔截，不能靠事後補救）。本 hook 是該
缺口的補網。

觸發時機: 執行 Bash 工具時
行為: 偵測到明確寫入 test/、lib/、*.dart 的 Bash 語法 → 轉呼
      lib/path_permission.check_file_permission() 判斷 → 不允許則 DENY（exit 2）；
      未偵測到明確寫入目標 → 一律 ALLOW（保守白名單策略，fail-open）。

兩層檢查：
- 第一層（主線程與代理人皆適用，不受開發分支跳過影響）：候選路徑以 payload cwd
  解析、換算成所在 checkout 根目錄的相對路徑，落在 lib/、test/、integration_test/、
  .claude/** 即 DENY。豁免：建置快取（.venv、__pycache__ 等）、.claude 本地執行期
  產物（hook-logs、dispatch-active.json 等，清單對齊 .gitignore）、.git/、
  checkout 外路徑（暫存區、/dev/null）、git mv。ticket／doc CLI 自寫檔不經 shell
  重導向，命令文字無目標路徑，不受影響。
- 第二層（僅主線程；與 main-thread-edit-restriction-hook.py 一致）：轉呼
  check_file_permission，開發分支（feat/*、fix/* 等）跳過
- 失敗語意 fail_closed：解析例外或分派層逾時時擋下
- 殘留風險清單（靜態解析 fail-open，未偵測）：
  直譯器內動態組成、且命令與原始碼都沒有受限路徑線索的寫入目標（不擋，以
  additionalContext 警告放行；有線索時以線索路徑判定範圍）；腳本檔內目標無法判定的寫入
  （不走線索、不警告：既有腳本參數常含 .claude/ 路徑，套用線索會誤擋例行包裝命令）；
  腳本以 python -m 模組形態執行；同一命令內先寫腳本再執行（PreToolUse 時腳本尚不存在，
  只剩 argv 的字面路徑線索）；
  值含其他變數或命令替換的 $VAR（同命令內的字面賦值、~、$HOME、$(pwd) 前綴已展開）；
  bash -c／eval 的非字面引數；
  awk -i inplace、ruby、install、truncate、patch、tar -C、dd of=、rsync、ln -s、
  touch、curl -o 與版本控制的還原類子命令（命令集合為列舉式）
- 不含跨專案判斷：Bash command 無單一 file_path，無法用
  find_target_repo() 判斷目標 repo；candidate path 皆以當前
  CLAUDE_PROJECT_DIR 正規化，跨專案 Bash 寫入若剛好命中
  test/lib/dart pattern 仍會被攔（已知的偏保守行為，優先度低於
  漏放）

偵測形態：
- cat > path / cat >> path（含 heredoc 重導向 `cat > path <<'EOF' ... EOF`）
- tee path / tee -a path
- sed -i ... path / sed --in-place ... path（原地編輯目標）
- python -c / python3 heredoc 內嵌腳本中的 open('path', ...) 呼叫
- cp src dst / mv src dst（目的地路徑；mv 的來源也算，移出等同刪除原位置）
- rm／unlink 的引數（路徑段含快取、hook-logs、.git、.github 者略過）
- 一般輸出重導向 > path / >> path（排除檔案描述符重導向 2>、&>）
- ed／ex 的檔案引數（編輯指令經 stdin 或 -c 送入，w／x 寫回該檔）
- python 腳本檔形態 python3 [選項] script.py args：腳本讀得到時以 ast 分析，
  只採可判定的寫入目標（常數或 argv 展開）；讀不到時 argv 中受限範圍的字面路徑納入候選
- node -e／--eval 腳本字串內 writeFileSync、appendFileSync 等 fs 寫入的字面路徑

共用介面：iter_checkout_write_targets(command, cwd) 逐候選產生 checkout 相對路徑，
bash-edit-guard-hook.py 同由 lib/bash_write_targets.py 取用，兩支守衛的寫入目標判定同源。

解析方式：
命令以單趟字元走訪切成「陳述 -> token」，每個字元只看一次，整體 O(n)，
不使用有回溯風險的複合正則（sed 判定用的正則曾兩度因回溯耗時形成逾時繞過）。
- heredoc 正文與引號內文字不是命令：不進入 token 走訪，描述寫入的文字不誤擋
- 例外：陳述的命令為 python* 時，其原文與 heredoc 正文掃描 open() 呼叫；
  命令為 sh/bash/zsh 時，heredoc 正文會被執行，遞迴解析（深度 2）
- bash -c '...' 字串內的寫入不在本 hook 範圍

FP 邊界（fail-open，保守白名單原則）：
抽出候選路徑後僅在正規化後命中 test/、lib/、*.dart 才轉呼判斷邏輯；
未命中或無法辨識寫入語法一律放行，不做「default deny」。
不設命令長度上限：解析為線性，長度上限只會增加誤擋面（大型 heredoc 正文
合法存在），不增加防護。
"""

import os
import sys
from pathlib import Path
from typing import List, Optional

sys.path.insert(0, str(Path(__file__).parent))         # .claude/hooks/
sys.path.insert(0, str(Path(__file__).parent.parent))   # .claude/       (lib.*)

from lib import setup_hook_logging, run_hook_safely, read_json_from_stdin, is_subagent_environment, emit_hook_output
from lib.git_utils import get_current_branch, is_allowed_branch
from lib.path_permission import check_file_permission, normalize_path
from lib.bash_write_targets import (
    _extract_candidate_paths,
    _scope_hit,
    iter_checkout_write_targets,
)

EXIT_ALLOW = 0
EXIT_BLOCK = 2


def _find_boundary_violation(command: str, logger) -> Optional[str]:
    """
    掃描命令的所有候選寫入路徑，回傳第一個命中 test/、lib/、*.dart 且
    check_file_permission 判定不允許的正規化路徑；無命中回傳 None。

    Args:
        command: Bash 命令
        logger: hook logger

    Returns:
        Optional[str] - 命中的正規化路徑，或 None
    """
    for raw_path in _extract_candidate_paths(command):
        normalized = normalize_path(raw_path)

        # 窄化門檻：僅 test/、lib/、*.dart 才進一步判斷（本票範圍，
        # 避免抽取雜訊觸發 check_file_permission 的 default-deny 分支）
        is_target_scope = (
            normalized.startswith("test/")
            or normalized.startswith("lib/")
            or normalized.endswith(".dart")
        )
        if not is_target_scope:
            continue

        is_allowed, reason = check_file_permission(raw_path, logger)
        if not is_allowed:
            logger.warning(
                "偵測到 Bash 寫入職責邊界違規: path=%s reason=%s command=%s",
                normalized, reason, command,
            )
            return normalized

    return None



def _find_scope_violation(command: str, cwd: str, logger,
                          skipped: Optional[List[str]] = None,
                          opaque: Optional[List[str]] = None) -> Optional[str]:
    """
    回傳第一個落在 lib/、test/、integration_test/、.claude/**（扣除豁免）的候選寫入路徑
    （換算成 checkout 相對路徑）；無命中回傳 None。

    候選路徑相對於 cwd（含命令內 cd 位移）解析，再換算成所在 checkout 根目錄
    （worktree 另加其主 checkout）的相對路徑比對，因此 worktree 內的 lib/x 也會命中。
    無法靜態判定的路徑（其他變數、命令替換、字串拼接）放行，見模組檔頭殘留風險。
    cwd 不在任何 checkout 內時，以 CLAUDE_PROJECT_DIR 所屬 checkout 為比對基準
    （未設定則維持以 cwd 為基準）。
    skipped 非 None 時，逐候選追加 "<raw>:<unresolvable|out_of_scope>"（命中者不列）。
    """
    def skip(raw: str, why: str) -> None:
        if skipped is not None:
            skipped.append("%s:%s" % (raw, why))

    for raw, rel, why in iter_checkout_write_targets(command, cwd, opaque):
        if rel is None:
            skip(raw, why)
            continue
        if not _scope_hit(rel):
            skip(raw, "out_of_scope")
            continue
        logger.warning("偵測到 Bash 寫入受限路徑: path=%s cwd=%s command=%s", rel, cwd, command)
        return rel
    return None


_LOG_CMD_LIMIT = 200  # 判定日誌的命令截斷上限，heredoc 正文不全文入日誌


def _decision_source(input_data: dict) -> str:
    """來源：沿用 is_subagent_environment 判定；代理人取 agent_id（缺則 agent_type），否則 main。"""
    if is_subagent_environment(input_data):
        return "agent:%s" % (input_data.get("agent_id") or input_data.get("agent_type") or "unknown")
    return "main"


def _log_decision(logger, decision: str, input_data: dict, reason_code: str,
                  command: str, targets: Optional[List[str]] = None,
                  skipped: Optional[List[str]] = None) -> None:
    """每個放行／阻擋分支記一行穩定可 grep 的判定：
    decision=<allow|deny> source=<main|agent:ID> reason=<code> targets=[...] skipped=[...] cmd=<前 200 字元>
    targets 為 None 時才即時抽取候選目標（抽取失敗記空，不影響判定）。
    skipped 為路徑範圍檢查逐候選的跳過原因（"<raw>:out_of_scope|unresolvable"），未檢查時為空。"""
    if targets is None:
        try:
            targets = _extract_candidate_paths(command) if command else []
        except Exception:  # 日誌輔助不得改變判定；失敗以空目標記錄
            targets = []
    cmd = command[:_LOG_CMD_LIMIT].replace("\n", "\\n")
    logger.info(
        "decision=%s source=%s reason=%s targets=%s skipped=%s cmd=%s",
        decision, _decision_source(input_data), reason_code, list(targets), list(skipped or []), cmd,
    )


def _opaque_write_warning(opaque: List[str]) -> Optional[str]:
    """寫入目標不明的 python 陳述的模型可見警告；無則 None。"""
    if not opaque:
        return None
    return (
        "[bash-write-boundary-guard] 放行，但偵測到 python 寫入呼叫的目標路徑無法靜態判定"
        f"（{opaque[0]}）。本 hook 無法確認它是否寫入 lib/、test/、integration_test/、.claude/**。"
        "若寫入對象是這些範圍或 docs/ 等受管檔案，改用 Edit／Write；"
        "寫入暫存區請讓路徑以字面寫出（如 /tmp/...）。"
    )


def _allow_and_exit(logger, reason: str, input_data: Optional[dict] = None,
                    reason_code: str = "", command: str = "",
                    skipped: Optional[List[str]] = None,
                    opaque: Optional[List[str]] = None) -> int:
    _log_decision(logger, "allow", input_data or {}, reason_code, command, None, skipped)
    warning = _opaque_write_warning(opaque or [])
    if warning:
        # 警告路徑只送 additionalContext，不帶 permission_decision：不擴大略過權限提示的範圍
        logger.info("opaque_write_warning count=%d first=%s", len(opaque), opaque[0][:80].replace("\n", "\\n"))
        emit_hook_output("PreToolUse", additional_context=warning)
        return EXIT_ALLOW
    # 放行不輸出 decision：allow 會略過平台的權限提示，等於代用戶核可
    logger.debug("放行不輸出 decision：%s", reason)
    return EXIT_ALLOW


def main() -> int:
    """
    主入口點

    流程: 初始化 → 讀取輸入 → 工具/subagent/分支/跨專案過濾 → 候選路徑抽取
          → 命中則轉呼 check_file_permission → 輸出
    """
    logger = setup_hook_logging("bash-write-boundary-guard")

    logger.info("Bash Write Boundary Guard Hook 啟動")

    input_data = read_json_from_stdin(logger)
    if not input_data:
        logger.debug("輸入為空或解析失敗，返回預設允許")
        return _allow_and_exit(logger, "輸入為空，預設允許", {}, "empty_input")

    tool_name = input_data.get("tool_name", "")
    tool_input = input_data.get("tool_input") or {}

    if tool_name != "Bash":
        logger.debug(f"跳過: 工具類型 {tool_name} 不是 Bash")
        return _allow_and_exit(logger, f"工具 {tool_name} 不在檢查範圍", input_data, "non_bash_tool")

    command = tool_input.get("command", "")
    if not command:
        return _allow_and_exit(logger, "command 為空，允許", input_data, "empty_command")

    # 第一層：路徑範圍阻擋，主線程與代理人皆適用，不受開發分支跳過影響
    # （feat/* worktree 內若跳過，整層即失效）
    cwd = input_data.get("cwd") or os.getcwd()
    skipped: List[str] = []
    opaque: List[str] = []
    scope_path = _find_scope_violation(command, cwd, logger, skipped, opaque)
    if scope_path is not None:
        who = "代理人" if is_subagent_environment(input_data) else "主線程"
        reason = (
            f"Bash 寫入受限路徑被擋下（path={scope_path}，呼叫身份={who}）。"
            "lib/、test/、integration_test/、.claude/** 禁止透過 Bash"
            "（cat/printf/tee/sed -i/python open()/cp/mv/重導向）寫入。"
            "請改用 Edit 或 Write 工具修改檔案；搬移已追蹤的檔案用 git mv，刪除已追蹤的檔案用 git rm"
            "（mv 的來源與 rm／unlink 的引數同樣受限）；未追蹤的檔案需要刪除或移出時停手回報。"
            "不得改用其他 Bash 寫法（python heredoc、argv 傳路徑、腳本檔等）重試同一寫入；"
            "Edit／Write 不可用時停手，於 ticket NeedsContext 記錄並回報 PM。"
            "依行範圍搬移文字（拆檔、移段落）改用 "
            "ticket track move-lines <ticket-id> --src … --lines A-B --dst … --at N；"
            "src 與 dst 須在該票 where.files 內，無票或檔案不在範圍內時不適用。"
            "lib/ 等處的建置快取（.dart_tool 等）與少數無讀取方的 .claude 本地產物不受此限。"
            "用戶以 ! 前綴自行執行的命令不經過本 hook，不受此限制。"
            "若是本 hook 自身異常而誤擋正常命令，改用 Edit 修正 "
            ".claude/hooks/bash-write-boundary-guard-hook.py（Edit 不受本 hook 影響）。"
        )
        _log_decision(logger, "deny", input_data, "scope_violation", command, [scope_path], skipped)
        emit_hook_output(
            "PreToolUse",
            permission_decision="deny",
            permission_decision_reason=reason,
        )
        logger.info("Hook 檢查完成（路徑範圍阻擋），exit code: %d", EXIT_BLOCK)
        return EXIT_BLOCK

    # 第二層（僅主線程）：PM 可寫路徑模型。Subagent 的 lib/test 寫入權責由
    # 第一層決定，不套用 PM 模型
    if is_subagent_environment(input_data):
        logger.info(f"subagent 環境（agent_id={input_data.get('agent_id')}），路徑範圍檢查通過")
        return _allow_and_exit(logger, "subagent 的 Bash 寫入未命中受限路徑", input_data, "subagent_no_scope_hit", command, skipped, opaque)

    # 開發分支跳過（feat/*, fix/* 等），與 main-thread-edit-restriction 一致；
    # 僅作用於第二層
    current_branch = get_current_branch()
    if current_branch and is_allowed_branch(current_branch):
        logger.info(f"開發分支 '{current_branch}' 上，跳過 Bash 寫入邊界限制")
        return _allow_and_exit(
            logger, f"開發分支 '{current_branch}' 不受主線程 Bash 寫入邊界限制",
            input_data, "dev_branch_skip", command, skipped, opaque,
        )

    violation_path = _find_boundary_violation(command, logger)

    if violation_path is None:
        logger.debug("未偵測到明確的 test/lib/dart 寫入目標，允許（fail-open）")
        return _allow_and_exit(logger, "未偵測到職責邊界違規的 Bash 寫入形態", input_data, "no_boundary_violation", command, skipped, opaque)

    reason = (
        f"偵測到 Bash 寫入職責邊界違規（path={violation_path}）。"
        "主線程禁止透過 Bash（cat/tee/sed -i/python open()/cp/mv/heredoc 等）"
        "寫入 test/、lib/、*.dart，等同繞過 main-thread-edit-restriction-hook.py "
        "的職責邊界執法。請改派代理人執行此寫入。"
    )
    _log_decision(logger, "deny", input_data, "boundary_violation", command, [violation_path])
    emit_hook_output(
        "PreToolUse",
        permission_decision="deny",
        permission_decision_reason=reason,
    )
    logger.info("Hook 檢查完成，exit code: %d", EXIT_BLOCK)
    return EXIT_BLOCK


if __name__ == "__main__":
    # fail_closed：此守衛的失效方向是放行；解析異常或分派層逾時時擋下，
    # 理由與負載實測見票面 Solution
    sys.exit(run_hook_safely(main, "bash-write-boundary-guard", fail_closed=True))
