"""--where 路徑 token 驗證測試。

動機：ticket create --where 曾靜默接受 'src=.claude/x' 當檔案路徑，髒值寫進
where.files 後致 dispatch hook 的路徑分類誤判（含 'src=' 前綴被當非框架路徑），
級聯成 worktree 誤強制與派發誤診。前置驗證從輸入端攔下整個缺陷類別。

驗證規則：路徑 token 的「第一段」（首個 '/' 之前）若含 '='，視為前綴髒值
（如 src=、layer=）並 reject；正常相對 / 絕對路徑 100% 放行不誤殺，路徑
中段含 '=' 的合法情況亦放行。

涵蓋：
- 髒值 reject：src=.claude/x、layer=core
- 正常放行：.claude/x、src/y、a/b.py、絕對路徑
- 邊界：路徑中段含 '=' 的合法路徑放行；含 '=' 的檔名放行
"""

import pytest

from ticket_system.commands.create import (
    _validate_where_file_token,
    _validate_where_files,
)


class TestValidateWhereFileToken:
    """單一路徑 token 驗證。"""

    # --- 髒值 reject（第一段含 '='） ---

    def test_prefix_src_equals_rejected(self):
        is_valid, _ = _validate_where_file_token("src=.claude/x")
        assert is_valid is False

    def test_prefix_layer_equals_rejected(self):
        is_valid, _ = _validate_where_file_token("layer=core")
        assert is_valid is False

    def test_prefix_equals_no_slash_rejected(self):
        # 整段即一個 key=value，無路徑分隔
        is_valid, _ = _validate_where_file_token("where=foo")
        assert is_valid is False

    def test_reject_returns_hint(self):
        is_valid, hint = _validate_where_file_token("src=.claude/x")
        assert is_valid is False
        assert hint
        # 修正提示應含剝除前綴後的建議路徑
        assert ".claude/x" in hint

    # --- 正常放行 ---

    def test_claude_path_allowed(self):
        is_valid, _ = _validate_where_file_token(".claude/skills/ticket/x.py")
        assert is_valid is True

    def test_src_path_allowed(self):
        is_valid, _ = _validate_where_file_token("src/background/index.js")
        assert is_valid is True

    def test_relative_path_allowed(self):
        is_valid, _ = _validate_where_file_token("a/b.py")
        assert is_valid is True

    def test_absolute_path_allowed(self):
        is_valid, _ = _validate_where_file_token("/Users/x/project/file.py")
        assert is_valid is True

    def test_single_file_no_slash_allowed(self):
        is_valid, _ = _validate_where_file_token("README.md")
        assert is_valid is True

    # --- 邊界：'=' 在中段或檔名中（合法） ---

    def test_equals_in_mid_segment_allowed(self):
        # '=' 出現在第一段之後（路徑中段），屬合法檔名字元
        is_valid, _ = _validate_where_file_token("src/a=b/c.py")
        assert is_valid is True

    def test_equals_in_filename_allowed(self):
        is_valid, _ = _validate_where_file_token("docs/report=final.md")
        assert is_valid is True

    # --- 空字串視為合法（由上游過濾，不在此 reject） ---

    def test_empty_token_allowed(self):
        is_valid, _ = _validate_where_file_token("")
        assert is_valid is True


class TestValidateWhereFiles:
    """批次驗證：回傳 (errors, files)。"""

    def test_all_valid_returns_no_errors(self):
        errors = _validate_where_files([".claude/x", "src/y", "a/b.py"])
        assert errors == []

    def test_dirty_token_collected(self):
        errors = _validate_where_files(["src=.claude/x", "src/y"])
        assert len(errors) == 1
        assert "src=.claude/x" in errors[0]

    def test_multiple_dirty_tokens_all_collected(self):
        errors = _validate_where_files(["src=.claude/x", "layer=core"])
        assert len(errors) == 2

    def test_empty_list_no_errors(self):
        assert _validate_where_files([]) == []
