#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.9"
# dependencies = ["pyyaml"]
# ///
"""
Skill Banned Term Scan Hook

掃描 `.claude/skills/` 內文是否誤用 language-constraints.md 規則 2 列出的
禁用詞（散文層 use），偵測 skill-sync pull 造成的用語回歸。

核心設計約束——use vs mention 判別：
- use（真違規）：散文中直接使用禁用詞，例如「這份文檔說明了流程」
- mention（合法）：禁用詞作為 grep pattern 樣本、地區用語對照表樣本，
  例如 `rg "集群|默認|質量|視頻"` 或術語卡「默認 / 預設」對照

無差別掃描會對這類 mention 報 WARNING，一次誤報就足以讓維護者忽略此訊號。
豁免機制刻意不採「行號」——skill-sync pull 會使行號漂移，行號豁免會靜默
保護到錯的內容。改採四種豁免管道：

1. inline code span（`` `...` ``）：banned term 落在反引號內即豁免
2. fenced code block（``` ... ```）：整段程式碼區塊內豁免
3. 檔案級白名單（FILE_LEVEL_ALLOWLIST）：整檔豁免（如地區用語對照表本體）
4. inline marker（`<!-- banned-term-exempt: 理由 -->`）：只豁免同一行

範圍排除：規則 2 的「優化」有明文語境例外（「程式碼品質上下文可用優化」），
無法機械判別語境，本 hook 不掃描此詞。「智能」/「軟件」/「硬件」/「信息」
現行 skills 內容零命中，隨主要 5 詞一併納入掃描（若未來出現亦可即時攔截）。

觸發時機：SessionStart（本 hook 目前未註冊至 settings.json，由後續 wave
統一註冊）。

依賴宣告：本檔透過 `from lib import ...` 觸發 `lib/__init__.py`，其會
`import .config_loader`；`config_loader` 內對 `yaml` 的 import 雖為函式內
延遲載入、當前執行路徑不會觸發，但 `lib/__init__.py` 屬共用進入點、其他
模組（`hook_ticket` 等）在同一 `__init__.py` 匯出集合下已固定要求
pyyaml——本檔隨現行慣例一併宣告，避免日後 `lib/__init__.py` 匯出範圍調整
時，本 hook 在 uv 隔離環境靜默 ModuleNotFoundError 失效卻無告警（掃描類
hook 失效與「掃描通過、內容合規」同形，維護者無法從外部行為分辨）。

Usage:
    python3 .claude/hooks/skill-banned-term-scan-hook.py

Exit codes:
    0 - 一律 0（WARNING only，不阻擋 session start）
"""

import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Set

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))
from lib import setup_hook_logging, run_hook_safely, get_project_root


# ============================================================================
# 常數定義
# ============================================================================

# language-constraints.md 規則 2 禁用詞清單（節錄，排除「優化」——見上方
# 模組 docstring「範圍排除」段落）
BANNED_TERMS = {
    "智能": "Hook 系統、規則比對",
    "文檔": "文件",
    "數據": "資料",
    "默認": "預設",
    "代碼": "程式碼",
    "視頻": "影片",
    "軟件": "軟體",
    "硬件": "硬體",
    "信息": "資訊",
}

# 檔案級白名單：整檔豁免（相對於 .claude/skills/ 的路徑，用 in 比對即可，
# 不需完全相等，容忍呼叫端傳入絕對路徑）
FILE_LEVEL_ALLOWLIST: Set[str] = {
    "compositional-writing/references/principles/regional-terminology-alignment.md",
}

INLINE_MARKER = "banned-term-exempt"

_INLINE_CODE_SPAN_RE = re.compile(r"`[^`]*`")
_FENCE_RE = re.compile(r"^\s*```")


@dataclass
class BannedTermHit:
    path: Path
    line_no: int
    term: str
    line_text: str


@dataclass
class ScanResult:
    violations: List[BannedTermHit]
    files_scanned: int
    files_allowlisted: int


def _is_allowlisted(path: Path, skills_root: Path, allowlist: Set[str]) -> bool:
    try:
        rel = path.relative_to(skills_root).as_posix()
    except ValueError:
        rel = path.as_posix()
    return any(rel.endswith(entry) for entry in allowlist)


def _strip_inline_code_spans(line: str) -> str:
    """把反引號內的內容清空，避免 mention 被誤判為 use（保留字元數不變，
    比對到的 term 位置不受影響，用空白填充維持行內位置對齊）。"""
    return _INLINE_CODE_SPAN_RE.sub(lambda m: " " * len(m.group(0)), line)


def scan_file(
    path: Path,
    skills_root: Optional[Path] = None,
    allowlist: Optional[Set[str]] = None,
) -> List[BannedTermHit]:
    """掃描單一檔案的禁用詞散文使用。

    豁免順序：檔案級白名單 -> fenced code block -> inline code span
    -> inline marker。
    """
    allowlist = allowlist if allowlist is not None else FILE_LEVEL_ALLOWLIST
    root = skills_root if skills_root is not None else path.parent

    if _is_allowlisted(path, root, allowlist):
        return []

    hits: List[BannedTermHit] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return []

    in_fence = False
    for line_no, raw_line in enumerate(lines, start=1):
        if _FENCE_RE.match(raw_line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if INLINE_MARKER in raw_line:
            continue

        scannable = _strip_inline_code_spans(raw_line)
        for term in BANNED_TERMS:
            if term in scannable:
                hits.append(BannedTermHit(path, line_no, term, raw_line.strip()))

    return hits


def scan_skills_dir(
    skills_dir: Path,
    allowlist: Optional[Set[str]] = None,
) -> ScanResult:
    """掃描整個 .claude/skills/ 目錄下所有 .md 檔案。"""
    allowlist = allowlist if allowlist is not None else FILE_LEVEL_ALLOWLIST

    violations: List[BannedTermHit] = []
    files_scanned = 0
    files_allowlisted = 0

    if not skills_dir.exists():
        return ScanResult(violations=[], files_scanned=0, files_allowlisted=0)

    for md_path in sorted(skills_dir.rglob("*.md")):
        if _is_allowlisted(md_path, skills_dir, allowlist):
            files_allowlisted += 1
            continue
        files_scanned += 1
        violations.extend(scan_file(md_path, skills_root=skills_dir, allowlist=allowlist))

    return ScanResult(
        violations=violations,
        files_scanned=files_scanned,
        files_allowlisted=files_allowlisted,
    )


def main() -> int:
    logger = setup_hook_logging("skill-banned-term-scan-hook")
    project_root = get_project_root()
    skills_dir = project_root / ".claude" / "skills"

    result = scan_skills_dir(skills_dir)

    print("\n[SkillBannedTermScan] Skill 禁用詞掃描結果")
    print("=" * 60)
    print(f"已掃描檔案: {result.files_scanned} 個")
    print(f"檔案級豁免: {result.files_allowlisted} 個")
    print(f"命中: {len(result.violations)} 處")

    if result.violations:
        print("\n偵測到疑似禁用詞散文使用（language-constraints.md 規則 2）：")
        for hit in result.violations:
            try:
                rel = hit.path.relative_to(skills_dir)
            except ValueError:
                rel = hit.path
            suggestion = BANNED_TERMS.get(hit.term, "")
            print(f"  - {rel}:{hit.line_no}  「{hit.term}」-> 建議「{suggestion}」")
            print(f"      {hit.line_text}")
        print(
            "\n若為合法引用（grep pattern / 術語對照樣本），改用反引號、"
            "程式碼區塊，或在行尾加 <!-- banned-term-exempt: 理由 -->"
        )
        logger.info("偵測到 %d 處禁用詞疑似違規", len(result.violations))
    else:
        print("\n未偵測到禁用詞散文使用")
        logger.debug("禁用詞掃描結果乾淨")

    print("=" * 60)

    # WARNING only，不阻擋 session start
    return 0


if __name__ == "__main__":
    sys.exit(run_hook_safely(main, "skill-banned-term-scan-hook"))
