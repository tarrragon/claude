#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
.claude 資料夾同步腳本 - 從獨立 repo 拉取更新

跨平台支援：macOS / Linux / Windows
依賴：Python 3.8+, git

拉取內容:
  - .claude/ 目錄所有檔案（同步覆蓋 + 清理遠端已刪除的檔案）
  - FLUTTER.md（若遠端 project-templates 中存在）

不覆蓋內容:
  - 根目錄 CLAUDE.md（保留專案特定配置）
  - .claude/hook-logs/（本地日誌）
  - .claude/handoff/（本地交接檔案）

Safety net:
  上游 repo 的 hook 檔案 mode 可能已損壞（Windows 推送時 NTFS 無 exec bit），
  本腳本會在同步後自動對 .claude/hooks/**/*.py 強制 chmod +x。
  完整背景與除錯指南詳見 WINDOWS-NOTES.md。
"""

import filecmp
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None

# 排除分類與 should_exclude 由 SSOT manifest 統一提供（ARCH-020，W1-027）。
# pull 端的三方合併用 should_exclude 過濾 LOCAL_ONLY / 憑證檔，避免本地 runtime
# state 被遠端 delta 蓋掉，與 push/status 端共用同一判定避免漂移。
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "hooks" / "lib"))
from sync_exclude_manifest import should_exclude  # noqa: E402

# ============================================================================
# Constants
# ============================================================================

REPO_URL = "https://github.com/tarrragon/claude.git"

# Git clone timeout protection (in seconds)
# L1：三方合併需完整 git 歷史（git diff BASE HEAD / git show BASE:path），
# shallow clone 取不到 base commit；改用較寬的 300s timeout 容納 full / blob:none clone。
GIT_CLONE_TIMEOUT_SECONDS = 300

# 同步狀態檔與 base SHA 欄位（與 status 端 SSOT 一致，W1-025 schema）。
SYNC_STATE_FILENAME = ".sync-state.json"
BASE_SHA_FIELD = "last_synced_base_sha"

# 三方合併衝突暫存目錄（M3：local-only，不推送）。
SYNC_CONFLICTS_DIR = ".sync-conflicts"
GIT_HTTP_LOW_SPEED_LIMIT_BYTES = "1000"
GIT_HTTP_LOW_SPEED_TIME_SECONDS = "30"

# Changed files display limit
MAX_CHANGED_FILES_DISPLAY = 3

# 大檔案比對閾值（超過此大小只比 size，不做全量內容比對）
_LARGE_FILE_THRESHOLD = 1_048_576  # 1MB

# 遠端 repo 專有：存在於遠端但不需複製到本地
REMOTE_ONLY = frozenset({".git", "project-templates"})

# 本地專有：只存在於本地，同步時不刪除也不覆蓋
#
# 排除分類（與 sync-claude-push.py EXCLUDE_PATTERNS 對稱，詳版見
# .claude/references/sync-exclusion-guide.md）：
#   A - Runtime state：dispatch-active.json、hook-state/、pm-status.json
#   B - Local-only settings：settings.local.json、sync-preserve.yaml、.sync-state.json
#   C - Session-bound log：hook-logs/、handoff/、PM_INTERVENTION_REQUIRED、ARCHITECTURE_REVIEW_REQUIRED
#
# 新增機制時請對應分類並同步更新 push 端 EXCLUDE_PATTERNS，避免不對稱同步。
LOCAL_ONLY = frozenset({
    # 類型 C - Session-bound log
    "hook-logs",
    "handoff",
    "PM_INTERVENTION_REQUIRED",
    "ARCHITECTURE_REVIEW_REQUIRED",
    # 類型 A - Runtime state
    "pm-status.json",
    "dispatch-active.json",    # 本 session 派發狀態，專案特定 runtime state
    "hook-state",              # Hook runtime state 目錄（wrap-tripwire 等）
    # 工具產物（Python 快取，無跨專案共用價值）
    "__pycache__",
    ".pytest_cache",
    ".venv",
    # 類型 B - Local-only settings
    "sync-preserve.yaml",      # 各專案的 preserve 清單不同，不可被遠端覆蓋
    ".sync-state.json",        # 本地同步狀態，不可被遠端覆蓋
    "settings.local.json",     # 各專案個別覆蓋設定，不應被遠端同步覆蓋
    ".zhtw-mcp-skip",          # 各專案 opt-out 繁中檢查的 flag，per-project 決定
})

# 同步時跳過的所有路徑（合併使用）
SKIP_DURING_SYNC = REMOTE_ONLY | LOCAL_ONLY

# Q（0.19.1-W1-021）：備份 .claude 時排除的工具產物，避免備份 bloat / 變慢
# / 遇 broken symlink 拋例外。主同步本身已排除這些，備份須一致。
BACKUP_IGNORE_PATTERNS = ("__pycache__", ".pytest_cache", ".venv")

# 同步後強制還原 executable bit 的目錄名（convention-based safety net）
# 上游 repo 的 mode 可能已損壞（push 端未保留 100755），
# pull 後需對這些目錄下的 .py 強制 chmod +x 確保 Hook 可執行。
# 注意：以「目錄名」遞迴比對，覆蓋頂層 .claude/hooks/ 與 W10-092 遷移後的
# skills/<name>/hooks/（缺陷 G）。
EXECUTABLE_HOOK_DIR_NAMES = ("hooks",)


def iter_executable_hook_dirs(root: Path):
    """遞迴 yield root 下所有名稱屬 EXECUTABLE_HOOK_DIR_NAMES 的目錄。

    取代舊 `root / subdir` 單層查找，使 skills/<name>/hooks/ 也被涵蓋。
    跳過 symlink 目錄避免循環。

    參數:
        root: 起始掃描根目錄（.claude 或其暫存樹）

    產出:
        Path: 每個符合名稱的目錄
    """
    if not root.is_dir():
        return
    for dirpath, dirnames, _filenames in os.walk(root):
        # 跳過 symlink 指向的子目錄（os.walk 預設 followlinks=False，已安全）
        for name in dirnames:
            if name in EXECUTABLE_HOOK_DIR_NAMES:
                yield Path(dirpath) / name


# settings.json 中提取 hook command 內 .py 路徑的正則（容錯 shell 包裝）
# 匹配 .claude/skills/.../xxx.py（不論前綴有 uv run / $CLAUDE_PROJECT_DIR 等）
_SKILL_SCRIPT_RE = re.compile(r"\.claude/(skills/[^\s'\"]+?\.py)")


def collect_registered_skill_scripts(claude_dir: Path) -> set[Path]:
    """從 settings.json 反查被註冊為 hook command 直接執行的 skill 根目錄 .py。

    背景（W9-007）：exec-bit 還原以「目錄名 hooks」為邊界，未涵蓋位於 skill
    根目錄（非 hooks/ 子目錄）但被 settings.json 註冊為執行的腳本，如
    skills/continuous-learning/evaluate-session.py。這類腳本 sync 後失去
    exec bit 會觸發 Permission denied。

    採策略 C（settings.json 反查）而非純 shebang 偵測：command 是「被註冊為
    執行」的權威來源，可精準命中且不會誤判未註冊的 shebang 腳本（如
    skills/ticket/test_migration_dryrun.py）。

    只解析 settings.json（settings.local.json 不 sync 故忽略）。command 可能含
    shell 包裝（uv run、$CLAUDE_PROJECT_DIR 變數），以正則容錯提取 .py 路徑。
    已落在 hooks/ 目錄者由 iter_executable_hook_dirs 涵蓋，此處只保留非 hooks/ 路徑
    以避免重複。

    參數:
        claude_dir: .claude 目錄的絕對路徑

    傳回:
        set[Path]: 存在於 claude_dir 下、被註冊執行且非 hooks/ 路徑的 .py 絕對路徑
    """
    settings_path = claude_dir / "settings.json"
    if not settings_path.is_file():
        return set()
    try:
        text = settings_path.read_text(encoding="utf-8")
    except OSError as exc:
        print_color(f"   警告: 無法讀取 settings.json: {exc}", "yellow")
        return set()

    scripts: set[Path] = set()
    for match in _SKILL_SCRIPT_RE.finditer(text):
        rel = match.group(1)  # skills/<name>/.../xxx.py
        # hooks/ 目錄下的已由 iter_executable_hook_dirs 涵蓋，避免重複
        if "/hooks/" in rel:
            continue
        candidate = claude_dir / rel
        if candidate.is_file():
            scripts.add(candidate)
    return scripts


def load_preserve_list(claude_dir: Path) -> set[str]:
    """讀取 sync-preserve.yaml 中的本地特化檔案清單。

    若檔案不存在，回傳空集合（合法情境：專案未定義 preserve 清單）。
    若檔案存在但解析失敗，fail-loud（stderr 警告 + raise），不靜默回空集合。

    H（0.19.1-W1-021）：靜默回空集合會關閉全部 preserve 保護，導致本地
    特化檔案（settings.local.json 等）被遠端覆蓋。違反 quality-baseline
    規則 4（禁止靜默失敗），故 malformed preserve 改為 fail-loud。

    參數:
        claude_dir: .claude 目錄路徑

    傳回:
        set[str]: 需要保留的相對路徑集合（相對於 .claude/）

    例外:
        Exception: sync-preserve.yaml 存在但無法解析時拋出（fail-loud）。
    """
    preserve_file = claude_dir / "sync-preserve.yaml"
    if not preserve_file.exists():
        return set()

    content = preserve_file.read_text(encoding="utf-8")

    # 嘗試使用 PyYAML，若未安裝則用簡易解析
    if yaml is not None:
        try:
            data = yaml.safe_load(content)
        except Exception as exc:
            # fail-loud：雙通道可觀測性（stderr + raise），禁止靜默回空集合
            sys.stderr.write(
                f"[sync-pull] preserve 清單解析失敗，sync 中止以避免關閉全部 "
                f"preserve 保護: {preserve_file}: {exc}\n"
            )
            raise
        if isinstance(data, dict) and isinstance(data.get("preserve"), list):
            return set(data["preserve"])
        # 結構不符（非 dict 或 preserve 非 list）：可能 YAML 合法但格式錯誤
        if data is None:
            return set()
        sys.stderr.write(
            f"[sync-pull] preserve 清單格式錯誤（預期 dict 含 preserve list）"
            f"，sync 中止以避免關閉全部 preserve 保護: {preserve_file}\n"
        )
        raise ValueError(
            f"sync-preserve.yaml 格式錯誤：預期 'preserve:' 為 list，"
            f"實際得到 {type(data).__name__}"
        )

    # 簡易 fallback 解析：讀取 "- path" 格式的行
    paths: set[str] = set()
    in_preserve = False
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("#") or not stripped:
            continue
        if stripped == "preserve:":
            in_preserve = True
            continue
        if in_preserve and stripped.startswith("- "):
            paths.add(stripped[2:].strip())
        elif stripped and not stripped.startswith("#"):
            # 只有非空、非註解的行才關閉 preserve 區塊
            in_preserve = False
        # 空行和註解行不影響 in_preserve 狀態
    return paths


def print_color(msg: str, color: str = "yellow") -> None:
    """輸出彩色訊息到標準輸出。

    使用 ANSI 顏色代碼，在 Windows 無終端環境下自動降級為無色輸出。

    參數:
        msg: 要輸出的訊息文字
        color: 顏色名稱，支援 "green"、"yellow"、"red"，預設為 "yellow"

    異常:
        無，異常情況會自動降級處理
    """
    colors = {"green": "\033[0;32m", "yellow": "\033[1;33m", "red": "\033[0;31m"}
    nc = "\033[0m"
    if sys.platform == "win32" and not os.environ.get("TERM"):
        print(msg)
    else:
        print(f"{colors.get(color, '')}{msg}{nc}")


def run_git(args: list[str], cwd: str | None = None) -> subprocess.CompletedProcess:
    """執行 git 命令並回傳結果。

    以子流程方式執行 git 命令，捕獲標準輸出和標準錯誤，
    結果以文字格式儲存在 CompletedProcess 物件中。

    參數:
        args: git 命令的引數清單（不包含 "git" 本身）
        cwd: 執行命令的工作目錄，預設為 None（使用目前工作目錄）

    傳回:
        subprocess.CompletedProcess: 包含 returncode、stdout、stderr 的結果物件
    """
    return subprocess.run(
        ["git", *args],
        capture_output=True,
        text=True,
        cwd=cwd,
    )


def find_project_root() -> Path:
    """向上尋找專案根目錄。

    從目前工作目錄開始，逐層向上尋找 .claude 目錄。
    若找不到，輸出錯誤訊息並終止程式。

    傳回:
        Path: 專案根目錄路徑（包含 .claude 的目錄）

    異常:
        呼叫 sys.exit(1)，如果找不到 .claude 目錄則終止程式
    """
    current = Path.cwd()
    while current != current.parent:
        if (current / ".claude").is_dir():
            return current
        current = current.parent
    print_color("找不到 .claude 目錄，請在專案根目錄執行此腳本", "red")
    sys.exit(1)


def check_uncommitted_changes(project_root: Path) -> None:
    """檢查 .claude 的未提交變更。

    執行 git diff 檢查工作目錄和暫存區是否有未提交的變更。
    若發現變更則輸出警告訊息並終止程式，防止同步時發生衝突。

    參數:
        project_root: 專案根目錄路徑

    異常:
        呼叫 sys.exit(1)，若有未提交變更或 git 命令失敗則終止程式
    """
    result = run_git(
        ["diff", "--name-only", "--", ".claude"],
        cwd=str(project_root),
    )
    cached = run_git(
        ["diff", "--cached", "--name-only", "--", ".claude"],
        cwd=str(project_root),
    )
    if result.returncode != 0 or cached.returncode != 0:
        print_color("警告: git diff 執行失敗，請確認 git 狀態正常", "red")
        sys.exit(1)
    has_changes = bool(result.stdout.strip() or cached.stdout.strip())
    if has_changes:
        print_color("警告: .claude 有未提交的變更", "red")
        print("請先提交或暫存變更，避免衝突")
        sys.exit(1)


def clone_repo(temp_dir: Path) -> None:
    """從遠端 repo 克隆最新版本到臨時目錄。

    L1：三方合併需要 base commit 可達（git diff BASE HEAD / git show BASE:path），
    淺層 clone（--depth 1）取不到歷史。改用 --filter=blob:none 的 partial clone：
    保留完整 commit graph（base commit 可達），blob 按需 lazy fetch，兼顧速度與可達性。
    若 partial clone 不被遠端支援，降級為 full clone。timeout 拉寬至 300s。

    參數:
        temp_dir: 臨時目錄路徑，克隆內容將放置於此

    異常:
        subprocess.TimeoutExpired: 若克隆超過設定的超時時間
        呼叫 sys.exit(1)，若克隆命令失敗則終止程式
    """
    env = os.environ.copy()
    env["GIT_HTTP_LOW_SPEED_LIMIT"] = GIT_HTTP_LOW_SPEED_LIMIT_BYTES
    env["GIT_HTTP_LOW_SPEED_TIME"] = GIT_HTTP_LOW_SPEED_TIME_SECONDS

    # 先嘗試 blob:none partial clone（保留 commit graph，blob lazy fetch）
    result = subprocess.run(
        ["git", "clone", "--filter=blob:none", REPO_URL, str(temp_dir)],
        capture_output=True,
        text=True,
        env=env,
        timeout=GIT_CLONE_TIMEOUT_SECONDS,
    )
    if result.returncode != 0:
        # 降級為 full clone（partial clone 不被遠端支援時）
        print_color("   partial clone 失敗，降級為 full clone...", "yellow")
        if temp_dir.exists():
            shutil.rmtree(temp_dir, ignore_errors=True)
        temp_dir.mkdir(parents=True, exist_ok=True)
        result = subprocess.run(
            ["git", "clone", REPO_URL, str(temp_dir)],
            capture_output=True,
            text=True,
            env=env,
            timeout=GIT_CLONE_TIMEOUT_SECONDS,
        )
        if result.returncode != 0:
            print_color(f"git clone 失敗: {result.stderr}", "red")
            sys.exit(1)


# ============================================================================
# 三方合併核心（A3+L+M）：base snapshot delta + 逐檔三方合併 + 原子套用
# ============================================================================


def read_base_sha(claude_dir: Path) -> str | None:
    """讀取 .sync-state.json 中的 last_synced_base_sha（W1-025 schema）。

    無檔案 / 無欄位 / 解析失敗皆回傳 None（向後相容：觸發全量 overlay fallback）。

    參數:
        claude_dir: .claude 目錄路徑

    傳回:
        str | None: 上次同步的上游 base commit SHA，無則 None
    """
    state_file = claude_dir / SYNC_STATE_FILENAME
    if not state_file.exists():
        return None
    try:
        data = json.loads(state_file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    sha = data.get(BASE_SHA_FIELD)
    return sha if isinstance(sha, str) and sha else None


def write_base_sha(claude_dir: Path, base_sha: str) -> None:
    """同步成功後，將上游 HEAD SHA 寫入 .sync-state.json 的 last_synced_base_sha。

    保留既有欄位（如 last_push_hash），僅覆寫 base SHA 單一欄位（H1：禁雙欄位）。

    參數:
        claude_dir: .claude 目錄路徑
        base_sha: 本次同步上游 HEAD 的 commit SHA
    """
    state_file = claude_dir / SYNC_STATE_FILENAME
    data: dict = {}
    if state_file.exists():
        try:
            data = json.loads(state_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            data = {}
    data[BASE_SHA_FIELD] = base_sha
    state_file.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def is_base_reachable(temp_dir: Path, base_sha: str) -> bool:
    """驗證 base_sha 在上游 clone 中可達為 commit 物件（H4）。

    用 git cat-file -e <sha>^{commit}：物件存在且可解析為 commit 才回 True。
    不可達（上游 force-push / GC / partial clone 未抓到）回 False，呼叫端降級全量 overlay。

    參數:
        temp_dir: 上游 repo clone 路徑
        base_sha: 待驗證的 base commit SHA

    傳回:
        bool: base commit 可達為 True
    """
    if not base_sha:
        return False
    result = run_git(
        ["cat-file", "-e", f"{base_sha}^{{commit}}"], cwd=str(temp_dir)
    )
    return result.returncode == 0


def compute_upstream_delta(temp_dir: Path, base_sha: str) -> dict[str, str]:
    """計算上游從 base_sha 到 HEAD 的檔案變更 delta（H3）。

    用 git diff --name-status --no-renames base HEAD：
      - --no-renames 使 rename 退化為 D(舊路徑) + A(新路徑)，避免 rename 偵測的
        路徑對應複雜度，三方合併端只需處理 A/M/D 三種狀態。
      - 輸出每行格式 "<status>\\t<path>"，以 split('\\t') 解析並斷言欄位數，
        防止含空白路徑被空白切割誤判。

    參數:
        temp_dir: 上游 repo clone 路徑
        base_sha: base commit SHA

    傳回:
        dict[str, str]: {相對 repo root 的路徑: 狀態字母}，狀態 ∈ {A, M, D}
    """
    result = run_git(
        ["diff", "--name-status", "--no-renames", base_sha, "HEAD"],
        cwd=str(temp_dir),
    )
    delta: dict[str, str] = {}
    if result.returncode != 0:
        return delta
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        fields = line.split("\t")
        # --no-renames 保證恰為 [status, path] 兩欄（無 rename 的 status\told\tnew）
        assert len(fields) == 2, f"非預期的 diff 行格式（含 rename？）: {line!r}"
        status, path = fields[0].strip(), fields[1].strip()
        # 只取狀態首字母（A/M/D），忽略 score 後綴
        delta[path] = status[:1]
    return delta


def _read_upstream_blob(temp_dir: Path, sha: str, rel_path: str) -> bytes | None:
    """讀取上游 repo 在 sha 版本下指定路徑的檔案內容（git show sha:path）。

    路徑不存在於該版本時回 None（例如 A 狀態檔在 base 無內容）。

    參數:
        temp_dir: 上游 repo clone 路徑
        sha: commit SHA
        rel_path: 相對 repo root 的路徑

    傳回:
        bytes | None: 檔案內容，不存在回 None
    """
    result = subprocess.run(
        ["git", "show", f"{sha}:{rel_path}"],
        cwd=str(temp_dir),
        capture_output=True,
    )
    if result.returncode != 0:
        return None
    return result.stdout


def three_way_merge_file(
    base_content: bytes | None,
    local_path: Path | None,
    upstream_path: Path | None,
    local_deleted: bool = False,
) -> tuple[bytes | None, bool]:
    """對單一檔案執行三方合併。

    回傳 (merged_content, conflict)：
      - merged_content is None 表示「此檔不應寫入本地」（本地刪除優先保留）
      - conflict True 表示 local 與 upstream 各自修改同一處，需人工處理

    合併規則：
      - 本地已刪除（local_deleted）：保留刪除，回 (None, False)（W10-092 遷移天然保留）
      - upstream 新增（base 無、local 無）：直接採 upstream
      - 三方齊備：用 git merge-file 做標準三方合併，衝突回 (..., True)
      - 純二進位差異無法 merge 時退化為衝突標記

    參數:
        base_content: base 版本內容（None 表 base 無此檔）
        local_path: 本地檔案路徑（None 表本地無此檔）
        upstream_path: 上游檔案路徑（None 表上游刪除此檔）
        local_deleted: 本地是否已主動刪除此檔

    傳回:
        tuple[bytes | None, bool]: (合併後內容或 None, 是否衝突)
    """
    # 本地刪除優先：不論上游如何，保留本地刪除
    if local_deleted:
        return None, False

    upstream_content = (
        upstream_path.read_bytes() if upstream_path and upstream_path.exists() else None
    )
    local_content = (
        local_path.read_bytes() if local_path and local_path.exists() else None
    )

    # upstream 刪除此檔
    if upstream_content is None:
        # 上游刪除：若本地未修改（local == base）則跟著刪，否則保留本地
        if local_content is None or local_content == base_content:
            return None, False
        return local_content, False

    # 本地無此檔（upstream 新增）→ 直接採 upstream
    if local_content is None:
        return upstream_content, False

    # 本地與 upstream 內容相同 → 無需合併
    if local_content == upstream_content:
        return upstream_content, False

    # base 無此檔但 local/upstream 皆有且不同 → add/add 衝突
    if base_content is None:
        return upstream_content, True

    # local 未改（== base）→ 採 upstream
    if local_content == base_content:
        return upstream_content, False

    # upstream 未改（== base）→ 採 local（理論上不會進到此函式，防禦性處理）
    if upstream_content == base_content:
        return local_content, False

    # 三方皆不同 → git merge-file 標準三方合併
    return _git_merge_three_files(base_content, local_content, upstream_content)


def _git_merge_three_files(
    base_content: bytes, local_content: bytes, upstream_content: bytes
) -> tuple[bytes | None, bool]:
    """用 git merge-file 對三份內容做三方合併，回 (merged, conflict)。"""
    with tempfile.TemporaryDirectory(prefix="claude-merge-") as td:
        tdir = Path(td)
        local_f = tdir / "local"
        base_f = tdir / "base"
        upstream_f = tdir / "upstream"
        local_f.write_bytes(local_content)
        base_f.write_bytes(base_content)
        upstream_f.write_bytes(upstream_content)
        # git merge-file <current> <base> <other>；結果寫回 <current>
        result = subprocess.run(
            ["git", "merge-file", "-p", str(local_f), str(base_f), str(upstream_f)],
            capture_output=True,
        )
        # returncode: 0 = 乾淨合併；>0 = 衝突數；<0 = 錯誤
        merged = result.stdout
        conflict = result.returncode != 0
        return merged, conflict


def should_use_full_overlay(claude_dir: Path, base_reachable: bool) -> bool:
    """判定是否走全量 overlay fallback（H4 向後相容）。

    當無 base SHA 或 base 不可達時，無法做三方合併 → 走舊版全量 overlay 路徑。

    參數:
        claude_dir: .claude 目錄路徑
        base_reachable: base commit 是否在上游 clone 可達

    傳回:
        bool: True 表應走全量 overlay；False 表可走三方合併
    """
    base_sha = read_base_sha(claude_dir)
    if base_sha is None:
        return True
    return not base_reachable


def _files_differ(src: Path, dst: Path) -> bool:
    """比對兩個檔案是否不同。大檔案用 size 快速判斷，小檔案做完整內容比對。"""
    # 拒絕比對符號連結，視為不同以確保安全
    if src.is_symlink() or dst.is_symlink():
        return True
    src_stat = src.stat()
    dst_stat = dst.stat()
    # 大小不同一定不同
    if src_stat.st_size != dst_stat.st_size:
        return True
    # 大檔案：大小相同就視為相同（避免全量比對）
    if src_stat.st_size > _LARGE_FILE_THRESHOLD:
        return False
    # 小檔案：完整內容比對
    return not filecmp.cmp(str(src), str(dst), shallow=False)


def sync_directory(
    src: Path,
    dst: Path,
    preserve: set[str] | None = None,
    prefix: Path = Path(),
) -> int:
    """增量同步來源目錄到目標目錄。

    遞迴地同步檔案和目錄，跳過排除清單中的項目和符號連結。
    對於已存在的目錄進行增量同步，對於新目錄則整體複製。
    在 preserve 清單中的檔案不會被覆蓋。

    參數:
        src: 來源目錄路徑
        dst: 目標目錄路徑
        preserve: 需要保留的本地特化檔案相對路徑集合
        prefix: 目前遞迴的相對路徑前綴

    傳回:
        int: 更新或複製的檔案總數

    說明:
        - 跳過 SKIP_DURING_SYNC 清單中的目錄和檔案
        - 跳過所有符號連結
        - 跳過 preserve 清單中的本地特化檔案
        - 保留檔案的修改時間戳（使用 shutil.copy2）
    """
    if preserve is None:
        preserve = set()
    count = 0
    for item in src.iterdir():
        if item.name in SKIP_DURING_SYNC:
            continue
        if item.is_symlink():
            continue

        rel = prefix / item.name
        dest_item = dst / item.name
        if item.is_dir():
            if dest_item.exists():
                count += sync_directory(item, dest_item, preserve, rel)
            else:
                shutil.copytree(item, dest_item, symlinks=False,
                                ignore=shutil.ignore_patterns(*SKIP_DURING_SYNC))
                count += sum(1 for f in dest_item.rglob("*") if f.is_file())
        else:
            rel_str = str(rel).replace("\\", "/")
            if rel_str in preserve:
                if not dest_item.exists():
                    print_color(f"   本地特化檔案不存在（可能已刪除）: {rel_str}", "yellow")
                else:
                    try:
                        if _files_differ(item, dest_item):
                            print_color(f"   本地特化檔案有遠端更新可用: {rel_str}", "yellow")
                        else:
                            print_color(f"   保留本地特化檔案: {rel_str}", "green")
                    except (FileNotFoundError, OSError):
                        print_color(f"   警告: 無法比對檔案 {rel_str}", "yellow")
                continue
            dest_item.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, dest_item)
            count += 1
    return count


def restore_executable_bits(claude_dir: Path) -> int:
    """對所有 hooks/ 目錄下的 .py 檔案強制加入 executable bit。

    背景：上游 tarrragon/claude.git 的 mode 已損壞（Python 檔案多為 100644），
    shutil.copy2 雖保留來源 mode，但來源本身就錯。Hook 系統（Stop、SessionStart 等）
    需要檔案有 +x 才能由 shell 直接執行，否則 Permission denied。

    本函式作 convention-based safety net：遞迴掃描 claude_dir 下所有名為 hooks/ 的
    目錄（頂層 .claude/hooks/ 與 W10-092 遷移後的 skills/<name>/hooks/，缺陷 G），
    對其下所有 .py 無條件加 +x（u/g/o 均加），獨立於上游 mode 狀態。

    不處理 .claude/scripts/ 下檔案，因該目錄有 644/755 混合（如 sync 腳本本身），
    精細處理屬另一範疇。

    參數:
        claude_dir: .claude 目錄的絕對路徑

    傳回:
        int: 實際變更 mode 的檔案數（已是可執行者不計）
    """
    count = 0
    targets: set[Path] = set()
    for target_dir in iter_executable_hook_dirs(claude_dir):
        for py_file in target_dir.rglob("*.py"):
            if py_file.is_file():
                targets.add(py_file)
    # W9-007：settings.json 註冊的 skill 根目錄執行檔（非 hooks/ 路徑）
    targets |= collect_registered_skill_scripts(claude_dir)
    for py_file in targets:
        mode = py_file.stat().st_mode
        new_mode = mode | 0o111
        if new_mode != mode:
            py_file.chmod(new_mode)
            count += 1
    return count


def collect_remote_files(src: Path, prefix: Path = Path()) -> set[Path]:
    """遞迴蒐集遠端 repo 中所有檔案的相對路徑。

    跳過排除清單中的項目和符號連結，返回所有檔案的相對路徑集合，
    用於後續的過時檔案清理工作。

    參數:
        src: 來源目錄路徑
        prefix: 相對於起始目錄的路徑前綴，用於遞迴調用

    傳回:
        set[Path]: 所有檔案的相對路徑集合
    """
    files: set[Path] = set()
    for item in src.iterdir():
        if item.name in SKIP_DURING_SYNC:
            continue
        if item.is_symlink():
            continue
        rel = prefix / item.name
        if item.is_dir():
            files.update(collect_remote_files(item, rel))
        else:
            files.add(rel)
    return files


def _is_git_tracked(rel_under_root: str, project_root: Path) -> bool:
    """判斷相對 project_root 的路徑是否受 git 追蹤。

    用 git ls-files --error-unmatch <path>：受追蹤回 returncode 0。
    非 git 環境或路徑未追蹤回 False，呼叫端視為可刪除的 runtime/stale 檔。

    參數:
        rel_under_root: 相對 git repo root 的路徑（如 .claude/error-patterns/PC-x.md）
        project_root: git repo root 路徑

    傳回:
        bool: 受 git 追蹤為 True
    """
    result = run_git(
        ["ls-files", "--error-unmatch", rel_under_root], cwd=str(project_root)
    )
    return result.returncode == 0


def cleanup_stale_files(
    claude_dir: Path,
    remote_files: set[Path],
    preserve: set[str] | None = None,
    project_root: Path | None = None,
) -> tuple[list[str], list[str]]:
    """移除本地有但遠端 repo 中不存在的過時檔案（git 追蹤感知）。

    git 追蹤感知：受 git 追蹤的本地獨有檔（= 本地累積、上游 repo 無）
    不靜默刪除，改移至 .sync-conflicts/ 並計入 preserved_as_conflict；僅非追蹤檔
    （runtime / 真 stale）維持原 unlink。preserve 清單中的檔案不刪也不移。

    背景：full overlay fallback 下本函式曾誤刪上游 repo 不存在但本地累積的防護檔
    （未列於 sync-preserve.yaml）。git 追蹤狀態是「本地有意保留內容」的可靠訊號，
    比手動維護的 preserve 清單更不易遺漏。

    參數:
        claude_dir: .claude 目錄路徑
        remote_files: 遠端 repo 檔案相對路徑集合
        preserve: 本地特化檔案相對路徑集合（不動）
        project_root: git repo root，預設 claude_dir.parent（git ls-files 判定基準）

    傳回:
        tuple[list[str], list[str]]:
          (removed, preserved_as_conflict)
          removed = 真正刪除（非 git 追蹤）的相對路徑清單
          preserved_as_conflict = git 追蹤而移至 .sync-conflicts 的相對路徑清單
    """
    if preserve is None:
        preserve = set()
    if project_root is None:
        project_root = claude_dir.parent
    removed: list[str] = []
    preserved_as_conflict: list[str] = []
    conflicts_dir: Path | None = None

    def _walk(directory: Path, prefix: Path = Path()) -> None:
        """遞迴走訪目錄，處理不存在於遠端 repo 中的過時檔案。

        跳過排除清單中的項目、符號連結和 preserve 清單中的檔案。
        受 git 追蹤的本地獨有檔移至 .sync-conflicts/（不刪）；其餘 unlink。
        對於空目錄在清理後自動刪除。
        """
        nonlocal conflicts_dir
        if not directory.exists():
            return
        for item in sorted(directory.iterdir()):
            if item.name in SKIP_DURING_SYNC:
                continue
            if item.is_symlink():
                continue
            rel = prefix / item.name
            if item.is_dir():
                _walk(item, rel)
                # Remove empty directories after cleaning files
                if item.exists() and not any(item.iterdir()):
                    item.rmdir()
                    removed.append(f"{rel}/ (empty dir)")
            elif rel not in remote_files:
                rel_str = str(rel).replace("\\", "/")
                if rel_str in preserve:
                    print_color(f"   保留本地特化檔案: {rel_str}", "green")
                    continue
                if _is_git_tracked(f".claude/{rel_str}", project_root):
                    # 本地累積內容：移至 .sync-conflicts，不靜默刪除
                    if conflicts_dir is None:
                        conflicts_dir = _ensure_conflicts_dir(claude_dir)
                    dest = conflicts_dir / rel_str.replace("/", "__")
                    shutil.move(str(item), str(dest))
                    preserved_as_conflict.append(rel_str)
                    print_color(
                        f"   本地獨有 git 追蹤檔不刪，移至 {SYNC_CONFLICTS_DIR}/: {rel_str}",
                        "yellow",
                    )
                else:
                    item.unlink()
                    removed.append(str(rel))

    _walk(claude_dir)
    return removed, preserved_as_conflict


def preview_overlay_changes(
    temp_dir: Path,
    claude_dir: Path,
    remote_files: set[Path],
    preserve: set[str] | None = None,
    project_root: Path | None = None,
) -> tuple[list[str], list[tuple[str, bool]]]:
    """full overlay 前的 dry-run 預覽。

    在實際 sync_directory + cleanup_stale_files 前，收集本次 overlay 的影響清單，
    讓使用者在覆蓋發生前看見將被覆蓋與將被刪除（含 git 追蹤標記）的檔案。

    參數:
        temp_dir: 上游 repo clone 路徑
        claude_dir: .claude 目錄路徑
        remote_files: 遠端 repo 檔案相對路徑集合
        preserve: 本地特化檔案相對路徑集合（不計入預覽）
        project_root: git repo root，預設 claude_dir.parent

    傳回:
        tuple[list[str], list[tuple[str, bool]]]:
          (will_overwrite, will_delete)
          will_overwrite = 本地存在且與遠端內容不同的相對路徑（會被覆蓋）
          will_delete = [(rel, is_tracked)] 本地有遠端無的檔；is_tracked True 者
                        將轉存 .sync-conflicts（非真刪），False 者真刪
    """
    if preserve is None:
        preserve = set()
    if project_root is None:
        project_root = claude_dir.parent
    will_overwrite: list[str] = []
    will_delete: list[tuple[str, bool]] = []

    def _walk(directory: Path, prefix: Path = Path()) -> None:
        if not directory.exists():
            return
        for item in sorted(directory.iterdir()):
            if item.name in SKIP_DURING_SYNC or item.is_symlink():
                continue
            rel = prefix / item.name
            if item.is_dir():
                _walk(item, rel)
                continue
            rel_str = str(rel).replace("\\", "/")
            if rel_str in preserve:
                continue
            if rel not in remote_files:
                will_delete.append(
                    (rel_str, _is_git_tracked(f".claude/{rel_str}", project_root))
                )
            else:
                upstream_item = temp_dir / rel
                if upstream_item.exists() and _files_differ(upstream_item, item):
                    will_overwrite.append(rel_str)

    _walk(claude_dir)
    return will_overwrite, will_delete


def _ensure_conflicts_dir(claude_dir: Path) -> Path:
    """建立 .sync-conflicts/ 目錄與 .gitignore（M3：local-only，不推送）。

    .gitignore 內容 `*`：整個衝突目錄不納入版控也不被 sync 推送
    （目錄名 .sync-conflicts 非 LOCAL_ONLY 段，但內容皆為衝突暫存，靠 .gitignore 隔離）。

    傳回:
        Path: .sync-conflicts/ 目錄路徑
    """
    conflicts_dir = claude_dir / SYNC_CONFLICTS_DIR
    conflicts_dir.mkdir(parents=True, exist_ok=True)
    gitignore = conflicts_dir / ".gitignore"
    if not gitignore.exists():
        gitignore.write_text("*\n", encoding="utf-8")
    return conflicts_dir


def _rel_under_claude(repo_rel_path: str) -> str | None:
    """將上游 repo root 相對路徑轉為 .claude/ 內相對路徑。

    上游獨立 repo 的 root 直接對應本地 .claude/（如 repo 的 "rules/x.md" →
    本地 ".claude/rules/x.md"）。repo root 的 REMOTE_ONLY 項（project-templates、
    .git）不屬 .claude/ 同步範疇，由 _update_project_templates 另行處理，回 None 跳過。
    """
    top_segment = repo_rel_path.split("/", 1)[0]
    if top_segment in REMOTE_ONLY:
        return None
    return repo_rel_path


# ============================================================================
# PC 編號撞號偵測與自動重編號（瑕疵 D / D3 import-time）
#
# 背景：上游框架 repo 與本專案各自獨立累積 error-pattern PC 編號。pull 把上游
# PC 檔帶入時，同一 PC 號可能已被本地不同 pattern 佔用（如上游 PC-165 auq-dispatch
# vs 本地 PC-165 false-positive-fix-chain）。本 session 手動以 PC-171 重編號處置，
# 此處將該流程自動化為 import-time 強制層（W1-014 瑕疵 D）。
# ============================================================================

import re as _re  # noqa: E402

# 刻意只認 flat 凍結核心格式（PC-NNN），不拓寬至前綴格式（1.0.0-W1-019.2 決策）。
# 本子系統是 flat 整數撞號解析（int(group(1)) + numbers: dict[int,str] +
# _next_available_pc_number 整數遞增）。Model 1 前綴格式（PC-V1-001）天生不參與
# flat 撞號——各專案在自己前綴空間累加，零協調防碰撞。現值 regex 對前綴檔匹配失敗
# 回 None（'V' 非 \d），正是正確排除行為；拓寬反而會把前綴檔誤拉進整數撞號路徑
# （int("V1-") → ValueError / group 錯位）。識別任意 ID 字串的用途請改用
# lib/pattern_id.py 的 PATTERN_ID_RE（error_pattern_attribution 已採用）。
_PC_FILENAME_RE = _re.compile(r"^PC-(\d+)-(.+)\.md$")
# 溯源註記內辨識上游號（與重編號寫入的註記字面對稱）
_PROVENANCE_UPSTREAM_RE = _re.compile(r"編號溯源.*?編號為\s*PC-(\d+)", _re.DOTALL)


def parse_pc_filename(repo_rel: str) -> tuple[int, str] | None:
    """解析 error-patterns 下 PC 檔的 (編號, slug)。

    僅匹配 error-patterns/ 範圍內、檔名形如 PC-<NNN>-<slug>.md 者。
    非 PC（README、IMP/TEST/ARCH 等其他前綴）回 None。
    """
    parts = repo_rel.split("/")
    if len(parts) < 2 or parts[0] != "error-patterns":
        return None
    m = _PC_FILENAME_RE.match(parts[-1])
    if not m:
        return None
    return int(m.group(1)), m.group(2)


def build_local_pc_index(claude_dir: Path) -> dict:
    """掃描本地 error-patterns/ 建立 PC 索引。

    回傳:
        {
          "numbers": {編號: slug, ...},           # 本地已佔用的 PC 號 → slug
          "provenance": {(上游號, slug): 本地號},  # 已重編過的溯源映射（去重用）
        }

    provenance 由本地檔內的「編號溯源」註記解析：若某本地 PC 檔記載「上游編號為
    PC-X」，即建立 (X, 該檔 slug) → 該檔本地號 的映射，供 dedup 辨識上游帶回的
    同一 pattern。
    """
    numbers: dict[int, str] = {}
    provenance: dict[tuple[int, str], int] = {}
    ep_root = claude_dir / "error-patterns"
    if not ep_root.is_dir():
        return {"numbers": numbers, "provenance": provenance}

    for path in ep_root.rglob("PC-*.md"):
        m = _PC_FILENAME_RE.match(path.name)
        if not m:
            continue
        local_num = int(m.group(1))
        slug = m.group(2)
        numbers[local_num] = slug
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        prov = _PROVENANCE_UPSTREAM_RE.search(text)
        if prov:
            upstream_num = int(prov.group(1))
            provenance[(upstream_num, slug)] = local_num
    return {"numbers": numbers, "provenance": provenance}


def _next_available_pc_number(numbers: dict[int, str], start: int) -> int:
    """從 start 起找第一個未被本地佔用的 PC 號。"""
    candidate = max(numbers, default=start - 1) + 1
    candidate = max(candidate, start + 1)
    while candidate in numbers:
        candidate += 1
    return candidate


def _build_provenance_note(upstream_num: int, local_num: int) -> str:
    """產生與本 session 手動格式對稱的溯源註記行。"""
    return (
        f"> **編號溯源**：本 pattern 在上游框架 repo（tarrragon/claude.git）"
        f"編號為 PC-{upstream_num}。因本專案 PC-{upstream_num} 已被既有 pattern 佔用，"
        f"於本專案重新編號為 PC-{local_num}。下次 sync-pull 仍會帶回上游 "
        f"PC-{upstream_num}，屆時應辨識為同一 pattern 並去重。\n"
    )


def resolve_pc_collision(
    repo_rel: str,
    upstream_content: bytes,
    local_index: dict,
) -> tuple[str, bytes, str]:
    """偵測上游 PC 檔是否與本地撞號並決定處置。

    回傳 (new_repo_rel, new_content, action)，action 枚舉：
      - "none"        無衝突（或同號同 slug 屬同一檔），原樣交三方合併
      - "dedup_skip"  上游帶回的是先前已重編過的同一 pattern，跳過不匯入
      - "renumber"    撞號（同號不同 slug），重編為本地可用號 + 注入溯源註記

    僅處理 error-patterns 下 PC 檔；其餘一律回 "none"。
    """
    parsed = parse_pc_filename(repo_rel)
    if parsed is None:
        return repo_rel, upstream_content, "none"

    upstream_num, slug = parsed
    numbers: dict[int, str] = local_index.get("numbers", {})
    provenance: dict[tuple[int, str], int] = local_index.get("provenance", {})

    # dedup：上游號 + slug 已在本地以重編號收錄 → 同一 pattern，跳過
    if (upstream_num, slug) in provenance:
        return repo_rel, upstream_content, "dedup_skip"

    existing_slug = numbers.get(upstream_num)
    # 無人佔用該號 → 無衝突
    if existing_slug is None:
        return repo_rel, upstream_content, "none"
    # 同號同 slug → 本就是同一檔，正常三方合併
    if existing_slug == slug:
        return repo_rel, upstream_content, "none"

    # 撞號（同號不同 slug）：重編號
    new_num = _next_available_pc_number(numbers, upstream_num)
    prefix = repo_rel.rsplit("/", 1)[0]
    new_repo_rel = f"{prefix}/PC-{new_num}-{slug}.md"
    new_content = _renumber_pc_content(
        upstream_content, upstream_num, new_num
    )
    return new_repo_rel, new_content, "renumber"


def _renumber_pc_content(content: bytes, upstream_num: int, local_num: int) -> bytes:
    """更新 PC 檔內容：frontmatter id 改為新號 + 插入溯源註記。

    溯源註記插在 frontmatter 結束（第二個 `---`）後第一個空行處；若無 frontmatter
    則插在檔首。frontmatter / H1 內的 PC-<upstream> 字面不全域替換，避免破壞其他
    對該編號的合法引用。
    """
    text = content.decode("utf-8")
    note = _build_provenance_note(upstream_num, local_num)

    lines = text.split("\n")
    # 更新 frontmatter id 欄位
    in_fm = False
    fm_end_idx: int | None = None
    for i, line in enumerate(lines):
        if i == 0 and line.strip() == "---":
            in_fm = True
            continue
        if in_fm and line.strip() == "---":
            fm_end_idx = i
            break
        if in_fm and line.startswith("id:"):
            lines[i] = _re.sub(
                rf"PC-{upstream_num}\b", f"PC-{local_num}", line
            )

    if fm_end_idx is not None:
        insert_at = fm_end_idx + 1
        # 跳過 frontmatter 後緊接的空行
        while insert_at < len(lines) and lines[insert_at].strip() == "":
            insert_at += 1
        lines.insert(insert_at, "")
        lines.insert(insert_at + 1, note.rstrip("\n"))
        lines.insert(insert_at + 2, "")
    else:
        lines.insert(0, note.rstrip("\n"))
        lines.insert(1, "")

    return "\n".join(lines).encode("utf-8")


def _apply_renumbered_pc(
    claude_dir: Path,
    new_repo_rel: str,
    new_content: bytes,
    local_pc_index: dict,
    rollback_log: list,
) -> int:
    """原子寫入重編號後的 PC 檔，並更新索引避免後續同號再撞。

    重編後的新號視為已佔用，且其溯源映射納入 provenance，使同批 delta 內後續
    若再帶回同 pattern 也能被 dedup。回傳寫入檔數（恆為 1）。
    """
    parsed = parse_pc_filename(new_repo_rel)
    local_file = claude_dir / new_repo_rel
    _atomic_write(local_file, new_content, rollback_log)
    if parsed is not None:
        new_num, slug = parsed
        local_pc_index.setdefault("numbers", {})[new_num] = slug
        prov = _PROVENANCE_UPSTREAM_RE.search(new_content.decode("utf-8"))
        if prov:
            upstream_num = int(prov.group(1))
            local_pc_index.setdefault("provenance", {})[(upstream_num, slug)] = new_num
    return 1


def apply_upstream_delta(
    project_root: Path,
    temp_dir: Path,
    base_sha: str,
    preserve: set[str] | None = None,
) -> tuple[int, list[str]]:
    """以三方合併方式套用上游 delta，原子置換只搬 delta 涉及的檔案（H2）。

    流程：
      1. compute_upstream_delta 取 .claude/ 範圍的 A/M/D 變更
      2. 過濾 should_exclude（LOCAL_ONLY / 憑證）與 preserve 清單（M4）
      3. 逐檔三方合併（base=上游 base 版本 / local=本地 / upstream=上游 HEAD 版本）
      4. 衝突檔寫入 .sync-conflicts/ 並保留本地原檔（M3）
      5. 原子套用：先寫 staging 檔再 os.replace 置換（rename 級，跨 fs fallback copy）
      6. 任一步失敗自動回滾已置換的檔案

    參數:
        project_root: 專案根目錄
        temp_dir: 上游 repo clone 路徑
        base_sha: 上游 base commit SHA
        preserve: sync-preserve.yaml 的 preserve 清單（相對 .claude/）

    傳回:
        tuple[int, list[str]]: (套用成功檔數, 衝突檔清單)
    """
    if preserve is None:
        preserve = set()
    claude_dir = project_root / ".claude"
    # 上游獨立 repo 的 root 直接對應本地 .claude/（repo 無 .claude/ 前綴）
    delta = compute_upstream_delta(temp_dir, base_sha)

    applied = 0
    conflicts: list[str] = []
    # 回滾記錄：(目標路徑, 備份路徑 or None 表原本不存在)
    rollback_log: list[tuple[Path, Path | None]] = []
    # PC 撞號偵測索引（瑕疵 D）：合併前一次性掃描本地 error-patterns。
    local_pc_index = build_local_pc_index(claude_dir)

    try:
        for repo_rel, status in sorted(delta.items()):
            # 瑕疵 D：error-patterns PC 檔在套用前先偵測撞號 / dedup / 重編號。
            # 僅對 A/M（上游新增或修改）的 PC 檔生效；D（上游刪除）不改名。
            if status in ("A", "M"):
                pc_upstream_path = temp_dir / repo_rel
                pc_content = (
                    pc_upstream_path.read_bytes()
                    if pc_upstream_path.exists() else None
                )
                if pc_content is not None:
                    new_rel, new_content, pc_action = resolve_pc_collision(
                        repo_rel, pc_content, local_pc_index
                    )
                    if pc_action == "dedup_skip":
                        print_color(
                            f"   PC 去重（上游帶回先前已重編 pattern）: {repo_rel}",
                            "green",
                        )
                        continue
                    if pc_action == "renumber":
                        applied += _apply_renumbered_pc(
                            claude_dir, new_rel, new_content,
                            local_pc_index, rollback_log,
                        )
                        print_color(
                            f"   PC 撞號自動重編: {repo_rel} → {new_rel}",
                            "yellow",
                        )
                        continue

            claude_rel = _rel_under_claude(repo_rel)
            if claude_rel is None:
                continue  # 非 .claude/ 檔，跳過
            rel_path = Path(claude_rel)
            # M4：preserve 與 LOCAL_ONLY / 憑證在合併前先過濾，完全跳過判定
            if should_exclude(rel_path):
                continue
            if claude_rel in preserve:
                print_color(f"   保留本地特化檔案（跳過 delta）: {claude_rel}", "green")
                continue

            local_file = claude_dir / rel_path
            local_exists = local_file.exists()
            # 本地刪除：上游有但本地無，且 base 有（曾存在後被本地刪除）
            base_content = _read_upstream_blob(temp_dir, base_sha, repo_rel)
            local_deleted = (not local_exists) and (base_content is not None) and (status != "A")

            upstream_file = temp_dir / repo_rel  # 上游 repo root 直接對應 .claude/
            upstream_path = upstream_file if status in ("A", "M") else None

            merged, conflict = three_way_merge_file(
                base_content=base_content,
                local_path=local_file if local_exists else None,
                upstream_path=upstream_path,
                local_deleted=local_deleted,
            )

            if conflict:
                # M3：衝突檔寫 .sync-conflicts/，保留本地原檔不動
                conflicts_dir = _ensure_conflicts_dir(claude_dir)
                conflict_target = conflicts_dir / rel_path
                conflict_target.parent.mkdir(parents=True, exist_ok=True)
                conflict_target.write_bytes(merged if merged is not None else b"")
                conflicts.append(claude_rel)
                print_color(f"   衝突: {claude_rel}（已存 {SYNC_CONFLICTS_DIR}/，本地原檔保留）", "red")
                continue

            if merged is None:
                # 本地刪除優先 or 雙方刪除 → 確保本地不存在
                if local_exists:
                    _atomic_remove(local_file, rollback_log)
                    applied += 1
                continue

            # 原子套用：staging → os.replace
            _atomic_write(local_file, merged, rollback_log)
            applied += 1

    except Exception as exc:  # noqa: BLE001
        print_color(f"   套用 delta 失敗，回滾中: {exc}", "red")
        _rollback(rollback_log)
        # 同步寫 stderr 確保可見（quality-baseline 規則 4）
        sys.stderr.write(f"apply_upstream_delta 失敗已回滾: {exc}\n")
        raise

    return applied, conflicts


def _atomic_write(target: Path, content: bytes, rollback_log: list) -> None:
    """原子寫入：先寫 .tmp 同目錄檔再 os.replace，跨 fs 失敗時 fallback copy。

    置換前先把原檔備份到 rollback_log，供失敗時回滾。
    """
    target.parent.mkdir(parents=True, exist_ok=True)
    backup: Path | None = None
    if target.exists():
        backup = Path(tempfile.mktemp(prefix="claude-rb-"))
        shutil.copy2(target, backup)
    rollback_log.append((target, backup))

    tmp = target.with_suffix(target.suffix + ".sync-tmp")
    tmp.write_bytes(content)
    try:
        os.replace(tmp, target)
    except OSError:
        # 跨檔案系統 fallback：copy + unlink tmp
        shutil.copy2(tmp, target)
        tmp.unlink(missing_ok=True)


def _atomic_remove(target: Path, rollback_log: list) -> None:
    """移除檔案並記錄回滾資訊（保留本地刪除時用）。"""
    backup = Path(tempfile.mktemp(prefix="claude-rb-"))
    shutil.copy2(target, backup)
    rollback_log.append((target, backup))
    target.unlink()


def _rollback(rollback_log: list) -> None:
    """回滾所有已套用的變更（反序還原）。"""
    for target, backup in reversed(rollback_log):
        try:
            if backup is None:
                # 原本不存在 → 刪除新寫入的檔
                if target.exists():
                    target.unlink()
            else:
                shutil.copy2(backup, target)
        except OSError as exc:
            sys.stderr.write(f"回滾 {target} 失敗: {exc}\n")
            print_color(f"   警告: 回滾 {target} 失敗: {exc}", "red")


def detect_changed_packages(project_root: Path) -> None:
    """偵測 .claude/skills/*/pyproject.toml 的變更檔案。

    使用 git diff --name-only 避免 glob pathspec 問題，改由 Python 端過濾檔案。

    使用三層 fallback 策略：
    1. origin/HEAD...HEAD（標準情況）
    2. HEAD~1...HEAD（無 origin/HEAD 時）
    3. HEAD（最後手段）

    不會中止主流程，僅記錄警告。
    """
    changed_pyproject_files = []

    # Try git diff --name-only with fallback strategy
    # 使用 --name-only 取得變更檔案列表，避免 glob 被 shell 展開
    git_commands = [
        ["diff", "--name-only", "origin/HEAD...HEAD"],
        ["diff", "--name-only", "HEAD~1...HEAD"],
        ["diff", "--name-only", "HEAD"],
    ]

    for git_args in git_commands:
        result = run_git(git_args, cwd=str(project_root))
        if result.returncode == 0:
            # 解析檔案列表並過濾 .claude/skills/*/pyproject.toml
            for line in result.stdout.splitlines():
                line = line.strip()
                # 篩選符合模式的檔案
                if ".claude/skills/" in line and "pyproject.toml" in line:
                    changed_pyproject_files.append(line)
            break  # Found a working git command
    else:
        # All git commands failed
        print_color("   提示: 無法執行 git diff，跳過套件版本檢查", "yellow")
        return

    if not changed_pyproject_files:
        print_color("   無套件版本變更", "green")
        return

    print_color(f"   偵測到 {len(changed_pyproject_files)} 個套件版本變更", "yellow")

    # For now, we only log the detection
    # The actual reinstallation will happen when the hook runs
    for file_path in changed_pyproject_files[:MAX_CHANGED_FILES_DISPLAY]:
        print_color(f"     - {file_path}")
    if len(changed_pyproject_files) > MAX_CHANGED_FILES_DISPLAY:
        print_color(f"     ... 及 {len(changed_pyproject_files) - MAX_CHANGED_FILES_DISPLAY} 個檔案")

    print_color("   套件將在下次 SessionStart 自動重新安裝", "green")


def backup_claude_dir(claude_dir: Path, dest: Path) -> None:
    """備份 .claude 目錄至 dest，排除工具產物（Q，0.19.1-W1-021）。

    使用 shutil.ignore_patterns 排除 __pycache__/.pytest_cache/.venv，
    避免備份 bloat / 變慢 / 遇 broken symlink 拋例外。symlinks=False
    沿用主同步行為（複製 symlink 指向的內容而非連結本身）。

    參數:
        claude_dir: 來源 .claude 目錄
        dest: 備份目標路徑（例如 backup_dir / ".claude"）
    """
    shutil.copytree(
        claude_dir,
        dest,
        symlinks=False,
        ignore=shutil.ignore_patterns(*BACKUP_IGNORE_PATTERNS),
    )


def _sync_with_backup(project_root: Path, temp_dir: Path) -> Path:
    """執行備份和同步操作。

    備份當前配置，然後同步遠端更新至本地。
    返回備份目錄路徑。

    參數:
        project_root: 專案根目錄
        temp_dir: 臨時目錄（含遠端 repo 內容）

    傳回:
        backup_dir: 備份目錄路徑
    """
    claude_dir = project_root / ".claude"

    # 備份當前配置
    print_color("備份當前配置...")
    backup_dir = Path(tempfile.mkdtemp(prefix="claude-backup-"))
    backup_claude_dir(claude_dir, backup_dir / ".claude")
    flutter_md = project_root / "FLUTTER.md"
    if flutter_md.exists():
        shutil.copy2(flutter_md, backup_dir / "FLUTTER.md")

    # 載入本地特化檔案清單
    preserve = load_preserve_list(claude_dir)
    if preserve:
        print_color(f"   載入 {len(preserve)} 個本地特化檔案路徑", "green")
        for rel_path in sorted(preserve):
            full_path = claude_dir / rel_path
            if not full_path.exists():
                print_color(f"   警告: preserve 清單中的檔案不存在: {rel_path}", "yellow")

    # 決定同步策略：三方合併（有可達 base）或全量 overlay（向後相容 fallback）
    base_sha = read_base_sha(claude_dir)
    base_reachable = (
        is_base_reachable(temp_dir, base_sha) if base_sha else False
    )
    use_full_overlay = should_use_full_overlay(claude_dir, base_reachable)

    if use_full_overlay:
        # H4 fallback：無 base SHA 或 base 不可達 → 全量 overlay（舊版行為）
        if base_sha and not base_reachable:
            print_color(
                f"   警告: base SHA {base_sha[:12]} 在上游不可達（force-push/GC？），"
                "降級為全量 overlay", "yellow"
            )
        print_color("更新 .claude 資料夾（全量 overlay）...")
        remote_files = collect_remote_files(temp_dir)

        # full overlay 前 dry-run 預覽（讓覆蓋/刪除在發生前可見）
        will_overwrite, will_delete = preview_overlay_changes(
            temp_dir, claude_dir, remote_files, preserve
        )
        if will_overwrite:
            print_color(f"   [dry-run] 將覆蓋 {len(will_overwrite)} 個本地檔案", "yellow")
            for w in will_overwrite[:50]:
                print_color(f"     ~ {w}")
        if will_delete:
            tracked = [r for r, t in will_delete if t]
            untracked = [r for r, t in will_delete if not t]
            print_color(
                f"   [dry-run] {len(will_delete)} 個本地獨有檔："
                f"{len(tracked)} 個 git 追蹤將轉 {SYNC_CONFLICTS_DIR}/、"
                f"{len(untracked)} 個非追蹤將刪除", "yellow"
            )
            for r in tracked[:50]:
                print_color(f"     -> conflict: {r}")
            for r in untracked[:50]:
                print_color(f"     - delete: {r}")

        file_count = sync_directory(temp_dir, claude_dir, preserve)
        print_color(f"   已更新 {file_count} 個檔案", "green")

        removed, preserved_conflicts = cleanup_stale_files(
            claude_dir, remote_files, preserve
        )
        if removed:
            print_color(f"   已清理 {len(removed)} 個過時檔案:", "green")
            for r in removed:
                print_color(f"     - {r}")
        else:
            print_color("   無過時檔案需清理", "green")
        if preserved_conflicts:
            print_color(
                f"   {len(preserved_conflicts)} 個本地獨有 git 追蹤檔已轉存 "
                f"{SYNC_CONFLICTS_DIR}/（非刪除）:", "yellow"
            )
            for p in preserved_conflicts:
                print_color(f"     -> {p}")
    else:
        # A3 三方合併：只搬 base→HEAD delta 涉及的檔案，保留本地刪除與 runtime state
        print_color("更新 .claude 資料夾（三方合併）...")
        applied, conflicts = apply_upstream_delta(
            project_root, temp_dir, base_sha, preserve
        )
        print_color(f"   已套用 {applied} 個 delta 變更", "green")
        if conflicts:
            print_color(
                f"   {len(conflicts)} 個檔案衝突，已存入 {SYNC_CONFLICTS_DIR}/（本地原檔保留）:",
                "red",
            )
            for c in conflicts:
                print_color(f"     - {c}")
        else:
            print_color("   無衝突", "green")

    # 同步成功後寫入新的 base SHA（上游 HEAD）
    head_result = run_git(["rev-parse", "HEAD"], cwd=str(temp_dir))
    if head_result.returncode == 0:
        new_base = head_result.stdout.strip()
        write_base_sha(claude_dir, new_base)
        print_color(f"   已記錄 base SHA: {new_base[:12]}", "green")

    # 還原 hook 檔案的 executable bit（上游 mode 損壞的 safety net）
    restored = restore_executable_bits(claude_dir)
    if restored:
        print_color(f"   已還原 {restored} 個 hook 檔案的執行權限", "green")

    # 偵測套件版本變更
    print_color("檢查套件版本變更...")
    detect_changed_packages(project_root)

    return backup_dir


def _update_project_templates(temp_dir: Path, project_root: Path) -> None:
    """更新專案模板檔案。

    從遠端 repo 的 project-templates 目錄更新 FLUTTER.md。
    不覆蓋根目錄的 CLAUDE.md（保留專案特定配置）。

    參數:
        temp_dir: 臨時目錄（含遠端 repo 內容）
        project_root: 專案根目錄
    """
    templates_dir = temp_dir / "project-templates"
    if templates_dir.is_dir():
        print_color("更新專案模板檔案...")
        src_flutter = templates_dir / "FLUTTER.md"
        if src_flutter.exists():
            shutil.copy2(src_flutter, project_root / "FLUTTER.md")
            print_color("   已更新 FLUTTER.md", "green")
        print_color("   注意: CLAUDE.md 未被覆蓋（保留專案特定配置）")


def _finalize_sync(backup_dir: Path) -> None:
    """完成同步並輸出提示訊息。

    顯示成功訊息、備份位置和初始化提示。

    參數:
        backup_dir: 備份目錄路徑
    """
    print_color("成功拉取 .claude 更新！", "green")
    print_color(f"備份位置: {backup_dir}", "green")
    print_color("請檢查變更並測試 Hook 系統是否正常運作", "green")
    print_color(f"如需還原，執行: cp -r {backup_dir}/.claude .")
    print()
    print_color("=== 新專案初始化提示 ===")
    print_color("如果是新專案，請手動建立 CLAUDE.md:")
    print_color("  1. cp .claude/templates/CLAUDE-template.md CLAUDE.md")
    print_color("  2. 填入專案特定資訊")
    print_color("  3. 驗證所有連結有效")


def _validate_environment(project_root: Path) -> None:
    """驗證專案環境和本地狀態。

    檢查專案根目錄有效性和本地未提交變更。若檢查失敗則終止程式。

    參數:
        project_root: 專案根目錄路徑

    異常:
        呼叫 sys.exit(1)，若檢查失敗則終止程式
    """
    print_color("檢查本地狀態...", "yellow")
    check_uncommitted_changes(project_root)


def _clone_and_backup(project_root: Path) -> tuple[Path, Path]:
    """克隆遠端 repo 並執行備份和同步。

    建立臨時目錄、克隆遠端 repo、執行備份和同步操作。
    返回臨時目錄和備份目錄路徑。

    參數:
        project_root: 專案根目錄路徑

    傳回:
        tuple[Path, Path]: (臨時目錄路徑, 備份目錄路徑)

    異常:
        subprocess.TimeoutExpired: 若克隆超過設定的超時時間
    """
    print_color("從獨立 repo 拉取更新...", "yellow")
    temp_dir = Path(tempfile.mkdtemp())
    clone_repo(temp_dir)
    backup_dir = _sync_with_backup(project_root, temp_dir)
    return temp_dir, backup_dir


BACKUP_DIR_PREFIX = "claude-backup-"
DEFAULT_BACKUP_RETENTION_DAYS = 7


def cleanup_old_backups(retention_days: int = DEFAULT_BACKUP_RETENTION_DAYS,
                        temp_root: Path | None = None) -> int:
    """清理系統 temp 目錄下超過保留期的 claude-backup-* 備份目錄。

    僅刪除符合 claude-backup-* 前綴且 mtime 超過 retention_days 的目錄。
    符號連結、其他前綴目錄、rmtree 失敗皆跳過並 log warning。

    參數:
        retention_days: 保留天數（含），預設 7 天
        temp_root: 掃描根目錄，預設 tempfile.gettempdir()

    傳回:
        已刪除的目錄數量
    """
    if temp_root is None:
        temp_root = Path(tempfile.gettempdir())

    if not temp_root.exists() or not temp_root.is_dir():
        print_color(f"   系統 temp 目錄不存在或無法存取: {temp_root}", "yellow")
        return 0

    cutoff = time.time() - retention_days * 86400
    removed_count = 0

    try:
        entries = list(temp_root.iterdir())
    except (OSError, PermissionError) as exc:
        print_color(f"   無法列出 temp 目錄: {exc}", "yellow")
        return 0

    for entry in entries:
        if not entry.name.startswith(BACKUP_DIR_PREFIX):
            continue
        if entry.is_symlink():
            # 安全起見不刪符號連結
            continue
        if not entry.is_dir():
            continue
        try:
            mtime = entry.stat().st_mtime
        except OSError as exc:
            print_color(f"   無法讀取 mtime: {entry} ({exc})", "yellow")
            continue
        if mtime >= cutoff:
            continue
        try:
            shutil.rmtree(entry)
            removed_count += 1
        except OSError as exc:
            print_color(f"   無法刪除 {entry}: {exc}", "yellow")

    return removed_count


def _complete_sync(temp_dir: Path, project_root: Path, backup_dir: Path) -> None:
    """完成同步：更新專案模板和輸出結果。

    更新專案模板檔案、清理臨時目錄、輸出完成訊息。

    參數:
        temp_dir: 臨時目錄路徑
        project_root: 專案根目錄路徑
        backup_dir: 備份目錄路徑
    """
    _update_project_templates(temp_dir, project_root)
    shutil.rmtree(temp_dir, ignore_errors=True)

    # 清理超期 backup_dir（W3-076）
    print_color("清理超期備份目錄...")
    removed = cleanup_old_backups(DEFAULT_BACKUP_RETENTION_DAYS)
    if removed > 0:
        print_color(f"   已清理 {removed} 個超過 {DEFAULT_BACKUP_RETENTION_DAYS} 天的備份目錄", "green")
    else:
        print_color(f"   無超過 {DEFAULT_BACKUP_RETENTION_DAYS} 天的備份需清理", "green")

    _finalize_sync(backup_dir)


def main() -> None:
    """同步 .claude 配置從獨立 repo。

    主要流程：
    1. 找出專案根目錄
    2. 驗證環境和本地狀態
    3. 克隆遠端 repo 並執行備份同步
    4. 完成同步（更新模板、清理、輸出結果）
    """
    print_color("開始從獨立 repo 拉取 .claude 更新...")

    project_root = find_project_root()
    _validate_environment(project_root)

    try:
        temp_dir, backup_dir = _clone_and_backup(project_root)
        _complete_sync(temp_dir, project_root, backup_dir)
    except subprocess.TimeoutExpired:
        print_color(f"git clone 超時（{GIT_CLONE_TIMEOUT_SECONDS} 秒），請檢查網路連線", "red")
        sys.exit(1)


if __name__ == "__main__":
    main()
