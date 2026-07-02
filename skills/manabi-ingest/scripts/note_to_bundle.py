#!/usr/bin/env python3
"""note記事のraw JSON → course-bundle 変換

入力: Chrome評価スクリプト（SKILL.md「note URLの場合」参照）が出力したJSON
  { url, title, author, purchased, raw_markdown }
  raw_markdown内のマーカー:
    <<H2>>見出し          … 章分割点
    <<IMG>>url<<CAP>>caption … 記事内画像
    <<VIDEO>>url<<VTITLE>>title … 埋め込み動画（iframe検知）

出力: course-bundle（章＝自己完結ユニット）
  chapters/NN/article.md, screenshots/, links.json
  manifest.json（content_type: article / hybrid）

使い方:
  python3 note_to_bundle.py raw.json /path/to/output-bundle
"""
import json
import os
import pathlib
import re
import sys
import urllib.request

SKIP_HEADINGS = re.compile(r"^(目次|高評価して応援しよう)")
OPTIONAL_KEYS = {"transcript_ts_path"}


def classify_link(url):
    if "notion." in url:
        return "notion"
    if "drive.google" in url or "docs.google" in url:
        return "gdrive"
    if url.endswith(".pdf"):
        return "pdf"
    if any(d in url for d in ("youtube.com", "youtu.be", "vimeo.com", "loom.com")):
        return "video"
    return "other"


def load_raw(path):
    with open(path) as f:
        outer = json.load(f)
    # evaluate_scriptの出力はJSON文字列が二重ラップされる場合がある
    return json.loads(outer) if isinstance(outer, str) else outer


def split_chapters(raw_md):
    """<<H2>>マーカーで章分割。リード文はイントロ章、目次/フッターは除外"""
    parts = re.split(r"<<H2>>(.+)\n", raw_md)
    sections = [("イントロダクション", parts[0])]
    for i in range(1, len(parts), 2):
        sections.append((parts[i].strip(), parts[i + 1] if i + 1 < len(parts) else ""))
    return [(h, b) for h, b in sections if not SKIP_HEADINGS.match(h) and b.strip()]


def process_chapter(cid, heading, body_md, chdir):
    """画像DL・動画マーカー変換・links.json生成。(article_md, img_count, videos)を返す"""
    shots = chdir / "screenshots"
    shots.mkdir(parents=True, exist_ok=True)
    links = []

    # --- 画像: DLしてMarkdown参照に置換 ---
    for n, (url, cap) in enumerate(re.findall(r"<<IMG>>(\S+?)<<CAP>>(.*)", body_md), 1):
        clean = url.split("?")[0]
        ext = os.path.splitext(clean)[1] or ".png"
        fname = f"img_{n:03d}{ext}"
        dest = shots / fname
        if not dest.exists():
            try:
                urllib.request.urlretrieve(url, dest)
            except Exception as e:
                print(f"  WARN image fail ch{cid} {fname}: {e}")
                continue
        alt = cap or f"図{n}"
        body_md = body_md.replace(
            f"<<IMG>>{url}<<CAP>>{cap}",
            f"![{alt}](screenshots/{fname})" + (f"\n*{cap}*" if cap else ""),
            1,
        )

    # --- 埋め込み動画: 人間用マーカー + manifest記録（欠落させない） ---
    videos = []
    for n, (url, vtitle) in enumerate(re.findall(r"<<VIDEO>>(\S+?)<<VTITLE>>(.*)", body_md), 1):
        vid = f"video_{n:02d}"
        label = vtitle or "埋め込み動画"
        body_md = body_md.replace(
            f"<<VIDEO>>{url}<<VTITLE>>{vtitle}",
            f"[🎬 {vid}: {label}]({url})\n※取り込み済みの場合の文字起こし: video/transcript_{n:02d}.txt",
            1,
        )
        videos.append({
            "id": vid, "source_url": url, "title": vtitle or None,
            "duration_seconds": None, "video_path": None,
            "transcript_path": None, "status": "skipped",
        })
        links.append({"text": label, "url": url, "context": heading, "type": "video"})

    # --- 本文中の外部リンクをlinks.jsonへ（[text](url)形式 + 裸URL両対応） ---
    seen = set(l["url"] for l in links)
    for text, url in re.findall(r"\[([^\]!🎬][^\]]*)\]\((https?://[^)]+)\)", body_md):
        if url not in seen:
            links.append({"text": text, "url": url, "context": heading,
                          "type": classify_link(url)})
            seen.add(url)
    for url in re.findall(r"(?<![(\[])(https?://[^\s)\]]+)", body_md):
        if url not in seen and "assets.st-note.com" not in url:
            links.append({"text": "", "url": url, "context": heading,
                          "type": classify_link(url)})
            seen.add(url)
    if links:
        (chdir / "links.json").write_text(
            json.dumps(links, ensure_ascii=False, indent=2), encoding="utf-8")

    article = f"## {heading}\n\n{body_md.strip()}\n"
    (chdir / "article.md").write_text(article, encoding="utf-8")
    return article, len(list(shots.glob("img_*"))), videos


def validate(out_dir, manifest):
    """パス検証。okフラグは一度Falseになったら戻さない"""
    ok = True
    for ch in manifest["chapters"]:
        keys = ["screenshots_dir"]
        if ch.get("article_path"):
            keys.append("article_path")
        if ch.get("transcript_path"):
            keys.append("transcript_path")
        for key in keys:
            p = out_dir / ch[key]
            if not p.exists():
                print(f"MISSING: {p}")
                if key not in OPTIONAL_KEYS:
                    ok = False
    return ok


def main():
    raw_path, out = sys.argv[1], pathlib.Path(sys.argv[2])
    data = load_raw(raw_path)
    chapters = split_chapters(data["raw_markdown"])

    manifest = {
        "course_name": data["title"],
        "source_type": "note",
        "source_url": data["url"],
        "language": "ja",
        "speaker": data.get("author", ""),
        "chapters": [],
    }
    total_videos = 0
    for idx, (heading, body) in enumerate(chapters):
        cid = f"{idx:02d}"
        chdir = out / "chapters" / cid
        article, img_count, videos = process_chapter(cid, heading, body, chdir)
        total_videos += len(videos)
        entry = {
            "id": cid,
            "title": heading,
            "content_type": "hybrid" if videos else "article",
            "article_path": f"chapters/{cid}/article.md",
            "screenshots_dir": f"chapters/{cid}/screenshots/",
            "screenshot_count": img_count,
            "char_count": len(article),
            "status": "complete",
        }
        if videos:
            entry["videos"] = videos
        manifest["chapters"].append(entry)

    (out / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    ok = validate(out, manifest)
    print("All paths valid" if ok else "VALIDATION FAILED")
    print(f"\n章数: {len(manifest['chapters'])} / 埋め込み動画: {total_videos}本")
    for ch in manifest["chapters"]:
        v = f", 動画{len(ch.get('videos', []))}本" if ch.get("videos") else ""
        print(f"  {ch['id']}: {ch['title'][:30]}  ({ch['char_count']}字, 画像{ch['screenshot_count']}枚{v})")
    if total_videos:
        print("\n⚠️ 埋め込み動画が見つかりました。取り込む場合はmanabi-ingestの動画確認フローへ")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
