"""
staged 範圍判定（裸 commit／-a 的內容安全性驗證）

自 bare-commit-guard-hook.py 依職責抽出。只回答「這批檔案是否安全」，
不組訊息（訊息在 messages.py）。

失敗語意：
- 讀 staged／unstaged-tracked 清單失敗：回空清單（fail-open）。空清單在
  `_staged_scope_is_safe_for_bare_commit` 視為安全，故讀取失敗等同放行，
  僅可能低估實際提交範圍。
- 範圍判定本身不拋例外、無 I/O；不確定時回 False（阻擋方向）。
"""

from pathlib import Path
from typing import Dict, List

from lib.git_utils import run_git_command


def _get_staged_files(project_root: Path) -> List[str]:
    """取得目前 staged 檔案清單，讀取失敗時回傳空清單（fail-open）。"""
    success, output = run_git_command(
        ["diff", "--cached", "--name-only", "-z"], cwd=str(project_root)
    )
    if not success or not output:
        return []
    return [path for path in output.split("\0") if path]


def _get_unstaged_tracked_files(project_root: Path) -> List[str]:
    """取得目前 unstaged 但已追蹤（tracked）的修改檔案清單（`git diff
    --name-only`，不含 untracked 新檔），供 `-a`／`--all` 的內容安全性
    驗證使用——`-a` 本身也不提交 untracked 檔案，故此清單即為 `-a` 會
    額外納入、`_get_staged_files` 未涵蓋的那部分。讀取失敗時回傳空清單
    （fail-open，與 `_get_staged_files` 相同語意：讀不到內容時保守視為
    無額外風險內容，不阻擋，僅可能低估 `-a` 實際提交範圍）。
    """
    success, output = run_git_command(
        ["diff", "--name-only", "-z"], cwd=str(project_root)
    )
    if not success or not output:
        return []
    return [path for path in output.split("\0") if path]


def _staged_scope_is_safe_for_bare_commit(
    staged_files: List[str], dispatches: List[Dict], logger=None
) -> bool:
    """裸 commit（純 index 提交）的安全性驗證，兩條放行路徑擇一命中即安全：

    1. 子集路徑：staged 內容完整落在某一活躍派發宣告的 `files` 範圍內。
       命中即代表這次提交不可能夾帶「其他」活躍派發的宣告檔案。
    2. 不相交路徑：staged 內容與所有「已宣告範圍」活躍派發（`files` 非空）
       的聯集完全不相交（例如 PM 提交 ticket metadata，內容從不出現在
       任何派發宣告中）。

    files 為空的派發記錄（修正舊版設計，見下方「範圍修正」段）：空宣告
    代表該派發未聲明任何檔案範圍，邏輯上不構成任何人的領地，計算聯集時
    予以排除（不計入 `all()` 判定、不參與 union）。這不會降低對「有宣告
    範圍」派發的保護——子集路徑與不相交路徑檢查的仍是這些派發的完整
    宣告；差異只在於不再讓單一筆空宣告使整個不相交放行路徑對所有人失效
    （實測案例：一筆 code-review 型派發因 ticket_id 無法從 prompt/
    description 解析而 files 為空，導致與其他有效宣告完全不相交的正常
    提交被誤擋）。若排除空宣告後已無任何已宣告範圍（例如所有活躍派發的
    files 皆為空），聯集為空集合，staged 內容對空集合恆為不相交，同樣
    視為安全——這是同一原則（空宣告不構成領地）的自然延伸，非另立特例。

    範圍修正：舊版設計要求「dispatches 非空、且每個派發的 files 皆非空」
    才驗證不相交路徑，任一派發 files 為空即整條路徑失效、必須落到不
    安全。此舉把「無法驗證安全」等同於「必須阻擋」，但空宣告本身不構成
    領地，阻擋的是與空宣告完全無關的內容——防護對象錯置。

    兩條路徑皆不依賴呼叫者身份比對（並行環境下 PreToolUse 拿不到可靠的
    呼叫者身份），只驗證「內容」是否安全。

    staged_files 為空時視為安全（無內容可構成汙染，`git commit` 本身
    亦會因空提交拒絕，不需本 hook 額外處理）。

    已知邊界：兩條路徑驗的都是「宣告的」派發檔案範圍，非「實際」staged
    範圍。若 agent stage 了自己未宣告的檔案，該檔不在任何派發的宣告清單
    內，不相交路徑會誤判為安全。子集路徑本就有相同暴露面，此非本次引入
    的回歸，留待後續處理。

    Args:
        logger: 選填，非 None 時對「存在 files 為空的派發記錄」發出
            warning（可觀測性；記錄本身仍保留在 dispatch-active.json，
            供 dispatch_count／orphan 偵測等其他用途，僅本函式的範圍
            判定將其排除）。
    """
    if not staged_files:
        return True
    staged_set = set(staged_files)

    declared_sets = [set(d.get("files") or []) for d in dispatches]
    known_scope_sets = [declared for declared in declared_sets if declared]

    for declared in known_scope_sets:
        if staged_set <= declared:
            return True

    empty_count = len(declared_sets) - len(known_scope_sets)
    if empty_count > 0 and logger is not None:
        logger.warning(
            "%d 筆活躍派發記錄 files 為空（範圍未知，ticket_id 可能無法"
            "解析），計算不相交聯集時已排除",
            empty_count,
        )

    if declared_sets:
        all_declared = set().union(*known_scope_sets) if known_scope_sets else set()
        if staged_set.isdisjoint(all_declared):
            return True

    return False
