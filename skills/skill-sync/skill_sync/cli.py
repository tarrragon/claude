"""skill-sync CLI: sync skills with a remote skills repository."""

from __future__ import annotations

import argparse
import filecmp
import hashlib
import os
import shutil
import json
import re
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

DEFAULT_REPO = "https://github.com/tarrragon/claude-skills.git"
EXCLUDE_DIRS = {
    "project-integration",
    ".venv",
    "__pycache__",
    ".pytest_cache",
    "build",
    ".egg-info",
    "hook-logs",
}

# 標記檔存在即宣告該 skill 的本地內容為刻意客製，`pull`（全量）分歧檢查略過回報
# （0.2.1-W3-124 acceptance 4 的宣告式 local override 決策：見 update_sync_manifest
# 與 _classify_sync_status 的 docstring）。
SKILL_SYNC_OVERRIDE_MARKER = ".skill-sync-override"


def _should_exclude_file(rel_path: str) -> bool:
    """Check if a file path should be excluded (covers dir names, incl. nested hook-logs/)."""
    parts = Path(rel_path).parts
    for part in parts:
        if part in EXCLUDE_DIRS or part.endswith(".egg-info"):
            return True
    return False


def get_repo_url() -> str:
    return os.environ.get("SKILL_SYNC_REPO", DEFAULT_REPO)


def _extract_version_string(text: str) -> str | None:
    """從 SKILL.md 文字擷取版本字串。

    僅供人類於 changelog 對照閱讀，不進入同步決策（見 update_sync_manifest）。
    """
    m = re.search(r"\*\*Version\*\*:\s*(\S+)", text)
    if not m:
        m = re.search(r"^version:\s*(\S+)", text, re.MULTILINE)
    return m.group(1) if m else None


def compute_content_hash(skill_dir: Path) -> str | None:
    """依檔案內容計算 skill 目錄的確定性雜湊，取代版本字串作為內容同一性判定依據。

    對 (相對路徑, 檔案位元組) 依路徑排序後逐一雜湊，雜湊值只反映內容與檔案樹結構，
    與 mtime、掃描順序、檔案系統無關：相同內容不論何處產生都得到相同雜湊，內容不同
    則版本字串相同也得到不同雜湊。這修正的是版本字串同時被當內容同一性與演化祖先關係
    使用、卻兩者都擔不起的機制缺陷（0.2.1-W3-124 §11.2：blog 與 canonical 的 2.5.0
    號碼相同、內容不同，曾被判為 up_to_date）。回傳 None 表示目錄不存在。
    """
    if not skill_dir.is_dir():
        return None

    rel_paths: list[str] = []
    for f in skill_dir.rglob("*"):
        if not f.is_file():
            continue
        rel = str(f.relative_to(skill_dir))
        if f.name == SKILL_SYNC_OVERRIDE_MARKER or _should_exclude_file(rel):
            continue
        rel_paths.append(rel)
    rel_paths.sort()

    hasher = hashlib.sha256()
    for rel in rel_paths:
        hasher.update(rel.encode("utf-8"))
        hasher.update((skill_dir / rel).read_bytes())
    return hasher.hexdigest()


def _has_local_override(skill_dir: Path) -> bool:
    """標記檔存在即宣告本地內容為刻意客製，`pull`（全量）分歧檢查略過此 skill。"""
    return (skill_dir / SKILL_SYNC_OVERRIDE_MARKER).is_file()


def update_sync_manifest(repo_dir: Path) -> None:
    """掃描 repo 內所有 skill，寫入版本字串（人類可讀）與內容雜湊（同步判定用）至 versions.json。

    版本字串不再進入同步決策：舊實作以版本字串相等判定內容同一性、以 semver 大小
    判定覆蓋方向，但兩個獨立演化的分支可能巧合共用同一版本號卻內容不同，semver
    比較亦預設線性演進，對分支式分歧失準（0.2.1-W3-124 §11.2）。版本字串保留於本檔
    供人類於 changelog 對照，內容同一性判定改用 hash 欄位。
    """
    manifest: dict[str, dict[str, str]] = {}
    for skill_md in sorted(repo_dir.glob("*/SKILL.md")):
        name = skill_md.parent.name
        content_hash = compute_content_hash(skill_md.parent)
        if content_hash is None:
            continue
        entry: dict[str, str] = {"hash": content_hash}
        try:
            text = skill_md.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            text = ""
        version = _extract_version_string(text)
        if version:
            entry["version"] = version
        manifest[name] = entry

    vf = repo_dir / "versions.json"
    existing = {}
    if vf.exists():
        try:
            existing = json.loads(vf.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass

    if manifest == existing:
        return

    vf.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
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
            if _should_exclude_file(rel):
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
                if _should_exclude_file(rel):
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

        local_ver = _extract_single_version(source / "SKILL.md")
        remote_ver = _extract_single_version(target / "SKILL.md") if target.is_dir() else None
        if local_ver and remote_ver and local_ver != remote_ver:
            print(f"\n  [Version] local {local_ver} vs remote {remote_ver}")

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

        update_sync_manifest(tmp)

    print(f"\nPushed '{name}' to {repo_url}")


def _classify_sync_status(
    local_manifest: dict[str, dict[str, str]],
    remote_manifest: dict,
    skills_dir: Path,
) -> tuple[list[str], list[tuple[str, str, str]], list[str], list[str]]:
    """依內容雜湊分類本地 skill 相對 remote manifest 的同步狀態。

    回傳 (up_to_date, diverged, overridden, skipped_no_hash)。雜湊相同 -> up_to_date；
    雜湊不同 -> diverged（覆蓋方向未知，需人工執行 pull/push 決定，見下方 rationale）；
    標記 SKILL_SYNC_OVERRIDE_MARKER -> overridden（略過分歧判定）；remote 尚未有 hash
    欄位（舊格式 versions.json，需下次 push 後才會補上）-> skipped_no_hash。

    不再嘗試自動判定覆蓋方向：舊實作以 semver 大小決定「該推或該拉」，但這預設了
    線性演進，對分支式分歧（兩個獨立演化的副本巧合共用同一版本號）必定失準
    （0.2.1-W3-124 §11.2）。內容雜湊只能證明「相同或不同」，方向留給人工判斷。
    """
    up_to_date: list[str] = []
    diverged: list[tuple[str, str, str]] = []
    overridden: list[str] = []
    skipped_no_hash: list[str] = []

    for name, local_entry in sorted(local_manifest.items()):
        if _has_local_override(skills_dir / name):
            overridden.append(name)
            continue

        remote_entry = remote_manifest.get(name)
        if not isinstance(remote_entry, dict) or "hash" not in remote_entry:
            skipped_no_hash.append(name)
            continue

        if local_entry["hash"] == remote_entry["hash"]:
            up_to_date.append(name)
        else:
            local_display = local_entry.get("version") or local_entry["hash"][:8]
            remote_display = remote_entry.get("version") or remote_entry["hash"][:8]
            diverged.append((name, local_display, remote_display))

    return up_to_date, diverged, overridden, skipped_no_hash


def cmd_pull_all(args: argparse.Namespace) -> None:
    """掃描本地已安裝 skill，以內容雜湊比對 versions.json，回報分歧供人工處理。

    --force 對此路徑無效：分歧不再自動套用（見 _classify_sync_status），每個分歧
    項目一律需個別執行 `skill-sync pull <name>` 或 `skill-sync push <name>` 決定方向。
    """
    repo_url = get_repo_url()
    skills_dir = get_skills_dir()

    local_manifest = _extract_local_manifest(skills_dir)
    if not local_manifest:
        print("No local skills found.")
        return

    raw_url = repo_url.replace(
        "https://github.com/", "https://raw.githubusercontent.com/"
    ).removesuffix(".git") + "/main/versions.json"

    try:
        req = urllib.request.Request(raw_url, headers={"User-Agent": "skill-sync"})
        # magic-exempt
        with urllib.request.urlopen(req, timeout=10) as resp:
            remote_manifest: dict = json.loads(resp.read())
    except Exception as e:
        print(f"Failed to fetch versions.json: {e}")
        print("Falling back to individual pull...")
        remote_manifest = {}

    if not remote_manifest:
        print("versions.json not available. Use 'skill-sync pull <name>' instead.")
        return

    up_to_date, diverged, overridden, skipped_no_hash = _classify_sync_status(
        local_manifest, remote_manifest, skills_dir
    )

    if overridden:
        print(f"[OVERRIDE] {len(overridden)} skill(s) declared local override "
              f"(skipped from divergence check):")
        for name in overridden:
            print(f"  {name}")

    if skipped_no_hash:
        print(f"\n[SKIP] {len(skipped_no_hash)} skill(s) have no remote hash data yet "
              f"(remote versions.json needs regenerating via next 'skill-sync push'):")
        for name in skipped_no_hash:
            print(f"  {name}")

    if not diverged:
        print(f"\nAll {len(up_to_date)} checked skill(s) are up to date.")
        return

    print(f"\n[DIVERGED] {len(diverged)} skill(s) differ from remote by content. "
          f"Direction unknown from hash alone — review and resolve manually:\n")
    for name, local_display, remote_display in diverged:
        print(f"  {name}: local({local_display}) vs remote({remote_display})")
        print(f"    -> skill-sync pull {name}   # inspect/take remote content")
        print(f"    -> skill-sync push {name}   # inspect/send local content")

    if up_to_date:
        print(f"\n{len(up_to_date)} other skill(s) are up to date.")


def _extract_single_version(skill_md: Path) -> str | None:
    """從單一 SKILL.md 提取版本號（僅供人類顯示，不進入同步判定）。"""
    if not skill_md.is_file():
        return None
    try:
        text = skill_md.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    return _extract_version_string(text)


def _extract_local_manifest(skills_dir: Path) -> dict[str, dict[str, str]]:
    """掃描本地 skills/*，回傳每個 skill 的內容雜湊（同步判定用）與版本字串（人類顯示用）。"""
    manifest: dict[str, dict[str, str]] = {}
    if not skills_dir.is_dir():
        return manifest
    for skill_md in sorted(skills_dir.glob("*/SKILL.md")):
        skill_dir = skill_md.parent
        content_hash = compute_content_hash(skill_dir)
        if content_hash is None:
            continue
        entry: dict[str, str] = {"hash": content_hash}
        try:
            text = skill_md.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            text = ""
        version = _extract_version_string(text)
        if version:
            entry["version"] = version
        manifest[skill_dir.name] = entry
    return manifest


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
    pull_parser.add_argument("name", nargs="?", default=None,
                             help="Skill name to pull (omit to update all installed)")
    pull_parser.add_argument("--force", "-f", action="store_true",
                             help="Apply changes without confirmation")

    push_parser = sub.add_parser("push", help="Push a local skill to remote repo")
    push_parser.add_argument("name", help="Skill name to push")
    push_parser.add_argument("-m", "--message", help="Commit message", default=None)
    push_parser.add_argument("--force", "-f", action="store_true",
                             help="Apply changes without confirmation")

    sub.add_parser("list", help="List available skills in remote repo")

    args = parser.parse_args()

    if args.command == "pull" and args.name is None:
        cmd_pull_all(args)
    else:
        commands = {
            "pull": cmd_pull,
            "push": cmd_push,
            "list": cmd_list,
        }
        commands[args.command](args)


if __name__ == "__main__":
    main()
