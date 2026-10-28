# 遊戲圖片辨識搜尋｜網頁版 MVP

使用者可透過瀏覽器上傳遊戲封面、圖示或截圖，系統會與從 Excel 遊戲百科匯入的圖片資料庫比對，回傳最相似的候選遊戲。

## 已包含
- 從使用者提供的 Excel 遊戲百科預先匯入 51 張遊戲圖片（`CG电子` 工作表）
- 網頁上傳 PNG / JPG / JPEG / WEBP / BMP 圖片
- 快速相似圖比對：結合低解析度結構特徵與 RGB 色彩直方圖，無需付費 API
- 可選 CLIP 視覺模型：有助於比較不同尺寸或畫面風格，但不保證能正確識別遊戲
- 依名稱瀏覽與搜尋遊戲資料庫

## 本機測試
需要 Python 3.10 或更新版本。

```bash
python -m venv .venv
# Windows：.venv\Scripts\activate
# macOS / Linux：source .venv/bin/activate
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

瀏覽器開啟終端機顯示的網址，通常為 `http://localhost:8501`。

## 免費部署成網頁（Streamlit Community Cloud）
1. 建立 GitHub repository。
2. 將此資料夾內的 `app.py`、`requirements.txt`、`data/` 與本 README 推送到 repository 根目錄。
3. 到 Streamlit Community Cloud 登入並連接 GitHub repository。
4. 選擇 `app.py` 作為 Main file path，按 Deploy。
5. 部署完成後即可透過網站網址使用。

注意：目前 `data/images/` 約 56 MB。整個資料夾都要一併上傳，不能只上傳 `app.py`。若之後圖片庫大幅增長，建議改用物件儲存或資料庫，不要無限制把所有圖片放在 Git repository。

## 啟用 CLIP AI（選用）
先確認部署平台的記憶體、磁碟與啟動時間足夠，再將 `requirements-ai.txt` 中的依賴合併進 `requirements.txt`，或在部署環境安裝：

```bash
python -m pip install -r requirements-ai.txt
```

首次使用會下載模型權重，模型體積與記憶體需求明顯高於快速比對。免費主機可能因資源限制而無法順利載入，因此預設不強制使用 CLIP。

## Excel 資料匯入方式
目前已把提供的 Excel「CG电子」工作表圖片抽取並整理到：
- `data/games.json`：遊戲名稱、圖片相對路徑、工作表與原始儲存格
- `data/images/`：圖片檔案

要更新資料庫，請將新抽取的圖片放進 `data/images/`，並更新 `data/games.json`，再重新部署。每筆 JSON 範例如下：

```json
{
  "name": "遊戲名稱",
  "image": "data/images/001_遊戲名稱.png",
  "sheet": "工作表名稱",
  "cell": "A1"
}
```

Excel 若使用 `DISPIMG` 公式，圖片可能是以 Excel 內部圖片資源儲存，不能只讀取公式字串就匯出；請保留圖片與遊戲名稱的對應關係，匯入後抽查幾筆，確認圖片沒有配錯名稱。當同一款遊戲有多張參考圖時，可在 JSON 加入多筆資料，並保持相同遊戲名稱。

## 架構
- 前端與應用伺服器：Streamlit
- 資料索引：`data/games.json`
- 圖片：`data/images/`
- 基礎比對：Pillow + NumPy（結構與色彩特徵）
- 可選 AI：OpenCLIP（本地模型推論，無需付費 API）

## 限制與隱私
- 系統只會在已匯入的圖片中找候選，不會自動搜尋整個網路。
- 相似度分數是排序指標，不是經過校準的正確機率；裁切、特效、遊戲改版或完全不同的畫面可能影響結果。
- 雲端部署時，上傳的查詢圖片會傳到部署網站的主機處理。此程式不會主動轉送到第三方 AI API；仍應依部署平台的隱私政策管理資料。
- 免費雲端方案可能有休眠、資源、儲存與流量限制，實際政策以平台當前條款為準。
