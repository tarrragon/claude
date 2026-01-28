"""
JavaScript/TypeScript 語言解析器

用途: 提取 JavaScript/TypeScript 程式碼中的函式定義，過濾關鍵字，檢查註解完整性

核心功能:
1. 函式識別 - 支援 6 種 JavaScript 函式定義模式
2. 關鍵字過濾 - 排除 JavaScript 語言關鍵字（if, for, while 等）
3. TypeScript 支援 - 兼容 TypeScript 類型註解和泛型
4. 註解檢查 - 驗證函式是否有完整的 JSDoc 註解

支援的函式模式:
1. 傳統函式宣告: function foo() { }
2. const 箭頭函式: const foo = () => { }
3. let 箭頭函式: let foo = () => { }
4. 函式表達式: const foo = function() { }
5. 非同步函式: async function foo() { }
6. 類別方法: class Foo { method() { } }

效能目標: <100ms（處理 1000 行程式碼）
準確率目標: 85-90%（相較於 AST 解析）

版本: v1.0
建立日期: 2025-01-10
"""

import re
from typing import List, Set

from .base import LanguageParser, Function


# JavaScript 語言關鍵字完整列表
# 來源: https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Lexical_grammar
JS_KEYWORDS = {
    # 控制流程關鍵字
    'if', 'else', 'for', 'while', 'do', 'switch', 'case', 'default',

    # 跳轉控制關鍵字
    'return', 'break', 'continue', 'throw', 'try', 'catch', 'finally',

    # 異步控制關鍵字
    'await', 'yield', 'async',

    # 模組管理關鍵字
    'import', 'export', 'from', 'as',

    # 類別相關關鍵字
    'class', 'extends', 'super', 'this', 'static', 'new',

    # 變數宣告關鍵字
    'var', 'let', 'const',

    # 函式相關關鍵字
    'function', 'get', 'set', 'constructor',

    # 類型檢查關鍵字
    'typeof', 'instanceof', 'in', 'of',

    # 其他關鍵字
    'with', 'delete', 'void', 'debugger',
}


class JavaScriptParser(LanguageParser):
    """
    JavaScript/TypeScript 語言解析器

    用途: 從 JavaScript/TypeScript 程式碼中提取函式定義並檢查註解品質

    使用範例:
        parser = JavaScriptParser()
        code = Path('src/services/book-service.js').read_text()
        functions = parser.extract_functions(code)

        for func in functions:
            if not func.has_comment:
                print(f"函式 {func.name} 缺少完整註解（行 {func.line_number}）")
    """

    @property
    def file_extensions(self) -> Set[str]:
        """支援的檔案副檔名"""
        return {'.js', '.jsx', '.ts', '.tsx', '.mjs'}

    @property
    def language_name(self) -> str:
        """語言名稱"""
        return 'JavaScript/TypeScript'

    def __init__(self):
        """初始化 JavaScript 解析器"""
        self.keywords = JS_KEYWORDS

        # 編譯正則表達式以提升效能
        # 模式 1: 傳統函式宣告
        # 格式: [export] [async] function functionName<T>(...) 或 function functionName(...)
        # 支援 TypeScript 泛型: <T>, <T, U>, 等
        self.traditional_pattern = re.compile(
            r'^\s*(export\s+)?(async\s+)?function\s+([a-zA-Z_$]\w*)(?:<[^>]*>)?\s*\(',
            re.MULTILINE
        )

        # 模式 2: const 箭頭函式
        # 格式: [export] const functionName = [async] (...) =>
        self.arrow_const_pattern = re.compile(
            r'^\s*(export\s+)?const\s+([a-zA-Z_$]\w*)\s*=\s*(?:async\s+)?\([^)]*\)\s*=>',
            re.MULTILINE
        )

        # 模式 3: let 箭頭函式
        # 格式: [export] let functionName = [async] (...) =>
        self.arrow_let_pattern = re.compile(
            r'^\s*(export\s+)?let\s+([a-zA-Z_$]\w*)\s*=\s*(?:async\s+)?\([^)]*\)\s*=>',
            re.MULTILINE
        )

        # 模式 4: 函式表達式
        # 格式: [export] const functionName = [async] function(
        self.function_expr_pattern = re.compile(
            r'^\s*(export\s+)?const\s+([a-zA-Z_$]\w*)\s*=\s*(async\s+)?function\s*\(',
            re.MULTILINE
        )

        # 模式 5-6: 類別方法
        # 格式: [static] [async] methodName(...) {
        # 注意: 只在 class 內部檢測
        self.class_method_pattern = re.compile(
            r'^\s*(static\s+)?(async\s+)?([a-zA-Z_$]\w*)\s*\([^)]*\)\s*\{',
            re.MULTILINE
        )

    def extract_functions(self, code: str) -> List[Function]:
        """
        提取所有函式定義

        流程:
        1. 使用正則表達式匹配 6 種函式模式
        2. 過濾 JavaScript 關鍵字（if, for, while 等）
        3. 檢查 JSDoc 註解完整性
        4. 返回函式列表

        Args:
            code: JavaScript/TypeScript 程式碼字串

        Returns:
            函式列表（Function 物件）

        範例:
            code = '''
            async function fetchData() {
                return await fetch('/api');
            }
            '''
            functions = parser.extract_functions(code)
            # 返回: [Function(name='fetchData', is_async=True, ...)]
        """
        if not code:
            return []

        functions = []
        lines = code.split('\n')

        # 追蹤是否在 class 內部
        in_class = False
        class_brace_count = 0

        # 逐行掃描
        for line_num, line in enumerate(lines, 1):
            # 檢測進入/離開 class
            if 'class ' in line and '{' in line:
                in_class = True
                class_brace_count = 1
            elif in_class:
                class_brace_count += line.count('{')
                class_brace_count -= line.count('}')
                if class_brace_count == 0:
                    in_class = False

            # 檢查是否有 JSDoc 註解
            has_comment = self._check_jsdoc(lines, line_num - 1)

            # 模式 1: 傳統函式宣告
            match = self.traditional_pattern.search(line)
            if match:
                func_name = match.group(3)
                if self._is_valid_function_name(func_name):
                    is_async = bool(match.group(2))
                    functions.append(Function(
                        name=func_name,
                        line_number=line_num,
                        has_comment=has_comment,
                        is_async=is_async,  # JavaScript 特定欄位
                        function_type='function'  # JavaScript 特定欄位
                    ))
                continue

            # 模式 2: const 箭頭函式
            match = self.arrow_const_pattern.search(line)
            if match:
                func_name = match.group(2)
                if self._is_valid_function_name(func_name):
                    is_async = 'async' in line
                    functions.append(Function(
                        name=func_name,
                        line_number=line_num,
                        has_comment=has_comment,
                        is_async=is_async,  # JavaScript 特定欄位
                        function_type='arrow'  # JavaScript 特定欄位
                    ))
                continue

            # 模式 3: let 箭頭函式
            match = self.arrow_let_pattern.search(line)
            if match:
                func_name = match.group(2)
                if self._is_valid_function_name(func_name):
                    is_async = 'async' in line
                    functions.append(Function(
                        name=func_name,
                        line_number=line_num,
                        has_comment=has_comment,
                        is_async=is_async,  # JavaScript 特定欄位
                        function_type='arrow'  # JavaScript 特定欄位
                    ))
                continue

            # 模式 4: 函式表達式
            match = self.function_expr_pattern.search(line)
            if match:
                func_name = match.group(2)
                if self._is_valid_function_name(func_name):
                    is_async = bool(match.group(3))
                    functions.append(Function(
                        name=func_name,
                        line_number=line_num,
                        has_comment=has_comment,
                        is_async=is_async,  # JavaScript 特定欄位
                        function_type='function'  # JavaScript 特定欄位
                    ))
                continue

            # 模式 5-6: 類別方法（只在 class 內檢測）
            if in_class:
                match = self.class_method_pattern.search(line)
                if match:
                    func_name = match.group(3)
                    # 排除 constructor, get, set
                    if (self._is_valid_function_name(func_name) and
                        func_name not in ['constructor', 'get', 'set']):
                        is_async = bool(match.group(2))
                        functions.append(Function(
                            name=func_name,
                            line_number=line_num,
                            has_comment=has_comment,
                            is_async=is_async,  # JavaScript 特定欄位
                            function_type='method'  # JavaScript 特定欄位
                        ))

        return functions

    def _is_valid_function_name(self, name: str) -> bool:
        """
        檢查是否為有效的函式名稱

        規則:
        1. 不是 JavaScript 關鍵字
        2. 不是空字串

        Args:
            name: 函式名稱

        Returns:
            True 如果有效，否則 False

        範例:
            _is_valid_function_name('handleClick')  # True
            _is_valid_function_name('if')           # False
            _is_valid_function_name('for')          # False
        """
        if not name:
            return False
        return name not in self.keywords

    def _check_jsdoc(self, lines: List[str], func_line_index: int) -> bool:
        """
        檢查函式上方是否有 JSDoc 註解

        JSDoc 標準格式:
            /**
             * 函式描述
             * @param {type} name - 說明
             * @returns {type} - 說明
             */

        檢測邏輯:
        1. 向上掃描最多 10 行
        2. 尋找 /** 開始標記
        3. 確認有 */ 結束標記

        Args:
            lines: 程式碼行列表
            func_line_index: 函式定義所在行號（0-based）

        Returns:
            True 如果有 JSDoc 註解，否則 False

        範例:
            完整 JSDoc:
                /**
                 * 取得書籍資料
                 * @param {string} id
                 */
                function getBook(id) { }

            無 JSDoc:
                // 這是單行註解
                function getBook(id) { }
        """
        if func_line_index == 0:
            return False

        # 檢查前 10 行是否有 JSDoc 開始標記
        for i in range(max(0, func_line_index - 10), func_line_index):
            line = lines[i].strip()
            if line.startswith('/**'):
                # 檢查是否有 JSDoc 結束標記
                for j in range(i, func_line_index):
                    if '*/' in lines[j]:
                        return True

        return False
