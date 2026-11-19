"""票庫 file_lock sentinel 的 .gitignore 必要項推導（hook 與 project-init onboard 共用）.

必要項 = `{票庫}/**/*.md.lock`。票庫根目錄取自 ticket skill 的 constants.py
（WORK_LOGS_DIR），讀取失敗退回框架預設。本模組只依標準函式庫，
使 onboard 能以檔案路徑載入受檢專案的副本。
"""

import importlib.util
from pathlib import Path

# 與 ticket_system/constants.py 的 WORK_LOGS_DIR 預設一致；僅在無法讀取 constants 時作 fail-open 退路
DEFAULT_TICKET_ROOT_DIR = "docs/work-logs"
TICKET_CONSTANTS_RELATIVE = ".claude/skills/ticket/ticket_system/constants.py"


def resolve_ticket_root_dir(project_root: Path, logger) -> str:
    """由 ticket skill 的 constants.py（WORK_LOGS_DIR）推導票庫根目錄。

    以檔案路徑載入 constants.py（該模組無 yaml 依賴）。任何失敗退回框架預設並寫日誌（fail-open）。
    """
    const_path = project_root / TICKET_CONSTANTS_RELATIVE
    try:
        spec = importlib.util.spec_from_file_location("_ticket_constants_probe", const_path)
        if spec is None or spec.loader is None:
            raise ImportError("無法建立 spec")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        value = str(getattr(module, "WORK_LOGS_DIR")).strip().strip("/")
        if not value:
            raise ValueError("WORK_LOGS_DIR 為空")
        logger.info("gitignore-check: 票庫根目錄取自 constants: %s", value)
        return value
    except Exception as e:  # noqa: BLE001 — fail-open：退回預設並寫日誌，不阻塞呼叫端
        logger.info(
            "gitignore-check: 讀取票庫設定失敗，退回預設 %s: %s",
            DEFAULT_TICKET_ROOT_DIR,
            e,
        )
        return DEFAULT_TICKET_ROOT_DIR


def ticket_lock_required_entry(root_dir: str) -> str:
    """票庫 lock 必要項（含票庫在 .claude/ 下的情形：必要規則清單沒有 `.claude/**/*.lock`）."""
    return f"{root_dir}/**/*.md.lock"


def ticket_lock_probe_path(root_dir: str) -> str:
    """git check-ignore 用的代表路徑（pattern 比對不需實際存在）."""
    return f"{root_dir}/x/y.md.lock"
