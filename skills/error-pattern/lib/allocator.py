"""error-pattern 來源前綴 ID 分配器（1.0.0-W1-019.3）。

實作 Model 1 來源前綴編號（W1-019 決策）的自動分配：
- identify_project_code：以 git toplevel basename 對應 registry `dir` → `code`，
  tooling 零 project-local 設定即可自我識別（registry 同時服務全域唯一 + 自我識別）。
- allocate_pattern_id：掃 `error-patterns/<cat-dir>/<CAT>-<PROJ>-*.md` 取既有最大號 +1，
  flat 凍結 base（`<CAT>-NNN`）不參與遞增（前綴命名空間獨立）。非原子操作，僅
  回傳預覽值（見下方 0.2.1-W3-167 章節）。
- allocate_and_reserve_pattern_id：原子版——持鎖後把「決定編號」與「建立佔位檔」
  合併為單一操作，杜絕並行呼叫撞號（見下方 0.2.1-W3-167 章節）。

依賴邊界：複用 `.claude/lib/pattern_id.py` 的 `PATTERN_ID_RE`（W1-019.2 SSOT），
不在 skill 內複製 regex 以免破壞剛收斂的單一權威。skill 獨立上架時的依賴打包
（pattern_id + pyyaml）屬 W1-001（SKILL 獨立上架規範）範圍。

規則來源：`.claude/methodologies/error-pattern-numbering-methodology.md`、
專案代號 SSOT：`.claude/error-patterns/_project-registry.yaml`。

0.2.1-W3-167（封閉兩面配號競爭）：
    (1) allocator 與 ticket 預留編號的競爭——0.2.1-W3-165 實證：ticket 標題已
        寫定未來要記錄的 pattern ID（如「記錄 IMP-BAL-005」），但對應檔案尚未
        建立，allocator 純掃檔案看不到這個「已預留」狀態，於是把同一號發給
        另一個真正在建檔的呼叫，兩者撞號。修法：`allocate_pattern_id` 與
        `allocate_and_reserve_pattern_id` 預設額外掃描
        `docs/work-logs/**/tickets/*.md` 中精確符合 `<CAT>-<PROJ>-NNN`（本專案
        前綴）的文字引用，視為已佔用（`_max_num_in_ticket_references`）。曾比較
        三個方向：(a) 本方案；(b) 建票時即建立佔位檔（需改 ticket_system 建票
        流程，超出本票宣告寫入集）；(c) 純規範「禁止預留」不修工具（無自動化
        防線，一違反即復發，且不滿足「模擬驗證不再撞號」的驗收要求）。選 (a)
        並將實作收斂為精確前綴比對（非籠統關鍵字搜尋）——0.2.1-W3-167 對本專案
        現有 7 筆全文候選比對只留 1 筆真前綴匹配（合法待建票 IMP-BAL-006），
        其餘 6 筆為 flat 格式（`PC-048` 等）的框架歷史討論文字，精確前綴過濾
        天然排除，證實低誤判率。
    (2) 框架 repo issue 28（TOCTOU）——兩個並行 agent 同時讀取最大編號 +1 配到
        同號（2026-07-31 consumer 實證）。修法：`allocate_and_reserve_pattern_id`
        以 `_allocation_lock` 持鎖序列化「掃描 → 決定 → 建立佔位檔」整段臨界
        區，使第二個呼叫的掃描必然看到第一個呼叫已建立的佔位檔。未採
        `filelock` 套件：allocator.py 供 plain `sys.path.insert` import 呼叫
        （見 skill.md 用法，非 uv-script 進入點），實測本機 plain python3 與
        `uv run --with pytest` 環境皆無 `filelock`，`fcntl` 則為 POSIX 標準庫
        恆可得，故改用 `fcntl.flock` 直接實作，避免引入不保證可得的依賴。
        非 POSIX 平台優雅降級（stderr 警告 + 無鎖續行，同
        `ticket_system.lib.file_lock.create_id_allocation_lock` 降級哲學）。
"""

import contextlib
import datetime
import re
import sys
from pathlib import Path

import yaml

try:
    import fcntl  # POSIX-only；非 POSIX 平台優雅降級（見 _allocation_lock）
except ImportError:  # pragma: no cover - 本機開發/CI 皆為 POSIX，缺口僅涵蓋跨平台移植
    fcntl = None

# 複用 lib 的 SSOT regex（W1-019.2，E2 linux F3）解析既有 ID。
_claude_dir = Path(__file__).resolve().parents[3]  # .claude
if str(_claude_dir) not in sys.path:
    sys.path.insert(0, str(_claude_dir))

from lib.pattern_id import PATTERN_ID_RE  # noqa: E402

# Category 前綴 → 目錄（與 skills/error-pattern/SKILL.md 編號章節一致）。
_CATEGORY_DIRS = {
    "ARCH": "architecture",
    "CQ": "code-quality",
    "DOC": "documentation",
    "IMP": "implementation",
    "PROC": "process",
    "PC": "process-compliance",
    "TEST": "test",
}

# ticket 目錄相對 claude_dir 上層的預設路徑段（見 _default_tickets_root）。
_TICKETS_SUBPATH = ("docs", "work-logs")


def identify_project_code(registry_path, repo_toplevel) -> str:
    """以 git toplevel basename 反查 registry `dir` 取得專案代號 `code`。

    Args:
        registry_path: `_project-registry.yaml` 路徑。
        repo_toplevel: git toplevel 路徑（取 basename 比對 `dir` 欄）。

    Raises:
        ValueError: basename 未登錄於 registry（防止靜默產生錯誤前綴）。
    """
    data = yaml.safe_load(Path(registry_path).read_text(encoding="utf-8")) or {}
    basename = Path(repo_toplevel).name
    for proj in data.get("projects", []):
        if proj.get("dir") == basename:
            return proj["code"]
    raise ValueError(
        f"專案目錄 '{basename}' 未登錄於 {registry_path}。"
        "新專案首次新增 error-pattern 前須先登錄 code + dir（見 numbering methodology）。"
    )


def _max_num_in_dir(cat_dir: Path, prefix: str) -> int:
    """掃 `cat_dir` 下 `{prefix}*.md` 取符合 `PATTERN_ID_RE` 的既有最大號；無則 0。"""
    max_num = 0
    if cat_dir.is_dir():
        for path in cat_dir.glob(f"{prefix}*.md"):
            match = PATTERN_ID_RE.search(path.name)
            if not match:
                continue
            pattern_id = match.group(0).upper()
            if not pattern_id.startswith(prefix):
                continue
            num = int(pattern_id.rsplit("-", 1)[1])
            max_num = max(max_num, num)
    return max_num


def _default_tickets_root(claude_dir) -> Path:
    """`claude_dir` 上層目錄下的預設 ticket 根目錄（`docs/work-logs`）。"""
    return Path(claude_dir).resolve().parent.joinpath(*_TICKETS_SUBPATH)


def _max_num_in_ticket_references(tickets_root: Path, cat: str, project_code: str) -> int:
    """掃 `tickets_root` 下所有 ticket md 檔的全文，取本專案精確前綴
    `<CAT>-<PROJ>-NNN` 文字引用的最大號；無則 0（0.2.1-W3-167）。

    只比對精確前綴（`cat` + `-` + `project_code` + `-`），不比對 flat 格式或
    其他專案前綴——避免把框架歷史文件中討論其他專案/其他 ticket 的 ID 字面
    誤判為本專案的預留編號（見模組 docstring 誤判率查證）。

    `tickets_root` 不存在（如測試 `tmp_path` 無 `docs/` 目錄，或專案尚無
    ticket 目錄）時回傳 0，不丟例外——此掃描屬盡力而為的輔助資訊，缺目錄
    不應阻斷配號。
    """
    if not tickets_root.is_dir():
        return 0
    ref_re = re.compile(
        rf"\b{re.escape(cat)}-{re.escape(project_code)}-(\d+)\b", re.IGNORECASE
    )
    max_num = 0
    for path in tickets_root.rglob("tickets/*.md"):
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for match in ref_re.finditer(text):
            max_num = max(max_num, int(match.group(1)))
    return max_num


def _resolve_tickets_root(claude_dir, tickets_root):
    """解析 `tickets_root` 參數：`False` 顯式停用；`None` 用預設路徑；其餘視為指定路徑。"""
    if tickets_root is False:
        return None
    return Path(tickets_root) if tickets_root else _default_tickets_root(claude_dir)


def allocate_pattern_id(category_prefix, claude_dir, project_code, *, tickets_root=None) -> str:
    """分配下一個來源前綴 ID：`<CAT>-<PROJ>-NNN`（NNN = 既有最大號 +1，首次 001）。

    flat 凍結 base（`PC-099`）不參與遞增——只掃 `<CAT>-<PROJ>-` 前綴空間。

    0.2.1-W3-167：預設額外掃描 `tickets_root`（預設 `{claude_dir 上層}/docs/
    work-logs`）下 ticket md 文字中已預留但檔案未建立的本專案前綴編號，一併
    納入 max 計算（見模組 docstring）。傳 `tickets_root=False` 可完全停用此
    掃描，回到純檔案掃描行為。

    本函式非原子操作：不持鎖、不建立檔案，僅回傳「呼叫當下」的預覽值。若
    呼叫後到實際建檔前存在並行呼叫風險，改用 `allocate_and_reserve_pattern_id`
    （持鎖 + 立即建立佔位檔，杜絕 TOCTOU）。

    Raises:
        ValueError: 未知 category 前綴。
    """
    cat = category_prefix.upper()
    if cat not in _CATEGORY_DIRS:
        raise ValueError(
            f"未知 category 前綴 '{category_prefix}'，合法值：{sorted(_CATEGORY_DIRS)}"
        )

    cat_dir = Path(claude_dir) / "error-patterns" / _CATEGORY_DIRS[cat]
    prefix = f"{cat}-{project_code.upper()}-"

    max_num = _max_num_in_dir(cat_dir, prefix)

    root = _resolve_tickets_root(claude_dir, tickets_root)
    if root is not None:
        max_num = max(max_num, _max_num_in_ticket_references(root, cat, project_code.upper()))

    return f"{prefix}{max_num + 1:03d}"


def _warn_allocation_lock_degraded(reason: str) -> None:
    """鎖降級警告（quality-baseline 規則 4：失敗必須對用戶可見，走 stderr）。"""
    sys.stderr.write(
        f"[WARNING] allocator: {reason}；以無鎖模式配號。並行呼叫期間請改為序列"
        f"執行以避免 ID 撞號（0.2.1-W3-167 / 框架 issue 28）\n"
    )


@contextlib.contextmanager
def _allocation_lock(claude_dir):
    """error-patterns 目錄級 blocking 鎖，序列化「掃描既有編號 → 決定 → 建立
    佔位檔」臨界區（0.2.1-W3-167，框架 issue 28 併入範圍）。

    Why：兩個並行 agent 同時呼叫配號會各自讀到同一份既有檔案最大號，各自 +1
    配出同一 ID（2026-07-31 consumer 實證，未釀事故僅因後者恰在寫入前重讀）。
    本鎖序列化整段 scan → decide → write 序列，配合
    `allocate_and_reserve_pattern_id` 立即建立佔位檔，使第二個呼叫的掃描必然
    看到第一個呼叫已佔用的編號。

    降級策略：`fcntl` 不可用（非 POSIX 平台）或取鎖失敗時，warn 並以無鎖模式
    續行，不阻斷單 process 呼叫——與 `ticket_system.lib.file_lock.
    create_id_allocation_lock` 同一降級哲學（見模組 docstring 依賴選型說明）。
    """
    lock_path = Path(claude_dir) / "error-patterns" / ".allocator.lock"
    if fcntl is None:
        _warn_allocation_lock_degraded("fcntl 不可用（非 POSIX 平台）")
        yield
        return
    try:
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        lock_file = open(lock_path, "a+")
    except OSError as exc:
        _warn_allocation_lock_degraded(f"lock file 開啟失敗（{exc}）")
        yield
        return
    try:
        fcntl.flock(lock_file, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(lock_file, fcntl.LOCK_UN)
        lock_file.close()


def allocate_and_reserve_pattern_id(
    category_prefix, claude_dir, project_code, *, tickets_root=None, reserved_by=None
) -> Path:
    """原子分配並立即保留：持鎖 → 掃描既有編號（含 ticket 文字引用）→ 建立
    佔位檔，回傳佔位檔路徑（0.2.1-W3-167，框架 issue 28 併入範圍）。

    與 `allocate_pattern_id` 的差異：後者僅回傳字串預覽、不持鎖、不建檔，呼叫
    後到實際建檔前存在 TOCTOU 空窗；本函式在鎖保護下把「決定編號」與「佔用
    該編號」合併為單一原子操作——回傳時佔位檔已存在於磁碟，任何後續呼叫
    （含並行 process/thread）掃描既有檔案時必然看到此佔位檔，不可能再配出
    相同編號（acceptance #4 以真實並行呼叫驗證，見對應測試）。

    佔位檔為最小 frontmatter（`status: reserved`），供呼叫端之後以 Edit（非
    Write 新檔）填入實際內容——檔案已存在，後續填寫不再有配號 race。長期
    停留 reserved 狀態的佔位檔應視為待處理提醒，由對應 ticket 進度驅動，非
    本函式職責。

    Returns:
        Path: 已建立的佔位檔路徑（檔名 `{pattern_id}.md`，無 slug；填入實際
            內容時可依慣例改名為 `{pattern_id}-{slug}.md`）。

    Raises:
        ValueError: 未知 category 前綴。
    """
    cat = category_prefix.upper()
    if cat not in _CATEGORY_DIRS:
        raise ValueError(
            f"未知 category 前綴 '{category_prefix}'，合法值：{sorted(_CATEGORY_DIRS)}"
        )

    claude_dir = Path(claude_dir)
    cat_dir = claude_dir / "error-patterns" / _CATEGORY_DIRS[cat]
    prefix = f"{cat}-{project_code.upper()}-"
    root = _resolve_tickets_root(claude_dir, tickets_root)

    with _allocation_lock(claude_dir):
        max_num = _max_num_in_dir(cat_dir, prefix)
        if root is not None:
            max_num = max(
                max_num, _max_num_in_ticket_references(root, cat, project_code.upper())
            )
        pattern_id = f"{prefix}{max_num + 1:03d}"

        cat_dir.mkdir(parents=True, exist_ok=True)
        stub_path = cat_dir / f"{pattern_id}.md"
        reserved_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
        stub_path.write_text(
            "---\n"
            f"id: {pattern_id}\n"
            "title: (reserved - 內容待補)\n"
            "status: reserved\n"
            f"reserved_by: {reserved_by or 'unknown'}\n"
            f"reserved_at: {reserved_at}\n"
            "---\n\n"
            f"# {pattern_id}: (reserved - 內容待補)\n\n"
            "此檔案由 allocate_and_reserve_pattern_id 建立，用於原子化保留編號，"
            "尚未填入實際內容。請以 Edit（非 Write 新檔）填入正式內容，並視需要"
            f"改名為 `{pattern_id}-<slug>.md`。\n",
            encoding="utf-8",
        )
        return stub_path
