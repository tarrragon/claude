"""測試檔子集選擇：S2b（直接匯入／檔名提及）加上有界匯入遞移。

回歸樣本（3.4.0-W1-191）：改動模組經中介模組被測試函式內匯入（測試 → create → version，
鏈長 2），S2b 只收直接匯入故漏選。fixture 以最小結構重現這條三層鏈。
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import merge_gate as mg  # noqa: E402

PKG = ".claude/skills/demo/demo_sys"
TESTS = ".claude/skills/demo/tests"
VERSION = f"{PKG}/lib/version.py"
T_DIRECT = f"{TESTS}/test_version_direct.py"
T_CREATE = f"{TESTS}/test_create_visible.py"   # 鏈長 2：函式內匯入 create，create 匯入 version
T_CLI = f"{TESTS}/test_cli_entry.py"           # 鏈長 3：cli → create → version
T_UNRELATED = f"{TESTS}/test_unrelated.py"
T_SUB = f"{TESTS}/sub/test_sub_plain.py"        # 不匯入任何改動鏈上的模組

FILES = {
    f"{PKG}/__init__.py": "",
    f"{PKG}/lib/__init__.py": "",
    VERSION: "def suggest():\n    return '1.0'\n",
    f"{PKG}/lib/other.py": "def other():\n    return 1\n",
    f"{PKG}/commands/__init__.py": "",
    f"{PKG}/commands/create.py": "from demo_sys.lib.version import suggest\n\n\ndef run():\n    return suggest()\n",
    f"{PKG}/commands/cli.py": "from demo_sys.commands.create import run\n",
    T_DIRECT: "from demo_sys.lib.version import suggest\n\n\ndef test_x():\n    assert suggest()\n",
    T_CREATE: "def test_create():\n    from demo_sys.commands.create import run\n    assert run()\n",
    T_CLI: "import demo_sys.commands.cli\n",
    T_UNRELATED: "from demo_sys.lib.other import other\n",
    f"{TESTS}/sub/conftest.py": "",
    T_SUB: "def test_plain():\n    assert True\n",
}


@pytest.fixture
def root(tmp_path):
    for rel, text in FILES.items():
        f = tmp_path / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text, encoding="utf-8")
    return tmp_path


def write(root, rel, text):
    f = root / rel
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(text, encoding="utf-8")


def sel(root, changed, depth):
    return set(mg.select_test_files(changed, str(root), depth=depth))


def test_s2b_misses_transitive_caller_and_depth2_selects_it(root):
    """E1 對照：同一 fixture 下 k=1（S2b）不選、k=2 選中，兩者產物不同。"""
    s2b = sel(root, [VERSION], depth=1)
    k2 = sel(root, [VERSION], depth=2)
    assert s2b != k2
    assert T_CREATE not in s2b
    assert T_CREATE in k2


def test_depth1_selects_direct_importer_only(root):
    assert sel(root, [VERSION], depth=1) == {T_DIRECT}


def test_depth_bounds_chain_length(root):
    assert T_CLI not in sel(root, [VERSION], depth=2)
    assert T_CLI in sel(root, [VERSION], depth=3)
    assert T_CLI in sel(root, [VERSION], depth=None)


def test_unrelated_tests_never_selected(root):
    for depth in (1, 2, 3, None):
        got = sel(root, [VERSION], depth=depth)
        assert T_UNRELATED not in got
        assert T_SUB not in got


def test_changed_test_file_selects_itself(root):
    assert sel(root, [T_UNRELATED], depth=2) == {T_UNRELATED}


def test_name_convention_selects_matching_test(root):
    """S1：test_<stem>*.py 與改動檔同名者選中，不需匯入。"""
    write(root, f"{TESTS}/test_other_naming.py", "def test_n():\n    assert True\n")
    assert f"{TESTS}/test_other_naming.py" in sel(root, [f"{PKG}/lib/other.py"], depth=1)


def test_mention_of_hyphenated_file_selects_test(root):
    """hook 以連字號檔名經路徑載入，測試只以字串提及其檔名。"""
    write(root, ".claude/hooks/some-guard-hook.py", "print('x')\n")
    write(root, ".claude/hooks/tests/test_guard_load.py", "PATH = 'some-guard-hook.py'\n")
    got = sel(root, [".claude/hooks/some-guard-hook.py"], depth=1)
    assert ".claude/hooks/tests/test_guard_load.py" in got


def test_transitive_edges_follow_imports_not_mentions(root):
    """遞移只沿匯入邊：僅以字串提及中介模組的測試，不因遞移被選中。"""
    write(root, f"{TESTS}/test_mentions_create.py", "NAME = 'create.py'\n")
    got = sel(root, [VERSION], depth=None)
    assert f"{TESTS}/test_mentions_create.py" not in got


def test_changed_conftest_selects_its_directory(root):
    got = sel(root, [f"{TESTS}/sub/conftest.py"], depth=2)
    assert T_SUB in got


def test_conftest_reached_by_transitive_import_does_not_expand_directory(root):
    """conftest 經遞移（第 2 層以上）觸及時不展開整目錄，避免退化成全套件。"""
    write(root, f"{TESTS}/sub/conftest.py", "from demo_sys.commands.create import run\n")
    got = sel(root, [VERSION], depth=2)
    assert T_SUB not in got


def test_conftest_directly_importing_change_expands_directory(root):
    """直接匯入改動檔的 conftest 沿用 S2b：展開其目錄。"""
    write(root, f"{TESTS}/sub/conftest.py", "from demo_sys.lib.version import suggest\n")
    got = sel(root, [VERSION], depth=1)
    assert T_SUB in got


def test_deleted_file_matched_by_basename_mention(root):
    write(root, f"{TESTS}/test_gone_ref.py", "NAME = 'gone_module.py'\n")
    got = sel(root, [f"{PKG}/lib/gone_module.py"], depth=2)
    assert f"{TESTS}/test_gone_ref.py" in got


def test_default_depth_constant_is_used(root):
    assert mg.select_test_files([VERSION], str(root)) == sorted(
        sel(root, [VERSION], depth=mg.TEST_SUBSET_IMPORT_DEPTH))


def test_scan_sources_skips_worktrees_and_venv(root):
    write(root, ".claude/worktrees/x/.claude/skills/demo/tests/test_copy.py", "import demo_sys\n")
    write(root, ".claude/skills/demo/.venv/lib/test_venv.py", "import demo_sys\n")
    paths, texts = mg.scan_sources(str(root))
    assert not any("/worktrees/" in p or "/.venv/" in p for p in paths)
    assert VERSION in texts and VERSION in paths
