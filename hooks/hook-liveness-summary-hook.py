#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Hook Liveness 彙整

SessionStart 觸發，讀取上一個完成 session 的 liveness 索引
（.claude/hook-logs/_liveness/<session_id>.jsonl），比對 settings.json
註冊表，將「已載入 / 本 session 從未觸發 / 未涵蓋（無 liveness 探針）」
三類清單寫入自身日誌，供事後查證「hook 是否已載入」時直接查詢，不需
依賴對照組（另一持續寫入的 hook）或即時探針推論。

三類清單定義：
- 已載入：涵蓋範圍內（run_hook_safely 覆蓋）且該 session 有 liveness 紀錄
- 本 session 從未觸發：涵蓋範圍內但該 session 無 liveness 紀錄（可能是該
  session 未觸發對應事件，非必然異常）
- 未涵蓋（無 liveness 探針）：hook 檔案未呼叫 run_hook_safely（如 lib
  import 失敗時定義自訂 no-op stub 的降級路徑），本機制無法觀測

不比對「本 session」（觸發本 hook 的新 session）而比對「上一個完成 session」
的理由：SessionStart 是新 session 的第一個事件，此時新 session 自己的
liveness 檔案尚無實質資料（僅本 hook自身剛寫入的一筆），比對上一個完成
session 才能反映有意義的覆蓋率。

第二段機制（2026-08-26 新增，方案 A）：SessionStart 主動崩潰偵測——上述
三類清單的比對前提是「hook 已進入 run_hook_safely」，此前提在 module-level
import 階段崩潰時不成立（run_hook_safely/setup_hook_logging/mark_hook_entry
三者皆未執行，liveness 索引不會有條目，一般的 stderr／日誌雙通道可觀測性
完全不適用）。此段主動對已註冊的 hook 執行一次 smoke test，以 sentinel
liveness 索引是否新增條目作為崩潰判準，偵測到崩潰時透過 SessionStart
additionalContext 主動回報，不依賴 hook 自身的錯誤處理是否啟動。詳見
`_smoke_test_registered_hooks` docstring 的偵測範圍邊界。
"""

import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lib.hook_logging import (
    setup_hook_logging,
    run_hook_safely,
    get_project_root,
    ENV_SESSION_ID,
    ENV_PROJECT_DIR,
    LIVENESS_SUBDIR,
)
from lib.hook_io import read_json_from_stdin, emit_hook_output

HOOK_NAME = "hook-liveness-summary"

# ============================================================================
# SessionStart 主動崩潰偵測（方案 A）用常數
# ============================================================================

# smoke test 使用的固定 sentinel session id，與真實 session 的 liveness
# 索引隔離，避免污染「本 session 從未觸發」等既有三類清單的判斷依據。
SMOKE_TEST_SENTINEL_SESSION_ID = "_smoke_test"

# 單次 SessionStart 內，smoke test 累計耗時上限——settings.json 對本 hook
# 的 SessionStart 註冊 timeout 為 5000ms，此預算需留有餘裕給既有三類清單
# 比對邏輯與鎖檔/快取 I/O，避免超時遭 CC runtime 中止（中止本身又會製造
# 一次無法歸因的「本 hook 未完成」訊號，與本機制要解決的問題同構）。
#
# 實機驗證發現：僅檢查「目前已耗用是否超過預算」不足以界定總耗時上限
# ——若檢查當下剛好在預算邊界之前，仍會啟動下一個候選，其執行時間
# （最壞情況等於 SMOKE_TEST_PER_HOOK_TIMEOUT_SECONDS）會使總耗時溢出
# 預算。迴圈內改用「預留單一候選最壞執行時間」的前瞻式判斷（見迴圈
# 實作），使總耗時上限有界於本預算值附近，不因單一候選的執行時間而
# 溢出到無法預期的長度。
SMOKE_TEST_TIME_BUDGET_SECONDS = 3.0

# 單一 hook 的 smoke test 逾時上限，避免單一掛住的 hook 吃光整個預算。
SMOKE_TEST_PER_HOOK_TIMEOUT_SECONDS = 2.0

# smoke test 鎖檔逾期視為前次進程異常中止的殘留，允許清除後重試一次。
SMOKE_TEST_LOCK_STALE_SECONDS = 60

SMOKE_TEST_CACHE_FILENAME = "_smoke_test_cache.json"
SMOKE_TEST_LOCK_FILENAME = "_smoke_test.lock"

# PEP 723 inline metadata 區塊（與 hook-dependency-isolation-check-hook.py
# 的同名正則獨立維護，非共用匯入——本檔案的 where.files 範圍不含該檔，
# 兩者職責亦不同：對方是靜態一致性檢查，本檔案是動態崩潰偵測）。
_PEP723_BLOCK_RE = re.compile(r"^# /// script\s*\n(.*?)^# ///\s*$", re.MULTILINE | re.DOTALL)
_DEPENDENCIES_RE = re.compile(r"dependencies\s*=\s*\[(.*?)\]", re.DOTALL)

# settings.json command 字串中，路徑之前的 $CLAUDE_PROJECT_DIR 變數尾綴，
# 供切分「呼叫前綴」與「路徑」時去除（與判準協調文件的用法一致）。
_PATH_VAR_SUFFIX_RE = re.compile(r"\$\{?CLAUDE_PROJECT_DIR\}?/?\s*$")


def _iter_registered_hook_commands(settings: dict):
    """走訪 settings.json 的 hooks 區塊，逐一 yield `.claude/hooks/*.py` 的
    command 字串（供 _registered_hook_names / _iter_registered_hook_command_prefixes
    共用，避免重複走訪邏輯）。"""
    hooks_cfg = settings.get("hooks", {})
    for event_entries in hooks_cfg.values():
        if not isinstance(event_entries, list):
            continue
        for group in event_entries:
            if not isinstance(group, dict):
                continue
            for entry in group.get("hooks", []):
                if not isinstance(entry, dict):
                    continue
                command = entry.get("command", "")
                if "/.claude/hooks/" not in command or not command.endswith(".py"):
                    # 僅涵蓋 .claude/hooks/ 直屬檔案；skills/scripts 下的
                    # hook 有各自的 hook_name 慣例，不在本次彙整範圍
                    continue
                yield command


def _registered_hook_names(settings: dict) -> set:
    """從 settings.json 擷取所有 .claude/hooks/*.py 的檔名（去副檔名）"""
    return {Path(command).stem for command in _iter_registered_hook_commands(settings)}


def _iter_registered_hook_command_prefixes(settings: dict):
    """逐一 yield (hook 名稱, 呼叫前綴)。

    前綴指 command 字串中路徑之前的直譯器宣告部分（如 `"uv run
    --quiet"`），空字串代表裸路徑呼叫（無直譯器前綴，由 OS 依可執行位元
    讀 shebang 決定直譯器）。同一路徑可能被多個 hook event 重複登記，
    呼叫端應以集合聚合（見 `_uv_registered_hook_names`）。
    """
    for command in _iter_registered_hook_commands(settings):
        idx = command.find(".claude/hooks/")
        if idx == -1:
            continue
        prefix = _PATH_VAR_SUFFIX_RE.sub("", command[:idx]).strip()
        yield Path(command).stem, prefix


def _resolve_uses_uv(shebang: str, command_prefixes) -> bool:
    """判定 uv 隔離環境是否對此 hook 實際生效。

    決定隔離與否的是「runtime 實際如何呼叫這個檔案」，不是檔案自身
    shebang——settings.json 以 `uv run <path>` 直接呼叫時，uv 讀的是目標
    檔的 PEP 723 metadata 建立隔離環境，與檔案自身 shebang 完全無關；
    反之以 `python3 <path>` 等明確直譯器呼叫時，shebang 同樣完全不被
    讀取，即使宣告 `uv run --script` 也不生效。判準優先序（與
    `hook-dependency-isolation-check-hook.py` 的 `_resolve_uses_uv` 對齊，
    兩檔各自獨立實作、不共用程式碼，經協調後判準邏輯一致）：

    1. 任一登記呼叫前綴以 `uv run` 開頭 -> 隔離確定生效
    2. 任一登記呼叫前綴為空字串（裸路徑） -> 該路徑實際依賴檔案自身
       shebang，回退讀 shebang
    3. 全部登記呼叫前綴皆為其他明確直譯器 -> 隔離確定不生效，shebang
       在此完全不被讀取，不可用來反駁

    無登記資訊時（理論上不會發生，因呼叫端只對已登記路徑呼叫本函式）
    保守回退純 shebang 判定。
    """
    if not command_prefixes:
        return "uv run" in shebang
    if any(prefix.startswith("uv run") for prefix in command_prefixes):
        return True
    if any(prefix == "" for prefix in command_prefixes):
        return "uv run" in shebang
    return False


def _read_first_line(path: Path) -> str:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.readline()
    except OSError:
        return ""


def _uv_registered_hook_names(root: Path, settings: dict) -> set:
    """回傳 uv 隔離環境實際生效的 .claude/hooks/*.py 檔名集合。

    與 `_registered_hook_names` 的差異：後者對呼叫方式無感知，僅抽取
    檔名；本函式進一步套用 `_resolve_uses_uv` 的判準（settings.json 呼叫
    方式優先，僅裸路徑登記才回退讀檔案自身 shebang）。實測確認：判準
    必須以登記方式為主，不可只憑檔案自身 shebang 判斷——`uv run <script>`
    直接解析目標檔案的 PEP 723 inline metadata 建立隔離環境，與 shebang
    內容無關；settings.json 以 `uv run <path>` 登記時，隔離機制實際生效，
    即使該檔案自身 shebang 仍是 `#!/usr/bin/env python3`。純看 registered
    command 字串是否含 `uv run` 子字串（不回退 shebang）在本專案目前無
    裸路徑登記時結果一致，但遇到裸路徑登記時會漏判——具體案例即本機制
    動機事件的 active-dispatch-tracker-hook.py（登記為 uv run，自身
    shebang 卻是 `#!/usr/bin/env python3`，屬「有明確前綴」而非「裸路徑」，
    本函式與純子字串判斷在此案例上結果相同，但裸路徑情境只有走完整
    `_resolve_uses_uv` 判準才不會漏判）。
    """
    prefixes_by_name: "Dict[str, set]" = {}
    for name, prefix in _iter_registered_hook_command_prefixes(settings):
        prefixes_by_name.setdefault(name, set()).add(prefix)

    hooks_dir = root / ".claude" / "hooks"
    result = set()
    for name, prefixes in prefixes_by_name.items():
        shebang = _read_first_line(hooks_dir / "{}.py".format(name))
        if _resolve_uses_uv(shebang, prefixes):
            result.add(name)
    return result


def _covered_by_run_hook_safely(root: Path, hook_names: set) -> set:
    """回傳有呼叫 run_hook_safely 的 hook 名稱子集（有 liveness 探針）"""
    covered = set()
    hooks_dir = root / ".claude" / "hooks"
    for name in hook_names:
        candidate = hooks_dir / "{}.py".format(name)
        if not candidate.exists():
            continue
        try:
            text = candidate.read_text(encoding="utf-8")
        except OSError:
            continue
        if "run_hook_safely" in text:
            covered.add(name)
    return covered


def _most_recent_completed_liveness_file(root: Path, exclude_session_id: str):
    """取得最近修改的 liveness 檔案，排除當前 session 自己的檔案"""
    liveness_dir = root / ".claude" / "hook-logs" / LIVENESS_SUBDIR
    if not liveness_dir.is_dir():
        return None
    candidates = [
        p for p in liveness_dir.glob("*.jsonl")
        if p.stem != exclude_session_id
    ]
    if not candidates:
        return None
    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0]


def _invoked_hook_names(liveness_file: Path) -> set:
    """解析 liveness 索引檔，回傳出現過的 hook 名稱集合"""
    invoked = set()
    try:
        with open(liveness_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                hook = entry.get("hook")
                if hook:
                    invoked.add(hook)
    except OSError:
        pass
    return invoked


# ============================================================================
# SessionStart 主動崩潰偵測（方案 A）
# ============================================================================


def _has_non_empty_pep723_deps(content: str) -> bool:
    """判斷檔案內容是否宣告非空 PEP 723 dependencies（smoke test 候選篩選）。

    僅非空依賴宣告才有「隔離環境缺依賴」的崩潰風險（純 stdlib 用法即使
    走 uv run 隔離也不會因缺套件而崩潰，篩掉可縮小 smoke test 候選集）。
    """
    block_match = _PEP723_BLOCK_RE.search(content)
    if block_match is None:
        return False
    dep_match = _DEPENDENCIES_RE.search(block_match.group(1))
    if dep_match is None:
        return False
    return bool(dep_match.group(1).strip())


def _smoke_test_candidates(root: Path, settings: dict) -> set:
    """回傳需要 smoke test 的 hook 名稱集合：settings.json 以 uv run 登記、
    宣告非空 PEP 723 dependencies、且有呼叫 `run_hook_safely`（見
    `_uv_registered_hook_names`、`_has_non_empty_pep723_deps`、
    `_covered_by_run_hook_safely` 的判準說明）。

    第三項篩選（run_hook_safely 覆蓋）在實機驗證階段補上：崩潰判準是
    「sentinel liveness 索引是否新增條目」，而該條目由 `mark_hook_entry`
    寫入，只有經過 `run_hook_safely` 的 hook 才會呼叫它。仍有少數既有
    hook（如直接 `sys.exit(main())`，不經 `run_hook_safely`）即使正常
    執行成功也不會寫入 liveness 條目——若不排除，這批 hook 會被本機制
    永遠誤判為「崩潰」，即使它們只是輸出正常的警告訊息（實機驗證撈到
    的真實案例：一個回報未提交變更的正常提示訊息被誤判為 crash 摘要）。
    此篩選與既有的「未涵蓋（無 liveness 探針）」分類同一依據，維持
    本檔案內部判準一致。
    """
    hooks_dir = root / ".claude" / "hooks"
    uv_registered = _uv_registered_hook_names(root, settings)
    covered = _covered_by_run_hook_safely(root, uv_registered)
    candidates = set()
    for name in covered:
        path = hooks_dir / "{}.py".format(name)
        try:
            content = path.read_text(encoding="utf-8")
        except OSError:
            continue
        if _has_non_empty_pep723_deps(content):
            candidates.add(name)
    return candidates


def _smoke_test_cache_path(root: Path) -> Path:
    return root / ".claude" / "hook-logs" / LIVENESS_SUBDIR / SMOKE_TEST_CACHE_FILENAME


def _load_smoke_test_cache(root: Path) -> dict:
    path = _smoke_test_cache_path(root)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _save_smoke_test_cache(root: Path, cache: dict, logger) -> None:
    path = _smoke_test_cache_path(root)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError as e:
        logger.warning("smoke test 快取寫入失敗: {}".format(e))


def _smoke_test_lock_path(root: Path) -> Path:
    return root / ".claude" / "hook-logs" / LIVENESS_SUBDIR / SMOKE_TEST_LOCK_FILENAME


def _acquire_smoke_test_lock(root: Path) -> bool:
    """以 O_CREAT|O_EXCL 建立鎖檔，避免多個並行 session 在快取尚未建立時
    同時觸發全量 smoke test（cold start 併發風暴：同時重置並寫入同一份
    sentinel liveness 檔與快取檔，會互相覆寫對方的測試結果）。鎖檔逾時
    視為前次進程異常中止的殘留，清除後重試一次；取得失敗時直接跳過本次
    smoke test（下次 SessionStart 重試），不阻擋 SessionStart 本身其餘
    既有邏輯。
    """
    lock_path = _smoke_test_lock_path(root)
    try:
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.close(fd)
        return True
    except FileExistsError:
        try:
            age = time.time() - lock_path.stat().st_mtime
        except OSError:
            return False
        if age <= SMOKE_TEST_LOCK_STALE_SECONDS:
            return False
        try:
            lock_path.unlink()
        except OSError:
            return False
        return _acquire_smoke_test_lock(root)
    except OSError:
        return False


def _release_smoke_test_lock(root: Path) -> None:
    try:
        _smoke_test_lock_path(root).unlink()
    except OSError:
        pass


def _count_jsonl_lines(path: Path) -> int:
    if not path.exists():
        return 0
    try:
        with open(path, "r", encoding="utf-8") as f:
            return sum(1 for line in f if line.strip())
    except OSError:
        return 0


def _run_single_smoke_test(root: Path, hook_name: str, sentinel_liveness_file: Path):
    """對單一 hook 執行一次 `uv run` 呼叫，回傳 (status: str, summary: str)。

    status 三態（實機驗證發現二態判準不足後改為三態，見下方 timeout 段）：
    - "ok"：本次呼叫使 sentinel liveness 索引新增至少一行，import 成功
      完成。
    - "crashed"：進程確實結束（非逾時）但未新增 liveness 條目，或行程
      啟動本身失敗（OSError）——判準為「本次呼叫是否使 sentinel liveness
      索引新增至少一行」，而非 raw exit code：exit code 混雜正常業務
      阻擋(2)/一般失敗(1)/import 崩潰等多種語意，liveness 條目有無才
      精確對應「import 是否成功完成」（`mark_hook_entry` 在 `main_func`
      執行前無條件寫入，早於任何業務邏輯，已於獨立重現實驗驗證）。
    - "timeout"：逾時（`SMOKE_TEST_PER_HOOK_TIMEOUT_SECONDS` 內未完成）。
      設計動機：專案為多 session 並行環境，理論上 `uv run` 子行程可能因
      真實系統負載（而非 hook 本身有問題）超過逾時；若逕自判定為
      "crashed" 會把系統忙碌誤報成 hook 崩潰。timeout 狀態不快取（見
      `_smoke_test_registered_hooks`），下次 SessionStart 會重新嘗試，
      不會因單次系統忙碌而產生永久性誤報。（附註：實機驗證階段最初
      觀察到的間歇性誤判，事後追查真正根因是 `CLAUDE_PROJECT_DIR`
      環境變數繼承問題——見下方 cwd/env 段落——而非系統負載造成的逾時；
      timeout 狀態仍保留作為系統真正過載時的防呆機制，非本次已知問題
      的實際成因。）

    cwd 固定為 root（主 repo），避免 smoke test 自身受 cwd 影響解析出
    worktree 根目錄（先前診斷記載過「觀測面/作用面落在不同檔案系統位置」
    的現象，成因之一即 cwd 解析差異），確保 smoke test 對自身呼叫的
    一致性；但此設計不代表本機制能偵測「其他 hook 在真實 worktree 派發
    時」的同類錯位——那是本機制已知且未解決的偵測範圍邊界（見
    `_smoke_test_registered_hooks` docstring）。

    同理，`env[ENV_PROJECT_DIR]` 明確釘死為 `root`，不依賴子行程自行解析
    ——`get_project_root()` 的判準優先序（`hook_base.py`）第 2 順位即讀
    `CLAUDE_PROJECT_DIR` 環境變數，優先於 cwd。若不明確覆寫，子行程會
    直接繼承呼叫端（本 hook 自身）的環境變數，當呼叫端本身是被 CC
    runtime 以真實 hook 身份啟動時，該變數已指向真正的專案根目錄——
    子行程即使 `cwd=root` 指向別處（如測試用的 tmp_path），仍會因環境
    變數優先而寫入錯誤位置的 liveness 索引，使本函式的 before/after
    行數比對完全失真（實機驗證撈到的真實案例：健康 hook 因此被誤判為
    崩潰，根因並非系統負載，而是子行程解析到的專案根目錄與呼叫端傳入
    的 `root` 不一致）。明確設定後，子行程的專案根目錄解析結果與呼叫端
    意圖一致，不受呼叫鏈上層環境變數污染影響。
    """
    hook_path = root / ".claude" / "hooks" / "{}.py".format(hook_name)
    before = _count_jsonl_lines(sentinel_liveness_file)

    env = os.environ.copy()
    env[ENV_SESSION_ID] = SMOKE_TEST_SENTINEL_SESSION_ID
    env[ENV_PROJECT_DIR] = str(root)

    try:
        result = subprocess.run(
            ["uv", "run", "--quiet", str(hook_path)],
            input="{}",
            capture_output=True,
            text=True,
            timeout=SMOKE_TEST_PER_HOOK_TIMEOUT_SECONDS,
            env=env,
            cwd=str(root),
        )
        stderr_text = result.stderr or ""
    except subprocess.TimeoutExpired:
        # 逾時前若已寫入 liveness 條目（import 已成功，只是後續邏輯較
        # 慢），仍視為 ok；否則視為不確定（見上方 docstring），不判崩潰。
        if _count_jsonl_lines(sentinel_liveness_file) > before:
            return "ok", ""
        return "timeout", "smoke test 逾時（> {}s，可能為系統負載，非必然崩潰）".format(
            SMOKE_TEST_PER_HOOK_TIMEOUT_SECONDS
        )
    except OSError as e:
        return "crashed", "smoke test 執行失敗: {}".format(e)

    after = _count_jsonl_lines(sentinel_liveness_file)
    if after > before:
        return "ok", ""
    lines = [line for line in stderr_text.splitlines() if line.strip()]
    return "crashed", " | ".join(lines[:3])


def _smoke_test_registered_hooks(root: Path, settings: dict, logger) -> list:
    """SessionStart 主動崩潰偵測本體（方案 A）。

    對 settings.json 以 uv run 登記且宣告非空 PEP 723 dependencies 的 hook
    執行一次 smoke test，偵測 module-level import 階段崩潰——此類崩潰會
    使 run_hook_safely/setup_hook_logging/mark_hook_entry 三者皆未執行，
    一般的 stderr 雙通道與日誌檔可觀測性完全不適用（已於獨立重現實驗
    證實）。

    偵測範圍的已知邊界（三種外部症狀近似但成因不同的失效模式）：

    (a) hook 已被觸發但 import 階段崩潰——本機制可偵測（liveness 條目
        缺席）。這是本機制設計聚焦的失效模式，也是動機案例
        （active-dispatch-tracker-hook.py 因缺 pyyaml 宣告而連續多日
        零告警）的實際成因。
    (b) hook 已註冊、事件確實發生，但 runtime 從未呼叫——理論可能性；
        先前分析原記載的疑似實例經後續查證推翻（該案例實為 (c)），
        目前無已知實例。本機制若真的遇上此類失效，因無法區分「事件
        未發生」與「事件發生但未被呼叫」（liveness 缺乏獨立的「事件
        應發生次數」對照來源），同樣無鑑別力。
    (c) hook 正常執行、log 正常寫入、狀態正常改變，但觀測面與作用面
        落在不同檔案系統位置（後續查證實證：worktree 內執行的
        SubagentStop cleanup hook 把 log 與 liveness 條目寫進 worktree
        自己的 `.claude/hook-logs/`，主 repo 側查詢得到零紀錄，而
        實際狀態變更已經發生）——本機制對此**無鑑別力**：liveness
        條目會正常寫入，只是寫在本機制固定查詢的主 repo 路徑之外；
        本機制的 smoke test 呼叫本身固定在主 repo 執行（`cwd=root`），
        無法涵蓋「同一 hook 在真實 worktree 派發時」的執行路徑，也就
        無法重現該情境下的錯位。此為已知殘留限制，需要一個獨立於
        執行路徑（不依賴猜測 hook 會在哪個檔案系統位置寫入）的狀態
        一致性偵測機制才能涵蓋，超出本機制「SessionStart 主動呼叫
        smoke test」的設計定位，已透過 spawn request 記錄供後續評估。

    增量快取：僅檔案 mtime 變動或未曾測試過的 hook 才重新執行，並在
    單次 SessionStart 內設時間預算上限（`SMOKE_TEST_TIME_BUDGET_SECONDS`），
    避免拖慢 session 啟動、觸及 settings.json 對本 hook 註冊的 5000ms
    timeout。預算內測不完的候選會在下次 SessionStart 繼續處理，快取
    持續累積直到涵蓋所有候選；已快取的崩潰狀態每次 SessionStart 都會
    回報（即使本次未重測），確保崩潰在修復前持續可見，不會因為「這次
    沒重跑」而從報告中消失。
    """
    candidates = _smoke_test_candidates(root, settings)
    if not candidates:
        return []

    cache = _load_smoke_test_cache(root)
    hooks_dir = root / ".claude" / "hooks"

    to_test = []
    for name in sorted(candidates):
        path = hooks_dir / "{}.py".format(name)
        try:
            mtime = path.stat().st_mtime
        except OSError:
            continue
        cached = cache.get(name)
        if cached is None or cached.get("mtime") != mtime:
            to_test.append((name, mtime))

    sentinel_liveness_file = (
        root / ".claude" / "hook-logs" / LIVENESS_SUBDIR
        / "{}.jsonl".format(SMOKE_TEST_SENTINEL_SESSION_ID)
    )
    if to_test:
        try:
            sentinel_liveness_file.parent.mkdir(parents=True, exist_ok=True)
            sentinel_liveness_file.write_text("", encoding="utf-8")
        except OSError as e:
            logger.warning("sentinel liveness 檔重置失敗: {}".format(e))

    start_time = time.time()
    tested_count = 0
    timeout_count = 0
    for name, mtime in to_test:
        # 前瞻式判斷：預留本候選最壞執行時間（per-hook timeout）仍在
        # 預算內才啟動，避免「檢查當下未超預算、但這一個候選跑完就
        # 超過」的溢出（實機驗證發現的落差，見上方常數註解）。
        elapsed = time.time() - start_time
        if elapsed + SMOKE_TEST_PER_HOOK_TIMEOUT_SECONDS >= SMOKE_TEST_TIME_BUDGET_SECONDS:
            logger.info(
                "smoke test 時間預算已用盡，剩餘 {} 個候選留待下次 "
                "SessionStart".format(len(to_test) - tested_count - timeout_count)
            )
            break
        status, summary = _run_single_smoke_test(root, name, sentinel_liveness_file)
        if status == "timeout":
            # 不快取：狀態不確定（可能是系統負載，非必然崩潰），保留在
            # 候選佇列，下次 SessionStart 重新嘗試（見 _run_single_smoke_test
            # docstring）。
            timeout_count += 1
            logger.debug("smoke test 逾時，留待下次重試: {}".format(name))
            continue
        cache[name] = {
            "mtime": mtime,
            "status": status,
            "summary": summary,
            "last_checked": datetime.now().isoformat(),
        }
        tested_count += 1

    # 候選集合可能隨時間變動（hook 移除或改為非 uv 登記），移除過期快取項
    for stale_name in set(cache.keys()) - candidates:
        del cache[stale_name]

    _save_smoke_test_cache(root, cache, logger)

    if tested_count or timeout_count:
        logger.info(
            "smoke test 本次執行 {} / {} 個候選（預算 {}s，另 {} 個逾時留待下次）".format(
                tested_count, len(to_test), SMOKE_TEST_TIME_BUDGET_SECONDS, timeout_count
            )
        )

    crashed_entries = [
        (name, info.get("summary", ""))
        for name, info in cache.items()
        if info.get("status") == "crashed"
    ]
    return sorted(crashed_entries)


def _report_smoke_test_crashes(root: Path, settings: dict, logger, input_data) -> None:
    """取得鎖檔後執行 smoke test，偵測到崩潰時透過 SessionStart
    additionalContext 回報（PM-only：崩潰是框架維運訊號，非任務執行
    內容，不需下發給 subagent）。鎖檔取得失敗時靜默跳過（下次
    SessionStart 重試），不影響本 hook 既有的三類清單彙整邏輯。
    """
    if not _acquire_smoke_test_lock(root):
        logger.debug("smoke test 鎖檔已被佔用，跳過本次（下次 SessionStart 重試）")
        return
    try:
        crashed = _smoke_test_registered_hooks(root, settings, logger)
    finally:
        _release_smoke_test_lock(root)

    if not crashed:
        return

    lines = [
        "[hook-liveness-summary] 偵測到 {} 個 hook 疑似 import 階段崩潰"
        "（module-level import 失敗，run_hook_safely 從未執行，一般的 "
        "stderr/日誌可觀測性不適用）：".format(len(crashed))
    ]
    for name, summary in crashed:
        lines.append("  - {}: {}".format(name, summary or "(無 stderr 摘要)"))
    lines.append(
        "偵測範圍邊界：僅涵蓋 hook 被呼叫但 import 崩潰的情形；hook 在"
        "非主 repo 路徑（如 worktree）執行時的觀測面/作用面錯位不在此"
        "機制涵蓋範圍。"
    )
    report = "\n".join(lines)
    logger.warning(report)
    emit_hook_output(
        "SessionStart",
        additional_context=report,
        audience="pm_only",
        input_data=input_data,
    )


def main() -> int:
    logger = setup_hook_logging(HOOK_NAME)
    input_data = read_json_from_stdin(logger)  # SessionStart 常無 stdin，僅統一入口消費

    root = get_project_root()
    settings_path = root / ".claude" / "settings.json"
    try:
        settings = json.loads(settings_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        logger.info("讀取 settings.json 失敗，跳過本次彙整: {}".format(e))
        return 0

    registered = _registered_hook_names(settings)
    covered = _covered_by_run_hook_safely(root, registered)
    uncovered = registered - covered

    current_session_id = os.environ.get(ENV_SESSION_ID, "").strip()
    liveness_file = _most_recent_completed_liveness_file(root, current_session_id)
    if liveness_file is None:
        logger.info(
            "尚無可比對的 liveness 索引（首次啟用或前一 session 無任何 hook "
            "觸發），涵蓋 {} / 未涵蓋(無探針) {}".format(len(covered), len(uncovered))
        )
        if uncovered:
            logger.info("未涵蓋（無 liveness 探針）: {}".format(sorted(uncovered)))
    else:
        invoked = _invoked_hook_names(liveness_file)
        loaded = covered & invoked
        never_triggered = covered - invoked

        logger.info(
            "Liveness 彙整（比對來源: {}）：已載入 {} / 涵蓋範圍 {} / "
            "未涵蓋(無探針) {}".format(
                liveness_file.name, len(loaded), len(covered), len(uncovered)
            )
        )
        if never_triggered:
            logger.info(
                "本 session 從未觸發（涵蓋範圍內，可能只是對應事件未發生）: "
                "{}".format(sorted(never_triggered))
            )
        if uncovered:
            logger.info(
                "未涵蓋（無 liveness 探針，需另評估）: {}".format(sorted(uncovered))
            )

    _report_smoke_test_crashes(root, settings, logger, input_data)

    return 0


if __name__ == "__main__":
    sys.exit(run_hook_safely(main, HOOK_NAME))
