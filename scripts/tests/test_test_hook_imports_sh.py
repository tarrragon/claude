"""test-hook-imports.sh 測試（3.3.0-W1-051）。

背景：舊版以 `timeout 5 python3 <hook>` 執行每支 hook。macOS 預設沒有 timeout 指令，
每支 hook 都以 command not found 結束，stderr 不含 import 錯誤，腳本因此全數回報通過。

本檔以只含必要工具、不含 timeout／gtimeout 的 PATH 執行腳本：
  - 正向對照：缺 import 的 hook 必須被判為失敗（結束碼非 0）
  - 對照：可正常 import 的 hook 判為通過
  - 直譯器不存在時，hook 不可被判為通過
  - 只載入模組、不跑 __main__（主流程的副作用不發生）
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parent.parent / "test-hook-imports.sh"
_TOOLS = ["bash", "env", "dirname", "basename", "grep", "find", "sort", "head", "cat", "mktemp", "rm"]


def _make_project(tmp_path: Path, hooks: dict[str, str]) -> Path:
    root = tmp_path / "proj"
    scripts = root / ".claude" / "scripts"
    scripts.mkdir(parents=True)
    shutil.copy(_SCRIPT, scripts / "test-hook-imports.sh")
    hooks_dir = root / ".claude" / "hooks"
    hooks_dir.mkdir(parents=True)
    for name, body in hooks.items():
        (hooks_dir / name).write_text(body, encoding="utf-8")
    (root / ".claude" / "skills").mkdir()
    return root


def _make_bin(tmp_path: Path, with_python: bool) -> Path:
    """建立只含必要工具的 bin 目錄；刻意不放 timeout 與 gtimeout。"""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    tools = list(_TOOLS) + (["python3"] if with_python else [])
    for tool in tools:
        src = shutil.which(tool)
        assert src, f"測試環境缺 {tool}"
        (bin_dir / tool).symlink_to(src)
    return bin_dir


def _run(root: Path, bin_dir: Path, locale: str | None = None,
         extra_env: dict | None = None) -> subprocess.CompletedProcess:
    env = {"PATH": str(bin_dir), "HOME": os.environ.get("HOME", "/tmp")}
    if locale:
        env["LC_ALL"] = locale
    env.update(extra_env or {})
    bash = shutil.which("bash")
    return subprocess.run(
        [bash, str(root / ".claude" / "scripts" / "test-hook-imports.sh"), "--verbose"],
        capture_output=True, text=True, env=env, timeout=60,
    )


def test_bin_has_no_timeout_command(tmp_path):
    """前提：測試用 PATH 確實找不到 timeout／gtimeout。"""
    bin_dir = _make_bin(tmp_path, with_python=True)
    assert not (bin_dir / "timeout").exists()
    assert not (bin_dir / "gtimeout").exists()


def test_missing_import_hook_fails_without_timeout(tmp_path):
    """正向對照：缺 import 的 hook 在無 timeout 的 PATH 下被判為失敗。"""
    root = _make_project(tmp_path, {
        "broken-hook.py": "import module_that_does_not_exist_051\n",
        "good-hook.py": "import json\n",
    })
    result = _run(root, _make_bin(tmp_path, with_python=True))
    assert result.returncode != 0, result.stdout + result.stderr
    assert "[FAIL] .claude/hooks/broken-hook.py" in result.stdout
    assert "[PASS] .claude/hooks/good-hook.py" in result.stdout


def test_all_importable_hooks_pass_without_timeout(tmp_path):
    """對照：全部可 import 時結束碼為 0。"""
    root = _make_project(tmp_path, {"good-hook.py": "import json\n"})
    result = _run(root, _make_bin(tmp_path, with_python=True))
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Pass: 1 | Fail: 0" in result.stdout


def test_unexecuted_hook_is_not_reported_as_pass(tmp_path):
    """python3 不存在時 hook 沒被載入，不可回報通過。"""
    root = _make_project(tmp_path, {"good-hook.py": "import json\n"})
    result = _run(root, _make_bin(tmp_path, with_python=False))
    assert result.returncode != 0, result.stdout + result.stderr
    assert "[PASS]" not in result.stdout
    assert "未執行" in result.stdout


def test_unexecuted_hook_fails_under_utf8_locale(tmp_path):
    """UTF-8 locale 下輸出含全形字元的失敗行時，腳本不中途出錯，結束碼仍非 0。

    曾發生：`$rel_path（` 在 UTF-8 locale 被讀成變數名而觸發 unbound variable，
    且 EXIT trap 把結束碼改成 0，整體回報為通過。
    """
    root = _make_project(tmp_path, {"good-hook.py": "import json\n"})
    result = _run(root, _make_bin(tmp_path, with_python=False), locale="en_US.UTF-8")
    assert "unbound variable" not in result.stdout + result.stderr
    assert result.returncode != 0, result.stdout + result.stderr
    assert "Total: 1" in result.stdout


def test_main_block_is_not_executed(tmp_path):
    """只載入模組：__main__ 區塊的副作用不發生。"""
    marker = tmp_path / "main-ran"
    root = _make_project(tmp_path, {
        "side-effect-hook.py": (
            "from pathlib import Path\n"
            "if __name__ == '__main__':\n"
            f"    Path({str(marker)!r}).write_text('x')\n"
        ),
    })
    result = _run(root, _make_bin(tmp_path, with_python=True))
    assert result.returncode == 0, result.stdout + result.stderr
    assert not marker.exists()


_PEP723_HOOK = (
    "#!/usr/bin/env -S uv run --quiet --script\n"
    "# /// script\n"
    "# requires-python = \">=3.11\"\n"
    "# dependencies = [\"pyyaml\"]\n"
    "# ///\n"
    "import yaml\n"
)


def test_pep723_dependency_is_loaded_via_uv(tmp_path):
    """宣告 PEP 723 依賴的 hook 依宣告帶依賴載入，不誤報缺 import。

    對照：同一份 import 拿掉宣告時，以系統直譯器載入（是否有 yaml 視環境而定，不斷言）。
    """
    if not shutil.which("uv"):
        import pytest
        pytest.skip("環境無 uv")
    bin_dir = _make_bin(tmp_path, with_python=True)
    (bin_dir / "uv").symlink_to(shutil.which("uv"))
    root = _make_project(tmp_path, {"yaml-hook.py": _PEP723_HOOK})
    result = _run(root, bin_dir)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "[PASS] .claude/hooks/yaml-hook.py" in result.stdout


def test_pep723_dependency_with_environment_marker(tmp_path):
    """依賴字串含環境標記（巢狀引號）時仍能解析並載入。"""
    if not shutil.which("uv"):
        import pytest
        pytest.skip("環境無 uv")
    bin_dir = _make_bin(tmp_path, with_python=True)
    (bin_dir / "uv").symlink_to(shutil.which("uv"))
    hook = _PEP723_HOOK.replace(
        '# dependencies = ["pyyaml"]\n',
        "# dependencies = [\"pyyaml\",\n#     \"tomli>=1.2.0;python_version<'3.11'\",\n# ]\n",
    )
    root = _make_project(tmp_path, {"marker-hook.py": hook})
    result = _run(root, bin_dir)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "[PASS] .claude/hooks/marker-hook.py" in result.stdout


def test_pep723_hook_without_uv_is_undetermined(tmp_path):
    """宣告依賴但找不到 uv：歸為無法判定，不回報通過、也不判為 import 斷裂（結束碼 0 但有示警）。"""
    root = _make_project(tmp_path, {
        "yaml-hook.py": _PEP723_HOOK,
        "good-hook.py": "import json\n",
    })
    result = _run(root, _make_bin(tmp_path, with_python=True))
    assert result.returncode == 0, result.stdout + result.stderr
    assert "[SKIP] .claude/hooks/yaml-hook.py" in result.stdout
    assert "[PASS] .claude/hooks/yaml-hook.py" not in result.stdout
    assert "Hook import check incomplete: 1" in result.stdout
    assert "All hooks passed" not in result.stdout
    assert "[WARNING]" in result.stderr


def test_unresolvable_dependency_offline_is_undetermined(tmp_path):
    """離線且依賴無法解析：歸為無法判定，不與 import 斷裂混同。"""
    if not shutil.which("uv"):
        import pytest
        pytest.skip("環境無 uv")
    bin_dir = _make_bin(tmp_path, with_python=True)
    (bin_dir / "uv").symlink_to(shutil.which("uv"))
    hook = _PEP723_HOOK.replace('"pyyaml"', '"package-that-does-not-exist-051xyz"')
    root = _make_project(tmp_path, {"offline-hook.py": hook})
    env_extra = {"UV_OFFLINE": "1"}
    result = _run(root, bin_dir, extra_env=env_extra)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "[SKIP] .claude/hooks/offline-hook.py" in result.stdout
    assert "Undetermined: 1" in result.stdout


def test_import_breakage_still_fails_alongside_undetermined(tmp_path):
    """正向對照：同時有無法判定與真的 import 斷裂時，仍以斷裂為準回非零。"""
    root = _make_project(tmp_path, {
        "yaml-hook.py": _PEP723_HOOK,
        "broken-hook.py": "import module_that_does_not_exist_051\n",
    })
    result = _run(root, _make_bin(tmp_path, with_python=True))
    assert result.returncode != 0, result.stdout + result.stderr
    assert "[FAIL] .claude/hooks/broken-hook.py" in result.stdout


def test_pytest_support_files_are_skipped(tmp_path):
    """conftest.py 等 pytest 支援檔不列入 hook 載入檢查。"""
    root = _make_project(tmp_path, {
        "conftest.py": "import module_that_does_not_exist_051\n",
        "good-hook.py": "import json\n",
    })
    result = _run(root, _make_bin(tmp_path, with_python=True))
    assert result.returncode == 0, result.stdout + result.stderr
    assert "conftest.py" not in result.stdout


def test_import_timeout_does_not_hang(tmp_path):
    """module-level 阻塞時由 python 端逾時結束，腳本不卡住。"""
    root = _make_project(tmp_path, {"slow-hook.py": "import time\ntime.sleep(30)\n"})
    result = _run(root, _make_bin(tmp_path, with_python=True))
    assert "Total: 1" in result.stdout
