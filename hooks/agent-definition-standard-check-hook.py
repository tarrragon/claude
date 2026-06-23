#!/usr/bin/env python3
"""
Agent Definition Standard Check Hook（SessionStart）

對 .claude/agents/*.md 執行知識載體分配約束的執法掃描：
1. 三區塊結構計數（允許產出 / 禁止行為 / 適用情境）須 == 3，缺漏輸出 top 3 違規檔。
2. 內容錯置啟發式 WARNING：偵測本應放規則/方法論層的「品質檢查全文 / 步驟化清單」
   被塞進 agent 定義檔（規範表的存在即病史，agent-definition-standard-details.md）。
3. 模板同步檢查：language-agent-template.md 三區塊存在性比對，防新實例從模板長出舊形態。

設計依據：
- 仿 skill-registration-check-hook.py 的 SessionStart 結構。
- 豁免清單沿用 .claude/references/agent-definition-standard-details.md：
  元文件（AGENT_PRELOAD.md）、DEPRECATED 標記檔、範本檔；
  另含目錄導引 README.md 與第三方 vendored agent（impeccable-manual-edit-applier）。

WARNING 級不阻擋 session（恆 exit 0）。異常 traceback 寫 stderr + log（quality-baseline 規則 4）。

Python 3.9 相容（CC 以系統 python3 執行 .py hook，忽略 shebang）。
"""

import re
import sys
from pathlib import Path
from typing import Dict, List, Optional

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))
from hook_utils import setup_hook_logging, run_hook_safely  # noqa: E402

# 三強制區塊（agent-definition-standard.md）
REQUIRED_SECTIONS = ("允許產出", "禁止行為", "適用情境")

# 範本檔（ticket 寫的「templates/」實際指此單檔，非獨立目錄）
TEMPLATE_FILENAME = "language-agent-template.md"

# 依檔名豁免：元文件、目錄導引、第三方 vendored agent
EXEMPT_FILENAMES = {
    "AGENT_PRELOAD.md",  # 共享 preamble，非 agent 定義
    "README.md",  # 目錄導引索引
    "impeccable-manual-edit-applier.md",  # 第三方 vendored agent，不依循三區塊標準
}

# 內容錯置啟發式：本應在 rules/methodologies 層的全文被塞進 agent 定義檔。
# 設計取捨（W8-016 dogfooding）：限 H2 (`## `) 層級命中，排除 H3+ 的 agent 領域專屬
# 子清單（如 cinnamon 的「### 重構品質指標」、TDD 流程內「### Step N: 品質檢查清單」），
# 避免高 false positive 使 WARNING 訊號失效（規範表的存在即病史 → 僅標 H2 級全文搬運）。
_MISPLACEMENT_PATTERNS = (
    # H2 級「品質檢查清單 / 提交前檢查清單」整段（典型 rules/core 全文搬運）
    re.compile(r"^##\s+(?:品質檢查清單|提交前檢查清單|品質基線)", re.MULTILINE),
    # H2 級「品質基線 / 強制規則」標題且內含測試通過率 100%（quality-baseline 全文特徵）
    re.compile(
        r"^##\s+.*(?:品質基線|強制規則).*$\n(?:.*\n)*?.*測試通過率\s*(?:必須)?\s*(?:維持)?\s*100\s*%",
        re.MULTILINE,
    ),
)


def _resolve_agents_dir() -> Path:
    """解析 .claude/agents/ 目錄（hook 位於 .claude/hooks/）。"""
    script_dir = Path(__file__).parent
    project_root = script_dir.parent.parent
    return project_root / ".claude" / "agents"


def count_required_sections(agent_path: Path) -> int:
    """計數 agent 檔內三強制區塊（## 層級）出現數。"""
    try:
        content = agent_path.read_text(encoding="utf-8")
    except OSError:
        return 0
    count = 0
    for section in REQUIRED_SECTIONS:
        if re.search(r"^##\s+" + re.escape(section) + r"\s*$", content, re.MULTILINE):
            count += 1
    return count


def is_exempt(filename: str, content: str) -> bool:
    """判定 agent 檔是否豁免三區塊結構檢查。"""
    if filename in EXEMPT_FILENAMES:
        return True
    # DEPRECATED 標記（description 或標題含 [DEPRECATED]）
    if "[DEPRECATED]" in content[:2000]:
        return True
    return False


def detect_content_misplacement(content: str) -> Optional[str]:
    """偵測內容錯置啟發式，命中回傳描述字串，否則 None。"""
    hits: List[str] = []
    if _MISPLACEMENT_PATTERNS[0].search(content):
        hits.append("含 H2 級品質/提交前檢查清單全文（宜放 rules/methodologies 層）")
    if _MISPLACEMENT_PATTERNS[1].search(content):
        hits.append("含 H2 級品質基線全文（測試通過率 100% 等強制規則搬運）")
    if hits:
        return "；".join(hits)
    return None


def check_template_sections(template_path: Path) -> List[str]:
    """檢查範本檔三區塊存在性，回傳缺漏區塊清單。

    範本不存在回傳 ["<file-not-found>"] 作為明確標記。
    """
    if not template_path.exists():
        return ["<file-not-found>"]
    try:
        content = template_path.read_text(encoding="utf-8")
    except OSError:
        return ["<file-not-found>"]
    missing: List[str] = []
    for section in REQUIRED_SECTIONS:
        if not re.search(r"^##\s+" + re.escape(section) + r"\s*$", content, re.MULTILINE):
            missing.append(section)
    return missing


def scan_agents(agents_dir: Path) -> Dict[str, object]:
    """掃描 agents 目錄，收集結構違規與內容錯置警告。"""
    structure_violations: List[Dict[str, object]] = []
    content_warnings: List[Dict[str, str]] = []

    if not agents_dir.exists():
        return {
            "structure_violations": [],
            "structure_violations_top3": [],
            "total_structure_violations": 0,
            "content_warnings": [],
        }

    for agent_path in sorted(agents_dir.glob("*.md")):
        filename = agent_path.name
        try:
            content = agent_path.read_text(encoding="utf-8")
        except OSError:
            content = ""

        if is_exempt(filename, content):
            continue

        count = count_required_sections(agent_path)
        if count != 3:
            structure_violations.append({"name": filename, "section_count": count})

        misplacement = detect_content_misplacement(content)
        if misplacement is not None:
            content_warnings.append({"name": filename, "reason": misplacement})

    return {
        "structure_violations": structure_violations,
        "structure_violations_top3": structure_violations[:3],
        "total_structure_violations": len(structure_violations),
        "content_warnings": content_warnings,
    }


def _report(result: Dict[str, object], template_missing: List[str], logger) -> None:
    """輸出掃描結果至 stdout（使用者可見）。"""
    total = result["total_structure_violations"]
    top3 = result["structure_violations_top3"]
    content_warnings = result["content_warnings"]

    print("\n[AgentDefCheck] Agent 定義標準執法掃描（WARNING 不阻擋）")
    print("=" * 60)

    if total == 0 and not content_warnings and not template_missing:
        print("所有 agent 定義符合三區塊標準，模板同步正常")
        print("=" * 60)
        return

    if total > 0:
        print(f"[結構違規] 三區塊不完整: {total} 個（顯示 top 3）")
        for v in top3:
            print(f"  - {v['name']}: 三區塊計數 {v['section_count']}/3")
        logger.info("structure violations total=%d top3=%s", total, top3)

    if content_warnings:
        print(f"[內容錯置] 可能錯置 rules/methodologies 層內容: {len(content_warnings)} 個")
        for w in content_warnings[:3]:
            print(f"  - {w['name']}: {w['reason']}")
        logger.info("content warnings=%s", content_warnings)

    if template_missing:
        if template_missing == ["<file-not-found>"]:
            print(f"[模板同步] {TEMPLATE_FILENAME} 不存在，無法比對三區塊")
        else:
            print(f"[模板同步] {TEMPLATE_FILENAME} 缺三區塊: {', '.join(template_missing)}")
        logger.info("template missing=%s", template_missing)

    print("\n建議：三區塊參考 .claude/references/agent-definition-standard-details.md；")
    print("      內容錯置請將品質/流程清單移至 rules/ 或 methodologies/ 層。")
    print("=" * 60)


def main() -> int:
    logger = setup_hook_logging("agent-definition-standard-check-hook")
    agents_dir = _resolve_agents_dir()

    result = scan_agents(agents_dir)
    template_missing = check_template_sections(agents_dir / TEMPLATE_FILENAME)

    _report(result, template_missing, logger)

    # WARNING 級：恆不阻擋 session
    return 0


if __name__ == "__main__":
    sys.exit(run_hook_safely(main, "agent-definition-standard-check-hook"))
