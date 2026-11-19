"""pytest conftest: 讓測試能 import 同 skill 目錄下的 scan_links.py。"""

import sys
from pathlib import Path

# scan_links.py 位於 tests/ 的上一層（skill 根目錄）
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))
from process_state_restore import process_state_guard  # noqa: E402,F401  逐測試還原 cwd/environ
