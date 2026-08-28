"""Commit 內容掃描共用邏輯（自 commit-stage-guard-gate-hook.py 抽出）。

背景：commit-stage-guard-gate-hook.py 原以「掃描點綁 `git commit` 命令」
為前提，內含 12 支既有 Edit/Write-only guard 的轉呼函式。實測發現該綁定
方式對「推薦的提交路徑」（`ticket track commit` 走 `commit-tree` +
`update-ref` 隔離索引、`ticket-md-auto-commit-hook.py` 的 PostToolUse
自動提交同走此路徑）與 `git merge --continue` 完全零命中——兩者皆寫入
ref 但不含 `git commit` 這個子命令字面，PreToolUse 層級的 Bash matcher
也看不到 `ticket track commit` 內部以 subprocess 發出的 `git
commit-tree`（首 token 是 `ticket` 非 `git`）。詳見
`.claude/references/rule-enforcement-binding-points.md`。

修復方向是新增一個綁「ref 寫入事件」而非「命令字面」的承載體
（`.claude/hooks/git-ref-transaction-content-guard.py`，掛
`.git/hooks/reference-transaction` 原生 git hook，見該檔案 docstring），
與既有 PreToolUse 層（commit-stage-guard-gate-hook.py，仍保留、繼續在
`git commit` 執行前提供即時回饋）共用同一組「掃描 StagedFile 內容並轉呼
12 支既有 guard」邏輯——差異只在「文字從哪裡重建」（PreToolUse 讀 index，
reference-transaction 讀已提交的 commit 物件），此模組即為兩者共用的
「文字重建完成之後」那一段。

本模組不依賴呼叫端如何取得 `StagedFile.pre_text` / `post_text` /
`added_text`，故 `StagedFile` 這個名稱維持不變（沿用 PreToolUse 語境的
命名，語意上是「本次變更前後與新增的三種文字」，非侷限於 git index）。
"""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path
from typing import Callable, Dict, List, NamedTuple, Optional

_LIB_DIR = Path(__file__).resolve().parent
_CLAUDE_DIR = _LIB_DIR.parent
_HOOKS_DIR = _CLAUDE_DIR / "hooks"


class Finding(NamedTuple):
    """單一 guard 對單一檔案的發現。"""

    severity: str  # "deny" | "warn"
    source: str  # 來源 guard 名稱，供訊息與稽核追溯
    message: str


class StagedFile(NamedTuple):
    """單一變更檔案的三種重建文字（變更前 / 變更後 / 本次新增行）。"""

    rel_path: str
    pre_text: str
    post_text: str
    added_text: str


def _load_module(mod_name: str, file_path: Path) -> Optional[types.ModuleType]:
    """以檔案路徑動態載入模組（檔名含連字號，無法用一般 import 語法）。

    載入失敗時回傳 None，呼叫端須降級跳過對應 guard（fail-open，不因單一
    guard 載入失敗而阻擋整個補網）。
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


# ============================================================================
# 12 支既有 guard 的轉呼函式（對照表見 commit-stage-guard-gate-hook.py
# 檔頭「產生路徑盤點表」）。函式簽章只依賴 StagedFile / logger /
# project_root，不假設文字重建來源，故可被 PreToolUse 與 reference-
# transaction 兩種承載體共用。
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
    from lib.git_utils import get_project_root  # noqa: PLC0415

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
    from lib.git_utils import get_current_branch, get_project_root, is_protected_branch, is_allowed_branch  # noqa: E402,PLC0415

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
    tool_name="Write" 呼叫（disk exists 判斷在 decide 內部完成，變更檔案
    在提交前已寫入磁碟，語意一致）。
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
    已呼叫 compositional-writing SKILL」——commit / ref 事件皆無對應可靠
    session 憑證，無法安全重現該判斷，故本函式一律降級為 WARN，不做
    strict deny，避免產生無法驗證的假陽性阻擋。
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
            f"[skill-trigger] 內含 framework 規則層變更：{rel_path}。"
            "建議確認已讀過 compositional-writing SKILL（此階段無法核實，僅提醒）。",
        )
    ]


def _check_memory_write(sf: StagedFile, logger) -> List[Finding]:
    """轉呼 memory-write-guard-hook：完整重用 is_memory_path。memory 目錄
    位於使用者 home 下（~/.claude/projects/.../memory/），本不落在專案
    git repo 內，變更檔案恆不會命中，此函式恆為 no-op；保留以防未來
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
    改用 added_text（本次變更新增行），與原 hook「只掃變更內容」的防呆
    設計一致。
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
    frontmatter status」）。微調豁免（is_micro_edit）不適用——此階段無
    tool_input 差異量可算，一律完整檢查（方向安全，僅可能多檢查不會
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
            f"[ticket-path-guard] 禁止提交 .claude/tickets/ 路徑下的檔案："
            f"{sf.rel_path}（正確位置：docs/work-logs/v{{version}}/tickets/，請改用 /ticket create）",
        )
    ]


def _check_wrap_skill_yaml(sf: StagedFile, logger, project_root: Path) -> List[Finding]:
    """轉呼 wrap-skill-yaml-consistency-hook（skills/wrap-decision）：完整
    重用 `_is_watched` / `load_alignment` / `load_yaml_config` /
    `check_signal_orphan` / `check_keyword_orphan` / `check_version_no_regress`
    ——皆讀磁碟現況與 git HEAD，不依賴 tool_input，於此階段語意與原
    PreToolUse 語境等價。
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
#     內容正確性無關，非補網範疇，刻意不建立對應 `_check_*` 函式（見
#     commit-stage-guard-gate-hook.py 檔頭「產生路徑盤點表」第 10 項）。


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
    """對每個變更檔案跑過 per-file 轉呼函式，另跑一次全域的
    wrap-skill-yaml 一致性檢查（該 guard 語意上是「專案狀態一致性」而非
    逐檔獨立判斷，避免同一警告因多檔變更而重複輸出）。
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


def _build_deny_message(deny_findings: List[Finding], header: str) -> str:
    body = "\n\n".join(f"[{f.source}] {f.message}" for f in deny_findings)
    return header + "\n" + body


def _build_warn_message(warn_findings: List[Finding], header: str) -> str:
    body = "\n\n".join(f"[{f.source}] {f.message}" for f in warn_findings)
    return header + "\n" + body
