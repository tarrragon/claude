#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PyYAML 替代評估腳本 — W39-002 Phase 3b

評估步驟：
1. 功能等價性測試：對比手寫解析器和 PyYAML 的輸出
2. 效能微基準測試：測量解析時間差異
3. 依賴整合影響分析：列舉使用 parse_ticket_frontmatter() 的 Hook
4. 產出評估報告

執行方式：
  uv run eval_pyyaml.py
"""

import sys
import timeit
from pathlib import Path
from datetime import datetime

# 添加 hook_utils 到路徑
sys.path.insert(0, str(Path(__file__).parent))

try:
    from hook_utils import parse_ticket_frontmatter
except ImportError:
    print("Error: 無法導入 hook_utils")
    sys.exit(1)

try:
    import yaml
    HAS_PYYAML = True
except ImportError:
    HAS_PYYAML = False
    print("Warning: PyYAML 未安裝，跳過性能測試")


def extract_frontmatter(file_path: Path) -> str:
    """從 Ticket 檔案提取 frontmatter 區塊"""
    try:
        content = file_path.read_text(encoding='utf-8')
        if not content.startswith('---'):
            return None
        end_idx = content.find('\n---\n', 4)
        if end_idx == -1:
            return None
        return content[4:end_idx]
    except Exception:
        return None


def collect_samples(max_samples: int = 10) -> list[str]:
    """蒐集代表性 Ticket frontmatter 樣本"""
    project_root = Path(__file__).parent.parent.parent
    ticket_dir = project_root / "docs" / "work-logs"

    samples = []
    for ticket_file in ticket_dir.rglob("*.md"):
        if len(samples) >= max_samples:
            break

        # 跳過非 Ticket 檔案（Ticket 檔案應在 tickets/ 目錄下）
        if "tickets" not in str(ticket_file):
            continue

        frontmatter = extract_frontmatter(ticket_file)
        if frontmatter:
            samples.append(frontmatter)

    return samples


def test_functional_equivalence(samples: list[str]) -> tuple[bool, list[str]]:
    """測試功能等價性：比較手寫解析器和 PyYAML 的輸出"""
    if not HAS_PYYAML:
        return None, ["PyYAML not installed - unable to test"]

    differences = []

    for i, sample in enumerate(samples):
        try:
            # 手寫解析器
            handwritten_result = parse_ticket_frontmatter(sample)

            # PyYAML
            pyyaml_result = yaml.safe_load(sample)

            # 比較
            if handwritten_result != pyyaml_result:
                differences.append(f"樣本 {i+1}: 輸出不相等")
                print(f"  樣本 {i+1} 差異:")
                print(f"    手寫: {handwritten_result}")
                print(f"    PyYAML: {pyyaml_result}")

        except Exception as e:
            differences.append(f"樣本 {i+1}: 解析錯誤 {e}")

    return len(differences) == 0, differences


def test_performance(samples: list[str]) -> dict:
    """執行效能微基準測試"""
    if not HAS_PYYAML:
        return None

    results = {
        "handwritten_avg_us": 0,
        "pyyaml_avg_us": 0,
        "ratio": 0,
    }

    if not samples:
        return results

    # 測試手寫解析器
    def test_handwritten():
        for sample in samples:
            parse_ticket_frontmatter(sample)

    # 測試 PyYAML
    def test_pyyaml():
        for sample in samples:
            yaml.safe_load(sample)

    # 執行 1000 次迴圈
    loops = 1000

    handwritten_time = timeit.timeit(test_handwritten, number=loops)
    pyyaml_time = timeit.timeit(test_pyyaml, number=loops)

    # 計算平均時間（微秒）
    total_samples = len(samples) * loops
    results["handwritten_avg_us"] = (handwritten_time * 1e6) / total_samples
    results["pyyaml_avg_us"] = (pyyaml_time * 1e6) / total_samples
    results["ratio"] = results["pyyaml_avg_us"] / results["handwritten_avg_us"] if results["handwritten_avg_us"] > 0 else 0

    return results


def find_hook_usage() -> list[str]:
    """列舉使用 parse_ticket_frontmatter() 的 Hook 檔案"""
    hook_dir = Path(__file__).parent
    hooks = []

    for hook_file in hook_dir.glob("*.py"):
        if hook_file.name.startswith("_") or hook_file.name == "eval_pyyaml.py":
            continue

        try:
            content = hook_file.read_text(encoding='utf-8')
            if "parse_ticket_frontmatter" in content:
                hooks.append(hook_file.name)
        except Exception:
            pass

    return hooks


def generate_report(samples: list[str], equiv_pass: bool, equiv_diffs: list[str],
                    perf_results: dict, hooks: list[str]) -> str:
    """產出評估報告"""
    report = f"""# PyYAML 替代評估報告

**評估時間**: {datetime.now().isoformat()}

## 評估摘要

本報告評估是否可用 PyYAML 替換手寫 YAML 解析器（parse_ticket_frontmatter）。

## 功能等價性測試結果

- **樣本數**: {len(samples)} 個代表性 Ticket frontmatter
- **測試結論**: {'全部通過' if equiv_pass else '部分失敗'}
- **已知差異**: {len(equiv_diffs)} 個
"""

    if equiv_diffs:
        report += "\n**差異詳情**:\n"
        for diff in equiv_diffs:
            report += f"- {diff}\n"

    if perf_results:
        report += f"""
## 效能微基準測試結果

- **手寫解析器平均時間**: {perf_results['handwritten_avg_us']:.2f} μs/op
- **PyYAML 平均時間**: {perf_results['pyyaml_avg_us']:.2f} μs/op
- **效能比率**: {perf_results['ratio']:.2f}x (PyYAML / 手寫解析器)
- **效能評估**: """

        if perf_results['ratio'] < 2:
            report += "< 2x（建議替換 PyYAML）\n"
        elif perf_results['ratio'] < 5:
            report += "2-5x（進一步評估）\n"
        else:
            report += "> 5x（不建議替換）\n"

    report += f"""
## 依賴整合影響

- **使用 parse_ticket_frontmatter() 的 Hook 數量**: {len(hooks)}
- **受影響 Hook**: {', '.join(hooks) if hooks else '無'}
- **修改複雜度**: 簡單（僅需新增 dependencies 宣告）

## 最終建議

"""

    # 決策邏輯
    # PyYAML 未安裝或等價測試失敗，建議保留
    can_replace = equiv_pass is True and (perf_results is None or perf_results['ratio'] < 5)

    if can_replace:
        report += """**結論**: 建議替換為 PyYAML

**理由**:
1. 功能等價（或差異可接受）
2. 效能評估良好（比率 < 5x）
3. 整合成本低（僅需修改 dependencies 宣告）

**後續行動**:
1. 在 Hook 中引入 PyYAML 依賴（uv inline script dependencies）
2. 將 parse_ticket_frontmatter 改為使用 yaml.safe_load()
3. 保留手寫解析器作為備用實作或移除
4. 執行全量測試確認無迴歸
"""
    else:
        report += """**結論**: 建議保留手寫解析器

**理由**: """
        if not equiv_pass:
            report += "功能等價測試失敗（存在差異）"
        elif perf_results and perf_results['ratio'] >= 5:
            report += "效能衰減顯著（> 5x）"
        report += "\n"

    report += "\n---\n\n_評估完成_\n"
    return report


def main():
    """主流程"""
    print("=" * 60)
    print("PyYAML 替代評估 — W39-002")
    print("=" * 60)

    # Step 1: 蒐集樣本
    print("\n[Step 1] 蒐集 Ticket frontmatter 樣本...")
    samples = collect_samples(max_samples=10)
    print(f"  成功蒐集 {len(samples)} 個樣本")

    if not samples:
        print("  警告：無法蒐集樣本，終止評估")
        return

    # Step 2: 功能等價性測試
    print("\n[Step 2] 執行功能等價性測試...")
    equiv_pass, equiv_diffs = test_functional_equivalence(samples)
    if equiv_pass:
        print("  結果：全部通過 ✓")
    else:
        print(f"  結果：{len(equiv_diffs)} 個差異")

    # Step 3: 效能微基準測試
    print("\n[Step 3] 執行效能微基準測試...")
    perf_results = test_performance(samples)
    if perf_results:
        print(f"  手寫解析器: {perf_results['handwritten_avg_us']:.2f} μs/op")
        print(f"  PyYAML: {perf_results['pyyaml_avg_us']:.2f} μs/op")
        print(f"  效能比率: {perf_results['ratio']:.2f}x")
    else:
        print("  結果：PyYAML 未安裝，跳過測試")

    # Step 4: 依賴整合影響分析
    print("\n[Step 4] 分析依賴整合影響...")
    hooks = find_hook_usage()
    print(f"  找到 {len(hooks)} 個使用 parse_ticket_frontmatter() 的 Hook")

    # Step 5: 產出報告
    print("\n[Step 5] 產出評估報告...")
    report = generate_report(samples, equiv_pass, equiv_diffs, perf_results, hooks)

    # 寫入報告檔案
    report_file = Path(__file__).parent / "pyyaml_evaluation_report.md"
    report_file.write_text(report, encoding='utf-8')
    print(f"  報告已寫入: {report_file}")

    # 列印報告摘要
    print("\n" + "=" * 60)
    print("評估報告摘要:")
    print("=" * 60)
    print(report)


if __name__ == "__main__":
    main()
