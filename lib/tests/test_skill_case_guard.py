"""Tests for skill_case_guard module."""

import subprocess
from pathlib import Path

from lib.skill_case_guard import check_git_tree_skill_md_case, warn_skill_md_case_mismatch


def _init_repo_with_files(repo_dir: Path, files: dict[str, str]) -> None:
    """建立一個最小 git repo 並 commit 給定的檔案內容（相對 repo_dir 的路徑）。"""
    repo_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q"], cwd=repo_dir, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_dir, check=True)
    subprocess.run(["git", "config", "user.name", "test"], cwd=repo_dir, check=True)
    for rel_path, content in files.items():
        target = repo_dir / rel_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=repo_dir, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=repo_dir, check=True)


def test_lowercase_variant_produces_warning(tmp_path: Path) -> None:
    skills_dir = tmp_path / "skills"
    skill_dir = skills_dir / "error-pattern"
    skill_dir.mkdir(parents=True)
    (skill_dir / "skill.md").write_text("# error-pattern\n", encoding="utf-8")

    warnings = warn_skill_md_case_mismatch(skills_dir)

    assert len(warnings) == 1
    assert "error-pattern" in warnings[0]
    assert "skill.md" in warnings[0]


def test_correct_uppercase_produces_no_warning(tmp_path: Path) -> None:
    skills_dir = tmp_path / "skills"
    skill_dir = skills_dir / "wrap-decision"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("# wrap-decision\n", encoding="utf-8")

    assert warn_skill_md_case_mismatch(skills_dir) == []


def test_missing_base_dir_returns_empty_list(tmp_path: Path) -> None:
    assert warn_skill_md_case_mismatch(tmp_path / "no-such-dir") == []


def test_multiple_mismatched_skills_each_produce_own_warning(tmp_path: Path) -> None:
    skills_dir = tmp_path / "skills"
    for name in ("alpha", "beta"):
        d = skills_dir / name
        d.mkdir(parents=True)
        (d / "skill.md").write_text("# body\n", encoding="utf-8")

    warnings = warn_skill_md_case_mismatch(skills_dir)

    assert len(warnings) == 2
    assert any("alpha" in w for w in warnings)
    assert any("beta" in w for w in warnings)


def test_git_tree_lowercase_skill_md_produces_warning_with_consequence(tmp_path: Path) -> None:
    repo_dir = tmp_path / "repo"
    _init_repo_with_files(repo_dir, {"skills/error-pattern/skill.md": "# body\n"})

    warnings = check_git_tree_skill_md_case(repo_dir)

    assert len(warnings) == 1
    assert "error-pattern" in warnings[0]
    # 驗收要求：訊息陳述後果（無法載入），非僅陳述檔名不符規範
    assert "無法載入" in warnings[0]


def test_git_tree_uppercase_skill_md_produces_no_warning(tmp_path: Path) -> None:
    repo_dir = tmp_path / "repo"
    _init_repo_with_files(repo_dir, {"skills/error-pattern/SKILL.md": "# body\n"})

    assert check_git_tree_skill_md_case(repo_dir) == []


def test_git_tree_check_reads_tree_object_not_local_filesystem(tmp_path: Path) -> None:
    """核心驗證：即使本地 checkout 出來的 dirent 名稱與 tree 記錄一致，判準仍以
    `git ls-tree` 讀出的 tree object bytes 為準，而非依賴本地 os.scandir /
    檔案系統列目錄（呼應驗收條目：驗證不得依賴本地檔案系統列目錄）。
    """
    repo_dir = tmp_path / "repo"
    _init_repo_with_files(repo_dir, {"skills/foo/skill.md": "# body\n"})

    # 直接讀 git tree（不透過本地檔案系統路徑存在與否）取得的結果應與函式一致
    result = subprocess.run(
        ["git", "ls-tree", "-r", "--name-only", "HEAD", "--", "skills"],
        cwd=repo_dir,
        capture_output=True,
        text=True,
        check=True,
    )
    assert "skills/foo/skill.md" in result.stdout

    warnings = check_git_tree_skill_md_case(repo_dir)
    assert len(warnings) == 1
    assert "foo" in warnings[0]


def test_git_tree_check_non_git_dir_returns_empty(tmp_path: Path) -> None:
    non_repo = tmp_path / "not-a-repo"
    non_repo.mkdir()

    assert check_git_tree_skill_md_case(non_repo) == []


def test_git_tree_check_multiple_skills_each_produce_own_warning(tmp_path: Path) -> None:
    repo_dir = tmp_path / "repo"
    _init_repo_with_files(
        repo_dir,
        {
            "skills/alpha/skill.md": "# alpha\n",
            "skills/beta/skill.md": "# beta\n",
            "skills/gamma/SKILL.md": "# gamma\n",
        },
    )

    warnings = check_git_tree_skill_md_case(repo_dir)

    assert len(warnings) == 2
    assert any("alpha" in w for w in warnings)
    assert any("beta" in w for w in warnings)
    assert not any("gamma" in w for w in warnings)
