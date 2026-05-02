#!/usr/bin/env python3
"""
UTAGE HLS動画ダウンローダー

UTAGE/Wasabi S3のHLS動画をダウンロードする専用スクリプト。
高速なHTTP persistent接続を使用。

Usage:
    python hls_downloader.py <m3u8_url> <output_path>

Example:
    python hls_downloader.py "https://s3.ap-northeast-1.wasabisys.com/.../video.m3u8" "videos/01_intro.mp4"
"""

import subprocess
import sys
import shutil
from pathlib import Path
from typing import Optional


def download_hls_video(
    m3u8_url: str,
    output_path: str,
    timeout: int = 600
) -> bool:
    """
    UTAGE/Wasabi S3向けのHLS動画ダウンロード

    Args:
        m3u8_url: HLSプレイリストのURL（.m3u8）
        output_path: 出力先MP4ファイルパス
        timeout: タイムアウト秒数（デフォルト10分）

    Returns:
        bool: 成功した場合True
    """
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    ffmpeg_path = shutil.which("ffmpeg")
    if not ffmpeg_path:
        print("Error: ffmpeg not found. Please install ffmpeg first.")
        print("  macOS: brew install ffmpeg")
        print("  Linux: apt install ffmpeg")
        return False

    # UTAGE/Wasabi S3向け高速設定
    cmd = [
        ffmpeg_path,
        "-y",
        # HTTP persistent接続（高速化のキー）
        "-http_persistent", "1",
        "-multiple_requests", "1",
        "-reconnect", "1",
        "-protocol_whitelist", "file,http,https,tcp,tls,crypto",
        "-i", m3u8_url,
        # コピーモード（再エンコードなし）
        "-c", "copy",
        "-bsf:a", "aac_adtstoasc",
        str(output),
    ]

    try:
        print(f"Downloading: {m3u8_url[:80]}...")
        print(f"Output: {output}")

        result = subprocess.run(
            cmd,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout
        )

        if output.exists():
            size_mb = output.stat().st_size / (1024 * 1024)
            print(f"Download complete: {size_mb:.1f} MB")
            return True
        else:
            print("Error: Output file not created")
            return False

    except subprocess.TimeoutExpired:
        print(f"Error: Download timed out after {timeout} seconds")
        return False
    except subprocess.CalledProcessError as e:
        err = e.stderr if e.stderr else ""
        if "HTTP error 403" in err:
            print("Error: Access denied (403)")
            print("The URL token may have expired. Please get a new URL.")
        elif "HTTP error 404" in err:
            print("Error: Video not found (404)")
            print("The video may have been removed or the URL is invalid.")
        else:
            print(f"Error: ffmpeg failed")
            print(err[:300] if err else "Unknown error")
        return False


def extract_audio(
    video_path: str,
    audio_path: str,
    sample_rate: int = 16000
) -> bool:
    """
    動画から音声を抽出（MP3形式）

    Args:
        video_path: 入力動画ファイルパス
        audio_path: 出力音声ファイルパス
        sample_rate: サンプリングレート

    Returns:
        bool: 成功した場合True
    """
    video = Path(video_path)
    audio = Path(audio_path)

    if not video.exists():
        print(f"Error: Video file not found: {video}")
        return False

    audio.parent.mkdir(parents=True, exist_ok=True)

    ffmpeg_path = shutil.which("ffmpeg")
    if not ffmpeg_path:
        print("Error: ffmpeg not found")
        return False

    cmd = [
        ffmpeg_path,
        "-y",
        "-i", str(video),
        "-vn",  # 映像なし
        "-acodec", "libmp3lame",
        "-ar", str(sample_rate),
        "-ac", "1",  # モノラル
        "-q:a", "2",  # 高品質
        str(audio),
    ]

    try:
        print(f"Extracting audio: {video.name} -> {audio.name}")

        subprocess.run(
            cmd,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=300
        )

        if audio.exists():
            size_mb = audio.stat().st_size / (1024 * 1024)
            print(f"Audio extracted: {size_mb:.1f} MB")
            return True
        else:
            print("Error: Audio file not created")
            return False

    except subprocess.CalledProcessError as e:
        print(f"Error: Audio extraction failed")
        print(e.stderr[:200] if e.stderr else "Unknown error")
        return False


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python hls_downloader.py <m3u8_url> <output_path>")
        print("       python hls_downloader.py --extract-audio <video_path> <audio_path>")
        sys.exit(1)

    if sys.argv[1] == "--extract-audio":
        if len(sys.argv) < 4:
            print("Usage: python hls_downloader.py --extract-audio <video_path> <audio_path>")
            sys.exit(1)
        success = extract_audio(sys.argv[2], sys.argv[3])
    else:
        success = download_hls_video(sys.argv[1], sys.argv[2])

    sys.exit(0 if success else 1)
