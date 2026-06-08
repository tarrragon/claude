#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""context-depth-warning-hook (Stop event) — 0.20.0-W2-013

Why:
  W2-012 ANA 結論：count-token malformed tool-call 的根因在模型 sampling 層，
  cache_read ~230K tokens 後 malformed 復發率升至 41.5%。W2-011 的偵測 + retry
  已攔截實際危害，但未消除 retry 的 token 與回合開銷——每進入高 context 深度，
  retry 窗口的累積成本仍在。本 hook 在 context 深度接近高頻 retry 窗口前主動提示
  用戶考慮 /clear 或 ticket handoff，降低進入高 retry 窗口的機率。

Consequence（不處理的代價）:
  用戶在無提示下持續累積 context，進入 ~230K 後的高頻 retry 窗口，每 2.4 個
  tool-call turn 即有一次 retry，浪費回合與重發 token，且難以察覺根因。

Action:
  每個 Stop event 讀 transcript 最後一則 assistant entry 的
  message.usage.cache_read_input_tokens。超過 THRESHOLD 且該 session 的當前
  tier 尚未提示過 → stderr 提示 + 更新去重 state + 檔案日誌。

  分層去重（避免提示疲勞）：tier = cache_read // TIER_STEP。每跨入更深的 tier
  才再提示一次，同 tier 內重複的 Stop event 不重發。state file 記
  {session_id: last_warned_tier}。

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

HOOK_DIR = Path(__file__).resolve().parent
LOG_DIR = HOOK_DIR / "hook-logs"
LOG_FILE = LOG_DIR / "context-depth-warning.log"
DEFAULT_STATE_FILE = LOG_DIR / "context-depth-warning-state.json"

# 常數（集中管理，模組頂層）
THRESHOLD = 180_000  # W2-012 onset ~230K，提前 50K 緩衝主動提示
TIER_STEP = 30_000   # 每加深 30K 再提示一次，避免每回合疲勞


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


def read_last_cache_read(transcript_path: str) -> Optional[int]:
    """從 transcript JSONL 取最後一則 assistant entry 的
    message.usage.cache_read_input_tokens。讀不到回 None。"""
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
                value = usage.get("cache_read_input_tokens")
                if isinstance(value, int):
                    last_value = value
    except Exception as exc:  # noqa: BLE001
        log(f"讀 transcript 失敗: {exc}")
        return None
    return last_value


def tier_of(cache_read: int) -> int:
    """cache_read 對應的去重 tier。"""
    return cache_read // TIER_STEP


def should_warn(cache_read: int, last_warned_tier: int) -> bool:
    """是否應提示：超閾值且當前 tier 比已提示的 tier 更深。"""
    if cache_read < THRESHOLD:
        return False
    return tier_of(cache_read) > last_warned_tier


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


def _warning_text(cache_read: int) -> str:
    return (
        f"[context-depth-warning] 當前 context 深度約 {cache_read // 1000}K tokens"
        "（cache_read）。依 W2-012，~230K 後 tool-call malformed 復發率升至 41.5%，"
        "每次 retry 浪費回合與 token。建議在進入高頻 retry 窗口前考慮 /clear 或 "
        "ticket handoff 保存進度。\n"
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

    cache_read = read_last_cache_read(transcript_path)
    if cache_read is None:
        return 0

    state_file = _state_file()
    state = load_state(state_file)
    last_warned_tier = state.get(session_id, -1)
    if not isinstance(last_warned_tier, int):
        last_warned_tier = -1

    if not should_warn(cache_read, last_warned_tier):
        return 0

    state[session_id] = tier_of(cache_read)
    save_state(state_file, state)
    log(
        f"提示 context 深度 session={session_id!r} cache_read={cache_read} "
        f"tier={tier_of(cache_read)}"
    )
    sys.stderr.write(_warning_text(cache_read))
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
