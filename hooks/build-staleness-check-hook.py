#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
Build Staleness Check - SessionStart Hook

偵測 build/development/ 是否相對 src/ 過期，並提示 `npm run build:dev`。

動機（W6-012.1）：build/development/ 停在 8 個月前但 src/ 持續更新，
Chrome Extension 載入舊 build 導致 bug 看似源自 src 實為 stale build，
浪費大量診斷時間。

行為：
- src 較新且差距超過 STALE_THRESHOLD_SECONDS：輸出 warning + 重建指令
- build/development/ 不存在：輸出 hint「尚未 build」
- build 較新或差距在閾值內：靜默
- 不阻擋（return 0）

Hook Event: SessionStart
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Optional, Tuple

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from lib import setup_hook_logging, run_hook_safely
except ImportError as e:
    print(f"[Hook Import Warning] build-staleness-check-hook: {e}", file=sys.stderr)

    def setup_hook_logging(name):  # type: ignore
        import logging
        return logging.getLogger(name)

    def run_hook_safely(func, name):  # type: ignore
        try:
            return func()
        except Exception as exc:  # noqa: BLE001
            print(f"[{name}] error: {exc}", file=sys.stderr)
            return 0


# 閾值：src 比 build 新超過此秒數才提示（防止剛 build 完誤判）
STALE_THRESHOLD_SECONDS = 3600  # 1 小時


def _get_project_root() -> Path:
    """取得專案根目錄，優先使用 CLAUDE_PROJECT_DIR 環境變數。"""
    env_root = os.environ.get("CLAUDE_PROJECT_DIR")
    if env_root:
        return Path(env_root)
    # fallback：.claude/hooks/ 的上兩層
    return Path(__file__).resolve().parent.parent.parent


def _latest_src_mtime(src_dir: Path) -> Optional[float]:
    """取得 src/**/* 中最新檔案 mtime；目錄不存在或無檔案回 None。"""
    if not src_dir.exists() or not src_dir.is_dir():
        return None
    latest: Optional[float] = None
    for path in src_dir.rglob("*"):
        try:
            if not path.is_file():
                continue
            mtime = path.stat().st_mtime
            if latest is None or mtime > latest:
                latest = mtime
        except OSError:
            continue
    return latest


def check_build_staleness(
    project_root: Path,
    threshold_seconds: int = STALE_THRESHOLD_SECONDS,
) -> Tuple[str, str]:
    """純函式：檢查 build 過期狀態。

    Returns:
        (status, message)
        status ∈ {"missing", "stale", "fresh", "no_src"}
        message：給用戶看的文字（status=fresh/no_src 時為空字串）
    """
    src_dir = project_root / "src"
    build_manifest = project_root / "build" / "development" / "manifest.json"

    src_mtime = _latest_src_mtime(src_dir)
    if src_mtime is None:
        return ("no_src", "")

    if not build_manifest.exists():
        msg = (
            "[build-staleness-check] 尚未建置 build/development/，"
            "請執行 `npm run build:dev` 後再載入 Chrome Extension。"
        )
        return ("missing", msg)

    try:
        build_mtime = build_manifest.stat().st_mtime
    except OSError:
        msg = (
            "[build-staleness-check] 無法讀取 build/development/manifest.json，"
            "建議執行 `npm run build:dev` 重建。"
        )
        return ("missing", msg)

    diff = src_mtime - build_mtime
    if diff > threshold_seconds:
        import datetime as _dt
        src_str = _dt.datetime.fromtimestamp(src_mtime).strftime("%Y-%m-%d %H:%M")
        build_str = _dt.datetime.fromtimestamp(build_mtime).strftime("%Y-%m-%d %H:%M")
        hours = diff / 3600
        msg = (
            f"[build-staleness-check] build/development/ 已過期："
            f"src 更新於 {src_str}，build 停於 {build_str}（落後約 {hours:.1f} 小時）。\n"
            f"請執行 `npm run build:dev` 重建後再載入 Chrome Extension。"
        )
        return ("stale", msg)

    return ("fresh", "")


def main() -> int:
    logger = setup_hook_logging("build-staleness-check")
    project_root = _get_project_root()

    status, message = check_build_staleness(project_root)
    logger.debug(f"status={status} root={project_root}")

    if status in ("stale", "missing") and message:
        # 不阻擋（return 0）；訊息走 stdout（SessionStart 屬 informational）
        print(message)

    return 0


if __name__ == "__main__":
    sys.exit(run_hook_safely(main, "build-staleness-check"))
