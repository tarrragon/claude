# GCP 管理通道的設定：IAP、OS Login、舊規則收斂、由 template 建的主機、GKE 與稽核

> **何時讀**：`dimensions/security.md`〈管理通道〉的三層表與判讀要點確認這個專案在 GCP 上有 VM、Kubernetes 節點或自管資料庫主機要登入之後，要實際設定或收斂時讀。訪談階段只需要那一節，不必讀本檔。
>
> **同目錄**：`gcp-spend-kill-switch.md`（GCP 支出停損的實作）。連線失敗的錯誤分層與主機金鑰核對見 `linux-install-debug` 的 remote-access；結束工作階段的步驟見 `linux-install-debug` 的 process-service-state。驗收依據見 `../principles/protection-proves-itself-by-firing.md`。

## 三層的設定指令（已實測）

```bash
# 網路可達性：只放行 IAP 位址段（35.235.240.0/20）連到帶 tag 的 VM 的 22 port；規則開 logging
gcloud compute firewall-rules create allow-ssh-from-iap --network=<network> \
  --direction=INGRESS --action=allow --rules=tcp:22 \
  --source-ranges=35.235.240.0/20 --target-tags=<ssh-tag> --enable-logging
# 剛開 logging 的最初幾分鐘 rule_details 是空的，驗證時改用來源位址段查（linux-install-debug 的 remote-access）

# 通道授權：只允許連 22 port，期限到了綁定自動失效（<expiry> 是 RFC 3339 時間，例如 2026-12-31T00:00:00Z）
gcloud projects add-iam-policy-binding <project> \
  --member=group:<ops-group> --role=roles/iap.tunnelResourceAccessor \
  --condition='expression=destination.port == 22 && request.time < timestamp("<expiry>"),title=iap-ssh'

# 主機登入驗證：先把登入角色綁給維運群組（要 sudo 時用 osAdminLogin，只登入、不 sudo 時用 osLogin），
# 再在專案層啟用 OS Login；順序反過來，啟用那一刻還沒拿到角色的人就登不進去。<ops-group> 是群組的 email
gcloud projects add-iam-policy-binding <project> --member=group:<ops-group> --role=roles/compute.osAdminLogin
gcloud compute project-info add-metadata --metadata enable-oslogin=TRUE
```

- 外部 IP 只承擔管理用途時才移除：對外流量經負載平衡器、出站另配 Cloud NAT 之後再拿掉；VM 本身就是對外入口時保留外部 IP，只收掉管理 port。
- VM 掛著服務帳號時，登入者另外要那個服務帳號的 `roles/iam.serviceAccountUser`。
- 救援入口是序列主控台加本機救援帳號：上線前實際登入一次並確認 `sudo` 可用，確認後把 `serial-port-enable` 設回 `FALSE`。

## 舊規則的停用、驗證與回退

1. 預設的全開規則（`default-allow-ssh`）涵蓋 IAP 的位址段，舊規則還在時連得上，證明不了新規則放行了 IAP 的連線，所以要先停用舊規則再驗新路徑。
2. 停用之前：救援入口已經登入過；專案已有主機時，先開舊規則的 logging 觀察，觀察期涵蓋最長週期的排程（週排程就觀察一週）；列出 project 與 instance metadata 的 `ssh-keys`，啟用 OS Login 之後它們失效，用它們登入的自動化要先改成有 `roles/compute.osLogin` 的服務帳號。
3. 新路徑驗不過時，用 `gcloud compute firewall-rules update default-allow-ssh --no-disabled` 恢復舊規則，再照 linux-install-debug 的 IAP 錯誤分層查。

## 由 template 建的主機

MIG 與 GKE node pool 的 tag、OS Login metadata、移除外部 IP 要寫在 instance template 或 node pool 設定裡，逐台修改在重建後消失。

## GKE 控制平面與節點除錯

- **控制平面**：公開的 API server 端點等同網路可達性全開。新叢集用 DNS-based endpoint（以 IAM 判斷能不能連、不受 IP 清單限制）；authorized networks 是 IP 白名單，更新時新清單整組取代舊清單（不是附加），清單只列維運與 CI 的來源，不要設成 IAP 的位址段（IAP TCP 轉送不代理 API server）。
- **節點除錯**：能在節點上建 `kubectl debug node` 除錯 Pod 的帳號，用預設的 `general`（或 `sysadmin`）debug profile 就能以 root 讀寫節點檔案；debug profile 裡同名的 `baseline`、`restricted` 不掛節點目錄。處置是把一般工作負載的 namespace 設成 Pod Security Admission 的 `baseline` 等級以上（它會拒絕 `general` 與 `sysadmin` 建的除錯 Pod），節點除錯集中到一個只有維運能建 Pod 的 namespace。

## 稽核紀錄

- IAP 開通道的紀錄屬於 Cloud Identity-Aware Proxy 的 Data Access `ADMIN_READ` 類型（只開 `DATA_READ` 時一筆都沒有），方法名稱是 `AuthorizeUser`。
- OS Login 每次登入留下 `CheckPolicy` 紀錄（`protoPayload.serviceName="oslogin.googleapis.com"`）。
- 開啟之後實際經由 IAP 連一次、查到這次連線的紀錄才算完成：

```bash
gcloud logging read 'protoPayload.serviceName="iap.googleapis.com" AND protoPayload.methodName="AuthorizeUser"' \
  --freshness=1h --format="value(timestamp,protoPayload.authenticationInfo.principalEmail,protoPayload.resourceName)"
```

## 人員離職

角色綁在群組上時，把那個人移出群組，不要移除群組的角色綁定（那會擋掉全部維運者）。撤銷只會擋住之後的新登入，已連著的工作階段要在主機上結束，並以 `pgrep -u <user> -a` 的輸出為空作為完成的判斷，步驟見 linux-install-debug 的 process-service-state。
