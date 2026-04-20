#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml>=6.0"]
# ///
"""
WRAP 絆腳索 Hook — wrap-decision-tripwire-hook.py

觸發時機：
  - PostToolUse（無 matcher 全捕；內部依 YAML tool_matcher 過濾）
  - UserPromptSubmit

模式：advisory（永遠 exit 0，只提醒不阻擋）

訊號：
  S1 consecutive_failures（category=wrap_standard）：連續代理人派發失敗
  S2 restrictive_keywords（category=wrap_standard）：PM 表達「做不到」類限制性語句
  S3 ana_claim（category=wrap_standard）：claim ANA 類型 ticket 的分析過程
  S4 reflection_depth_challenge（category=reflection_trigger）：反思深度質疑關鍵字

category 分流（W15-018）：
  wrap_standard     → 訊息前綴「[WRAP 絆腳索]」，引導 /wrap-decision
  reflection_trigger → 訊息前綴「[Reflection Trigger]」，引導 three-phase-reflection
各訊號 cooldown 由 state.signals[sd.id] 獨立追蹤，不跨 category 互相壓制。

唯一觸發條件來源：.claude/config/wrap-triggers.yaml（W10-052 約束）
禁止在本檔案中硬編碼 triggers / keywords / thresholds。
"""

import json
import os
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Protocol

import yaml

sys.path.insert(0, str(Path(__file__).parent))
from hook_utils import (
    setup_hook_logging,
    run_hook_safely,
    read_json_from_stdin,
    get_project_root,
    parse_ticket_frontmatter,
    find_ticket_file,
)


# ============================================================================
# 路徑常數
# ============================================================================

CONFIG_REL_PATH = ".claude/config/wrap-triggers.yaml"
DEFAULT_STATE_REL_PATH = ".claude/hook-state/wrap-tripwire-state.json"
EXPECTED_VERSION = "1.0.0"
HOOK_NAME = "wrap-decision-tripwire"


# ============================================================================
# 時間注入點（測試可 monkeypatch）
# ============================================================================

def _now() -> datetime:
    """返回當前時間。測試可透過 monkeypatch 此函式凍結時間。"""
    return datetime.now()


# ============================================================================
# Dataclass
# ============================================================================

@dataclass
class SignalDef:
    id: str
    # category 區分訊號語意分類（W15-018）：
    #   wrap_standard     — S1/S2/S3 標準 WRAP 絆腳索
    #   reflection_trigger — S4 反思深度觸發（three-phase-reflection 方法論）
    # 未標註時預設為 wrap_standard（向後相容）。
    category: str = "wrap_standard"
    enabled: bool = True
    event_sources: List[str] = field(default_factory=list)
    tool_matcher: Optional[str] = None
    threshold: Optional[int] = None
    keywords: List[str] = field(default_factory=list)
    match_mode: str = "substring"
    case_sensitive: bool = False
    min_prompt_length: int = 0
    command_pattern: Optional[str] = None
    ticket_type_filter: Optional[str] = None
    reset_conditions: List[str] = field(default_factory=list)
    message_template: str = ""
    raw: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Config:
    version: str = ""
    state_file: str = DEFAULT_STATE_REL_PATH
    warn_cooldown_seconds: int = 300
    hook_mode: str = "advisory"
    signals: List[SignalDef] = field(default_factory=list)
    stderr_prefix: str = "[WRAP Tripwire]"


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
# Config 載入
# ============================================================================

_VALID_RESET_CONDITIONS = {
    "agent_success",
    "ticket_switch",
    "manual_wrap_invocation",
    "wrap_section_written",
    # W15-018 reflection_trigger 類別新增
    "manual_reflection_invocation",
    "session_end",
}


def _parse_settings(raw: Dict[str, Any], cfg: Config) -> None:
    """將 settings + output 節填入 cfg。"""
    settings = raw.get("settings") or {}
    cfg.state_file = settings.get("state_file", DEFAULT_STATE_REL_PATH)
    cfg.warn_cooldown_seconds = int(settings.get("warn_cooldown_seconds", 300))
    cfg.hook_mode = settings.get("hook_mode", "advisory")

    output = raw.get("output") or {}
    cfg.stderr_prefix = output.get("stderr_prefix", "[WRAP Tripwire]")


def _parse_signals(signals_raw: Any, logger) -> List[SignalDef]:
    """解析 signals list，過濾無效項目。"""
    if not isinstance(signals_raw, list):
        logger.info("signals not a list; treating as empty")
        return []

    signals: List[SignalDef] = []
    for item in signals_raw:
        if not isinstance(item, dict):
            continue
        sd = SignalDef(id=str(item.get("id", "")))
        if not sd.id:
            continue
        # W15-018: category 預設 wrap_standard（向後相容）
        sd.category = str(item.get("category", "wrap_standard"))
        sd.enabled = bool(item.get("enabled", True))
        sd.event_sources = list(item.get("event_sources", []))
        sd.tool_matcher = item.get("tool_matcher")
        sd.threshold = item.get("threshold")
        sd.keywords = list(item.get("keywords", []))
        sd.match_mode = item.get("match_mode", "substring")
        sd.case_sensitive = bool(item.get("case_sensitive", False))
        sd.min_prompt_length = int(item.get("min_prompt_length", 0))
        sd.command_pattern = item.get("command_pattern")
        sd.ticket_type_filter = item.get("ticket_type_filter")
        sd.reset_conditions = list(item.get("reset_conditions", []))
        sd.message_template = item.get("message_template", "")
        sd.raw = item

        if not sd.message_template:
            logger.info("signal %s missing message_template; skipping", sd.id)
            continue

        for rc in sd.reset_conditions:
            if rc not in _VALID_RESET_CONDITIONS:
                logger.info("signal %s unknown reset_condition: %s", sd.id, rc)

        signals.append(sd)
    return signals


def load_config(config_path: Path, logger) -> Optional[Config]:
    """載入 YAML config。失敗時輸出雙通道並返回 None。"""
    if not config_path.exists():
        msg = "[WRAP Tripwire] config missing: {}".format(config_path)
        sys.stderr.write(msg + "\n")
        logger.info("config missing: %s", config_path)
        return None
    try:
        raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        msg = "[WRAP Tripwire] config parse error: {}".format(e)
        sys.stderr.write(msg + "\n")
        logger.info("config parse error: %s", e)
        return None
    except OSError as e:
        msg = "[WRAP Tripwire] config read error: {}".format(e)
        sys.stderr.write(msg + "\n")
        logger.info("config read error: %s", e)
        return None

    if not isinstance(raw, dict):
        sys.stderr.write("[WRAP Tripwire] config root must be mapping\n")
        logger.info("config root is not mapping")
        return None

    cfg = Config()
    cfg.version = str(raw.get("version", ""))
    if cfg.version != EXPECTED_VERSION:
        sys.stderr.write(
            "[WRAP Tripwire] version mismatch (expected={}, got={}); best-effort parsing\n".format(
                EXPECTED_VERSION, cfg.version
            )
        )
        logger.info("version mismatch expected=%s got=%s", EXPECTED_VERSION, cfg.version)

    _parse_settings(raw, cfg)
    cfg.signals = _parse_signals(raw.get("signals") or [], logger)
    return cfg


# ============================================================================
# State 載入與 atomic 寫入
# ============================================================================

def load_state(state_path: Path, logger) -> Dict[str, Any]:
    """讀取 state.json。不存在或 parse 失敗時返回初始狀態。"""
    if not state_path.exists():
        logger.info("state file does not exist; returning initial state: %s", state_path)
        return _initial_state()
    try:
        raw = json.loads(state_path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            logger.info("state file root not mapping; reinitializing")
            return _initial_state()
        logger.info("state loaded: %s", state_path)
        return raw
    except (json.JSONDecodeError, OSError) as e:
        logger.info("state load failed (%s); reinitializing", e)
        return _initial_state()


def _initial_state() -> Dict[str, Any]:
    return {
        "version": "1.0.0",
        "current_ticket": None,
        "last_updated": None,
        "signals": {},
    }


def save_state_atomic(state_path: Path, state: Dict[str, Any], logger) -> None:
    """原子寫入 state.json（tmp + os.replace）。失敗僅記錄不 raise。"""
    try:
        parent = state_path.parent
        parent.mkdir(parents=True, exist_ok=True)
        state["last_updated"] = _now().isoformat()
        fd, tmp_name = tempfile.mkstemp(
            dir=str(parent), prefix=".state-", suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as tmp:
                json.dump(state, tmp, ensure_ascii=False, indent=2)
                tmp.flush()
                os.fsync(tmp.fileno())
            os.replace(tmp_name, state_path)
            logger.info("state saved atomically: %s", state_path)
        except Exception:
            # 清理 tmp
            try:
                os.unlink(tmp_name)
            except OSError:
                pass
            raise
    except Exception as e:
        # 規則 4：雙通道
        sys.stderr.write("[WRAP Tripwire] state write error: {}\n".format(e))
        logger.info("state write failed: %s", e)


# ============================================================================
# Ticket 推導 fallback chain
# ============================================================================

def derive_ticket(event: Dict[str, Any], cwd: Path, logger) -> Optional[str]:
    """四層 fallback 推導當前 ticket。全部失敗返回 None。"""
    # 層 1：環境變數
    t = os.environ.get("TICKET_ID")
    if t:
        return t

    # 層 2：dispatch-active.json
    dispatch_path = cwd / ".claude" / "dispatch-active.json"
    try:
        data = json.loads(dispatch_path.read_text(encoding="utf-8"))
        if isinstance(data, list) and data:
            latest = max(data, key=lambda x: x.get("dispatched_at", "") if isinstance(x, dict) else "")
            if isinstance(latest, dict):
                t = latest.get("ticket_id")
                if t:
                    return t
    except FileNotFoundError:
        logger.info("dispatch-active.json not found (normal in many sessions)")
    except (json.JSONDecodeError, OSError) as e:
        logger.info("dispatch-active.json unreadable: %s", e)

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
        return "/wrap-decision" in prompt
    if event_name == "PostToolUse" and event.get("tool_name") == "Bash":
        cmd = _extract_bash_command(event)
        return "/wrap-decision" in cmd
    return False


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
    # B-2 (W10-056.3): 改用 hook_utils.find_ticket_file，移除本地重複實作（DRY 原則）。
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
    # B-2 (W10-056.3): 改用 hook_utils.find_ticket_file。
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

    # B-1 + C3-1 (W10-056.3): 失敗判定條件改讀 YAML signals[S1].failure_detection（W10-052
    # source-of-truth 原則）。當 YAML 未提供 failure_detection 時，使用以下 backward-compatible
    # 預設值（避開破壞既有測試 fixture）。生產 YAML 已明確列出，故實際 source-of-truth 由 YAML 決定。
    _DEFAULT_FAILURE_KEYWORDS = ("error", "exception", "failed", "timeout")
    _DEFAULT_FAILURE_STATUSES = ("failed", "error")

    def detect(self, event: Dict[str, Any], state: Dict[str, Any],
               sd: SignalDef, current_ticket: Optional[str], logger) -> DetectResult:
        if event.get("tool_name") != (sd.tool_matcher or "Task"):
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
        # 從 YAML 讀取失敗判定條件（W10-052 source-of-truth）
        failure_cfg = sd.raw.get("failure_detection") or {}
        statuses = failure_cfg.get("structured_statuses") or list(self._DEFAULT_FAILURE_STATUSES)
        keywords = failure_cfg.get("keywords") or list(self._DEFAULT_FAILURE_KEYWORDS)

        tr = event.get("tool_response")
        # 結構化失敗標記
        if isinstance(tr, dict):
            status = str(tr.get("status", "")).lower()
            if status in {str(s).lower() for s in statuses}:
                return True
        # 字串關鍵字（fallback）
        text = json.dumps(tr, ensure_ascii=False) if tr is not None else ""
        low = text.lower()
        for kw in keywords:
            if str(kw).lower() in low:
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
            sig_state["last_failure_time"] = _now().isoformat()
            if current_ticket:
                sig_state["last_signal_ticket"] = current_ticket
        return state


class RestrictiveKeywordsStrategy:
    def detect(self, event: Dict[str, Any], state: Dict[str, Any],
               sd: SignalDef, current_ticket: Optional[str], logger) -> DetectResult:
        prompt = str(event.get("prompt", "") or "")
        if len(prompt) < sd.min_prompt_length:
            return DetectResult(hit=False, signal_id=sd.id)
        haystack = prompt if sd.case_sensitive else prompt.lower()
        matched = None
        for kw in sd.keywords:
            needle = kw if sd.case_sensitive else kw.lower()
            if needle and needle in haystack:
                matched = kw
                break
        if matched is None:
            return DetectResult(hit=False, signal_id=sd.id)
        return DetectResult(hit=True, matched_keyword=matched, should_warn=True, signal_id=sd.id)

    def apply(self, state: Dict[str, Any], result: DetectResult,
              current_ticket: Optional[str]) -> Dict[str, Any]:
        if result.hit and result.signal_id:
            sig_state = state.setdefault("signals", {}).setdefault(result.signal_id, {})
            sig_state["last_matched_keyword"] = result.matched_keyword
        return state


class AnaClaimStrategy:
    """S3 ana_claim Strategy。

    project_root_provider: 用於 DI（C1+CE-7）。預設從模組 get_project_root 取用，
    測試可透過 monkeypatch hook 模組的 get_project_root 覆寫（既有測試相容）。
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
    # W15-018: S4 reflection_depth_challenge 使用與 S2 相同的關鍵字匹配邏輯
    # （UserPromptSubmit + keywords + min_prompt_length），但 signal_id 獨立
    # 確保 cooldown state 不跨訊號壓制。訊息前綴差異由 YAML message_template 控制。
    "reflection_depth_challenge": RestrictiveKeywordsStrategy(),
}


# ============================================================================
# Cooldown / 重置輔助
# ============================================================================

def in_cooldown(state: Dict[str, Any], signal_id: str, cooldown_seconds: int) -> bool:
    sig_state = state.get("signals", {}).get(signal_id, {})
    last_warned = sig_state.get("last_warned_at")
    if not last_warned:
        return False
    try:
        last_dt = datetime.fromisoformat(last_warned)
    except (TypeError, ValueError):
        return False
    elapsed = (_now() - last_dt).total_seconds()
    if elapsed < 0:
        # 時鐘倒退 → 視為已過 cooldown
        return False
    return elapsed < cooldown_seconds


def mark_warned(state: Dict[str, Any], signal_id: str) -> Dict[str, Any]:
    sig_state = state.setdefault("signals", {}).setdefault(signal_id, {})
    sig_state["last_warned_at"] = _now().isoformat()
    return state


def apply_ticket_switch_reset(state: Dict[str, Any], current_ticket: Optional[str]) -> Dict[str, Any]:
    """若 ticket 變化則全訊號歸零。current_ticket 為 None 時不動。"""
    if current_ticket is None:
        return state
    prev = state.get("current_ticket")
    if prev != current_ticket:
        state["current_ticket"] = current_ticket
        state["signals"] = {}
    return state


def reset_all_signals(state: Dict[str, Any]) -> Dict[str, Any]:
    state["signals"] = {}
    return state


# ============================================================================
# Message rendering
# ============================================================================

def render_message(sd: SignalDef, result: DetectResult,
                   current_ticket: Optional[str]) -> str:
    # 使用 format_map + 白名單 keys 避免 f-string 注入風險
    safe = {
        "count": result.count if result.count is not None else "",
        "ticket_id": result.ticket_id or current_ticket or "",
        "matched_keyword": result.matched_keyword or "",
        "signal_id": sd.id,
    }
    # 使用 defaultdict-style 處理缺 key
    class _Safe(dict):
        def __missing__(self, key):
            return "{" + key + "}"
    try:
        return sd.message_template.format_map(_Safe(**safe))
    except Exception:
        return sd.message_template


# ============================================================================
# 主流程
# ============================================================================

def _process_signals(
    event: Dict[str, Any],
    event_name: str,
    state: Dict[str, Any],
    config: Config,
    current_ticket: Optional[str],
    logger,
) -> List[str]:
    """逐 signal 執行 detect/apply，回傳應輸出的 warning 字串清單。

    副作用：會就地修改 state（cooldown / 計數等）。
    """
    warnings: List[str] = []
    for sd in config.signals:
        if not sd.enabled:
            continue
        if event_name not in sd.event_sources:
            continue
        strategy = SIGNAL_STRATEGIES.get(sd.id)
        if strategy is None:
            logger.info("unknown signal id (no strategy): %s", sd.id)
            continue
        try:
            result = strategy.detect(event, state, sd, current_ticket, logger)
        except Exception as e:
            logger.info("signal %s detect error: %s", sd.id, e)
            continue
        state = strategy.apply(state, result, current_ticket)

        if result.should_warn and not in_cooldown(state, sd.id, config.warn_cooldown_seconds):
            msg = render_message(sd, result, current_ticket)
            warnings.append(msg)
            state = mark_warned(state, sd.id)
            logger.info("signal %s triggered; warning emitted", sd.id)
        elif result.should_warn:
            logger.info("signal %s in cooldown; warning suppressed", sd.id)
    return warnings


def main() -> int:
    logger = setup_hook_logging(HOOK_NAME)
    event = read_json_from_stdin(logger)
    if event is None:
        return 0

    project_root = get_project_root()
    config_path = project_root / CONFIG_REL_PATH

    config = load_config(config_path, logger)
    if config is None:
        return 0

    state_path = project_root / config.state_file
    state = load_state(state_path, logger)
    cwd = Path(event.get("cwd") or project_root)

    current_ticket = derive_ticket(event, cwd, logger)
    state = apply_ticket_switch_reset(state, current_ticket)

    if is_manual_wrap_invocation(event):
        state = reset_all_signals(state)
        logger.info("manual /wrap-decision detected; all signals reset")

    event_name = event.get("hook_event_name", "")
    warnings = _process_signals(event, event_name, state, config, current_ticket, logger)

    save_state_atomic(state_path, state, logger)

    if warnings:
        sys.stderr.write("\n".join(warnings) + "\n")

    return 0


if __name__ == "__main__":
    sys.exit(run_hook_safely(main, HOOK_NAME))
