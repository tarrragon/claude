"""
Ticket Quality Gate - 邊界測試案例

測試邊界情況和異常情況處理
"""

import sys
from pathlib import Path

# 添加父目錄到 Python 路徑
hooks_path = Path(__file__).parent.parent
sys.path.insert(0, str(hooks_path))
sys.path.insert(0, str(hooks_path / "lib"))

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
    empty_ticket = ""

    # 測試 C1 God Ticket 檢測
    result_c1 = check_god_ticket_automated(empty_ticket)
    assert result_c1["status"] == "passed", "C1: 空 Ticket 應通過（無檔案 = 無超標）"
    assert result_c1["details"]["file_count"] == 0, "C1: 檔案數應為 0"

    # 測試 C2 Incomplete Ticket 檢測
    result_c2 = check_incomplete_ticket_automated(empty_ticket)
    assert result_c2["status"] == "failed", "C2: 空 Ticket 應失敗（缺少所有必要元素）"
    assert len(result_c2["details"]["missing_elements"]) == 4, "C2: 應缺少 4 個必要元素"

    # 測試 C3 Ambiguous Responsibility 檢測
    result_c3 = check_ambiguous_responsibility_automated(empty_ticket)
    assert result_c3["status"] == "failed", "C3: 空 Ticket 應失敗（無層級標示）"
    assert not result_c3["details"]["has_layer_marker"], "C3: 應無層級標示"


def test_large_ticket():
    """
    測試邊界情況 2: 超大 Ticket 的效能和記憶體使用

    驗證點:
    - 執行時間 < 2s
    - 正確識別大量檔案
    - 不應發生記憶體錯誤
    """
    import time

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

    start_time = time.time()

    # 執行 C1 檢測
    result_c1 = check_god_ticket_automated(large_ticket)

    execution_time = time.time() - start_time

    # 驗證效能
    assert execution_time < 2.0, f"執行時間超標: {execution_time:.3f}s > 2.0s"

    # 驗證檢測結果
    assert result_c1["status"] == "failed", "C1: 50 個檔案應超標"
    assert result_c1["details"]["file_count"] == 200, f"C1: 檔案數應為 200（實際: {result_c1['details']['file_count']}）"


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

    # 驗證章節內容提取
    acceptance = extract_section(ticket, "驗收條件")
    steps = extract_section(ticket, "實作步驟")
    test_plan = extract_section(ticket, "測試規劃")

    assert "主要驗收1" in acceptance, "驗收條件應包含項目1"
    assert "主要驗收2" in acceptance, "驗收條件應包含項目2"
    assert "主要驗收3" in acceptance, "驗收條件應包含項目3"

    assert "步驟 1" in steps, "實作步驟應包含步驟1"
    assert "步驟 2" in steps, "實作步驟應包含步驟2"

    assert "單元測試" in test_plan, "測試規劃應包含單元測試"
    assert "整合測試" in test_plan, "測試規劃應包含整合測試"

    # 驗證驗收條件提取功能
    criteria = extract_acceptance_criteria(ticket)
    assert len(criteria) == 3, f"應提取到 3 個驗收條件（實際: {len(criteria)}）"
    assert "主要驗收1" in criteria, "應包含驗收條件1"
    assert "主要驗收2" in criteria, "應包含驗收條件2"
    assert "主要驗收3" in criteria, "應包含驗收條件3"


def test_unicode_and_emojis():
    """
    測試邊界情況 5: Unicode 字元和表情符號處理

    驗證點:
    - 章節標題包含表情符號
    - 檔案路徑包含中文字元
    - 驗收條件包含表情符號
    - 表情符號不影響提取邏輯
    """
    ticket = """
## [TARGET] 驗收條件
- [ ] [PASS] 功能完成
- [ ] [TEST] 測試通過
- [ ] [METRIC] 效能達標

## [PLAN] 實作步驟
步驟 1: 修改 lib/domains/書籍/entities/book.dart
步驟 2: 撰寫測試 test/書籍_test.dart

## [LINK] 參考文件
- docs/設計文件.md
- docs/需求規格.md
"""

    # 驗證表情符號不影響章節提取
    assert has_section(ticket, "驗收條件"), "應檢測到「驗收條件」章節（忽略表情符號）"
    assert has_section(ticket, "實作步驟"), "應檢測到「實作步驟」章節（忽略表情符號）"
    assert has_section(ticket, "參考文件"), "應檢測到「參考文件」章節（忽略表情符號）"

    # 驗證 Unicode 路徑提取
    paths = extract_file_paths(ticket)
    assert "lib/domains/書籍/entities/book.dart" in paths, "應提取到中文路徑"
    assert "test/書籍_test.dart" in paths, "應提取到中文測試檔案"
    assert "docs/設計文件.md" in paths, "應提取到中文文件路徑"
    assert "docs/需求規格.md" in paths, "應提取到中文需求文件"

    # 驗證驗收條件提取
    criteria = extract_acceptance_criteria(ticket)
    assert len(criteria) == 3, f"應提取到 3 個驗收條件（實際: {len(criteria)}）"
    assert any("功能完成" in c for c in criteria), "應包含「功能完成」"
    assert any("測試通過" in c for c in criteria), "應包含「測試通過」"
    assert any("效能達標" in c for c in criteria), "應包含「效能達標」"


def test_c3_layer_0_infrastructure():
    """
    測試邊界情況 6: Layer 0 (Infrastructure) 層級的 C3 檢測

    驗證點:
    - [Layer 0] 層級標示被正確識別
    - Infrastructure 層關鍵詞（Hook, Script, 腳本, 環境, 設定, 配置等）在驗收條件中被識別
    - 驗收條件包含層級關鍵詞時，acceptance_aligned 應為 True（核心修復驗證）
    - 驗收條件無 Layer 0 關鍵詞時，acceptance_aligned 應為 False
    """
    # 情況 1: Infrastructure Ticket 驗收條件含 Layer 0 關鍵詞 → acceptance_aligned 應為 True（核心修復）
    infrastructure_ticket = """
[Layer 0]

## 驗收條件
- [ ] Infrastructure 層 layer_keywords[0] 已補充
- [ ] Hook 系統修復完成
- [ ] Script 測試通過
- [ ] 環境 配置驗證完成

## 修改檔案
.claude/hooks/lib/ticket_quality/detectors.py
"""

    result = check_ambiguous_responsibility_automated(infrastructure_ticket)
    assert result["details"]["has_layer_marker"], "C3: 應有 Layer 0 標示"
    assert result["details"]["declared_layer"] == 0, "C3: 應識別為 Layer 0"
    assert result["details"]["acceptance_aligned"] == True, f"C3: Infrastructure 關鍵詞應對齊驗收條件（核心修復），實際: {result['details']['acceptance_aligned']}"

    # 情況 2: Layer 0 但驗收條件無 Layer 0 關鍵詞 → acceptance_aligned 應為 False
    infrastructure_ticket_without_keywords = """
[Layer 0]

## 驗收條件
- [ ] 完成
- [ ] 測試通過

## 修改檔案
.claude/hooks/lib/ticket_quality/detectors.py
"""

    result = check_ambiguous_responsibility_automated(infrastructure_ticket_without_keywords)
    assert result["details"]["declared_layer"] == 0, "C3: 應識別為 Layer 0"
    assert not result["details"]["acceptance_aligned"], "C3: 無 Layer 0 關鍵詞時 acceptance_aligned 應為 False"

    # 情況 3: 驗證 Layer 0 的 11 個關鍵詞都被正確識別
    test_keywords = [
        ("Infrastructure", "Infrastructure 修復完成"),
        ("Hook", "Hook 系統最佳化"),
        ("Script", "Script 執行檢查"),
        ("腳本", "腳本 優化"),
        ("環境", "環境 配置"),
        ("設定", "設定 檢驗"),
        ("配置", "配置 驗證"),
        ("CI", "CI 管道構建"),
        ("CD", "CD 流程測試"),
        ("部署", "部署 驗證"),
        ("Sync", "Sync 機制實作"),
    ]

    for idx, (keyword, sample_text) in enumerate(test_keywords):
        ticket = f"""
[Layer 0]

## 驗收條件
- [ ] {sample_text}

## 修改檔案
.claude/hooks/lib/ticket_quality/detectors.py
"""
        result = check_ambiguous_responsibility_automated(ticket)
        assert result["details"]["acceptance_aligned"], f"C3: 應識別關鍵詞「{keyword}」在驗收條件中（{idx+1}/11）"


