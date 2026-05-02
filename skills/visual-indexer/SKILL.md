---
name: visual-indexer
description: "course-bundleの全スクリーンショットをカタログ化。各フレームの画像分類（スライド/ブラウザ/図解/トーキングヘッド等）、テキスト内容のOCR抽出、キーワード付与を行い、visual-index.jsonとvisual-catalog.jsonを生成。「画像インデックス」「スクショ分類」「visual index」「フレーム分析」で発動。procedure-extractorのスクショ紐付けに必要。concept-extractorと並列実行可能。"
---

# visual-indexer

course-bundleの全スクリーンショットをカタログ化し、分類・OCR・メタデータ付与を行うスキル。

---

## 推奨実行モデル & 並列化

**モデル**: `sonnet` 必須（opusはコスト3-5倍。精度差は小さい）

**1回の実行で全フレームをReadするためコスト最大。sonnet並列を厳守。**

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

## WHAT — 何をするか

コースの全チャプターに含まれるスクリーンショット画像を1枚ずつ読み取り、以下を行う:

1. **フレーム分類** — コア型7種 + 講座固有型（custom_types）で画像を分類
2. **OCR抽出** — 画像内のテキストをすべて抽出
3. **ビジュアル要素の特定** — 図形、矢印、ボックス等の視覚要素を記録
4. **キーワード付与** — ダウンストリームのスキルが検索しやすいようにタグ付け
5. **インデックス生成** — チャプター別 `visual-index.json` + 全体 `visual-catalog.json`

---

## WHY — なぜ必要か

- procedure-extractorが手順画像を紐付けるのにOCR情報とフレーム分類が必要
- concept-extractorがスライド画像を補強材料として使う
- talking_headやtransitionを除外することで後段の処理コストを削減
- コース全体の画像資産を俯瞰できるカタログが必要

---

## HOW — 実行手順

### Phase 0: 準備・検証

```
BLOCKER: manifest.jsonが存在するか確認
  → 存在しない場合は course-ingest を先に実行するよう案内して停止
```

1. `manifest.json` を読み込み、チャプター一覧とスクリーンショットディレクトリを取得
2. 各チャプターのスクリーンショットディレクトリの存在を確認
3. 全フレーム数をカウントし、処理計画を立てる

### Phase 0.5: 講座固有型の発見

各章の最初の5フレームをサンプル読みし:

1. コア型に当てはまるか判定
2. 当てはまらない画面が2枚以上ある → 講座固有型を提案
3. ユーザーまたはメインセッションに型定義を提示（章の最初だけ）
4. 確定したら `visual-index.json` の `custom_types` に登録
5. 以降のフレームはコア型 + 講座固有型から選択

注: 完全自動化する場合は、Phase 0.5でAgent自身が判断して登録する。

### Phase 1: チャプター別フレーム処理

各チャプターについて以下を実行:

#### Step 1.1: フレーム一覧取得

```bash
ls chapters/{chapter_id}/screenshots/
```

#### Step 1.2: バッチ処理（5-10枚ずつ）

```
BLOCKER: 各画像は必ずReadツールで読み取ってから分類する
  → ファイル名からの推測は NG
```

各フレームについて:

1. **Readツールで画像を読み取る**
2. **フレーム分類** — 以下のタクソノミーで分類:

**コア型**（全講座共通）:

| type | 説明 | ダウンストリームでの使われ方 |
|------|------|---------------------------|
| `title_slide` | 章タイトル | マニュアルの見出し画像 |
| `content_slide` | 概念図・スライド | concept-extractorの補強 |
| `browser_screenshot` | ブラウザ画面 | procedure-extractorの手順画像 |
| `terminal_screenshot` | コマンドライン | procedure-extractorの手順画像 |
| `diagram` | フローチャート・図解 | 概念関係の可視化 |
| `talking_head` | 話者の映像のみ | 低価値、スキップ可 |
| `transition` | 空白・遷移フレーム | スキップ |

コア型に当てはまらない繰り返し画面は **講座固有型（custom_types）** として登録する（後述）。

## 講座固有型（custom_types）

コア型に当てはまらないが、講座内で繰り返し出現する画面は**講座固有型**として動的に作成する。

### 作成ルール

1. **最初の3-5フレーム**を見て型候補を検討
2. 「コア型に当てはまらない」かつ「2枚以上出る」 → 講座固有型として登録
3. 命名は snake_case、講座のキーワードを含む
   - 例: `tmux_pane`, `vscode_editor`, `ae_timeline`, `figma_canvas`
4. 1講座あたり**最大5型**まで（無限増殖防止）
5. 1枚しか出ない型は作らず、コア型のうち最も近いものに割り当て

3. **OCR抽出** — 画像内の全テキストを `text_content` 配列に格納
4. **ビジュアル要素特定** — `visual_elements` 配列に記録
5. **キーワード付与** — 内容を表すキーワードを `keywords` 配列に格納
6. **信頼度判定** — `confidence` を `high` / `medium` / `low` で設定
7. **UI操作判定** — ブラウザ/ターミナル画面の場合 `is_ui_walkthrough` を設定

#### Step 1.3: visual-index.json 生成

チャプターの全フレーム処理が完了したら `visual-index.json` を生成:

```json
{
  "chapter_id": "03",
  "custom_types": {
    "tmux_pane": "tmuxで複数paneに分割されたClaude Code画面（タイトルバーにtmux表記、画面分割あり）"
  },
  "frames": [
    {
      "filename": "frame_005.jpg",
      "type": "content_slide",
      "text_content": ["AIマインド", "壁打ち", "アイデア", "専門知識"],
      "visual_elements": ["equation_diagram", "four_boxes", "arrow"],
      "keywords": ["4原則", "マインド"],
      "confidence": "high"
    }
  ]
}
```

出力先: `chapters/{chapter_id}/visual-index.json`

スキーマ: `schemas/visual-index.schema.json` に準拠すること。

### Phase 2: visual-catalog.json 生成

全チャプターの処理完了後、コース全体のカタログを生成:

```json
{
  "course_name": "YouTube Booster",
  "total_frames": 245,
  "course_custom_types": {
    "tmux_pane": {"definition": "tmuxで複数paneに分割されたClaude Code画面", "frame_count": 18},
    "vscode_editor": {"definition": "VS Codeのエディタ画面（ファイルツリー+エディタ+ステータスバー）", "frame_count": 8}
  },
  "type_distribution": {
    "content_slide": 89,
    "browser_screenshot": 45,
    "talking_head": 67,
    "diagram": 23,
    "title_slide": 12,
    "transition": 9
  },
  "chapters": [
    {
      "chapter_id": "03",
      "frame_count": 31,
      "high_value_frames": ["frame_005.jpg", "frame_012.jpg"],
      "visual_index_path": "chapters/03/visual-index.json"
    }
  ]
}
```

- `high_value_frames`: `content_slide`, `browser_screenshot`, `diagram` のうち `confidence: "high"` のもの
- `type_distribution`: 全チャプターのフレームタイプを集計

出力先: プロジェクトルートの `visual-catalog.json`

### Phase 3: 自己検証

以下のチェックリストを全て通過すること:

- [ ] 全フレームに `type` が設定されているか
- [ ] `text_content` が空の `content_slide` がないか（スライドには必ずテキストがある）
- [ ] `talking_head` のフレーム数が妥当か（通常20-40%）
- [ ] `visual-catalog.json` の `total_frames` が実際のファイル数と一致するか
- [ ] 各 `visual-index.json` が `schemas/visual-index.schema.json` に準拠しているか
- [ ] `type_distribution` の合計が `total_frames` と一致するか
- [ ] `custom_types` の数は5以下か
- [ ] 各 `custom_type` に定義文があるか
- [ ] 各 `custom_type` を使ったフレームが2枚以上あるか
- [ ] `custom_type` の命名が snake_case か

```
検証失敗時:
  → 不一致があれば該当チャプターを再処理
  → text_contentが空のcontent_slideがあれば画像を再読み取り
```

---

## BLOCKER ゲート

| Gate | 条件 | 未達時の対応 |
|------|------|-------------|
| G1 | manifest.jsonが存在する | course-ingestを先に実行するよう案内 |
| G2 | スクリーンショットディレクトリが存在する | video-to-framesを先に実行するよう案内 |
| G3 | 各画像をReadツールで実際に読み取った | ファイル名推測は禁止、必ず読み取る |
| G4 | 全フレームを処理した（サンプルではなく全数） | 未処理フレームがあれば追加処理 |
| G5 | 自己検証チェックリスト全項目パス | 失敗項目を修正して再検証 |

---

## NG / OK 判定表

| NG | OK | 理由 |
|----|-----|------|
| ファイル名だけで分類する | 画像をReadツールで読んでから分類 | ファイル名に内容情報がない |
| talking_headを見逃して全部content_slideにする | 人物のみのフレームは明確にtalking_headに分類 | 後段のスキルが不要な画像を処理してしまう |
| text_contentを空で済ませる | 画像内のテキストを全て抽出 | OCR情報がprocedure-extractorの紐付けに必要 |
| 一部のフレームだけサンプル処理する | 全フレームを漏れなく処理する | 抜け落ちたフレームが手順画像だった場合に手順が欠落する |
| content_slideとdiagramを区別しない | スライド形式かフローチャート形式かで明確に分ける | concept-extractorの処理方法が異なる |
| confidenceを全部highにする | 判断に迷う画像はmedium/lowにする | 後段で優先順位をつけるための情報が必要 |
| visual_elementsを省略する | 矢印、ボックス、表、コード等を記録する | ダウンストリームの画像選択精度に影響 |
| 当てはまらない画面を無理にコア型に押し込む | 講座固有型を作成 | 誤分類が後段スキルを破壊する |
| 1枚しか出ない型を作る | 最も近いコア型に割り当て | 型の無限増殖を防ぐ |
| 1講座で5型超の講座固有型を作る | 上位5つに統合 | カタログの肥大化防止 |
| 講座固有型の命名が汎用語（`editor`等） | 講座キーワードを含む（`vscode_editor`等） | 他講座と衝突しない |

---

## フレーム分類の判断基準

詳細は `references/frame-types.md` を参照。概要:

- **title_slide**: 大きなテキスト、章番号、背景デザイン。テキスト要素が少ない
- **content_slide**: 箇条書き、図表、概念説明。テキスト量が多い
- **browser_screenshot**: ブラウザのUI要素（アドレスバー、タブ等）が見える
- **terminal_screenshot**: 黒背景にモノスペースフォント、コマンドライン
- **diagram**: 矢印やフロー、接続線。構造化された図形の配置
- **talking_head**: 人物の映像が画面の大部分を占める。テキスト要素がない/少ない
- **transition**: 無地の画面、フェード、ぼかし

### エッジケース

- スライド上に小さな話者映像がオーバーレイ → `content_slide`（スライドが主体）
- ブラウザ画面+解説テキストのオーバーレイ → `browser_screenshot`
- 半分スライド・半分話者 → テキスト量で判断、テキストが多ければ `content_slide`

---

## 出力ファイル一覧

| ファイル | 場所 | 内容 |
|---------|------|------|
| visual-index.json | chapters/{id}/visual-index.json | チャプター別フレーム情報 |
| visual-catalog.json | プロジェクトルート | コース全体のカタログ |

---

## 連携スキル

| スキル | 関係 |
|--------|------|
| course-ingest | 前提: manifest.jsonを生成 |
| video-to-frames | 前提: スクリーンショットを生成 |
| procedure-extractor | 後続: フレーム分類とOCRを利用 |
| concept-extractor | 並列実行可能: content_slideを補強に利用 |

---

## バッチ処理の注意

- Readツールで画像を読み取る際、1回のバッチで5-10枚を処理
- 大量のフレーム（100枚超）がある場合でも全数処理する
- 処理の進捗を章ごとに報告する: `Chapter 03: 31/31 frames processed`
- エラーが発生したフレームは `confidence: "low"` で記録し、エラー内容をメモ
