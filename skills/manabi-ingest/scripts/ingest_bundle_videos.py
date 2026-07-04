#!/usr/bin/env python3
"""hybrid章の埋め込み動画を取り込む（DL→音声抽出→Groq文字起こし→pHashスクショ）

manifest.jsonの videos[] (status: skipped) を処理して fetched に更新する。
同一動画が複数章に埋まっている場合は1回だけDL・文字起こしし、他章へはコピーする。

使い方:
  python3 ingest_bundle_videos.py <bundle_dir> [--only VIDEO_ID] [--limit N]
依存: yt-dlp, ffmpeg, GROQ_API_KEY（transcribe.py経由）, imagehash+Pillow（スクショ）
"""
import argparse
import json
import pathlib
import re
import shutil
import subprocess
import sys

SKILLS = pathlib.Path.home() / ".claude" / "skills"
TRANSCRIBE = SKILLS / "utage-manual" / "scripts" / "transcribe.py"
SCREENSHOT = SKILLS / "utage-manual" / "scripts" / "screenshot_extractor.py"
ENV_DIR = SKILLS / "utage-manual"  # .env（GROQ_API_KEY）の場所


def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def yt_id(url):
    m = re.search(r"(?:v=|youtu\.be/)([\w-]+)", url)
    return m.group(1) if m else re.sub(r"\W", "", url)[-11:]


def process_video(url, vid_entry, chdir, cid, cache):
    """1本処理。cacheに同一URL処理済みがあれば流用"""
    videodir = chdir / "video"
    videodir.mkdir(exist_ok=True)
    vid = vid_entry["id"]  # video_01 等（章内連番）
    mp4 = videodir / f"{vid}.mp4"
    txt = videodir / f"transcript_{vid.split('_')[1]}.txt"
    shots = chdir / "screenshots"

    if url in cache:  # 別章で処理済み → コピー
        src = cache[url]
        if not txt.exists():
            shutil.copy(src["txt"], txt)
        vid_entry.update({
            "video_path": str(src["mp4"].relative_to(chdir.parent.parent)),
            "transcript_path": f"chapters/{cid}/video/{txt.name}",
            "duration_seconds": src["duration"],
            "title": src["title"],
            "status": "fetched",
            "note": f"動画実体は初出章と共有（{src['mp4']}）",
        })
        print(f"  ch{cid} {vid}: 共有コピー ({src['title'][:30]})")
        return True

    # --- DL（再開安全: 既DLならスキップしてメタデータのみ取得） ---
    if mp4.exists() and mp4.stat().st_size > 0:
        r = run(["yt-dlp", "--print", "%(duration)s\t%(title)s", "--skip-download", url])
        print(f"  ch{cid} {vid}: DL済みを再利用")
    else:
        r = run(["yt-dlp", "-f", "bv*[height<=1080][ext=mp4]+ba[ext=m4a]/b[height<=1080][ext=mp4]/b",
                 "--merge-output-format", "mp4", "-o", str(mp4),
                 "--print", "after_move:%(duration)s\t%(title)s", "--no-simulate", url])
        if r.returncode != 0 or not mp4.exists():
            vid_entry["status"] = "failed"
            vid_entry["note"] = f"DL失敗: {r.stderr.strip()[-200:]}"
            print(f"  ch{cid} {vid}: ❌ DL失敗 {url}")
            return False
    dur, title = (r.stdout.strip().split("\t") + [""])[:2]
    duration = int(float(dur)) if dur.replace(".", "").isdigit() else None

    # --- 音声抽出 → 文字起こし ---
    mp3 = videodir / f"{vid}.mp3"
    run(["ffmpeg", "-y", "-i", str(mp4), "-vn", "-acodec", "libmp3lame", "-b:a", "64k", str(mp3)])
    r = run(["python3", str(TRANSCRIBE), str(mp3), str(txt)], cwd=str(ENV_DIR))
    if r.returncode != 0 or not txt.exists():
        vid_entry["status"] = "failed"
        vid_entry["note"] = f"文字起こし失敗: {r.stderr.strip()[-200:]}"
        print(f"  ch{cid} {vid}: ❌ 文字起こし失敗")
        return False
    mp3.unlink(missing_ok=True)

    # --- pHashスクショ（v{章内連番}_ プレフィックス） ---
    n = vid.split("_")[1]
    tmp = chdir / f"_vshots_{n}"
    r = run(["python3", str(SCREENSHOT), str(mp4), str(tmp)])
    count = 0
    if tmp.exists():
        shots.mkdir(exist_ok=True)
        for f in sorted(tmp.glob("*")):
            if f.suffix.lower() in (".jpg", ".jpeg", ".png"):
                shutil.move(str(f), shots / f"v{n}_{f.name}")
                count += 1
        shutil.rmtree(tmp, ignore_errors=True)

    vid_entry.update({
        "video_path": f"chapters/{cid}/video/{mp4.name}",
        "transcript_path": f"chapters/{cid}/video/{txt.name}",
        "duration_seconds": duration,
        "title": title or None,
        "status": "fetched",
    })
    cache[url] = {"mp4": mp4, "txt": txt, "duration": duration, "title": title}
    print(f"  ch{cid} {vid}: ✅ {title[:36]} ({duration}s, transcript {txt.stat().st_size}b, スクショ{count}枚)")
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("bundle")
    ap.add_argument("--only", help="このYouTube IDのみ処理（先行1本レビュー用）")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    bundle = pathlib.Path(args.bundle).resolve()
    mpath = bundle / "manifest.json"
    manifest = json.loads(mpath.read_text(encoding="utf-8"))

    cache, done, fail, skipped = {}, 0, 0, 0
    for ch in manifest["chapters"]:
        for v in ch.get("videos", []):
            if v.get("status") == "fetched":
                cache.setdefault(v["source_url"], None)  # 既処理扱いにはしない（安全側）
                continue
            if args.only and yt_id(v["source_url"]) != args.only:
                skipped += 1
                continue
            if args.limit and done + fail >= args.limit:
                skipped += 1
                continue
            chdir = bundle / "chapters" / ch["id"]
            ok = process_video(v["source_url"], v, chdir, ch["id"], cache)
            done += ok
            fail += (not ok)
            # 都度保存（中断しても再開可能）
            mpath.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n完了: {done}本 / 失敗: {fail}本 / 未処理: {skipped}本")
    print("失敗分は manifest の videos[].note に理由を記録済み（statusはfailedのまま＝欠落の可視化）")


if __name__ == "__main__":
    main()
