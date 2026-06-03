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
    # 類型 A - Runtime state
    "pm-status.json",
    "dispatch-active.json",
    "hook-state",
    # 工具產物（Python 快取，無跨專案共用價值）
    "__pycache__",
    ".pytest_cache",
    ".venv",
    # 類型 B - Local-only settings
    "sync-preserve.yaml",
    ".sync-state.json",
    ".sync-conflicts",         # 三方合併衝突暫存目錄（pull/push 皆不同步，本地手動解決）
    "settings.local.json",
    ".zhtw-mcp-skip",          # 各專案 opt-out 繁中檢查的 flag，per-project 決定
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
GITIGNORE_EXPECTED = LOCAL_ONLY_PATTERNS

# 預計算小寫版本，避免每次呼叫 should_exclude 重複計算
_PUSH_EXCLUDE_LOWER = frozenset(p.lower() for p in PUSH_EXCLUDE)
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
    return any(part.lower() in _PUSH_EXCLUDE_LOWER for part in path.parts)


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
