#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml"]
# ///
"""
Skill Description Length Check Hook

掃描所有 .claude/skills/*/SKILL.md 的 YAML frontmatter description 欄位長度。
超過 250 字的輸出 warning，協助維持 description 精簡以避免觸發詞截斷。

執法升級：
  本檔同時扮演兩個角色，依 stdin 是否帶 `tool_name` 判斷：
    - 無 tool_name（SessionStart 等資訊性事件）→ 沿用既有全量掃描，
      純提醒不阻擋（exit 0）。
    - tool_name 為 Edit/Write/MultiEdit 且目標路徑是 SKILL.md
      → 執法層：重建編輯後內容，超過門檻時依 baseline 檔判斷是否阻擋。

  baseline 檔（.claude/hooks/skill-description-baseline.json）記錄既有
  超標存量，避免升級執法時一次全部變紅。阻擋條件：
    - description 超過 WARNING_THRESHOLD，且
    - 該 skill 不在 baseline（新增違規），或
    - 該 skill 在 baseline 但目前長度已超過 baseline 記錄值（存量惡化）
  baseline 檔缺失或格式錯誤 → 降級為全 warning，不誤擋（fail-open）。
  baseline 檔本身透過 `--generate-baseline` CLI 模式重新產生，內容來自
  實際掃描結果，不寫死於程式碼。

事件：SessionStart（掃描）+ PreToolUse Edit/Write/MultiEdit（執法）
退出碼：SessionStart 恆 0；PreToolUse 命中阻擋條件時 2，否則 0
"""

import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))
from lib import setup_hook_logging, run_hook_safely, get_project_root, read_json_from_stdin
from lib.skill_case_guard import warn_skill_md_case_mismatch

# description 長度閾值（字元數）
WARNING_THRESHOLD = 250
INFO_THRESHOLD = 100

# SKILL.md 路徑樣式：取出 skill 名稱（最後一段 .claude/skills/<name>/SKILL.md）
SKILL_MD_PATH_PATTERN = re.compile(r"(?:^|/)\.claude/skills/([^/]+)/SKILL\.md$")

EXIT_ALLOW = 0
EXIT_BLOCK = 2


def parse_description_from_text(content: str) -> Tuple[bool, str]:
    """
    從 SKILL.md 檔案內容（字串）解析 YAML frontmatter 中的 description 欄位。

    需求：description 可能是單行或多行（YAML block scalar）。
    不使用外部 YAML 套件，手動解析以維持零依賴。

    Returns:
        (found, description_text)
    """
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


def parse_description_from_frontmatter(skill_md_path: Path) -> Tuple[bool, str]:
    """從 SKILL.md 檔案路徑讀取內容並解析 description 欄位（parse_description_from_text 的檔案版包裝）。"""
    try:
        content = skill_md_path.read_text(encoding="utf-8")
    except Exception:
        return (False, "")
    return parse_description_from_text(content)


# ============================================================
# SessionStart 全量掃描（既有行為，不變）
# ============================================================


def _run_session_scan(logger) -> int:
    """Hook 資訊性入口：掃描所有 Skill description 長度，純提醒不阻擋。"""
    project_root = get_project_root()
    skills_dir = project_root / ".claude" / "skills"

    if not skills_dir.exists():
        logger.info("skills 目錄不存在，跳過檢查")
        return EXIT_ALLOW

    case_warnings = warn_skill_md_case_mismatch(skills_dir)
    if case_warnings:
        lines = ["[SkillCheck] skill.md 大小寫警告"]
        for w in case_warnings:
            lines.append(f"  - {w}")
        sys.stderr.write("\n".join(lines) + "\n")
        logger.warning("skill.md 大小寫不符: %d 項", len(case_warnings))

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

    return EXIT_ALLOW


# ============================================================
# PreToolUse 執法層
# ============================================================


def extract_skill_name(file_path: str) -> Optional[str]:
    """從編輯目標路徑取出 skill 名稱；非 .claude/skills/<name>/SKILL.md 形態回傳 None。"""
    if not file_path:
        return None
    normalized = file_path.replace("\\", "/")
    match = SKILL_MD_PATH_PATTERN.search(normalized)
    return match.group(1) if match else None


def _read_file_text(file_path: str) -> str:
    """讀取檔案編輯前的磁碟內容；不存在或無法解碼時回傳空字串（視為新檔）。"""
    try:
        return Path(file_path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""


def reconstruct_post_text(tool_name: str, tool_input: dict, file_path: str) -> str:
    """套用本次 Edit/Write/MultiEdit 重建編輯後內容。

    重建失敗（old_string 找不到、欄位型別不符）時保守回退為編輯前內容——
    寧可用舊內容誤放，也不因重建失敗而阻擋與本次操作無關的判斷。
    """
    pre_text = _read_file_text(file_path)

    if tool_name == "Write":
        content = tool_input.get("content")
        return content if isinstance(content, str) else pre_text

    if tool_name == "Edit":
        old_string = tool_input.get("old_string")
        new_string = tool_input.get("new_string")
        if not isinstance(old_string, str) or not isinstance(new_string, str):
            return pre_text
        if old_string and old_string in pre_text:
            if tool_input.get("replace_all"):
                return pre_text.replace(old_string, new_string)
            return pre_text.replace(old_string, new_string, 1)
        return pre_text

    if tool_name == "MultiEdit":
        edits = tool_input.get("edits")
        if not isinstance(edits, list):
            return pre_text
        post_text = pre_text
        for edit in edits:
            if not isinstance(edit, dict):
                continue
            old_string = edit.get("old_string")
            new_string = edit.get("new_string")
            if not isinstance(old_string, str) or not isinstance(new_string, str):
                continue
            if old_string and old_string in post_text:
                if edit.get("replace_all"):
                    post_text = post_text.replace(old_string, new_string)
                else:
                    post_text = post_text.replace(old_string, new_string, 1)
        return post_text

    return pre_text


def get_baseline_path(project_root: Path) -> Path:
    """baseline 檔固定位置：.claude/hooks/skill-description-baseline.json。"""
    return project_root / ".claude" / "hooks" / "skill-description-baseline.json"


def load_baseline(baseline_path: Path) -> Optional[Dict[str, int]]:
    """讀取 baseline 檔的 skills 對照表。

    缺失、非 JSON、或 `skills` 欄位不是物件 → 回傳 None（呼叫端須降級為
    全 warning，不阻擋，fail-open）。單一 entry 值無法轉 int 時僅跳過該筆，
    不影響 baseline 其餘記錄的有效性。
    """
    try:
        data = json.loads(baseline_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    skills = data.get("skills")
    if not isinstance(skills, dict):
        return None
    result: Dict[str, int] = {}
    for name, length in skills.items():
        try:
            result[name] = int(length)
        except (TypeError, ValueError):
            continue
    return result


def build_block_message(
    skill_name: str, char_count: int, baseline_count: Optional[int]
) -> str:
    """組合阻擋訊息：含現值、門檻/基準差，以及處置建議。"""
    if baseline_count is None:
        detail = (
            f"目前 {char_count} 字，超過門檻 {WARNING_THRESHOLD} 字 "
            f"（超出 {char_count - WARNING_THRESHOLD} 字，非既有 baseline 存量）"
        )
    else:
        detail = (
            f"目前 {char_count} 字，超過 baseline 記錄值 {baseline_count} 字 "
            f"（超出 {char_count - baseline_count} 字，既有存量變得更長）"
        )
    return (
        f"[BLOCKED][skill-description-length-check] 本次操作已被阻擋（exit 2）："
        f"{skill_name}\n"
        f"  - {detail}\n"
        f"處置：縮短 description 至 {WARNING_THRESHOLD} 字以內（建議 "
        f"{INFO_THRESHOLD} 字以內）。若此為既有 baseline 存量的合理調整，"
        f"需先執行 `uv run .claude/hooks/skill-description-length-check-hook.py "
        f"--generate-baseline` 重新產生 baseline 檔再重試。"
    )


def build_baseline_missing_warning(
    skill_name: str, char_count: int, baseline_path: Path
) -> str:
    """組合 baseline 缺失時的降級警告訊息（不阻擋）。"""
    return (
        f"[SkillCheck][baseline-missing] description 長度警告（未阻擋，baseline "
        f"檔缺失已降級為 warning）：\n"
        f"  - {skill_name}: {char_count} 字（超過 {WARNING_THRESHOLD} 字上限）\n"
        f"  baseline 檔缺失或格式錯誤：{baseline_path}\n"
        f"  建議：執行 `uv run .claude/hooks/skill-description-length-check-hook.py "
        f"--generate-baseline` 重新產生。"
    )


def _run_pretooluse_enforcement(logger, input_data: dict) -> int:
    """PreToolUse 執法入口：Edit/Write/MultiEdit 目標為 SKILL.md 時檢查長度。"""
    tool_name = input_data.get("tool_name", "")
    if tool_name not in ("Edit", "Write", "MultiEdit"):
        return EXIT_ALLOW

    tool_input = input_data.get("tool_input") or {}
    file_path = tool_input.get("file_path", "")

    skill_name = extract_skill_name(file_path)
    if skill_name is None:
        logger.debug("非 SKILL.md 路徑，跳過執法檢查: %s", file_path)
        return EXIT_ALLOW

    post_text = reconstruct_post_text(tool_name, tool_input, file_path)
    found, description = parse_description_from_text(post_text)
    if not found:
        logger.debug("編輯後內容找不到 description 欄位，跳過: %s", skill_name)
        return EXIT_ALLOW

    char_count = len(description)
    if char_count <= WARNING_THRESHOLD:
        return EXIT_ALLOW

    project_root = get_project_root()
    baseline_path = get_baseline_path(project_root)
    baseline = load_baseline(baseline_path)

    if baseline is None:
        sys.stderr.write(
            build_baseline_missing_warning(skill_name, char_count, baseline_path) + "\n"
        )
        logger.warning(
            "baseline 缺失，降級為 warning：skill=%s count=%d", skill_name, char_count
        )
        return EXIT_ALLOW

    baseline_count = baseline.get(skill_name)
    if baseline_count is not None and char_count <= baseline_count:
        logger.info(
            "既有 baseline 存量未惡化，放行：skill=%s count=%d baseline=%d",
            skill_name, char_count, baseline_count,
        )
        return EXIT_ALLOW

    sys.stderr.write(build_block_message(skill_name, char_count, baseline_count) + "\n")
    logger.warning(
        "阻擋 description 超標：skill=%s count=%d baseline=%s",
        skill_name, char_count, baseline_count,
    )
    return EXIT_BLOCK


# ============================================================
# baseline 產生 CLI（一次性工具，不在 hook 執行路徑中呼叫）
# ============================================================


def _cli_generate_baseline() -> int:
    """掃描目前所有 skill，將超過門檻者的現值寫入 baseline 檔。

    內容完全來自實際掃描結果，不寫死於程式碼；供啟用執法前建立初始
    baseline，或既有存量合理調整後重新產生。
    """
    project_root = get_project_root()
    skills_dir = project_root / ".claude" / "skills"
    skills: Dict[str, int] = {}

    for skill_path in sorted(skills_dir.iterdir()):
        if not skill_path.is_dir() or skill_path.name.startswith("."):
            continue
        skill_md = skill_path / "SKILL.md"
        if not skill_md.exists():
            continue
        found, description = parse_description_from_frontmatter(skill_md)
        if not found:
            continue
        char_count = len(description)
        if char_count > WARNING_THRESHOLD:
            skills[skill_path.name] = char_count

    baseline_path = get_baseline_path(project_root)
    baseline_path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "threshold": WARNING_THRESHOLD,
        "skills": dict(sorted(skills.items())),
    }
    baseline_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"[baseline] 已寫入 {len(skills)} 筆超標記錄至 {baseline_path}")
    return 0


def main() -> int:
    """Hook 主入口：依 stdin 是否帶 tool_name 分派 SessionStart 掃描或 PreToolUse 執法。"""
    logger = setup_hook_logging("skill-description-length-check-hook")

    input_data = read_json_from_stdin(logger) or {}
    tool_name = input_data.get("tool_name", "")

    if tool_name in ("Edit", "Write", "MultiEdit"):
        return _run_pretooluse_enforcement(logger, input_data)

    return _run_session_scan(logger)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--generate-baseline":
        sys.exit(_cli_generate_baseline())
    sys.exit(run_hook_safely(main, "skill-description-length-check-hook"))
