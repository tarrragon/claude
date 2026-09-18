"""Tests: 已知替代註冊管道不得被誤報為「未出現在 settings.json」.

0.1.0-W3-138 動機：`hook-registration-coverage-check.py`（原名
hook-completeness-check.py）量的是「檔名是否出現在 settings.json 的 hooks
config」，但曾把宣稱寫成「未註冊」這個更大的結論——即使該檔其實透過其他管道
（installer 生成的原生 git hook shim、被其他已註冊 hook 匯入的共用模組）被
執行。修法：把兩個已知案例登記進 hook-exclude-list.json 的 notes，並沿用既有
「排除清單」機制（非新增偵測邏輯），本測試釘住此行為不回歸。

覆蓋範圍（對應 acceptance「測試涵蓋」）：
1. hook-exclude-list.json 的 notes 對兩個已知案例有具體理由（非空字串）
2. 對真實 .claude/hooks/ 掃描，git-ref-transaction-content-guard.py 不落在
   「未出現在 settings.json」的集合中
3. 對真實 .claude/skills/ticket/hooks/ 掃描，handoff_session_mgmt.py 同上
4. 正常經 settings.json 註冊的 hook（以本檢查器自身為例）行為不變：
   仍出現在 registered_hooks，且不落在未出現集合中
"""

import json
import sys
from pathlib import Path

_HOOKS_DIR = Path(__file__).resolve().parent.parent
_PROJECT_ROOT = _HOOKS_DIR.parent.parent
_PROJECT_INIT = _PROJECT_ROOT / ".claude" / "skills" / "project-init"
if str(_PROJECT_INIT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_INIT))

from project_init.lib.hook_checker import (  # noqa: E402
    extract_registered_hooks,
    extract_registered_skill_hooks,
    get_exclude_patterns,
    load_json_file,
    scan_hooks_directory,
    scan_skill_hooks,
)

_EXCLUDE_LIST_PATH = _HOOKS_DIR / "hook-exclude-list.json"
_SETTINGS_PATH = _PROJECT_ROOT / ".claude" / "settings.json"
_SKILLS_DIR = _PROJECT_ROOT / ".claude" / "skills"

_INSTALLER_ROUTED_HOOK = "git-ref-transaction-content-guard.py"
_IMPORTED_HELPER_MODULE = "ticket/hooks/handoff_session_mgmt.py"
_KNOWN_REGISTERED_HOOK = "hook-registration-coverage-check.py"


def _load_exclude_list() -> dict:
    with open(_EXCLUDE_LIST_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


class TestExcludeListDocumentsAlternateRegistration:
    def test_installer_routed_guard_has_documented_reason(self):
        exclude_list = _load_exclude_list()
        assert "git-ref-transaction-content-guard.py" in exclude_list["exclude"]
        note = exclude_list["notes"].get("git-ref-transaction-content-guard.py", "")
        assert note, "installer 型註冊必須有非空理由，否則排除本身不可追溯"

    def test_imported_helper_module_has_documented_reason(self):
        exclude_list = _load_exclude_list()
        assert "handoff_session_mgmt.py" in exclude_list["exclude"]
        note = exclude_list["notes"].get("handoff_session_mgmt.py", "")
        assert note, "被匯入模組型排除必須有非空理由，否則排除本身不可追溯"


class TestRealScanNoLongerFlagsKnownAlternateChannels:
    """對真實專案檔案掃描（非合成 tmp_path），驗證兩個已知案例確實被排除."""

    def test_installer_routed_guard_not_in_unregistered_set(self):
        exclude_list = _load_exclude_list()
        exact_excludes, patterns = get_exclude_patterns(exclude_list)
        settings = load_json_file(_SETTINGS_PATH)

        all_hooks = scan_hooks_directory(_HOOKS_DIR, exact_excludes, patterns)
        registered_hooks = extract_registered_hooks(settings)
        unregistered = all_hooks - registered_hooks

        assert _INSTALLER_ROUTED_HOOK not in unregistered

    def test_imported_helper_module_not_in_unregistered_skill_set(self):
        exclude_list = _load_exclude_list()
        exact_excludes, patterns = get_exclude_patterns(exclude_list)
        settings = load_json_file(_SETTINGS_PATH)

        all_skill_hooks = scan_skill_hooks(_SKILLS_DIR, exact_excludes, patterns)
        registered_skill_hooks = extract_registered_skill_hooks(settings)
        unregistered_skill_hooks = all_skill_hooks - registered_skill_hooks

        assert _IMPORTED_HELPER_MODULE not in unregistered_skill_hooks

    def test_normal_registered_hook_behavior_unchanged(self):
        """回歸防護：排除機制不得連帶影響正常經 settings.json 註冊的 hook."""
        exclude_list = _load_exclude_list()
        exact_excludes, patterns = get_exclude_patterns(exclude_list)
        settings = load_json_file(_SETTINGS_PATH)

        all_hooks = scan_hooks_directory(_HOOKS_DIR, exact_excludes, patterns)
        registered_hooks = extract_registered_hooks(settings)
        unregistered = all_hooks - registered_hooks

        assert _KNOWN_REGISTERED_HOOK in all_hooks
        assert _KNOWN_REGISTERED_HOOK in registered_hooks
        assert _KNOWN_REGISTERED_HOOK not in unregistered
