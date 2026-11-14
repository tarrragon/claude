"""commit 守衛的 doc validate 檢查：本次提交觸及的 docs 節點只擋新增的驗證錯誤。

背景：線直接提交規格到共用 main 時不經合併閘門，commit 守衛也不跑 `doc validate`，
格式錯誤的規格因此直接進 main。本模組由 commit_content_guards._run_all_checks 呼叫，
PreToolUse（commit-stage-guard-gate，讀 index）與 reference-transaction
（git-ref-transaction-content-guard，讀 commit tree）兩條路徑共用。

判定：
- 觸及節點：本次變更、變更後仍存在、位於 doc skill 的 spec／usecases／events 目錄
  或為 docs 根的 domain-map、frontmatter 帶 id 的 .md。docs/proposals/ 由
  proposal-evaluation-gate 負責，不在此重複判定；`doc validate` 不檢查 UC 編號是否存在
  （該項由 uc-reference-validation 負責），兩者範圍不重疊。
- 只擋新增：同一 doc_id 在「本次提交前」的 docs 樹再驗一次，扣除已存在的錯誤項目，
  剩餘非空才算新增。提交前的樹以工作區複製，並把本次變更的每個 docs 檔還原為
  pre_text（新檔則移除），等同提交前的 docs 狀態。
- 比對基準：doc validate 讀工作區。工作區內容與 StagedFile.post_text（PreToolUse 為
  index、reference-transaction 為 commit tree）不一致時，驗證結果不代表提交內容，
  新增錯誤降為 warn。
- doc CLI 失敗、逾時或輸出無法辨識：fail-open，寫 stderr 與日誌。
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Dict, FrozenSet, List, Optional, Tuple

DOC_VALIDATE_SOURCE = "doc-validate"
DOC_VALIDATE_TIMEOUT_SECONDS = 30

# 路徑以 doc skill 的分段寫法表示（同 doc_system.core.file_locator 與 commands/validate.py
# 的 root / "docs" / ... 組法），兩處各自的名稱來源皆為 doc skill。
_DOCS = "docs"
_DOMAIN_MAP = (_DOCS, "domain-map.md")
_NODE_DIRS = ((_DOCS, "spec"), (_DOCS, "usecases"), (_DOCS, "events"))
_NODE_DIR_PREFIXES = tuple("/".join(parts) + "/" for parts in _NODE_DIRS)
_NODE_SINGLE_FILES = ("/".join(_DOMAIN_MAP),)
# doc validate 讀取的路徑（見 doc_system.core.file_locator 與 commands/validate.py）
_VALIDATE_INPUT_PATHS = tuple(
    "/".join(parts)
    for parts in (*_NODE_DIRS, (_DOCS, "proposals"), _DOMAIN_MAP, (_DOCS, "proposals-tracking.yaml"))
)
_FAIL_HEADER = "驗證失敗:"
_ITEM_PREFIX = "  - "
_EXIT_PASS, _EXIT_FAIL, _EXIT_NOT_FOUND = 0, 1, 2

_DOC_SKILL_DIR = Path(__file__).resolve().parent.parent / "skills" / "doc"


class ValidateResult:
    """一次 doc validate 的結果：ok=False 代表 CLI 本身失敗（fail-open 用）。"""

    def __init__(self, ok: bool, errors: FrozenSet[Tuple[str, str]], detail: str = "") -> None:
        self.ok = ok
        self.errors = errors
        self.detail = detail


def is_doc_node_path(rel_path: str) -> bool:
    if not rel_path.endswith(".md"):
        return False
    return rel_path.startswith(_NODE_DIR_PREFIXES) or rel_path in _NODE_SINGLE_FILES


def frontmatter_id(text: str) -> Optional[str]:
    """取 frontmatter 的 id 值；無 frontmatter 或無 id 回傳 None。"""
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        return None
    for line in lines[1:]:
        if line.strip() == "---":
            return None
        if line.startswith("id:"):
            value = line[len("id:"):].strip().strip("\"'")
            return value or None
    return None


def parse_validate_output(returncode: int, stdout: str) -> ValidateResult:
    """把 doc validate 輸出轉為錯誤項目集合（以「失敗標頭、項目」配對）。"""
    if returncode == _EXIT_PASS:
        return ValidateResult(True, frozenset())
    if returncode == _EXIT_NOT_FOUND:
        first = stdout.strip().split("\n")[0] if stdout.strip() else ""
        return ValidateResult(True, frozenset({("rc=2", first)}))
    if returncode != _EXIT_FAIL:
        return ValidateResult(False, frozenset(), f"rc={returncode}")
    errors = set()
    header: Optional[str] = None
    for line in stdout.split("\n"):
        if line.startswith(_FAIL_HEADER):
            header = line.strip()
            errors.add((header, ""))
        elif line.startswith(_ITEM_PREFIX) and header is not None:
            errors.add((header, line[len(_ITEM_PREFIX):].strip()))
        else:
            header = None
    if not errors:
        # rc=1 但無「驗證失敗:」標頭：多為 import 失敗等 CLI 自身錯誤，不當成驗證結果
        return ValidateResult(False, frozenset(), f"rc=1 輸出無驗證失敗標頭：{stdout.strip()[:200]}")
    return ValidateResult(True, frozenset(errors))


def run_doc_validate(doc_id: str, root: Path) -> ValidateResult:
    """以子程序執行 doc validate；專案根以 CLAUDE_PROJECT_DIR 指定。"""
    env = dict(os.environ)
    env["CLAUDE_PROJECT_DIR"] = str(root)
    env["PYTHONPATH"] = str(_DOC_SKILL_DIR) + os.pathsep + env.get("PYTHONPATH", "")
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "doc_system", "validate", doc_id],
            cwd=str(root), env=env, capture_output=True, text=True,
            timeout=DOC_VALIDATE_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        return ValidateResult(False, frozenset(), f"逾時（{DOC_VALIDATE_TIMEOUT_SECONDS}s）")
    except OSError as exc:
        return ValidateResult(False, frozenset(), f"無法啟動：{exc}")
    result = parse_validate_output(proc.returncode, proc.stdout)
    if not result.ok and proc.stderr:
        result.detail += f"；stderr：{proc.stderr.strip()[-300:]}"
    return result


def _build_pre_commit_tree(project_root: Path, staged_files, dest: Path) -> None:
    """複製 doc validate 會讀的路徑，再把本次變更的 docs 檔還原為提交前內容。"""
    for rel in _VALIDATE_INPUT_PATHS:
        src = project_root / rel
        if src.is_dir():
            shutil.copytree(src, dest / rel)
        elif src.is_file():
            (dest / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest / rel)
    for sf in staged_files:
        if not sf.rel_path.startswith("docs/"):
            continue
        target = dest / sf.rel_path
        if sf.pre_text:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(sf.pre_text, encoding="utf-8")
        elif target.exists():
            target.unlink()


def _normalize(text: str) -> str:
    """與呼叫端重建 post_text 的正規化一致：換行統一為 \\n、去尾端換行
    （PreToolUse 的 run_git_command 與 reference-transaction 的 cat-file 皆如此處理）。"""
    return text.replace("\r\n", "\n").replace("\r", "\n").rstrip("\n")


def _workspace_matches(project_root: Path, sf) -> bool:
    try:
        workspace = (project_root / sf.rel_path).read_text(encoding="utf-8")
    except OSError:
        return False
    return _normalize(workspace) == _normalize(sf.post_text)


def _report_cli_failure(doc_id: str, rel_path: str, detail: str, logger) -> None:
    """fail-open：doc CLI 失敗不阻擋，但 stderr 與日誌都要看得到（規則 4）。"""
    msg = f"[doc-validate] {rel_path}（{doc_id}）doc validate 執行失敗，已放行未判定：{detail}"
    sys.stderr.write(msg + "\n")
    logger.warning(msg)


def _format_errors(errors) -> str:
    return "\n".join(f"  - {h} {item}".rstrip() for h, item in sorted(errors))


def check_doc_validate(staged_files, project_root: Path, logger, finding_cls) -> list:
    """對觸及的 docs 節點跑 doc validate，回傳 Finding 清單（新增錯誤才產生）。"""
    nodes: List[Tuple[object, str]] = []
    for sf in staged_files:
        if not sf.post_text or not is_doc_node_path(sf.rel_path):
            continue
        doc_id = frontmatter_id(sf.post_text)
        if doc_id:
            nodes.append((sf, doc_id))
    if not nodes:
        return []

    findings = []
    pre_results: Dict[str, ValidateResult] = {}
    tmp_dir: Optional[str] = None
    try:
        for sf, doc_id in nodes:
            post = run_doc_validate(doc_id, project_root)
            if not post.ok:
                _report_cli_failure(doc_id, sf.rel_path, post.detail, logger)
                continue
            if not post.errors:
                logger.info("doc validate 通過：%s（%s）", sf.rel_path, doc_id)
                continue
            if tmp_dir is None:
                tmp_dir = tempfile.mkdtemp(prefix="commit-doc-validate-")
                _build_pre_commit_tree(project_root, staged_files, Path(tmp_dir))
            pre = run_doc_validate(doc_id, Path(tmp_dir)) if sf.pre_text else ValidateResult(True, frozenset())
            if not pre.ok:
                _report_cli_failure(doc_id, sf.rel_path, "提交前基準：" + pre.detail, logger)
                continue
            pre_results[doc_id] = pre
            new_errors = post.errors - pre.errors
            logger.info(
                "doc validate：%s（%s）現行錯誤 %d 項，提交前已有 %d 項，新增 %d 項",
                sf.rel_path, doc_id, len(post.errors), len(pre.errors), len(new_errors),
            )
            if not new_errors:
                continue
            consistent = _workspace_matches(project_root, sf)
            severity = "deny" if consistent else "warn"
            note = "" if consistent else (
                "（工作區內容與提交內容不一致，驗證結果不代表提交內容，降為提醒）"
            )
            findings.append(finding_cls(
                severity, DOC_VALIDATE_SOURCE,
                f"[doc-validate] {sf.rel_path}（{doc_id}）本次變更新增 doc validate 錯誤{note}：\n"
                f"{_format_errors(new_errors)}\n"
                f"修正後重跑 `doc validate {doc_id}` 確認；提交前已存在的錯誤不阻擋。",
                sf.rel_path,
            ))
    finally:
        if tmp_dir is not None:
            shutil.rmtree(tmp_dir, ignore_errors=True)
    return findings
