---
name: procedure-extractor
description: "講座トランスクリプトからUIウォークスルー・設定手順・操作手順を抽出し、スクリーンショットと紐付けてprocedures.jsonを生成。course-bundleのtranscript + visual-indexerの結果を入力とする。「手順抽出」「procedure extract」「操作手順の抽出」「ウォークスルー抽出」で発動。concept-extractorとは異なりマルチモーダル（スクショを読む必要がある）。visual-indexerの完了後に実行すること。"
---

# Procedure Extractor

## 推奨実行モデル & 並列化

**モデル**: `sonnet` 必須（opusはコスト3-5倍。精度差は小さい）
**haiku禁止**: 手順の意味的な紐付けにはsonnet以上が必要

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

**前提**: visual-indexerが完了していること。procedure-extractorはvisual-index.jsonのフレーム情報を参照して手順とスクショを紐付ける。

---

## WHAT

講座トランスクリプトからUIウォークスルー・操作手順を抽出し、visual-indexerが分類したスクリーンショットと紐付けて `procedures.json` を生成する。

## WHY

- 講座動画には「概念の説明」と「操作の実演」が混在している
- concept-extractorは概念・定義・名言を抽出するが、操作手順は対象外
- 手順はスクリーンショットと紐付けることで初めて再現可能になる
- 本スキルはマルチモーダル（スクショを実際に読む）である点がconcept-extractorと異なる

## concept-extractorとの境界

| 対象 | 担当スキル | 例 |
|------|-----------|-----|
| 概念・定義・理論 | concept-extractor | 「壁打ちとは〜」 |
| 名言・引用 | concept-extractor | 「AIは道具です」 |
| 画面操作・設定手順 | **procedure-extractor** | 「ここをクリックして〜」 |
| ツール操作のデモ | **procedure-extractor** | 「noteで検索欄に入力して〜」 |

---

## 入力の優先順位

| 優先度 | ソース | 用途 |
|--------|--------|------|
| 1 | `chapters/{id}/manual.md` | 手順の文脈理解（編集済みで構造化されている） |
| 2 | `chapters/{id}/transcript.txt` | 手順の詳細（操作の言い回しが残っている） |
| 3 | `chapters/{id}/visual-index.json` | スクショ紐付け（必須） |
| 4 | `resources-manifest.json` | リソース参照の紐付け |

マニュアルとトランスクリプトの両方を読むのがベスト。
マニュアルで手順の構造を把握し、トランスクリプトで具体的な操作の言い回しを拾う。

---

## BLOCKER gates

以下を満たさない場合は処理を中断し、ユーザーに報告する。

| Gate | チェック内容 | 中断時メッセージ |
|------|------------|----------------|
| B1 | manifest.jsonが存在する | `manifest.jsonが見つかりません。course-bundleを先に実行してください。` |
| B2 | 対象チャプターのvisual-index.jsonが存在する | `visual-index.jsonが見つかりません。visual-indexerを先に実行してください。` |
| B3 | 対象チャプターのtranscript.txtが存在する | `transcript.txtが見つかりません。` |

---

## 処理フロー

```
1. manifest.json を読む
2. 対象チャプターの visual-index.json を読む  ← BLOCKER B2
3. 対象チャプターの transcript.txt を読む     ← BLOCKER B3
4. 対象チャプターの manual.md があれば読む（構造化済みマニュアル）
5. transcript_ts.json があれば読む（タイムスタンプ付きセグメント）
6. resources-manifest.json があれば読む（リソース参照用）
7. トランスクリプト（+マニュアル）から手順的言語パターンをスキャン
8. 関連するアクションをprocedureにグルーピング
9. 各ステップをスクリーンショットと紐付け（→ Screenshot Correlation）
10. 各ステップのリソース参照を紐付け（→ リソース参照の紐付け）
11. procedures.json を生成
12. 自己検証を実行
```

---

## Step 5: 手順的言語パターンの検出

トランスクリプトから以下のパターンを検出する。詳細は `references/visual-correlation.md` を参照。

### アクション動詞パターン

| カテゴリ | パターン例 |
|---------|----------|
| クリック系 | クリック、タップ、押す、押して、ポチッと |
| 入力系 | 入力、入れて、打って、書いて、貼り付け |
| 選択系 | 選択、選んで、チェック、オン/オフ |
| 移動系 | 開く、アクセス、移動、飛んで、遷移 |
| 設定系 | 設定、変更、切り替え、オンにして |
| 指示語+動詞 | 「ここを〜」「この画面で〜」「こちらの〜」 |

### グルーピングルール

| NG | OK | 理由 |
|----|-----|------|
| 1つの巨大procedure（20ステップ） | 5-8ステップの小さなprocedureに分割 | 長い手順は理解しにくい |
| 概念説明を手順として抽出 | 明確なアクション（動詞+対象）のみ抽出 | 概念はconcept-extractorの領域 |
| 文脈なしにステップを列挙 | titleとoutcomeで手順の目的を明示 | 手順だけでは「何のために」がわからない |
| リソース参照を無視してaction文だけ記録 | resource_refで外部リソースを紐付け | スキル化時にリソースをassets/に含められる |
| マニュアルがあるのにトランスクリプトだけから抽出 | マニュアル+トランスクリプト両方を活用 | マニュアルは構造化済みで手順の把握が容易 |

分割の目安:
- 画面が変わるタイミング
- 目的が変わるタイミング（「検索する」→「購入する」）
- 8ステップを超えたら分割を検討

---

## Step 7: Screenshot Correlation

スクリーンショットとの紐付けロジック。

### 紐付けフロー

```
1. transcript_ts.json からアクション動詞の出現タイムスタンプを特定
2. visual-index.json で該当タイムスタンプ付近のフレームを検索
   - 対象: type が browser_screenshot または terminal_screenshot のフレーム
   - 範囲: アクション前後 ±5秒
3. 候補フレームを Read ツールで実際に読み、内容を確認
4. トランスクリプトの操作内容と画面内容が一致するフレームを screenshot_ref に設定
```

### 紐付けルール

| NG | OK | 理由 |
|----|-----|------|
| screenshot_refに存在しないファイルを指定 | visual-indexから実在するフレームのみ参照 | 壊れた参照はスキル合成時にエラーになる |
| 全ステップにscreenshot_refを強制 | スクショなしのステップは `screenshot_ref: null` | すべてのアクションに画面があるわけではない |
| 1枚のスクショを無理に1ステップに限定 | 複数ステップが同一スクショを参照してもよい | 同じ画面での連続操作は自然 |
| タイムスタンプだけで機械的にマッチ | 画像の中身を実際に読んで確認 | タイムスタンプのずれは頻繁に発生する |

### transcript_ts.json がない場合

タイムスタンプ情報がない場合は以下で代替する:
1. トランスクリプト内の位置（先頭からの割合）でチャプター全体の時間軸を推定
2. visual-index.json のフレーム順序と照合
3. 画像内容を実際に読んで、トランスクリプトの文脈と照合

### 記事章（content_type: article/hybrid）の場合

記事章ではタイムスタンプ紐付けは不要。**article.md内の画像参照は著者が正しい位置に
埋め込み済み**なので、手順テキストの直近にある画像参照（`![...](screenshots/img_NNN.png)`）
をそのまま `screenshot_ref` に使う。これはタイムスタンプ推定より確実。

- 手順の抽出元はarticle.md（原文）。hybrid章では動画transcriptからも抽出し、
  各手順に `source: "article" | "video"` を付ける
- 画像なしの手順は `screenshot_ref: null` でよい（記事は文章だけで完結する手順が多い）

---

## Step 10: リソース参照の紐付け

手順内で外部リソースを使用するステップには `resource_ref` を設定する。

### 検知パターン

- 「Notionからコピー」「テンプレートを使って」「PDFを参照」
- 「ここにあるプロンプトを」「ダウンロードして」

### 紐付け方法

1. resources-manifest.json を読む
2. 手順内のリソース言及を検知
3. manifest内の該当リソースとマッチング
4. resource_ref にパスを設定（マッチしない場合は null）

---

## 出力フォーマット: procedures.json

チャプターごとに `procedures.json` を生成する。

```json
{
  "chapter_id": "06",
  "procedures": [
    {
      "id": "p06-01",
      "title": "noteでプロンプトを検索する方法",
      "steps": [
        { "step": 1, "action": "NotionからPredictionXプロンプトをコピー", "screenshot_ref": "frame_011.jpg", "resource_ref": "prompts/prediction-x.md" },
        { "step": 2, "action": "note.comにアクセス", "screenshot_ref": "frame_012.jpg", "resource_ref": null },
        { "step": 3, "action": "検索欄に「プロンプト」と入力", "screenshot_ref": "frame_013.jpg", "resource_ref": null },
        { "step": 4, "action": "有料のみフィルタを選択", "screenshot_ref": "frame_014.jpg", "resource_ref": null }
      ],
      "outcome": "有料のプロンプト一覧が表示される",
      "tags": ["note", "プロンプト検索", "壁打ち"],
      "prerequisites": ["c03-02"],
      "difficulty": "beginner"
    }
  ]
}
```

### フィールド仕様

| フィールド | 必須 | 説明 |
|-----------|------|------|
| chapter_id | Yes | チャプター番号（manifest.jsonと一致） |
| procedures[].id | Yes | `p{chapter_id}-{連番}` 形式 |
| procedures[].title | Yes | 手順の目的を表す簡潔なタイトル |
| procedures[].steps[].step | Yes | ステップ番号（1始まり） |
| procedures[].steps[].action | Yes | 具体的な操作内容 |
| procedures[].steps[].screenshot_ref | Yes | フレームファイル名 or `null` |
| procedures[].steps[].resource_ref | No | リソースファイルパス or `null`（resources-manifest.jsonと対応） |
| procedures[].outcome | Yes | この手順を完了すると何が起きるか |
| procedures[].tags | Yes | 具体的なタグ（ツール名・機能名） |
| procedures[].prerequisites | No | 前提となるconcept ID（c{xx}-{yy}形式） |
| procedures[].difficulty | Yes | `beginner` / `intermediate` / `advanced` |

### difficulty 判定基準

| レベル | 基準 |
|--------|------|
| beginner | 1画面で完結、特別な知識不要 |
| intermediate | 複数画面遷移、設定項目の理解が必要 |
| advanced | 外部連携、API設定、条件分岐あり |

---

## Step 9: 自己検証

生成後に以下をすべてチェックする。1つでも失敗したら修正する。

- [ ] 各procedureに明確なtitleとoutcomeがあるか
- [ ] screenshot_refが全てvisual-index.jsonに存在するフレームを指しているか
- [ ] stepsの順序が論理的か（前提なしに後段のステップが来ていないか）
- [ ] tagsが具体的か（「その他」のような曖昧タグがないか）
- [ ] 概念的な内容が混入していないか（それはconcept-extractorの仕事）
- [ ] 1つのprocedureが8ステップ以下か
- [ ] procedures.jsonが `schemas/procedures.schema.json` に準拠しているか
- [ ] 全screenshot_refのファイルが実際に存在するか（Bashで確認）
- [ ] resource_refが設定されたステップのパスがresources-manifest.jsonに存在するか
- [ ] マニュアルがある章でマニュアルを参照したか

### screenshot_ref 検証コマンド

```bash
# procedures.jsonから全screenshot_refを抽出し、存在チェック
jq -r '.procedures[].steps[].screenshot_ref // empty' procedures.json | while read f; do
  [ -f "$FRAMES_DIR/$f" ] || echo "MISSING: $f"
done
```

---

## ユーザーへの提示

処理完了後、以下の形式で報告する:

```
## 手順抽出完了: Chapter {id}

- 抽出数: {n} procedures, {m} total steps
- スクショ紐付け: {linked}/{total} steps にスクショあり
- 難易度分布: beginner={b}, intermediate={i}, advanced={a}

### 抽出した手順一覧
| ID | タイトル | ステップ数 | スクショ数 |
|----|---------|----------|----------|
| p{id}-01 | ... | 5 | 3 |
| p{id}-02 | ... | 4 | 4 |

出力先: {path}/procedures.json
```

---

## このスキルがやらないこと

| やらないこと | 理由 | 代わりに使うスキル |
|-------------|------|-----------------|
| 概念・定義の抽出 | テキストのみの作業 | concept-extractor |
| 動画のフレーム切り出し | 前処理 | manabi-ingest |
| スクショの分類・インデックス作成 | 前処理 | visual-indexer |
| 動画ダウンロード | 前処理 | video-downloader |
| マニュアル文書の生成 | 後工程 | （別スキル） |
