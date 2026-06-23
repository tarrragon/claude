"""skill-sync CLI: sync skills with a remote skills repository."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

DEFAULT_REPO = "https://github.com/tarrragon/claude-skills.git"
EXCLUDE_DIRS = {"project-integration"}


def get_repo_url() -> str:
    return os.environ.get("SKILL_SYNC_REPO", DEFAULT_REPO)


def get_skills_dir() -> Path:
    return Path.cwd() / ".claude" / "skills"


def run_git(args: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        ["git"] + args,
        cwd=cwd,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"git error: {result.stderr.strip()}", file=sys.stderr)
        sys.exit(1)
    return result


def copytree_filtered(src: Path, dst: Path) -> None:
    """Copy directory tree, excluding EXCLUDE_DIRS."""
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(
        src,
        dst,
        ignore=shutil.ignore_patterns(*EXCLUDE_DIRS),
    )


def cmd_pull(args: argparse.Namespace) -> None:
    name: str = args.name
    repo_url = get_repo_url()
    skills_dir = get_skills_dir()
    target = skills_dir / name

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir) / "repo"
        print(f"Pulling skill '{name}' from {repo_url} ...")

        run_git(["clone", "--depth", "1", "--filter=blob:none", "--sparse", repo_url, str(tmp)])
        run_git(["sparse-checkout", "set", f"{name}/"], cwd=tmp)

        source = tmp / name
        if not source.is_dir():
            print(f"Error: skill '{name}' not found in remote repo.", file=sys.stderr)
            sys.exit(1)

        skills_dir.mkdir(parents=True, exist_ok=True)
        copytree_filtered(source, target)

    print(f"Pulled '{name}' to {target}")


def cmd_push(args: argparse.Namespace) -> None:
    name: str = args.name
    message: str = args.message or f"Update skill: {name}"
    repo_url = get_repo_url()
    skills_dir = get_skills_dir()
    source = skills_dir / name

    if not source.is_dir():
        print(f"Error: local skill '{name}' not found at {source}", file=sys.stderr)
        sys.exit(1)

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir) / "repo"
        print(f"Pushing skill '{name}' to {repo_url} ...")

        run_git(["clone", "--depth", "1", repo_url, str(tmp)])

        target = tmp / name
        copytree_filtered(source, target)

        run_git(["add", "-A"], cwd=tmp)

        status = subprocess.run(
            ["git", "diff", "--cached", "--quiet"],
            cwd=tmp,
        )
        if status.returncode == 0:
            print("No changes to push.")
            return

        run_git(["commit", "-m", message], cwd=tmp)
        run_git(["push"], cwd=tmp)

    print(f"Pushed '{name}' to {repo_url}")


def cmd_list(args: argparse.Namespace) -> None:
    repo_url = get_repo_url()

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir) / "repo"
        run_git(["clone", "--depth", "1", "--filter=blob:none", "--sparse", repo_url, str(tmp)])
        run_git(["sparse-checkout", "set", "--no-cone", "*/SKILL.md"], cwd=tmp)

        result = run_git(["ls-tree", "--name-only", "HEAD"], cwd=tmp)
        dirs = [line for line in result.stdout.strip().splitlines() if line]

        if not dirs:
            print("No skills found in remote repo.")
            return

        print(f"{'Skill':<30} Description")
        print(f"{'-----':<30} -----------")

        for d in sorted(dirs):
            skill_md = tmp / d / "SKILL.md"
            desc = ""
            if skill_md.is_file():
                for line in skill_md.read_text(encoding="utf-8").splitlines():
                    stripped = line.strip()
                    if stripped and not stripped.startswith("#"):
                        desc = stripped[:70]
                        break
            print(f"{d:<30} {desc}")


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="skill-sync",
        description="Sync Claude Code skills with a remote repository.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    pull_parser = sub.add_parser("pull", help="Pull a skill from remote repo")
    pull_parser.add_argument("name", help="Skill name to pull")

    push_parser = sub.add_parser("push", help="Push a local skill to remote repo")
    push_parser.add_argument("name", help="Skill name to push")
    push_parser.add_argument("-m", "--message", help="Commit message", default=None)

    sub.add_parser("list", help="List available skills in remote repo")

    args = parser.parse_args()

    commands = {
        "pull": cmd_pull,
        "push": cmd_push,
        "list": cmd_list,
    }
    commands[args.command](args)


if __name__ == "__main__":
    main()
