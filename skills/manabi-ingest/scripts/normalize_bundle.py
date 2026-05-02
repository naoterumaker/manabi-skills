#!/usr/bin/env python3
"""
normalize_bundle.py

utage-manual形式の出力ディレクトリをcourse-bundle標準フォーマットに変換する。

Usage:
    python normalize_bundle.py \
        --input "/path/to/youtube_booster_manual" \
        --output "/path/to/course-bundle" \
        --course-name "YouTube Booster" \
        --speaker "おさる" \
        --source-type "utage"
"""

import argparse
import json
import os
import re
import shutil
import sys
from pathlib import Path


def detect_chapters(input_dir: Path) -> list[dict]:
    """入力ディレクトリからチャプター情報を検出する。

    transcripts/, screenshots/, manuals/ のファイル名からチャプターIDを抽出し、
    統合したチャプターリストを返す。
    """
    chapters = {}

    # transcripts/ から検出
    transcripts_dir = input_dir / "transcripts"
    if transcripts_dir.is_dir():
        for f in sorted(transcripts_dir.iterdir()):
            if f.suffix == ".txt" and f.name != "CLAUDE.md":
                chapter_id = f.stem  # e.g., "03", "12-1"
                if chapter_id not in chapters:
                    chapters[chapter_id] = {"id": chapter_id, "title": ""}
                chapters[chapter_id]["has_transcript"] = True
                chapters[chapter_id]["transcript_source"] = str(f)

    # screenshots/ から検出
    screenshots_dir = input_dir / "screenshots"
    if screenshots_dir.is_dir():
        for d in sorted(screenshots_dir.iterdir()):
            if d.is_dir():
                chapter_id = d.name
                if chapter_id not in chapters:
                    chapters[chapter_id] = {"id": chapter_id, "title": ""}
                jpg_files = list(d.glob("*.jpg")) + list(d.glob("*.png"))
                chapters[chapter_id]["has_screenshots"] = True
                chapters[chapter_id]["screenshot_count"] = len(jpg_files)
                chapters[chapter_id]["screenshots_source"] = str(d)

    # manuals/ からタイトルを抽出
    manuals_dir = input_dir / "manuals"
    if manuals_dir.is_dir():
        for f in sorted(manuals_dir.iterdir()):
            if f.suffix == ".md" and f.name != "CLAUDE.md":
                # ファイル名パターン: "03_タイトル.md" or "03.md"
                match = re.match(r"^([0-9a-zA-Z_-]+?)_(.+)\.md$", f.name)
                if match:
                    chapter_id = match.group(1)
                    title = match.group(2)
                else:
                    chapter_id = f.stem
                    title = ""

                if chapter_id not in chapters:
                    chapters[chapter_id] = {"id": chapter_id, "title": ""}
                if title:
                    chapters[chapter_id]["title"] = title
                chapters[chapter_id]["has_manual"] = True
                chapters[chapter_id]["manual_source"] = str(f)

    # タイトルが空の場合、transcriptの先頭行から推測
    for ch_id, ch in chapters.items():
        if not ch.get("title") and ch.get("transcript_source"):
            try:
                with open(ch["transcript_source"], "r", encoding="utf-8") as f:
                    first_line = f.readline().strip()
                    if first_line:
                        ch["title"] = first_line[:80]
            except Exception:
                pass
        if not ch.get("title"):
            ch["title"] = f"Chapter {ch_id}"

    # 実質的なコンテンツがないチャプターを除外
    filtered = {
        k: v for k, v in chapters.items()
        if v.get("has_transcript") or v.get("has_manual") or v.get("screenshot_count", 0) > 0
    }

    return sorted(filtered.values(), key=lambda c: c["id"])


def estimate_duration(transcript_path: str) -> int | None:
    """transcriptの文字数から動画の長さを推定する。

    日本語の場合、1分あたり約300-400文字として推定。
    """
    try:
        with open(transcript_path, "r", encoding="utf-8") as f:
            text = f.read()
        char_count = len(text)
        # 1分あたり350文字として推定
        estimated_minutes = char_count / 350
        return int(estimated_minutes * 60)
    except Exception:
        return None


def create_bundle(
    input_dir: Path,
    output_dir: Path,
    course_name: str,
    speaker: str,
    source_type: str,
    source_url: str | None,
    language: str,
) -> dict:
    """course-bundleを作成する。"""
    chapters_data = detect_chapters(input_dir)

    if not chapters_data:
        print("ERROR: チャプターが検出されませんでした。", file=sys.stderr)
        print(f"  入力ディレクトリ: {input_dir}", file=sys.stderr)
        print(
            "  transcripts/, screenshots/, manuals/ のいずれかが必要です。",
            file=sys.stderr,
        )
        sys.exit(1)

    # 出力ディレクトリ作成
    chapters_out = output_dir / "chapters"
    chapters_out.mkdir(parents=True, exist_ok=True)

    manifest_chapters = []

    for ch in chapters_data:
        ch_id = ch["id"]
        ch_dir = chapters_out / ch_id
        ch_dir.mkdir(exist_ok=True)

        # transcript をコピー
        transcript_path = None
        if ch.get("has_transcript") and ch.get("transcript_source"):
            src = Path(ch["transcript_source"])
            dst = ch_dir / "transcript.txt"
            shutil.copy2(src, dst)
            transcript_path = f"chapters/{ch_id}/transcript.txt"

            # タイムスタンプ付きJSONがあれば一緒にコピー
            ts_src = src.with_suffix(".json")
            if not ts_src.exists():
                ts_src = src.parent / f"{src.stem}_ts.json"
            ts_path = None
            if ts_src.exists():
                ts_dst = ch_dir / "transcript_ts.json"
                shutil.copy2(ts_src, ts_dst)
                ts_path = f"chapters/{ch_id}/transcript_ts.json"
        else:
            transcript_path = f"chapters/{ch_id}/transcript.txt"
            ts_path = None

        # screenshots をコピー
        ss_count = 0
        ss_dir_rel = f"chapters/{ch_id}/screenshots/"
        if ch.get("has_screenshots") and ch.get("screenshots_source"):
            src_dir = Path(ch["screenshots_source"])
            dst_dir = ch_dir / "screenshots"
            if dst_dir.exists():
                shutil.rmtree(dst_dir)
            shutil.copytree(src_dir, dst_dir)
            ss_count = ch.get("screenshot_count", 0)
        else:
            (ch_dir / "screenshots").mkdir(exist_ok=True)

        # manual をコピー
        manual_path = None
        if ch.get("has_manual") and ch.get("manual_source"):
            src = Path(ch["manual_source"])
            dst = ch_dir / "manual.md"
            shutil.copy2(src, dst)
            manual_path = f"chapters/{ch_id}/manual.md"

        # duration推定
        duration = None
        if ch.get("transcript_source"):
            duration = estimate_duration(ch["transcript_source"])

        # status判定
        has_transcript = ch.get("has_transcript", False)
        has_screenshots = ch.get("has_screenshots", False) and ss_count > 0
        if has_transcript and has_screenshots:
            status = "complete"
        elif has_transcript or has_screenshots:
            status = "partial"
        else:
            status = "pending"

        manifest_chapters.append(
            {
                "id": ch_id,
                "title": ch["title"],
                "duration_seconds": duration,
                "transcript_path": transcript_path,
                "transcript_ts_path": ts_path,
                "screenshots_dir": ss_dir_rel,
                "screenshot_count": ss_count,
                **({"manual_path": manual_path} if manual_path else {}),
                "status": status,
            }
        )

    # manifest.json 生成
    manifest = {
        "course_name": course_name,
        "source_type": source_type,
        **({"source_url": source_url} if source_url else {}),
        "language": language,
        "speaker": speaker,
        "chapters": manifest_chapters,
    }

    manifest_path = output_dir / "manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    return manifest


def validate_manifest(output_dir: Path) -> bool:
    """manifest.jsonのパスが全て実在するか検証する。"""
    manifest_path = output_dir / "manifest.json"
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    all_valid = True
    for ch in manifest["chapters"]:
        for key in ["transcript_path", "screenshots_dir"]:
            rel_path = ch.get(key)
            if rel_path:
                full_path = output_dir / rel_path
                if not full_path.exists():
                    print(f"MISSING: {full_path}", file=sys.stderr)
                    all_valid = False

        ts_path = ch.get("transcript_ts_path")
        if ts_path:
            full_path = output_dir / ts_path
            if not full_path.exists():
                print(f"WARNING (optional): {full_path} not found", file=sys.stderr)

        ss_dir = ch.get("screenshots_dir")
        if ss_dir:
            full_path = output_dir / ss_dir
            if full_path.exists():
                actual_count = len(
                    list(full_path.glob("*.jpg")) + list(full_path.glob("*.png"))
                )
                expected = ch.get("screenshot_count", 0)
                if actual_count != expected:
                    print(
                        f"WARNING: {ch['id']} screenshot_count mismatch: "
                        f"expected={expected}, actual={actual_count}",
                        file=sys.stderr,
                    )

    return all_valid


def main():
    parser = argparse.ArgumentParser(
        description="utage-manual形式の出力をcourse-bundleフォーマットに正規化する"
    )
    parser.add_argument(
        "--input",
        required=True,
        help="入力ディレクトリ（utage-manual出力形式）",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="出力ディレクトリ（course-bundle）",
    )
    parser.add_argument(
        "--course-name",
        required=True,
        help="講座名",
    )
    parser.add_argument(
        "--speaker",
        default="",
        help="講師名",
    )
    parser.add_argument(
        "--source-type",
        choices=["utage", "youtube", "udemy", "loom", "local"],
        default="utage",
        help="入力ソースの種類",
    )
    parser.add_argument(
        "--source-url",
        default=None,
        help="ソースURL（任意）",
    )
    parser.add_argument(
        "--language",
        default="ja",
        help="言語コード（デフォルト: ja）",
    )
    args = parser.parse_args()

    input_dir = Path(args.input).resolve()
    output_dir = Path(args.output).resolve()

    if not input_dir.is_dir():
        print(f"ERROR: 入力ディレクトリが存在しません: {input_dir}", file=sys.stderr)
        sys.exit(1)

    if output_dir.exists() and any(output_dir.iterdir()):
        print(f"WARNING: 出力ディレクトリが空ではありません: {output_dir}", file=sys.stderr)
        response = input("上書きしますか？ (y/N): ").strip().lower()
        if response != "y":
            print("中断しました。")
            sys.exit(0)

    print(f"入力: {input_dir}")
    print(f"出力: {output_dir}")
    print(f"講座名: {args.course_name}")
    print(f"講師: {args.speaker}")
    print(f"ソース: {args.source_type}")
    print()

    # チャプター検出
    chapters = detect_chapters(input_dir)
    print(f"検出チャプター数: {len(chapters)}")
    for ch in chapters:
        parts = []
        if ch.get("has_transcript"):
            parts.append("transcript")
        if ch.get("has_screenshots"):
            parts.append(f"screenshots({ch.get('screenshot_count', 0)})")
        if ch.get("has_manual"):
            parts.append("manual")
        print(f"  {ch['id']}: {ch['title'][:40]} [{', '.join(parts)}]")
    print()

    # Bundle作成
    manifest = create_bundle(
        input_dir=input_dir,
        output_dir=output_dir,
        course_name=args.course_name,
        speaker=args.speaker,
        source_type=args.source_type,
        source_url=args.source_url,
        language=args.language,
    )

    # バリデーション
    print("manifest.json バリデーション中...")
    if validate_manifest(output_dir):
        print("✓ 全パス正常")
    else:
        print("✗ 一部パスに問題があります", file=sys.stderr)
        sys.exit(1)

    # サマリー
    complete = sum(1 for ch in manifest["chapters"] if ch["status"] == "complete")
    partial = sum(1 for ch in manifest["chapters"] if ch["status"] == "partial")
    pending = sum(1 for ch in manifest["chapters"] if ch["status"] == "pending")

    print()
    print("=== Course Bundle 作成完了 ===")
    print(f"  出力先: {output_dir}")
    print(f"  チャプター数: {len(manifest['chapters'])}")
    print(f"  complete: {complete}, partial: {partial}, pending: {pending}")
    print(f"  manifest: {output_dir / 'manifest.json'}")


if __name__ == "__main__":
    main()
