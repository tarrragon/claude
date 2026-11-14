"""共用模組：專案自有 hook 清冊（.claude/project-integration/hook-registry.yaml）的讀取點。

格式見 `.claude/references/project-hook-registry-format.md`。產生器
（project-hook-registry-sync-hook）、註冊涵蓋率檢查與 sync-pull 的 local 檢查
都經本模組取得「清冊產生的 command」，確保三處對同一條目的判定一致。

yaml 在函式內延遲匯入：呼叫端（如 sync-claude-pull 以 python3 直接執行時）可能
沒有 pyyaml，此時 `manifest_commands` 回傳 None，由呼叫端決定如何呈現「無法判定」。
"""

from pathlib import Path
from typing import List, Optional, Set, Tuple

from lib.hook_registry import COMMAND_TEMPLATE

MANIFEST_RELATIVE = Path(".claude") / "project-integration" / "hook-registry.yaml"
SUPPORTED_VERSION = 1
PROJECT_DIR_VAR = "$CLAUDE_PROJECT_DIR"


class ManifestError(Exception):
    """清冊無法使用（格式錯誤、版本不支援、欄位缺漏）。"""


def build_command(script: str) -> str:
    """依格式文件〈command 字串的正規化形式〉組出 command。"""
    if script.startswith("./"):
        script = script[2:]
    if script.endswith(".py"):
        # 與 sync 自動註冊、dispatch registry 併入同一模板，字串相同 Claude Code 才會去重
        return COMMAND_TEMPLATE.format(path=script)
    return "{}/{}".format(PROJECT_DIR_VAR, script)


def parse_manifest(text: str) -> List[Tuple[str, str, str, Optional[int]]]:
    """解析清冊，回傳 [(event, matcher, command, timeout)]；不合格式即拋 ManifestError。"""
    import yaml

    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as e:
        raise ManifestError("YAML 解析失敗：{}".format(e))
    if not isinstance(data, dict):
        raise ManifestError("頂層須為對應表")
    if data.get("version") != SUPPORTED_VERSION:
        raise ManifestError("不支援的 version：{!r}（支援 {}）".format(data.get("version"), SUPPORTED_VERSION))
    hooks = data.get("hooks")
    if not isinstance(hooks, dict):
        raise ManifestError("缺 hooks 對應表")
    entries = []
    for key, meta in hooks.items():
        if not isinstance(meta, dict) or not meta.get("script") or not meta.get("event"):
            raise ManifestError("條目 {} 缺 script 或 event".format(key))
        timeout = meta.get("timeout")
        if timeout is not None and not isinstance(timeout, int):
            raise ManifestError("條目 {} 的 timeout 須為整數（秒）".format(key))
        entries.append((meta["event"], meta.get("matcher", "") or "", build_command(str(meta["script"])), timeout))
    return entries


def manifest_commands(root: Path) -> Optional[Set[str]]:
    """清冊產生的 command 集合。清冊不存在回傳空集合；無 pyyaml 或清冊無法使用回傳 None。"""
    path = Path(root) / MANIFEST_RELATIVE
    if not path.is_file():
        return set()
    try:
        return {cmd for _e, _m, cmd, _t in parse_manifest(path.read_text(encoding="utf-8"))}
    except (ImportError, OSError, ManifestError):
        # 無法判定時回傳 None，呼叫端照「清冊外」處理並註明無法判定，不可當成空清冊
        return None
