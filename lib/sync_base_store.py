"""同步基準點與版本 pin 的入版控存放（.claude/sync-base.json）。

base（last_synced_base_sha）與 pin（pinned_version）描述「已提交的 .claude/ 內容
對應上游哪個版本」，必須跟著 commit 走：放在 gitignore 的 .sync-state.json 時，新
clone 與 linked worktree 讀不到 base，pull 退回全量 overlay，無法三方合併。

本模組是兩欄位唯一的讀寫入口，pull、push、status 共用：
- 讀取：新檔有值用新檔；新檔缺值時回退讀 .sync-state.json 的舊值（不寫檔，
  唯讀命令與中止的 pull 不留副作用）。
- 寫入：寫入任一欄位時，先把新檔缺、舊檔有的欄位一併搬過來，再從舊檔移除已搬
  的欄位。兩欄位一起搬，避免 base 進了新檔而 pin 還留在本機，新 clone 讀不到 pin。

.sync-state.json 其餘欄位（last_push_*、pending base、自動登記紀錄）屬本機狀態，
不經本模組。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

SYNC_BASE_FILENAME = "sync-base.json"
LEGACY_STATE_FILENAME = ".sync-state.json"

BASE_SHA_FIELD = "last_synced_base_sha"
PINNED_VERSION_FIELD = "pinned_version"
TRACKED_FIELDS = (BASE_SHA_FIELD, PINNED_VERSION_FIELD)
# pull 取得 base 當下本地 HEAD 的 commit SHA。push 以 merge-base --is-ancestor 判斷
# 刪除 commit 是否早於取得 base。新欄位無舊位置可遷移，故不列入 TRACKED_FIELDS。
BASE_ACQUIRED_HEAD_FIELD = "base_acquired_local_head"
WRITABLE_FIELDS = TRACKED_FIELDS + (BASE_ACQUIRED_HEAD_FIELD,)


def _read_json_dict(path: Path) -> dict:
    """讀 JSON 物件；無檔、解析失敗或非 dict 皆回空 dict。"""
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        # 損毀視同無值（與既有 read_base_sha 行為一致，退回全量 overlay 路徑）
        sys.stderr.write(f"[sync-base] 無法解析 {path.name}，視同無值: {exc}\n")
        return {}
    return data if isinstance(data, dict) else {}


def _write_json_dict(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _valid(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def read_sync_base_field(claude_dir: Path, field: str) -> str | None:
    """讀取 base 或 pin；新檔缺值時回退舊位置，不寫檔。"""
    value = _valid(_read_json_dict(claude_dir / SYNC_BASE_FILENAME).get(field))
    if value is not None:
        return value
    return _valid(_read_json_dict(claude_dir / LEGACY_STATE_FILENAME).get(field))


def migrate_legacy_fields(claude_dir: Path) -> list[str]:
    """把舊位置的 base、pin 搬到新檔，回傳搬過的欄位名。

    新檔已有值的欄位以新檔為準，舊檔殘值只移除不覆蓋。舊檔無這兩欄位時不動任何檔。
    """
    legacy_path = claude_dir / LEGACY_STATE_FILENAME
    legacy = _read_json_dict(legacy_path)
    present = [f for f in TRACKED_FIELDS if f in legacy]
    if not present:
        return []
    store_path = claude_dir / SYNC_BASE_FILENAME
    store = _read_json_dict(store_path)
    moved = []
    for field in present:
        value = _valid(legacy.pop(field))
        if value is not None and _valid(store.get(field)) is None:
            store[field] = value
            moved.append(field)
    if moved:
        _write_json_dict(store_path, store)
        sys.stderr.write(
            f"[sync-base] 已將 {', '.join(moved)} 從 {LEGACY_STATE_FILENAME} "
            f"遷移到 {SYNC_BASE_FILENAME}（此檔進版控，請一併 commit）\n"
        )
    _write_json_dict(legacy_path, legacy)
    return moved


def write_sync_base_field(claude_dir: Path, field: str, value: str) -> None:
    """寫入 base 或 pin；先遷移舊位置的兩欄位，再覆寫指定欄位。"""
    if field not in WRITABLE_FIELDS:
        raise ValueError(f"非 sync-base 欄位: {field}")
    migrate_legacy_fields(claude_dir)
    store_path = claude_dir / SYNC_BASE_FILENAME
    store = _read_json_dict(store_path)
    store[field] = value
    _write_json_dict(store_path, store)
