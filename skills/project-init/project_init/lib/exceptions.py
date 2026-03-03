"""環境設定例外類別階層。

提供結構化的例外型別，用於不同的環境問題場景。
每個例外包含 tool（工具名稱）、reason（失敗原因）、guidance（修復步驟）。
"""

from typing import Optional


class EnvironmentSetupError(Exception):
    """環境設定例外的基底類別。

    Attributes:
        tool: 受影響的工具或元件名稱
        reason: 失敗的具體原因
        guidance: 逐步修復建議清單
    """

    def __init__(self, tool: str, reason: str, guidance: list[str] | None = None):
        """初始化環境設定例外。

        Args:
            tool: 工具名稱（如 'Python', 'UV', 'ripgrep'）
            reason: 失敗原因的簡短描述
            guidance: 修復步驟清單（如果為 None，使用空清單）
        """
        self.tool = tool
        self.reason = reason
        self.guidance = guidance or []
        message = f"{tool}: {reason}"
        super().__init__(message)

    def get_full_message(self) -> str:
        """取得包含指導的完整訊息。

        Returns:
            str: 格式化的訊息，包含原因和修復步驟。
        """
        lines = [f"{self.tool}: {self.reason}"]
        if self.guidance:
            lines.append("\n修復步驟:")
            for i, step in enumerate(self.guidance, 1):
                lines.append(f"  {i}. {step}")
        return "\n".join(lines)


class ToolNotFoundError(EnvironmentSetupError):
    """工具未找到例外。

    當系統中找不到必需的工具時拋出。
    """

    pass


class VersionTooOldError(EnvironmentSetupError):
    """版本過舊例外。

    當工具版本低於最低需求時拋出。
    """

    pass


class PermissionDeniedError(EnvironmentSetupError):
    """權限被拒例外。

    當因為權限問題無法執行操作時拋出。
    """

    pass


class NetworkError(EnvironmentSetupError):
    """網路錯誤例外。

    當因為網路問題無法下載或連接時拋出。
    """

    pass


class DiskSpaceError(EnvironmentSetupError):
    """磁碟空間不足例外。

    當磁碟空間不足以完成安裝時拋出。
    """

    pass


class ConfigurationError(EnvironmentSetupError):
    """設定錯誤例外。

    當環境設定有問題（如缺少必要檔案）時拋出。
    """

    pass


class ExecutionError(EnvironmentSetupError):
    """執行錯誤例外。

    當執行命令失敗時拋出。
    """

    pass
