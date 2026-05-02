---
type: reference
skill: visual-indexer
---

# フレームタイプ分類ガイド

visual-indexerが画像を分類する際の詳細判定基準。

---

## 1. title_slide（章タイトル）

### 視覚的特徴
- 大きなフォントサイズのテキスト（画面の中央に配置されることが多い）
- 章番号やセクション番号が含まれる（例: 「第3章」「Chapter 03」「STEP 3」）
- 装飾的な背景（グラデーション、パターン、ブランドカラー）
- テキスト要素が少ない（タイトル + サブタイトル程度）
- ロゴやコースブランディングが含まれることがある

### エッジケース
- タイトル+箇条書きの概要がある場合 → テキスト量で判断。概要が3項目以下なら `title_slide`、それ以上なら `content_slide`
- セクション区切りのインタースティシャル → `title_slide`

### ダウンストリーム優先度: 中
マニュアルの見出し画像として使用。必ず1チャプターに1枚以上あるはず。

### visual_elements の典型値
`logo`, `icon`, `subtitle_text`, `watermark`

---

## 2. content_slide（概念図・スライド）

### 視覚的特徴
- 箇条書き、番号付きリスト、テーブルなどの構造化テキスト
- 概念の説明図が含まれる
- 背景は単色またはテンプレートデザイン
- テキスト量が多い（3行以上の本文）
- 図とテキストの混在

### エッジケース
- スライド上に小さな話者映像（ワイプ）がオーバーレイ → `content_slide`（スライド内容が主体）
- 半分スライド・半分話者 → テキスト量で判断。テキスト情報が画面の50%以上なら `content_slide`
- スライドに1つの図だけ → 図がフローチャートなら `diagram`、概念説明なら `content_slide`

### ダウンストリーム優先度: 高
concept-extractorの補強材料。text_contentの完全な抽出が必須。

### visual_elements の典型値
`bullet_list`, `numbered_list`, `box`, `four_boxes`, `arrow`, `table`, `icon`, `highlight`, `equation_diagram`

---

## 3. browser_screenshot（ブラウザ画面）

### 視覚的特徴
- ブラウザのUI要素が見える:
  - アドレスバー（URL表示）
  - タブバー
  - ブックマークバー
  - ナビゲーションボタン（戻る/進む）
- Webページのコンテンツが表示されている
- 典型的なWebデザイン要素（ヘッダー、サイドバー、フォーム等）

### エッジケース
- ブラウザ全画面モード（UIが隠れている）→ URLやWebデザイン要素から判断
- ブラウザ画面+解説テキストのオーバーレイ → `browser_screenshot`
- アプリのWebビュー → ブラウザUI要素があれば `browser_screenshot`
- モバイルブラウザのスクリーンショット → `browser_screenshot`

### ダウンストリーム優先度: 高
procedure-extractorの手順画像として最重要。`is_ui_walkthrough: true` の設定を忘れずに。

### visual_elements の典型値
`url_bar`, `tab_bar`, `sidebar`, `form`, `button`, `modal`, `dropdown`, `cursor`, `highlight`, `annotation`, `circle_emphasis`

---

## 4. terminal_screenshot（コマンドライン）

### 視覚的特徴
- 黒背景（または暗い背景色）
- モノスペースフォント
- コマンドプロンプト（`$`, `>`, `#` 等）
- コマンド出力テキスト
- ターミナルエミュレータのウィンドウ枠

### エッジケース
- IDE内のターミナルパネル → ターミナル部分が主体なら `terminal_screenshot`、コード編集が主体なら `browser_screenshot`（IDE系）
- コードエディタ → コマンドラインでなくコードファイルの場合は `content_slide` に近い。判断に迷えば `notes` にメモ
- PowerShellの青い背景 → `terminal_screenshot`

### ダウンストリーム優先度: 高
procedure-extractorの手順画像。コマンドの正確なOCR抽出が重要。

### visual_elements の典型値
`terminal_prompt`, `code_block`, `cursor`, `highlight`

---

## 5. diagram（フローチャート・図解）

### 視覚的特徴
- 矢印で接続されたノード/ボックス
- フローチャート形式の構造
- マインドマップ
- 組織図、階層図
- プロセスフロー
- テキストよりも図形と接続線が主体

### エッジケース
- スライド内の小さな図 → スライドのテキストが主体なら `content_slide`、図が画面の60%以上なら `diagram`
- 表（テーブル）→ データ表示が目的なら `content_slide`、関係性を示すなら `diagram`
- インフォグラフィック → `diagram`

### ダウンストリーム優先度: 高
概念関係の可視化に使用。ノード間の関係性の抽出が重要。

### visual_elements の典型値
`flowchart`, `arrow`, `box`, `hierarchy`, `venn_diagram`, `matrix`, `timeline`

---

## 6. talking_head（話者の映像のみ）

### 視覚的特徴
- 人物の顔/上半身が画面の大部分を占める
- テキスト要素がない、または名前テロップ程度
- 背景は部屋やバーチャル背景
- Webカメラの画質感
- 表情や身振りでの説明

### エッジケース
- 話者+小さなスライドのワイプ → スライド内容が読み取れるなら `content_slide`。読み取れないほど小さければ `talking_head`
- 話者+テロップ/字幕 → テロップが単なる装飾なら `talking_head`、内容説明なら `content_slide`
- 複数人の対談画面 → `talking_head`

### ダウンストリーム優先度: 低
通常スキップ対象。ただし `visual-catalog.json` の `high_value_frames` には含めない。

### visual_elements の典型値
`speaker_thumbnail`, `subtitle_text`, `overlay_text`, `watermark`

---

## 7. transition（空白・遷移フレーム）

### 視覚的特徴
- 単色の画面（黒、白、ブランドカラー）
- フェードイン/フェードアウトの中間状態
- ぼかし効果
- モーションブラーで内容が判読不能
- ローディング画面

### エッジケース
- ロゴのみの画面 → コースロゴで内容がない場合は `transition`。タイトル文字があれば `title_slide`
- 画面切り替え中のフレーム → `transition`
- エンドカード（「ご視聴ありがとうございました」等）→ `title_slide`（テキストコンテンツがあるため）

### ダウンストリーム優先度: なし
完全スキップ対象。`text_content` は空配列でよい。

### visual_elements の典型値
`logo`, `watermark`（あれば）

---

## 判定フローチャート

```
画像を読み取る
  │
  ├─ テキスト/コンテンツがほぼない
  │   ├─ 人物が映っている → talking_head
  │   └─ 人物もない → transition
  │
  ├─ ブラウザUI要素がある → browser_screenshot
  │
  ├─ ターミナル/コマンドラインである → terminal_screenshot
  │
  ├─ 図形・矢印・フローが主体 → diagram
  │
  ├─ 大きなタイトルテキスト + 少ないテキスト → title_slide
  │
  └─ 構造化テキスト + 説明図 → content_slide
```

---

## confidence の判定基準

| レベル | 基準 |
|--------|------|
| `high` | 明確に1つのタイプに該当。迷いなし |
| `medium` | 2つのタイプの特徴が混在。主体のタイプで分類した |
| `low` | 判断が困難。ぼやけている、過渡的、または複数タイプの特徴が均等 |

---

## visual_elements 値の一覧と説明

### レイアウト系
| 値 | 説明 |
|----|------|
| `arrow` | 矢印（方向を示す） |
| `box` | 単一のボックス/枠 |
| `four_boxes` | 4象限や4つのボックスのレイアウト |
| `table` | テーブル/表 |
| `list` | リスト（種類不明） |
| `numbered_list` | 番号付きリスト |
| `bullet_list` | 箇条書きリスト |

### 図解系
| 値 | 説明 |
|----|------|
| `flowchart` | フローチャート |
| `hierarchy` | 階層図・組織図 |
| `equation_diagram` | 数式や等式を含む図 |
| `pie_chart` | 円グラフ |
| `bar_chart` | 棒グラフ |
| `line_chart` | 折れ線グラフ |
| `timeline` | タイムライン |
| `venn_diagram` | ベン図 |
| `matrix` | マトリクス図 |

### UI要素系
| 値 | 説明 |
|----|------|
| `url_bar` | ブラウザのアドレスバー |
| `tab_bar` | ブラウザのタブバー |
| `sidebar` | サイドバー |
| `form` | 入力フォーム |
| `button` | ボタン |
| `modal` | モーダルダイアログ |
| `dropdown` | ドロップダウンメニュー |

### ターミナル系
| 値 | 説明 |
|----|------|
| `terminal_prompt` | コマンドプロンプト |
| `code_block` | コードブロック |
| `cursor` | カーソル |

### 装飾・強調系
| 値 | 説明 |
|----|------|
| `icon` | アイコン |
| `logo` | ロゴ |
| `highlight` | ハイライト/蛍光マーカー |
| `annotation` | 手書きや後付けの注釈 |
| `circle_emphasis` | 丸で囲んだ強調 |
| `screenshot_border` | スクリーンショットの枠線 |
| `watermark` | 透かし |
| `subtitle_text` | 字幕テキスト |
| `overlay_text` | オーバーレイテキスト |
| `speaker_thumbnail` | 話者のサムネイル（ワイプ） |
| `other` | 上記に該当しないもの |
