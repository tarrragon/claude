#!/usr/bin/env python3
"""
dispatch_stats.py — Agent Dispatch Validation 警告統計與標註 CLI

對應 Ticket: 0.18.0-W11-004.1.1
規格權威: ticket Solution「Phase 1 功能規格設計 v2」

用法：
    python3 .claude/hooks/dispatch_stats.py list    [--status ...] [--agent NAME]
                                                    [--since YYYY-MM-DD] [--limit N]
                                                    [--format text|json]
    python3 .claude/hooks/dispatch_stats.py show    <event_id> [--format text|json]
    python3 .claude/hooks/dispatch_stats.py annotate <event_id>
                                                    --label {true_positive|false_positive|unknown}
                                                    [--note TEXT]
    python3 .claude/hooks/dispatch_stats.py annotate --all-unannotated --label unknown
    python3 .claude/hooks/dispatch_stats.py stats   [--groupby agent|keyword|none]
                                                    [--since YYYY-MM-DD]
                                                    [--format text|json|markdown]

Exit codes：
    0  成功（含「尚無事件」與冪等）
    1  其他未預期錯誤（OSError 等）
    2  argparse 錯誤 / event_id 不存在 / label 不合法
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# A. Constants & Path Resolution
# ---------------------------------------------------------------------------

VALID_LABELS = ("true_positive", "false_positive", "unknown")
THRESHOLD_FPR = 0.10

REQUIRED_EVENT_FIELDS = (
    "event_id", "timestamp", "subagent_type",
    "conflicts", "prompt_hash", "prompt_length",
)


_PROJECT_ROOT: Path = Path(__file__).resolve().parents[2]
# 與 agent-dispatch-validation-hook.py 的 _EVENTS_JSONL_PATH 必須一致
_EVENTS_JSONL_PATH: Path = _PROJECT_ROOT / ".claude/hook-logs/agent-dispatch-validation/events/events.jsonl"
_ANNOTATIONS_JSON_PATH: Path = _PROJECT_ROOT / ".claude/hook-logs/agent-dispatch-validation/events/annotations.json"


def _resolve_path(env_var: str, default: Path) -> Path:
    """統一的路徑解析：環境變數優先，否則回傳 default（模組常數，可被測試 monkeypatch）。"""
    env = os.environ.get(env_var)
    return Path(env) if env else default


# ---------------------------------------------------------------------------
# B. Store（I/O 原語）
# ---------------------------------------------------------------------------


def _has_required_fields(obj: Any) -> bool:
    if not isinstance(obj, dict):
        return False
    return all(k in obj for k in REQUIRED_EVENT_FIELDS)


def read_events(path: Optional[Path] = None) -> Tuple[List[Dict[str, Any]], int]:
    """讀 events.jsonl，回傳 (events, malformed_lines)。

    格式錯誤行 skip 並寫 stderr「第 N 行格式錯誤」。
    """
    p = path if path is not None else _resolve_path("DISPATCH_STATS_EVENTS_PATH", _EVENTS_JSONL_PATH)
    if not p.exists():
        return [], 0
    events: List[Dict[str, Any]] = []
    malformed = 0
    try:
        raw_text = p.read_text(encoding="utf-8")
    except OSError:
        return [], 0
    for lineno, raw in enumerate(raw_text.splitlines(), start=1):
        s = raw.strip()
        if not s:
            continue
        try:
            obj = json.loads(s)
        except json.JSONDecodeError:
            print(f"dispatch_stats: 第 {lineno} 行格式錯誤 (malformed JSON, skip)", file=sys.stderr)
            malformed += 1
            continue
        if not _has_required_fields(obj):
            print(f"dispatch_stats: 第 {lineno} 行格式錯誤 (missing required fields, skip)", file=sys.stderr)
            malformed += 1
            continue
        events.append(obj)
    return events, malformed


def read_annotations(path: Optional[Path] = None) -> Dict[str, Dict[str, Any]]:
    p = path if path is not None else _resolve_path("DISPATCH_STATS_ANNOTATIONS_PATH", _ANNOTATIONS_JSON_PATH)
    if not p.exists():
        return {}
    try:
        text = p.read_text(encoding="utf-8").strip()
    except OSError:
        return {}
    if not text:
        return {}
    try:
        obj = json.loads(text)
    except json.JSONDecodeError:
        print("dispatch_stats: annotations.json 格式錯誤，視為空", file=sys.stderr)
        return {}
    if not isinstance(obj, dict):
        return {}
    return obj


def write_annotations(annotations: Dict[str, Dict[str, Any]],
                       path: Optional[Path] = None) -> None:
    """atomic rename 寫入 annotations.json。"""
    p = path if path is not None else _resolve_path("DISPATCH_STATS_ANNOTATIONS_PATH", _ANNOTATIONS_JSON_PATH)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = p.with_name(p.name + ".tmp." + uuid.uuid4().hex[:8])
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(annotations, f, ensure_ascii=False, indent=2)
            f.flush()
            try:
                os.fsync(f.fileno())
            except OSError:
                pass
        os.replace(tmp_path, p)
    except OSError:
        if tmp_path.exists():
            try:
                os.remove(tmp_path)
            except OSError:
                pass
        raise


class EventNotFound(Exception):
    pass


def _now_iso8601_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def annotate_event(event_id: str, label: str, note: str = "") -> bool:
    """寫入/覆寫標註。回傳 True 表示實際覆寫了既有不同標註（可能需 stderr 警告）。

    event_id 不存在 → raise EventNotFound。
    """
    if label not in VALID_LABELS:
        raise ValueError(f"invalid label: {label}")

    events, _ = read_events()
    valid_ids = {e["event_id"] for e in events}
    if event_id not in valid_ids:
        raise EventNotFound(event_id)

    annotations = read_annotations()
    existing = annotations.get(event_id) or {}
    # 冪等早退：label + note 完全相同時不寫入
    if existing.get("label") == label and existing.get("note", "") == note:
        return False
    annotations[event_id] = {
        "label": label,
        "note": note,
        "annotated_at": _now_iso8601_utc(),
    }
    write_annotations(annotations)
    return bool(existing) and existing.get("label") != label


# ---------------------------------------------------------------------------
# C. Compute（純函式）
# ---------------------------------------------------------------------------


def _parse_since(since: Optional[str]) -> Optional[datetime]:
    if not since:
        return None
    try:
        return datetime.strptime(since, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _parse_event_timestamp(ts: str) -> Optional[datetime]:
    if not isinstance(ts, str):
        return None
    try:
        if ts.endswith("Z"):
            return datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        return datetime.fromisoformat(ts)
    except ValueError:
        return None


def _dedupe_first_wins(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen = set()
    out = []
    for e in events:
        eid = e.get("event_id")
        if eid in seen:
            continue
        seen.add(eid)
        out.append(e)
    return out


def filter_events(
    events: List[Dict[str, Any]],
    annotations: Dict[str, Dict[str, Any]],
    status: str = "unannotated",
    agent: Optional[str] = None,
    since: Optional[str] = None,
    limit: Optional[int] = None,
) -> List[Dict[str, Any]]:
    events = _dedupe_first_wins(events)
    since_dt = _parse_since(since)
    filtered = []
    for e in events:
        if agent and e.get("subagent_type") != agent:
            continue
        if since_dt is not None:
            ets = _parse_event_timestamp(e.get("timestamp", ""))
            if ets is None or ets < since_dt:
                continue
        eid = e.get("event_id")
        ann = annotations.get(eid)
        if status == "unannotated":
            if ann is not None:
                continue
        elif status == "annotated":
            if ann is None:
                continue
        elif status == "all":
            pass
        else:
            continue
        filtered.append(e)
    if limit is not None and limit >= 0:
        filtered = filtered[:limit]
    return filtered


def compute_stats(
    events: List[Dict[str, Any]],
    annotations: Dict[str, Dict[str, Any]],
    groupby: str = "none",
    since: Optional[str] = None,
    malformed_lines: int = 0,
) -> Dict[str, Any]:
    events = _dedupe_first_wins(events)
    since_dt = _parse_since(since)
    if since_dt is not None:
        events = [
            e for e in events
            if (_parse_event_timestamp(e.get("timestamp", "")) or datetime.min.replace(tzinfo=timezone.utc)) >= since_dt
        ]

    valid_ids = {e["event_id"] for e in events}
    # 孤兒 annotation 不計
    eff_ann = {k: v for k, v in annotations.items() if k in valid_ids}

    tp = fp = unk = unannotated = 0
    for e in events:
        ann = eff_ann.get(e["event_id"])
        if ann is None:
            unannotated += 1
        else:
            lbl = ann.get("label")
            if lbl == "true_positive":
                tp += 1
            elif lbl == "false_positive":
                fp += 1
            else:
                unk += 1

    if tp + fp == 0:
        fpr: Optional[float] = None
        meets: Optional[bool] = None
    else:
        fpr = fp / (tp + fp)
        meets = fpr <= THRESHOLD_FPR

    result: Dict[str, Any] = {
        "total_events": len(events),
        "annotated": tp + fp + unk,
        "unannotated": unannotated,
        "true_positive": tp,
        "false_positive": fp,
        "unknown": unk,
        "false_positive_rate": fpr,
        "meets_threshold": meets,
        "malformed_lines": malformed_lines,
        "groups": [],
    }

    if groupby == "agent":
        result["groups"] = _group_by(events, eff_ann, _key_agent)
    elif groupby == "keyword":
        result["groups"] = _group_by(events, eff_ann, _key_keyword)

    return result


def _group_summary(
    items: List[Tuple[str, Optional[str]]],
) -> Dict[str, Any]:
    """items: list of (key, label_or_none). 回傳 {tp,fp,unknown,unannotated,total,fpr}。"""
    tp = fp = unk = una = 0
    for _, lbl in items:
        if lbl is None:
            una += 1
        elif lbl == "true_positive":
            tp += 1
        elif lbl == "false_positive":
            fp += 1
        else:
            unk += 1
    total = tp + fp + unk + una
    fpr = (fp / (tp + fp)) if (tp + fp) > 0 else None
    return {
        "true_positive": tp,
        "false_positive": fp,
        "unknown": unk,
        "unannotated": una,
        "total": total,
        "false_positive_rate": fpr,
    }


def _group_by(events, eff_ann, key_fn):
    """通用分組：key_fn(event) 回傳 0..N 個分組 key（字串）。

    - agent 分組：key_fn 回傳 [subagent_type]
    - keyword 分組：key_fn 回傳每個 conflict 的 keyword 清單
    """
    groups: Dict[str, List[Tuple[str, Optional[str]]]] = {}
    for e in events:
        ann = eff_ann.get(e["event_id"])
        lbl = ann.get("label") if ann else None
        for k in key_fn(e):
            groups.setdefault(k, []).append((k, lbl))
    out = []
    for k, items in sorted(groups.items()):
        summary = _group_summary(items)
        summary["key"] = k
        out.append(summary)
    return out


def _key_agent(e: Dict[str, Any]) -> List[str]:
    return [e.get("subagent_type", "")]


def _key_keyword(e: Dict[str, Any]) -> List[str]:
    return [c.get("keyword", "") for c in (e.get("conflicts") or [])]


# ---------------------------------------------------------------------------
# D. Format
# ---------------------------------------------------------------------------


def _fpr_text(fpr: Optional[float]) -> str:
    return "N/A" if fpr is None else f"{fpr:.1%}"


def format_list_text(events: List[Dict[str, Any]], annotations: Dict[str, Dict[str, Any]]) -> str:
    if not events:
        return "尚無事件"
    lines = ["EVENT_ID\tTIME\tAGENT\tCONFLICTS\tANNOTATION"]
    for e in events:
        ann = annotations.get(e["event_id"])
        ann_label = ann["label"] if ann else "(unannotated)"
        lines.append("\t".join([
            str(e.get("event_id", "")),
            str(e.get("timestamp", "")),
            str(e.get("subagent_type", "")),
            str(len(e.get("conflicts", []) or [])),
            ann_label,
        ]))
    return "\n".join(lines)


def format_list_json(events: List[Dict[str, Any]]) -> str:
    return json.dumps(events, ensure_ascii=False, indent=2)


def format_show(event: Dict[str, Any]) -> str:
    """show 的 text 與 json 格式相同（皆為 pretty JSON），合併為單一函式。"""
    return json.dumps(event, ensure_ascii=False, indent=2)


def format_stats_text(stats: Dict[str, Any]) -> str:
    if stats["total_events"] == 0:
        return "尚無事件"
    lines = [
        "=== Agent Dispatch Validation Stats ===",
        f"總事件: {stats['total_events']}",
        f"  已標註: {stats['annotated']}  (TP: {stats['true_positive']}, "
        f"FP: {stats['false_positive']}, Unknown: {stats['unknown']})",
        f"  未標註: {stats['unannotated']}",
        f"誤報率: FP / (TP + FP) = {_fpr_text(stats['false_positive_rate'])}",
        f"目標: <= {THRESHOLD_FPR:.0%}",
        f"狀態: {'達標' if stats['meets_threshold'] is True else ('未達標' if stats['meets_threshold'] is False else 'N/A')}",
        f"malformed_lines: {stats['malformed_lines']}",
    ]
    if stats.get("groups"):
        lines.append("")
        lines.append("分組統計：")
        for g in stats["groups"]:
            lines.append(
                f"  {g['key']}: TP={g['true_positive']} FP={g['false_positive']} "
                f"Unknown={g['unknown']} 誤報率={_fpr_text(g['false_positive_rate'])}"
            )
    return "\n".join(lines)


def format_stats_json(stats: Dict[str, Any]) -> str:
    return json.dumps(stats, ensure_ascii=False, indent=2)


def format_stats_markdown(stats: Dict[str, Any]) -> str:
    if stats["total_events"] == 0:
        return "尚無事件"
    lines = [
        "# Agent Dispatch Validation Stats",
        "",
        "| 指標 | 值 |",
        "|---|---|",
        f"| 總事件 | {stats['total_events']} |",
        f"| 已標註 | {stats['annotated']} |",
        f"| 未標註 | {stats['unannotated']} |",
        f"| TP | {stats['true_positive']} |",
        f"| FP | {stats['false_positive']} |",
        f"| Unknown | {stats['unknown']} |",
        f"| 誤報率 | {_fpr_text(stats['false_positive_rate'])} |",
        f"| 達標 | {stats['meets_threshold']} |",
        f"| malformed_lines | {stats['malformed_lines']} |",
    ]
    if stats.get("groups"):
        lines.append("")
        lines.append("## 分組")
        lines.append("")
        lines.append("| key | TP | FP | Unknown | 誤報率 |")
        lines.append("|---|---|---|---|---|")
        for g in stats["groups"]:
            lines.append(
                f"| {g['key']} | {g['true_positive']} | {g['false_positive']} "
                f"| {g['unknown']} | {_fpr_text(g['false_positive_rate'])} |"
            )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# E. CLI
# ---------------------------------------------------------------------------


def cmd_list(ns: argparse.Namespace) -> int:
    events, _malformed = read_events()
    annotations = read_annotations()
    filtered = filter_events(
        events, annotations,
        status=ns.status, agent=ns.agent,
        since=ns.since, limit=ns.limit,
    )
    if ns.format == "json":
        print(format_list_json(filtered))
    else:
        if not events:
            print("尚無事件")
        else:
            print(format_list_text(filtered, annotations))
    return 0


def cmd_show(ns: argparse.Namespace) -> int:
    events, _ = read_events()
    events = _dedupe_first_wins(events)
    target = None
    for e in events:
        if e.get("event_id") == ns.event_id:
            target = e
            break
    if target is None:
        print(f"dispatch_stats: event_id 不存在：{ns.event_id}", file=sys.stderr)
        return 2
    # show 的 text 與 json 輸出皆為 pretty JSON（規格），共用 format_show
    print(format_show(target))
    return 0


def cmd_annotate(ns: argparse.Namespace) -> int:
    if ns.all_unannotated:
        events, _ = read_events()
        annotations = read_annotations()
        unannotated_ids = [
            e["event_id"] for e in _dedupe_first_wins(events)
            if e["event_id"] not in annotations
        ]
        for eid in unannotated_ids:
            try:
                annotate_event(eid, ns.label, ns.note or "")
            except EventNotFound:
                continue
        return 0

    if not ns.event_id:
        print("dispatch_stats: annotate 需要 event_id 或 --all-unannotated", file=sys.stderr)
        return 2

    try:
        overwrote = annotate_event(ns.event_id, ns.label, ns.note or "")
    except EventNotFound:
        print(f"dispatch_stats: event_id 不存在：{ns.event_id}", file=sys.stderr)
        return 2
    except ValueError as e:
        print(f"dispatch_stats: {e}", file=sys.stderr)
        return 2
    if overwrote:
        print(
            f"warning: 覆寫 {ns.event_id} 既有標註（改為 {ns.label}）",
            file=sys.stderr,
        )
    return 0


def cmd_stats(ns: argparse.Namespace) -> int:
    events, malformed = read_events()
    annotations = read_annotations()
    # 空事件走 compute_stats + format_* 通用路徑：total_events=0 時，
    # format_stats_text / format_stats_markdown 皆回「尚無事件」；
    # json 仍輸出完整 stats 結構，維持 CLI 契約一致。
    stats = compute_stats(events, annotations, groupby=ns.groupby,
                           since=ns.since, malformed_lines=malformed)
    if ns.format == "json":
        print(format_stats_json(stats))
    elif ns.format == "markdown":
        print(format_stats_markdown(stats))
    else:
        print(format_stats_text(stats))
    return 0


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="dispatch_stats.py")
    sub = p.add_subparsers(dest="command", required=True)

    # list
    p_list = sub.add_parser("list")
    p_list.add_argument("--status", choices=("unannotated", "annotated", "all"),
                        default="unannotated")
    p_list.add_argument("--agent", default=None)
    p_list.add_argument("--since", default=None)
    p_list.add_argument("--limit", type=int, default=None)
    p_list.add_argument("--format", choices=("text", "json"), default="text")
    p_list.set_defaults(func=cmd_list)

    # show
    p_show = sub.add_parser("show")
    p_show.add_argument("event_id")
    p_show.add_argument("--format", choices=("text", "json"), default="text")
    p_show.set_defaults(func=cmd_show)

    # annotate
    p_ann = sub.add_parser("annotate")
    p_ann.add_argument("event_id", nargs="?", default=None)
    p_ann.add_argument("--label", choices=VALID_LABELS, required=True)
    p_ann.add_argument("--note", default="")
    p_ann.add_argument("--all-unannotated", action="store_true")
    p_ann.set_defaults(func=cmd_annotate)

    # stats
    p_stats = sub.add_parser("stats")
    p_stats.add_argument("--groupby", choices=("agent", "keyword", "none"),
                         default="none")
    p_stats.add_argument("--since", default=None)
    p_stats.add_argument("--format", choices=("text", "json", "markdown"),
                         default="text")
    p_stats.set_defaults(func=cmd_stats)

    return p


def main(argv: Optional[List[str]] = None) -> int:
    parser = _build_parser()
    ns = parser.parse_args(argv)
    try:
        return ns.func(ns)
    except OSError as e:
        print(f"dispatch_stats: OSError: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
