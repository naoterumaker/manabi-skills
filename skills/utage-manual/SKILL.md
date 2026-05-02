---
name: utage-manual
description: "UTAGEの動画講座からマニュアルを自動作成。Chrome操作で講座構成を把握し処理計画を立案、ffmpegでダウンロード、Groq Whisperで文字起こし、シーン検出でスクリーンショット抽出、読みやすい文章スタイルでMarkdownマニュアル生成、画像と文章の整合性チェックまで一括処理。"
---

# UTAGE動画マニュアル作成スキル

## 概要

UTAGEの動画講座ページから、読みやすいマニュアルを自動作成します。

## 処理フロー

1. **出力フォルダの確認**（ユーザーに毎回確認）
2. **講座構成の把握と計画立案**（Chrome連携）
3. 各章の動画URLを取得
4. ffmpegでHLS動画をダウンロード
5. 音声を抽出
6. Groq Whisperで文字起こし
7. シーン検出でスクリーンショットを抽出
8. 読みやすい文章スタイルでマニュアル作成
9. 画像と文章の整合性チェック
10. 全章結合版の作成（オプション）

---

## Step 1: 講座ページと出力先の確認

**MANDATORY**: 処理を開始する前に、必ずユーザーに確認する。

```
📚 講座ページのURLを教えてください

（例: https://utage-system.com/members/xxxxx/course/xxxxx）

📁 出力先フォルダ: [現在のディレクトリ]/[講座名]_manual/
　（変更したい場合は教えてください）
```

**注意**: ユーザーから講座URLを受け取ってから、Chrome連携で講座ページにアクセスする。

---

## 出力ファイル構成（例）

> ⚠️ 以下はフォルダ構成の**例**です。実際のフォルダ名・ファイル名は講座内容に応じて変わります。

```
[出力フォルダ]/
├── videos/
│   ├── [章番号]_[タイトル].mp4
│   └── ...
├── audio/
│   ├── [章番号].mp3
│   └── ...
├── transcripts/
│   ├── [章番号].txt
│   └── ...
├── screenshots/
│   ├── [章番号]/
│   │   ├── title.jpg
│   │   ├── frame_001.jpg
│   │   └── ...
│   └── ...
├── manuals/
│   ├── [章番号]_[タイトル].md
│   └── ...
└── full_manual.md  # 全章結合版
```

---

## Step 2: 講座構成の把握と計画立案

### 2-1. 講座ページにアクセス

```javascript
// tabs_context_mcp でタブ情報を取得
// navigate で講座ページに移動
// read_page でページ構造を取得
```

### 2-2. 章一覧を抽出

```javascript
// javascript_tool で章リストを取得
const lessons = document.querySelectorAll('a[href*="/lesson/"]');
const chapters = Array.from(lessons).map((a, i) => ({
  index: i,
  title: a.textContent.trim(),
  url: a.href
}));
JSON.stringify(chapters);
```

### 2-3. 処理計画を作成

抽出した章一覧をユーザーに提示し、確認を取る:

```
📋 講座構成（全N章）

[抽出した章一覧を表示]

処理対象を選択してください:
- 全章処理
- 特定の章のみ（番号指定）
- 範囲指定（例: 0-5）
```

---

## Step 3: 動画URL取得

各章のレッスンページから動画URLを取得:

```javascript
// iframeから動画URLを取得
const iframe = document.querySelector('iframe');
iframe.src  // → https://utage-system.com/video/xxxxx
```

動画ページに移動後、`read_network_requests` で `.m3u8` URLを取得:
```
urlPattern: ".m3u8"
→ https://s3.ap-northeast-1.wasabisys.com/utagesystem-video/.../video.m3u8
```

---

## Step 4: 動画ダウンロード

**スクリプト**: [`scripts/hls_downloader.py`](scripts/hls_downloader.py)

```bash
# 動画ダウンロード（UTAGE/Wasabi S3向け高速設定）
python scripts/hls_downloader.py "[m3u8 URL]" "videos/[章番号]_[タイトル].mp4"
```

**特徴**:
- HTTP persistent接続で高速ダウンロード
- コピーモード（再エンコードなし）
- 自動リトライ対応

---

## Step 5: 音声抽出

**スクリプト**: [`scripts/hls_downloader.py`](scripts/hls_downloader.py)

```bash
# 動画から音声を抽出（MP3形式）
python scripts/hls_downloader.py --extract-audio "videos/[章番号]_[タイトル].mp4" "audio/[章番号].mp3"
```

---

## Step 6: 文字起こし

**スクリプト**: [`scripts/transcribe.py`](scripts/transcribe.py)

```bash
# Groq Whisperで文字起こし
python scripts/transcribe.py "audio/[章番号].mp3" "transcripts/[章番号].txt"
```

**特徴**:
- 3分チャンクで分割（安定性重視）
- 並列処理（チャンク数に応じて3〜10並列）
- レート制限時は自動リトライ
- GROQ_API_KEYは`.env`ファイルから自動読み込み

---

## Step 7: スクリーンショット抽出

**スクリプト**: [`scripts/screenshot_extractor.py`](scripts/screenshot_extractor.py)

```bash
# pHashモード（デフォルト・推奨）: スライド変化を検出して重複を排除
python scripts/screenshot_extractor.py "videos/[章番号]_[タイトル].mp4" "screenshots/[章番号]"

# pHash閾値を調整（デフォルト=8, 小さいほど多く取る）
python scripts/screenshot_extractor.py "videos/[章番号]_[タイトル].mp4" "screenshots/[章番号]" --phash-threshold 6

# レガシーモード: 30秒間隔（pHashが使えない環境用）
python scripts/screenshot_extractor.py "videos/[章番号]_[タイトル].mp4" "screenshots/[章番号]" --no-phash --interval 30
```

**特徴**:
- pHashモード（デフォルト）でスライド切替・UI変化を正確に検出
- 重複フレームを自動で排除（30秒間隔方式の弱点を解消）
- コンテンツ変化量に応じて枚数が自動調整される（スライド中心=少なめ、デモ中心=多め）
- imagehash + Pillow が必要（`pip install imagehash Pillow`）

---

## Step 8: マニュアル作成

**MANDATORY**: [`writing-style.md`](writing-style.md) を読むこと。

### 文章スタイルのルール

- 箇条書き・表の多用は避ける
- 文章で流れるように説明
- 動画の語り口調を活かす
- 読者への問いかけを使う
- 最後に明確なアクションを提示

---

## Step 9: マニュアルのレビューと修正

> **BLOCKER**: マニュアル生成後のレビューは必須。生成完了 ≠ 完了。
> 各Agentに委譲する場合も、Agentプロンプトに必ず以下を含めること:
> - "writing-style.md と image-alignment.md を必ず読むこと"
> - "Step 9のレビューチェックリストを全項目通過するまで完了報告しないこと"
> - "画像と文章の整合性を画像内容を確認しながらチェックすること"

**MANDATORY**: マニュアル作成後、必ず以下のレビューを実施し、問題があれば修正すること。

### 9-1. 画像チェック

**必須確認項目**:
- [ ] 各セクションに最低1枚は画像が貼られているか
- [ ] 画像パスが正しいか（`../screenshots/XX/frame_XXX.jpg`形式）
- [ ] 画像の内容に文章で言及しているか（「上の画像にあるように〜」など）

```bash
# 画像の参照数を確認
grep -c "!\[" manuals/[章番号]_*.md

# 各セクション（##）に画像があるか確認
grep -E "^##|!\[" manuals/[章番号]_*.md
```

### 9-1-1. 画像が不足している場合の対処

画像が不足している場合は、以下の手順で追加する:

**手順1: 文字起こしから画像が必要な箇所を特定**

文字起こしを読み、以下のような箇所を特定:
- 操作手順の説明（「ここをタップして」「この画面で」など）
- 設定画面の説明
- 図解やスライドへの言及
- ツールのインターフェース説明

**手順2: 必要なタイムスタンプを推定**

文字起こしの位置から、動画内のおおよそのタイムスタンプを推定:
- 文字起こしの全体の長さと、該当箇所の位置から割合を計算
- 動画の長さに割合を掛けて、おおよその秒数を算出

例: 文字起こし全体が3000文字、該当箇所が1500文字目付近、動画が10分(600秒)の場合
→ 1500/3000 × 600 = 300秒(5分)付近

**手順3: 追加のスクリーンショットを抽出**

```bash
# 特定のタイムスタンプでフレームを抽出
python scripts/screenshot_extractor.py "videos/[章番号]_[タイトル].mp4" "screenshots/[章番号]" --timestamps "120,180,240,300"

# または、より細かい間隔で再抽出（例: 15秒間隔）
python scripts/screenshot_extractor.py "videos/[章番号]_[タイトル].mp4" "screenshots/[章番号]" --interval 15
```

**手順4: 抽出した画像を確認してマニュアルに追加**

1. Readツールで抽出した画像を確認
2. 適切な画像をマニュアルの該当箇所に追加
3. 画像の内容に言及する文章も追加

```markdown
![設定画面](../screenshots/XX/ts_001_00180.jpg)

上の画像にあるように、この設定画面では〜
```

### 9-1-2. 画像が必要な典型的なパターン

以下のパターンでは画像が必須:

1. **操作手順**: 「タップ」「クリック」「選択」などの動作がある場合
2. **設定変更**: 「オンにする」「チェックを入れる」などの場合
3. **画面説明**: 「この画面」「ここに表示される」などの場合
4. **比較説明**: 「Before/After」「変更前/変更後」の場合
5. **複雑な概念**: 図解があると理解しやすい場合

### 9-2. 読みやすさチェック

**確認項目**:
- [ ] 箇条書きが3つ以上連続していないか
- [ ] 表が2つ以上連続していないか
- [ ] セクション間の繋がりは自然か（「では」「さて」「ここで」などの接続）
- [ ] 動画の語り口調が活きているか
- [ ] 最後に明確なアクション（次にやること）があるか

### 9-3. 整合性チェック

**MANDATORY**: [`image-alignment.md`](image-alignment.md) を読むこと。

1. **各画像の内容を確認**: Readツールで画像ファイルを読み込む
2. **画像内のテキスト・図を把握**: タイトル、見出し、図解の内容をメモ
3. **整合性を確認**: 画像を参照する箇所の文章が、画像の内容と一致しているか
4. **不一致があれば修正**: 画像の内容に合わせて文章を調整

### 9-4. 修正の実施

レビューで問題が見つかった場合は、**必ず修正してから次の章に進む**。

```
✅ レビュー完了チェックリスト
- 画像: 各セクションに配置済み
- 読みやすさ: 箇条書き過多なし、セクション接続OK
- 整合性: 画像と文章の内容が一致
```

---


## Agent委譲時の必須指示テンプレート

マニュアル生成を複数Agentに分散する場合、以下のテンプレートに従う:

````
Agent(
  model: "sonnet",
  prompt: """
  必ず以下を読んでから生成開始:
  - ~/.claude/skills/utage-manual/writing-style.md
  - ~/.claude/skills/utage-manual/image-alignment.md
  
  生成対象: ch{N}-{M}
  
  各章について:
  1. transcript.txt 全文読込 (BLOCKER)
  2. screenshots/ から最低5枚をRead (画像内容把握 - BLOCKER)
  3. マニュアル生成 (writing-style.md準拠)
  4. レビュー実施:
     - 各セクションに画像があるか
     - 画像と文章の内容が整合しているか
     - 箇条書き3つ以上連続していないか
     - 流れる文章になっているか
  5. レビューで問題があれば修正してから完了報告
  
  完了報告時にレビュー結果も含めること。
  """
)
````

### NG/OK対照表

| NG | OK | 理由 |
|---|---|---|
| Agentにマニュアル生成依頼するときレビュー指示なし | レビュー指示必須 | レビューなしだと整合性破綻 |
| 画像を読まずにファイル名から推測 | 必ずReadで画像内容確認 | ファイル名は内容を表さない |
| writing-style.md読まずに生成 | 必ず読んでから | スタイル一貫性のため |

---

## Step 10: 全章結合版の作成（オプション）

全章のマニュアルを1つのファイルに結合:

```markdown
# [講座名] 完全マニュアル

## 目次

[各章へのリンクを生成]

---

# 第X章：[タイトル]

[各章のマニュアル内容を結合]

...
```

---

## 必要環境

- GROQ_API_KEY（`.env`ファイルに保存済み）
- ffmpeg（動画処理）
- Python 3 + requests（文字起こしスクリプト用）
- Chrome + Claude in Chrome拡張機能

### スクリプト一覧

| スクリプト | 用途 |
|---|---|
| [`scripts/hls_downloader.py`](scripts/hls_downloader.py) | HLS動画ダウンロード＋音声抽出 |
| [`scripts/transcribe.py`](scripts/transcribe.py) | Groq Whisper文字起こし（並列処理） |
| [`scripts/screenshot_extractor.py`](scripts/screenshot_extractor.py) | スクリーンショット抽出（間隔/シーン検出） |

### インストール

```bash
# 必要なPythonパッケージ
pip install requests

# ffmpegのインストール（macOS）
brew install ffmpeg
```
