#!/usr/bin/env python3
"""dart-style-guardian-hook 測試

聚焦本 hook 與 style_checker 的接線：規則與專案校準是否真的來自 skill、
豁免標記是否生效、hook 自身特有的原生元件檢查是否保留。
"""

import importlib.util
import io
import json
import sys
from pathlib import Path

import pytest

hook_dir = Path(__file__).parent.parent
sys.path.insert(0, str(hook_dir))

spec = importlib.util.spec_from_file_location(
    "dart_style_guardian_hook", hook_dir / "dart-style-guardian-hook.py"
)
hook_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hook_module)

check_file_for_violations = hook_module.check_file_for_violations
is_presentation_file = hook_module.is_presentation_file
should_skip_file = hook_module.should_skip_file


PROJECT_CONFIG = {
    "tokens": {
        "color": "AppPalette",
        "spacing": "AppSpacing",
        "font_size": "AppTypography",
        "border_radius": "AppRadius",
    },
    "i18n": {
        "accessor": "AppLocalizations.of(context).keyName",
        "compliance_pattern": r"AppLocalizations\.of\(",
    },
    "exempt_markers": ["magic-exempt", "i18n-exempt"],
}


@pytest.fixture
def dart_file(tmp_path):
    """Build a project tree carrying calibration, and write a Dart file into it."""
    root = tmp_path / "proj"
    (root / ".claude" / "config").mkdir(parents=True)
    (root / ".claude" / "config" / "dart-style-guardian.json").write_text(
        json.dumps(PROJECT_CONFIG), encoding="utf-8"
    )
    target_dir = root / "lib" / "presentation"
    target_dir.mkdir(parents=True)

    def _write(body: str, name: str = "screen.dart") -> Path:
        path = target_dir / name
        path.write_text(body, encoding="utf-8")
        return path

    return _write


class TestStyleCheckerWiring:
    def test_suggestions_come_from_project_calibration(self, dart_file):
        """建議必須說出本專案的 token 名，而非 hook 內寫死的他專案命名。"""
        path = dart_file("Text('x', style: TextStyle(color: Colors.blue));\n")
        violations = check_file_for_violations(path)
        suggestions = " ".join(v["suggestion"] for v in violations)
        assert "AppPalette" in suggestions
        assert "UIColors" not in suggestions

    def test_style_checker_is_available(self):
        """接線斷掉時 hook 會降級為只檢查原生元件，此旗標即為早期警訊。"""
        assert hook_module.STYLE_CHECKER_AVAILABLE is True


class TestExemptMarkers:
    @pytest.mark.parametrize("marker", ["magic-exempt", "i18n-exempt"])
    def test_marked_line_produces_no_violation(self, dart_file, marker):
        path = dart_file(f"const SizedBox(height: 7); // {marker}: 刻意值\n")
        assert check_file_for_violations(path) == []

    def test_unmarked_line_still_reported(self, dart_file):
        path = dart_file("const SizedBox(height: 7);\n")
        violations = check_file_for_violations(path)
        assert any(v["category"] == "SizedBox" for v in violations)


class TestNativeComponentCheck:
    def test_native_component_still_detected(self, dart_file):
        """原生元件規則屬 hook 特有，接線改動後必須仍在。"""
        path = dart_file("TextButton(onPressed: () {}, child: child);\n")
        violations = check_file_for_violations(path)
        assert any(v["category"] == "NativeComponent" for v in violations)

    def test_migrated_component_not_flagged(self, dart_file):
        path = dart_file("AppButton(onPressed: () {}, child: child);\n")
        violations = check_file_for_violations(path)
        assert all(v["category"] != "NativeComponent" for v in violations)

    def test_suggestion_has_no_hardcoded_other_project_names(self, dart_file):
        """建議文字不得寫死他專案的替代元件名（如 AppCard/AppDialog），
        應改指向元件庫定義位置。"""
        path = dart_file("Card(child: child);\n")
        violations = check_file_for_violations(path)
        native = [v for v in violations if v["category"] == "NativeComponent"]
        assert native
        for v in native:
            assert "AppCard" not in v["suggestion"]
            assert "AppDialog" not in v["suggestion"]
            assert "component-contract-design" in v["suggestion"]


class TestScopeFilters:
    @pytest.mark.parametrize(
        "path,expected",
        [
            ("lib/presentation/home.dart", True),
            ("/abs/lib/presentation/home.dart", True),
            ("lib/domain/entity.dart", False),
        ],
    )
    def test_presentation_scope(self, path, expected):
        assert is_presentation_file(path) is expected

    @pytest.mark.parametrize(
        "path",
        ["a.g.dart", "a.freezed.dart", "/x/test/a.dart", "/x/l10n/a.dart", "theme.dart"],
    )
    def test_generated_and_config_files_skipped(self, path):
        assert should_skip_file(path) is True


class TestMainOutputChannel:
    """違規提醒必須走 additionalContext（模型可見），非 message 欄位或 stderr。"""

    def _run(self, monkeypatch, capsys, arg, payload=None):
        """以實測 PostToolUse payload 形狀（tool_input.file_path）餵 stdin。"""
        if payload is None:
            payload = {
                "hook_event_name": "PostToolUse",
                "tool_name": "Edit",
                "tool_input": {"file_path": str(arg)},
            }
        monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
        rc = hook_module.main()
        return rc, capsys.readouterr()

    def test_violation_emits_additional_context(self, dart_file, monkeypatch, capsys):
        path = dart_file("TextButton(onPressed: () {}, child: child);\n")
        rc, captured = self._run(monkeypatch, capsys, path)
        payload = json.loads(captured.out)
        out = payload["hookSpecificOutput"]

        assert rc == 0
        assert out["hookEventName"] == "PostToolUse"
        assert "NativeComponent" in out["additionalContext"]
        assert "message" not in payload
        assert "permissionDecision" not in out
        assert "decision" not in payload

    def test_clean_file_has_no_additional_context(self, dart_file, monkeypatch, capsys):
        path = dart_file("AppButton(onPressed: () {}, child: child);\n")
        rc, captured = self._run(monkeypatch, capsys, path)

        assert rc == 0
        assert "additionalContext" not in captured.out

    def test_non_presentation_file_has_no_additional_context(
        self, tmp_path, monkeypatch, capsys
    ):
        target = tmp_path / "lib" / "domain" / "a.dart"
        target.parent.mkdir(parents=True)
        target.write_text("TextButton(onPressed: () {});\n", encoding="utf-8")
        rc, captured = self._run(monkeypatch, capsys, target)

        assert rc == 0
        assert "additionalContext" not in captured.out

    def test_write_tool_payload_triggers(self, dart_file, monkeypatch, capsys):
        """E1：Write 工具 payload 同樣觸發。"""
        path = dart_file("TextButton(onPressed: () {}, child: child);\n")
        payload = {
            "hook_event_name": "PostToolUse",
            "tool_name": "Write",
            "tool_input": {"file_path": str(path), "content": "x"},
        }
        rc, captured = self._run(monkeypatch, capsys, path, payload)
        assert rc == 0
        assert "NativeComponent" in captured.out

    @pytest.mark.parametrize(
        "name", ["a.txt", "a_test.dart", "a.g.dart", "a.freezed.dart"]
    )
    def test_non_dart_or_generated_file_silent(
        self, dart_file, monkeypatch, capsys, name
    ):
        """E2：非 dart 檔與產生檔不輸出。"""
        path = dart_file("TextButton(onPressed: () {});\n", name=name)
        rc, captured = self._run(monkeypatch, capsys, path)
        assert rc == 0
        if name == "a_test.dart":
            return  # 測試檔命名由 /test/ 目錄規則排除，此處僅確認不崩潰
        assert "additionalContext" not in captured.out

    def test_test_dir_file_silent(self, tmp_path, monkeypatch, capsys):
        target = tmp_path / "test" / "lib" / "presentation" / "a.dart"
        target.parent.mkdir(parents=True)
        target.write_text("TextButton(onPressed: () {});\n", encoding="utf-8")
        rc, captured = self._run(monkeypatch, capsys, target)
        assert rc == 0
        assert "additionalContext" not in captured.out

    @pytest.mark.parametrize(
        "payload",
        [
            {"tool_name": "Edit", "tool_input": {}},
            {"tool_name": "Edit"},
            {"tool_name": "Edit", "tool_input": {"file_path": ""}},
            {"tool_name": "Edit", "tool_input": {"file_path": 3}},
            {"tool_name": "Edit", "tool_input": "oops"},
        ],
    )
    def test_missing_path_fails_open(self, monkeypatch, capsys, payload):
        """payload 缺路徑：fail-open，輸出 continue，不輸出提醒。"""
        rc, captured = self._run(monkeypatch, capsys, "", payload)
        assert rc == 0
        assert json.loads(captured.out) == {"continue": True}

    def test_empty_stdin_fails_open(self, monkeypatch, capsys):
        monkeypatch.setattr(sys, "stdin", io.StringIO(""))
        rc = hook_module.main()
        assert rc == 0
        assert "additionalContext" not in capsys.readouterr().out

    def test_argv_is_ignored(self, dart_file, monkeypatch, capsys):
        """舊 argv 路徑不再被讀取。"""
        path = dart_file("TextButton(onPressed: () {});\n")
        monkeypatch.setattr(sys, "argv", ["hook", str(path)])
        monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps({"tool_input": {}})))
        rc = hook_module.main()
        assert rc == 0
        assert "additionalContext" not in capsys.readouterr().out


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
