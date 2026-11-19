"""sync push 前的框架核心套件 smoke test。"""

import importlib
import importlib.util
import pkgutil
import sys
from pathlib import Path

from lib.sync_cli_io import print_color


# staging 樹（已 strip .claude/ 前綴）內框架核心套件的相對路徑。
# 此套件被全 consumer 直接 import 執行，是不完整重構留下的 import 殘留零審查傳染
# 到全部 consumer 這類事故（見 PC-V1-009）風險最高的單點，故作為 push 前
# smoke test 的目標。
FRAMEWORK_CORE_PACKAGE_DIR = Path("skills") / "ticket" / "ticket_system"
FRAMEWORK_CORE_PACKAGE_NAME = "ticket_system"

# push 執行環境（uv run --script，零宣告依賴）必然缺席的第三方庫。
# 這些模組缺失屬環境限制，非框架碼缺陷，smoke test 不得據此誤報 abort
# （acceptance：正常 push 零誤報）。框架內部模組（FRAMEWORK_CORE_PACKAGE_NAME.*）
# 的缺失則屬真實 import 殘留缺陷，必須攔截。
SMOKE_TEST_TOLERATED_MISSING = frozenset({
    "filelock",
    "yaml",
    "pyyaml",
    "pytest",
})


def _is_tolerated_import_error(exc: ModuleNotFoundError) -> bool:
    """判定 ModuleNotFoundError 是否屬「環境限制可容忍」而非框架碼缺陷。

    缺席的若是已知第三方庫（push 零依賴環境本就無）→ 容忍；
    缺席的若是框架核心套件自身的子模組（import 殘留，指向已刪除/改名的內部
    模組）→ 不容忍，視為缺陷。

    參數:
        exc: 捕捉到的 ModuleNotFoundError

    傳回:
        bool: True 表示可容忍（環境限制），False 表示屬框架缺陷
    """
    missing = (exc.name or "").split(".")[0]
    if not missing:
        return False
    # 框架核心套件內部的 import 殘留：絕不容忍（此即目標缺陷類別）
    if missing == FRAMEWORK_CORE_PACKAGE_NAME:
        return False
    return missing in SMOKE_TEST_TOLERATED_MISSING


def run_framework_smoke_test(staging_dir: Path) -> None:
    """push / tag 前對 staging 樹的框架核心套件做 import smoke test（C1 生產閘）。

    呼叫時機：stage_tracked_tree() 取得 git tracked 樹後、git push（含版本 tag）
    任何階段「之前」。red 時 sys.exit(1)，與 check_release_version 並列為 push 前
    fail-fast 防護，紅燈時不得進入 push / tag。

    Why：機械缺陷（import 殘留——殘留對已刪除/改名內部模組的 import）零審查直推會
    瞬時傳染全部 consumer 致下游崩潰（框架核心套件被全 consumer 直接 import 執行）。
    push 前在 staging 樹實際 import 全模組，可零誤報攔下整個缺陷類別。

    Consequence：缺此閘門時，一次不完整重構（漏改某處 import）即可在無人審查下
    push 出損壞框架，下游 pull 後 ticket 工具整體 import 失敗。

    Action：以 pkgutil.walk_packages 走訪 staging 樹核心套件全子模組逐一 import。
      - 框架內部模組缺失（ModuleNotFoundError name 屬核心套件）/ 語法錯誤
        （SyntaxError）/ 其他 import 期例外 → 視為缺陷 → sys.exit(1)。
      - 已知第三方依賴缺失（SMOKE_TEST_TOLERATED_MISSING，push 零依賴環境本就無）
        → 容忍，不算缺陷（零誤報要求）。
    staging 樹無核心套件時（理論上不會發生）安全略過，不 abort。

    隔離：本函式以獨立 sys.path 前綴 import 並在結束後清理已 import 的核心套件
    模組，避免污染 push 腳本自身的 import 狀態（push 腳本另經 sys.path 載入
    lib 的 manifest）。

    參數:
        staging_dir: git archive 解出、已 strip .claude/ 前綴的 staging 樹根目錄
    """
    pkg_dir = staging_dir / FRAMEWORK_CORE_PACKAGE_DIR
    if not (pkg_dir / "__init__.py").is_file():
        # staging 樹未含核心套件：無可檢查項，安全略過（不視為缺陷）
        return

    print_color("push 前框架 import smoke test（C1 生產閘）...")
    search_root = str((staging_dir / FRAMEWORK_CORE_PACKAGE_DIR).parent)
    failures: list[str] = []
    inserted = False
    imported_before = set(sys.modules)
    try:
        if search_root not in sys.path:
            sys.path.insert(0, search_root)
            inserted = True
        importlib.invalidate_caches()

        try:
            pkg = importlib.import_module(FRAMEWORK_CORE_PACKAGE_NAME)
        except ModuleNotFoundError as exc:
            if not _is_tolerated_import_error(exc):
                failures.append(f"{FRAMEWORK_CORE_PACKAGE_NAME}: {exc}")
            pkg = None
        except (ImportError, SyntaxError, Exception) as exc:  # noqa: BLE001
            failures.append(f"{FRAMEWORK_CORE_PACKAGE_NAME}: {exc!r}")
            pkg = None

        if pkg is not None:
            for mod in pkgutil.walk_packages(
                pkg.__path__, prefix=f"{FRAMEWORK_CORE_PACKAGE_NAME}."
            ):
                # 測試模組（tests）import pytest 等非生產依賴，不屬下游執行路徑，跳過
                if ".tests" in mod.name or mod.name.endswith(".tests"):
                    continue
                try:
                    importlib.import_module(mod.name)
                except ModuleNotFoundError as exc:
                    if not _is_tolerated_import_error(exc):
                        failures.append(f"{mod.name}: {exc}")
                except (ImportError, SyntaxError, Exception) as exc:  # noqa: BLE001
                    failures.append(f"{mod.name}: {exc!r}")
    finally:
        # 清理：移除本次 import 進來的核心套件模組與 sys.path 前綴，避免污染
        for name in set(sys.modules) - imported_before:
            if name == FRAMEWORK_CORE_PACKAGE_NAME or name.startswith(
                f"{FRAMEWORK_CORE_PACKAGE_NAME}."
            ):
                sys.modules.pop(name, None)
        if inserted and search_root in sys.path:
            sys.path.remove(search_root)
        importlib.invalidate_caches()

    if failures:
        print_color(
            f"[FAIL] 框架 import smoke test 偵測到 {len(failures)} 個模組無法 import：",
            "red",
        )
        for item in failures:
            print_color(f"   - {item}", "red")
        print_color(
            "push 已中止：staging 樹存在 import 殘留 / 語法錯誤等機械缺陷，"
            "若推出會瞬時傳染全部下游。請先修復後重試。",
            "red",
        )
        sys.exit(1)
    print_color("   smoke test 通過：框架核心套件全模組可 import", "green")
