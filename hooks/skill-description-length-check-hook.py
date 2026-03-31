#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
Skill Description Length Check Hook

掃描所有 .claude/skills/*/SKILL.md 的 YAML frontmatter description 欄位長度。
超過 250 字的輸出 warning，協助維持 description 精簡以避免觸發詞截斷。

事件：SessionStart
退出碼：0（純提醒，不阻擋）
"""

import sys
from pathlib import Path
from typing import List, Tuple

sys.path.insert(0, str(Path(__file__).parent))
from hook_utils import setup_hook_logging, run_hook_safely, get_project_root

# description 長度閾值（字元數）
WARNING_THRESHOLD = 250
INFO_THRESHOLD = 100


def parse_description_from_frontmatter(skill_md_path: Path) -> Tuple[bool, str]:
    """
    從 SKILL.md 解析 YAML frontmatter 中的 description 欄位。

    需求：description 可能是單行或多行（YAML block scalar）。
    不使用外部 YAML 套件，手動解析以維持零依賴。

    Returns:
        (found, description_text)
    """
    try:
        content = skill_md_path.read_text(encoding="utf-8")
    except Exception:
        return (False, "")

    lines = content.split("\n")

    # 必須以 --- 開頭
    if not lines or lines[0].strip() != "---":
        return (False, "")

    # 找到 frontmatter 結束的 ---
    closing_idx = -1
    for i in range(1, min(len(lines), 80)):
        if lines[i].strip() == "---":
            closing_idx = i
            break

    if closing_idx == -1:
        return (False, "")

    # 從 frontmatter 行中找 description
    fm_lines = lines[1:closing_idx]
    desc_parts: List[str] = []
    in_description = False

    for line in fm_lines:
        stripped = line.strip()

        if in_description:
            # 縮排行屬於 description 多行值
            if line.startswith("  ") or line.startswith("\t"):
                desc_parts.append(stripped)
            else:
                # 遇到非縮排行，description 結束
                break
        elif stripped.startswith("description:"):
            value = stripped[len("description:"):].strip()
            # 移除可能的引號
            if value and value[0] in ('"', "'"):
                value = value.strip('"').strip("'")
            if value:
                desc_parts.append(value)
            in_description = True

    if not desc_parts:
        return (False, "")

    return (True, " ".join(desc_parts))


def main() -> int:
    """Hook 主邏輯：掃描所有 Skill description 長度。"""
    logger = setup_hook_logging("skill-description-length-check-hook")

    project_root = get_project_root()
    skills_dir = project_root / ".claude" / "skills"

    if not skills_dir.exists():
        logger.info("skills 目錄不存在，跳過檢查")
        return 0

    warnings: List[Tuple[str, int]] = []
    infos: List[Tuple[str, int]] = []
    scanned = 0

    for skill_path in sorted(skills_dir.iterdir()):
        if not skill_path.is_dir() or skill_path.name.startswith("."):
            continue

        skill_md = skill_path / "SKILL.md"
        if not skill_md.exists():
            continue

        scanned += 1
        found, description = parse_description_from_frontmatter(skill_md)
        if not found:
            continue

        char_count = len(description)
        if char_count > WARNING_THRESHOLD:
            warnings.append((skill_path.name, char_count))
        elif char_count >= INFO_THRESHOLD:
            infos.append((skill_path.name, char_count))

    logger.info(
        "掃描完成: %d 個 Skill, %d 個超長, %d 個中等",
        scanned, len(warnings), len(infos),
    )

    # 有超長 description 時輸出 warning 到 stderr
    if warnings:
        lines = ["[SkillCheck] description 長度警告"]
        for name, count in warnings:
            lines.append(
                f"  - {name}: {count} 字（超過 {WARNING_THRESHOLD} 字上限，"
                f"觸發詞可能被截斷）"
            )
        lines.append(f"  建議：縮短至 {INFO_THRESHOLD} 字以內。")
        sys.stderr.write("\n".join(lines) + "\n")

    # 中等長度 description 輸出 info 到 stderr
    if infos:
        lines = ["[SkillCheck] description 長度提醒"]
        for name, count in infos:
            lines.append(f"  - {name}: {count} 字")
        sys.stderr.write("\n".join(lines) + "\n")

    return 0


if __name__ == "__main__":
    sys.exit(run_hook_safely(main, "skill-description-length-check-hook"))
