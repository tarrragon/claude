# 單次請求 I/O 採集去重規範

本文件規範同一請求生命週期內，同一筆 I/O 資料的採集與消費邊界，作為 PC-097（同一資料於同一請求中被兩處 I/O 重複呼叫）防護的引用來源（SSOT）。

> **核心理念**：同一請求內，同一筆外部資料（檔案、git、HTTP、DB）只能有一個採集點；其他消費者透過 state/dataclass 取值，不得自行呼叫底層 I/O。

---

## 適用範圍

| 對象 | 是否適用 |
|------|---------|
| `.claude/skills/ticket/ticket_system/` 下 commands / lib 層 | 是 |
| `.claude/hooks/` 下任一 hook 單次觸發內 | 是 |
| 任何單次 CLI / HTTP / event handler 請求 | 是 |
| 跨請求（不同 session、不同 hook 觸發）| 否（本規範不約束） |
| 純記憶體計算（無 I/O） | 否 |

---

## 規則 1：單一採集點原則

同一請求生命週期內，同一筆 I/O（例如 `git status`、`Path.read_text(file)`、同一 HTTP endpoint）只能由唯一一個函式採集；其他消費者透過該採集點寫入的 state/dataclass 欄位取值。

**Why**：兩處各自採集會在競態下取得不同快照（race window），且兩個時間戳難以同步——「幾乎一樣」即等同 race condition，不可接受。重複 I/O 也造成效能浪費（大 repo 的 `git status` 數百 ms / 次）。

**Consequence**：違反此原則會讓 command 層與 lib 層各自擁有「我的 git status」心智模型，code review 難發現重複（檔案不同、上下文不同）；測試多 mock 掉 I/O，重複呼叫不會被偵測；資料不一致的 bug 在生產環境才浮現。

**Action**：

| 角色 | 動作 |
|------|------|
| 採集點（單一） | 以底層命令呼叫 I/O，回傳結構化欄位寫入 state dataclass |
| 消費端 | 從 state/dataclass 欄位讀取，禁止呼叫底層 I/O |
| 介面設計 | lib 層回傳結構必須包含所有消費端可能需要的欄位；不足時擴充 lib 介面，禁止繞過 |

---

## 規則 2：時間戳語意規範

任何 `computed_at` / `fetched_at` / `collected_at` 等時間欄位必須指向**唯一一次**對應 I/O 的時刻；同一名稱的時間欄位禁止對應多個 I/O 時刻。

**Why**：時間戳是請求一致性的試金石。若 state 寫入 `computed_at=T1`，但 command 層渲染時實際呼叫的是 `T2` 快照，時間戳即說謊；後人追查資料不一致時無法區分「時間戳錯」還是「資料漂移」。

**Consequence**：時間戳語意混亂會讓 debug 失去錨點——日誌顯示 `computed_at=14:30:00`，但實際渲染的 dirty files 是 `14:30:00.450` 取得，無法重現問題。

**Action**：

| 欄位語意 | 命名與規範 |
|---------|----------|
| 整體 state 計算完成時刻 | `computed_at`（指 state 物件組裝完成的時刻） |
| 個別 I/O 採集時刻 | 若需區分，採 `git_status_fetched_at` / `dispatch_loaded_at` 等具語意名稱 |
| 多筆 I/O 共享單一時間戳 | 禁止；若採集間隔 > 100 ms，應拆為獨立時間欄位 |
| 消費端渲染時間 | 不寫入 state；如需顯示「現在時間」由 render 層自行取，禁止與採集時間混用 |

---

## 規則 3：Phase 1 設計檢查清單

Phase 1 規格設計（與 Phase 4 重構評估）必須逐項通過以下檢查，未通過即視為規格不完整、不可進入 Phase 2 RED 撰寫。

- [ ] **I/O 清單**：列出本請求所有 I/O 操作（git / file / HTTP / DB）及其呼叫位置（檔案:行號或函式名）
- [ ] **重複檢查**：上述清單是否有任兩處採集相同資料？若有，指定其中一處為唯一採集點
- [ ] **State dataclass 欄位完備性**：採集點寫入的 state/dataclass 是否包含所有消費端需要的欄位？若不足，先擴充欄位再進 Phase 2
- [ ] **消費端取值路徑**：每個消費端（command / render / hook）取值來源是否明確指向 state 欄位（而非底層 I/O）？
- [ ] **命名規範**：採集函式以 `_read_*` / `_fetch_*` 開頭；消費函式以 `_print_*_from_state` / `_render_*` 開頭，命名即標示責任邊界
- [ ] **時間戳對應**：state 內每個時間欄位是否明確對應到唯一一次 I/O？多筆 I/O 共用單一時間戳是否合理（採集間隔 < 100 ms）？
- [ ] **測試斷言**：Phase 2 RED 測試是否包含「mock 底層 I/O，斷言呼叫次數 ≤ 1」（call count assertion）？

---

## 規則 4：套用範例

### 正例：`git status` 採集（已落地）

**採集點（單一）**：`.claude/skills/ticket/ticket_system/lib/checkpoint_state.py:381` `_read_git_status`

```python
def _read_git_status(project_root: Optional[Path] = None) -> int:
    """讀取 git status --porcelain，回傳未提交檔案數。"""
    root = project_root or get_project_root()
    result = _run_subprocess(
        ["git", "status", "--porcelain"], root, _GIT_CMD_TIMEOUT
    )
    lines = [ln for ln in result.stdout.splitlines() if ln.strip()]
    return len(lines)
```

採集結果寫入 `CheckpointState.uncommitted_files`（dataclass 欄位，連同 `computed_at` 標示組裝時刻）。

**消費端（從 state 取值）**：`.claude/skills/ticket/ticket_system/commands/track_snapshot.py:233` `_print_git_status_from_state`

```python
def _print_git_status_from_state(branch: str, state: CheckpointState) -> None:
    """輸出 git 狀態（v2 §3.4：從 state.uncommitted_files 取值，不再呼叫 git status）。"""
    print("--- Git 狀態 ---")
    print(f"  分支: {branch}")
    if state.uncommitted_files is None:
        print("  未提交: 資料源不可用")
    else:
        print(f"  未提交: {state.uncommitted_files} 個檔案")
```

**設計要點**：

| 元素 | 規範對應 |
|------|---------|
| 函式命名 `_read_git_status` | 規則 3 命名規範：採集函式以 `_read_*` 開頭 |
| 函式命名 `_print_git_status_from_state` | 規則 3 命名規範：消費函式以 `_print_*_from_state` 結尾，標示「從 state 取」 |
| 註解明示「不再呼叫 git status」 | 規則 1 單一採集點：消費端禁止繞過 |
| 寫入 `state.uncommitted_files` 與 `computed_at` | 規則 2 時間戳語意：computed_at 對應 state 組裝時刻 |

### 反例：handoff stop hook 同一 ticket frontmatter 多次讀取

**反例位置**：`.claude/hooks/handoff-auto-resume-stop-hook.py::scan_pending_handoff_tasks` 迴圈內。

**結構描述**：單次 stop hook 觸發、單筆 handoff record 處理路徑，可能對同一 ticket_id 重複呼叫 `find_ticket_file` + `parse_ticket_frontmatter`：

| 呼叫位置 | 觸發路徑 | I/O 行為 |
|---------|---------|---------|
| `is_handoff_stale(data, project_root)` | lib SSOT，依 direction / from_ticket 內部呼叫 `_load_ticket_status` | 讀 ticket md frontmatter（1 次） |
| `is_ticket_completed(project_root, ticket_id, logger)` | delegate 至 lib `is_ticket_terminal` | 讀同一 ticket md（2 次） |
| `is_ticket_recently_started(project_root, ticket_id, logger)` | hook 內 `find_ticket_file` + `parse_ticket_frontmatter` | 讀同一 ticket md（3 次） |

當 `target_id == from_ticket == ticket_id` 時，同一檔案在單次 scan 內被開啟解析 **最多 3 次**，違反規則 1 單一採集點原則。

**修復前**：

```python
def is_ticket_recently_started(project_root: Path, ticket_id: str, logger) -> bool:
    ticket_path = find_ticket_file(ticket_id, project_root, logger)
    if not ticket_path:
        return False
    frontmatter = parse_ticket_frontmatter(ticket_path, logger)  # 每次呼叫都重讀
    ...
```

**修復後**（採方案 B：lib 層 API 接受預採集參數注入）：

```python
def _load_frontmatter_cached(cache, ticket_id, project_root, logger):
    """單次請求內 frontmatter 採集點：cache 命中則直接回傳，未命中才走 I/O。"""
    if cache is not None and ticket_id in cache:
        return cache[ticket_id]
    ticket_path = find_ticket_file(ticket_id, project_root, logger)
    result = parse_ticket_frontmatter(ticket_path, logger) if ticket_path else None
    if cache is not None:
        cache[ticket_id] = result
    return result


def is_ticket_recently_started(project_root, ticket_id, logger, frontmatter_cache=None):
    frontmatter = _load_frontmatter_cached(frontmatter_cache, ticket_id, project_root, logger)
    if not frontmatter:
        return False
    ...


def scan_pending_handoff_tasks(project_root, logger):
    frontmatter_cache: Dict[str, Optional[dict]] = {}  # 採集快取（請求範圍）
    for file_path in sorted(pending_dir.glob("*.json")):
        ...
        elif is_ticket_recently_started(project_root, ticket_id, logger, frontmatter_cache):
            ...
```

**對應違反的規則編號**：規則 1（單一採集點原則）。`is_ticket_recently_started` 與其他 predicate 各自採集同一 ticket frontmatter，未透過共用 cache 收斂為「單次採集 + 多消費」結構。

**補強測試（mock call count assertion 範例）**：

```python
def test_is_ticket_recently_started_cache_hit_avoids_reparse(monkeypatch, tmp_path):
    """PC-097：傳入 frontmatter_cache 時，同一 ticket 第二次呼叫不重複解析。"""
    parse_calls = {"count": 0}
    def counting_parse(path, log):
        parse_calls["count"] += 1
        return {"started_at": datetime.now().isoformat()}
    monkeypatch.setattr(hook, "find_ticket_file", lambda tid, root, log: fake_path)
    monkeypatch.setattr(hook, "parse_ticket_frontmatter", counting_parse)

    cache: dict = {}
    hook.is_ticket_recently_started(tmp_path, "X", MagicMock(), cache)
    assert parse_calls["count"] == 1, "第一次呼叫應解析一次"
    hook.is_ticket_recently_started(tmp_path, "X", MagicMock(), cache)
    assert parse_calls["count"] == 1, "第二次呼叫應走快取，不重複解析"
```

**設計要點**：

| 元素 | 規範對應 |
|------|---------|
| `_load_frontmatter_cached` 為採集函式 | 規則 3 命名規範：採集函式以 `_load_*` / `_read_*` 表達「外部 I/O」 |
| `frontmatter_cache` 參數注入 | 規則 1 方案 B：lib 層 API 接受預採集參數，呼叫端控制請求範圍 |
| cache 預設為 `None` 維持向後相容 | 單一查詢場景無需快取，避免強制全域狀態 |
| Call count assertion `assert parse_calls["count"] == 1` | 規則 3 設計檢查清單：mock 底層 I/O，斷言呼叫次數 ≤ 1 |

**未完全收斂的部分**：`is_handoff_stale`（lib SSOT 函式）與 `is_ticket_completed`（delegate 至 lib `is_ticket_terminal`）目前仍各自呼叫 `_load_ticket_status`，因屬於 lib 層共用 API 改動成本較高。本反例先於 hook 層收斂 `is_ticket_recently_started`，剩餘兩個 predicate 之後可在 lib 層擴充「接受預採集 frontmatter 參數」介面（規則 1 方案 B）統一收斂。

---

## 規則 5：與 `CheckpointState` dataclass 機制的銜接

本規範以 `CheckpointState`（`.claude/skills/ticket/ticket_system/lib/checkpoint_state.py:81`）為單一請求 I/O 採集結果的承載結構參考實作；其他模組設計類似機制時應對齊以下要素。

**Why**：dataclass 是 Python 將「採集結果」與「消費介面」解耦的最輕量機制——`@dataclass(frozen=True)` 額外提供不可變保證，消費端無法在傳遞中竄改採集結果，等同強制單一資料源。

**Consequence**：若採集結果以散落變數（多參數 / dict）傳遞，消費端易在中途自行補資料（再呼叫一次 I/O），形成重複採集；且 dict 欄位無型別約束，缺欄位時消費端傾向「自己補一下」而非修 lib 介面。

**Action**：

| 要素 | `CheckpointState` 實作 | 套用建議 |
|------|----------------------|---------|
| 不可變結構 | `@dataclass` + `frozen=True` 預設選項 | 採集結果以 frozen dataclass 傳遞，禁止 dict / namedtuple（無型別約束） |
| 採集元資訊欄位 | `computed_at: str` / `data_sources` | dataclass 內固定保留時間戳與資料來源欄位 |
| 缺值表達 | `Optional[int] = None`（None 表資料源失敗，0 表 clean） | 區分「採集失敗」vs「採集成功但值為零」，禁止以 0 / "" 混合表達 |
| 採集函式簽名 | `_read_*(project_root) -> 結構化值` | 採集函式回傳純值或小 tuple；組裝由上層統一處理 |
| 組裝點 | `checkpoint_state()` 統一呼叫所有 `_read_*` 後組 dataclass | 單一組裝點集中所有 I/O，便於後續加 instrumentation（總時間、失敗回退） |

---

## 與其他規則的邊界

| 規則 / 模式 | 聚焦 | 與本規範差異 |
|-----------|------|------------|
| PC-006（過早抽象統一） | 反向問題：抽象太早 | 本規範處理「該統一卻未統一」的反向場景 |
| PC-068（規劃新工具未掃描既有） | Phase 3a 工具盤點 | 本規範聚焦 I/O 採集邊界，非工具選擇 |
| `.claude/rules/core/observability-rules.md` | 異常 / 日誌可觀測性 | 互補：本規範管「資料一致性」，observability 管「失敗訊號可見」 |
| `.claude/rules/core/cognitive-load.md` | 認知負擔 | 互補：單一採集點降低「該以哪份為準」的認知負擔 |

---

## 檢查清單（提交前自審）

設計新請求 / 重構既有請求前自問：

- [ ] 本請求所有 I/O 已列出？
- [ ] 是否有任兩處採集相同資料？若有，已指定單一採集點？
- [ ] state dataclass 欄位足以讓所有消費端不需另呼叫 I/O？
- [ ] 採集函式 / 消費函式命名是否標示責任邊界（`_read_*` / `_*_from_state`）？
- [ ] 時間戳欄位是否明確對應唯一一次 I/O 時刻？
- [ ] 是否有 mock call count assertion 測試（同一請求內 I/O 呼叫 ≤ 1）？
- [ ] dataclass 是否 `frozen=True`，禁止消費端中途竄改？

---

## 相關文件

- `.claude/error-patterns/process-compliance/PC-097-duplicate-io-call-for-same-data.md` — 首發案例與根因分析
- `.claude/error-patterns/process-compliance/PC-006-premature-unification-abstraction.md` — 姊妹模式（反向問題）
- `.claude/error-patterns/process-compliance/PC-068-phase3a-planning-new-utility-without-scan.md` — 姊妹模式（盤點缺失）
- `.claude/skills/ticket/ticket_system/lib/checkpoint_state.py` — 參考實作（採集點 + dataclass 結構）
- `.claude/skills/ticket/ticket_system/commands/track_snapshot.py` — 參考實作（消費端從 state 取值）

---

**Last Updated**: 2026-05-18
**Version**: 1.0.0
**Source**: PC-097 防護落地（規則層 SSOT）
