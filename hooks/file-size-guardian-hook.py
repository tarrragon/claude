#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
File Size Guardian Hook - 過大檔案掃描

觸發時機: SessionStart
模式: 提醒為主（不阻擋操作）

掃描 .claude/ 和 src/ 目錄中的檔案行數，
找出超過閾值的檔案並輸出警告。

另量測 auto-load 集合（CLAUDE.md + rules/core/*.md + @ 引用鏈）
的 token 總量，超過預算（AUTO_LOAD_BUDGET_TOKENS）時輸出 WARNING，
防止每次事故教訓寫進自動載入層導致集合總量回彈。

核心理念：行數超標是症狀，domain 混合是病因。
回合耗盡 = 認知負擔過載的具體訊號。

來源: PC-042（單檔掃描）、1.0.0-W7-004.7（auto-load 預算量測）
"""

import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from hook_utils import setup_hook_logging, run_hook_safely, get_project_root

# 閾值設定
RULE_FILE_WARN = 200       # 規則/文件檔案警戒值
RULE_FILE_CRITICAL = 300   # 規則/文件檔案必須拆分值
CODE_FILE_WARN = 300       # 程式碼檔案警戒值
CODE_FILE_CRITICAL = 500   # 程式碼檔案必須拆分值

# Auto-load 集合 token 預算（來源: 1.0.0-W7-004.7，防止自動載入層回彈膨脹）
AUTO_LOAD_BUDGET_TOKENS = 45_000
# Token 估算係數：tokens = int(chars / CHARS_PER_TOKEN)。
# 校準依據（2026-06-12，1.0.0-W7-006）：/context Memory files 同集合實測 38.9k tokens
# vs 合計 chars 50.7k → 50.7k / 38.9k ≈ 1.30 chars/token（繁中為主集合）。
# 原值 3 為未經實測的保守假設，低估 2.3 倍（IMP-V1-001：估算係數未經實測校準即上線）。
CHARS_PER_TOKEN = 1.3
# @ 引用解析最大遞迴深度（目前 CLAUDE.md 的 @ 鏈深度為 1，遞迴一層即可）
AT_REF_MAX_DEPTH = 1
# 超標時列出的最大體量檔數
BUDGET_TOP_FILES = 3
# @ 引用 pattern：行首或空白/括號後的 @path（僅取 .md 路徑，排除 email 與程式碼裝飾器）
AT_REF_PATTERN = re.compile(r"(?:^|[\s(（])@([A-Za-z0-9_.\-/]+\.md)", re.MULTILINE)

# 掃描路徑和對應閾值
SCAN_CONFIG = [
    # (路徑 pattern, 副檔名, 警戒值, 拆分值, 類型標籤)
    (".claude/pm-rules", ".md", RULE_FILE_WARN, RULE_FILE_CRITICAL, "PM 規則"),
    (".claude/rules", ".md", RULE_FILE_WARN, RULE_FILE_CRITICAL, "品質規則"),
    (".claude/references", ".md", RULE_FILE_WARN, RULE_FILE_CRITICAL, "參考文件"),
]

# 排除的檔案名稱（不需要檢查的大檔案）
EXCLUDE_FILES = {
    "CHANGELOG.md",
    "README.md",
}


def count_lines(file_path: Path) -> int:
    """計算檔案行數"""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return sum(1 for _ in f)
    except (OSError, UnicodeDecodeError):
        return 0


def scan_directory(root: Path, rel_dir: str, ext: str, warn: int, critical: int, label: str) -> tuple[list, list]:
    """掃描目錄，回傳 (warnings, criticals)"""
    warnings = []
    criticals = []
    scan_path = root / rel_dir

    if not scan_path.exists():
        return warnings, criticals

    for file_path in scan_path.rglob(f"*{ext}"):
        if file_path.name in EXCLUDE_FILES:
            continue
        if "__pycache__" in str(file_path):
            continue

        lines = count_lines(file_path)
        rel = file_path.relative_to(root)

        if lines > critical:
            criticals.append((str(rel), lines, label))
        elif lines > warn:
            warnings.append((str(rel), lines, label))

    return warnings, criticals


def main():
    logger = setup_hook_logging("file-size-guardian")
    root = get_project_root()

    if not root:
        return

    root = Path(root)
    _report_oversized_files(root)
    report_auto_load_budget(root, logger)


def _report_oversized_files(root: Path) -> None:
    """既有單檔超標掃描：只在有超標檔案時輸出"""
    all_warnings = []
    all_criticals = []

    for rel_dir, ext, warn, critical, label in SCAN_CONFIG:
        w, c = scan_directory(root, rel_dir, ext, warn, critical, label)
        all_warnings.extend(w)
        all_criticals.extend(c)

    if not all_criticals and not all_warnings:
        return

    verbose = os.environ.get("FILE_SIZE_GUARDIAN_VERBOSE") == "1"
    log_path = root / ".claude" / "hook-logs" / "file-size-guardian.log"
    sorted_criticals = sorted(all_criticals, key=lambda x: -x[1])
    sorted_warnings = sorted(all_warnings, key=lambda x: -x[1])

    _write_full_report(log_path, sorted_criticals, sorted_warnings)

    print("============================================================")
    print("[File Size Guardian] 檔案體量掃描")
    print("============================================================")

    if verbose:
        _print_full(sorted_criticals, sorted_warnings)
    else:
        _print_summary(sorted_criticals, sorted_warnings, log_path)

    print("============================================================")


def _print_summary(criticals: list, warnings: list, log_path: Path) -> None:
    """精簡模式: 統計 + Top 3 critical"""
    print(f"超標 {len(criticals)} 個 / 警戒 {len(warnings)} 個")
    if criticals:
        print(f"\nTop 3 超標檔案 (閾值 {RULE_FILE_CRITICAL}):")
        for path, lines, label in criticals[:3]:
            print(f"  {path}: {lines} 行 ({label})")
    print(f"\n完整清單: {log_path.relative_to(log_path.parents[2])}")
    print("(設定 FILE_SIZE_GUARDIAN_VERBOSE=1 還原完整輸出)")


def _print_full(criticals: list, warnings: list) -> None:
    """Verbose 模式: 完整清單"""
    if criticals:
        print()
        print(f"[WARNING] {len(criticals)} 個檔案超過拆分閾值：")
        for path, lines, label in criticals:
            print(f"  {path}: {lines} 行 ({label}, 閾值 {RULE_FILE_CRITICAL})")
        print()
        print("  建議：分析 domain 邊界，考慮拆分為獨立檔案")
        print("  理念：行數超標是症狀，domain 混合是病因")
    if warnings:
        print()
        print(f"[INFO] {len(warnings)} 個檔案接近警戒值：")
        for path, lines, label in warnings:
            print(f"  {path}: {lines} 行 ({label}, 警戒 {RULE_FILE_WARN})")
    print()


def _write_full_report(log_path: Path, criticals: list, warnings: list) -> None:
    """完整清單寫入日誌檔（每次 SessionStart 覆蓋）"""
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, "w", encoding="utf-8") as f:
            f.write(f"# File Size Guardian Report\n")
            f.write(f"# Generated: {datetime.now().isoformat(timespec='seconds')}\n\n")
            f.write(f"## 超標檔案 ({len(criticals)})\n\n")
            for path, lines, label in criticals:
                f.write(f"- {path}: {lines} 行 ({label}, 閾值 {RULE_FILE_CRITICAL})\n")
            f.write(f"\n## 警戒檔案 ({len(warnings)})\n\n")
            for path, lines, label in warnings:
                f.write(f"- {path}: {lines} 行 ({label}, 警戒 {RULE_FILE_WARN})\n")
    except OSError:
        pass


# ============================================================
# Auto-load 預算量測（來源: 1.0.0-W7-004.7）
# ============================================================


def parse_at_references(text: str) -> list[str]:
    """解析文字中的 @ 引用路徑（行首與行內 @path.md 形式）"""
    return AT_REF_PATTERN.findall(text)


def resolve_at_references(source: Path, root: Path, depth: int = AT_REF_MAX_DEPTH) -> set[Path]:
    """解析 source 內 @ 引用為實際檔案路徑，遞迴 depth 層。

    不存在的引用路徑 graceful skip（@ 引用可能 stale，量測不因此失敗）。
    """
    resolved: set[Path] = set()
    try:
        text = source.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return resolved  # 來源檔不可讀時跳過：量測為提醒性質，不阻擋 session

    for ref in parse_at_references(text):
        ref_path = root / ref
        if not ref_path.is_file():
            continue
        if ref_path in resolved:
            continue
        resolved.add(ref_path)
        if depth > 0:
            resolved |= resolve_at_references(ref_path, root, depth - 1)
    return resolved


def collect_auto_load_files(root: Path) -> set[Path]:
    """收集 auto-load 集合：CLAUDE.md + rules/core/*.md + CLAUDE.md 的 @ 引用鏈"""
    files: set[Path] = set()

    claude_md = root / "CLAUDE.md"
    if claude_md.is_file():
        files.add(claude_md)
        files |= resolve_at_references(claude_md, root)

    core_dir = root / ".claude" / "rules" / "core"
    if core_dir.is_dir():
        files.update(p for p in core_dir.glob("*.md") if p.is_file())

    return files


def measure_auto_load_budget(root: Path) -> tuple[int, list[tuple[str, int]]]:
    """量測 auto-load 集合 token 總量。

    Returns:
        (total_tokens, [(相對路徑, tokens)]) — 清單依 tokens 由大到小排序
    """
    per_file: list[tuple[str, int]] = []
    for file_path in collect_auto_load_files(root):
        try:
            char_count = len(file_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError):
            continue  # 單檔不可讀時跳過：量測為提醒性質
        rel = str(file_path.relative_to(root))
        per_file.append((rel, int(char_count / CHARS_PER_TOKEN)))

    per_file.sort(key=lambda item: -item[1])
    total_tokens = sum(tokens for _, tokens in per_file)
    return total_tokens, per_file


def _get_budget_state_path(root: Path) -> Path:
    return root / ".claude" / "hook-logs" / "auto-load-budget-state.json"


def load_previous_budget_total(state_path: Path) -> int | None:
    """讀取上次量測總量；state 檔不存在或損壞時回傳 None（首次量測初始化路徑）"""
    try:
        data = json.loads(state_path.read_text(encoding="utf-8"))
        total = data.get("total_tokens")
        return int(total) if total is not None else None
    except (OSError, ValueError, TypeError):
        return None


def save_budget_state(state_path: Path, total_tokens: int) -> None:
    """寫入本次量測結果供下次計算差值"""
    state = {
        "total_tokens": total_tokens,
        "measured_at": datetime.now().isoformat(timespec="seconds"),
    }
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def _print_budget_report(total_tokens: int, per_file: list, previous_total: int | None) -> None:
    """輸出 Auto-load 預算區塊：預算內一行摘要；超標附 top 3 體量檔與差值"""
    budget_k = AUTO_LOAD_BUDGET_TOKENS // 1000
    print(f"[Auto-load 預算] 集合 ~{total_tokens / 1000:.1f}k / {budget_k}k tokens")

    if total_tokens <= AUTO_LOAD_BUDGET_TOKENS:
        return

    print(f"[WARNING] auto-load 集合超過預算 {budget_k}k tokens，建議收斂自動載入層")
    print(f"  Top {BUDGET_TOP_FILES} 體量檔:")
    for rel, tokens in per_file[:BUDGET_TOP_FILES]:
        print(f"    {rel}: ~{tokens / 1000:.1f}k tokens")
    if previous_total is not None:
        delta = total_tokens - previous_total
        print(f"  與上次量測差值: {delta:+d} tokens")


def report_auto_load_budget(root: Path, logger) -> None:
    """量測並輸出 Auto-load 預算區塊。

    失敗安全：量測異常時 stderr 警告 + 日誌記錄，不阻擋 session
    （quality-baseline 規則 4 雙通道）。
    """
    try:
        total_tokens, per_file = measure_auto_load_budget(root)
        state_path = _get_budget_state_path(root)
        previous_total = load_previous_budget_total(state_path)
        _print_budget_report(total_tokens, per_file, previous_total)
        save_budget_state(state_path, total_tokens)
    except Exception as exc:  # noqa: BLE001 — 失敗安全：任何量測異常皆不阻擋 session
        sys.stderr.write(f"[file-size-guardian] Auto-load 預算量測異常: {exc}\n")
        logger.error("Auto-load 預算量測異常: %s", exc, exc_info=True)


if __name__ == "__main__":
    run_hook_safely(main, "file-size-guardian")
