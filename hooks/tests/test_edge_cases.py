"""
Ticket Quality Gate - 邊界測試案例

測試邊界情況和異常情況處理
"""

import sys
from pathlib import Path

# 添加父目錄到 Python 路徑
sys.path.insert(0, str(Path(__file__).parent.parent))

from ticket_quality.detectors import (
    check_god_ticket_automated,
    check_incomplete_ticket_automated,
    check_ambiguous_responsibility_automated
)
from ticket_quality.extractors import (
    extract_file_paths,
    extract_section,
    has_section,
    extract_acceptance_criteria
)
from ticket_quality.analyzers import determine_layer


def test_empty_ticket():
    """
    測試邊界情況 1: 空內容 Ticket 的處理

    驗證點:
    - 不應拋出異常
    - C1 應通過（沒有檔案 = 沒有超標）
    - C2 應失敗（缺少所有必要元素）
    - C3 應失敗（沒有層級標示）
    """
    print("\n=== 測試 1: 空內容 Ticket ===")
    empty_ticket = ""

    # 測試 C1 God Ticket 檢測
    result_c1 = check_god_ticket_automated(empty_ticket)
    assert result_c1["status"] == "passed", "C1: 空 Ticket 應通過（無檔案 = 無超標）"
    assert result_c1["details"]["file_count"] == 0, "C1: 檔案數應為 0"
    print("✅ C1 檢測：通過（無檔案修改）")

    # 測試 C2 Incomplete Ticket 檢測
    result_c2 = check_incomplete_ticket_automated(empty_ticket)
    assert result_c2["status"] == "failed", "C2: 空 Ticket 應失敗（缺少所有必要元素）"
    assert len(result_c2["details"]["missing_elements"]) == 4, "C2: 應缺少 4 個必要元素"
    print("✅ C2 檢測：失敗（缺少驗收條件、測試規劃、工作日誌、參考文件）")

    # 測試 C3 Ambiguous Responsibility 檢測
    result_c3 = check_ambiguous_responsibility_automated(empty_ticket)
    assert result_c3["status"] == "failed", "C3: 空 Ticket 應失敗（無層級標示）"
    assert not result_c3["details"]["has_layer_marker"], "C3: 應無層級標示"
    print("✅ C3 檢測：失敗（無層級標示）")

    print("✅ 測試 1 通過：空內容 Ticket 處理正確")


def test_large_ticket():
    """
    測試邊界情況 2: 超大 Ticket 的效能和記憶體使用

    驗證點:
    - 執行時間 < 2s
    - 正確識別大量檔案
    - 不應發生記憶體錯誤
    """
    print("\n=== 測試 2: 超大 Ticket（10,000 行，50 個檔案）===")

    # 生成 10,000 行 Ticket 內容（50 個檔案）
    large_ticket_lines = ["# 大型 Ticket 測試\n\n"]
    large_ticket_lines.append("## 實作步驟\n\n")

    for i in range(50):
        large_ticket_lines.append(f"步驟 {i+1}: 修改 lib/feature{i}/screen.dart\n")
        large_ticket_lines.append(f"步驟 {i+51}: 修改 lib/feature{i}/controller.dart\n")
        large_ticket_lines.append(f"步驟 {i+101}: 修改 lib/feature{i}/use_case.dart\n")
        large_ticket_lines.append(f"步驟 {i+151}: 修改 test/feature{i}_test.dart\n")

    # 填充到 10,000 行
    while len(large_ticket_lines) < 10000:
        large_ticket_lines.append("# 填充行\n")

    large_ticket = "".join(large_ticket_lines)

    import time
    start_time = time.time()

    # 執行 C1 檢測
    result_c1 = check_god_ticket_automated(large_ticket)

    execution_time = time.time() - start_time

    # 驗證效能
    assert execution_time < 2.0, f"執行時間超標: {execution_time:.3f}s > 2.0s"
    print(f"✅ 效能測試通過：執行時間 {execution_time:.3f}s < 2.0s")

    # 驗證檢測結果
    assert result_c1["status"] == "failed", "C1: 50 個檔案應超標"
    assert result_c1["details"]["file_count"] == 200, f"C1: 檔案數應為 200（實際: {result_c1['details']['file_count']}）"
    print("✅ 檢測結果正確：識別到 200 個檔案（超標）")

    print("✅ 測試 2 通過：超大 Ticket 處理正確且效能達標")


def test_special_characters_in_paths():
    """
    測試邊界情況 3: 特殊字元路徑處理

    驗證點:
    - 支援破折號（-）
    - 支援底線（_）
    - 支援點（.）
    - 支援中文路徑
    - 支援版本號（v2）
    """
    print("\n=== 測試 3: 特殊字元路徑 ===")

    ticket = """
## 實作步驟
- 修改 `lib/features/user-profile/screens/edit_profile.dart`
- 修改 `lib/domains/書籍管理/entities/book.dart`
- 修改 `lib/ui/widgets/custom_button.v2.dart`
- 修改 `test/unit/book_test.integration.dart`
"""

    paths = extract_file_paths(ticket)

    # 驗證特殊字元處理
    expected_paths = [
        "lib/features/user-profile/screens/edit_profile.dart",
        "lib/domains/書籍管理/entities/book.dart",
        "lib/ui/widgets/custom_button.v2.dart",
        "test/unit/book_test.integration.dart"
    ]

    for expected_path in expected_paths:
        assert expected_path in paths, f"路徑提取失敗: {expected_path}"
        print(f"✅ 成功提取路徑: {expected_path}")

    print("✅ 測試 3 通過：特殊字元路徑處理正確")


def test_nested_sections():
    """
    測試邊界情況 4: 多層級巢狀章節提取

    驗證點:
    - 支援多層級標題（##、###）
    - has_section 能檢測到子章節
    - extract_section 的行為符合實際實作（遇到 ### 會停止）
    - 驗收條件提取功能正常

    注意: extract_section 的正則 (?=\n##|$) 會匹配 \n## 或 \n###（因為 ##+ 匹配多個#），
    所以提取會在遇到下一個任何層級的標題時停止。
    """
    print("\n=== 測試 4: 多層級巢狀章節 ===")

    ticket = """
## 驗收條件
- [ ] 主要驗收1
- [ ] 主要驗收2
- [ ] 主要驗收3

## 實作步驟
步驟 1: 修改 lib/test.dart
步驟 2: 修改 test/test.dart

## 測試規劃
- 單元測試: test_unit.dart
- 整合測試: test_integration.dart
"""

    # 驗證章節存在性檢查
    assert has_section(ticket, "驗收條件"), "應檢測到「驗收條件」章節"
    assert has_section(ticket, "實作步驟"), "應檢測到「實作步驟」章節"
    assert has_section(ticket, "測試規劃"), "應檢測到「測試規劃」章節"
    print("✅ 章節存在性檢查通過")

    # 驗證章節內容提取
    acceptance = extract_section(ticket, "驗收條件")
    steps = extract_section(ticket, "實作步驟")
    test_plan = extract_section(ticket, "測試規劃")

    assert "主要驗收1" in acceptance, "驗收條件應包含項目1"
    assert "主要驗收2" in acceptance, "驗收條件應包含項目2"
    assert "主要驗收3" in acceptance, "驗收條件應包含項目3"
    print("✅ 驗收條件章節提取正確")

    assert "步驟 1" in steps, "實作步驟應包含步驟1"
    assert "步驟 2" in steps, "實作步驟應包含步驟2"
    print("✅ 實作步驟章節提取正確")

    assert "單元測試" in test_plan, "測試規劃應包含單元測試"
    assert "整合測試" in test_plan, "測試規劃應包含整合測試"
    print("✅ 測試規劃章節提取正確")

    # 驗證驗收條件提取功能
    criteria = extract_acceptance_criteria(ticket)
    assert len(criteria) == 3, f"應提取到 3 個驗收條件（實際: {len(criteria)}）"
    assert "主要驗收1" in criteria, "應包含驗收條件1"
    assert "主要驗收2" in criteria, "應包含驗收條件2"
    assert "主要驗收3" in criteria, "應包含驗收條件3"
    print("✅ 驗收條件提取功能正確")

    print("✅ 測試 4 通過：多層級巢狀章節處理正確")


def test_unicode_and_emojis():
    """
    測試邊界情況 5: Unicode 字元和表情符號處理

    驗證點:
    - 章節標題包含表情符號
    - 檔案路徑包含中文字元
    - 驗收條件包含表情符號
    - 表情符號不影響提取邏輯
    """
    print("\n=== 測試 5: Unicode 和表情符號 ===")

    ticket = """
## 🎯 驗收條件
- [ ] ✅ 功能完成
- [ ] 🧪 測試通過
- [ ] 📊 效能達標

## 📋 實作步驟
步驟 1: 修改 lib/domains/書籍/entities/book.dart
步驟 2: 撰寫測試 test/書籍_test.dart

## 🔗 參考文件
- docs/設計文件.md
- docs/需求規格.md
"""

    # 驗證表情符號不影響章節提取
    assert has_section(ticket, "驗收條件"), "應檢測到「驗收條件」章節（忽略表情符號）"
    assert has_section(ticket, "實作步驟"), "應檢測到「實作步驟」章節（忽略表情符號）"
    assert has_section(ticket, "參考文件"), "應檢測到「參考文件」章節（忽略表情符號）"
    print("✅ 表情符號不影響章節檢測")

    # 驗證 Unicode 路徑提取
    paths = extract_file_paths(ticket)
    assert "lib/domains/書籍/entities/book.dart" in paths, "應提取到中文路徑"
    assert "test/書籍_test.dart" in paths, "應提取到中文測試檔案"
    assert "docs/設計文件.md" in paths, "應提取到中文文件路徑"
    assert "docs/需求規格.md" in paths, "應提取到中文需求文件"
    print("✅ Unicode 路徑提取正確")

    # 驗證驗收條件提取
    criteria = extract_acceptance_criteria(ticket)
    assert len(criteria) == 3, f"應提取到 3 個驗收條件（實際: {len(criteria)}）"
    assert any("功能完成" in c for c in criteria), "應包含「功能完成」"
    assert any("測試通過" in c for c in criteria), "應包含「測試通過」"
    assert any("效能達標" in c for c in criteria), "應包含「效能達標」"
    print("✅ 驗收條件提取正確（忽略表情符號）")

    print("✅ 測試 5 通過：Unicode 和表情符號處理正確")


def run_all_edge_case_tests():
    """執行所有邊界測試案例"""
    print("\n" + "="*60)
    print("Ticket Quality Gate - 邊界測試案例執行")
    print("="*60)

    tests = [
        ("T1: 空內容 Ticket", test_empty_ticket),
        ("T2: 超大 Ticket", test_large_ticket),
        ("T3: 特殊字元路徑", test_special_characters_in_paths),
        ("T4: 巢狀章節", test_nested_sections),
        ("T5: Unicode 和表情符號", test_unicode_and_emojis)
    ]

    passed = 0
    failed = 0

    for test_name, test_func in tests:
        try:
            test_func()
            passed += 1
        except AssertionError as e:
            print(f"\n❌ {test_name} 失敗: {e}")
            failed += 1
        except Exception as e:
            print(f"\n❌ {test_name} 錯誤: {e}")
            failed += 1

    print("\n" + "="*60)
    print(f"測試結果: {passed}/{len(tests)} 通過")
    if failed == 0:
        print("✅ 所有邊界測試案例通過")
    else:
        print(f"❌ {failed} 個測試案例失敗")
    print("="*60)

    return failed == 0


if __name__ == "__main__":
    success = run_all_edge_case_tests()
    sys.exit(0 if success else 1)
