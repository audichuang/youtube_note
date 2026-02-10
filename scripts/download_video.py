#!/usr/bin/env python3
"""
下載 YouTube 影片和字幕
使用 yt-dlp 下載影片（最高 1080p）和多語言字幕
"""

from __future__ import annotations

import sys
import os
import json
from pathlib import Path
from typing import Optional, Dict, Any

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    import yt_dlp
except ImportError:
    print("❌ Error: yt-dlp not installed")
    print("Please install: pip install yt-dlp")
    sys.exit(1)

from utils import (
    validate_url,
    format_file_size,
    get_video_duration_display,
    ensure_directory,
    create_note_output_dir
)


def download_video(url: str, output_dir: Optional[str] = None) -> Dict[str, Any]:
    """
    下載 YouTube 影片和字幕

    Args:
        url: YouTube URL
        output_dir: 輸出目錄，預設會用影片標題建立 youtube-notes/<title>/ 目錄

    Returns:
        dict: 包含影片路徑、字幕路徑、標題、時長等資訊
    """
    if not validate_url(url):
        raise ValueError(f"Invalid YouTube URL: {url}")

    # 先取得影片資訊以決定輸出目錄
    print("🎬 取得影片資訊...")
    try:
        with yt_dlp.YoutubeDL({'quiet': True, 'no_warnings': True}) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as e:
        raise RuntimeError(f"無法取得影片資訊: {e}")

    title = info.get('title', 'Unknown')
    duration = info.get('duration', 0)
    video_id = info.get('id', 'unknown')
    channel = info.get('channel', info.get('uploader', 'Unknown'))
    upload_date = info.get('upload_date', '')

    # 設定輸出目錄
    if output_dir is None:
        out_path = create_note_output_dir(title)
    else:
        out_path = ensure_directory(Path(output_dir))

    print(f"   標題: {title}")
    print(f"   頻道: {channel}")
    print(f"   時長: {get_video_duration_display(duration)}")
    print(f"   影片ID: {video_id}")
    print(f"   輸出目錄: {out_path}")

    # 格式優先順序：高畫質 → 低畫質 fallback（YouTube SABR 403 問題）
    formats_to_try = [
        'bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080][ext=mp4]/best[ext=mp4]/best',
        '18/best[ext=mp4]/best',  # format 18 = 360p mp4，通常不受 SABR 限制
    ]

    base_opts = {
        'extractor_args': {'youtube': {'player_client': ['default']}},
        'merge_output_format': 'mp4',
        'outtmpl': str(out_path / f'{video_id}.%(ext)s'),
        'writesubtitles': True,
        'writeautomaticsub': True,
        'subtitleslangs': ['en', 'zh-Hant', 'zh-Hans'],
        'subtitlesformat': 'vtt',
        'writethumbnail': False,
        'quiet': False,
        'no_warnings': False,
        'progress_hooks': [_progress_hook],
    }

    try:
        info = None
        for fmt_idx, fmt in enumerate(formats_to_try):
            try:
                ydl_opts = {**base_opts, 'format': fmt}
                print(f"\n📥 開始下載...{'（降級畫質重試）' if fmt_idx > 0 else ''}")
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                break  # 下載成功，跳出迴圈
            except Exception as e:
                if '403' in str(e) and fmt_idx < len(formats_to_try) - 1:
                    print(f"\n⚠️  高畫質格式下載失敗 (HTTP 403)，嘗試降級畫質...")
                    continue
                raise  # 最後一個格式也失敗，拋出例外

        if info is None:
            raise RuntimeError("下載失敗：所有格式均不可用")

        # 用 outtmpl 推算檔案路徑
        video_path = out_path / f'{video_id}.mp4'

        # 如果 .mp4 不存在，搜尋目錄下實際的影片檔
        if not video_path.exists():
            for f in out_path.iterdir():
                if f.name.startswith(video_id) and f.suffix in ('.mp4', '.mkv', '.webm'):
                    video_path = f
                    break

        if not video_path.exists():
            raise RuntimeError("Video file not found after download")

        file_size = video_path.stat().st_size

        # 尋找字幕檔
        subtitle_path = None
        for lang in ['en', 'zh-Hant', 'zh-Hans']:
            potential_sub = video_path.parent / f"{video_path.stem}.{lang}.vtt"
            if potential_sub.exists():
                subtitle_path = potential_sub
                break

        print(f"\n✅ 影片下載完成: {video_path.name}")
        print(f"   大小: {format_file_size(file_size)}")

        if subtitle_path and subtitle_path.exists():
            print(f"✅ 字幕下載完成: {subtitle_path.name}")
        else:
            print("⚠️  未找到字幕檔")

        # 格式化上傳日期
        formatted_date = ''
        if upload_date and len(upload_date) == 8:
            formatted_date = f"{upload_date[:4]}-{upload_date[4:6]}-{upload_date[6:8]}"

        return {
            'video_path': str(video_path),
            'subtitle_path': str(subtitle_path) if subtitle_path else None,
            'title': title,
            'duration': duration,
            'file_size': file_size,
            'video_id': video_id,
            'channel': channel,
            'upload_date': formatted_date,
            'url': url,
            'output_dir': str(out_path)
        }

    except Exception as e:
        print(f"\n❌ 下載失敗: {str(e)}")
        raise


def _progress_hook(d: dict) -> None:
    """下載進度回呼"""
    if d['status'] == 'downloading':
        total = d.get('total_bytes') or d.get('total_bytes_estimate')
        downloaded = d.get('downloaded_bytes', 0)
        speed = d.get('speed') or 0

        if total and downloaded:
            percent = downloaded / total * 100
            downloaded_str = format_file_size(downloaded)
            total_str = format_file_size(total)
            speed_str = format_file_size(speed) + '/s' if speed else 'N/A'

            bar_length = 30
            filled = int(bar_length * percent / 100)
            bar = '█' * filled + '░' * (bar_length - filled)

            print(f"\r   [{bar}] {percent:.1f}% - {downloaded_str}/{total_str} - {speed_str}", end='', flush=True)
        elif downloaded:
            downloaded_str = format_file_size(downloaded)
            speed_str = format_file_size(speed) + '/s' if speed else 'N/A'
            print(f"\r   下載中... {downloaded_str} - {speed_str}", end='', flush=True)

    elif d['status'] == 'finished':
        print()


def main():
    if len(sys.argv) < 2:
        print("Usage: python download_video.py <youtube_url> [output_dir]")
        print("\nExample:")
        print("  python download_video.py https://youtube.com/watch?v=Ckt1cj0xjRM")
        print("  python download_video.py https://youtube.com/watch?v=Ckt1cj0xjRM ~/Downloads")
        sys.exit(1)

    url = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else None

    try:
        result = download_video(url, output_dir)

        print("\n" + "=" * 60)
        print("下載結果 (JSON):")
        print(json.dumps(result, indent=2, ensure_ascii=False))

    except Exception as e:
        print(f"\n❌ 錯誤: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
