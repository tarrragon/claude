"""wrap-decision-tripwire-hook 的實作套件（職責拆分，hook 檔只保留 main 流程）。

模組依賴方向（單向，無循環）：signals 依賴 config、state；render 依賴 config、signals；state 與 config 互不依賴
  config.py  設定與訊號定義解析
  state.py   狀態檔管理（路徑、載入、原子寫入、過期清理、cooldown、換票重置）與時鐘注入點
  signals.py 票號推導與訊號判定（Strategy）
  render.py  訊息渲染與 prompt 摘錄
"""
