"""parallel-dispatch-verification：目錄條目、未追蹤新檔、::read 提示。

驗證：
1. where.files 的目錄條目（有無尾斜線皆同）底下有該票變更時不報缺失（修正前恆報缺失）
2. 未追蹤的新檔計入未提交變更（修正前 git diff HEAD 抓不到，報缺失）
3. 正向對照（E2）：真正未修改的檔案仍報缺失；目錄條目底下無變更仍報缺失；
   同字首的兄弟目錄變更不覆蓋目錄條目
4. 缺失警告的建議段提示 ::read

git fixture 為 function scope 的 tmp repo；git 子行程以去除 GIT_* 的 env 執行。
"""

import importlib.util
import json
import os
import subprocess
import sys
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import pytest

HOOK_PATH = Path(__file__).parent.parent / "parallel-dispatch-verification-hook.py"
TICKET = "0.1.0-W41-003"


def _load():
    spec = importlib.util.spec_from_file_location("pdv_dir_untracked", HOOK_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


hook = _load()

_ENV = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}


def _git(repo, *args):
    subprocess.run(["git", "-C", str(repo), *args], check=True,
                   capture_output=True, text=True, env=_ENV)


def _commit(repo, files, message):
    for name in files:
        f = repo / name
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(f"{message}\n{name}\n", encoding="utf-8")
        _git(repo, "add", name)
    _git(repo, "commit", "-q", "-m", message)


@pytest.fixture
def repo(tmp_path):
    r = tmp_path / "repo"
    r.mkdir()
    _git(r, "init", "-q", "-b", "main")
    _git(r, "config", "user.email", "t@example.com")
    _git(r, "config", "user.name", "t")
    _git(r, "config", "commit.gpgsign", "false")
    _commit(r, ["base.txt", "pkg-extra/keep.py"], "base")
    _commit(r, ["pkg/mod/a.py", "src/b.py"], f"fix({TICKET}): work")
    return r


def _run(where_files, repo):
    payload = {"tool_name": "Bash",
               "tool_input": {"command": f"ticket track complete {TICKET}"},
               "tool_response": {"stdout": "[OK] 已完成 Ticket", "stderr": "",
                                 "interrupted": False, "isImage": False,
                                 "noOutputExpected": False}}
    out = StringIO()
    with patch.object(hook, "read_json_from_stdin", return_value=payload), \
         patch.object(hook, "is_subagent_environment", return_value=False), \
         patch.object(hook, "get_project_root", return_value=repo), \
         patch.object(hook, "read_ticket_where_files", return_value=where_files), \
         patch("sys.stdout", out):
        hook.main()
    return json.loads(out.getvalue())["hookSpecificOutput"].get("additionalContext", "")


def _missing(ctx):
    lines = ctx.splitlines()
    head = next((i for i, l in enumerate(lines) if l.startswith("缺失檔案")), None)
    if head is None:
        return []
    items = []
    for l in lines[head + 1:]:
        if not l.startswith("  - "):
            break
        items.append(l[4:])
    return items


# ---------- 目錄條目 ----------

@pytest.mark.parametrize("entry", ["pkg", "pkg/", "pkg/mod", "pkg/mod/"])
def test_directory_entry_with_changes_not_missing(repo, entry):
    where = [hook.normalize_path(entry), "src/b.py"]
    assert _missing(_run(where, repo)) == []


def test_find_missing_files_directory_prefix():
    assert hook.find_missing_files(["pkg"], ["pkg/mod/a.py"]) == []


@pytest.mark.parametrize("where,changed,expected", [
    (["docs"], ["pkg/mod/a.py"], ["docs"]),          # 目錄底下無變更 → 仍缺失
    (["pkg"], ["pkg-extra/keep.py"], ["pkg"]),       # 同字首兄弟目錄不覆蓋
    (["src/c.py"], ["src/b.py"], ["src/c.py"]),      # 真正未修改的檔案
])
def test_find_missing_files_positive_control(where, changed, expected):
    # E2 正向對照
    assert hook.find_missing_files(where, changed) == expected


def test_untouched_file_still_reported_end_to_end(repo):
    assert _missing(_run(["src/b.py", "src/never_touched.py"], repo)) == ["src/never_touched.py"]


# ---------- 未追蹤新檔 ----------

def test_untracked_new_file_counted_as_uncommitted(repo):
    (repo / "src" / "new_untracked.py").write_text("x\n", encoding="utf-8")
    ctx = _run(["src/b.py", "src/new_untracked.py"], repo)
    assert _missing(ctx) == []
    assert "  - src/new_untracked.py" in ctx.splitlines()  # 列為產出未 commit


def test_gitignored_file_not_counted(repo):
    (repo / ".gitignore").write_text("ignored.py\n", encoding="utf-8")
    _git(repo, "add", ".gitignore")
    _git(repo, "commit", "-q", "-m", "ignore")
    (repo / "ignored.py").write_text("x\n", encoding="utf-8")
    assert _missing(_run(["src/b.py", "ignored.py"], repo)) == ["ignored.py"]


# ---------- 訊息 ----------

def test_missing_warning_mentions_read_suffix(repo):
    ctx = _run(["src/b.py", "src/never_touched.py"], repo)
    assert "::read" in ctx
