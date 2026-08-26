"""schema export 子指令測試：JSON 合法性 + 雙向一致性。

tracking_schema.py（GRAPH_NODE_TYPES / GRAPH_EDGE_TYPES）是唯一 SSOT。本測試
分兩組：

- TestBuildSchemaDictWellFormed / TestExecuteExportJsonFlag / TestExecuteRouting：
  測產生器 build_schema_dict() 本身的正確性（即時從 .py 產出）。
- TestBidirectionalConsistency*：測「磁碟上已產生的 tracking_schema.json」是
  否相對 SSOT 過期，此為一致性測試唯一有效的比對兩端——讀已產生的 JSON
  檔（json.load），對照 import 進來的 GRAPH_NODE_TYPES / GRAPH_EDGE_TYPES。

  必須讀磁碟檔而非呼叫 build_schema_dict()：後者即時從同一份 .py 產出，
  拿它跟 .py 比對兩端同源，任何 .py 修改都會同步反映在兩側，恆等式恆成
  立，無法偵測「.py 已改但 JSON 忘記重新執行 `doc schema export`」這個
  ticket 驗收條件明訂要抓的情境（此為初版實作的失效根因，已用「往 .py
  注入 MUTANT 型別、不動 JSON」的突變測試驗證修正後版本能正確紅燈）。

  - test_json_missing_*: JSON 缺少 .py 有的項目（方向一：刪除/遺漏偵測）
  - test_json_extra_*: JSON 多出 .py 沒有的項目（方向二：新增未重產偵測；
    .py 新增型別但忘記重產 JSON 時，磁碟上的 JSON 是 .py 的真子集，若只測
    「JSON 缺少」方向這裡會漏測，而這正是消費端渲染不完整的成因，見 ticket
    0.2.1-W3-1113 Context Bundle 陷阱二）
"""

import argparse
import json
from pathlib import Path

import pytest

from doc_system.commands.schema import (
    ID_PATTERN_DIALECT,
    build_schema_dict,
    execute,
    execute_export,
)
from doc_system.core.tracking_schema import GRAPH_EDGE_TYPES, GRAPH_NODE_TYPES

# 磁碟上已產生的產物，雙向一致性測試的比對端點之一（另一端是 import 進來
# 的 GRAPH_NODE_TYPES / GRAPH_EDGE_TYPES）。路徑與 commands/schema.py
# execute_export() 的輸出路徑一致。
TRACKING_SCHEMA_JSON_PATH = (
    Path(__file__).resolve().parents[1] / "doc_system" / "core" / "tracking_schema.json"
)


def _load_schema_json_from_disk() -> dict:
    """讀磁碟上實際產生的 tracking_schema.json（非即時產生）。"""
    with open(TRACKING_SCHEMA_JSON_PATH, encoding="utf-8") as f:
        return json.load(f)


class TestBuildSchemaDictWellFormed:
    """build_schema_dict() 產出本身合法且可序列化為 JSON。"""

    def test_returns_dict_json_serializable(self):
        schema_dict = build_schema_dict()
        # 不拋例外即代表可序列化；同時確認非空字串。
        rendered = json.dumps(schema_dict, ensure_ascii=False)
        assert rendered

    def test_has_top_level_keys(self):
        schema_dict = build_schema_dict()
        assert {
            "schema_generated_at_framework_version",
            "id_pattern_dialect",
            "notice",
            "node_types",
            "edge_types",
        } <= schema_dict.keys()

    def test_id_pattern_dialect_is_python_re(self):
        """陷阱三：id_pattern 為 Python re 語法，JSON 須標明方言來源。"""
        schema_dict = build_schema_dict()
        assert schema_dict["id_pattern_dialect"] == ID_PATTERN_DIALECT
        assert schema_dict["id_pattern_dialect"] == "python-re"

    def test_framework_version_key_is_not_literally_framework_version(self):
        """陷阱一：鍵名不可用會被誤讀為「當前框架版本」的 framework_version。"""
        schema_dict = build_schema_dict()
        assert "framework_version" not in schema_dict
        assert "schema_generated_at_framework_version" in schema_dict


class TestBidirectionalConsistencyNodeTypes:
    """節點型別表雙向一致性：磁碟上的 JSON 產物 vs import 進來的 SSOT。"""

    def test_json_missing_node_types_from_py(self):
        """方向一：SSOT 有的節點型別，磁碟上的 JSON 不可缺漏（刪除偵測）。"""
        disk_schema = _load_schema_json_from_disk()
        json_node_names = set(disk_schema["node_types"].keys())
        py_node_names = set(GRAPH_NODE_TYPES.keys())

        missing_in_json = py_node_names - json_node_names
        assert missing_in_json == set(), (
            f"tracking_schema.py 有但 tracking_schema.json 缺少的節點型別: {missing_in_json}"
        )

    def test_json_extra_node_types_not_in_py(self):
        """方向二：磁碟上的 JSON 不可多出 SSOT 沒有的節點型別（新增未重產偵測）。

        單向測試（僅測方向一）無法偵測「.py 新增型別但忘記重新執行
        `doc schema export`」——此情況下磁碟上的 JSON 是 .py 的真子集，
        方向一恆綠燈。此方向反過來測，確保新增型別也能被抓到。
        """
        disk_schema = _load_schema_json_from_disk()
        json_node_names = set(disk_schema["node_types"].keys())
        py_node_names = set(GRAPH_NODE_TYPES.keys())

        extra_in_json = json_node_names - py_node_names
        assert extra_in_json == set(), (
            f"tracking_schema.json 有但 tracking_schema.py 沒有的節點型別: {extra_in_json}"
        )

    def test_node_type_fields_match_ssot_exactly(self):
        """磁碟上每個節點型別的欄位值須與 SSOT 逐項一致（全欄位帶出，不挑選）。"""
        disk_schema = _load_schema_json_from_disk()
        for name, fields in GRAPH_NODE_TYPES.items():
            assert disk_schema["node_types"][name] == dict(fields), (
                f"節點型別 {name} 的 tracking_schema.json 欄位與 SSOT 不一致"
            )


class TestBidirectionalConsistencyEdgeTypes:
    """語意邊表雙向一致性：磁碟上的 JSON 產物 vs import 進來的 SSOT。"""

    def test_json_missing_edge_types_from_py(self):
        """方向一：SSOT 有的邊型別，磁碟上的 JSON 不可缺漏（刪除偵測）。"""
        disk_schema = _load_schema_json_from_disk()
        json_edge_names = set(disk_schema["edge_types"].keys())
        py_edge_names = set(GRAPH_EDGE_TYPES.keys())

        missing_in_json = py_edge_names - json_edge_names
        assert missing_in_json == set(), (
            f"tracking_schema.py 有但 tracking_schema.json 缺少的邊型別: {missing_in_json}"
        )

    def test_json_extra_edge_types_not_in_py(self):
        """方向二：磁碟上的 JSON 不可多出 SSOT 沒有的邊型別（新增未重產偵測）。"""
        disk_schema = _load_schema_json_from_disk()
        json_edge_names = set(disk_schema["edge_types"].keys())
        py_edge_names = set(GRAPH_EDGE_TYPES.keys())

        extra_in_json = json_edge_names - py_edge_names
        assert extra_in_json == set(), (
            f"tracking_schema.json 有但 tracking_schema.py 沒有的邊型別: {extra_in_json}"
        )

    def test_edge_type_fields_match_ssot_exactly(self):
        """磁碟上每個邊型別的欄位值須與 SSOT 逐項一致（全欄位帶出，不挑選）。"""
        disk_schema = _load_schema_json_from_disk()
        for name, fields in GRAPH_EDGE_TYPES.items():
            assert disk_schema["edge_types"][name] == dict(fields), (
                f"邊型別 {name} 的 tracking_schema.json 欄位與 SSOT 不一致"
            )


class TestExecuteExportJsonFlag:
    """execute_export() 的 --json 行為：印出 stdout 不寫檔。"""

    def test_json_flag_prints_valid_json(self, capsys):
        args = argparse.Namespace(json=True)
        execute_export(args)
        captured = capsys.readouterr()
        parsed = json.loads(captured.out)
        assert "node_types" in parsed
        assert "edge_types" in parsed


class TestExecuteRouting:
    """execute() 子命令路由。"""

    def test_execute_routes_to_export(self, capsys):
        args = argparse.Namespace(schema_command="export", json=True)
        execute(args)
        captured = capsys.readouterr()
        parsed = json.loads(captured.out)
        assert "node_types" in parsed

    def test_execute_without_subcommand_prints_help(self, capsys):
        args = argparse.Namespace(schema_command=None)
        execute(args)
        captured = capsys.readouterr()
        assert "export" in captured.out
