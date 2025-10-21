"""
Ticket Quality Gate Hook - 基礎功能測試

測試 Hook 系統的基本功能
"""

import sys
from pathlib import Path

# 加入模組路徑
sys.path.insert(0, str(Path(__file__).parent.parent))

from ticket_quality.extractors import (
    has_section,
    extract_section,
    extract_acceptance_criteria,
    extract_file_paths,
    count_steps
)
from ticket_quality.analyzers import (
    determine_layer,
    calculate_layer_span,
    estimate_hours
)
from ticket_quality.detectors import (
    check_god_ticket_automated,
    check_incomplete_ticket_automated,
    check_ambiguous_responsibility_automated
)


def test_has_section():
    """測試章節存在性檢查"""
    content = """
# Test Ticket

## 驗收條件

- Item 1
- Item 2

## 參考文件

- docs/test.md
"""
    assert has_section(content, "驗收條件") == True
    assert has_section(content, "參考文件") == True
    assert has_section(content, "不存在的章節") == False
    print("✅ test_has_section 通過")


def test_extract_section():
    """測試章節內容提取"""
    content = """
# Test Ticket

## 驗收條件

- Item 1
- Item 2

## 參考文件

- docs/test.md
"""
    section = extract_section(content, "驗收條件")
    assert "Item 1" in section
    assert "Item 2" in section
    print("✅ test_extract_section 通過")


def test_extract_acceptance_criteria():
    """測試驗收條件提取"""
    content = """
## 驗收條件

- [ ] 條件 1
- [ ] 條件 2
- [ ] 條件 3
"""
    criteria = extract_acceptance_criteria(content)
    assert len(criteria) == 3
    assert "條件 1" in criteria
    print("✅ test_extract_acceptance_criteria 通過")


def test_extract_file_paths():
    """測試檔案路徑提取"""
    content = """
## 實作步驟

步驟 1: 修改 lib/domain/entities/book.dart
步驟 2: 修改 `lib/domain/value_objects/isbn.dart`
步驟 3: 新增測試 test/domain/book_test.dart

修改檔案:
- lib/ui/widgets/book_list.dart
"""
    paths = extract_file_paths(content)
    assert len(paths) >= 3
    assert "lib/domain/entities/book.dart" in paths
    assert "lib/domain/value_objects/isbn.dart" in paths
    assert "test/domain/book_test.dart" in paths
    print(f"✅ test_extract_file_paths 通過（提取了 {len(paths)} 個路徑）")


def test_determine_layer():
    """測試層級判斷"""
    assert determine_layer("lib/ui/widgets/book_list.dart") == 1
    assert determine_layer("lib/application/book_controller.dart") == 2
    assert determine_layer("lib/usecases/get_book.dart") == 3
    assert determine_layer("lib/domain/events/book_created.dart") == 4
    assert determine_layer("lib/domain/entities/book.dart") == 5
    assert determine_layer("lib/infrastructure/database/db.dart") == 0
    print("✅ test_determine_layer 通過")


def test_calculate_layer_span():
    """測試層級跨度計算"""
    assert calculate_layer_span([1, 2, 3]) == 3
    assert calculate_layer_span([1, 5]) == 5
    assert calculate_layer_span([3]) == 1
    assert calculate_layer_span([]) == 0
    print("✅ test_calculate_layer_span 通過")


def test_estimate_hours():
    """測試工時預估"""
    # 10 步驟，5 檔案，2 層級跨度
    hours = estimate_hours(10, 5, 2)
    # 10*0.5 + 5*0.5 + 2*2 = 5 + 2.5 + 4 = 11.5 → 11
    assert hours == 11
    print(f"✅ test_estimate_hours 通過（預估 {hours} 小時）")


def test_c2_incomplete_ticket():
    """測試 C2 Incomplete Ticket 檢測"""
    # 缺少驗收條件的 Ticket
    content = """
## 📋 實作步驟

步驟 1: 修改 lib/domain/entities/book.dart
步驟 2: 撰寫測試 test/domain/book_test.dart

## 🔗 參考文件

- docs/app-requirements-spec.md
"""
    result = check_incomplete_ticket_automated(content)
    assert result["status"] == "failed"
    assert "acceptance_criteria" in result["details"]["missing_elements"]
    print("✅ test_c2_incomplete_ticket 通過")


def test_c1_god_ticket():
    """測試 C1 God Ticket 檢測（簡化版）"""
    # 建立一個層級跨度超標的 Ticket
    content = """
## 📋 實作步驟

步驟 1: 修改 lib/domain/entities/rating.dart
步驟 2: 修改 lib/usecases/calculate_rating.dart
步驟 3: 修改 lib/application/rating_controller.dart
步驟 4: 修改 lib/ui/widgets/rating_display.dart
步驟 5: 新增測試 test/domain/rating_test.dart
"""
    result = check_god_ticket_automated(content)
    # 應該檢測到層級跨度超標（Layer 5 → 1，跨 5 層）
    assert result["details"]["layer_span"] > 1
    print(f"✅ test_c1_god_ticket 通過（層級跨度: {result['details']['layer_span']}）")


def test_c3_ambiguous_responsibility():
    """測試 C3 Ambiguous Responsibility 檢測"""
    # 沒有層級標示的 Ticket
    content = """
## 📋 實作步驟

步驟 1: 修改 lib/domain/entities/book.dart
步驟 2: 撰寫測試 test/domain/book_test.dart
"""
    result = check_ambiguous_responsibility_automated(content)
    assert result["status"] == "failed"
    assert result["details"]["has_layer_marker"] == False
    print("✅ test_c3_ambiguous_responsibility 通過")


def run_all_tests():
    """執行所有測試"""
    print("\n" + "="*60)
    print("開始執行基礎功能測試")
    print("="*60 + "\n")

    try:
        # Extractors 測試
        print("【Extractors 模組測試】")
        test_has_section()
        test_extract_section()
        test_extract_acceptance_criteria()
        test_extract_file_paths()
        print()

        # Analyzers 測試
        print("【Analyzers 模組測試】")
        test_determine_layer()
        test_calculate_layer_span()
        test_estimate_hours()
        print()

        # Detectors 測試
        print("【Detectors 模組測試】")
        test_c2_incomplete_ticket()
        test_c1_god_ticket()
        test_c3_ambiguous_responsibility()
        print()

        print("="*60)
        print("✅ 所有基礎功能測試通過！")
        print("="*60)
        return 0

    except AssertionError as e:
        print(f"\n❌ 測試失敗: {e}")
        import traceback
        traceback.print_exc()
        return 1
    except Exception as e:
        print(f"\n🔥 測試執行錯誤: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(run_all_tests())
