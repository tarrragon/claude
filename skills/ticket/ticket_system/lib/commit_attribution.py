"""提交訊息歸屬 trailer 補全。

`ticket track commit` 的訊息缺 Co-Authored-By 時，由 transcript 最後一則
assistant 訊息的 model id 推導顯示名稱後補上；Claude-Session 行若存在但與
Co-Authored-By 不相鄰，移到相鄰位置。取不到值時只警告、不補，提交照常。

transcript 位置（實測，Claude Code 2.1.x）：
- 主 session：``~/.claude/projects/<專案目錄編碼>/<CLAUDE_CODE_SESSION_ID>.jsonl``
- 子代理人：``~/.claude/projects/<專案目錄編碼>/<父 session id>/subagents/agent-<agentId>.jsonl``
  子代理人環境的 CLAUDE_CODE_SESSION_ID 是父 session 的值；agentId 取自
  worktree 目錄名 ``agent-<agentId>``（cwd 判定，不用 AI_AGENT；共用 checkout
  內的子代理人會被當成主 session，本框架中該類只會是唯讀審查者，可接受）。
專案目錄編碼為路徑中非英數字元一律換成 ``-``；本模組以 glob 找 session id
而不重算編碼，避免編碼規則漂移。
"""
import json
import os
import re
from pathlib import Path
from typing import List, Optional, Tuple

# 通則 claude-<family>-<major>-<minor> -> Claude <Family> <major>.<minor>；
# 此表只收通則推導結果不正確的例外項（單一常數）。
MODEL_DISPLAY_NAMES: dict = {}
_MODEL_ID_RE = re.compile(r"^claude-(?P<family>[a-z]+)-(?P<major>\d+)-(?P<minor>\d+)$")
CO_AUTHOR_EMAIL = "noreply@anthropic.com"
_TAIL_BYTES = 512 * 1024
_CO_RE = re.compile(r"^Co-Authored-By:", re.IGNORECASE)
_SESSION_RE = re.compile(r"^Claude-Session:", re.IGNORECASE)
_TRAILER_RE = re.compile(r"^[A-Za-z][A-Za-z0-9-]*:\s+\S")


def _claude_home() -> Path:
    return Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude")


def _find_transcript(repo_root: str) -> Tuple[Optional[Path], str]:
    """回傳 (transcript 路徑, 失敗原因)。子代理人只認自身 transcript。"""
    session_id = os.environ.get("CLAUDE_CODE_SESSION_ID")
    if not session_id:
        return None, "CLAUDE_CODE_SESSION_ID 未設定"
    # 以 cwd 判定：toplevel 為 .claude/worktrees/agent-<id> 即該子代理人。
    # AI_AGENT 主 session 也帶 _agent 尾綴，不是子代理人訊號。
    # 已知限制：共用 checkout 內的子代理人會被當成主 session；本框架中實作
    # 代理人由 hook 強制使用 worktree，共用 checkout 的子代理人只會是唯讀
    # 審查者、不提交，故可接受。
    root = Path(os.path.abspath(repo_root))
    base = root.name
    is_subagent = base.startswith("agent-") and root.parent.name == "worktrees"
    projects = _claude_home() / "projects"
    if is_subagent:
        hits = list(projects.glob(f"*/{session_id}/subagents/{base}.jsonl"))
    else:
        hits = list(projects.glob(f"*/{session_id}.jsonl"))
    if not hits:
        return None, "找不到 transcript"
    return hits[0], ""


def _last_assistant_model(path: Path) -> Optional[str]:
    try:
        with open(path, "rb") as fh:
            fh.seek(0, os.SEEK_END)
            fh.seek(max(0, fh.tell() - _TAIL_BYTES))
            lines = fh.read().decode("utf-8", errors="replace").splitlines()
    except OSError:
        return None
    for line in reversed(lines):
        try:
            msg = json.loads(line).get("message")
        except ValueError:
            continue
        model = msg.get("model") if isinstance(msg, dict) else None
        if model and model != "<synthetic>":
            return model
    return None


def display_name_for_model(model: str) -> Optional[str]:
    key = re.sub(r"\[.*?\]$", "", model)
    key = re.sub(r"-\d{8}$", "", key)
    if key in MODEL_DISPLAY_NAMES:
        return MODEL_DISPLAY_NAMES[key]
    m = _MODEL_ID_RE.match(key)
    if not m:
        return None
    return f"Claude {m['family'].capitalize()} {m['major']}.{m['minor']}"


def resolve_co_author_line(repo_root: str) -> Tuple[Optional[str], str]:
    """回傳 (完整 Co-Authored-By 行, 失敗原因)。"""
    path, reason = _find_transcript(repo_root)
    if path is None:
        return None, reason
    model = _last_assistant_model(path)
    if not model:
        return None, "transcript 內無 assistant model"
    name = display_name_for_model(model)
    if not name:
        return None, f"model {model} 無法推導顯示名稱"
    return f"Co-Authored-By: {name} <{CO_AUTHOR_EMAIL}>", ""


def _move_session_adjacent(lines: List[str]) -> List[str]:
    co_idx = [i for i, l in enumerate(lines) if _CO_RE.match(l)]
    sess_idx = [i for i, l in enumerate(lines) if _SESSION_RE.match(l)]
    if not co_idx or not sess_idx:
        return lines
    last_co = co_idx[-1]
    if all(i == last_co + 1 or i == co_idx[0] - 1 for i in sess_idx):
        return lines
    moved = [lines[i] for i in sess_idx]
    rest = [l for i, l in enumerate(lines) if i not in sess_idx]
    pos = max(i for i, l in enumerate(rest) if _CO_RE.match(l)) + 1
    return rest[:pos] + moved + rest[pos:]


def _append_trailer(lines: List[str], trailer: str) -> List[str]:
    while lines and not lines[-1].strip():
        lines = lines[:-1]
    last_par = []
    for l in reversed(lines):
        if not l.strip():
            break
        last_par.append(l)
    only_trailers = bool(last_par) and len(last_par) < len(lines) and all(
        _TRAILER_RE.match(l) for l in last_par
    )
    return lines + ([] if only_trailers else [""]) + [trailer]


def apply_attribution(message: str, repo_root: str) -> Tuple[str, Optional[str]]:
    """回傳 (處理後訊息, 警告)。已含 Co-Authored-By 時只處理 Claude-Session 相鄰。"""
    original = message.rstrip("\n").split("\n")
    lines = original
    if not any(_CO_RE.match(l) for l in lines):
        co_line, reason = resolve_co_author_line(repo_root)
        if co_line is None:
            return message, f"[WARNING] 訊息缺 Co-Authored-By 且無法自動補上：{reason}"
        lines = _append_trailer(lines, co_line)
    new_lines = _move_session_adjacent(lines)
    if new_lines == original:
        return message, None
    return "\n".join(new_lines) + "\n", None
