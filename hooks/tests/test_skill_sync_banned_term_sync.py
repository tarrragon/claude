"""skill-sync 增量禁用詞掃描的詞表/豁免規則與 skill-banned-term-scan-hook 的漂移檢查。

skill-sync 是零框架依賴的獨立套件（見 skill_sync/cli.py 模組頂部說明），不
import .claude/hooks/skill-banned-term-scan-hook.py——push 端的增量掃描判準
是該 hook 判準的字面複製。本測試斷言兩者字面一致，SSOT（本檔視
skill-banned-term-scan-hook.py 為判準來源）修改詞表或豁免規則時，能被此
測試捕捉，而非任由兩處各自維護悄悄分歧。

本測試刻意放在專案層級（.claude/hooks/tests/），不在 skill-sync 自身目錄
內——比照既有裸格式 ticket ID 正則複製的同一模式（見
test_skill_sync_ticket_id_pattern_sync.py），若放進 skill 目錄，測試原始碼
本身含框架共用工具模組的字面路徑引用會被閘門自己的 consumer-path 判準命中，
形成自我指涉違規。
"""
import importlib.util
import sys
from pathlib import Path

_hooks_dir = Path(__file__).resolve().parent.parent  # .claude/hooks
_project_root = _hooks_dir.parent.parent  # 專案根
_skill_sync_dir = _project_root / ".claude" / "skills" / "skill-sync"

if str(_skill_sync_dir) not in sys.path:
    sys.path.insert(0, str(_skill_sync_dir))

from skill_sync.cli import (  # noqa: E402
    _BANNED_TERMS,
    _BANNED_TERM_INLINE_MARKER,
)

# skill-banned-term-scan-hook.py 檔名含連字號，非合法模組識別符，無法直接
# `import`，改用 importlib 依檔案路徑載入（既有專案內處理連字號檔名 hook 的
# 慣例手法）。
_hook_path = _hooks_dir / "skill-banned-term-scan-hook.py"
_spec = importlib.util.spec_from_file_location("skill_banned_term_scan_hook", _hook_path)
_hook_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_hook_module)


def test_skill_sync_banned_terms_match_hook_literal():
    """cli.py 的 _BANNED_TERMS 詞表（含建議替換字）須與 hook 的 BANNED_TERMS 逐字一致。"""
    assert _BANNED_TERMS == _hook_module.BANNED_TERMS


def test_skill_sync_inline_marker_matches_hook_literal():
    """行內豁免標記字面須一致，否則同一份標記在兩套系統下的豁免效果會不對等。"""
    assert _BANNED_TERM_INLINE_MARKER == _hook_module.INLINE_MARKER
