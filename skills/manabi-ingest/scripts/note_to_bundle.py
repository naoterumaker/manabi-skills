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
  python3 note_to_bundle.py raw.json /path/to/output-bundle [--force]
"""
import argparse
import json
import os
import pathlib
import re
import shutil
import sys
import urllib.request

SKIP_HEADINGS = re.compile(r"^(目次|高評価して応援しよう)")
OPTIONAL_KEYS = {"transcript_ts_path"}

# 画像DL上限: 30MB
IMAGE_SIZE_LIMIT = 30 * 1024 * 1024

# マーカー正規表現（行単位マッチ）
IMG_PATTERN = re.compile(r"^<<IMG>>(\S+?)<<CAP>>(.*)$", re.MULTILINE)
VIDEO_PATTERN = re.compile(r"^<<VIDEO>>(\S+?)<<VTITLE>>(.*)$", re.MULTILINE)

# 裸URL末尾から除去する句読点・閉じ括弧
URL_TRAILING_JUNK = re.compile(r"[）)。、」\]]+$")


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
    with open(path, encoding="utf-8") as f:
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


def download_image(url, dest, fname, cid):
    """画像をDL。失敗時はFalseを返す（例外を上げない）"""
    try:
        req = urllib.request.urlopen(url, timeout=30)
        data = req.read(IMAGE_SIZE_LIMIT + 1)
        if len(data) > IMAGE_SIZE_LIMIT:
            print(f"  WARN image too large ch{cid} {fname}: {len(data)} bytes > 30MB limit")
            return False
        dest.write_bytes(data)
        return True
    except Exception as e:
        print(f"  WARN image fail ch{cid} {fname}: {e}")
        return False


def process_chapter(cid, heading, body_md, chdir):
    """画像DL・動画マーカー変換・links.json生成。(article_md, img_count, videos, status)を返す"""
    shots = chdir / "screenshots"
    shots.mkdir(parents=True, exist_ok=True)
    links = []
    has_failure = False

    # --- 画像: DLしてMarkdown参照に置換 ---
    for n, m in enumerate(IMG_PATTERN.finditer(body_md), 1):
        url, cap = m.group(1), m.group(2)
        clean = url.split("?")[0]
        ext = os.path.splitext(clean)[1] or ".png"
        fname = f"img_{n:03d}{ext}"
        dest = shots / fname
        if not dest.exists():
            ok = download_image(url, dest, fname, cid)
            if not ok:
                has_failure = True
                # 失敗時は画像参照を除去し失敗マーカーテキストで置換
                body_md = body_md.replace(
                    m.group(0),
                    f"（画像取得失敗: {url} ）",
                    1,
                )
                continue
        alt = cap or f"図{n}"
        body_md = body_md.replace(
            m.group(0),
            f"![{alt}](screenshots/{fname})" + (f"\n*{cap}*" if cap else ""),
            1,
        )

    # --- 埋め込み動画: 人間用マーカー + manifest記録（欠落させない） ---
    videos = []
    for n, m in enumerate(VIDEO_PATTERN.finditer(body_md), 1):
        url, vtitle = m.group(1), m.group(2)
        vid = f"video_{n:02d}"
        label = vtitle or "埋め込み動画"
        body_md = body_md.replace(
            m.group(0),
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
        # 末尾の句読点・閉じ括弧を除去
        url = URL_TRAILING_JUNK.sub("", url)
        if url not in seen and "assets.st-note.com" not in url:
            links.append({"text": "", "url": url, "context": heading,
                          "type": classify_link(url)})
            seen.add(url)
    if links:
        (chdir / "links.json").write_text(
            json.dumps(links, ensure_ascii=False, indent=2), encoding="utf-8")

    article = f"## {heading}\n\n{body_md.strip()}\n"
    (chdir / "article.md").write_text(article, encoding="utf-8")
    status = "partial" if has_failure else "complete"
    if has_failure:
        print(f"  WARN ch{cid} ({heading[:20]}): 画像取得失敗あり → status=partial")
    return article, len(list(shots.glob("img_*"))), videos, status


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
    ap = argparse.ArgumentParser()
    ap.add_argument("raw_path")
    ap.add_argument("out_dir")
    ap.add_argument("--force", action="store_true",
                    help="既存の出力先バンドルを上書きする（章ディレクトリを再作成）")
    args = ap.parse_args()

    out = pathlib.Path(args.out_dir)

    # 再実行時の汚染防止: 既存出力があれば --force なしで停止
    if out.exists() and (out / "manifest.json").exists():
        if not args.force:
            sys.exit(
                f"既存出力あり: {out}\n"
                "上書きする場合は --force を指定してください。"
            )
        else:
            # --force: 章ディレクトリを削除して再作成（manifest.jsonは最後に上書き）
            chapters_dir = out / "chapters"
            if chapters_dir.exists():
                shutil.rmtree(chapters_dir)
            print(f"--force: {out}/chapters を再作成します")

    data = load_raw(args.raw_path)
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

        # 空章はdropせずpartialで残す
        if not body.strip():
            print(f"  WARN ch{cid} ({heading[:20]}): 本文が空 → status=partial で保持")
            chdir.mkdir(parents=True, exist_ok=True)
            (chdir / "screenshots").mkdir(parents=True, exist_ok=True)
            (chdir / "article.md").write_text(f"## {heading}\n\n", encoding="utf-8")
            entry = {
                "id": cid,
                "title": heading,
                "content_type": "article",
                "article_path": f"chapters/{cid}/article.md",
                "screenshots_dir": f"chapters/{cid}/screenshots/",
                "screenshot_count": 0,
                "char_count": 0,
                "status": "partial",
            }
            manifest["chapters"].append(entry)
            continue

        article, img_count, videos, status = process_chapter(cid, heading, body, chdir)
        total_videos += len(videos)
        entry = {
            "id": cid,
            "title": heading,
            "content_type": "hybrid" if videos else "article",
            "article_path": f"chapters/{cid}/article.md",
            "screenshots_dir": f"chapters/{cid}/screenshots/",
            "screenshot_count": img_count,
            "char_count": len(article),
            "status": status,
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
