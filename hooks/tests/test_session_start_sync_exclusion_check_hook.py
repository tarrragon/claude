"""
session-start-sync-exclusion-check-hook 交叉驗證測試套件

驗證 gitignore↔manifest 交叉驗證（0.19.1-W1-031，W1-024 方案 C / 多視角 M2）：

- gitignore 解析正規化（strip .claude/ 前綴、strip 尾 /、忽略註解空行）
- 三形式涵蓋判定（glob、目錄、檔名）避免 false positive
- 漂移偵測列缺項
- import manifest GITIGNORE_EXPECTED（不重寫分類）

Ticket：0.19.1-W1-031
"""

import importlib.util
from pathlib import Path


HOOK_PATH = (
    Path(__file__).parent.parent / "session-start-sync-exclusion-check-hook.py"
)


def load_hook_module():
    spec = importlib.util.spec_from_file_location(
        "session_start_sync_exclusion_check_hook", HOOK_PATH
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _make_gitignore(tmp_path: Path, content: str) -> Path:
    gi = tmp_path / ".gitignore"
    gi.write_text(content, encoding="utf-8")
    return gi


# ---------------------------------------------------------------------------
# 1. import manifest GITIGNORE_EXPECTED（不重寫分類）
# ---------------------------------------------------------------------------
def test_hook_imports_gitignore_expected_from_manifest():
    hook = load_hook_module()
    from lib.sync_exclude_manifest import GITIGNORE_EXPECTED  # noqa
    assert hook.GITIGNORE_EXPECTED is GITIGNORE_EXPECTED


# ---------------------------------------------------------------------------
# 2. 正規化：strip .claude/ 前綴、strip 尾 /、忽略註解空行
# ---------------------------------------------------------------------------
def test_parse_gitignore_normalization():
    content = (
        "# 註解行應忽略\n"
        "\n"
        "   \n"
        ".claude/hook-state/\n"      # 前綴 + 尾 /
        ".claude/pm-status.json\n"   # 前綴
        "handoff\n"                  # 裸名
        "**/.pytest_cache/\n"        # glob + 尾 /
    )
    parsed = load_hook_module().parse_gitignore_entries(content)
    assert "hook-state" in parsed
    assert "pm-status.json" in parsed
    assert "handoff" in parsed
    assert ".pytest_cache" in parsed
    # 註解與空行不得進入結果
    assert "# 註解行應忽略" not in parsed
    assert "" not in parsed


# ---------------------------------------------------------------------------
# 3. 三形式涵蓋判定避免 false positive
# ---------------------------------------------------------------------------
def test_drift_covered_by_three_forms(tmp_path):
    hook = load_hook_module()
    lines = []
    for name in sorted(hook.GITIGNORE_EXPECTED):
        # 交替使用 glob / 目錄 / 檔名三形式表達涵蓋
        idx = sorted(hook.GITIGNORE_EXPECTED).index(name)
        if idx % 3 == 0:
            lines.append(f".claude/{name}/")     # 目錄形式
        elif idx % 3 == 1:
            lines.append(f"**/{name}")           # glob 形式
        else:
            lines.append(name)                   # 裸檔名形式
    gi = _make_gitignore(tmp_path, "\n".join(lines) + "\n")
    drift = hook.find_gitignore_drift(gi)
    assert drift == [], f"不應有 false positive，但偵測到缺項：{drift}"


# ---------------------------------------------------------------------------
# 4. 漂移偵測列缺項
# ---------------------------------------------------------------------------
def test_drift_lists_missing(tmp_path):
    hook = load_hook_module()
    missing_item = ".zhtw-mcp-skip"
    assert missing_item in hook.GITIGNORE_EXPECTED
    entries = [
        f".claude/{n}" for n in sorted(hook.GITIGNORE_EXPECTED) if n != missing_item
    ]
    gi = _make_gitignore(tmp_path, "\n".join(entries) + "\n")
    drift = hook.find_gitignore_drift(gi)
    assert missing_item in drift


# ---------------------------------------------------------------------------
# 5. .gitignore 不存在 → 回傳全部缺項（不拋例外）
# ---------------------------------------------------------------------------
def test_missing_gitignore_returns_all(tmp_path):
    hook = load_hook_module()
    drift = hook.find_gitignore_drift(tmp_path / ".gitignore")
    assert set(drift) == set(hook.GITIGNORE_EXPECTED)


# ---------------------------------------------------------------------------
# 6. 漂移警告區塊含缺項名稱
# ---------------------------------------------------------------------------
def test_build_drift_warning_lists_items():
    hook = load_hook_module()
    section = hook.build_gitignore_drift_section([".zhtw-mcp-skip", "hook-state"])
    assert ".zhtw-mcp-skip" in section
    assert "hook-state" in section
    assert "WARNING" in section
