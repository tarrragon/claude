#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
.claude 同步狀態檢查工具

比對本地與遠端的版本號和內容指紋，快速判斷是否需要推送或拉取。

依賴：Python 3.8+, git
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# 排除分類與 should_exclude / compute_content_hash 由 SSOT manifest 統一提供
# （ARCH-020：消除 push/status 重複定義漂移；修缺陷 N——status 舊版 EXCLUDE_PATTERNS
# 漏列 dispatch-active.json/hook-state/settings.local.json/.zhtw-mcp-skip 導致與 push
# 指紋不一致）。manifest 位於 .claude/lib/。
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from lib.sync_exclude_manifest import should_exclude, compute_content_hash  # noqa: E402, F401

REPO_URL = "https://github.com/tarrragon/claude.git"

SYNC_STATE_FILENAME = ".sync-state.json"

# 單一 base snapshot 欄位（多視角 H1：禁雙欄位 push/pull + 禁對 SHA 用 max()）。
# commit SHA 為字典序字串，max(SHA) 會選錯共同祖先；push/pull 成功皆覆寫此同一欄位。
BASE_SHA_FIELD = "last_synced_base_sha"
NO_RECORD = "（無記錄）"


def resolve_base_sha_display(sync_state: dict) -> str:
    """從 sync_state 取單一 base SHA 供顯示，缺欄位回退「無記錄」。

    僅認 BASE_SHA_FIELD 單一鍵，不接受 push/pull 雙欄位 schema（H1 防護）。
    """
    return sync_state.get(BASE_SHA_FIELD) or NO_RECORD


def print_color(msg: str, color: str = "yellow") -> None:
    """輸出彩色訊息。"""
    colors = {"green": "\033[0;32m", "yellow": "\033[1;33m", "red": "\033[0;31m"}
    nc = "\033[0m"
    if sys.platform == "win32" and not os.environ.get("TERM"):
        print(msg)
    else:
        print(f"{colors.get(color, '')}{msg}{nc}")


def find_project_root() -> Path:
    """向上尋找包含 .claude/ 的專案根目錄。"""
    current = Path.cwd()
    while current != current.parent:
        if (current / ".claude").is_dir():
            return current
        current = current.parent
    print_color("找不到 .claude 目錄，請在專案根目錄執行此腳本", "red")
    sys.exit(1)


def extract_version_string(content: str) -> str:
    """從 VERSION 檔案內容中提取版本號，跳過空行和註解，移除 v 前綴。"""
    for line in content.split("\n"):
        line = line.strip()
        if line and not line.startswith("#"):
            return line.lstrip("v")
    return ""


def parse_version(version_str: str) -> list[int]:
    """將版本字串解析為整數清單 [major, minor, patch]。"""
    parts = version_str.split(".")
    result: list[int] = []
    for part in parts[:3]:
        try:
            result.append(int(part))
        except ValueError:
            result.append(0)
    while len(result) < 3:
        result.append(0)
    return result


def get_remote_version() -> str:
    """透過 shallow clone 取得遠端 VERSION 檔案內容。"""
    temp_dir = Path(tempfile.mkdtemp())
    try:
        result = subprocess.run(
            ["git", "clone", "--depth", "1", REPO_URL, str(temp_dir)],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode != 0:
            return ""
        version_file = temp_dir / "VERSION"
        if version_file.exists():
            return extract_version_string(version_file.read_text(encoding="utf-8"))
        return ""
    except (subprocess.TimeoutExpired, OSError):
        return ""
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def load_sync_state(claude_dir: Path) -> dict:
    """讀取 .sync-state.json，不存在時回傳空字典。"""
    state_file = claude_dir / SYNC_STATE_FILENAME
    if state_file.exists():
        try:
            return json.loads(state_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def main() -> None:
    project_root = find_project_root()
    claude_dir = project_root / ".claude"

    # 本地版本
    version_file = claude_dir / "VERSION"
    local_version = ""
    if version_file.exists():
        local_version = extract_version_string(version_file.read_text(encoding="utf-8"))

    # 遠端版本
    print_color("取得遠端版本...", "yellow")
    remote_version = get_remote_version()

    # 版本比對
    if local_version and remote_version:
        local_parts = parse_version(local_version)
        remote_parts = parse_version(remote_version)
        if local_parts == remote_parts:
            version_status = "同步"
            version_color = "green"
        elif local_parts < remote_parts:
            version_status = "本地落後"
            version_color = "yellow"
        else:
            version_status = "本地領先"
            version_color = "green"
    elif not remote_version:
        version_status = "無法取得遠端版本"
        version_color = "yellow"
    else:
        version_status = "本地無版本檔案"
        version_color = "yellow"

    # 內容指紋
    current_hash = compute_content_hash(claude_dir)
    sync_state = load_sync_state(claude_dir)
    last_push_hash = sync_state.get("last_push_hash", NO_RECORD)
    base_sha = resolve_base_sha_display(sync_state)

    if last_push_hash == NO_RECORD:
        content_status = "無推送記錄"
        content_color = "yellow"
    elif current_hash == last_push_hash:
        content_status = "無變更"
        content_color = "green"
    else:
        content_status = "有變更"
        content_color = "yellow"

    # 輸出
    print()
    print_color(".claude 同步狀態", "green")
    print_color("================", "green")
    print_color(f"本地版本:  {local_version or '（無）'}", "green")
    print_color(f"遠端版本:  {remote_version or '（無法取得）'}", "green")
    print_color(f"版本狀態:  {version_status}", version_color)
    print()
    print_color(f"內容指紋:  {current_hash}", "green")
    print_color(f"上次推送:  {last_push_hash}", "green")
    print_color(f"內容狀態:  {content_status}", content_color)
    print()
    print_color(f"同步 base SHA: {base_sha}", "green")


if __name__ == "__main__":
    main()
