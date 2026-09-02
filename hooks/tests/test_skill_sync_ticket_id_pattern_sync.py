"""skill-sync 可攜性閘門的裸格式 ticket ID 正則與框架 SSOT 的漂移檢查。

skill-sync 是零框架依賴的獨立套件（見 skill_sync/cli.py 模組頂部說明），不
import lib/ticket_id_pattern.py——閘門內的裸格式正則是該 SSOT 的字面複製。
本測試斷言兩者字面一致，SSOT 修改時能被此測試捕捉，而非任由兩處各自 compile
悄悄分歧（lib/ticket_id_pattern.py docstring 記載的既有覆轍：hooks 全域曾有
約 10 處各自定義，比對行為不一致而產生跨處判定漂移）。

本測試刻意放在專案層級（.claude/hooks/tests/），不在 skill-sync 自身目錄
內——若放進 skill 目錄，測試原始碼本身含框架共用工具模組的字面路徑引用會被
閘門自己的 consumer-path 判準命中，形成自我指涉違規。
"""
import sys
from pathlib import Path

_hooks_dir = Path(__file__).resolve().parent.parent  # .claude/hooks
_project_root = _hooks_dir.parent.parent  # 專案根
_skill_sync_dir = _project_root / ".claude" / "skills" / "skill-sync"

if str(_hooks_dir) not in sys.path:
    sys.path.insert(0, str(_hooks_dir))
if str(_skill_sync_dir) not in sys.path:
    sys.path.insert(0, str(_skill_sync_dir))

from lib.ticket_id_pattern import BARE_BOTH_BOUNDED_RE  # noqa: E402
from skill_sync.cli import _BARE_TICKET_ID_RE  # noqa: E402


def test_skill_sync_bare_ticket_id_regex_matches_ssot_literal():
    """cli.py 的裸格式正則字面須與 SSOT 的 BARE_BOTH_BOUNDED_RE 逐字一致。"""
    assert _BARE_TICKET_ID_RE.pattern == BARE_BOTH_BOUNDED_RE.pattern
