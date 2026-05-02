---
name: concept-extractor
description: "講座トランスクリプトから概念・定義・暗黙知・重要引用・教え方パターンを構造化抽出しknowledge.jsonとknowledge-graph.jsonを生成。course-ingestのcourse-bundleを入力とする。「概念抽出」「ナレッジ抽出」「concept extract」「知識抽出」で発動。テキストのみで完結（画像不要）。procedure-extractorやvisual-indexerと並列実行可能。"
---

# Concept Extractor

## 推奨実行モデル & 並列化

**モデル**: `sonnet` 必須（opusはコスト3-5倍。精度差は小さい）

**並列化**: 章をN分割してN Agent並列起動

| 章数 | 推奨並列度 | 各Agent担当章数 |
|------|----------|--------------|
| ~12章 | 2 Agent | 6章ずつ |
| ~24章 | 4 Agent | 6章ずつ |
| ~36章 | 4-6 Agent | 6-9章ずつ |
| 36章+ | 6 Agent | 6-10章ずつ |

**Agent起動テンプレート**:
```
Agent(
  model: "sonnet",
  mode: "bypassPermissions",
  run_in_background: true,
  prompt: "Process chapters NN-NN of [bundle_path]..."
)
```

**注意**: visual-indexerは画像を全Read するため最もコスト重い。**必ずsonnet+並列**。opusで全章順次は禁じ手。

---

## WHAT

講座のcourse-bundle（manifest.json + 各章のmanual.md/transcript.txt）を入力として、6カテゴリの構造化知識を抽出する。

**出力ファイル:**

| ファイル | 粒度 | 内容 |
|---------|------|------|
| `knowledge/chXX-knowledge.json` | 章単位 | concepts, key_quotes, tacit_knowledge, teaching_patterns, cross_references, resource_references |
| `knowledge/knowledge-graph.json` | コース全体 | 前提関係グラフ、概念階層、横断テーマ |

**スコープ外:**
- 画像・スライドの分析（visual-indexerの責務）
- 手順・ワークフローの抽出（procedure-extractorの責務）
- トランスクリプトの作成・整形（course-ingestの責務）

---

## WHY

トランスクリプトは長大で非構造的。そのままではRAGに使えず、マニュアル生成にも活用しにくい。概念・定義・暗黙知を構造化することで:

1. マニュアル生成スキルが正確な定義を引用できる
2. 前提関係グラフにより学習順序を最適化できる
3. 話者の暗黙知が明示化され、AIエージェントのナレッジベースに組み込める

---

## HOW

### 入力要件

| 必須 | 内容 |
|------|------|
| manifest.json | course-ingestが生成したコース構成ファイル |
| chapters/chXX/manual.md または transcript.txt | 各章のソーステキスト（下記優先順位参照） |

manifest.jsonが見つからない場合はユーザーに確認し、course-ingestの実行を提案すること。

### 入力の優先順位

各章について、以下の優先順位でソースを選択する:

| 優先度 | ソース | 理由 |
|--------|--------|------|
| 1 | `chapters/{id}/manual.md` | utage-manual出力。編集済み・構造化済み・画像紐付け済み |
| 2 | `chapters/{id}/page_text.md` | 講座ページの説明文。補足情報を含む |
| 3 | `chapters/{id}/transcript.txt` | 生トランスクリプト。マニュアルがない場合のフォールバック |

マニュアルがある場合はマニュアルを一次ソースとし、トランスクリプトは
マニュアルに含まれていない情報の補完に使う。

### BLOCKER: ソーステキスト全文読み込み

> **各章のmanual.md（またはtranscript.txt）は必ず全文を読んでから抽出を開始すること。**
> 最初の50行だけ読んで始めてはならない。Read toolでoffset/limitを使う場合は、
> 必ず末尾まで複数回に分けて読み切ること。

---

### 6つの抽出カテゴリ

| カテゴリ | 何を抽出するか | 例 |
|----------|---------------|-----|
| concept | 名前＋定義＋具体例 | 「AIマインド＝脱AI責思考。AIのせいにせず自分の指示力に責任を持つ」 |
| key_quote | 話者の原文ママの重要発言 | 「AIのせいにした時点でもう何も作れません」 |
| tacit_knowledge | 話者が暗黙的に持つ判断基準 | 「専門知識が深い人ほどAIを使いこなせる。AIは鏡」 |
| teaching_pattern | 話者の教え方パターン | 「痛み提示→原因特定→原則提示→具体事例→マインド再強調」 |
| cross_reference | 他章への参照・前提関係 | 「第9章の魔法台本プロンプトにはこの4原則が前提」 |
| resource_reference | 外部リソースへの言及 | 「Notionにプロンプト格納してます」「PDFダウンロードしてください」 |

カテゴリの判別に迷う場合は `references/extraction-taxonomy.md` を参照。

#### resource_reference の検知パターン

トランスクリプトやマニュアル内で以下のパターンを検知:
- 「Notionに〜」「リンクは〜」「概要欄に〜」「ダウンロード〜」
- 「ここに格納」「テンプレート」「プレゼント」「配布物」
- URL言及（notion.so, drive.google.com, etc.）

knowledge.jsonでの出力形式:
```json
"resource_references": [
  {
    "id": "rr03-01",
    "text": "Notionの方にプロンプト格納してます",
    "type": "notion_page",
    "context": "PredictionXプロンプトの保管場所",
    "url_if_detected": null
  }
]
```

---

### 処理ステップ

```
Step 1: manifest.json読み込み → 章リスト取得
Step 2: 各章のソース選択（manual.md優先 → transcript.txtフォールバック）＋全文読み込み ← BLOCKER
Step 3: 6カテゴリ抽出（章ごと）
Step 4: chXX-knowledge.json生成（章ごと）
Step 5: 全章処理完了後 → knowledge-graph.json生成
Step 6: 自己検証
```

#### Step 1: manifest.json読み込み

manifest.jsonからコース名と章リストを取得する。

#### Step 2-4: 章ごとの処理

各章について以下を実行:

1. **ソース選択**: manual.mdが存在すればそれを一次ソースとする。なければtranscript.txtにフォールバック
2. **一次ソース全文読み込み**（BLOCKER: 部分読みNG）。マニュアルがある場合、transcript.txtは補完情報として必要に応じて参照
3. **concept抽出**: 話者が名前をつけて説明している概念を特定。name, definition, examples, key_quotes, speaker_framing, prerequisites, related_conceptsを記録
4. **key_quote抽出**: 強い主張・印象的な表現・核心的な発言を原文ママで記録。要約・意訳は絶対にしない
5. **tacit_knowledge抽出**: 話者が明示的に定義していないが暗黙的に前提としている判断基準・価値観を特定。必ずevidenceとして引用を添える
6. **teaching_pattern抽出**: 話者の説明の構造パターンを特定（例: 痛み→原因→原則→事例→再強調）
7. **cross_reference抽出**: 他章への言及・前提関係を記録
8. **resource_reference抽出**: 外部リソース（Notion, PDF, テンプレート, ダウンロードリンク等）への言及を検知・記録
9. **chXX-knowledge.json出力**

スキーマは `schemas/knowledge.schema.json` に準拠すること。

#### Step 5: knowledge-graph.json生成

**BLOCKER: 全章のknowledge.json生成完了後に実行すること。1章だけ見て全体グラフを作ってはならない。**

全章のknowledge.jsonを統合し:

1. **prerequisite_graph**: concept間の前提関係（cross_referenceとprerequisitesから構築）
2. **concept_hierarchy**: 概念のカテゴリ分類
3. **cross_chapter_themes**: 複数章に横断するテーマ

スキーマは `schemas/knowledge-graph.schema.json` に準拠すること。

#### Step 6: 自己検証

以下をすべてチェックし、問題があれば修正:

- [ ] 各conceptにname, definition, examplesがあるか
- [ ] key_quotesは原文ママか（要約していないか）
- [ ] tacit_knowledgeのevidenceにトランスクリプトの引用があるか
- [ ] concept IDが全章で一意か（c03-01, c04-01のように章番号含む）
- [ ] cross_referenceが実在する章を参照しているか
- [ ] knowledge-graph.jsonのprerequisite_graphが実在するconcept IDのみ参照しているか
- [ ] total_conceptsの数値が実際のconcept数と一致するか
- [ ] マニュアルがある章でマニュアルを一次ソースにしたか
- [ ] リソース言及（Notion, PDF, テンプレート等）を検知したか

---

### NG / OK テーブル

| NG | OK | 理由 |
|----|-----|------|
| 「重要な概念が述べられている」 | 「AIマインド＝脱AI責思考」と名前+定義を記載 | 抽象的な記述は活用不能 |
| key_quoteを要約・意訳する | 話者の原文ママを記録 | 引用は原文が価値 |
| 1章だけ読んで全体のgraphを作る | 全章処理後にgraphを作る | 前提関係は全体を見ないとわからない |
| transcript.txtの最初の50行だけ読む | 全文を読み切ってから抽出開始 | 重要概念が後半にあることが多い |
| examplesを空配列にする | 話者が挙げた具体例を最低1つ記録 | 定義だけでは概念が伝わらない |
| tacit_knowledgeにevidenceなし | トランスクリプトから該当箇所を引用 | 根拠なき推測は信頼できない |
| concept IDを「c1」「c2」と連番にする | 「c03-01」「c04-01」と章番号を含める | 全章で一意性を保証するため |
| definitionに3文以上の長文を書く | 1-2文で簡潔に核心を記述 | 定義は短く明確であるべき |
| マニュアルがあるのにトランスクリプトから抽出 | マニュアルを一次ソースにする | マニュアルは編集済みで品質が高い |
| リソース言及を無視する | resource_referencesとして記録 | スキル化時にリソース取得の手がかりになる |

---

### 出力ディレクトリ構造

```
{course-bundle}/
├── knowledge/
│   ├── ch00-knowledge.json
│   ├── ch01-knowledge.json
│   ├── ...
│   └── knowledge-graph.json
```

---

### ユーザーへの提示

処理完了後、以下のサマリーを提示:

```
## Concept Extraction Complete

- コース: {course_name}
- 処理章数: {n}章
- 抽出概念数: {total_concepts}
- 抽出引用数: {total_quotes}
- 暗黙知: {total_tacit}件
- 教え方パターン: {total_patterns}件
- リソース言及: {total_resources}件
- 横断テーマ: {total_themes}件

### 主要概念（上位5件）
1. {concept_name} - {definition}
...

### 横断テーマ
- {theme}: 章{chapters}
...
```
