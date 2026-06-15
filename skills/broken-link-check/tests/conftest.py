"""pytest conftest: 讓測試能 import 同 skill 目錄下的 scan_links.py。"""

import sys
from pathlib import Path

# scan_links.py 位於 tests/ 的上一層（skill 根目錄）
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
