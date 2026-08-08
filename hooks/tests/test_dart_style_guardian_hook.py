#!/usr/bin/env python3
"""dart-style-guardian-hook 測試

聚焦本 hook 與 style_checker 的接線：規則與專案校準是否真的來自 skill、
豁免標記是否生效、hook 自身特有的原生元件檢查是否保留。
"""

import importlib.util
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


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
