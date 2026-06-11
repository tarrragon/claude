"""
Ticket 建構模組

從 create.py 提取的 Ticket 建構相關函式，提供公開 API 供 create 和 generate 命令重用。
提取函式：
  - format_ticket_id(): 格式化根任務 ID
  - format_child_ticket_id(): 格式化子任務 ID
  - get_next_seq(): 取得下一個根任務序號
  - get_next_child_seq(): 取得下一個子任務序號
  - create_ticket_frontmatter(): 建立 Ticket frontmatter
  - create_ticket_body(): 建立 Ticket body
  - update_parent_children(): 更新父 Ticket 的 children
  - update_source_spawned_tickets(): 更新 source Ticket 的 spawned_tickets（PC-073）

使用 TypedDict 減少函式參數數量，提高程式碼可讀性。
"""

import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, TypedDict

from ticket_system.lib.constants import STATUS_PENDING, DEFAULT_UNDEFINED_VALUE
from ticket_system.lib.paths import GIT_TOPLEVEL_TIMEOUT, get_project_root
from ticket_system.lib.ticket_loader import (
    get_tickets_dir,
    save_ticket,
    load_ticket,
    get_ticket_path,
)
from ticket_system.lib.ticket_validator import extract_version_from_ticket_id
from ticket_system.lib.file_lock import file_lock

# git ls-tree 候選 ref，依序嘗試（PM 決策 2026-05-22：main → master）
_MAIN_REF_CANDIDATES: Tuple[str, ...] = ("main", "master")


def list_ticket_files_from_main(
    version: str, ref_candidates: Tuple[str, ...] = _MAIN_REF_CANDIDATES
) -> Optional[List[str]]:
    """列舉 git ref（預設 main，失敗試 master）上指定版本 tickets 目錄的檔案。

    B3 方案（0.19.0-W1-037）核心輔助函式：補足 worktree 從 stale base 分叉時
    本地工作樹掃描不到 main 上已存在 ticket 的缺口。回傳 main ref 上的 ticket
    檔路徑清單，供 get_next_seq / _scan_child_files_max_seq 與本地 glob 取聯集。

    Args:
        version: 版本號（如 "0.19.0"，可帶或不帶 v 前綴）。
        ref_candidates: 依序嘗試的 git ref 名稱；任一成功即回傳。

    Returns:
        成功：main ref 上 tickets 目錄的檔案路徑清單（相對 repo root 的路徑字串）。
        失敗（非 git 環境、main/master 皆不存在、git 不存在、ls-tree 逾時）：None。
        失敗時 caller 應 fallback 為純本地掃描（聯集設計確保不比現況差）。
    """
    project_root = get_project_root()
    tickets_dir = get_tickets_dir(version)
    try:
        rel_tickets_dir = tickets_dir.relative_to(project_root)
    except ValueError:
        # tickets_dir 不在 project_root 之下（測試以外少見）；無法構造 ls-tree pathspec
        return None

    for ref in ref_candidates:
        try:
            result = subprocess.run(
                [
                    "git",
                    "ls-tree",
                    "-r",
                    "--name-only",
                    ref,
                    "--",
                    str(rel_tickets_dir),
                ],
                cwd=str(project_root),
                capture_output=True,
                text=True,
                timeout=GIT_TOPLEVEL_TIMEOUT,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
            # git 不存在或逾時：記錄後 fallback 純本地掃描（規則 4：異常可觀測）
            sys.stderr.write(
                f"[WARNING] list_ticket_files_from_main: git ls-tree {ref} "
                f"失敗（{type(exc).__name__}），fallback 純本地掃描\n"
            )
            return None
        if result.returncode == 0:
            return [
                line.strip()
                for line in result.stdout.splitlines()
                if line.strip()
            ]
        # returncode != 0：該 ref 不存在，續試下一候選

    # 所有候選 ref 皆無法解析（非 git 環境或無 main/master）→ fallback 純本地
    return None


# 預設驗收條件（依 Ticket 類型）
# 注意：所有條件都應包含量化佔位符或可客觀驗證的標準，禁止使用模糊詞
DEFAULT_ACCEPTANCE_CRITERIA = {
    "IMP": [
        "指定功能（{feature_name}）實作符合設計規格",
        "相關測試 100% 通過（flutter test / uv run pytest）",
        "dart analyze / ruff check 0 issues"
    ],
    "TST": [
        "設計 N 個測試案例，覆蓋正常/邊界/異常路徑",
        "所有測試案例執行通過（通過率 100%）",
        "測試覆蓋率達 {coverage_target}%（由 SA 或代理人指定）"
    ],
    "ADJ": [
        "調整內容（{adjustment_target}）符合規格",
        "相關測試通過（通過率 100%）",
        "lint 檢查 0 critical issues"
    ],
    "RES": [
        "研究報告已撰寫（含背景、方法、發現、結論 4 部分）",
        "結論明確且可行（避免「可能」「似乎」等模糊詞）",
        "至少提出 N 個可行的改善建議"
    ],
    "ANA": [
        "分析報告已撰寫（含問題敘述、根因分析、改善方案 3 部分）",
        "根因已通過 5W1H 或因果鏈分析確認",
        "改善方案至少包含症狀修復和根因防護兩個方向",
        "[ ] 分析結論已建立修復 Ticket（症狀修復），Ticket ID 已記錄在 spawned_tickets",
        "[ ] 根因已建立防護 Ticket（機制防護），Ticket ID 已記錄在 spawned_tickets",
        "[ ] 若無後續 Ticket 需建立，需說明理由"
    ],
    "INV": [
        "調查報告已撰寫（含調查範圍、發現、驗證過程 3 部分）",
        "事實已通過實驗/測試/文件驗證確認（不依賴推測）",
        "後續行動已定義：建立 {N} 個相關 Ticket，IDs 已記錄"
    ],
    "DOC": [
        "文件內容完整：包含標題、背景、正文、結論、附錄等 {N} 部分",
        "格式符合規範：遵守 CLAUDE.md 的文件格式規則",
        "內容無遺漏：所有預期的小節都已填寫（無 TODO 或空白區段）"
    ],
    # 問題 5 修正：移除未在 TICKET_TYPES 中註冊的類型
    # SEC、PERF、INFRA 類型未在 constants.py 的 TICKET_TYPES 中定義
    # 若需支援這些類型，請先在 TICKET_TYPES 中註冊
}


class TicketConfig(TypedDict, total=False):
    """Ticket 建立配置。

    使用 TypedDict 減少函式參數數量，提高程式碼可讀性。
    total=False 表示所有欄位都是可選的。
    """

    # 基本資訊（6 個欄位）
    ticket_id: str              # Ticket ID（如 0.31.0-W5-001）
    version: str                # 版本號（如 0.31.0）
    wave: int                   # Wave 編號（如 5）
    title: str                  # 標題（「動詞 + 目標」格式）
    ticket_type: str            # 類型（IMP/TST/ADJ/RES/ANA/INV/DOC）
    priority: str               # 優先級（P0/P1/P2/P3）

    # 5W1H 資訊（7 個欄位）
    who: str                    # 執行代理人（如 parsley-flutter-developer）
    what: str                   # 任務描述
    when: str                   # 觸發時機
    where_layer: str            # 架構層級（Domain/Application/Infrastructure/Presentation）
    where_files: List[str]      # 影響檔案清單
    why: str                    # 需求依據
    how_task_type: str          # Task Type（Implementation/Analysis/etc.）
    how_strategy: str           # 實作策略

    # 關係資訊（4 個欄位）
    parent_id: Optional[str]    # 父 Ticket ID（子任務才有）
    blocked_by: Optional[List[str]]  # 依賴的 Ticket IDs
    related_to: Optional[List[str]]  # 相關的 Ticket IDs（多對多關聯）
    source_ticket: Optional[str]  # 衍生來源 Ticket ID（spawned 關係，與 parent_id 互斥）

    # TDD 資訊（2 個欄位）
    tdd_phase: Optional[str]    # 當前 TDD 階段（phase1/phase2/phase3a/phase3b/phase4）
    tdd_stage: Optional[List[str]]  # TDD 階段清單

    # 驗收條件（1 個欄位）
    acceptance: Optional[List[str]]  # 驗收條件清單

    # 決策樹路徑（1 個欄位）
    decision_tree_path: Optional[Dict[str, str]]  # {"entry_point": ..., "final_decision": ..., "rationale": ...}


def get_default_acceptance_criteria(ticket_type: str) -> List[str]:
    """取得預設驗收條件（依 Ticket 類型）。

    Args:
        ticket_type: Ticket 類型（IMP, TST, ADJ, RES, ANA, INV, DOC）

    Returns:
        預設驗收條件清單

    Examples:
        >>> get_default_acceptance_criteria("IMP")
        ["任務實作完成", "相關測試通過", "無程式碼品質警告"]

        >>> get_default_acceptance_criteria("ANA")
        ["分析報告完成", "根因已識別", "改善方案已提出",
         "[ ] 分析結論已建立修復 Ticket（症狀修復）",
         "[ ] 根因已建立防護 Ticket（機制防護）",
         "[ ] 後續 Ticket 已記錄在 children 或 spawned_tickets"]

        >>> get_default_acceptance_criteria("UNKNOWN")
        ["任務實作完成", "相關測試通過", "無程式碼品質警告"]
    """
    return DEFAULT_ACCEPTANCE_CRITERIA.get(
        ticket_type,
        DEFAULT_ACCEPTANCE_CRITERIA["IMP"]  # 預設為 IMP 類型
    )


def validate_create_checklist(
    config: TicketConfig,
    ticket_type: str,
) -> List[str]:
    """PROP-009 清單式欄位驗證（三建票路徑共用）。

    建立前檢查必填欄位，回傳缺失欄位名稱清單。本函式為純驗證，
    不阻擋、不 print；由呼叫端決定 warning 或阻擋行為：
    - create 命令層：缺失 + 未 --force 時阻擋（W11-003.5）
    - batch-create / generate 路徑：warning 級不阻擋（1.0.0-W1-027）

    讀取的是 flat config key（who/why/where_files 等），非經
    create_ticket_frontmatter 轉換後的巢狀 frontmatter。呼叫端
    必須在 flat config 階段呼叫，否則 key 不符會全部誤判。

    Args:
        config: Ticket 配置（flat key 形態）
        ticket_type: Ticket 類型（IMP, ANA, DOC 等）

    Returns:
        缺失欄位名稱的清單，空清單表示全部通過
    """
    missing: List[str] = []

    # where.files 至少 1 個
    if not config.get("where_files"):
        missing.append("where.files")

    # acceptance 至少 1 項
    if not config.get("acceptance"):
        missing.append("acceptance")

    # decision_tree_path 三個子欄位都非空（DOC 類型和子任務豁免）
    is_exempt_from_decision_tree = (
        ticket_type == "DOC" or config.get("parent_id")
    )
    if not is_exempt_from_decision_tree:
        dt = config.get("decision_tree_path") or {}
        has_complete_path = (
            dt.get("entry_point")
            and dt.get("final_decision")
            and dt.get("rationale")
        )
        if not has_complete_path:
            missing.append("decision_tree_path")

    # when 非「待定義」
    if config.get("when") == DEFAULT_UNDEFINED_VALUE:
        missing.append("when")

    # W11-003.5: 5W1H 全欄位必填擴充
    # who 不可為空、"pending" 或「待定義」
    who_value = config.get("who")
    if not who_value or who_value in ("pending", DEFAULT_UNDEFINED_VALUE):
        missing.append("who")

    # what 不可為空（CLI argparse 已強制 --action/--target，此處為防禦性檢查）
    if not config.get("what"):
        missing.append("what")

    # why 非空且非「待定義」（DOC 類型豁免；1.0.0-W1-043 補空字串漏判）
    if ticket_type != "DOC":
        why_value = config.get("why")
        if not why_value or why_value == DEFAULT_UNDEFINED_VALUE:
            missing.append("why")

    # how_strategy 非空且非「待定義」（1.0.0-W1-043 補空字串漏判）
    how_strategy_value = config.get("how_strategy")
    if not how_strategy_value or how_strategy_value == DEFAULT_UNDEFINED_VALUE:
        missing.append("how_strategy")

    return missing


def format_ticket_id(version: str, wave: int, seq: int) -> str:
    """格式化根任務 Ticket ID。

    Args:
        version: 版本號（如 "v0.31.0" 或 "0.31.0"）
        wave: Wave 編號（正整數）
        seq: 序號（正整數）

    Returns:
        格式化的 Ticket ID（如 "0.31.0-W5-001"）

    Examples:
        >>> format_ticket_id("v0.31.0", 5, 1)
        '0.31.0-W5-001'
        >>> format_ticket_id("0.31.0", 5, 1)
        '0.31.0-W5-001'
        >>> format_ticket_id("0.32.0", 10, 999)
        '0.32.0-W10-999'

    Implementation:
        - 移除 version 的 "v" 前綴（若有）
        - 格式：{version}-W{wave}-{seq:03d}
        - seq 使用 3 位數補零（如 001, 015, 123）
    """
    # 移除 v 前綴
    v: str = version[1:] if version.startswith("v") else version
    return f"{v}-W{wave}-{seq:03d}"


def format_child_ticket_id(parent_id: str, child_seq: int) -> str:
    """格式化子任務 Ticket ID。

    Args:
        parent_id: 父 Ticket ID（如 "0.31.0-W5-001"）
        child_seq: 子任務序號（正整數）

    Returns:
        子任務 ID（如 "0.31.0-W5-001.1"）

    Examples:
        >>> format_child_ticket_id("0.31.0-W5-001", 1)
        '0.31.0-W5-001.1'
        >>> format_child_ticket_id("0.31.0-W5-001.1", 2)
        '0.31.0-W5-001.1.2'
        >>> format_child_ticket_id("0.31.0-W5-001.1.1.1", 1)
        '0.31.0-W5-001.1.1.1.1'

    Implementation:
        - 格式：{parent_id}.{child_seq}
        - 支援無限深度的子任務（如 001.1.1.1）
    """
    return f"{parent_id}.{child_seq}"


def get_next_seq(version: str, wave: int) -> int:
    """取得下一個根任務序號。

    Args:
        version: 版本號（如 "0.31.0"）
        wave: Wave 編號

    Returns:
        下一個序號（正整數，從 1 開始）

    Examples:
        若 0.31.0-W5-001.md 和 0.31.0-W5-002.md 已存在：
        >>> get_next_seq("0.31.0", 5)
        3

        若該 Wave 無任何 Ticket：
        >>> get_next_seq("0.31.0", 5)
        1

    Implementation:
        1. 取得 tickets_dir（透過 get_tickets_dir(version)）
        2. glob 本地工作樹的 *-W{wave}-*.md 檔案
        3. list_ticket_files_from_main 取得 main ref 上的 ticket 檔（B3 方案）
        4. 兩來源取聯集後解析所有檔名，取得最大序號
        5. 返回 max_seq + 1（無任何來源檔案時返回 1）

    注意:
        - 只計算根任務序號（不包含子任務的點號部分）
        - 如 0.31.0-W5-001.1.md 只取 001
        - main ref 掃描失敗（非 git / 無 main / 逾時）時降級為純本地掃描
    """
    tickets_dir = get_tickets_dir(version)

    # 掃描邊界（W1-052）：正常路徑的「max+1 天然不撞」論證只認 .md ——
    # local glob 限 `*-W{wave}-*.md`，main ref 也只收 endswith(".md") 的 stem。
    # .yaml-only ticket（無對應 .md）不在此掃描集合，理論上是「max+1 不撞」的洞。
    # 現實風險 ~0（系統只產 .md、repo 現存 0 個 .yaml ticket），故不為此修碼；
    # 降級分支的 resolve_available_seq 經 get_ticket_path 探測會同時覆蓋 .md/.yaml，
    # 是 .yaml 撞號的實際防線。此處僅顯性標註正常路徑的邊界。
    # 來源 1：本地工作樹 glob
    local_stems: List[str] = []
    if tickets_dir.exists():
        local_stems = [f.stem for f in tickets_dir.glob(f"*-W{wave}-*.md")]

    # 來源 2：main ref（B3 方案，補足 stale base worktree 掃不到的 ticket）
    main_stems: List[str] = []
    main_files = list_ticket_files_from_main(version)
    if main_files is not None:
        main_stems = [
            Path(p).stem for p in main_files if Path(p).name.endswith(".md")
        ]

    # 聯集解析最大根任務序號
    max_seq = 0
    for stem in set(local_stems) | set(main_stems):
        seq = _parse_root_seq(stem, wave)
        if seq is not None:
            max_seq = max(max_seq, seq)

    candidate = max_seq + 1

    # 降級可觀測 + 內聚 collision guard（W1-042 / W1-051 / quality-baseline 規則 4）：
    # 本地 glob 為空且 main ref 掃描降級（回 None，非有效空清單）時，
    # 兩來源同時掃空會回傳 candidate=1，可能誤配已存在 ID（W1-039 撞號事件）。
    #
    # linux caveat（W1-051）：正常路徑（任一來源有效）的 candidate = max+1 對
    # 已掃描集合天然不撞，故不在正常路徑做逐一 .exists() 探測；guard 緊貼降級
    # 分支——僅當降級偵測成立時，才以檔案系統探測推進至真正可用 seq，使
    # get_next_seq 回傳值內部保證可用（消除 create.py caller 層 while-loop 外洩）。
    if not local_stems and main_files is None:
        resolved = resolve_available_seq(version, wave, candidate)
        # W1-052 措辭收斂：FS 探測看不到 main-only 檔（main ref 已降級），故
        # collision guard 僅保證「本地檔案系統可用」，對 main-only 撞號無保證；
        # 不過度承諾「已推進至可用序號」。
        sys.stderr.write(
            f"[WARNING] get_next_seq: 本地工作樹與 main ref 同時掃描不到 "
            f"{version} W{wave} 的 ticket（main ref 降級），初始配號回退為 "
            f"{candidate}；collision guard 已推進至本地檔案系統可用序號 {resolved}"
            f"（僅保證本地 FS 可用，無法保證 main-only 票不撞）\n"
        )
        return resolved

    return candidate


def resolve_available_seq(version: str, wave: int, start_seq: int) -> int:
    """從 start_seq 起遞增，回傳第一個檔案系統上不存在的根任務序號。

    W1-051 內聚 collision guard 的共用 helper：把「可用性保證」收斂到單一
    權威點，供 get_next_seq 降級分支與 bulk_create 批次配號共享，消除 caller
    層各自實作 while-loop 的特例外洩（L1）與 bulk 無 guard 的連鎖覆寫風險（R1）。

    可用性判定用 get_ticket_path(...).exists()——該函式對 .md 與 .yaml 皆探測
    （優先回存在者），故同時覆蓋 .md / .yaml 兩種落盤格式的撞號（W1-051 .yaml 缺口）。

    Args:
        version: 版本號（如 "1.0.0"）。
        wave: Wave 編號。
        start_seq: 起始候選序號（呼叫端通常傳 max_seq + 1 或批次當前 seq）。

    Returns:
        第一個 get_ticket_path 探測不存在的序號（>= start_seq）。

    Examples:
        若 1.0.0-W1-001.md 存在、W1-002 不存在：
        >>> resolve_available_seq("1.0.0", 1, 1)
        2
    """
    seq = start_seq
    while get_ticket_path(version, format_ticket_id(version, wave, seq)).exists():
        seq += 1
    return seq


def _parse_root_seq(stem: str, wave: int) -> Optional[int]:
    """從 ticket 檔名 stem 解析指定 wave 的根任務序號。

    Args:
        stem: ticket 檔名（不含副檔名），如 "0.31.0-W5-001" 或 "0.31.0-W5-001.1"。
        wave: 目標 Wave 編號；stem 的 wave 不符時回傳 None。

    Returns:
        根任務序號（忽略子任務點號部分），無法解析或 wave 不符時回傳 None。
    """
    try:
        # 格式：{version}-W{wave}-{seq}.md 或 {version}-W{wave}-{seq}.{child}.md
        parts = stem.split("-W")
        if len(parts) != 2:
            return None
        wave_seq = parts[1].split("-", 1)
        if len(wave_seq) != 2:
            return None
        if int(wave_seq[0]) != wave:
            return None
        # 只取根任務的序號（不含子任務部分）
        return int(wave_seq[1].split(".")[0])
    except (ValueError, IndexError):
        return None


def _extract_direct_child_seq(child_id: str, parent_id: str) -> Optional[int]:
    """從子任務 ID 中提取直接子任務序號。

    只提取直接子任務（深度 = parent_depth + 1），
    忽略更深層的子任務（如 001.1.1）。

    Args:
        child_id: 子任務 ID（如 "0.31.0-W5-001.2"）
        parent_id: 父任務 ID（如 "0.31.0-W5-001"）

    Returns:
        直接子任務序號，若非直接子任務則返回 None
    """
    prefix = parent_id + "."
    if not child_id.startswith(prefix):
        return None
    remainder = child_id[len(prefix):]
    # 直接子任務的 remainder 不含點號
    if "." in remainder:
        return None
    try:
        return int(remainder)
    except ValueError:
        return None


def _scan_child_files_max_seq(tickets_dir: Path, parent_id: str) -> int:
    """掃描子 Ticket 檔案找出最大直接子任務序號（本地工作樹 ∪ main ref）。

    這是防止父 Ticket 的 children 欄位未同步時的安全機制，
    確保不會覆蓋已存在的子 Ticket 檔案。B3 方案（0.19.0-W1-037）擴增資料來源：
    除本地工作樹 glob 外，併入 main ref 上的子 ticket 檔，避免 stale base
    worktree 掃不到 main 已建立的子 ticket 而分配碰撞序號。

    Args:
        tickets_dir: Ticket 檔案目錄
        parent_id: 父任務 ID

    Returns:
        最大直接子任務序號，無子 Ticket 檔案時返回 0
    """
    # 掃描邊界（W1-052 對齊 root 路徑標註）：glob 限 `{parent_id}.*.md`，
    # .yaml-only 子票不在掃描集合——與 get_next_seq 正常路徑的 .md-only 邊界
    # 同構。現實風險 ~0（系統只產 .md），children 欄位為另一獨立來源可兜底，
    # 故不為此修碼，僅顯性標註。
    # 來源 1：本地工作樹 glob
    local_stems: List[str] = []
    if tickets_dir.exists():
        local_stems = [f.stem for f in tickets_dir.glob(f"{parent_id}.*.md")]

    # 來源 2：main ref（B3 方案）；version 由 parent_id 解析
    main_stems: List[str] = []
    version = extract_version_from_ticket_id(parent_id)
    if version is not None:
        main_files = list_ticket_files_from_main(version)
        if main_files is not None:
            child_prefix = f"{parent_id}."
            main_stems = [
                Path(p).stem
                for p in main_files
                if Path(p).name.endswith(".md")
                and Path(p).stem.startswith(child_prefix)
            ]

    # 聯集解析最大直接子任務序號
    max_seq = 0
    for stem in set(local_stems) | set(main_stems):
        seq = _extract_direct_child_seq(stem, parent_id)
        if seq is not None:
            max_seq = max(max_seq, seq)
    return max_seq


def _normalize_children(raw: Any) -> List[str]:
    """將 children 欄位正規化為字串清單。

    防禦性型別處理：children 可能因手動編輯變成字串（換行分隔），
    或因序列化問題變成非預期型別。

    Args:
        raw: children 欄位的原始值（list、str 或其他型別）

    Returns:
        正規化後的子任務 ID 清單
    """
    if isinstance(raw, list):
        return raw
    if isinstance(raw, str):
        return [c.strip() for c in raw.split("\n") if c.strip()]
    return []


def get_next_child_seq(parent_id: str) -> int:
    """取得下一個子任務序號。

    同時檢查父 Ticket 的 children 欄位和檔案系統中的子 Ticket 檔案，
    取兩者的最大序號 + 1，確保不會覆蓋已存在的子 Ticket。

    Args:
        parent_id: 父 Ticket ID（如 "0.31.0-W5-001"）

    Returns:
        下一個子任務序號（正整數，從 1 開始）

    Examples:
        若父 Ticket 有 children: ["0.31.0-W5-001.1", "0.31.0-W5-001.2"]：
        >>> get_next_child_seq("0.31.0-W5-001")
        3

        若父 Ticket 無 children 但檔案系統有 0.31.0-W5-001.1.md：
        >>> get_next_child_seq("0.31.0-W5-001")
        2

        若父 Ticket 無 children 且無檔案：
        >>> get_next_child_seq("0.31.0-W5-001")
        1
    """
    version = extract_version_from_ticket_id(parent_id)
    if version is None:
        return 1

    # 來源 1：父 Ticket 的 children 欄位（single source of truth）
    max_seq_from_children = 0
    parent = load_ticket(version, parent_id)
    if parent:
        children_list = _normalize_children(parent.get("children", []))
        for child_id in children_list:
            seq = _extract_direct_child_seq(child_id, parent_id)
            if seq is not None:
                max_seq_from_children = max(max_seq_from_children, seq)

    # 來源 2：檔案系統掃描（fallback 安全機制，防止覆蓋已存在的子 Ticket）
    tickets_dir = get_tickets_dir(version)
    max_seq_from_files = _scan_child_files_max_seq(tickets_dir, parent_id)

    # 不一致時輸出 warning，便於追蹤 update_parent_children 失敗
    if max_seq_from_children != max_seq_from_files and max_seq_from_children > 0 and max_seq_from_files > 0:
        print(
            f"[WARNING] 父 Ticket {parent_id} 的 children 欄位（max_seq={max_seq_from_children}）"
            f"與檔案系統（max_seq={max_seq_from_files}）不一致",
            file=sys.stderr,
        )

    # 取兩者最大值，確保不覆蓋
    max_seq = max(max_seq_from_children, max_seq_from_files)
    return max_seq + 1


def create_ticket_frontmatter(config: TicketConfig) -> Dict[str, Any]:
    """建立 Ticket frontmatter。

    使用 TypedDict 配置參數簡化函式簽名，從 15 個參數減至 1 個。

    Args:
        config: 包含所有 Ticket 配置資訊的 TicketConfig 字典

    Returns:
        包含 frontmatter 資訊的字典

    Frontmatter 欄位清單（28 個欄位）:
        - id: config["ticket_id"]
        - title: config["title"]
        - type: config["ticket_type"]
        - status: "pending"（固定值，來自 STATUS_PENDING 常數）
        - version: config["version"]
        - wave: config["wave"]
        - priority: config["priority"]
        - parent_id: config.get("parent_id")（可選）
        - children: []（空清單，建立時無子任務）
        - blockedBy: config.get("blocked_by") or []
        - relatedTo: config.get("related_to") or []（多對多關聯）
        - spawned_tickets: []（空清單）
        - source_ticket: config.get("source_ticket")（可選；衍生關係）
        - dispatch_reason: ""（空字串）
        - decision_tree_path: config.get("decision_tree_path")（決策樹路徑，可選）
        - who: {"current": config["who"], "history": {}}
        - what: config["what"]
        - when: config["when"]
        - where: {"layer": config["where_layer"], "files": config.get("where_files", [])}
        - why: config["why"]
        - how: {"task_type": config["how_task_type"], "strategy": config["how_strategy"]}
        - acceptance: config.get("acceptance") or 預設驗收條件
        - tdd_phase: config.get("tdd_phase")
        - tdd_stage: config.get("tdd_stage") or []
        - assigned: False（固定值）
        - creation_accepted: False（固定值，建立後品質驗收狀態）
        - started_at: None
        - completed_at: None
        - created: 當前日期（YYYY-MM-DD）
        - updated: 當前日期（YYYY-MM-DD）

    預設驗收條件（依 Ticket 類型）:
        - IMP: ["任務實作完成", "相關測試通過", "無程式碼品質警告"]
        - ANA: ["分析報告完成", "根因已識別", "改善方案已提出",
                "[ ] 分析結論已建立修復 Ticket（症狀修復）",
                "[ ] 根因已建立防護 Ticket（機制防護）",
                "[ ] 後續 Ticket 已記錄在 children 或 spawned_tickets"]
        - 其他類型: 參考 DEFAULT_ACCEPTANCE_CRITERIA

    Examples:
        >>> config = TicketConfig(
        ...     ticket_id="0.31.0-W5-001",
        ...     version="0.31.0",
        ...     wave=5,
        ...     title="實作功能 X",
        ...     ticket_type="IMP",
        ...     priority="P1",
        ...     who="parsley-flutter-developer",
        ...     what="實作功能 X",
        ...     when="Phase 3b",
        ...     where_layer="Application",
        ...     where_files=["lib/application/use_case.dart"],
        ...     why="需求規格要求",
        ...     how_task_type="Implementation",
        ...     how_strategy="TDD Phase 3b"
        ... )
        >>> frontmatter = create_ticket_frontmatter(config)
        >>> frontmatter["id"]
        '0.31.0-W5-001'
        >>> frontmatter["status"]
        'pending'
    """
    return {
        "id": config["ticket_id"],
        "title": config["title"],
        "type": config["ticket_type"],
        "status": STATUS_PENDING,
        "version": config["version"],
        "wave": config["wave"],
        "priority": config["priority"],
        "parent_id": config.get("parent_id"),
        "children": [],
        "blockedBy": config.get("blocked_by") or [],
        "relatedTo": config.get("related_to") or [],
        "spawned_tickets": [],
        "source_ticket": config.get("source_ticket"),
        "dispatch_reason": "",
        "decision_tree_path": config.get("decision_tree_path"),
        "who": {"current": config["who"], "history": {}},
        "what": config["what"],
        "when": config["when"],
        "where": {"layer": config["where_layer"], "files": config.get("where_files", [])},
        "why": config["why"],
        "how": {"task_type": config["how_task_type"], "strategy": config["how_strategy"]},
        "acceptance": [
            f"[ ] {item}" if not (item.startswith("[") and "]" in item) else item
            for item in (config.get("acceptance") or get_default_acceptance_criteria(config["ticket_type"]))
        ],
        "tdd_phase": config.get("tdd_phase"),
        "tdd_stage": config.get("tdd_stage") or [],
        "assigned": False,
        "creation_accepted": False,
        "started_at": None,
        "completed_at": None,
        "created": datetime.now().strftime("%Y-%m-%d"),
        "updated": datetime.now().strftime("%Y-%m-%d"),
    }


def _ana_reproduction_section(ticket_type: str) -> str:
    """產生 ANA Ticket 專屬的「重現實驗結果」章節。

    當 ticket_type == 'ANA' 時回傳完整章節（前後含空行），否則回傳空字串。
    此章節為 PC-063 防護措施 1：強制 ANA Ticket 完成 Reality Test 才允許列方案，
    防止基於未驗證假設過早收斂方案。
    """
    if ticket_type != "ANA":
        return ""
    return """
## 重現實驗結果

### 實驗方法

（必填：如何重現問題？用什麼指令/測試？本章節為 ANA Ticket 強制章節——PC-063 防護措施）

### 實驗執行

（必填：實驗執行過程記錄，包含輸入、步驟、觀察到的實際行為）

### 實驗發現

（必填：實驗結論——已驗證的事實 vs 仍未驗證的假設。僅在完成實驗後才允許列候選方案。）

---
"""


def _schema_marker(ticket_type: str, section: str) -> str:
    """回傳 Schema 標註註解（type-aware body schema）。

    依 .claude/pm-rules/ticket-body-schema.md 映射章節填寫要求。未知 type 或
    未定義章節回傳空字串（向後相容）。

    Args:
        ticket_type: Ticket 類型（ANA/IMP/DOC 等）
        section: 章節名稱（Problem Analysis/Solution/Test Results/Completion Info）

    Returns:
        HTML 註解標註字串（含前綴換行）或空字串
    """
    schema = {
        "ANA": {
            "Problem Analysis": "必填",
            "Solution": "必填",
            "Test Results": "選填（ANA 若有實驗輸出才填；無實驗可留 placeholder）",
            "Completion Info": "必填",
        },
        "IMP": {
            "Problem Analysis": "選填（小型 IMP 可留 placeholder；大型 IMP 建議填寫）",
            "Solution": "選填",
            "Test Results": "必填（至少記錄執行指令與通過數或 commit SHA）",
            "Completion Info": "必填",
        },
        "DOC": {
            "Problem Analysis": "選填（若 DOC 起因於缺陷或盤點結論可填）",
            "Solution": "免填（DOC 類型以變更摘要取代）",
            "Test Results": "免填（DOC 類型無需測試）",
            "Completion Info": "必填（需附變更摘要：哪些文件/章節更新）",
        },
    }
    note = schema.get(ticket_type, {}).get(section)
    if not note:
        return ""
    return f"\n<!-- Schema[{ticket_type}/{section}]: {note}（.claude/pm-rules/ticket-body-schema.md） -->"


def create_ticket_body(what: str, who: str, ticket_type: str = "") -> str:
    """建立 Ticket body。

    Args:
        what: 任務描述（來自 frontmatter["what"]）
        who: 執行代理人（來自 frontmatter["who"]["current"]）
        ticket_type: Ticket 類型（如 'ANA'、'IMP'、'DOC' 等）。當為 'ANA' 時，
            body 會在 Problem Analysis 後插入「重現實驗結果」必填章節
            （PC-063 防護措施 1：強制 ANA Ticket 完成 Reality Test 才列方案）。

    Returns:
        Ticket body 字串（Markdown 格式）

    Body 結構:
        # Execution Log

        ## Task Summary
        {what}

        ---

        ## Problem Analysis
        結構化的問題分析區段，包含根因、影響範圍和相關錯誤模式

        ---

        ## Solution
        <!-- To be filled by executing agent -->

        ---

        ## Test Results
        <!-- To be filled by executing agent -->

        ---

        ## Completion Info
        **Completion Time**: (pending)
        **Executing Agent**: {who}
        **Review Status**: pending

    Examples:
        >>> body = create_ticket_body(
        ...     what="實作功能 X",
        ...     who="parsley-flutter-developer"
        ... )
        >>> "# Execution Log" in body
        True
        >>> "實作功能 X" in body
        True
    """
    pa_marker = _schema_marker(ticket_type, "Problem Analysis")
    sol_marker = _schema_marker(ticket_type, "Solution")
    tr_marker = _schema_marker(ticket_type, "Test Results")
    ci_marker = _schema_marker(ticket_type, "Completion Info")
    return f"""# Execution Log

## Task Summary

{what}

---

## Problem Analysis{pa_marker}

### 問題根因

（待填寫：問題發生的直接原因是什麼？）

### 影響範圍

（待填寫：哪些檔案、模組或功能受影響？）

### 相關 Error Pattern

（待填寫：是否有相關的已知錯誤模式？執行 /error-pattern query 確認）

<!-- 調查過程記錄（可選）：
搜尋指令：grep -rn "pattern" path/ --include="*.py"
確認的位置：
- file1.py:123
注意：接手者應獨立重新驗證數量/範圍（PC-162）
-->

---
{_ana_reproduction_section(ticket_type)}
## Solution{sol_marker}

<!-- To be filled by executing agent -->

---

## Test Results{tr_marker}

<!-- To be filled by executing agent -->

---

## NeedsContext

<!-- 代理人回報資料缺口時追加於此（W17-010 協議）。子項建議 template：
- **缺失項**:（具體指出需要的 context 是什麼）
- **觸發位置**:（檔案:行號 或 決策點）
- **影響**:（缺料導致無法完成哪些 acceptance）
- **建議補料**:（PM 可採取的補充動作）
- **重派成本**:（若需重派所需 token/context 估算）
-->

---

## Exit Status

<!-- 代理人結束時以 YAML 格式回報（W17-010 schema）：
```yaml
status: success        # 枚舉: success|needs_context|blocked|partial_success|failed
reason: ""             # 狀態原因說明
confidence: 1.0        # 0.0-1.0 信心度
acceptance_met: []     # 已完成的 acceptance index 列表
acceptance_unmet: []   # 未完成的 acceptance index 列表
artifacts: []          # 產出檔案路徑列表
context_dependencies: []  # 依賴的 context 來源
estimated_recovery_effort: ""  # 若 needs_context/blocked，預估補料成本
```
對應 exit code: success=0, partial_success=0, needs_context=2, blocked=2, failed=1 -->

---

## Completion Info{ci_marker}

**Completion Time**: (pending)
**Executing Agent**: {who}
**Review Status**: pending
"""


def _append_unique_to_list_field(
    version: str,
    ticket_id: str,
    field_name: str,
    value: str,
) -> bool:
    """通用 helper：append-unique 到目標 ticket 的清單欄位（lock 包圍序列）。

    為 update_parent_children / update_source_spawned_tickets 抽出的共用邏輯。
    兩者差異僅在欄位名（children vs spawned_tickets）與 warning 訊息文案，
    其餘 load → 防禦正規化 → append-unique → save 序列完全一致。

    Why:
        W14-042 race 修復後兩函式幾乎同構，DRY 抽 helper 避免修 lock 邏輯
        時要改兩處（IMP-003 防護）。helper 內統一 try/except 回傳 False，
        讓兩 caller 的失敗策略一致（save 失敗 → False，不 propagate）。

    Args:
        version: 已解析的版本號（caller 應先以 extract_version_from_ticket_id
            解析並 guard None 後傳入）。
        ticket_id: 目標 ticket ID（被修改的 ticket）。
        field_name: 欄位名（"children" 或 "spawned_tickets"）。
        value: 要 append 的值（child_id 或 new_ticket_id）。

    Returns:
        True 表示已成功 load → modify → save（或值已存在，無需寫入）；
        False 表示 ticket 不存在或寫入失敗。
    """
    ticket_path: Path = Path(get_ticket_path(version, ticket_id))
    # W14-042: 用 per-ticket-file lock 包圍 load → modify → save 三步驟，
    # 消除 logical race（W14-005 重現實驗 lost_rate 55.6%~71.9%）。
    with file_lock(ticket_path):
        ticket: Optional[Dict[str, Any]] = load_ticket(version, ticket_id)
        if not ticket:
            return False

        # 防禦性型別檢查：欄位可能因手動編輯變成字串
        raw_field = ticket.get(field_name, [])
        if isinstance(raw_field, str):
            print(
                f"[WARNING] Ticket {ticket_id} 的 {field_name} 欄位為字串而非清單，"
                f"已自動修正",
                file=sys.stderr,
            )
        # _normalize_children 語義為「將任意輸入正規化為 list[str]」，無 children
        # 特化邏輯（pepper Phase 3a §2 決策不改名），可重用於 spawned_tickets。
        items: List[str] = _normalize_children(raw_field)

        if value in items:
            return True  # already present, no-op

        items.append(value)
        ticket[field_name] = items

        actual_path: Path = Path(ticket.get("_path", ticket_path))
        # save_ticket 失敗時回傳 False（不 propagate exception；對齊 CLI 層不回滾設計）
        try:
            save_ticket(ticket, actual_path)
        except (IOError, OSError):
            return False

    return True


def update_parent_children(version: str, parent_id: str, child_id: str) -> bool:
    """更新父 Ticket 的 children 欄位。

    version 參數為向後相容保留，實際使用從 parent_id 提取的版本號。
    這確保跨版本建立子 Ticket 時不會因版本不符而找不到父 Ticket。

    Args:
        version: 版本號（向後相容保留，實際不使用）
        parent_id: 父 Ticket ID（如 "0.31.0-W5-001"）
        child_id: 子 Ticket ID（如 "0.31.0-W5-001.1"）

    Returns:
        bool: 成功更新返回 True，失敗返回 False

    Implementation:
        1. 從 parent_id 提取版本號（不依賴 version 參數）
        2. 載入 parent Ticket（使用 load_ticket）
        3. 若 parent 不存在，返回 False
        4. 取得 children 欄位，確保為 list 型別
        5. 若 child_id 不在 children 中，加入
        6. 更新 parent["children"]
        7. 儲存 parent Ticket（使用 save_ticket）
        8. 返回 True

    Examples:
        >>> update_parent_children("0.31.0", "0.31.0-W5-001", "0.31.0-W5-001.1")
        True

        >>> update_parent_children("0.31.0", "invalid-id", "0.31.0-W5-001.1")
        False

    Side Effects:
        - 修改父 Ticket 檔案
        - 更新 parent["children"] 清單
    """
    # 從 parent_id 提取版本，避免 version 參數與 parent_id 版本不一致
    # （根因：create 命令傳入 current_version，但 parent 可能屬於不同版本）
    resolved_version: Optional[str] = extract_version_from_ticket_id(parent_id)
    if resolved_version is None:
        return False
    return _append_unique_to_list_field(
        resolved_version, parent_id, "children", child_id
    )


def update_source_spawned_tickets(source_ticket_id: str, new_ticket_id: str) -> bool:
    """更新 source Ticket 的 spawned_tickets 欄位（append + 去重）。

    鏡像 update_parent_children 的結構，差異僅在欄位名（children → spawned_tickets）。
    本函式對應 PC-073 CLI 能力缺口修補：spawned 關係代表衍生項獨立交付，
    不會阻擋 source 的 complete。

    Args:
        source_ticket_id: source Ticket ID（如 "0.18.0-W12-002"）
        new_ticket_id: 新建立的衍生 Ticket ID（如 "0.18.0-W12-006"）

    Returns:
        bool: 成功更新返回 True；source 不存在、版本解析失敗或儲存失敗返回 False。

    Implementation:
        1. 從 source_ticket_id 提取版本號
        2. 載入 source Ticket
        3. 若 source 不存在，返回 False
        4. 取得 spawned_tickets 欄位，確保為 list 型別（防禦性：字串→list）
        5. 若 new_ticket_id 不在清單中，append
        6. 儲存 source Ticket（失敗捕獲 IOError/OSError 並返回 False，不向外傳播）
        7. 返回 True

    Side Effects:
        - 修改 source Ticket 檔案
        - 更新 source["spawned_tickets"] 清單

    Examples:
        >>> update_source_spawned_tickets("0.18.0-W12-002", "0.18.0-W12-006")
        True

        >>> update_source_spawned_tickets("invalid-id", "0.18.0-W12-006")
        False
    """
    # 從 source_ticket_id 提取版本（對齊 update_parent_children 的跨版本處理）
    resolved_version: Optional[str] = extract_version_from_ticket_id(source_ticket_id)
    if resolved_version is None:
        return False
    return _append_unique_to_list_field(
        resolved_version, source_ticket_id, "spawned_tickets", new_ticket_id
    )


# ---------------------------------------------------------------------------
# Idempotent Schema H2 dedupe helper（W11-003.3）
# ---------------------------------------------------------------------------
#
# Why: 既有 ticket md 出現相同 Schema H2（例如 ## Test Results）重複出現的情況
# （根因：手動 Edit 時把 frontmatter 預設模板再次插入，或自定義 H2 切斷了 section
# 擷取邊界後 append-log 又補了一份空模板）。重複 H2 會：
#   1) 讓 acceptance-auditor 把純 placeholder 段判為 Solution/Test Results 空，誤報；
#   2) 讓 append-log 的 regex 命中第一個 H2，內容寫入舊段而非預期段；
#   3) 增加閱讀者的認知負擔。
#
# Action: 提供 idempotent 的 dedupe_schema_sections，輸入 body 字串、回傳整理後字串。
# 只處理 Schema 章節清單（pm-rules/ticket-body-schema.md 的權威清單），其他 H2 維持
# 原樣以免誤刪 ANA 重現實驗或 H3 自由結構。
# ---------------------------------------------------------------------------

# Schema 章節清單（與 .claude/rules/core/agent-definition-standard.md 「章節結構規則」一致）
SCHEMA_H2_SECTIONS: Tuple[str, ...] = (
    "Task Summary",
    "Problem Analysis",
    "重現實驗結果",
    "Solution",
    "Test Results",
    "Context Bundle",
    "NeedsContext",
    "Exit Status",
    "Completion Info",
)

# Placeholder pattern：純 frontmatter 模板殘留判定
# 命中即視為「無實質內容」：
#   - <!-- To be filled by executing agent -->
#   - （待填寫：...）
#   - <!-- 調查過程記錄（可選）：... -->（Problem Analysis 預設模板註解）
#   - 純空白 / horizontal rule (---)
_PLACEHOLDER_LINE_PATTERNS = (
    re.compile(r"^\s*<!--\s*To be filled by executing agent\s*-->\s*$"),
    re.compile(r"^\s*（待填寫[:：].*?）\s*$"),
    re.compile(r"^\s*###\s+(問題根因|影響範圍|相關 Error Pattern)\s*$"),
)


def _is_placeholder_only(content: str) -> bool:
    """判斷 H2 區塊內容是否僅為 frontmatter 預設模板殘留。

    Args:
        content: H2 標題之後、下一個 H2 之前的全部文字（含換行）。

    Returns:
        True 若每一個非空白行都符合 placeholder pattern 或屬於 HTML 註解區塊；
        False 若存在任何被視為實質內容的行（包含 ### 子標題以外的人寫文字、
        表格、列表、程式碼區塊等）。
    """
    in_html_comment = False
    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        # 多行 HTML 註解（例：Problem Analysis 預設「<!-- 調查過程記錄... -->」）視為 placeholder
        if in_html_comment:
            if "-->" in line:
                in_html_comment = False
            continue
        if line.startswith("<!--") and "-->" not in line:
            in_html_comment = True
            continue
        if line == "---":
            continue
        if any(pat.match(line) for pat in _PLACEHOLDER_LINE_PATTERNS):
            continue
        # 預設 Problem Analysis 子標題下的「（待填寫：...）」已被 _PLACEHOLDER_LINE_PATTERNS
        # 命中；此處仍出現代表為實質內容
        return False
    return True


def _split_body_by_h2(body: str) -> List[Tuple[Optional[str], str]]:
    """以 H2 (## Title) 為界把 body 切段。

    Returns:
        List of (h2_title or None, segment_text)。第一段若無 H2 前綴，h2_title 為 None；
        segment_text 包含 H2 標題行本身（若有），以維持原始格式還原。
    """
    h2_re = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)
    segments: List[Tuple[Optional[str], str]] = []
    last_end = 0
    last_title: Optional[str] = None
    for match in h2_re.finditer(body):
        if match.start() > last_end or last_title is not None:
            segments.append((last_title, body[last_end:match.start()]))
        last_end = match.start()
        last_title = match.group(1).strip()
    segments.append((last_title, body[last_end:]))
    return segments


def dedupe_schema_sections(body: str) -> str:
    """合併重複出現的 Schema H2 章節，回傳 idempotent 結果。

    規則：
    1. 僅處理 SCHEMA_H2_SECTIONS 列出的章節；其他 H2（含 ANA 重現實驗子段、自定義 H2）
       維持原樣不動。
    2. 對於同名重複 H2：
       - 若僅有一份有實質內容、其餘皆 placeholder：保留有內容那份位置（首次出現），
         移除所有 placeholder 重複段。
       - 若多份都有實質內容：保留首次出現的位置與內容，將後續同名段的內容
         合併到首段尾端（以 `\\n\\n` 分隔），移除後續 H2 標題行避免重複。
       - 若全部皆 placeholder：保留首次出現的 placeholder，移除後續。
    3. 不改變 SCHEMA_H2_SECTIONS 各章節之間的相對順序，也不會新增本來不存在的章節。

    Args:
        body: Ticket body markdown 字串。

    Returns:
        整理後的 body 字串。對相同輸入呼叫多次回傳值穩定（idempotent）。
    """
    segments = _split_body_by_h2(body)

    # 收集每個 Schema 章節的所有出現位置與內容
    occurrences: Dict[str, List[int]] = {}
    for idx, (title, _) in enumerate(segments):
        if title in SCHEMA_H2_SECTIONS:
            occurrences.setdefault(title, []).append(idx)

    # 標記需要刪除的段索引；同時準備首段內容追加
    indices_to_remove: set = set()
    content_to_append: Dict[int, List[str]] = {}

    for title, indices in occurrences.items():
        if len(indices) <= 1:
            continue
        # 拆出每段「H2 標題行」與「內容」
        segment_bodies: List[str] = []
        for idx in indices:
            seg_text = segments[idx][1]
            # 移除第一行 H2 標題（含換行），剩下視為內容
            content_match = re.match(r"^##\s+.+?$\n?", seg_text, re.MULTILINE)
            content_only = seg_text[content_match.end():] if content_match else seg_text
            segment_bodies.append(content_only)

        # 找實質內容段
        substantive_idx_in_indices: List[int] = [
            i for i, c in enumerate(segment_bodies) if not _is_placeholder_only(c)
        ]

        if substantive_idx_in_indices:
            keeper_pos_in_indices = substantive_idx_in_indices[0]
        else:
            keeper_pos_in_indices = 0

        keeper_segment_idx = indices[keeper_pos_in_indices]

        # 後續實質內容段 → 追加到 keeper 尾端
        extras: List[str] = []
        for i, seg_idx in enumerate(indices):
            if i == keeper_pos_in_indices:
                continue
            indices_to_remove.add(seg_idx)
            if i in substantive_idx_in_indices and i != keeper_pos_in_indices:
                extras.append(segment_bodies[i].rstrip())
        if extras:
            content_to_append[keeper_segment_idx] = extras

    if not indices_to_remove and not content_to_append:
        return body

    # 重組
    rebuilt: List[str] = []
    for idx, (title, seg_text) in enumerate(segments):
        if idx in indices_to_remove:
            continue
        appended_text = seg_text
        if idx in content_to_append:
            extras_joined = "\n\n".join(content_to_append[idx])
            # 確保 keeper 段尾與 extras 之間有空行分隔
            if not appended_text.endswith("\n"):
                appended_text += "\n"
            if not appended_text.endswith("\n\n"):
                appended_text += "\n"
            appended_text += extras_joined + "\n"
        rebuilt.append(appended_text)

    return "".join(rebuilt)


def insert_missing_schema_section(
    body: str,
    section: str,
    content: str,
    ticket_type: str = "",
) -> Optional[str]:
    """於 canonical 順序位置插入缺失的 Schema H2 章節（含首筆內容）。

    背景：create 模板僅預生成部分 Schema 章節（如 IMP 模板無 Context Bundle），
    append-log 對「白名單合法但 body 缺失」的章節原本回報 SECTION_NOT_FOUND，
    呼叫端（PM 派發前寫 Context Bundle）被迫繞道手動 Edit ticket md。
    本函式讓缺失章節依 SCHEMA_H2_SECTIONS 的 canonical 順序自動補建，
    消除「目標章節不存在導致 append-log 失敗」的派發前摩擦。

    Args:
        body: Ticket body markdown 字串。
        section: 章節名稱，必須屬於 SCHEMA_H2_SECTIONS（Execution Log 等
            非 Schema 章節不在自動補建範圍，呼叫端應走既有錯誤路徑）。
        content: 首筆寫入內容（呼叫端已完成 H2 → H3 降級等前處理）。
        ticket_type: Ticket 類型（用於補 type-aware Schema 標註註解；
            未定義 type/章節組合時無標註，向後相容）。

    Returns:
        插入後的新 body；section 不在 SCHEMA_H2_SECTIONS 時回傳 None
        （呼叫端 fallback 既有 SECTION_NOT_FOUND 錯誤路徑）。

    插入規則：
        1. 錨點 = body 中第一個 canonical 順序晚於目標章節的既有 Schema H2，
           新章節插在錨點之前（維持 schema 章節相對順序）。
        2. 非 Schema 自定義 H2 不作為錨點（位置語意不明，跳過）。
        3. 無更晚章節時附加於 body 末尾（補 --- 分隔線維持章節邊界格式）。
    """
    if section not in SCHEMA_H2_SECTIONS:
        return None

    canonical_index = SCHEMA_H2_SECTIONS.index(section)
    marker = _schema_marker(ticket_type, section)
    new_block = f"## {section}{marker}\n\n{content}\n\n---\n\n"

    for header_match in re.finditer(r"^##\s+(.+?)\s*$", body, re.MULTILINE):
        title = header_match.group(1).strip()
        if (
            title in SCHEMA_H2_SECTIONS
            and SCHEMA_H2_SECTIONS.index(title) > canonical_index
        ):
            insert_at = header_match.start()
            return body[:insert_at] + new_block + body[insert_at:]

    # 無 canonical 順序更晚的章節 → 附加於 body 末尾
    trimmed = body.rstrip("\n")
    if not trimmed:
        return new_block.rstrip("\n") + "\n"
    separator = "\n\n" if trimmed.endswith("---") else "\n\n---\n\n"
    return trimmed + separator + new_block.rstrip("\n") + "\n"
