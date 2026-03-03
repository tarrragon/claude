"""
Mermaid ASCII 集中式訊息管理模組

定義所有錯誤訊息、提示文字和命令列說明。
確保訊息統一、易於維護和國際化。
"""

# ============================================================================
# 驗證和錯誤訊息
# ============================================================================

# 輸入驗證
ERROR_EMPTY_INPUT = "輸入的 Mermaid 文本不能為空"

# 渲染錯誤
ERROR_RENDER_FAILED = "渲染失敗: {error}"

# 檔案操作錯誤
ERROR_FILE_NOT_FOUND = "檔案不存在: {file_path}"
ERROR_READ_INPUT_FAILED = "讀取輸入失敗: {error}"

# 標準錯誤輸出前綴
ERROR_PREFIX = "錯誤: "
RENDER_ERROR_PREFIX = "渲染錯誤: "
IO_ERROR_PREFIX = "I/O 錯誤: "
UNEXPECTED_ERROR_PREFIX = "未預期的錯誤: "

# ============================================================================
# 標準輸出訊息
# ============================================================================

# 中斷信號
INTERRUPT_MESSAGE = "\n中斷"

# ============================================================================
# 命令列參數和幫助文字
# ============================================================================

# 主程式資訊
PROGRAM_NAME = "mermaid-ascii"
PROGRAM_DESCRIPTION = "Mermaid ASCII 渲染工具 - 將 Mermaid 圖表渲染為 ASCII 或 Unicode"
PROGRAM_VERSION = "1.0.0"

# 輸入選項幫助文字
INPUT_OPTION_HELP = "輸入 Mermaid 檔案路徑。若不指定則從 stdin 讀取"
INPUT_OPTION_METAVAR = "FILE"

# 輸出格式選項幫助文字
ASCII_OPTION_HELP = "輸出純 ASCII 字元（無 Unicode 方框字元）"
UNICODE_OPTION_HELP = "輸出 Unicode 方框字元（預設）"

# 命令列範例
CLI_EXAMPLES = (
    "示例:\n"
    "  python render.py --input diagram.mmd --ascii\n"
    "  cat diagram.mmd | python render.py --unicode"
)

# ============================================================================
# 模組文件字串
# ============================================================================

MODULE_DOCSTRING = (
    "Mermaid ASCII CLI 入口\n\n"
    "支援將 Mermaid 圖表渲染為 ASCII 或 Unicode 藝術，支援檔案和 stdin 輸入。\n\n"
    "用法:\n"
    "    # 從檔案輸入\n"
    "    python render.py --input diagram.mmd --ascii\n\n"
    "    # 從 stdin 輸入（pipe）\n"
    "    cat diagram.mmd | python render.py --unicode\n\n"
    "    # 指定輸出格式\n"
    "    python render.py -i diagram.mmd --ascii    # 純 ASCII（無 Unicode）\n"
    "    python render.py -i diagram.mmd --unicode  # 使用 Unicode 方框字元"
)
