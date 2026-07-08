#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
Version Tracking Consistency Guard Hook - 版本追蹤一致性守衛

觸發時機: SessionStart（每 session 必經，不可繞過）
模式: 提醒為主（不阻擋操作，exit 0）

背景：PC-MON-001 診斷出既有防護（version-release pre-flight 的 stale
active 掃描）放在可選 CLI 流程內，手動收尾路徑從未觸發，版本追蹤五載體
（git tag / todolist.yaml / ticket frontmatter / CHANGELOG / worklog 目錄）
持續漂移而不被發現。本 hook 將偵測動作前移到 session-start 必經路徑。

偵測六類漂移，異常寫 stderr 警告（雙通道：stderr + 日誌檔，
quality-baseline 規則 4）：

1. 多重 active 版本：todolist.yaml 中 status: active 的版本 > 1 個
2. 幽靈版本：worklog 目錄或 ticket 存在，但 todolist.yaml 無對應條目
3. 全完成未收版：某版本所有 ticket 皆 completed/closed，但 todolist
   status 仍為 active
4. tag-todolist drift：最新 git tag 對應版本，在 todolist.yaml 中的
   status 非 completed
5. closed 票延後承諾稽核：closed_by 缺失、非合法 Ticket ID，或
   close_reason_note 含延後語意（延後/移到/後續）卻無 ticket ID 引用
   （0.3.6-W1-006 稽核已知六張 0.3.0 歷史存量列豁免清單，技術債由
   0.3.6-W1-005 承接，避免重複噪音）
6. 提案層 stale：提案 target_version 在 todolist.yaml 已 completed，
   但提案 status 仍為 draft（0.3.6-W1-004 評估結論）
7. 提案未註冊 todolist：提案 status 為 confirmed 且 target_version 非
   null，但 target_version 未在 todolist.yaml 中登記（任何 status 皆算
   已登記）。缺席時 activate 版本推進看不到此候選（0.38.0-W1-002，PROP-016
   實證：confirmed 且 target_version=v0.38.0，但提案確認流程無 todolist
   註冊步驟，導致 activate 誤選 1.0.0）
8. 版本目錄缺 main worklog：todolist.yaml 中 status 為 active/planned 的
   版本，其 worklog 目錄已存在，但目錄下無 v{version}-main.md（實證：
   v0.37.0 目錄缺 main worklog 達三個月，既有幽靈偵測只查 todolist 條目
   缺席，未查目錄「存在但缺檔案」的維度）。僅查 active/planned 是歷史盤點
   結論——本 repo 33 個版本目錄中 16 個為 completed 存量且無 main.md，若
   全量檢查將重演噪音淹沒訊號（W9-003 教訓），故限縮為只查尚在進行/待辦
   的版本

來源: PC-MON-001、0.4.0-W1-003、0.3.6-W1-006、0.3.6-W1-004、0.38.0-W1-002、
0.38.0-W1-005
"""

import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))
from lib import setup_hook_logging, run_hook_safely, get_project_root, parse_ticket_frontmatter

VERSION_DIR_PATTERN = re.compile(r"^v(\d+\.\d+\.\d+)$")
VERSION_ENTRY_PATTERN = re.compile(
    r'-\s*version:\s*["\']?(\d+\.\d+\.\d+)["\']?\s*\n(?:.*\n)*?\s*status:\s*["\']?(\w+)["\']?'
)
# 純 semver 格式（X.Y.Z，皆為數字）。用於過濾 ticket frontmatter 中非
# semver 的 version token（如 "0.22.x"、"可選"），避免誤列為幽靈版本。
SEMVER_PATTERN = re.compile(r"^\d+\.\d+\.\d+$")
TAG_VERSION_PATTERN = re.compile(r"^v(\d+\.\d+\.\d+)$")
COMPLETED_TICKET_STATUSES = {"completed", "closed"}

# 漂移 5：closed 票延後承諾稽核用常數
# 與 ticket_system/constants.py TICKET_ID_PATTERN 同構，本 hook 不 import
# ticket_system（避免拉入 yaml 依賴鏈，PEP 723 dependencies = []）。
CLOSED_BY_TICKET_ID_PATTERN = re.compile(
    r"^(\d+\.\d+\.\d+)-W(\d+)-(\d+(?:\.\d+)*)(-[a-z0-9][a-z0-9-]{0,59})?$"
)
TICKET_ID_REF_PATTERN = re.compile(
    r"\d+\.\d+\.\d+-W\d+-\d+(?:\.\d+)*(?:-[a-z0-9][a-z0-9-]{0,59})?"
)
DEFER_SEMANTIC_PATTERN = re.compile(r"延後|移到|後續")
CLOSED_BY_NONE_TOKEN = "none"

# 0.3.6-W1-006 全歷史稽核已知六張 0.3.0 存量票：延後語意但無 follow-up
# ticket ID 引用，技術債由 0.3.6-W1-005 承接（非本 hook 職責），故豁免以
# 避免每 session 重複噪音。
KNOWN_LEGACY_CLOSED_TICKET_IDS = frozenset(
    {
        "0.3.0-W1-004",
        "0.3.0-W1-005",
        "0.3.0-W1-006",
        "0.3.0-W1-007",
        "0.3.0-W2-008",
        "0.3.0-W3-005",
    }
)

# 漂移 6/7：提案層偵測用常數
# 對應 docs/proposals-tracking.yaml 實際結構：`  - id: PROP-016`（YAML 清單項）。
PROPOSAL_ID_PATTERN = re.compile(r"^\s*-\s*id:\s*(PROP-\d+)\s*$", re.MULTILINE)
# 區塊邊界：任何未縮排（頂層 key，如 `usecases:`）行，避免最後一個提案的
# 區塊解析吞噬後續頂層區塊內容。
SECTION_BOUNDARY_PATTERN = re.compile(r"^\S", re.MULTILINE)

# 漂移 8：main worklog 缺席偵測僅查此範圍內的 status。completed 版本歷史
# 存量大量缺 main.md（33 個版本目錄中 16 個），全量檢查將重演噪音淹沒訊號
# （W9-003 教訓），故限縮為進行中/待辦版本。
MAIN_WORKLOG_CHECK_STATUSES = frozenset({"active", "planned"})


def parse_todolist(todolist_path: Path, logger) -> dict:
    """解析 todolist.yaml，回傳 {version: status} 字典。

    採 regex 逐項解析（與既有 version-consistency-guard-hook 一致的手法），
    避免額外引入 YAML 套件依賴（PEP 723 dependencies = []）。
    """
    if not todolist_path.exists():
        return {}

    try:
        content = todolist_path.read_text(encoding="utf-8")
    except OSError as exc:
        logger.warning("讀取 todolist.yaml 失敗: %s", exc)
        return {}

    versions: dict[str, str] = {}
    for match in VERSION_ENTRY_PATTERN.finditer(content):
        version, status = match.group(1), match.group(2)
        versions[version] = status
    return versions


def scan_worklog_versions(project_root: Path) -> set[str]:
    """掃描 docs/work-logs/ 下所有 vX.Y.Z 葉節點目錄，回傳版本號集合。"""
    work_logs_dir = project_root / "docs" / "work-logs"
    if not work_logs_dir.exists():
        return set()

    versions: set[str] = set()
    for path in work_logs_dir.rglob("v*"):
        if not path.is_dir():
            continue
        match = VERSION_DIR_PATTERN.match(path.name)
        if match:
            versions.add(match.group(1))
    return versions


def scan_ticket_versions(project_root: Path) -> set[str]:
    """掃描所有 ticket 檔案的 frontmatter version 欄位，回傳版本號集合。

    僅回傳純 semver 格式（X.Y.Z）token；非 semver token（如 "0.22.x"、
    "可選" 等歷史存量 ticket 的佔位/範圍值）不視為版本，避免誤列幽靈版本。
    """
    tickets_root = project_root / "docs" / "work-logs"
    if not tickets_root.exists():
        return set()

    versions: set[str] = set()
    for ticket_file in tickets_root.rglob("tickets/*.md"):
        frontmatter = parse_ticket_frontmatter(ticket_file)
        version = frontmatter.get("version")
        if not version:
            continue
        token = str(version).strip("'\"")
        if SEMVER_PATTERN.match(token):
            versions.add(token)
    return versions


def get_latest_git_tag_version(project_root: Path, logger) -> str | None:
    """取得最新（依 semver 排序）git tag 對應的版本號，取不到時回傳 None。

    只認 HEAD 可達的 tags（--merged HEAD）：框架 repo（tarrragon/claude.git）
    的版本 tags（v2.x 系列）若因 sync-pull 未加 --no-tags 而混入本地，其指向
    的 commit 不在本 APP repo 的 HEAD 歷史內，--merged 過濾天然排除，不需
    額外維護版本範圍白名單（0.37.0-W9-005）。
    """
    try:
        result = subprocess.run(
            ["git", "-C", str(project_root), "tag", "--merged", "HEAD", "--sort=-v:refname"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        logger.info("git tag 查詢失敗: %s", exc)
        return None

    if result.returncode != 0:
        return None

    for line in result.stdout.splitlines():
        match = TAG_VERSION_PATTERN.match(line.strip())
        if match:
            return match.group(1)
    return None


def get_version_ticket_statuses(project_root: Path, version: str) -> list[str]:
    """回傳指定版本目錄下所有 ticket 的 status 清單（空清單代表無 ticket 或目錄不存在）。"""
    parts = version.split(".")
    if len(parts) != 3:
        return []
    major_dir = f"v{parts[0]}"
    minor_dir = f"v{parts[0]}.{parts[1]}"
    patch_dir = f"v{version}"
    tickets_dir = (
        project_root / "docs" / "work-logs" / major_dir / minor_dir / patch_dir / "tickets"
    )
    if not tickets_dir.exists():
        return []

    statuses = []
    for ticket_file in sorted(tickets_dir.glob("*.md")):
        frontmatter = parse_ticket_frontmatter(ticket_file)
        status = frontmatter.get("status")
        if status:
            statuses.append(status)
    return statuses


def detect_multiple_active(versions: dict[str, str]) -> list[str]:
    """偵測漂移 1：多重 active 版本"""
    active = [v for v, status in versions.items() if status == "active"]
    return sorted(active) if len(active) > 1 else []


def detect_ghost_versions(versions: dict[str, str], project_root: Path) -> list[str]:
    """偵測漂移 2：worklog 目錄或 ticket 存在，但 todolist.yaml 無條目"""
    known = scan_worklog_versions(project_root) | scan_ticket_versions(project_root)
    ghosts = known - set(versions.keys())
    return sorted(ghosts)


def detect_stale_active(versions: dict[str, str], project_root: Path) -> list[str]:
    """偵測漂移 3：版本所有 ticket 皆完成，但 todolist status 仍為 active"""
    stale = []
    for version, status in versions.items():
        if status != "active":
            continue
        statuses = get_version_ticket_statuses(project_root, version)
        if statuses and all(s in COMPLETED_TICKET_STATUSES for s in statuses):
            stale.append(version)
    return sorted(stale)


def detect_missing_main_worklog(versions: dict[str, str], project_root: Path) -> list[str]:
    """偵測漂移 8：版本目錄存在但缺 v{version}-main.md

    僅查 MAIN_WORKLOG_CHECK_STATUSES（active/planned）版本，且僅在版本目錄
    已存在時才檢查（尚未開工的版本目錄不存在，不誤報）。
    """
    missing = []
    for version, status in versions.items():
        if status not in MAIN_WORKLOG_CHECK_STATUSES:
            continue
        parts = version.split(".")
        if len(parts) != 3:
            continue
        major_dir = f"v{parts[0]}"
        minor_dir = f"v{parts[0]}.{parts[1]}"
        patch_dir = f"v{version}"
        version_dir = project_root / "docs" / "work-logs" / major_dir / minor_dir / patch_dir
        if not version_dir.is_dir():
            continue
        if not (version_dir / f"v{version}-main.md").exists():
            missing.append(version)
    return sorted(missing)


def detect_tag_drift(versions: dict[str, str], project_root: Path, logger) -> str | None:
    """偵測漂移 4：最新 git tag 版本在 todolist.yaml 中非 completed"""
    latest_tag_version = get_latest_git_tag_version(project_root, logger)
    if not latest_tag_version:
        return None
    status = versions.get(latest_tag_version)
    if status != "completed":
        return latest_tag_version
    return None


def scan_closed_tickets(project_root: Path, logger) -> list[dict]:
    """掃描全歷史 ticket 檔案，回傳 status=closed 的 frontmatter dict 清單（含 _path）。"""
    tickets_root = project_root / "docs" / "work-logs"
    if not tickets_root.exists():
        return []

    closed: list[dict] = []
    for ticket_file in tickets_root.rglob("tickets/*.md"):
        frontmatter = parse_ticket_frontmatter(ticket_file, logger)
        if frontmatter.get("status") != "closed":
            continue
        frontmatter["_path"] = ticket_file
        closed.append(frontmatter)
    return closed


def detect_closed_ticket_anomalies(closed_tickets: list[dict]) -> list[str]:
    """偵測漂移 5：closed 票 closed_by 缺失/非合法 ID，或 note 含延後語意無 ticket ID 引用。

    已知六張 0.3.0 歷史存量（KNOWN_LEGACY_CLOSED_TICKET_IDS）列入豁免，
    避免每 session 重複噪音（0.3.6-W1-006 稽核結論）。
    """
    anomalies: list[str] = []
    for frontmatter in closed_tickets:
        ticket_id = frontmatter.get("id") or str(frontmatter.get("_path", ""))
        if ticket_id in KNOWN_LEGACY_CLOSED_TICKET_IDS:
            continue

        closed_by = str(frontmatter.get("closed_by") or "").strip()
        reason_note = str(frontmatter.get("close_reason_note") or "").strip()

        if not closed_by:
            anomalies.append(f"{ticket_id}: closed_by 缺失")
            continue

        if closed_by.lower() != CLOSED_BY_NONE_TOKEN and not CLOSED_BY_TICKET_ID_PATTERN.match(closed_by):
            anomalies.append(f"{ticket_id}: closed_by 非合法 Ticket ID（{closed_by!r}）")
            continue

        if DEFER_SEMANTIC_PATTERN.search(reason_note) and not TICKET_ID_REF_PATTERN.search(reason_note):
            anomalies.append(f"{ticket_id}: close_reason_note 含延後語意但無 ticket ID 引用")

    return sorted(anomalies)


def parse_proposals(proposals_path: Path, logger) -> dict:
    """解析 proposals-tracking.yaml，回傳
    {proposal_id: {"status": str, "target_version": str | None}}。

    target_version 欄位缺席（如 PROP-007 這類尚未指定目標版本的提案）時
    該鍵值為 None，交由呼叫端（漂移 6/7）依語意決定是否略過。
    """
    if not proposals_path.exists():
        return {}

    try:
        content = proposals_path.read_text(encoding="utf-8")
    except OSError as exc:
        logger.warning("讀取 proposals-tracking.yaml 失敗: %s", exc)
        return {}

    markers = list(PROPOSAL_ID_PATTERN.finditer(content))
    boundaries = [m.start() for m in SECTION_BOUNDARY_PATTERN.finditer(content)]
    proposals: dict[str, dict] = {}
    for index, marker in enumerate(markers):
        proposal_id = marker.group(1)
        start = marker.end()
        next_marker_start = markers[index + 1].start() if index + 1 < len(markers) else len(content)
        next_boundary = next((b for b in boundaries if b > start), len(content))
        end = min(next_marker_start, next_boundary)
        block = content[start:end]

        status_match = re.search(r"^\s*status:\s*(\w+)", block, re.MULTILINE)
        if not status_match:
            continue
        version_match = re.search(
            r'^\s*target_version:\s*["\']?v?(\d+\.\d+\.\d+)["\']?', block, re.MULTILINE
        )

        proposals[proposal_id] = {
            "status": status_match.group(1),
            "target_version": version_match.group(1) if version_match else None,
        }
    return proposals


def detect_stale_proposals(proposals: dict, versions: dict[str, str]) -> list[str]:
    """偵測漂移 6：提案 target_version 在 todolist.yaml 已 completed，但提案 status 仍 draft"""
    stale: list[str] = []
    for proposal_id, info in proposals.items():
        if info["status"] != "draft":
            continue
        target_version = info.get("target_version")
        if not target_version:
            continue
        target_status = versions.get(target_version)
        if target_status == "completed":
            stale.append(f"{proposal_id}（target_version v{target_version} 已 completed）")
    return sorted(stale)


def detect_unregistered_confirmed_proposals(proposals: dict, versions: dict[str, str]) -> list[str]:
    """偵測漂移 7：confirmed 提案 target_version 未在 todolist.yaml 註冊。

    對賬方向與漂移 6 相反：漂移 6 查「已註冊但收版慢半拍」，本項查
    「提案已 confirmed 但從未進入 todolist 候選清單」——未註冊時
    activate 版本推進邏輯看不到此候選（0.38.0-W1-002 背景：PROP-016
    confirmed + target_version=v0.38.0，但 0.38.0 缺席 planned 清單，
    導致 activate 誤選 1.0.0）。target_version 已在 todolist.yaml 中
    登記即視為已知（不論 status 為 planned/active/completed）。
    """
    unregistered: list[str] = []
    for proposal_id, info in proposals.items():
        if info["status"] != "confirmed":
            continue
        target_version = info.get("target_version")
        if not target_version:
            continue
        if target_version not in versions:
            unregistered.append(
                f"{proposal_id}（target_version v{target_version} 未註冊 todolist.yaml）"
            )
    return sorted(unregistered)


def build_warning_lines(
    multiple_active: list[str],
    ghosts: list[str],
    stale_active: list[str],
    tag_drift_version: str | None,
    versions: dict[str, str],
    closed_ticket_anomalies: list[str],
    stale_proposals: list[str],
    unregistered_confirmed_proposals: list[str],
    missing_main_worklog: list[str],
) -> list[str]:
    """組裝警告訊息行。無漂移時回傳空清單（呼叫端據此判斷是否輸出）。"""
    lines: list[str] = []

    if multiple_active:
        lines.append(f"[多重 active 版本] {', '.join(multiple_active)} 同時標記 active，應僅保留一個")

    if ghosts:
        lines.append(f"[幽靈版本] worklog/ticket 存在但 todolist.yaml 無條目: {', '.join(ghosts)}")

    if stale_active:
        lines.append(f"[全完成未收版] 版本 ticket 已全數完成，但 status 仍為 active: {', '.join(stale_active)}")

    if tag_drift_version:
        actual_status = versions.get(tag_drift_version, "(無條目)")
        lines.append(
            f"[tag-todolist drift] 最新 git tag v{tag_drift_version} 對應版本，"
            f"todolist.yaml status 為 {actual_status}（預期 completed）"
        )

    if closed_ticket_anomalies:
        lines.append(
            "[closed 票延後承諾稽核] closed_by 缺失/非法或延後語意無 ticket ID 引用: "
            + "; ".join(closed_ticket_anomalies)
        )

    if stale_proposals:
        lines.append(
            "[提案層 stale] target_version 已 completed 但提案 status 仍 draft: "
            + ", ".join(stale_proposals)
        )

    if unregistered_confirmed_proposals:
        lines.append(
            "[提案未註冊 todolist] confirmed 提案 target_version 未登記，"
            "activate 推進將看不到此候選: " + ", ".join(unregistered_confirmed_proposals)
        )

    if missing_main_worklog:
        lines.append(
            "[缺 main worklog] 版本目錄存在但缺 v{version}-main.md（僅查 "
            "active/planned，避免歷史存量噪音）: " + ", ".join(missing_main_worklog)
        )

    return lines


def print_warnings(lines: list[str]) -> None:
    """輸出警告區塊至 stdout（session-start hook 訊息通道，用戶可見）"""
    print()
    print("=" * 60)
    print("[Version Tracking Consistency Guard] 版本追蹤一致性掃描")
    print("=" * 60)
    print()
    print("docs/todolist.yaml 與實際狀態（git tag / worklog / ticket）不一致：")
    print()
    for line in lines:
        print(f"  - {line}")
    print()
    print("建議：校準 docs/todolist.yaml，或補建缺漏版本條目")
    print("背景：.claude/error-patterns/process-compliance/PC-MON-001-guard-on-bypassable-execution-point.md")
    print()
    print("=" * 60)
    print()


def main() -> int:
    logger = setup_hook_logging("version-tracking-consistency-guard")
    project_root = get_project_root()

    if not project_root:
        logger.debug("無法定位 project root，跳過掃描")
        return 0

    project_root = Path(project_root)

    try:
        todolist_path = project_root / "docs" / "todolist.yaml"
        versions = parse_todolist(todolist_path, logger)

        if not versions:
            logger.debug("todolist.yaml 無法解析或無版本條目，跳過掃描")
            return 0

        multiple_active = detect_multiple_active(versions)
        ghosts = detect_ghost_versions(versions, project_root)
        stale_active = detect_stale_active(versions, project_root)
        tag_drift_version = detect_tag_drift(versions, project_root, logger)

        closed_tickets = scan_closed_tickets(project_root, logger)
        closed_ticket_anomalies = detect_closed_ticket_anomalies(closed_tickets)

        proposals_path = project_root / "docs" / "proposals-tracking.yaml"
        proposals = parse_proposals(proposals_path, logger)
        stale_proposals = detect_stale_proposals(proposals, versions)
        unregistered_confirmed_proposals = detect_unregistered_confirmed_proposals(proposals, versions)

        missing_main_worklog = detect_missing_main_worklog(versions, project_root)

        lines = build_warning_lines(
            multiple_active,
            ghosts,
            stale_active,
            tag_drift_version,
            versions,
            closed_ticket_anomalies,
            stale_proposals,
            unregistered_confirmed_proposals,
            missing_main_worklog,
        )

        if lines:
            print_warnings(lines)
            logger.info("偵測到 %d 項版本追蹤漂移: %s", len(lines), "; ".join(lines))
        else:
            logger.debug("版本追蹤一致性掃描：無漂移")
    except Exception as exc:  # noqa: BLE001 — 失敗安全：掃描異常不阻擋 session，僅雙通道記錄
        sys.stderr.write(f"[version-tracking-consistency-guard] 掃描異常: {exc}\n")
        logger.error("版本追蹤一致性掃描異常: %s", exc, exc_info=True)

    return 0


if __name__ == "__main__":
    sys.exit(run_hook_safely(main, "version-tracking-consistency-guard"))
