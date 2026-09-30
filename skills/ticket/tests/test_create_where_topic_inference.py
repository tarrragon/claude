"""ticket create 給 --where 而未給主題旗標時，S2 主題推導須接受清單形態的 where_files。

回歸來源：--where 改為 action="append" 後，args.where_files 由字串變為字串清單；
topic_inference.infer_topic_from_files 仍對其呼叫 .split(",")，未給
--topic / --new-topic / --no-topic 時 create 以 AttributeError 崩潰。

E1 對照：同一批路徑以清單與逗號字串兩種形態輸入，推導結果須相同。
端到端案例沿用 test_create_repeated_list_args 的慣例：經 register 建 parser，
從真實 argv 解析，才能取得 append 產生的清單形態（手組 Namespace 給字串會繞過回歸點）。
"""

import argparse
import io
from contextlib import redirect_stderr, redirect_stdout

from ticket_system.commands import create as create_cmd
from ticket_system.commands.create import register
from ticket_system.lib import topic_inference as ti
from ticket_system.lib.topic_assignments import list_assignments

CLUSTER_PATH = ".claude/hooks/sample-guard-hook.py"
OTHER_PATH = "docs/spec/unrelated.md"


class TestInferTopicFromFilesAcceptsListAndString:
    def _stub_clusters(self, monkeypatch):
        monkeypatch.setattr(ti, "build_topic_file_clusters", lambda: {"叢集主題": {CLUSTER_PATH}})

    def test_list_and_comma_string_infer_same_topic(self, monkeypatch):
        self._stub_clusters(monkeypatch)
        from_list = ti.infer_topic_from_files([OTHER_PATH, CLUSTER_PATH])
        from_string = ti.infer_topic_from_files(f"{OTHER_PATH},{CLUSTER_PATH}")
        assert from_list == from_string
        assert from_list[0] == "叢集主題"

    def test_list_with_comma_chunks_equals_flat_string(self, monkeypatch):
        self._stub_clusters(monkeypatch)
        from_list = ti.infer_topic_from_files([f"{OTHER_PATH}, {CLUSTER_PATH}"])
        from_string = ti.infer_topic_from_files(f"{OTHER_PATH},{CLUSTER_PATH}")
        assert from_list == from_string

    def test_empty_list_returns_none(self, monkeypatch):
        self._stub_clusters(monkeypatch)
        assert ti.infer_topic_from_files([]) == (None, None)


def _parse_create(argv):
    root = argparse.ArgumentParser()
    register(root.add_subparsers(dest="command"))
    return root.parse_args([
        "create",
        "--version", "1.0.1",
        "--wave", "1",
        "--action", "實作",
        "--type", "IMP",
        "--who", "待派發",
        "--when", "立即",
        "--why", "驗證 --where 清單形態的主題推導",
        "--how-strategy", "驗證主題推導",
        "--acceptance", "測試通過",
        "--decision-tree-entry", "Ticket",
        "--decision-tree-decision", "直接派發",
        "--decision-tree-rationale", "測試情境",
        # where 全在 .claude/ 下會觸發可攜問題分流硬閘門；帶查重結論放行。
        "--dedup-checked", "none",
        *argv,
    ])


def _capture(args):
    out_buf, err_buf = io.StringIO(), io.StringIO()
    try:
        with redirect_stdout(out_buf), redirect_stderr(err_buf):
            exit_code = create_cmd.execute(args)
    except SystemExit as exc:
        exit_code = exc.code
    return out_buf.getvalue(), err_buf.getvalue(), exit_code


class TestCreateRepeatedWhereWithoutTopicFlag:
    def test_repeated_where_without_topic_flag_creates_and_infers(self, seeded_repo_root):
        seed = _parse_create(["--target", "種子票", "--where", CLUSTER_PATH, "--new-topic", "叢集主題"])
        _, _, seed_rc = _capture(seed)
        assert seed_rc == 0

        args = _parse_create(["--target", "重複 where 推導", "--where", OTHER_PATH, "--where", CLUSTER_PATH])
        assert isinstance(args.where_files, list)
        assert args.topic is None and args.new_topic is None and not args.no_topic

        out, err, exit_code = _capture(args)
        assert exit_code == 0, err
        assert list_assignments()["1.0.1-W1-002"] == "叢集主題"
        assert "S2" in out
