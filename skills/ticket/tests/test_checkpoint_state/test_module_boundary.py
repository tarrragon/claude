"""Group F：模組邊界測試（防循環依賴 + import 清單 + 反向可 import）。

對應 Phase 2 §3 Group F（F1/F2/F3）與 AC3 模組邊界。
"""

from __future__ import annotations

import ast
import importlib
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# F1：import checkpoint_state 後 sys.modules 不含 track_snapshot / track_query
# ---------------------------------------------------------------------------


def test_F1_checkpoint_state_does_not_import_track_modules():
    """checkpoint_state 只能依賴 paths/constants/handoff_utils/subprocess 等底層。

    禁止 import track_snapshot / track_query（會造成循環依賴）。
    """

    # 清除可能的殘留快取（本測試若在其他測試後跑，track_* 可能已被其他模組載入，
    # 所以改用「checkpoint_state 原始碼層級」驗證：F1 以 AST 形式驗證 import 清單）
    import ticket_system.lib.checkpoint_state as mod

    module_path = Path(mod.__file__)
    tree = ast.parse(module_path.read_text(encoding="utf-8"))

    imported_names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported_names.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imported_names.append(node.module)

    # 斷言：不存在 track_snapshot / track_query 的 import
    joined = " ".join(imported_names)
    assert "track_snapshot" not in joined, (
        f"checkpoint_state 禁止依賴 track_snapshot（循環依賴）；實際 imports: {imported_names}"
    )
    assert "track_query" not in joined, (
        f"checkpoint_state 禁止依賴 track_query（循環依賴）；實際 imports: {imported_names}"
    )


# ---------------------------------------------------------------------------
# F2：AST 解析 import 清單，僅包含允許的模組
# ---------------------------------------------------------------------------


def test_F2_checkpoint_state_imports_only_allowed_modules():
    """Phase 3a §T5 + Phase 2 §3 Group F2：import 清單白名單檢查。

    允許：paths / constants / handoff_utils / subprocess / dataclasses /
          datetime / json / pathlib / typing / time / sys / __future__
    """

    import ticket_system.lib.checkpoint_state as mod

    module_path = Path(mod.__file__)
    tree = ast.parse(module_path.read_text(encoding="utf-8"))

    allowed = {
        "__future__",
        "dataclasses",
        "datetime",
        "json",
        "pathlib",
        "subprocess",
        "sys",
        "time",
        "typing",
        # 模組內部相對 import
        ".paths",
        ".constants",
        ".handoff_utils",
        # 絕對形式
        "ticket_system.lib.paths",
        "ticket_system.lib.constants",
        "ticket_system.lib.handoff_utils",
    }

    seen: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                seen.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            # level=1 代表相對 import（from .paths import ...）
            prefix = "." * (node.level or 0)
            module = f"{prefix}{node.module or ''}"
            seen.append(module)

    unexpected = [name for name in seen if name not in allowed]
    assert not unexpected, (
        f"checkpoint_state import 超出允許清單：{unexpected}；允許的：{sorted(allowed)}"
    )


# ---------------------------------------------------------------------------
# F3：反向可 import（三投影 CLI 未來可 import checkpoint_state 而無循環）
# ---------------------------------------------------------------------------


def test_F3_checkpoint_state_module_is_importable_from_commands_layer():
    """反向驗證：從 commands 層（track_snapshot）的位置可成功 import checkpoint_state。

    做法：直接從 ticket_system.lib.checkpoint_state import 主要 public API，
    若有循環依賴會於此 import 時失敗。
    """

    # 強制重新 import 確認無副作用
    if "ticket_system.lib.checkpoint_state" in sys.modules:
        del sys.modules["ticket_system.lib.checkpoint_state"]

    mod = importlib.import_module("ticket_system.lib.checkpoint_state")

    # 基本 public API 皆存在
    for name in (
        "CheckpointState",
        "PendingCheck",
        "_derive_checkpoint",
        "SAFE_CALL",
        "IO_ERRORS",
        "_read_git_status",
        "_read_dispatch_active",
        "_read_handoff_pending",
        "_query_in_progress_tickets",
        "_read_git_worktrees",
    ):
        assert hasattr(mod, name), f"checkpoint_state 缺少 public API: {name}"
