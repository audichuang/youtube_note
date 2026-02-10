---
name: youtube-note
description: >
  Generates topic-driven bilingual learning notes from YouTube videos with key screenshots.
  Automatically fetches transcripts (3-layer fallback including Deepgram speech recognition),
  captures screenshots at visually valuable moments, and produces structured Markdown notes
  organized by knowledge logic rather than chronological order.
  Use when a user provides a YouTube link and wants study notes, video summaries,
  or learning materials. Triggers on: YouTube URL, video notes, study notes, 學習筆記, 影片筆記, 整理筆記.
allowed-tools:
  - Read
  - Write
  - Bash
  - AskUserQuestion
---

# YouTube 影片學習筆記生成工具

## 腳本路徑

所有腳本位於 `~/.claude/skills/youtube-note/scripts/`，始終使用絕對路徑呼叫：

```bash
python3 ~/.claude/skills/youtube-note/scripts/<script_name>.py <args>
```

輸出到使用者當前工作目錄下的 `youtube-notes/<title>/`。

## 工作流程

### 階段 1: 環境檢測

確認 `yt-dlp`、`ffmpeg`、`python3` 可用，以及 Python 套件 `yt_dlp`、`youtube_transcript_api`、`deepgram`、`dotenv` 已安裝。缺失時提示對應的 `brew install` 或 `pip install` 命令。

### 階段 2: 取得字幕

```bash
python3 ~/.claude/skills/youtube-note/scripts/get_transcript.py <youtube_url>
```

三層 fallback（腳本自動處理）：
1. youtube-transcript-api（秒級）
2. yt-dlp 字幕下載（秒級）
3. Deepgram 語音辨識（分鐘級，需 `DEEPGRAM_API_KEY`）

腳本輸出 JSON 到 stdout，用 Write 工具存到 `subtitles/transcript.json`。

**手動 fallback**（三層全失敗時）：
```bash
python3 ~/.claude/skills/youtube-note/scripts/download_video.py <url>
python3 ~/.claude/skills/youtube-note/scripts/extract_audio.py <video.mp4>
python3 ~/.claude/skills/youtube-note/scripts/get_transcript.py --audio_file <audio.wav>
```

### 階段 3: 下載影片

```bash
python3 ~/.claude/skills/youtube-note/scripts/download_video.py <youtube_url> <output_dir>
```

僅供截圖用，階段 6 自動刪除。輸出影片資訊 JSON 到 stdout。

### 階段 4: AI 語義分析

讀取 `subtitles/transcript.json`，執行深層分析：

1. **判斷影片類型**：`tutorial` | `demo` | `discussion` | `interview`
2. **提煉 2-4 個核心主題**——按知識邏輯組織，非時間順序。一個主題可跨越多個時間段
3. **決定截圖時間點**——只在有視覺價值時截（圖表、投影片、操作步驟），總計 5-15 張
4. **教學/演示類**額外整理 step-by-step 操作步驟
5. **提煉關鍵金句和思考問題**

輸出 JSON：

```json
{
  "video_type": "tutorial | discussion | demo | interview",
  "tldr": ["收穫1", "收穫2", "收穫3"],
  "topics": [
    {
      "title": "主題標題",
      "narrative": "大綱：是什麼 → 為什麼重要 → 怎麼運作",
      "related_timestamps": ["00:01:00-00:03:00", "00:07:00-00:08:00"],
      "screenshots": [
        {"timestamp": "00:02:30", "label": "描述性標籤", "description": "截圖內容"}
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

### 階段 5: 截圖擷取

將截圖設定寫入暫存 JSON 檔，再呼叫腳本：

```bash
python3 ~/.claude/skills/youtube-note/scripts/capture_screenshots.py <video_path> \
  --config <output_dir>/screenshots_config.json \
  --output_dir <output_dir>/screenshots/
```

### 階段 6: 生成筆記 + 清理

參考 `~/.claude/skills/youtube-note/assets/note-template.md` 結構，用 Write 工具生成 `note.md`。

**筆記撰寫原則：**

- **TL;DR 開頭**：3-5 個 bullet points，寫「學到了什麼」
- **核心概念區**：按主題組織，自然段落展開，主題之間有過渡語說明邏輯關聯
- **截圖穿插文中**作為視覺輔助，不是段落開頭硬放
- **實戰操作區（選填）**：僅 `tutorial` / `demo` 類型需要
- **雙語策略**：中文敘述為主，英文只在引用原文金句時使用（blockquote 格式）
- **關鍵收穫與反思**：insight、思考問題、延伸閱讀

**清理暫存檔：**
```bash
rm -f <output_dir>/*.mp4 <output_dir>/*.wav <output_dir>/screenshots_config.json
```

**完成後展示：**
```
✅ 筆記生成完成！
📁 輸出目錄: ./youtube-notes/<title>/
📝 筆記: note.md
📸 截圖: screenshots/ (X 張)
📄 字幕: subtitles/transcript.json
```
