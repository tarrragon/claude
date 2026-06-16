"""Tests for sync-claude-push.py 框架 import smoke test 閘門（C1 生產閘）.

涵蓋 acceptance：
  (1) staging 樹 import 全模組失敗時 push 以 exit 1 abort（內部 import 殘留 / 語法錯誤）
  (3) 至少 2 個 smoke test 閘門單元測試（綠燈放行 / 紅燈 abort）

設計：run_framework_smoke_test(staging_dir) 於 staging 樹（git archive 解出、已 strip
.claude/ 前綴的目錄）import ticket_system 全模組。內部模組缺失（import 殘留，即 W9-001
型機械缺陷）或語法錯誤 → sys.exit(1)。已知第三方依賴（filelock / yaml）在無依賴的
push 執行環境缺失屬環境限制，不算缺陷，不得誤報 abort。
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parent.parent / "sync-claude-push.py"
_spec = importlib.util.spec_from_file_location("sync_claude_push", _SCRIPT)
assert _spec and _spec.loader
sync_mod = importlib.util.module_from_spec(_spec)
sys.modules["sync_claude_push"] = sync_mod
_spec.loader.exec_module(sync_mod)  # type: ignore[union-attr]


def _make_ticket_system(staging: Path) -> Path:
    """在 staging 樹建立最小可 import 的 ticket_system 套件，回傳套件目錄。

    結構對應 staging 樹（已 strip .claude/ 前綴）：
        skills/ticket/ticket_system/__init__.py
        skills/ticket/ticket_system/constants.py
    """
    pkg = staging / "skills" / "ticket" / "ticket_system"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "constants.py").write_text(
        "GATE_OK = True\n", encoding="utf-8"
    )
    return pkg


def test_smoke_test_passes_on_valid_tree(tmp_path: Path):
    """綠燈放行：staging 樹全模組可 import → 函式正常返回，不 exit。"""
    staging = tmp_path / "staging"
    staging.mkdir()
    _make_ticket_system(staging)

    # 不應拋 SystemExit
    sync_mod.run_framework_smoke_test(staging)


def test_smoke_test_aborts_on_internal_import_residue(tmp_path: Path):
    """紅燈 abort：模組殘留對已刪除內部模組的 import（W9-001 型缺陷）→ exit 1。"""
    staging = tmp_path / "staging"
    staging.mkdir()
    pkg = _make_ticket_system(staging)
    (pkg / "broken.py").write_text(
        "from ticket_system.deleted_module import gone\n", encoding="utf-8"
    )

    with pytest.raises(SystemExit) as exc:
        sync_mod.run_framework_smoke_test(staging)
    assert exc.value.code == 1


def test_smoke_test_aborts_on_syntax_error(tmp_path: Path):
    """紅燈 abort：模組語法錯誤 → exit 1。"""
    staging = tmp_path / "staging"
    staging.mkdir()
    pkg = _make_ticket_system(staging)
    (pkg / "broken.py").write_text(
        "def f(:\n    pass\n", encoding="utf-8"
    )

    with pytest.raises(SystemExit) as exc:
        sync_mod.run_framework_smoke_test(staging)
    assert exc.value.code == 1


def test_smoke_test_tolerates_missing_third_party_dep(tmp_path: Path):
    """零誤報：模組 import 不存在的第三方依賴（環境限制非缺陷）→ 不 abort。"""
    staging = tmp_path / "staging"
    staging.mkdir()
    pkg = _make_ticket_system(staging)
    # 模擬 file_lock.py：import 真實第三方庫 filelock，push 零依賴環境本就無
    (pkg / "lib").mkdir()
    (pkg / "lib" / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "lib" / "file_lock.py").write_text(
        "import filelock  # noqa: F401\n", encoding="utf-8"
    )

    # 不應 abort（第三方缺失屬環境限制，非 import 殘留缺陷）
    sync_mod.run_framework_smoke_test(staging)


def test_smoke_test_no_op_when_package_absent(tmp_path: Path):
    """staging 樹無 ticket_system（理論上不會發生）→ 不 abort，安全略過。"""
    staging = tmp_path / "staging"
    staging.mkdir()
    # 不建立 ticket_system
    sync_mod.run_framework_smoke_test(staging)
