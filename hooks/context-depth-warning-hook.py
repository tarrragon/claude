#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""context-depth-warning-hook (Stop event)

Why:
  用戶需求：context 合計超過 400K 時，提示做 compact 或寫 handoff 換 session。
  背景：早期分析發現 cache_read 達 ~230K 後 tool-call malformed 復發率升高，
  深 context 的 retry 成本也是提早收斂的理由之一。

Consequence（不處理的代價）:
  用戶在無提示下持續累積 context，品質與回合成本惡化而難以察覺根因。

Action:
  每個 Stop event 讀 transcript 最後一則 assistant entry 的 usage，
  合計 input_tokens + cache_creation_input_tokens + cache_read_input_tokens。
  合計 >= THRESHOLD（預設 400K）且當前 tier 尚未提示 → 以 emit_hook_output
  輸出 additionalContext（模型可見；含 K 數、請用戶 /compact、或寫 handoff 後
  claude -n 開新 session）+ 更新去重 state + 檔案日誌。

  分層去重（避免提示疲勞）：tier = 合計 // TIER_STEP（預設 50K）。每跨入更深
  的 tier 才再提示一次。state file 記 {session_id: last_warned_tier}；
  合計降回 THRESHOLD 以下時清除該 session 的 state，再超過會重新提示。

  環境變數覆寫：CONTEXT_DEPTH_WARNING_THRESHOLD、CONTEXT_DEPTH_WARNING_TIER_STEP、
  CONTEXT_DEPTH_WARNING_STATE（state 檔路徑，供測試隔離）。

  永遠 exit 0：本 hook 為提示性質，禁 exit 2 阻擋 Stop（與同 Stop event 的
  malformed-tool-call-detector 職責分離——後者 exit 2 阻擋格式錯誤，本 hook
  僅提示深度，不打斷對話）。所有 IO/解析失敗吞掉並 exit 0，但寫檔案日誌
  （雙通道可觀測性，quality-baseline 規則 4）。
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from lib import emit_hook_output  # noqa: E402

HOOK_DIR = Path(__file__).resolve().parent
LOG_DIR = HOOK_DIR / "hook-logs"
LOG_FILE = LOG_DIR / "context-depth-warning.log"
DEFAULT_STATE_FILE = LOG_DIR / "context-depth-warning-state.json"

# 常數（集中管理，模組頂層）
DEFAULT_THRESHOLD = 400_000  # 用戶需求：合計 context 超過 400K 提示
DEFAULT_TIER_STEP = 50_000   # 每加深 50K 再提示一次，避免每回合疲勞


def _env_int(name: str, default: int) -> int:
    """讀整數環境變數，非法值回預設。"""
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return default


THRESHOLD = _env_int("CONTEXT_DEPTH_WARNING_THRESHOLD", DEFAULT_THRESHOLD)
TIER_STEP = _env_int("CONTEXT_DEPTH_WARNING_TIER_STEP", DEFAULT_TIER_STEP)
USAGE_FIELDS = (
    "input_tokens",
    "cache_creation_input_tokens",
    "cache_read_input_tokens",
)


def _state_file() -> Path:
    """state file 路徑（可由環境變數覆寫，供測試隔離）。"""
    override = os.environ.get("CONTEXT_DEPTH_WARNING_STATE")
    return Path(override) if override else DEFAULT_STATE_FILE


def log(message: str) -> None:
    """雙通道可觀測性：寫檔案日誌（stderr 留給提示訊息本身）。"""
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with LOG_FILE.open("a", encoding="utf-8") as fh:
            fh.write(f"[{stamp}] {message}\n")
    except Exception as exc:  # noqa: BLE001 - 日誌失敗不可反過來阻斷主流程
        sys.stderr.write(f"[context-depth-warning] log 失敗: {exc}\n")


def read_last_total_context(transcript_path: str) -> Optional[int]:
    """從 transcript JSONL 取最後一則 assistant entry 的
    usage 合計（input + cache_creation + cache_read）。讀不到回 None。"""
    path = Path(transcript_path)
    if not path.is_file():
        return None

    last_value: Optional[int] = None
    try:
        with path.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                message = entry.get("message") or entry
                if message.get("role") != "assistant":
                    continue
                usage = message.get("usage")
                if not isinstance(usage, dict):
                    continue
                if not isinstance(usage.get("cache_read_input_tokens"), int):
                    continue
                last_value = sum(
                    v for v in (usage.get(f) for f in USAGE_FIELDS)
                    if isinstance(v, int)
                )
    except Exception as exc:  # noqa: BLE001
        log(f"讀 transcript 失敗: {exc}")
        return None
    return last_value


def tier_of(total_context: int) -> int:
    """total_context（三項合計）對應的去重 tier。"""
    return total_context // TIER_STEP


def should_warn(total_context: int, last_warned_tier: int) -> bool:
    """是否應提示：超閾值且當前 tier 比已提示的 tier 更深。"""
    if total_context < THRESHOLD:
        return False
    return tier_of(total_context) > last_warned_tier


def load_state(state_file: Path) -> dict:
    """讀去重 state（{session_id: last_warned_tier}）。失敗回空 dict。"""
    try:
        if not state_file.is_file():
            return {}
        data = json.loads(state_file.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception as exc:  # noqa: BLE001
        log(f"讀 state 失敗: {exc}")
        return {}


def save_state(state_file: Path, state: dict) -> None:
    """寫去重 state。失敗僅記錄，不阻斷主流程。"""
    try:
        state_file.parent.mkdir(parents=True, exist_ok=True)
        state_file.write_text(
            json.dumps(state, ensure_ascii=False), encoding="utf-8"
        )
    except Exception as exc:  # noqa: BLE001
        log(f"寫 state 失敗: {exc}")


def _warning_text(total_context: int) -> str:
    return (
        f"[context-depth-warning] 當前 context 合計約 {total_context // 1000}K tokens"
        f"（input + cache_creation + cache_read），已超過 {THRESHOLD // 1000}K。"
        "請告知用戶擇一處理：(1) 請用戶執行 /compact（模型無法自行觸發）；"
        "(2) 先把進度寫入 ticket 與 handoff，再請用戶以 "
        "`claude -n <線主題>` 開新 session 接續。"
    )


def main() -> int:
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        payload = {}
    if not isinstance(payload, dict):
        payload = {}

    transcript_path = payload.get("transcript_path", "")
    session_id = payload.get("session_id", "")
    if not transcript_path:
        return 0

    total_context = read_last_total_context(transcript_path)
    if total_context is None:
        return 0

    state_file = _state_file()
    state = load_state(state_file)
    last_warned_tier = state.get(session_id, -1)
    if not isinstance(last_warned_tier, int):
        last_warned_tier = -1

    if total_context < THRESHOLD:
        if session_id in state:  # 降回門檻以下：清除去重，再超過會重新提示
            del state[session_id]
            save_state(state_file, state)
        return 0

    if not should_warn(total_context, last_warned_tier):
        return 0

    state[session_id] = tier_of(total_context)
    save_state(state_file, state)
    log(
        f"提示 context 深度 session={session_id!r} total={total_context} "
        f"tier={tier_of(total_context)}"
    )
    emit_hook_output("Stop", additional_context=_warning_text(total_context))
    return 0


# ---------------------------------------------------------------------------
# 內嵌 self-test（仿 malformed-detector 設計，由 --self-test 分支執行）
# ---------------------------------------------------------------------------


def _self_test() -> list:
    """執行純函式層級的閾值 / 去重 self-test，回傳失敗描述清單（空=全通過）。"""
    failures = []

    # 1. 低於閾值 → 不觸發
    if should_warn(THRESHOLD - 1, last_warned_tier=-1):
        failures.append("低於閾值不應觸發，卻觸發")

    # 2. 到閾值且該 tier 未提示 → 觸發
    if not should_warn(THRESHOLD, last_warned_tier=-1):
        failures.append("到閾值首次應觸發，卻未觸發")

    # 3. 同 tier 已提示 → 不重複
    same_tier = tier_of(THRESHOLD)
    if should_warn(THRESHOLD, last_warned_tier=same_tier):
        failures.append("同 tier 已提示不應重複，卻重複")

    # 4. 跨下一 tier → 再次觸發
    deeper = THRESHOLD + TIER_STEP
    if tier_of(deeper) <= same_tier:
        failures.append("TIER_STEP 設定異常：跨 step 未進入更深 tier")
    if not should_warn(deeper, last_warned_tier=same_tier):
        failures.append("跨下一 tier 應再次觸發，卻未觸發")

    return failures


if __name__ == "__main__":
    if "--self-test" in sys.argv[1:]:
        problems = _self_test()
        if problems:
            sys.stderr.write("[context-depth-warning] self-test 失敗:\n")
            for item in problems:
                sys.stderr.write(f"  - {item}\n")
            sys.exit(1)
        sys.stdout.write(
            "[context-depth-warning] self-test 通過：閾值/去重 4 案例\n"
        )
        sys.exit(0)
    sys.exit(main())
