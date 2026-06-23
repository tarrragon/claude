"""error-pattern 來源前綴 ID 分配器（1.0.0-W1-019.3）。

實作 Model 1 來源前綴編號（W1-019 決策）的自動分配：
- identify_project_code：以 git toplevel basename 對應 registry `dir` → `code`，
  tooling 零 project-local 設定即可自我識別（registry 同時服務全域唯一 + 自我識別）。
- allocate_pattern_id：掃 `error-patterns/<cat-dir>/<CAT>-<PROJ>-*.md` 取既有最大號 +1，
  flat 凍結 base（`<CAT>-NNN`）不參與遞增（前綴命名空間獨立）。

依賴邊界：複用 `.claude/lib/pattern_id.py` 的 `PATTERN_ID_RE`（W1-019.2 SSOT），
不在 skill 內複製 regex 以免破壞剛收斂的單一權威。skill 獨立上架時的依賴打包
（pattern_id + pyyaml）屬 W1-001（SKILL 獨立上架規範）範圍。

規則來源：`.claude/methodologies/error-pattern-numbering-methodology.md`、
專案代號 SSOT：`.claude/error-patterns/_project-registry.yaml`。
"""

import sys
from pathlib import Path

import yaml

# 複用 lib 的 SSOT regex（W1-019.2，E2 linux F3）解析既有 ID。
_claude_dir = Path(__file__).resolve().parents[3]  # .claude
if str(_claude_dir) not in sys.path:
    sys.path.insert(0, str(_claude_dir))

from lib.pattern_id import PATTERN_ID_RE  # noqa: E402

# Category 前綴 → 目錄（與 skills/error-pattern/skill.md 編號章節一致）。
_CATEGORY_DIRS = {
    "ARCH": "architecture",
    "CQ": "code-quality",
    "DOC": "documentation",
    "IMP": "implementation",
    "PROC": "process",
    "PC": "process-compliance",
    "TEST": "test",
}


def identify_project_code(registry_path, repo_toplevel) -> str:
    """以 git toplevel basename 反查 registry `dir` 取得專案代號 `code`。

    Args:
        registry_path: `_project-registry.yaml` 路徑。
        repo_toplevel: git toplevel 路徑（取 basename 比對 `dir` 欄）。

    Raises:
        ValueError: basename 未登錄於 registry（防止靜默產生錯誤前綴）。
    """
    data = yaml.safe_load(Path(registry_path).read_text(encoding="utf-8")) or {}
    basename = Path(repo_toplevel).name
    for proj in data.get("projects", []):
        if proj.get("dir") == basename:
            return proj["code"]
    raise ValueError(
        f"專案目錄 '{basename}' 未登錄於 {registry_path}。"
        "新專案首次新增 error-pattern 前須先登錄 code + dir（見 numbering methodology）。"
    )


def allocate_pattern_id(category_prefix, claude_dir, project_code) -> str:
    """分配下一個來源前綴 ID：`<CAT>-<PROJ>-NNN`（NNN = 既有最大號 +1，首次 001）。

    flat 凍結 base（`PC-099`）不參與遞增——只掃 `<CAT>-<PROJ>-` 前綴空間。

    Raises:
        ValueError: 未知 category 前綴。
    """
    cat = category_prefix.upper()
    if cat not in _CATEGORY_DIRS:
        raise ValueError(
            f"未知 category 前綴 '{category_prefix}'，合法值：{sorted(_CATEGORY_DIRS)}"
        )

    cat_dir = Path(claude_dir) / "error-patterns" / _CATEGORY_DIRS[cat]
    prefix = f"{cat}-{project_code.upper()}-"

    max_num = 0
    if cat_dir.is_dir():
        for path in cat_dir.glob(f"{prefix}*.md"):
            match = PATTERN_ID_RE.search(path.name)
            if not match:
                continue
            pattern_id = match.group(0).upper()
            if not pattern_id.startswith(prefix):
                continue
            num = int(pattern_id.rsplit("-", 1)[1])
            max_num = max(max_num, num)

    return f"{prefix}{max_num + 1:03d}"
