"""逐測試還原行程級狀態（cwd 與 os.environ 全量快照）。

各套件的 conftest 以 `from process_state_restore import process_state_guard`
引用（autouse fixture 隨 import 生效）。

快照取在每個測試開始時，因此 session 級設定（CLAUDE_PROJECT_DIR、session id
替換、洩漏哨兵）在測試開始前已就位，自然被保留；只還原測試期間造成的變動。
本 fixture 無依賴，先於其他 fixture 建立、後於其拆除，與 monkeypatch 的 undo 相容。
"""

import os

import pytest


def restore_process_state(cwd: str, environ: dict) -> None:
    """將 cwd 與 os.environ 還原為快照內容（僅在有差異時動作）。"""
    if os.environ != environ:
        os.environ.clear()
        os.environ.update(environ)
    try:
        if os.getcwd() != cwd:
            os.chdir(cwd)
    except OSError:
        # cwd 已被刪除（getcwd 失敗）時直接切回快照目錄
        os.chdir(cwd)


@pytest.fixture(autouse=True)
def process_state_guard():
    cwd = os.getcwd()
    environ = dict(os.environ)
    yield
    restore_process_state(cwd, environ)
