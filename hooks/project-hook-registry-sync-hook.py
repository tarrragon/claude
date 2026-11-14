#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml"]
# ///
"""
專案自有 hook 清冊同步（SessionStart）

依 `.claude/project-integration/hook-registry.yaml` 重建
`.claude/settings.local.json` 的 `hooks` 區段。格式見
`.claude/references/project-hook-registry-format.md`。

清冊外的 local hook 條目只移除可判定為錯誤的兩類，其餘保留並示警：
  1. 幽靈：command 指向的 `.claude/` 下檔案不存在
  2. 框架重複：同一腳本已由 settings.json 或 hook-dispatch-registry 註冊

輸出：有移除、示警或錯誤時，stderr 與 additionalContext（pm_only）都列出。
失敗語意：清冊格式錯誤或寫檔失敗時不寫入 settings.local.json，回報錯誤；
SessionStart 不阻擋。
"""

import hashlib
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lib.hook_base import get_code_root  # noqa: E402
from lib.hook_logging import setup_hook_logging, run_hook_safely, get_hook_log_dir  # noqa: E402
from lib.hook_io import read_json_from_stdin, emit_hook_output  # noqa: E402
from lib.hook_registry import merge_dispatch_registry  # noqa: E402
from lib.project_hook_registry import (  # noqa: E402,F401  build_command 供測試沿用
    MANIFEST_RELATIVE,
    ManifestError,
    build_command,
    parse_manifest,
)

HOOK_NAME = "project-hook-registry-sync"
LOCAL_SETTINGS_RELATIVE = Path(".claude") / "settings.local.json"
# 從 command 取出 `.claude/` 之後的腳本相對路徑（容許引號、${} 寫法與直譯器前綴）
_SCRIPT_PATH_RE = re.compile(r"\.claude/([^\s'\"]+)")


def script_identity(command: str) -> str:
    """command 指向的 `.claude/` 腳本相對路徑；非 `.claude/` 腳本回傳空字串。"""
    match = _SCRIPT_PATH_RE.search(command)
    return match.group(1) if match else ""


def framework_script_identities(settings: dict, root: Path, logger) -> set:
    """settings.json 與 dispatch registry 已註冊的腳本集合（併入只作判斷）。"""
    merged = merge_dispatch_registry(json.loads(json.dumps(settings)), root, logger)
    identities = set()
    for entry in iter_hook_entries(merged):
        identity = script_identity(entry[2].get("command", ""))
        if identity:
            identities.add(identity)
    return identities


def iter_hook_entries(settings: dict):
    """逐一 yield (event, matcher, hook_entry)。"""
    for event, groups in (settings.get("hooks") or {}).items():
        if not isinstance(groups, list):
            continue
        for group in groups:
            if not isinstance(group, dict):
                continue
            for hook in group.get("hooks", []):
                if isinstance(hook, dict):
                    yield event, group.get("matcher", ""), hook


def classify_local_entry(command: str, root: Path, framework_ids: set, previously_generated: set = frozenset()) -> str:
    """清冊外條目的分類：manifest_removed / ghost / framework_duplicate / keep。

    manifest_removed：上次由本 hook 依清冊產生、清冊已不再列出的條目。它是框架
    產生的，不是用戶手寫的設定，移除屬可判定的同步，不屬刪除用戶設定。
    """
    if command in previously_generated:
        return "manifest_removed"
    identity = script_identity(command)
    if identity and identity in framework_ids:
        return "framework_duplicate"
    if identity and not (root / ".claude" / identity).exists():
        return "ghost"
    return "keep"


def rebuild_hooks(manifest_entries: list, local_settings: dict, root: Path, framework_ids: set,
                  previously_generated: set = frozenset()):
    """回傳 (新 hooks 區段, removed, kept_unlisted)。removed 為 [(類別, command)]。"""
    manifest_commands = {cmd for _e, _m, cmd, _t in manifest_entries}
    removed, kept_unlisted, survivors = [], [], []
    for event, matcher, hook in iter_hook_entries(local_settings):
        command = hook.get("command", "")
        if command in manifest_commands:
            continue  # 由清冊重新產生
        kind = classify_local_entry(command, root, framework_ids, previously_generated)
        if kind == "keep":
            kept_unlisted.append(command)
            survivors.append((event, matcher, hook))
        else:
            removed.append((kind, command))
    hooks: dict = {}
    for event, matcher, command, timeout in manifest_entries:
        item = {"type": "command", "command": command}
        if timeout:
            item["timeout"] = timeout
        _append(hooks, event, matcher, item)
    for event, matcher, hook in survivors:
        _append(hooks, event, matcher, hook)
    return hooks, removed, kept_unlisted


def _append(hooks: dict, event: str, matcher: str, item: dict) -> None:
    groups = hooks.setdefault(event, [])
    for group in groups:
        if group.get("matcher", "") == matcher:
            group["hooks"].append(item)
            return
    group = {"hooks": [item]}
    if matcher:
        group["matcher"] = matcher
    groups.append(group)


def format_report(removed: list, kept_unlisted: list, error: str = "") -> str:
    """組出給 PM 與 stderr 的報告；無事可報回傳空字串。"""
    labels = {
        "ghost": "指向不存在的檔案",
        "framework_duplicate": "重複註冊框架 hook",
        "manifest_removed": "已從清冊刪除",
    }
    lines = []
    if error:
        lines.append("[{}] 清冊無法使用，未改動 settings.local.json：{}".format(HOOK_NAME, error))
    if removed:
        lines.append("[{}] 已從 settings.local.json 移除 {} 筆 hook 註冊：".format(HOOK_NAME, len(removed)))
        lines.extend("  - [{}] {}".format(labels[kind], cmd) for kind, cmd in removed)
    if kept_unlisted:
        lines.append(
            "[{}] settings.local.json 有 {} 筆 hook 不在專案清冊 {}，已保留；"
            "請加入清冊，否則換機器或新 clone 後不會存在：".format(HOOK_NAME, len(kept_unlisted), MANIFEST_RELATIVE)
        )
        lines.extend("  - {}".format(cmd) for cmd in kept_unlisted)
    return "\n".join(lines)


def load_json(path: Path) -> dict:
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _root_digest(root: Path) -> str:
    """code root resolve 後絕對路徑的 sha256 前 16 碼，作為配對狀態檔名的區分鍵。"""
    return hashlib.sha256(str(root.resolve()).encode("utf-8")).hexdigest()[:16]


def state_path(root: Path) -> Path:
    """上次產生的 command 清單；放 hook 日誌目錄（LR，本機狀態，不進 git）。

    它描述的是 root 下的 settings.local.json，而日誌目錄由所有 checkout 共用，
    檔名因此依 root 區分，避免不同 code root 交替執行時互相覆蓋。
    """
    return get_hook_log_dir(HOOK_NAME) / "generated-{}.json".format(_root_digest(root))


def load_previously_generated(root: Path, logger) -> set:
    try:
        return set(load_json(state_path(root)).get("commands", []))
    except (OSError, ValueError) as e:
        # 狀態檔損壞只影響「已從清冊刪除」的判定（退化為保留並示警），不中止同步
        logger.warning("讀取產生紀錄失敗，本次不移除已從清冊刪除的條目：{}".format(e))
        return set()


def save_generated(root: Path, commands: list, logger) -> None:
    path = state_path(root)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"commands": sorted(commands)}, ensure_ascii=False) + "\n", encoding="utf-8")
    except OSError as e:
        logger.warning("寫入產生紀錄失敗（下次無法辨識已從清冊刪除的條目）：{}".format(e))


def sync(root: Path, logger):
    """執行同步，回傳報告字串（無事可報為空字串）。"""
    manifest_path = root / MANIFEST_RELATIVE
    local_path = root / LOCAL_SETTINGS_RELATIVE
    try:
        local_settings = load_json(local_path)
        settings = load_json(root / ".claude" / "settings.json")
    except (OSError, ValueError) as e:
        return format_report([], [], "讀取設定檔失敗：{}".format(e))

    manifest_entries = []
    if manifest_path.is_file():
        try:
            manifest_entries = parse_manifest(manifest_path.read_text(encoding="utf-8"))
        except (OSError, ManifestError) as e:
            return format_report([], [], str(e))
    if not manifest_entries and not local_settings.get("hooks"):
        return ""

    framework_ids = framework_script_identities(settings, root, logger)
    previously_generated = load_previously_generated(root, logger)
    hooks, removed, kept_unlisted = rebuild_hooks(
        manifest_entries, local_settings, root, framework_ids, previously_generated
    )
    if hooks != (local_settings.get("hooks") or {}):
        new_settings = dict(local_settings)
        if hooks:
            new_settings["hooks"] = hooks
        else:
            new_settings.pop("hooks", None)
        try:
            local_path.write_text(json.dumps(new_settings, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        except OSError as e:
            return format_report([], [], "寫入 settings.local.json 失敗：{}".format(e))
        logger.info("settings.local.json hooks 區段已依清冊重建（{} 筆清冊條目）".format(len(manifest_entries)))
    save_generated(root, [cmd for _e, _m, cmd, _t in manifest_entries], logger)
    return format_report(removed, kept_unlisted)


def main() -> int:
    logger = setup_hook_logging(HOOK_NAME)
    input_data = read_json_from_stdin(logger)
    report = sync(get_code_root(), logger)  # CR：清冊、settings.json 讀取與 settings.local.json 寫入
    if report:
        logger.warning(report)
        sys.stderr.write(report + "\n")
        emit_hook_output("SessionStart", additional_context=report, audience="pm_only", input_data=input_data)
    return 0


if __name__ == "__main__":
    sys.exit(run_hook_safely(main, HOOK_NAME))
