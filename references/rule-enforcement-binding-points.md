# 規則執行點：綁命令還是綁事件

> **何時讀**：要讓一條規則被機械執行，而在挑選掛載點的時候；或手上已有一個執行點，要判斷它實際覆蓋多少。
>
> **一句話結論**：執行點綁在**命令**上時，覆蓋的是管道；管道是開放集合，換一個命令就繞過去了。要覆蓋檔案而非管道，落點在推送之後。

## 問題形態

「這條規則已經有 linter 在管了」這句宣稱，對的時候與錯的時候在文件上長得一樣。要看出差別，必須去查那個執行者掛在哪個事件上——而那不在任何一份談這條規則的文件裡，只在註冊設定裡。

以下是本機幾個常見執行點的實測覆蓋範圍。**每一列都是「這一層覆蓋誰」，不是「這條規則被保證了」**——後者需要把所有層加起來，而層數本身要先被列舉出來才數得清。

## 工具層：agent 框架的 PreToolUse

以 matcher 指定它攔哪些工具。典型註冊是 `Edit` 與 `Write`。

| 覆蓋 | 不覆蓋 |
|------|--------|
| 經該 matcher 所列工具的寫入 | 經 Bash 寫入（heredoc、`sed -i`、內嵌腳本） |

**加一個 matcher 不解決問題**——那只是把管道從一條擴成兩條。

## commit 層：掃 staged 內容

有些框架會在 commit 前補一道網，轉呼工具層各 guard 的判斷函式、掃描對象改為本次 commit 的新增行。這一層**補上了 Bash 寫入的缺口**，方向正確。

但它通常綁在 `git commit` 這個命令上。實測不經該命令而寫入 ref 的路徑：

- `commit-tree` + `update-ref`（隔離索引提交，CLI 內部常用此法避開共用 index 的競爭）
- `git merge --continue`

兩者都寫了 ref，兩者都不經過該層。

**一個容易忽略的後果**：當某個 CLI 的推薦提交路徑走隔離索引、而不推薦的 fallback 走裸 `git commit` 時，**推薦路徑不被稽核，不推薦的 fallback 被稽核**。選命令的人依語意或依推薦來選，而那個選擇同時決定了要不要被稽核，選的人不知道自己在選這個。

## git 原生 hook：`pre-commit` 也綁命令

`pre-commit` 只是把命令換了一層。實測（git 2.50.1）：

| 路徑 | `pre-commit` | `reference-transaction` |
|------|:---:|:---:|
| `git commit` | 觸發 | 觸發 |
| `git commit --no-verify` | **不觸發** | **觸發** |
| `commit-tree` + `update-ref` | **不觸發** | **觸發** |
| `git checkout -b`（僅建 ref，無內容變更） | 不觸發 | 觸發 |

最後一列是最乾淨的證據：它**沒有任何內容變更**，只建立了一個 ref，而 `reference-transaction` 仍然觸發。這把「綁 ref 不綁 commit」從推論變成可指認的現象。

## `reference-transaction`：本機唯一綁事件的落點

git 2.28 起提供。它綁的是 ref transaction 本身而非任何命令。

### 狀態與離開碼

它以第一個參數傳入交易狀態，**每次交易觸發多次**（`prepared`、`committed`，中止時另有 `aborted`），naive 計數會重複計算。內部 ref 也會觸發，例如合併期間的 `AUTO_MERGE`。

**只有 `prepared` 狀態的非零離開碼會中止交易**（手冊所載，實測相符）：hook 僅於 `committed` 回非零時，`rev-parse` 仍取得新 hash、`git log` 有該 commit；而無條件失敗的版本在 `prepared` 那次即中止，git 回報 `fatal: ref updates aborted by hook`。

它是實質閘門，但**閘門只有一格**。

### 必備的第一行

`prepared` 對每一次 ref 交易都會叫，所以**任何無條件失敗路徑會讓該 repo 的每一次 ref 更新失敗**——包含 `git checkout -b`。

```sh
[ "$1" = prepared ] || exit 0     # 當閘門用：把爆炸面收到只剩真正判斷的那一次
```

當通知用則反過來只認 `committed`——那一格的離開碼被忽略，寫壞了也不會中止交易。

### stdin 的三種形態

收到的是 `<old-value> SP <new-value> SP <ref-name>` 每行一筆，**不是 diff**。內容檢查須自行從 new-oid 走訪 tree，而兩端的欄位有三種形態：

| 形態 | 何時出現 | 對 `cat-file` |
|------|---------|--------------|
| 物件名 | 一般情形 | 合法 |
| 全零 | 見下表 | **fatal** |
| `ref:<ref-target>` | 符號 ref 更新（手冊所載） | **fatal** |

走訪實作必須先擋掉後兩種。

### 全零的兩端意義不同

實測：

| 情境 | old-oid | new-oid |
|------|:---:|:---:|
| `checkout -b`（建立） | 全零 | 正常 |
| `update-ref` 建立 | 全零 | 正常 |
| `branch -D`（強制刪除） | 全零 | 全零 |
| `branch -d`（非強制、已合併） | 全零 | 全零 |
| 合併期間的 `AUTO_MERGE` | 全零 | 全零 |

**`new-oid` 全零是可靠的刪除訊號。** `old-oid` 則否——它是**呼叫端傳入的期望舊值**，而非 ref 當下的值；不提供期望值的命令一律送全零，而是否提供因命令而異（實測：`git commit` 更新既有分支時提供真實舊值，`branch -d` 與 `checkout -b` 皆送全零）。

所以 **`old-oid` 不能用來判斷這是建立還是更新**。

### 分辨建立與更新：`rev-parse`，但只在 `prepared`

手冊指定的做法是對該 ref 執行 `git rev-parse`。實測其回傳**隨狀態改變**（同一個呼叫）：

```
[prepared ]  refs/heads/work   old=f38ba32  new=baa5afb   rev-parse=f38ba3225   ← 舊值
[committed]  refs/heads/work   old=f38ba32  new=baa5afb   rev-parse=baa5afb3e   ← 新值
```

`prepared` 時 ref 已鎖未寫，取得交易前的值；`committed` 時交易已完成，同一個呼叫取得的是新值。

| 情境 | `rev-parse <ref>`（`prepared` 時） |
|------|---|
| 建立 | 失敗（ref 不存在） |
| 更新 | 交易前的真實值 |

所以在 `prepared` 階段呼叫時，`rev-parse` 同時解兩件事：判別建立與更新，以及在 `old-oid` 為全零時取得真正的舊值。

**手冊那句「用 `rev-parse` 分辨」只在 `prepared` 成立**——寫在 `committed` 通知裡的人會拿到新值卻以為是舊值，而兩種寫法在程式碼上長得一樣。這與上面的 `[ "$1" = prepared ] || exit 0` 是同一條紀律的兩面：**閘門要分支，取值也要分支。**

### 它為什麼不適合承載內容檢查

不是看不到內容——實測 `prepared` 時對 new-oid 執行 `cat-file -t` 回傳 `commit`，新物件已在物件庫中（`git commit` 先寫 tree 與 commit、才更新 ref），走訪做得到。

**擋住它的是頻率與成本**：fetch、reset、`checkout -b` 一律要付這筆走訪錢，而其中多數與內容檢查無關。此處的頻率判斷為推測，未量測。

## 結論：兩者兼得的位置在伺服器端

要同時滿足「綁事件而非命令」與「適合承載內容檢查」，落點是 `pre-receive` 或 push 觸發的 CI：

- 那裡「ref 變了」是事件本身
- 換一個本機命令繞不過去——繞過本機不改變推上來的東西

**但這一格未經本文實測**。`pre-receive` 同樣有繞過面（直接寫入伺服器端 repo、繞過推送流程的部署路徑），強度不應等同於上表那四列已實測的路徑。

## 挑選執行點時問的三句

1. **它綁在哪個事件上？** 綁命令的話，列出所有能造成同一效果的其他命令
2. **它的覆蓋範圍是管道還是檔案？** 加一個 matcher 只是多一條管道
3. **還有沒有第二層？** 查到一個執行者不代表查完了——它只回答了「這一層覆蓋誰」

第三句是最容易漏的：一份宣稱有了第一個執行者之後，通常就沒有人再問還有沒有下一層。

---

## 出處

本文的實測皆於 git 2.50.1（macOS）以拋棄式 repo 進行，每項標明「實測」或「手冊所載」。未標明者為推論。

工具層與 commit 層的行為描述來自兩個使用 agent 框架 hook 的專案，機制名稱已泛化——各框架的 hook 名稱與註冊方式不同，此處描述的是形態而非特定實作。
