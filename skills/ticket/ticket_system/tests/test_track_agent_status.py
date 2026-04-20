"""track agent-status 命令測試（W10-061 項目 4）"""
import argparse
import io
import sys

from ticket_system.commands.track_agent_status import (
    execute_agent_status,
    register_agent_status,
)


def _run(agent_id=None) -> str:
    args = argparse.Namespace(agent_id=agent_id)
    buf = io.StringIO()
    saved = sys.stdout
    sys.stdout = buf
    try:
        rc = execute_agent_status(args)
    finally:
        sys.stdout = saved
    assert rc == 0
    return buf.getvalue()


def test_guidance_prints_when_agent_id_given():
    out = _run(agent_id="abc123")
    assert "abc123" in out
    assert "ToolSearch" in out
    assert "<status>" in out


def test_guidance_prints_placeholder_when_no_agent_id():
    out = _run(agent_id=None)
    assert "<agentId>" in out
    assert "PC-050" in out
    assert "PC-070" in out


def test_guidance_warns_about_body_pollution():
    out = _run(agent_id="x")
    assert "<output>" in out
    assert "模式 D" in out


def test_guidance_mentions_time_threshold():
    out = _run(agent_id="x")
    assert "2 分鐘" in out
    assert "模式 E" in out


def test_register_agent_status_registers_subcommand():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="operation")
    register_agent_status(subparsers)
    ns = parser.parse_args(["agent-status", "some-id"])
    assert ns.operation == "agent-status"
    assert ns.agent_id == "some-id"
