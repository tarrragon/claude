---
id: IMP-057
title: grep pattern 的匹配條件與待答問題的判準不一致（多行語句 / block style 值 / 匯入形態）
category: implementation
severity: medium
first_seen: 2026-04-11
---

# IMP-057: grep pattern 的匹配條件與待答問題的判準不一致（多行語句 / block style 值 / 匯入形態）

## 症狀

- 使用 `grep -v "file=sys.stderr"` 篩選 bare print() 時，多行 print 語句被誤判為違規
- 掃描報告的違規數量比實際多（本次：grep 報 18 處，AST 驗證為 14 處，3 個 Hook 為誤報）

## 根因

Python 的 `print()` 可以跨行書寫：

```python
# grep 只看到 line 275 有 print(，沒有 file=sys.stderr → 誤判為 bare stdout
print(                          # line 275 ← grep 匹配此行
    "[WARNING] message",        # line 276
    file=sys.stderr,            # line 277 ← 關鍵資訊在另一行
)                               # line 278
```

`grep -v "file=sys.stderr"` 是逐行比對，無法跨行關聯 `print(` 和 `file=sys.stderr`。

更一般地說，失效條件是 **pattern 的匹配條件與待答問題的判準不一致**。逐行比對只是其中一種形態（pattern 無法表達跨行條件），另一種是 pattern 的命中範圍寬於判準——命中了，但命中的東西不全具備待答問題關心的那個屬性。下方兩個延伸形態分屬這兩種。

### 延伸形態：YAML block style 的值不在欄位名行上（2026-08-20）

同根因在資料檔上的表現，且多一層危害——不只漏看，漏看造成的形態差異被當成資料特徵。

檢查 YAML frontmatter 時以 `grep -E "^(fieldA|fieldB):"` 取欄位值，同一份文件內兩個相鄰欄位的可見性不一致：

```yaml
blockedBy: []          # flow style：值在同一行，grep 看得到
relatedTo:             # block style：grep 只看到這一行
- some-value           # 值在下一行以 "- " 起始，pattern 不匹配
```

觀測者據此得出「傳了值的欄位反而是空值，未傳的是空清單」的結論，並將此不對稱當成缺陷線索，進而建立了一張前提錯誤的 ticket、寫入錯誤的因果推論、質疑了結論正確的執行者。真實資料無此不對稱——它完全由 grep pattern 與序列化形態的交互產生。

**與原案例的差異**：原案例的後果是誤報（多算違規數量），本延伸的後果是把觀測工具的產物當成資料特徵。前者在覆核時會被數量對不上而發現，後者因為「看起來有意義的形態差異」反而自帶說服力，不易自我察覺。

**檢查方式**：`sed -n 'N,Mp'` 取區段、`grep -A2 "^field:"`，或以 yaml 解析後取值。判斷訊號是「同類欄位的可見性不一致」——這通常是序列化形態差異而非資料差異，須先排除觀測方法再談資料。

### 延伸形態：grep 命中集合不等於受影響集合（2026-08-21）

三個形態的共同根源見 §根因 的上位敘述：pattern 的匹配條件與待答問題的判準不一致。前兩個形態的不一致表現為 pattern 無法表達跨行條件（漏看，假陰性），本形態相反——pattern 命中範圍寬於判準，命中了，但命中的東西裡只有一部分真正相關。

評估「清空某 package `__init__.py` 的 re-export 會影響誰」時，掃描 `from pkg import` 推估遷移工作量。同一條指令在數週間量到 95、115、125 三個遞增值（期間陸續有新測試檔匯入該 package），據此判定為大範圍任務。實際動手後發現受影響者為零：

```python
from pkg import submodule   # Python 找 pkg/submodule.py，不依賴 __init__ 的 re-export
from pkg import symbol      # 依賴 __init__ 有該符號，清空後即壞
```

同一個 pattern 兩者都命中，只有後者受影響。該次評估的 125 行全屬前者，清空 re-export 對它們毫無影響，真正的遷移工作量是零。

危害不在多做工，在規劃階段的判斷被數字扭曲。該任務因這個計數被列為大範圍高風險，要求分批執行，並標注須獨占派發、不可與其他任務並行；實際只需改一個檔案。

更值得記的是：**限定條件其實已被寫下**。該任務的敘述欄明載「絕大多數匯入的是子模組名稱而非 re-export 的個別符號」——區分是知道的。但驅動排程決策的仍是那個不帶限定的計數。帶限定的敘述與不帶限定的數字並存於同一份文件時，後者主導決策，因為它可以直接進入判斷而前者需要再讀一次。

**檢查方式**：本形態的鑑別可機械化——取出每個匯入名，比對 `pkg/` 下是否存在同名模組檔；存在即屬子模組匯入，不受 re-export 清空影響。剩餘者才是真正的受影響集合。

無法機械化時的兜底：對「命中數即工作量」的推論，先問「這個 pattern 命中的東西，是否全部具備我關心的那個屬性」，再從命中集合抽幾筆逐一確認語意，而非直接用總數推估。

## 影響範圍

- 任何需要掃描 Python print() 語句用途的分析任務
- 本次影響：3 個 Hook（post-git-commit-hook, branch-verify-hook, layer-boundary-validator-hook）被誤報為違規

## 解決方案

使用 Python AST 分析代替 grep 進行精確掃描：

```python
import ast

for node in ast.walk(tree):
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "print":
        has_stderr = any(
            kw.arg == "file" and isinstance(kw.value, ast.Attribute) and kw.value.attr == "stderr"
            for kw in node.keywords
        )
        has_json = any(
            isinstance(arg, ast.Call) and isinstance(arg.func, ast.Attribute) and arg.func.attr == "dumps"
            for arg in node.args
        )
        if not has_stderr and not has_json:
            print(f"BARE stdout: {hook}:{node.lineno}")
```

## 防護措施

1. **掃描 Python 語法結構時優先使用 AST**：grep 適合文字搜尋，不適合語法分析
2. **grep 初篩 + AST 精確驗證**：先用 grep 快速縮小範圍，再用 AST 排除誤報
3. **建立子 Ticket 前先驗證計數**：基於 grep 結果建立的 Ticket 應在派發前驗證實際數量——語法結構類用 AST，命中範圍過寬類用上述機械化鑑別或取樣確認語意

## 行為模式

開發者習慣用 grep 做 code scan，對於大多數場景足夠。但 Python 的多行語法（函式呼叫、字典、列表等跨行書寫）讓逐行 grep 失效。這在需要理解「語法結構」而非「文字出現」時特別明顯。
