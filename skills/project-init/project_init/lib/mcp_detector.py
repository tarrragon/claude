"""MCP server 偵測模組 — codebase-memory-mcp 與 codegraph CLI 檢查。

本模組偵測兩個 user-level MCP server binary 的可用性與本專案索引狀態，
配合 project-init check 與 SessionStart hook 在新環境/換電腦時提早暴露
MCP binary 缺失或索引未建立的問題（W6-001.2 / PC-159 防護）。
"""

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

# 索引狀態常數
INDEX_OK = "INDEX_OK"
INDEX_MISSING = "INDEX_MISSING"
INDEX_STALE = "INDEX_STALE"
INDEX_MCP_MANAGED = "INDEX_MCP_MANAGED"
INDEX_UNKNOWN = "INDEX_UNKNOWN"


@dataclass
class McpInfo:
    """MCP server 資訊."""

    name: str
    """顯示名稱（如 'codebase-memory-mcp' / 'codegraph'）."""
    version: str
    """版本字串（從 --version 或 --info 第一行擷取）."""
    path: Optional[str]
    """binary 絕對路徑."""
    is_available: bool
    """binary 是否在 PATH 中且可執行."""
    index_status: str = INDEX_UNKNOWN
    """本專案索引狀態（INDEX_OK / INDEX_MISSING / INDEX_STALE / INDEX_MCP_MANAGED / INDEX_UNKNOWN）."""
    failure_reason: Optional[str] = None
    """失敗原因（若 is_available 為 False）."""


def _detect_binary(
    name: str,
    version_args: Optional[list[str]] = None,
) -> tuple[Optional[str], str]:
    """偵測 binary 路徑與版本資訊。

    Args:
        name: binary 名稱（在 PATH 中查找）。
        version_args: 取得版本的參數，預設 ['--version']。
            對於不支援 --version 的 binary（如 codegraph-mcp），可傳 ['--info']。

    Returns:
        (path, version_first_line) tuple。binary 不存在或執行失敗時回 (None, '')。
    """
    if version_args is None:
        version_args = ["--version"]
    path = shutil.which(name)
    if path is None:
        return None, ""
    try:
        result = subprocess.run(
            [name] + version_args,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            first_line = result.stdout.strip().split("\n", 1)[0]
            return path, first_line
        return None, ""
    except subprocess.TimeoutExpired:
        return None, ""
    except Exception:
        return None, ""


def detect_codebase_memory_mcp() -> McpInfo:
    """偵測 codebase-memory-mcp CLI 可用性與版本。

    索引由 MCP 工具管理（CLI 不暴露），index_status 固定為 INDEX_MCP_MANAGED。

    Returns:
        McpInfo: 偵測結果。
    """
    path, version = _detect_binary("codebase-memory-mcp")
    if path is None:
        return McpInfo(
            name="codebase-memory-mcp",
            version="",
            path=None,
            is_available=False,
            failure_reason="codebase-memory-mcp 命令未在 PATH 中找到",
        )
    return McpInfo(
        name="codebase-memory-mcp",
        version=version,
        path=path,
        is_available=True,
        index_status=INDEX_MCP_MANAGED,
    )


def detect_codegraph(project_root: Optional[Path] = None) -> McpInfo:
    """偵測 codegraph (codegraph-mcp) CLI 與本專案索引狀態。

    @astudioplus/codegraph-mcp@0.16.6 之後 bin 名稱為 codegraph-mcp，
    版本資訊透過 --info 取得（不支援 --version）。
    若舊版環境仍提供 codegraph binary，亦能 fallback 偵測。

    Args:
        project_root: 專案根目錄，用於判定 .codegraph/ 索引存在性。
            None 時 index_status 為 INDEX_UNKNOWN。

    Returns:
        McpInfo: 偵測結果。
    """
    # 0.16.6+ 用 codegraph-mcp，舊版可能是 codegraph
    path, version = _detect_binary("codegraph-mcp", version_args=["--info"])
    if path is None:
        # Fallback：舊版 codegraph binary
        path, version = _detect_binary("codegraph", version_args=["--info"])

    if path is None:
        return McpInfo(
            name="codegraph",
            version="",
            path=None,
            is_available=False,
            failure_reason=(
                "codegraph-mcp 命令未在 PATH 中找到"
                "（請安裝 @astudioplus/codegraph-mcp）"
            ),
        )

    info = McpInfo(
        name="codegraph",
        version=version,
        path=path,
        is_available=True,
        index_status=INDEX_UNKNOWN,
    )

    if project_root is not None:
        info.index_status = _check_codegraph_index(project_root)

    return info


def _check_codegraph_index(project_root: Path) -> str:
    """檢查 project_root/.codegraph/ 目錄判定索引狀態。

    Args:
        project_root: 專案根目錄。

    Returns:
        INDEX_OK / INDEX_MISSING / INDEX_UNKNOWN 之一。

    Note:
        STALE 判定（索引晚於 src 變更）未在本版本實作，
        因為 codegraph-mcp 內建 file watcher 自動 sync（debounce ~500ms），
        STALE 通常為瞬時狀態而非穩定可偵測訊號。
    """
    codegraph_dir = project_root / ".codegraph"
    if not codegraph_dir.exists():
        return INDEX_MISSING
    if not codegraph_dir.is_dir():
        return INDEX_UNKNOWN
    return INDEX_OK
