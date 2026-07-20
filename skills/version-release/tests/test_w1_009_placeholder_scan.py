"""
0.38.1-W1-009: version-release check 補佔位掃描測試

覆蓋 check_placeholder_implementations()：
1. 無 lib/ 目錄時視為通過
2. lib/ 存在但無佔位命中時通過
3. 命中 ComingSoon / UnimplementedError / 空 onPressed 三類模式時回傳命中清單
4. preflight_check() 佔位命中不影響 all_ok（WARNING only）
"""

import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import version_release as vr  # noqa: E402


class TestCheckPlaceholderImplementations:
    def test_missing_lib_dir_passes(self, tmp_path):
        """lib/ 目錄不存在時視為通過（無佔位）"""
        passed, hits = vr.check_placeholder_implementations(tmp_path / "lib")

        assert passed is True
        assert hits == []

    def test_no_placeholder_hits_passes(self, tmp_path):
        """lib/ 存在但檔案內無佔位模式時通過"""
        lib_dir = tmp_path / "lib"
        lib_dir.mkdir()
        (lib_dir / "main.dart").write_text(
            "void main() { runApp(MyApp()); }\n", encoding="utf-8"
        )

        passed, hits = vr.check_placeholder_implementations(lib_dir)

        assert passed is True
        assert hits == []

    def test_coming_soon_placeholder_detected(self, tmp_path):
        """ComingSoon 佔位頁命中"""
        lib_dir = tmp_path / "lib"
        lib_dir.mkdir()
        (lib_dir / "router.dart").write_text(
            "final page = ComingSoon();\n", encoding="utf-8"
        )

        passed, hits = vr.check_placeholder_implementations(lib_dir)

        assert passed is False
        assert len(hits) == 1
        assert "router.dart:1:" in hits[0]

    def test_unimplemented_error_detected(self, tmp_path):
        """佔位 provider（UnimplementedError）命中"""
        lib_dir = tmp_path / "lib"
        lib_dir.mkdir()
        (lib_dir / "provider.dart").write_text(
            "throw UnimplementedError('todo');\n", encoding="utf-8"
        )

        passed, hits = vr.check_placeholder_implementations(lib_dir)

        assert passed is False
        assert "provider.dart" in hits[0]

    def test_empty_onpressed_detected(self, tmp_path):
        """空 onPressed callback 命中"""
        lib_dir = tmp_path / "lib"
        lib_dir.mkdir()
        (lib_dir / "button.dart").write_text(
            "AppButton(onPressed: () {});\n", encoding="utf-8"
        )

        passed, hits = vr.check_placeholder_implementations(lib_dir)

        assert passed is False
        assert "button.dart" in hits[0]

    def test_nested_directory_scanned(self, tmp_path):
        """遞迴掃描子目錄"""
        lib_dir = tmp_path / "lib"
        nested = lib_dir / "presentation" / "home"
        nested.mkdir(parents=True)
        (nested / "home_screen.dart").write_text(
            "final flag = featureInDevelopment;\n", encoding="utf-8"
        )

        passed, hits = vr.check_placeholder_implementations(lib_dir)

        assert passed is False
        assert "home_screen.dart" in hits[0]

    def test_non_dart_files_ignored(self, tmp_path):
        """非 .dart 檔案不掃描"""
        lib_dir = tmp_path / "lib"
        lib_dir.mkdir()
        (lib_dir / "notes.txt").write_text("ComingSoon\n", encoding="utf-8")

        passed, hits = vr.check_placeholder_implementations(lib_dir)

        assert passed is True
        assert hits == []


class TestSilentPlaceholderDetection:
    """W1-117: 靜默佔位偵測（佔位關鍵字註解 + return 空值）"""

    def test_w1_116_regression_sample(self, tmp_path):
        """W1-116 修復前的 _queryBooks 佔位模式應被偵測"""
        lib_dir = tmp_path / "lib"
        lib_dir.mkdir()
        (lib_dir / "export_books_usecase.dart").write_text(
            "  Future<List<Book>> _queryBooks() async {\n"
            "    // 暫時實作：使用簡單的書籍查詢\n"
            "    // 完整實作應根據 request.range 和 selectedSources 過濾\n"
            "    return [];\n"
            "  }\n",
            encoding="utf-8",
        )

        passed, hits = vr.check_placeholder_implementations(lib_dir)

        assert passed is False
        assert len(hits) == 1
        assert "[silent-placeholder]" in hits[0]
        assert "return []" in hits[0]

    def test_todo_with_return_null_detected(self, tmp_path):
        """TODO 註解 + return null 組合應偵測"""
        lib_dir = tmp_path / "lib"
        lib_dir.mkdir()
        (lib_dir / "service.dart").write_text(
            "  // TODO: implement real logic\n"
            "  return null;\n",
            encoding="utf-8",
        )

        passed, hits = vr.check_placeholder_implementations(lib_dir)

        assert passed is False
        assert "[silent-placeholder]" in hits[0]

    def test_placeholder_comment_with_return_false_detected(self, tmp_path):
        """placeholder 註解 + return false 組合應偵測"""
        lib_dir = tmp_path / "lib"
        lib_dir.mkdir()
        (lib_dir / "checker.dart").write_text(
            "  // placeholder until auth is ready\n"
            "  return false;\n",
            encoding="utf-8",
        )

        passed, hits = vr.check_placeholder_implementations(lib_dir)

        assert passed is False

    def test_legitimate_empty_return_not_detected(self, tmp_path):
        """合法的空回傳（無佔位關鍵字）不應誤報"""
        lib_dir = tmp_path / "lib"
        lib_dir.mkdir()
        (lib_dir / "repo.dart").write_text(
            "  Future<List<Book>> getBooks() async {\n"
            "    // No books in cache\n"
            "    return [];\n"
            "  }\n",
            encoding="utf-8",
        )

        passed, hits = vr.check_placeholder_implementations(lib_dir)

        assert passed is True
        assert hits == []

    def test_comment_beyond_lookahead_not_detected(self, tmp_path):
        """佔位註解超出 lookahead 距離（3 行）的 return 不應偵測"""
        lib_dir = tmp_path / "lib"
        lib_dir.mkdir()
        (lib_dir / "service.dart").write_text(
            "  // TODO: implement\n"
            "  final a = 1;\n"
            "  final b = 2;\n"
            "  final c = 3;\n"
            "  return [];\n",
            encoding="utf-8",
        )

        passed, hits = vr.check_placeholder_implementations(lib_dir)

        assert passed is True
        assert hits == []


class TestPreflightCheckPlaceholderIntegration:
    def test_placeholder_hits_do_not_block_all_ok(self, tmp_path):
        """佔位命中僅 WARNING，不影響 all_ok（不阻擋發布）"""
        lib_dir = tmp_path / "lib"
        lib_dir.mkdir()
        (lib_dir / "router.dart").write_text(
            "final page = ComingSoon();\n", encoding="utf-8"
        )

        with patch.object(vr, "get_project_root", return_value=tmp_path), \
             patch.object(vr, "check_worklog_completed", return_value=(True, [])), \
             patch.object(
                 vr,
                 "check_technical_debt_status",
                 return_value={"passed": True, "message": "ok", "skipped": False, "pending_tds": []},
             ), \
             patch.object(vr, "check_technical_debt", return_value=(True, [])), \
             patch.object(vr, "check_previous_versions_completed", return_value=(True, [])), \
             patch.object(vr, "check_stale_active_versions", return_value=(True, [])), \
             patch.object(vr, "check_version_sync", return_value=(True, [])), \
             patch.object(vr, "check_memory_upgrade_status", return_value=(True, ["ok"])):
            all_ok, results = vr.preflight_check("1.0.0")

        assert all_ok is True
        ph_ok, ph_hits = results["placeholder_scan"]
        assert ph_ok is False
        assert len(ph_hits) == 1
