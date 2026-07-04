#!/usr/bin/env python3
"""既存マニュアル/バンドルを学びライブラリへ移行する

方針:
- 新形式（manifest.json有り）: そのまま bundles/ へ移動
- 旧形式（manuals/*.md有り）: manifest.json を生成して移動（中身は無加工。
  画像パスの解決はアプリ側がmdファイル相対で行うため書き換え不要）
- ペア（bundle+manual同一講座）: bundleを正とし、manual側は bundle/source_media/ へ同居

使い方:
  python3 migrate_to_library.py <移行元フォルダ> [--pair-into <ライブラリ内バンドル名>]
  # ライブラリの場所は ~/.claude/manabi-home から読む
"""
import argparse
import json
import pathlib
import re
import shutil
import sys

HOME_POINTER = pathlib.Path.home() / ".claude" / "manabi-home"


def library_root():
    if not HOME_POINTER.exists():
        sys.exit("学びホーム未設定。先に初期化してください（~/.claude/manabi-home が必要）")
    root = pathlib.Path(HOME_POINTER.read_text().strip()).expanduser()
    (root / "bundles").mkdir(parents=True, exist_ok=True)
    return root


def is_bundle(p):
    return (p / "manifest.json").exists() and (p / "chapters").is_dir()


def title_from_filename(name):
    stem = pathlib.Path(name).stem
    return re.sub(r"^\d+[_-]?", "", stem).replace("_", " ") or stem


def convert_legacy(src, dest):
    """旧形式: manifest.jsonを生成して移動。中身は無加工"""
    manuals = sorted((src / "manuals").glob("*.md"))
    if not manuals:
        sys.exit(f"{src}: manuals/*.md が見つからない（旧形式ではない）")
    chapters = []
    for i, mf in enumerate(manuals):
        chapters.append({
            "id": f"{i:03d}",
            "title": title_from_filename(mf.name),
            "content_type": "article",
            "manual_path": f"manuals/{mf.name}",
            "screenshots_dir": None,
            "screenshot_count": 0,
            "status": "complete",
        })
    manifest = {
        "course_name": re.sub(r"_manual$", "", src.name),
        "source_type": "legacy",
        "language": "ja",
        "speaker": "",
        "chapters": chapters,
    }
    (src / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    shutil.move(str(src), str(dest))
    return len(chapters)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("source")
    ap.add_argument("--pair-into", help="ライブラリ内の既存バンドル名（source_media/として同居させる）")
    args = ap.parse_args()

    src = pathlib.Path(args.source).resolve()
    if not src.is_dir():
        sys.exit(f"見つからない: {src}")
    lib = library_root()

    if args.pair_into:
        target = lib / "bundles" / args.pair_into / "source_media" / src.name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(target))
        print(f"同居移動: {src.name} → bundles/{args.pair_into}/source_media/")
        return

    dest = lib / "bundles" / src.name
    if dest.exists():
        sys.exit(f"既に存在: {dest}")

    if is_bundle(src):
        shutil.move(str(src), str(dest))
        m = json.loads((dest / "manifest.json").read_text())
        print(f"移動（新形式）: {src.name} → bundles/ | {m['course_name']} | {len(m['chapters'])}章")
    else:
        n = convert_legacy(src, dest)
        print(f"変換+移動（旧形式）: {src.name} → bundles/ | {n}章（manifest生成・中身無加工）")


if __name__ == "__main__":
    main()
