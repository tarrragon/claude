#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
Session Start Issue Check Hook

SessionStart 事件觸發時，對本專案（owner）擁有區段的 framework issue 執行
既有 `section_comment.py check` 子命令，於警訊 B（當前結論落後最新觀測）命中
時輸出待整合觀測連結。

背景：comment-as-section 協定下，owner 沒有機制得知自己的 issue 有新觀測
——GitHub watch 為帳號層、session 不繼承未讀狀態，owner 只會在因別的原因打
開 issue 時才看到累積的觀測。check 已列出待整合觀測（警訊 B），缺的是有人
在對的時機跑它；本 hook 只負責在 SessionStart 呼叫既有 check，不重寫其警訊
邏輯。

owner 識別優先讀本地 owned-issues 登記檔（section_comment.py 的 init／
update 成功寫入 GitHub 後同步落地，見 owned_issues_registry 模組
docstring）：登記檔存在且為空清單 -> 本專案已知無擁有任何 issue，直接
跳過、不發任何 gh API 呼叫；登記檔存在且非空 -> 逐張呼叫既有 check（省略
候選發現／owner 驗證兩步驟，登記檔內容已由寫入端確定為真）；登記檔缺失
或無法讀取（從未執行過 init/update、檔案遭刪除、schema 不符）-> fail-open
退回舊 heuristic 路徑：
1. 前綴推導：本專案 git 主 repo 目錄名稱 kebab-case 化（如
   flutter_balance -> flutter-balance），對應本專案歷史上實際使用的 owner
   慣例（如 `flutter-balance-99`）。
2. 候選發現：以 `gh search issues --match comments` 用前綴粗篩候選 issue
   （relevance 排序，非精確比對，可能有 false positive/negative）。
3. 本地驗證：讀取候選 issue 的 comments，比對區段標記首行是否有
   `owner: <前綴>-...`，只有精確比對通過者才視為本專案擁有。

失敗語意：fail-open。登記檔讀取失敗、gh 不可用／未登入／任何步驟逾時或
例外，一律靜默略過（`suppressOutput: true`），僅寫入 hook-logs，不阻擋
session 啟動。
"""

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List, Optional, Tuple

# 加入 hook_utils 路徑
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))
from lib import (  # noqa: E402
    setup_hook_logging,
    run_hook_safely,
    read_json_from_stdin,
    get_project_root,
)
from lib.hook_io import is_subagent_environment  # noqa: E402

EXIT_SUCCESS = 0

FRAMEWORK_REPO = "tarrragon/claude"
SECTION_COMMENT_SCRIPT = ".claude/skills/framework-issue/scripts/section_comment.py"
# owned_issues_registry 模組所在目錄：section_comment.py 家族現行不依賴
# .claude/lib，本 hook 改以 sys.path 插入方式引用其共用 schema/讀寫模組
# （見 _read_owned_issue_numbers），與呼叫 section_comment.py 走 subprocess
# 的既有手法不同——讀 registry 是純檔案 IO，不需 subprocess 開銷。
FRAMEWORK_ISSUE_SCRIPTS_DIR = ".claude/skills/framework-issue/scripts"

# 個別 gh 呼叫逾時（秒）：auth 檢查／search／單一 issue comments 讀取共用。
# 值取小是刻意的——這些呼叫在正常網路下 < 1 秒完成，逾時值只是異常網路下的
# 安全上限，真正的整體上限是 settings.json 註冊的 hook timeout（外層強制
# 終止，見 Ticket Solution 失敗語意說明）。
GH_TIMEOUT_SECONDS = 6
# section_comment.py check 內部自身有兩次 gh 呼叫（各 60 秒逾時），本 hook
# 對其包一層較短逾時，逾時即放棄該張 issue 的這次檢查（下次 session 再試），
# 避免單張 issue 網路異常拖垮整個 hook。
CHECK_TIMEOUT_SECONDS = 12

# gh search 候選上限：query 組成 "owner <prefix>"（單一字串、內含空白，非
# 拆成兩個位置參數）觸發 GitHub 搜尋的同欄位實例 AND 語意——詞彙需落在同一
# 則 comment 內才算命中，故候選精確度已高（實測：僅 "flutter-balance" 12
# 命中且目標排名第 7；"owner flutter-balance" 精確命中僅目標 1 筆）。上限
# 仍保留作為防禦性上界，非仰賴截斷排除雜訊。
SEARCH_RESULT_LIMIT = 10

# 只在「真正的新 session 開始」執行；compact/clear 屬同一 session 內的
# context 事件，非新 session，避免每次都重複觸發網路查詢。
SOURCES_TO_RUN = frozenset({"startup", "resume"})

_SECTION_MARKER_RE = re.compile(
    r"^<!-- section: (?P<name>.+?) owner: (?P<owner>.+?) -->"
)
_WARNING_B_HIT_RE = re.compile(r"^\[警訊 B\]\[主警訊\] 觸發")


def _suppressed_output() -> str:
    """無內容可回報時的標準 SessionStart JSON 輸出（不顯示於對話）。"""
    return json.dumps({"suppressOutput": True}, ensure_ascii=False)


def _project_owner_prefix(logger) -> str:
    """本專案 owner 慣例前綴：git 主 repo 目錄名稱 kebab-case 化。

    刻意不用 lib.get_project_root()（worktree 感知，會回傳 worktree 自身
    路徑）——owner 前綴是「這個專案」的屬性，不是「這個 worktree」的屬性，
    worktree 下跑此 hook 仍須解析回主 repo 名稱，故改用
    `git --git-common-dir`（worktree 與主 repo 皆指向同一個 .git）。
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            basename = Path(result.stdout.strip()).parent.name
            return basename.replace("_", "-")
    except (subprocess.TimeoutExpired, OSError) as exc:
        logger.info("git-common-dir 解析失敗，改用 get_project_root(): %s", exc)
    return get_project_root().name.replace("_", "-")


def _gh_ready(logger) -> bool:
    """gh 可用性 + 認證前置檢查，任一不滿足即 fail-open 略過。"""
    if shutil.which("gh") is None:
        logger.info("gh 未安裝，fail-open 略過")
        return False
    try:
        result = subprocess.run(
            ["gh", "auth", "status"],
            capture_output=True,
            text=True,
            timeout=GH_TIMEOUT_SECONDS,
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        logger.info("gh auth status 例外，fail-open 略過: %s", exc)
        return False
    if result.returncode != 0:
        logger.info("gh 未登入，fail-open 略過")
        return False
    return True


def _search_candidate_issues(prefix: str, logger) -> List[int]:
    """以 gh search issues 粗篩候選 issue（見檔頭「候選發現」說明）。

    query 刻意組成單一字串 "owner <prefix>"（非拆成兩個位置參數）：gh 對
    「單一字串內含空白」與「多個位置參數」的搜尋語意不同，前者觸發同一
    comment 實例內的 AND 匹配，精確度遠高於後者（見上方常數註解的實測對照）。

    失敗（例外／逾時／非 0／JSON 解析失敗）一律回傳空清單，fail-open。
    """
    query = f"owner {prefix}"
    try:
        result = subprocess.run(
            [
                "gh", "search", "issues",
                "--repo", FRAMEWORK_REPO,
                "--match", "comments",
                "--json", "number",
                "--limit", str(SEARCH_RESULT_LIMIT),
                "--", query,
            ],
            capture_output=True,
            text=True,
            timeout=GH_TIMEOUT_SECONDS,
        )
        if result.returncode != 0:
            logger.info("gh search issues 失敗，fail-open 略過: %s", result.stderr.strip())
            return []
        hits = json.loads(result.stdout or "[]")
        return [hit["number"] for hit in hits]
    except (subprocess.TimeoutExpired, OSError, json.JSONDecodeError, KeyError) as exc:
        logger.info("gh search issues 例外，fail-open 略過: %s", exc)
        return []


def _issue_owner_matches(issue_number: int, prefix: str, logger) -> bool:
    """讀取候選 issue 的 comments，比對是否存在 owner 以本專案前綴開頭的
    區段標記（見檔頭「本地驗證」說明）。失敗一律回傳 False，fail-open。
    """
    try:
        result = subprocess.run(
            [
                "gh", "api",
                f"repos/{FRAMEWORK_REPO}/issues/{issue_number}/comments",
                "--paginate",
            ],
            capture_output=True,
            text=True,
            timeout=GH_TIMEOUT_SECONDS,
        )
        if result.returncode != 0:
            logger.info(
                "issue #%s comments 讀取失敗，fail-open 略過: %s",
                issue_number, result.stderr.strip(),
            )
            return False
        comments = json.loads(result.stdout or "[]")
    except (subprocess.TimeoutExpired, OSError, json.JSONDecodeError) as exc:
        logger.info("issue #%s comments 讀取例外，fail-open 略過: %s", issue_number, exc)
        return False

    for comment in comments:
        match = _SECTION_MARKER_RE.match((comment.get("body") or "").strip())
        if match and match.group("owner").startswith(f"{prefix}-"):
            return True
    return False


def _run_check(issue_number: int, logger) -> Optional[str]:
    """呼叫既有 section_comment.py check 子命令（不重寫其警訊邏輯），警訊 B
    命中時回傳完整 stdout；未命中或執行失敗回傳 None。"""
    script = get_project_root() / SECTION_COMMENT_SCRIPT
    try:
        result = subprocess.run(
            [sys.executable, str(script), "check", str(issue_number)],
            capture_output=True,
            text=True,
            timeout=CHECK_TIMEOUT_SECONDS,
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        logger.info("issue #%s check 執行例外，fail-open 略過: %s", issue_number, exc)
        return None
    if result.returncode != 0:
        logger.info(
            "issue #%s check 非 0 結束，fail-open 略過: %s",
            issue_number, result.stderr.strip(),
        )
        return None
    if any(_WARNING_B_HIT_RE.match(line) for line in result.stdout.splitlines()):
        return result.stdout
    return None


def _collect_hits(prefix: str, logger) -> List[Tuple[int, str]]:
    """舊路徑：候選發現 -> 本地驗證 -> 呼叫既有 check 三步驟，回傳警訊 B
    命中清單（owned-issues 登記檔缺失或無法讀取時的 fail-open fallback，
    見檔頭「owner 識別」說明）。"""
    hits: List[Tuple[int, str]] = []
    candidates = _search_candidate_issues(prefix, logger)
    logger.info("prefix=%s candidates=%s", prefix, candidates)
    for number in candidates:
        if not _issue_owner_matches(number, prefix, logger):
            continue
        output = _run_check(number, logger)
        if output:
            hits.append((number, output))
    return hits


def _collect_registry_hits(owned_numbers: List[int], logger) -> List[Tuple[int, str]]:
    """快速路徑：owned-issues 登記檔內容已由寫入端（section_comment.py
    init／update）確定為真，逐張直接呼叫既有 check，省略舊路徑的候選發現
    與本地 owner 驗證兩步驟。"""
    hits: List[Tuple[int, str]] = []
    for number in owned_numbers:
        output = _run_check(number, logger)
        if output:
            hits.append((number, output))
    return hits


def _read_owned_issue_numbers(project_root: Path, logger) -> Optional[List[int]]:
    """讀取本地 owned-issues 登記檔（section_comment.py 寫入端共用模組
    owned_issues_registry，見該模組 docstring 完整 schema／語意說明）。

    回傳 None 代表登記檔缺失／損毀／模組載入失敗，呼叫端應 fail-open 退回
    舊路徑（見檔頭「失敗語意」）；回傳空清單代表已確認本專案無擁有任何
    issue，呼叫端可直接跳過（不發任何 gh API 呼叫）；兩者語意不同，比照
    owned_issues_registry.owned_issue_numbers() 的呼叫端判斷慣例。
    """
    scripts_dir = project_root / FRAMEWORK_ISSUE_SCRIPTS_DIR
    sys.path.insert(0, str(scripts_dir))
    try:
        import owned_issues_registry  # noqa: PLC0415
    except ImportError as exc:
        logger.info("owned_issues_registry 模組載入失敗，fail-open 退回舊路徑: %s", exc)
        return None
    return owned_issues_registry.owned_issue_numbers(project_root=project_root)


def _build_context(label: str, hits: List[Tuple[int, str]]) -> str:
    """組裝 additionalContext 內容：逐張命中 issue 附上 check 完整輸出。

    label 描述本次命中清單的判定依據（登記檔快速路徑 vs owner 前綴
    heuristic fallback），供 additionalContext 說明來源，不影響命中邏輯。
    """
    lines = [
        "## Framework Issue 待整合觀測（session-start-issue-check）",
        "",
        f"以下 {len(hits)} 張本專案（{label}）擁有區段的 "
        "framework issue，「當前結論」已落後最新觀測，內容待整合：",
        "",
    ]
    for number, output in hits:
        lines.append(f"### tarrragon/claude#{number}")
        lines.append("")
        lines.append("```")
        lines.append(output.rstrip())
        lines.append("```")
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    logger = setup_hook_logging("session-start-issue-check")
    input_data = read_json_from_stdin(logger) or {}

    if is_subagent_environment(input_data):
        logger.debug("subagent 環境，framework issue 整合非其職責，略過")
        print(_suppressed_output())
        return EXIT_SUCCESS

    source = input_data.get("source", "")
    if source not in SOURCES_TO_RUN:
        logger.debug("source=%s 非 startup/resume，略過", source)
        print(_suppressed_output())
        return EXIT_SUCCESS

    project_root = get_project_root()
    owned_numbers = _read_owned_issue_numbers(project_root, logger)

    if owned_numbers is not None:
        logger.info("owned-issues 登記檔命中，issues=%s", owned_numbers)
        if not owned_numbers:
            logger.info("登記檔存在但無擁有項目，略過（不發 gh API 呼叫）")
            print(_suppressed_output())
            return EXIT_SUCCESS
        if not _gh_ready(logger):
            print(_suppressed_output())
            return EXIT_SUCCESS
        hits = _collect_registry_hits(owned_numbers, logger)
        label = "owned-issues 登記檔"
    else:
        logger.info("owned-issues 登記檔缺失或無法讀取，fail-open 退回 gh search heuristic 路徑")
        if not _gh_ready(logger):
            print(_suppressed_output())
            return EXIT_SUCCESS
        prefix = _project_owner_prefix(logger)
        hits = _collect_hits(prefix, logger)
        label = f"owner 前綴 `{prefix}-`"

    if not hits:
        logger.info("無警訊 B 命中")
        print(_suppressed_output())
        return EXIT_SUCCESS

    logger.info("警訊 B 命中 %d 張 issue: %s", len(hits), [n for n, _ in hits])
    print(json.dumps(
        {
            "hookSpecificOutput": {
                "hookEventName": "SessionStart",
                "additionalContext": _build_context(label, hits),
            },
            "suppressOutput": False,
        },
        ensure_ascii=False,
    ))
    return EXIT_SUCCESS


if __name__ == "__main__":
    sys.exit(run_hook_safely(main, "session-start-issue-check"))
