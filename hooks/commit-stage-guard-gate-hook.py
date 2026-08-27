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

import importlib.util
import sys
import types
from pathlib import Path
from typing import Callable, Dict, List, NamedTuple, Optional

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib import setup_hook_logging, run_hook_safely, read_json_from_stdin  # noqa: E402
from lib.git_command_parse import find_git_invocations, contains_git_word  # noqa: E402
from lib.git_utils import get_project_root, run_git_command  # noqa: E402

EXIT_ALLOW = 0
EXIT_BLOCK = 2

_HOOKS_DIR = Path(__file__).resolve().parent
_CLAUDE_DIR = _HOOKS_DIR.parent


class Finding(NamedTuple):
    """單一 guard 對單一檔案的發現。"""

    severity: str  # "deny" | "warn"
    source: str  # 來源 guard 名稱，供訊息與稽核追溯
    message: str


class StagedFile(NamedTuple):
    """單一 staged 檔案的三種重建文字。"""

    rel_path: str
    pre_text: str
    post_text: str
    added_text: str


def _load_module(mod_name: str, file_path: Path) -> Optional[types.ModuleType]:
    """以檔案路徑動態載入模組（檔名含連字號，無法用一般 import 語法）。

    載入失敗時回傳 None，呼叫端須降級跳過對應 guard（fail-open，不因單一
    guard 載入失敗而阻擋整個 commit-stage 補網）。
    """
    try:
        spec = importlib.util.spec_from_file_location(mod_name, file_path)
        if spec is None or spec.loader is None:
            return None
        module = importlib.util.module_from_spec(spec)
        sys.modules[mod_name] = module
        spec.loader.exec_module(module)
        return module
    except Exception:
        return None


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


# ============================================================================
# 12 支 guard 的轉呼函式（見檔頭「產生路徑盤點表」對照）
# ============================================================================


def _check_rule8(sf: StagedFile, logger) -> List[Finding]:
    """轉呼 reference-stability-rule8-guard-hook：完整重用
    is_scanned_path / is_class4_whitelisted / is_class5_test_path /
    diff_new_hits / filter_marker_exempt / build_block_message。
    """
    m = _load_module(
        "commit_gate_rule8", _HOOKS_DIR / "reference-stability-rule8-guard-hook.py"
    )
    if m is None:
        return []
    if not m.is_scanned_path(sf.rel_path):
        return []
    if m.is_class4_whitelisted(sf.rel_path) or m.is_class5_test_path(sf.rel_path):
        return []
    new_hits = m.diff_new_hits(sf.pre_text, sf.post_text)
    if not new_hits:
        return []
    blocked_hits, format_error_messages = m.filter_marker_exempt(
        sf.rel_path, sf.post_text, new_hits
    )
    findings: List[Finding] = []
    if blocked_hits:
        findings.append(
            Finding("deny", "reference-stability-rule8-guard", m.build_block_message(sf.rel_path, blocked_hits))
        )
    for msg in format_error_messages:
        findings.append(Finding("deny", "reference-stability-rule8-guard", msg))
    return findings


def _check_uc_reference(sf: StagedFile, logger) -> List[Finding]:
    """轉呼 uc-reference-validation-hook：直接 import doc_system.core.uc_registry
    （原 hook 亦於 main() 內 lazy import 同一模組）。WARN-only，保留原語意
    不升級為 deny。
    """
    doc_skill_dir = _CLAUDE_DIR / "skills" / "doc"
    if str(doc_skill_dir) not in sys.path:
        sys.path.insert(0, str(doc_skill_dir))
    try:
        from doc_system.core.uc_registry import (  # noqa: PLC0415
            HOOK_SCANNABLE_EXTENSIONS,
            find_uc_tokens_in_text,
            get_valid_uc_map,
            is_exempt_path,
            is_violation_token,
            normalize_token,
        )
    except ImportError:
        return []

    if not sf.rel_path.lower().endswith(HOOK_SCANNABLE_EXTENSIONS):
        return []
    project_root = str(get_project_root())
    if is_exempt_path(sf.rel_path, project_root):
        return []
    if not sf.added_text:
        return []
    tokens = find_uc_tokens_in_text(sf.added_text)
    if not tokens:
        return []
    valid = get_valid_uc_map(project_root)
    violations = sorted(
        {
            normalize_token(token)
            for token, _lineno in tokens
            if is_violation_token(token, valid)
        }
    )
    if not violations:
        return []
    return [
        Finding(
            "warn",
            "uc-reference-validation",
            f"[uc-reference-validation] {sf.rel_path} 新增內容含未定義 UC 編號："
            f"{', '.join(violations)}（規則來源 docs/spec/uc-numbering-convention.md）",
        )
    ]


def _check_file_type_permission(sf: StagedFile, logger) -> List[Finding]:
    """file-type-permission-hook 原始行為從不阻擋（僅對 ticket/worklog 類別
    輸出 allow + 提示訊息），無 deny 路徑可轉呼。no-op，保留函式作為
    「產生路徑盤點表」的顯性記錄，避免遺漏此 guard 而誤判為疏漏。
    """
    return []


def _check_branch_verify(sf: StagedFile, logger) -> List[Finding]:
    """轉呼 branch-verify-hook：完整重用 is_protected_branch /
    is_allowed_branch / is_exempt_path_on_protected_branch，內容無關，
    僅依當前分支與檔案路徑判斷。
    """
    m = _load_module("commit_gate_branch_verify", _HOOKS_DIR / "branch-verify-hook.py")
    if m is None:
        return []
    from lib.git_utils import get_current_branch, is_protected_branch, is_allowed_branch  # noqa: E402

    project_root = get_project_root()
    current_branch = get_current_branch(cwd=str(project_root))
    if not current_branch or is_allowed_branch(current_branch):
        return []
    if not is_protected_branch(current_branch):
        return []
    if m.is_exempt_path_on_protected_branch(sf.rel_path, cwd=str(project_root)):
        return []
    return [
        Finding(
            "deny",
            "branch-verify",
            f"[branch-verify] 保護分支 '{current_branch}' 上 commit 非豁免檔案 {sf.rel_path}，"
            "請切換至 feature 分支後再提交。",
        )
    ]


def _check_error_pattern_flat(sf: StagedFile, logger) -> List[Finding]:
    """轉呼 error-pattern-flat-gate-hook：`decide()` 為純函式，直接以
    tool_name="Write" 呼叫（disk exists 判斷在 decide 內部完成，staged
    新檔在 commit 前已寫入磁碟，語意一致）。
    """
    m = _load_module(
        "commit_gate_error_pattern_flat",
        _CLAUDE_DIR / "skills" / "error-pattern" / "hooks" / "error-pattern-flat-gate-hook.py",
    )
    if m is None:
        return []
    decision, reason, _exit_code = m.decide("Write", {"file_path": sf.rel_path})
    if decision != "deny":
        return []
    return [Finding("deny", "error-pattern-flat-gate", reason)]


def _check_framework_skill_trigger(sf: StagedFile, logger) -> List[Finding]:
    """轉呼 framework-rule-edit-skill-trigger-hook：簡化重用。原 hook 的
    deny 分支（strict 模式）依賴 transcript_path 掃描確認「本 session 是否
    已呼叫 compositional-writing SKILL」——commit 事件無對應可靠 session
    憑證，無法安全重現該判斷，故本函式一律降級為 WARN，不做 strict deny，
    避免產生無法驗證的假陽性阻擋 commit（已於檔頭已知邊界段落載明）。
    """
    m = _load_module(
        "commit_gate_framework_skill_trigger",
        _HOOKS_DIR / "framework-rule-edit-skill-trigger-hook.py",
    )
    if m is None:
        return []
    rel_path = m._normalize_to_relative(sf.rel_path)  # noqa: SLF001（模組內部函式，刻意重用）
    if not m.framework_paths.is_framework_path(rel_path):
        return []
    return [
        Finding(
            "warn",
            "framework-rule-edit-skill-trigger",
            f"[skill-trigger] commit 內含 framework 規則層變更：{rel_path}。"
            "建議確認已讀過 compositional-writing SKILL（commit 階段無法核實，僅提醒）。",
        )
    ]


def _check_memory_write(sf: StagedFile, logger) -> List[Finding]:
    """轉呼 memory-write-guard-hook：完整重用 is_memory_path。memory 目錄
    位於使用者 home 下（~/.claude/projects/.../memory/），本不落在專案
    git repo 內，staged 檔案恆不會命中，此函式恆為 no-op；保留以防未來
    memory 路徑定義變動而納入專案樹。
    """
    m = _load_module("commit_gate_memory_write", _HOOKS_DIR / "memory-write-guard-hook.py")
    if m is None:
        return []
    if not m.is_memory_path(sf.rel_path):
        return []
    return [Finding("deny", "memory-write-guard", m.DENY_REASON)]


def _check_presence_detection(sf: StagedFile, logger) -> List[Finding]:
    """轉呼 presence-detection-hook：完整重用 get_profile_for_path /
    should_skip_file / detect_violations / build_block_message，掃描對象
    改用 added_text（本次 commit 新增行），與原 hook「只掃變更內容」的
    防呆設計一致。
    """
    m = _load_module("commit_gate_presence_detection", _HOOKS_DIR / "presence-detection-hook.py")
    if m is None:
        return []
    presence_profiles = _load_module(
        "commit_gate_presence_profiles", _CLAUDE_DIR / "config" / "presence_profiles.py"
    )
    if presence_profiles is None:
        return []
    profile = presence_profiles.get_profile_for_path(sf.rel_path)
    if profile is None:
        return []
    if m.should_skip_file(sf.rel_path, profile):
        return []
    if not sf.added_text.strip():
        return []
    violations = m.detect_violations(sf.added_text, profile)
    if not violations:
        return []
    return [Finding("deny", "presence-detection", m.build_block_message(sf.rel_path, violations))]


def _check_proposal_evaluation(sf: StagedFile, logger) -> List[Finding]:
    """轉呼 proposal-evaluation-gate-hook：完整重用 is_target_file /
    parse_frontmatter / check_prop_content / check_tracking_yaml。
    old_status 由 pre_text frontmatter 推導（取代原 hook 依賴
    tool_name/tool_input 的 get_old_status，語意等價：兩者都是「編輯前
    frontmatter status」）。微調豁免（is_micro_edit）不適用——commit 階段
    無 tool_input 差異量可算，一律完整檢查（方向安全，僅可能多檢查不會
    漏檢查）。
    """
    m = _load_module(
        "commit_gate_proposal_evaluation",
        _HOOKS_DIR / "proposal-evaluation-gate-hook.py",
    )
    if m is None:
        return []
    target = m.is_target_file(sf.rel_path)
    if target is None:
        return []
    if not sf.post_text:
        return []

    if target == "prop":
        old_status = None
        fm_old = m.parse_frontmatter(sf.pre_text) if sf.pre_text else None
        if fm_old:
            old_status = m.normalize_status(fm_old.get("status"))
        should_block, reason = m.check_prop_content(sf.post_text, logger, old_status)
    else:
        should_block, reason = m.check_tracking_yaml(sf.post_text, logger)

    if not should_block:
        return []
    return [Finding("deny", "proposal-evaluation-gate", f"[proposal-evaluation-gate] {sf.rel_path}: {reason}")]


def _check_ticket_path(sf: StagedFile, logger) -> List[Finding]:
    """轉呼 ticket-path-guard-hook（skills/ticket）：完整重用
    is_forbidden_ticket_path。"""
    m = _load_module(
        "commit_gate_ticket_path",
        _CLAUDE_DIR / "skills" / "ticket" / "hooks" / "ticket-path-guard-hook.py",
    )
    if m is None:
        return []
    if not m.is_forbidden_ticket_path(sf.rel_path, logger):
        return []
    return [
        Finding(
            "deny",
            "ticket-path-guard",
            f"[ticket-path-guard] 禁止 commit .claude/tickets/ 路徑下的檔案："
            f"{sf.rel_path}（正確位置：docs/work-logs/v{{version}}/tickets/，請改用 /ticket create）",
        )
    ]


def _check_wrap_skill_yaml(sf: StagedFile, logger, project_root: Path) -> List[Finding]:
    """轉呼 wrap-skill-yaml-consistency-hook（skills/wrap-decision）：完整
    重用 `_is_watched` / `load_alignment` / `load_yaml_config` /
    `check_signal_orphan` / `check_keyword_orphan` / `check_version_no_regress`
    ——皆讀磁碟現況與 git HEAD，不依賴 tool_input，於 commit 階段語意
    與原 PreToolUse 語境等價。
    """
    m = _load_module(
        "commit_gate_wrap_skill_yaml",
        _CLAUDE_DIR / "skills" / "wrap-decision" / "hooks" / "wrap-skill-yaml-consistency-hook.py",
    )
    if m is None or not getattr(m, "_LIB_AVAILABLE", True):
        return []
    watched = m._is_watched(sf.rel_path, project_root)  # noqa: SLF001（模組內部函式，刻意重用）
    if not watched:
        return []

    alignment, err = m.load_alignment(project_root, logger)
    if alignment is None:
        return [Finding("deny", "wrap-skill-yaml-consistency", f"[WRAP Consistency] 映射檔錯誤（阻擋）：{err}")]

    yaml_data = m.load_yaml_config(project_root, logger)
    warnings: List[str] = []
    if yaml_data:
        warnings.extend(m.check_signal_orphan(yaml_data, alignment, logger))
        warnings.extend(m.check_keyword_orphan(yaml_data, alignment, logger))
    warnings.extend(m.check_version_no_regress(project_root, logger))
    if not warnings:
        return []
    return [
        Finding(
            "warn",
            "wrap-skill-yaml-consistency",
            "[WRAP Consistency] 偵測到 " + str(len(warnings)) + " 項一致性警告：\n" + "\n".join(warnings),
        )
    ]


# 10. suggest-compact.py：純 session 步調建議（tool-call 計數），與檔案
#     內容正確性無關，非 commit 補網範疇，刻意不建立對應 `_check_*` 函式
#     （見檔頭「產生路徑盤點表」第 10 項）。


_PER_FILE_CHECKS: List[Callable[[StagedFile, "object"], List[Finding]]] = [
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
]


def _run_all_checks(staged_files: List[StagedFile], project_root: Path, logger) -> List[Finding]:
    """對每個 staged 檔案跑過 per-file 轉呼函式，另跑一次全域的
    wrap-skill-yaml 一致性檢查（該 guard 語意上是「專案狀態一致性」而非
    逐檔獨立判斷，避免同一警告因多檔 staged 而重複輸出）。
    """
    findings: List[Finding] = []
    wrap_checked = False
    for sf in staged_files:
        for check in _PER_FILE_CHECKS:
            findings.extend(check(sf, logger))
        if not wrap_checked:
            wrap_findings = _check_wrap_skill_yaml(sf, logger, project_root)
            if wrap_findings:
                findings.extend(wrap_findings)
                wrap_checked = True
    return findings


def _build_deny_message(deny_findings: List[Finding]) -> str:
    header = (
        "[commit-stage-guard-gate] commit 被阻擋：staged 內容經事後掃描"
        f"命中 {len(deny_findings)} 項 B 組 guard 違規（原 guard 僅註冊於 "
        "Edit/Write/MultiEdit，本次寫入可能經 Bash 繞過，故於 commit 前補網）。\n"
        "請依下列各項訊息修正後重新 staged 並 commit：\n"
    )
    body = "\n\n".join(f"[{f.source}] {f.message}" for f in deny_findings)
    return header + "\n" + body


def _build_warn_message(warn_findings: List[Finding]) -> str:
    header = f"[commit-stage-guard-gate] 提醒：staged 內容命中 {len(warn_findings)} 項 WARN 級發現（不阻擋）：\n"
    body = "\n\n".join(f"[{f.source}] {f.message}" for f in warn_findings)
    return header + "\n" + body


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
