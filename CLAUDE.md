# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

YouTube 影片學習筆記生成工具（Claude Skill）。給一個 YouTube 連結，自動取得字幕、截圖，AI 語義分析後產出**主題導向**的結構化學習筆記。

## Architecture

**核心設計：計算任務（Python 腳本）與認知任務（Claude AI 分析）分離。**

腳本只做資料處理並輸出到 stdout，Claude 負責語義分析、決策和檔案寫入。

### 6 階段工作流（定義在 SKILL.md）

1. **環境檢測** → 2. **字幕取得**（三層 fallback）→ 3. **下載影片**（僅截圖用）→ 4. **AI 語義分析** → 5. **截圖擷取** → 6. **生成筆記 + 清理**

腳本輸出 JSON 到 stdout，Claude 用 Write 工具存檔。最終保留：`note.md` + `screenshots/` + `subtitles/`。

### 腳本職責

| 腳本 | 用途 | 關鍵細節 |
|------|------|----------|
| `scripts/get_transcript.py` | 三層 fallback 取字幕 | 支援 youtube-transcript-api v0.x/v1.x，Deepgram Nova-2 |
| `scripts/download_video.py` | yt-dlp 下載影片 | 有格式 fallback 避免 HTTP 403（YouTube SABR 問題）|
| `scripts/capture_screenshots.py` | FFmpeg 批次截圖 | 透過 `--config` JSON 檔傳入設定，避免 shell 引號問題 |
| `scripts/extract_audio.py` | 從影片提取音軌 | 16kHz mono WAV，為 Deepgram 優化 |
| `scripts/utils.py` | 共用工具函式 | URL 驗證、時間轉換、檔名清理、目錄建立 |

## Commands

### 安裝為 Claude Skill
```bash
bash install_as_skill.sh
```
安裝到 `~/.claude/skills/youtube-note/`，不會覆蓋已存在的 `.env`。

### 呼叫腳本（安裝後）
```bash
python3 ~/.claude/skills/youtube-note/scripts/get_transcript.py <youtube_url>
python3 ~/.claude/skills/youtube-note/scripts/download_video.py <youtube_url> <output_dir>
python3 ~/.claude/skills/youtube-note/scripts/capture_screenshots.py <video_path> --config <config.json> --output_dir <dir>
python3 ~/.claude/skills/youtube-note/scripts/extract_audio.py <video.mp4>
```

### 開發環境依賴
```bash
pip install yt-dlp youtube-transcript-api deepgram-sdk python-dotenv
brew install yt-dlp ffmpeg
```

## Key Design Decisions

- **字幕優先策略**：先嘗試免費方法（youtube-transcript-api → yt-dlp），最後才用付費的 Deepgram
- **主題導向筆記**：按知識邏輯組織，不按時間順序。一個主題可跨越影片多個時間段（`related_timestamps` 是陣列）
- **截圖只在有視覺價值時擷取**，穿插在筆記文中作為輔助，不是每段硬塞
- **雙語策略**：中文為主要敘述語言，英文只在引用原文金句時使用（blockquote 格式）
- **實戰操作區是選填的**：只有 `video_type` 為 `tutorial` 或 `demo` 的影片才需要
- **路徑隔離**：腳本用絕對路徑呼叫，輸出到使用者的工作目錄，不要 cd 到 skill 目錄
- **目錄結構對齊 Skill 最佳實踐**：`scripts/`（可執行腳本）、`assets/`（輸出模板）、`references/`（參考文檔）

## Output Structure

```
youtube-notes/<video_title>/
├── note.md                ← 主要交付物
├── screenshots/*.jpg      ← 5-15 張關鍵截圖
└── subtitles/transcript.json
```

暫存檔（.mp4、.wav、screenshots_config.json）在階段 6 自動清理。
