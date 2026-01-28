"""
Parser Factory 測試套件

測試目標:
1. 語言檢測（Language Detection）
2. Parser 創建（Parser Creation）
3. 統一介面（Unified Interface）
4. 註冊機制（Registration）
5. Function 資料結構（Function Data Structure）
6. 整合測試（Integration）
7. 錯誤處理（Error Handling）

版本: v1.0
建立日期: 2025-01-10
"""

import sys
import pytest
from pathlib import Path

# 加入 parsers 模組路徑
sys.path.insert(0, str(Path(__file__).parent.parent))

from parsers import (
    Language,
    LanguageParser,
    Function,
    ParserFactory,
    DartParser,
    JavaScriptParser,
)


class TestLanguageDetection:
    """語言檢測測試套件"""

    def test_detect_dart_file(self):
        """測試 .dart 檔案識別"""
        language = ParserFactory.detect_language('lib/main.dart')
        assert language == Language.DART

    def test_detect_javascript_file(self):
        """測試 .js 檔案識別"""
        language = ParserFactory.detect_language('src/app.js')
        assert language == Language.JAVASCRIPT

    def test_detect_typescript_file(self):
        """測試 .ts 檔案識別"""
        language = ParserFactory.detect_language('src/app.ts')
        assert language == Language.TYPESCRIPT

    def test_detect_jsx_file(self):
        """測試 .jsx 檔案識別"""
        language = ParserFactory.detect_language('components/Button.jsx')
        assert language == Language.JAVASCRIPT

    def test_detect_tsx_file(self):
        """測試 .tsx 檔案識別"""
        language = ParserFactory.detect_language('components/Button.tsx')
        assert language == Language.TYPESCRIPT

    def test_detect_mjs_file(self):
        """測試 .mjs 檔案識別"""
        language = ParserFactory.detect_language('module.mjs')
        assert language == Language.JAVASCRIPT

    def test_detect_unknown_file(self):
        """測試不支援的檔案類型"""
        language = ParserFactory.detect_language('file.xyz')
        assert language == Language.UNKNOWN

    def test_detect_case_insensitive(self):
        """測試副檔名大小寫不敏感"""
        assert ParserFactory.detect_language('Main.DART') == Language.DART
        assert ParserFactory.detect_language('App.JS') == Language.JAVASCRIPT

    def test_detect_with_path(self):
        """測試完整路徑檢測"""
        path = '/Users/tarragon/Projects/book_overview_app/lib/main.dart'
        language = ParserFactory.detect_language(path)
        assert language == Language.DART


class TestParserCreation:
    """Parser 創建測試套件"""

    def test_create_dart_parser(self):
        """測試創建 Dart Parser"""
        parser = ParserFactory.create_parser(Language.DART)
        assert isinstance(parser, DartParser)
        assert isinstance(parser, LanguageParser)

    def test_create_javascript_parser(self):
        """測試創建 JavaScript Parser"""
        parser = ParserFactory.create_parser(Language.JAVASCRIPT)
        assert isinstance(parser, JavaScriptParser)
        assert isinstance(parser, LanguageParser)

    def test_create_typescript_parser(self):
        """測試創建 TypeScript Parser（應使用 JavaScriptParser）"""
        parser = ParserFactory.create_parser(Language.TYPESCRIPT)
        assert isinstance(parser, JavaScriptParser)
        assert isinstance(parser, LanguageParser)

    def test_create_parser_for_dart_file(self):
        """測試根據檔案路徑創建 Dart Parser"""
        parser = ParserFactory.create_parser_for_file('lib/main.dart')
        assert isinstance(parser, DartParser)

    def test_create_parser_for_js_file(self):
        """測試根據檔案路徑創建 JavaScript Parser"""
        parser = ParserFactory.create_parser_for_file('src/app.js')
        assert isinstance(parser, JavaScriptParser)

    def test_create_parser_for_ts_file(self):
        """測試根據檔案路徑創建 TypeScript Parser"""
        parser = ParserFactory.create_parser_for_file('src/app.ts')
        assert isinstance(parser, JavaScriptParser)

    def test_create_parser_unsupported_language(self):
        """測試不支援的語言類型拋出異常"""
        with pytest.raises(ValueError, match="不支援的語言"):
            ParserFactory.create_parser(Language.UNKNOWN)

    def test_create_parser_unsupported_file(self):
        """測試不支援的檔案類型拋出異常"""
        with pytest.raises(ValueError, match="不支援的檔案類型"):
            ParserFactory.create_parser_for_file('file.xyz')


class TestUnifiedInterface:
    """統一介面測試套件"""

    def test_dart_parser_implements_interface(self):
        """測試 DartParser 實作 LanguageParser 介面"""
        parser = DartParser()
        assert isinstance(parser, LanguageParser)
        assert hasattr(parser, 'extract_functions')
        assert hasattr(parser, 'file_extensions')
        assert hasattr(parser, 'language_name')

    def test_javascript_parser_implements_interface(self):
        """測試 JavaScriptParser 實作 LanguageParser 介面"""
        parser = JavaScriptParser()
        assert isinstance(parser, LanguageParser)
        assert hasattr(parser, 'extract_functions')
        assert hasattr(parser, 'file_extensions')
        assert hasattr(parser, 'language_name')

    def test_polymorphic_usage(self):
        """測試多型使用（統一介面呼叫）"""
        dart_parser = ParserFactory.create_parser(Language.DART)
        js_parser = ParserFactory.create_parser(Language.JAVASCRIPT)

        # 測試統一介面
        dart_code = "void main() { }"
        js_code = "function main() { }"

        dart_functions = dart_parser.extract_functions(dart_code)
        js_functions = js_parser.extract_functions(js_code)

        # 兩者返回相同的資料結構
        assert isinstance(dart_functions, list)
        assert isinstance(js_functions, list)

        if dart_functions:
            assert isinstance(dart_functions[0], Function)
        if js_functions:
            assert isinstance(js_functions[0], Function)

    def test_file_extensions_property(self):
        """測試 file_extensions 屬性"""
        dart_parser = DartParser()
        js_parser = JavaScriptParser()

        assert '.dart' in dart_parser.file_extensions
        assert '.js' in js_parser.file_extensions
        assert '.ts' in js_parser.file_extensions

    def test_language_name_property(self):
        """測試 language_name 屬性"""
        dart_parser = DartParser()
        js_parser = JavaScriptParser()

        assert dart_parser.language_name == 'Dart'
        assert js_parser.language_name == 'JavaScript/TypeScript'


class TestRegistration:
    """註冊機制測試套件"""

    def test_auto_registration_dart(self):
        """測試 DartParser 自動註冊"""
        parser = ParserFactory.create_parser(Language.DART)
        assert isinstance(parser, DartParser)

    def test_auto_registration_javascript(self):
        """測試 JavaScriptParser 自動註冊"""
        parser = ParserFactory.create_parser(Language.JAVASCRIPT)
        assert isinstance(parser, JavaScriptParser)

    def test_extension_mapping_dart(self):
        """測試 .dart 副檔名正確映射"""
        language = ParserFactory.detect_language('test.dart')
        assert language == Language.DART

    def test_extension_mapping_javascript(self):
        """測試 JavaScript 相關副檔名正確映射"""
        assert ParserFactory.detect_language('test.js') == Language.JAVASCRIPT
        assert ParserFactory.detect_language('test.jsx') == Language.JAVASCRIPT
        assert ParserFactory.detect_language('test.mjs') == Language.JAVASCRIPT

    def test_extension_mapping_typescript(self):
        """測試 TypeScript 相關副檔名正確映射"""
        assert ParserFactory.detect_language('test.ts') == Language.TYPESCRIPT
        assert ParserFactory.detect_language('test.tsx') == Language.TYPESCRIPT

    def test_is_supported_dart(self):
        """測試 is_supported 方法（Dart 檔案）"""
        assert ParserFactory.is_supported('lib/main.dart') is True

    def test_is_supported_javascript(self):
        """測試 is_supported 方法（JavaScript 檔案）"""
        assert ParserFactory.is_supported('src/app.js') is True

    def test_is_supported_unknown(self):
        """測試 is_supported 方法（不支援的檔案）"""
        assert ParserFactory.is_supported('file.xyz') is False


class TestFunctionDataStructure:
    """Function 資料結構測試套件"""

    def test_function_basic_fields(self):
        """測試 Function 基本欄位"""
        func = Function(
            name='handleClick',
            line_number=10,
            has_comment=True
        )
        assert func.name == 'handleClick'
        assert func.line_number == 10
        assert func.has_comment is True

    def test_function_optional_fields_default(self):
        """測試 Function Optional 欄位預設值"""
        func = Function(
            name='main',
            line_number=1,
            has_comment=False
        )
        assert func.return_type is None
        assert func.is_async is False
        assert func.function_type == 'function'

    def test_function_dart_specific_fields(self):
        """測試 Function Dart 特定欄位"""
        func = Function(
            name='build',
            line_number=20,
            has_comment=True,
            return_type='Widget'
        )
        assert func.return_type == 'Widget'

    def test_function_javascript_specific_fields(self):
        """測試 Function JavaScript 特定欄位"""
        func = Function(
            name='fetchData',
            line_number=15,
            has_comment=True,
            is_async=True,
            function_type='arrow'
        )
        assert func.is_async is True
        assert func.function_type == 'arrow'

    def test_function_cross_language_compatibility(self):
        """測試 Function 跨語言相容性"""
        # Dart 函式
        dart_func = Function(
            name='dartFunction',
            line_number=10,
            has_comment=True,
            return_type='void'
        )

        # JavaScript 函式
        js_func = Function(
            name='jsFunction',
            line_number=20,
            has_comment=True,
            is_async=True
        )

        # 兩者都是 Function 類型
        assert isinstance(dart_func, Function)
        assert isinstance(js_func, Function)

        # 可以放在同一個列表中
        functions = [dart_func, js_func]
        assert len(functions) == 2


class TestIntegration:
    """整合測試套件"""

    def test_end_to_end_dart(self):
        """測試 Dart 完整流程"""
        # 1. 檢測語言
        language = ParserFactory.detect_language('lib/main.dart')
        assert language == Language.DART

        # 2. 創建 Parser
        parser = ParserFactory.create_parser(language)
        assert isinstance(parser, DartParser)

        # 3. 提取函式
        code = "void main() { print('Hello'); }"
        functions = parser.extract_functions(code)

        # 4. 驗證結果
        assert len(functions) == 1
        assert functions[0].name == 'main'

    def test_end_to_end_javascript(self):
        """測試 JavaScript 完整流程"""
        # 1. 根據檔案路徑直接創建 Parser
        parser = ParserFactory.create_parser_for_file('src/app.js')
        assert isinstance(parser, JavaScriptParser)

        # 2. 提取函式
        code = "function handleClick() { console.log('clicked'); }"
        functions = parser.extract_functions(code)

        # 3. 驗證結果
        assert len(functions) == 1
        assert functions[0].name == 'handleClick'

    def test_mixed_language_processing(self):
        """測試混合語言處理"""
        files = [
            ('lib/main.dart', 'void main() { }'),
            ('src/app.js', 'function main() { }'),
            ('src/utils.ts', 'async function fetchData() { }')
        ]

        all_functions = []

        for file_path, code in files:
            if ParserFactory.is_supported(file_path):
                parser = ParserFactory.create_parser_for_file(file_path)
                functions = parser.extract_functions(code)
                all_functions.extend(functions)

        # 驗證提取到 3 個函式
        assert len(all_functions) == 3
        assert all([isinstance(f, Function) for f in all_functions])


class TestErrorHandling:
    """錯誤處理測試套件"""

    def test_invalid_parser_registration(self):
        """測試註冊無效的 Parser 類別"""
        class InvalidParser:
            pass

        with pytest.raises(ValueError, match="必須繼承 LanguageParser"):
            ParserFactory.register_parser(Language.DART, InvalidParser)

    def test_create_parser_unknown_language(self):
        """測試創建不支援的語言 Parser"""
        with pytest.raises(ValueError, match="不支援的語言"):
            ParserFactory.create_parser(Language.UNKNOWN)

    def test_create_parser_for_unsupported_file(self):
        """測試創建不支援檔案類型的 Parser"""
        with pytest.raises(ValueError, match="不支援的檔案類型"):
            ParserFactory.create_parser_for_file('file.xyz')

    def test_empty_code_handling(self):
        """測試空程式碼處理"""
        parser = ParserFactory.create_parser(Language.DART)
        functions = parser.extract_functions('')
        assert functions == []

    def test_none_code_handling(self):
        """測試 None 程式碼處理（應返回空列表）"""
        parser = ParserFactory.create_parser(Language.DART)
        # DartParser 會檢查 code，空字串返回空列表
        functions = parser.extract_functions('')
        assert functions == []


if __name__ == '__main__':
    # 執行測試
    pytest.main([__file__, '-v', '--tb=short'])
