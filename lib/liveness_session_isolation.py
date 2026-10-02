"""測試 session 的 liveness 隔離：專屬 session id 與洩漏哨兵。

Why：mark_hook_entry 以 CLAUDE_CODE_SESSION_ID 決定 _liveness 索引檔名；測試沿用
呼叫者的 session id 時，測試特徵記錄會併入真實 session 的索引檔，已失效的 hook
被誤判為存活。測試 session 改用 pytest- 前綴 id，使任何漏網寫入都落在可辨識的
獨立檔，再由哨兵在 session 結束時 fail-closed。

哨兵只判斷 pytest- 前綴檔存不存在，不比對整個目錄：並行的真實 session 也會寫入
同一目錄，整目錄比對會誤判。
"""

import os
import sys
import uuid
from pathlib import Path
from typing import List

ENV_SESSION_ID = "CLAUDE_CODE_SESSION_ID"
SESSION_ID_PREFIX = "pytest-"
LIVENESS_RELATIVE = Path(".claude") / "hook-logs" / "_liveness"


def new_test_session_id() -> str:
    return "{}{}-{}".format(SESSION_ID_PREFIX, os.getpid(), uuid.uuid4().hex[:8])


def find_leaked_liveness_files(real_root: Path) -> List[Path]:
    """回傳真實根 _liveness 下的 pytest- 前綴檔；目錄不存在視為無洩漏。"""
    liveness_dir = real_root / LIVENESS_RELATIVE
    if not liveness_dir.is_dir():
        return []
    return sorted(liveness_dir.glob(SESSION_ID_PREFIX + "*"))


def apply_leak_sentinel(session, real_root: Path) -> List[Path]:
    """偵測到洩漏時令套件失敗（exitstatus=1）並寫 stderr，回傳洩漏檔清單。"""
    leaked = find_leaked_liveness_files(real_root)
    if leaked:
        sys.stderr.write(
            "[liveness-leak-sentinel] 真實 _liveness 出現測試 session 檔，"
            "有測試繞過重導寫入真實 hook-logs: {}\n".format([p.name for p in leaked])
        )
        session.exitstatus = 1
    return leaked
