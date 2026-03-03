"""測試 plan_parser.py 模組。

測試 Plan 檔案的解析、任務項目識別、欄位提取、類型推斷。
"""

import pytest
from pathlib import Path
from datetime import datetime

# 假設 plan_parser 模組的路徑
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "ticket_system" / "lib"))

from plan_parser import (
    PlanTask,
    PlanParseResult,
    parse_plan,
    _infer_task_type,
    _infer_layer,
    _extract_action_and_target,
    _estimate_complexity,
)


class TestPlanParserInference:
    """測試推斷函式。"""

    def test_infer_task_type_imp(self):
        """測試 IMP 類型推斷。"""
        assert _infer_task_type("建立 Parser 模組") == "IMP"
        assert _infer_task_type("新增驗證功能") == "IMP"
        assert _infer_task_type("實作算法") == "IMP"

    def test_infer_task_type_adj(self):
        """測試 ADJ 類型推斷。"""
        assert _infer_task_type("修改 Parser 邏輯") == "ADJ"
        assert _infer_task_type("調整配置") == "ADJ"
        assert _infer_task_type("修正 bug") == "ADJ"

    def test_infer_task_type_ana(self):
        """測試 ANA 類型推斷。"""
        assert _infer_task_type("分析效能問題") == "ANA"
        assert _infer_task_type("研究最佳實踐") == "ANA"
        assert _infer_task_type("調查系統") == "ANA"

    def test_infer_task_type_doc(self):
        """測試 DOC 類型推斷。"""
        assert _infer_task_type("撰寫文件") == "DOC"
        assert _infer_task_type("更新文件") == "DOC"
        assert _infer_task_type("記錄決策") == "DOC"

    def test_infer_layer_domain(self):
        """測試 Domain 層級推斷。"""
        assert _infer_layer(["lib/domain/model.dart"]) == "Domain"
        assert _infer_layer(["lib/domain/entity.dart"]) == "Domain"

    def test_infer_layer_application(self):
        """測試 Application 層級推斷。"""
        assert _infer_layer(["lib/application/use_case.dart"]) == "Application"
        assert _infer_layer(["lib/application/service.dart"]) == "Application"

    def test_infer_layer_infrastructure(self):
        """測試 Infrastructure 層級推斷。"""
        assert _infer_layer(["lib/infrastructure/repo.dart"]) == "Infrastructure"
        assert _infer_layer(["lib/infrastructure/data_source.dart"]) == "Infrastructure"

    def test_infer_layer_presentation(self):
        """測試 Presentation 層級推斷。"""
        assert _infer_layer(["lib/presentation/widget.dart"]) == "Presentation"
        assert _infer_layer(["lib/presentation/page.dart"]) == "Presentation"

    def test_infer_layer_unknown(self):
        """測試未知層級推斷。"""
        assert _infer_layer(["unknown/path.dart"]) == "待定義"
        assert _infer_layer([]) == "待定義"

    def test_extract_action_and_target(self):
        """測試動作和目標提取。"""
        action, target = _extract_action_and_target("建立 Plan Parser 模組")
        assert action == "建立"
        assert "Plan Parser 模組" in target

    def test_estimate_complexity_basic(self):
        """測試基礎複雜度估算。"""
        # 基礎：5
        assert _estimate_complexity([], "", "IMP") == 5

    def test_estimate_complexity_with_files(self):
        """測試包含檔案的複雜度估算。"""
        # 基礎 5 + 2 個檔案 = 7
        complexity = _estimate_complexity(
            ["lib/a.py", "lib/b.py"],
            "",
            "IMP"
        )
        assert complexity == 7

    def test_estimate_complexity_with_description(self):
        """測試包含描述的複雜度估算。"""
        # 基礎 5 + 長描述 (+1) = 6
        long_desc = "a" * 150
        complexity = _estimate_complexity([], long_desc, "IMP")
        assert complexity == 6


class TestValidMarkdown:
    """測試有效 Markdown 解析。"""

    def test_parse_plan_valid_markdown(self, tmp_path):
        """Given: 有效 Plan 檔案
        When: 解析檔案
        Then: 成功解析並提取標題、描述、任務清單
        """
        plan_content = """# 實作計畫：Plan Parser

## 概述
解析 Plan 檔案並提取任務項目

## 實作步驟

1. 建立 Plan Parser 模組
   - 修改檔案：lib/plan_parser.py
   說明：實作解析器主要邏輯

2. 修改 Ticket Builder 整合
   - 修改檔案：lib/ticket_builder.py
"""

        plan_file = tmp_path / "test_plan.md"
        plan_file.write_text(plan_content, encoding="utf-8")

        result = parse_plan(plan_file)

        assert result.success
        assert result.plan_title == "實作計畫：Plan Parser"
        assert "解析 Plan 檔案" in result.plan_description
        assert len(result.tasks) == 2
        assert result.tasks[0].title == "建立 Plan Parser 模組"
        assert "lib/plan_parser.py" in result.tasks[0].files

    def test_parse_plan_task_type_inference(self, tmp_path):
        """Given: 包含多個任務類型的 Plan 檔案
        When: 解析檔案
        Then: 推斷出正確的任務類型
        """
        plan_content = """# 測試計畫

## 概述
測試任務類型推斷

## 實作步驟

1. 建立 X 模組
   - 修改檔案：lib/x.py

2. 修改 Y 邏輯
   - 修改檔案：lib/y.py

3. 分析 Z 問題
   - 修改檔案：lib/z.py

4. 撰寫文件
   - 修改檔案：README.md
"""

        plan_file = tmp_path / "test_plan.md"
        plan_file.write_text(plan_content, encoding="utf-8")

        result = parse_plan(plan_file)

        assert result.success
        assert len(result.tasks) == 4
        assert result.tasks[0].task_type == "IMP"
        assert result.tasks[1].task_type == "ADJ"
        assert result.tasks[2].task_type == "ANA"
        assert result.tasks[3].task_type == "DOC"

    def test_parse_plan_layer_inference(self, tmp_path):
        """Given: 包含不同層級檔案的 Plan 檔案
        When: 解析檔案
        Then: 推斷出正確的架構層級
        """
        plan_content = """# 測試計畫

## 概述
測試層級推斷

## 實作步驟

1. 建立 Domain 層
   - 修改檔案：lib/domain/model.dart

2. 建立 Application 層
   - 修改檔案：lib/application/use_case.dart

3. 建立 Infrastructure 層
   - 修改檔案：lib/infrastructure/repo.dart

4. 建立 Presentation 層
   - 修改檔案：lib/presentation/widget.dart
"""

        plan_file = tmp_path / "test_plan.md"
        plan_file.write_text(plan_content, encoding="utf-8")

        result = parse_plan(plan_file)

        assert result.success
        assert result.tasks[0].layer == "Domain"
        assert result.tasks[1].layer == "Application"
        assert result.tasks[2].layer == "Infrastructure"
        assert result.tasks[3].layer == "Presentation"

    def test_parse_plan_complex_structure(self, tmp_path):
        """Given: 複雜 Plan 含多層級步驟、子項目、詳細說明
        When: 解析檔案
        Then: 正確解析所有層級
        """
        plan_content = """# 複雜計畫

## 概述
測試複雜結構解析

## 實作步驟

1. 建立核心模組
   - 修改檔案：lib/core/parser.py
   - 修改檔案：lib/core/builder.py
   詳細說明：這是核心模組
   包含兩個主要檔案

2. 建立測試模組
   - 修改檔案：test/test_parser.py
"""

        plan_file = tmp_path / "test_plan.md"
        plan_file.write_text(plan_content, encoding="utf-8")

        result = parse_plan(plan_file)

        assert result.success
        assert len(result.tasks[0].files) == 2
        assert result.tasks[0].complexity > 5  # 多個檔案應該增加複雜度


class TestEdgeCases:
    """測試邊界條件。"""

    def test_parse_plan_file_not_found(self):
        """Given: Plan 檔案路徑不存在
        When: 呼叫 parse_plan
        Then: 返回失敗，提示檔案不存在
        """
        result = parse_plan(Path("nonexistent.md"))

        assert not result.success
        assert "檔案不存在" in result.error_message

    def test_parse_plan_empty_file(self, tmp_path):
        """Given: 空 Plan 檔案
        When: 解析檔案
        Then: 返回失敗
        """
        plan_file = tmp_path / "empty.md"
        plan_file.write_text("", encoding="utf-8")

        result = parse_plan(plan_file)

        assert not result.success
        error_msg = result.error_message
        assert error_msg
        assert "empty" in error_msg.lower() or "空" in error_msg

    def test_parse_plan_no_overview_section(self, tmp_path):
        """Given: Plan 檔案無 ## 概述 區段
        When: 解析檔案
        Then: 仍能解析，但 plan_description 為空
        """
        plan_content = """# 計畫標題

## 實作步驟

1. 建立模組
   - 修改檔案：lib/test.py
"""

        plan_file = tmp_path / "test_plan.md"
        plan_file.write_text(plan_content, encoding="utf-8")

        result = parse_plan(plan_file)

        assert result.success
        assert result.plan_title == "計畫標題"
        assert result.plan_description == ""

    def test_parse_plan_no_implementation_section(self, tmp_path):
        """Given: Plan 檔案無 ## 實作步驟 區段
        When: 解析檔案
        Then: 返回失敗
        """
        plan_content = """# 計畫標題

## 概述
沒有實作步驟區段
"""

        plan_file = tmp_path / "test_plan.md"
        plan_file.write_text(plan_content, encoding="utf-8")

        result = parse_plan(plan_file)

        assert not result.success
        assert "實作步驟" in result.error_message

    def test_parse_plan_invalid_file_extension(self, tmp_path):
        """Given: 檔案副檔名不是 .md
        When: 呼叫 parse_plan
        Then: 返回失敗
        """
        plan_file = tmp_path / "test.txt"
        plan_file.write_text("# 標題\n## 實作步驟\n1. 任務", encoding="utf-8")

        result = parse_plan(plan_file)

        assert not result.success
        assert ".md" in result.error_message


class TestChineseAndSpecialCharacters:
    """測試中文和特殊字元處理。"""

    def test_parse_plan_chinese_english_mixed(self, tmp_path):
        """Given: Plan 檔案包含中英文混合
        When: 解析檔案
        Then: 正確處理中英文，無編碼錯誤
        """
        plan_content = """# 實作計畫：Plan-to-Ticket Generator

## 概述
Implement Plan parser for automatic Ticket generation

## 實作步驟

1. 實作 Plan Parser 模組 (Module Implementation)
   - 修改檔案：lib/plan_parser.py
   說明：Parsing Markdown Plan files with Chinese/English support

2. 修改 Ticket Builder 整合 (Integration with Ticket Builder)
   - 修改檔案：lib/ticket_builder.py
"""

        plan_file = tmp_path / "test_plan.md"
        plan_file.write_text(plan_content, encoding="utf-8")

        result = parse_plan(plan_file)

        assert result.success
        assert len(result.tasks) == 2
        assert "Parser" in result.tasks[0].title

    def test_parse_plan_special_characters_in_title(self, tmp_path):
        """Given: 步驟標題含特殊字元
        When: 解析檔案
        Then: 正確保存標題及特殊字元
        """
        plan_content = """# 計畫

## 概述
測試特殊字元

## 實作步驟

1. 建立 [核心] {模組} - Parser & Builder
   - 修改檔案：lib/parser.py
"""

        plan_file = tmp_path / "test_plan.md"
        plan_file.write_text(plan_content, encoding="utf-8")

        result = parse_plan(plan_file)

        assert result.success
        assert "[核心]" in result.tasks[0].title
        assert "{模組}" in result.tasks[0].title
        assert "&" in result.tasks[0].title

    def test_parse_plan_long_title(self, tmp_path):
        """Given: 步驟標題超過 100 字元
        When: 解析檔案
        Then: 完整保存標題，無截斷
        """
        long_title = "建立" + "X" * 100 + "模組"
        plan_content = f"""# 計畫

## 概述
測試長標題

## 實作步驟

1. {long_title}
   - 修改檔案：lib/test.py
"""

        plan_file = tmp_path / "test_plan.md"
        plan_file.write_text(plan_content, encoding="utf-8")

        result = parse_plan(plan_file)

        assert result.success
        assert result.tasks[0].title == long_title
        assert len(result.tasks[0].title) > 100


class TestMultipleFiles:
    """測試多檔案處理。"""

    def test_parse_plan_multiple_files_per_task(self, tmp_path):
        """Given: 步驟含多個修改檔案
        When: 解析檔案
        Then: 正確識別所有檔案
        """
        plan_content = """# 計畫

## 概述
測試多檔案

## 實作步驟

1. 建立模組
   - 修改檔案：lib/a.py
   - 修改檔案：lib/b.py
   - 修改檔案：test/a_test.py
"""

        plan_file = tmp_path / "test_plan.md"
        plan_file.write_text(plan_content, encoding="utf-8")

        result = parse_plan(plan_file)

        assert result.success
        assert len(result.tasks[0].files) == 3
        assert "lib/a.py" in result.tasks[0].files
        assert "lib/b.py" in result.tasks[0].files
        assert "test/a_test.py" in result.tasks[0].files


class TestComplexityEstimation:
    """測試複雜度估算。"""

    def test_parse_plan_complexity_estimation(self, tmp_path):
        """Given: 步驟的修改檔案數和描述長度
        When: 解析檔案
        Then: 估算出合理的複雜度（範圍 1-15+）
        """
        plan_content = """# 計畫

## 概述
測試複雜度

## 實作步驟

1. 簡單任務
   - 修改檔案：lib/simple.py

2. 複雜任務
   - 修改檔案：lib/a.py
   - 修改檔案：lib/b.py
   - 修改檔案：lib/c.py
   - 修改檔案：lib/d.py
   - 修改檔案：lib/e.py
   詳細說明：這是一個非常複雜的任務，涉及多個檔案的修改，
   需要深入理解系統架構，並且可能需要重構現有的代碼結構。
"""

        plan_file = tmp_path / "test_plan.md"
        plan_file.write_text(plan_content, encoding="utf-8")

        result = parse_plan(plan_file)

        assert result.success
        simple_complexity = result.tasks[0].complexity
        complex_complexity = result.tasks[1].complexity

        # 複雜任務應該有更高的複雜度
        assert complex_complexity > simple_complexity
        assert 1 <= simple_complexity <= 15
        assert 1 <= complex_complexity <= 15


class TestTaskOrdering:
    """測試任務順序。"""

    def test_parse_plan_task_ordering(self, tmp_path):
        """Given: 包含多個任務的 Plan 檔案
        When: 解析檔案
        Then: 任務的 order 屬性正確反映在 Plan 中的順序
        """
        plan_content = """# 計畫

## 概述
測試順序

## 實作步驟

1. 第一個任務
   - 修改檔案：lib/first.py

2. 第二個任務
   - 修改檔案：lib/second.py

3. 第三個任務
   - 修改檔案：lib/third.py
"""

        plan_file = tmp_path / "test_plan.md"
        plan_file.write_text(plan_content, encoding="utf-8")

        result = parse_plan(plan_file)

        assert result.success
        assert result.tasks[0].order == 1
        assert result.tasks[1].order == 2
        assert result.tasks[2].order == 3


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
