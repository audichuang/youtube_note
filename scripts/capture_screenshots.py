#!/usr/bin/env python3
"""
批次截圖腳本
使用 FFmpeg 從影片中擷取關鍵畫面
"""

from __future__ import annotations

import sys
import os
import json
import argparse
import shutil
import subprocess
from pathlib import Path
from typing import List, Dict, Any

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils import format_file_size, ensure_directory, sanitize_filename


def capture_screenshot(video_path: str, timestamp: str, output_path: str) -> Dict[str, Any]:
    """
    從影片擷取單張截圖

    Args:
        video_path: 影片檔路徑
        timestamp: 時間戳（格式: HH:MM:SS 或 MM:SS 或秒數）
        output_path: 輸出截圖路徑

    Returns:
        dict: {'path': str, 'timestamp': str, 'success': bool, 'file_size': int}
    """
    video = Path(video_path)
    out = Path(output_path)

    if not video.exists():
        return {'path': str(out), 'timestamp': timestamp, 'success': False, 'error': 'Video not found'}

    # 確保輸出目錄存在
    out.parent.mkdir(parents=True, exist_ok=True)

    # ffmpeg -ss <timestamp> -i <video> -frames:v 1 -q:v 2 <output.jpg>
    cmd = [
        'ffmpeg',
        '-ss', str(timestamp),
        '-i', str(video),
        '-frames:v', '1',
        '-q:v', '2',
        '-y',
        str(out)
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode != 0:
            return {
                'path': str(out),
                'timestamp': timestamp,
                'success': False,
                'error': f'FFmpeg error: {result.stderr[:200]}'
            }

        if not out.exists():
            return {
                'path': str(out),
                'timestamp': timestamp,
                'success': False,
                'error': 'Screenshot file not created'
            }

        file_size = out.stat().st_size

        return {
            'path': str(out),
            'timestamp': timestamp,
            'success': True,
            'file_size': file_size
        }

    except subprocess.TimeoutExpired:
        # 清理不完整的輸出檔
        if out.exists():
            out.unlink()
        return {
            'path': str(out),
            'timestamp': timestamp,
            'success': False,
            'error': 'FFmpeg timeout'
        }


def batch_capture(video_path: str, screenshots_config: List[Dict[str, str]], output_dir: str) -> Dict[str, Any]:
    """
    批次擷取截圖

    Args:
        video_path: 影片檔路徑
        screenshots_config: 截圖設定列表
            [{"timestamp": "00:02:45", "label": "01_intro"}, ...]
        output_dir: 輸出目錄

    Returns:
        dict: {'total': int, 'success': int, 'failed': int, 'screenshots': [...]}
    """
    # 檢查 FFmpeg
    if shutil.which('ffmpeg') is None:
        raise RuntimeError("ffmpeg 未安裝。請執行: brew install ffmpeg")

    out_path = ensure_directory(Path(output_dir))

    print(f"📸 批次截圖: {len(screenshots_config)} 張")
    print(f"   影片: {Path(video_path).name}")
    print(f"   輸出: {out_path}")

    results: List[Dict[str, Any]] = []
    success_count = 0
    failed_count = 0

    for i, config in enumerate(screenshots_config):
        timestamp = config.get('timestamp', '0')
        label = config.get('label', f'{i+1:02d}_screenshot')

        # 用 sanitize_filename 清理 label
        label = sanitize_filename(label)

        screenshot_path = out_path / f"{label}.jpg"

        print(f"   [{i+1}/{len(screenshots_config)}] {timestamp} → {label}.jpg", end='')

        result = capture_screenshot(video_path, timestamp, str(screenshot_path))
        results.append(result)

        if result['success']:
            success_count += 1
            print(f" ✅ ({format_file_size(result['file_size'])})")
        else:
            failed_count += 1
            print(f" ❌ ({result.get('error', 'Unknown error')})")

    print(f"\n📊 截圖結果: {success_count} 成功, {failed_count} 失敗")

    return {
        'total': len(screenshots_config),
        'success': success_count,
        'failed': failed_count,
        'screenshots': results
    }


def main():
    parser = argparse.ArgumentParser(description='從影片批次擷取截圖')
    parser.add_argument('video_path', help='影片檔路徑')
    parser.add_argument('--config', required=True,
                        help='截圖設定 JSON 字串或檔案路徑')
    parser.add_argument('--output_dir', default='./screenshots/',
                        help='輸出目錄（預設: ./screenshots/）')

    args = parser.parse_args()

    # 解析設定
    config_str = args.config
    try:
        if os.path.isfile(config_str):
            with open(config_str, 'r') as f:
                screenshots_config = json.load(f)
        else:
            screenshots_config = json.loads(config_str)
    except json.JSONDecodeError as e:
        print(f"❌ JSON 格式錯誤: {e}")
        sys.exit(1)

    try:
        result = batch_capture(args.video_path, screenshots_config, args.output_dir)

        print("\n" + "=" * 60)
        print("截圖結果 (JSON):")
        print(json.dumps(result, indent=2, ensure_ascii=False))

    except Exception as e:
        print(f"\n❌ 錯誤: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
