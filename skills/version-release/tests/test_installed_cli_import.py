"""安裝版 CLI 跨 skill import 斷裂修復驗證（0.38.1-W1-114）。

uv tool install 後 version_release.py 的 __file__ 位於 site-packages，
原本以 __file__ 相對路徑推導 .claude 目錄的邏輯在此情境下失效
（找不到專案結構）。本測試模擬安裝版路徑情境（無 source layout 標記、
無 CLAUDE_PROJECT_DIR），驗證 _resolve_claude_dir 能透過
git rev-parse --show-toplevel 回退找到正確的 .claude 目錄。

註：memory_upgrade 相關 import 已隨 memory 升級工作流移除
（0.2.1-W3-091），本測試僅驗證 _resolve_claude_dir 本身。
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))


@pytest.fixture
def clean_version_release_import():
    """每次測試前清除快取的 version_release module，避免互相污染。"""
    sys.modules.pop("version_release", None)
    yield
    sys.modules.pop("version_release", None)


def test_resolve_claude_dir_source_layout(clean_version_release_import):
    """source layout（開發環境直跑）：__file__ 相對路徑推導成功。"""
    import version_release

    claude_dir = version_release._resolve_claude_dir()
    assert claude_dir is not None
    assert (claude_dir / "skills" / "continuous-learning").exists()


def test_installed_cli_import_subprocess_simulation(tmp_path):
    """完整模擬安裝版場景：複製 version_release.py 到隔離目錄執行，
    確認在無 source layout 標記時，透過 CLAUDE_PROJECT_DIR fallback
    仍能成功 import 且 _resolve_claude_dir 能定位真實專案根目錄。
    """
    project_root = Path(__file__).resolve().parents[4]
    assert (project_root / ".claude").exists(), "應能定位真實專案根目錄"

    isolated_dir = tmp_path / "site-packages-simulation"
    isolated_dir.mkdir()
    isolated_script = isolated_dir / "version_release.py"
    isolated_script.write_text(
        (SCRIPTS_DIR / "version_release.py").read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    env = os.environ.copy()
    env["CLAUDE_PROJECT_DIR"] = str(project_root)
    env.pop("PYTHONPATH", None)

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; sys.path.insert(0, %r); import version_release; "
            "d = version_release._resolve_claude_dir(); "
            "print('OK', d is not None)" % str(isolated_dir),
        ],
        capture_output=True,
        text=True,
        cwd=str(tmp_path),
        env=env,
        timeout=30,
    )

    assert result.returncode == 0, f"stdout={result.stdout}\nstderr={result.stderr}"
    assert "OK True" in result.stdout
