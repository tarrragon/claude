"""skill-trigger 提醒依 skill 目錄聚合輸出（3.3.0-W1-048）。

缺陷：一次收入整個 skill（如回流 compositional-writing 與 multi-round-review）時，
commit 守衛逐檔印出相同的 skill-trigger 提醒，數十則淹沒同段其他警告。
修復：_build_warn_message（commit-stage-guard-gate 與 git-ref-transaction-content-guard
共用的輸出層）把同一 skill 目錄下 2 個以上檔案的提醒合為一則並附檔數；
findings 本身維持逐檔。
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from lib.commit_content_guards import (  # noqa: E402
    Finding,
    _build_warn_message,
    _group_skill_trigger_findings,
)

SOURCE = "framework-rule-edit-skill-trigger"
HEADER = "[header]"


def _trigger(path: str) -> Finding:
    return Finding(
        "warn",
        SOURCE,
        f"[skill-trigger] 內含 framework 規則層變更：{path}。建議確認已讀過 "
        "compositional-writing SKILL（此階段無法核實，僅提醒）。",
        path=path,
    )


def test_same_skill_multiple_files_merged_with_count():
    findings = [_trigger(f".claude/skills/compositional-writing/references/f{i}.md") for i in range(23)]
    findings += [_trigger(f".claude/skills/multi-round-review/r{i}.md") for i in range(20)]

    message = _build_warn_message(findings, HEADER)

    assert message.count("[skill-trigger]") == 2
    assert ".claude/skills/compositional-writing/ 下 23 個檔案" in message
    assert ".claude/skills/multi-round-review/ 下 20 個檔案" in message


def test_single_rule_file_still_reminded():
    """正向對照：單一規則檔變更仍逐檔印出提醒，內容不變。"""
    finding = _trigger(".claude/rules/core/quality-baseline.md")

    message = _build_warn_message([finding], HEADER)

    assert message.count("[skill-trigger]") == 1
    assert ".claude/rules/core/quality-baseline.md。" in message


def test_non_skill_framework_files_not_merged():
    """skill 目錄外的框架檔即使多個也逐檔提醒（各檔可能屬不同規則，需逐一確認）。"""
    findings = [
        _trigger(".claude/references/a.md"),
        _trigger(".claude/references/b.md"),
    ]

    grouped = _group_skill_trigger_findings(findings)

    assert grouped == findings


def test_single_file_in_skill_not_merged():
    finding = _trigger(".claude/skills/ticket/SKILL.md")

    assert _group_skill_trigger_findings([finding]) == [finding]


def test_other_sources_untouched_and_order_kept():
    other = Finding("warn", "some-other-guard", "其他警告")
    findings = [
        _trigger(".claude/skills/x/a.md"),
        other,
        _trigger(".claude/skills/x/b.md"),
    ]

    grouped = _group_skill_trigger_findings(findings)

    assert len(grouped) == 2
    assert grouped[0].source == SOURCE
    assert ".claude/skills/x/ 下 2 個檔案" in grouped[0].message
    assert grouped[1] == other


def test_findings_without_path_kept_as_is():
    """未帶 path 的既有 Finding（三欄建構）不受影響。"""
    legacy = Finding("warn", SOURCE, "舊格式訊息")

    assert _group_skill_trigger_findings([legacy, legacy]) == [legacy, legacy]
