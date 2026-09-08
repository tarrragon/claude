"""section_comment.py 測試：init（兩階段）/ update（precision PATCH）/ observe。

全程以 mock 攔截 gh subprocess，不真打 GitHub API（`preflight()` 亦以
monkeypatch 直接繞過，同 test_framework_issue.py 慣例）。
"""

import json
import subprocess
import sys
from pathlib import Path
from unittest import mock

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import gh_common  # noqa: E402
import section_comment  # noqa: E402


def _completed(returncode=0, stdout="", stderr=""):
    return subprocess.CompletedProcess(
        args=["gh"], returncode=returncode, stdout=stdout, stderr=stderr
    )


@pytest.fixture(autouse=True)
def _bypass_preflight(monkeypatch):
    """所有測試皆不需真正檢查 gh 安裝/登入狀態，僅降級路徑測試單獨覆蓋。"""
    monkeypatch.setattr(gh_common, "check_gh_available", lambda: True)
    monkeypatch.setattr(gh_common, "check_gh_authenticated", lambda: True)


@pytest.fixture(autouse=True)
def _stub_owned_issues_registry(monkeypatch):
    """owned-issues 登記檔寫入為 init／update 成功路徑新增的旁路 side
    effect，非本檔案既有測試的驗證焦點；預設 stub 為 no-op，避免其內部
    `git rev-parse` 呼叫被既有 `_run` side_effect 函式判為「未預期的 gh
    呼叫」而炸開（`mock.patch.object(section_comment.subprocess, "run",
    ...)` patch 的是共用 subprocess 模組，owned_issues_registry 的呼叫
    亦會被攔截）。「owned-issues 登記檔寫入」節的專屬測試另行覆蓋以驗證
    呼叫參數。"""
    monkeypatch.setattr(section_comment, "record_owned_issue", lambda *a, **k: None)


# --- 純函式：標記渲染與抽取 ---


def test_render_section_comment_marker_is_first_line():
    rendered = section_comment.render_section_comment("當前結論", "flutter-balance-99", "內容")
    assert rendered.startswith(
        "<!-- section: 當前結論 owner: flutter-balance-99 -->\n"
    )
    assert rendered.endswith("內容")


def test_render_observation_comment_marker_is_first_line():
    rendered = section_comment.render_observation_comment("實測結果", "session-a", "觀測內容")
    assert rendered.startswith("<!-- observation: 實測結果 by session-a -->\n")


def test_extract_section_marker_handles_owner_with_hyphens():
    """owner 常含連字號（如 flutter-balance-99），非貪婪比對不可誤在第一個連字號處截斷。"""
    body = "<!-- section: 當前結論 owner: flutter-balance-99 -->\n## 內容"
    marker = section_comment.extract_section_marker(body)
    assert marker == {"name": "當前結論", "owner": "flutter-balance-99"}


def test_extract_section_marker_returns_none_for_observation_comment():
    """觀測 comment 首行為 observation: 標記，不得被誤判為區段（acceptance 條款）。"""
    body = "<!-- observation: 實測結果 by session-a -->\n內容"
    assert section_comment.extract_section_marker(body) is None


def test_extract_section_marker_returns_none_for_plain_comment():
    assert section_comment.extract_section_marker("一般留言，無標記") is None


def test_render_index_includes_permalink_table():
    posted = [
        {"name": "當前結論", "html_url": "https://github.com/tarrragon/claude/issues/81#issuecomment-1"},
        {"name": "方案評估", "html_url": "https://github.com/tarrragon/claude/issues/81#issuecomment-2"},
    ]
    rendered = section_comment.render_index(posted)
    assert rendered.startswith(section_comment.INDEX_BEGIN)
    assert rendered.endswith(section_comment.INDEX_END)
    assert "| 當前結論 | https://github.com/tarrragon/claude/issues/81#issuecomment-1 |" in rendered
    assert "| 方案評估 | https://github.com/tarrragon/claude/issues/81#issuecomment-2 |" in rendered


def test_render_index_table_renders_name_url_rows():
    rows = [
        {"name": "當前結論", "url": "https://github.com/tarrragon/claude/issues/81#issuecomment-1"},
        {"name": "方案評估", "url": "https://github.com/tarrragon/claude/issues/81#issuecomment-2"},
    ]
    rendered = section_comment.render_index_table(rows)
    assert rendered.startswith(section_comment.INDEX_BEGIN)
    assert rendered.endswith(section_comment.INDEX_END)
    assert "| 當前結論 | https://github.com/tarrragon/claude/issues/81#issuecomment-1 |" in rendered
    assert "| 方案評估 | https://github.com/tarrragon/claude/issues/81#issuecomment-2 |" in rendered


# --- validate_owner：init/add/transfer-owner 共用的 owner 格式驗證 ---


def test_validate_owner_accepts_kebab_prefix_with_numeric_suffix():
    section_comment.validate_owner("flutter-balance-77")  # 不拋例外即通過


def test_validate_owner_rejects_agent_name_without_numeric_suffix():
    with pytest.raises(ValueError, match="owner 格式不符"):
        section_comment.validate_owner("framework-issue-curator")


def test_validate_owner_rejects_underscore_separated_form():
    with pytest.raises(ValueError, match="owner 格式不符"):
        section_comment.validate_owner("flutter_balance-pm")


def test_load_sections_spec_rejects_missing_content_field(tmp_path):
    spec_file = tmp_path / "sections.json"
    spec_file.write_text(json.dumps([{"name": "當前結論"}]), encoding="utf-8")
    with pytest.raises(ValueError, match="name 與 content"):
        section_comment.load_sections_spec(str(spec_file))


def test_load_sections_spec_rejects_empty_array(tmp_path):
    spec_file = tmp_path / "sections.json"
    spec_file.write_text("[]", encoding="utf-8")
    with pytest.raises(ValueError, match="非空"):
        section_comment.load_sections_spec(str(spec_file))


# --- init：兩階段（POST 全部區段 → GET body → 回填索引 → PATCH 一次） ---


def _init_side_effect(post_urls, captured):
    """依呼叫的 gh 參數形態分派回應：查重 search / POST comment / GET body / edit body。

    edit body 呼叫時即讀出 --body-file 內容存入 captured（`write_body` 在
    `finally` 區塊刪除暫存檔，呼叫結束後才讀取會拿到已刪除的路徑）。查重
    search 一律回傳空清單（無命中），聚焦驗證既有 init 兩階段流程不受影響。
    """
    post_iter = iter(post_urls)

    def _run(args, **kwargs):
        if args[:3] == ["gh", "search", "issues"]:
            return _completed(stdout=json.dumps([]))
        if args[:2] == ["gh", "api"] and "--paginate" in args:
            # init 前置的既有區段掃描（cmd_init 的 fetch_comments 呼叫）；
            # 預設無既有區段 comment，走 init 正常流程。
            return _completed(stdout=json.dumps([]))
        if args[:2] == ["gh", "api"] and args[2].endswith("/comments") and "--method" not in args:
            url, comment_id = next(post_iter)
            return _completed(stdout=json.dumps({"id": comment_id, "html_url": url}))
        if args[:3] == ["gh", "issue", "view"]:
            return _completed(stdout=json.dumps({"body": "## 摘要\n\n既有內容"}))
        if args[:3] == ["gh", "issue", "edit"]:
            body_file = Path(args[args.index("--body-file") + 1])
            captured["body"] = body_file.read_text(encoding="utf-8")
            return _completed(stdout="")
        raise AssertionError(f"未預期的 gh 呼叫：{args}")

    return _run


def test_init_posts_all_sections_then_backfills_index_once(tmp_path):
    sections_file = tmp_path / "sections.json"
    sections_file.write_text(
        json.dumps(
            [
                {"name": "當前結論", "content": "## 當前結論\n內容 A"},
                {"name": "方案評估", "content": "## 方案評估\n內容 B"},
            ]
        ),
        encoding="utf-8",
    )
    post_urls = [
        ("https://github.com/tarrragon/claude/issues/81#issuecomment-1", 1),
        ("https://github.com/tarrragon/claude/issues/81#issuecomment-2", 2),
    ]
    captured = {}
    with mock.patch.object(
        section_comment.subprocess, "run", side_effect=_init_side_effect(post_urls, captured)
    ) as run:
        rc = section_comment.main(
            [
                "init", "81", "--owner", "test-session-1", "--sections-file", str(sections_file),
                "--dedup-keywords", "測試關鍵字",
            ]
        )
    assert rc == 0

    api_calls = [
        c
        for c in run.call_args_list
        if c.args[0][:2] == ["gh", "api"] and "--paginate" not in c.args[0]
    ]
    assert len(api_calls) == 2
    first_body = api_calls[0].args[0][-1]
    assert first_body == "body=<!-- section: 當前結論 owner: test-session-1 -->\n## 當前結論\n內容 A"

    written_body = captured["body"]
    assert "既有內容" in written_body
    assert section_comment.INDEX_BEGIN in written_body
    assert "https://github.com/tarrragon/claude/issues/81#issuecomment-1" in written_body
    assert "https://github.com/tarrragon/claude/issues/81#issuecomment-2" in written_body


def test_init_backfills_schema_marker_when_missing_in_single_patch(tmp_path):
    """body 缺 fw-issue-schema 標記時，init 於索引回填的同一次 PATCH 內連同
    標記一併補上（首行），不觸發第二次 `gh issue edit`（見票 why：原本兩次
    手工 PATCH 順序未定義，有並行覆蓋窗口）。"""
    sections_file = tmp_path / "sections.json"
    sections_file.write_text(
        json.dumps([{"name": "當前結論", "content": "## 當前結論\n內容"}]), encoding="utf-8"
    )
    post_urls = [("https://github.com/tarrragon/claude/issues/81#issuecomment-1", 1)]
    captured = {}
    with mock.patch.object(
        section_comment.subprocess, "run", side_effect=_init_side_effect(post_urls, captured)
    ) as run:
        rc = section_comment.main(
            [
                "init", "81", "--owner", "test-session-1", "--sections-file", str(sections_file),
                "--dedup-keywords", "測試關鍵字",
            ]
        )
    assert rc == 0
    written_body = captured["body"]
    assert written_body.startswith(section_comment.FW_ISSUE_SCHEMA_MARKER)
    edit_calls = [c for c in run.call_args_list if c.args[0][:3] == ["gh", "issue", "edit"]]
    assert len(edit_calls) == 1


def test_init_does_not_duplicate_schema_marker_when_already_present(tmp_path):
    """body 已含 fw-issue-schema 標記時，init 原樣保留，不重複插入第二則。"""
    sections_file = tmp_path / "sections.json"
    sections_file.write_text(
        json.dumps([{"name": "當前結論", "content": "## 當前結論\n內容"}]), encoding="utf-8"
    )
    captured = {}

    def _run(args, **kwargs):
        if args[:3] == ["gh", "search", "issues"]:
            return _completed(stdout=json.dumps([]))
        if args[:2] == ["gh", "api"] and "--paginate" in args:
            return _completed(stdout=json.dumps([]))
        if args[:2] == ["gh", "api"] and args[2].endswith("/comments") and "--method" not in args:
            return _completed(
                stdout=json.dumps(
                    {"id": 1, "html_url": "https://github.com/tarrragon/claude/issues/81#issuecomment-1"}
                )
            )
        if args[:3] == ["gh", "issue", "view"]:
            return _completed(
                stdout=json.dumps(
                    {"body": f"{section_comment.FW_ISSUE_SCHEMA_MARKER}\n\n## 摘要\n\n既有內容"}
                )
            )
        if args[:3] == ["gh", "issue", "edit"]:
            body_file = Path(args[args.index("--body-file") + 1])
            captured["body"] = body_file.read_text(encoding="utf-8")
            return _completed(stdout="")
        raise AssertionError(f"未預期的 gh 呼叫：{args}")

    with mock.patch.object(section_comment.subprocess, "run", side_effect=_run):
        rc = section_comment.main(
            [
                "init", "81", "--owner", "test-session-1", "--sections-file", str(sections_file),
                "--dedup-keywords", "測試關鍵字",
            ]
        )
    assert rc == 0
    written_body = captured["body"]
    assert written_body.count(section_comment.FW_ISSUE_SCHEMA_MARKER) == 1


def test_init_prints_dedup_report_before_creating_sections(tmp_path, capsys):
    """init 輸出須含查重報告（回顯關鍵字、命中清單），且早於區段建立完成前輸出。"""
    sections_file = tmp_path / "sections.json"
    sections_file.write_text(
        json.dumps([{"name": "當前結論", "content": "內容"}]), encoding="utf-8"
    )
    post_urls = [("https://github.com/tarrragon/claude/issues/81#issuecomment-1", 1)]
    captured = {}

    def _run(args, **kwargs):
        if args[:3] == ["gh", "search", "issues"]:
            return _completed(
                stdout=json.dumps(
                    [{"number": 82, "title": "既有相關 issue", "url": "https://x/82", "state": "open", "body": ""}]
                )
            )
        if args[:2] == ["gh", "api"] and "--paginate" in args:
            # 命中位置判定對候選 issue 讀取全部 comment（見 _has_comment_match）。
            return _completed(stdout=json.dumps([]))
        return _init_side_effect(post_urls, captured)(args, **kwargs)

    with mock.patch.object(section_comment.subprocess, "run", side_effect=_run):
        rc = section_comment.main(
            [
                "init", "81", "--owner", "test-session-1", "--sections-file", str(sections_file),
                "--dedup-keywords", "元件契約",
            ]
        )
    assert rc == 0
    out = capsys.readouterr().out
    assert "查重關鍵字集合（1 組）" in out
    assert "元件契約" in out
    assert "#82" in out
    assert "既有相關 issue" in out
    assert "命中不等於重複" in out


def test_init_reports_partial_success_count_on_mid_failure(tmp_path, capsys):
    """第二則區段 POST 失敗時，錯誤訊息須含已成功則數，body 不應被回填。"""
    sections_file = tmp_path / "sections.json"
    sections_file.write_text(
        json.dumps(
            [
                {"name": "當前結論", "content": "內容 A"},
                {"name": "方案評估", "content": "內容 B"},
            ]
        ),
        encoding="utf-8",
    )

    call_count = {"n": 0}

    def _run(args, **kwargs):
        if args[:2] == ["gh", "api"] and "--paginate" in args:
            # init 前置的既有區段掃描；獨立於下方 call_count 計數，避免
            # 位移原本鎖定「第 2 次呼叫成功、其餘失敗」的測試意圖。
            return _completed(stdout=json.dumps([]))
        call_count["n"] += 1
        if args[:3] == ["gh", "search", "issues"]:
            return _completed(stdout=json.dumps([]))
        if call_count["n"] == 2:
            return _completed(stdout=json.dumps({"id": 1, "html_url": "url-1"}))
        return _completed(returncode=1, stderr="API rate limit exceeded")

    with mock.patch.object(section_comment.subprocess, "run", side_effect=_run):
        rc = section_comment.main(
            [
                "init", "81", "--owner", "test-session-1", "--sections-file", str(sections_file),
                "--dedup-keywords", "測試關鍵字",
            ]
        )
    assert rc == gh_common.EXIT_DEGRADED
    err = capsys.readouterr().err
    assert "1/2" in err


def test_init_rejects_empty_sections_file(tmp_path, capsys):
    sections_file = tmp_path / "sections.json"
    sections_file.write_text("[]", encoding="utf-8")
    rc = section_comment.main(
        [
            "init", "81", "--owner", "test-session-1", "--sections-file", str(sections_file),
            "--dedup-keywords", "測試關鍵字",
        ]
    )
    assert rc == gh_common.EXIT_DEGRADED
    assert "非空" in capsys.readouterr().err


def test_init_requires_dedup_keywords_flag(tmp_path):
    """`--dedup-keywords` 為必填，缺少時 argparse 直接拒絕（exit code 2）。"""
    sections_file = tmp_path / "sections.json"
    sections_file.write_text(
        json.dumps([{"name": "當前結論", "content": "內容"}]), encoding="utf-8"
    )
    with pytest.raises(SystemExit) as exc_info:
        section_comment.main(
            ["init", "81", "--owner", "test-session-1", "--sections-file", str(sections_file)]
        )
    assert exc_info.value.code == 2


@pytest.mark.parametrize("bad_owner", ["framework-issue-curator", "flutter_balance-pm"])
def test_init_rejects_invalid_owner_format(tmp_path, capsys, bad_owner):
    sections_file = tmp_path / "sections.json"
    sections_file.write_text(
        json.dumps([{"name": "當前結論", "content": "內容"}]), encoding="utf-8"
    )
    rc = section_comment.main(
        [
            "init", "81", "--owner", bad_owner, "--sections-file", str(sections_file),
            "--dedup-keywords", "測試關鍵字",
        ]
    )
    assert rc == gh_common.EXIT_DEGRADED
    err = capsys.readouterr().err
    assert "owner 格式不符" in err
    assert "flutter-balance-77" in err


# --- owned-issues 登記檔寫入：init／update 成功後同步落地一筆登記 ---


def test_init_records_owned_issue_after_successful_section_creation(tmp_path):
    """區段 comment 全數建立成功後，須以 (issue number, owner, timestamp)
    呼叫 record_owned_issue——即使後續 body 索引回填步驟才執行。"""
    sections_file = tmp_path / "sections.json"
    sections_file.write_text(
        json.dumps([{"name": "當前結論", "content": "內容"}]), encoding="utf-8"
    )
    post_urls = [("https://github.com/tarrragon/claude/issues/81#issuecomment-1", 1)]
    captured = {}

    with mock.patch.object(
        section_comment.subprocess, "run", side_effect=_init_side_effect(post_urls, captured)
    ), mock.patch.object(section_comment, "record_owned_issue") as record:
        rc = section_comment.main(
            [
                "init", "81", "--owner", "test-session-1", "--sections-file", str(sections_file),
                "--dedup-keywords", "測試關鍵字",
            ]
        )
    assert rc == 0
    record.assert_called_once()
    number, owner, updated_at = record.call_args.args
    assert number == 81
    assert isinstance(number, int)
    assert owner == "test-session-1"
    assert isinstance(updated_at, str) and updated_at


# --- init：issue 已有區段 comment 時預設拒絕，--force 與既有索引列合併 ---


def test_init_rejects_when_sections_already_exist_without_force(tmp_path, capsys):
    """acceptance：issue 已有任何 section 標記 comment 時 init 無 --force
    即 exit 3 並印 add 用法。"""
    sections_file = tmp_path / "sections.json"
    sections_file.write_text(
        json.dumps([{"name": "方案評估", "content": "內容"}]), encoding="utf-8"
    )
    existing_comment = {
        "id": 1,
        "body": "<!-- section: 當前結論 owner: other-session-1 -->\n內容",
    }

    def _run(args, **kwargs):
        if args[:2] == ["gh", "api"] and "--paginate" in args:
            return _completed(stdout=json.dumps([existing_comment]))
        raise AssertionError(f"未預期的 gh 呼叫：{args}")

    with mock.patch.object(section_comment.subprocess, "run", side_effect=_run):
        rc = section_comment.main(
            [
                "init", "81", "--owner", "test-session-2", "--sections-file", str(sections_file),
                "--dedup-keywords", "測試關鍵字",
            ]
        )
    assert rc == gh_common.EXIT_DEGRADED
    err = capsys.readouterr().err
    assert "add" in err
    assert "--force" in err


def test_init_force_merges_with_existing_index_when_sections_present(tmp_path):
    """acceptance：對已含他方索引列的 issue 執行 init（--force）後，索引
    表列出他方列與本方列，他方 comment id（連結中的 issuecomment-1）不變。"""
    sections_file = tmp_path / "sections.json"
    sections_file.write_text(
        json.dumps([{"name": "方案評估", "content": "## 方案評估\n內容"}]), encoding="utf-8"
    )
    existing_body = (
        "## 摘要\n\n"
        "<!-- section-index -->\n"
        "## 區段索引\n\n"
        "| 區段 | 永久連結 |\n"
        "|------|---------|\n"
        "| 當前結論 | https://github.com/tarrragon/claude/issues/81#issuecomment-1 |\n"
        "<!-- /section-index -->\n"
    )
    existing_comment = {
        "id": 1,
        "body": "<!-- section: 當前結論 owner: other-session-1 -->\n內容",
    }
    captured = {}

    def _run(args, **kwargs):
        if args[:3] == ["gh", "search", "issues"]:
            return _completed(stdout=json.dumps([]))
        if args[:2] == ["gh", "api"] and "--paginate" in args:
            return _completed(stdout=json.dumps([existing_comment]))
        if args[:2] == ["gh", "api"] and args[2].endswith("/comments") and "--method" not in args:
            return _completed(
                stdout=json.dumps(
                    {
                        "id": 2,
                        "html_url": "https://github.com/tarrragon/claude/issues/81#issuecomment-2",
                    }
                )
            )
        if args[:3] == ["gh", "issue", "view"]:
            return _completed(stdout=json.dumps({"body": existing_body}))
        if args[:3] == ["gh", "issue", "edit"]:
            body_file = Path(args[args.index("--body-file") + 1])
            captured["body"] = body_file.read_text(encoding="utf-8")
            return _completed(stdout="")
        raise AssertionError(f"未預期的 gh 呼叫：{args}")

    with mock.patch.object(section_comment.subprocess, "run", side_effect=_run):
        rc = section_comment.main(
            [
                "init", "81", "--owner", "test-session-2", "--sections-file", str(sections_file),
                "--dedup-keywords", "測試關鍵字", "--force",
            ]
        )
    assert rc == 0
    written_body = captured["body"]
    assert "| 當前結論 | https://github.com/tarrragon/claude/issues/81#issuecomment-1 |" in written_body
    assert "| 方案評估 | https://github.com/tarrragon/claude/issues/81#issuecomment-2 |" in written_body
    assert written_body.count("issuecomment-1") == 1


# --- add：對既有 issue 追加單一區段，既有索引列不被覆寫 ---


def _add_side_effect(post_url_id, existing_body, captured):
    """依 gh 參數形態分派回應：POST 單一區段 comment / GET body / edit body。

    與 `_init_side_effect` 的差異：`add` 只 POST 一則 comment（非逐一走
    sections 清單），且不觸發查重 search（`add` 無 `--dedup-keywords`）。
    """
    url, comment_id = post_url_id

    def _run(args, **kwargs):
        if args[:2] == ["gh", "api"] and args[2].endswith("/comments") and "--method" not in args:
            return _completed(stdout=json.dumps({"id": comment_id, "html_url": url}))
        if args[:3] == ["gh", "issue", "view"]:
            return _completed(stdout=json.dumps({"body": existing_body}))
        if args[:3] == ["gh", "issue", "edit"]:
            body_file = Path(args[args.index("--body-file") + 1])
            captured["body"] = body_file.read_text(encoding="utf-8")
            return _completed(stdout="")
        raise AssertionError(f"未預期的 gh 呼叫：{args}")

    return _run


def test_add_appends_new_row_without_disturbing_existing_index_rows(tmp_path):
    """acceptance：add 對已有索引的 issue 執行後，show 列出原有區段加新區段，
    原有列 comment id（即 URL 中的 issuecomment-<id>）不變。"""
    content_file = tmp_path / "content.md"
    content_file.write_text("## 方案評估\n新內容", encoding="utf-8")
    existing_body = (
        "## 摘要\n\n"
        "## 區段索引\n\n"
        "| 區段 | 永久連結 |\n"
        "|------|---------|\n"
        "| 當前結論 | https://github.com/tarrragon/claude/issues/81#issuecomment-1 |\n"
    )
    captured = {}
    with mock.patch.object(
        section_comment.subprocess,
        "run",
        side_effect=_add_side_effect(
            ("https://github.com/tarrragon/claude/issues/81#issuecomment-2", 2),
            existing_body,
            captured,
        ),
    ) as run:
        rc = section_comment.main(
            [
                "add", "81", "--owner", "test-session-1", "--name", "方案評估",
                "--content-file", str(content_file),
            ]
        )
    assert rc == 0

    written_body = captured["body"]
    assert "| 當前結論 | https://github.com/tarrragon/claude/issues/81#issuecomment-1 |" in written_body
    assert "| 方案評估 | https://github.com/tarrragon/claude/issues/81#issuecomment-2 |" in written_body

    post_calls = [
        c for c in run.call_args_list
        if c.args[0][:2] == ["gh", "api"] and c.args[0][2].endswith("/comments") and "--method" not in c.args[0]
    ]
    assert len(post_calls) == 1
    posted_body = post_calls[0].args[0][-1]
    assert posted_body == "body=<!-- section: 方案評估 owner: test-session-1 -->\n## 方案評估\n新內容"


def test_add_success_message_prints_issue_section_name_and_owner(tmp_path, capsys):
    """成功訊息比照 transfer-owner 逐字印出結果，供操作者不需另開 comment
    即可確認 issue、區段名、owner 三項。"""
    content_file = tmp_path / "content.md"
    content_file.write_text("內容", encoding="utf-8")
    existing_body = "## 摘要\n\n無索引表的一般內容"
    with mock.patch.object(
        section_comment.subprocess,
        "run",
        side_effect=_add_side_effect(
            ("https://github.com/tarrragon/claude/issues/81#issuecomment-9", 9),
            existing_body,
            {},
        ),
    ):
        rc = section_comment.main(
            [
                "add", "81", "--owner", "test-session-1", "--name", "當前結論",
                "--content-file", str(content_file),
            ]
        )
    assert rc == 0
    err = capsys.readouterr().err
    assert "區段「當前結論」已建立 @ 81" in err
    assert "owner=test-session-1" in err


def test_add_merges_hand_written_index_table_without_duplicating_rows(tmp_path):
    """Problem Analysis 第二個同源缺陷：body 已有手寫索引表（無
    `<!-- section-index -->` 標記）時，add 併入既有列而非在其後追加第二張
    表；重寫後只留一份標記索引，既有列與新列各出現一次。"""
    content_file = tmp_path / "content.md"
    content_file.write_text("## 方案評估\n新內容", encoding="utf-8")
    existing_body = (
        "## 摘要\n\n"
        "## 區段索引\n\n"
        "| 區段 | 永久連結 |\n"
        "|------|---------|\n"
        "| 當前結論 | https://github.com/tarrragon/claude/issues/81#issuecomment-1 |\n"
    )
    captured = {}
    with mock.patch.object(
        section_comment.subprocess,
        "run",
        side_effect=_add_side_effect(
            ("https://github.com/tarrragon/claude/issues/81#issuecomment-2", 2),
            existing_body,
            captured,
        ),
    ):
        rc = section_comment.main(
            [
                "add", "81", "--owner", "test-session-1", "--name", "方案評估",
                "--content-file", str(content_file),
            ]
        )
    assert rc == 0
    written_body = captured["body"]
    assert written_body.count(section_comment.INDEX_BEGIN) == 1
    assert written_body.count("issuecomment-1") == 1
    assert written_body.count("issuecomment-2") == 1


def test_add_dedupes_existing_duplicate_rows_by_comment_id(tmp_path):
    """既有索引表因修法前的殘留缺陷已含重複列（相同 comment id 出現兩次）
    時，add 合併後的索引表以 comment id 去重，不延續既有重複（自我修復，
    見本 ticket Problem Analysis 第二個同源缺陷）。"""
    content_file = tmp_path / "content.md"
    content_file.write_text("內容", encoding="utf-8")
    existing_body = (
        "## 摘要\n\n"
        "## 區段索引\n\n"
        "| 區段 | 永久連結 |\n"
        "|------|---------|\n"
        "| 當前結論 | https://github.com/tarrragon/claude/issues/81#issuecomment-1 |\n"
        "| 當前結論 | https://github.com/tarrragon/claude/issues/81#issuecomment-1 |\n"
    )
    captured = {}
    with mock.patch.object(
        section_comment.subprocess,
        "run",
        side_effect=_add_side_effect(
            ("https://github.com/tarrragon/claude/issues/81#issuecomment-2", 2),
            existing_body,
            captured,
        ),
    ):
        rc = section_comment.main(
            [
                "add", "81", "--owner", "test-session-1", "--name", "方案評估",
                "--content-file", str(content_file),
            ]
        )
    assert rc == 0
    written_body = captured["body"]
    assert written_body.count("issuecomment-1") == 1
    assert "issuecomment-2" in written_body


def test_add_creates_index_table_when_missing(tmp_path):
    content_file = tmp_path / "content.md"
    content_file.write_text("內容", encoding="utf-8")
    existing_body = "## 摘要\n\n無索引表的一般內容"
    captured = {}
    with mock.patch.object(
        section_comment.subprocess,
        "run",
        side_effect=_add_side_effect(
            ("https://github.com/tarrragon/claude/issues/81#issuecomment-9", 9),
            existing_body,
            captured,
        ),
    ):
        rc = section_comment.main(
            [
                "add", "81", "--owner", "test-session-1", "--name", "當前結論",
                "--content-file", str(content_file),
            ]
        )
    assert rc == 0
    written_body = captured["body"]
    assert section_comment.INDEX_BEGIN in written_body
    assert "| 當前結論 | https://github.com/tarrragon/claude/issues/81#issuecomment-9 |" in written_body
    assert "無索引表的一般內容" in written_body


def test_add_backfills_schema_marker_when_missing_in_single_patch(tmp_path):
    """`add` 對 body-only 舊 issue（無標記亦無索引表）附加區段時，同一次
    PATCH 內連同 fw-issue-schema 標記一併補上，與 `init` 行為一致。"""
    content_file = tmp_path / "content.md"
    content_file.write_text("內容", encoding="utf-8")
    existing_body = "## 摘要\n\n無索引表的一般內容"
    captured = {}
    with mock.patch.object(
        section_comment.subprocess,
        "run",
        side_effect=_add_side_effect(
            ("https://github.com/tarrragon/claude/issues/81#issuecomment-9", 9),
            existing_body,
            captured,
        ),
    ) as run:
        rc = section_comment.main(
            [
                "add", "81", "--owner", "test-session-1", "--name", "當前結論",
                "--content-file", str(content_file),
            ]
        )
    assert rc == 0
    written_body = captured["body"]
    assert written_body.startswith(section_comment.FW_ISSUE_SCHEMA_MARKER)
    edit_calls = [c for c in run.call_args_list if c.args[0][:3] == ["gh", "issue", "edit"]]
    assert len(edit_calls) == 1


def test_add_records_owned_issue_after_successful_section_creation(tmp_path):
    content_file = tmp_path / "content.md"
    content_file.write_text("內容", encoding="utf-8")
    existing_body = "## 摘要\n\n無索引"
    captured = {}
    with mock.patch.object(
        section_comment.subprocess,
        "run",
        side_effect=_add_side_effect(
            ("https://github.com/tarrragon/claude/issues/81#issuecomment-9", 9),
            existing_body,
            captured,
        ),
    ), mock.patch.object(section_comment, "record_owned_issue") as record:
        rc = section_comment.main(
            [
                "add", "81", "--owner", "test-session-1", "--name", "當前結論",
                "--content-file", str(content_file),
            ]
        )
    assert rc == 0
    record.assert_called_once()
    number, owner, updated_at = record.call_args.args
    assert number == 81
    assert owner == "test-session-1"
    assert isinstance(updated_at, str) and updated_at


@pytest.mark.parametrize("bad_owner", ["framework-issue-curator", "flutter_balance-pm"])
def test_add_rejects_invalid_owner_format(tmp_path, capsys, bad_owner):
    content_file = tmp_path / "content.md"
    content_file.write_text("內容", encoding="utf-8")
    rc = section_comment.main(
        ["add", "81", "--owner", bad_owner, "--name", "當前結論", "--content-file", str(content_file)]
    )
    assert rc == gh_common.EXIT_DEGRADED
    err = capsys.readouterr().err
    assert "owner 格式不符" in err
    assert "flutter-balance-77" in err


# --- dedup：查重（token 聯集查詢，避免跨 comment AND 語意漏判） ---


def test_split_keyword_tokens_keeps_cjk_compound_as_single_token():
    assert section_comment._split_keyword_tokens("元件契約") == ["元件契約"]


def test_split_keyword_tokens_splits_on_whitespace():
    assert section_comment._split_keyword_tokens("UX skill") == ["UX", "skill"]


def test_search_issues_by_keyword_builds_expected_gh_command():
    with mock.patch.object(
        section_comment.subprocess,
        "run",
        return_value=_completed(
            stdout=json.dumps([{"number": 81, "title": "t", "url": "u", "state": "open"}])
        ),
    ) as run:
        hits = section_comment.search_issues_by_keyword("元件契約")
    assert hits == [{"number": 81, "title": "t", "url": "u", "state": "open"}]
    args = run.call_args.args[0]
    assert args[:3] == ["gh", "search", "issues"]
    assert "--repo" in args and args[args.index("--repo") + 1] == "tarrragon/claude"
    assert "--match" in args and args[args.index("--match") + 1] == "title,body,comments"
    # keyword 排在 "--" 之後，避免以 "-" 開頭的 token 被誤判為旗標。
    assert args[-2:] == ["--", "元件契約"]


def test_search_issues_by_keyword_places_hyphen_prefixed_token_after_double_dash():
    """關鍵字「commit -a」拆分出的 "-a" 若排在旗標前，會被 gh 的 cobra flag
    parser 誤判為短旗標；驗證 "--" 分隔確實把它排到位置參數區。"""
    with mock.patch.object(
        section_comment.subprocess,
        "run",
        return_value=_completed(stdout=json.dumps([])),
    ) as run:
        section_comment.search_issues_by_keyword("-a")
    args = run.call_args.args[0]
    assert args[-2:] == ["--", "-a"]
    assert "-a" not in args[:-1]


def test_search_issues_by_keyword_raises_on_gh_failure():
    with mock.patch.object(
        section_comment.subprocess,
        "run",
        return_value=_completed(returncode=1, stderr="rate limited"),
    ):
        with pytest.raises(RuntimeError, match="rate limited"):
            section_comment.search_issues_by_keyword("x")


def test_hit_field_labels_detects_title_body_and_comment_positions():
    """三種命中位置：title／body 由 search 回傳欄位本地子字串比對；comments
    對該 issue 全部 comment 本地比對（title／body 皆未命中時才會命中）。"""
    comment_cache = {}

    def _run(args, **kwargs):
        assert args[:2] == ["gh", "api"] and "--paginate" in args
        issue_number = int(args[2].split("/")[-2])
        if issue_number == 3:
            return _completed(stdout=json.dumps([{"id": 1, "body": "內文提到 元件契約 這個詞"}]))
        return _completed(stdout=json.dumps([]))

    issue_title_hit = {"number": 1, "title": "元件契約 相關討論", "body": ""}
    issue_body_hit = {"number": 2, "title": "無關標題", "body": "body 內含 元件契約"}
    issue_comment_hit = {"number": 3, "title": "無關", "body": "也無關"}

    with mock.patch.object(section_comment.subprocess, "run", side_effect=_run):
        assert section_comment._hit_field_labels("元件契約", issue_title_hit, comment_cache) == {"title"}
        assert section_comment._hit_field_labels("元件契約", issue_body_hit, comment_cache) == {"body"}
        assert section_comment._hit_field_labels("元件契約", issue_comment_hit, comment_cache) == {"comments"}


def test_render_dedup_report_includes_matched_tokens_and_hit_fields():
    """報告每筆命中列出命中詞與命中位置（見 search_duplicates 的
    matched_tokens／hit_fields）。"""
    hits = {
        "元件契約": [
            {
                "number": 81, "title": "t", "url": "u", "state": "open",
                "matched_tokens": ["元件契約"], "hit_fields": ["body", "title"],
            },
        ]
    }
    report = section_comment.render_dedup_report(["元件契約"], hits)
    assert "命中詞：元件契約｜命中位置：body、title" in report


def test_search_duplicates_unions_tokens_to_cover_cross_comment_terms():
    """重現並修正涵蓋缺口：關鍵字組「skill 拆分」單一 AND 查詢會漏掉某 issue
    （兩詞分屬同一 issue 的不同 comment，gh 多詞 AND 語意要求同一欄位實例內
    共現）；拆為單詞查詢後聯集才涵蓋。命中多個 token 的 issue（79）排在只命中
    一個 token 的 issue（82）之前（依 matched_tokens 數量遞減排序）。"""

    def _run(args, **kwargs):
        if args[:3] == ["gh", "search", "issues"]:
            token = args[-1]
            if token == "skill":
                return _completed(stdout=json.dumps([{"number": 79, "title": "a", "url": "u1", "state": "open"}]))
            if token == "拆分":
                return _completed(
                    stdout=json.dumps(
                        [
                            {"number": 79, "title": "a", "url": "u1", "state": "open"},
                            {"number": 82, "title": "b", "url": "u2", "state": "open"},
                        ]
                    )
                )
            raise AssertionError(f"未預期的 token：{token}")
        if args[:2] == ["gh", "api"] and "--paginate" in args:
            # 命中位置判定對候選 issue 讀取全部 comment（見 _has_comment_match）。
            return _completed(stdout=json.dumps([]))
        raise AssertionError(f"未預期的 gh 呼叫：{args}")

    with mock.patch.object(section_comment.subprocess, "run", side_effect=_run):
        results, skipped = section_comment.search_duplicates(["skill 拆分"])
    hits = results["skill 拆分"]
    assert [issue["number"] for issue in hits] == [79, 82]
    assert hits[0]["matched_tokens"] == ["skill", "拆分"]
    assert hits[1]["matched_tokens"] == ["拆分"]
    assert skipped == 0


def test_search_duplicates_skips_failed_token_without_aborting_others(capsys):
    def _run(args, **kwargs):
        if args[:3] == ["gh", "search", "issues"]:
            token = args[-1]
            if token == "壞詞":
                return _completed(returncode=1, stderr="network error")
            return _completed(stdout=json.dumps([{"number": 1, "title": "t", "url": "u", "state": "open"}]))
        if args[:2] == ["gh", "api"] and "--paginate" in args:
            return _completed(stdout=json.dumps([]))
        raise AssertionError(f"未預期的 gh 呼叫：{args}")

    with mock.patch.object(section_comment.subprocess, "run", side_effect=_run):
        results, skipped = section_comment.search_duplicates(["壞詞", "好詞"])
    assert results["壞詞"] == []
    assert [issue["number"] for issue in results["好詞"]] == [1]
    assert results["好詞"][0]["matched_tokens"] == ["好詞"]
    err = capsys.readouterr().err
    assert "壞詞" in err
    assert "[WARNING]" in err
    assert skipped == 1


def test_search_duplicates_counts_skipped_hyphen_prefixed_token_and_still_unions_rest(capsys):
    """關鍵字組「commit -a」含以 "-" 開頭的 token；驗證該 token 不再因旗標
    誤判而查詢失敗（實際送出 query），且失敗計數與涵蓋範圍缺口正確反映。"""

    def _run(args, **kwargs):
        if args[:3] == ["gh", "search", "issues"]:
            token = args[-1]
            if token == "--force":
                return _completed(returncode=1, stderr="network error")
            if token in ("commit", "-a"):
                return _completed(stdout=json.dumps([{"number": 5, "title": "t", "url": "u", "state": "open"}]))
            raise AssertionError(f"未預期的 token：{token}")
        if args[:2] == ["gh", "api"] and "--paginate" in args:
            return _completed(stdout=json.dumps([]))
        raise AssertionError(f"未預期的 gh 呼叫：{args}")

    with mock.patch.object(section_comment.subprocess, "run", side_effect=_run):
        results, skipped = section_comment.search_duplicates(["commit -a", "--force"])
    assert [issue["number"] for issue in results["commit -a"]] == [5]
    assert results["commit -a"][0]["matched_tokens"] == ["-a", "commit"]
    assert results["--force"] == []
    assert skipped == 1


def test_render_dedup_report_lists_no_hit_group_and_footer():
    report = section_comment.render_dedup_report(["無命中詞"], {"無命中詞": []})
    assert "查重關鍵字集合（1 組）" in report
    assert "無命中詞" in report
    assert "無命中" in report
    assert "命中不等於重複" in report
    # 未傳 skipped 時預設 0，末行仍固定重述（tail -1 可見的涵蓋缺口宣告）。
    assert report.rstrip("\n").splitlines()[-1] == "查詢失敗略過的 token 數：0"


def test_render_dedup_report_last_line_restates_skipped_count():
    """略過的關鍵字查詢失敗數須在報告最後一行重述，`tail -1` 即可見。"""
    report = section_comment.render_dedup_report(["--force"], {"--force": []}, skipped=1)
    assert report.rstrip("\n").splitlines()[-1] == "查詢失敗略過的 token 數：1"


def test_cmd_dedup_is_read_only_and_does_not_call_gh_issue_or_api():
    """dedup 子命令只呼叫 `gh search issues`，不觸碰 `gh issue` / `gh api`（不建立 issue）。"""
    with mock.patch.object(
        section_comment.subprocess, "run", return_value=_completed(stdout=json.dumps([]))
    ) as run:
        rc = section_comment.main(["dedup", "--keywords", "元件契約", "component"])
    assert rc == 0
    for call in run.call_args_list:
        assert call.args[0][:2] == ["gh", "search"]


def test_cmd_dedup_cli_accepts_hyphen_prefixed_keyword_group_end_to_end(capsys):
    """端對端重現 acceptance 命令：`dedup --keywords "commit -a" "--dry-run"`。

    "--dry-run" 本身即一整個 keyword group（非拆自「commit -a」的子 token，
    亦非本檔任何子命令實際註冊的旗標——`init` 的 `--force` 已註冊，故不可
    再用它示範「未註冊旗標形態的字面值」），需先通過 argparse 收值
    （`_escape_dash_prefixed_keyword_values`）才會被傳入 `search_duplicates`；
    兩個 token 皆須實際送出 gh 查詢。"""
    queried_tokens = []

    def _run(args, **kwargs):
        queried_tokens.append(args[-1])
        return _completed(stdout=json.dumps([]))

    with mock.patch.object(section_comment.subprocess, "run", side_effect=_run):
        rc = section_comment.main(["dedup", "--keywords", "commit -a", "--dry-run"])
    assert rc == 0
    assert set(queried_tokens) == {"commit", "-a", "--dry-run"}
    out = capsys.readouterr().out
    assert out.rstrip("\n").splitlines()[-1] == "查詢失敗略過的 token 數：0"


# --- update：以 comment id 精準 PATCH，保留首行標記，不動其他 comment ---


def test_update_patches_only_target_comment_and_preserves_owner(tmp_path):
    content_file = tmp_path / "content.md"
    content_file.write_text("## 當前結論\n更新後內容", encoding="utf-8")

    def _run(args, **kwargs):
        if args[:2] == ["gh", "api"] and "--method" not in args:
            return _completed(
                stdout=json.dumps(
                    {"body": "<!-- section: 當前結論 owner: flutter-balance-99 -->\n舊內容"}
                )
            )
        if "--method" in args and args[args.index("--method") + 1] == "PATCH":
            return _completed(stdout=json.dumps({"id": 5523472948}))
        raise AssertionError(f"未預期的 gh 呼叫：{args}")

    with mock.patch.object(section_comment.subprocess, "run", side_effect=_run) as run:
        rc = section_comment.main(["update", "5523472948", "--content-file", str(content_file)])
    assert rc == 0

    patch_call = next(
        c for c in run.call_args_list if "--method" in c.args[0] and "PATCH" in c.args[0]
    )
    patch_args = patch_call.args[0]
    assert "issues/comments/5523472948" in patch_args[2]
    patched_body = patch_args[-1]
    assert patched_body == (
        "body=<!-- section: 當前結論 owner: flutter-balance-99 -->\n## 當前結論\n更新後內容"
    )
    # 只呼叫兩次 gh api（GET 既有內容一次、PATCH 一次），不觸碰 body 或其他 comment。
    assert run.call_count == 2


def test_update_rejects_comment_without_section_marker(tmp_path, capsys):
    """非區段 comment（如觀測留言）拒絕更新，避免誤改。"""
    content_file = tmp_path / "content.md"
    content_file.write_text("新內容", encoding="utf-8")

    with mock.patch.object(
        section_comment.subprocess,
        "run",
        return_value=_completed(
            stdout=json.dumps({"body": "<!-- observation: 實測 by session-a -->\n觀測內容"})
        ),
    ) as run:
        rc = section_comment.main(["update", "999", "--content-file", str(content_file)])
    assert rc == gh_common.EXIT_DEGRADED
    assert "非區段標記" in capsys.readouterr().err
    # 確認未發出 PATCH（僅 GET 一次即被拒）。
    assert run.call_count == 1


def test_update_records_owned_issue_with_number_from_issue_url(tmp_path):
    """cmd_update 只收 comment_id，issue number 須從既有 comment 的
    issue_url 回推；成功時以 (issue number, owner, timestamp) 呼叫
    record_owned_issue。"""
    content_file = tmp_path / "content.md"
    content_file.write_text("## 當前結論\n更新後內容", encoding="utf-8")

    def _run(args, **kwargs):
        if args[:2] == ["gh", "api"] and "--method" not in args:
            return _completed(
                stdout=json.dumps(
                    {
                        "body": "<!-- section: 當前結論 owner: flutter-balance-99 -->\n舊內容",
                        "issue_url": "https://api.github.com/repos/tarrragon/claude/issues/81",
                    }
                )
            )
        if "--method" in args and args[args.index("--method") + 1] == "PATCH":
            return _completed(stdout=json.dumps({"id": 5523472948}))
        raise AssertionError(f"未預期的 gh 呼叫：{args}")

    with mock.patch.object(section_comment.subprocess, "run", side_effect=_run), \
            mock.patch.object(section_comment, "record_owned_issue") as record:
        rc = section_comment.main(["update", "5523472948", "--content-file", str(content_file)])
    assert rc == 0
    record.assert_called_once()
    number, owner, updated_at = record.call_args.args
    assert number == 81
    assert owner == "flutter-balance-99"
    assert isinstance(updated_at, str) and updated_at


def test_update_skips_registry_write_when_issue_url_missing(tmp_path):
    """既有 comment 缺 issue_url（非標準/測試替身資料）時，回推失敗只略過
    登記檔寫入，不影響 update 本身成功。"""
    content_file = tmp_path / "content.md"
    content_file.write_text("## 當前結論\n更新後內容", encoding="utf-8")

    def _run(args, **kwargs):
        if args[:2] == ["gh", "api"] and "--method" not in args:
            return _completed(
                stdout=json.dumps(
                    {"body": "<!-- section: 當前結論 owner: flutter-balance-99 -->\n舊內容"}
                )
            )
        if "--method" in args and args[args.index("--method") + 1] == "PATCH":
            return _completed(stdout=json.dumps({"id": 5523472948}))
        raise AssertionError(f"未預期的 gh 呼叫：{args}")

    with mock.patch.object(section_comment.subprocess, "run", side_effect=_run), \
            mock.patch.object(section_comment, "record_owned_issue") as record:
        rc = section_comment.main(["update", "5523472948", "--content-file", str(content_file)])
    assert rc == 0
    record.assert_not_called()


# --- transfer-owner：PATCH 首行標記的 owner 欄，內容不變 ---


def test_transfer_owner_patches_owner_field_and_preserves_content(tmp_path):
    def _run(args, **kwargs):
        if args[:2] == ["gh", "api"] and "--method" not in args:
            return _completed(
                stdout=json.dumps(
                    {"body": "<!-- section: 當前結論 owner: flutter-balance-99 -->\n舊內容不變"}
                )
            )
        if "--method" in args and args[args.index("--method") + 1] == "PATCH":
            return _completed(stdout=json.dumps({"id": 5523472948}))
        raise AssertionError(f"未預期的 gh 呼叫：{args}")

    with mock.patch.object(section_comment.subprocess, "run", side_effect=_run) as run:
        rc = section_comment.main(["transfer-owner", "5523472948", "--to", "flutter-balance-100"])
    assert rc == 0

    patch_call = next(
        c for c in run.call_args_list if "--method" in c.args[0] and "PATCH" in c.args[0]
    )
    patched_body = patch_call.args[0][-1]
    assert patched_body == "body=<!-- section: 當前結論 owner: flutter-balance-100 -->\n舊內容不變"
    # 只呼叫兩次 gh api（GET 既有內容一次、PATCH 一次），不觸碰 body 或其他 comment。
    assert run.call_count == 2


def test_transfer_owner_rejects_comment_without_section_marker(tmp_path, capsys):
    """非區段 comment（如觀測留言）拒絕轉移 owner，避免誤改。"""
    with mock.patch.object(
        section_comment.subprocess,
        "run",
        return_value=_completed(
            stdout=json.dumps({"body": "<!-- observation: 實測 by session-a -->\n觀測內容"})
        ),
    ) as run:
        rc = section_comment.main(["transfer-owner", "999", "--to", "flutter-balance-100"])
    assert rc == gh_common.EXIT_DEGRADED
    assert "非區段標記" in capsys.readouterr().err
    assert run.call_count == 1


def test_transfer_owner_records_owned_issue_with_new_owner(tmp_path):
    def _run(args, **kwargs):
        if args[:2] == ["gh", "api"] and "--method" not in args:
            return _completed(
                stdout=json.dumps(
                    {
                        "body": "<!-- section: 當前結論 owner: flutter-balance-99 -->\n內容",
                        "issue_url": "https://api.github.com/repos/tarrragon/claude/issues/81",
                    }
                )
            )
        if "--method" in args and args[args.index("--method") + 1] == "PATCH":
            return _completed(stdout=json.dumps({"id": 5523472948}))
        raise AssertionError(f"未預期的 gh 呼叫：{args}")

    with mock.patch.object(section_comment.subprocess, "run", side_effect=_run), \
            mock.patch.object(section_comment, "record_owned_issue") as record:
        rc = section_comment.main(["transfer-owner", "5523472948", "--to", "flutter-balance-100"])
    assert rc == 0
    record.assert_called_once()
    number, owner, updated_at = record.call_args.args
    assert number == 81
    assert owner == "flutter-balance-100"
    assert isinstance(updated_at, str) and updated_at


@pytest.mark.parametrize("bad_owner", ["framework-issue-curator", "flutter_balance-pm"])
def test_transfer_owner_rejects_invalid_owner_format(bad_owner, capsys):
    rc = section_comment.main(["transfer-owner", "999", "--to", bad_owner])
    assert rc == gh_common.EXIT_DEGRADED
    err = capsys.readouterr().err
    assert "owner 格式不符" in err
    assert "flutter-balance-77" in err


# --- observe：任何 session 可用，不需 owner，不改 body ---


def test_observe_posts_comment_without_owner_requirement(tmp_path, capsys):
    content_file = tmp_path / "observation.md"
    content_file.write_text("以 #81 實測 observe 通道", encoding="utf-8")

    with mock.patch.object(
        section_comment.subprocess,
        "run",
        return_value=_completed(
            stdout=json.dumps(
                {"id": 999, "html_url": "https://github.com/tarrragon/claude/issues/81#issuecomment-999"}
            )
        ),
    ) as run:
        rc = section_comment.main(
            [
                "observe", "81",
                "--summary", "實測結果",
                "--session", "session-a",
                "--content-file", str(content_file),
            ]
        )
    assert rc == 0
    assert run.call_count == 1
    posted_body = run.call_args.args[0][-1]
    assert posted_body == (
        "body=<!-- observation: 實測結果 by session-a -->\n以 #81 實測 observe 通道"
    )
    out = capsys.readouterr().out
    assert "issuecomment-999" in out


def test_observe_failure_degrades_without_crashing(tmp_path, capsys):
    content_file = tmp_path / "observation.md"
    content_file.write_text("內容", encoding="utf-8")

    with mock.patch.object(
        section_comment.subprocess,
        "run",
        return_value=_completed(returncode=1, stderr="network error"),
    ):
        rc = section_comment.main(
            [
                "observe", "81",
                "--summary", "摘要",
                "--session", "session-a",
                "--content-file", str(content_file),
            ]
        )
    assert rc == gh_common.EXIT_DEGRADED
    assert "network error" in capsys.readouterr().err


# --- 降級路徑（沿用 gh_common 既有機制，section_comment 不需重新實作） ---


def test_degraded_when_gh_not_installed(monkeypatch, capsys):
    """autouse fixture 已將 check_gh_available 換成固定 True 的 lambda，本測試
    須直接覆寫該函式本身（覆寫 shutil.which 對已替換的 lambda 不再有作用）。"""
    monkeypatch.setattr(gh_common, "check_gh_available", lambda: False)
    rc = section_comment.main(
        ["observe", "81", "--summary", "s", "--session", "a", "--content-file", "/nonexistent"]
    )
    assert rc == gh_common.EXIT_DEGRADED
    assert "未安裝" in capsys.readouterr().err


# --- parse_index_table：兩種真實觀測形態（2 欄純連結 / 3 欄含 markdown 連結） ---


def test_parse_index_table_two_column_bare_url():
    body = (
        "## 區段索引\n\n"
        "| 區段 | 永久連結 |\n"
        "|------|---------|\n"
        "| 當前結論（讀者入口） | https://github.com/tarrragon/claude/issues/81#issuecomment-5523472948 |\n"
        "| 方案評估 | https://github.com/tarrragon/claude/issues/81#issuecomment-5523478800 |\n"
    )
    rows = section_comment.parse_index_table(body)
    assert rows == [
        {
            "name": "當前結論（讀者入口）",
            "id": 5523472948,
            "url": "https://github.com/tarrragon/claude/issues/81#issuecomment-5523472948",
        },
        {
            "name": "方案評估",
            "id": 5523478800,
            "url": "https://github.com/tarrragon/claude/issues/81#issuecomment-5523478800",
        },
    ]


def test_parse_index_table_three_column_markdown_link():
    body = (
        "## 區段索引\n\n"
        "| 區段 | 連結 | 內容 |\n"
        "|------|------|------|\n"
        "| 當前結論 | [#issuecomment-5523598606]"
        "(https://github.com/tarrragon/claude/issues/82#issuecomment-5523598606) | 修正後的方案 |\n"
    )
    rows = section_comment.parse_index_table(body)
    assert rows == [
        {
            "name": "當前結論",
            "id": 5523598606,
            "url": "https://github.com/tarrragon/claude/issues/82#issuecomment-5523598606",
        }
    ]


def test_parse_index_table_returns_empty_when_no_index_present():
    assert section_comment.parse_index_table("## 摘要\n\n無索引表的一般內容") == []


# --- classify_comments：依首行標記分區段／觀測流 ---


def test_classify_comments_separates_section_and_stream():
    comments = [
        {"id": 1, "body": "<!-- section: 當前結論 owner: s -->\n內容"},
        {"id": 2, "body": "<!-- observation: 摘要 by s -->\n觀測內容"},
        {"id": 3, "body": "一般留言，無標記"},
    ]
    sections, stream = section_comment.classify_comments(comments)
    assert set(sections.keys()) == {1}
    assert sections[1]["name"] == "當前結論"
    assert [c["id"] for c in stream] == [2, 3]


# --- show：以索引為入口區分區段／觀測流 ---


def _show_side_effect(body_text, comments_payload):
    def _run(args, **kwargs):
        if args[:3] == ["gh", "issue", "view"]:
            return _completed(stdout=json.dumps({"body": body_text}))
        if args[:2] == ["gh", "api"] and args[2].endswith("/comments"):
            return _completed(stdout=json.dumps(comments_payload))
        raise AssertionError(f"未預期的 gh 呼叫：{args}")

    return _run


def test_show_lists_sections_from_index_and_stream_separately():
    body = (
        "## 區段索引\n\n"
        "| 區段 | 永久連結 |\n"
        "|------|---------|\n"
        "| 當前結論 | https://github.com/tarrragon/claude/issues/81#issuecomment-1 |\n"
    )
    comments = [
        {
            "id": 1,
            "body": "<!-- section: 當前結論 owner: s -->\n內容",
            "updated_at": "2026-09-03T09:48:40Z",
            "created_at": "2026-09-03T09:17:38Z",
            "html_url": "https://github.com/tarrragon/claude/issues/81#issuecomment-1",
        },
        {
            "id": 2,
            "body": "<!-- observation: 實測結果 by session-a -->\n觀測內容",
            "created_at": "2026-09-03T09:27:24Z",
            "html_url": "https://github.com/tarrragon/claude/issues/81#issuecomment-2",
        },
        {
            "id": 3,
            "body": "## 觀測：無標記的一般留言\n內文",
            "created_at": "2026-09-03T09:31:46Z",
            "html_url": "https://github.com/tarrragon/claude/issues/81#issuecomment-3",
        },
    ]
    with mock.patch.object(
        section_comment.subprocess, "run", side_effect=_show_side_effect(body, comments)
    ):
        rc = section_comment.main(["show", "81"])
    assert rc == 0


def test_show_output_content(capsys):
    body = (
        "## 區段索引\n\n"
        "| 區段 | 永久連結 |\n"
        "|------|---------|\n"
        "| 當前結論 | https://github.com/tarrragon/claude/issues/81#issuecomment-1 |\n"
    )
    comments = [
        {
            "id": 1,
            "body": "<!-- section: 當前結論 owner: s -->\n內容",
            "updated_at": "2026-09-03T09:48:40Z",
            "created_at": "2026-09-03T09:17:38Z",
            "html_url": "https://github.com/tarrragon/claude/issues/81#issuecomment-1",
        },
        {
            "id": 2,
            "body": "<!-- observation: 實測結果 by session-a -->\n觀測內容",
            "created_at": "2026-09-03T09:27:24Z",
            "html_url": "https://github.com/tarrragon/claude/issues/81#issuecomment-2",
        },
    ]
    with mock.patch.object(
        section_comment.subprocess, "run", side_effect=_show_side_effect(body, comments)
    ):
        rc = section_comment.main(["show", "81"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "區段索引來源：body 表格" in out
    assert "當前結論 owner=s updated_at=2026-09-03T09:48:40Z" in out
    assert "觀測流（1 則" in out
    assert "實測結果 by session-a" in out
    assert "索引缺失" not in out


def test_show_falls_back_to_marker_scan_when_index_missing(capsys):
    body = "## 摘要\n\n無索引表的一般內容"
    comments = [
        {
            "id": 1,
            "body": "<!-- section: 當前結論 owner: s -->\n內容",
            "updated_at": "2026-09-03T09:48:40Z",
            "created_at": "2026-09-03T09:17:38Z",
            "html_url": "https://github.com/tarrragon/claude/issues/81#issuecomment-1",
        },
        {
            "id": 2,
            "body": "一般觀測留言",
            "created_at": "2026-09-03T09:27:24Z",
            "html_url": "https://github.com/tarrragon/claude/issues/81#issuecomment-2",
        },
    ]
    with mock.patch.object(
        section_comment.subprocess, "run", side_effect=_show_side_effect(body, comments)
    ):
        rc = section_comment.main(["show", "81"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "索引缺失" in out
    assert "當前結論 owner=s updated_at=2026-09-03T09:48:40Z" in out
    assert "觀測流（1 則" in out


# --- check：三項早期警訊 ---


def test_check_reports_all_clear_when_consistent_and_fresh():
    body = (
        "## 區段索引\n\n"
        "| 區段 | 永久連結 |\n"
        "|------|---------|\n"
        "| 當前結論 | https://github.com/tarrragon/claude/issues/81#issuecomment-1 |\n"
    )
    comments = [
        {
            "id": 1,
            "body": "<!-- section: 當前結論 owner: s -->\n內容",
            "updated_at": "2026-09-03T10:00:00Z",
            "created_at": "2026-09-03T09:17:38Z",
        },
        {
            "id": 2,
            "body": "一般觀測",
            "created_at": "2026-09-03T09:27:24Z",
        },
    ]
    with mock.patch.object(
        section_comment.subprocess, "run", side_effect=_show_side_effect(body, comments)
    ):
        rc = section_comment.main(["check", "81"])
    assert rc == 0


def test_check_output_content_all_clear(capsys):
    body = (
        "## 區段索引\n\n"
        "| 區段 | 永久連結 |\n"
        "|------|---------|\n"
        "| 當前結論 | https://github.com/tarrragon/claude/issues/81#issuecomment-1 |\n"
    )
    comments = [
        {
            "id": 1,
            "body": "<!-- section: 當前結論 owner: s -->\n內容",
            "updated_at": "2026-09-03T10:00:00Z",
            "created_at": "2026-09-03T09:17:38Z",
        },
        {
            "id": 2,
            "body": "一般觀測",
            "created_at": "2026-09-03T09:27:24Z",
        },
    ]
    with mock.patch.object(
        section_comment.subprocess, "run", side_effect=_show_side_effect(body, comments)
    ):
        rc = section_comment.main(["check", "81"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "comment 數：2" in out
    assert "[警訊 A][輔助] comment 數 2 未超過閾值 30（略過）" in out
    assert "[警訊 C] 索引一致：1 筆" in out
    assert "[警訊 B][主警訊] 未觸發" in out


def test_check_warning_a_triggers_over_custom_threshold(capsys):
    body = "## 摘要\n\n無索引"
    comments = [{"id": i, "body": "一般留言", "created_at": "2026-09-03T09:00:00Z"} for i in range(5)]
    with mock.patch.object(
        section_comment.subprocess, "run", side_effect=_show_side_effect(body, comments)
    ):
        rc = section_comment.main(["check", "81", "--comment-threshold", "3"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "[警訊 A][輔助] comment 數 5 超過閾值 3" in out


def test_check_warning_c_reports_index_actual_mismatch(capsys):
    """索引列出的 id 在實際 comment 中不存在（或非區段），須雙向列出差異。"""
    body = (
        "## 區段索引\n\n"
        "| 區段 | 永久連結 |\n"
        "|------|---------|\n"
        "| 當前結論 | https://github.com/tarrragon/claude/issues/81#issuecomment-1 |\n"
        "| 已刪除區段 | https://github.com/tarrragon/claude/issues/81#issuecomment-99 |\n"
    )
    comments = [
        {
            "id": 1,
            "body": "<!-- section: 當前結論 owner: s -->\n內容",
            "updated_at": "2026-09-03T10:00:00Z",
            "created_at": "2026-09-03T09:00:00Z",
        },
        {
            "id": 2,
            "body": "<!-- section: 未在索引的區段 owner: s -->\n內容",
            "updated_at": "2026-09-03T09:00:00Z",
            "created_at": "2026-09-03T09:00:00Z",
        },
    ]
    with mock.patch.object(
        section_comment.subprocess, "run", side_effect=_show_side_effect(body, comments)
    ):
        rc = section_comment.main(["check", "81"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "[警訊 C] 索引不一致：索引 2 筆、實際區段 2 筆" in out
    assert "索引缺漏的區段 comment id：[2]" in out
    assert "索引列出但實際非區段/不存在的 comment id：[99]" in out


def test_check_warning_b_triggers_and_lists_newer_observation_urls(capsys):
    """主警訊命中時，須列出當前結論 updated_at 之後新增的觀測 comment html_url。"""
    body = (
        "## 區段索引\n\n"
        "| 區段 | 永久連結 |\n"
        "|------|---------|\n"
        "| 當前結論 | https://github.com/tarrragon/claude/issues/81#issuecomment-1 |\n"
    )
    comments = [
        {
            "id": 1,
            "body": "<!-- section: 當前結論 owner: s -->\n內容",
            "updated_at": "2026-09-01T00:00:00Z",
            "created_at": "2026-08-30T00:00:00Z",
        },
        {
            "id": 2,
            "body": "新觀測 1",
            "created_at": "2026-09-02T00:00:00Z",
            "html_url": "https://github.com/tarrragon/claude/issues/81#issuecomment-2",
        },
        {
            "id": 3,
            "body": "新觀測 2",
            "created_at": "2026-09-03T00:00:00Z",
            "html_url": "https://github.com/tarrragon/claude/issues/81#issuecomment-3",
        },
    ]
    with mock.patch.object(
        section_comment.subprocess, "run", side_effect=_show_side_effect(body, comments)
    ):
        rc = section_comment.main(["check", "81", "--stale-days", "1"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "[警訊 B][主警訊] 觸發" in out
    assert "https://github.com/tarrragon/claude/issues/81#issuecomment-2" in out
    assert "https://github.com/tarrragon/claude/issues/81#issuecomment-3" in out


def test_check_warning_b_multiple_conclusion_sections_report_each_with_owner(capsys):
    """多 owner 情境：兩則「當前結論*」區段（含後綴區段）各自輸出警訊 B 判定並標 owner。"""
    body = "## 摘要\n\n無索引"
    comments = [
        {
            "id": 1,
            "body": "<!-- section: 當前結論 owner: flutter-balance-1 -->\n內容",
            "updated_at": "2026-09-01T00:00:00Z",
            "created_at": "2026-08-30T00:00:00Z",
        },
        {
            "id": 2,
            "body": "<!-- section: 當前結論（unipos：規則 8） owner: unipos-2 -->\n內容",
            "updated_at": "2026-09-05T00:00:00Z",
            "created_at": "2026-08-30T00:00:00Z",
        },
        {
            "id": 3,
            "body": "新觀測",
            "created_at": "2026-09-02T00:00:00Z",
            "html_url": "https://github.com/tarrragon/claude/issues/81#issuecomment-3",
        },
    ]
    with mock.patch.object(
        section_comment.subprocess, "run", side_effect=_show_side_effect(body, comments)
    ):
        rc = section_comment.main(["check", "81", "--stale-days", "0"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "[警訊 B][主警訊] 觸發：「當前結論」（owner: flutter-balance-1）" in out
    assert "https://github.com/tarrragon/claude/issues/81#issuecomment-3" in out
    assert (
        "[警訊 B][主警訊] 未觸發：「當前結論（unipos：規則 8）」（owner: unipos-2） "
        "updated_at=2026-09-05T00:00:00Z 無晚於此的觀測" in out
    )


def test_check_warning_b_no_conclusion_section_reports_not_found(capsys):
    body = "## 摘要\n\n無索引"
    comments = [
        {"id": 1, "body": "<!-- section: 方案評估 owner: s -->\n內容", "updated_at": "2026-09-01T00:00:00Z"},
    ]
    with mock.patch.object(
        section_comment.subprocess, "run", side_effect=_show_side_effect(body, comments)
    ):
        rc = section_comment.main(["check", "81"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "找不到「當前結論」區段 comment，無法比對" in out


def test_show_and_check_degrade_on_gh_failure(capsys):
    with mock.patch.object(
        section_comment.subprocess,
        "run",
        return_value=_completed(returncode=1, stderr="network error"),
    ):
        rc_show = section_comment.main(["show", "81"])
    assert rc_show == gh_common.EXIT_DEGRADED
    assert "network error" in capsys.readouterr().err

    with mock.patch.object(
        section_comment.subprocess,
        "run",
        return_value=_completed(returncode=1, stderr="network error"),
    ):
        rc_check = section_comment.main(["check", "81"])
    assert rc_check == gh_common.EXIT_DEGRADED
    assert "network error" in capsys.readouterr().err


# --- 待辦與來源：表格欄位與列舉驗證（寫入端 init/add/update 共用 validate_todo_table） ---

_VALID_TODO_TABLE = (
    "## 待辦與來源（flutter-balance）\n\n"
    "| 來源票 | 做什麼 | acceptance 條數 | 優先級 | 階段 | 狀態 |\n"
    "|--------|--------|----------------|--------|------|------|\n"
    "| imp-1 | 對帳工具：讀三份清單輸出差集 | 4 | P1 | 本版 | 待裁票 |\n"
)


def test_add_rejects_invalid_todo_status_lists_legal_values(tmp_path, capsys):
    """acceptance：add 對「待辦與來源」區段寫入狀態值「未執行」時 exit 3，
    印出全部五個合法值；驗證發生在任何 gh 呼叫之前（不燒查重／建立成本）。"""
    content_file = tmp_path / "todo.md"
    content_file.write_text(_VALID_TODO_TABLE.replace("待裁票", "未執行"), encoding="utf-8")

    with mock.patch.object(section_comment.subprocess, "run") as run:
        rc = section_comment.main(
            [
                "add", "81", "--owner", "test-session-1",
                "--name", "待辦與來源（flutter-balance）",
                "--content-file", str(content_file),
            ]
        )
    assert rc == gh_common.EXIT_DEGRADED
    err = capsys.readouterr().err
    for legal in section_comment.TODO_STATUS_VALUES:
        assert legal in err
    run.assert_not_called()


def test_init_rejects_invalid_todo_stage_value(tmp_path, capsys):
    """寫入端三入口共用同一驗證函式：init 對 sections-file 內「待辦與來源」
    區段的「階段」值同樣驗證，不合法自由文字（如「立即做」）exit 3。"""
    sections_file = tmp_path / "sections.json"
    sections_file.write_text(
        json.dumps(
            [
                {
                    "name": "待辦與來源（flutter-balance）",
                    "content": _VALID_TODO_TABLE.replace("本版", "立即做"),
                }
            ]
        ),
        encoding="utf-8",
    )

    with mock.patch.object(section_comment.subprocess, "run") as run:
        rc = section_comment.main(
            [
                "init", "81", "--owner", "test-session-1",
                "--sections-file", str(sections_file),
                "--dedup-keywords", "任意",
            ]
        )
    assert rc == gh_common.EXIT_DEGRADED
    err = capsys.readouterr().err
    for legal in section_comment.TODO_STAGE_VALUES:
        assert legal in err
    run.assert_not_called()


def test_add_accepts_valid_todo_table(tmp_path):
    """必要 6 欄、狀態與階段皆合法值的表格通過驗證，正常建立區段（放行路徑）。"""
    content_file = tmp_path / "todo.md"
    content_file.write_text(_VALID_TODO_TABLE, encoding="utf-8")
    existing_body = "## 摘要\n\n無索引表的一般內容"

    with mock.patch.object(
        section_comment.subprocess,
        "run",
        side_effect=_add_side_effect(
            ("https://github.com/tarrragon/claude/issues/81#issuecomment-9", 9),
            existing_body,
            {},
        ),
    ):
        rc = section_comment.main(
            [
                "add", "81", "--owner", "test-session-1",
                "--name", "待辦與來源（flutter-balance）",
                "--content-file", str(content_file),
            ]
        )
    assert rc == 0


def test_update_accepts_valid_todo_table_with_optional_type_column(tmp_path):
    """7 欄表頭（必要 6 欄 + 選填「型別」欄，插於「來源票」之後）為第二種
    合法表頭形態，通過驗證（放行路徑，覆蓋 update 入口與帶型別欄的表頭
    形態；欄位順序對齊既有 issue 實跑觀測到的慣例，見 TODO_HEADER_WITH_TYPE
    註解）。"""
    content_file = tmp_path / "todo.md"
    content_file.write_text(
        "## 待辦與來源（flutter-balance）\n\n"
        "| 來源票 | 型別 | 做什麼 | acceptance 條數 | 優先級 | 階段 | 狀態 |\n"
        "|--------|------|--------|----------------|--------|------|------|\n"
        "| imp-1 | IMP | 對帳工具 | 4 | P1 | 本版 | 待裁票 |\n",
        encoding="utf-8",
    )

    def _run(args, **kwargs):
        if args[:2] == ["gh", "api"] and "--method" not in args:
            return _completed(
                stdout=json.dumps(
                    {
                        "body": "<!-- section: 待辦與來源（flutter-balance） "
                        "owner: flutter-balance-99 -->\n舊內容"
                    }
                )
            )
        if "--method" in args and args[args.index("--method") + 1] == "PATCH":
            return _completed(stdout=json.dumps({"id": 5523472948}))
        raise AssertionError(f"未預期的 gh 呼叫：{args}")

    with mock.patch.object(section_comment.subprocess, "run", side_effect=_run):
        rc = section_comment.main(["update", "5523472948", "--content-file", str(content_file)])
    assert rc == 0


# --- todo：跨 open issue 聚合「待辦與來源*」區段表格列（讀取端） ---


def _todo_side_effect(comments_by_issue: dict, open_numbers: list = None):
    """依 gh 參數形態分派 todo 相關回應：`gh issue list`（open 清單，`--all`
    或預設範圍會觸發）／`gh api .../issues/<n>/comments`（per-issue
    comments，依 issue number 分派不同 payload，模擬多 issue 聚合場景）。
    """

    def _run(args, **kwargs):
        if args[:3] == ["gh", "issue", "list"]:
            numbers = open_numbers if open_numbers is not None else list(comments_by_issue.keys())
            return _completed(stdout=json.dumps([{"number": n} for n in numbers]))
        if args[:2] == ["gh", "api"] and args[2].endswith("/comments"):
            parts = args[2].split("/")
            number = int(parts[parts.index("issues") + 1])
            return _completed(stdout=json.dumps(comments_by_issue.get(number, [])))
        raise AssertionError(f"未預期的 gh 呼叫：{args}")

    return _run


def _todo_section_comment(comment_id: int, section_name: str, owner: str, table: str) -> dict:
    return {
        "id": comment_id,
        "body": f"<!-- section: {section_name} owner: {owner} -->\n{table}",
    }


def test_todo_json_aggregates_rows_with_required_fields(capsys):
    """acceptance：todo --json 輸出每列含 issue／owner／來源票／做什麼／
    階段／狀態／優先級／acceptance 條數。"""
    comments = [
        _todo_section_comment(1, "待辦與來源（flutter-balance）", "flutter-balance-77", _VALID_TODO_TABLE)
    ]
    with mock.patch.object(
        section_comment.subprocess, "run", side_effect=_todo_side_effect({81: comments})
    ):
        rc = section_comment.main(["todo", "--issue", "81", "--json"])
    assert rc == 0

    rows = json.loads(capsys.readouterr().out)
    assert len(rows) == 1
    row = rows[0]
    for key in ("issue", "owner", "來源票", "做什麼", "階段", "狀態", "優先級", "acceptance 條數"):
        assert key in row
    assert row["issue"] == 81
    assert row["owner"] == "flutter-balance-77"


def test_todo_warns_and_continues_on_mismatched_header(capsys):
    """acceptance：todo 對表頭不符的區段印警告並繼續，不中止——同一 issue
    內一則區段表頭不符，另一則合法區段的列仍正常聚合。"""
    bad_table = (
        "## 待辦與來源（bad）\n\n"
        "| 來源票 | 做什麼 |\n"
        "|--------|--------|\n"
        "| imp-1 | 對帳工具 |\n"
    )
    good_table = (
        "## 待辦與來源（good）\n\n"
        "| 來源票 | 做什麼 | acceptance 條數 | 優先級 | 階段 | 狀態 |\n"
        "|--------|--------|----------------|--------|------|------|\n"
        "| imp-2 | 補文件 | 2 | P2 | 下版 | 已裁票 |\n"
    )
    comments = [
        _todo_section_comment(1, "待辦與來源（bad）", "flutter-balance-77", bad_table),
        _todo_section_comment(2, "待辦與來源（good）", "flutter-balance-77", good_table),
    ]
    with mock.patch.object(
        section_comment.subprocess, "run", side_effect=_todo_side_effect({81: comments})
    ):
        rc = section_comment.main(["todo", "--issue", "81", "--json"])
    assert rc == 0

    captured = capsys.readouterr()
    rows = json.loads(captured.out)
    assert len(rows) == 1
    assert rows[0]["來源票"] == "imp-2"
    assert "表頭不符" in captured.err


def test_todo_filters_by_status(capsys):
    """--status 篩選：只列指定狀態值的列。"""
    table = (
        "## 待辦與來源（flutter-balance）\n\n"
        "| 來源票 | 做什麼 | acceptance 條數 | 優先級 | 階段 | 狀態 |\n"
        "|--------|--------|----------------|--------|------|------|\n"
        "| imp-1 | 對帳工具 | 4 | P1 | 本版 | 待裁票 |\n"
        "| imp-2 | 補文件 | 2 | P2 | 下版 | 已裁票 |\n"
    )
    comments = [_todo_section_comment(1, "待辦與來源（flutter-balance）", "flutter-balance-77", table)]
    with mock.patch.object(
        section_comment.subprocess, "run", side_effect=_todo_side_effect({81: comments})
    ):
        rc = section_comment.main(["todo", "--issue", "81", "--status", "待裁票", "--json"])
    assert rc == 0
    rows = json.loads(capsys.readouterr().out)
    assert len(rows) == 1
    assert rows[0]["來源票"] == "imp-1"


def test_todo_filters_by_consumer(capsys):
    """--consumer 篩選：`--all` 掃描多張 issue 時只列 owner 前綴符合的列。"""
    comments_81 = [
        _todo_section_comment(1, "待辦與來源（flutter-balance）", "flutter-balance-77", _VALID_TODO_TABLE)
    ]
    other_table = (
        "## 待辦與來源（other-project）\n\n"
        "| 來源票 | 做什麼 | acceptance 條數 | 優先級 | 階段 | 狀態 |\n"
        "|--------|--------|----------------|--------|------|------|\n"
        "| imp-9 | 其他任務 | 1 | P3 | 下版 | 待裁票 |\n"
    )
    comments_82 = [_todo_section_comment(2, "待辦與來源（other-project）", "other-project-3", other_table)]

    with mock.patch.object(
        section_comment.subprocess,
        "run",
        side_effect=_todo_side_effect(
            {81: comments_81, 82: comments_82}, open_numbers=[81, 82]
        ),
    ):
        rc = section_comment.main(["todo", "--all", "--consumer", "flutter-balance", "--json"])
    assert rc == 0

    rows = json.loads(capsys.readouterr().out)
    assert len(rows) == 1
    assert rows[0]["owner"] == "flutter-balance-77"
