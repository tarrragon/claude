"""定位 docs/ 下的文件路徑。"""

import os
import subprocess
import sys
from pathlib import Path
from typing import NamedTuple

import yaml

from doc_system.core.constants import CODE_ROOT_CONFIG_KEY

PROJECT_DIR_ENV = "CLAUDE_PROJECT_DIR"
REPO_PATH_PREFIX = "repo:"
CODE_ROOT_EXIT_CODE = 2
_TRACEABILITY_REL_PATH = os.path.join("docs", "traceability.yaml")


class CodeRootError(Exception):
    """code root 無法解析（外接模式未設定、設定格式不符或路徑不存在）。"""


class CodeRoot(NamedTuple):
    """程式碼端根目錄與其模式；external 為 True 時輸出路徑須帶 repo: 前綴。"""

    path: str
    external: bool


def _git_common_dir(directory: str) -> str | None:
    """回傳 directory 所屬 repo 的共用 git 目錄（realpath）；不在 repo 內回傳 None。

    worktree 與主 checkout 共用同一個 common dir，是辨識「同一個 repo」的依據。
    """
    try:
        result = subprocess.run(
            ["git", "-C", directory, "rev-parse", "--git-common-dir"],
            capture_output=True, text=True, check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        # 不在 repo 內或無 git：以 None 表示「無 repo 身份」，由呼叫端判讀，非錯誤
        return None
    out = result.stdout.strip()
    if not out:
        return None
    return os.path.realpath(os.path.join(directory, out))


def is_external_mode() -> bool:
    """判定是否為外接模式（doc root 為分析者端外接資料夾，程式碼在另一個 repo）。

    偵測依據：CLAUDE_PROJECT_DIR（外接模式的唯一入口，規格 C2）所指目錄，
    與 cwd 所屬 repo 是否為同一個 repo（比對 git common dir）。
    - 環境變數未設定，或目錄不存在：單根。
    - cwd 不在 git repo 內：無從比對，保守判單根。
    - 該目錄不在任何 repo 內，或屬於不同 repo：外接。
    - 同一 repo（含 linked worktree 與主 checkout 互為 doc root 與 cwd）：單根；
      worktree 的 toplevel 與主 checkout 不同，故不比對 toplevel，改比對 common dir。
    """
    env_root = os.environ.get(PROJECT_DIR_ENV)
    if not env_root or not Path(env_root).is_dir():
        return False
    cwd_common = _git_common_dir(os.getcwd())
    if cwd_common is None:
        return False
    return _git_common_dir(env_root) != cwd_common


def _read_configured_code_root(doc_root: str) -> object | None:
    """讀 traceability.yaml 的 code_root 原值；檔案缺席、不可解析、鍵缺席或 null 皆回 None。"""
    path = os.path.join(doc_root, _TRACEABILITY_REL_PATH)
    if not os.path.isfile(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except (OSError, yaml.YAMLError) as e:
        sys.stderr.write(f"[doc] WARNING：無法讀取 {_TRACEABILITY_REL_PATH}，code_root 視為未設定：{e}\n")
        return None
    if not isinstance(data, dict):
        return None
    return data.get(CODE_ROOT_CONFIG_KEY)


def _validate_code_root_path(raw: object, base_dir: str, source: str) -> str:
    """驗證 code root 值為非空字串且指向存在的目錄，回傳絕對路徑；相對路徑以 base_dir 解析。"""
    if not isinstance(raw, str) or not raw.strip():
        raise CodeRootError(f"{source} 須為非空的目錄字串，實際為 {raw!r}")
    candidate = Path(raw.strip()).expanduser()
    if not candidate.is_absolute():
        candidate = Path(base_dir) / candidate
    if not candidate.is_dir():
        raise CodeRootError(f"{source} 指向的目錄不存在：{candidate}")
    return str(candidate)


def resolve_code_root(
    doc_root: str, override: str | None = None, external: bool | None = None
) -> CodeRoot:
    """程式碼端根目錄的單一入口（test-map、uc trace、uc verify 共用）。

    來源優先序：--code-root 覆寫 > docs/traceability.yaml 的 code_root 鍵（唯一權威）。
    都沒有時：單根回傳 doc_root；外接模式拋 CodeRootError，不退回 doc root
    （退回會掃到外接資料夾而得到成功語氣的空結果）。
    設定存在但格式不符或路徑不存在一律拋 CodeRootError，單根亦然。
    """
    if external is None:
        external = is_external_mode()
    if override is not None:
        path = _validate_code_root_path(override, os.getcwd(), "--code-root")
        return CodeRoot(path, external)
    configured = _read_configured_code_root(doc_root)
    if configured is not None:
        path = _validate_code_root_path(
            configured, doc_root, f"{_TRACEABILITY_REL_PATH} 的 {CODE_ROOT_CONFIG_KEY}"
        )
        return CodeRoot(path, external)
    if external:
        raise CodeRootError(
            "外接模式（CLAUDE_PROJECT_DIR 指向 cwd 所屬 repo 之外的資料夾）下找不到程式碼根目錄。"
            f"請在 docs/traceability.yaml 設定頂層鍵 {CODE_ROOT_CONFIG_KEY}"
            "（被操作 repo 的路徑），或以 --code-root <路徑> 指定。"
        )
    return CodeRoot(doc_root, external)


def resolve_code_root_or_exit(doc_root: str, override: str | None = None) -> CodeRoot:
    """resolve_code_root 的命令列包裝：失敗時寫 stderr 並以 CODE_ROOT_EXIT_CODE 結束。"""
    try:
        return resolve_code_root(doc_root, override)
    except CodeRootError as e:
        sys.stderr.write(f"錯誤：{e}\n")
        sys.exit(CODE_ROOT_EXIT_CODE)


def format_code_path(rel_path: str, external: bool) -> str:
    """外接模式下為相對 code root 的路徑加 repo: 前綴（規格 2.4），單根原樣回傳。"""
    if not external:
        return rel_path
    return REPO_PATH_PREFIX + rel_path.replace(os.sep, "/")


# ID 前綴到 FileLocator 查詢方法的對應
ID_PREFIX_FINDERS = {
    "PROP": "find_proposal",
    "UC": "find_usecase",
    "SPEC": "find_spec",
    "EVT": "find_event",
}


class FileLocator:
    """定位 proposals/spec/usecases 文件的工具類別。"""

    def __init__(self, project_root: str) -> None:
        self.project_root = project_root
        root = Path(project_root)
        self.proposals_dir = str(root / "docs" / "proposals")
        self.spec_dir = str(root / "docs" / "spec")
        self.usecases_dir = str(root / "docs" / "usecases")
        self.events_dir = str(root / "docs" / "events")
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

    def find_event(self, event_id: str) -> str | None:
        """依 EVT ID 找到對應檔案路徑（含 domain 子目錄），找不到回傳 None。

        EVT 的 domain-scoped ID（如 EVT-LIBRARY-001）與 PROP/UC/SPEC 一樣
        僅需精確前綴比對，故沿用同一套 _find_file_by_id 邏輯，不需額外的
        EVT 特有解析規則。
        """
        return self._find_file_by_id(self.events_dir, event_id)

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
