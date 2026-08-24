#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml"]
# ///

"""
Hook Health Monitor - Hook 系統健康狀態監控

在 SessionStart 時檢查所有 SessionStart Hook 的運作狀態。

檢查內容：
1. 動態解析 settings.json 中所有 SessionStart hooks
2. 驗證每個 hook 的日誌目錄是否正常更新
3. 報告覆蓋全部 SessionStart hooks 的健康狀態

Exit Code:
- 0: 所有 Hook 正常或僅有警告

使用方式：
  由 SessionStart Hook 自動觸發

運作邏輯：
1. 從 settings.json 動態載入所有 SessionStart hooks（不硬編碼）
2. 純機械推導解析各 hook 對應的日誌目錄
3. 檢查日誌目錄最新修改時間
4. 輸出覆蓋全部 hooks 的健康報告
5. 失敗的 hook 資訊輸出到 stderr

改進 (v2.0.0):
- 動態解析 settings.json 取得所有 SessionStart hooks
- 移除硬編碼 MONITORED_HOOKS
- 純機械推導解析日誌目錄（命名一致性已修復）
- 失敗 hook 資訊輸出到 stderr
"""

import json
import logging
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Tuple, List, Dict

# 添加 lib 目錄到路徑（M-003 標準化）
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from lib import setup_hook_logging, run_hook_safely
    from lib.common_functions import get_project_root, hook_output
    from lib import hook_health
except ImportError as e:
    print(json.dumps({"result": "continue"}))
    print(f"[Hook Import Error] {Path(__file__).name}: {e}", file=sys.stderr)
    sys.exit(0)

# ============================================================================
# 常數定義
# ============================================================================

WARNING_THRESHOLD_HOURS = 24  # 發出警告的時間閾值
CRITICAL_THRESHOLD_HOURS = 48  # 發出嚴重警告的時間閾值

# W13-017: 觸發頻率掃描使用「7 天 baseline」(W13-008 量化標準)
FREQUENCY_SCAN_WINDOW_DAYS = 7

# W13-017: marker file 相對於 project_root 的路徑
SESSION_MARKER_RELPATH = (".claude", "state", "last-session-start.marker")


# ============================================================================
# 輔助函式
# ============================================================================

def _extract_filename_from_command(command: str) -> Optional[str]:
    """從 .claude/hooks/ 下的 hook command 字串中提取 .py 檔案名稱

    只處理位於 .claude/hooks/ 目錄下的 hook，
    忽略 skills 腳本或其他路徑的 command（避免無效的監控目標）。

    Args:
        command: hook command 字串

    Returns:
        hook 檔案名稱（如 'foo.py'），或 None（非 hooks 目錄、非 .py、或格式不符）
    """
    if not command:
        return None
    # 支援三種形式：裸路徑、'uv run [--quiet] <path>'、'python3 <path>'。
    # 不再假設 command_parts[0] 即為 hook 路徑，改在整個 command 字串中
    # 找出 .claude/hooks/ 下的 .py token（889 遷移引入顯式解譯器前綴後，
    # command_parts[0] 可能是 'uv' 或 'python3' 而非 hook 路徑本身）。
    for part in command.split():
        hook_path = part
        if hook_path.startswith('$CLAUDE_PROJECT_DIR/'):
            hook_path = hook_path.replace('$CLAUDE_PROJECT_DIR/', '')
        if '.claude/hooks/' not in hook_path:
            continue
        hook_filename = Path(hook_path).name
        if hook_filename.endswith('.py'):
            return hook_filename
    return None


def load_sessionstart_hooks_from_settings(
    settings_path: Path
) -> List[str]:
    """從 settings.json 動態載入所有 SessionStart hooks 的檔案名稱

    Args:
        settings_path: settings.json 檔案路徑

    Returns:
        去重的 hook 檔案名稱清單（如 ['cli-dependency-check.py', ...]）
    """
    if not settings_path.exists():
        return []

    try:
        with open(settings_path, 'r', encoding='utf-8') as f:
            settings = json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        print(
            f"[hook-health-monitor] Failed to parse settings.json: {e}",
            file=sys.stderr
        )
        return []

    hook_filenames = set()
    hooks = settings.get('hooks', {})
    session_start_hooks = hooks.get('SessionStart', [])

    for hook_group in session_start_hooks:
        hooks_list = hook_group.get('hooks', [])
        for hook in hooks_list:
            filename = _extract_filename_from_command(hook.get('command', ''))
            if filename:
                hook_filenames.add(filename)

    return sorted(hook_filenames)


def _resolve_hook_name_from_source(
    hook_filename: str, project_root: Path
) -> Optional[str]:
    """從 hook 原始碼掃描 `HOOK_NAME = "..."` 常數

    部分 hook 呼叫 `setup_hook_logging(HOOK_NAME)` 時，HOOK_NAME 是與檔名
    stem（去 `-hook` 後綴亦不符）無關的自訂短名（如某 MCP 可用性檢查 hook
    的 HOOK_NAME 為與檔名無關的短名）。stem 與 stem 去 `-hook` 兩種猜測皆
    無法命中時，改讀原始碼常數作第三層 fallback，避免誤判為
    「log dir not found」。

    Args:
        hook_filename: hook 檔案名稱（如 'foo-check-hook.py'）
        project_root: 專案根目錄

    Returns:
        HOOK_NAME 常數字串值，或 None（找不到檔案/常數）
    """
    hook_path = project_root / ".claude" / "hooks" / hook_filename
    if not hook_path.is_file():
        return None

    try:
        source = hook_path.read_text(encoding="utf-8")
    except OSError:
        return None

    for line in source.splitlines():
        stripped = line.strip()
        if not stripped.startswith("HOOK_NAME"):
            continue
        if "=" not in stripped:
            continue
        _, _, value_part = stripped.partition("=")
        value = value_part.strip()
        if value.startswith(('"', "'")) and value.endswith(('"', "'")) and len(value) >= 2:
            return value[1:-1]

    return None


def resolve_hook_log_dir(
    hook_filename: str, project_root: Path
) -> Tuple[str, Path, bool]:
    """根據 hook 檔案名稱解析對應的日誌目錄

    優先使用檔名 stem 作為 log dir，若不存在則嘗試去掉 `-hook` 後綴的 fallback。
    原因：部分 hook 呼叫 `setup_hook_logging("xxx")` 時傳入不含 `-hook` 的類別名
    （如 file-size-guardian-hook.py 實際 log dir 為 file-size-guardian/）。
    兩者皆不符時（如自訂 HOOK_NAME 常數與檔名完全無關聯），第三層 fallback
    讀取原始碼中的 HOOK_NAME 常數值。

    Args:
        hook_filename: hook 檔案名稱（如 'cli-dependency-check.py'）
        project_root: 專案根目錄

    Returns:
        (log_dir_name, full_path, dir_exists)
    """
    stem = Path(hook_filename).stem
    base_dir = project_root / ".claude" / "hook-logs"

    primary = base_dir / stem
    if primary.is_dir():
        return stem, primary, True

    if stem.endswith("-hook"):
        fallback_name = stem[: -len("-hook")]
        fallback = base_dir / fallback_name
        if fallback.is_dir():
            return fallback_name, fallback, True

    hook_name_const = _resolve_hook_name_from_source(hook_filename, project_root)
    if hook_name_const:
        source_fallback = base_dir / hook_name_const
        if source_fallback.is_dir():
            return hook_name_const, source_fallback, True

    return stem, primary, False


def _newest_file_mtime(log_dir: Path) -> float:
    """回傳 log_dir 第一層檔案（不遞迴子目錄）的最新 mtime

    log_dir 本身的 mtime 只在目錄項增減（新增/刪除檔案）時變動；對單一
    持久檔案採逐次 append 寫入（open mode "a"）的 hook（如 diagnostic.log），
    目錄項數量從未變化，導致目錄 mtime 停在建檔當下，即使檔案內容持續
    更新也會被誤判為 staleness。改掃描目錄內檔案的最新 mtime 才能反映
    真實的最後寫入時間。

    範圍刻意限制第一層、不遞迴（P0 回歸修復）：初版用 Path.rglob("*") 遞迴
    掃描，對 .claude/hook-logs 這種累積數十萬檔案的目錄（實測 666,853 個）
    造成 monitor 執行超過 60 秒，而它是 SessionStart hook，每次 session
    啟動都會卡住。log dir 命名慣例本身即保證同一 hook 的日誌只會出現在
    對應的第一層目錄，不會有子目錄結構需要遞迴；改用 os.scandir()
    （比 Path.iterdir() 少一層 stat 呼叫）取得檔案 entry 直接讀 stat 結果，
    避免二次 syscall。

    語意假設（供後續 hook_logging 寫入策略變更票參考）：本函式假設
    log_dir 內為「一次觸發一檔、檔名含時間戳」的寫入模式（如
    hook-name-20260821-193000.log），故「目錄內最新檔案 mtime」等價於
    「最近一次觸發時間」。若日誌寫入方式改為每日輪替（一天一檔）或單檔
    持續 append（同一檔案整天被覆寫更新），則此函式回傳的「最新檔案
    mtime」語意會從「最近一次觸發」退化為「當日最後一次寫入」，跨日邊界
    時判斷可能有最多一天的誤差（例如今日僅在 00:05 觸發過一次，之後 23
    小時無新觸發，仍會因檔案在 00:05 才建立而非「今日最後寫入」被視為
    當日活躍）。若同儕分析評估中的每日輪替/單檔 append 方案落地為
    hook_logging 的實作變更，該落地票須同步檢視本函式與
    WARNING_THRESHOLD_HOURS/CRITICAL_THRESHOLD_HOURS 判準是否仍成立。

    Args:
        log_dir: 日誌目錄路徑

    Returns:
        目錄內最新檔案的 mtime（epoch seconds）；目錄為空或無檔案時
        fallback 回傳 log_dir 本身的 mtime。
    """
    newest = None
    try:
        with os.scandir(log_dir) as it:
            for entry in it:
                try:
                    if not entry.is_file():
                        continue
                    mtime = entry.stat().st_mtime
                except OSError:
                    continue
                if newest is None or mtime > newest:
                    newest = mtime
    except OSError:
        pass

    if newest is not None:
        return newest

    return log_dir.stat().st_mtime


def _check_single_hook_log(
    hook_filename: str, project_root: Path
) -> Tuple[int, str, str]:
    """檢查單個 hook 的日誌狀態

    Args:
        hook_filename: hook 檔案名稱
        project_root: 專案根目錄

    Returns:
        (severity, message, hook_filename)
    """
    candidate, log_dir, found = resolve_hook_log_dir(hook_filename, project_root)

    if not found:
        msg = "[WARN] {} log dir not found".format(hook_filename)
        return 2, msg, hook_filename

    try:
        newest_mtime = _newest_file_mtime(log_dir)
        last_modified = datetime.fromtimestamp(newest_mtime)
        hours_ago = (datetime.now() - last_modified).total_seconds() / 3600

        if hours_ago < WARNING_THRESHOLD_HOURS:
            severity, msg = 0, "[OK] {} (last update: {}h ago)".format(
                hook_filename, int(hours_ago)
            )
        elif hours_ago < CRITICAL_THRESHOLD_HOURS:
            severity, msg = 1, "[WARN] {} (last update: {}h ago)".format(
                hook_filename, int(hours_ago)
            )
        else:
            severity, msg = 2, "[FAIL] {} (last update: {}h ago)".format(
                hook_filename, int(hours_ago)
            )

        return severity, msg, hook_filename

    except OSError as e:
        msg = "[FAIL] {} error: {}".format(hook_filename, str(e))
        return 2, msg, hook_filename


def check_hook_logs(
    project_root: Path,
    logger: logging.Logger,
    hook_filenames: List[str]
) -> Tuple[int, List[Tuple[int, str, str]]]:
    """檢查所有 SessionStart Hook 的日誌是否正常更新

    Args:
        project_root: 專案根目錄
        logger: 日誌物件，記錄每個 hook 的檢查結果到日誌檔
        hook_filenames: hook 檔案名稱清單

    Returns:
        (max_severity, check_results_list)
        max_severity: 0=正常, 1=警告, 2=嚴重警告
    """
    results = []
    max_severity = 0

    for hook_filename in hook_filenames:
        severity, msg, _ = _check_single_hook_log(hook_filename, project_root)
        results.append((severity, msg, hook_filename))
        max_severity = max(max_severity, severity)
        # 持久化每個 hook 的檢查結果到日誌檔
        if severity == 0:
            logger.debug(msg)
        elif severity == 1:
            logger.warning(msg)
        else:
            logger.error(msg)

    return max_severity, results


def _output_health_report(
    hook_filenames: List[str], log_results: List[Tuple[int, str, str]]
) -> None:
    """輸出健康檢查報告（純輸出，無回傳值）

    Args:
        hook_filenames: hook 檔案名稱清單
        log_results: 檢查結果清單
    """
    hook_output("=" * 70, "info")
    hook_output("Hook system health check", "info")
    hook_output("=" * 70, "info")
    hook_output("Checking {} SessionStart hooks".format(len(hook_filenames)), "info")

    for _, msg, _ in log_results:
        hook_output(msg, "info")

    hook_output("=" * 70, "info")


def write_session_marker(project_root: Path, now: Optional[datetime] = None) -> Path:
    """W13-017: SessionStart 時寫入 last-session-start.marker (ISO timestamp)

    供後續 hook-health 掃描判定「本 session 觸發」邊界，取代 timestamp gap heuristic
    (W13-008 §Session 邊界)。

    Args:
        project_root: 專案根目錄
        now: 注入點供測試覆蓋；預設為 datetime.now()

    Returns:
        marker 檔案路徑（已寫入）
    """
    marker_path = project_root.joinpath(*SESSION_MARKER_RELPATH)
    marker_path.parent.mkdir(parents=True, exist_ok=True)
    ts = (now or datetime.now()).isoformat(timespec="seconds")
    marker_path.write_text(ts, encoding="utf-8")
    return marker_path


def _load_settings(settings_path: Path) -> Dict:
    """讀取 settings.json；錯誤時回 {} (W13-017 內部工具)"""
    if not settings_path.exists():
        return {}
    try:
        with open(settings_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}


def _today_str(now: Optional[datetime] = None) -> str:
    return (now or datetime.now()).strftime("%Y-%m-%d")


def _compute_baseline(per_day: Dict[str, int], window_days: int = FREQUENCY_SCAN_WINDOW_DAYS) -> float:
    """W13-008 量化標準：baseline = sum(last_7_days) / 7

    使用 scan_logs 取得的 per_day 字典；不足 7 天時除以實際天數可能膨脹基線，
    故除以固定 window_days 以保持保守 (under-trigger 優於 over-trigger)。
    """
    total = sum(per_day.values())
    return total / float(window_days) if window_days > 0 else 0.0


def run_frequency_scan(
    project_root: Path,
    logger: logging.Logger,
    now: Optional[datetime] = None,
    logs_root: Optional[Path] = None,
) -> List[Tuple[str, "hook_health.Verdict"]]:
    """W13-017: 掃描全部 hooks 的觸發頻率並產出 stderr 摘要

    Scope 從原 SessionStart hooks 擴大為「全部出現在 hook-logs/ 的 hooks」
    (W13-008 IMP-2 acceptance)。

    步驟：
      1. scan_logs(since=7d) → 每 hook 的 total/per_day
      2. recent = today 的 per_day 計數
      3. baseline = sum(per_day) / 7
      4. classify_hook → high_freq_ok / low_freq_expected
      5. evaluate → Verdict(normal | warning | critical)
      6. critical / warning 輸出 stderr 摘要（不阻擋，不建 ticket）

    Args:
        project_root: 專案根目錄
        logger: 日誌物件
        now: 注入點供測試覆蓋
        logs_root: 注入點供測試覆蓋

    Returns:
        [(hook_name, Verdict)] 全部命中 warning/critical 的 hook，供呼叫端
        二次使用或測試斷言。
    """
    now = now or datetime.now()
    since = now - timedelta(days=FREQUENCY_SCAN_WINDOW_DAYS)
    settings = _load_settings(project_root / ".claude" / "settings.json")

    stats_by_hook = hook_health.scan_logs(since=since, logs_root=logs_root, logger=logger)
    today = _today_str(now)

    flagged: List[Tuple[str, hook_health.Verdict]] = []

    for hook_name, stats in sorted(stats_by_hook.items()):
        per_day = stats.get("per_day", {})
        recent = per_day.get(today, 0)
        baseline = _compute_baseline(per_day)
        hook_type = hook_health.classify_hook(hook_name, settings)

        verdict = hook_health.evaluate(
            stats={"total": stats.get("total", 0), "recent": recent, "per_day": per_day},
            hook_type=hook_type,
            baseline=baseline,
        )

        if verdict.status == "normal":
            continue

        flagged.append((hook_name, verdict))

        # W13-008 Solution §自動建 Ticket 流程：純 stderr 提醒，不自動建 ticket
        threshold = baseline * verdict.multiplier if not verdict.bootstrap else None
        if verdict.bootstrap:
            stderr_msg = (
                "[hook-health] {lvl}: {h} 今日觸發 {r} 次 (bootstrap, 無 7 天 baseline)"
            ).format(lvl=verdict.status.upper(), h=hook_name, r=recent)
        else:
            stderr_msg = (
                "[hook-health] {lvl}: {h} 今日觸發 {r} 次 > 基線 {b:.1f} × {n}"
            ).format(
                lvl=verdict.status.upper(),
                h=hook_name,
                r=recent,
                b=baseline,
                n=verdict.multiplier,
            )
        print(stderr_msg, file=sys.stderr)
        if verdict.reasons:
            print("  reasons: " + "; ".join(verdict.reasons), file=sys.stderr)
        logger.warning(stderr_msg)

    if flagged:
        print(
            "建議：手動建 ANA 排查（ticket track create --type ANA --who basil-hook-architect ...）",
            file=sys.stderr,
        )

    return flagged


def main() -> int:
    """主函式"""
    logger = setup_hook_logging("hook-health-monitor")

    # get_project_root() 回傳 str（git_utils），但本檔全函式以 Path 標註並使用
    # `/` 與 .joinpath()，故統一包成 Path，避免 write_session_marker 等處對 str
    # 呼叫 Path 方法拋 AttributeError（0.37.0-W6-003）。
    project_root = Path(get_project_root())
    if not project_root:
        hook_output("Error: Cannot find project root", "error")
        return 1

    # W13-017 (1): SessionStart marker — 給後續掃描判定 session 邊界
    try:
        write_session_marker(project_root)
    except OSError as e:
        # marker 寫入失敗不應阻擋既有健康檢查；輸出 stderr + log warning
        logger.warning("Failed to write session marker: {}".format(e))
        print("[hook-health] WARN: failed to write session marker: {}".format(e), file=sys.stderr)

    # W13-017 (2): 觸發頻率掃描（全部 hooks）— 純 stderr 提醒，不阻擋既有邏輯
    try:
        run_frequency_scan(project_root, logger)
    except Exception as e:  # noqa: BLE001 — 監測本身禁止讓既有健康檢查降級
        logger.warning("Frequency scan failed: {}".format(e))
        print("[hook-health] WARN: frequency scan failed: {}".format(e), file=sys.stderr)

    settings_path = project_root / ".claude" / "settings.json"
    hook_filenames = load_sessionstart_hooks_from_settings(settings_path)

    # 排除自身：monitor 的 setup_hook_logging 會立即更新 mtime，
    # 導致永遠自報健康，無法偵測自身故障
    own_filename = Path(__file__).name
    hook_filenames = [f for f in hook_filenames if f != own_filename]

    if not hook_filenames:
        hook_output(
            "Warning: No SessionStart hooks found in settings.json",
            "warning"
        )
        logger.warning("No SessionStart hooks found")

    log_severity, log_results = check_hook_logs(
        project_root, logger, hook_filenames
    )

    _output_health_report(hook_filenames, log_results)
    failure_hooks = [f for s, _, f in log_results if s == 2]

    # 失敗 hook 資訊輸出到 stderr
    if failure_hooks:
        stderr_msg = "Hook health check: {} hook(s) have critical issues: {}".format(
            len(failure_hooks), ", ".join(failure_hooks)
        )
        print(stderr_msg, file=sys.stderr)
        logger.warning(stderr_msg)

    # 決定最終狀態
    if log_severity == 0:
        hook_output("\nHook system is healthy", "info")
        logger.info("Hook health check passed")
    else:
        hook_output(
            "\nHook system has warnings. Please check .claude/hook-logs/",
            "warning"
        )
        logger.info("Hook health check: completed with warnings")

    return 0


if __name__ == "__main__":
    sys.exit(run_hook_safely(main, "hook-health-monitor"))
