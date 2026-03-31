#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
Skill Registration Completeness Check Hook

Verifies that all Skill directories in .claude/skills/ are properly registered
by checking for required SKILL.md files and valid YAML frontmatter.

Runs on SessionStart to catch missing or malformed Skill configurations.

Usage:
    python3 .claude/hooks/skill-registration-check-hook.py

Exit codes:
    0 - All skills properly registered (or warning only)
    0 - Missing/malformed skills detected (warning, does not block session)
"""

import re
import sys
from pathlib import Path
from typing import Dict, Set, List, Tuple, Optional

sys.path.insert(0, str(Path(__file__).parent))
from hook_utils import setup_hook_logging, run_hook_safely


def extract_skill_dirs(skills_dir: Path) -> Set[str]:
    """Extract all skill directory names from .claude/skills/."""
    skill_dirs: Set[str] = set()

    if not skills_dir.exists():
        return skill_dirs

    for dir_path in skills_dir.iterdir():
        if dir_path.is_dir() and not dir_path.name.startswith('.'):
            skill_dirs.add(dir_path.name)

    return skill_dirs


def get_exclude_list() -> Set[str]:
    """
    Get list of skill directories that should be excluded from checks.
    These are special-purpose directories that don't need SKILL.md.
    """
    return {
        'learned',  # Special purpose: stores learned patterns, empty directory expected
    }


def check_skill_registration(skill_dir: Path) -> Tuple[bool, Optional[str]]:
    """
    Check if a skill directory is properly registered.

    Returns:
        (is_registered, problem_description)
        - (True, None) if properly registered
        - (False, description) if has problems
    """

    # Check for SKILL.md (case-sensitive)
    skill_md = skill_dir / 'SKILL.md'

    # Special case: if only skill.md exists (lowercase), it's a problem
    skill_md_lowercase = skill_dir / 'skill.md'
    if skill_md_lowercase.exists() and not skill_md.exists():
        return (False, "has skill.md (lowercase) instead of SKILL.md")

    # Check if SKILL.md exists
    if not skill_md.exists():
        # Check what files are in the directory
        files = list(skill_dir.glob('*'))
        if files:
            return (False, "missing SKILL.md")
        else:
            return (False, "empty directory")

    # Check for valid YAML frontmatter in SKILL.md
    try:
        with open(skill_md, 'r', encoding='utf-8') as f:
            # Read more content to find the closing --- delimiter
            content = f.read(2000)

            # Must start with --- delimiter
            if not content.startswith('---'):
                return (False, "SKILL.md missing YAML frontmatter (no leading ---)")

            # Find closing --- delimiter (allowing for different line endings)
            lines = content.split('\n')

            if len(lines) < 2:
                return (False, "SKILL.md too short")

            # Check if first line is just ---
            if lines[0].strip() != '---':
                return (False, "SKILL.md malformed: first line should be ---")

            # Find the closing --- (skip first line, search up to 50 lines)
            closing_idx = -1
            frontmatter_lines = []

            for i in range(1, min(len(lines), 50)):
                line = lines[i]
                # --- on its own line marks the end of frontmatter
                if line.strip() == '---':
                    closing_idx = i
                    break
                frontmatter_lines.append(line)

            if closing_idx == -1:
                return (False, "SKILL.md malformed YAML frontmatter (no closing ---)")

            # Join frontmatter content
            frontmatter = '\n'.join(frontmatter_lines)

            # Check for required fields
            if 'name:' not in frontmatter:
                return (False, "SKILL.md missing 'name' field in frontmatter")

            if 'description:' not in frontmatter:
                return (False, "SKILL.md missing 'description' field in frontmatter")

            return (True, None)

    except Exception as e:
        return (False, f"error reading SKILL.md: {str(e)}")


def main():
    logger = setup_hook_logging("skill-registration-check-hook")
    # Determine project root
    script_dir = Path(__file__).parent
    project_root = script_dir.parent.parent
    skills_dir = project_root / '.claude' / 'skills'

    # Get all skill directories
    all_skills = extract_skill_dirs(skills_dir)
    exclude_list = get_exclude_list()

    # Check each skill
    problems: Dict[str, str] = {}
    registered_count = 0

    for skill_name in sorted(all_skills):
        # Skip excluded directories
        if skill_name in exclude_list:
            continue

        skill_path = skills_dir / skill_name
        is_registered, problem = check_skill_registration(skill_path)

        if is_registered:
            registered_count += 1
        else:
            problems[skill_name] = problem

    # Report results
    print("\n[SkillCheck] Skill 註冊完整性檢查結果")
    print("=" * 60)
    print(f"已註冊: {registered_count} 個")
    print(f"未註冊: {len(problems)} 個")
    print(f"已排除: {len(exclude_list)} 個")

    if problems:
        print("\n有問題的 Skill 目錄:")
        for skill_name in sorted(problems.keys()):
            print(f"  - {skill_name}: {problems[skill_name]}")

        print("\n建議修復:")
        print("  1. 確認 SKILL.md 文件名大小寫正確（必須是大寫 SKILL.md）")
        print("  2. 確認 SKILL.md 包含有效的 YAML frontmatter（以 --- 開始和結束）")
        print("  3. 確認 frontmatter 中包含 'name' 和 'description' 欄位")
    else:
        print("\n所有 Skill 目錄都已正確註冊")

    print("=" * 60)

    # Exit 0 to not block session start (warning only)
    return 0


if __name__ == "__main__":
    sys.exit(run_hook_safely(main, "skill-registration-check-hook"))
