"""
Dart 語言解析器

用途: 提取 Dart 程式碼中的函式定義，過濾關鍵字和建構式，檢查註解完整性

核心功能:
1. 函式識別 - 使用正則表達式匹配函式定義
2. 關鍵字過濾 - 排除 Dart 語言關鍵字（if, for, while 等）
3. 建構式過濾 - 排除 PascalCase 命名的建構式（SizedBox, Container 等）
4. 註解檢查 - 驗證函式是否有完整的追溯註解

效能目標: <100ms（處理 1000 行程式碼）
準確率目標: 85-90%（相較於 AST 解析）

版本: v1.0
建立日期: 2025-01-10
"""

import re
from typing import List, Set

from .base import LanguageParser, Function


# Dart 語言關鍵字完整列表
# 來源: https://dart.dev/language/keywords
DART_KEYWORDS = {
    # 控制流程關鍵字
    'if', 'else', 'for', 'while', 'do', 'switch', 'case', 'default',

    # 跳轉控制關鍵字
    'return', 'break', 'continue', 'throw', 'try', 'catch', 'finally',
    'rethrow',

    # 異步控制關鍵字
    'assert', 'await', 'yield', 'async', 'sync',

    # 模組管理關鍵字
    'import', 'export', 'library', 'part', 'as', 'show', 'hide', 'deferred',

    # 類別相關關鍵字
    'class', 'extends', 'implements', 'with', 'mixin',
    'abstract', 'interface', 'enum', 'extension', 'sealed', 'base',

    # 變數宣告關鍵字
    'var', 'final', 'const', 'late', 'dynamic', 'required', 'covariant',

    # 函式相關關鍵字
    'void', 'Function', 'typedef',

    # 存取控制關鍵字
    'new', 'this', 'super', 'static', 'get', 'set', 'operator',
    'external', 'factory',

    # 比較和類型檢查關鍵字
    'is', 'in', 'null', 'true', 'false',

    # 其他關鍵字
    'on', 'when',
}


class DartParser(LanguageParser):
    """
    Dart 語言解析器

    用途: 從 Dart 程式碼中提取函式定義並檢查註解品質

    使用範例:
        parser = DartParser()
        code = Path('lib/presentation/widgets/book_list.dart').read_text()
        functions = parser.extract_functions(code)

        for func in functions:
            if not func.has_comment:
                print(f"函式 {func.name} 缺少完整註解（行 {func.line_number}）")
    """

    @property
    def file_extensions(self) -> Set[str]:
        """支援的檔案副檔名"""
        return {'.dart'}

    @property
    def language_name(self) -> str:
        """語言名稱"""
        return 'Dart'

    def __init__(self):
        """初始化 Dart 解析器"""
        self.keywords = DART_KEYWORDS

        # 編譯正則表達式以提升效能
        # 匹配函式定義格式: returnType functionName(
        # returnType 可以是:
        # 1. 內建類型: void, bool, int, String, double
        # 2. 泛型類型: Future<T>, Stream<T>, List<T>, Map<K,V>, OperationResult<T>
        # 3. 自定義類別: Widget, Book, 等（PascalCase）
        self.function_pattern = re.compile(
            r'^(?:'
            r'(Future<[^>]+>|Stream<[^>]+>|OperationResult<[^>]+>|List<[^>]+>|Map<[^>]+>)|'  # 泛型
            r'(void|bool|int|String|double|dynamic|num)|'  # 內建類型
            r'([A-Z]\w*)'  # 自定義類別（PascalCase）
            r')\s+'
            r'([a-z_]\w*)\s*\(',  # 函式名稱（camelCase 或 _private）
            re.MULTILINE
        )

    def extract_functions(self, code: str) -> List[Function]:
        """
        提取所有函式定義

        流程:
        1. 使用正則表達式匹配所有候選函式
        2. 過濾 Dart 關鍵字（if, for, while 等）
        3. 過濾 PascalCase 建構式（SizedBox, Container 等）
        4. 檢查註解完整性
        5. 返回函式列表

        Args:
            code: Dart 程式碼字串

        Returns:
            函式列表（Function 物件）

        範例:
            code = '''
            void handleBookAdded(Book book) {
                if (book.title.isEmpty) return;
            }
            '''
            functions = parser.extract_functions(code)
            # 返回: [Function(name='handleBookAdded', ...)]
        """
        if not code:
            return []

        functions = []
        lines = code.split('\n')

        # 逐行掃描
        i = 0
        while i < len(lines):
            # 收集上方的註解（/// 開頭）
            comment_lines = []
            while i < len(lines) and lines[i].strip().startswith('///'):
                comment_lines.append(lines[i].strip())
                i += 1

            if i >= len(lines):
                break

            line = lines[i].strip()

            # 跳過空行和普通註解
            if not line or line.startswith('//'):
                i += 1
                continue

            # 早期過濾：跳過以關鍵字開頭的行（提升效能）
            # 例如: if (condition), for (var i in list), while (true)
            # 注意：void, bool, int 等可以作為回傳類型，不應被過濾
            words = line.split()
            if words:
                first_word = words[0].rstrip('(')
                # 只過濾控制流程關鍵字（不是回傳類型）
                control_keywords = {
                    'if', 'else', 'for', 'while', 'do', 'switch', 'case', 'default',
                    'return', 'break', 'continue', 'throw', 'try', 'catch', 'finally',
                    'assert', 'await', 'yield', 'async', 'sync',
                    'import', 'export', 'library', 'part', 'as', 'show', 'hide',
                    'class', 'extends', 'implements', 'with', 'mixin',
                    'var', 'final', 'const', 'late', 'new', 'this', 'super',
                    'static', 'get', 'set', 'is', 'in'
                }
                if first_word in control_keywords:
                    i += 1
                    continue

            # 匹配函式定義
            match = self.function_pattern.search(line)

            if match:
                # 回傳類型可能在 group(1)、group(2) 或 group(3) 中
                return_type = match.group(1) or match.group(2) or match.group(3)
                func_name = match.group(4)  # 函式名稱在第 4 個捕獲組

                # 1. 過濾關鍵字（雙重檢查）
                if self._is_keyword(func_name):
                    i += 1
                    continue

                # 2. 過濾建構式（PascalCase）
                if self._is_constructor(func_name):
                    i += 1
                    continue

                # 3. 排除 getter/setter
                if func_name in ['get', 'set']:
                    i += 1
                    continue

                # 4. 檢查註解完整性
                has_complete = self._has_complete_comment(comment_lines)

                # 5. 建立 Function 物件（使用統一的 Function 資料結構）
                func = Function(
                    name=func_name,
                    line_number=i + 1,  # 行號從 1 開始
                    has_comment=has_complete,
                    return_type=return_type  # Dart 特定欄位
                )

                functions.append(func)

            i += 1

        return functions

    def _is_keyword(self, name: str) -> bool:
        """
        檢查是否為 Dart 關鍵字

        Args:
            name: 函式名稱

        Returns:
            True 如果是關鍵字，否則 False

        範例:
            _is_keyword('if')    # True
            _is_keyword('for')   # True
            _is_keyword('build') # False
        """
        return name in self.keywords

    def _is_constructor(self, name: str) -> bool:
        """
        檢查是否為建構式（PascalCase 命名）

        規則: 首字母大寫的名稱視為類別或建構式

        Args:
            name: 函式名稱

        Returns:
            True 如果是建構式，否則 False

        範例:
            _is_constructor('SizedBox')      # True
            _is_constructor('Container')     # True
            _is_constructor('build')         # False
            _is_constructor('testFunction')  # False
        """
        if not name:
            return False
        return name[0].isupper()

    def _has_complete_comment(self, comment_lines: List[str]) -> bool:
        """
        檢查是否有完整的追溯註解

        完整註解標準（基於 comment-writing-methodology.md）:
        - 必須包含「需求來源」或「需求」關鍵字
        - 必須包含「規格文件」或「工作日誌」關鍵字
        - 或包含具體的需求編號（UC-, BR-）和文件路徑（docs/）

        Args:
            comment_lines: 註解行列表（/// 開頭）

        Returns:
            True 如果註解完整，否則 False

        範例:
            完整註解:
                /// 【需求來源】UC-01: Chrome Extension匯入
                /// 【規格文件】docs/app-requirements-spec.md

            不完整註解:
                /// 這是一個測試函式
        """
        if not comment_lines:
            return False

        # 合併所有註解行
        comment_text = ' '.join(comment_lines)

        # 檢查關鍵標記
        has_requirement = any(keyword in comment_text for keyword in [
            '需求來源', '需求:', 'UC-', 'BR-'
        ])

        has_traceability = any(keyword in comment_text for keyword in [
            '規格文件', '工作日誌', 'docs/'
        ])

        return has_requirement and has_traceability
