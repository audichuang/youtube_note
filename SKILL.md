---
name: youtube-note
description: >
  YouTube 影片學習筆記生成工具。給一個連結，自動取得字幕（支援無字幕影片，使用 Deepgram 語音辨識），
  AI 語義分析內容後產出雙語結構化學習筆記，搭配關鍵畫面截圖。
  使用場景：當用戶提供 YouTube 連結需要整理學習筆記時。
  關鍵詞：YouTube、學習筆記、影片筆記、截圖、note、筆記
allowed-tools:
  - Read
  - Write
  - Bash
  - Glob
  - AskUserQuestion
---

# YouTube 影片學習筆記生成工具

> **Installation**: If you're installing this skill from GitHub, run:
> ```bash
> bash install_as_skill.sh
> ```

## 重要：腳本路徑與工作目錄

- 所有 Python 腳本位於 `~/.claude/skills/youtube-note/scripts/`
- **不要 cd 到 skill 目錄**，始終使用絕對路徑呼叫腳本
- 影片和筆記輸出到**使用者的當前工作目錄**下的 `youtube-notes/<title>/`

呼叫腳本的標準方式：
```bash
python3 ~/.claude/skills/youtube-note/scripts/<script_name>.py <args>
```

## 工作流程

你將按照以下 6 個階段執行 YouTube 影片學習筆記生成任務：

### 階段 1: 環境檢測

**目標**: 確保所有必需工具和依賴都已安裝

1. 檢測 yt-dlp 是否可用
   ```bash
   yt-dlp --version
   ```

2. 檢測 FFmpeg（標準版即可，不需要 ffmpeg-full）
   ```bash
   ffmpeg -version
   ```

3. 檢測 Python 依賴
   ```bash
   python3 -c "import yt_dlp; print('✅ yt-dlp available')"
   python3 -c "from youtube_transcript_api import YouTubeTranscriptApi; print('✅ youtube-transcript-api available')"
   python3 -c "from deepgram import DeepgramClient; print('✅ deepgram-sdk available')"
   python3 -c "from dotenv import load_dotenv; print('✅ python-dotenv available')"
   ```

**如果環境檢測失敗**:
- yt-dlp 未安裝: 提示 `brew install yt-dlp` 或 `pip install yt-dlp`
- FFmpeg 未安裝: 提示 `brew install ffmpeg`
- youtube-transcript-api 缺失: `pip install youtube-transcript-api`
- deepgram-sdk 缺失: `pip install deepgram-sdk`
- python-dotenv 缺失: `pip install python-dotenv`

**注意**: 標準 FFmpeg 即可（不需要 ffmpeg-full），必須先通過環境檢測才能繼續。

---

### 階段 2: 取得字幕（三層 fallback）

**目標**: 用最快的方式取得影片字幕

**核心策略：先取字幕，再決定是否下載影片**

1. 執行字幕取得腳本
   ```bash
   python3 ~/.claude/skills/youtube-note/scripts/get_transcript.py <youtube_url>
   ```

2. 腳本會依序嘗試：
   - **第 1 層**: youtube-transcript-api（最快，不需下載影片，秒級完成）
   - **第 2 層**: yt-dlp 字幕下載（下載字幕檔但不下載影片）
   - **第 3 層**: Deepgram API 語音辨識（自動下載音軌並辨識，分鐘級完成）

3. 腳本會將字幕 JSON 輸出到 **stdout**

4. **你需要用 Write 工具**將 JSON 結果保存到輸出目錄的 `subtitles/transcript.json`

5. 記錄字幕來源（`youtube-api` / `yt-dlp` / `deepgram`）

**重要**:
- 腳本只輸出到 stdout，不會自動寫入檔案
- 如果第 1、2 層成功，此時還不需要下載影片
- 如果第 3 層被觸發，腳本會自動下載音軌到 tempdir 並辨識完成後清理

**如果三層全部失敗且需要手動處理**:
1. 先用 `download_video.py` 下載影片
2. 再用 `extract_audio.py` 從影片提取音軌
3. 最後用 `get_transcript.py --audio_file <audio.wav>` 呼叫 Deepgram

```bash
# 手動 Deepgram 路徑
python3 ~/.claude/skills/youtube-note/scripts/download_video.py <url>
python3 ~/.claude/skills/youtube-note/scripts/extract_audio.py <video.mp4>
python3 ~/.claude/skills/youtube-note/scripts/get_transcript.py --audio_file <audio.wav>
```

---

### 階段 3: 下載影片（截圖用）

**目標**: 下載影片以供截圖使用

1. 執行下載腳本（**傳入輸出目錄**以確保下載到正確位置）
   ```bash
   python3 ~/.claude/skills/youtube-note/scripts/download_video.py <youtube_url> <output_dir>
   ```

   其中 `<output_dir>` 是階段 2 建立的 `youtube-notes/<title>/` 目錄。
   如果未傳入 output_dir，腳本會在**當前工作目錄**下建立 `youtube-notes/<title>/`。

2. 如果階段 2 的第 3 層已觸發下載，影片可能已被清理（因為第 3 層使用 tempdir）。此時仍需重新下載。

3. 記錄影片資訊：標題、頻道、時長、上傳日期、URL

**輸出**:
- 影片檔: `<output_dir>/<video_id>.mp4`
- 影片資訊 JSON（輸出到 stdout）

---

### 階段 4: AI 語義分析（核心智慧階段）

**目標**: 閱讀完整字幕，提煉核心主題並規劃主題導向筆記結構

**這是你作為 AI 最關鍵的步驟。你需要做深層分析，而非簡單分段摘要：**

1. **閱讀完整字幕內容**
   - 讀取 `subtitles/transcript.json`
   - 理解影片的完整內容、論點邏輯和知識結構

2. **判斷影片類型**
   - `tutorial`：教學類，有步驟性操作
   - `demo`：演示類，展示工具/產品使用
   - `discussion`：觀點討論類，分享想法和見解
   - `interview`：訪談類，對話形式

3. **提煉核心主題（2-4 個）**
   - **按知識邏輯組織**，而非按時間順序
   - 一個主題可能跨越影片的多個時間段（前後呼應同一概念）
   - 每個主題要有清晰的「故事線」：是什麼 → 為什麼重要 → 怎麼運作
   - 主題之間要有邏輯關聯和過渡

4. **決定截圖時間點**（只在有視覺價值時截）
   - 有圖表、投影片、視覺化內容時：截圖
   - 純對話、訪談段：少截或不截
   - 關鍵操作步驟時：截圖作為操作參考
   - 不再要求每段都有截圖，總計通常 5-15 張

5. **如果是教學/演示類影片** → 額外整理實戰操作步驟
   - 提取可直接照做的 step-by-step
   - 每個步驟搭配截圖時間點

6. **提煉關鍵金句和 insight**
   - 從字幕中找出值得引用的原文金句
   - 提煉對讀者有啟發的思考問題

7. **輸出 JSON 結構**
   ```json
   {
     "video_type": "tutorial | discussion | demo | interview",
     "tldr": ["收穫1", "收穫2", "收穫3"],
     "topics": [
       {
         "title": "主題標題",
         "narrative": "這個主題要講述的故事/邏輯（給 AI 生成筆記用的大綱）",
         "related_timestamps": ["00:01:00-00:03:00", "00:07:00-00:08:00"],
         "screenshots": [
           {"timestamp": "00:02:30", "label": "描述性標籤", "description": "截圖內容描述"}
         ]
       }
     ],
     "action_steps": [
       {"step": "步驟描述", "screenshot_timestamp": "00:06:00"}
     ],
     "key_quotes": ["金句1", "金句2"],
     "thinking_questions": ["問題1", "問題2"],
     "related_topics": ["延伸1", "延伸2"]
   }
   ```

   **注意**：
   - `related_timestamps` 是陣列，因為一個主題可能跨越影片多個時間段
   - `action_steps` 只有教學/演示類影片才需要填寫，其他類型留空陣列
   - `tldr` 是「學到了什麼」而非「影片講了什麼」

---

### 階段 5: 截圖擷取

**目標**: 根據 AI 分析結果批次截圖

1. 從 AI 分析結果提取截圖設定

2. **先將截圖設定寫入臨時 JSON 檔案**（避免 shell 引號轉義問題）
   ```bash
   # 用 Write 工具寫入 JSON 檔案
   # 然後呼叫腳本
   python3 ~/.claude/skills/youtube-note/scripts/capture_screenshots.py <video_path> \
     --config <output_dir>/screenshots_config.json \
     --output_dir <output_dir>/screenshots/
   ```

3. 驗證截圖結果，刪除臨時的 `screenshots_config.json`

**輸出**: `screenshots/` 目錄下的 `.jpg` 檔案

---

### 階段 6: 生成筆記 + 清理

**目標**: 使用 Write 工具生成主題導向的 Markdown 學習筆記

1. **生成 note.md**
   - 參考 `~/.claude/skills/youtube-note/templates/note-template.md` 結構
   - 根據階段 4 的分析結果，按主題邏輯組織內容
   - **不要逐段摘要**，要像寫技術文章一樣組織

2. **筆記撰寫原則**：
   - **TL;DR 開頭**：3-5 個 bullet points，寫「學到了什麼」而非「影片講了什麼」
   - **核心概念區**：按主題而非時間組織，每個主題用自然段落展開
   - **主題之間要有過渡**：說明邏輯關聯，為什麼 A 引出了 B
   - **截圖穿插在文中**：作為說明的視覺輔助，不是段落開頭硬放
   - **實戰操作區是選填的**：只有教學/演示類影片（`video_type` 為 `tutorial` 或 `demo`）才需要
   - **雙語策略**：中文為主要敘述語言，英文只在引用原文金句時使用（用 blockquote 格式）
   - **關鍵收穫與反思區**：提煉 insight、思考問題、延伸閱讀

3. **自動清理**
   - 刪除 .mp4 影片檔（截圖已擷取，不再需要）
   - 刪除 .wav 音軌檔（如果有的話）
   - 刪除臨時 JSON 設定檔（如果有的話）
   ```bash
   rm -f <output_dir>/*.mp4 <output_dir>/*.wav <output_dir>/screenshots_config.json
   ```

4. **展示結果**
   ```
   ✅ 筆記生成完成！

   📁 輸出目錄: ./youtube-notes/<title>/
   📝 筆記: note.md
   📸 截圖: screenshots/ (X 張)
   📄 字幕: subtitles/transcript.json

   快速開啟:
   open ./youtube-notes/<title>/note.md
   ```

---

## 流程圖

```
URL → 嘗試 youtube-transcript-api
       ├── 成功 → 下載影片（僅截圖用）→ AI 分析 → 截圖 → 生成筆記 → 刪影片
       └── 失敗 → yt-dlp 字幕
                   ├── 成功 → 下載影片（僅截圖用）→ AI 分析 → 截圖 → 生成筆記 → 刪影片
                   └── 失敗 → Deepgram（自動下載音軌辨識）
                               ├── 成功 → 下載影片（僅截圖用）→ AI 分析 → 截圖 → 生成筆記 → 刪影片
                               └── 失敗 → 手動下載 → extract_audio → Deepgram
```

---

## 錯誤處理

### 環境問題
- 缺少工具 → 提示安裝命令
- Python 依賴缺失 → 提示 pip install

### 字幕問題
- 三層 fallback 全部失敗 → 告知用戶，詢問是否手動提供字幕檔
- Deepgram API key 未設定 → 提示在 `~/.claude/skills/youtube-note/.env` 設定
- Deepgram API 額度耗盡 → 告知用戶檢查 Deepgram 帳戶

### 下載問題
- 無效 URL → 提示檢查 URL 格式
- 網路錯誤 → 提示重試
- 影片不可用（地區限制、私人影片）→ 告知用戶

### 截圖問題
- FFmpeg 執行失敗 → 顯示詳細錯誤，嘗試跳過該截圖繼續
- 截圖全部失敗 → 生成筆記但不含截圖

---

## 筆記品質要點

1. **主題導向**: 按知識邏輯組織，不按時間順序，像技術文章一樣有邏輯流
2. **截圖有意義**: 穿插在文中作為視覺輔助，只在有視覺價值時放，不是每段硬塞
3. **自然敘述**: 用段落式寫作展開概念，不要填表格式的重複結構
4. **主題關聯**: 主題之間有過渡語，說明知識之間的邏輯關聯
5. **雙語策略**: 中文為主要敘述語言，英文只在引用原文金句時使用（blockquote 格式）
6. **深度提煉**: 不只是「影片說了什麼」，還要提煉「為什麼重要」和「怎麼用」
7. **可操作**: 教學類影片整理 step-by-step，思考問題引導深入學習

---

## 開始執行

當用戶觸發這個 Skill 時：
1. 立即開始階段 1（環境檢測）
2. 按照 6 個階段順序執行
3. 每個階段完成後自動進入下一階段
4. 遇到問題時提供清晰的解決方案
5. 最後展示完整的輸出結果

記住：這個 Skill 的核心價值在於 **AI 語義分析生成高品質雙語筆記** 和 **智慧截圖**，讓用戶能從長影片中快速獲取結構化知識。
