"""專案 settings.json 的 statusLine 命令測試：以 /bin/sh 執行設定中的命令字串本身。

驗的是命令層契約，不是 statusline_lane.py 的內部邏輯（後者見 test_statusline_lane.py）：
- 腳本定位不依賴啟動目錄、不寫死本機絕對路徑
- 腳本缺席或執行失敗時退回內層狀態列（全域 statusLine.command），整條不消失
"""
import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
SETTINGS = REPO_ROOT / ".claude" / "settings.json"
SCRIPT_REL = Path(".claude/skills/multi-session-orchestration/scripts/statusline_lane.py")
INNER = "echo INNER-OUT"


def statusline_command() -> str:
    settings = json.loads(SETTINGS.read_text(encoding="utf-8"))
    return settings["statusLine"]["command"]


def make_home(tmp_path: Path) -> Path:
    home = tmp_path / "home"
    (home / ".claude").mkdir(parents=True)
    (home / ".claude" / "settings.json").write_text(
        json.dumps({"statusLine": {"type": "command", "command": INNER}}), encoding="utf-8"
    )
    return home


def run_statusline(tmp_path, stdin, project_dir_env=None):
    cwd = tmp_path / "some" / "subdir"
    cwd.mkdir(parents=True, exist_ok=True)
    env = {
        "HOME": str(make_home(tmp_path)),
        "PATH": f"{Path(sys.executable).parent}:/usr/bin:/bin",
    }
    if project_dir_env is not None:
        env["CLAUDE_PROJECT_DIR"] = str(project_dir_env)
    return subprocess.run(
        ["/bin/sh", "-c", statusline_command()],
        input=stdin, capture_output=True, text=True, env=env, cwd=cwd,
    )


def payload(project_dir=""):
    return json.dumps({"session_name": "alpha", "workspace": {"project_dir": str(project_dir)}})


def fake_project(tmp_path: Path, script_body: str) -> Path:
    project = tmp_path / "proj"
    script = project / SCRIPT_REL
    script.parent.mkdir(parents=True)
    script.write_text(script_body, encoding="utf-8")
    return project


def test_command_points_to_script_without_machine_path():
    command = statusline_command()
    assert SCRIPT_REL.as_posix() in command
    assert "/Users/" not in command and "/home/" not in command


def test_script_runs_from_subdir_via_env(tmp_path):
    result = run_statusline(tmp_path, payload(), project_dir_env=REPO_ROOT)
    assert result.stdout.splitlines()[0] == "alpha"
    assert result.stdout.splitlines()[-1] == "INNER-OUT"


def test_script_runs_via_workspace_dir_when_env_missing(tmp_path):
    result = run_statusline(tmp_path, payload(REPO_ROOT))
    assert result.stdout.splitlines()[0] == "alpha"
    assert result.stdout.splitlines()[-1] == "INNER-OUT"


def test_missing_script_falls_back_to_inner(tmp_path):
    # 對照輸入：專案目錄下沒有腳本，主命令必然失敗
    empty_project = tmp_path / "empty"
    empty_project.mkdir()
    assert not (empty_project / SCRIPT_REL).exists()
    result = run_statusline(tmp_path, payload(), project_dir_env=empty_project)
    assert result.stdout == "INNER-OUT\n"


def test_unresolvable_project_dir_falls_back_to_inner(tmp_path):
    # 對照輸入：環境變數與 stdin 都給不出專案目錄
    result = run_statusline(tmp_path, payload(""))
    assert result.stdout == "INNER-OUT\n"


def test_crashing_script_falls_back_to_inner(tmp_path):
    # 對照輸入：腳本存在但以非零結束碼崩潰；先證明它確實失敗
    project = fake_project(tmp_path, "import sys\nsys.exit(3)\n")
    direct = subprocess.run([sys.executable, str(project / SCRIPT_REL)], input="", text=True)
    assert direct.returncode != 0
    result = run_statusline(tmp_path, payload(), project_dir_env=project)
    assert result.stdout == "INNER-OUT\n"


def test_fallback_not_triggered_when_script_succeeds(tmp_path):
    # E1 對照：腳本成功時只輸出腳本結果，不再疊一份內層
    project = fake_project(tmp_path, "print('FROM-SCRIPT')\n")
    result = run_statusline(tmp_path, payload(), project_dir_env=project)
    assert result.stdout == "FROM-SCRIPT\n"
