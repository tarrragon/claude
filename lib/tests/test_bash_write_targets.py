"""bash_write_targets 共用抽取模組的載入鎖定與正向對照。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from lib import bash_write_targets  # noqa: E402


def test_module_exposes_callable_extractor():
    """模組可 import 且抽取函式可呼叫（載入失效時紅燈）。"""
    assert callable(bash_write_targets.iter_checkout_write_targets)


_PATH_HEAD = "import sys\nfrom pathlib import Path\nw = Path(sys.argv[1])\n"


def test_path_open_write_modes_counted_as_write():
    """3.6.0-W1-263 正向對照：Path 串接／Path 變數 .open(寫入模式) 目標不明時計入 opaque。"""
    for call in ("(w / 'x').open('a')", "(w / 'x').open('w')", "(w / 'x').open('x')",
                 "(w / 'x').open('r+')", "w.open(mode='w')"):
        _targets, opaque, _strs = bash_write_targets._ast_analyze(_PATH_HEAD + call)
        assert opaque == 1, call


def test_path_open_read_modes_not_write():
    """負向對照：.open()、.open('r')、'rb' 不算寫入。"""
    for call in ("(w / 'x').open()", "(w / 'x').open('r')", "w.open('rb')"):
        _targets, opaque, _strs = bash_write_targets._ast_analyze(_PATH_HEAD + call)
        assert opaque == 0, call


def test_non_path_receiver_open_not_write():
    """file.open 等非路徑接收者不判。"""
    _t, opaque, _s = bash_write_targets._ast_analyze("import sys\nf = sys.stdin\nf.open('a')")
    assert opaque == 0


def test_ticket_md_write_yields_nonempty_targets(tmp_path):
    """正向對照（E2）：已知寫入 ticket md 的命令必須抽出目標。"""
    (tmp_path / ".git").mkdir()
    cmd = ("python3 -c \"open('docs/work-logs/v3/v3.6/v3.6.0/tickets/x.md','w')\"")
    targets = list(bash_write_targets.iter_checkout_write_targets(cmd, str(tmp_path)))
    rels = [rel for _raw, rel, _why in targets if rel]
    assert "docs/work-logs/v3/v3.6/v3.6.0/tickets/x.md" in rels
