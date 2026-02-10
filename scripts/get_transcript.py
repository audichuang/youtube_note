#!/usr/bin/env python3
"""
字幕取得腳本（三層 fallback）
1. youtube-transcript-api（最快，免下載影片）
2. yt-dlp 字幕下載（解析已下載的 VTT 字幕檔）
3. Deepgram API 語音辨識（從影片音軌生成逐字稿）
"""

from __future__ import annotations

import sys
import os
import re
import json
import argparse
from typing import Optional, List, Dict, Any

# 將 scripts 目錄加入 path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils import extract_video_id, validate_url, time_to_seconds


def get_transcript(video_url_or_id: str, language: str = 'en',
                   subtitle_file: Optional[str] = None,
                   audio_file: Optional[str] = None,
                   video_path: Optional[str] = None) -> Dict[str, Any]:
    """
    三層 fallback 取得字幕

    Args:
        video_url_or_id: YouTube URL 或影片 ID
        language: 字幕語言
        subtitle_file: 已下載的字幕檔路徑（跳過第 1 層）
        audio_file: 音軌檔路徑（直接用 Deepgram）
        video_path: 已下載的影片路徑（第 3 層從影片提取音軌再送 Deepgram）

    Returns:
        dict: {
            "source": "youtube-api" | "yt-dlp" | "deepgram",
            "subtitles": [{"start": 0.0, "end": 3.5, "text": "..."}],
            "subtitle_count": int,
            "total_duration": float,
            "language": str
        }
    """
    # 如果提供音軌檔，直接用 Deepgram
    if audio_file:
        print("🎤 使用 Deepgram API 語音辨識...")
        result = _try_deepgram(audio_file, language)
        if result:
            return result
        raise RuntimeError("Deepgram 語音辨識失敗")

    # 如果提供字幕檔，直接解析
    if subtitle_file:
        print(f"📄 解析字幕檔: {subtitle_file}")
        result = _try_ytdlp_subtitles(subtitle_file, language)
        if result:
            return result
        raise RuntimeError(f"無法解析字幕檔: {subtitle_file}")

    # 需要 video_url_or_id 才能進行三層 fallback
    if not video_url_or_id:
        raise ValueError("未提供影片 URL 或 ID")

    # 提取影片 ID
    if validate_url(video_url_or_id):
        video_id = extract_video_id(video_url_or_id)
    else:
        # 驗證看起來像是 video ID
        if not re.match(r'^[a-zA-Z0-9_-]{11}$', video_url_or_id):
            raise ValueError(f"無效的影片 URL 或 ID: {video_url_or_id}")
        video_id = video_url_or_id

    print(f"🔍 影片 ID: {video_id}")

    # 第 1 層：youtube-transcript-api
    print("\n--- 第 1 層：youtube-transcript-api ---")
    result = _try_youtube_transcript_api(video_id, language)
    if result:
        print(f"✅ 成功取得字幕（youtube-transcript-api）: {result['subtitle_count']} 條")
        return result

    # 第 2 層：yt-dlp 字幕下載
    print("\n--- 第 2 層：yt-dlp 字幕下載 ---")
    result = _try_ytdlp_download_subtitles(video_id, language)
    if result:
        print(f"✅ 成功取得字幕（yt-dlp）: {result['subtitle_count']} 條")
        return result

    # 第 3 層：Deepgram API（需要已下載的影片或音軌）
    print("\n--- 第 3 層：Deepgram API 語音辨識 ---")

    if video_path and os.path.exists(video_path):
        print(f"🎬 使用已下載的影片提取音軌: {os.path.basename(video_path)}")
        result = _try_deepgram_from_video(video_path, language)
        if result:
            print(f"✅ 成功取得字幕（Deepgram）: {result['subtitle_count']} 條")
            return result

    raise RuntimeError(
        "所有字幕取得方式均失敗。\n"
        "建議：\n"
        "1. 確認影片 URL 是否正確\n"
        "2. 確認 DEEPGRAM_API_KEY 是否已設定\n"
        "3. 先下載影片後傳入 --video_path，或用 extract_audio.py 提取音軌再用 --audio_file"
    )


def _try_youtube_transcript_api(video_id: str, language: str) -> Optional[Dict[str, Any]]:
    """第 1 層：用 youtube-transcript-api 直接抓字幕（相容 v0.x 和 v1.x）"""
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
    except ImportError:
        print("⚠️  youtube-transcript-api 未安裝，跳過第 1 層")
        print("   安裝方式: pip install youtube-transcript-api")
        return None

    try:
        # 嘗試 v1.x API（實例方法）
        try:
            ytt_api = YouTubeTranscriptApi()
            transcript = ytt_api.fetch(video_id, languages=[language])

            subtitles = []
            for snippet in transcript.snippets:
                start = snippet.start
                duration = snippet.duration
                subtitles.append({
                    "start": round(start, 3),
                    "end": round(start + duration, 3),
                    "text": snippet.text.strip()
                })
        except (TypeError, AttributeError):
            # v0.x fallback（靜態方法）
            transcript = YouTubeTranscriptApi.get_transcript(
                video_id, languages=[language]
            )
            subtitles = []
            for entry in transcript:
                start = entry['start']
                duration = entry.get('duration', 0)
                subtitles.append({
                    "start": round(start, 3),
                    "end": round(start + duration, 3),
                    "text": entry['text'].strip()
                })

        if not subtitles:
            return None

        total_duration = subtitles[-1]['end']

        return {
            "source": "youtube-api",
            "subtitles": subtitles,
            "subtitle_count": len(subtitles),
            "total_duration": round(total_duration, 3),
            "language": language
        }

    except Exception as e:
        print(f"⚠️  youtube-transcript-api 失敗: {e}")
        return None


def _try_ytdlp_download_subtitles(video_id: str, language: str) -> Optional[Dict[str, Any]]:
    """第 2 層：用 yt-dlp 下載字幕並解析"""
    try:
        import yt_dlp
    except ImportError:
        print("⚠️  yt-dlp 未安裝，跳過第 2 層")
        return None

    import tempfile

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            # 只下載使用者指定語言 + en 作為通用 fallback
            langs = [language] if language == 'en' else [language, 'en']

            ydl_opts = {
                'writesubtitles': True,
                'writeautomaticsub': True,
                'subtitleslangs': langs,
                'subtitlesformat': 'vtt',
                'skip_download': True,
                'outtmpl': os.path.join(tmpdir, '%(id)s.%(ext)s'),
                'quiet': True,
                'no_warnings': True,
            }

            url = f"https://www.youtube.com/watch?v={video_id}"

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])

            # 尋找下載的字幕檔
            vtt_files = [f for f in os.listdir(tmpdir) if f.endswith('.vtt')]
            if not vtt_files:
                print("⚠️  yt-dlp 未下載到字幕檔")
                return None

            # 優先選擇指定語言的字幕
            target_file = None
            for vtt in vtt_files:
                if f'.{language}.' in vtt:
                    target_file = vtt
                    break
            if not target_file:
                target_file = vtt_files[0]

            subtitle_path = os.path.join(tmpdir, target_file)
            return _try_ytdlp_subtitles(subtitle_path, language)

    except Exception as e:
        print(f"⚠️  yt-dlp 字幕下載失敗: {e}")
        return None


def _try_ytdlp_subtitles(subtitle_path: str, language: str = "en") -> Optional[Dict[str, Any]]:
    """解析 VTT 字幕檔"""
    try:
        with open(subtitle_path, 'r', encoding='utf-8') as f:
            content = f.read()

        subtitles = _parse_vtt(content)

        if not subtitles:
            return None

        total_duration = subtitles[-1]['end']

        return {
            "source": "yt-dlp",
            "subtitles": subtitles,
            "subtitle_count": len(subtitles),
            "total_duration": round(total_duration, 3),
            "language": language
        }

    except Exception as e:
        print(f"⚠️  VTT 解析失敗: {e}")
        return None


def _parse_vtt(content: str) -> List[Dict[str, Any]]:
    """
    解析 VTT 字幕格式

    只移除相鄰重複（而非全域重複），避免誤刪合法的重複台詞。
    支援 HH:MM:SS.mmm 和 MM:SS.mmm 兩種時間戳格式。
    """
    subtitles: List[Dict[str, Any]] = []

    # VTT 時間戳正則：支援 HH:MM:SS.mmm 和 MM:SS.mmm
    timestamp_pattern = re.compile(
        r'(\d{1,2}(?::\d{2}){1,2}\.\d{1,3})\s*-->\s*(\d{1,2}(?::\d{2}){1,2}\.\d{1,3})'
    )

    lines = content.split('\n')
    i = 0
    while i < len(lines):
        match = timestamp_pattern.match(lines[i].strip())
        if match:
            start_str, end_str = match.groups()
            start = time_to_seconds(start_str)
            end = time_to_seconds(end_str)

            # 收集後續文字行
            text_lines = []
            i += 1
            while i < len(lines) and lines[i].strip() and not timestamp_pattern.match(lines[i].strip()):
                line = lines[i].strip()
                # 移除 VTT 標籤
                line = re.sub(r'<[^>]+>', '', line)
                if line:
                    text_lines.append(line)
                i += 1

            text = ' '.join(text_lines).strip()

            # 過濾空白和相鄰重複（而非全域重複）
            if text and (not subtitles or text != subtitles[-1]["text"]):
                subtitles.append({
                    "start": round(start, 3),
                    "end": round(end, 3),
                    "text": text
                })
        else:
            i += 1

    return subtitles


def _try_deepgram_from_video(video_path: str, language: str) -> Optional[Dict[str, Any]]:
    """第 3 層：從已下載的影片提取音軌，再用 Deepgram API 辨識"""
    # 先檢查 Deepgram SDK
    try:
        from deepgram import DeepgramClient
    except ImportError:
        print("⚠️  deepgram-sdk 未安裝，跳過第 3 層")
        print("   安裝方式: pip install deepgram-sdk")
        return None

    # 載入 API key
    api_key = _get_deepgram_api_key()
    if not api_key:
        print("⚠️  未設定 DEEPGRAM_API_KEY，跳過第 3 層")
        print("   請在 .env 檔案中設定 DEEPGRAM_API_KEY")
        return None

    if not os.path.exists(video_path):
        print(f"⚠️  影片檔不存在: {video_path}")
        return None

    import subprocess

    try:
        # 用 extract_audio 模組從影片提取音軌
        from extract_audio import extract_audio

        video_dir = os.path.dirname(video_path)
        video_stem = os.path.splitext(os.path.basename(video_path))[0]
        wav_path = os.path.join(video_dir, f"{video_stem}.wav")

        print("🔄 從影片提取音軌 (16kHz mono WAV)...")
        audio_result = extract_audio(video_path, wav_path)
        wav_path = audio_result['audio_path']

        result = _try_deepgram(wav_path, language)

        # 辨識完成後清理 WAV 檔
        if os.path.exists(wav_path):
            os.remove(wav_path)
            print(f"🗑️  已清理音軌檔: {os.path.basename(wav_path)}")

        return result

    except Exception as e:
        print(f"⚠️  Deepgram 路徑失敗: {e}")
        return None


def _try_deepgram(audio_path: str, language: str = 'en') -> Optional[Dict[str, Any]]:
    """用 Deepgram API 做語音辨識（相容 deepgram-sdk v3/v4）"""
    try:
        from deepgram import DeepgramClient, PrerecordedOptions
    except ImportError:
        print("⚠️  deepgram-sdk 未安裝")
        return None

    api_key = _get_deepgram_api_key()
    if not api_key:
        print("⚠️  未設定 DEEPGRAM_API_KEY")
        return None

    try:
        file_size = os.path.getsize(audio_path)
        print(f"🎤 Deepgram 辨識中: {os.path.basename(audio_path)} ({file_size // 1024 // 1024}MB)")

        from deepgram import DeepgramClientOptions
        config = DeepgramClientOptions(options={"keepalive": "true"})
        client = DeepgramClient(api_key, config)

        with open(audio_path, 'rb') as f:
            buffer_data = f.read()

        payload = {"buffer": buffer_data, "mimetype": "audio/wav"}

        options = PrerecordedOptions(
            model="nova-2",
            language=language,
            smart_format=True,
            punctuate=True,
            paragraphs=True,
            utterances=True,
            utt_split=0.8,
        )

        # v4: client.listen.rest, v3: client.listen.prerecorded
        import httpx
        listen = client.listen.rest
        response = listen.v("1").transcribe_file(
            payload, options,
            timeout=httpx.Timeout(300.0, connect=30.0, read=300.0, write=300.0, pool=300.0)
        )
        result = response.to_dict()

        # 解析 Deepgram 結果
        subtitles: List[Dict[str, Any]] = []

        # 優先使用 utterances（較自然的分段）
        utterances = result.get('results', {}).get('utterances', [])
        if utterances:
            for utt in utterances:
                subtitles.append({
                    "start": round(utt['start'], 3),
                    "end": round(utt['end'], 3),
                    "text": utt['transcript'].strip()
                })
        else:
            # 退回使用 words 手動分段
            channels = result.get('results', {}).get('channels', [])
            if channels:
                alternatives = channels[0].get('alternatives', [])
                if alternatives:
                    words = alternatives[0].get('words', [])
                    subtitles = _words_to_subtitles(words)

        if not subtitles:
            return None

        total_duration = subtitles[-1]['end']

        return {
            "source": "deepgram",
            "subtitles": subtitles,
            "subtitle_count": len(subtitles),
            "total_duration": round(total_duration, 3),
            "language": language
        }

    except Exception as e:
        error_msg = str(e)
        # 清除可能包含的 API key
        if api_key and api_key in error_msg:
            error_msg = error_msg.replace(api_key, "***")
        print(f"⚠️  Deepgram 辨識失敗: {error_msg}")
        return None


def _words_to_subtitles(words: List[Dict], max_words: int = 12, max_duration: float = 5.0) -> List[Dict[str, Any]]:
    """將 Deepgram word-level 結果分段為字幕"""
    subtitles: List[Dict[str, Any]] = []
    current_words: List[str] = []
    current_start: Optional[float] = None

    sentence_endings = ('.', '?', '!', '。', '？', '！')

    for word in words:
        if current_start is None:
            current_start = word['start']

        current_words.append(word['punctuated_word'])
        current_end = word['end']

        # 檢查是否應該結束這段
        duration = current_end - current_start
        pw = word['punctuated_word'].rstrip('"\'")>')
        if (len(current_words) >= max_words or
                duration >= max_duration or
                pw.endswith(sentence_endings)):
            subtitles.append({
                "start": round(current_start, 3),
                "end": round(current_end, 3),
                "text": ' '.join(current_words)
            })
            current_words = []
            current_start = None

    # 處理剩餘的文字
    if current_words and current_start is not None:
        subtitles.append({
            "start": round(current_start, 3),
            "end": round(words[-1]['end'], 3),
            "text": ' '.join(current_words)
        })

    return subtitles


def _get_deepgram_api_key() -> Optional[str]:
    """取得 Deepgram API key"""
    # 先檢查環境變數
    api_key = os.environ.get('DEEPGRAM_API_KEY')
    if api_key:
        return api_key

    # 嘗試從 .env 讀取
    try:
        from dotenv import load_dotenv

        # 搜尋 .env 檔案
        script_dir = os.path.dirname(os.path.abspath(__file__))
        project_dir = os.path.dirname(script_dir)

        for env_path in [
            os.path.join(project_dir, '.env'),
            os.path.join(os.path.expanduser('~'), '.claude', 'skills', 'youtube-note', '.env'),
        ]:
            if os.path.exists(env_path):
                load_dotenv(env_path)
                api_key = os.environ.get('DEEPGRAM_API_KEY')
                if api_key:
                    return api_key
    except ImportError:
        pass

    return None


def main():
    parser = argparse.ArgumentParser(description='取得 YouTube 影片字幕（三層 fallback）')
    parser.add_argument('video_url', nargs='?', help='YouTube URL 或影片 ID')
    parser.add_argument('--subtitle_file', help='已下載的字幕檔路徑')
    parser.add_argument('--audio_file', help='音軌檔路徑（直接用 Deepgram）')
    parser.add_argument('--video_path', help='已下載的影片路徑（第 3 層從影片提取音軌再送 Deepgram）')
    parser.add_argument('--language', default='en', help='字幕語言（預設: en）')

    args = parser.parse_args()

    if not args.video_url and not args.subtitle_file and not args.audio_file:
        parser.print_help()
        sys.exit(1)

    try:
        result = get_transcript(
            video_url_or_id=args.video_url or '',
            language=args.language,
            subtitle_file=args.subtitle_file,
            audio_file=args.audio_file,
            video_path=args.video_path
        )

        print("\n" + "=" * 60)
        print("字幕取得結果 (JSON):")
        print(json.dumps(result, indent=2, ensure_ascii=False))

    except Exception as e:
        print(f"\n❌ 錯誤: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
