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
                "init", "81", "--owner", "test-session", "--sections-file", str(sections_file),
                "--dedup-keywords", "測試關鍵字",
            ]
        )
    assert rc == 0

    api_calls = [c for c in run.call_args_list if c.args[0][:2] == ["gh", "api"]]
    assert len(api_calls) == 2
    first_body = api_calls[0].args[0][-1]
    assert first_body == "body=<!-- section: 當前結論 owner: test-session -->\n## 當前結論\n內容 A"

    written_body = captured["body"]
    assert "既有內容" in written_body
    assert section_comment.INDEX_BEGIN in written_body
    assert "https://github.com/tarrragon/claude/issues/81#issuecomment-1" in written_body
    assert "https://github.com/tarrragon/claude/issues/81#issuecomment-2" in written_body


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
                    [{"number": 82, "title": "既有相關 issue", "url": "https://x/82", "state": "open"}]
                )
            )
        return _init_side_effect(post_urls, captured)(args, **kwargs)

    with mock.patch.object(section_comment.subprocess, "run", side_effect=_run):
        rc = section_comment.main(
            [
                "init", "81", "--owner", "test-session", "--sections-file", str(sections_file),
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
        call_count["n"] += 1
        if args[:3] == ["gh", "search", "issues"]:
            return _completed(stdout=json.dumps([]))
        if call_count["n"] == 2:
            return _completed(stdout=json.dumps({"id": 1, "html_url": "url-1"}))
        return _completed(returncode=1, stderr="API rate limit exceeded")

    with mock.patch.object(section_comment.subprocess, "run", side_effect=_run):
        rc = section_comment.main(
            [
                "init", "81", "--owner", "test-session", "--sections-file", str(sections_file),
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
            "init", "81", "--owner", "test-session", "--sections-file", str(sections_file),
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
            ["init", "81", "--owner", "test-session", "--sections-file", str(sections_file)]
        )
    assert exc_info.value.code == 2


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
    assert args[:4] == ["gh", "search", "issues", "元件契約"]
    assert "--repo" in args and args[args.index("--repo") + 1] == "tarrragon/claude"
    assert "--match" in args and args[args.index("--match") + 1] == "title,body,comments"


def test_search_issues_by_keyword_raises_on_gh_failure():
    with mock.patch.object(
        section_comment.subprocess,
        "run",
        return_value=_completed(returncode=1, stderr="rate limited"),
    ):
        with pytest.raises(RuntimeError, match="rate limited"):
            section_comment.search_issues_by_keyword("x")


def test_search_duplicates_unions_tokens_to_cover_cross_comment_terms():
    """重現並修正涵蓋缺口：關鍵字組「skill 拆分」單一 AND 查詢會漏掉某 issue
    （兩詞分屬同一 issue 的不同 comment，gh 多詞 AND 語意要求同一欄位實例內
    共現）；拆為單詞查詢後聯集才涵蓋。"""

    def _run(args, **kwargs):
        token = args[3]
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

    with mock.patch.object(section_comment.subprocess, "run", side_effect=_run):
        results = section_comment.search_duplicates(["skill 拆分"])
    numbers = sorted(issue["number"] for issue in results["skill 拆分"])
    assert numbers == [79, 82]


def test_search_duplicates_skips_failed_token_without_aborting_others(capsys):
    def _run(args, **kwargs):
        token = args[3]
        if token == "壞詞":
            return _completed(returncode=1, stderr="network error")
        return _completed(stdout=json.dumps([{"number": 1, "title": "t", "url": "u", "state": "open"}]))

    with mock.patch.object(section_comment.subprocess, "run", side_effect=_run):
        results = section_comment.search_duplicates(["壞詞", "好詞"])
    assert results["壞詞"] == []
    assert results["好詞"] == [{"number": 1, "title": "t", "url": "u", "state": "open"}]
    assert "壞詞" in capsys.readouterr().err


def test_render_dedup_report_lists_no_hit_group_and_footer():
    report = section_comment.render_dedup_report(["無命中詞"], {"無命中詞": []})
    assert "查重關鍵字集合（1 組）" in report
    assert "無命中詞" in report
    assert "無命中" in report
    assert "命中不等於重複" in report


def test_cmd_dedup_is_read_only_and_does_not_call_gh_issue_or_api():
    """dedup 子命令只呼叫 `gh search issues`，不觸碰 `gh issue` / `gh api`（不建立 issue）。"""
    with mock.patch.object(
        section_comment.subprocess, "run", return_value=_completed(stdout=json.dumps([]))
    ) as run:
        rc = section_comment.main(["dedup", "--keywords", "元件契約", "component"])
    assert rc == 0
    for call in run.call_args_list:
        assert call.args[0][:2] == ["gh", "search"]


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
    assert "當前結論 updated_at=2026-09-03T09:48:40Z" in out
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
    assert "當前結論 updated_at=2026-09-03T09:48:40Z" in out
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
