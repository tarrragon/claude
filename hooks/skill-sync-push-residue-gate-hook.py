#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""PreToolUse: 阻擋帶他專案殘留的 skill 被 push 至 canonical。

攔在 Bash 工具層而非改 skill-sync 內部：skill-sync 是零框架依賴的獨立 uv
套件，讓它 import `.claude/scripts/` 會使其不再能單獨安裝於沒有本框架的環境。
攔截層放在框架這一側，兩者的邊界因此不動。

只擋 blocking 級（引用的路徑或腳本不存在）。advisory 級的他專案 ticket ID
存量上百，擋下來的結果是每次 push 都要 --force，而習慣性加 --force 會連帶
讓 blocking 級的真訊號失去效力。

旁路：命令自帶 `--force` 時放行——push 本身已用該旗標表達「我知道自己在做
什麼」，再要一個獨立旗標只是增加記憶負擔。
"""

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from lib import setup_hook_logging, run_hook_safely  # noqa: E402
from skill_residue_detector import (  # noqa: E402
    blocking_only,
    format_report,
    scan_skill,
)

# `skill-sync push <name>`，允許中間夾雜旗標
_PUSH_RE = re.compile(r"skill-sync\s+(?:[-\w]+\s+)*?push\s+(?:-\S+\s+)*([\w.-]+)")


def project_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


def extract_target(command: str) -> str | None:
    match = _PUSH_RE.search(command)
    return match.group(1) if match else None


def main() -> int:
    logger = setup_hook_logging("skill-sync-push-residue-gate-hook")

    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError) as exc:
        logger.warning("無法解析 stdin（%s），放行", exc)
        return 0

    command = payload.get("tool_input", {}).get("command", "")
    if not command or "skill-sync" not in command:
        return 0

    target = extract_target(command)
    if not target:
        return 0

    if "--force" in command:
        logger.info("push %s 帶 --force，略過殘留檢查", target)
        return 0

    root = project_root()
    skill_dir = root / ".claude" / "skills" / target
    if not skill_dir.is_dir():
        return 0

    findings = blocking_only({target: scan_skill(skill_dir, root)})
    if not findings:
        logger.info("push %s 殘留檢查通過", target)
        return 0

    total = sum(len(v) for v in findings.values())
    logger.warning("阻擋 push %s：%d 項殘留", target, total)

    sys.stderr.write(
        f"\n[Skill Residue Gate] 阻擋 push '{target}'：{total} 項引用指向本專案不存在的檔案\n\n"
    )
    for line in format_report(findings):
        sys.stderr.write(line + "\n")
    sys.stderr.write(
        "\n這些內容推上 canonical 後會被其他 consumer 取走，把讀者導向不存在的檔案。\n"
        "處理方式擇一：\n"
        "  1. 修正引用，或改為不指名具體路徑的描述性敘述\n"
        "  2. 確屬示意路徑時，於該行加 `skill-residue-exempt: <理由>` 標記\n"
        "  3. 確知無妨時，於 push 命令加 --force 旁路\n"
    )
    return 2


if __name__ == "__main__":
    sys.exit(run_hook_safely(main, "skill-sync-push-residue-gate-hook"))
