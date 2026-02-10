#!/usr/bin/env python3
"""
共用工具函數
提供時間格式轉換、檔案名清理、路徑處理等功能
複用自 Youtube-clipper-skill，並針對 youtube-note 擴充
"""

from __future__ import annotations

import re
import os
from pathlib import Path
from typing import Optional, Union
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse


def time_to_seconds(time_str: str) -> float:
    """
    將時間字串轉換為秒數

    支持格式:
    - HH:MM:SS.mmm
    - MM:SS.mmm
    - SS.mmm

    Examples:
        >>> time_to_seconds("01:23:45.678")
        5025.678
        >>> time_to_seconds("23:45.678")
        1425.678
        >>> time_to_seconds("45.678")
        45.678
    """
    if not time_str or not isinstance(time_str, str):
        raise ValueError(f"Invalid time string: {time_str!r}")

    time_str = time_str.strip()
    if not time_str:
        raise ValueError("Time string cannot be empty")

    parts = time_str.split(':')
    if len(parts) > 3:
        raise ValueError(f"Invalid time format (too many colons): {time_str!r}")

    try:
        if len(parts) == 3:
            hours, minutes, seconds = parts
            return int(hours) * 3600 + int(minutes) * 60 + float(seconds)
        elif len(parts) == 2:
            minutes, seconds = parts
            return int(minutes) * 60 + float(seconds)
        else:
            return float(parts[0])
    except ValueError:
        raise ValueError(f"Invalid time format: {time_str!r}")


def seconds_to_time(seconds: float, include_hours: bool = True, use_comma: bool = False) -> str:
    """
    將秒數轉換為時間字串

    Examples:
        >>> seconds_to_time(5025.678)
        '01:23:45.678'
        >>> seconds_to_time(1425.678, include_hours=False)
        '23:45.678'
    """
    if seconds < 0:
        raise ValueError(f"Seconds must be non-negative, got {seconds}")

    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = seconds % 60

    separator = ',' if use_comma else '.'

    if include_hours or hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:06.3f}".replace('.', separator)
    else:
        return f"{minutes:02d}:{secs:06.3f}".replace('.', separator)


def sanitize_filename(filename: str, max_length: int = 100) -> str:
    """
    清理檔案名，移除非法字元

    Examples:
        >>> sanitize_filename("Hello: World?")
        'Hello_World'
    """
    if not filename or not isinstance(filename, str):
        return "untitled"

    illegal_chars = r'[<>:"/\\|?*]'
    filename = re.sub(illegal_chars, '_', filename)
    filename = filename.strip('. ')
    filename = filename.replace(' ', '_')
    filename = re.sub(r'_+', '_', filename)
    filename = filename.strip('_')

    if not filename:
        return "untitled"

    if len(filename) > max_length:
        name, ext = os.path.splitext(filename)
        if ext:
            max_name_length = max_length - len(ext)
            filename = name[:max_name_length] + ext
        else:
            filename = filename[:max_length]

    return filename


def format_file_size(size_bytes: Union[int, float, None]) -> str:
    """
    格式化檔案大小為可讀格式

    Examples:
        >>> format_file_size(1048576)
        '1.0 MB'
    """
    if size_bytes is None or size_bytes < 0:
        return "0.0 B"

    size = float(size_bytes)
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size < 1024.0:
            return f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{size:.1f} PB"


def get_video_duration_display(seconds: float) -> str:
    """
    取得影片時長的顯示格式

    Examples:
        >>> get_video_duration_display(125.5)
        '02:05'
        >>> get_video_duration_display(3725.5)
        '1:02:05'
    """
    if seconds < 0:
        seconds = 0

    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)

    if hours > 0:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    else:
        return f"{minutes:02d}:{secs:02d}"


def validate_url(url: str) -> bool:
    """
    驗證 YouTube URL 格式

    Examples:
        >>> validate_url("https://youtube.com/watch?v=Ckt1cj0xjRM")
        True
        >>> validate_url("https://youtu.be/Ckt1cj0xjRM")
        True
        >>> validate_url("https://youtube.com/watch?v=abc123&list=PLabc")
        True
        >>> validate_url("invalid_url")
        False
    """
    if not url or not isinstance(url, str):
        return False

    try:
        parsed = urlparse(url)
    except Exception:
        return False

    if parsed.scheme not in ('http', 'https'):
        return False

    hostname = parsed.hostname or ''

    if hostname in ('youtube.com', 'www.youtube.com'):
        if parsed.path == '/watch':
            params = parse_qs(parsed.query)
            v_list = params.get('v', [])
            return bool(v_list and re.match(r'^[\w-]{11}$', v_list[0]))
        if re.match(r'^/embed/[\w-]{11}$', parsed.path):
            return True
        if re.match(r'^/shorts/[\w-]{11}$', parsed.path):
            return True
    elif hostname in ('youtu.be', 'www.youtu.be'):
        if re.match(r'^/[\w-]{11}$', parsed.path):
            return True

    return False


def ensure_directory(path: Union[str, Path]) -> Path:
    """確保目錄存在，不存在則建立"""
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def extract_video_id(url: str) -> str:
    """
    從 YouTube URL 提取影片 ID

    Examples:
        >>> extract_video_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        'dQw4w9WgXcQ'
        >>> extract_video_id("https://youtu.be/dQw4w9WgXcQ")
        'dQw4w9WgXcQ'
        >>> extract_video_id("https://youtube.com/shorts/dQw4w9WgXcQ")
        'dQw4w9WgXcQ'
    """
    match = re.search(
        r'(?:v=|/v/|youtu\.be/|/embed/|/shorts/)([a-zA-Z0-9_-]{11})',
        url
    )
    if match:
        return match.group(1)
    raise ValueError(f"Cannot extract video ID from URL: {url}")


def create_note_output_dir(title: str, base_dir: Optional[Union[str, Path]] = None) -> Path:
    """
    建立筆記輸出目錄

    Args:
        title: 影片標題（用於資料夾命名）
        base_dir: 基礎目錄，預設為當前工作目錄下的 youtube-notes

    Returns:
        Path: 輸出目錄路徑
    """
    if base_dir is None:
        base_dir = Path.cwd() / "youtube-notes"
    else:
        base_dir = Path(base_dir)

    dir_name = sanitize_filename(title)
    output_dir = base_dir / dir_name
    output_dir.mkdir(parents=True, exist_ok=True)

    # 建立子目錄
    (output_dir / "screenshots").mkdir(exist_ok=True)
    (output_dir / "subtitles").mkdir(exist_ok=True)

    return output_dir


def format_timestamp_link(seconds: float, video_url: str) -> str:
    """
    生成帶時間戳的 YouTube 連結（會覆寫而非重複附加 t 參數）

    Examples:
        >>> format_timestamp_link(125.5, "https://youtube.com/watch?v=abc123")
        'https://youtube.com/watch?v=abc123&t=125s'
    """
    if seconds < 0:
        seconds = 0

    t = int(seconds)
    parsed = urlparse(video_url)
    params = parse_qs(parsed.query)
    params['t'] = [f"{t}s"]
    new_query = urlencode(params, doseq=True)
    return urlunparse(parsed._replace(query=new_query))


if __name__ == "__main__":
    print("Testing utils.py...")

    assert abs(time_to_seconds("01:23:45.678") - 5025.678) < 0.001
    assert abs(time_to_seconds("23:45.678") - 1425.678) < 0.001
    assert abs(time_to_seconds("45.678") - 45.678) < 0.001

    assert sanitize_filename("Hello: World?") == "Hello_World"
    assert sanitize_filename("") == "untitled"
    assert sanitize_filename("???") == "untitled"

    assert validate_url("https://youtube.com/watch?v=Ckt1cj0xjRM") == True
    assert validate_url("https://youtu.be/Ckt1cj0xjRM") == True
    assert validate_url("https://youtube.com/watch?v=abc12345678&list=PLabc") == True
    assert validate_url("invalid_url") == False

    assert extract_video_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ") == "dQw4w9WgXcQ"
    assert extract_video_id("https://youtu.be/dQw4w9WgXcQ") == "dQw4w9WgXcQ"
    assert extract_video_id("https://youtube.com/shorts/dQw4w9WgXcQ") == "dQw4w9WgXcQ"

    assert "t=125s" in format_timestamp_link(125.5, "https://youtube.com/watch?v=abc12345678")

    print("All tests passed!")
