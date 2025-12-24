"""
語言解析器模組

提供多種程式語言的函式識別和註解檢查功能

支援的語言:
- Dart (dart_parser.py)
- JavaScript/TypeScript (javascript_parser.py)

使用範例:
    from parsers import ParserFactory

    # 根據檔案路徑自動選擇 Parser
    parser = ParserFactory.create_parser_for_file('lib/main.dart')
    functions = parser.extract_functions(code)

    # 檢查檔案是否支援
    if ParserFactory.is_supported('src/app.js'):
        parser = ParserFactory.create_parser_for_file('src/app.js')
"""

from .base import Language, LanguageParser, Function, ParserFactory
from .dart_parser import DartParser, DART_KEYWORDS
from .javascript_parser import JavaScriptParser, JS_KEYWORDS


# 自動註冊 Parser
# 注意: TypeScript 和 JavaScript 共用 JavaScriptParser
# 需要明確指定副檔名以避免衝突

# Dart: .dart
ParserFactory.register_parser(Language.DART, DartParser)

# JavaScript: .js, .jsx, .mjs
ParserFactory.register_parser(Language.JAVASCRIPT, JavaScriptParser,
                              extensions={'.js', '.jsx', '.mjs'})

# TypeScript: .ts, .tsx（共用 JavaScriptParser）
ParserFactory.register_parser(Language.TYPESCRIPT, JavaScriptParser,
                              extensions={'.ts', '.tsx'})


__all__ = [
    # 核心類別
    'Language',
    'LanguageParser',
    'Function',
    'ParserFactory',

    # Parser 實作
    'DartParser',
    'JavaScriptParser',

    # 關鍵字集合
    'DART_KEYWORDS',
    'JS_KEYWORDS',
]
