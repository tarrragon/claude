"""skill-sync CLI: sync skills with a remote skills repository."""

from __future__ import annotations

import argparse
import filecmp
import os
import shutil
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

DEFAULT_REPO = "https://github.com/tarrragon/claude-skills.git"
EXCLUDE_DIRS = {"project-integration"}


def get_repo_url() -> str:
    return os.environ.get("SKILL_SYNC_REPO", DEFAULT_REPO)


def update_versions_json(repo_dir: Path) -> None:
    """掃描 repo 內所有 skill 的 SKILL.md 版本，更新 versions.json 並 push。"""
    versions: dict[str, str] = {}
    for skill_md in sorted(repo_dir.glob("*/SKILL.md")):
        name = skill_md.parent.name
        try:
            text = skill_md.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        m = re.search(r"\*\*Version\*\*:\s*(\S+)", text)
        if not m:
            m = re.search(r"^version:\s*(\S+)", text, re.MULTILINE)
        if m:
            versions[name] = m.group(1)

    vf = repo_dir / "versions.json"
    existing = {}
    if vf.exists():
        try:
            existing = json.loads(vf.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass

    if versions == existing:
        return

    vf.write_text(
        json.dumps(versions, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    run_git(["add", "versions.json"], cwd=repo_dir)

    status = subprocess.run(
        ["git", "diff", "--cached", "--quiet"], cwd=repo_dir
    )
    if status.returncode == 0:
        return

    run_git(["commit", "-m", "chore: update versions.json"], cwd=repo_dir)
    run_git(["push"], cwd=repo_dir)
    print("  [OK] versions.json updated")


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


def _should_exclude(name: str) -> bool:
    return name in EXCLUDE_DIRS


def compute_diff(src: Path, dst: Path) -> dict[str, list[str]]:  # i18n-exempt
    """Compare src and dst directories, return categorized file lists.

    This is a disk-walk diff (compares filesystem trees directly).
    NOT interchangeable with sync-claude-push's copy_filtered_from_staging
    which uses git-tracked-only source (git archive) for security guarantees.

    Returns dict with keys: added, modified, unchanged, dst_only.
    """
    diff: dict[str, list[str]] = {
        "added": [],
        "modified": [],
        "unchanged": [],
        "dst_only": [],
    }

    src_files: set[str] = set()
    for f in src.rglob("*"):
        if f.is_file():
            rel = str(f.relative_to(src))
            if any(_should_exclude(part) for part in f.relative_to(src).parts):
                continue
            src_files.add(rel)
            dst_file = dst / rel
            if not dst_file.exists():
                diff["added"].append(rel)
            elif not filecmp.cmp(f, dst_file, shallow=False):
                diff["modified"].append(rel)
            else:
                diff["unchanged"].append(rel)

    if dst.exists():
        for f in dst.rglob("*"):
            if f.is_file():
                rel = str(f.relative_to(dst))
                if any(_should_exclude(part) for part in f.relative_to(dst).parts):
                    continue
                if rel not in src_files:
                    diff["dst_only"].append(rel)

    for key in diff:
        diff[key].sort()
    return diff


def print_diff_preview(diff: dict[str, list[str]], direction: str) -> None:
    """Print a human-readable diff preview."""
    has_changes = diff["added"] or diff["modified"]
    preserve_label = "remote-only (preserved)" if direction == "push" else "local-only (preserved)"

    if not has_changes and not diff["dst_only"]:
        print("  No changes detected.")
        return

    if diff["added"]:
        print(f"  [ADD] {len(diff['added'])} file(s):")
        for f in diff["added"]:
            print(f"    + {f}")

    if diff["modified"]:
        print(f"  [MOD] {len(diff['modified'])} file(s):")
        for f in diff["modified"]:
            print(f"    ~ {f}")

    if diff["dst_only"]:
        print(f"  [{preserve_label}] {len(diff['dst_only'])} file(s):")
        for f in diff["dst_only"]:
            print(f"    ? {f}")

    if diff["unchanged"]:
        print(f"  [unchanged] {len(diff['unchanged'])} file(s)")


def overlay_copy(src: Path, dst: Path, diff: dict[str, list[str]]) -> int:
    """Copy only added and modified files from src to dst. Never delete dst-only files.

    Known limitation: not atomic — partial failure leaves inconsistent state.
    Acceptable for single-user CLI; git history provides recovery path.
    """
    copied = 0
    for rel in diff["added"] + diff["modified"]:
        src_file = src / rel
        dst_file = dst / rel
        dst_file.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_file, dst_file)
        copied += 1
    return copied


def cmd_pull(args: argparse.Namespace) -> None:
    name: str = args.name
    force: bool = args.force
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

        diff = compute_diff(source, target)
        print("\n[Pull Preview]")
        print_diff_preview(diff, direction="pull")

        if not diff["added"] and not diff["modified"]:
            print(f"\n'{name}' is up to date.")
            return

        if diff["dst_only"]:
            print(f"\n  Note: {len(diff['dst_only'])} local-only file(s) will be preserved.")

        if not force:
            print("\n  Use --force to apply changes without confirmation.")
            try:
                answer = input("  Apply changes? [y/N] ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                answer = ""
            if answer != "y":
                print("  Aborted.")
                return

        copied = overlay_copy(source, target, diff)
        print(f"\nPulled '{name}' to {target} ({copied} file(s) updated)")


def cmd_push(args: argparse.Namespace) -> None:
    name: str = args.name
    message: str = args.message or f"Update skill: {name}"
    force: bool = args.force
    repo_url = get_repo_url()
    skills_dir = get_skills_dir()
    source = skills_dir / name

    if not source.is_dir():
        print(f"Error: local skill '{name}' not found at {source}", file=sys.stderr)
        sys.exit(1)

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir) / "repo"
        print(f"Pushing skill '{name}' to {repo_url} ...")

        # depth-1 full clone (not sparse) — push needs complete repo for git add/commit/push.
        # Sparse checkout would reduce download but git add -A behavior differs on sparse repos.
        run_git(["clone", "--depth", "1", repo_url, str(tmp)])

        target = tmp / name

        diff = compute_diff(source, target)
        print("\n[Push Preview]")
        print_diff_preview(diff, direction="push")

        if not diff["added"] and not diff["modified"]:
            print("\nNo changes to push.")
            return

        if diff["dst_only"]:
            print(f"\n  Note: {len(diff['dst_only'])} remote-only file(s) will be preserved (not deleted).")

        if not force:
            print("\n  Use --force to apply changes without confirmation.")
            try:
                answer = input("  Apply changes? [y/N] ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                answer = ""
            if answer != "y":
                print("  Aborted.")
                return

        overlay_copy(source, target, diff)

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

        update_versions_json(tmp)

    print(f"\nPushed '{name}' to {repo_url}")


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
    pull_parser.add_argument("--force", "-f", action="store_true",
                             help="Apply changes without confirmation")

    push_parser = sub.add_parser("push", help="Push a local skill to remote repo")
    push_parser.add_argument("name", help="Skill name to push")
    push_parser.add_argument("-m", "--message", help="Commit message", default=None)
    push_parser.add_argument("--force", "-f", action="store_true",
                             help="Apply changes without confirmation")

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
