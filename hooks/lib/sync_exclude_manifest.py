"""Sync 排除分類 SSOT（Single Source of Truth）manifest。

本模組為 .claude/ 同步機制的 local-only / 敏感憑證分類唯一來源，
消除 sync-claude-push.py / sync-claude-status.py 三件套
（EXCLUDE_PATTERNS + EXCLUDE_SUFFIXES + EXCLUDE_NAME_PREFIXES）
與 should_exclude() / compute_content_hash() 在多檔重複定義造成的漂移
（ARCH-020）。

設計原則：
- 對外暴露「原始分類 frozenset」（LOCAL_ONLY_PATTERNS / CREDENTIAL_PATTERNS /
  EXCLUDE_SUFFIXES / EXCLUDE_NAME_PREFIXES），各腳本依需要組合，避免新漂移面。
- 「組合集合」（PUSH_EXCLUDE / SYNC_EXCLUDE_ALL）以具名常數呈現並附單行理由，
  讓組合語意顯性化而非散落各腳本各自拼裝。
- should_exclude 與 compute_content_hash 為唯一實作，三腳本與 hook 一律 import。

匯入範本（uv run --script 獨立檔不能直接 import，需 sys.path.insert）：

    # .claude/hooks/ 下的 hook：
    sys.path.insert(0, str(Path(__file__).parent / "lib"))
    from sync_exclude_manifest import should_exclude, compute_content_hash

    # .claude/scripts/ 下的三腳本：
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "hooks" / "lib"))
    from sync_exclude_manifest import should_exclude, compute_content_hash

本模組屬框架資產，正常 sync（不在排除清單內）。

來源：0.19.1-W1-027（W1-024 H1/H2/H3）。
"""

from __future__ import annotations

import hashlib
from pathlib import Path

# ============================================================================
# 原始分類 frozenset（對外暴露，各腳本依需要組合）
# ============================================================================
#
# 排除分類（新增項目時請對應下列四類之一，若都不符合請先評估是否應進 framework）
#
# 類型 A - Runtime state（本 session 執行期狀態，專案特定且會隨時間變動）
#   特徵：記錄當前派發/Hook/PM 狀態，跨專案共用會造成狀態污染
#   範例：dispatch-active.json、hook-state/、pm-status.json
#
# 類型 B - Local-only settings（各專案個別設定，不應跨專案同步）
#   特徵：每個專案 preserve/狀態/覆蓋設定獨立管理
#   範例：settings.local.json、sync-preserve.yaml、.sync-state.json
#
# 類型 C - Session-bound log（本地產生的日誌/交接檔案）
#   特徵：只對本機 session 有意義，無跨專案共用價值
#   範例：hook-logs/、handoff/、PM_INTERVENTION_REQUIRED、ARCHITECTURE_REVIEW_REQUIRED
#
# 新增機制時的 checklist 與決策流程見 .claude/references/sync-exclusion-guide.md

# 本地專有名稱（類型 A/B/C + 工具產物）：sync 時不推送、不覆蓋、不納入 hash
LOCAL_ONLY_PATTERNS = frozenset({
    # 類型 C - Session-bound log
    "handoff",
    "hook-logs",
    "PM_INTERVENTION_REQUIRED",
    "ARCHITECTURE_REVIEW_REQUIRED",
    "TASK_AVOIDANCE_FIX_MODE",  # PM task-avoidance fix-mode flag（與上述兩 flag 同族 runtime；
                               # 曾僅進 gitignore-check REQUIRED 未進 manifest，雙 SOT 漂移補齊）
    # 類型 A - Runtime state
    "pm-status.json",
    "dispatch-active.json",
    "dispatch-active.lock",    # W1-018.2: dispatch tracker advisory lock（.json 已排除，.lock 補齊）
    "scheduled_tasks.lock",    # W1-018.2: scheduled tasks runtime lock（session-local）
    "hook-state",
    # 工具產物（Python 快取，無跨專案共用價值）
    "__pycache__",
    ".pytest_cache",
    ".venv",
    # 類型 B - Local-only settings
    "sync-preserve.yaml",
    ".sync-state.json",
    # version-release CLI 專案配置（release workflow / tag 格式 / worklog 路徑
    # 皆 per-project，跨專案 sync 會以他專案設定覆蓋本專案；本專案 repo 內仍正常 track）
    ".version-release.yaml",
    ".sync-conflicts",         # 三方合併衝突暫存目錄（pull/push 皆不同步，本地手動解決）
    "settings.local.json",
    ".zhtw-mcp-skip",          # 各專案 opt-out 繁中檢查的 flag，per-project 決定
})

# 僅 .claude/ 根層的 local-only 目錄（W1-018.2）。
#
# 與 LOCAL_ONLY_PATTERNS 的差異：這些名稱（logs / state）過於通用，作為 part-level
# 黑名單會誤殺 skill 內部的同名 live 目錄（例：
# skills/cc-release-impact-review/state/last-reviewed.md 是 skill 維護的去重狀態
# 真實 tracked 檔，非 runtime 污染）。故僅在「相對 claude_dir 路徑的第一段」命中時
# 排除，避免 false positive 阻斷 live 內容同步或被 --clean 誤刪。
#
# 對應 .gitignore 以 root-anchored 形式宣告（.claude/logs/ 與 .claude/state/）。
LOCAL_ONLY_ROOT_DIRS = frozenset({
    "logs",     # 類型 C - session log 根目錄（曾外洩遠端，補入防再洩）
    "state",    # 類型 A - session state markers 根目錄（runtime，曾外洩遠端）
    # 類型 A - agent worktree 根目錄（runtime，本地 agent worktree 產物；曾誤推遠端為
    # 6 個 gitlink 160000 垃圾）。採 root-anchored 而非 part-level：worktrees 雖為
    # 具名（無已知 skill 內部同名巢狀目錄，目前 part-level 不會誤殺），但語意上
    # .claude/worktrees/ 必為根層 runtime 產物，root-anchored 對未來新增的巢狀
    # worktrees/ 目錄天然免疫（與 logs / state 同策略）。對應 .gitignore 既有
    # root-anchored 宣告 .claude/worktrees/。來源：W1-018.3。
    "worktrees",
    # 專案產物（非框架資產）：以下三者為 per-project 工作產物，框架定義目錄結構但
    # 目錄內的實例屬各專案私有，跨專案 sync 會把他專案的 ticket 備份 / 分析 / 計畫
    # 推進公開框架 repo 造成污染（root-anchored，對應 .gitignore 同名宣告）。
    #
    # [維護者警告 — 勿於 sync-pull 衝突時還原] 此三條曾於框架 repo 累積大量孤兒
    # （某下游專案 78 個 migration-backups + 6 analyses + 5 plans 被誤推進公開 repo）。
    # 本條目即為根除該污染的防護。曾因另一專案 full-overlay sync-push 攜帶舊版 manifest
    # 而被靜默蓋掉，pull 三方合併再把刪除帶回下游，形成 clobber 循環。若你在 sync
    # 衝突中看到「刪除這三行」的 delta，那是上游被舊 manifest 覆蓋的結果，非有意移除，
    # 請採 local（保留本三條），勿還原。根治需框架維護者在 canonical 源頭一併保留本條目。
    "migration-backups",  # ticket migrate 自動產生的 ticket md 備份
    "analyses",           # 專案分析報告產物
    "plans",              # 專案計畫 / 設計 / 遷移文件
})

# 類型 D - 敏感憑證（嚴禁推送至公開 repo；含密鑰/token/環境變數，外流即安全事故）
CREDENTIAL_PATTERNS = frozenset({
    ".env",
    ".env.local",
    ".env.production",
    "credentials.json",
    "secrets.yaml",
    "secrets.json",
    ".secrets",
    # 目錄層級排除（與 .secrets 對齊）
    "secrets",
    "private",
    ".keys",
})

# 副檔名排除（含憑證副檔名 .pem/.key/.p12/.pfx/.jks，類型 D 最高風險維度）
EXCLUDE_SUFFIXES = frozenset({".pyc", ".pem", ".key", ".p12", ".pfx", ".jks"})

# 檔案名稱前綴匹配（涵蓋 .env.staging, secrets_prod.json 等變體）
EXCLUDE_NAME_PREFIXES = frozenset({
    ".env.",    # .env.staging, .env.test, .env.development 等
    "secret",   # secrets.json, secret_key.txt 等
})

# ============================================================================
# 組合集合（具名常數 + 單行理由，組合語意顯性化）
# ============================================================================

# push / status 端的名稱黑名單：local-only 與敏感憑證皆須排除（避免外洩至公開 repo）
PUSH_EXCLUDE = LOCAL_ONLY_PATTERNS | CREDENTIAL_PATTERNS

# content hash 與 copy 共用的完整名稱黑名單（與 PUSH_EXCLUDE 同義，供語意檢索）
SYNC_EXCLUDE_ALL = PUSH_EXCLUDE

# .gitignore 必須涵蓋的 local-only 名稱（gitignore↔manifest 交叉驗證基準）。
#
# 與 LOCAL_ONLY_PATTERNS 同義：這些是各專案個別管理、不應被 git track 的 runtime
# state / local-only settings / session log / 工具產物。若 .gitignore 漏列其一，
# push 端 clean-check 會把未追蹤的本地檔判為 dirty 而 abort（W1-024 缺陷 T）。
# 故 session-start hook 以此集合交叉驗證 .gitignore 涵蓋度，偵測未來漂移。
#
# 不含 CREDENTIAL_PATTERNS：憑證的 gitignore 涵蓋由 .env / secret 等專用 glob
# 規則處理（且部分為目錄層級），語意與 local-only 名稱比對不同，故分開不混入。
# 含 LOCAL_ONLY_ROOT_DIRS：logs / state 同須在 .gitignore 宣告（root-anchored 形式），
# 故併入交叉驗證基準。
GITIGNORE_EXPECTED = LOCAL_ONLY_PATTERNS | LOCAL_ONLY_ROOT_DIRS

# 預計算小寫版本，避免每次呼叫 should_exclude 重複計算
_PUSH_EXCLUDE_LOWER = frozenset(p.lower() for p in PUSH_EXCLUDE)
_LOCAL_ONLY_ROOT_DIRS_LOWER = frozenset(p.lower() for p in LOCAL_ONLY_ROOT_DIRS)
_EXCLUDE_SUFFIXES_LOWER = frozenset(s.lower() for s in EXCLUDE_SUFFIXES)
_EXCLUDE_NAME_PREFIXES_LOWER = frozenset(p.lower() for p in EXCLUDE_NAME_PREFIXES)


# ============================================================================
# 唯一實作（should_exclude / compute_content_hash）
# ============================================================================

def should_exclude(path: Path) -> bool:
    """檢查相對路徑是否應排除在 sync / hash 之外（大小寫不敏感）。

    契約：path 必須為「相對 claude_dir 的路徑」（非絕對路徑）。傳入絕對路徑會使
    path.parts 含 .claude 之外的目錄段（如根目錄各層），破壞 part-level 黑名單
    判斷的語意，故以 assert 強制此前提。

    判斷規則（任一命中即排除）：
      1. 檔名命中名稱黑名單（PUSH_EXCLUDE）
      2. 副檔名命中 EXCLUDE_SUFFIXES（含 .pem/.key 等憑證副檔名）
      3. 檔名前綴命中 EXCLUDE_NAME_PREFIXES（.env. / secret 變體）
      4. 路徑任一目錄段命中名稱黑名單（排除整個 hook-state/ secrets/ 目錄）
      5. 路徑第一段命中 LOCAL_ONLY_ROOT_DIRS（僅 root-anchored，避免誤殺 skill
         內部同名目錄如 skills/*/state/）（W1-018.2）
    """
    assert not path.is_absolute(), (
        f"should_exclude 要求相對 claude_dir 的路徑，收到絕對路徑：{path}"
    )
    name_lower = path.name.lower()
    if name_lower in _PUSH_EXCLUDE_LOWER:
        return True
    if path.suffix.lower() in _EXCLUDE_SUFFIXES_LOWER:
        return True
    if any(name_lower.startswith(prefix) for prefix in _EXCLUDE_NAME_PREFIXES_LOWER):
        return True
    if any(part.lower() in _PUSH_EXCLUDE_LOWER for part in path.parts):
        return True
    # root-anchored：僅第一段命中才排除（logs / state 通用名只在 .claude/ 根層為 runtime）
    parts = path.parts
    return bool(parts) and parts[0].lower() in _LOCAL_ONLY_ROOT_DIRS_LOWER


def compute_content_hash(claude_dir: Path) -> str:
    """遞迴計算 .claude/ 目錄的內容指紋（前 16 字元）。

    每個檔案產生 "相對路徑:sha256(內容)" 字串，
    所有字串排序後合併取總 sha256 前 16 字元。
    排除清單由 should_exclude 統一判定，確保 push / status 兩端指紋一致。
    """
    file_hashes: list[str] = []
    for file_path in sorted(claude_dir.rglob("*")):
        if not file_path.is_file() or file_path.is_symlink():
            continue
        rel = file_path.relative_to(claude_dir)
        if should_exclude(rel):
            continue
        content_hash = hashlib.sha256(file_path.read_bytes()).hexdigest()
        rel_posix = rel.as_posix()  # 統一使用正斜線，確保跨平台一致
        file_hashes.append(f"{rel_posix}:{content_hash}")

    combined = "\n".join(file_hashes)
    return hashlib.sha256(combined.encode("utf-8")).hexdigest()[:16]
