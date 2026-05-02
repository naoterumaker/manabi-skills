#!/usr/bin/env python3
"""
スクリーンショット抽出スクリプト

動画からスクリーンショットを抽出する。
- 一定間隔での抽出
- シーン変化検出での抽出（オプション）

Usage:
    python screenshot_extractor.py <video_path> <output_dir> [--interval SECONDS] [--scene]

Example:
    python screenshot_extractor.py "videos/01_intro.mp4" "screenshots/01" --interval 30
    python screenshot_extractor.py "videos/01_intro.mp4" "screenshots/01" --scene
"""

import subprocess
import sys
import shutil
import argparse
from pathlib import Path
from typing import List, Optional


def get_video_duration(video_path: Path) -> float:
    """動画の長さを取得（秒）"""
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(video_path)
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return float(result.stdout.strip())


def extract_title_frame(video_path: Path, output_dir: Path) -> Optional[Path]:
    """
    タイトル画像を抽出（1秒目）

    Returns:
        出力ファイルパス（成功時）
    """
    output_file = output_dir / "title.jpg"

    cmd = [
        "ffmpeg", "-y",
        "-i", str(video_path),
        "-ss", "00:00:01",
        "-vframes", "1",
        "-q:v", "2",
        str(output_file)
    ]

    try:
        subprocess.run(cmd, capture_output=True, check=True)
        if output_file.exists():
            print(f"Title frame: {output_file.name}")
            return output_file
    except subprocess.CalledProcessError:
        pass

    return None


def extract_interval_frames(
    video_path: Path,
    output_dir: Path,
    interval: int = 30
) -> List[Path]:
    """
    一定間隔でフレームを抽出

    Args:
        video_path: 入力動画
        output_dir: 出力ディレクトリ
        interval: 抽出間隔（秒）

    Returns:
        抽出されたファイルパスのリスト
    """
    pattern = str(output_dir / "frame_%03d.jpg")

    # fps=1/interval で指定間隔ごとに抽出
    cmd = [
        "ffmpeg", "-y",
        "-i", str(video_path),
        "-vf", f"fps=1/{interval}",
        "-q:v", "2",
        pattern
    ]

    try:
        subprocess.run(cmd, capture_output=True, check=True)
    except subprocess.CalledProcessError as e:
        print(f"Error extracting frames: {e.stderr[:200] if e.stderr else 'Unknown'}")
        return []

    # 生成されたファイルを収集
    frames = sorted(output_dir.glob("frame_*.jpg"))
    print(f"Extracted {len(frames)} frames at {interval}s intervals")

    return frames


def extract_scene_frames(
    video_path: Path,
    output_dir: Path,
    threshold: float = 0.3
) -> List[Path]:
    """
    シーン変化検出でフレームを抽出

    Args:
        video_path: 入力動画
        output_dir: 出力ディレクトリ
        threshold: シーン変化しきい値（0.0-1.0、小さいほど敏感）

    Returns:
        抽出されたファイルパスのリスト
    """
    pattern = str(output_dir / "scene_%03d.jpg")

    cmd = [
        "ffmpeg", "-y",
        "-i", str(video_path),
        "-vf", f"select='gt(scene,{threshold})',showinfo",
        "-vsync", "vfr",
        "-q:v", "2",
        pattern
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
    except subprocess.CalledProcessError as e:
        print(f"Error detecting scenes: {e.stderr[:200] if e.stderr else 'Unknown'}")
        return []

    # 生成されたファイルを収集
    frames = sorted(output_dir.glob("scene_*.jpg"))
    print(f"Detected {len(frames)} scene changes (threshold: {threshold})")

    return frames


def extract_timestamps_frames(
    video_path: Path,
    output_dir: Path,
    timestamps: List[float]
) -> List[Path]:
    """
    指定したタイムスタンプでフレームを抽出

    Args:
        video_path: 入力動画
        output_dir: 出力ディレクトリ
        timestamps: 抽出する時間（秒）のリスト

    Returns:
        抽出されたファイルパスのリスト
    """
    frames = []

    for i, ts in enumerate(timestamps):
        output_file = output_dir / f"ts_{i:03d}_{int(ts):05d}.jpg"

        # 時間を HH:MM:SS 形式に変換
        hours = int(ts // 3600)
        minutes = int((ts % 3600) // 60)
        seconds = ts % 60

        cmd = [
            "ffmpeg", "-y",
            "-ss", f"{hours:02d}:{minutes:02d}:{seconds:06.3f}",
            "-i", str(video_path),
            "-vframes", "1",
            "-q:v", "2",
            str(output_file)
        ]

        try:
            subprocess.run(cmd, capture_output=True, check=True)
            if output_file.exists():
                frames.append(output_file)
        except subprocess.CalledProcessError:
            print(f"Failed to extract frame at {ts}s")

    print(f"Extracted {len(frames)} frames at specified timestamps")
    return frames


def extract_phash_frames(
    video: Path,
    output_dir: Path,
    sample_interval: int = 2,
    phash_threshold: int = 8
) -> List[Path]:
    """
    pHash（Perceptual Hash）方式でフレーム抽出

    細かい間隔で候補フレームを抽出し、連続するフレームのpHash距離が
    閾値を超えた場合のみ採用する（重複排除）。

    Args:
        video: 入力動画
        output_dir: 出力ディレクトリ
        sample_interval: 候補抽出間隔（秒、細かいほど精度↑、処理↑）
        phash_threshold: pHashハミング距離の閾値（大きいほど選別厳しい）

    Returns:
        採用されたフレームファイルパスのリスト
    """
    try:
        import imagehash
        from PIL import Image
    except ImportError:
        print("Error: imagehash and Pillow required for --phash mode")
        print("Install: pip install imagehash Pillow")
        return []

    # 一時ディレクトリで候補フレームを抽出
    import tempfile
    temp_dir = Path(tempfile.mkdtemp(prefix="phash_candidates_"))

    try:
        pattern = str(temp_dir / "cand_%05d.jpg")
        cmd = [
            "ffmpeg", "-y",
            "-i", str(video),
            "-vf", f"fps=1/{sample_interval}",
            "-q:v", "3",
            "-loglevel", "error",
            pattern
        ]
        subprocess.run(cmd, check=True)

        candidates = sorted(temp_dir.glob("cand_*.jpg"))
        print(f"Extracted {len(candidates)} candidate frames at {sample_interval}s intervals")

        # pHashでデデュープ
        kept = []
        prev_hash = None
        for c in candidates:
            try:
                h = imagehash.phash(Image.open(c))
            except Exception as e:
                print(f"Failed to hash {c.name}: {e}")
                continue
            if prev_hash is None or (h - prev_hash) > phash_threshold:
                kept.append(c)
                prev_hash = h

        print(f"Deduped: {len(kept)} unique frames (threshold={phash_threshold})")

        # 採用分を出力ディレクトリに連番コピー
        output_frames = []
        for i, src in enumerate(kept, 1):
            dst = output_dir / f"frame_{i:03d}.jpg"
            shutil.copy2(src, dst)
            output_frames.append(dst)

        return output_frames

    finally:
        try:
            shutil.rmtree(temp_dir)
        except Exception:
            pass


def extract_screenshots(
    video_path: str,
    output_dir: str,
    interval: int = 30,
    use_scene_detection: bool = False,
    scene_threshold: float = 0.3,
    include_title: bool = True,
    use_phash: bool = False,
    phash_sample_interval: int = 2,
    phash_threshold: int = 8
) -> List[Path]:
    """
    動画からスクリーンショットを抽出

    Args:
        video_path: 入力動画ファイル
        output_dir: 出力ディレクトリ
        interval: 抽出間隔（秒、シーン検出時は無視）
        use_scene_detection: シーン検出を使用
        scene_threshold: シーン変化しきい値
        include_title: タイトル画像を含める

    Returns:
        抽出されたファイルパスのリスト
    """
    video = Path(video_path)
    output = Path(output_dir)

    # ffmpegチェック
    if not shutil.which("ffmpeg"):
        print("Error: ffmpeg not found. Please install ffmpeg first.")
        return []

    if not video.exists():
        print(f"Error: Video file not found: {video}")
        return []

    # 出力ディレクトリ作成
    output.mkdir(parents=True, exist_ok=True)

    duration = get_video_duration(video)
    print(f"Video: {video.name}")
    print(f"Duration: {duration:.1f}s ({duration/60:.1f} min)")

    frames = []

    # タイトル画像を抽出
    if include_title:
        title = extract_title_frame(video, output)
        if title:
            frames.append(title)

    # メインの抽出処理
    if use_phash:
        phash_frames = extract_phash_frames(
            video, output,
            sample_interval=phash_sample_interval,
            phash_threshold=phash_threshold
        )
        frames.extend(phash_frames)

        # pHashで少なすぎる場合は間隔抽出も併用
        if len(phash_frames) < 5:
            print("Too few phash frames, falling back to interval...")
            interval_frames = extract_interval_frames(video, output, interval)
            frames.extend(interval_frames)
    elif use_scene_detection:
        scene_frames = extract_scene_frames(video, output, scene_threshold)
        frames.extend(scene_frames)

        # シーン検出で少なすぎる場合は間隔抽出も併用
        if len(scene_frames) < 5:
            print("Too few scenes detected, adding interval frames...")
            interval_frames = extract_interval_frames(video, output, interval)
            frames.extend(interval_frames)
    else:
        interval_frames = extract_interval_frames(video, output, interval)
        frames.extend(interval_frames)

    print(f"\nTotal: {len(frames)} screenshots extracted to {output}")
    return frames


def main():
    parser = argparse.ArgumentParser(
        description="Extract screenshots from video"
    )
    parser.add_argument("video_path", help="Input video file")
    parser.add_argument("output_dir", help="Output directory for screenshots")
    parser.add_argument(
        "--interval", "-i",
        type=int,
        default=30,
        help="Extraction interval in seconds (default: 30)"
    )
    parser.add_argument(
        "--scene", "-s",
        action="store_true",
        help="Use scene change detection"
    )
    parser.add_argument(
        "--threshold", "-t",
        type=float,
        default=0.3,
        help="Scene detection threshold 0.0-1.0 (default: 0.3)"
    )
    parser.add_argument(
        "--no-title",
        action="store_true",
        help="Don't extract title frame"
    )
    parser.add_argument(
        "--timestamps",
        type=str,
        help="Extract frames at specific timestamps (comma-separated seconds, e.g., '60,120,180')"
    )
    parser.add_argument(
        "--phash",
        action="store_true",
        default=True,
        help="Use perceptual hash dedup mode (DEFAULT - catches slide changes, removes duplicates)"
    )
    parser.add_argument(
        "--no-phash",
        dest="phash",
        action="store_false",
        help="Disable pHash mode and use the legacy interval/scene mode"
    )
    parser.add_argument(
        "--phash-sample",
        type=int,
        default=2,
        help="pHash candidate sampling interval in seconds (default: 2)"
    )
    parser.add_argument(
        "--phash-threshold",
        type=int,
        default=8,
        help="pHash hamming distance threshold 0-64 (default: 8, lower=more frames)"
    )

    args = parser.parse_args()

    # タイムスタンプ指定モード
    if args.timestamps:
        video = Path(args.video_path)
        output = Path(args.output_dir)
        output.mkdir(parents=True, exist_ok=True)

        timestamps = [float(t.strip()) for t in args.timestamps.split(",")]
        print(f"Extracting {len(timestamps)} frames at specified timestamps...")
        frames = extract_timestamps_frames(video, output, timestamps)
        sys.exit(0 if frames else 1)

    # 通常モード
    frames = extract_screenshots(
        video_path=args.video_path,
        output_dir=args.output_dir,
        interval=args.interval,
        use_scene_detection=args.scene,
        scene_threshold=args.threshold,
        include_title=not args.no_title,
        use_phash=args.phash,
        phash_sample_interval=args.phash_sample,
        phash_threshold=args.phash_threshold
    )

    sys.exit(0 if frames else 1)


if __name__ == "__main__":
    main()
