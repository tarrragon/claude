"""agent-dispatch-validation-hook _classify_paths（where.files 分類）的目錄邊界與磁碟機路徑。

驗證：
1. 同字首他 repo 的 .claude/（/a/proj2/.claude/ 對根 /a/proj）判為外部（修正前判主 repo）
2. 本 repo 的 Windows 磁碟機 .claude/ 路徑判為主 repo：
   正斜線修正前判外部、反斜線修正前判 other；代號大小寫不同仍屬本 repo
3. E2 正向對照：他 repo 的 .claude/（POSIX 與磁碟機路徑）仍判外部，經 where.files
   fallback 進入 main() 後被阻擋（exit 2）
4. 既有分類不變：本 repo 絕對路徑、相對 .claude/ 判主 repo，其他路徑判 other

磁碟機路徑在 POSIX 上不存在，同層 checkout 判定（_is_same_repo_sibling_checkout）
解析不出所屬 checkout，回 False，不影響本檔斷言。
"""

import importlib.util
import io
import json
import sys
from pathlib import Path

import pytest

_HOOKS_DIR = Path(__file__).parent.parent
_TICKET_HOOKS_DIR = _HOOKS_DIR.parent / "skills" / "ticket" / "hooks"
sys.path.insert(0, str(_TICKET_HOOKS_DIR))
_spec = importlib.util.spec_from_file_location(
    "agent_dispatch_validation_hook_boundary",
    _TICKET_HOOKS_DIR / "agent-dispatch-validation-hook.py",
)
_hook = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_hook)

MAIN, EXT, OTHER = (True, False, False), (False, True, False), (False, False, True)


@pytest.mark.parametrize("path,root,expected", [
    # 1. 目錄邊界：同字首他 repo 判外部
    ("/a/proj2/.claude/hooks/x.py", "/a/proj", EXT),
    ("C:/u/proj2/.claude/hooks/x.py", "C:/u/proj", EXT),
    # 2. 本 repo 的磁碟機路徑判主 repo
    ("C:/u/proj/.claude/hooks/x.py", "C:/u/proj", MAIN),
    ("C:\\u\\proj\\.claude\\hooks\\x.py", "C:/u/proj", MAIN),
    ("c:/u/proj/.claude/hooks/x.py", "C:/u/proj", MAIN),
    ("C:/u/proj/.claude/hooks/x.py", "C:\\u\\proj", MAIN),
    # 3. E2：他 repo 的 .claude/ 仍判外部
    ("/b/other/.claude/hooks/x.py", "/a/proj", EXT),
    ("D:/other/.claude/hooks/x.py", "C:/u/proj", EXT),
    # 4. 既有分類不變
    ("/a/proj/.claude/hooks/x.py", "/a/proj", MAIN),
    (".claude/hooks/x.py", "/a/proj", MAIN),
    ("src/a.py", "/a/proj", OTHER),
])
def test_classify_paths(path, root, expected):
    assert _hook._classify_paths([path], root) == expected


def test_classify_paths_empty_root_stays_external():
    # 專案根解析失敗（空字串）：絕對路徑 .claude/ 落在外部（阻擋側），與修正前相同
    assert _hook._classify_paths(["/a/proj/.claude/x.py"], "") == EXT


@pytest.mark.parametrize("where_file", [
    "/a/proj2/.claude/hooks/x.py",
    "/b/other/.claude/hooks/x.py",
])
def test_external_where_files_blocks_dispatch(monkeypatch, where_file):
    # E2：prompt 只寫票號，路徑分類走 where.files fallback；外部 .claude/ → exit 2
    monkeypatch.setattr(_hook, "get_project_root", lambda: Path("/a/proj"))
    monkeypatch.setattr(_hook, "_load_ticket_where_files", lambda tid: [where_file])
    payload = {
        "tool_name": "Agent",
        "tool_input": {
            "subagent_type": "thyme-python-developer",
            "prompt": "執行 3.3.0-W1-999",
        },
    }
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
    assert _hook.main() == 2
