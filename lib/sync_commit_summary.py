"""sync push 的 commit 訊息生成：過濾專案特定資訊並生成結構化摘要。"""

import functools
import re
import sys
from collections import defaultdict
from pathlib import Path

from lib.sync_cli_io import run_git
from lib.ticket_id_pattern import (
    SEARCH_BOUNDED_RE as _VERSIONED_TICKET_RE,
    BARE_BOTH_BOUNDED_RE as _BARE_TICKET_RE,
)

# commit 訊息中需要過濾的專案特定模式
# 獨立 repo 是跨專案通用框架，commit 訊息禁止包含專案版本號/Wave/Ticket 編號
#
# 各條附帶一個 placeholder：移除位置若非 conventional scope 的 `(...)`
# 括號（即句中位置），改用 placeholder 取代而非清空，避免留下無主詞的
# 斷句（見 strip_project_specific_info）。
PROJECT_SPECIFIC_PATTERNS = [
    (r"\b\d+\.\d+\.\d+-W\d+-\d+\b", "某票"),   # 完整格式 Ticket ID
    (r"\bW\d+-\d+\b", "某票"),                  # 短格式 Ticket（省略版本前綴）
    (r"\bv\d+\.\d+\.\d+\b", "某版本"),         # 版本號: v0.2.0（框架自身版本保留，見 framework_version_set）
    (r"\bWave\s*\d+\b", "某 Wave"),            # Wave 5
    (r"\b0\.\d+\.\d+\b", "某版本"),            # 裸版本: 0.2.0
]

# commit type 分類對應的 bump 等級（僅供 commit 訊息摘要與 dry-run 參考，不決定版號）
VERSION_BUMP_WEIGHTS = {
    "feat": "minor",
    "refactor": "minor",
    "fix": "patch",
    "docs": "patch",
    "chore": "patch",
    "style": "patch",
    "test": "patch",
    "perf": "minor",
    # revert 視為回退性變更，最低 patch；若同批含 feat/refactor 自動升 minor
    "revert": "patch",
}

# 版本號類 pattern 的 placeholder：命中值屬於框架自身版本時保留原字面，
# 不換成 placeholder（見 framework_version_set）。
_VERSION_PLACEHOLDER = "某版本"

# 本模組所在的 `.claude/`：推送方自己的框架副本，VERSION 與 CHANGELOG 即
# 推送方已知的框架版本。
_THIS_CLAUDE_DIR = Path(__file__).resolve().parent.parent
_CHANGELOG_HEADING_RE = re.compile(r"^## \[(\d+\.\d+\.\d+)\]", re.MULTILINE)


def framework_version_set(claude_dir: Path) -> frozenset[str]:
    """回傳應保留原字面的框架版本號集合（不含前綴 v）。

    集合 = `.claude/VERSION` 加上 `.claude/CHANGELOG.md` 的 `## [x.y.z]` 標題，
    再限縮到與 VERSION 相同的主版號。限縮主版號是因為框架舊系列（1.x、2.x）
    有數百個版本，與 consumer 自己的版本號重疊機率高；consumer 版本號屬專案
    特定資訊，不得因撞號而留在 canonical 的 commit 訊息。
    讀不到 VERSION 時回傳空集合（全數剝除，回到修改前的行為），並寫 stderr。
    """
    try:
        current = (claude_dir / "VERSION").read_text(encoding="utf-8").strip()
    except OSError as exc:
        sys.stderr.write(
            f"[sync-commit-summary] 讀不到 {claude_dir / 'VERSION'}（{exc}），"
            "框架版本號將一併剝除\n"
        )
        return frozenset()
    major = current.split(".", 1)[0]
    try:
        headings = set(
            _CHANGELOG_HEADING_RE.findall(
                (claude_dir / "CHANGELOG.md").read_text(encoding="utf-8")
            )
        )
    except (OSError, UnicodeDecodeError) as exc:
        sys.stderr.write(
            f"[sync-commit-summary] 讀不到 {claude_dir / 'CHANGELOG.md'}（{exc}），"
            "只保留 VERSION 本身\n"
        )
        headings = set()
    return frozenset(v for v in headings | {current} if v.split(".", 1)[0] == major)


@functools.lru_cache(maxsize=1)
def _default_keep_versions() -> frozenset[str]:
    return framework_version_set(_THIS_CLAUDE_DIR)



def _is_bare_paren_scope(text: str, start: int, end: int) -> bool:
    """判斷 [start, end) 是否為一對括號唯一內容（conventional commit scope）。

    往前找最近的 `(`、往後找最近的 `)`，兩者之間（扣掉待判定區間本身）
    若只有空白，代表該括號是為此區間量身包住的 scope（如
    `revert(<id>):` 的 `(<id>)`），此時連括號一併整組剝除才乾淨。
    括號內夾帶其他文字（如 `(見<id>說明)`）不算，維持句中處置。
    """
    open_idx = text.rfind("(", 0, start)
    close_idx = text.find(")", end)
    if open_idx == -1 or close_idx == -1:
        return False
    return text[open_idx + 1 : start].strip() == "" and text[end:close_idx].strip() == ""


def strip_project_specific_info(
    text: str, keep_versions: frozenset[str] | None = None
) -> str:
    """Remove project-specific info (Ticket IDs, version numbers, Wave refs) from text.

    The independent repo is a cross-project framework.
    Commit messages must focus on framework functionality, not project-specific progress.

    移除位置決定處置方式（句法位置而非內容類型）：
      - 位於 conventional scope 的 `(...)` 內（且為括號唯一內容）：整組
        剝除，括號隨後由下方清理一併移除，輸出乾淨（如
        `revert(<id>):` 剝除後為 `revert:`）。
      - 其他位置（句中/句首/句尾）：以 placeholder 取代，保留讀者可見
        的移除痕跡，避免主詞消失、語意斷裂（識別符原在描述文字中段時，
        剝除後應留下「某票」等佔位，而非讓前後文字直接相接）。

    版本號類 pattern 命中 `keep_versions` 內的值（框架自身版本）時保留原字面；
    `keep_versions` 省略時取本模組所在 `.claude/` 的 framework_version_set。
    Ticket ID 由前面的 pattern 先行剝除，不受保留集合影響。
    """
    keep = _default_keep_versions() if keep_versions is None else keep_versions
    result = text
    for pattern, placeholder in PROJECT_SPECIFIC_PATTERNS:
        def _replace(match: re.Match[str], _placeholder: str = placeholder) -> str:
            if _placeholder == _VERSION_PLACEHOLDER and match.group(0).lstrip("v") in keep:
                return match.group(0)
            if _is_bare_paren_scope(match.string, match.start(), match.end()):
                return ""
            return _placeholder

        result = re.sub(pattern, _replace, result)
    # Clean up leftover artifacts: multiple spaces, trailing colons, empty parens
    result = re.sub(r"\(\s*\)", "", result)
    result = re.sub(r":\s*$", "", result, flags=re.MULTILINE)
    result = re.sub(r"  +", " ", result)
    return result.strip()


def parse_commit_type(subject: str) -> tuple[str, str]:
    """Parse conventional commit subject into (type, description).

    Returns (type, description) where type is feat/fix/refactor/docs/chore/etc.
    If no conventional prefix, returns ("other", full_subject).

    Special handling: git 原生 `Revert "..."` 格式（無 conventional prefix）
    一律歸類為 "revert" type，description 為被 revert 的原 subject 內容。
    """
    # git 原生 revert message: `Revert "<original subject>"`
    revert_match = re.match(r'^Revert\s+"(.+)"\s*$', subject)
    if revert_match:
        return "revert", revert_match.group(1).strip()

    match = re.match(r"^(\w+)(?:\([^)]*\))?:\s*(.+)", subject)
    if match:
        return match.group(1).lower(), match.group(2).strip()
    return "other", subject.strip()


def parse_revert_info(subject: str) -> tuple[str, str] | None:
    """Parse revert commit subject and return (original_subject, original_ref).

    支援三種 revert 格式：
      1. `revert(scope): <original subject>` — conventional revert
      2. `revert: <original subject>` — conventional revert without scope
      3. `Revert "<original subject>"` — git default revert message

    傳回 (original_subject, original_ref)：
      - original_subject: 被 revert 的原 commit subject（已 strip 引號）
      - original_ref: 從原 subject 萃取的引用（W14-xxx 或裸 hash 或 ""）

    若 subject 非 revert 格式則回傳 None。
    """
    original = None

    # 格式 3: git default `Revert "<subject>"`
    m = re.match(r'^Revert\s+"(.+)"\s*$', subject)
    if m:
        original = m.group(1).strip()
    else:
        # 格式 1/2: conventional revert
        m = re.match(r"^revert(?:\([^)]*\))?:\s*(.+)", subject)
        if m:
            original = m.group(1).strip()
            # 若內層仍包 quotes，剝一層
            inner = re.match(r'^"(.+)"\s*$', original)
            if inner:
                original = inner.group(1).strip()

    if original is None:
        return None

    # 萃取引用：優先 Ticket ID（含 Wave 編號，版本化或裸格式皆可），其次
    # 7+ hex 短 hash。萃取到的 ticket ID 是否可寫入 CHANGELOG 由呼叫端經
    # _is_project_specific_ref 另行判定（見 categorize_commits）。
    ref = ""
    ticket_match = _VERSIONED_TICKET_RE.search(original) or _BARE_TICKET_RE.search(
        original
    )
    if ticket_match:
        ref = ticket_match.group(0)
    else:
        hash_match = re.search(r"\b([0-9a-f]{7,40})\b", original)
        if hash_match:
            ref = hash_match.group(1)

    return original, ref


def _is_project_specific_ref(ref: str) -> bool:
    """判斷 ref 是否為 ticket ID 樣式（版本化或裸格式），而非 commit hash。

    ticket ID 屬 consumer 專屬識別符，經 sync-push 寫入獨立 repo 後會擴散至
    所有 consumer，觸發各自的 reference-stability rule8 守衛；commit hash
    不含專案識別資訊，不受本判定影響。
    """
    if not ref:
        return False
    return bool(_VERSIONED_TICKET_RE.fullmatch(ref) or _BARE_TICKET_RE.fullmatch(ref))


def get_last_sync_timestamp(remote_repo_dir: str) -> str | None:
    """Get the timestamp of the latest commit in the remote repo.

    This represents when the last sync-push happened.
    """
    result = run_git(
        ["log", "-1", "--format=%aI"],
        cwd=remote_repo_dir,
        check=False,
    )
    if result.returncode == 0 and result.stdout.strip():
        return result.stdout.strip()
    return None


def collect_claude_commits(project_root: str, since: str | None) -> list[str]:
    """Collect commit subjects that touch .claude/ since the given timestamp.

    Returns list of commit subject lines.
    """
    args = ["log", "--format=%s", "--no-merges", "--", ".claude/"]
    if since:
        args.insert(2, f"--since={since}")
    result = run_git(args, cwd=project_root, check=False)
    if result.returncode != 0 or not result.stdout.strip():
        return []
    return [line for line in result.stdout.strip().split("\n") if line.strip()]


def _commit_touches_only_version_file(project_root: str, commit_sha: str) -> bool:
    """判斷單一 commit 在 .claude/ 底下變更的檔案是否僅有 VERSION（記帳 commit）。

    歷史上 push 後會回寫本地 VERSION 並由使用者另行 commit（現已不回寫）；該類
    commit 在 .claude/ 底下唯一改動的檔案就是 VERSION，內容已反映於上次 push
    計算的 last_push_hash 中，屬於「記帳」而非「實質」變更。
    """
    result = run_git(
        ["diff-tree", "--no-commit-id", "--name-only", "-r", commit_sha, "--", ".claude/"],
        cwd=project_root,
        check=False,
    )
    if result.returncode != 0:
        return False
    changed = [line.strip() for line in result.stdout.strip().split("\n") if line.strip()]
    if not changed:
        return False
    return all(Path(p).name == "VERSION" for p in changed)


def filter_out_version_only_commits(project_root: str, since: str | None) -> list[str] | None:
    """回傳排除「僅變更 .claude/VERSION」記帳 commit 後的 commit hash 清單。

    tarrragon/claude#66：VERSION 回寫後使用者提交此變更形成的記帳 commit，會被
    collect_claude_commits 的 subject 訊號誤判為「有新變更」，使零實質變更仍
    再次觸發版本 bump，形成回寫 -> 誤判有變更 -> 再次 bump -> 再次回寫的自反饋
    迴路，版本永不收斂。本函式以 diff 內容（而非 commit subject）過濾此類 commit。

    傳回 None 表示無法判定（例如 project_root 非 git repo或 git 指令失敗），
    呼叫端必須 fail-safe 回退既有 subject-based 判斷，不可將 None 當作「已過濾
    為空」處理。
    """
    args = ["log", "--format=%H", "--no-merges", "--", ".claude/"]
    if since:
        args.insert(2, f"--since={since}")
    result = run_git(args, cwd=project_root, check=False)
    if result.returncode != 0:
        return None
    if not result.stdout.strip():
        return []
    hashes = [line.strip() for line in result.stdout.strip().split("\n") if line.strip()]
    return [
        commit_sha
        for commit_sha in hashes
        if not _commit_touches_only_version_file(project_root, commit_sha)
    ]


def _normalize_subject_for_match(subject: str) -> str:
    """正規化 commit subject 用於 revert 配對比對。

    移除 conventional prefix（type(scope):）後 strip + lower，
    讓 `chore(<ticket-id>): migrate X` 與 `revert(<ticket-id>): migrate X`
    的 description 可正確配對。
    """
    # 剝 conventional prefix
    m = re.match(r"^\w+(?:\([^)]*\))?:\s*(.+)", subject)
    body = m.group(1).strip() if m else subject.strip()
    # 剝外圍引號
    inner = re.match(r'^"(.+)"\s*$', body)
    if inner:
        body = inner.group(1).strip()
    return body.lower()


def categorize_commits(subjects: list[str]) -> dict[str, list[str]]:
    """Categorize commit subjects by conventional commit type.

    淨效應邏輯：若同批 commits 同時含 X 與 revert(X)（X 為任意 type），
    則 X 不列入 categories（被 revert 抵銷），僅保留 revert 行並在
    description 末尾標註被撤回的原 commit。

    Returns dict mapping type -> list of descriptions.
    """
    # Step 1: 先掃描所有 revert，建立 (normalized_original) -> revert_index map
    reverted_originals: dict[str, str] = {}  # normalized_subject -> original_ref
    revert_entries: list[tuple[str, str, str]] = []  # (original_subject, original_ref, raw_subject)
    non_revert_subjects: list[tuple[str, str]] = []  # (commit_type, description) for non-revert

    for subject in subjects:
        info = parse_revert_info(subject)
        if info is not None:
            original_subject, original_ref = info
            revert_entries.append((original_subject, original_ref, subject))
            reverted_originals[_normalize_subject_for_match(original_subject)] = original_ref
        else:
            commit_type, description = parse_commit_type(subject)
            non_revert_subjects.append((commit_type, description))

    categories: dict[str, list[str]] = defaultdict(list)

    # Step 2: 加入 non-revert，跳過被 revert 抵銷的
    for commit_type, description in non_revert_subjects:
        norm = _normalize_subject_for_match(f"{commit_type}: {description}")
        if norm in reverted_originals:
            # 被同批 revert 抵銷，跳過
            continue
        cleaned = strip_project_specific_info(description)
        if cleaned:
            categories[commit_type].append(cleaned)

    # Step 3: 加入 revert 行，附註原 commit ref
    for original_subject, original_ref, _raw in revert_entries:
        cleaned_original = strip_project_specific_info(original_subject)
        # ticket ID 樣式的 ref（版本化或裸格式）屬 consumer 專屬識別符，
        # 不可寫入 CHANGELOG（經 sync-push 擴散至獨立 repo 後，會觸發每個
        # consumer 自己的 reference-stability rule8 守衛）；commit hash
        # 不受影響，仍保留供追溯。
        safe_ref = "" if _is_project_specific_ref(original_ref) else original_ref
        if safe_ref:
            desc = f"{cleaned_original} (原 commit: {safe_ref})" if cleaned_original else f"revert {safe_ref}"
        else:
            desc = f"{cleaned_original} (原 commit)" if cleaned_original else "revert (原 commit 細節省略)"
        categories["revert"].append(desc)

    return dict(categories)


def suggest_version_bump(categories: dict[str, list[str]]) -> str:
    """Suggest version bump level based on commit types.

    Returns "major", "minor", or "patch".
    """
    has_minor = False
    for commit_type in categories:
        bump = VERSION_BUMP_WEIGHTS.get(commit_type, "patch")
        if bump == "major":
            return "major"
        if bump == "minor":
            has_minor = True
    return "minor" if has_minor else "patch"


def generate_commit_summary(categories: dict[str, list[str]], bump_suggestion: str) -> str:
    """Generate a structured commit message from categorized commits.

    The first line is always a descriptive summary suitable for git commit subject.
    Additional detail lines follow after a blank line.
    """
    display_order = ["revert", "feat", "refactor", "fix", "docs", "chore", "style", "test", "perf", "other"]

    # Collect all unique descriptions with their types, preserving order
    all_items: list[tuple[str, str]] = []
    for t in display_order:
        if t not in categories:
            continue
        for desc in dict.fromkeys(categories[t]):
            all_items.append((t, desc))

    total_count = len(all_items)

    # First line: descriptive summary (not just counts)
    # Few commits (1-3): list actual descriptions joined by "; "
    # Many commits (4+): highlight top items with count context
    MAX_SUBJECT_ITEMS = 3
    if total_count <= MAX_SUBJECT_ITEMS:
        subject_parts = [f"{t}: {desc}" for t, desc in all_items]
        summary_line = "; ".join(subject_parts)
    else:
        # Show first few items + count of remaining
        shown_parts = [f"{t}: {desc}" for t, desc in all_items[:MAX_SUBJECT_ITEMS]]
        remaining = total_count - MAX_SUBJECT_ITEMS
        summary_line = "; ".join(shown_parts) + f" (+{remaining} more)"

    # Build detail lines for body (all items)
    details: list[str] = []
    for t, desc in all_items:
        details.append(f"- {t}: {desc}")

    # Stats line for context
    type_counts = []
    for t in display_order:
        if t in categories:
            type_counts.append(f"{len(categories[t])} {t}")
    stats = ", ".join(type_counts)

    body_parts = [f"Changes: {stats}"]
    if details:
        body_parts.append("")
        body_parts.extend(details)

    return f"{summary_line}\n\n" + "\n".join(body_parts)
