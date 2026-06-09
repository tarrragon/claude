"""Error-pattern ID 解析單一權威（SSOT）。

來源：1.0.0-W1-019.2（E2 / linux F3：收斂散佈 regex 為單一 util，避免下次再獵）。

支援 Model 1 來源前綴格式（W1-019 決策）：
- flat 凍結核心：`PC-099`、`IMP-049`（既有共享 base，凍結不再新增）
- 前綴格式：`PC-V1-001`、`IMP-APP-012`（`<CAT>-<PROJ>-NNN`，各專案命名空間）

用途邊界（重要）：本 util 服務「識別任意 error-pattern ID 字串」用途——歸屬判斷
（error_pattern_attribution）、未來的 ID 生成 / 驗證（W1-019.3 `/error-pattern add`）。

flat-only 的 collision-resolution 子系統（`scripts/sync-claude-pull.py` 的
`_PC_FILENAME_RE` / `_PROVENANCE_UPSTREAM_RE`）**刻意不使用**本 util：前綴格式天生
不參與 flat 整數撞號（各專案在自己前綴空間累加，零協調防碰撞），其 regex 只認 flat
凍結核心才是正確語意（W1-019.2 範圍收斂決策）。
"""

import re

# Category 前綴清單（與 error_pattern_attribution 既有 _PATTERN_ID_RE 一致）。
_CATEGORIES = "PC|IMP|ARCH|ANA|REF|DOC|CQ|PROC|TEST"

# 格式：<CAT>-([A-Z0-9]+-)?<NNN>
# - `(?:[A-Z0-9]+-)?` 為 optional 前綴段：flat（PC-099）與前綴（PC-V1-001）皆匹配。
# - 前綴段字元集含數字，因專案代碼本身可含數字（V1 / C2C）。regex 引擎對 flat 編號
#   會正確回溯（編號後無 `-` → optional 段放棄 → `\d+` 接手），由 test_pattern_id 鎖定。
# - `\b` 邊界保留以防 substring 誤判（PC-113 / PC-138 / PC-144 word-boundary 家族）。
PATTERN_ID_RE = re.compile(
    rf"\b(?:{_CATEGORIES})-(?:[A-Z0-9]+-)?\d+\b",
    re.IGNORECASE,
)


def extract_pattern_id(text: str):
    """從字串提取第一個 error-pattern ID（大寫正規化）；無命中回 None。

    用於從檔名或自由文字辨識 ID，例：
    `pc-v1-001-foo.md` → `PC-V1-001`、`see PC-099 detail` → `PC-099`。
    """
    m = PATTERN_ID_RE.search(text)
    return m.group(0).upper() if m else None
