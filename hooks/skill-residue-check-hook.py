#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""SessionStart: 回報 skill 內殘留的他專案痕跡。

本 hook 只負責可見性，不阻擋任何操作——阻擋層在 push 路徑
（`skill-sync-push-residue-gate-hook.py` 與 `sync-claude-push.py`）。
兩者分工的理由：session 開場的警告若能阻擋，會在每次啟動時要求處理與當下
工作無關的存量債；而只有警告、沒有 push gate，則等於把「有沒有看到開場輸出」
當成防線，那不是防線。

輸出只列 blocking 級（引用的路徑或腳本不存在）。advisory 級的
FOREIGN_TICKET_ID 存量達百項，列進開場輸出會淹沒其餘 SessionStart hook 的
訊息，需要時以 `--all` 手動執行本檔查看。
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from lib import setup_hook_logging, run_hook_safely  # noqa: E402
from skill_residue_detector import (  # noqa: E402
    blocking_only,
    format_report,
    scan_all,
)

SEPARATOR = "=" * 60


def project_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


def main() -> int:
    logger = setup_hook_logging("skill-residue-check-hook")
    show_all = "--all" in sys.argv

    root = project_root()
    findings = scan_all(root / ".claude" / "skills", root)
    blocking = blocking_only(findings)
    advisory_count = sum(len(v) for v in findings.values()) - sum(
        len(v) for v in blocking.values()
    )

    if not blocking and not show_all:
        logger.info("skill 殘留檢查通過（advisory %d 項）", advisory_count)
        print(SEPARATOR)
        print("[Skill Residue] 無 blocking 級殘留")
        if advisory_count:
            print(f"  advisory（他專案 ticket ID）{advisory_count} 項，push 不受阻擋")
        print(SEPARATOR)
        return 0

    target = findings if show_all else blocking
    total = sum(len(v) for v in target.values())
    logger.warning("偵測到 skill 殘留 %d 項", total)

    print(SEPARATOR)
    print(f"[Skill Residue] 偵測到 {total} 項他專案痕跡（{len(target)} 個 skill）")
    print()
    for line in format_report(target):
        print(line)
    print()
    print("這些引用指向本專案不存在的檔案。push 至 canonical 前需修正，")
    print("或於該行加 `skill-residue-exempt: <理由>` 標記說明為示意路徑。")
    if not show_all and advisory_count:
        print(f"另有 advisory {advisory_count} 項（他專案 ticket ID），以 --all 查看。")
    print(SEPARATOR)
    return 0


if __name__ == "__main__":
    sys.exit(run_hook_safely(main, "skill-residue-check-hook"))
