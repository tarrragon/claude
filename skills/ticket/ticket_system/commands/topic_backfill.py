"""既有 pending 票的主題分批回填入口。

背景：建票時標記只覆蓋增量，存量 pending 票（量測時 190 張，日換血率
31.2%）需要獨立的回填入口，逐批將既有票指派至 `topic_registry` 維護的
中央主題清單。回填只寫「中央清單」（本模組定義的 assignment log +
topic_registry 的主題名清單），不寫任何 ticket frontmatter 欄位——ticket
檔案本身在整個回填流程中不被開啟為寫入目標，僅以唯讀方式解析
frontmatter 取得 id / status。

設計決策（Solution 記錄詳述，此處摘要供程式碼閱讀者對照）：

    映射載體 —— 為何新增 `docs/work-logs/topic-assignments.txt`，
    不合併進 `topics-registry.txt`：
        `topic_registry.py` 的 `topics-registry.txt` 語意是「主題名去重
        清單」（單欄，正規化去重比對主題名本身）。回填需要的是
        「ticket_id -> topic」的雙欄映射，兩者是不同維度的資料（一份是
        值域去重清單，一份是鍵值對應表）。混入單欄清單會破壞其正規化
        去重邏輯對「一行一主題名」的格式假設；`topic_registry.py` 本身
        由並行任務維護不可修改，故映射另立同層檔案，格式比照
        `topics-registry.txt` 的 append-only 純文字設計（tab 分隔
        `ticket_id\\ttopic`，人可讀、diff 最小）。

    續作起點 —— 為何不另存進度檔：
        `list_unassigned_pending_tickets()` 直接以「pending 票集合 減去
        assignment log 已有 ticket_id 集合」現場計算。assignment log
        本身已是唯一且權威的「哪些票已回填」依據，另存進度檔會產生
        第二份可能與 log 本身漂移的狀態（違反 quality-baseline 對狀態
        單一真相來源的要求），且中斷後重新掃描的成本遠低於既有規模，
        不需快取進度。

    單批失敗不影響已完成批次 —— 為何用逐筆 immediate-write 而非交易：
        `assign_batch()` 對批次中每筆呼叫 `append_assignment()`，每筆
        呼叫皆是獨立的 append-only 檔案寫入（開檔即寫即關閉，無暫存緩衝
        跨筆累積）。故某筆因驗證失敗（如空白 topic）而中止，不影響此前
        已成功寫入 log 的筆次——它們已是 log 檔案的既有內容，符合
        append-only 語意下「先前寫入不因後續失敗而回滾」的行為。

Public API:
    list_pending_ticket_ids() -> list[str]
        列出所有版本中 status=pending 的 ticket id（唯讀掃描，去重）。
    list_assignments() -> dict[str, str]
        讀取 assignment log，回傳 {ticket_id: topic}。
    list_unassigned_pending_tickets() -> list[str]
        acceptance 第 1 條：列出尚未歸屬主題的 pending 票。
    append_assignment(ticket_id: str, topic: str) -> bool
        單筆指派，寫入 assignment log 並同步註冊主題至中央主題清單。
    reassign_assignment(ticket_id: str, topic: str) -> bool
        顯式改派：對已有指派的 ticket_id 追加新指派（見
        `lib/topic_assignments.py` 模組 docstring）。
    assign_batch(assignments: dict[str, str], reassign: bool = False) -> dict[str, list[str]]
        acceptance 第 2、3 條：分批指派，單筆失敗不影響其餘筆次。
        `reassign=True` 時對整批已有指派的 ticket_id 追加新指派而非拒絕。
    register(subparsers) -> None
        CLI 入口註冊。

CLI 入口：
    本模組原無 `register()`，`track.py` 亦未 import，`ticket track --help`
    無任何回填相關命令，存量未歸屬 pending 票無觸發途徑（查證見本模組
    對應修復票的 Problem Analysis）。CLI 設計比照 `commands/track_topics.py`
    的 version-agnostic 註冊形式，新增兩個扁平命令（不用巢狀子動作，維持
    與 `topics`/`topic`、`batch-claim`/`batch-complete` 等既有命令的扁平
    命名慣例一致）：

    topic-backfill-list
        acceptance 第 2 條：列出尚未歸屬主題的 pending 票（純讀取）。
    topic-backfill-assign --file <path>
        acceptance 第 3 條：批次指派主題。映射載體選擇「檔案輸入」而非
        逐筆旗標或互動式輸入——現況存量規模達數百張，逐筆旗標
        （`--assign ID=TOPIC` 重複多次）在此規模下不可用；互動式輸入
        無法被腳本化重跑，不符合模組層「中斷後續作」的設計意圖。檔案
        格式選擇與 assignment log 本身相同的 tab 分隔格式
        （`ticket_id\\ttopic`，一行一筆），理由：格式讀者已熟悉（同一
        份 log 檔案本身即是此格式的範例），且省去額外解析器維護成本。

        指派不存在的主題名時的行為（修正後）：CLI 層預設拒絕中央清單
        未見的主題名，只印出既有主題名並提示改用 `--allow-new-topics`；
        該筆不寫入 assignment log、不觸發任何 `append_assignment` 呼叫，
        其餘已知主題名的筆次不受影響。行為對齊 `create.py` 的
        `topic_inference.validate_topic_selection`（`--topic` 白名單拒絕語意）。加上
        `--allow-new-topics` 旗標時，該次執行涵蓋的所有未知主題名皆
        透傳至 `assign_batch` -> `append_assignment` 自動註冊（旗標對
        整份輸入檔生效，非逐筆指定——回填為批次操作，逐筆旗標在數百筆
        規模下不可用；此顯式旗標本身即防呆點：使用者一次性確認「這批
        輸入檔內的新主題名皆為有意新增」，等同 `create.py`
        `--new-topic` 逐筆顯式旗標的批次形式）。

        原始設計（修正前）理由是「分批指派主題，中斷後續作行為與模組層
        一致」——模組層 `append_assignment` 本身即帶自動註冊語意，CLI 層
        故不新增白名單拒絕層。實測發現此設計在真實批次規模下會讓形近
        錯字直接污染 append-only 的中央清單且無法清除。兩者其實不衝突：
        本次修正的拒絕發生在呼叫 `assign_batch` 之前的 CLI 層前置過濾，
        未知主題名的筆次不進入 `assign_batch` -> `append_assignment`
        呼叫鏈；模組層 `append_assignment` 本身收到呼叫時仍是原封不動的
        自動註冊語意（見 `TestAppendAssignmentBasic`，本次修復未變動）。

        改派（修正錯誤指派）：加 `--reassign` 旗標時，輸入檔中已有指派
        的 ticket_id 改呼叫 `reassign_assignment`（對整份輸入檔生效，
        理由同 `--allow-new-topics`——批次規模下逐筆旗標不可用），追加
        一筆新指派而非被 `append_assignment` 拒絕。未指定 `--reassign`
        時行為不變（已有指派的 ticket_id 一律拒絕，防止批次回填誤
        覆蓋）。詳細設計理由（表示形式、歷史保留）見
        `lib/topic_assignments.py` 模組 docstring 與對應 Solution 記錄。
"""
from __future__ import annotations

# 防止直接執行此模組
if __name__ == "__main__":
    from ..lib.messages import print_not_executable_and_exit
    print_not_executable_and_exit()


import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List

from ticket_system.constants import STATUS_PENDING
from ticket_system.lib.paths import get_project_root
from ticket_system.lib.parser import parse_frontmatter

# assignment log 讀寫層已下沉至 lib/topic_assignments.py（create.py 亦需
# 寫入同一映射，commands/ 之間互相 import 違反既有分層）。此處 re-export
# 維持既有呼叫端與測試（tests/test_topic_backfill.py）的匯入路徑不變。
from ticket_system.lib.topic_assignments import (  # noqa: F401
    TOPIC_ASSIGNMENTS_RELATIVE_PATH,
    _assignments_path,
    append_assignment,
    list_assignment_history,
    list_assignments,
    reassign_assignment,
)


def _iter_ticket_files() -> List[Path]:
    """掃描所有版本目錄下的 ticket 檔案（唯讀，比照既有遷移命令的雙
    掃描策略：支援 flat 與三層版本目錄結構）。
    """
    work_logs_root = get_project_root() / "docs" / "work-logs"
    if not work_logs_root.exists():
        return []
    flat_dirs = list(work_logs_root.glob("v*/tickets"))
    hierarchical_dirs = list(work_logs_root.glob("v*/v*/v*/tickets"))
    files: List[Path] = []
    for tickets_dir in sorted(set(flat_dirs + hierarchical_dirs)):
        files.extend(sorted(tickets_dir.glob("*.md")))
    return files


def list_pending_ticket_ids() -> List[str]:
    """列出所有版本中 status=pending 的 ticket id（依掃描順序，去重）。

    純唯讀操作：僅呼叫 `parse_frontmatter` 解析既有內容，不寫入任何
    ticket 檔案。讀取或解析失敗的個別檔案記錄 stderr 後略過，不中斷
    整體掃描（observability-rules 規則 1：降級處理需可見）。
    """
    ids: List[str] = []
    seen: set = set()
    for ticket_file in _iter_ticket_files():
        try:
            content = ticket_file.read_text(encoding="utf-8")
        except OSError as exc:
            sys.stderr.write(
                f"[topic_backfill] 讀取 ticket 檔案失敗，略過: "
                f"{ticket_file} ({exc})\n"
            )
            continue

        try:
            frontmatter, _ = parse_frontmatter(content)
        except Exception as exc:  # noqa: BLE001 - 單檔 frontmatter 解析失敗僅略過該檔
            sys.stderr.write(
                f"[topic_backfill] 解析 frontmatter 失敗，略過: "
                f"{ticket_file} ({exc})\n"
            )
            continue

        if not frontmatter or frontmatter.get("status") != STATUS_PENDING:
            continue

        ticket_id = frontmatter.get("id")
        if not ticket_id or ticket_id in seen:
            continue
        seen.add(ticket_id)
        ids.append(ticket_id)
    return ids


def list_unassigned_pending_tickets() -> List[str]:
    """acceptance 第 1 條：列出尚未歸屬主題的 pending 票。

    續作起點由 assignment log 既有內容現場判定（不另存進度檔，理由見
    模組 docstring「續作起點」段）。
    """
    assigned = list_assignments()
    return [tid for tid in list_pending_ticket_ids() if tid not in assigned]


def assign_batch(
    assignments: Dict[str, str], reassign: bool = False
) -> Dict[str, List[str]]:
    """acceptance 第 2、3 條：分批指派主題。

    逐筆呼叫 `append_assignment`（`reassign=False`，預設）或
    `reassign_assignment`（`reassign=True`）；單筆因驗證錯誤失敗時記錄
    stderr 並略過，不影響其餘筆次的處理與此前筆次已寫入 log 的內容
    （原因見模組 docstring「單批失敗不影響已完成批次」段）。

    `reassign` 對整批輸入生效（非逐筆指定）——與 CLI 層
    `--allow-new-topics` 同一設計理由：批次操作在數百筆規模下，逐筆
    旗標不可用，此顯式旗標本身即是使用者一次性確認「這批輸入檔內的
    ticket_id 皆為有意改派」的防呆點（acceptance 第 2 條：改派須與一般
    指派用不同的顯式命令或旗標）。

    Args:
        assignments: {ticket_id: topic} 待指派映射。
        reassign: True 時對已有指派的 ticket_id 追加新指派（改派）；
            False（預設）時對已有指派的 ticket_id 拒絕寫入，行為與既有
            `append_assignment` 完全一致。

    Returns:
        {"succeeded": [...], "failed": [...]}：成功寫入與驗證失敗的
        ticket_id 列表（各自維持輸入的迭代順序）。
    """
    write_fn = reassign_assignment if reassign else append_assignment
    succeeded: List[str] = []
    failed: List[str] = []
    for ticket_id, topic in assignments.items():
        try:
            write_fn(ticket_id, topic)
            succeeded.append(ticket_id)
        except ValueError as exc:
            sys.stderr.write(
                f"[topic_backfill] 指派失敗，略過: {ticket_id} ({exc})\n"
            )
            failed.append(ticket_id)
    return {"succeeded": succeeded, "failed": failed}


# ---------------------------------------------------------------------------
# CLI 入口（version-agnostic，比照 track_topics.py 慣例）
# ---------------------------------------------------------------------------


def execute_topic_backfill_list(args: "argparse.Namespace") -> int:
    """執行 `ticket track topic-backfill-list`：列出尚未歸屬主題的 pending 票（純讀取）。"""
    fmt = getattr(args, "format", "table") or "table"
    unassigned = list_unassigned_pending_tickets()

    if fmt == "json":
        print(json.dumps(
            {"unassigned": unassigned, "count": len(unassigned)},
            ensure_ascii=False,
            indent=2,
        ))
        return 0

    if not unassigned:
        print("（無未歸屬主題的 pending 票）")
        return 0
    for ticket_id in unassigned:
        print(ticket_id)
    print(f"共 {len(unassigned)} 筆")
    return 0


def _parse_assignment_file(path: Path) -> Dict[str, str]:
    """解析批次指派輸入檔：tab 分隔 `ticket_id\\ttopic`，一行一筆（格式同
    assignment log 本身，設計理由見模組 docstring「CLI 入口」段）。

    格式錯誤行（缺 tab 分隔）記錄 stderr 後略過，不中斷整體解析
    （observability-rules 規則 1：降級處理需可見）。
    """
    assignments: Dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        # 先判斷空白/註解行（用 strip() 判斷即可，不影響有 tab 的資料行），
        # 但 tab 存在性檢查用原始 line（非 strip 後），避免 topic 為純空白
        # （如「ID\t   」）時被 line.strip() 誤剝掉 tab 而降級成格式錯誤行
        # ——那種情況應交給模組層 append_assignment 判定為驗證失敗，不是
        # 本函式的格式解析失敗。
        if not line.strip() or line.strip().startswith("#"):
            continue
        if "\t" not in line:
            sys.stderr.write(
                f"[topic_backfill] 略過格式錯誤行（缺 tab 分隔）: {line.strip()!r}\n"
            )
            continue
        ticket_id, topic = line.split("\t", 1)
        assignments[ticket_id.strip()] = topic.strip()
    return assignments


def _partition_known_unknown_topics(
    assignments: Dict[str, str],
) -> tuple:
    """依中央主題清單將 assignments 拆為「已知主題」與「未知主題」兩組。

    比對採正規化比對（與 create.py `topic_inference.validate_topic_selection` 一致），
    避免大小寫/空白差異造成誤判為未知。

    Returns:
        (known, unknown) tuple：兩者皆為 {ticket_id: topic} dict，鍵集合
        互斥且聯集等於輸入 assignments，各自維持輸入的迭代順序。
    """
    from ticket_system.lib.topic_registry import list_topics, normalize_topic_name

    existing_keys = {normalize_topic_name(t) for t in list_topics()}
    known: Dict[str, str] = {}
    unknown: Dict[str, str] = {}
    for ticket_id, topic in assignments.items():
        if normalize_topic_name(topic) in existing_keys:
            known[ticket_id] = topic
        else:
            unknown[ticket_id] = topic
    return known, unknown


def execute_topic_backfill_assign(args: "argparse.Namespace") -> int:
    """執行 `ticket track topic-backfill-assign --file <path>`：批次指派主題。

    預設拒絕中央清單未見的主題名（防呆對齊 create.py `--topic` 白名單
    拒絕語意，理由見模組 docstring「CLI 入口」段「指派不存在的主題名時的
    行為」）：未知主題名的筆次不寫入、不觸發 `append_assignment`，僅印出
    既有主題名供對照；加 `--allow-new-topics` 時對整份輸入檔透傳給
    `assign_batch` 自動註冊，行為與模組層 `assign_batch` 完全一致。已知
    主題名的筆次不受同批未知主題名筆次影響；單筆驗證失敗（如空白 topic）
    同樣不影響其餘筆次與此前已成功寫入的筆次。
    """
    input_path = Path(args.file)
    if not input_path.exists():
        print(f"[Error] 輸入檔不存在: {input_path}")
        return 1

    assignments = _parse_assignment_file(input_path)
    if not assignments:
        print("（輸入檔無有效指派筆次）")
        return 0

    allow_new_topics = bool(getattr(args, "allow_new_topics", False))
    rejected_unknown: List[str] = []

    if not allow_new_topics:
        from ticket_system.lib.topic_registry import list_topics

        known, unknown = _partition_known_unknown_topics(assignments)
        if unknown:
            existing = list_topics()
            hint = (
                ("既有主題：" + "、".join(existing))
                if existing
                else "目前尚無任何既有主題"
            )
            print("[Error] 以下筆次的主題名不存在於中央清單，已拒絕（不自動註冊）：")
            for ticket_id, topic in unknown.items():
                print(f"  - {ticket_id}: {topic!r}")
            print(f"{hint}。如需新增這些主題，請加上 --allow-new-topics 重新執行本次輸入檔")
            rejected_unknown = list(unknown.keys())
        assignments = known

    if not assignments:
        print(
            f"成功: 0 筆，失敗: 0 筆" + (
                f"，拒絕未知主題: {len(rejected_unknown)} 筆" if rejected_unknown else ""
            )
        )
        return 1 if rejected_unknown else 0

    reassign = bool(getattr(args, "reassign", False))
    result = assign_batch(assignments, reassign=reassign)
    summary = f"成功: {len(result['succeeded'])} 筆，失敗: {len(result['failed'])} 筆"
    if rejected_unknown:
        summary += f"，拒絕未知主題: {len(rejected_unknown)} 筆"
    print(summary)
    if result["failed"]:
        print(f"失敗筆次: {', '.join(result['failed'])}")
    if rejected_unknown:
        print(f"拒絕筆次（未知主題）: {', '.join(rejected_unknown)}")
    if result["failed"] or rejected_unknown:
        return 1
    return 0


def register(subparsers: "argparse._SubParsersAction") -> None:
    """註冊 `topic-backfill-list` 與 `topic-backfill-assign` 兩個 version-agnostic
    子命令 parser（dispatch 由 `track.py` 的
    `_create_version_agnostic_handlers()` dict 統一處理，命名慣例與命令形式
    選擇理由見模組 docstring「CLI 入口」段）。
    """
    p_list = subparsers.add_parser(
        "topic-backfill-list",
        help="列出尚未歸屬主題的 pending 票（純讀取）",
    )
    p_list.add_argument(
        "--format",
        choices=["table", "json"],
        default="table",
        help="輸出格式（預設 table）",
    )

    p_assign = subparsers.add_parser(
        "topic-backfill-assign",
        help="批次指派主題（輸入檔格式：tab 分隔 ticket_id<TAB>topic，一行一筆）",
    )
    p_assign.add_argument(
        "--file",
        required=True,
        help="批次指派輸入檔路徑",
    )
    p_assign.add_argument(
        "--allow-new-topics",
        dest="allow_new_topics",
        action="store_true",
        help=(
            "允許輸入檔含未見於中央清單的主題名並自動新增（預設拒絕"
            "未知主題名並列出既有主題名，行為對齊 create --new-topic）"
        ),
    )
    p_assign.add_argument(
        "--reassign",
        dest="reassign",
        action="store_true",
        help=(
            "改派模式：對輸入檔中已有指派的 ticket_id 追加新指派（取代"
            "既有主題），而非預設的拒絕重複指派行為。與一般指派用不同"
            "顯式旗標區分，避免批次誤覆蓋既有指派"
        ),
    )
