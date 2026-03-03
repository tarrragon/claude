"""環境設定的使用者訊息常數集中管理。

所有面向使用者的訊息字串在此模組定義，禁止在其他模組中硬編碼。
遵循命名規則：CONTEXT_DESCRIPTION（如 PYTHON_NOT_INSTALLED）。
"""


# ========== OS 訊息 ==========
class OSMessages:
    """作業系統相關訊息."""

    DETECTION_FAILED = "無法偵測作業系統"


# ========== Python 訊息 ==========
class PythonMessages:
    """Python 環境相關訊息."""

    NOT_INSTALLED = "版本: 未安裝"
    NOT_INSTALLED_STATUS = "狀態: Python 3.11+ 是必需的"
    INSTALL_GUIDANCE = "安裝指引: https://www.python.org/downloads/"


# ========== UV 訊息 ==========
class UVMessages:
    """UV 工具相關訊息."""

    NOT_INSTALLED = "版本: 未安裝"
    NOT_INSTALLED_STATUS = "狀態: UV 是必需的"
    INSTALL_GUIDANCE = "安裝指引: https://docs.astral.sh/uv/guides/installing-uv/"


# ========== ripgrep 訊息 ==========
class RipgrepMessages:
    """ripgrep 工具相關訊息."""

    NOT_INSTALLED = "版本: 未安裝"
    NOT_INSTALLED_STATUS = "狀態: ripgrep 是可選的，但建議安裝"
    INSTALL_GUIDANCE_MACOS = "安裝指令: brew install ripgrep"
    INSTALL_GUIDANCE_LINUX = "安裝指令: apt-get install ripgrep"
    INSTALL_GUIDANCE_WINDOWS = "安裝指令: winget install BurntSushi.ripgrep.MSVC"


# ========== Hook 系統訊息 ==========
class HookSystemMessages:
    """Hook 系統相關訊息."""

    COMPILATION_ERROR = "編譯狀態: {count} 個失敗"
    PEP723_FAILED = "PEP 723 執行: 失敗"
    ALL_OK = "編譯狀態: 全部通過"


# ========== 自製套件訊息 ==========
class PackageMessages:
    """自製套件相關訊息."""

    NO_PACKAGES = "無自製套件"
    NOT_INSTALLED = "{name} ({version}) [MISSING]"
    NOT_INSTALLED_ACTION = "  → 需執行: uv tool install ."
    OUTDATED = "{name} ({version}) [OUTDATED]"
    OUTDATED_ACTION = "  → 原始碼已更新，需重新安裝: uv tool install . --force --reinstall"


# ========== Setup 訊息 ==========
class SetupMessages:
    """Setup 命令相關訊息."""

    STEP_CHECK = "[1/3] 檢查環境狀態..."
    STEP_HANDLE_TOOLS = "[2/3] 處理缺失和過時工具..."
    STEP_HANDLE_PACKAGES = "[3/3] 更新自製套件..."
    NO_PROBLEMS = "[2/3] 無需處理..."
    INSTALL_COMPLETE_HEADER = "安裝指令"
    INSTALLING = "正在安裝..."
    UPDATING = "正在重新安裝..."
    INSTALL_SUCCESS = "安裝完成"
    UPDATE_SUCCESS = "更新完成"
    INSTALL_FAILED = "安裝失敗"
    UPDATE_FAILED = "更新失敗"
    COMPLETE_SUMMARY = "設定完成: {summary}"
    UP_TO_DATE = "環境已是最新狀態"
    UP_TO_DATE_SUMMARY = "設定完成: 環境已是最新狀態"
    AUTO_FIXED = "{count} 項已自動修復"
    MANUAL_REQUIRED = "{count} 項需手動處理"


# ========== 檢查命令訊息 ==========
class CheckMessages:
    """Check 命令相關訊息."""

    HEADER = "project-init check — 環境狀態報告"
    SUMMARY_TOTAL = "總結: {summary}"
    SUMMARY_FORMAT = "{ok}/{total} 項目正常"


# ========== Onboard 訊息 ==========
class OnboardMessages:
    """Onboard 命令相關訊息."""

    HEADER = "project-init onboard — 框架定制引導"
    LANGUAGE_SECTION = "專案語言偵測"
    LANGUAGE_DETECTED = "偵測結果: {language}"
    LANGUAGE_IDENTIFIER = "識別依據: {identifier}"
    LANGUAGE_UNKNOWN = "未偵測到已知語言"
    HOOK_CLASSIFICATION_SECTION = "Hook 語言分類"
    FLUTTER_HOOKS_LABEL = "Flutter 特定 Hook（保留）:"
    PROJECT_SPECIFIC_HOOKS_LABEL = "專案特定 Hook（需檢查）:"
    CLAUDE_MD_SECTION = "CLAUDE.md"
    CLAUDE_MD_OK = "狀態: [OK] 已存在"
    CLAUDE_MD_TODO = "狀態: [TODO] 不存在"
    CLAUDE_MD_COPY_HINT = "建議: 請從 .claude/templates/CLAUDE-template.md 複製"
    LANGUAGE_TEMPLATE_SECTION = "語言模板"
    TEMPLATE_OK = "{language} 模板: [OK] .claude/project-templates/{template_file}"
    TEMPLATE_TODO = "{language} 模板: [TODO] 尚無模板"
    SETTINGS_LOCAL_SECTION = "settings.local.json"
    SETTINGS_LOCAL_OK = "狀態: [OK] 已存在"
    SETTINGS_LOCAL_TODO = "狀態: [TODO] 不存在"
    SETTINGS_LOCAL_HINT = "建議: 檢查 [{language}] 標記的權限是否適用"
    TODOLIST_HEADER = "待辦清單"
    TODOLIST_COUNT = "{count} 項需處理"
    TODOLIST_NONE = "0 項需處理"


# ========== 錯誤修復指導 ==========
class RemediationGuidance:
    """各類問題的修復步驟指導."""

    @staticmethod
    def get_python_install_steps() -> list[str]:
        """取得 Python 安裝步驟."""
        return [
            "訪問 https://www.python.org/downloads/ 下載 Python 3.11 或更高版本",
            "執行安裝程式並完成安裝",
            "驗證安裝: python3 --version",
            "重新執行 project-init check",
        ]

    @staticmethod
    def get_uv_install_steps() -> list[str]:
        """取得 UV 安裝步驟."""
        return [
            "訪問 https://docs.astral.sh/uv/guides/installing-uv/",
            "根據平台選擇合適的安裝方式",
            "驗證安裝: uv --version",
            "重新執行 project-init check",
        ]

    @staticmethod
    def get_ripgrep_install_steps(os_type: str = "darwin") -> list[str]:
        """取得 ripgrep 安裝步驟。

        Args:
            os_type: 作業系統類型（darwin/linux/windows）

        Returns:
            list[str]: 分步驟安裝指導清單
        """
        if os_type.lower() in ("darwin", "macos"):
            return [
                "確保已安裝 Homebrew: https://brew.sh",
                "執行: brew install ripgrep",
                "驗證安裝: rg --version",
                "重新執行 project-init check",
            ]
        elif os_type.lower() == "linux":
            return [
                "Debian/Ubuntu: sudo apt-get update && sudo apt-get install -y ripgrep",
                "Fedora/RHEL: sudo dnf install -y ripgrep",
                "Arch: sudo pacman -S ripgrep",
                "驗證安裝: rg --version",
                "重新執行 project-init check",
            ]
        else:  # windows
            return [
                "使用 winget: winget install -e --id BurntSushi.ripgrep.MSVC",
                "或使用 scoop: scoop install ripgrep",
                "驗證安裝: rg --version",
                "重新執行 project-init check",
            ]
