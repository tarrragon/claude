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

category 分流：
  wrap_standard     → 訊息前綴「[WRAP 絆腳索]」，引導 /wrap-decision
  reflection_trigger → 訊息前綴「[Reflection Trigger]」，引導 three-phase-reflection
各訊號 cooldown 由 state.signals[sd.id] 獨立追蹤，不跨 category 互相壓制。

結構：本檔只保留 main 流程（_process_signals / main），其餘職責在同目錄 tripwire/ 套件
（config / state / signals / render），原頂層名稱由本檔 re-export。pyyaml 依賴由
tripwire/config.py 實際 import，PEP 723 宣告須保留。

唯一觸發條件來源：.claude/config/wrap-triggers.yaml（W10-052 約束，portability-allow: 此 skill 對消費端環境的選用性依賴——缺該設定檔時 advisory 模式優雅降級為不觸發，非硬性中止；沿用時如需啟用訊號偵測，需提供對應設定檔）
禁止在本檔案中硬編碼 triggers / keywords / thresholds。
"""

import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# 加入框架共用程式庫路徑：.claude/（for `from lib import ...`）+ .claude/hooks/（portability-allow: 架構性橋接至框架共用模組，consumer 端結構相同）
_claude_dir = Path(__file__).resolve().parents[3]
_hooks_dir = _claude_dir / "hooks"
if _hooks_dir not in [Path(p) for p in sys.path]:
    sys.path.insert(0, str(_hooks_dir))
if _claude_dir not in [Path(p) for p in sys.path]:
    sys.path.insert(0, str(_claude_dir))

# 本 hook 同目錄：tripwire/ 套件。hook-dispatcher in-process 載入與 `uv run` 單獨執行
# 兩種方式 sys.path 皆不含此目錄，須自行掛載。
_self_dir = Path(__file__).resolve().parent
if _self_dir not in [Path(p) for p in sys.path]:
    sys.path.insert(0, str(_self_dir))

try:
    from lib import (
        setup_hook_logging,
        run_hook_safely,
        read_json_from_stdin,
        get_project_root,
        get_effort_level,
        emit_hook_output,
    )
    _LIB_AVAILABLE = True
except ImportError:
    # 消費端未提供 .claude/lib/ 時優雅降級（portability-allow: 選用性依賴，
    # 缺件優雅降級，非可攜性違規）：main() 開頭直接印出 [WARNING] 並
    # return 0（advisory hook 本就以 exit 0 為常態，不阻擋任何操作）。
    _LIB_AVAILABLE = False

# 以下為 re-export：保留原頂層匯入路徑（tripwire.signals 在缺 lib 時仍可匯入）。
# 刻意不 re-export `_now`：時鐘注入點在 tripwire.state，hook 檔留一份副本會讓
# 對副本的 monkeypatch 靜默無效。
from tripwire.config import (  # noqa: E402,F401
    CONFIG_REL_PATH,
    DEFAULT_STATE_REL_PATH,
    EXPECTED_VERSION,
    HOOK_NAME,
    Config,
    ContextBlacklist,
    SignalDef,
    _VALID_RESET_CONDITIONS,
    _parse_settings,
    _parse_signals,
    load_config,
)
from tripwire.state import (  # noqa: E402,F401
    STALE_STATE_DAYS,
    _initial_state,
    apply_ticket_switch_reset,
    in_cooldown,
    load_state,
    mark_warned,
    prune_stale_state_files,
    reset_all_signals,
    resolve_state_path,
    save_state_atomic,
)
from tripwire.signals import (  # noqa: E402,F401
    SIGNAL_STRATEGIES,
    AnaClaimStrategy,
    ConsecutiveFailuresStrategy,
    DetectResult,
    RestrictiveKeywordsStrategy,
    SignalStrategy,
    _WRAP_COMMAND_RE,
    _extract_bash_command,
    _starts_with_wrap_command,
    _ticket_from_agent_payload,
    derive_ticket,
    is_manual_wrap_invocation,
    read_ticket_type,
    wrap_section_already_written,
)
from tripwire.render import (  # noqa: E402,F401
    _EXCERPT_RADIUS,
    _build_prompt_excerpt,
    render_message,
)


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
            # 保留原訊息行（向後相容既有 grep / 掃描工具）
            logger.info("signal %s triggered; warning emitted", sd.id)
            # 附加觀測欄位（matched_keyword + prompt_excerpt），供
            # 未來 S2 誤報率重評時依關鍵字 / 上下文分類樣本。S1/S3 等無 keyword
            # 或無 prompt 的 signal 填 "-"。
            kw = result.matched_keyword or "-"
            prompt = str(event.get("prompt", "") or "")
            excerpt = _build_prompt_excerpt(prompt, result.matched_keyword)
            logger.info(
                "signal %s observability matched_keyword=%s prompt_excerpt=%s",
                sd.id, kw, excerpt,
            )
        elif result.should_warn:
            logger.info("signal %s in cooldown; warning suppressed", sd.id)
    return warnings


def is_pytest_environment() -> bool:
    """偵測是否在 pytest 測試環境（MVP）。

    觸發條件（任一成立即視為 pytest 環境）：
      - PYTEST_CURRENT_TEST env var 存在（pytest 主流程自動注入）
      - 當前工作目錄路徑含 'pytest-of-'（pytest tmp_path fixture 慣例）

    用途：避免 hook 在自身的 unit test 中觸發 detection（hit 2 fixture 字串污染）。
    """
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return True
    try:
        cwd_str = str(Path.cwd())
    except (FileNotFoundError, OSError):
        return False
    if "pytest-of-" in cwd_str:
        return True
    return False


def main() -> int:
    if not _LIB_AVAILABLE:
        sys.stderr.write(
            "[WARNING] wrap-decision-tripwire-hook 未執行：找不到 .claude/lib/，"
            "此為消費端需自行提供的框架共用模組（advisory WRAP 訊號偵測功能"
            "停用，不影響其他操作）。\n"
        )
        return 0
    logger = setup_hook_logging(HOOK_NAME)
    event = read_json_from_stdin(logger)
    if event is None:
        return 0

    if is_pytest_environment():
        logger.debug("pytest environment detected, skipping detection")
        return 0

    # Effort 感知（v2.1.133+）：本 hook 為 advisory WRAP 訊號偵測（PC-066/PC-093）
    # 屬「事實判斷」核心訊號，low effort 下仍必須提醒，不短路放行（quality-baseline 規則 6 防護）
    effort = get_effort_level(event)
    logger.info("effort=%s，wrap-decision-tripwire 維持完整偵測（advisory，不依 effort 放行）", effort)

    project_root = get_project_root()
    config_path = project_root / CONFIG_REL_PATH

    config = load_config(config_path, logger)
    if config is None:
        return 0

    base_state_path = project_root / config.state_file
    state_path = resolve_state_path(base_state_path, event, logger)
    prune_stale_state_files(base_state_path, state_path, logger)
    state = load_state(state_path, logger)
    cwd = Path(event.get("cwd") or project_root)

    current_ticket = derive_ticket(event, cwd, logger)
    state = apply_ticket_switch_reset(state, current_ticket)

    if is_manual_wrap_invocation(event):
        state = reset_all_signals(state)
        logger.info("manual /wrap-decision detected; signals of this state file reset")

    event_name = event.get("hook_event_name", "")
    warnings = _process_signals(event, event_name, state, config, current_ticket, logger)

    save_state_atomic(state_path, state, logger)

    if warnings:
        message = "\n".join(warnings)
        # stderr 保留作日誌；exit 0 時 stderr 不進模型 context（305 實測），
        # 故另以 additionalContext 輸出。audience 用預設 "all"：訊號偵測的是
        # 當前執行緒自身的決策過程（PM 的派發失敗/限制性語句，代理人的 ANA
        # claim），兩者皆為提醒對象，pm_only 會讓代理人端的 S3 提醒被丟棄。
        sys.stderr.write(message + "\n")
        emit_hook_output(event_name, additional_context=message)

    return 0


if __name__ == "__main__":
    if _LIB_AVAILABLE:
        sys.exit(run_hook_safely(main, HOOK_NAME))
    else:
        sys.exit(main())
