#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml"]
# ///
"""
Commit Stage Guard Gate Hook - PreToolUse Hook（Bash matcher）

功能: commit 階段補網。既往分析（來源分析票，見同波次 ANA 結論）實測確認
      13 個僅註冊於 Edit/Write/MultiEdit 的 PreToolUse guard 對 Bash 寫入
      （heredoc / sed -i / python3 內嵌腳本等）全數繞過。其中 B 組（12 支
      「內容正確性」guard）繞過後仍留痕於檔案內容，可於 commit 前補一道
      關卡事後掃描 staged 內容，轉呼各 guard 既有的判斷函式（不重寫邏輯）。
      A 組（main-thread-edit-restriction，職責邊界執法）繞過後不留痕，
      不屬本票範圍，由同波次另一 IMP 票承接。

Hook Event: PreToolUse
Matcher: Bash
觸發條件: 命令含真實 `git commit` 呼叫（find_git_invocations，與
          bare-commit-guard-hook.py 共用同一套 argv 結構解析，非字串
          子字串比對，避免 payload/heredoc 內文誤判）。
Decision: 任一 guard 產出 deny 級發現 -> exit 2（阻擋 commit，stderr
          附逐項發現與修正指引）；僅 WARN 級發現 -> exit 0（stderr 提示，
          不阻擋）；皆無發現 -> 靜默 exit 0。

已知涵蓋邊界（掃描點綁「命令」而非「ref 寫入事件」）: 本 hook 只在命令字
面含 `git commit` 時觸發，對「不經 `git commit` 而直接寫入 ref」的路徑
零命中——包含隔離索引提交（`commit-tree` + `update-ref`，`ticket track
commit` 與 `ticket-md-auto-commit-hook.py` 皆走此路徑）與 `git merge
--continue`。此邊界已由另一承載體
`.claude/hooks/git-ref-transaction-content-guard.py`（掛 `.git/hooks/
reference-transaction` 原生 git hook，綁「ref 寫入」事件本身而非任何命令
字面）補齊，兩者共用 `lib/commit_content_guards.py` 的檢查邏輯，互為補充
不互相取代——本 hook 在 `git commit` 執行前即可攔截並即時回饋，
reference-transaction 版本則涵蓋所有寫入 ref 的路徑但只在 ref 交易
`prepared` 階段才能中止。完整覆蓋範圍盤點見
`.claude/references/rule-enforcement-binding-points.md`。

============================================================
掃描對象與內容重建
============================================================
掃描對象為 `git diff --cached --name-only --diff-filter=ACMR` 的 staged
檔案清單（新增/修改/rename，已刪除檔案略過，見 `_get_staged_file_list`）。
rename 檔案（含純 rename 與 rename 併內容變更）不略過，改以 `git diff
--cached -M --name-status` 取得舊路徑對照表（見 `_get_staged_rename_map`），
三種重建文字對 rename 檔案改採下列基準：
  - pre_text：一般檔案為 `git show HEAD:<path>`（新檔則為空字串）；rename
    檔案改用 `git show HEAD:<old_path>`（rename 前的舊路徑），對應各原
    guard「編輯前磁碟內容」的角色。純 rename 因 pre_text 與 post_text
    內容相同，diff 淨增量自然為零，不需額外豁免路徑。
  - post_text：`git show :<path>`（index 中的 staged 內容，非 working
    tree），對應各原 guard Write 工具 content 的角色。
  - added_text：一般檔案為 `git diff --cached -- <path>`；rename 檔案改
    用 `git diff --cached -M -- <old_path> <path>`（同時帶回舊路徑作
    pathspec，使 git 能配對 rename 對；僅給新路徑會讓 rename 退化為整檔
    新增，是本票修復的根因）。抽出以單一 `+` 開頭（非 `+++`）的行，對應
    各原 guard Edit/MultiEdit new_string 的角色（僅涵蓋「本次變更新增」
    的片段，非全檔案，維持與原 guard 一致的防呆設計——只掃變更內容不誤觸
    既有存量）。

============================================================
12 支既有 guard 的轉呼方式（逐一列於各 `_check_*` 函式 docstring）
============================================================
以下對照表為「產生路徑盤點表」（acceptance-gate 四項必含之一）：完整 12
支 guard 分別對應下方哪個 `_check_*` 函式，以及各自的轉呼策略類別。

| # | Guard（原檔案）                                        | 轉呼函式                    | 策略 |
|---|--------------------------------------------------------|------------------------------|------|
| 1 | reference-stability-rule8-guard-hook.py                | `_check_rule8`               | 完整重用（diff_new_hits + filter_marker_exempt + build_block_message） |
| 2 | uc-reference-validation-hook.py                        | `_check_uc_reference`        | 完整重用（doc_system.core.uc_registry 直接 import，WARN-only 保留原語意） |
| 3 | file-type-permission-hook.py                           | `_check_file_type_permission`| 無 deny 路徑，no-op（原 hook 本身從不阻擋，記錄於 docstring 供稽核） |
| 4 | branch-verify-hook.py                                  | `_check_branch_verify`       | 完整重用（is_protected_branch + is_exempt_path_on_protected_branch） |
| 5 | error-pattern-flat-gate-hook.py（skills/error-pattern） | `_check_error_pattern_flat`  | 完整重用（`decide()` 純函式，直接以 tool_name="Write" 呼叫） |
| 6 | framework-rule-edit-skill-trigger-hook.py               | `_check_framework_skill_trigger` | 簡化重用：commit 階段無 transcript 可核實是否已讀 SKILL，降級為固定 WARN（不比照原 hook 的 strict deny），已於函式 docstring 說明限制 |
| 7 | memory-write-guard-hook.py                              | `_check_memory_write`        | 完整重用（is_memory_path，路徑判斷；memory 目錄本不在專案 git 內，恆為 no-op，保留以防未來路徑定義變動） |
| 8 | presence-detection-hook.py                              | `_check_presence_detection`  | 完整重用（get_profile_for_path + should_skip_file + detect_violations + build_block_message，掃描對象改用 added_text） |
| 9 | proposal-evaluation-gate-hook.py                        | `_check_proposal_evaluation` | 完整重用（is_target_file + parse_frontmatter + check_prop_content + check_tracking_yaml；old_status 由 pre_text frontmatter 推導取代原 tool_input 依賴） |
| 10| suggest-compact.py                                      | （無對應函式）                | 排除：純 session 步調建議（tool-call 計數），與檔案內容正確性無關，非 commit 補網範疇 |
| 11| ticket-path-guard-hook.py（skills/ticket）              | `_check_ticket_path`         | 完整重用（is_forbidden_ticket_path） |
| 12| wrap-skill-yaml-consistency-hook.py（skills/wrap-decision）| `_check_wrap_skill_yaml`  | 完整重用（`_is_watched` + `load_alignment` + `load_yaml_config` + `check_signal_orphan` + `check_keyword_orphan` + `check_version_no_regress`，皆讀磁碟現況，不依賴 tool_input） |

第 3、10 項無實際攔截邏輯可轉呼（原 hook 從不 deny／與內容無關），計入
「12 支」是因來源分析票原始分組清單即含此二者；本票如實記錄其 no-op
狀態而非虛構檢查邏輯，避免產生假的防護錯覺。

============================================================
已知邊界（刻意不做，非遺漏）
============================================================
- 對「寫入後未 commit 即讀取/交接」的中間狀態無防護（來源分析票候選
  方案 c 評估已載明此限制，接受此邊界換取比 PostToolUse 更低的誤判成本）。
- `framework-rule-edit-skill-trigger` 於 commit 階段無法核實 SKILL 是否
  已讀（transcript_path 屬 session 概念，commit 事件無對應可靠依據），
  降級為固定 WARN，不做 strict deny（避免無法驗證的假陽性阻擋 commit）。
- 各 guard 若在原始 PreToolUse 語境下依賴 `tool_input`（如 Edit 的
  old_string/new_string 部分替換語意）之處，本 hook 一律改用「整檔
  pre/post/added 文字」近似，可能與原 hook 逐次 Edit 呼叫的精確重建結果
  有微小差異（例如 MultiEdit 多段 edits 各自失敗重建的保守退化行為，
  commit 階段以完整 staged 內容取代，不重現該退化分支）。方向安全（多掃
  不會漏掃，僅可能對已豁免的既有存量誤增判斷成本，已透過 pre/post diff
  比對抵銷此風險，見 `_check_rule8`）。
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, List, Optional

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib import setup_hook_logging, run_hook_safely, read_json_from_stdin  # noqa: E402
from lib.git_command_parse import find_git_invocations, contains_git_word  # noqa: E402
from lib.git_utils import get_project_root, run_git_command  # noqa: E402
from lib.commit_content_guards import (  # noqa: E402
    Finding,
    StagedFile,
    _load_module,
    _check_rule8,
    _check_uc_reference,
    _check_file_type_permission,
    _check_branch_verify,
    _check_error_pattern_flat,
    _check_framework_skill_trigger,
    _check_memory_write,
    _check_presence_detection,
    _check_proposal_evaluation,
    _check_ticket_path,
    _check_wrap_skill_yaml,
    _run_all_checks,
    _build_deny_message as _build_deny_message_body,
    _build_warn_message as _build_warn_message_body,
)

EXIT_ALLOW = 0
EXIT_BLOCK = 2

_HOOKS_DIR = Path(__file__).resolve().parent
_CLAUDE_DIR = _HOOKS_DIR.parent

# Finding / StagedFile / _load_module / 12 支 guard 轉呼函式 / _run_all_checks
# 已抽出至 lib/commit_content_guards.py，供本檔（PreToolUse，掃 index）與
# git-ref-transaction-content-guard.py（reference-transaction，掃已提交
# commit）共用；此處僅 re-export 以維持既有測試（test_commit_stage_guard_
# gate_hook.py 以 `hook_module.StagedFile` / `hook_module._check_rule8`
# 等既有路徑存取）向後相容，邏輯本體見該 lib 模組。


def _get_staged_file_list(project_root: Path) -> List[str]:
    """取得 staged 檔案清單（新增/修改/rename，已刪除檔案略過）。"""
    success, output = run_git_command(
        ["diff", "--cached", "--name-only", "--diff-filter=ACMR"],
        cwd=str(project_root),
    )
    if not success or not output:
        return []
    return [line.strip() for line in output.splitlines() if line.strip()]


def _get_staged_rename_map(project_root: Path) -> Dict[str, str]:
    """取得本次 staged 變更中 rename 檔案的新路徑 -> 舊路徑對照表（含純
    rename 與 rename 併內容變更）。`-M` 顯式開啟 rename 偵測（不依賴 git
    版本/組態預設值）；`--name-status` 逐行輸出 `狀態<TAB>舊路徑<TAB>新路徑`
    （R 開頭後接相似度百分比，如 R100/R063，皆視為 rename）。非 rename 的
    行只有兩欄，split 後長度不符會被過濾。
    """
    success, output = run_git_command(
        ["diff", "--cached", "-M", "--name-status"],
        cwd=str(project_root),
    )
    if not success or not output:
        return {}
    rename_map: Dict[str, str] = {}
    for line in output.splitlines():
        parts = line.split("\t")
        if len(parts) != 3 or not parts[0].startswith("R"):
            continue
        _status, old_path, new_path = parts
        rename_map[new_path] = old_path
    return rename_map


def _git_show(rev_spec: str, project_root: Path) -> str:
    """`git show <rev_spec>`，失敗（檔案不存在等）回傳空字串。"""
    success, output = run_git_command(["show", rev_spec], cwd=str(project_root))
    if not success:
        return ""
    return output


def _get_added_text(
    rel_path: str, project_root: Path, old_path: Optional[str] = None
) -> str:
    """抽出 staged diff 中以單一 `+` 開頭（非 `+++`）的行，串接成文字。

    rename 檔案（`old_path` 非 None）額外把舊路徑一併帶入 pathspec 並加
    `-M`，使 git 能配對 rename 對；僅給新路徑單一 pathspec 時，git 找不到
    配對的舊路徑，rename 會退化為整檔新增（本函式修復前的根因行為）。
    """
    diff_args = ["diff", "--cached"]
    if old_path is not None:
        diff_args.append("-M")
    diff_args.append("--")
    if old_path is not None:
        diff_args.append(old_path)
    diff_args.append(rel_path)
    success, output = run_git_command(diff_args, cwd=str(project_root))
    if not success or not output:
        return ""
    added_lines = [
        line[1:]
        for line in output.splitlines()
        if line.startswith("+") and not line.startswith("+++")
    ]
    return "\n".join(added_lines)


def _build_staged_file(
    rel_path: str,
    project_root: Path,
    rename_map: Optional[Dict[str, str]] = None,
) -> StagedFile:
    old_path = (rename_map or {}).get(rel_path)
    pre_path = old_path if old_path is not None else rel_path
    pre_text = _git_show(f"HEAD:{pre_path}", project_root)
    post_text = _git_show(f":{rel_path}", project_root)
    added_text = _get_added_text(rel_path, project_root, old_path=old_path)
    return StagedFile(rel_path, pre_text, post_text, added_text)


def _build_deny_message(deny_findings: List[Finding]) -> str:
    """本檔（PreToolUse，掃 index）專屬 header；逐項訊息組裝共用
    lib.commit_content_guards._build_deny_message。"""
    header = (
        "[commit-stage-guard-gate] commit 被阻擋：staged 內容經事後掃描"
        f"命中 {len(deny_findings)} 項 B 組 guard 違規（原 guard 僅註冊於 "
        "Edit/Write/MultiEdit，本次寫入可能經 Bash 繞過，故於 commit 前補網）。\n"
        "請依下列各項訊息修正後重新 staged 並 commit：\n"
    )
    return _build_deny_message_body(deny_findings, header)


def _build_warn_message(warn_findings: List[Finding]) -> str:
    """本檔（PreToolUse，掃 index）專屬 header；逐項訊息組裝共用
    lib.commit_content_guards._build_warn_message。"""
    header = f"[commit-stage-guard-gate] 提醒：staged 內容命中 {len(warn_findings)} 項 WARN 級發現（不阻擋）：\n"
    return _build_warn_message_body(warn_findings, header)


def main() -> int:
    logger = setup_hook_logging("commit-stage-guard-gate")

    input_data = read_json_from_stdin(logger)
    if not input_data:
        return EXIT_ALLOW

    if input_data.get("tool_name", "") != "Bash":
        return EXIT_ALLOW

    tool_input = input_data.get("tool_input") or {}
    command = tool_input.get("command", "") or ""

    if not contains_git_word(command):
        return EXIT_ALLOW

    invocations = find_git_invocations(command, {"commit"})
    if not invocations:
        logger.debug("命令不含 git commit 呼叫，或無法安全解析，放行")
        return EXIT_ALLOW

    project_root = get_project_root()
    staged_paths = _get_staged_file_list(project_root)
    if not staged_paths:
        logger.debug("無 staged 檔案，放行")
        return EXIT_ALLOW

    rename_map = _get_staged_rename_map(project_root)
    staged_files = [
        _build_staged_file(p, project_root, rename_map) for p in staged_paths
    ]
    findings = _run_all_checks(staged_files, project_root, logger)

    deny_findings = [f for f in findings if f.severity == "deny"]
    warn_findings = [f for f in findings if f.severity == "warn"]

    if deny_findings:
        logger.warning(
            "commit 被阻擋：deny=%d warn=%d staged_files=%d",
            len(deny_findings), len(warn_findings), len(staged_files),
        )
        sys.stderr.write(_build_deny_message(deny_findings) + "\n")
        return EXIT_BLOCK

    if warn_findings:
        logger.info(
            "commit 放行但有 WARN 發現：warn=%d staged_files=%d",
            len(warn_findings), len(staged_files),
        )
        sys.stderr.write(_build_warn_message(warn_findings) + "\n")
        return EXIT_ALLOW

    logger.debug("staged 內容無發現，放行：staged_files=%d", len(staged_files))
    return EXIT_ALLOW


if __name__ == "__main__":
    sys.exit(run_hook_safely(main, "commit-stage-guard-gate"))
