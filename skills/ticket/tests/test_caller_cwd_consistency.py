"""ticket、worktree、doc 三處內嵌的 restore_caller_cwd 行為須一致。

以 ast 取出各檔的函式原始碼獨立執行，避免匯入 worktree_manager 的模組層副作用。
"""

import ast
import os
import sys
from pathlib import Path

import pytest

SKILLS = Path(__file__).resolve().parents[2]
SOURCES = {
    "ticket": SKILLS / "ticket/ticket_system/scripts/ticket.py",
    "worktree": SKILLS / "worktree/scripts/worktree_manager.py",
    "doc": SKILLS / "doc/doc_system/cli.py",
}
ENV = "SKILL_CLI_CALLER_CWD"


def _extract(path: Path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    keep = [
        n for n in tree.body
        if (isinstance(n, ast.FunctionDef) and n.name == "restore_caller_cwd")
        or (isinstance(n, ast.Assign) and getattr(n.targets[0], "id", "") == "CALLER_CWD_ENV")
    ]
    ns = {"os": os, "sys": sys}
    exec(compile(ast.Module(body=keep, type_ignores=[]), str(path), "exec"), ns)
    return ns["restore_caller_cwd"]


@pytest.fixture(autouse=True)
def _restore_cwd(monkeypatch):
    """被測函式會真的 os.chdir；先記下原 cwd，拆除時還原，避免汙染後續測試檔。"""
    monkeypatch.chdir(os.getcwd())


@pytest.fixture(params=sorted(SOURCES))
def restore(request):
    return _extract(SOURCES[request.param])


def test_valid_value_changes_cwd(restore, tmp_path, monkeypatch, capsys):
    target = tmp_path / "caller"
    target.mkdir()
    monkeypatch.setenv(ENV, str(target))
    restore()
    assert Path.cwd() == target.resolve()
    assert capsys.readouterr().err == ""


def test_unset_keeps_cwd(restore, tmp_path, monkeypatch, capsys):
    monkeypatch.delenv(ENV, raising=False)
    before = Path.cwd()
    restore()
    assert Path.cwd() == before
    assert capsys.readouterr().err == ""


@pytest.mark.parametrize("bad", ["relative/dir", "/nonexistent/zzz-caller"])
def test_invalid_value_warns_and_keeps_cwd(restore, monkeypatch, capsys, bad):
    monkeypatch.setenv(ENV, bad)
    before = os.getcwd()
    restore()
    err = capsys.readouterr().err
    assert os.getcwd() == before
    assert ENV in err and bad in err and before in err


def test_relative_and_absolute_path_agree(restore, tmp_path, monkeypatch):
    """E1 對照：還原後，相對與絕對路徑引數解析到同一檔案。"""
    caller = tmp_path / "caller"
    (caller / "lib").mkdir(parents=True)
    (caller / "lib/a.txt").write_text("x")
    monkeypatch.setenv(ENV, str(caller))
    restore()
    assert os.path.abspath("lib/a.txt") == os.path.abspath(str(caller / "lib/a.txt"))
    assert os.path.abspath("lib/a.txt") != str(tmp_path / "lib/a.txt")


@pytest.mark.parametrize("value", ["valid", "relative/dir"])
def test_env_var_consumed_after_call(restore, tmp_path, monkeypatch, value):
    """讀一次即移除：避免子行程（如合併閘門的 pytest）繼承並被再次 chdir。"""
    monkeypatch.setenv(ENV, str(tmp_path) if value == "valid" else value)
    restore()
    assert ENV not in os.environ


def test_child_process_does_not_see_env(restore, tmp_path, monkeypatch):
    import subprocess

    monkeypatch.setenv(ENV, str(tmp_path))
    restore()
    out = subprocess.run(
        [sys.executable, "-c", f"import os;print(os.environ.get('{ENV}'))"],
        capture_output=True, text=True, env=os.environ.copy(),
    )
    assert out.stdout.strip() == "None"


def test_implementations_identical():
    bodies = {
        name: ast.dump(next(
            n for n in ast.parse(p.read_text(encoding="utf-8")).body
            if isinstance(n, ast.FunctionDef) and n.name == "restore_caller_cwd"
        ))
        for name, p in SOURCES.items()
    }
    assert len(set(bodies.values())) == 1


def test_worktree_restores_before_project_root_eval():
    """根目錄求值時點鎖定：讀回須早於模組層 _resolve_project_root() 呼叫。"""
    src = SOURCES["worktree"].read_text(encoding="utf-8")
    assert src.index("\nrestore_caller_cwd()\n") < src.index("project_root = _resolve_project_root()")


def test_ticket_main_restores_before_anything_else():
    src = SOURCES["ticket"].read_text(encoding="utf-8")
    main_body = src[src.index("def main() -> int:"):]
    assert main_body.index("restore_caller_cwd()") < main_body.index("check_installation()")
