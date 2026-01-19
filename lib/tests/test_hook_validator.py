#!/usr/bin/env python3
"""
hook_validator 模組單元測試

測試 Hook 合規性驗證器的各項功能。
"""

import unittest
import tempfile
import json
from pathlib import Path
from unittest.mock import patch, MagicMock
import sys

# 添加 lib 目錄到路徑
sys.path.insert(0, str(Path(__file__).parent.parent))

from hook_validator import (
    HookValidator,
    ValidationIssue,
    ValidationResult,
    validate_hook,
    validate_all_hooks,
    format_validation_report,
)


class TestValidationIssue(unittest.TestCase):
    """測試 ValidationIssue 資料類別"""

    def test_basic_issue(self):
        """測試基本問題建立"""
        issue = ValidationIssue(
            level="error",
            message="Test error"
        )
        self.assertEqual(issue.level, "error")
        self.assertEqual(issue.message, "Test error")
        self.assertIsNone(issue.line)
        self.assertIsNone(issue.suggestion)

    def test_issue_with_all_fields(self):
        """測試包含所有欄位的問題"""
        issue = ValidationIssue(
            level="warning",
            message="Test warning",
            line=42,
            suggestion="Do something"
        )
        self.assertEqual(issue.level, "warning")
        self.assertEqual(issue.line, 42)
        self.assertEqual(issue.suggestion, "Do something")


class TestValidationResult(unittest.TestCase):
    """測試 ValidationResult 資料類別"""

    def test_compliant_result(self):
        """測試合規結果"""
        result = ValidationResult(
            hook_path="/path/to/hook.py",
            issues=[]
        )
        self.assertTrue(result.is_compliant)

    def test_non_compliant_with_error(self):
        """測試有 error 的不合規結果"""
        result = ValidationResult(
            hook_path="/path/to/hook.py",
            issues=[
                ValidationIssue(level="error", message="Critical issue")
            ]
        )
        self.assertFalse(result.is_compliant)

    def test_non_compliant_with_warning_only(self):
        """測試只有 warning 的結果（應該合規）"""
        result = ValidationResult(
            hook_path="/path/to/hook.py",
            issues=[
                ValidationIssue(level="warning", message="Minor issue")
            ]
        )
        self.assertTrue(result.is_compliant)


class TestHookValidatorImports(unittest.TestCase):
    """測試 Hook 導入檢查"""

    def setUp(self):
        """設定測試環境"""
        self.validator = HookValidator()

    def test_missing_hook_io_import(self):
        """測試缺少 hook_io 導入"""
        content = """
import json
import sys

# Hook 程式碼
"""
        issues = self.validator.check_lib_imports(content)
        self.assertTrue(
            any(
                issue.level == "warning" and "hook_io" in issue.message
                for issue in issues
            )
        )

    def test_hook_io_import_detected(self):
        """測試成功檢測 hook_io 導入"""
        content = """
from hook_io import read_hook_input, write_hook_output
import json
"""
        issues = self.validator.check_lib_imports(content)
        self.assertFalse(
            any(
                issue.level == "warning" and "hook_io" in issue.message
                for issue in issues
            )
        )

    def test_hook_io_lib_import_detected(self):
        """測試檢測 lib.hook_io 導入"""
        content = """
from lib.hook_io import read_hook_input
"""
        issues = self.validator.check_lib_imports(content)
        self.assertFalse(
            any(
                issue.level == "warning" and "hook_io" in issue.message
                for issue in issues
            )
        )

    def test_missing_hook_logging_import(self):
        """測試缺少 hook_logging 導入"""
        content = """
from hook_io import read_hook_input
# 沒有 hook_logging
"""
        issues = self.validator.check_lib_imports(content)
        self.assertTrue(
            any(
                issue.level == "info" and "hook_logging" in issue.message
                for issue in issues
            )
        )

    def test_config_loader_detection(self):
        """測試檢測配置載入需求"""
        # 應該檢測到需要 config_loader
        content = """
from hook_io import read_hook_input

config = load_config("agents")
"""
        issues = self.validator.check_lib_imports(content)
        self.assertTrue(
            any(
                "config_loader" in issue.message
                for issue in issues
            )
        )

    def test_git_utils_detection(self):
        """測試檢測 Git 操作需求"""
        content = """
from hook_io import read_hook_input

branch = get_current_branch()
"""
        issues = self.validator.check_lib_imports(content)
        self.assertTrue(
            any(
                "git_utils" in issue.message
                for issue in issues
            )
        )


class TestHookValidatorOutput(unittest.TestCase):
    """測試 Hook 輸出格式檢查"""

    def setUp(self):
        """設定測試環境"""
        self.validator = HookValidator()

    def test_good_output_format(self):
        """測試推薦的輸出格式"""
        content = """
from hook_io import write_hook_output

output = create_pretooluse_output("allow", "OK")
write_hook_output(output)
"""
        issues = self.validator.check_output_format(content)
        # 應該沒有關於輸出格式的警告
        self.assertFalse(
            any(
                "write_hook_output" in issue.message or "print(json" in issue.message
                for issue in issues
                if issue.level == "warning"
            )
        )

    def test_bad_output_format(self):
        """測試不推薦的輸出格式"""
        content = """
import json
import sys

output = {"decision": "allow"}
print(json.dumps(output))
"""
        issues = self.validator.check_output_format(content)
        self.assertTrue(
            any(
                "json.dumps" in issue.message
                for issue in issues
                if issue.level == "warning"
            )
        )


class TestHookValidatorNaming(unittest.TestCase):
    """測試命名規範檢查"""

    def setUp(self):
        """設定測試環境"""
        self.validator = HookValidator()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)

    def tearDown(self):
        """清理臨時檔案"""
        self.temp_dir.cleanup()

    def test_valid_kebab_case(self):
        """測試有效的 kebab-case 命名"""
        hook_path = self.temp_path / "check-file-permissions.py"
        hook_path.touch()

        issues = self.validator.check_naming_convention(hook_path)
        # 應該沒有命名規範的警告
        self.assertFalse(
            any(
                "不符合規範" in issue.message
                for issue in issues
            )
        )

    def test_valid_snake_case(self):
        """測試有效的 snake_case 命名"""
        hook_path = self.temp_path / "check_file_permissions.py"
        hook_path.touch()

        issues = self.validator.check_naming_convention(hook_path)
        self.assertFalse(
            any(
                "不符合規範" in issue.message
                for issue in issues
            )
        )

    def test_invalid_naming(self):
        """測試無效的命名"""
        hook_path = self.temp_path / "CheckFilePermissions.py"
        hook_path.touch()

        issues = self.validator.check_naming_convention(hook_path)
        self.assertTrue(
            any(
                "不符合規範" in issue.message
                for issue in issues
            )
        )

    def test_vague_name(self):
        """測試過於簡略的名稱"""
        hook_path = self.temp_path / "hook.py"
        hook_path.touch()

        issues = self.validator.check_naming_convention(hook_path)
        self.assertTrue(
            any(
                "功能描述" in issue.message
                for issue in issues
            )
        )


class TestHookValidatorTesting(unittest.TestCase):
    """測試測試檔案存在性檢查"""

    def setUp(self):
        """設定測試環境"""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)

        # 建立目錄結構
        (self.temp_path / ".claude" / "hooks").mkdir(parents=True)
        (self.temp_path / ".claude" / "lib" / "tests").mkdir(parents=True)

        self.validator = HookValidator(str(self.temp_path))

    def tearDown(self):
        """清理臨時檔案"""
        self.temp_dir.cleanup()

    def test_test_file_exists(self):
        """測試測試檔案存在"""
        hook_path = self.temp_path / ".claude" / "hooks" / "my_hook.py"
        hook_path.touch()

        test_file = self.temp_path / ".claude" / "lib" / "tests" / "test_my_hook.py"
        test_file.touch()

        issues = self.validator.check_test_exists(hook_path)
        self.assertFalse(
            any(issue.level == "info" for issue in issues)
        )

    def test_test_file_missing(self):
        """測試測試檔案缺失"""
        hook_path = self.temp_path / ".claude" / "hooks" / "my_hook.py"
        hook_path.touch()

        issues = self.validator.check_test_exists(hook_path)
        self.assertTrue(
            any("未找到對應的測試檔案" in issue.message for issue in issues)
        )


class TestHookValidatorIntegration(unittest.TestCase):
    """整合測試"""

    def setUp(self):
        """設定測試環境"""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)

        # 建立目錄結構
        (self.temp_path / ".claude" / "hooks").mkdir(parents=True)
        (self.temp_path / ".claude" / "lib" / "tests").mkdir(parents=True)

        self.validator = HookValidator(str(self.temp_path))

    def tearDown(self):
        """清理臨時檔案"""
        self.temp_dir.cleanup()

    def test_validate_good_hook(self):
        """測試驗證合規的 Hook"""
        hook_path = self.temp_path / ".claude" / "hooks" / "check-permissions.py"
        hook_content = """#!/usr/bin/env python3
from hook_io import read_hook_input, write_hook_output
from hook_logging import setup_hook_logging
from git_utils import get_current_branch

logger = setup_hook_logging("check-permissions")
input_data = read_hook_input()
output = {"decision": "allow"}
write_hook_output(output)
"""
        hook_path.write_text(hook_content)

        # 建立測試檔案
        test_file = self.temp_path / ".claude" / "lib" / "tests" / "test_check_permissions.py"
        test_file.touch()

        result = self.validator.validate_hook(str(hook_path))
        # 不應該有 error，可能有 info（缺少的功能）
        self.assertTrue(
            all(issue.level != "error" for issue in result.issues)
        )

    def test_validate_bad_hook(self):
        """測試驗證不合規的 Hook"""
        hook_path = self.temp_path / ".claude" / "hooks" / "bad_hook.py"
        hook_content = """
import json
# 缺少 hook_io 導入
output = {"decision": "allow"}
print(json.dumps(output))
"""
        hook_path.write_text(hook_content)

        result = self.validator.validate_hook(str(hook_path))
        # 應該有 warning（缺少 hook_io 或不推薦的輸出方式）
        self.assertTrue(
            any(issue.level == "warning" for issue in result.issues)
        )

    def test_validate_all_hooks(self):
        """測試驗證所有 Hook"""
        # 建立多個 Hook
        hooks = [
            ("hook1.py", "from hook_io import write_hook_output\n"),
            ("hook2.py", "import json\n"),
        ]

        for name, content in hooks:
            hook_path = self.temp_path / ".claude" / "hooks" / name
            hook_path.write_text(content)

        results = self.validator.validate_all_hooks()
        self.assertEqual(len(results), 2)


class TestFormatValidationReport(unittest.TestCase):
    """測試報告格式化"""

    def test_format_report_empty(self):
        """測試格式化空報告"""
        results = []
        report = format_validation_report(results)
        self.assertIn("Hook 合規性驗證報告", report)
        self.assertIn("總數: 0", report)

    def test_format_report_with_results(self):
        """測試格式化包含結果的報告"""
        results = [
            ValidationResult(
                hook_path="/path/to/hook1.py",
                issues=[
                    ValidationIssue(level="error", message="Test error")
                ]
            ),
            ValidationResult(
                hook_path="/path/to/hook2.py",
                issues=[]
            ),
        ]
        report = format_validation_report(results)
        self.assertIn("總數: 2", report)
        self.assertIn("合規: 1", report)
        self.assertIn("不合規: 1", report)


class TestPublicAPI(unittest.TestCase):
    """測試公開 API"""

    def test_validate_hook_api(self):
        """測試 validate_hook 公開函式"""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            (temp_path / ".claude" / "lib" / "tests").mkdir(parents=True)

            hook_path = temp_path / ".claude" / "hooks" / "test.py"
            hook_path.parent.mkdir(exist_ok=True)
            hook_path.write_text("from hook_io import write_hook_output\n")

            # 應該能成功呼叫
            result = validate_hook(str(hook_path), str(temp_path))
            self.assertIsInstance(result, ValidationResult)

    def test_validate_all_hooks_api(self):
        """測試 validate_all_hooks 公開函式"""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            hooks_dir = temp_path / ".claude" / "hooks"
            hooks_dir.mkdir(parents=True)

            # 建立測試 Hook
            (hooks_dir / "test.py").write_text("# Hook\n")

            results = validate_all_hooks(str(hooks_dir), str(temp_path))
            self.assertIsInstance(results, list)


if __name__ == "__main__":
    unittest.main()
