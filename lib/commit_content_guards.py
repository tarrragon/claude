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
import json
import re
import sys
import types
from pathlib import Path
from typing import Callable, Dict, List, NamedTuple, Optional, Tuple

_VERSION_FILE_NAMES = frozenset({"pubspec.yaml", "package.json", "pyproject.toml"})
_LIB_DIR = Path(__file__).resolve().parent
_CLAUDE_DIR = _LIB_DIR.parent
_HOOKS_DIR = _CLAUDE_DIR / "hooks"


class Finding(NamedTuple):
    """單一 guard 對單一檔案的發現。"""

    severity: str  # "deny" | "warn"
    source: str  # 來源 guard 名稱，供訊息與稽核追溯
    message: str
    path: str = ""  # 觸發本發現的檔案相對路徑（需依路徑聚合輸出的 guard 才填）


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
    # per-project 區段（sync 雙向排除）與編輯層一致豁免。gitignore 本機檔豁免
    # 不比照：staged 檔必為 tracked，check-ignore 對 tracked 檔恆回「未忽略」，
    # 且 sf.rel_path 為相對路徑、此處無可靠 repo 起點（編輯層函式對相對路徑亦回 False）。
    if m.is_per_project_path(sf.rel_path):
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


def _fallback_action_root(payload: Optional[dict] = None) -> Path:
    """呼叫端未傳 project_root 時的作用根。

    payload 帶 cwd 時依 cwd 所屬 checkout 解析（情境 C：env 指向 MAIN、cwd 在
    linked worktree，取 worktree）；缺 cwd 時不呼叫 get_action_root（其缺 cwd
    會寫 stderr），沿用 get_project_root()。
    """
    from lib.git_utils import get_action_root, get_project_root  # noqa: PLC0415

    root = get_project_root()
    if isinstance(payload, dict) and payload.get("cwd"):
        return get_action_root(payload, root)
    return root


def _check_uc_reference(
    sf: StagedFile,
    logger,
    project_root: Optional[str] = None,
    payload: Optional[dict] = None,
) -> List[Finding]:
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
    if project_root is None:
        project_root = str(_fallback_action_root(payload))
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


_PUBSPEC_VERSION_RE = re.compile(r"^version:\s*(\S+)\s*$")
_TOML_VERSION_RE = re.compile(r"""^version\s*=\s*["']([^"']+)["']\s*$""")
_TOML_SECTION_RE = re.compile(r"^\[([^\[\]]+)\]\s*$")
_TOML_VERSION_SECTIONS = ("project", "tool.poetry")


def _toml_section_at(lines: List[str], index: int) -> str:
    """回傳第 index 行所屬的 TOML section 名稱（最近的前置 `[name]`）。"""
    for line in reversed(lines[:index]):
        match = _TOML_SECTION_RE.match(line)
        if match:
            return match.group(1).strip()
    return ""


def _single_changed_line(pre: List[str], post: List[str]) -> Optional[int]:
    """兩份文字逐行比對，恰有一行相異且行數相同時回傳該行索引，否則 None。"""
    if len(pre) != len(post):
        return None
    changed = [i for i, (a, b) in enumerate(zip(pre, post)) if a != b]
    return changed[0] if len(changed) == 1 else None


def _json_version_bump(pre_text: str, post_text: str) -> Optional[Tuple[str, str]]:
    try:
        pre, post = json.loads(pre_text), json.loads(post_text)
    except ValueError:
        return None
    if not isinstance(pre, dict) or not isinstance(post, dict):
        return None
    old, new = pre.pop("version", None), post.pop("version", None)
    if old is None or new is None or old == new or pre != post:
        return None
    return str(old), str(new)


def _line_version_bump(
    name: str, pre_lines: List[str], post_lines: List[str]
) -> Optional[Tuple[str, str]]:
    index = _single_changed_line(pre_lines, post_lines)
    if index is None:
        return None
    pattern = _PUBSPEC_VERSION_RE if name == "pubspec.yaml" else _TOML_VERSION_RE
    old_match = pattern.match(pre_lines[index])
    new_match = pattern.match(post_lines[index])
    if not (old_match and new_match):
        return None
    if name == "pyproject.toml" and (
        _toml_section_at(pre_lines, index) not in _TOML_VERSION_SECTIONS
    ):
        return None
    return old_match.group(1), new_match.group(1)


def _pure_version_bump(sf: StagedFile) -> Optional[Tuple[str, str]]:
    """版本檔且前後差異只有版本欄位那一行時回傳 (舊版本, 新版本)，否則 None。

    版本欄位：pubspec.yaml 頂層 `version:`；package.json 頂層 `"version"`；
    pyproject.toml 的 `[project]` 或 `[tool.poetry]` 下 `version =`。
    檔名以 basename 比對，涵蓋 monorepo 子目錄。新增檔案（pre 為空）不算 bump。
    """
    name = Path(sf.rel_path).name
    if name not in _VERSION_FILE_NAMES or not sf.pre_text or sf.pre_text == sf.post_text:
        return None
    if name == "package.json":
        return _json_version_bump(sf.pre_text, sf.post_text)
    return _line_version_bump(name, sf.pre_text.splitlines(), sf.post_text.splitlines())


class _BranchContext(NamedTuple):
    """branch-verify 的「與檔案無關」前置判定結果（每次掃描只解析一次）。"""

    module: types.ModuleType
    project_root: Path
    current_branch: str
    host_root: str


_CTX_UNSET = object()


def _resolve_branch_context(
    is_merge_commit: bool,
    project_root: Optional[Path] = None,
    branch: Optional[str] = None,
    payload: Optional[dict] = None,
) -> Optional[_BranchContext]:
    """解析 branch-verify 與檔案無關的前置條件：專案根、當前分支、是否受保護、
    是否為合併事件。回傳 None 代表本次掃描 branch-verify 不會產生任何發現
    （模組載入失敗 / 允許分支 / 非保護分支 / 合併事件），呼叫端可對所有檔案
    直接略過。

    這些條件都不依賴個別檔案，原本每個檔案各重查一輪（專案根 + 分支 + 豁免
    判斷內的專案根，共 3 個 git 子程序），變更檔數 F 越大持鎖越久；提到迴圈外
    後與 F 無關。判斷順序與原逐檔實作相同。

    project_root：呼叫端已解析的專案根。提供時不再於內部重新解析
    （CLAUDE_PROJECT_DIR 優先會在 worktree 情境取到別的 checkout，造成誤擋
    或誤放）；host_root 同取此值。未提供時維持舊行為（單檔呼叫端相容）。
    branch：本次實際寫入的分支（reference-transaction 取 stdin 的 ref）。
    提供時以之為準；未提供（None，含 detached HEAD 寫入）時退回讀
    project_root 的 HEAD 分支。
    payload：未提供 project_root 時，帶 cwd 則以其所屬 checkout 為作用根
    （見 _fallback_action_root）；缺 cwd 沿用 get_project_root()。
    """
    m = _load_module("commit_gate_branch_verify", _HOOKS_DIR / "branch-verify-hook.py")
    if m is None:
        return None
    from lib.git_utils import get_current_branch, get_project_root, is_protected_branch, is_allowed_branch  # noqa: E402,PLC0415

    explicit_root = project_root is not None
    project_root = Path(project_root) if explicit_root else _fallback_action_root(payload)
    current_branch = branch or get_current_branch(cwd=str(project_root))
    if not current_branch or is_allowed_branch(current_branch):
        return None
    if not is_protected_branch(current_branch):
        return None
    if is_merge_commit:
        return None
    host_root = (
        str(project_root) if explicit_root else str(get_project_root(cwd=str(project_root)))
    )
    return _BranchContext(m, project_root, current_branch, host_root)


def _check_branch_verify(
    sf: StagedFile,
    logger,
    is_merge_commit: bool = False,
    ctx=_CTX_UNSET,
    payload: Optional[dict] = None,
) -> List[Finding]:
    """轉呼 branch-verify-hook：完整重用 is_protected_branch /
    is_allowed_branch / is_exempt_path_on_protected_branch，內容無關，
    僅依當前分支與檔案路徑判斷。

    is_merge_commit：本次寫入來自合併 commit（多 parent）時為 True，一律
    放行（不看個別路徑是否豁免）。守衛要擋的是「繞過 feature 分支、直接
    對保護分支寫入非豁免內容」；merge 是把已經過各項 guard 檢查（原始
    提交在 feature 分支上時已受同一套檢查）的內容整批帶入保護分支的正規
    動作，與逐檔直接提交性質不同，豁免對象是「這次 merge 事件」而非個別
    檔案內容——其餘 per-file guard（rule8 等）不受 is_merge_commit 影響，
    仍照常執行。直接提交（is_merge_commit=False，預設值）維持原行為不變。

    ctx：`_resolve_branch_context` 的預先解析結果（None 表示已判定無須檢查）。
    未提供時（單檔呼叫端）於本次呼叫內自行解析，行為與批次前相同。
    """
    if ctx is _CTX_UNSET:
        ctx = _resolve_branch_context(is_merge_commit, payload=payload)
    if ctx is None:
        return []
    if ctx.module.is_exempt_path_on_protected_branch(
        sf.rel_path, cwd=str(ctx.project_root), host_root=ctx.host_root
    ):
        return []
    bump = _pure_version_bump(sf)
    if bump is not None:
        logger.info(
            "[branch-verify] 保護分支 '%s' 上放行純版本號變動 %s：%s -> %s",
            ctx.current_branch, sf.rel_path, bump[0], bump[1],
        )
        return []
    return [
        Finding(
            "deny",
            "branch-verify",
            f"[branch-verify] 保護分支 '{ctx.current_branch}' 上 commit 非豁免檔案 {sf.rel_path}，"
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
            _SKILL_TRIGGER_SOURCE,
            f"[skill-trigger] 內含 framework 規則層變更：{rel_path}。"
            f"{_SKILL_TRIGGER_ADVICE}",
            path=rel_path,
        )
    ]


_SKILL_TRIGGER_SOURCE = "framework-rule-edit-skill-trigger"
_SKILL_TRIGGER_ADVICE = "建議確認已讀過 compositional-writing SKILL（此階段無法核實，僅提醒）。"
_SKILL_DIR_RE = re.compile(r"^(\.claude/skills/[^/]+)/")


def _group_skill_trigger_findings(findings: List[Finding]) -> List[Finding]:
    """skill-trigger 提醒依 skill 目錄聚合：同一 skill 目錄下 2 個以上檔案合為一則並附檔數。

    一次收入整個 skill（如 skill-sync pull 回流）時，逐檔提醒會印出數十則
    相同建議，淹沒同段輸出的其他警告。只聚合輸出，findings 本身仍逐檔，
    稽核與計數不變。skill 目錄外的框架檔（rules、pm-rules、references 等）
    與只動到單一檔的 skill 維持逐檔提醒。聚合後的訊息放在該組第一則的位置。
    """
    groups: dict = {}
    for f in findings:
        if f.source != _SKILL_TRIGGER_SOURCE:
            continue
        m = _SKILL_DIR_RE.match(f.path or "")
        if m:
            groups.setdefault(m.group(1), []).append(f)
    merged: List[Finding] = []
    emitted: set = set()
    for f in findings:
        m = _SKILL_DIR_RE.match(f.path or "") if f.source == _SKILL_TRIGGER_SOURCE else None
        group = groups.get(m.group(1)) if m else None
        if not group or len(group) < 2:
            merged.append(f)
            continue
        skill_dir = m.group(1)
        if skill_dir in emitted:
            continue
        emitted.add(skill_dir)
        merged.append(
            Finding(
                f.severity,
                f.source,
                f"[skill-trigger] 內含 framework 規則層變更：{skill_dir}/ 下 {len(group)} 個檔案"
                f"（例：{group[0].path}）。{_SKILL_TRIGGER_ADVICE}",
                path=skill_dir + "/",
            )
        )
    return merged


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
    if not sf.post_text.strip():
        return []
    violations = _net_new_violations(m, profile, sf.pre_text, sf.post_text)
    if not violations:
        return []
    return [Finding("deny", "presence-detection", m.build_block_message(sf.rel_path, violations))]


def _squash_whitespace(snippet: str) -> str:
    """去除所有空白，使換行、縮排不同的同一字面視為同一筆。"""
    return re.sub(r"\s+", "", snippet)


def _join_wrapped_lines(text: str) -> str:
    """把括號未閉合的多行合併為單行，並去除 `,)` 的尾逗號。

    dart format 會合併、拆分行並增刪尾逗號，逐行片段不穩定；合併後
    「拆成多行」與「合併成一行」的同一敘述得到相同字面。
    """
    out: List[str] = []
    buf = ""
    depth = 0
    for line in text.split("\n"):
        buf += line.strip() if buf else line
        depth += line.count("(") - line.count(")")
        if depth <= 0:
            out.append(re.sub(r",\s*\)", ")", buf))
            buf, depth = "", 0
    if buf:
        out.append(re.sub(r",\s*\)", ")", buf))
    return "\n".join(out)


def _violation_key(m, profile, text: str, v: dict) -> Tuple[str, str]:
    """比對鍵：(category, 命中的字面)，與整行排版、前後文無關。

    snippet 為整行且截斷 80 字，不穩定；改取 profile 的命中片段。
    已知取捨：同檔把某魔術數字換成另一處同字面者不會被抓到。
    """
    line = text.split("\n")[v["line"] - 1]
    category = v["category"]
    if category == "i18n":
        literal = "".join(m._string_literal_contents(line))
    else:
        patterns = profile.color_detect if category == "color" else profile.magic_detect
        hit = next((p.search(line) for p in patterns if p.search(line)), None)
        literal = hit.group(0) if hit else line
    return (category, _squash_whitespace(literal))


def _net_new_violations(m, profile, pre_text: str, post_text: str) -> list:
    """pre -> post 的淨增量發現（多重集合比對，比照 rule8 diff_new_hits）。

    純排版 diff（重排、縮排）使行文字改變但字面不變，掃 added_text 會誤判；
    改掃 post_text 並扣除 pre_text 已存在的同類同字面發現。
    """
    pre_text = _join_wrapped_lines(pre_text)
    post_text = _join_wrapped_lines(post_text)
    remaining: Dict[Tuple[str, str], int] = {}
    for v in m.detect_violations(pre_text, profile):
        key = _violation_key(m, profile, pre_text, v)
        remaining[key] = remaining.get(key, 0) + 1
    new_violations = []
    for v in m.detect_violations(post_text, profile):
        key = _violation_key(m, profile, post_text, v)
        if remaining.get(key, 0) > 0:
            remaining[key] -= 1
            continue
        new_violations.append(v)
    return new_violations


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


# _check_branch_verify 不列入本清單：其判斷需額外的 is_merge_commit 旗標
# （見該函式 docstring），_run_all_checks 對它單獨呼叫，與 _check_wrap_
# skill_yaml（需額外 project_root 參數，同理不列入）採同一種特例模式。
_PER_FILE_CHECKS: List[Callable[[StagedFile, "object"], List[Finding]]] = [
    _check_rule8,
    _check_uc_reference,
    _check_file_type_permission,
    _check_error_pattern_flat,
    _check_framework_skill_trigger,
    _check_memory_write,
    _check_presence_detection,
    _check_proposal_evaluation,
    _check_ticket_path,
]


def _run_all_checks(
    staged_files: List[StagedFile],
    project_root: Path,
    logger,
    is_merge_commit: bool = False,
    branch: Optional[str] = None,
) -> List[Finding]:
    """對每個變更檔案跑過 per-file 轉呼函式，另跑一次全域的
    wrap-skill-yaml 一致性檢查（該 guard 語意上是「專案狀態一致性」而非
    逐檔獨立判斷，避免同一警告因多檔變更而重複輸出）。

    is_merge_commit：轉呼 _check_branch_verify（見該函式 docstring）；預設
    False，既有呼叫端（commit-stage-guard-gate-hook.py 的 PreToolUse 掃
    index 路徑）不帶此參數即維持原行為不變。

    branch：本次寫入的分支名（見 _resolve_branch_context）；分支判定的專案根
    一律採呼叫端傳入的 project_root，不再重新解析 CLAUDE_PROJECT_DIR。
    """
    findings: List[Finding] = []
    wrap_checked = False
    if not staged_files:
        return findings
    # 與檔案無關的解析提到迴圈外，避免每個檔案各付一輪 git 子程序。
    branch_ctx = _resolve_branch_context(is_merge_commit, project_root, branch)
    root_str = str(project_root)
    for sf in staged_files:
        for check in _PER_FILE_CHECKS:
            if check is _check_uc_reference:
                findings.extend(check(sf, logger, project_root=root_str))
            else:
                findings.extend(check(sf, logger))
        findings.extend(
            _check_branch_verify(sf, logger, is_merge_commit=is_merge_commit, ctx=branch_ctx)
        )
        if not wrap_checked:
            wrap_findings = _check_wrap_skill_yaml(sf, logger, project_root)
            if wrap_findings:
                findings.extend(wrap_findings)
                wrap_checked = True
    findings.extend(_check_doc_validate(staged_files, project_root, logger, is_merge_commit))
    _log_skill_trigger_grouping(findings, logger)
    return findings


def _check_doc_validate(
    staged_files: List[StagedFile], project_root: Path, logger, is_merge_commit: bool
) -> List[Finding]:
    """觸及的 docs 節點跑 doc validate，只擋新增錯誤（判定見 .claude/lib/commit_doc_validate.py）。

    合併 commit 不套用：合併帶入的內容已在分支提交時驗過，且合併進行中工作區
    可能含衝突中間態。整批檔案一次判定（需建一次提交前 docs 樹），故不列入
    _PER_FILE_CHECKS。模組載入或執行例外時 fail-open，stderr 與日誌雙通道。
    """
    if is_merge_commit:
        return []
    try:
        from lib.commit_doc_validate import check_doc_validate  # noqa: PLC0415

        return check_doc_validate(staged_files, project_root, logger, Finding)
    except Exception as exc:  # noqa: BLE001 — fail-open，見 docstring
        msg = f"[doc-validate] 檢查內部錯誤，已放行未判定：{exc}"
        sys.stderr.write(msg + "\n")
        logger.warning(msg)
        return []


def _log_skill_trigger_grouping(findings: List[Finding], logger) -> None:
    """記錄 skill-trigger 提醒的聚合結果（輸出由 _build_warn_message 聚合，findings 不變）。"""
    before = sum(1 for f in findings if f.source == _SKILL_TRIGGER_SOURCE)
    if before < 2:
        return
    after = sum(1 for f in _group_skill_trigger_findings(findings) if f.source == _SKILL_TRIGGER_SOURCE)
    if after < before:
        logger.info(f"skill-trigger 提醒依 skill 目錄聚合：{before} 則合為 {after} 則")


def _build_deny_message(deny_findings: List[Finding], header: str) -> str:
    body = "\n\n".join(f"[{f.source}] {f.message}" for f in deny_findings)
    return header + "\n" + body


def _build_warn_message(warn_findings: List[Finding], header: str) -> str:
    grouped = _group_skill_trigger_findings(warn_findings)
    body = "\n\n".join(f"[{f.source}] {f.message}" for f in grouped)
    return header + "\n" + body
