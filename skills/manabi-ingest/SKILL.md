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

### Phase 0: 学びホーム（ライブラリ）

全ての取り込み成果物は**学びホーム**に集約する（作業はプロジェクト、資産はホーム）。

- ホームの場所は `~/.claude/manabi-home`（1行のパスファイル）が指す
- **このファイルが無ければ初回**。以下を実行してから本処理に進む:

```
📚 学びライブラリをどこに作りますか？
   デフォルト: ~/ManabiLibrary
   → ここでいいですか？（一度決めたら以降は聞きません）
```

```bash
mkdir -p <ホーム>/bundles <ホーム>/.index
echo '<ホーム>' > ~/.claude/manabi-home
# config.json（名前・作成日）も作る
```

- 出力先のデフォルトは `<ホーム>/bundles/<教材名>/`（Step 1の確認は従来どおり行う）
- 既存マニュアル・バンドルの移行: `scripts/migrate_to_library.py` を使う
  - 新形式はそのまま移動、旧形式（manuals/*.md）はmanifest生成のみで中身無加工
  - 同一講座のbundle+manualペアは `--pair-into` でbundle内source_media/に同居させ1講座1エントリを保つ
初回のホーム作成直後に、ダッシュボードのセットアップを提案する:

```
📊 ダッシュボード（manabi-hub）もセットアップしますか？
   → 蔵書が並ぶWebダッシュボード。検索・フィルタ・リーダー・テーマ切替付き
   → Node.js 18+ が必要です
```

Yesの場合:
```bash
git clone https://github.com/naoterumaker/manabi-hub.git ~/manabi-hub
cd ~/manabi-hub && npm install && npm run build
起動: (nohup npm start > /tmp/manabi-hub.log 2>&1 &) → http://localhost:3939
```
以後の起動用に `~/.claude/skills/manabi-hub/SKILL.md`（起動スキル）を
manabi-hubリポジトリ内の `docs/launcher-skill.md` からコピーして作成する。

Noの場合（またはNode.jsがない場合）:
閲覧はbundle_to_html.pyの単一HTML書き出しで代替できる（依存ゼロ）。

### Phase A: Course-Bundle 作成

#### Step 0: 入力タイプの判定

| 入力 | 判定方法 | 処理パイプライン |
|------|----------|----------------|
| UTAGE URL | `utage-system.com` を含むURL | Chrome抽出→HLS DL→文字起こし→スクショ→ページテキスト・リンク抽出 |
| YouTube URL | `youtube.com` or `youtu.be` を含むURL | video-downloaderでDL→文字起こし→スクショ |
| Udemy URL | `udemy.com` を含むURL | Chrome連携→動画DL→文字起こし→スクショ→補足資料取得 |
| Loom URL | `loom.com` を含むURL | 動画DL→文字起こし→スクショ→説明文取得 |
| note記事 URL | `note.com/{user}/n/` を含むURL | Chrome抽出→h2章分割→画像DL→note_to_bundle.py（後述） |
| noteマガジン URL | `note.com/{user}/m/` を含むURL | 記事一覧を章一覧として提示→各記事を上記処理 |
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

📁 出力先フォルダ（必ず確認する）:
   デフォルト: [学びホーム]/bundles/[教材名]/
   → ここでいいですか？変更する場合はパスを指定してください

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
**出力先フォルダはStep 1で必ず明示的に質問する**（表示するだけでは不十分。回答を得てから進む）。

#### Step 2: ルート選択と入力タイプ別パイプライン

**2ルート構造**: 教材は「講座系」と「記事系」の2ルートに分かれる。両者は主素材と補助素材が
鏡像の関係にあり、どちらも同じcourse-bundleに正規化されて合流する。

| ルート | 主素材 | 補助素材 | 対象入力 |
|--------|--------|----------|----------|
| **A: 講座ルート** | 動画（transcript + スクショ） | ページ文章（page_text.md）・リンク・配布物 | UTAGE / YouTube / Udemy / Loom / ローカル動画 |
| **B: 記事ルート** | 本文（article.md）+ 記事内画像 | 埋め込み動画（video/）・リンク・特典 | note / Brain / 汎用Web記事（無料・有料とも） |

**設計原則（if文の堰き止め）**:
- `source_type` による分岐は**このStep 2のルート選択だけ**。ここが唯一のif文
- Phase B（抽出以降）は章の `content_type`（video/article/hybrid）**のみ**を参照する。
  Phase B以降でsource_typeを参照するのは設計違反（プラットフォームが増えるたびに
  後段へ分岐が染み出すのを防ぐ）
- 講座内の文章（ページ説明文）はルートAの補助素材として、記事内の動画はルートBの
  補助素材として、それぞれのルートの中で処理する。ルートをまたぐif文を書かない
- 例外は「主役判定」（記事なのに動画が主体）のみ。その場合はルートBからルートAに
  **切り替える**のであって、両ルートを混ぜない

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

##### 記事ルート（ルートB）共通: プラットフォーム別アダプタ

記事ルートで**プラットフォームごとに違うのは「アダプタ」（本文セレクタ＋ペイウォール判定）だけ**。
抽出JS・note_to_bundle.py・以降のパイプラインは全プラットフォーム共通。
新しい記事プラットフォームへの対応は、この表に1行足すことを意味する（パイプラインの複製はしない）。

| プラットフォーム | 本文コンテナ | ペイウォール検知 | 購入済み判定 |
|----------------|-------------|----------------|-------------|
| note.com | `.note-common-styles__textnote-body` | 「この続きをみるには」「購入手続きへ」 | 「購入済」表示 or 本文末尾がフッター到達 |
| Brain (brain-market.com) | （未調査。下記フォールバック手順で追加する） | — | — |
| 汎用Web記事 | 不定 → フォールバック手順 | — | — |

**未知サイトのフォールバック手順**（「本文が読めるか分からない」への答え）:
1. `article`タグ等の**祖先要素を安易に掴まない**（ヘッダー・フッターが混入する）
2. 本文候補コンテナをDOM調査する: 候補セレクタごとに `innerText.length` と `h2数` を
   evaluate_scriptで測り、本文だけを包む最小のコンテナを特定する
3. 抽出後、**取得文字数と冒頭・末尾をユーザーに提示**して「全文取れていますか？」を確認（BLOCKER）
4. 確認が取れたら、そのセレクタを上のアダプタ表に追記する（次回から調査不要）

##### note URL の場合

**前提**: 有料記事は**自分が購入済みのもののみ**対象。Chrome連携（ログイン済みセッション）で取得する。

1. Chromeで記事ページを開く
2. **ペイウォール確認（BLOCKER）**: 本文中に「この続きをみるには」「購入手続きへ」があれば
   **未購入のため取得不可**と報告して停止。回避は絶対に試みない。
   購入済み判定: ページ内の「購入済」表示、または本文末尾がフッター（ハッシュタグ・チップ欄）まで到達していること
3. 本文を抽出する。抽出JSは **`scripts/note_extract.js`** をReadして、その関数を
   そのままevaluate_scriptに渡す（SKILL.mdにはコードを書かない。修正はjsファイル側で行う）
   - マーカー仕様: `<<H2>>`章見出し / `<<IMG>>url<<CAP>>caption` / `<<VIDEO>>url<<VTITLE>>title`
   - **注意**: 本文コンテナは`.note-common-styles__textnote-body`。`article`セレクタは祖先要素を掴むので使わない

4. 抽出JSONを `note_to_bundle.py` でcourse-bundle化:
```bash
python ~/.claude/skills/manabi-ingest/scripts/note_to_bundle.py raw.json "/path/to/bundle"
```
   - h2見出しで章分割（目次・フッターは自動除外、リード文はイントロ章）
   - 記事内画像を各章の `screenshots/` にDL
   - 本文中のリンク・裸URLを `links.json` に記録（特典・配布物の検知用）

5. **埋め込み動画の確認（BLOCKER）**（⚠️ hybrid章の取り込みは未検証ルート: 初回実行時はサンプルレビューを厚めに）: 変換結果に動画があれば、必ずユーザーに提示:
```
⚠️ 記事内に動画がN本見つかりました
  ch02: 解説動画（YouTube・12分）
動画も取り込みますか？
→ はい: yt-dlp（--cookies-from-browser chrome）でDL→文字起こし→pHashスクショ。
       章は content_type: "hybrid" になり、video/とv{NN}_frame_*が追加される
→ いいえ: manifest.videos に status: "skipped" で記録して続行
       （後段の抽出でunresolvedとして明示される。静かな欠落にはしない）
```

6. **主役判定**: 本文が数百字しかなく長尺動画が主体の記事（動画講座のnote配布形式）は、
   記事の章構造に情報がないため**動画1本＝1章**の動画パイプラインに切り替える。
   迷う場合はユーザーに提示して選んでもらう:

| 条件 | 扱い |
|------|------|
| 本文が主・動画が補足 | 記事のh2構造で章分割、動画は章内に吊るす（基本形） |
| 動画が主・本文が添え書き | 動画1本＝1章。本文はpage_text.mdとして保存 |

7. Step 4（バリデーション）へ（note_to_bundle.pyが正規化まで行うためStep 3は不要）

##### noteマガジン URL の場合（⚠️ 未検証ルート: 初回実行時はサンプルレビューを厚めに）

1. Chromeでマガジンページを開き、記事一覧（タイトル・URL・有料/無料）を取得
2. 記事一覧を章一覧としてユーザーに提示し、処理対象を選択してもらう（動画講座の章選択と同じUI）
3. 選択された各記事に「note URL の場合」の処理を実行（記事1本＝1章）

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
OPTIONAL = {'transcript_ts_path'}  # 欠落を許容するキー
ok = True
for ch in m['chapters']:
    ctype = ch.get('content_type', 'video')
    keys = ['screenshots_dir']
    if ctype in ('video', 'hybrid'):
        keys += ['transcript_path', 'transcript_ts_path']
    if ctype in ('article', 'hybrid'):
        keys.append('article_path')
    for key in keys:
        rel = ch.get(key) or ''
        path = os.path.join(os.path.dirname(sys.argv[1]), rel)
        if rel and not os.path.exists(path):
            print(f'MISSING: {path}')
            if key not in OPTIONAL:
                ok = False  # 一度Falseになったら戻さない（上書き禁止）
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
1. **concept-extractor** sonnet, 4並列（章を分割して4 Agent同時起動）— マニュアルがあればマニュアルを一次ソースとして使用。concept-extractorとvisual-indexerは互いに独立なので**同時に起動してよい**
2. **visual-indexer** sonnet, 4並列（コスト重いため並列必須）— スクリーンショットの分類・タグ付け
3. **procedure-extractor** sonnet, 4並列 — visual-index 完了後に実行（画像参照が必要なため）

##### 章内完結ルール（並列Agentの鉄則）

**章＝自己完結ユニット。並列Agentは自分の担当章の箱の中だけを読み書きする。**

| ルール | 内容 |
|--------|------|
| 書き込み先は章の中だけ | `chapters/NN/knowledge.json`, `chapters/NN/visual-index.json`, `chapters/NN/procedures.json` |
| 全章統合は書かせない | `knowledge-graph.json`・`visual-catalog.json`は**全Agent完了後にメインセッション（または専用Agent1体）が1回だけ生成**。並列Agentに書かせると部分グラフの上書き合戦になる |
| custom_typesは先行1章で確定 | visual-indexerの講座固有型は先行1章のAgentが提案→確定した型定義を残りAgentのプロンプトに配布。各Agentに勝手に発明させない（タクソノミー分裂防止） |
| 必読リストはmanifest駆動 | 章の`content_type`を見て必読ファイルを決める。本文中の参照マーカー任せにしない |

##### content_type別の必読ファイル（BLOCKER）

| content_type | Agentが必ず全文読むもの |
|--------------|------------------------|
| video | transcript.txt + screenshots/ |
| article | article.md + screenshots/（画像0枚の章はvisual-index.jsonを空で出してスキップ） |
| hybrid | article.md + **video/transcript_*.txt** + screenshots/（記事画像`img_*`と動画フレーム`v*_frame_*`の両方） |

- hybrid章はテキスト量が跳ね上がるため**1Agent専属**にする（char_count＋動画分で見積もる）
- hybrid章でtranscriptを読まずにknowledge.jsonを出すのは検証で弾く
- `videos[].status: "skipped"`（未取り込み動画）がある章は、knowledge.jsonに
  「未処理動画あり（URL・長さ）」のunresolvedエントリを必ず記録する。**静かな欠落は禁止**
- 抽出結果には`source: "article" | "video"`を付ける（記事本文は原文、文字起こしはWhisper経由で信頼度が異なるため）

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

#### 仕上げ（全レベル共通・オプション）: HTMLビューア生成

どのレベルでも、処理完了報告の後に必ず提案する:

```
📖 HTMLビューアを生成しますか？
→ 左に章目次・右に本文＋画像の1ファイルビューア（ブラウザで開くだけ）
```

```bash
python ~/.claude/skills/manabi-ingest/scripts/bundle_to_html.py "/path/to/course-bundle"
# → bundle直下に manual_viewer.html を生成
```

- **役割分担**: MDは資産（原文・再抽出可能・Git管理）、HTMLは人間用ビューア（認知負荷対策）。manabi-hubセットアップ済みならブラウザでlocalhost:3939を開くだけでよい（再生成不要）。HTMLビューアは配布・共有用
- 表示ソースの優先順位: manual.md > article.md > transcript.txt（章ごとに自動選択）
- knowledge.jsonがあれば章冒頭に「💡この章の概念」折りたたみパネルを自動挿入
- 章ごと切り替え表示（左目次クリック / ←→キー / 前後章ボタン）
- 単一HTMLファイル・依存なし。画像はbundle内を相対参照するため**bundle直下から動かさない**
- 生成後、`file://` でChromeに開いて見た目を確認する

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
    00/                     ← 章＝自己完結ユニット
      transcript.txt        ← video/hybrid章
      transcript_ts.json
      article.md            ← article/hybrid章（note等の記事本文）
      video/                ← hybrid章の埋め込み動画
        video_01.mp4
        transcript_01.txt
      screenshots/
        title.jpg
        frame_001.jpg ...   ← 動画由来（講座動画）
        img_001.png ...     ← 記事由来
        v01_frame_001.jpg   ← 埋め込み動画由来（v{NN}_で名前空間分離）
      page_text.md
      links.json
      manual.md             ← utage-manual output (Level 2+)
      knowledge.json        ← Level 1+ 抽出結果（章の中に置く）
      visual-index.json
      procedures.json
    01/ ...
  knowledge/
    knowledge-graph.json    ← 全章統合。集約は最後に1回だけ
  resources/
    prompts/
    pdfs/
    templates/
  resources-manifest.json
  visual-catalog.json       ← 全章統合。同上
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
| 未購入の有料記事をペイウォール回避で取得 | 未購入と報告して停止 | 購入済みのみ対象。規約・著作権 |
| 埋め込み動画を無言でスキップ | 検知→ユーザー確認→取り込まない場合もskipped記録 | 静かな欠落は追跡不能 |
| 参照マーカー頼みで動画transcriptを読ませる | manifest.content_typeで必読リストを機械的に決定 | Agentがマーカーを見落とすと丸ごと欠落する |
| 並列Agentにknowledge-graph.jsonを書かせる | 集約は全Agent完了後に1回だけ | 部分グラフの上書き合戦になる |
| 各AgentにCustom_typesを発明させる | 先行1章で確定して残りAgentに配布 | タクソノミー分裂防止 |
| 出力先を表示だけして処理開始 | 出力先を明示的に質問し回答を得る | 意図しない場所への大量書き込み防止 |
| Phase B以降でsource_typeを分岐に使う | content_typeのみ参照 | 後段への分岐の染み出し防止 |
| 記事プラットフォーム対応でパイプラインを複製 | アダプタ表に1行追加 | 複製はメンテ地獄（改名事故の教訓） |
| 未知サイトで`article`タグを安易に掴む | 最小コンテナをDOM調査→全文確認 | 祖先要素はヘッダー・フッターが混入する |

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
| note記事→bundle変換 | `~/.claude/skills/manabi-ingest/scripts/note_to_bundle.py` |
| HTMLビューア生成 | `~/.claude/skills/manabi-ingest/scripts/bundle_to_html.py` |
| 正規化 | `~/.claude/skills/manabi-ingest/scripts/normalize_bundle.py` |
| ナレッジ抽出 | concept-extractor スキル |
| 画像分類 | visual-indexer スキル |
| 手順抽出 | procedure-extractor スキル |
| マニュアル生成 | utage-manual スキル |
| スキル化プラン | skill-planner スキル |
| スキル生成 | skill-synthesizer スキル |
