#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml"]
# ///
"""
Git Ref Transaction Content Guard - 原生 git `reference-transaction` hook

背景（實測，非文件敘述，見同節「已知邊界」段落與
`.claude/references/rule-enforcement-binding-points.md`）：
commit-stage-guard-gate-hook.py 掛 PreToolUse（Bash matcher），觸發判準是
命令字面含 `git commit` 子命令。實測確認以下寫入 ref 的路徑不含此字面，
對該 hook 完全零命中：

1. 隔離索引提交（`commit-tree` + `update-ref`）——`ticket track commit`
   （`.claude/skills/ticket/ticket_system/lib/git_ops.py`
   `commit_files_isolated`）與 `ticket-md-auto-commit-hook.py`
   （PostToolUse 自動提交，獨立實作同一手法）皆走此路徑；且該路徑由
   ticket CLI 內部以 subprocess 發出，PreToolUse 收到的命令首 token 是
   `ticket` 非 `git`，屬雙重繞過。
2. `git merge --continue`（子命令為 `merge`，非 `commit`）。

本 hook 改綁「ref 寫入」這個**事件**本身，而非任何命令字面——不論呼叫端
是 `git commit`、`ticket track commit` 內部的 plumbing 呼叫、或未來任何
新寫法，只要最終落地為對 `refs/heads/*` 的一次寫入，就會被本 hook 看見。
此為本票選型依據的核心（掃描點的正確綁定對象是事件而非命令）。

============================================================
選型依據（實測，非文件敘述）
============================================================
`pre-commit` / `commit-msg` 等傳統 git hook 一樣綁在 `git commit` 命令
上，對 `commit-tree` + `update-ref` 路徑同樣零命中（本身也是「綁命令」
的變體，只是換了一層）。`reference-transaction`（git 2.28+）是本機唯一
綁「ref transaction 事件」而非命令的原生掛載點，實測（git 2.50.1）：

| 路徑 | `reference-transaction` |
|------|:---:|
| `git commit` | 觸發 |
| `git commit --no-verify` | 觸發（`--no-verify` 只跳過 pre-commit/commit-msg，不影響本掛載點） |
| `commit-tree` + `update-ref`（隔離索引） | 觸發 |
| `git merge --continue` | 觸發 |

四項皆以拋棄式 repo 實測確認（`prepared` 狀態回傳非零離開碼可中止該次
ref transaction，`fatal: ref updates aborted by hook`）。

============================================================
`prepared` / `committed` / `aborted` 三態
============================================================
`reference-transaction` 對每次 ref transaction 觸發多次（`prepared` ->
`committed` 或 `aborted`）。**只有 `prepared` 狀態的非零離開碼會中止交易**
（手冊所載，實測相符）；`committed`/`aborted` 狀態的離開碼被忽略。本 hook
只在 `state == "prepared"` 時執行實質檢查，其餘狀態立即 exit 0（避免對
`committed`/`aborted` 的無意義呼叫重複付出檢查成本）。

============================================================
判定「本次 transaction 引入哪些新內容」
============================================================
stdin 收到的是 `<old-oid> SP <new-oid> SP <ref-name>` 逐行清單（不是
diff）。`old-oid` 是否可靠因命令而異（部分命令不提供 CAS 期望值時一律送
全零，即使該 ref 早已存在，如 `git checkout -b` 建立指向既有 commit 的新
分支），故不直接以 `old-oid` 是否全零判斷「建立」或「更新」。

改用 `git rev-list <new-oid> --not --all`：在 `prepared` 階段，本次
transaction 尚未寫入 ref，`--all` 反映的是**交易前**的既有 ref 集合，故
此指令的結果精確等於「本次 transaction 引入、且不曾被任何既有 ref
涵蓋的 commit 集合」——不論該 ref 是全新建立還是既有更新皆適用同一條
指令，不需分支判斷建立/更新。若結果為空（如 `git checkout -b` 建立分支
指向已被其他 ref 涵蓋的既有 commit），代表無新內容，直接放行，避免對
「純 ref 重新指向」的常見操作（如新建分支、fast-forward）付出無意義的
掃描成本。

同一次 transaction 若有多個 `refs/heads/*` 行（如合併同時動到多個 ref），
每個新 commit 只掃描一次（跨行去重），對每個新 commit 以其第一個 parent
為基準做 diff（根 commit 則以 git 空樹 SHA 為基準）——多 parent 的合併
commit 因其他分支的祖先若「新」也會各自出現在 rev-list 結果中並被獨立
掃描，故以 first-parent 為單一 commit 的 diff 基準不會漏掃合併帶入的新
內容。

============================================================
已知邊界（刻意不做，非遺漏）
============================================================
- 只處理 `refs/heads/*` 與裸 `HEAD`（detached HEAD commit 直接寫
  `HEAD` 而非任何分支 ref）。其餘 ref（`refs/tags/*`、
  `refs/remotes/*`、`refs/stash`、rebase 期間的 `refs/rewritten/*` 等）
  一律略過——這些 ref 的內容變更若引入新 commit，該 commit 必然也會經由
  某個 `refs/heads/*` 更新被掃到（tag/remote-tracking ref 本身不是「新
  內容的原始來源」）；`HEAD` 這一分支目前未經實測覆蓋，屬推論式涵蓋。
- `git push` 更新的是遠端 repo 的 ref，屬另一個 repo 的
  `reference-transaction`（若遠端有安裝的話），本 hook 只在本機 repo
  生效，不涵蓋伺服器端。伺服器端把關（`pre-receive`）需另外評估，未經
  本票實測。
- 效能成本未經量測：`git rev-list <new-oid> --not --all` 隨全域 ref 數量
  增長而變貴，`reference-transaction` 對 fetch/reset/checkout 等高頻操作
  也會觸發（僅 `prepared` 狀態才執行實質工作，已降低一半觸發成本，但未
  對大型 repo 做效能基準測試）。
- 各 guard 若依賴 `tool_input`（如 Edit 的 old_string/new_string 部分替換
  語意）之處，改用「整個新 commit 相對其 first-parent 的 pre/post/added
  文字」近似，與 commit-stage-guard-gate-hook.py（掃 index）的既知邊界
  相同（見該檔檔頭「已知邊界」段）。

============================================================
安裝方式
============================================================
`.git/hooks/` 不受版本控制，本檔不會被 git 自動安裝為
`reference-transaction` hook。安裝由
`.claude/hooks/git-ref-transaction-guard-install-hook.py`（SessionStart）
負責：於 `git rev-parse --git-common-dir` 解析出的共用 hooks 目錄寫入一個
極小 shim，執行時以 `uv run --quiet` 呼叫本檔（shim 內容與安裝／冪等策略
見該檔 docstring）。

失敗語意：內部例外一律 fail-open（exit 0，放行本次 ref transaction），
但異常訊息必寫 stderr（git hook 的 stderr 會直接顯示於使用者終端機，
不同於 Claude Code PreToolUse 的 JSON channel）並記錄檔案日誌，避免單一
guard 載入失敗或程式錯誤全域擋下團隊所有 git 操作，同時符合「Hook 失敗
必須可見」的可觀測性要求。
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib import setup_hook_logging  # noqa: E402
from lib.git_utils import get_project_root, run_git_command  # noqa: E402
from lib.commit_content_guards import (  # noqa: E402
    Finding,
    StagedFile,
    _run_all_checks,
    _build_deny_message,
    _build_warn_message,
)

EXIT_ALLOW = 0
EXIT_BLOCK = 1  # `prepared` 狀態任何非零離開碼皆中止該次 ref transaction

_HEADS_PREFIX = "refs/heads/"
_HEAD_REF = "HEAD"
_EMPTY_TREE_SHA = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"  # git 內建空樹物件


def _is_zero_oid(oid: str) -> bool:
    """判斷 oid 是否為全零（刪除訊號，或部分命令未提供 CAS 期望值時的
    佔位值——後者不代表刪除，見檔頭「判定新內容」段落，故只用於過濾
    `new-oid` 全零的刪除情境，不用於推斷建立/更新）。"""
    return bool(oid) and set(oid) == {"0"}


def _read_ref_transaction_lines() -> List[Tuple[str, str, str]]:
    """讀取 stdin 的 `<old-oid> SP <new-oid> SP <ref-name>` 逐行清單。"""
    lines: List[Tuple[str, str, str]] = []
    for raw in sys.stdin:
        parts = raw.rstrip("\n").split(" ", 2)
        if len(parts) != 3:
            continue
        old_oid, new_oid, ref_name = parts
        if not new_oid or not ref_name:
            continue
        lines.append((old_oid, new_oid, ref_name))
    return lines


def _collect_new_commits(new_oid: str, project_root: Path) -> List[str]:
    """`git rev-list <new_oid> --not --all`：prepared 階段尚未寫入 ref，
    `--all` 反映交易前的既有 ref 集合，結果即本次 transaction 引入且未被
    任何既有 ref 涵蓋的 commit 集合（見檔頭「判定新內容」段落）。"""
    ok, out = run_git_command(
        ["rev-list", new_oid, "--not", "--all"], cwd=str(project_root)
    )
    if not ok or not out:
        return []
    return [line.strip() for line in out.splitlines() if line.strip()]


def _first_parent(commit_sha: str, project_root: Path) -> Optional[str]:
    ok, out = run_git_command(
        ["rev-parse", "--quiet", "--verify", f"{commit_sha}^"], cwd=str(project_root)
    )
    if not ok or not out.strip():
        return None
    return out.strip()


def _changed_files(pre_rev: str, new_rev: str, project_root: Path) -> List[str]:
    ok, out = run_git_command(
        ["diff", "--name-only", pre_rev, new_rev], cwd=str(project_root)
    )
    if not ok or not out:
        return []
    return [line.strip() for line in out.splitlines() if line.strip()]


def _rename_map(pre_rev: str, new_rev: str, project_root: Path) -> Dict[str, str]:
    """新路徑 -> 舊路徑對照表，語意與
    commit-stage-guard-gate-hook.py 的 `_get_staged_rename_map` 相同，
    差別僅在比對對象是兩個 commit revision 而非 index。"""
    ok, out = run_git_command(
        ["diff", "-M", "--name-status", pre_rev, new_rev], cwd=str(project_root)
    )
    if not ok or not out:
        return {}
    rename_map: Dict[str, str] = {}
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) != 3 or not parts[0].startswith("R"):
            continue
        _status, old_path, new_path = parts
        rename_map[new_path] = old_path
    return rename_map


def _git_show(rev_spec: str, project_root: Path) -> str:
    ok, out = run_git_command(["show", rev_spec], cwd=str(project_root))
    return out if ok else ""


def _added_text(
    pre_rev: str,
    new_rev: str,
    rel_path: str,
    project_root: Path,
    old_path: Optional[str] = None,
) -> str:
    args = ["diff"]
    if old_path is not None:
        args.append("-M")
    args += [pre_rev, new_rev, "--"]
    if old_path is not None:
        args.append(old_path)
    args.append(rel_path)
    ok, out = run_git_command(args, cwd=str(project_root))
    if not ok or not out:
        return ""
    return "\n".join(
        line[1:]
        for line in out.splitlines()
        if line.startswith("+") and not line.startswith("+++")
    )


def _build_commit_scan_file(
    rel_path: str,
    pre_rev: str,
    new_rev: str,
    project_root: Path,
    rename_map: Dict[str, str],
) -> StagedFile:
    old_path = rename_map.get(rel_path)
    pre_path = old_path if old_path is not None else rel_path
    pre_text = _git_show(f"{pre_rev}:{pre_path}", project_root)
    post_text = _git_show(f"{new_rev}:{rel_path}", project_root)
    added_text = _added_text(pre_rev, new_rev, rel_path, project_root, old_path=old_path)
    return StagedFile(rel_path, pre_text, post_text, added_text)


def _scan_new_commit(commit_sha: str, project_root: Path, logger) -> List[Finding]:
    parent = _first_parent(commit_sha, project_root)
    pre_rev = parent if parent is not None else _EMPTY_TREE_SHA
    changed = _changed_files(pre_rev, commit_sha, project_root)
    if not changed:
        return []
    rename_map = _rename_map(pre_rev, commit_sha, project_root)
    staged_files = [
        _build_commit_scan_file(p, pre_rev, commit_sha, project_root, rename_map)
        for p in changed
    ]
    return _run_all_checks(staged_files, project_root, logger)


def main() -> int:
    logger = setup_hook_logging("git-ref-transaction-content-guard")

    state = sys.argv[1] if len(sys.argv) > 1 else ""
    ref_lines = _read_ref_transaction_lines()

    if state != "prepared":
        # 僅 prepared 狀態的非零離開碼會中止交易，其餘狀態無需執行實質
        # 檢查（見檔頭「prepared / committed / aborted 三態」段落）。
        logger.debug("state=%s 非 prepared，略過（無需實質檢查）", state)
        return EXIT_ALLOW

    project_root = get_project_root()

    new_commit_shas: Set[str] = set()
    for old_oid, new_oid, ref_name in ref_lines:
        if not (ref_name.startswith(_HEADS_PREFIX) or ref_name == _HEAD_REF):
            continue
        if _is_zero_oid(new_oid):
            continue  # 刪除，無新內容
        new_commit_shas.update(_collect_new_commits(new_oid, project_root))

    if not new_commit_shas:
        logger.debug("本次 transaction 無新 commit（純 ref 重新指向），放行")
        return EXIT_ALLOW

    findings: List[Finding] = []
    for commit_sha in sorted(new_commit_shas):
        findings.extend(_scan_new_commit(commit_sha, project_root, logger))

    deny_findings = [f for f in findings if f.severity == "deny"]
    warn_findings = [f for f in findings if f.severity == "warn"]

    if deny_findings:
        logger.warning(
            "ref transaction 被阻擋：deny=%d warn=%d new_commits=%d",
            len(deny_findings), len(warn_findings), len(new_commit_shas),
        )
        header = (
            "[git-ref-transaction-content-guard] ref 寫入被阻擋：新提交內容經"
            f"事後掃描命中 {len(deny_findings)} 項 guard 違規（此路徑不經 "
            "`git commit` 命令，commit-stage-guard-gate 的 PreToolUse 層看不到，"
            "故由本 reference-transaction 原生 hook 補上）。\n"
            "請修正後重新提交：\n"
        )
        sys.stderr.write(_build_deny_message(deny_findings, header) + "\n")
        return EXIT_BLOCK

    if warn_findings:
        logger.info(
            "ref transaction 放行但有 WARN 發現：warn=%d new_commits=%d",
            len(warn_findings), len(new_commit_shas),
        )
        header = f"[git-ref-transaction-content-guard] 提醒：新提交內容命中 {len(warn_findings)} 項 WARN 級發現（不阻擋）：\n"
        sys.stderr.write(_build_warn_message(warn_findings, header) + "\n")
        return EXIT_ALLOW

    logger.debug("新 commit 內容無發現，放行：new_commits=%d", len(new_commit_shas))
    return EXIT_ALLOW


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001 — 頂層防護，見檔頭「安裝方式」段落失敗語意
        # fail-open：內部錯誤不應全域擋下所有 git 操作，但必須可見（規則 4）。
        sys.stderr.write(
            f"[git-ref-transaction-content-guard] 內部錯誤（已放行，未阻擋本次 ref 寫入）：{exc}\n"
        )
        try:
            import traceback

            _logger = setup_hook_logging("git-ref-transaction-content-guard")
            _logger.critical(
                "git-ref-transaction-content-guard 內部錯誤：%s\n%s",
                exc,
                traceback.format_exc(),
            )
        except Exception:  # noqa: BLE001 — 日誌本身失敗不應影響 fail-open 決策
            pass
        sys.exit(EXIT_ALLOW)
