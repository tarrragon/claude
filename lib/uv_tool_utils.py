"""
uv tool install 安裝的 skill 之 source vs installed 偵測共用工具。

職責：抽取自 ticket-reinstall-hook 的 SHA256 hash 比對與安裝定位邏輯，
供 uv-tool-staleness-check-hook（多 skill 偵測）與 ticket-reinstall-hook
（單 skill 自動修復）共用，避免 ARCH-020 平行實作家族。

對應規則 4：所有 except 必須記錄至 logger（hook_utils 預設雙通道 stderr + file）。
"""

from __future__ import annotations

import hashlib
import logging
import subprocess
from pathlib import Path
from typing import Dict, Optional, Set, Tuple

# 預設排除目錄。ticket-reinstall-hook 傳入 {"__pycache__", ".venv"} 維持原行為；
# uv-tool-staleness-check-hook 額外排除 "tests"（測試碼不影響 installed 行為）。
DEFAULT_EXCLUDE_DIRS: Set[str] = {"__pycache__", ".venv"}
STALENESS_EXCLUDE_DIRS: Set[str] = {"__pycache__", ".venv", "tests"}

# cwd-resolving shim 識別標記（ARCH-APP-002）。
# 字面須與 .claude/scripts/install-skill-clis.py 的 SHIM_MARKER 完全一致；
# is_shimmed_cli 與 installer --check 共用此標記辨認「這是 shim 非 uv tool bin」。
SHIM_MARKER = "# cwd-resolving shim (ARCH-APP-002)"


def is_shimmed_cli(cli_name: str, logger: Optional[logging.Logger] = None) -> bool:
    """
    判斷 PATH 上的 CLI 是否為 cwd-resolving shim（而非 uv tool install 的 bin）。

    流程：`which <cli_name>` 取得 binary 路徑後，讀其內容檢查 SHIM_MARKER。
    shim 化的 CLI 不應被 staleness / ownership / reinstall hook 視為 stale，
    否則 uv tool reinstall 會把 shim 蓋回（ARCH-APP-002 根因）。

    Args:
        cli_name: CLI 名稱（如 "ticket" / "doc" / "worktree"）
        logger: 可選日誌器（失敗時 debug 記錄）

    Returns:
        True 表示該 CLI 為 shim；False 表示非 shim 或無法判定（找不到 / 讀取失敗）。
    """
    try:
        result = subprocess.run(
            ["which", cli_name],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=5,  # magic-exempt: which 子程序逾時秒數，與本檔既有 which 呼叫一致
        )
        if result.returncode != 0 or not result.stdout.strip():
            return False
        binary = Path(result.stdout.strip())
        return SHIM_MARKER in binary.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        if logger:
            logger.debug(f"is_shimmed_cli({cli_name}) failed: {e}")
        return False


# 判定重裝來源是否為主 checkout 的 git 子程序逾時（秒）
REINSTALL_ROOT_CHECK_TIMEOUT = 5


def reinstall_skip_reason(
    project_root: Path, logger: Optional[logging.Logger] = None
) -> Optional[str]:
    """
    判定能否以 project_root 的源碼重裝全域 uv tool，不能時回傳原因。

    `uv tool install . --reinstall` 會把來源目錄的源碼複製進全域 tool 環境，
    影響所有 session，直到下次重裝。來源若是 linked worktree，全域 CLI 就換成
    該 worktree 尚未合併的版本，所以只有主 checkout 可以自動重裝。

    判據：`git rev-parse --git-dir --git-common-dir`，兩者相同為主 checkout，
    不同為 linked worktree。git 失敗、逾時或輸出不完整時視為無法判定，
    回傳原因（不重裝）：無法確認來源是主 checkout，就不拿它覆蓋全域 CLI。
    這點和 hook_base._linked_worktree_root、git_utils.is_in_worktree 不同，
    它們在判定失敗時回「非 worktree」。

    Args:
        project_root: 準備作為重裝來源的專案根
        logger: 可選日誌器；不重裝時以 warning 記錄原因

    Returns:
        None 表示 project_root 為主 checkout，可以重裝；字串為不重裝的原因。
    """
    reason = _probe_reinstall_root(project_root)
    if reason is not None and logger:
        logger.warning(f"reinstall_skip_reason({project_root}): {reason}")
    return reason


def _probe_reinstall_root(project_root: Path) -> Optional[str]:
    """執行 git 判定；回傳 None（主 checkout）或不重裝原因。"""
    try:
        result = subprocess.run(
            [
                "git", "-C", str(project_root), "rev-parse",
                "--path-format=absolute", "--git-dir", "--git-common-dir",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=REINSTALL_ROOT_CHECK_TIMEOUT,
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        return f"無法判定 {project_root} 是否為主 checkout（git 執行失敗：{e}）"

    if result.returncode != 0:
        detail = result.stderr.strip()[:200]
        return (
            f"無法判定 {project_root} 是否為主 checkout"
            f"（git rev-parse rc={result.returncode}：{detail}）"
        )

    lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    if len(lines) < 2:
        return f"無法判定 {project_root} 是否為主 checkout（git rev-parse 輸出不完整）"

    git_dir = Path(lines[0]).resolve()
    common_dir = Path(lines[1]).resolve()
    if git_dir == common_dir:
        return None
    return (
        f"{project_root} 是 linked worktree（主 checkout 為 {common_dir.parent}），"
        "從這裡重裝會以該 worktree 的源碼覆蓋全域 CLI"
    )


def compute_file_hashes(
    directory: Path,
    exclude_dirs: Optional[Set[str]] = None,
) -> Dict[str, str]:
    """
    計算目錄下所有 .py 檔案的 SHA256 hash。

    Args:
        directory: 來源目錄
        exclude_dirs: 排除的子目錄名稱集合（任一路徑成分匹配即排除）

    Returns:
        {relative_path_str: sha256_hex}；目錄不存在或讀取失敗時回傳空 dict
        或部分結果（單檔失敗跳過該檔）。
    """
    hashes: Dict[str, str] = {}
    if exclude_dirs is None:
        exclude_dirs = DEFAULT_EXCLUDE_DIRS

    if not directory.exists():
        return hashes

    try:
        for py_file in sorted(directory.rglob("*.py")):
            if any(part in exclude_dirs for part in py_file.parts):
                continue
            try:
                with open(py_file, "rb") as f:
                    file_hash = hashlib.sha256(f.read()).hexdigest()
                    rel_path = py_file.relative_to(directory)
                    hashes[str(rel_path)] = file_hash
            except Exception:
                # 單檔讀取失敗跳過；不中斷整體掃描
                pass
    except Exception:
        # 遞迴掃描異常時回傳已收集的部分結果
        pass

    return hashes


def find_installed_module_dir(
    cli_name: str,
    package_dir_name: str,
    logger: logging.Logger,
) -> Optional[Path]:
    """
    定位 uv tool 安裝的 module 目錄。

    流程：
      1. `which <cli_name>` 取得 CLI binary 路徑
      2. 讀 binary shebang 取得 Python interpreter 路徑
      3. 透過 interpreter 取得 site-packages
      4. 回傳 site-packages/<package_dir_name>

    Args:
        cli_name: CLI 名稱（如 "ticket" / "doc"）
        package_dir_name: site-packages 下的子目錄名（如 "ticket_system"）
        logger: 日誌器

    Returns:
        module 目錄 Path，或 None（任一步失敗）
    """
    try:
        which_result = subprocess.run(
            ["which", cli_name],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=5,
        )
        if which_result.returncode != 0 or not which_result.stdout.strip():
            logger.debug(f"CLI {cli_name} not found via which")
            return None
        cli_binary = Path(which_result.stdout.strip())
    except Exception as e:
        logger.debug(f"which {cli_name} failed: {e}")
        return None

    try:
        with open(cli_binary, "r", encoding="utf-8", errors="ignore") as f:
            shebang = f.readline()
        if not shebang.startswith("#!"):
            logger.debug(f"Invalid shebang in {cli_binary}")
            return None
        python_path = shebang[2:].strip()
        if not python_path:
            return None
    except Exception as e:
        logger.debug(f"Cannot read shebang from {cli_binary}: {e}")
        return None

    try:
        site_result = subprocess.run(
            [python_path, "-c", "import site; print(site.getsitepackages()[0])"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=5,
        )
        if site_result.returncode != 0:
            logger.debug(f"site.getsitepackages failed for {python_path}")
            return None
        site_packages = Path(site_result.stdout.strip())
    except Exception as e:
        logger.debug(f"Failed to query site-packages: {e}")
        return None

    module_dir = site_packages / package_dir_name
    if not module_dir.exists():
        logger.debug(f"Module dir {module_dir} does not exist")
        return None
    return module_dir


def compare_hash_sets(
    source_hashes: Dict[str, str],
    installed_hashes: Dict[str, str],
) -> Tuple[bool, Dict[str, object]]:
    """
    比對 source 與 installed 的 hash 集合。

    Returns:
        (is_identical, {"added": set, "removed": set, "modified": list})
    """
    source_files = set(source_hashes.keys())
    installed_files = set(installed_hashes.keys())

    differences: Dict[str, object] = {
        "added": source_files - installed_files,
        "removed": installed_files - source_files,
        "modified": [],
    }

    modified = []
    for file_path in source_files & installed_files:
        if source_hashes[file_path] != installed_hashes[file_path]:
            modified.append(file_path)
    differences["modified"] = modified

    is_identical = not (
        differences["added"] or differences["removed"] or modified
    )
    return is_identical, differences
