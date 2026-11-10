"""PEP 723 內嵌依賴為專案環境子集的不變式驗證

背景：`0.0.1-W1-012` 將正式測試指令定為 `uv run --directory .claude/hooks pytest`，
依賴改由 `.claude/hooks/pyproject.toml` 與 `uv.lock` 提供，不再手動補 `--with` 旗標。

此設計成立的前提是——tests/ 下各檔以 PEP 723 內嵌宣告的依賴，不超出專案環境
實際安裝的套件集合。若某測試檔宣告了環境沒有的套件，正式指令會再度出現
`ModuleNotFoundError` + `Interrupted: N errors during collection`，且失敗形態與
W1-012 修復前完全相同，難以分辨是新的依賴缺口或舊問題復發。

在 `0.0.1-W1-015` 之前，此不變式僅由 `tests/README.md` 的一行維護提醒防守。依
`opinionated-default-design` 主張 1，以文件提醒守護不變式正是工具預設不足的信號，
故本模組將其轉為機械驗證。

**可用套件集合的定義**：`uv run --directory` 會安裝專案本身（帶入
`[project].dependencies`）並預設啟用 `dev` 依賴群組，故可用集合為兩者聯集。實測佐證：
`pytest` 僅宣告於 dev group 而未見於 `[project].dependencies`，在專案環境中確實可用。
"""

import re
import tomllib
from pathlib import Path

import pytest


_TESTS_DIR = Path(__file__).parent
_PYPROJECT_PATH = _TESTS_DIR.parent / "pyproject.toml"

# PEP 723 規範的區塊擷取式（取自 PEP 723 reference implementation）。
# 錨定行首與行尾是關鍵：程式碼中縮排的字串常值（如 `assert "# /// script" in text`）
# 不得被誤判為真正的 metadata 區塊。
_PEP723_BLOCK = re.compile(
    r"(?m)^# /// (?P<type>[a-zA-Z0-9-]+)$\s(?P<content>(^#(| .*)$\s)+)^# ///$"
)


def normalize_package_name(requirement: str) -> str:
    """從 PEP 508 需求字串取出套件名並依 PEP 503 正規化。

    `pyyaml>=6.0` -> `pyyaml`、`PyYAML` -> `pyyaml`、`foo[extra]>=1.0` -> `foo`。
    正規化後才比對，避免大小寫或 `-`/`_`/`.` 寫法差異造成誤報。
    """
    name = re.split(r"[<>=!~;@\[\s(]", requirement.strip(), maxsplit=1)[0]
    return re.sub(r"[-_.]+", "-", name).lower()


def extract_pep723_dependencies(source: str) -> "list[str] | None":
    """擷取 Python 原始碼中 PEP 723 script 區塊宣告的 dependencies。

    Returns:
        依賴字串列表；若檔案沒有 script 區塊則回傳 None（與「有區塊但依賴為空」區分）。
    """
    for match in _PEP723_BLOCK.finditer(source):
        if match.group("type") != "script":
            continue
        content = "".join(
            line[2:] if line.startswith("# ") else line[1:]
            for line in match.group("content").splitlines(keepends=True)
        )
        return tomllib.loads(content).get("dependencies", [])
    return None


def available_packages(pyproject_text: str) -> "set[str]":
    """解析 pyproject.toml，取得專案環境預設安裝的套件集合（正規化後）。

    來源為 `[project].dependencies` 與 `[dependency-groups].dev` 的聯集，
    對應 `uv run --directory` 的預設行為。
    """
    data = tomllib.loads(pyproject_text)
    declared = list(data.get("project", {}).get("dependencies", []))
    declared += list(data.get("dependency-groups", {}).get("dev", []))
    return {normalize_package_name(item) for item in declared}


def scan_dependency_violations(
    tests_dir: Path, available: "set[str]"
) -> "dict[str, set[str]]":
    """掃描目錄下所有測試檔，回報 PEP 723 依賴超出可用集合的部分。

    Returns:
        {檔名: 超出的套件名集合}，僅包含有違反的檔案。
    """
    violations = {}
    for path in sorted(tests_dir.glob("test_*.py")):
        declared = extract_pep723_dependencies(path.read_text(encoding="utf-8"))
        if not declared:
            continue
        extras = {normalize_package_name(item) for item in declared} - available
        if extras:
            violations[path.name] = extras
    return violations


class TestPep723BlockExtraction:
    """PEP 723 區塊擷取的正確性"""

    def test_extracts_declared_dependencies(self):
        source = (
            "# /// script\n"
            '# requires-python = ">=3.10"\n'
            "# dependencies = [\n"
            '#     "pytest>=7.0",\n'
            '#     "pyyaml>=6.0",\n'
            "# ]\n"
            "# ///\n"
            "import pytest\n"
        )
        assert extract_pep723_dependencies(source) == ["pytest>=7.0", "pyyaml>=6.0"]

    def test_returns_none_when_no_block(self):
        assert extract_pep723_dependencies("import pytest\n\n\ndef test_x():\n    pass\n") is None

    def test_returns_empty_list_for_block_without_dependencies(self):
        source = "# /// script\n" '# requires-python = ">=3.10"\n' "# ///\n"
        assert extract_pep723_dependencies(source) == []

    def test_ignores_indented_string_literal(self):
        """縮排的字串常值不得被當成 metadata 區塊。

        `test_wrap_decision_tripwire_hook.py` 內有
        `assert "# /// script" in text`——該處斷言的是受測 hook 檔含 metadata，
        測試檔本身並無區塊。以未錨定的子字串搜尋會將其誤計為 PEP 723 檔案。
        """
        source = (
            "def test_hook_has_metadata():\n"
            "    text = HOOK_PATH.read_text()\n"
            '    assert "# /// script" in text\n'
            '    assert "pyyaml" in text\n'
        )
        assert extract_pep723_dependencies(source) is None


class TestPackageNameNormalization:
    """套件名正規化"""

    @pytest.mark.parametrize(
        "requirement,expected",
        [
            ("pytest", "pytest"),
            ("pytest>=7.0", "pytest"),
            ("PyYAML", "pyyaml"),
            ("pyyaml>=6.0", "pyyaml"),
            ("types_PyYAML", "types-pyyaml"),
            ("foo[extra]>=1.0", "foo"),
            ("foo @ https://example.com/foo.whl", "foo"),
            ('bar ; python_version < "3.11"', "bar"),
        ],
    )
    def test_normalizes_to_comparable_name(self, requirement, expected):
        assert normalize_package_name(requirement) == expected


class TestAvailablePackages:
    """pyproject.toml 可用套件集合解析"""

    def test_unions_project_dependencies_and_dev_group(self):
        pyproject = (
            "[project]\n"
            'name = "x"\n'
            'dependencies = ["pyyaml>=6.0"]\n'
            "\n"
            "[dependency-groups]\n"
            'dev = ["pytest>=7.0"]\n'
        )
        assert available_packages(pyproject) == {"pyyaml", "pytest"}

    def test_tolerates_missing_sections(self):
        assert available_packages('[project]\nname = "x"\n') == set()


class TestViolationScan:
    """違反偵測與回報"""

    def test_detects_dependency_outside_available_set(self, tmp_path):
        (tmp_path / "test_offender.py").write_text(
            "# /// script\n"
            "# dependencies = [\n"
            '#     "pytest",\n'
            '#     "requests>=2.0",\n'
            "# ]\n"
            "# ///\n",
            encoding="utf-8",
        )
        violations = scan_dependency_violations(tmp_path, {"pytest", "pyyaml"})

        assert violations == {"test_offender.py": {"requests"}}

    def test_reports_every_offending_file(self, tmp_path):
        for name, package in [("test_a.py", "requests"), ("test_b.py", "httpx")]:
            (tmp_path / name).write_text(
                f'# /// script\n# dependencies = ["{package}"]\n# ///\n',
                encoding="utf-8",
            )
        violations = scan_dependency_violations(tmp_path, {"pytest"})

        assert violations == {"test_a.py": {"requests"}, "test_b.py": {"httpx"}}

    def test_clean_directory_yields_no_violations(self, tmp_path):
        (tmp_path / "test_ok.py").write_text(
            '# /// script\n# dependencies = ["pytest"]\n# ///\n', encoding="utf-8"
        )
        (tmp_path / "test_plain.py").write_text("def test_x():\n    pass\n", encoding="utf-8")

        assert scan_dependency_violations(tmp_path, {"pytest", "pyyaml"}) == {}

    def test_case_and_separator_differences_are_not_violations(self, tmp_path):
        (tmp_path / "test_case.py").write_text(
            '# /// script\n# dependencies = ["PyYAML>=6.0"]\n# ///\n', encoding="utf-8"
        )

        assert scan_dependency_violations(tmp_path, {"pyyaml"}) == {}


class TestRepositoryInvariant:
    """本 repo 現況的不變式"""

    def test_tests_pep723_dependencies_are_subset_of_project_environment(self):
        available = available_packages(_PYPROJECT_PATH.read_text(encoding="utf-8"))
        violations = scan_dependency_violations(_TESTS_DIR, available)

        assert violations == {}, (
            "下列測試檔的 PEP 723 依賴超出專案環境可用範圍，"
            "`uv run --directory .claude/hooks pytest` 將出現 ModuleNotFoundError：\n"
            + "\n".join(
                f"  {name}: 缺少 {sorted(packages)}"
                for name, packages in sorted(violations.items())
            )
            + f"\n可用套件：{sorted(available)}"
            + "\n處置：將缺少的套件加入 .claude/hooks/pyproject.toml 的 "
            "[dependency-groups].dev，或改用環境已有的套件。"
        )

    def test_project_environment_declares_expected_baseline(self):
        """dev group 至少須含 pytest 與 pyyaml——移除任一都會使全量指令失效。"""
        available = available_packages(_PYPROJECT_PATH.read_text(encoding="utf-8"))

        assert {"pytest", "pyyaml"} <= available
