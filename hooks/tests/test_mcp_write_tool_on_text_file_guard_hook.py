"""
Test: mcp-write-tool-on-text-file-guard hook（Ticket: 0.18.0-W17-090）

驗證 PreToolUse hook 對 mcp__serena__ 寫入工具用於非程式碼檔的偵測：
1. 程式碼檔（.py / .js / .ts）→ 允許
2. .md → 拒絕（含 PC-112 引用）
3. .yaml → 拒絕
4. .json → 拒絕
5. 大小寫邊界（.MD / .YAML）→ 拒絕
6. 唯讀工具（find_symbol）→ 不在範圍（允許）
7. 多副檔名（.test.md）→ 拒絕

來源：W17-090 落地 PC-112 三層防護的 hook 強制層。
"""

import sys
from pathlib import Path

HOOKS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HOOKS_DIR))

import importlib.util

_spec = importlib.util.spec_from_file_location(
    "mcp_guard_hook",
    HOOKS_DIR / "mcp-write-tool-on-text-file-guard-hook.py",
)
_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_module)

is_serena_write_tool = _module.is_serena_write_tool
classify_extension = _module.classify_extension
is_non_code_file = _module.is_non_code_file
extract_file_path = _module.extract_file_path
build_deny_message = _module.build_deny_message


# ---------- is_serena_write_tool ----------

def test_serena_write_tools_recognised():
    for name in [
        "mcp__serena__replace_content",
        "mcp__serena__replace_symbol_body",
        "mcp__serena__insert_after_symbol",
        "mcp__serena__insert_before_symbol",
        "mcp__serena__safe_delete_symbol",
    ]:
        assert is_serena_write_tool(name), f"{name} 應屬於寫入工具"


def test_readonly_serena_tool_not_in_scope():
    """find_symbol / get_symbols_overview 為唯讀，不在本 hook 範圍。"""
    assert not is_serena_write_tool("mcp__serena__find_symbol")
    assert not is_serena_write_tool("mcp__serena__get_symbols_overview")
    assert not is_serena_write_tool("Edit")
    assert not is_serena_write_tool("Write")


# ---------- classify_extension ----------

def test_classify_extension_basic():
    assert classify_extension("foo.md") == ".md"
    assert classify_extension("foo.py") == ".py"
    assert classify_extension("a/b/c.yaml") == ".yaml"


def test_classify_extension_case_insensitive():
    assert classify_extension("README.MD") == ".md"
    assert classify_extension("Config.YAML") == ".yaml"


def test_classify_extension_multi_dot():
    """多副檔名取最後一個（.test.md → .md）。"""
    assert classify_extension("foo.test.md") == ".md"
    assert classify_extension("a.b.c.json") == ".json"


def test_classify_extension_no_extension():
    assert classify_extension("Makefile") == ""
    assert classify_extension("") == ""


# ---------- is_non_code_file ----------

def test_non_code_extensions_detected():
    for path in ["a.md", "a.txt", "a.yaml", "a.yml", "a.json", "a.toml"]:
        assert is_non_code_file(path), f"{path} 應屬非程式碼類"


def test_non_code_extensions_case_insensitive():
    for path in ["README.MD", "data.YAML", "pkg.JSON"]:
        assert is_non_code_file(path), f"{path} 應屬非程式碼類（大小寫不敏感）"


def test_code_extensions_pass_through():
    for path in ["main.py", "app.js", "index.ts", "lib.dart", "tool.go", "Makefile"]:
        assert not is_non_code_file(path), f"{path} 不應被視為非程式碼類"


def test_multi_dot_test_md_blocked():
    """多副檔名邊界：foo.test.md 視為 .md，應屬非程式碼類。"""
    assert is_non_code_file("foo.test.md")


# ---------- extract_file_path ----------

def test_extract_file_path_prefers_relative_path():
    assert extract_file_path({"relative_path": "a.md", "file_path": "/abs/b.md"}) == "a.md"


def test_extract_file_path_fallback_to_file_path():
    assert extract_file_path({"file_path": "b.md"}) == "b.md"


def test_extract_file_path_empty():
    assert extract_file_path({}) == ""
    assert extract_file_path({"relative_path": "", "file_path": ""}) == ""


# ---------- build_deny_message ----------

def test_build_deny_message_contains_pc112_and_rule_reference():
    msg = build_deny_message("mcp__serena__replace_content", "docs/foo.md", ".md")
    assert "PC-112" in msg
    assert "tool-selection.md" in msg
    assert "Edit" in msg
    assert "docs/foo.md" in msg
