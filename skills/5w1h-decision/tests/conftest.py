"""pytest conftest: 讓測試能 import 同 skill 目錄下的 scripts/generate_token.py。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
