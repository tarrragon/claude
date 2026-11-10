"""sync-pull / sync-push 執行權限還原改以 shebang 判定（tarrragon/claude#21）。

背景：舊判準以目錄名 hooks/ 加 settings.json 反查為邊界，hooks/ 外的 shebang
腳本（scripts/、skills/<name>/scripts/ 等）在上游以 100644 追蹤時，pull 後失去
執行權限。新判準：首行為 shebang 的檔案一律 +x，非 shebang 檔案的權限不動；
pull 與 push 匯入同一判定函式（lib/executable_bits）。

取代 test_sync_exec_bit_skills_hooks.py（hooks/ 目錄名判準）與
test_sync_exec_bit_settings_registered.py（settings.json 反查判準），兩者斷言的
是已移除的舊判準。
"""
from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent


def _load(module_name: str, filename: str):
    spec = importlib.util.spec_from_file_location(module_name, _SCRIPTS_DIR / filename)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = mod
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


pull_mod = _load("sync_claude_pull", "sync-claude-pull.py")
push_mod = _load("sync_claude_push", "sync-claude-push.py")

# Windows NTFS 無 exec bit，filesystem chmod 對 mode 無作用，本測試跳過
pytestmark = pytest.mark.skipif(
    os.name == "nt", reason="POSIX exec-bit semantics required"
)

# 應加 +x：首行為 shebang、位於同步範圍內（不限 hooks/、不限 .py）
_SHEBANG_IN_SCOPE = (
    "hooks/top_hook.py",
    "skills/ticket/hooks/skill_hook.py",
    "scripts/tool.py",
    "skills/continuous-learning/evaluate-session.py",
    "skills/foo/scripts/run.sh",
)
# 不應變更：非 shebang（含 hooks/ 下的非 shebang .py），或 shebang 但在排除範圍內
_NOT_TOUCHED = (
    "hooks/lib/helper.py",            # hooks/ 下但無 shebang（舊判準會加 +x）
    "skills/foo/SKILL.md",
    "scripts/data.json",
    "hook-logs/run/leftover.py",      # local-only 目錄，shebang 也不處理
    ".venv/bin/tool",
)


def _mode(p: Path) -> int:
    return p.stat().st_mode & 0o777


def _make_tree(root: Path) -> None:
    for rel in _SHEBANG_IN_SCOPE:
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        interp = "bash" if rel.endswith(".sh") else "python3"
        path.write_text(f"#!/usr/bin/env {interp}\nprint('x')\n")
    for rel in _NOT_TOUCHED:
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        shebang = rel.startswith(("hook-logs/", ".venv/"))
        path.write_text(("#!/usr/bin/env python3\n" if shebang else "") + "content\n")
    for rel in (*_SHEBANG_IN_SCOPE, *_NOT_TOUCHED):
        (root / rel).chmod(0o644)


@pytest.mark.parametrize("mod", [pull_mod, push_mod], ids=["pull", "push"])
def test_restore_sets_exec_on_shebang_only(mod, tmp_path):
    """shebang 檔加 +x；非 shebang 與排除範圍內的檔案維持 644（E2 正反對照）。"""
    _make_tree(tmp_path)

    count = mod.restore_executable_bits(tmp_path)

    for rel in _SHEBANG_IN_SCOPE:
        assert _mode(tmp_path / rel) == 0o755, rel
    for rel in _NOT_TOUCHED:
        assert _mode(tmp_path / rel) == 0o644, rel
    assert count == len(_SHEBANG_IN_SCOPE)


@pytest.mark.parametrize("mod", [pull_mod, push_mod], ids=["pull", "push"])
def test_restore_keeps_non_shebang_mode_unchanged(mod, tmp_path):
    """非 shebang 檔案原本是 755 時不被降權，原本是 600 時不被提權。"""
    exec_plain = tmp_path / "scripts" / "already_exec.txt"
    private = tmp_path / "scripts" / "private.txt"
    exec_plain.parent.mkdir(parents=True)
    exec_plain.write_text("no shebang\n")
    private.write_text("no shebang\n")
    exec_plain.chmod(0o755)
    private.chmod(0o600)

    assert mod.restore_executable_bits(tmp_path) == 0
    assert _mode(exec_plain) == 0o755
    assert _mode(private) == 0o600


@pytest.mark.parametrize("mod", [pull_mod, push_mod], ids=["pull", "push"])
def test_restore_skips_symlink_and_is_idempotent(mod, tmp_path):
    root = tmp_path / "claude"
    target = tmp_path / "outside.py"  # 掃描根目錄之外，只能經 symlink 觸及
    target.write_text("#!/usr/bin/env python3\n")
    target.chmod(0o644)
    (root / "scripts").mkdir(parents=True)
    (root / "scripts" / "link.py").symlink_to(target)
    real = root / "scripts" / "real.py"
    real.write_text("#!/usr/bin/env python3\n")
    real.chmod(0o644)

    assert mod.restore_executable_bits(root) == 1
    assert mod.restore_executable_bits(root) == 0
    assert _mode(target) == 0o644


def test_pull_and_push_share_one_predicate():
    """push 端與 pull 端使用同一個判定函式（不是兩份對稱實作）。"""
    from lib import executable_bits

    assert pull_mod.restore_shebang_exec_bits is executable_bits.restore_shebang_exec_bits
    assert push_mod.restore_shebang_exec_bits is executable_bits.restore_shebang_exec_bits
    assert push_mod.iter_shebang_files is executable_bits.iter_shebang_files


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(root), *args], check=True, capture_output=True, text=True
    ).stdout


def test_push_index_chmod_marks_shebang_files_100755(tmp_path):
    """push 端在 git index 寫入 100755 的對象與 filesystem 判準相同。"""
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "core.fileMode", "false")  # 模擬 NTFS：index 不從 filesystem 讀 mode
    shebang = tmp_path / "scripts" / "tool.py"
    plain = tmp_path / "hooks" / "lib" / "helper.py"
    for path, text in ((shebang, "#!/usr/bin/env python3\n"), (plain, "x = 1\n")):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        path.chmod(0o644)
    _git(tmp_path, "add", "-A")

    push_mod.git_update_index_chmod(tmp_path)

    modes = {
        line.split("\t")[1]: line.split()[0]
        for line in _git(tmp_path, "ls-files", "-s").splitlines()
    }
    assert modes["scripts/tool.py"] == "100755"
    assert modes["hooks/lib/helper.py"] == "100644"
