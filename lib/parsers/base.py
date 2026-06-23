"""
語言解析器抽象基類和工廠模式

用途: 提供統一的 Parser 介面，支援多種程式語言

核心類別:
1. Language - 語言類型枚舉
2. Function - 統一的函式資料結構
3. LanguageParser - 抽象基類（所有 Parser 必須繼承）
4. ParserFactory - 工廠類別（創建和管理 Parser）

設計理念:
- 語言無關: 統一介面，支援多型
- 零配置: 自動註冊機制
- 可擴展: 新增語言只需繼承 LanguageParser

版本: v1.0
建立日期: 2025-01-10
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Set, Type


class Language(Enum):
    """
    支援的程式語言類型

    每個語言對應一個 Parser 實作

    Attributes:
        DART: Dart 語言
        JAVASCRIPT: JavaScript 語言
        TYPESCRIPT: TypeScript 語言（使用 JavaScriptParser）
        UNKNOWN: 不支援的語言
    """
    DART = 'dart'
    JAVASCRIPT = 'javascript'
    TYPESCRIPT = 'typescript'
    UNKNOWN = 'unknown'


@dataclass
class Function:
    """
    統一的函式資料結構（跨語言）

    此資料類別用於表示不同語言中的函式定義
    使用 Optional 欄位支援語言特定屬性

    Attributes:
        name: 函式名稱（如 handleBookAdded）
        line_number: 函式定義所在行號（從 1 開始）
        has_comment: 是否有完整的追溯註解
        return_type: 回傳類型（可選，Dart 特有）
        is_async: 是否為非同步函式（可選，JavaScript 特有）
        function_type: 函式類型（可選，JavaScript 特有: function, arrow, method）

    範例:
        # Dart 函式
        Function(
            name='build',
            line_number=20,
            has_comment=True,
            return_type='Widget'
        )

        # JavaScript 箭頭函式
        Function(
            name='fetchData',
            line_number=15,
            has_comment=True,
            is_async=True,
            function_type='arrow'
        )
    """
    name: str
    line_number: int
    has_comment: bool
    return_type: Optional[str] = None
    is_async: bool = False
    function_type: str = 'function'


class LanguageParser(ABC):
    """
    語言解析器抽象基類

    所有語言的 Parser 必須繼承此類並實作抽象方法

    必須實作的方法:
    - extract_functions: 提取函式定義
    - file_extensions: 支援的檔案副檔名
    - language_name: 語言名稱

    使用範例:
        class MyParser(LanguageParser):
            def extract_functions(self, code: str) -> List[Function]:
                # 實作邏輯
                pass

            @property
            def file_extensions(self) -> Set[str]:
                return {'.myext'}

            @property
            def language_name(self) -> str:
                return 'MyLanguage'
    """

    @abstractmethod
    def extract_functions(self, code: str) -> List[Function]:
        """
        提取程式碼中的所有函式定義

        Args:
            code: 程式碼字串

        Returns:
            函式列表（Function 物件）

        注意: 空程式碼應返回空列表，不應拋出異常
        """
        pass

    @property
    @abstractmethod
    def file_extensions(self) -> Set[str]:
        """
        支援的檔案副檔名

        Returns:
            副檔名集合（如 {'.dart'}）

        注意: 副檔名必須包含點號（.）
        """
        pass

    @property
    @abstractmethod
    def language_name(self) -> str:
        """
        語言名稱

        Returns:
            語言名稱字串（如 'Dart'）

        用途: 日誌記錄和除錯
        """
        pass


class ParserFactory:
    """
    Parser 工廠類別

    職責:
    1. 維護 Language → Parser 的映射關係
    2. 維護副檔名 → Language 的映射關係
    3. 提供 Parser 創建方法
    4. 支援自動註冊機制

    使用範例:
        # 註冊 Parser
        ParserFactory.register_parser(Language.DART, DartParser)

        # 方式 1: 根據語言類型創建
        parser = ParserFactory.create_parser(Language.DART)

        # 方式 2: 根據檔案路徑創建
        parser = ParserFactory.create_parser_for_file('lib/main.dart')

        # 方式 3: 檢測語言
        language = ParserFactory.detect_language('src/app.js')

        # 方式 4: 檢查是否支援
        if ParserFactory.is_supported('test.go'):
            parser = ParserFactory.create_parser_for_file('test.go')
    """

    # 類別變數：Language → Parser Class 映射
    _parsers: Dict[Language, Type[LanguageParser]] = {}

    # 類別變數：副檔名 → Language 映射
    _extension_map: Dict[str, Language] = {}

    @classmethod
    def register_parser(cls, language: Language,
                       parser_class: Type[LanguageParser],
                       extensions: Optional[Set[str]] = None) -> None:
        """
        註冊 Parser

        Args:
            language: 語言類型
            parser_class: Parser 類別（必須繼承 LanguageParser）
            extensions: 要註冊的副檔名集合（可選，預設使用 Parser 的 file_extensions）

        Raises:
            ValueError: 如果 parser_class 未繼承 LanguageParser

        注意: 此方法會自動建立副檔名映射
        當 extensions 參數指定時，只註冊指定的副檔名（用於 TypeScript 共用 JavaScriptParser 的情況）
        """
        if not issubclass(parser_class, LanguageParser):
            raise ValueError(
                f"{parser_class.__name__} 必須繼承 LanguageParser"
            )

        cls._parsers[language] = parser_class

        # 決定要註冊的副檔名
        parser_instance = parser_class()
        exts_to_register = extensions if extensions is not None else parser_instance.file_extensions

        # 自動註冊副檔名映射
        for ext in exts_to_register:
            cls._extension_map[ext] = language

    @classmethod
    def create_parser(cls, language: Language) -> LanguageParser:
        """
        根據語言類型創建 Parser

        Args:
            language: 語言類型

        Returns:
            Parser 實例

        Raises:
            ValueError: 如果語言類型不支援

        範例:
            parser = ParserFactory.create_parser(Language.DART)
            functions = parser.extract_functions(code)
        """
        if language not in cls._parsers:
            raise ValueError(f"不支援的語言: {language}")

        parser_class = cls._parsers[language]
        return parser_class()

    @classmethod
    def create_parser_for_file(cls, file_path: str) -> LanguageParser:
        """
        根據檔案路徑創建 Parser

        Args:
            file_path: 檔案路徑

        Returns:
            Parser 實例

        Raises:
            ValueError: 如果檔案類型不支援

        範例:
            parser = ParserFactory.create_parser_for_file('lib/main.dart')
            code = Path('lib/main.dart').read_text()
            functions = parser.extract_functions(code)
        """
        language = cls.detect_language(file_path)
        if language == Language.UNKNOWN:
            raise ValueError(f"不支援的檔案類型: {file_path}")

        return cls.create_parser(language)

    @classmethod
    def detect_language(cls, file_path: str) -> Language:
        """
        根據檔案副檔名檢測語言類型

        Args:
            file_path: 檔案路徑

        Returns:
            Language 枚舉值

        注意: 副檔名檢測不區分大小寫

        範例:
            detect_language('lib/main.dart')    # Language.DART
            detect_language('src/app.js')       # Language.JAVASCRIPT
            detect_language('test.xyz')         # Language.UNKNOWN
        """
        path = Path(file_path)
        ext = path.suffix.lower()

        return cls._extension_map.get(ext, Language.UNKNOWN)

    @classmethod
    def is_supported(cls, file_path: str) -> bool:
        """
        檢查檔案是否支援

        Args:
            file_path: 檔案路徑

        Returns:
            True 如果支援，否則 False

        範例:
            if ParserFactory.is_supported('test.go'):
                print("支援 Go 語言")
            else:
                print("不支援 Go 語言")
        """
        return cls.detect_language(file_path) != Language.UNKNOWN
