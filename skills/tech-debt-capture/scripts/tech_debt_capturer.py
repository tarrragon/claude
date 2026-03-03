#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml"]
# ///
"""
Tech Debt Capture - Phase 4 技術債務自動捕獲與 Ticket 建立工具

使用方式:
  uv run .claude/skills/tech-debt-capture/scripts/tech_debt_capturer.py capture \\
      docs/work-logs/v0.19.8-phase4-final-evaluation.md

  uv run ... capture ... --target-version 0.20.0

  uv run ... capture ... --dry-run

  uv run ... list --version 0.20.0
"""

import argparse
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Tuple
import yaml


# ============================================================================
# 常數定義
# ============================================================================

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.parent
WORK_LOGS_DIR = PROJECT_ROOT / "docs" / "work-logs"
TODOLIST_PATH = PROJECT_ROOT / "docs" / "todolist.yaml"

RISK_LEVELS = {
    "高": ("high", 1),
    "中": ("medium", 2),
    "低": ("low", 3),
    "極低": ("critical", 4),
}

RISK_LEVEL_REVERSE = {v[0]: k for k, v in RISK_LEVELS.items()}

# UC 版本對應（根據 todolist）
UC_VERSION_MAPPING = {
    "v0.12.x": ("UC-01", "0.12"),
    "v0.13.x": ("UC-02", "0.13"),
    "v0.14.x": ("UC-03", "0.14"),
    "v0.15.x": ("UC-04", "0.15"),
    "v0.16.x": ("UC-05", "0.16"),
    "v0.17.x": ("UC-06", "0.17"),
    "v0.18.x": ("UC-07", "0.18"),
    "v0.19.x": ("UC-08", "0.19"),
    "v0.20.x": ("UC-09", "0.20"),
}


# ============================================================================
# 技術債務解析
# ============================================================================

class TechDebtParser:
    """解析 Phase 4 工作日誌中的技術債務表格"""

    def __init__(self, log_file: Path):
        self.log_file = log_file
        self.content = log_file.read_text(encoding="utf-8")
        self.debts: List[Dict] = []

    def parse(self) -> List[Dict]:
        """解析技術債務表格"""
        # 尋找「技術債務識別」區塊
        debt_section = self._extract_tech_debt_section()
        if not debt_section:
            raise ValueError("找不到技術債務表格區塊（應包含 '技術債務識別' 標題）")

        # 解析表格
        self.debts = self._parse_table(debt_section)
        if not self.debts:
            raise ValueError("技術債務表格為空或格式不符")

        return self.debts

    def _extract_tech_debt_section(self) -> Optional[str]:
        """提取技術債務識別區塊"""
        lines = self.content.split("\n")
        section_start = None
        section_end = None

        # 尋找包含 6. 和技術債務的標題
        for i, line in enumerate(lines):
            if re.match(r"^##\s+6\.", line):
                section_start = i
                break

        if section_start is None:
            return None

        # 找到下一個相同等級的 ## 標題
        for i in range(section_start + 1, len(lines)):
            if re.match(r"^##\s", lines[i]):
                section_end = i
                break

        if section_end is None:
            section_end = len(lines)

        return "\n".join(lines[section_start:section_end])

    def _parse_table(self, section: str) -> List[Dict]:
        """解析 Markdown 表格"""
        # 尋找表格開始（包含 TD- 的行）
        lines = section.split("\n")
        table_start = None
        debts = []

        for i, line in enumerate(lines):
            # 尋找以 | TD- 開頭的行
            if "| TD-" in line:
                debt = self._parse_row(line)
                if debt:
                    debts.append(debt)

        return debts

    def _parse_row(self, row_line: str) -> Optional[Dict]:
        """解析表格行"""
        cells = [cell.strip() for cell in row_line.split("|")]
        # 移除前後空元素（表格行以 | 開始和結束）
        cells = [c for c in cells if c]

        if len(cells) < 4:
            return None

        try:
            # 順序為: ID, 描述, 風險等級, 建議處理時機
            return {
                "original_id": cells[0],
                "description": cells[1],
                "risk_level_zh": cells[2],
                "suggested_timing": cells[3],
            }
        except (IndexError, ValueError):
            return None


# ============================================================================
# 版本決策引擎
# ============================================================================

class VersionDecider:
    """根據風險等級和來源版本決定目標版本"""

    def __init__(self, source_version: str, target_version: Optional[str] = None):
        self.source_version = source_version
        self.target_version = target_version
        self.source_uc = self._extract_uc(source_version)
        self.source_minor = self._extract_minor_version(source_version)

    def decide_target_version(self, risk_level: str) -> str:
        """根據風險等級決定目標版本"""
        if self.target_version:
            return self.target_version

        # 風險等級對應規則
        risk_key = RISK_LEVELS.get(risk_level, ("unknown", 99))[0]

        if risk_key in ("high", "medium"):
            # 高/中風險：當前 UC 的下一個版本 (v0.20.0)
            next_uc_minor = int(self.source_minor) + 1
            return f"0.{next_uc_minor}.0"
        else:
            # 低/極低：當前 UC 版本系列的下一版本 (v0.20.0)
            # 對於低風險，也建議在下一個 UC 中處理
            next_uc_minor = int(self.source_minor) + 1
            return f"0.{next_uc_minor}.0"

    def _extract_uc(self, version: str) -> str:
        """從版本提取 UC 編號"""
        # 從版本檔案名提取 UC
        # 例如 v0.19.8 → UC-08
        match = re.search(r"v0\.(\d+)", version)
        if match:
            minor = int(match.group(1))
            # v0.19 → UC-08 (19-11=8)
            uc_num = minor - 11
            return f"UC-{uc_num:02d}"
        return "UC-??"

    def _extract_minor_version(self, version: str) -> str:
        """從版本提取 minor 版本號"""
        # 例如 v0.19.8 → 19
        match = re.search(r"v0\.(\d+)", version)
        if match:
            return match.group(1)
        return "??"


# ============================================================================
# Ticket 生成器
# ============================================================================

class TicketGenerator:
    """生成 Atomic Ticket 檔案"""

    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self.created_tickets: List[Path] = []

    def generate_ticket(
        self,
        debt: Dict,
        target_version: str,
        source_version: str,
        seq: int,
    ) -> Path:
        """生成 Ticket 檔案"""
        ticket_id = f"{target_version}-TD-{seq:03d}"
        source_uc = self._extract_uc(source_version)

        # 決定代理人（根據技術債務類型推測）
        agent = self._decide_agent(debt["description"])

        # 生成 frontmatter
        frontmatter = self._generate_frontmatter(
            ticket_id=ticket_id,
            target_version=target_version,
            source_version=source_version,
            source_uc=source_uc,
            debt=debt,
            agent=agent,
        )

        # 生成完整檔案內容
        content = frontmatter + "\n\n" + self._generate_body()

        # 決定儲存位置
        ticket_dir = WORK_LOGS_DIR / f"v{target_version}" / "tickets"
        ticket_path = ticket_dir / f"{ticket_id}.md"

        # 建立目錄
        if not self.dry_run:
            ticket_dir.mkdir(parents=True, exist_ok=True)
            ticket_path.write_text(content, encoding="utf-8")
            self.created_tickets.append(ticket_path)

        return ticket_path

    def _extract_uc(self, version: str) -> str:
        """從版本提取 UC 編號"""
        match = re.search(r"v0\.(\d+)", version)
        if match:
            minor = int(match.group(1))
            uc_num = minor - 11
            return f"UC-{uc_num:02d}"
        return "UC-??"

    def _decide_agent(self, description: str) -> str:
        """根據技術債務描述決定執行代理人"""
        # 簡單的啟發式規則
        if "資料庫" in description or "索引" in description:
            return "parsley-flutter-developer"
        elif "Repository" in description or "Service" in description:
            return "parsley-flutter-developer"
        elif "Linter" in description or "警告" in description:
            return "mint-format-specialist"
        else:
            return "parsley-flutter-developer"

    def _generate_frontmatter(
        self,
        ticket_id: str,
        target_version: str,
        source_version: str,
        source_uc: str,
        debt: Dict,
        agent: str,
    ) -> str:
        """生成 YAML frontmatter"""
        # 決定 action 和 target
        action, target = self._decompose_description(debt["description"])

        # 風險等級編碼
        risk_level_zh = debt["risk_level_zh"]
        risk_level_en = RISK_LEVELS.get(risk_level_zh, ("unknown", 99))[0]

        # 建立 YAML 字符串
        lines = ["---"]

        # 按分類加入欄位
        lines.append("# === Identification ===")
        lines.append(f"ticket_id: {ticket_id}")
        lines.append('ticket_type: "tech-debt"')
        lines.append(f"version: {target_version}")

        lines.append("")
        lines.append("# === Technical Debt Specific ===")
        lines.append(f"source_version: {source_version}")
        lines.append(f"source_uc: {source_uc}")
        lines.append(f"risk_level: {risk_level_en}")
        lines.append(f"original_id: {debt['original_id']}")

        lines.append("")
        lines.append("# === Single Responsibility ===")
        lines.append(f"action: {action}")
        lines.append(f'target: "{target}"')

        lines.append("")
        lines.append("# === Execution ===")
        lines.append(f"agent: {agent}")

        lines.append("")
        lines.append("# === 5W1H Design ===")
        lines.append(
            f"who: \"{agent} (執行者) | rosemary-project-manager (分派者)\""
        )
        lines.append(f"what: \"{action} {target}\"")
        lines.append(f"when: \"v{target_version} 開發期間\"")
        lines.append(f"where: \"{self._infer_location(debt['description'])}\"")
        lines.append(f"why: \"{debt['description']}\"")
        lines.append(f"how: \"[Task Type: Implementation] {debt['suggested_timing']}\"")

        lines.append("")
        lines.append("# === Acceptance Criteria ===")
        lines.append("acceptance:")
        lines.append("  - 技術債務修復完成")
        lines.append("  - 相關測試通過")
        lines.append("  - 驗證修復有效性")

        lines.append("")
        lines.append("# === Related Files ===")
        lines.append("files:")
        for file in self._infer_files(debt["description"]):
            lines.append(f"  - {file}")

        lines.append("")
        lines.append("# === Dependencies ===")
        lines.append("dependencies: []")

        lines.append("")
        lines.append("# === Status Tracking ===")
        lines.append("status: pending")
        lines.append("assigned: false")
        lines.append("started_at: null")
        lines.append("completed_at: null")

        lines.append("---")
        return "\n".join(lines)

    def _decompose_description(self, description: str) -> Tuple[str, str]:
        """將描述分解為 action 和 target"""
        # 簡單的啟發式分解
        if "新增" in description or "添加" in description or "建立" in description:
            action = "Add"
            target = description.replace("新增", "").replace("添加", "").replace("建立", "").strip()
        elif "抽取" in description or "重構" in description:
            action = "Refactor"
            target = description.replace("抽取", "").replace("重構", "").strip()
        elif "清理" in description or "移除" in description:
            action = "Clean"
            target = description.replace("清理", "").replace("移除", "").strip()
        elif "整合" in description:
            action = "Integrate"
            target = description.replace("整合", "").strip()
        else:
            action = "Fix"
            target = description

        return action, target

    def _infer_location(self, description: str) -> str:
        """根據描述推測檔案位置"""
        if "資料庫" in description or "Repository" in description:
            return "lib/infrastructure/database/"
        elif "Widget" in description or "UI" in description:
            return "lib/presentation/"
        elif "Service" in description:
            return "lib/infrastructure/"
        else:
            return "lib/"

    def _infer_files(self, description: str) -> List[str]:
        """根據描述推測相關檔案"""
        files = []
        if "book_tags" in description:
            files.append("lib/infrastructure/database/sqlite_book_repository.dart")
        if "BackgroundProcessingService" in description:
            files.append("lib/infrastructure/async/background_processing_service.dart")
        if "Repository" in description:
            files.append("lib/domains/library/repositories/book_repository.dart")
        if not files:
            files.append("lib/")
        return files

    def _generate_body(self) -> str:
        """生成 Ticket 本體（執行日誌區塊）"""
        return """# Execution Log

## Task Summary

<!-- Will be filled by executing agent -->

## Problem Analysis

<!-- To be filled by executing agent -->

## Solution

<!-- To be filled by executing agent -->

## Test Results

<!-- To be filled by executing agent -->

## Completion Info

**Completion Time**: (pending)
**Executing Agent**: (pending)
**Review Status**: pending"""


# ============================================================================
# TodoList 更新器
# ============================================================================

class TodoListUpdater:
    """更新 todolist.yaml 的技術債務追蹤區塊"""

    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self.todolist_path = TODOLIST_PATH

    def update(self, tickets: List[Tuple[str, Dict, str]]) -> None:
        """更新 todolist 中的技術債務追蹤區塊"""
        if not self.todolist_path.exists():
            print(f"⚠️  找不到 {self.todolist_path}")
            return

        content = self.todolist_path.read_text(encoding="utf-8")

        # 生成新的技術債務區塊
        new_section = self._generate_tech_debt_section(tickets)

        # 查找現有區塊或在末尾新增
        if "## 技術債務追蹤" in content:
            # 替換現有區塊
            pattern = r"## 技術債務追蹤.*?(?=\n##|\Z)"
            content = re.sub(pattern, new_section, content, flags=re.DOTALL)
        else:
            # 在末尾新增
            content = content.rstrip() + "\n\n" + new_section

        if not self.dry_run:
            self.todolist_path.write_text(content, encoding="utf-8")

    def _generate_tech_debt_section(
        self, tickets: List[Tuple[str, Dict, str]]
    ) -> str:
        """生成技術債務追蹤區塊"""
        lines = ["## 技術債務追蹤"]
        lines.append("")
        lines.append(
            "| Ticket ID | 描述 | 來源版本 | 目標版本 | 風險 | 狀態 |"
        )
        lines.append("|-----------|------|---------|--------|------|------|")

        for ticket_id, debt, source_version in tickets:
            target_version = ticket_id.split("-")[0]
            risk_level = debt["risk_level_zh"]
            lines.append(
                f"| {ticket_id} | {debt['description']} | {source_version} | "
                f"v{target_version} | {risk_level} | pending |"
            )

        return "\n".join(lines)


# ============================================================================
# 命令行介面
# ============================================================================

def cmd_capture(args) -> int:
    """解析技術債務並建立 Ticket"""
    log_file = Path(args.log_file)

    if not log_file.exists():
        print(f"❌ 錯誤: 找不到工作日誌檔案: {log_file}")
        return 1

    # 提取版本號
    match = re.search(r"v(\d+\.\d+\.\d+)", log_file.name)
    if not match:
        print(f"❌ 錯誤: 無法從檔案名提取版本號: {log_file.name}")
        return 1

    source_version = f"v{match.group(1)}"

    # 解析技術債務
    try:
        parser = TechDebtParser(log_file)
        debts = parser.parse()
        print(f"📋 找到 {len(debts)} 個技術債務項目")
    except ValueError as e:
        print(f"❌ 錯誤: {e}")
        return 1

    # 版本決策
    decider = VersionDecider(source_version, args.target_version)
    print("\n📊 版本對應決策")

    ticket_plan = []
    seq_counter = {}

    for debt in debts:
        target_version = decider.decide_target_version(debt["risk_level_zh"])

        # 為每個版本分別計數
        if target_version not in seq_counter:
            seq_counter[target_version] = 1

        ticket_id = f"{target_version}-TD-{seq_counter[target_version]:03d}"
        seq_counter[target_version] += 1

        risk_zh = debt["risk_level_zh"]
        print(f"  {debt['original_id']} ({risk_zh}) → {ticket_id}")
        ticket_plan.append((ticket_id, target_version, debt))

    # 預覽模式
    if args.dry_run:
        print("\n📋 預覽模式 - 不會建立實際檔案")
        return 0

    # 建立 Ticket
    print("\n📝 建立 Ticket 檔案")
    generator = TicketGenerator(dry_run=False)
    created_tickets = []

    for ticket_id, target_version, debt in ticket_plan:
        seq = int(ticket_id.split("-")[-1])
        path = generator.generate_ticket(debt, target_version, source_version, seq)
        created_tickets.append((ticket_id, debt, source_version))
        print(f"  ✅ {path.relative_to(PROJECT_ROOT)}")

    # 更新 todolist
    print("\n📝 更新 todolist.yaml")
    updater = TodoListUpdater(dry_run=False)
    updater.update(created_tickets)
    print("  ✅ 技術債務追蹤區塊已更新")

    print(f"\n✅ 完成！共建立 {len(created_tickets)} 個技術債務 Ticket")
    return 0


def cmd_init(args) -> int:
    """初始化版本目錄"""
    version = args.version
    version_dir = WORK_LOGS_DIR / f"v{version}"
    tickets_dir = version_dir / "tickets"

    tickets_dir.mkdir(parents=True, exist_ok=True)
    print(f"✅ 已建立版本目錄: {version_dir.relative_to(PROJECT_ROOT)}")
    print(f"✅ 已建立 Tickets 子目錄: {tickets_dir.relative_to(PROJECT_ROOT)}")
    return 0


def cmd_list(args) -> int:
    """列出技術債務 Ticket"""
    version = args.version
    tickets_dir = WORK_LOGS_DIR / f"v{version}" / "tickets"

    if not tickets_dir.exists():
        print(f"⚠️  找不到版本目錄: {tickets_dir}")
        return 1

    # 尋找所有 TD Ticket
    td_tickets = sorted(tickets_dir.glob("*-TD-*.md"))

    if not td_tickets:
        print(f"📋 v{version} 中無技術債務 Ticket")
        return 0

    print(f"📋 v{version} 技術債務清單\n")
    print("Ticket ID         | 描述                      | 風險  | 來源版本")
    print("-" * 70)

    for ticket_file in td_tickets:
        # 解析 frontmatter
        content = ticket_file.read_text(encoding="utf-8")
        try:
            fm_end = content.find("---", 4)
            fm_text = content[4:fm_end]
            frontmatter = yaml.safe_load(fm_text)

            if not frontmatter:
                print(f"{ticket_file.name:17} | [解析失敗] |")
                continue

            ticket_id = frontmatter.get("ticket_id", "??")
            description = frontmatter.get("why", "")[:20]
            risk = frontmatter.get("risk_level", "unknown")
            source_version = frontmatter.get("source_version", "??")

            risk_zh = RISK_LEVEL_REVERSE.get(risk, "未知")
            print(
                f"{ticket_id:17} | {description:25} | {risk_zh:4} | {source_version}"
            )
        except Exception as e:
            print(f"{ticket_file.name:17} | [解析失敗: {str(e)[:20]}] |")

    return 0


# ============================================================================
# 主程式
# ============================================================================

def main():
    """主程式"""
    parser = argparse.ArgumentParser(
        description="Phase 4 技術債務自動捕獲與 Ticket 建立工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
範例:
  # 捕獲技術債務並建立 Ticket
  uv run .claude/skills/tech-debt-capture/scripts/tech_debt_capturer.py capture \\
      docs/work-logs/v0.19.8-phase4-final-evaluation.md

  # 指定目標版本
  uv run ... capture ... --target-version 0.20.0

  # 預覽模式
  uv run ... capture ... --dry-run

  # 列出技術債務
  uv run ... list --version 0.20.0

  # 初始化版本目錄
  uv run ... init 0.20.0
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="子命令")

    # capture 命令
    capture_parser = subparsers.add_parser(
        "capture", help="解析工作日誌並建立技術債務 Ticket"
    )
    capture_parser.add_argument(
        "log_file", help="Phase 4 工作日誌檔案路徑"
    )
    capture_parser.add_argument(
        "--target-version",
        help="指定目標版本（預設自動推導）",
    )
    capture_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="預覽模式，不建立實際檔案",
    )
    capture_parser.set_defaults(func=cmd_capture)

    # init 命令
    init_parser = subparsers.add_parser("init", help="初始化版本目錄")
    init_parser.add_argument("version", help="版本號（例如 0.20.0）")
    init_parser.set_defaults(func=cmd_init)

    # list 命令
    list_parser = subparsers.add_parser("list", help="列出技術債務 Ticket")
    list_parser.add_argument("--version", required=True, help="版本號")
    list_parser.set_defaults(func=cmd_list)

    # 解析參數
    args = parser.parse_args()

    if not hasattr(args, "func"):
        parser.print_help()
        return 1

    # 執行命令
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
