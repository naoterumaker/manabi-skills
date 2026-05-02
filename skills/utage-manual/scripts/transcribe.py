#!/usr/bin/env python3
"""
Groq Whisper 文字起こしスクリプト

音声ファイルをチャンク分割してGroq Whisper APIで文字起こしする。
3分チャンク + 並列処理で高速化。

Usage:
    python transcribe.py <audio_path> <output_path>
    python transcribe.py <audio_path> <output_path> --timestamps <ts_output_path>

Example:
    python transcribe.py "audio/01.mp3" "transcripts/01.txt"
    python transcribe.py "audio/01.mp3" "transcripts/01.txt" --timestamps "transcripts/01_ts.json"

Environment:
    GROQ_API_KEY: Groq APIキー（必須）
"""

import json
import os
import sys
import time
import subprocess
import tempfile
import shutil
from pathlib import Path
from typing import List, Tuple, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
except ImportError:
    print("Error: requests library not found")
    print("Install: pip install requests")
    sys.exit(1)


def get_api_key() -> str:
    """APIキーを取得（環境変数または.envファイル）"""
    api_key = os.getenv("GROQ_API_KEY")

    if not api_key:
        # .envファイルを探す
        env_paths = [
            Path(__file__).parent.parent / ".env",
            Path.home() / ".claude/skills/utage-manual/.env",
            Path.cwd() / ".env",
        ]

        for env_path in env_paths:
            if env_path.exists():
                with open(env_path) as f:
                    for line in f:
                        if line.startswith("GROQ_API_KEY="):
                            api_key = line.split("=", 1)[1].strip().strip('"').strip("'")
                            break
                if api_key:
                    break

    return api_key or ""


def create_session() -> requests.Session:
    """リトライ付きセッションを作成"""
    sess = requests.Session()
    retry = Retry(
        total=3,
        backoff_factor=0.5,
        status_forcelist=[429, 500, 502, 503, 504]
    )
    adapter = HTTPAdapter(
        max_retries=retry,
        pool_connections=10,
        pool_maxsize=10
    )
    sess.mount("https://", adapter)
    sess.mount("http://", adapter)
    return sess


def get_audio_duration(audio_path: Path) -> float:
    """音声ファイルの長さを取得（秒）"""
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(audio_path)
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return float(result.stdout.strip())


def split_audio_to_chunks(
    audio_path: Path,
    chunk_seconds: int = 180,
    temp_dir: Optional[Path] = None
) -> List[Path]:
    """
    音声ファイルをチャンクファイルに分割

    Args:
        audio_path: 入力音声ファイル
        chunk_seconds: チャンク秒数（デフォルト3分）
        temp_dir: 一時ディレクトリ（Noneの場合自動作成）

    Returns:
        チャンクファイルパスのリスト
    """
    if temp_dir is None:
        temp_dir = Path(tempfile.mkdtemp(prefix="utage_chunks_"))
    else:
        temp_dir.mkdir(parents=True, exist_ok=True)

    # 音声長を取得
    duration = get_audio_duration(audio_path)
    num_chunks = int(duration / chunk_seconds) + (1 if duration % chunk_seconds > 0 else 0)

    print(f"Audio duration: {duration:.1f}s, splitting into {num_chunks} chunks")

    # ffmpeg segmentモードで分割
    pattern = str(temp_dir / "chunk_%04d.mp3")
    cmd = [
        "ffmpeg", "-y",
        "-i", str(audio_path),
        "-f", "segment",
        "-segment_time", str(chunk_seconds),
        "-vn",
        "-ar", "16000",
        "-ac", "1",
        "-b:a", "64k",
        "-acodec", "libmp3lame",
        "-reset_timestamps", "1",
        "-loglevel", "error",
        pattern
    ]

    subprocess.run(cmd, capture_output=True, check=True)

    # 生成されたチャンクを収集
    chunks = []
    for i in range(num_chunks):
        chunk_path = temp_dir / f"chunk_{i:04d}.mp3"
        if chunk_path.exists():
            chunks.append(chunk_path)

    print(f"Created {len(chunks)} chunk files")
    return chunks


def transcribe_chunk(
    session: requests.Session,
    api_key: str,
    chunk_path: Path,
    model: str = "whisper-large-v3",
    language: str = "ja",
    max_retries: int = 3,
    response_format: str = "text"
):
    """
    単一チャンクを文字起こし

    Args:
        session: リクエストセッション
        api_key: Groq APIキー
        chunk_path: チャンクファイルパス
        model: Whisperモデル
        language: 言語コード
        max_retries: リトライ回数
        response_format: "text" or "verbose_json"

    Returns:
        文字起こしテキスト（text形式）またはdict（verbose_json形式）
    """
    url = "https://api.groq.com/openai/v1/audio/transcriptions"

    for attempt in range(max_retries):
        try:
            with open(chunk_path, "rb") as f:
                files = {"file": (chunk_path.name, f, "audio/mpeg")}
                headers = {"Authorization": f"Bearer {api_key}"}
                data = {
                    "model": model,
                    "response_format": response_format,
                    "language": language,
                }
                if response_format == "verbose_json":
                    data["timestamp_granularities[]"] = "segment"

                resp = session.post(
                    url,
                    headers=headers,
                    files=files,
                    data=data,
                    timeout=120
                )

                if resp.status_code == 200:
                    if response_format == "verbose_json":
                        return resp.json()
                    return resp.text.strip()

                if resp.status_code == 429:
                    wait = min(30, 2 ** attempt)
                    print(f"Rate limit, waiting {wait}s...")
                    time.sleep(wait)
                elif resp.status_code in [500, 502, 503, 504]:
                    wait = min(30, 5 * (2 ** attempt))
                    print(f"Server error {resp.status_code}, waiting {wait}s...")
                    time.sleep(wait)
                else:
                    print(f"API error {resp.status_code}: {resp.text[:200]}")

        except Exception as e:
            print(f"Request failed (attempt {attempt+1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)

    return {} if response_format == "verbose_json" else ""


def transcribe_audio(
    audio_path: str,
    output_path: str,
    chunk_seconds: int = 180,
    max_workers: int = 10,
    model: str = "whisper-large-v3",
    language: str = "ja",
    timestamps_path: Optional[str] = None
) -> Tuple[bool, str]:
    """
    音声ファイルを文字起こし

    Args:
        audio_path: 入力音声ファイル
        output_path: 出力テキストファイル
        chunk_seconds: チャンク秒数
        max_workers: 並列ワーカー数
        model: Whisperモデル
        language: 言語
        timestamps_path: タイムスタンプJSON出力パス（Noneの場合は出力しない）

    Returns:
        (成功フラグ, 文字起こしテキスト)
    """
    audio = Path(audio_path)
    output = Path(output_path)
    want_timestamps = timestamps_path is not None

    if not audio.exists():
        print(f"Error: Audio file not found: {audio}")
        return False, ""

    api_key = get_api_key()
    if not api_key:
        print("Error: GROQ_API_KEY not found")
        print("Set environment variable or add to .env file")
        return False, ""

    output.parent.mkdir(parents=True, exist_ok=True)
    if timestamps_path:
        Path(timestamps_path).parent.mkdir(parents=True, exist_ok=True)

    start_time = time.time()
    temp_dir = None

    try:
        # チャンク分割
        chunks = split_audio_to_chunks(audio, chunk_seconds)
        temp_dir = chunks[0].parent if chunks else None

        total_chunks = len(chunks)

        # 動的並列数調整
        if total_chunks <= 10:
            workers = total_chunks
        elif total_chunks <= 30:
            workers = min(max_workers, 10)
        elif total_chunks <= 50:
            workers = min(max_workers, 8)
        else:
            workers = min(max_workers, 5)

        print(f"Processing {total_chunks} chunks with {workers} workers")

        # セッション作成
        session = create_session()

        # 並列処理
        resp_format = "verbose_json" if want_timestamps else "text"
        results = [None] * total_chunks
        completed = 0

        def process_chunk(idx: int, chunk_path: Path):
            result = transcribe_chunk(
                session, api_key, chunk_path, model, language,
                response_format=resp_format
            )
            try:
                chunk_path.unlink()
            except:
                pass
            return idx, result

        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(process_chunk, i, chunk): i
                for i, chunk in enumerate(chunks)
            }

            for future in as_completed(futures):
                try:
                    idx, result = future.result()
                    results[idx] = result
                    completed += 1
                    print(f"Completed {completed}/{total_chunks}")
                except Exception as e:
                    idx = futures[future]
                    results[idx] = "" if not want_timestamps else {}
                    completed += 1
                    print(f"Chunk {idx} failed: {e}")

        if want_timestamps:
            # verbose_json: テキスト結合 + タイムスタンプJSON生成
            text_parts = []
            all_segments = []
            for idx, result in enumerate(results):
                if not result:
                    continue
                text_parts.append(result.get("text", ""))
                chunk_offset = idx * chunk_seconds
                for seg in result.get("segments", []):
                    all_segments.append({
                        "start": round(seg.get("start", 0) + chunk_offset, 2),
                        "end": round(seg.get("end", 0) + chunk_offset, 2),
                        "text": seg.get("text", "").strip()
                    })
            combined_text = "\n".join([t for t in text_parts if t])

            # タイムスタンプJSONを保存
            ts_data = {
                "segments": all_segments,
                "total_segments": len(all_segments)
            }
            Path(timestamps_path).write_text(
                json.dumps(ts_data, ensure_ascii=False, indent=2),
                encoding="utf-8"
            )
            print(f"  Timestamps: {timestamps_path} ({len(all_segments)} segments)")
        else:
            # text形式: そのまま結合
            combined_text = "\n".join([r for r in results if r])

        # ファイルに保存
        output.write_text(combined_text, encoding="utf-8")

        elapsed = time.time() - start_time
        duration = get_audio_duration(audio)
        speed = duration / elapsed if elapsed > 0 else 0

        print(f"Transcription complete!")
        print(f"  Duration: {duration:.1f}s")
        print(f"  Time: {elapsed:.1f}s")
        print(f"  Speed: {speed:.1f}x realtime")
        print(f"  Output: {output}")

        return True, combined_text

    finally:
        # 一時ディレクトリを削除
        if temp_dir and temp_dir.exists():
            try:
                shutil.rmtree(temp_dir)
            except:
                pass


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Groq Whisper文字起こし")
    parser.add_argument("audio_path", help="入力音声ファイル")
    parser.add_argument("output_path", help="出力テキストファイル")
    parser.add_argument("--timestamps", help="タイムスタンプJSON出力パス", default=None)
    args = parser.parse_args()

    success, _ = transcribe_audio(args.audio_path, args.output_path, timestamps_path=args.timestamps)
    sys.exit(0 if success else 1)
