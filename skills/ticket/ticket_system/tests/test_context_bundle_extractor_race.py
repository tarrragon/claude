"""W14-043 — extract_and_write_context_bundle race regression test.

對應 ticket 0.18.0-W14-043（W14-042.1.4 caller 審計識別為次高風險）。

設計（沿用 test_save_ticket_race.py v2 模式）：
-----------------------
真正 race 發生在 `extract_and_write_context_bundle` 的 load → modify → save
三步驟序列（context_bundle_extractor.py L851-880）。本測試模擬該層級 race，
預期有 file_lock 保護後 lost_rate == 0%。

並發場景：多個 process 同時對同一 target ticket 呼叫
extract_and_write_context_bundle（例如多個 ticket 同時被 claim 觸發 auto
context bundle 提取，剛好都指向同一個 sibling target）。
"""

from __future__ import annotations

import multiprocessing as mp
from pathlib import Path

import pytest

from ticket_system.lib import context_bundle_extractor as cbe
from ticket_system.lib import parser
from ticket_system.lib.parser import parse_frontmatter


# ============================================================
# Fixtures
# ============================================================

@pytest.fixture(scope="module", autouse=True)
def _force_fork_mode():
    """macOS Python 3.13 預設 spawn，顯式切回 fork 以共享 monkeypatch state。"""
    try:
        mp.set_start_method("fork", force=True)
    except RuntimeError:
        pass
    current = mp.get_start_method()
    assert current == "fork", (
        f"fork mode required for race tests; current start method = {current!r}."
    )


@pytest.fixture
def tmp_ticket_dir(tmp_path: Path) -> Path:
    d = tmp_path / "tickets"
    d.mkdir()
    return d


def _write_target_ticket(path: Path, tid: str, source_id: str) -> None:
    """建立 target ticket，frontmatter 含 source_ticket，body 含空 Context Bundle section。"""
    content = (
        "---\n"
        f"id: {tid}\n"
        "title: race target\n"
        "status: pending\n"
        f"source_ticket: {source_id}\n"
        "---\n"
        "\n"
        "# Body\n"
        "\n"
    )
    path.write_text(content, encoding="utf-8")


def _write_source_ticket(path: Path, tid: str) -> None:
    """建立 source ticket，提供可被 extract 的 what/why。"""
    content = (
        "---\n"
        f"id: {tid}\n"
        "title: race source\n"
        "status: completed\n"
        f"what: source-what-content-{tid}\n"
        f"why: source-why-content-{tid}\n"
        "---\n"
        "\n"
        "body\n"
    )
    path.write_text(content, encoding="utf-8")


@pytest.fixture
def race_tickets(tmp_ticket_dir: Path, monkeypatch):
    """建立 target + source ticket，並 patch get_ticket_path / load_ticket。"""
    version = "0.0.0"
    target_id = "0.0.0-W0-TARGET"
    source_id = "0.0.0-W0-SRC"

    target_path = tmp_ticket_dir / f"{target_id}.md"
    source_path = tmp_ticket_dir / f"{source_id}.md"
    _write_target_ticket(target_path, target_id, source_id)
    _write_source_ticket(source_path, source_id)

    def _fake_get_ticket_path(v: str, tid: str) -> Path:
        return tmp_ticket_dir / f"{tid}.md"

    def _fake_load_ticket(v: str, tid: str):
        path = tmp_ticket_dir / f"{tid}.md"
        if not path.exists():
            return None
        content = path.read_text(encoding="utf-8")
        try:
            fm, body = parse_frontmatter(content)
        except Exception:
            return None
        if not fm:
            return None
        fm["_body"] = body
        fm["_path"] = str(path)
        return fm

    # Patch 在 context_bundle_extractor 模組命名空間
    monkeypatch.setattr(cbe, "get_ticket_path", _fake_get_ticket_path)
    monkeypatch.setattr(cbe, "load_ticket", _fake_load_ticket)

    return version, target_id, target_path


# ============================================================
# Workers
# ============================================================

def _worker_extract(args):
    """並發呼叫 extract_and_write_context_bundle。"""
    version, target_id = args
    try:
        result, _notes = cbe.extract_and_write_context_bundle(version, target_id)
        return True
    except Exception:
        return False


# ============================================================
# Tests
# ============================================================

class TestExtractAndWriteContextBundleRace:
    """N 並行 extract_and_write_context_bundle 必須產出單一一致檔案內容。

    file_lock 保護下：所有 writer 完成後，target ticket 檔案必須：
    - 仍為合法 frontmatter + body 格式（parse_frontmatter 不拋例外）
    - Context Bundle section 內含 auto-extracted block（單一 block，無 corruption）
    """

    def test_concurrent_extract_no_corruption(self, race_tickets):
        version, target_id, target_path = race_tickets
        N = 20
        N_ROUNDS = 3

        for round_idx in range(N_ROUNDS):
            # 重置 target body（保留 source_ticket 連結）
            _write_target_ticket(
                target_path, target_id, "0.0.0-W0-SRC"
            )

            try:
                parser._ticket_cache.clear()
            except Exception:
                pass

            args = [(version, target_id) for _ in range(N)]
            with mp.Pool(N) as pool:
                results = pool.map(_worker_extract, args)

            # 至少一個 writer 必須成功（無 lock 時可能全失敗於 parse 中段 corrupted）
            assert any(results), (
                f"round {round_idx}: all {N} workers failed (suggests file "
                f"corruption made every retry unparsable)"
            )

            # 最終檔案必須仍可正常解析
            content = target_path.read_text(encoding="utf-8")
            try:
                fm, body = parse_frontmatter(content)
            except Exception as exc:
                pytest.fail(
                    f"round {round_idx}: final ticket file unparsable "
                    f"(race corruption): {exc}\n"
                    f"---file content---\n{content}\n---end---"
                )
            assert fm and fm.get("id") == target_id, (
                f"round {round_idx}: frontmatter id missing or wrong: {fm}"
            )

            # Body 中應僅有單一 auto-extracted block（不應有重複 marker 累積）
            marker_count = body.count("<!-- auto-extracted: v1")
            assert marker_count == 1, (
                f"round {round_idx}: expected exactly 1 auto-extracted "
                f"block, got {marker_count}\n"
                f"---body---\n{body}\n---end---"
            )
