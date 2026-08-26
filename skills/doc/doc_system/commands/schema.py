"""schema 子命令 — 從 tracking_schema.py 產生機器可讀的圖譜型別表 JSON。

tracking_schema.py（GRAPH_NODE_TYPES / GRAPH_EDGE_TYPES）是唯一 SSOT，本模組
只負責把該 SSOT 轉譯為 JSON 供任何語言消費（如外部 app 讀取他人機器上的
.claude/ 框架版本）。本模組**不裁決** schema 內容，發現內容需修改時走 ticket
spawn-request 流程，不在此處自行改值（tracking_schema.py 檔頭同精神）。

version 語意見 `_read_framework_version_at_generation()` docstring：JSON 內
`schema_generated_at_framework_version` 承載的是「本次產生時讀到的框架版
本」，非「消費端讀取當下的框架版本」——兩者在 sync-push 前後有時序落差，
鍵名刻意避免使用容易被誤讀為後者的 `framework_version`。
"""

import argparse
import json
from pathlib import Path

from doc_system.core.file_locator import FileLocator
from doc_system.core.tracking_schema import GRAPH_EDGE_TYPES, GRAPH_NODE_TYPES

# id_pattern 欄位的正則語法方言。這些字串是 Python `re` 語法，在 Dart
# `RegExp` 下多數情況語意相同，但具名群組 / lookbehind / `\p{}` 等處語法
# 並非全等。此鍵給未來新增 pattern 的人看：目前安全不代表加了 lookbehind
# 之後仍安全，屆時失效的是消費端而非本專案，不會有紅燈（見 Context Bundle
# 陷阱三）。
ID_PATTERN_DIALECT = "python-re"

# 本產物不可被直接編輯的提醒鍵值，呼應 tracking_schema.py 檔頭「Markdown
# 表格內容不可再被引用為權威來源」的精神延伸。
SCHEMA_EDIT_NOTICE = (
    "本檔為 tracking_schema.py 的衍生產物，唯一 SSOT 為該 .py 檔。"
    "禁止直接編輯本 JSON，修改型別表請改 tracking_schema.py 後重新執行"
    "`doc schema export` 產生。"
)


def _read_framework_version_at_generation(project_root: Path) -> str:
    """讀取產生當下的 .claude/VERSION 值。

    此值不等於「消費端讀取本 JSON 當下的框架版本」——.claude/VERSION 的
    bump 時機在 sync-push，晚於本檔的產生與 commit（見 Context Bundle
    陷阱一：改 schema → 重產 JSON → commit → sync-push 才 bump VERSION）。
    因此本函式讀到的值恆為「上一次 push 後」的版本，語意是「schema 最後
    一次產生時的框架版本」，非當前框架版本。消費端若要當前框架版本，應
    直接讀取隨框架同步的 .claude/VERSION，不透過本 JSON。
    """
    version_file = project_root / ".claude" / "VERSION"
    try:
        return version_file.read_text(encoding="utf-8").strip()
    except OSError:
        return "unknown"


def build_schema_dict(project_root: Path | None = None) -> dict:
    """從 GRAPH_NODE_TYPES / GRAPH_EDGE_TYPES 建構可序列化為 JSON 的 dict。

    全欄位帶出，不逐欄挑選——逐欄挑選會製造「哪些欄位該進 JSON」這個需
    持續維護的第二判斷，其錯誤形態是消費端缺欄位且無紅燈（見 Context
    Bundle「消費端已確認的欄位用途」表）。
    """
    root = project_root or Path(FileLocator.get_project_root())

    return {
        "schema_generated_at_framework_version": _read_framework_version_at_generation(root),
        "id_pattern_dialect": ID_PATTERN_DIALECT,
        "notice": SCHEMA_EDIT_NOTICE,
        "node_types": {
            name: dict(fields) for name, fields in GRAPH_NODE_TYPES.items()
        },
        "edge_types": {
            name: dict(fields) for name, fields in GRAPH_EDGE_TYPES.items()
        },
    }


def execute(args: argparse.Namespace) -> None:
    """schema 子命令群組路由：export。"""
    schema_command = getattr(args, "schema_command", None)
    if schema_command == "export":
        execute_export(args)
        return
    print("doc schema export [--json]   從 tracking_schema.py 產生圖譜型別表 JSON")


def execute_export(args: argparse.Namespace) -> None:
    """產生圖譜型別表 JSON。

    --json：印出 JSON 至 stdout（供管線消費/測試），不寫檔。
    省略 --json：寫入 doc_system/core/tracking_schema.json 並印出路徑。
    """
    project_root = Path(FileLocator.get_project_root())
    schema_dict = build_schema_dict(project_root)
    rendered = json.dumps(schema_dict, ensure_ascii=False, indent=2, sort_keys=True)

    if getattr(args, "json", False):
        print(rendered)
        return

    output_path = (
        project_root
        / ".claude"
        / "skills"
        / "doc"
        / "doc_system"
        / "core"
        / "tracking_schema.json"
    )
    output_path.write_text(rendered + "\n", encoding="utf-8")
    print(f"已產生: {output_path}")
