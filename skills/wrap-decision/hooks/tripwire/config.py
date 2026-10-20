"""
設定與訊號定義解析（自 wrap-decision-tripwire-hook.py 拆出，行為不變）。

唯一觸發條件來源：專案的 wrap-triggers.yaml 設定檔（路徑見 CONFIG_REL_PATH）。
禁止在本套件中硬編碼 triggers / keywords / thresholds。
"""

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

# ============================================================================
# 路徑常數
# ============================================================================

CONFIG_REL_PATH = ".claude/config/wrap-triggers.yaml"
DEFAULT_STATE_REL_PATH = ".claude/hook-state/wrap-tripwire-state.json"
EXPECTED_VERSION = "1.0.0"
HOOK_NAME = "wrap-decision-tripwire"


# ============================================================================
# Dataclass
# ============================================================================

@dataclass
class ContextBlacklist:
    """S2 context-aware filter：keyword match 後，
    若觸發詞前後 window 字內含 words 任一者，視為技術語境陳述，suppress signal。
    """
    window: int = 20
    words: List[str] = field(default_factory=list)


@dataclass
class SignalDef:
    id: str
    # category 區分訊號語意分類：
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
    # context-aware filter（黑名單版）。None 表示未啟用。
    context_blacklist: Optional[ContextBlacklist] = None
    # 非使用者撰寫回合的框架標記（選填）。prompt 去除前導空白後以任一前綴開頭，
    # 該訊號整個跳過（代理人交回報告、跨 session 訊息中的字樣是引述，非 PM 結論）。
    skip_prompt_prefixes: List[str] = field(default_factory=list)
    # 只檢查 prompt 開頭幾行（框架會在標記前加一行固定引導句）。
    skip_prompt_scan_lines: int = 3
    raw: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Config:
    version: str = ""
    state_file: str = DEFAULT_STATE_REL_PATH
    warn_cooldown_seconds: int = 300
    hook_mode: str = "advisory"
    signals: List[SignalDef] = field(default_factory=list)
    stderr_prefix: str = "[WRAP Tripwire]"


# ============================================================================
# Config 載入
# ============================================================================

_VALID_RESET_CONDITIONS = {
    "agent_success",
    "ticket_switch",
    "manual_wrap_invocation",
    "wrap_section_written",
    # reflection_trigger 類別新增
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
        # category 預設 wrap_standard（向後相容）
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
        prefixes = item.get("skip_prompt_prefixes") or []
        if isinstance(prefixes, list):
            sd.skip_prompt_prefixes = [str(p) for p in prefixes if str(p)]
        try:
            sd.skip_prompt_scan_lines = int(item.get("skip_prompt_scan_lines", 3))
        except (TypeError, ValueError):
            sd.skip_prompt_scan_lines = 3
        # 解析 context_blacklist（選填）
        cb_raw = item.get("context_blacklist")
        if isinstance(cb_raw, dict):
            words = cb_raw.get("words") or []
            if isinstance(words, list) and words:
                try:
                    window = int(cb_raw.get("window", 20))
                except (TypeError, ValueError):
                    window = 20
                sd.context_blacklist = ContextBlacklist(
                    window=window,
                    words=[str(w) for w in words],
                )
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
