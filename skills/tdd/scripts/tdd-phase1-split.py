#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml"]
# ///
"""
TDD Phase 1 SOLID 原則驅動拆分輔助工具

在 Phase 1（功能設計）階段分析功能範圍，識別獨立職責，
產出拆分建議和版本號分配。
"""

import argparse
import sys
import re
from pathlib import Path
from datetime import datetime
from typing import Optional
import subprocess

# 專案根目錄
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.parent


# === SOLID 原則定義 ===

SOLID_PRINCIPLES = {
    "SRP": {
        "name": "Single Responsibility Principle",
        "chinese": "單一職責原則",
        "questions": [
            "這個功能有幾個獨立的修改原因？",
            "能用「動詞 + 單一目標」描述嗎？",
            "所有驗收條件都指向同一目標嗎？"
        ],
        "signals": [
            "有 2+ 個修改原因",
            "需要用「和」連接描述",
            "驗收條件指向不同目標"
        ]
    },
    "OCP": {
        "name": "Open-Closed Principle",
        "chinese": "開閉原則",
        "questions": [
            "未來擴展需要修改現有程式碼嗎？",
            "有沒有可以抽象的變化點？"
        ],
        "signals": [
            "需要 switch/case 或 if/else 處理不同類型",
            "未來新增類型需要修改現有程式碼"
        ]
    },
    "LSP": {
        "name": "Liskov Substitution Principle",
        "chinese": "里氏替換原則",
        "questions": [
            "有繼承關係嗎？",
            "子類別能完全替換父類別嗎？"
        ],
        "signals": [
            "子類別需要覆寫並改變父類別行為",
            "某些方法在子類別中沒有意義"
        ]
    },
    "ISP": {
        "name": "Interface Segregation Principle",
        "chinese": "介面隔離原則",
        "questions": [
            "介面有沒有強迫實作不需要的方法？",
            "一個介面服務多少個不同的客戶端？"
        ],
        "signals": [
            "實作類別有空方法或拋出 NotImplemented",
            "不同客戶端只使用介面的一部分"
        ]
    },
    "DIP": {
        "name": "Dependency Inversion Principle",
        "chinese": "依賴反轉原則",
        "questions": [
            "高層模組是否依賴低層模組？",
            "依賴的是抽象還是具體實作？"
        ],
        "signals": [
            "直接 import 具體類別",
            "無法獨立測試（依賴外部服務）"
        ]
    }
}

# 架構層級定義
ARCHITECTURE_LAYERS = {
    "Domain": {"order": 1, "description": "領域層（Entity, Value Object）"},
    "Application": {"order": 2, "description": "應用層（UseCase）"},
    "Infrastructure": {"order": 3, "description": "基礎設施層（Repository 實作）"},
    "Presentation": {"order": 4, "description": "表示層（Widget, Controller）"}
}


def print_header(title: str):
    """印出標題"""
    print(f"\n{'=' * 60}")
    print(f" {title}")
    print('=' * 60)


def print_section(title: str):
    """印出區段標題"""
    print(f"\n{'-' * 40}")
    print(f" {title}")
    print('-' * 40)


# === 分析命令 ===

def cmd_analyze(args):
    """互動式 SOLID 分析"""
    description = args.description

    print_header("TDD Phase 1 SOLID 分析")
    print(f"\n功能描述: {description}")

    results = {}

    for principle, info in SOLID_PRINCIPLES.items():
        print_section(f"{principle}: {info['chinese']}")
        print(f"({info['name']})\n")

        print("檢查問題:")
        for i, q in enumerate(info['questions'], 1):
            print(f"  {i}. {q}")

        print("\n拆分信號:")
        for signal in info['signals']:
            print(f"  - {signal}")

        # 互動式輸入
        print(f"\n[{principle}] 分析結果:")
        has_issue = input("  是否發現問題需要拆分? (y/n): ").strip().lower()

        if has_issue == 'y':
            note = input("  請簡述問題: ").strip()
            results[principle] = {
                "has_issue": True,
                "note": note
            }
        else:
            results[principle] = {
                "has_issue": False,
                "note": ""
            }

    # 產出報告
    print_header("SOLID 分析報告")

    issues_found = [p for p, r in results.items() if r['has_issue']]

    if issues_found:
        print(f"\n發現 {len(issues_found)} 個需要拆分的原則違反:")
        for p in issues_found:
            print(f"  [{p}] {results[p]['note']}")
        print("\n建議: 使用 'suggest' 命令獲取拆分建議")
    else:
        print("\n未發現明顯的 SOLID 原則違反")
        print("功能可能不需要進一步拆分")

    return 0


# === 拆分建議命令 ===

def cmd_suggest(args):
    """產出拆分建議"""
    description = args.description
    version = args.version

    print_header("TDD Phase 1 拆分建議")
    print(f"\n原始需求: {description}")
    print(f"目標版本: {version}")

    # 簡化的分析流程（實際應該更複雜）
    print_section("功能範圍分析")

    # 從描述中識別關鍵字
    keywords = extract_keywords(description)
    print(f"識別關鍵字: {', '.join(keywords)}")

    # 建議的拆分
    print_section("建議拆分清單")

    # 產生建議的子功能（這是簡化版本，實際應該更智能）
    suggestions = generate_split_suggestions(description, version)

    print(f"\n{'子功能':<6} | {'描述':<30} | {'架構層':<15} | {'版本':<8} | 依賴")
    print("-" * 80)
    for s in suggestions:
        deps = ", ".join(s['depends']) if s['depends'] else "無"
        print(f"{s['id']:<6} | {s['description']:<30} | {s['layer']:<15} | {s['version']:<8} | {deps}")

    # 版本分配說明
    print_section("版本分配說明")

    versions = {}
    for s in suggestions:
        v = s['version']
        if v not in versions:
            versions[v] = []
        versions[v].append(s['id'])

    for v in sorted(versions.keys()):
        ids = ", ".join(versions[v])
        parallel = "可並行" if len(versions[v]) > 1 else "序列"
        print(f"- {v}: {ids} ({parallel})")

    print("\n建議: 使用 'create-tickets' 命令建立 Tickets")

    return 0


def extract_keywords(description: str) -> list[str]:
    """從描述中提取關鍵字"""
    # 常見動詞
    verbs = ["實作", "建立", "新增", "修改", "刪除", "查詢", "搜尋", "更新"]
    # 常見名詞模式

    keywords = []
    for verb in verbs:
        if verb in description:
            keywords.append(verb)

    # 提取名詞（簡化版本）
    words = re.findall(r'[\u4e00-\u9fff]+', description)
    for word in words:
        if word not in verbs and len(word) >= 2:
            keywords.append(word)

    return keywords[:5]  # 最多 5 個


def generate_split_suggestions(description: str, version: str) -> list[dict]:
    """產生拆分建議"""
    # 這是簡化版本，實際應該更智能地分析

    # 從 version 產生小版本
    parts = version.split('.')
    major = parts[0]
    minor = parts[1]

    v1 = f"{major}.{minor}.1"
    v2 = f"{major}.{minor}.2"
    v3 = f"{major}.{minor}.3"

    suggestions = []

    # 根據描述中的關鍵字產生建議
    if "搜尋" in description or "查詢" in description:
        suggestions = [
            {"id": "A", "description": "SearchQuery 值物件", "layer": "Domain", "version": v1, "depends": []},
            {"id": "B", "description": "SearchResult Entity", "layer": "Domain", "version": v1, "depends": []},
            {"id": "C", "description": "ISearchRepository 介面", "layer": "Domain", "version": v1, "depends": []},
            {"id": "D", "description": "SearchUseCase", "layer": "Application", "version": v2, "depends": ["A", "B", "C"]},
            {"id": "E", "description": "SearchRepository 實作", "layer": "Infrastructure", "version": v2, "depends": ["C"]},
            {"id": "F", "description": "SearchWidget", "layer": "Presentation", "version": v3, "depends": ["D"]},
        ]
    elif "新增" in description or "建立" in description or "實作" in description:
        # 通用 CRUD 功能
        target = description.replace("實作", "").replace("新增", "").replace("建立", "").strip()
        suggestions = [
            {"id": "A", "description": f"{target} Entity", "layer": "Domain", "version": v1, "depends": []},
            {"id": "B", "description": f"I{target}Repository 介面", "layer": "Domain", "version": v1, "depends": []},
            {"id": "C", "description": f"Create{target}UseCase", "layer": "Application", "version": v2, "depends": ["A", "B"]},
            {"id": "D", "description": f"{target}Repository 實作", "layer": "Infrastructure", "version": v2, "depends": ["B"]},
            {"id": "E", "description": f"{target}Widget", "layer": "Presentation", "version": v3, "depends": ["C"]},
        ]
    else:
        # 預設模板
        suggestions = [
            {"id": "A", "description": "Domain 模型", "layer": "Domain", "version": v1, "depends": []},
            {"id": "B", "description": "UseCase 邏輯", "layer": "Application", "version": v2, "depends": ["A"]},
            {"id": "C", "description": "UI 元件", "layer": "Presentation", "version": v3, "depends": ["B"]},
        ]

    return suggestions


# === 建立 Tickets 命令 ===

def cmd_create_tickets(args):
    """根據分析結果建立 Tickets"""
    description = args.description
    version = args.version
    wave = args.wave

    print_header("建立拆分 Tickets")
    print(f"\n原始需求: {description}")
    print(f"版本: {version}, Wave: {wave}")

    # 產生拆分建議
    suggestions = generate_split_suggestions(description, version)

    # 確認建立
    print_section("將建立以下 Tickets")

    print(f"\n父 Ticket:")
    print(f"  {version}-W{wave}-001: {description}")

    print(f"\n子 Tickets:")
    for i, s in enumerate(suggestions, 2):
        print(f"  {version}-W{wave}-{i:03d}: {s['description']}")

    confirm = input("\n確認建立? (y/n): ").strip().lower()
    if confirm != 'y':
        print("已取消")
        return 0

    # 建立 Tickets
    ticket_creator = PROJECT_ROOT / ".claude" / "skills" / "ticket-create" / "scripts" / "ticket-creator.py"

    if not ticket_creator.exists():
        print(f"[Error] 找不到 ticket-creator.py")
        return 1

    # 建立父 Ticket
    print_section("建立父 Ticket")

    # 提取動詞和目標
    action = "實作"
    target = description.replace("實作", "").strip()

    cmd = [
        "uv", "run", str(ticket_creator), "create",
        "--version", version,
        "--wave", str(wave),
        "--action", action,
        "--target", target
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, cwd=PROJECT_ROOT)
    if result.returncode != 0:
        print(f"[Error] 建立父 Ticket 失敗: {result.stderr}")
        return 1

    print(result.stdout)

    # 解析父 Ticket ID
    parent_id = f"{version}-W{wave}-001"

    # 建立子 Tickets
    print_section("建立子 Tickets")

    for s in suggestions:
        cmd = [
            "uv", "run", str(ticket_creator), "create-child",
            "--parent-id", parent_id,
            "--wave", str(wave),
            "--action", "建立",
            "--target", s['description']
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, cwd=PROJECT_ROOT)
        if result.returncode != 0:
            print(f"[Warning] 建立子 Ticket 失敗: {result.stderr}")
        else:
            print(result.stdout.strip())

    print_section("完成")
    print(f"已建立 1 個父 Ticket 和 {len(suggestions)} 個子 Tickets")

    return 0


# === 驗證命令 ===

def cmd_validate(args):
    """驗證拆分是否符合 SOLID 原則"""
    ticket_id = args.ticket_id

    print_header("驗證 Ticket 拆分")
    print(f"\nTicket ID: {ticket_id}")

    # 解析 ticket_id 取得版本
    parts = ticket_id.split('-')
    if len(parts) < 3:
        print(f"[Error] 無效的 Ticket ID 格式")
        return 1

    version = parts[0]

    # 尋找 Ticket 檔案
    tickets_dir = PROJECT_ROOT / "docs" / "work-logs" / f"v{version}" / "tickets"

    if not tickets_dir.exists():
        print(f"[Error] 找不到 tickets 目錄: {tickets_dir}")
        return 1

    ticket_file = tickets_dir / f"{ticket_id}.md"

    if not ticket_file.exists():
        print(f"[Error] 找不到 Ticket 檔案: {ticket_file}")
        return 1

    # 讀取 Ticket
    content = ticket_file.read_text(encoding='utf-8')

    print_section("Ticket 內容分析")

    # 檢查是否有子 Tickets
    if "children:" in content:
        # 提取 children
        match = re.search(r'children:\s*\[(.*?)\]', content, re.DOTALL)
        if match:
            children_str = match.group(1).strip()
            if children_str:
                children = [c.strip().strip('"\'') for c in children_str.split(',')]
                print(f"找到 {len(children)} 個子 Tickets")

                # 驗證每個子 Ticket
                print_section("SOLID 檢查")

                for child_id in children:
                    child_file = tickets_dir / f"{child_id}.md"
                    if child_file.exists():
                        child_content = child_file.read_text(encoding='utf-8')

                        # SRP 檢查
                        title_match = re.search(r'title:\s*["\'](.+?)["\']', child_content)
                        title = title_match.group(1) if title_match else "unknown"

                        srp_ok = "和" not in title and len(title.split()) <= 5
                        srp_status = "[OK]" if srp_ok else "[Warning]"
                        print(f"  {child_id}: {srp_status} SRP - {title}")
                    else:
                        print(f"  {child_id}: [Error] 找不到檔案")
            else:
                print("此 Ticket 沒有子 Tickets")
        else:
            print("此 Ticket 沒有子 Tickets")
    else:
        print("此 Ticket 沒有子 Tickets（可能不需要拆分）")

    print_section("驗證結果")
    print("驗證完成。請檢查上方的 SOLID 檢查結果。")

    return 0


# === 報告命令 ===

def cmd_report(args):
    """產出拆分報告"""
    description = args.description
    version = args.version
    output = args.output

    # 產生報告內容
    suggestions = generate_split_suggestions(description, version)

    report = f"""## Phase 1 拆分報告

### 原始需求
- **描述**: {description}
- **目標版本**: {version}
- **產出時間**: {datetime.now().strftime('%Y-%m-%d %H:%M')}

### SOLID 分析摘要

| 原則 | 狀態 | 建議 |
|------|------|------|
| SRP | 需檢查 | 確認只有一個修改原因 |
| OCP | 需檢查 | 考慮擴展點抽象 |
| LSP | - | 視繼承需求而定 |
| ISP | 需檢查 | 確認介面最小化 |
| DIP | 需檢查 | 依賴抽象而非具體 |

### 拆分清單

| ID | 描述 | 層級 | 版本 | 依賴 |
|----|------|------|------|------|
"""

    for s in suggestions:
        deps = ", ".join(s['depends']) if s['depends'] else "-"
        report += f"| {s['id']} | {s['description']} | {s['layer']} | {s['version']} | {deps} |\n"

    report += f"""
### 執行計畫

"""

    # 按版本分組
    versions = {}
    for s in suggestions:
        v = s['version']
        if v not in versions:
            versions[v] = []
        versions[v].append(s)

    step = 1
    for v in sorted(versions.keys()):
        items = versions[v]
        parallel = "並行" if len(items) > 1 else "序列"
        report += f"{step}. **{v}**（{parallel}）\n"
        for item in items:
            report += f"   - {item['id']}: {item['description']}\n"
        step += 1

    report += """
### 建議行動
1. 建立父 Ticket
2. 建立子 Tickets
3. 設定依賴關係
4. 開始 TDD 循環
"""

    if output:
        output_path = Path(output)
        output_path.write_text(report, encoding='utf-8')
        print(f"[OK] 報告已儲存到: {output}")
    else:
        print(report)

    return 0


# === 主程式 ===

def main():
    parser = argparse.ArgumentParser(
        description="TDD Phase 1 SOLID 原則驅動拆分輔助工具"
    )

    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # analyze 命令
    analyze_parser = subparsers.add_parser("analyze", help="互動式 SOLID 分析")
    analyze_parser.add_argument("--description", "-d", required=True, help="功能描述")

    # suggest 命令
    suggest_parser = subparsers.add_parser("suggest", help="產出拆分建議")
    suggest_parser.add_argument("--description", "-d", required=True, help="功能描述")
    suggest_parser.add_argument("--version", "-v", required=True, help="目標版本")

    # create-tickets 命令
    create_parser = subparsers.add_parser("create-tickets", help="建立拆分 Tickets")
    create_parser.add_argument("--description", "-d", required=True, help="功能描述")
    create_parser.add_argument("--version", "-v", required=True, help="目標版本")
    create_parser.add_argument("--wave", "-w", type=int, required=True, help="Wave 編號")

    # validate 命令
    validate_parser = subparsers.add_parser("validate", help="驗證拆分")
    validate_parser.add_argument("--ticket-id", "-t", required=True, help="Ticket ID")

    # report 命令
    report_parser = subparsers.add_parser("report", help="產出拆分報告")
    report_parser.add_argument("--description", "-d", required=True, help="功能描述")
    report_parser.add_argument("--version", "-v", required=True, help="目標版本")
    report_parser.add_argument("--output", "-o", help="輸出檔案路徑")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    commands = {
        "analyze": cmd_analyze,
        "suggest": cmd_suggest,
        "create-tickets": cmd_create_tickets,
        "validate": cmd_validate,
        "report": cmd_report
    }

    return commands[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
