"""Tests for sync-claude-pull.py 大小寫不敏感檔案系統下的刪除防護。

背景（2026-08 P0 事故）：下游消費專案執行 sync-pull 後，三個 skill 入口檔在工作區
消失（git 顯示三筆刪除），事後以 sha256 比對確認無內容遺失（可從 HEAD 還原），但屬
實際資料刪除。受控實驗（隔離 fixture repo，四種組合 x 兩種 upstream 大小寫，共 8
組）證實：cleanup_stale_files 對 rel 不在 remote_files 集合的檔案，於 git 未追蹤時
直接 unlink；_is_git_tracked 用 `git ls-files --error-unmatch` 查詢，其 pathspec
比對固定為大小寫敏感（即使 core.ignorecase=true 亦不受影響，已用裸 git 指令驗證），
而查詢用的路徑字串來自「磁碟 dirent」（cleanup_stale_files._walk 的 item.name），
非 git index 的實際條目名稱。當「本地磁碟大小寫」同時偏離「本地 git index 大小寫」
與「上游大小寫」時，_is_git_tracked 誤判為未追蹤，安全網被繞過，已追蹤內容遭
unlink 而非移至 .sync-conflicts/。

實驗證實觸發條件精確式：DELETED iff (磁碟大小寫 != 上游大小寫) 且
(磁碟大小寫 != 本地 index 大小寫)。原票面假說「僅 index 與磁碟不一致」不足以
解釋刪除（該假說描述的組合 index=lower/disk=upper/upstream=upper 實測不刪除，
因磁碟大小寫恰好與上游一致而完全不觸發 stale 判定）；真正觸發需磁碟大小寫同時
偏離另外兩者。修復：_is_git_tracked 於 exact match 失敗時，改列出同目錄下的
git 追蹤條目做大小寫不敏感 fallback 比對。

本檔後半另收錄第二條獨立的刪除路徑（0.2.1-W3-1155）：三方合併路徑
（apply_upstream_delta）在 base..upstream 之間存在純大小寫改名時，
--no-renames 拆出的 D+A 配對，其 D 半邊以路徑字串構造 local_file 在大小寫
不敏感檔案系統上誤刪 A 半邊對應的實體檔。觸發變數與上述 cleanup_stale_files
路徑不同（見「三方合併路徑」段落），兩組測試互不取代，須同時涵蓋。

本檔末段另收錄第三條路徑（0.2.1-W3-1142）：反向孤兒偵測
（compute_reverse_orphan_candidates）以逐字元集合差集比對本地與上游檔名，
上游為 SKILL.md、本地為 skill.md（或反之）時被誤判為「本地缺漏」，並建議
補齊——若消費端剛完成大小寫修復，照建議補齊會把修復抵銷。此路徑不涉及
unlink（訊息層缺陷，非刪除路徑），但與前兩條共用「大小寫比對未考慮不敏感
檔案系統」的根因家族，修法重用本檔已建立的 _find_case_variant_dirent。
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

# sync-claude-pull.py 含連字符且 shebang 為 uv script，須以 importlib 載入
_SCRIPT = Path(__file__).resolve().parent.parent / "sync-claude-pull.py"
_spec = importlib.util.spec_from_file_location("sync_claude_pull_case_mismatch", _SCRIPT)
assert _spec and _spec.loader
sync_mod = importlib.util.module_from_spec(_spec)
sys.modules["sync_claude_pull_case_mismatch"] = sync_mod
_spec.loader.exec_module(sync_mod)  # type: ignore[union-attr]


def _run(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    result = subprocess.run(args, cwd=cwd, capture_output=True, text=True)
    assert result.returncode == 0, (
        f"cmd failed: {args} in {cwd}\nSTDOUT:{result.stdout}\nSTDERR:{result.stderr}"
    )
    return result


def _init_git_repo(root: Path) -> None:
    _run(["git", "init", "-q"], root)
    _run(["git", "config", "user.email", "t@example.com"], root)
    _run(["git", "config", "user.name", "test"], root)


def _make_local_repo(root: Path, index_case: str, disk_case: str, content: bytes) -> Path:
    """建立本地（受影響端）fixture repo：index 與磁碟大小寫可獨立設定。

    磁碟建 disk_case 名稱的真實檔案；git index 用
    `update-index --add --cacheinfo` 直接寫入 index_case 名稱的條目（不觸碰磁碟），
    模擬案例級大小寫改名只更新 index、未真正改寫磁碟 dirent 的長期分歧狀態
    （macOS/APFS 等大小寫不敏感檔案系統的 case-preserving 特性下可自然發生）。
    """
    claude_dir = root / ".claude"
    skill_dir = claude_dir / "skills" / "foo"
    skill_dir.mkdir(parents=True)

    disk_name = "SKILL.md" if disk_case == "upper" else "skill.md"
    index_name = "SKILL.md" if index_case == "upper" else "skill.md"

    disk_path = skill_dir / disk_name
    disk_path.write_bytes(content)

    _init_git_repo(root)
    blob_sha = _run(
        ["git", "hash-object", "-w", str(disk_path.relative_to(root))], root
    ).stdout.strip()
    index_rel = f".claude/skills/foo/{index_name}"
    _run(
        ["git", "update-index", "--add", "--cacheinfo", f"100644,{blob_sha},{index_rel}"],
        root,
    )
    _run(["git", "commit", "-q", "-m", "setup fixture"], root)
    return claude_dir


def _make_remote_src(root: Path, case: str, content: bytes) -> Path:
    """建立上游樹：index 與磁碟一致（新鮮 clone 天然一致，非本測試變數）。"""
    claude_dir = root / ".claude"
    skill_dir = claude_dir / "skills" / "foo"
    skill_dir.mkdir(parents=True)
    name = "SKILL.md" if case == "upper" else "skill.md"
    (skill_dir / name).write_bytes(content)
    return claude_dir


CASE_COMBINATIONS = [
    ("lower", "lower", "upper"),
    ("lower", "upper", "upper"),
    ("upper", "lower", "upper"),
    ("upper", "upper", "upper"),
    ("lower", "lower", "lower"),
    ("lower", "upper", "lower"),
    ("upper", "lower", "lower"),
    ("upper", "upper", "lower"),
]


@pytest.mark.parametrize("index_case,disk_case,upstream_case", CASE_COMBINATIONS)
def test_case_mismatch_never_deletes_tracked_file(
    tmp_path: Path, index_case: str, disk_case: str, upstream_case: str
) -> None:
    """四組（index x disk）在兩種 upstream 大小寫下皆不得刪除已追蹤的 skill 入口檔。

    驗收條件：檔案內容須存活於本地磁碟上（不論最終落在原路徑或
    .sync-conflicts/），任何組合都不得觸發 unlink。
    """
    content = b"skill entry content\n"
    local_claude = _make_local_repo(tmp_path / "local", index_case, disk_case, content)
    remote_claude = _make_remote_src(tmp_path / "remote", upstream_case, content)

    remote_files = sync_mod.collect_remote_files(remote_claude)
    removed, preserved_as_conflict = sync_mod.cleanup_stale_files(
        local_claude, remote_files, preserve=set(), project_root=tmp_path / "local"
    )

    non_empty_removed = [r for r in removed if "(empty dir)" not in r]
    assert not non_empty_removed, (
        f"不應刪除已追蹤檔（index={index_case}, disk={disk_case}, "
        f"upstream={upstream_case}）：removed={removed}"
    )

    # 內容須存活：原路徑存在，或已移至 .sync-conflicts/
    survives_in_place = any(local_claude.rglob("*.md"))
    survives_in_conflicts = bool(preserved_as_conflict)
    assert survives_in_place or survives_in_conflicts, (
        f"檔案內容必須存活於磁碟（index={index_case}, disk={disk_case}, "
        f"upstream={upstream_case}）"
    )


def test_is_git_tracked_case_insensitive_fallback(tmp_path: Path) -> None:
    """_is_git_tracked 對「查詢路徑大小寫」與「index 條目大小寫」不一致時仍須回 True。

    直接針對修復的函式做單元級驗證：exact match 失敗（大小寫不同）時，
    fallback 列出同目錄 git 追蹤條目做大小寫不敏感比對。
    """
    root = tmp_path
    claude_dir = root / ".claude"
    skill_dir = claude_dir / "skills" / "foo"
    skill_dir.mkdir(parents=True)
    disk_path = skill_dir / "skill.md"
    disk_path.write_bytes(b"content\n")

    _init_git_repo(root)
    blob_sha = _run(
        ["git", "hash-object", "-w", str(disk_path.relative_to(root))], root
    ).stdout.strip()
    _run(
        [
            "git", "update-index", "--add", "--cacheinfo",
            f"100644,{blob_sha},.claude/skills/foo/SKILL.md",
        ],
        root,
    )
    _run(["git", "commit", "-q", "-m", "setup"], root)

    # 查詢用磁碟案例（lower），但 index 條目是 upper（模擬 _walk 傳入的路徑來源）
    assert sync_mod._is_git_tracked(
        ".claude/skills/foo/skill.md", root
    ), "大小寫不同但同名（fold 後相等）的 index 條目應被判定為已追蹤"


def test_is_git_tracked_still_false_for_genuinely_untracked(tmp_path: Path) -> None:
    """回歸保護：fallback 不可讓真正未追蹤的檔被誤判為已追蹤。"""
    root = tmp_path
    claude_dir = root / ".claude"
    skill_dir = claude_dir / "skills" / "foo"
    skill_dir.mkdir(parents=True)
    (skill_dir / "other.md").write_bytes(b"content\n")

    _init_git_repo(root)
    _run(["git", "commit", "-q", "-m", "empty", "--allow-empty"], root)

    assert not sync_mod._is_git_tracked(
        ".claude/skills/foo/other.md", root
    ), "未追蹤檔不應因 fallback 誤判為已追蹤"


# ---------------------------------------------------------------------------
# 三方合併路徑（apply_upstream_delta）的純大小寫改名誤刪
#
# 背景（0.2.1-W3-1155）：compute_upstream_delta 用 --no-renames，使上游純
# 大小寫改名（skill.md -> SKILL.md）拆為獨立的 D(舊路徑) + A(新路徑) 兩筆
# delta。apply_upstream_delta 逐檔處理 D 半邊時以路徑字串構造 local_file，
# 在大小寫不敏感檔案系統上該路徑會解析到 A 半邊對應的實體檔案，
# three_way_merge_file 判定「本地未改、跟隨上游刪除」後 _atomic_remove
# 直接 unlink，刪掉的其實是應保留（改名後）的檔案。
#
# 觸發變數與 test_case_mismatch_never_deletes_tracked_file（上方，
# cleanup_stale_files 全量 overlay 路徑）不同：該組測試的變數是磁碟/index/
# 上游三者的大小寫組合，觸發面是 cleanup_stale_files 的 stale 判定；本組
# 測試的變數是 base..upstream 之間是否存在純大小寫改名，觸發面是
# apply_upstream_delta 的三方合併 delta 套用，兩者互不取代，須同時涵蓋。
# ---------------------------------------------------------------------------


def _make_upstream_case_rename_repo(root: Path, content: bytes) -> tuple[Path, str]:
    """建立上游 repo：base commit 含 skill.md（小寫），HEAD commit 純大小寫
    改名為 SKILL.md（大寫），內容不變。

    HEAD 的改名以 git plumbing（hash-object + update-index --cacheinfo）直接
    操作 index，不依賴實際檔案系統 rename 是否大小寫敏感——git diff /
    git show 讀的是 tree 物件，不受工作目錄殘留檔案的大小寫影響，測試結果
    因此不受執行環境檔案系統大小寫敏感度左右。

    傳回:
        tuple[Path, str]: (上游 repo 根目錄, base commit sha)
    """
    skill_dir = root / "skills" / "foo"
    skill_dir.mkdir(parents=True)
    _init_git_repo(root)
    lower_path = skill_dir / "skill.md"
    lower_path.write_bytes(content)
    _run(["git", "add", "."], root)
    _run(["git", "commit", "-q", "-m", "base: skill.md"], root)
    base_sha = _run(["git", "rev-parse", "HEAD"], root).stdout.strip()

    blob_sha = _run(
        ["git", "hash-object", str(lower_path.relative_to(root))], root
    ).stdout.strip()
    _run(["git", "rm", "--cached", "-q", "skills/foo/skill.md"], root)
    _run(
        [
            "git", "update-index", "--add", "--cacheinfo",
            f"100644,{blob_sha},skills/foo/SKILL.md",
        ],
        root,
    )
    _run(["git", "commit", "-q", "-m", "rename: skill.md -> SKILL.md"], root)
    return root, base_sha


def _make_local_disk_only(root: Path, filename: str, content: bytes) -> Path:
    """建立本地磁碟（無 git）：僅在磁碟寫入指定大小寫的檔案。"""
    claude_dir = root / ".claude"
    skill_dir = claude_dir / "skills" / "foo"
    skill_dir.mkdir(parents=True)
    (skill_dir / filename).write_bytes(content)
    return claude_dir


def test_case_only_rename_does_not_delete_local_file(tmp_path: Path) -> None:
    """純大小寫改名（base 有 skill.md、upstream 改名為 SKILL.md）套用三方合併
    delta 後，本地大寫檔案須存活且內容正確，不得被誤刪。

    這是本票的最小重現：修復前，此斷言於大小寫不敏感檔案系統上會失敗
    （檔案被 _atomic_remove 誤刪）。
    """
    content = b"skill entry content\n"
    upstream_root, base_sha = _make_upstream_case_rename_repo(
        tmp_path / "upstream", content
    )
    local_claude = _make_local_disk_only(tmp_path / "local", "SKILL.md", content)
    project_root = tmp_path / "local"

    applied, conflicts, residue = sync_mod.apply_upstream_delta(
        project_root, upstream_root, base_sha, preserve=set(), skills_config=None
    )

    assert not conflicts, f"純大小寫改名不應產生衝突：{conflicts}"
    assert not residue
    target = local_claude / "skills" / "foo" / "SKILL.md"
    assert target.exists(), "改名後的大寫檔案必須存活於磁碟"
    assert target.read_bytes() == content, "內容不得因改名套用而遺失或損毀"
    assert applied == 1


def test_case_only_rename_repeated_pull_does_not_redelete(tmp_path: Path) -> None:
    """base SHA 推進至改名後的 commit 後，再次套用 delta 不應重複刪除。

    模擬 pull 主流程「無衝突則推進 base SHA」後的下一次 pull：以推進後的
    base（= upstream HEAD）重算 delta 應為空集合，不再觸發任何 unlink。
    """
    content = b"skill entry content\n"
    upstream_root, base_sha = _make_upstream_case_rename_repo(
        tmp_path / "upstream", content
    )
    local_claude = _make_local_disk_only(tmp_path / "local", "SKILL.md", content)
    project_root = tmp_path / "local"

    sync_mod.apply_upstream_delta(
        project_root, upstream_root, base_sha, preserve=set(), skills_config=None
    )
    head_sha = _run(["git", "rev-parse", "HEAD"], upstream_root).stdout.strip()

    applied_2, conflicts_2, residue_2 = sync_mod.apply_upstream_delta(
        project_root, upstream_root, head_sha, preserve=set(), skills_config=None
    )

    assert applied_2 == 0, "base 已推進過改名點，重放同一份 delta 不應再套用任何變更"
    assert not conflicts_2
    assert not residue_2
    target = local_claude / "skills" / "foo" / "SKILL.md"
    assert target.exists(), "第二次 pull 不應重複刪除已改名的檔案"
    assert target.read_bytes() == content


def test_detect_case_only_renames_pairs_d_and_a() -> None:
    """_detect_case_only_renames 直接單元測試：純大小寫差異的 D+A 應配對。"""
    delta = {
        "skills/foo/skill.md": "D",
        "skills/foo/SKILL.md": "A",
        "rules/unrelated.md": "M",
    }
    renames = sync_mod._detect_case_only_renames(delta)
    assert renames == {"skills/foo/SKILL.md": "skills/foo/skill.md"}


def test_detect_case_only_renames_ignores_ambiguous_group() -> None:
    """同一 lower() 對應多個 D 或 A 時保守略過，不誤配對。"""
    delta = {
        "skills/foo/skill.md": "D",
        "skills/foo/Skill.md": "D",
        "skills/foo/SKILL.md": "A",
    }
    renames = sync_mod._detect_case_only_renames(delta)
    assert renames == {}


def test_detect_case_only_renames_ignores_content_add_delete_pair() -> None:
    """路徑大小寫不同但非「同一路徑僅差大小寫」以外的一般 D/A 不應被誤配。"""
    delta = {
        "skills/foo/old.md": "D",
        "skills/bar/new.md": "A",
    }
    assert sync_mod._detect_case_only_renames(delta) == {}


def test_find_case_variant_dirent_returns_real_name(tmp_path: Path) -> None:
    """_find_case_variant_dirent 以 os.scandir 回傳真實 dirent 名稱，不受
    查詢字串大小寫影響。"""
    skill_dir = tmp_path / "skills" / "foo"
    skill_dir.mkdir(parents=True)
    (skill_dir / "skill.md").write_bytes(b"x")

    assert sync_mod._find_case_variant_dirent(skill_dir, "SKILL.md") == "skill.md"
    assert sync_mod._find_case_variant_dirent(skill_dir, "skill.md") == "skill.md"


def test_find_case_variant_dirent_returns_none_when_absent(tmp_path: Path) -> None:
    """目錄下無任何大小寫變體時回 None。"""
    skill_dir = tmp_path / "skills" / "foo"
    skill_dir.mkdir(parents=True)
    assert sync_mod._find_case_variant_dirent(skill_dir, "SKILL.md") is None


def test_detect_pending_case_renames_lists_new_path(tmp_path: Path) -> None:
    """自檢函式 detect_pending_case_renames：偵測到待套用的純大小寫改名時，
    回傳新路徑清單（唯讀，不套用、不寫入本地檔）。"""
    content = b"skill entry content\n"
    upstream_root, base_sha = _make_upstream_case_rename_repo(
        tmp_path / "upstream", content
    )

    pending = sync_mod.detect_pending_case_renames(upstream_root, base_sha)

    assert pending == ["skills/foo/SKILL.md"]


def test_detect_pending_case_renames_empty_when_no_rename(tmp_path: Path) -> None:
    """base 與 HEAD 之間無變更時，自檢函式回空清單（不誤報）。"""
    root = tmp_path / "upstream"
    skill_dir = root / "skills" / "foo"
    skill_dir.mkdir(parents=True)
    _init_git_repo(root)
    (skill_dir / "SKILL.md").write_bytes(b"content\n")
    _run(["git", "add", "."], root)
    _run(["git", "commit", "-q", "-m", "no rename"], root)
    base_sha = _run(["git", "rev-parse", "HEAD"], root).stdout.strip()

    assert sync_mod.detect_pending_case_renames(root, base_sha) == []


# ---------------------------------------------------------------------------
# 反向孤兒偵測命中大小寫變體時的誤導性補齊建議（0.2.1-W3-1142）
# ---------------------------------------------------------------------------


def test_classify_reverse_orphans_separates_case_variant_from_genuine_missing(
    tmp_path: Path,
) -> None:
    """_classify_reverse_orphans_by_case：本地有大小寫變體者歸類為
    case_variant_pairs，本地完全無對應內容者歸類為 genuinely_missing。"""
    claude_dir = tmp_path / ".claude"
    skill_dir = claude_dir / "skills" / "foo"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_bytes(b"content\n")  # 大小寫變體：上游 skill.md

    reverse_orphans = [
        "skills/foo/skill.md",  # 本地有 SKILL.md（大小寫變體）
        "rules/truly-missing.md",  # 本地完全無對應內容
    ]

    genuinely_missing, case_variant_pairs = sync_mod._classify_reverse_orphans_by_case(
        claude_dir, reverse_orphans
    )

    assert genuinely_missing == ["rules/truly-missing.md"]
    assert case_variant_pairs == [("skills/foo/skill.md", "skills/foo/SKILL.md")]


def test_classify_reverse_orphans_all_genuine_when_no_case_variant(
    tmp_path: Path,
) -> None:
    """本地完全無任何大小寫變體時，全部歸類為 genuinely_missing。"""
    claude_dir = tmp_path / ".claude"
    (claude_dir / "rules").mkdir(parents=True)

    genuinely_missing, case_variant_pairs = sync_mod._classify_reverse_orphans_by_case(
        claude_dir, ["rules/a.md", "rules/b.md"]
    )

    assert genuinely_missing == ["rules/a.md", "rules/b.md"]
    assert case_variant_pairs == []


def test_print_reverse_orphans_case_variant_does_not_suggest_fill_in(
    tmp_path: Path, capsys
) -> None:
    """_print_reverse_orphans：大小寫變體改述為「不建議補齊」，不落入紅色
    「本地缺漏」警示，且不含舊版「補齊」建議措辭。"""
    claude_dir = tmp_path / ".claude"
    skill_dir = claude_dir / "skills" / "foo"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_bytes(b"content\n")

    sync_mod._print_reverse_orphans(claude_dir, ["skills/foo/skill.md"])

    out = capsys.readouterr().out
    assert "大小寫不一致" in out
    assert "不建議補齊" in out
    assert "本地缺漏" not in out
    assert "[警示]" not in out


def test_print_reverse_orphans_genuine_missing_keeps_alert_wording(
    tmp_path: Path, capsys
) -> None:
    """_print_reverse_orphans：真缺漏（無任何大小寫變體）維持既有 [警示] 措辭。"""
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir(parents=True)

    sync_mod._print_reverse_orphans(claude_dir, ["rules/truly-missing.md"])

    out = capsys.readouterr().out
    assert "[警示]" in out
    assert "本地缺漏" in out
    assert "truly-missing.md" in out
    assert "大小寫不一致" not in out


def test_main_flow_reverse_orphan_case_variant_not_flagged_as_missing(
    tmp_path: Path, capsys
) -> None:
    """端到端（主 pull 流程）：base == HEAD（無 delta 需套用），上游檔名為
    SKILL.md、本地磁碟仍是 skill.md（歷史大小寫分歧，非本次 pull 造成）時，
    反向孤兒提醒不得把它列為需要 [警示] 的本地缺漏，也不得建議補齊回小寫。
    """
    content = b"skill entry content\n"
    upstream_root = tmp_path / "upstream"
    skill_dir = upstream_root / "skills" / "foo"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_bytes(content)
    _init_git_repo(upstream_root)
    _run(["git", "add", "."], upstream_root)
    _run(["git", "commit", "-q", "-m", "upstream head"], upstream_root)
    base_sha = _run(["git", "rev-parse", "HEAD"], upstream_root).stdout.strip()

    project_root = tmp_path / "local"
    local_claude = project_root / ".claude"
    local_skill_dir = local_claude / "skills" / "foo"
    local_skill_dir.mkdir(parents=True)
    (local_skill_dir / "skill.md").write_bytes(content)  # 本地仍為歷史小寫
    (local_claude / ".sync-state.json").write_text(
        f'{{"last_synced_base_sha": "{base_sha}"}}', encoding="utf-8"
    )

    sync_mod._sync_with_backup(project_root, upstream_root)

    out = capsys.readouterr().out
    assert "本地缺漏" not in out, f"大小寫變體不應被列為本地缺漏：{out}"
    assert "不建議補齊" in out, f"應明確標示不建議補齊：{out}"
    assert "可能需要" not in out, f"不應出現舊版誤導性補齊建議措辭：{out}"
    assert "大小寫不一致" in out, f"應改述為大小寫不一致：{out}"
    assert (local_skill_dir / "skill.md").exists(), "本地原檔不應被本次 pull 動到"


# ---------------------------------------------------------------------------
# 正向孤兒稽核命中大小寫變體時的誤導性移除建議（0.2.1-W3-1161）
# ---------------------------------------------------------------------------


def test_classify_orphans_separates_case_variant_from_genuine_orphan(
    tmp_path: Path,
) -> None:
    """_classify_orphans_by_case：上游有大小寫變體者歸類為 case_variant_pairs，
    上游完全無對應內容者歸類為 genuinely_orphan。"""
    upstream_dir = tmp_path / "upstream"
    skill_dir = upstream_dir / "skills" / "foo"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_bytes(b"content\n")  # 大小寫變體：本地 skill.md

    orphans = [
        "skills/foo/skill.md",  # 上游有 SKILL.md（大小寫變體）
        "rules/truly-orphan.md",  # 上游完全無對應內容
    ]

    genuinely_orphan, case_variant_pairs = sync_mod._classify_orphans_by_case(
        upstream_dir, orphans
    )

    assert genuinely_orphan == ["rules/truly-orphan.md"]
    assert case_variant_pairs == [("skills/foo/skill.md", "skills/foo/SKILL.md")]


def test_classify_orphans_all_genuine_when_no_case_variant(tmp_path: Path) -> None:
    """上游完全無任何大小寫變體時，全部歸類為 genuinely_orphan。"""
    upstream_dir = tmp_path / "upstream"
    (upstream_dir / "rules").mkdir(parents=True)

    genuinely_orphan, case_variant_pairs = sync_mod._classify_orphans_by_case(
        upstream_dir, ["rules/a.md", "rules/b.md"]
    )

    assert genuinely_orphan == ["rules/a.md", "rules/b.md"]
    assert case_variant_pairs == []


def test_print_orphan_audit_case_variant_fallback_path_does_not_suggest_removal(
    tmp_path: Path, capsys
) -> None:
    """_print_orphan_audit：base sha 缺失（fallback 分支）下，大小寫變體改述
    為不建議手動移除，不落入「請手動移除」建議。"""
    upstream_dir = tmp_path / "upstream"
    skill_dir = upstream_dir / "skills" / "foo"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_bytes(b"content\n")

    sync_mod._print_orphan_audit(upstream_dir, ["skills/foo/skill.md"], None, None)

    out = capsys.readouterr().out
    assert "大小寫不一致" in out
    assert "不建議手動移除" in out
    assert "請手動移除" not in out


def test_print_orphan_audit_case_variant_split_path_does_not_suggest_removal(
    tmp_path: Path, capsys
) -> None:
    """_print_orphan_audit：base sha 可達（split 分支）下，大小寫變體改述為
    不建議手動移除，不落入「可手動移除」建議，也不落入將刪除/將保留分組。"""
    upstream_dir = tmp_path / "upstream"
    skill_dir = upstream_dir / "skills" / "foo"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_bytes(b"content\n")

    sync_mod._print_orphan_audit(
        upstream_dir, ["skills/foo/skill.md"], "deadbeef", set()
    )

    out = capsys.readouterr().out
    assert "大小寫不一致" in out
    assert "不建議手動移除" in out
    assert "可手動移除" not in out
    assert "將被刪除" not in out
    assert "將保留" not in out


def test_print_orphan_audit_genuine_orphan_keeps_existing_wording(
    tmp_path: Path, capsys
) -> None:
    """_print_orphan_audit：真孤兒（無任何大小寫變體）維持既有分組措辭不變。"""
    upstream_dir = tmp_path / "upstream"
    upstream_dir.mkdir(parents=True)

    sync_mod._print_orphan_audit(upstream_dir, ["rules/truly-orphan.md"], None, None)

    out = capsys.readouterr().out
    assert "孤兒候選" in out
    assert "請手動移除" in out
    assert "大小寫不一致" not in out


def test_run_audit_forward_orphan_case_variant_does_not_suggest_manual_removal(
    tmp_path: Path, capsys, monkeypatch
) -> None:
    """端到端 --audit（run_audit）：本地為歷史小寫、上游為大寫的同名檔，
    正向孤兒稽核不得建議手動移除（會刪除本地與上游同名、僅大小寫不同的
    正常檔案）。"""
    content = b"skill entry content\n"
    project_root = tmp_path / "local"
    local_claude = project_root / ".claude"
    local_skill_dir = local_claude / "skills" / "foo"
    local_skill_dir.mkdir(parents=True)
    (local_skill_dir / "skill.md").write_bytes(content)  # 本地仍為歷史小寫

    def _fake_clone(temp_dir: Path) -> None:
        temp_dir.mkdir(parents=True, exist_ok=True)
        (temp_dir / "skills" / "foo").mkdir(parents=True)
        (temp_dir / "skills" / "foo" / "SKILL.md").write_bytes(content)

    monkeypatch.setattr(sync_mod, "find_project_root", lambda: project_root)
    monkeypatch.setattr(sync_mod, "clone_repo", _fake_clone)

    sync_mod.run_audit()

    out = capsys.readouterr().out
    assert "skill.md" in out
    assert "大小寫不一致" in out
    assert "不建議手動移除" in out
    assert "請手動移除" not in out, f"不應建議手動移除大小寫變體：{out}"
    assert (local_skill_dir / "skill.md").exists()
