"""
票號推導與訊號判定（自 wrap-decision-tripwire-hook.py 拆出，行為不變）。

含：DetectResult、票號推導 fallback chain、手動 /wrap-decision 偵測、
ticket frontmatter / Solution 讀取、四個訊號 Strategy 與 SIGNAL_STRATEGIES。
時鐘一律經 `_state._now()` 屬性存取，維持全套件單一注入點。
"""

import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Protocol

from . import state as _state
from .config import SignalDef

try:
    from lib import (
        get_project_root,
        parse_ticket_frontmatter,
        find_ticket_file,
    )
    from lib.ticket_id_pattern import extract_ticket_id_anchored
except ImportError:
    # 消費端未提供 .claude/lib/ 時優雅降級（portability-allow: 選用性依賴，
    # 缺件優雅降級，非可攜性違規）：本模組仍可匯入，由 hook 的 main() 依
    # _LIB_AVAILABLE 在偵測前直接放行；這些名稱此時不會被呼叫。
    get_project_root = None
    parse_ticket_frontmatter = None
    find_ticket_file = None
    extract_ticket_id_anchored = None


@dataclass
class DetectResult:
    hit: bool = False
    should_warn: bool = False
    reset: bool = False
    count: Optional[int] = None
    matched_keyword: Optional[str] = None
    ticket_id: Optional[str] = None
    log_reason: Optional[str] = None
    # signal_id 由 detect() 於返回前填入（= sd.id）；apply() 讀取以定位 state 子 key。
    # 取代先前類別層級 signal_id 屬性，消除與 SIGNAL_STRATEGIES key 的 drift 風險（CE-4+R2）。
    signal_id: Optional[str] = None


# ============================================================================
# Ticket 推導 fallback chain
# ============================================================================

def _ticket_from_agent_payload(event: Dict[str, Any]) -> Optional[str]:
    """從 Agent/Task 事件 tool_input.prompt 首行取票號（派發 hook 已強制含 Ticket 行）。

    PostToolUse / PostToolUseFailure 的 payload 皆帶 tool_input（與
    active-dispatch-tracker-hook 讀同一欄位）；UserPromptSubmit 無此欄位，返回 None。
    """
    if event.get("tool_name") not in ("Agent", "Task"):
        return None
    tool_input = event.get("tool_input")
    if not isinstance(tool_input, dict):
        return None
    prompt = tool_input.get("prompt")
    if not isinstance(prompt, str) or not prompt.strip():
        return None
    return extract_ticket_id_anchored(prompt.strip().splitlines()[0])


def derive_ticket(event: Dict[str, Any], cwd: Path, logger) -> Optional[str]:
    """五層 fallback 推導當前 ticket。全部失敗返回 None。"""
    # 層 0：事件 payload（Agent 派發 prompt 首行的 Ticket 標籤）
    t = _ticket_from_agent_payload(event)
    if t:
        return t

    # 層 1：環境變數
    t = os.environ.get("TICKET_ID")
    if t:
        return t

    # 原層 2（讀 dispatch-active.json 取最新派發）已移除：實檔形狀為
    # {"dispatches": [...]}，且全域狀態在並行派發或派發已結束時會取到別張票，
    # 語意不正確；Agent 事件已由層 0 涵蓋。

    # 層 3：git branch
    try:
        result = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=2,
        )
        if result.returncode == 0:
            branch = result.stdout.strip()
            m = re.match(r"feat/(?P<id>[0-9.]+-W\d+-\d+)", branch)
            if m:
                return m.group("id")
    except (subprocess.SubprocessError, FileNotFoundError, OSError) as e:
        logger.info("git branch derivation failed: %s", e)

    # 層 4：全部失敗
    logger.info("unable to derive ticket from any source")
    return None


# ============================================================================
# 手動 /wrap-decision 重置偵測
# ============================================================================

def is_manual_wrap_invocation(event: Dict[str, Any]) -> bool:
    """偵測是否是手動執行 /wrap-decision（走 UserPromptSubmit 或 PostToolUse Bash）。"""
    event_name = event.get("hook_event_name", "")
    if event_name == "UserPromptSubmit":
        prompt = event.get("prompt", "") or ""
        return _starts_with_wrap_command(prompt)
    if event_name == "PostToolUse" and event.get("tool_name") == "Bash":
        return _starts_with_wrap_command(_extract_bash_command(event))
    return False


_WRAP_COMMAND_RE = re.compile(r"^/wrap-decision(\s|$)")


def _starts_with_wrap_command(text: str) -> bool:
    """命令形式比對：去除前導空白後以 /wrap-decision 開頭，其後為空白或結尾。

    檔案路徑中的 /wrap-decision 片段不算手動執行。
    """
    return _WRAP_COMMAND_RE.match(text.lstrip()) is not None


def _extract_bash_command(event: Dict[str, Any]) -> str:
    tool_input = event.get("tool_input") or {}
    if isinstance(tool_input, dict):
        return str(tool_input.get("command", ""))
    return ""


# ============================================================================
# Ticket frontmatter / Solution 章節讀取（S3）
# ============================================================================

def read_ticket_type(ticket_id: str, project_root: Path, logger) -> Optional[str]:
    """讀 ticket frontmatter 的 type 欄位。讀不到返回 None。"""
    # B-2: 改用 hook_utils.find_ticket_file，移除本地重複實作（DRY 原則）。
    path = find_ticket_file(ticket_id, project_root, logger)
    if path is None:
        logger.info("ticket file not found: %s", ticket_id)
        return None
    fm = parse_ticket_frontmatter(path, logger)
    if not fm:
        return None
    t = fm.get("type")
    return str(t) if t else None


def wrap_section_already_written(ticket_id: str, project_root: Path, logger) -> bool:
    """檢查 ticket 的 Solution 章節是否含 WRAP 三問章節。"""
    # B-2: 改用 hook_utils.find_ticket_file。
    path = find_ticket_file(ticket_id, project_root, logger)
    if path is None:
        return False
    try:
        content = path.read_text(encoding="utf-8")
    except OSError:
        return False
    # 尋找常見的 WRAP 章節標題
    patterns = [
        r"##\s+WRAP\s*三問",
        r"##\s+W\s*[（(]\s*Widen\s*[）)]",
        r"WRAP\s+三問\s*（claim\s*Checkpoint",
    ]
    for p in patterns:
        if re.search(p, content, re.IGNORECASE):
            return True
    return False


# ============================================================================
# Signal Strategies
# ============================================================================

class SignalStrategy(Protocol):
    """所有 Signal Strategy 需實作此介面。state 子 key 由 sd.id 決定，不由 Strategy 持有。"""

    def detect(self, event: Dict[str, Any], state: Dict[str, Any],
               sd: SignalDef, current_ticket: Optional[str], logger) -> DetectResult:
        ...

    def apply(self, state: Dict[str, Any], result: DetectResult,
              current_ticket: Optional[str]) -> Dict[str, Any]:
        ...


class ConsecutiveFailuresStrategy:
    # _DEFAULT_SIGNAL_ID 為 apply() 在 result.signal_id 缺失時的備援 key（例如測試直接構造
    # DetectResult 不經 detect()）。正式流程中 detect() 會將 sd.id 寫入 result.signal_id，
    # 此屬性不會實際被使用，避免與 SIGNAL_STRATEGIES key 產生 drift。
    _DEFAULT_SIGNAL_ID = "consecutive_failures"

    # B-1 + C3-1: 失敗判定條件改讀 YAML signals[S1].failure_detection（
    # source-of-truth 原則）。當 YAML 未提供 failure_detection 時，使用以下 backward-compatible
    # 預設值（避開破壞既有測試 fixture）。生產 YAML 已明確列出，故實際 source-of-truth 由 YAML 決定。
    _DEFAULT_FAILURE_STATUSES = ("failed", "error")

    def detect(self, event: Dict[str, Any], state: Dict[str, Any],
               sd: SignalDef, current_ticket: Optional[str], logger) -> DetectResult:
        # 平台代理人派發工具名為 Agent（舊名 Task），兩者皆認
        accepted = {sd.tool_matcher or "Agent", "Agent", "Task"}
        if event.get("tool_name") not in accepted:
            return DetectResult(hit=False, signal_id=sd.id)
        is_failure = self._is_failure(event, sd)
        sig_state = state.setdefault("signals", {}).setdefault(sd.id, {})
        if is_failure:
            new_count = int(sig_state.get("count", 0)) + 1
            threshold = sd.threshold if sd.threshold is not None else 2
            return DetectResult(
                hit=True,
                count=new_count,
                should_warn=(new_count >= threshold),
                signal_id=sd.id,
            )
        else:
            return DetectResult(hit=False, reset=True, signal_id=sd.id)

    def _is_failure(self, event: Dict[str, Any], sd: SignalDef) -> bool:
        # 失敗來源一：PostToolUseFailure 事件即工具層失敗（派發本身失敗）
        if event.get("hook_event_name") == "PostToolUseFailure":
            return True
        # 失敗來源二：PostToolUse 的結構化 status 欄位（YAML 為 source-of-truth）。
        # 不比對 tool_response 全文關鍵字：前景代理人報告常含 error、failed 字樣。
        failure_cfg = sd.raw.get("failure_detection") or {}
        statuses = failure_cfg.get("structured_statuses") or list(self._DEFAULT_FAILURE_STATUSES)
        tr = event.get("tool_response")
        if isinstance(tr, dict):
            status = str(tr.get("status", "")).lower()
            if status in {str(s).lower() for s in statuses}:
                return True
        return False

    def apply(self, state: Dict[str, Any], result: DetectResult,
              current_ticket: Optional[str]) -> Dict[str, Any]:
        sid = result.signal_id or self._DEFAULT_SIGNAL_ID
        sig_state = state.setdefault("signals", {}).setdefault(sid, {})
        if result.reset:
            sig_state["count"] = 0
        elif result.hit and result.count is not None:
            sig_state["count"] = result.count
            sig_state["last_failure_time"] = _state._now().isoformat()
            if current_ticket:
                sig_state["last_signal_ticket"] = current_ticket
        return state


class RestrictiveKeywordsStrategy:
    def detect(self, event: Dict[str, Any], state: Dict[str, Any],
               sd: SignalDef, current_ticket: Optional[str], logger) -> DetectResult:
        prompt = str(event.get("prompt", "") or "")
        if len(prompt) < sd.min_prompt_length:
            return DetectResult(hit=False, signal_id=sd.id)
        if self._is_framework_message(prompt, sd, logger):
            logger.info("signal %s skipped: framework-marked non-user turn", sd.id)
            return DetectResult(hit=False, log_reason="framework_message", signal_id=sd.id)
        haystack = prompt if sd.case_sensitive else prompt.lower()
        matched = None
        for kw in sd.keywords:
            needle = kw if sd.case_sensitive else kw.lower()
            if needle and needle in haystack:
                matched = kw
                break
        if matched is None:
            return DetectResult(hit=False, signal_id=sd.id)
        # context-aware filter（黑名單版）。
        # 觸發詞前後 window 字內含 blacklist 詞 → 視為技術語境陳述，suppress signal。
        if sd.context_blacklist is not None and self._check_context_blacklist(
            prompt, matched, sd.context_blacklist.window, sd.context_blacklist.words,
            sd.case_sensitive,
        ):
            logger.info(
                "signal %s context_blacklist matched; suppressing (keyword=%s)",
                sd.id, matched,
            )
            return DetectResult(hit=False, log_reason="context_blacklist", signal_id=sd.id)
        return DetectResult(hit=True, matched_keyword=matched, should_warn=True, signal_id=sd.id)

    @staticmethod
    def _is_framework_message(prompt: str, sd: SignalDef, logger) -> bool:
        """開頭數行內是否有以框架標記開頭的行（行首比對，非全文子字串）。

        判定失敗時 fail-open：視為使用者回合照常比對關鍵字，
        同時寫 stderr 與日誌，不阻擋。
        """
        try:
            lines = prompt.lstrip().splitlines()[:sd.skip_prompt_scan_lines]
            return any(
                ln.lstrip().startswith(p)
                for ln in lines for p in sd.skip_prompt_prefixes
            )
        except Exception as exc:  # noqa: BLE001 - fail-open，已雙通道記錄
            logger.info("signal %s framework marker check failed: %s", sd.id, exc)
            sys.stderr.write(
                "[wrap-decision-tripwire] framework marker check failed "
                "(fail-open): %s\n" % exc
            )
            return False

    @staticmethod
    def _check_context_blacklist(
        prompt: str, keyword: str, window: int, blacklist: List[str],
        case_sensitive: bool = False,
    ) -> bool:
        """檢查觸發詞前後 window 字內是否含 blacklist 任一詞。

        回傳 True 表示應 suppress signal。case_sensitive=False 時比對採大小寫不敏感
        （與 keyword 匹配邏輯一致）。
        """
        haystack = prompt if case_sensitive else prompt.lower()
        needle = keyword if case_sensitive else keyword.lower()
        idx = haystack.find(needle)
        if idx < 0:
            return False
        start = max(0, idx - window)
        end = min(len(prompt), idx + len(keyword) + window)
        excerpt = prompt[start:end]
        excerpt_cmp = excerpt if case_sensitive else excerpt.lower()
        for bl in blacklist:
            bl_cmp = bl if case_sensitive else bl.lower()
            if bl_cmp and bl_cmp in excerpt_cmp:
                return True
        return False

    def apply(self, state: Dict[str, Any], result: DetectResult,
              current_ticket: Optional[str]) -> Dict[str, Any]:
        if result.hit and result.signal_id:
            sig_state = state.setdefault("signals", {}).setdefault(result.signal_id, {})
            sig_state["last_matched_keyword"] = result.matched_keyword
        return state


class AnaClaimStrategy:
    """S3 ana_claim Strategy。

    project_root_provider: 用於 DI（C1+CE-7）。預設從本模組的 get_project_root 取用，
    測試可透過 monkeypatch 本模組的 get_project_root 覆寫（既有測試相容）。
    """

    def __init__(self, project_root_provider: Optional[Callable[[], Path]] = None):
        self._project_root_provider = project_root_provider

    def detect(self, event: Dict[str, Any], state: Dict[str, Any],
               sd: SignalDef, current_ticket: Optional[str], logger) -> DetectResult:
        if event.get("tool_name") != (sd.tool_matcher or "Bash"):
            return DetectResult(hit=False, signal_id=sd.id)
        cmd = _extract_bash_command(event)
        if not cmd or not sd.command_pattern:
            return DetectResult(hit=False, signal_id=sd.id)
        try:
            m = re.search(sd.command_pattern, cmd)
        except re.error as e:
            logger.info("invalid command_pattern in ana_claim: %s", e)
            return DetectResult(hit=False, signal_id=sd.id)
        if not m:
            return DetectResult(hit=False, signal_id=sd.id)
        ticket_id = self._extract_ticket_id(cmd)
        if not ticket_id:
            return DetectResult(hit=False, signal_id=sd.id)
        # DI：優先用注入的 provider；無則從模組級 get_project_root 取（測試可 monkeypatch）
        project_root = (
            self._project_root_provider()
            if self._project_root_provider is not None
            else get_project_root()
        )
        t_type = read_ticket_type(ticket_id, project_root, logger)
        if t_type is None or t_type != (sd.ticket_type_filter or "ANA"):
            return DetectResult(hit=False, signal_id=sd.id)
        if wrap_section_already_written(ticket_id, project_root, logger):
            logger.info("wrap_section_written suppresses S3 for %s", ticket_id)
            return DetectResult(hit=False, log_reason="wrap_section_written", signal_id=sd.id)
        return DetectResult(hit=True, ticket_id=ticket_id, should_warn=True, signal_id=sd.id)

    def _extract_ticket_id(self, cmd: str) -> Optional[str]:
        m = re.search(r"\b([0-9]+\.[0-9]+\.[0-9]+-W\d+-\d+)\b", cmd)
        if m:
            return m.group(1)
        m = re.search(r"\b(W\d+-\d+)\b", cmd)
        if m:
            return m.group(1)
        return None

    def apply(self, state: Dict[str, Any], result: DetectResult,
              current_ticket: Optional[str]) -> Dict[str, Any]:
        if result.hit and result.ticket_id and result.signal_id:
            sig_state = state.setdefault("signals", {}).setdefault(result.signal_id, {})
            sig_state["last_claimed_ticket"] = result.ticket_id
        return state


# SIGNAL_STRATEGIES key 即為 signal id（與 SignalDef.id 對應），由 _process_signals
# 透過 sd.id 取得 Strategy；Strategy 本體不再持有 signal_id（CE-4+R2 去除 drift 風險）。
SIGNAL_STRATEGIES: Dict[str, SignalStrategy] = {
    "consecutive_failures": ConsecutiveFailuresStrategy(),
    "restrictive_keywords": RestrictiveKeywordsStrategy(),
    "ana_claim": AnaClaimStrategy(),
    # S4 reflection_depth_challenge 使用與 S2 相同的關鍵字匹配邏輯
    # （UserPromptSubmit + keywords + min_prompt_length），但 signal_id 獨立
    # 確保 cooldown state 不跨訊號壓制。訊息前綴差異由 YAML message_template 控制。
    "reflection_depth_challenge": RestrictiveKeywordsStrategy(),
}
