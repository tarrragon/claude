"""
Agent Dispatch Validation Hook - target-based 路徑分類測試（ARCH-015 2026-04-18 修正版）

對應 Ticket 0.18.0-W5-047.5 AC：
- _classify_prompt_paths 回傳三元 (has_main_repo_claude, has_external_claude, has_other)
- 決策邏輯優先順序：
  (1) has_external_claude=True → 阻擋（外部 .claude/ runtime 必拒）
  (2) has_other=True 且 isolation != worktree → 阻擋（強制 worktree 防 .git/HEAD 污染）
  (3) 其他 → 放行

取代 W10-042 舊設計（.claude/ 跨路徑一律阻擋）。
新的 W5-050 實證：主 repo .claude/ + 非 .claude/ + worktree 可合法派發。
"""

import json
import sys
import importlib.util
import io
from pathlib import Path

import pytest


# 動態載入 hook module（檔名含連字號，無法直接 import）
_HOOKS_DIR = Path(__file__).parent.parent
if str(_HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOKS_DIR))

_spec = importlib.util.spec_from_file_location(
    "agent_dispatch_validation_hook",
    _HOOKS_DIR / "agent-dispatch-validation-hook.py",
)
_hook = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_hook)

_classify_prompt_paths = _hook._classify_prompt_paths
main = _hook.main


# 專案根目錄（測試 fixtures 用來構造「主 repo 內絕對路徑」）
_PROJECT_ROOT = _HOOKS_DIR.parent.parent  # .claude/hooks -> .claude -> root


# ----------------------------------------------------------------------------
# 單元測試：_classify_prompt_paths 三元分類邏輯
# ----------------------------------------------------------------------------

def test_classify_empty_prompt_returns_no_paths():
    """空 prompt 應回傳 (False, False, False)。"""
    assert _classify_prompt_paths("") == (False, False, False)


def test_classify_only_relative_claude_path_counts_as_main_repo():
    """相對路徑 .claude/ 預設視為主 repo 內（符合 PM 派發主流慣例）。"""
    prompt = "修改 .claude/hooks/agent-dispatch-validation-hook.py 加入路徑檢測"
    main_repo, external, other = _classify_prompt_paths(prompt)
    assert main_repo is True
    assert external is False
    assert other is False


def test_classify_absolute_path_in_main_repo_is_main_claude():
    """絕對路徑 .claude/ 落在主 repo 樹內 → has_main_repo_claude。"""
    prompt = f"修改 {_PROJECT_ROOT}/.claude/hooks/foo.py"
    main_repo, external, other = _classify_prompt_paths(prompt)
    assert main_repo is True
    assert external is False


def test_classify_absolute_path_external_is_external_claude():
    """絕對路徑 .claude/ 不在主 repo 樹內 → has_external_claude。"""
    prompt = "修改 /tmp/other-repo/.claude/hooks/foo.py"
    main_repo, external, other = _classify_prompt_paths(prompt)
    assert external is True
    assert main_repo is False


def test_classify_tmp_worktree_claude_is_external():
    """/tmp/ 下的 worktree 內 .claude/ → has_external_claude。"""
    prompt = "在 /tmp/worktree-xyz/.claude/hooks/bar.py 加入邏輯"
    main_repo, external, other = _classify_prompt_paths(prompt)
    assert external is True
    assert main_repo is False


def test_classify_only_non_claude_path_src():
    """僅提及 src/ 的 prompt 應分類為 other=True。"""
    prompt = "在 src/components/BookCard.js 實作新 Widget"
    main_repo, external, other = _classify_prompt_paths(prompt)
    assert main_repo is False
    assert external is False
    assert other is True


@pytest.mark.parametrize(
    "path_sample",
    # docs/ 不在偵測清單內（read-only context，見 hook 註解）
    ["src/main.dart", "tests/unit/foo_test.dart", "test/foo_test.go",
     "lib/services/x.dart", "app/main.py",
     "assets/icons/", "scripts/build.sh", "public/index.html",
     "bin/cli.go", "cmd/server/main.go"],
)
def test_classify_common_project_paths_detected_as_other(path_sample):
    """常見專案路徑開頭應被偵測為 other=True。"""
    prompt = f"Edit {path_sample} 實作功能"
    main_repo, external, other = _classify_prompt_paths(prompt)
    assert main_repo is False
    assert external is False
    assert other is True


def test_classify_cross_paths_main_repo_claude_and_other():
    """同時提及相對 .claude/ 與 src/ → (True, False, True)。"""
    prompt = (
        "修改 .claude/hooks/foo.py 並更新 src/widgets/bar.dart 對應邏輯"
    )
    main_repo, external, other = _classify_prompt_paths(prompt)
    assert main_repo is True
    assert external is False
    assert other is True


def test_classify_nested_claude_docs_not_counted_as_other():
    """.claude/references/docs-guide.md 不應被誤判為 docs/ 路徑。"""
    prompt = "更新 .claude/references/docs-guide.md 和 .claude/docs/README.md"
    main_repo, external, other = _classify_prompt_paths(prompt)
    assert main_repo is True
    assert other is False, "巢狀於 .claude/ 下的 docs/ 不應觸發 other 分類"


def test_classify_no_paths_at_all():
    """完全無路徑的 prompt 應回傳 (False, False, False)。"""
    prompt = "請分析系統架構並提供改進建議"
    assert _classify_prompt_paths(prompt) == (False, False, False)


# ----------------------------------------------------------------------------
# 整合測試：main() Hook 入口點
# ----------------------------------------------------------------------------

def _run_hook(monkeypatch, capsys, tool_input: dict) -> int:
    """以 monkeypatch 模擬 stdin 輸入並執行 main()。

    回傳：exit code（0=放行, 2=阻擋）
    """
    payload = {"tool_name": "Agent", "tool_input": tool_input}
    stdin_buffer = io.StringIO(json.dumps(payload))
    monkeypatch.setattr(sys, "stdin", stdin_buffer)
    return main()


def test_hook_allows_non_implementation_agent(monkeypatch, capsys):
    """非實作代理人（如 Explore）一律放行，不受 worktree 強制約束。"""
    exit_code = _run_hook(
        monkeypatch,
        capsys,
        tool_input={"subagent_type": "Explore", "prompt": "search for pattern"},
    )
    assert exit_code == 0


def test_hook_allows_worktree_isolation(monkeypatch, capsys):
    """實作代理人使用 worktree isolation 時放行。"""
    exit_code = _run_hook(
        monkeypatch,
        capsys,
        tool_input={
            "subagent_type": "thyme-python-developer",
            "isolation": "worktree",
            "prompt": "edit src/foo.py",
        },
    )
    assert exit_code == 0


def test_hook_allows_claude_only_prompt_without_worktree(monkeypatch, capsys):
    """主 repo .claude/ 僅有 prompt，無 worktree 時放行（ARCH-015 豁免）。"""
    exit_code = _run_hook(
        monkeypatch,
        capsys,
        tool_input={
            "subagent_type": "thyme-python-developer",
            "prompt": "修改 .claude/hooks/foo.py 加入新檢查邏輯",
        },
    )
    assert exit_code == 0, "僅主 repo .claude/ 的 prompt 應放行"


def test_hook_blocks_non_claude_prompt_without_worktree(monkeypatch, capsys):
    """僅非 .claude/ 路徑且無 worktree 時，原強制邏輯阻擋。"""
    exit_code = _run_hook(
        monkeypatch,
        capsys,
        tool_input={
            "subagent_type": "parsley-flutter-developer",
            "prompt": "實作 src/widgets/book_card.dart 並寫 tests/unit/book_card_test.dart",
        },
    )
    assert exit_code == 2
    err = capsys.readouterr().err
    assert "必須使用 isolation" in err, "應使用原 BLOCK_MESSAGE_TEMPLATE"


def test_hook_allows_cross_path_with_worktree_when_claude_in_main_repo(monkeypatch, capsys):
    """W5-050 新發現：主 repo .claude/ + 非 .claude/ + worktree 合法派發。

    取代舊 W10-042 的 CROSS_PATH_BLOCK。worktree subagent 可 Edit 主 repo 內 .claude/。
    """
    exit_code = _run_hook(
        monkeypatch,
        capsys,
        tool_input={
            "subagent_type": "thyme-python-developer",
            "isolation": "worktree",
            "prompt": "同時修改 .claude/hooks/foo.py 和 src/api/bar.py",
        },
    )
    assert exit_code == 0, "W5-050：主 repo .claude/ + src/ + worktree 應放行"


def test_hook_blocks_cross_path_without_worktree(monkeypatch, capsys):
    """主 repo .claude/ + 非 .claude/ 但無 worktree → 阻擋（強制 worktree）。"""
    exit_code = _run_hook(
        monkeypatch,
        capsys,
        tool_input={
            "subagent_type": "thyme-python-developer",
            "prompt": "同時修改 .claude/hooks/foo.py 和 src/api/bar.py",
        },
    )
    assert exit_code == 2
    err = capsys.readouterr().err
    assert "必須使用 isolation" in err


def test_hook_blocks_external_claude_path_absolute(monkeypatch, capsys):
    """絕對路徑指向外部 .claude/（/tmp/ 等）→ 阻擋（runtime 必拒）。"""
    exit_code = _run_hook(
        monkeypatch,
        capsys,
        tool_input={
            "subagent_type": "thyme-python-developer",
            "prompt": "修改 /tmp/other-repo/.claude/hooks/foo.py",
        },
    )
    assert exit_code == 2
    err = capsys.readouterr().err
    assert "外部 .claude/" in err or "external" in err.lower() or "ARCH-015" in err


def test_hook_blocks_external_claude_even_with_worktree(monkeypatch, capsys):
    """外部 .claude/ 即使宣告 worktree 也阻擋（runtime 仍會拒絕）。"""
    exit_code = _run_hook(
        monkeypatch,
        capsys,
        tool_input={
            "subagent_type": "thyme-python-developer",
            "isolation": "worktree",
            "prompt": "修改 /tmp/other-repo/.claude/hooks/foo.py",
        },
    )
    assert exit_code == 2
    err = capsys.readouterr().err
    assert "外部 .claude/" in err or "ARCH-015" in err


def test_hook_blocks_empty_prompt_without_worktree(monkeypatch, capsys):
    """空 prompt 且無 worktree：回退到原強制邏輯（無路徑資訊不應誤豁免）。"""
    exit_code = _run_hook(
        monkeypatch,
        capsys,
        tool_input={
            "subagent_type": "thyme-python-developer",
            "prompt": "",
        },
    )
    assert exit_code == 2
    err = capsys.readouterr().err
    assert "必須使用 isolation" in err


def test_hook_allows_no_subagent_type(monkeypatch, capsys):
    """缺少 subagent_type 時放行。"""
    exit_code = _run_hook(
        monkeypatch,
        capsys,
        tool_input={"prompt": "some prompt without agent"},
    )
    assert exit_code == 0


def test_hook_ignores_non_agent_tool(monkeypatch, capsys):
    """Hook 只對 Agent 工具生效。"""
    payload = {"tool_name": "Bash", "tool_input": {"command": "ls"}}
    stdin_buffer = io.StringIO(json.dumps(payload))
    monkeypatch.setattr(sys, "stdin", stdin_buffer)
    assert main() == 0


# ============================================================================
# W5-047.2: 並行場景廣域 staging 偵測（PC-092 防護）
# ============================================================================

_has_wide_staging = _hook._has_wide_staging
_count_active_dispatches = _hook._count_active_dispatches


class TestHasWideStaging:
    """_has_wide_staging 正則偵測。"""

    @pytest.mark.parametrize("cmd", [
        "git add .",
        "git add -A",
        "git add --all",
        "請先執行 git add . 再 commit",
        "run: git  add  -A  # with extra spaces",
    ])
    def test_detects_wide_staging_patterns(self, cmd):
        assert _has_wide_staging(cmd) is True

    @pytest.mark.parametrize("cmd", [
        "",
        "git add src/foo.py",
        "git add src/ tests/",
        "git add -- path",
        "git commit -m 'msg'",
        "run: git status",
        "addendum: note about .claude/ hooks",
    ])
    def test_does_not_match_safe_patterns(self, cmd):
        assert _has_wide_staging(cmd) is False


def _write_dispatch_active(tmp_path, count: int) -> Path:
    """建立假的 .claude/dispatch-active.json（含 count 個 dispatches 條目）。"""
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir(parents=True, exist_ok=True)
    state = {
        "dispatches": [
            {
                "agent_description": f"fake agent {i}",
                "tool_use_id": f"toolu_fake_{i}",
                "agent_id": None,
                "ticket_id": "",
                "files": [],
                "branch_name": "",
                "dispatched_at": "2026-04-18T00:00:00+00:00",
            }
            for i in range(count)
        ]
    }
    state_file = claude_dir / "dispatch-active.json"
    state_file.write_text(json.dumps(state), encoding="utf-8")
    return state_file


class TestParallelWideStagingWarning:
    """整合：main() 在並行場景偵測廣域 staging 時印警告。"""

    def test_parallel_with_wide_staging_emits_warning(
        self, monkeypatch, capsys, tmp_path
    ):
        """並行場景（>=2 dispatches）+ prompt 含 git add . → stderr 印警告。"""
        _write_dispatch_active(tmp_path, count=2)
        monkeypatch.setattr(_hook, "get_project_root", lambda: tmp_path)

        exit_code = _run_hook(
            monkeypatch,
            capsys,
            tool_input={
                "subagent_type": "thyme-python-developer",
                "isolation": "worktree",
                "prompt": "完成後執行 git add . && git commit -m msg，修改 src/foo.py",
            },
        )
        err = capsys.readouterr().err
        assert "PC-092" in err, "警告訊息必須引用 PC-092"
        assert "git add" in err, "警告訊息需提示 wide staging"
        assert exit_code == 0, "警告非阻擋，不改變 return code"

    def test_parallel_with_wide_staging_dash_A_emits_warning(
        self, monkeypatch, capsys, tmp_path
    ):
        """並行 + git add -A → 警告。"""
        _write_dispatch_active(tmp_path, count=3)
        monkeypatch.setattr(_hook, "get_project_root", lambda: tmp_path)

        exit_code = _run_hook(
            monkeypatch,
            capsys,
            tool_input={
                "subagent_type": "parsley-flutter-developer",
                "isolation": "worktree",
                "prompt": "git add -A 然後 commit 修改 lib/foo.dart",
            },
        )
        err = capsys.readouterr().err
        assert "PC-092" in err
        assert exit_code == 0

    def test_parallel_with_precise_staging_no_warning(
        self, monkeypatch, capsys, tmp_path
    ):
        """並行場景但 prompt 是精準 staging（git add src/foo.py）→ 不警告。"""
        _write_dispatch_active(tmp_path, count=2)
        monkeypatch.setattr(_hook, "get_project_root", lambda: tmp_path)

        exit_code = _run_hook(
            monkeypatch,
            capsys,
            tool_input={
                "subagent_type": "thyme-python-developer",
                "isolation": "worktree",
                "prompt": "git add src/foo.py src/bar.py && commit",
            },
        )
        err = capsys.readouterr().err
        assert "PC-092" not in err, "精準 staging 不應觸發警告"
        assert exit_code == 0

    def test_single_dispatch_with_wide_staging_no_warning(
        self, monkeypatch, capsys, tmp_path
    ):
        """單一派發場景（<2 dispatches）+ git add . → 不警告（合法單人用例）。"""
        _write_dispatch_active(tmp_path, count=1)
        monkeypatch.setattr(_hook, "get_project_root", lambda: tmp_path)

        exit_code = _run_hook(
            monkeypatch,
            capsys,
            tool_input={
                "subagent_type": "thyme-python-developer",
                "isolation": "worktree",
                "prompt": "git add . 然後 commit 修改 src/foo.py",
            },
        )
        err = capsys.readouterr().err
        assert "PC-092" not in err, "單一派發場景不應觸發警告"
        assert exit_code == 0

    def test_no_dispatch_file_no_warning(
        self, monkeypatch, capsys, tmp_path
    ):
        """dispatch-active.json 不存在 → 不警告（視為單一場景）。"""
        monkeypatch.setattr(_hook, "get_project_root", lambda: tmp_path)

        exit_code = _run_hook(
            monkeypatch,
            capsys,
            tool_input={
                "subagent_type": "thyme-python-developer",
                "isolation": "worktree",
                "prompt": "git add -A",
            },
        )
        err = capsys.readouterr().err
        assert "PC-092" not in err
        assert exit_code == 0

    def test_count_active_dispatches_handles_missing_file(self, tmp_path, monkeypatch):
        """_count_active_dispatches：檔案不存在回傳 0。"""
        monkeypatch.setattr(_hook, "get_project_root", lambda: tmp_path)
        assert _count_active_dispatches() == 0

    def test_count_active_dispatches_reads_entries(self, tmp_path, monkeypatch):
        """_count_active_dispatches：正確計數 dispatches 條目。"""
        _write_dispatch_active(tmp_path, count=3)
        monkeypatch.setattr(_hook, "get_project_root", lambda: tmp_path)
        assert _count_active_dispatches() == 3

    def test_count_active_dispatches_handles_corrupt_json(self, tmp_path, monkeypatch):
        """_count_active_dispatches：損壞 JSON 回傳 0。"""
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        (claude_dir / "dispatch-active.json").write_text("not json", encoding="utf-8")
        monkeypatch.setattr(_hook, "get_project_root", lambda: tmp_path)
        assert _count_active_dispatches() == 0


# ============================================================================
# W5-045: Agent 禁止行為關鍵字衝突掃描
# ============================================================================

_extract_prohibited_actions = _hook._extract_prohibited_actions
_detect_keyword_conflicts = _hook._detect_keyword_conflicts


def _write_agent_md(tmp_path: Path, subagent_type: str, body: str) -> Path:
    """在 tmp_path/.claude/agents/ 建立假 agent .md 檔。"""
    agents_dir = tmp_path / ".claude" / "agents"
    agents_dir.mkdir(parents=True, exist_ok=True)
    md_path = agents_dir / f"{subagent_type}.md"
    md_path.write_text(body, encoding="utf-8")
    return md_path


_SAGE_LIKE_MD = """---
name: sage-test-architect
---

# sage-test-architect

設計和規劃測試策略。

## 適用情境

Phase 2 測試設計。

## 禁止行為

### 絕對禁止

1. **禁止實作程式碼**：
   - 不得撰寫任何可執行的程式碼
   - 由 pepper 等實作代理人負責

2. **禁止設計功能規格**：
   - 不得設計功能規格

3. **禁止直接執行測試修復**：
   - 不得修復失敗測試

## 工作流程

略。
"""


class TestExtractProhibitedActions:
    """_extract_prohibited_actions 解析 `## 禁止行為` 區塊。"""

    def test_extracts_labels_from_hierarchical_section(self, tmp_path):
        """階層式結構（sage-like）應抽出三條 prohibited action 標籤。"""
        md = _write_agent_md(tmp_path, "sage-test-architect", _SAGE_LIKE_MD)
        actions = _extract_prohibited_actions(md)
        assert "實作程式碼" in actions
        assert "設計功能規格" in actions
        assert "直接執行測試修復" in actions

    def test_extracts_from_flat_section(self, tmp_path):
        """扁平式結構（無 ### 子標）也應正確抽出。"""
        body = """## 禁止行為

1. **禁止 git commit**：不得自行提交
2. **禁止修改檔案**：只讀取

## 其他章節
"""
        md = _write_agent_md(tmp_path, "flat-agent", body)
        actions = _extract_prohibited_actions(md)
        assert "git commit" in [a.strip() for a in actions]
        assert "修改檔案" in actions

    def test_returns_empty_when_no_section(self, tmp_path):
        """無『## 禁止行為』區塊時回傳空 list。"""
        md = _write_agent_md(tmp_path, "no-forbid", "# Some agent\n\n只有簡介。\n")
        assert _extract_prohibited_actions(md) == []

    def test_returns_empty_when_file_missing(self, tmp_path):
        """檔案不存在時回傳空 list（不丟例外）。"""
        assert _extract_prohibited_actions(tmp_path / "nonexistent.md") == []

    def test_section_terminates_at_next_level2_heading(self, tmp_path):
        """下一個 `## ` 應終止區塊，後續 `**禁止X**` 不應被誤抽。"""
        body = """## 禁止行為

1. **禁止實作**：略

## 適用情境

注意事項：**禁止忽略此規則** 屬於其他區塊不應被抽取。
"""
        md = _write_agent_md(tmp_path, "bounded", body)
        actions = _extract_prohibited_actions(md)
        assert "實作" in actions
        assert "忽略此規則" not in actions, "下一章節的粗體不應被抽取"


class TestDetectKeywordConflicts:
    """_detect_keyword_conflicts 匹配 prompt 關鍵字與 prohibited actions。"""

    def test_detects_implementation_keyword_in_prompt(self):
        prompt = "請實作新功能並寫入 src/foo.py"
        conflicts = _detect_keyword_conflicts(prompt, ["實作程式碼"])
        assert len(conflicts) >= 1
        assert any(c["action"] == "實作程式碼" and c["keyword"] == "實作" for c in conflicts)

    def test_detects_git_commit_keyword(self):
        prompt = "完成後請執行 git commit -m 'msg'"
        conflicts = _detect_keyword_conflicts(prompt, ["git commit"])
        assert len(conflicts) >= 1
        assert any(c["keyword"] == "git commit" for c in conflicts)

    def test_detects_spec_design_keyword(self):
        prompt = "請設計此 UC 的規格文件"
        conflicts = _detect_keyword_conflicts(prompt, ["設計功能規格"])
        assert len(conflicts) >= 1
        assert any(c["keyword"] == "設計功能規格" for c in conflicts)

    def test_no_conflict_for_clean_prompt(self):
        """prompt 與所有禁止項皆無關時應無衝突。"""
        prompt = "請閱讀 docs/foo.md 並撰寫分析報告"
        conflicts = _detect_keyword_conflicts(
            prompt, ["實作程式碼", "git commit", "設計功能規格"]
        )
        assert conflicts == []

    def test_no_conflict_for_empty_prompt(self):
        assert _detect_keyword_conflicts("", ["實作程式碼"]) == []

    def test_no_conflict_for_empty_prohibited_list(self):
        assert _detect_keyword_conflicts("實作某功能", []) == []

    def test_prohibited_action_without_mapped_keyword_yields_no_conflict(self):
        """prohibited action 標籤無法映射到 FORBIDDEN_KEYWORD_MAP → 不觸發衝突。"""
        prompt = "請執行某操作"
        conflicts = _detect_keyword_conflicts(prompt, ["超出測試設計範圍的工作"])
        assert conflicts == []


class TestKeywordConflictIntegration:
    """整合：main() 掃描 sage 類 agent 的派發 prompt。"""

    def test_sage_like_agent_with_implement_prompt_emits_warning(
        self, monkeypatch, capsys, tmp_path
    ):
        """AC-T1：sage agent + prompt 含『實作』 → stderr 印警告。"""
        _write_agent_md(tmp_path, "sage-test-architect", _SAGE_LIKE_MD)
        monkeypatch.setattr(_hook, "get_project_root", lambda: tmp_path)

        exit_code = _run_hook(
            monkeypatch,
            capsys,
            tool_input={
                "subagent_type": "sage-test-architect",
                "prompt": "請實作新測試並寫入 tests/unit/foo_test.py",
            },
        )
        err = capsys.readouterr().err
        assert "W5-045" in err or "禁止行為" in err, (
            "sage + 『實作』應觸發 W5-045 警告"
        )
        assert "實作" in err
        # sage 非 IMPLEMENTATION_AGENTS，掃描後放行
        assert exit_code == 0

    def test_implementation_agent_with_git_commit_prompt_emits_warning(
        self, monkeypatch, capsys, tmp_path
    ):
        """AC-T2（W11-004.1.4 升級）：實作代理人 + prompt 含 git commit
        （若該 agent 禁止）→ 高信心 BLOCK（exit 2）。"""
        body = """## 禁止行為

1. **禁止 git commit**：不得自行 commit
"""
        _write_agent_md(tmp_path, "thyme-python-developer", body)
        monkeypatch.setattr(_hook, "get_project_root", lambda: tmp_path)
        monkeypatch.delenv(_hook._BYPASS_ENV_VAR, raising=False)

        exit_code = _run_hook(
            monkeypatch,
            capsys,
            tool_input={
                "subagent_type": "thyme-python-developer",
                "isolation": "worktree",
                "prompt": "修改 src/foo.py 後 git commit -m msg",
            },
        )
        err = capsys.readouterr().err
        assert "git commit" in err
        assert "高信心" in err or "W11-004.1.4" in err or "已阻擋" in err
        assert exit_code == 2, "git commit 屬高信心越界，應被 block"

    def test_clean_prompt_no_warning(self, monkeypatch, capsys, tmp_path):
        """AC-T3：prompt 與 agent 禁止行為無衝突 → 不警告。"""
        _write_agent_md(tmp_path, "sage-test-architect", _SAGE_LIKE_MD)
        monkeypatch.setattr(_hook, "get_project_root", lambda: tmp_path)

        exit_code = _run_hook(
            monkeypatch,
            capsys,
            tool_input={
                "subagent_type": "sage-test-architect",
                "prompt": "請分析現有測試架構並提供重構建議，不要修改程式碼",
            },
        )
        err = capsys.readouterr().err
        # 不應含 W5-045 警告標記（"設計" 可能誤觸？檢查 "設計功能規格" 的 pattern
        # 是 "設計.*規格"，此 prompt 無 "規格" → 不命中）
        assert "W5-045" not in err
        assert "禁止行為" not in err or "衝突" not in err
        assert exit_code == 0

    def test_missing_agent_md_no_warning(self, monkeypatch, capsys, tmp_path):
        """agent .md 檔不存在時靜默放行（不丟例外）。"""
        monkeypatch.setattr(_hook, "get_project_root", lambda: tmp_path)

        exit_code = _run_hook(
            monkeypatch,
            capsys,
            tool_input={
                "subagent_type": "unknown-agent",
                "prompt": "請實作某功能",
            },
        )
        err = capsys.readouterr().err
        assert "W5-045" not in err
        assert exit_code == 0

    def test_agent_without_prohibited_section_no_warning(
        self, monkeypatch, capsys, tmp_path
    ):
        """agent 檔存在但無『## 禁止行為』區塊 → 不警告。"""
        _write_agent_md(
            tmp_path, "bare-agent", "# bare\n\n只有簡介\n"
        )
        monkeypatch.setattr(_hook, "get_project_root", lambda: tmp_path)

        exit_code = _run_hook(
            monkeypatch,
            capsys,
            tool_input={
                "subagent_type": "bare-agent",
                "prompt": "請實作某功能",
            },
        )
        err = capsys.readouterr().err
        assert "W5-045" not in err
        assert exit_code == 0


# ============================================================================
# W11-004.1.2: 擴充 keyword map 六類新 pattern（A-F）
# ============================================================================

_FORBIDDEN_KEYWORD_MAP = _hook.FORBIDDEN_KEYWORD_MAP


class TestExpandedKeywordMap:
    """W11-004.1.2：A-F 六類新 pattern 的 match / non-match 驗證。"""

    def _match_any(self, keyword: str, prompt: str) -> bool:
        patterns = _FORBIDDEN_KEYWORD_MAP[keyword]
        return any(p.search(prompt) for p in patterns)

    # 類別 A：Ticket CLI
    @pytest.mark.parametrize("prompt", [
        "請執行 ticket track append-log 0.18-W1",
        "請跑 /ticket create IMP",
        "ticket claim 0.18-W1-001",
    ])
    def test_ticket_cli_matches(self, prompt):
        assert self._match_any("ticket CLI", prompt) is True

    @pytest.mark.parametrize("prompt", [
        "請閱讀 ticket 文件並整理摘要",
        "分析 docs/ 下的文件",
    ])
    def test_ticket_cli_non_matches(self, prompt):
        assert self._match_any("ticket CLI", prompt) is False

    # 類別 B：修改規格
    @pytest.mark.parametrize("prompt", [
        "請修改 docs/use-cases.md 的規格",
        "Edit spec 文件加入新需求",
        "更新規格以對齊新版",
    ])
    def test_modify_spec_matches(self, prompt):
        assert self._match_any("修改規格", prompt) is True

    @pytest.mark.parametrize("prompt", [
        "請閱讀規格文件",
        "分析現有需求並產出報告",
    ])
    def test_modify_spec_non_matches(self, prompt):
        assert self._match_any("修改規格", prompt) is False

    # 類別 C：git 寫入
    @pytest.mark.parametrize("prompt", [
        "完成後請 git push origin main",
        "請 git merge feature-branch",
        "執行 git rebase main",
        "執行 git reset --hard HEAD~1",
        "請推送分支至 PR",
    ])
    def test_git_write_matches(self, prompt):
        assert self._match_any("git 寫入", prompt) is True

    @pytest.mark.parametrize("prompt", [
        "git status 查看狀態",
        "git log --oneline",
        "git diff HEAD",
    ])
    def test_git_write_non_matches(self, prompt):
        assert self._match_any("git 寫入", prompt) is False

    # 類別 D：執行重構
    @pytest.mark.parametrize("prompt", [
        "請執行重構移除過時函式",
        "進行重構讓函式更短",
        "請移除 src/foo.py",
        "刪除 lib/bar.dart 中的過時邏輯",
        "Please refactor the parser",
    ])
    def test_refactor_matches(self, prompt):
        assert self._match_any("執行重構", prompt) is True

    @pytest.mark.parametrize("prompt", [
        "請分析後提出建議但不要動程式",
        "規劃策略",
    ])
    def test_refactor_non_matches(self, prompt):
        assert self._match_any("執行重構", prompt) is False

    # 類別 E：系統審查
    @pytest.mark.parametrize("prompt", [
        "請做系統審查",
        "進行系統級審查",
        "盤點全專案架構",
        "審計系統的相依關係",
    ])
    def test_system_review_matches(self, prompt):
        assert self._match_any("系統審查", prompt) is True

    @pytest.mark.parametrize("prompt", [
        "請檢視單一檔案",
        "盤點本 ticket 的改動",
    ])
    def test_system_review_non_matches(self, prompt):
        assert self._match_any("系統審查", prompt) is False

    # 類別 F：分支操作
    @pytest.mark.parametrize("prompt", [
        "git checkout feature-x",
        "git branch -d old",
        "git switch main",
        "執行 worktree add /tmp/wt",
        "worktree remove wt-1",
    ])
    def test_branch_ops_matches(self, prompt):
        assert self._match_any("分支操作", prompt) is True

    @pytest.mark.parametrize("prompt", [
        "git status",
        "查看分支列表（僅讀取）",
    ])
    def test_branch_ops_non_matches(self, prompt):
        assert self._match_any("分支操作", prompt) is False

    def test_new_categories_have_at_least_10_regex(self):
        new_keys = ["ticket CLI", "修改規格", "git 寫入", "執行重構", "系統審查", "分支操作"]
        total = sum(len(_FORBIDDEN_KEYWORD_MAP[k]) for k in new_keys)
        assert total >= 10, f"新增 regex 應 >= 10，實際 {total}"

    def test_existing_categories_preserved(self):
        for k in ["實作", "修改檔案", "git commit", "設計功能規格", "直接執行測試修復", "執行測試"]:
            assert k in _FORBIDDEN_KEYWORD_MAP
            assert len(_FORBIDDEN_KEYWORD_MAP[k]) >= 1


# ============================================================================
# W11-004.1.3: 白名單過濾 - 合法引用情境排除誤觸
# ============================================================================
#
# 對應 ticket 0.18.0-W11-004.1.3：識別合法情境並排除誤觸。
# 設計：四條白名單規則（純函式 + WHITELIST_RULES 清單），在 _detect_keyword_conflicts
# 回傳前過濾。
#
# 待實作符號（thyme Phase 3b GREEN）：
#   _is_quoted_match(prompt, start, end) -> Tuple[bool, str]
#   _has_negation_prefix(prompt, start) -> Tuple[bool, str]
#   _is_in_path_context(prompt, start, end) -> Tuple[bool, str]
#   _is_meta_task_prompt(prompt) -> Tuple[bool, str]
#   WHITELIST_RULES: List[Callable]
#
# 整合行為：_detect_keyword_conflicts 內部套用白名單過濾，被白名單化的匹配不進結果。


class TestWhitelistRuleA_QuotedReference:
    """規則 A：引號包圍偵測 _is_quoted_match。"""

    @pytest.fixture
    def fn(self):
        return getattr(_hook, "_is_quoted_match")

    @pytest.mark.parametrize("prompt,start_substr", [
        ("請遵守 thyme 定義中的『禁止實作程式碼』邊界", "實作"),
        ("sage 的「禁止 git commit」章節", "git commit"),
        ("參照 standard.md 的 **禁止執行測試** 格式", "執行測試"),
        ('agent 的 "禁止修改規格" 範例說明', "修改規格"),
        ("詳見 `禁止 git push` 條款", "git push"),
    ])
    def test_whitelisted_when_wrapped_in_quotes(self, fn, prompt, start_substr):
        """匹配位置落在引號內 → 白名單化（回傳 (True, reason)）。"""
        start = prompt.index(start_substr)
        end = start + len(start_substr)
        is_wl, reason = fn(prompt, start, end)
        assert is_wl is True
        assert reason, "白名單命中時必須回傳非空 reason"

    @pytest.mark.parametrize("prompt,start_substr", [
        ("請實作 src/foo.py 的新功能", "實作"),
        ("完成後 git commit -m 'fix'", "git commit"),
        ("請修改規格文件加入新需求", "修改規格"),
    ])
    def test_not_whitelisted_when_no_quotes(self, fn, prompt, start_substr):
        """匹配位置不在引號內 → 不白名單化。"""
        start = prompt.index(start_substr)
        end = start + len(start_substr)
        is_wl, _ = fn(prompt, start, end)
        assert is_wl is False

    def test_unclosed_quote_does_not_infinite_loop(self, fn):
        """未閉合引號不應造成回圈，視為未在引號內。"""
        prompt = "請『實作新功能 src/foo.py"  # 開引號無閉合
        start = prompt.index("實作")
        end = start + len("實作")
        is_wl, _ = fn(prompt, start, end)
        # 接受 True/False，核心是「不 hang」；若實作選擇嚴格閉合 → False
        assert isinstance(is_wl, bool)

    def test_cross_line_quote_not_counted(self, fn):
        """引號跨行不視為包圍（避免過寬匹配）。"""
        prompt = "標題：『警告\n內容：實作' 範例"
        start = prompt.index("實作")
        end = start + len("實作")
        is_wl, _ = fn(prompt, start, end)
        assert is_wl is False


class TestWhitelistRuleB_NegationPrefix:
    """規則 B：否定前綴偵測 _has_negation_prefix。"""

    @pytest.fixture
    def fn(self):
        return getattr(_hook, "_has_negation_prefix")

    @pytest.mark.parametrize("prompt,start_substr", [
        ("請勿實作程式碼，僅產出設計", "實作"),
        ("不要執行 git commit", "git commit"),
        ("禁止修改 src/ 下檔案", "修改"),
        ("不得進行重構", "重構"),
        ("do not commit changes", "commit"),
        ("avoid refactor in this task", "refactor"),
    ])
    def test_whitelisted_when_negation_within_10_chars(self, fn, prompt, start_substr):
        """匹配位置前 10 字元內含否定詞 → 白名單化。"""
        start = prompt.index(start_substr)
        is_wl, reason = fn(prompt, start)
        assert is_wl is True
        assert reason

    @pytest.mark.parametrize("prompt,start_substr", [
        ("請實作新功能", "實作"),
        ("完成後 git commit", "git commit"),
        ("請修改 src/foo.py", "修改"),
    ])
    def test_not_whitelisted_without_negation(self, fn, prompt, start_substr):
        start = prompt.index(start_substr)
        is_wl, _ = fn(prompt, start)
        assert is_wl is False

    def test_negation_too_far_not_counted(self, fn):
        """否定詞與匹配跨越逗號邊界視為無效前綴（W11-004.1.3.3 調校後）。"""
        prompt = "請不要忘記這件事，然後開始實作新功能"
        start = prompt.index("實作")
        is_wl, _ = fn(prompt, start)
        assert is_wl is False

    def test_sentence_boundary_blocks_negation(self, fn):
        """否定詞與匹配跨越句號/分號 → 不算前綴。"""
        prompt = "不要忘記。請實作新功能"
        start = prompt.index("實作")
        is_wl, _ = fn(prompt, start)
        assert is_wl is False


class TestWhitelistRuleC_PathContext:
    """規則 C：路徑/檔名上下文偵測 _is_in_path_context。"""

    @pytest.fixture
    def fn(self):
        return getattr(_hook, "_is_in_path_context")

    @pytest.mark.parametrize("prompt,start_substr", [
        ("參考 .claude/error-patterns/implementation/IMP-057.md 的教訓", "implementation"),
        ("閱讀 docs/spec/modify-spec-guide.md 文件", "modify-spec"),
        ("修改 docs/work-logs/v0.18/IMP-052-implementation.md", "implementation"),
    ])
    def test_whitelisted_when_in_file_path(self, fn, prompt, start_substr):
        """匹配位置落在檔案路徑內 → 白名單化。"""
        start = prompt.index(start_substr)
        end = start + len(start_substr)
        is_wl, reason = fn(prompt, start, end)
        assert is_wl is True
        assert reason

    @pytest.mark.parametrize("prompt,start_substr", [
        ("請在 src/foo.py 中實作新功能", "實作"),
        ("完成後執行 git commit 提交", "git commit"),
        ("請修改規格以符合新需求", "修改規格"),
    ])
    def test_not_whitelisted_when_not_in_path(self, fn, prompt, start_substr):
        start = prompt.index(start_substr)
        end = start + len(start_substr)
        is_wl, _ = fn(prompt, start, end)
        assert is_wl is False

    def test_ticket_id_context_whitelisted(self, fn):
        """ticket ID 模式內的關鍵字視為引用（ticket track 命令）。"""
        prompt = "ticket track query 0.18.0-W11-004.1.2"
        start = prompt.index("ticket track")
        end = start + len("ticket track")
        is_wl, _ = fn(prompt, start, end)
        # 本 case 不嚴格要求 True（由實作決定），但不應 raise
        assert isinstance(is_wl, bool)


class TestWhitelistRuleD_MetaTaskPrompt:
    """規則 D（延伸）：Meta-task 偵測 _is_meta_task_prompt。"""

    @pytest.fixture
    def fn(self):
        return getattr(_hook, "_is_meta_task_prompt")

    @pytest.mark.parametrize("prompt", [
        "修改 .claude/rules/core/ai-communication-rules.md 新增『禁止硬編碼』章節",
        "編輯規則文件加入新約束",
        "更新 FORBIDDEN_KEYWORD_MAP 加入 git push pattern",
        "修改 .claude/agents/thyme-python-developer.md 的禁止行為章節",
    ])
    def test_meta_task_detected(self, fn, prompt):
        is_meta, reason = fn(prompt)
        assert is_meta is True
        assert reason

    @pytest.mark.parametrize("prompt", [
        "實作 src/foo.py 的 parse 函式",
        "修復 tests/unit/test_bar.py 失敗",
        "分析 docs/foo.md 後產出報告",
    ])
    def test_non_meta_task_not_detected(self, fn, prompt):
        is_meta, _ = fn(prompt)
        assert is_meta is False


class TestWhitelistIntegration:
    """整合測試：_detect_keyword_conflicts 套用白名單後過濾合法情境。"""

    def test_quoted_reference_not_emitted(self):
        prompt = "請遵守 thyme 定義中的『禁止實作程式碼』邊界"
        conflicts = _detect_keyword_conflicts(prompt, ["實作程式碼"])
        assert conflicts == [], f"引號引用不應觸發，但得到 {conflicts}"

    def test_negation_prefix_not_emitted(self):
        prompt = "請勿實作程式碼，僅產出設計規格"
        conflicts = _detect_keyword_conflicts(prompt, ["實作程式碼"])
        assert conflicts == []

    def test_path_context_not_emitted(self):
        prompt = "參考 .claude/error-patterns/PC-057-unauthorized-implementation.md"
        conflicts = _detect_keyword_conflicts(prompt, ["實作程式碼"])
        assert conflicts == []

    def test_real_violation_still_emitted(self):
        """真實越界案例（W5-001 範型）仍應觸發。"""
        prompt = "請實作新測試並寫入 tests/unit/foo.py"
        conflicts = _detect_keyword_conflicts(prompt, ["實作程式碼"])
        assert len(conflicts) >= 1

    def test_git_commit_real_violation_still_emitted(self):
        prompt = "修改 src/foo.py 後 git commit -m msg"
        conflicts = _detect_keyword_conflicts(prompt, ["git commit"])
        assert len(conflicts) >= 1

    def test_mixed_quoted_and_real_only_real_emitted(self):
        """同 prompt 含引號引用 + 真實違反 → 僅真實違反觸發。"""
        prompt = "說明『禁止 git commit』邊界。但請實作新功能 src/foo.py"
        conflicts = _detect_keyword_conflicts(
            prompt, ["實作程式碼", "git commit"]
        )
        keywords = {c["keyword"] for c in conflicts}
        assert "實作" in keywords
        assert "git commit" not in keywords, "引號引用不應觸發"


class TestWhitelistRulesRegistry:
    """WHITELIST_RULES 清單可擴充性驗證。"""

    def test_whitelist_rules_is_list(self):
        rules = getattr(_hook, "WHITELIST_RULES")
        assert isinstance(rules, list)

    def test_whitelist_rules_has_at_least_three_entries(self):
        """規則 A/B/C 必備；D 為延伸，至少 3 條。"""
        rules = getattr(_hook, "WHITELIST_RULES")
        assert len(rules) >= 3

    def test_each_rule_is_callable(self):
        rules = getattr(_hook, "WHITELIST_RULES")
        for rule in rules:
            assert callable(rule)


class TestWhitelistListDriven:
    """AC5 regression：新增規則到清單即生效（不需修改 _detect_keyword_conflicts）。

    防護 W11-004.1.3 Phase 4 三視角發現：WHITELIST_RULES 聲稱可擴充但整合點硬編碼，
    新增規則無法自動套用。本測試鎖死「清單驅動」契約。
    """

    def test_per_match_list_split_exists(self):
        """PER_MATCH_WHITELIST_RULES 與 PROMPT_LEVEL_WHITELIST_RULES 必須存在且為 list。"""
        per_match = getattr(_hook, "PER_MATCH_WHITELIST_RULES")
        prompt_level = getattr(_hook, "PROMPT_LEVEL_WHITELIST_RULES")
        assert isinstance(per_match, list) and len(per_match) >= 3
        assert isinstance(prompt_level, list) and len(prompt_level) >= 1

    def test_rule_b_wrapper_eliminated(self):
        """_rule_b_wrapper 必須被消除（簽名統一後不再需要）。"""
        assert not hasattr(_hook, "_rule_b_wrapper"), (
            "_rule_b_wrapper 應已消除；規則 B 改用統一簽名 (prompt, start, end=None)"
        )

    def test_adding_per_match_rule_takes_effect(self):
        """新增假 per-match 規則（永遠回 True）到清單 → 所有 conflict 應被過濾。"""
        def _fake_always_whitelist(prompt, start, end):
            return True, "fake_rule_for_test"

        original = list(_hook.PER_MATCH_WHITELIST_RULES)
        try:
            _hook.PER_MATCH_WHITELIST_RULES.append(_fake_always_whitelist)
            # 使用一個平時會觸發 git commit 的 prompt
            prompt = "請執行 git commit -m 'update'"
            conflicts = _detect_keyword_conflicts(prompt, ["git commit"])
            real = [c for c in conflicts if not c.get("whitelist_reason")]
            assert real == [], (
                f"新增假 per-match 規則後應過濾所有 conflict，實際 real={real}；"
                f"若仍觸發，代表 _detect_keyword_conflicts 未走清單迭代（硬編碼）"
            )
        finally:
            _hook.PER_MATCH_WHITELIST_RULES[:] = original


# ----------------------------------------------------------------------------
# W11-004.1.3.2：Meta-task 整體豁免改為 per-match 降級（TD-2 安全修復）
# ----------------------------------------------------------------------------

class TestMetaTaskPerMatchDegrade:
    """Meta-task prompt 不再整體豁免：真違規仍需偵測，僅透過 whitelist_reason 標記降級。

    修復前：_detect_keyword_conflicts 在 meta-task 命中時 `return []`，
    使後段真違規（git commit / 實作 / 修改檔案）靜默通過。

    修復後：meta-task 命中的 conflict 附帶 `whitelist_reason='meta_task_*'`，
    呼叫端據此降級為 logger.debug，不寫 events.jsonl；
    但真違規（非 meta-task 範疇的 keyword 命中）仍正常回報。
    """

    # --- AC：真違規在 meta-task prompt 中仍觸發（3 個情境）---

    def test_meta_task_with_git_commit_still_detects_git_commit(self):
        """情境 1：修改 .claude/rules/ + git commit → git commit 仍應觸發。"""
        prompt = (
            "修改 .claude/rules/core/quality-baseline.md 新增章節，"
            "完成後 git commit -m 'update rules'"
        )
        conflicts = _detect_keyword_conflicts(
            prompt, ["實作程式碼", "git commit"]
        )
        real = [c for c in conflicts if not c.get("whitelist_reason")]
        keywords = {c["keyword"] for c in real}
        assert "git commit" in keywords, (
            f"meta-task prompt 的真違規 git commit 應觸發，實際 conflicts={conflicts}"
        )

    def test_meta_task_with_impl_still_detects_impl(self):
        """情境 2：編輯規則文件 + 實作 src/foo.py → 實作 仍應觸發。"""
        prompt = (
            "編輯規則文件加入新約束，並請實作 src/foo.py 的 helper 函式"
        )
        conflicts = _detect_keyword_conflicts(prompt, ["實作程式碼"])
        real = [c for c in conflicts if not c.get("whitelist_reason")]
        assert len(real) >= 1, (
            f"meta-task prompt 後段的實作越界應觸發，實際 conflicts={conflicts}"
        )

    def test_meta_task_with_git_push_still_detects_git_push(self):
        """情境 3：更新 FORBIDDEN_KEYWORD_MAP + git push → git 寫入類違規仍應觸發。

        git push 在 FORBIDDEN_KEYWORD_MAP 下屬「git 寫入」key，action 標籤需含該子字串。
        """
        prompt = (
            "更新 FORBIDDEN_KEYWORD_MAP 加入 pattern 後 git push origin main"
        )
        conflicts = _detect_keyword_conflicts(
            prompt, ["git commit", "禁止 git 寫入操作"]
        )
        real = [c for c in conflicts if not c.get("whitelist_reason")]
        keywords = {c["keyword"] for c in real}
        assert "git 寫入" in keywords, (
            f"meta-task prompt 的真違規 git push 應觸發，實際 conflicts={conflicts}"
        )

    # --- AC：純 meta-task 與其他白名單組合不觸發（3 個情境）---

    def test_pure_meta_task_no_real_violation(self):
        """情境 4：純 meta-task（無違規動詞） → 不回報 real conflict。"""
        prompt = "修改 .claude/rules/core/ai-communication-rules.md 的章節結構"
        conflicts = _detect_keyword_conflicts(prompt, ["實作程式碼", "git commit"])
        real = [c for c in conflicts if not c.get("whitelist_reason")]
        assert real == [], (
            f"純 meta-task 不應產生 real conflict，實際 real={real}"
        )

    def test_meta_task_with_quoted_keyword_no_real_violation(self):
        """情境 5：meta-task + 引號內禁止詞（規則 A 應過濾）→ 不觸發 real。"""
        prompt = "修改 .claude/rules/ 加入『禁止實作』章節的說明"
        conflicts = _detect_keyword_conflicts(prompt, ["實作程式碼"])
        real = [c for c in conflicts if not c.get("whitelist_reason")]
        assert real == [], (
            f"引號引用應被規則 A 過濾，實際 real={real}"
        )

    def test_meta_task_with_negation_prefix_no_real_violation(self):
        """情境 6：meta-task + 否定前綴（規則 B 應過濾）→ 不觸發 real。"""
        prompt = "修改 .claude/rules/core/ 規則 X，請勿實作任何程式碼"
        conflicts = _detect_keyword_conflicts(prompt, ["實作程式碼"])
        real = [c for c in conflicts if not c.get("whitelist_reason")]
        assert real == [], (
            f"否定前綴應被規則 B 過濾，實際 real={real}"
        )

    # --- 補強：meta-task 匹配本身仍能被標記（供 caller 降級使用）---

    def test_meta_task_match_carries_whitelist_reason(self):
        """meta-task 命中的 conflict（若存在）需帶 whitelist_reason 以供 caller 降級。

        本測試確保下游 _emit_keyword_conflict_warning_if_any 能依此欄位
        區分 meta-filtered vs real，實現 logger.debug 降級而非 stderr 噴發。
        """
        # 此 prompt 為 meta-task 且含 keyword「修改」類（視 FORBIDDEN_KEYWORD_MAP 而定）；
        # 若無 keyword 命中，conflicts 為 []，仍滿足「不誤報」語意。
        prompt = "修改 .claude/rules/core/quality-baseline.md 補齊說明"
        conflicts = _detect_keyword_conflicts(prompt, ["實作程式碼", "git commit"])
        # 任何被認定為 meta-filtered 的 conflict 都必須帶 whitelist_reason
        for c in conflicts:
            # 若沒有 whitelist_reason，代表被當作真違規，這不該發生在此純 meta prompt
            assert c.get("whitelist_reason"), (
                f"純 meta-task prompt 的 conflict 應被標記 whitelist_reason，"
                f"實際={c}"
            )


# ============================================================================
# W11-004.1.3.3：白名單規則邊界調校
# ============================================================================


class TestRuleC_PositiveTokenCalibration:
    """規則 C 調校：路徑判斷改正向 token（非反向「無空白」）。

    問題：現行 `if " " not in between` 會把 `.claude/xxx禁止` 的 `禁止` 誤判為
    路徑內（between=`xxx`，無空白 → 誤 whitelist）。改用正向 token 驗證後，
    CJK 關鍵字不應被視為路徑內容。
    """

    @pytest.fixture
    def fn(self):
        return getattr(_hook, "_is_in_path_context")

    def test_cjk_keyword_after_path_prefix_not_whitelisted(self, fn):
        """.claude/xxx禁止 的 `禁止` 為 CJK 關鍵字，不應被判為路徑內。"""
        prompt = ".claude/xxx禁止"
        start = prompt.index("禁止")
        end = start + len("禁止")
        is_wl, _ = fn(prompt, start, end)
        assert is_wl is False, (
            "CJK 關鍵字緊接 .claude/xxx 後不應被誤判為路徑（W11-004.1.3.3 規則 C 調校）"
        )

    def test_keyword_after_path_with_whitespace_separator_not_whitelisted(self, fn):
        """.claude/foo-bar.md 禁止 中的 `禁止` 被空白分隔，不應判為路徑內。"""
        prompt = ".claude/rules/foo-bar.md 禁止修改此檔案"
        start = prompt.index("禁止")
        end = start + len("禁止")
        is_wl, _ = fn(prompt, start, end)
        assert is_wl is False

    def test_ascii_word_inside_path_still_whitelisted(self, fn):
        """正向 token 調校不應破壞既有 ASCII 路徑片段識別能力。"""
        prompt = "參考 .claude/error-patterns/implementation/IMP.md"
        start = prompt.index("implementation")
        end = start + len("implementation")
        is_wl, _ = fn(prompt, start, end)
        assert is_wl is True


class TestRuleB_NegationWindowCalibration:
    """規則 B 調校：視窗 10→20 + 逗號作句子邊界。

    問題：現行 10 字元視窗漏掉常見中文長句型
    「請不要在這個 ticket 裡面實作」，否定詞距關鍵字 14+ 字元。
    擴至 20 後可命中，同時逗號應視為句子邊界以保留「跨句不算」語意。
    """

    @pytest.fixture
    def fn(self):
        return getattr(_hook, "_has_negation_prefix")

    def test_long_form_chinese_negation_within_20_chars_whitelisted(self, fn):
        """中長距（14+ 字）否定句應被視為否定前綴。"""
        prompt = "請不要在這個 ticket 裡面實作程式碼"
        start = prompt.index("實作")
        is_wl, reason = fn(prompt, start)
        assert is_wl is True, (
            "20 字內的否定詞（跨 ticket 字串）應被識別為否定前綴（W11-004.1.3.3 規則 B 調校）"
        )
        assert reason

    def test_negation_separated_by_period_still_not_counted(self, fn):
        """否定詞與關鍵字跨越句號 → 仍不算前綴（保留原語意）。"""
        prompt = "請不要。請實作新功能"
        start = prompt.index("實作")
        is_wl, _ = fn(prompt, start)
        assert is_wl is False


class TestRuleD_MetaTaskWindowCalibration:
    """規則 D 調校：meta-task 視窗由固定 100 字 → 第一段或前 500 字。

    問題：Ticket prompt 第一行常為 `Ticket: 0.18.0-W...`（30 字），
    meta-task 描述（如「修改 .claude/rules/...」）出現在空行後第二段，
    100 字視窗會漏判。
    """

    @pytest.fixture
    def fn(self):
        return getattr(_hook, "_is_meta_task_prompt")

    def test_ticket_header_then_meta_task_body_detected(self, fn):
        """Ticket 標題段（>100 字）後第二段為 meta-task 描述，應命中。"""
        prompt = (
            "Ticket: 0.18.0-W11-004.1.3.3 調校白名單規則邊界"
            "（路徑判斷改正向 token + 否定視窗擴展 + meta-task 第一段語意邊界）\n\n"
            "修改 .claude/rules/core/quality-baseline.md 補齊說明，"
            "新增『失敗案例學習』章節。"
        )
        is_meta, reason = fn(prompt)
        assert is_meta is True, (
            "第二段的 meta-task pattern 應被命中（W11-004.1.3.3 規則 D 調校）"
        )
        assert reason

    def test_long_prompt_without_meta_pattern_not_detected(self, fn):
        """單段長 prompt 但無 meta-task pattern → 不命中（避免誤報）。"""
        prompt = (
            "實作 src/extractor/foo.py 的 parse 函式，"
            "處理 Readmoo API 回傳的 JSON 結構，"
            "注意空值與錯誤欄位的 fallback 設計。"
            "測試覆蓋率要求 >= 80%，"
            "請在 tests/unit/test_foo.py 新增至少 5 個測試案例。"
        ) * 3  # 確保超過 500 字
        is_meta, _ = fn(prompt)
        assert is_meta is False


# ============================================================================
# W11-004.1.4：分層判決測試（high-confidence block / low-confidence warn / bypass）
# ============================================================================

_HIGH_CONF_AGENT_MD = """---
name: tiered-test-agent
---

## 允許產出

略

## 禁止行為

1. **禁止 git commit**：不得自行 commit
2. **禁止 ticket CLI**：不得呼叫 ticket 指令
3. **禁止 git 寫入**：不得 push / merge
4. **禁止分支操作**：不得 checkout / switch
5. **禁止實作程式碼**：不得撰寫實作

## 適用情境

略
"""


class TestTieredVerdictUnit:
    """分層判決純函式單元測試（不經 main()）。"""

    def test_partition_separates_high_and_low(self):
        conflicts = [
            {"keyword": "git commit", "action": "a", "matched_pattern": "", "prompt_excerpt": ""},
            {"keyword": "實作", "action": "b", "matched_pattern": "", "prompt_excerpt": ""},
            {"keyword": "ticket CLI", "action": "c", "matched_pattern": "", "prompt_excerpt": ""},
            {"keyword": "修改檔案", "action": "d", "matched_pattern": "", "prompt_excerpt": ""},
        ]
        high, low = _hook._partition_by_confidence(conflicts)
        assert {c["keyword"] for c in high} == {"git commit", "ticket CLI"}
        assert {c["keyword"] for c in low} == {"實作", "修改檔案"}

    def test_bypass_env_var_triggers(self, monkeypatch):
        monkeypatch.setenv(_hook._BYPASS_ENV_VAR, "1")
        bypassed, reason = _hook._is_bypass_requested("any prompt")
        assert bypassed is True
        assert "env" in reason

    def test_bypass_prompt_marker_triggers(self, monkeypatch):
        monkeypatch.delenv(_hook._BYPASS_ENV_VAR, raising=False)
        bypassed, reason = _hook._is_bypass_requested(
            f"請執行任務 {_hook._BYPASS_PROMPT_MARKER}"
        )
        assert bypassed is True
        assert "prompt_marker" in reason

    def test_no_bypass_when_neither_present(self, monkeypatch):
        monkeypatch.delenv(_hook._BYPASS_ENV_VAR, raising=False)
        bypassed, _reason = _hook._is_bypass_requested("no bypass here")
        assert bypassed is False

    def test_high_confidence_keywords_contains_git_commit(self):
        assert "git commit" in _hook.HIGH_CONFIDENCE_KEYWORDS
        assert "ticket CLI" in _hook.HIGH_CONFIDENCE_KEYWORDS
        assert "git 寫入" in _hook.HIGH_CONFIDENCE_KEYWORDS
        assert "分支操作" in _hook.HIGH_CONFIDENCE_KEYWORDS
        # 低信心 keyword 不應出現在集合
        assert "實作" not in _hook.HIGH_CONFIDENCE_KEYWORDS
        assert "修改檔案" not in _hook.HIGH_CONFIDENCE_KEYWORDS


class TestTieredVerdictIntegration:
    """整合：main() 分層判決。"""

    def _setup(self, monkeypatch, tmp_path, agent_name="tiered-test-agent"):
        _write_agent_md(tmp_path, agent_name, _HIGH_CONF_AGENT_MD)
        monkeypatch.setattr(_hook, "get_project_root", lambda: tmp_path)
        monkeypatch.delenv(_hook._BYPASS_ENV_VAR, raising=False)

    def test_high_confidence_git_commit_blocks(self, monkeypatch, capsys, tmp_path):
        """AC-T4：高信心 git commit 衝突 → exit 2。"""
        self._setup(monkeypatch, tmp_path)
        exit_code = _run_hook(
            monkeypatch, capsys,
            tool_input={
                "subagent_type": "tiered-test-agent",
                "prompt": "完成後 git commit -m 'done'",
            },
        )
        err = capsys.readouterr().err
        assert exit_code == 2
        assert "git commit" in err
        assert "已阻擋" in err or "高信心" in err

    def test_high_confidence_ticket_cli_blocks(self, monkeypatch, capsys, tmp_path):
        """AC-T5：高信心 ticket CLI 衝突 → exit 2。"""
        self._setup(monkeypatch, tmp_path)
        exit_code = _run_hook(
            monkeypatch, capsys,
            tool_input={
                "subagent_type": "tiered-test-agent",
                "prompt": "請執行 ticket track claim 0.18.0-W1-001",
            },
        )
        assert exit_code == 2

    def test_low_confidence_only_warns_not_blocks(
        self, monkeypatch, capsys, tmp_path
    ):
        """AC-T6：僅低信心衝突（實作）→ 警告，exit 0。"""
        self._setup(monkeypatch, tmp_path)
        exit_code = _run_hook(
            monkeypatch, capsys,
            tool_input={
                "subagent_type": "tiered-test-agent",
                "prompt": "請實作新功能並寫入設計",
            },
        )
        err = capsys.readouterr().err
        assert exit_code == 0
        assert "實作" in err
        # 警告 template 特徵
        assert "警告" in err or "W5-045" in err
        # 不應使用 block template
        assert "已阻擋" not in err

    def test_bypass_env_var_downgrades_block_to_warn(
        self, monkeypatch, capsys, tmp_path
    ):
        """AC-T7：高信心 + bypass env → exit 0（降級為 warn）。"""
        self._setup(monkeypatch, tmp_path)
        monkeypatch.setenv(_hook._BYPASS_ENV_VAR, "1")
        exit_code = _run_hook(
            monkeypatch, capsys,
            tool_input={
                "subagent_type": "tiered-test-agent",
                "prompt": "完成後 git commit -m 'done'",
            },
        )
        err = capsys.readouterr().err
        assert exit_code == 0
        assert "BYPASS" in err
        assert "git commit" in err

    def test_bypass_prompt_marker_downgrades_block_to_warn(
        self, monkeypatch, capsys, tmp_path
    ):
        """AC-T8：高信心 + prompt marker → exit 0。"""
        self._setup(monkeypatch, tmp_path)
        exit_code = _run_hook(
            monkeypatch, capsys,
            tool_input={
                "subagent_type": "tiered-test-agent",
                "prompt": (
                    f"完成後 git commit -m 'done' {_hook._BYPASS_PROMPT_MARKER}"
                ),
            },
        )
        err = capsys.readouterr().err
        assert exit_code == 0
        assert "BYPASS" in err

    def test_block_message_contains_agent_name_and_suggestion(
        self, monkeypatch, capsys, tmp_path
    ):
        """AC-T9：block 訊息含 agent 名稱與建議（職責、改派、繞過方式）。"""
        self._setup(monkeypatch, tmp_path)
        exit_code = _run_hook(
            monkeypatch, capsys,
            tool_input={
                "subagent_type": "tiered-test-agent",
                "prompt": "請 git commit 完成此任務",
            },
        )
        err = capsys.readouterr().err
        assert exit_code == 2
        assert "tiered-test-agent" in err
        assert "職責" in err or "改派" in err or "繞過" in err
        assert _hook._BYPASS_ENV_VAR in err  # 應告知繞過方式

    def test_clean_prompt_still_passes(self, monkeypatch, capsys, tmp_path):
        """AC-T10：無衝突 prompt → exit 0 + 無警告/阻擋訊息。"""
        self._setup(monkeypatch, tmp_path)
        exit_code = _run_hook(
            monkeypatch, capsys,
            tool_input={
                "subagent_type": "tiered-test-agent",
                "prompt": "請分析現有架構並撰寫分析報告",
            },
        )
        err = capsys.readouterr().err
        assert exit_code == 0
        assert "已阻擋" not in err
        assert "W5-045" not in err

    def test_mixed_high_and_low_blocks(self, monkeypatch, capsys, tmp_path):
        """AC-T11：高+低信心並存 → 走 block 路徑。"""
        self._setup(monkeypatch, tmp_path)
        exit_code = _run_hook(
            monkeypatch, capsys,
            tool_input={
                "subagent_type": "tiered-test-agent",
                "prompt": "請實作功能並 git commit -m 'done'",
            },
        )
        assert exit_code == 2


# ----------------------------------------------------------------------------
# W17-018：Ticket where.files fallback 測試
# ----------------------------------------------------------------------------


def test_extract_ticket_ids_finds_full_ids():
    """從 prompt 擷取完整 ticket ID。"""
    ids = _hook._extract_ticket_ids(
        "Ticket: 0.18.0-W17-015.2，依賴 0.18.0-W17-015.3"
    )
    assert "0.18.0-W17-015.2" in ids
    assert "0.18.0-W17-015.3" in ids


def test_extract_ticket_ids_no_match_for_bare_short_id():
    """短 ID（W17-015）無版本前綴時不匹配（避免誤判）。"""
    ids = _hook._extract_ticket_ids("Ticket: W17-015")
    assert ids == []


def test_load_ticket_where_files_returns_paths_for_w17_015_2():
    """W17-015.2 ticket md 存在時，應讀出 where.files。"""
    files = _hook._load_ticket_where_files("0.18.0-W17-015.2")
    # 此 ticket 已存在且 where 含 .claude/ 路徑
    assert any(".claude/skills/ticket" in f for f in files)


def test_load_ticket_where_files_returns_empty_for_nonexistent():
    """不存在的 ticket 回傳空清單。"""
    files = _hook._load_ticket_where_files("9.9.9-W99-999")
    assert files == []


def test_hook_fallback_to_ticket_when_prompt_has_no_paths(
    monkeypatch, capsys
):
    """W17-018 關鍵：prompt 無路徑線索但含 ticket ID 指向 .claude/ 任務時，
    應從 ticket where.files 補分類為主 repo .claude/，放行無 worktree。"""
    exit_code = _run_hook(
        monkeypatch,
        capsys,
        tool_input={
            "subagent_type": "thyme-python-developer",
            "prompt": "Ticket: 0.18.0-W17-015.2\nRead ticket md 依規格實作。",
        },
    )
    # W17-015.2 where.files 為 .claude/skills/ticket/... → 全主 repo .claude/
    # → 豁免 worktree 放行
    assert exit_code == 0


# ----------------------------------------------------------------------------
# W11-004.7：_resolve_path_classification helper 測試（Phase 2 RED）
#
# 對應 Ticket 0.18.0-W11-004.7 規格：
# - 抽取統一 helper：_resolve_path_classification(prompt, ticket_ids, *, logger=None)
# - 三層整合：L1 _classify_prompt_paths → L2 W17-018 ticket where.files fallback
#   → L3 W11-004.7 純 .claude/ 豁免判斷
# - 回傳統一分類結果：(has_main_repo_claude, has_external_claude, has_other)
#
# 設計目標：
# 1. 主入口 main() 將呼叫 helper 而非散落的三層邏輯
# 2. helper 可獨立測試，覆蓋三大情境（純 .claude/、混合、空）+ 反向風險
# 3. 邊界條件（空 ticket_ids、空 prompt、has_other 仍 True 的混合 case）
# ----------------------------------------------------------------------------


@pytest.fixture
def _resolve_helper():
    """取得 _resolve_path_classification helper（RED：尚未實作）。"""
    return _hook._resolve_path_classification


# === 情境 1：純 .claude/ ticket（L1 + L2 都指向主 repo .claude/） ===

def test_resolve_pure_claude_prompt_only(_resolve_helper):
    """L1：prompt 直接含 .claude/ 路徑，無需 L2 fallback。
    預期：(True, False, False) 純主 repo .claude/。"""
    result = _resolve_helper(
        prompt="修改 .claude/hooks/foo.py 加入新檢查",
        ticket_ids=[],
    )
    assert result == (True, False, False)


def test_resolve_pure_claude_via_ticket_fallback(_resolve_helper):
    """L2：prompt 無路徑線索，ticket where.files 全為 .claude/。
    預期：(True, False, False) 由 fallback 補分類後回傳。"""
    result = _resolve_helper(
        prompt="Ticket: 0.18.0-W17-015.2\nRead ticket md 依規格實作。",
        ticket_ids=["0.18.0-W17-015.2"],
    )
    # W17-015.2 where.files 為 .claude/skills/ticket/...
    assert result[0] is True, "應補分類為主 repo .claude/"
    assert result[1] is False, "不應誤判為外部 .claude/"
    assert result[2] is False, "純 .claude/ ticket 不應有 has_other"


# === 情境 2：混合 ticket（.claude/ + 非 .claude/） ===

def test_resolve_mixed_prompt_main_claude_and_other(_resolve_helper):
    """L1：prompt 同時含主 repo .claude/ 與 src/。
    預期：(True, False, True) 混合（has_other 仍為 True）。"""
    result = _resolve_helper(
        prompt="同時修改 .claude/hooks/foo.py 和 src/api/bar.py",
        ticket_ids=[],
    )
    assert result == (True, False, True)


def test_resolve_mixed_via_ticket_fallback(_resolve_helper, tmp_path, monkeypatch):
    """L2：prompt 無路徑，ticket where.files 含 .claude/ + src/ 混合。
    預期：(True, False, True)。"""
    # 偽造 ticket md，含混合 where.files
    fake_ticket_md = tmp_path / "tickets" / "9.9.9-W99-001.md"
    fake_ticket_md.parent.mkdir(parents=True, exist_ok=True)
    fake_ticket_md.write_text(
        "---\nid: 9.9.9-W99-001\nwhere:\n  files:\n"
        "  - .claude/hooks/foo.py\n"
        "  - src/api/bar.py\n---\n",
        encoding="utf-8",
    )
    # 注入 _load_ticket_where_files 返回混合路徑
    monkeypatch.setattr(
        _hook,
        "_load_ticket_where_files",
        lambda tid: [".claude/hooks/foo.py", "src/api/bar.py"]
        if tid == "9.9.9-W99-001"
        else [],
    )

    result = _resolve_helper(
        prompt="Ticket: 9.9.9-W99-001\n依規格實作。",
        ticket_ids=["9.9.9-W99-001"],
    )
    assert result[0] is True, "應補分類含主 repo .claude/"
    assert result[2] is True, "應補分類含 has_other（src/）"


# === 情境 3：空 ticket where.files（L2 fallback 無資料） ===

def test_resolve_empty_ticket_where_files(_resolve_helper, monkeypatch):
    """L2：prompt 無路徑、ticket 存在但 where.files 為空。
    預期：(False, False, False) 三層皆無資訊，由上層決定阻擋。"""
    monkeypatch.setattr(
        _hook,
        "_load_ticket_where_files",
        lambda tid: [],
    )
    result = _resolve_helper(
        prompt="Ticket: 9.9.9-W99-002\n做點事。",
        ticket_ids=["9.9.9-W99-002"],
    )
    assert result == (False, False, False)


def test_resolve_empty_prompt_empty_ticket_ids(_resolve_helper):
    """邊界：prompt 空 + ticket_ids 空 → (False, False, False)。"""
    result = _resolve_helper(prompt="", ticket_ids=[])
    assert result == (False, False, False)


# === 反向風險：非 .claude/ ticket 在 prompt 引用 .claude/ 規則文件 ===
# 規則 .md 引用不應觸發豁免，避免錯誤豁免應走 worktree 的純 src/ ticket。

def test_resolve_non_claude_ticket_prompt_quotes_claude_rule_doc(
    _resolve_helper, monkeypatch
):
    """反向風險：純 src/ ticket 的 prompt 提及 .claude/rules/...md 作參考。

    雖然 prompt 字串含 .claude/ 字樣（規則文件引用），但 ticket where.files
    指向 src/，整合分類後 has_other 仍應為 True，不應被誤判為純 .claude/ 任務
    而豁免 worktree。

    預期：(True, False, True) — has_main_repo_claude 因 prompt 文本為 True，
    但 has_other 同時為 True，上層仍會強制 worktree。
    """
    monkeypatch.setattr(
        _hook,
        "_load_ticket_where_files",
        lambda tid: ["src/api/bar.py", "tests/api/bar_test.py"]
        if tid == "9.9.9-W99-003"
        else [],
    )
    result = _resolve_helper(
        prompt=(
            "Ticket: 9.9.9-W99-003\n"
            "請依 .claude/rules/core/quality-baseline.md 規範實作 src/api/bar.py"
        ),
        ticket_ids=["9.9.9-W99-003"],
    )
    # 關鍵：has_other 必為 True（避免上層誤豁免）
    assert result[2] is True, "ticket where.files 含 src/ → has_other 必為 True"


# === 邊界：has_other 仍 True 的混合 case（豁免不應觸發） ===

def test_resolve_mixed_case_has_other_remains_true(_resolve_helper):
    """邊界：L1 已分類混合（has_main_claude=True, has_other=True），
    L2 fallback 不應吞掉 has_other 訊號（即 OR 累加，非覆寫）。"""
    result = _resolve_helper(
        prompt="修改 .claude/hooks/foo.py 和 lib/widgets/bar.dart",
        ticket_ids=[],
    )
    assert result[0] is True
    assert result[2] is True, "has_other 必須保留，不可被豁免邏輯抹除"


# === 邊界：logger 參數可選（不傳不應 crash） ===

def test_resolve_logger_optional(_resolve_helper):
    """helper 簽章：logger 為 keyword-only optional，不傳應正常運作。"""
    # 不傳 logger
    result = _resolve_helper(prompt=".claude/hooks/foo.py", ticket_ids=[])
    assert result == (True, False, False)


def test_resolve_logger_passed_does_not_crash(_resolve_helper):
    """傳入 logger 也應正常運作（fallback 路徑會用到 logger.info）。"""
    import logging
    logger = logging.getLogger("test_resolve")
    result = _resolve_helper(
        prompt="修改 src/foo.py",
        ticket_ids=[],
        logger=logger,
    )
    assert result == (False, False, True)


# === 整合：main() 呼叫 helper 後行為一致 ===

def test_main_uses_resolver_for_pure_claude_ticket(monkeypatch, capsys):
    """整合：純 .claude/ ticket 經 helper 分類後，main 應放行（無 worktree）。

    與既有 test_hook_fallback_to_ticket_when_prompt_has_no_paths 相同行為，
    但本測試確認在 helper 抽取後仍維持。
    """
    exit_code = _run_hook(
        monkeypatch,
        capsys,
        tool_input={
            "subagent_type": "thyme-python-developer",
            "prompt": "Ticket: 0.18.0-W17-015.2\nRead ticket md 依規格實作。",
        },
    )
    assert exit_code == 0


def test_main_uses_resolver_for_mixed_ticket_blocks_without_worktree(
    monkeypatch, capsys
):
    """整合：混合 ticket（.claude/ + src/）無 worktree → 阻擋。

    確認 helper 整合後，has_other=True 的訊號不會被豁免邏輯吞掉。
    """
    monkeypatch.setattr(
        _hook,
        "_load_ticket_where_files",
        lambda tid: [".claude/hooks/foo.py", "src/api/bar.py"]
        if tid == "9.9.9-W99-004"
        else [],
    )
    exit_code = _run_hook(
        monkeypatch,
        capsys,
        tool_input={
            "subagent_type": "thyme-python-developer",
            "prompt": "Ticket: 9.9.9-W99-004\n依規格實作。",
        },
    )
    assert exit_code == 2, "混合 ticket 無 worktree 應阻擋"
