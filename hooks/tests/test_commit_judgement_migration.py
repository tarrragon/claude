"""五支 PostToolUse 提示型 hook 的 git commit 判定遷移測試（0.5.0-W1-120.7.6）

E2：每支 hook 含正向對照輸入（git -C x commit 必命中）與反向輸入
（echo git commit 不命中），並以 monkeypatch 變異確認斷言有鑑別力。
"""

import importlib.util
from pathlib import Path

import pytest

HOOKS = Path(__file__).parent.parent


def _load(filename, modname):
    spec = importlib.util.spec_from_file_location(modname, HOOKS / filename)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _cases():
    ch = _load("changelog-update-hook.py", "m_changelog")
    hd = _load("commit-handoff-hook.py", "m_handoff")
    pg = _load("post-git-commit-hook.py", "m_postgit")
    sk = _load("skill-cli-sync-check-hook.py", "m_skillsync")
    vc = _load("variable-count-literal-guard-hook.py", "m_varcount")
    return [
        ("changelog", ch, lambda m, c: m.is_git_commit({"command": c}), False),
        ("handoff", hd, lambda m, c: m.is_git_commit_command(c), True),
        ("post-git-commit", pg, lambda m, c: m._is_git_commit_command(c), True),
        ("skill-cli-sync", sk, lambda m, c: m.is_git_commit_command(c), True),
        ("variable-count", vc, lambda m, c: m.is_git_commit_command(c), True),
    ]


CASES = _cases()
IDS = [c[0] for c in CASES]


@pytest.mark.parametrize("name,mod,fn,excl", CASES, ids=IDS)
def test_positive_git_dash_c_commit_hits(name, mod, fn, excl):
    assert fn(mod, 'git -C x commit -m "feat: a"') is True


@pytest.mark.parametrize("name,mod,fn,excl", CASES, ids=IDS)
def test_negative_echo_git_commit_not_hit(name, mod, fn, excl):
    assert fn(mod, "echo git commit") is False


@pytest.mark.parametrize("name,mod,fn,excl", CASES, ids=IDS)
def test_unparsable_treated_as_miss(name, mod, fn, excl):
    assert fn(mod, 'git commit -m "unclosed') is False


@pytest.mark.parametrize("name,mod,fn,excl", CASES, ids=IDS)
def test_amend_variant_preserved(name, mod, fn, excl):
    # excl=True：原本排除 amend；False：原本不排除（子字串判定下 amend 命中）
    assert fn(mod, "git commit --amend --no-edit") is (not excl)


@pytest.mark.parametrize("name,mod,fn,excl", CASES, ids=IDS)
def test_mutation_parser_flip_changes_result(name, mod, fn, excl, monkeypatch):
    # 變異確認：判定函式恆回 False 時正向輸入翻轉；恆回 True 時反向輸入翻轉
    monkeypatch.setattr(mod, "match_git_commit", lambda *a, **k: False)
    assert fn(mod, 'git -C x commit -m "feat: a"') is False
    monkeypatch.setattr(mod, "match_git_commit", lambda *a, **k: True)
    assert fn(mod, "echo git commit") is True
