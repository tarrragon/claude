# GCP 支出停損的實作：預算、Pub/Sub、函式部署、驗收與停用後的恢復

> **何時讀**：`dimensions/capacity-performance.md`〈支出停損〉的決策點判定某個 GCP 專案要建停損（解除帳單連結）或只停止花錢的資源之後，要實際建置、驗收或在停用後恢復時讀。訪談階段只需要那一節的決策點，不必讀本檔。
>
> **同目錄**：`gcp-management-access.md`（GCP 管理通道的設定）。判斷依據見 `../principles/protection-proves-itself-by-firing.md`。

整條鏈是：預算（帳單帳戶）→ 通知 → Pub/Sub topic → Eventarc 觸發器 → Cloud Run functions 函式 → 解除帳單連結（`projects.updateBillingInfo`，`billingAccountName` 給空字串），或停止花錢的資源。兩種處置共用預算、topic、觸發器與重試設定，差別在函式本體、服務帳號的角色與驗收的終點。下文以解除帳單連結為主，只停止花錢的資源的差異寫在各節末。

## 預算與 topic

1. **接停損的預算另外建**，不接到既有的帳戶層級警示預算上：
   - 範圍用 `--filter-projects=projects/<project>` 限定在要停用的那一個專案。不限定時 `costAmount` 是整個帳單帳戶的合計，別的專案的花費也會觸發停損。
   - 金額設成這個專案本期能承受的最高花費，減掉帳單資料延遲期間最多能多花的金額（約「每小時最多能花的費用 × 延遲時數」，每小時上限由配額與最大執行個體數決定）；不是預期花費。
   - 帳戶有大額抵免時加 `--credit-types-treatment=exclude-all-credits`，否則抵免用完前 `costAmount` 接近 0、停損不會觸發（實測同一段期間扣抵免的預算報 0.05、不扣的報 0.37）。只想讓部分抵免照扣時用 `include-specified-credits` 加 `--filter-credit-types=FREE_TIER` 這類類型名稱；`--help` 不列類型，寫錯回 `INVALID_ARGUMENT`。`FREE_TIER` 是抵免類型，所以 `exclude-all-credits` 也把免費方案的用量以原價算進去。
2. **一個 topic 只接一個預算**：本檔的函式不分辨通知來自哪一個預算，好幾個預算送到同一個 topic 時，任何一個超支都會讓它停掉 `TARGET_PROJECT_ID`。topic 原本接在別的預算上時，`gcloud billing budgets update` 沒有清除旗標，用預算 API 以 `updateMask=notificationsRule.pubsubTopic` PATCH 成空字串。
3. **通知管道**：`--notifications-rule-monitoring-notification-channels` 只接受電子郵件類型的 Cloud Monitoring 管道；接 webhook 類型時只回 `INVALID_ARGUMENT: Request contains an invalid argument`，不說原因。

```bash
# 預算通知送到 Pub/Sub topic；設定通知目標時會自動授權 billing-budget-alert@system.gserviceaccount.com 發布
gcloud pubsub topics create budget-alerts --project=<project>
gcloud billing budgets create --billing-account=<billing-account-id> --display-name=<name> \
  --budget-amount=<能承受的最高花費減掉延遲期間的花費><currency> --filter-projects=projects/<project> \
  --notifications-rule-pubsub-topic=projects/<project>/topics/budget-alerts --billing-project=<project>
```

`--billing-project` 指定的專案要先啟用 `billingbudgets.googleapis.com`。建立預算的身分要通過兩道檢查，被拒時依序對照：先是那個專案的 `serviceusage.services.use`（`USER_PROJECT_DENIED`），再是帳單帳戶上帳單帳戶管理員或費用管理員的角色。`budgetFilter.projects` 存的是專案編號。

## 服務帳號與函式部署

```bash
# 解除帳單連結用 billing.projectManager，讀取帳單狀態（getBillingInfo）另外要 browser；
# --condition=None 讓專案裡已有條件式綁定時，非互動模式不會停下來要求選擇條件
gcloud projects add-iam-policy-binding <project> --member=serviceAccount:<sa> --role=roles/billing.projectManager --condition=None
gcloud projects add-iam-policy-binding <project> --member=serviceAccount:<sa> --role=roles/browser --condition=None

# 兩個服務帳號旗標都明確指定：--trigger-service-account 不給時，gcloud 說明寫用 Compute Engine 預設服務帳號，
# 實測卻沿用 --service-account；--retry 讓暫時性失敗的通知幾分鐘內重送；--max-instances=1 讓多則通知依序處理
gcloud functions deploy <name> --gen2 --trigger-topic=budget-alerts --service-account=<sa> \
  --trigger-service-account=<sa> --retry --max-instances=1 --set-env-vars=TARGET_PROJECT_ID=<project> \
  --runtime=<runtime> --entry-point=<function> --source=<dir> --region=<region> --project=<project>

# 觸發器以 --trigger-service-account 的身分呼叫函式，要給它呼叫權限，否則每次推送都 403
gcloud run services add-iam-policy-binding <name> --region=<region> --member=serviceAccount:<sa> \
  --role=roles/run.invoker --project=<project>
```

部署的身分要有 `<sa>` 的 `roles/iam.serviceAccountUser`。部署後用 `gcloud functions describe <name> --region=<region>` 確認 `eventTrigger.serviceAccountEmail` 與 `eventTrigger.retryPolicy`（`RETRY_POLICY_RETRY`）。

只停止花錢的資源時：函式用 `instances().aggregatedList(filter='status = "RUNNING"')` 跨全部 zone 列出 VM 再逐台 `stop`（實測服務帳號只要 `roles/compute.instanceAdmin.v1`，約兩分鐘後 `TERMINATED`），MIG 目標台數設成 0、GKE node pool 縮到 0 另要 container 的權限（未實跑）。

## 判斷規則

- 只看實際花費：`budgetAmount > 0` 且 `costAmount >= budgetAmount` 才處置；改看預測花費會讓一次短暫的尖峰停掉服務。
- 讀不懂或解碼失敗的訊息直接結束、不拋出例外，否則 `--retry` 讓它一直重送。
- 呼叫 Cloud Billing API 的錯誤不攔，交給 `--retry`。
- 解除之前先 `getBillingInfo`，帳單已停用就回 `none`。

## 驗收

部署成功、狀態 `ACTIVE` 不算完成。`run.invoker`、`browser` 與 `--retry` 三項缺任何一個，停損都會在看似正常的狀態下失效。驗收分兩段：

1. **topic 之前**：等第一則真實的預算通知，查函式紀錄裡的 `received`，確認 `budgetDisplayName` 是接停損的預算、`costAmount` 與帳單報表上這個專案本期的費用相符（接近 0 而報表不是，就是抵免或範圍設錯）。
2. **topic 之後**：超出預算那一則會實際停用帳單、可能刪除資料，所以排在停機可以接受的時段做。
   1. 先發低於預算的那一則（`gcloud pubsub topics publish budget-alerts --message='{"costAmount": <值>, "budgetAmount": <預算>}'`，`<值>` 低於 `<預算>`），確認函式紀錄有 `action=none`。查詢回傳零筆時，改查同一個服務的請求紀錄（`logName:"run.googleapis.com%2Frequests"`、`httpRequest.status`）：有 403 代表缺 `run.invoker`。
   2. 再發 `<值>` 不低於 `<預算>` 的那一則，看到 `gcloud billing projects describe <project>` 的 `billingEnabled` 變成 `false`。
   3. 用 `gcloud billing projects link <project> --billing-account=<billing-account-id>` 重新連結，連結完成才算驗收結束。
3. **專案有停用後不能遺失的資料時，改用分段驗證**：另部署一份換了函式名稱與 topic 的複本（例如 `budget-killswitch-test`、`budget-alerts-test`），`TARGET_PROJECT_ID` 指向可拋棄的空專案、兩個角色綁在那個空專案上，對複本的 topic 發超出預算的訊息——沿用正式名稱會蓋掉正式函式，發到正式 topic 會停掉正式專案。正式專案只用 Policy Troubleshooter 確認函式的服務帳號持有 `resourcemanager.projects.deleteBillingAssignment` 與 `resourcemanager.projects.get`（`gcloud policy-intelligence troubleshoot-policy iam //cloudresourcemanager.googleapis.com/projects/<project> --principal-email=<sa> --permission=<permission>`，先啟用 `policytroubleshooter.googleapis.com`，`overallAccessState` 要是 `CAN_ACCESS`），驗收紀錄寫明缺了正式專案上那一次解除連結。
4. **心跳監看**：把函式帶 `action` 的紀錄做成日誌指標（`gcloud logging metrics create`），建一條缺席條件的告警；缺席條件的時間窗上限 23 小時 30 分，設 23 小時。設好之後先縮到幾分鐘確認通知送得到，再改回；放在被保護的專案以外。

只停止花錢的資源時，第 2 步的終點改成 `gcloud compute instances list` 的狀態變成 `TERMINATED`、MIG 目標台數與 node pool 節點數變成 0，每一個 zone 與資源型別各確認一次，也不需要重新連結。

## 反應時間與停用後的恢復

- 停損限制的是損失的上限，帳單資料延遲期間（數小時、有時超過一天）已經發生的費用攔不下來；從超支訊息發出到停用約十幾秒。
- 帳單停用期間資源清單回傳空的，空清單不代表資源已刪除；重新連結後留下的資源繼續計費，清理以重新連結後的清單為準。
- 停損程式跑在被停用的專案上時，它自己也會停擺（實測停用後約一分鐘內函式仍處理了下一則通知，查詢函式狀態的 API 則回 403）；被入侵而有編輯權限的身分也刪得掉它。這兩點不可接受時，把 topic、函式與服務帳號放在另一個專案（管理專案），被保護的專案只綁兩個角色（實測被保護的專案 9 秒後停用，管理專案的函式照常處理之後的訊息）。
- `costAmount` 是本期累計值，只重新連結的話下一則通知會再停用一次：
  - **服務自己出錯**：修好程式之後，先調高預算金額或刪掉函式，再重新連結。
  - **資源被別人濫用**：重新連結之前把預算金額調成目前的 `costAmount` 加上清理期間能承受的金額，並先撤銷外洩的 API 金鑰與服務帳號金鑰（實測帳單停用期間 `gcloud services api-keys delete` 照常可用）；重新連結後列出並刪除不屬於自己的 VM、instance template 與 MIG，確認乾淨之後再把預算調回原本的金額。
