#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml"]
# ///
"""
Spec 版本標示一致性檢查 Hook

觸發時機: SessionStart
模式: 提醒為主（不阻擋操作），一致時靜默

動機: 0.4.1-W1-001 摩擦 F2 — SPEC-014 frontmatter version 與版本歷史表
各改一半造成雙軌漂移，需人工於 commit 624e077 手動對齊。本 hook 在
session 啟動時自動掃描 docs/spec/**/*.md，偵測 frontmatter version
與「## 變更歷史」表格最大版號是否一致，漂移時輸出警告（含兩處版號），
一致時不輸出任何內容。

檢查邏輯:
1. 掃描 docs/spec/**/*.md
2. 解析 frontmatter 的 version 欄位
3. 解析「## 變更歷史」表格，取第一欄可解析為版號的最大值
4. 兩者不一致 → 輸出警告；缺 frontmatter 或缺變更歷史表 → 略過該檔
"""

import re
import sys
from pathlib import Path
from typing import List, NamedTuple, Optional, Tuple

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))
from lib import setup_hook_logging, run_hook_safely, get_project_root

HOOK_NAME = "spec-version-consistency-check-hook"

SPEC_GLOB = "docs/spec/**/*.md"
CHANGE_HISTORY_HEADING = "## 變更歷史"
FRONTMATTER_VERSION_PATTERN = re.compile(r'^version:\s*"?([0-9]+(?:\.[0-9]+)*)"?\s*$', re.MULTILINE)
HISTORY_ROW_VERSION_PATTERN = re.compile(r'^\|\s*([0-9]+(?:\.[0-9]+)*)\s*\|')
FRONTMATTER_BLOCK_PATTERN = re.compile(r'^---\n(.*?)\n---\n', re.DOTALL)


class DriftResult(NamedTuple):
    """單一 spec 檔案的版號漂移檢查結果"""

    file_path: Path
    frontmatter_version: str
    history_max_version: str


def _version_key(version: str) -> Tuple[int, ...]:
    """將版號字串轉為可比較的整數 tuple，例如 "1.10" -> (1, 10)"""
    return tuple(int(part) for part in version.split(".") if part.isdigit())


def extract_frontmatter_version(content: str) -> Optional[str]:
    """從 frontmatter 區塊擷取 version 欄位值

    Args:
        content: spec 檔案完整內容

    Returns:
        版號字串（如 "1.2"），frontmatter 不存在或無 version 欄位時回傳 None
    """
    block_match = FRONTMATTER_BLOCK_PATTERN.match(content)
    if not block_match:
        return None

    frontmatter_body = block_match.group(1)
    version_match = FRONTMATTER_VERSION_PATTERN.search(frontmatter_body)
    if not version_match:
        return None

    return version_match.group(1)


def extract_history_max_version(content: str) -> Optional[str]:
    """從「## 變更歷史」表格擷取最大版號

    只掃描該標題之後、下一個「## 」標題之前的區段，避免誤取其他表格的版號列。

    Args:
        content: spec 檔案完整內容

    Returns:
        表格中最大的版號字串，找不到變更歷史區段或表格內無版號列時回傳 None
    """
    heading_index = content.find(CHANGE_HISTORY_HEADING)
    if heading_index == -1:
        return None

    section = content[heading_index + len(CHANGE_HISTORY_HEADING):]
    next_heading_index = section.find("\n## ")
    if next_heading_index != -1:
        section = section[:next_heading_index]

    versions: List[str] = []
    for line in section.splitlines():
        row_match = HISTORY_ROW_VERSION_PATTERN.match(line.strip())
        if row_match:
            versions.append(row_match.group(1))

    if not versions:
        return None

    return max(versions, key=_version_key)


def check_spec_file(file_path: Path) -> Optional[DriftResult]:
    """檢查單一 spec 檔案的 frontmatter 版號與變更歷史最大版號是否一致

    Args:
        file_path: spec 檔案絕對路徑

    Returns:
        版號不一致時回傳 DriftResult；一致或資料不足（缺任一來源）時回傳 None
    """
    try:
        content = file_path.read_text(encoding="utf-8")
    except OSError:
        return None

    frontmatter_version = extract_frontmatter_version(content)
    history_max_version = extract_history_max_version(content)

    if frontmatter_version is None or history_max_version is None:
        return None

    if _version_key(frontmatter_version) == _version_key(history_max_version):
        return None

    return DriftResult(
        file_path=file_path,
        frontmatter_version=frontmatter_version,
        history_max_version=history_max_version,
    )


def scan_spec_drifts(project_root: Path) -> List[DriftResult]:
    """掃描 docs/spec/ 底下所有 spec 檔案，回傳所有版號漂移結果

    Args:
        project_root: 專案根目錄

    Returns:
        漂移結果列表；無漂移時回傳空列表
    """
    drifts: List[DriftResult] = []
    for file_path in sorted(project_root.glob(SPEC_GLOB)):
        drift = check_spec_file(file_path)
        if drift is not None:
            drifts.append(drift)

    return drifts


def format_drift_warning(drifts: List[DriftResult], project_root: Path) -> str:
    """將漂移結果格式化為警告訊息

    Args:
        drifts: 漂移結果列表
        project_root: 專案根目錄（用於顯示相對路徑）

    Returns:
        警告訊息文字
    """
    lines = ["[Spec Version Drift] 偵測到 frontmatter 與變更歷史表版號不一致："]
    for drift in drifts:
        relative_path = drift.file_path.relative_to(project_root)
        lines.append(
            f"  - {relative_path}: frontmatter={drift.frontmatter_version}, "
            f"變更歷史最大版號={drift.history_max_version}"
        )
    return "\n".join(lines)


def main() -> int:
    """主函數"""
    logger = setup_hook_logging(HOOK_NAME)
    project_root = get_project_root()

    drifts = scan_spec_drifts(project_root)

    if not drifts:
        logger.info("Spec 版本一致性檢查完成，無漂移")
        return 0

    warning = format_drift_warning(drifts, project_root)
    print(warning, file=sys.stderr)
    logger.warning(warning)
    return 0


if __name__ == "__main__":
    sys.exit(run_hook_safely(main, HOOK_NAME))
