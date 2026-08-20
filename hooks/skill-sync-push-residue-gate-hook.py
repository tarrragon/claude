#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml"]
# ///
"""PreToolUse: 阻擋帶他專案殘留的 skill 被 push 至 canonical，以及阻擋
private skill 被 push 至任何遠端。

攔在 Bash 工具層而非改 skill-sync 內部：skill-sync 是零框架依賴的獨立 uv
套件，讓它 import `.claude/scripts/` 或 `.claude/lib/` 會使其不再能單獨安裝
於沒有本框架的環境。攔截層放在框架這一側，兩者的邊界因此不動。

只擋 blocking 級（引用的路徑或腳本不存在）。advisory 級的他專案 ticket ID
存量上百，擋下來的結果是每次 push 都要 --force，而習慣性加 --force 會連帶
讓 blocking 級的真訊號失去效力。

旁路：命令自帶 `--force` 時，殘留檢查放行——push 本身已用該旗標表達「我
知道自己在做什麼」，再要一個獨立旗標只是增加記憶負擔。

private skill 守衛：`.claude/sync-skills.yaml` 的 `private` 清單宣告該
skill 設計上不進任何遠端（框架 repo 與 skill 發佈庫皆不進）。skill-sync
套件的 push 命令對此清單全無感知——實作全文無 private 判斷，若不在 Bash
工具層擋下，drift report 對 private skill 的「遠端無記錄」誤報會誘導使用者
把專案特化 skill 實際推上公開發佈庫，這是比誤報本身更嚴重的實害路徑。

裁示：private 守衛**不接受 `--force` 旁路**（無條件 deny）。殘留檢查的
旁路理由（「push 本身已表達知情」）不自動適用於此——殘留檢查擋的是可由
使用者評估風險後自行放行的「內容品質問題」；private 守衛擋的是「設計上
本不該存在的遠端副本」，一旦推送即產生無法靠旗標撤回的外部可見狀態（公開
repo 的歷史紀錄），唯一正確的解除方式是先把該 skill 從 `sync-skills.yaml`
的 private 清單移除，而非在單次呼叫加旗標繞過。故本守衛判斷順序排在
`--force` 檢查之前，且不讀取該旗標。
"""

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from lib import setup_hook_logging, run_hook_safely  # noqa: E402
from lib.sync_exclude_manifest import load_sync_skills_config  # noqa: E402
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


def is_private_skill(target: str, root: Path) -> bool:
    """判斷 target 是否命中 sync-skills.yaml 的 private 清單。

    獨立函式以利測試 monkeypatch，並讓 main() 的判斷順序清楚可讀。
    """
    config = load_sync_skills_config(root / ".claude")
    return target in config.get("private", [])


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

    root = project_root()

    # private 守衛先於 --force 判斷：無條件 deny，不讀取該旗標（見檔頭裁示）。
    if is_private_skill(target, root):
        logger.warning("阻擋 push %s：private skill，設計上不推送任何遠端", target)
        sys.stderr.write(
            f"\n[Skill Residue Gate] 阻擋 push '{target}'：此 skill 為專案特化 private "
            "skill，設計上不推送至任何遠端（.claude/sync-skills.yaml 的 private 清單）。\n"
            "此檢查不接受 --force 旁路。若確實要推送，須先從 sync-skills.yaml 的 private\n"
            "清單移除該 skill，而非在單次呼叫加旗標繞過。\n"
        )
        return 2

    if "--force" in command:
        logger.info("push %s 帶 --force，略過殘留檢查", target)
        return 0

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
