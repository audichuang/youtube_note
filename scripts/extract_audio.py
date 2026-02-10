#!/usr/bin/env python3
"""
從影片中提取音軌
供 Deepgram 語音辨識使用
輸出格式: 16kHz, mono, WAV（Deepgram 建議）
"""

from __future__ import annotations

import sys
import os
import json
import shutil
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils import format_file_size


def extract_audio(video_path: str, output_path: Optional[str] = None) -> Dict[str, Any]:
    """
    從影片提取音軌

    Args:
        video_path: 影片檔路徑
        output_path: 輸出音軌路徑，預設為同目錄下的 <stem>.wav

    Returns:
        dict: {'audio_path': str, 'file_size': int, 'duration': float}
    """
    # 檢查 FFmpeg
    if shutil.which('ffmpeg') is None:
        raise RuntimeError("ffmpeg 未安裝。請執行: brew install ffmpeg")

    video = Path(video_path)

    if not video.exists():
        raise FileNotFoundError(f"影片檔不存在: {video}")

    if output_path is None:
        out = video.parent / f"{video.stem}.wav"
    else:
        out = Path(output_path)

    print("🎵 提取音軌...")
    print(f"   來源: {video.name}")
    print(f"   輸出: {out}")

    # 使用 FFmpeg 提取音軌
    cmd = [
        'ffmpeg', '-i', str(video),
        '-vn',
        '-acodec', 'pcm_s16le',
        '-ar', '16000',
        '-ac', '1',
        '-y',
        str(out)
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600
        )

        if result.returncode != 0:
            raise RuntimeError(f"FFmpeg 失敗: {result.stderr[-500:]}")

        if not out.exists():
            raise RuntimeError("音軌檔未生成")

        file_size = out.stat().st_size
        duration = _get_audio_duration(str(out))

        print("✅ 音軌提取完成")
        print(f"   大小: {format_file_size(file_size)}")
        print(f"   格式: WAV 16kHz mono")

        return {
            'audio_path': str(out),
            'file_size': file_size,
            'duration': duration
        }

    except subprocess.TimeoutExpired:
        # 清理不完整的輸出檔
        if out.exists():
            out.unlink()
        raise RuntimeError("FFmpeg 執行逾時（超過 10 分鐘）")


def _get_audio_duration(audio_path: str) -> float:
    """取得音軌時長"""
    try:
        result = subprocess.run(
            ['ffprobe', '-v', 'quiet', '-show_entries', 'format=duration',
             '-of', 'default=noprint_wrappers=1:nokey=1', audio_path],
            capture_output=True, text=True, timeout=30
        )
        output = result.stdout.strip()
        if output:
            return float(output)
        return 0.0
    except Exception:
        return 0.0


def main():
    if len(sys.argv) < 2:
        print("Usage: python extract_audio.py <video_path> [output.wav]")
        print("\nExample:")
        print("  python extract_audio.py video.mp4")
        print("  python extract_audio.py video.mp4 audio.wav")
        sys.exit(1)

    video_path = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else None

    try:
        result = extract_audio(video_path, output_path)

        print("\n" + "=" * 60)
        print("音軌提取結果 (JSON):")
        print(json.dumps(result, indent=2, ensure_ascii=False))

    except Exception as e:
        print(f"\n❌ 錯誤: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
