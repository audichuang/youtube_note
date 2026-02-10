# FFmpeg 截圖指令參考

## 基本截圖

從影片擷取單張截圖：
```bash
ffmpeg -ss 00:02:45 -i video.mp4 -frames:v 1 -q:v 2 screenshot.jpg
```

參數說明：
- `-ss 00:02:45`：跳到指定時間點（放在 `-i` 前面是 seek 模式，更快）
- `-i video.mp4`：輸入影片
- `-frames:v 1`：只擷取 1 幀
- `-q:v 2`：JPEG 品質（2 是高品質，範圍 2-31，數字越小品質越高）
- `-y`：覆蓋已存在的檔案

## 品質選項

| -q:v 值 | 品質 | 檔案大小 | 適用場景 |
|---------|------|---------|---------|
| 2 | 最高 | 大 | 需要清晰細節的截圖 |
| 5 | 高 | 中 | 一般筆記截圖（推薦） |
| 10 | 中 | 小 | 快速預覽 |
| 20 | 低 | 極小 | 縮圖 |

## 批次截圖

方法 1：多次呼叫（本專案使用）
```bash
ffmpeg -ss 00:01:30 -i video.mp4 -frames:v 1 -q:v 2 screenshot_01.jpg
ffmpeg -ss 00:05:00 -i video.mp4 -frames:v 1 -q:v 2 screenshot_02.jpg
ffmpeg -ss 00:12:30 -i video.mp4 -frames:v 1 -q:v 2 screenshot_03.jpg
```

方法 2：固定間隔截圖（每 60 秒一張）
```bash
ffmpeg -i video.mp4 -vf "fps=1/60" -q:v 2 screenshots/frame_%04d.jpg
```

方法 3：場景變化截圖
```bash
ffmpeg -i video.mp4 -vf "select='gt(scene,0.4)'" -vsync vfr -q:v 2 screenshots/scene_%04d.jpg
```

## 提取音軌

給 Deepgram 使用的音軌提取：
```bash
ffmpeg -i video.mp4 -vn -acodec pcm_s16le -ar 16000 -ac 1 audio.wav
```

參數說明：
- `-vn`：不要影像軌
- `-acodec pcm_s16le`：16-bit PCM 編碼
- `-ar 16000`：16kHz 取樣率（Deepgram 建議）
- `-ac 1`：單聲道（節省頻寬和處理時間）

## 取得影片時長

```bash
ffprobe -v quiet -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 video.mp4
```

## 注意事項

1. `-ss` 放在 `-i` 前面（input seeking）比放在後面（output seeking）快很多
2. 使用 `-frames:v 1` 而非 `-vframes 1`（後者已過時）
3. JPEG 品質 2 對筆記截圖來說足夠，不需要 PNG
4. 本專案不需要 ffmpeg-full（不燒錄字幕），標準 FFmpeg 即可
