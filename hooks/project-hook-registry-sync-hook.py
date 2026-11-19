#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml"]
# ///
"""
專案自有 hook 清冊同步（SessionStart）

依 `.claude/project-integration/hook-registry.yaml` 重建
`.claude/settings.local.json` 的 `hooks` 區段。格式見
`.claude/references/project-hook-registry-format.md`。

清冊外的 local hook 條目只移除可判定為錯誤的兩類，其餘保留並示警：
  1. 幽靈：command 指向的 `.claude/` 下檔案不存在
  2. 框架重複：同一腳本已由 settings.json 或 hook-dispatch-registry 註冊

輸出：有移除、示警或錯誤時，stderr 與 additionalContext（pm_only）都列出。
失敗語意：清冊格式錯誤或寫檔失敗時不寫入 settings.local.json，回報錯誤；
SessionStart 不阻擋。
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lib.hook_base import get_code_root  # noqa: E402
from lib.hook_logging import setup_hook_logging, run_hook_safely  # noqa: E402
from lib.hook_io import read_json_from_stdin, emit_hook_output  # noqa: E402
# 產生器已搬到 lib 供 sync-pull 共用；保留同名匯入，測試經 hook.<名稱> 存取
from lib.project_hook_registry import (  # noqa: E402,F401
    HOOK_NAME,
    LOCAL_SETTINGS_RELATIVE,
    MANIFEST_RELATIVE,
    ManifestError,
    build_command,
    parse_manifest,
    script_identity,
    framework_script_identities,
    iter_hook_entries,
    classify_local_entry,
    rebuild_hooks,
    _append,
    format_report,
    load_json,
    _root_digest,
    state_path,
    load_previously_generated,
    save_generated,
    sync,
)



def main() -> int:
    logger = setup_hook_logging(HOOK_NAME)
    input_data = read_json_from_stdin(logger)
    report = sync(get_code_root(), logger)  # CR：清冊、settings.json 讀取與 settings.local.json 寫入
    if report:
        logger.warning(report)
        sys.stderr.write(report + "\n")
        emit_hook_output("SessionStart", additional_context=report, audience="pm_only", input_data=input_data)
    return 0


if __name__ == "__main__":
    sys.exit(run_hook_safely(main, HOOK_NAME))
