---
name: manabi-ingest
description: "動画講座やドキュメントを標準フォーマット（course-bundle）に変換し、ナレッジ抽出・マニュアル生成・スキル化までの全パイプラインをオーケストレーション。UTAGE / YouTube / Udemy / Notion / ローカルファイル等に対応。取り込み後にユーザーに処理レベル（ナレッジのみ / マニュアル / スキル化）を確認。「学びを取り込み」「manabi ingest」「講座を取り込み」「コースバンドル作成」「講座を処理」で発動。"
---

# Manabi Ingest スキル（学習素材オーケストレーター）

## WHAT

動画講座コンテンツを標準フォーマット（course-bundle）に変換し、
ユーザーが選んだレベルに応じてナレッジ抽出・マニュアル生成・スキル化まで一気通貫で実行する。

## WHY

- 講座取り込みから成果物生成まで手作業で繋ぐのは非効率
- 標準フォーマットがあれば後続処理（ナレッジ抽出、マニュアル生成、スキル化）を共通化できる
- レベル選択により、必要な深さだけ処理できる

## HOW

### Phase A: Course-Bundle 作成

#### Step 0: 入力タイプの判定

| 入力 | 判定方法 | 処理パイプライン |
|------|----------|----------------|
| UTAGE URL | `utage-system.com` を含むURL | Chrome抽出→HLS DL→文字起こし→スクショ→ページテキスト・リンク抽出 |
| YouTube URL | `youtube.com` or `youtu.be` を含むURL | video-downloaderでDL→文字起こし→スクショ |
| Udemy URL | `udemy.com` を含むURL | Chrome連携→動画DL→文字起こし→スクショ→補足資料取得 |
| Loom URL | `loom.com` を含むURL | 動画DL→文字起こし→スクショ→説明文取得 |
| ローカル動画ファイル | `.mp4`, `.mkv`, `.webm` などのファイルパス | 文字起こし→スクショ |
| 既存transcript+screenshots | ディレクトリパス（transcripts/やscreenshots/を含む） | normalize_bundle.pyで正規化のみ |

**BLOCKER**: 入力タイプが判定できない場合はユーザーに確認する。勝手に推測して進めない。

対応プラットフォーム:
- UTAGE: 動画+説明文+リンク+配布物
- Udemy: 動画+補足資料+リンク
- Loom: 動画+説明文
- YouTube: 動画+概要欄
- ローカル: 動画ファイル or 既存データ
- テキストのみの章: ページ全文取得（動画なし）

講座にはテキストだらけの章、動画中心の章、外部リンクが多い章など
様々なパターンがある。Chrome連携時に検知したコンテンツは
可能な限り取得する。必須ではないが、あれば品質が上がる。

#### Step 1: ヒアリング

取り込み処理を開始する前に、講座の概要をユーザーに聞く。
この情報があると、リソース検知の精度とスキル計画の質が大幅に上がる。

```
📦 Manabi Ingest

入力: [判定した入力タイプと内容]
出力先: [出力ディレクトリ]

📋 講座について教えてください（わかる範囲で）

・どんな内容の講座ですか？（一言で）
・配布物はありますか？
  （テンプレート、PDF、Notionページ、スプレッドシート等）
・この講座から作りたいスキルのイメージはありますか？

例: 「AI台本作成の講座。Notionにプロンプトテンプレートが
何個かある。テンプレートを使って台本自動生成するスキルが
作れるといい」
```

ユーザーの回答を manifest.json に保存:
```json
{
  "user_context": {
    "description": "AI台本作成の講座",
    "expected_resources": ["Notionプロンプトテンプレート"],
    "skill_hypotheses": ["テンプレートで台本自動生成"],
    "notes": ""
  }
}
```

この情報は以降のフェーズで活用する:
- **リソース検知時**: expected_resourcesを手がかりにNotionリンク等を重点チェック
- **skill-planner**: skill_hypothesesとの照合で仮説→検証の流れを作る

#### Step 1.5: 処理計画提示

ヒアリング回答を受けたら、処理を開始する前に具体的な計画をユーザーに提示する:

```
📋 処理計画
- 検出: N章
- DL予定: N本 (推定 X分)
- 並列度: 5並列ダウンロード
- 文字起こし: 6 Agent並列 (sonnet)
- スクショ抽出: 並列
- 推定所要時間: 約X分
この計画で進めますか？
```

**BLOCKER**: ユーザーの確認を得るまで取り込み処理を開始しない。

#### Step 2: 入力タイプ別パイプライン

##### UTAGE URL の場合

1. utage-manualスキルの手順でChrome連携→章一覧取得
2. 各章のHLS URLを取得
3. `~/.claude/skills/utage-manual/scripts/hls_downloader.py` でダウンロード
4. `~/.claude/skills/utage-manual/scripts/transcribe.py` で文字起こし
5. `~/.claude/skills/utage-manual/scripts/transcribe.py --timestamps` でタイムスタンプ付きJSON生成
6. `~/.claude/skills/utage-manual/scripts/screenshot_extractor.py` でスクリーンショット抽出（pHashモード・デフォルト）
7. **ページテキスト・リンク抽出**（後述）
8. Step 3 へ

##### YouTube URL の場合

1. video-downloaderスキルで動画をダウンロード
2. `~/.claude/skills/utage-manual/scripts/transcribe.py` で文字起こし
3. `~/.claude/skills/utage-manual/scripts/transcribe.py --timestamps` でタイムスタンプ付きJSON生成
4. `~/.claude/skills/utage-manual/scripts/screenshot_extractor.py` でスクリーンショット抽出（pHashモード・デフォルト）
5. Step 3 へ

##### ローカル動画ファイルの場合

1. `~/.claude/skills/utage-manual/scripts/transcribe.py` で文字起こし
2. `~/.claude/skills/utage-manual/scripts/transcribe.py --timestamps` でタイムスタンプ付きJSON生成
3. `~/.claude/skills/utage-manual/scripts/screenshot_extractor.py` でスクリーンショット抽出（pHashモード・デフォルト）
4. Step 3 へ

##### 既存transcript+screenshots の場合

1. 直接 Step 3 へ

#### スクリーンショット抽出について

screenshot_extractor.py は**pHash (perceptual hash) モード**をデフォルトで使用:
- スライド切替・UI変化を正確に検出
- 重複フレームを自動排除
- コンテンツ変化量に応じて枚数が自動調整
  - スライド中心章 → 少なめ（例: 6分動画で8枚）
  - デモ中心章 → 多め（例: 17分動画で45枚）
- 30秒固定間隔モードはレガシー扱い（`--no-phash` で呼び出し）

依存: `pip install imagehash Pillow`

#### Step 2.5: ページテキスト・リンク抽出（Chrome連携時）

各章のページにアクセスした際、動画以外のコンテンツも取得する:

1. **テキスト抽出**: 動画の下/周辺にある説明文・補足テキストを取得
2. **リンク抽出**: ページ内の全リンクを収集
   - Notion ページ、Google Drive、PDF ダウンロードリンク等
   - 「プレゼント」「特典」「配布物」セクションを重点チェック
3. 保存先:
   - `chapters/{id}/page_text.md` — ページのテキストコンテンツ
   - `chapters/{id}/links.json` — 検出したリンク一覧

links.json の形式:
```json
[
  {
    "text": "リンクテキスト",
    "url": "https://...",
    "context": "特典セクション",
    "type": "notion|gdrive|pdf|other"
  }
]
```

#### Step 2.6: 外部リソース取得

全章のリンク収集後、フェッチ可能なリソースを取得する:

1. 全章の links.json を集約
2. フェッチ可能なリソースを検出（Notion ページ、PDF、テンプレート等）
3. Chrome 経由でアクセス可能なものを取得
4. 保存先: `resources/` ディレクトリ（種別ごとにサブディレクトリ）
5. `resources-manifest.json` を生成

resources-manifest.json の形式:
```json
{
  "fetched": [
    {
      "source_url": "https://...",
      "source_chapter": "03",
      "type": "pdf|notion|template",
      "local_path": "resources/pdfs/filename.pdf",
      "title": "リソースタイトル",
      "status": "fetched|failed|skipped"
    }
  ]
}
```

**NOTE**: リソース取得は best-effort。認証が必要なものやアクセスできないものは skipped にして続行。

#### Step 3: normalize_bundle.py で正規化

```bash
python ~/.claude/skills/manabi-ingest/scripts/normalize_bundle.py \
  --input "/path/to/source_dir" \
  --output "/path/to/course-bundle" \
  --course-name "講座名" \
  --speaker "講師名" \
  --source-type "utage|youtube|local"
```

**BLOCKER**: 正規化前に、以下を確認する:
- transcripts/ ディレクトリに .txt ファイルが存在すること
- screenshots/ ディレクトリにサブディレクトリが存在すること

#### Step 4: manifest.json のバリデーション

正規化後、manifest.json の全パスが実在するファイルを指しているか検証する。

```bash
python -c "
import json, os, sys
with open(sys.argv[1]) as f:
    m = json.load(f)
ok = True
for ch in m['chapters']:
    for key in ['transcript_path', 'transcript_ts_path', 'screenshots_dir']:
        path = os.path.join(os.path.dirname(sys.argv[1]), ch.get(key, ''))
        if path and not os.path.exists(path):
            print(f'MISSING: {path}')
            ok = True if key == 'transcript_ts_path' else False
if ok:
    print('All paths valid')
else:
    print('VALIDATION FAILED')
    sys.exit(1)
" "/path/to/course-bundle/manifest.json"
```

**BLOCKER**: バリデーション失敗時は処理を中断し、ユーザーに報告する。

#### Step 5: Bundle 完了報告 + レベル選択

```
✅ Course Bundle 作成完了

📁 出力先: [出力ディレクトリ]
📋 章数: [N]章
📊 ステータス:

| 章 | タイトル | transcript | screenshots | page_text | links | status |
|----|---------|-----------|-------------|-----------|-------|--------|
| 00 | [title] | ✅         | ✅ (31枚)    | ✅        | 3件   | complete |
| 01 | [title] | ✅         | ✅ (25枚)    | ❌        | 0件   | complete |
...

manifest.json のパスバリデーション: ✅ 全パス正常
外部リソース: [N]件取得 / [M]件スキップ
```

直後にレベル選択を提示:

```
どこまで処理しますか？

1️⃣ ナレッジ抽出のみ
   → 概念・暗黙知・手順・画像分類を構造化

2️⃣ ナレッジ + マニュアル生成
   → 上記 + 画像付きMarkdownマニュアル（人間向け）

3️⃣ ナレッジ + マニュアル + スキル化
   → 上記 + 実行可能なClaude Codeスキル自動生成
   → スキル化前にプランを提示して承認を取ります
```

**BLOCKER**: ユーザーの選択を待つ。勝手にレベルを決めない。

---

### Phase B: レベル別パイプライン実行

#### Level 1: ナレッジ抽出

実行順序（各extractor は sonnet & 並列必須）:
1. **concept-extractor** sonnet, 4並列（章を分割して4 Agent同時起動）— マニュアルがあればマニュアルを一次ソースとして使用
2. **visual-indexer** sonnet, 4並列（コスト重いため並列必須）— スクリーンショットの分類・タグ付け
3. **procedure-extractor** sonnet, 4並列 — visual-index 完了後に実行（画像参照が必要なため）

#### Level 2: ナレッジ + マニュアル生成

Level 1 の全処理に加え:
4. **utage-manual** sonnet, 6並列 — 画像付き Markdown マニュアル生成
5. **レビュー必須**: マニュアル生成後は必ず image-alignment.md・writing-style.md に従ってレビュー実施（省略不可）
6. concept-extractor がマニュアルを一次ソースとして再抽出可能（より高品質なナレッジ）

#### Level 3: ナレッジ + マニュアル + スキル化

Level 2 の全処理に加え:
7. **skill-planner** opus — スキル化プランを生成してユーザーに提示
   - **BLOCKER**: プランへのユーザー承認を待つ
8. **skill-synthesizer** opus — 承認されたスキルを生成（**staging dir 経由で cp**、~/.claude/skills/ への直接書き込み不可）

---

## 並列実行パターン

各extractor呼び出し時は必ず以下のテンプレートに従う:

```
Agent起動時の必須パラメータ:
- model: "sonnet"  ← extractor系は必ずsonnet
- run_in_background: true
- mode: "bypassPermissions"

章をN分割してN Agent並列起動:
- 36章 → 4-6 Agent (各6-9章担当)
- visual-indexer: 特にコスト重い → 必ずsonnet & 並列必須
```

並列度の目安:

| 処理 | 並列数 | モデル |
|------|--------|--------|
| concept-extractor | 4並列 | sonnet |
| visual-indexer | 4並列 | sonnet |
| procedure-extractor | 4並列 | sonnet |
| マニュアル生成 | 6並列 | sonnet |
| skill-planner | 1（単発） | opus |
| skill-synthesizer | 1（単発） | opus |

---

## レビューチェックポイント（先行1章方式）

全章レビューは遅い。全くレビューしないと品質崩壊。
**解決策**: 1-2章だけ先行完了させてサンプルレビュー → OKなら残り章を並列一気処理。

### 4つのチェックポイント

```
Phase A: 取り込み
  ↓
🔍 レビューA: 1章のtranscript + 5枚スクショをサンプル確認
  → 文字起こし精度OK？スクショ枚数・内容OK？
  → NG: 設定変更（chunk_seconds, interval等）して再実行
  → OK: 全章並列処理を継続

Phase B Level 1: ナレッジ抽出
  ↓
🔍 レビューB: 1章のknowledge.json + visual-index.json + procedures.json
  → 概念抽出の粒度OK？画像分類OK？手順の粒度OK？
  → NG: プロンプト調整して再実行
  → OK: 残り全章の並列処理を継続

Phase B Level 2: マニュアル生成
  ↓
🔍 レビューC: 2章のマニュアル（短い章+長い章）
  → 文章スタイルOK？画像配置OK？整合性OK？
  → NG: writing-style.md参照 + 該当章のみ再生成
  → OK: 残り全章継続

Phase B Level 3: skill-planner完了後
  ↓
✅ プラン承認BLOCKER（既存）
  ↓
Phase B Level 3: skill-synthesizer完了後
  ↓
🔍 レビューD: 1スキルのSKILL.mdサンプル確認
  → 実行可能？プロンプトテンプレ入ってる？
  → NG: synthesizer再実行
  → OK: 完了報告
```

### サンプル選定ルール

| レビュー | サンプル選定 |
|---------|------------|
| レビューA | 中位の章（1章目は導入で短いことが多い） |
| レビューB | 概念・手順両方含む章（分類できないから） |
| レビューC | 短い章 + 長い章の2本（両極の品質を確認） |
| レビューD | 最初に完成したexecutable skill（1本で良い） |

### 並列処理との両立

並列処理は**止めない**。以下のやり方でサンプルレビューを組み込む:

1. **先行1章方式**: 全Agent起動するが、1つのAgentだけ1章担当にする
2. その1章が最初に完了 → サンプル提示 → ユーザー確認
3. 確認中も残りAgentは処理継続
4. 確認NG → 残りAgentを停止 → プロンプト調整 → 再起動
5. 確認OK → そのまま全章完了を待つ

### BLOCKER

- **レビューD**のみ承認必須BLOCKER。
- レビューA/B/Cは**警告**扱い（確認しながら処理継続可）。
- 重大な問題（パス不整合・エラー率高）が検出された場合のみ処理停止。

---

## 出力フォーマット: course-bundle

```
course-bundle/
  manifest.json
  chapters/
    00/
      transcript.txt
      transcript_ts.json
      screenshots/
        title.jpg
        frame_001.jpg ...
      page_text.md
      links.json
      manual.md             ← utage-manual output (Level 2+)
    01/ ...
  resources/
    prompts/
    pdfs/
    templates/
  resources-manifest.json
```

### manifest.json の構造

スキーマ: `~/.claude/skills/manabi-ingest/schemas/manifest.schema.json`

```json
{
  "course_name": "YouTube Booster",
  "source_type": "utage",
  "source_url": "https://...",
  "language": "ja",
  "speaker": "おさる",
  "chapters": [
    {
      "id": "03",
      "title": "生成AIを使いこなす4つの原理原則",
      "duration_seconds": 612,
      "transcript_path": "chapters/03/transcript.txt",
      "transcript_ts_path": "chapters/03/transcript_ts.json",
      "screenshots_dir": "chapters/03/screenshots/",
      "screenshot_count": 31,
      "page_text_path": "chapters/03/page_text.md",
      "links_path": "chapters/03/links.json",
      "status": "complete"
    }
  ]
}
```

---

## NG / OK パターン

| NG | OK | 理由 |
|----|-----|------|
| ユーザー確認なしで処理開始 | Step 1で確認してから開始 | 出力先や講座名の確認が必要 |
| manifest.jsonのパスを検証せずに完了報告 | Step 4で全パスを検証 | 壊れたbundleを渡すと後続処理が全部失敗する |
| 存在しないtranscriptを「status: complete」にする | ファイル有無で正確にstatusを設定 | 嘘の状態は後から追跡不能 |
| 元ファイルを移動・削除する | コピーして元は保持 | 元データを壊すと取り返しがつかない |
| transcript_ts.jsonがないのにエラーにする | statusを「partial」にして続行 | タイムスタンプは必須ではない |
| レベル選択を提示せずにナレッジ抽出を開始 | Bundle完了後にレベル選択を提示 | ユーザーが処理範囲を決める |
| スキル化プランを承認なしで実行 | プラン提示→承認→実行 | 不要なスキルを生成しない |
| リソース取得失敗でパイプライン全体を止める | skippedにして続行 | リソース取得はbest-effort |
| ページテキストがないことをエラーにする | 取得できたものだけ保存 | 動画のみの章もある |
| extractorをopusで実行 | sonnetで実行 | コスト3-5倍差 |
| 1 Agentで全章順次処理 | 章を分割してN Agent並列 | 速度N倍 |
| マニュアル生成後にレビュー省略 | image-alignment.mdに従ってレビュー | 整合性検証必須 |
| skill-synthesizerが ~/.claude/skills/ に直接書く | staging dir経由でcp | Write権限ブロック対策 |
| 全章完了してからまとめてレビュー | 先行1章でサンプルレビュー | 手戻りコスト最小化 |
| サンプルレビューで並列処理を止める | 並列継続しつつ確認 | 速度を犠牲にしない |
| 30秒間隔でスクショ抽出（--no-phash） | pHashモード（デフォルト）で抽出 | スライド見落とし・重複を防げる |

---

## セルフ検証チェックリスト

処理完了時に以下を確認:

### Phase A（Bundle作成）
- [ ] manifest.json が存在し、JSON として valid
- [ ] manifest.json の全 transcript_path が実在ファイルを指す
- [ ] manifest.json の全 screenshots_dir が実在ディレクトリを指す
- [ ] 各章の screenshot_count が実際のファイル数と一致
- [ ] status が各章の実態を正確に反映（complete / partial / pending）
- [ ] 元ファイルが変更・削除されていない
- [ ] page_text.md / links.json は取得できた章のみ存在
- [ ] resources-manifest.json が存在し、各エントリのstatusが正確

### Phase B（レベル別処理）
- [ ] ユーザーが選択したレベルの処理が全て完了
- [ ] Level 2+: 全章のmanual.mdが生成されている
- [ ] Level 3: スキル化プランがユーザー承認済み
- [ ] Level 3: 承認されたスキルのSKILL.mdが生成されている

---

## 必要環境

- Python 3
- ffmpeg（動画処理時）
- GROQ_API_KEY（文字起こし時、`.env`ファイルに保存）
- Chrome + Claude in Chrome拡張（UTAGE/Udemy URL時）

## 依存スキル・スクリプト

| 用途 | パス |
|------|------|
| HLSダウンロード | `~/.claude/skills/utage-manual/scripts/hls_downloader.py` |
| 文字起こし | `~/.claude/skills/utage-manual/scripts/transcribe.py` |
| スクリーンショット抽出 | `~/.claude/skills/utage-manual/scripts/screenshot_extractor.py` |
| YouTubeダウンロード | video-downloader スキル |
| 正規化 | `~/.claude/skills/manabi-ingest/scripts/normalize_bundle.py` |
| ナレッジ抽出 | concept-extractor スキル |
| 画像分類 | visual-indexer スキル |
| 手順抽出 | procedure-extractor スキル |
| マニュアル生成 | utage-manual スキル |
| スキル化プラン | skill-planner スキル |
| スキル生成 | skill-synthesizer スキル |
