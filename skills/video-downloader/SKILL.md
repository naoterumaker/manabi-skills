---
name: video-downloader
description: "yt-dlpを使ってYouTube/Loom/Vimeo等の動画をローカルにダウンロードする。manabi-ingestのYouTube処理から呼ばれるほか、単独で「この動画をダウンロード」「YouTube DL」「動画落として」などで発動。音声のみ/プレイリスト/画質指定にも対応。"
---

# Video Downloader

`yt-dlp` を使った動画ダウンローダ。YouTube / Loom / Vimeo / その他 yt-dlp が対応する全プラットフォームに対応。

## 前提

```bash
brew install yt-dlp ffmpeg
```

## 基本ダウンロード（推奨設定）

最大1080p・mp4で保存。manabi-ingest からの呼び出しもこれを使う。

```bash
yt-dlp \
  -o "downloads/%(title)s.%(ext)s" \
  -f "bv*[height<=1080][ext=mp4]+ba[ext=m4a]/b[height<=1080][ext=mp4]/b" \
  --merge-output-format mp4 \
  "<URL>"
```

## 画質指定

```bash
# 720p
yt-dlp -f "bv*[height<=720]+ba/b[height<=720]" "<URL>"

# 4K
yt-dlp -f "bv*[height<=2160]+ba/b[height<=2160]" "<URL>"

# 利用可能なフォーマット一覧
yt-dlp -F "<URL>"
```

## 音声のみ

```bash
yt-dlp -x --audio-format mp3 -o "downloads/%(title)s.%(ext)s" "<URL>"
```

## プレイリスト一括

```bash
yt-dlp \
  -o "downloads/%(playlist_title)s/%(playlist_index)s-%(title)s.%(ext)s" \
  "<PLAYLIST_URL>"
```

## バッチダウンロード（複数URL）

```bash
yt-dlp -a urls.txt
```
（`urls.txt` に1行1URL）

## メタデータ・サムネイル保存

```bash
yt-dlp \
  --write-info-json \
  --write-thumbnail \
  --write-description \
  -o "downloads/%(title)s.%(ext)s" \
  "<URL>"
```

## 字幕ダウンロード

```bash
# 自動生成字幕も含めて取得
yt-dlp --write-subs --write-auto-subs --sub-langs "ja,en" --skip-download "<URL>"
```

## 困ったとき

| 症状 | 対処 |
|------|------|
| `ERROR: Unsupported URL` | `pip install -U yt-dlp` で最新化 |
| 認証必須の動画 | `--cookies-from-browser chrome` でブラウザCookie利用 |
| ダウンロード遅い | `-N 4` で並列セグメントDL |
| 結合エラー | `ffmpeg` 未インストール → `brew install ffmpeg` |

## ライセンス・利用上の注意

- 自分が権利を持つ動画、または利用規約・著作権法上ダウンロードが許される動画のみ対象
- プラットフォーム規約を確認すること
- 個人視聴・教育・公正利用の範囲で使用
