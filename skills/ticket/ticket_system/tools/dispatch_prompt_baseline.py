#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""
派發 Prompt 補洞基線量測腳本。

用途：
  重跑「派發 prompt 補洞現象」基線量測，重現對應分析票 Problem Analysis
  中的統計表（骨架行 vs 非骨架行、非骨架文字對票 md 的 5-gram 覆蓋率）。
  數字會因 transcript 增長而變動，屬預期行為（非迴歸）。

資料來源：
  - session transcript：~/.claude/projects/<project-slug>/*.jsonl
    （Agent/Task tool_use 的 input.prompt 全文；hook 日誌
    agent-dispatch.jsonl 僅存 500 字 preview，不可作全文來源）
  - 對應票 md：docs/work-logs/v{version}/**/tickets/{ticket_id}.md

方法：
  1. 掃描 transcript，抽取所有 Agent/Task tool_use 的 prompt 全文與
     對應 ticket_id（用 `Ticket: <id>` 這行解析）。
  2. 依骨架關鍵字（見 SKELETON_PATTERNS）逐行分類為骨架行/非骨架行。
  3. 非骨架文字去空白後切 5-gram，與該票 md 全文的 5-gram 集合比對，
     算覆蓋率（高 = 票內已有 = 重述；低 = 票內沒有 = 補洞）。
  4. 輸出統計表（總數、行數分位數、覆蓋率分位數、重述/混合/補洞分佈、
     非骨架行分類計數）。

使用：
  uv run .claude/skills/ticket/ticket_system/tools/dispatch_prompt_baseline.py
  可加 --project-slug 覆蓋預設專案目錄、--since YYYY-MM-DD 限制時間範圍。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from statistics import median

REPO_ROOT = Path(__file__).resolve().parents[5]
DEFAULT_PROJECT_SLUG = "-Users-mac-eric-project-flutter-balance"
CLAUDE_PROJECTS_DIR = Path.home() / ".claude" / "projects"

# 骨架行判準：對應 agent-dispatch-template.md 權威版固定段落的關鍵字。
# 命中任一 pattern 視為骨架行（重述模板結構），不計入非骨架文字。
SKELETON_PATTERNS = [
    re.compile(r"^Ticket[:：]"),
    re.compile(r"^##\s*任務"),
    re.compile(r"讀取\s*[Tt]icket"),
    re.compile(r"認領[:：]?\s*`?ticket track claim"),
    re.compile(r"依\s*Context Bundle"),
    re.compile(r"衝突.*停手|停手.*上報|NeedsContext"),
    re.compile(r"遇阻.*回報|禁繞過\s*Hook"),
    re.compile(r"收尾[:：]"),
]

# 非骨架行的次分類，供輸出「類別 x 票內已有/不存在」交叉表。
LINE_CATEGORY_PATTERNS = [
    ("檔案路徑", re.compile(r"\.(py|dart|md|yaml|yml|json)\b|/[\w-]+/[\w./-]+")),
    ("commit 歸屬 / staging", re.compile(r"git add|git commit|staging|歸屬")),
    ("禁令約束", re.compile(r"禁止|不可|不得|禁繞")),
    ("收尾協議", re.compile(r"set-acceptance|append-log|complete\b|收尾")),
    ("驗收 / AC", re.compile(r"驗收|acceptance|AC\b")),
]


def is_skeleton_line(line: str) -> bool:
    return any(p.search(line) for p in SKELETON_PATTERNS)


def categorize_line(line: str) -> str:
    for name, pattern in LINE_CATEGORY_PATTERNS:
        if pattern.search(line):
            return name
    return "其他（任務框架、步驟、審查問題）"


def ngrams(text: str, n: int = 5) -> set:
    tokens = re.sub(r"\s+", "", text)
    if len(tokens) < n:
        return {tokens} if tokens else set()
    return {tokens[i : i + n] for i in range(len(tokens) - n + 1)}


def find_ticket_body(ticket_id: str) -> str | None:
    matches = list((REPO_ROOT / "docs" / "work-logs").rglob(f"{ticket_id}.md"))
    if not matches:
        return None
    return matches[0].read_text(encoding="utf-8", errors="ignore")


TICKET_ID_PATTERN = re.compile(r"\d+\.\d+\.\d+-W\d+-\d+(?:\.\d+)?")


def extract_ticket_id(prompt: str) -> tuple[str | None, str | None]:
    """回傳 (ticket_id, matched_by)。matched_by 為 'header' 或 'fallback'。

    首行優先比對 `Ticket: <id>` 樣式；找不到時回退搜尋 prompt 任意位置
    符合 ticket ID 格式的字串，避免非骨架派發被排除於量測母體外。
    """
    m = re.search(r"Ticket[:：]\s*`?([\w.\-]+)`?", prompt)
    if m:
        return m.group(1), "header"
    m = TICKET_ID_PATTERN.search(prompt)
    if m:
        return m.group(0), "fallback"
    return None, None


def iter_agent_prompts(project_slug: str, since: str | None):
    project_dir = CLAUDE_PROJECTS_DIR / project_slug
    if not project_dir.exists():
        return
    for jsonl_path in sorted(project_dir.glob("*.jsonl")):
        try:
            lines = jsonl_path.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            continue
        for raw in lines:
            raw = raw.strip()
            if not raw:
                continue
            try:
                record = json.loads(raw)
            except json.JSONDecodeError:
                continue
            ts = record.get("timestamp", "")
            if since and ts and ts[:10] < since:
                continue
            message = record.get("message", {})
            content = message.get("content", [])
            if not isinstance(content, list):
                continue
            for block in content:
                if not isinstance(block, dict):
                    continue
                if block.get("type") != "tool_use":
                    continue
                if block.get("name") not in ("Agent", "Task"):
                    continue
                prompt = block.get("input", {}).get("prompt", "")
                if prompt:
                    yield prompt


def percentile(values: list, pct: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    k = (len(s) - 1) * pct
    f = int(k)
    c = min(f + 1, len(s) - 1)
    if f == c:
        return s[f]
    return s[f] + (s[c] - s[f]) * (k - f)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-slug", default=DEFAULT_PROJECT_SLUG)
    parser.add_argument("--since", default=None, help="YYYY-MM-DD，僅含此日期後的紀錄")
    args = parser.parse_args()

    total = 0
    matched_ticket = 0
    matched_by_header = 0
    matched_by_fallback = 0
    total_lines = []
    non_skeleton_lines = []
    coverage_values = []
    bucket_counts = {"重述主導(>=0.6)": 0, "混合": 0, "補洞主導(<0.3)": 0}
    category_counts = {name: {"absent": 0, "present": 0} for name, _ in LINE_CATEGORY_PATTERNS}
    category_counts["其他（任務框架、步驟、審查問題）"] = {"absent": 0, "present": 0}

    for prompt in iter_agent_prompts(args.project_slug, args.since):
        total += 1
        lines = [ln for ln in prompt.splitlines() if ln.strip()]
        total_lines.append(len(lines))
        non_skel = [ln for ln in lines if not is_skeleton_line(ln)]
        non_skeleton_lines.append(len(non_skel))

        ticket_id, matched_by = extract_ticket_id(prompt)
        body = find_ticket_body(ticket_id) if ticket_id else None
        if body is None:
            continue
        matched_ticket += 1
        if matched_by == "header":
            matched_by_header += 1
        elif matched_by == "fallback":
            matched_by_fallback += 1
        body_ngrams = ngrams(body)

        non_skel_text = "\n".join(non_skel)
        prompt_ngrams = ngrams(non_skel_text)
        if prompt_ngrams:
            covered = len(prompt_ngrams & body_ngrams) / len(prompt_ngrams)
        else:
            covered = 1.0
        coverage_values.append(covered)
        if covered >= 0.6:
            bucket_counts["重述主導(>=0.6)"] += 1
        elif covered < 0.3:
            bucket_counts["補洞主導(<0.3)"] += 1
        else:
            bucket_counts["混合"] += 1

        for ln in non_skel:
            cat = categorize_line(ln)
            present = bool(ngrams(ln) & body_ngrams)
            category_counts.setdefault(cat, {"absent": 0, "present": 0})
            category_counts[cat]["present" if present else "absent"] += 1

    print(f"派發總數: {total}")
    print(
        f"可對應票檔: {matched_ticket} "
        f"(matched_by_header={matched_by_header}, matched_by_fallback={matched_by_fallback})"
    )
    if total_lines:
        print(
            f"prompt 行數 median/p90/max: "
            f"{median(total_lines):.0f}/{percentile(total_lines, 0.9):.0f}/{max(total_lines)}"
        )
    if non_skeleton_lines:
        over10 = sum(1 for n in non_skeleton_lines if n > 10) / len(non_skeleton_lines)
        print(
            f"非骨架行 median/p90; >10行比例: "
            f"{median(non_skeleton_lines):.0f}/{percentile(non_skeleton_lines, 0.9):.0f}; {over10:.0%}"
        )
    if coverage_values:
        print(
            f"非骨架文字覆蓋率 median (p25-p75): "
            f"{median(coverage_values):.2f} "
            f"({percentile(coverage_values, 0.25):.2f}-{percentile(coverage_values, 0.75):.2f})"
        )
    print(f"重述/混合/補洞分佈: {bucket_counts}")
    print("非骨架行分類（票內不存在 / 票內已有）：")
    for cat, counts in category_counts.items():
        print(f"  {cat}: {counts['absent']} / {counts['present']}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
