#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml"]
# ///
"""error-pattern carrier 欄位檢查：carrier 已填但目標載體沒有指向該 pattern 的路由。

carrier 值域與解析（目標載體 -> 路由 = 目標文字含 pattern ID）：
- rule                          -> rules/**、pm-rules/** 任一 .md 含 ID
- skill:<名>                    -> skills/<名>/ 下任一 .md 含 ID
- lang-pack:<skill>/<語言>      -> skills/<skill>/references/<語言>.md 含 ID
- agent:<名>                    -> agents/<名>.md 含 ID
- none / 未填                   -> 不檢查（存量 pattern 不回填）

缺口三類：invalid（值非法）、missing_target（目標載體不存在）、no_route。
有缺口 exit 1，無缺口 exit 0。
"""

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

import yaml

KIND_INVALID = "invalid"
KIND_MISSING_TARGET = "missing_target"
KIND_NO_ROUTE = "no_route"

_NAME = r"[A-Za-z0-9_.-]+"
_SKILL_RE = re.compile(rf"^skill:({_NAME})$")
_LANG_RE = re.compile(rf"^lang-pack:({_NAME})/({_NAME})$")
_AGENT_RE = re.compile(rf"^agent:({_NAME})$")


@dataclass(frozen=True)
class Finding:
    pattern_id: str
    carrier: str
    kind: str
    path: Path


def _read_frontmatter(path):
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return {}
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}
    try:
        data = yaml.safe_load(parts[1]) or {}
    except yaml.YAMLError:
        return {}
    return data if isinstance(data, dict) else {}


def _target_files(claude_dir, carrier):
    """回傳 (目標檔清單, 是否合法)；合法但目標不存在回 ([], True)。"""
    if carrier == "rule":
        files = []
        for sub in ("rules", "pm-rules"):
            files += sorted((claude_dir / sub).rglob("*.md"))
        return files, True
    if m := _SKILL_RE.match(carrier):
        return sorted((claude_dir / "skills" / m.group(1)).rglob("*.md")), True
    if m := _LANG_RE.match(carrier):
        f = claude_dir / "skills" / m.group(1) / "references" / f"{m.group(2)}.md"
        return ([f] if f.is_file() else []), True
    if m := _AGENT_RE.match(carrier):
        f = claude_dir / "agents" / f"{m.group(1)}.md"
        return ([f] if f.is_file() else []), True
    return [], False


def _mentions(files, pattern_id):
    return any(pattern_id in f.read_text(encoding="utf-8") for f in files)


def _check(claude_dir, path, fm):
    carrier = fm.get("carrier")
    if carrier is None or carrier == "none":
        return None
    pid = str(fm.get("id", path.stem))
    carrier = str(carrier)
    files, valid = _target_files(claude_dir, carrier)
    if not valid:
        return Finding(pid, carrier, KIND_INVALID, path)
    if not files:
        return Finding(pid, carrier, KIND_MISSING_TARGET, path)
    if not _mentions(files, pid):
        return Finding(pid, carrier, KIND_NO_ROUTE, path)
    return None


def audit(claude_dir):
    """掃描 <claude_dir>/error-patterns，回傳缺口清單。"""
    claude_dir = Path(claude_dir)
    findings = []
    for path in sorted((claude_dir / "error-patterns").rglob("*.md")):
        fm = _read_frontmatter(path)
        if "carrier" not in fm:
            continue
        finding = _check(claude_dir, path, fm)
        if finding:
            findings.append(finding)
    return findings


def format_report(findings):
    if not findings:
        return "carrier 檢查：無缺口"
    lines = [f"carrier 檢查：{len(findings)} 筆缺口"]
    lines += [f"  [{f.kind}] {f.pattern_id} carrier={f.carrier}" for f in findings]
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    default = Path(__file__).resolve().parents[3]
    parser.add_argument("--claude-dir", default=str(default))
    args = parser.parse_args(argv)
    findings = audit(args.claude_dir)
    print(format_report(findings))
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
