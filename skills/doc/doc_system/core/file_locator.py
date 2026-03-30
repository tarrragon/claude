"""定位 docs/ 下的文件路徑。"""

import os
import subprocess
from pathlib import Path


# ID 前綴到 FileLocator 查詢方法的對應
ID_PREFIX_FINDERS = {
    "PROP": "find_proposal",
    "UC": "find_usecase",
    "SPEC": "find_spec",
}


class FileLocator:
    """定位 proposals/spec/usecases 文件的工具類別。"""

    def __init__(self, project_root: str) -> None:
        self.project_root = project_root
        root = Path(project_root)
        self.proposals_dir = str(root / "docs" / "proposals")
        self.spec_dir = str(root / "docs" / "spec")
        self.usecases_dir = str(root / "docs" / "usecases")
        self.tracking_file = str(root / "docs" / "proposals-tracking.yaml")

    def find_proposal(self, prop_id: str) -> str | None:
        """依 proposal ID 找到對應檔案路徑，找不到回傳 None。"""
        return self._find_file_by_id(self.proposals_dir, prop_id)

    def find_usecase(self, uc_id: str) -> str | None:
        """依 usecase ID 找到對應檔案路徑，找不到回傳 None。"""
        return self._find_file_by_id(self.usecases_dir, uc_id)

    def find_spec(self, spec_id: str) -> str | None:
        """依 spec ID 找到對應檔案路徑，找不到回傳 None。"""
        return self._find_file_by_id(self.spec_dir, spec_id)

    def list_proposals(self) -> list[str]:
        """列出所有 proposal 檔案路徑。"""
        return self._list_markdown_files(self.proposals_dir)

    def list_usecases(self) -> list[str]:
        """列出所有 usecase 檔案路徑。"""
        return self._list_markdown_files(self.usecases_dir)

    def list_specs(self, domain: str | None = None) -> list[str]:
        """列出 spec 檔案路徑，可選依 domain 子目錄篩選。"""
        if domain is not None:
            target_dir = str(Path(self.spec_dir) / domain)
        else:
            target_dir = self.spec_dir
        return self._list_markdown_files(target_dir)

    def resolve_file(self, doc_id: str) -> str | None:
        """依 ID 前綴找到對應檔案路徑。

        從 query.py 移至此處，作為公開方法供 query/nav 共用。
        """
        for prefix, method_name in ID_PREFIX_FINDERS.items():
            if doc_id.upper().startswith(prefix):
                finder = getattr(self, method_name)
                return finder(doc_id)
        return None

    @staticmethod
    def get_project_root() -> str:
        """定位專案根目錄。

        優先順序：
        1. CLAUDE_PROJECT_DIR 環境變數
        2. git rev-parse --show-toplevel
        3. 從當前目錄往上尋找包含 docs/ 的目錄（fallback）

        Raises:
            FileNotFoundError: 三種方式都找不到專案根目錄。
        """
        # 1. 環境變數優先
        env_root = os.environ.get("CLAUDE_PROJECT_DIR")
        if env_root and Path(env_root).is_dir():
            return env_root

        # 2. git rev-parse --show-toplevel
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                capture_output=True,
                text=True,
                check=True,
            )
            git_root = result.stdout.strip()
            if git_root and Path(git_root).is_dir():
                return git_root
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass

        # 3. fallback: 往上搜尋 docs/ 目錄
        current = Path.cwd()
        for directory in [current, *current.parents]:
            if (directory / "docs").is_dir():
                return str(directory)
        raise FileNotFoundError("找不到包含 docs/ 的專案根目錄")

    @staticmethod
    def _find_file_by_id(directory: str, file_id: str) -> str | None:
        """在目錄中（含子目錄）尋找檔名以 file_id 為精確前綴的 .md 檔案。

        匹配規則：stem == file_id 或 stem 以 file_id + "-" 開頭。
        避免 UC-01 誤匹配 UC-010。
        """
        dir_path = Path(directory)
        if not dir_path.is_dir():
            return None

        for md_file in dir_path.rglob("*.md"):
            stem = md_file.stem
            if stem == file_id or stem.startswith(file_id + "-"):
                return str(md_file)
        return None

    @staticmethod
    def _list_markdown_files(directory: str) -> list[str]:
        """列出目錄下（含子目錄）所有 .md 檔案路徑，排序後回傳。"""
        dir_path = Path(directory)
        if not dir_path.is_dir():
            return []

        return sorted(str(f) for f in dir_path.rglob("*.md"))
