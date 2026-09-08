#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
Skill Body Size Check Hook

掃描所有 .claude/skills/*/SKILL.md，量測全檔（含 frontmatter）的估算 token
數與行數，超過 skill-design-guide 第 2 層預算者輸出警告。

門檻對象是 SKILL.md 全檔（含 frontmatter），非僅 body：frontmatter 雖已常駐
第 1 層 system prompt，但觸發後全檔仍會原樣再讀入 context 一次，此成本計入
第 2 層預算（見 skill-design-guide/SKILL.md〈Progressive Disclosure〉）。

估算公式（分段加總，非全檔比例內插）：
    tokens = round(ascii_chars / 4 + non_ascii_chars / 1.3)
- ASCII 比例 4 字元/token：取寬鬆側，無實測，一般 BPE 分詞落在 3-4
- 非 ASCII 比例 1.3 字元/token：沿用 file-size-guardian-hook.py 的
  CHARS_PER_TOKEN（2026-06-12 以 /context 實測校準）

行數門檻對應官方 "Keep SKILL.md body under 500 lines"（best practices），
兩個門檻各自獨立判定，任一超標即列入警告——行數合規不代表 token 合規。

事件：SessionStart
退出碼：0（純提醒，不阻擋）
"""

import sys
from pathlib import Path
from typing import List, Tuple

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))
from lib import setup_hook_logging, run_hook_safely, get_project_root

# 第 2 層預算門檻（skill-design-guide/SKILL.md〈Progressive Disclosure — 三層載入〉）
TOKEN_THRESHOLD = 5_000
LINE_THRESHOLD = 500

# 分段估算係數
ASCII_CHARS_PER_TOKEN = 4
NON_ASCII_CHARS_PER_TOKEN = 1.3

# 警告輸出列出的最大體量檔數
TOP_N = 5


def estimate_tokens(text: str) -> int:
    """分段估算 token 數：ASCII 與非 ASCII 字元各自換算後加總。

    分段法解掉單一字元門檻的兩類誤判（純 ASCII 檔低估、混合內容判不出結
    論），見 skill-design-guide/SKILL.md〈Progressive Disclosure〉。
    """
    ascii_chars = sum(1 for c in text if ord(c) < 128)
    non_ascii_chars = len(text) - ascii_chars
    return round(
        ascii_chars / ASCII_CHARS_PER_TOKEN
        + non_ascii_chars / NON_ASCII_CHARS_PER_TOKEN
    )


def count_lines(text: str) -> int:
    """計算行數，與 `wc -l` 語意一致（計算換行符數）。"""
    return text.count("\n")


def scan_skills(
    skills_dir: Path,
) -> Tuple[List[Tuple[str, int]], List[Tuple[str, int]]]:
    """掃描 skills_dir 下所有 SKILL.md，回傳 (超 token 門檻清單, 超行數門檻清單)。

    每個清單元素為 (skill 名稱, 量測值)，依量測值由大到小排序。
    跳過非目錄項、隱藏目錄（`.` 開頭）、無 SKILL.md 的目錄。
    """
    over_token: List[Tuple[str, int]] = []
    over_lines: List[Tuple[str, int]] = []

    if not skills_dir.exists():
        return over_token, over_lines

    for skill_path in sorted(skills_dir.iterdir()):
        if not skill_path.is_dir() or skill_path.name.startswith("."):
            continue

        skill_md = skill_path / "SKILL.md"
        if not skill_md.exists():
            continue

        try:
            content = skill_md.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue

        tokens = estimate_tokens(content)
        lines = count_lines(content)

        if tokens > TOKEN_THRESHOLD:
            over_token.append((skill_path.name, tokens))
        if lines > LINE_THRESHOLD:
            over_lines.append((skill_path.name, lines))

    over_token.sort(key=lambda item: -item[1])
    over_lines.sort(key=lambda item: -item[1])
    return over_token, over_lines


def _print_report(over_token: List[Tuple[str, int]], over_lines: List[Tuple[str, int]]) -> None:
    """輸出警告到 stderr（純提醒，不阻擋）。"""
    if not over_token and not over_lines:
        return

    lines_out = ["[SkillBodySize] SKILL.md 體量超標（第 2 層預算）"]

    if over_token:
        lines_out.append(f"  Token 超標（門檻 {TOKEN_THRESHOLD}）: {len(over_token)} 支")
        for name, tokens in over_token[:TOP_N]:
            lines_out.append(f"    - {name}: ~{tokens} tokens")

    if over_lines:
        lines_out.append(f"  行數超標（門檻 {LINE_THRESHOLD}）: {len(over_lines)} 支")
        for name, count in over_lines[:TOP_N]:
            lines_out.append(f"    - {name}: {count} 行")

    lines_out.append("  建議：見 skill-design-guide/SKILL.md〈Progressive Disclosure〉外移判準")
    sys.stderr.write("\n".join(lines_out) + "\n")


def main() -> int:
    """Hook 主邏輯：掃描所有 Skill 的 SKILL.md 體量。"""
    logger = setup_hook_logging("skill-body-size-check-hook")

    project_root = get_project_root()
    if not project_root:
        return 0

    skills_dir = Path(project_root) / ".claude" / "skills"
    if not skills_dir.exists():
        logger.info("skills 目錄不存在，跳過檢查")
        return 0

    over_token, over_lines = scan_skills(skills_dir)

    logger.info(
        "掃描完成: %d 支 token 超標, %d 支行數超標",
        len(over_token), len(over_lines),
    )

    _print_report(over_token, over_lines)

    return 0


if __name__ == "__main__":
    sys.exit(run_hook_safely(main, "skill-body-size-check-hook"))
