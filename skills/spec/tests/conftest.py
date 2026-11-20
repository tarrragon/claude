"""pytest conftest: 逐測試還原 cwd 與 os.environ。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))
from process_state_restore import process_state_guard  # noqa: E402,F401
