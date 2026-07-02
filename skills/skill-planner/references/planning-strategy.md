# Planning Strategy

course-bundleの抽出結果からスキル計画を策定するための詳細ガイド。

---

## 1. Executableスキルの特定方法

### 判定フロー

```
procedures.jsonの各手順について:
  ├─ 明確な入力→出力があるか？
  │   ├─ YES: スキル候補
  │   └─ NO: shared_knowledgeへ
  │
  スキル候補について:
  ├─ 対応するプロンプト/テンプレートがresources-manifest.jsonにあるか？
  │   ├─ YES (fetched): executable (Ready)
  │   ├─ YES (not_fetched): executable (Unresolved記載)
  │   └─ NO: 手順のみのexecutable（リソース不要型）
  │
  リソース不要型の判定:
  ├─ 手順だけで実行完結するか？（例: 設定手順、分析手順）
  │   ├─ YES: executable
  │   └─ NO: unresolvedに記載
```

### 入力→出力の判定基準

以下のパターンがあればスキル候補:

| パターン | 例 |
|---------|-----|
| テキスト入力 → テキスト出力 | 文字起こし → 台本プロンプト |
| テンプレート + パラメータ → 成果物 | プロンプトテンプレート + ジャンル → 完成プロンプト |
| 既存コンテンツ → 変換コンテンツ | 長尺動画 → ショート動画台本 |
| 分析入力 → 分析レポート | チャンネルURL → 改善提案 |
| 設定指示 → 設定完了確認 | ツール名 → 設定手順ガイド |

### スキルにならないもの

| パターン | 理由 | 行き先 |
|---------|------|--------|
| 「AIマインドを持ちましょう」 | 実行物がない | shared_knowledge.concepts |
| 「成功者の共通点は...」 | マインドセット | shared_knowledge.concepts |
| 「〇〇と△△の違いは...」 | 概念説明 | shared_knowledge.concepts |
| 「NGな例：...」 | 判断基準 | shared_knowledge.ng_ok_patterns |

---

## 2. スキル境界の判定（分割 vs 統合）

### 分割すべき場合

| シグナル | 例 | 対応 |
|---------|-----|------|
| 別のプロンプトテンプレートを使う | PredictionXプロンプトとFusionOmegaプロンプト | 別スキル |
| 入力の種類が異なる | 文字起こしテキスト vs チャンネルURL | 別スキル |
| 出力の種類が異なる | 台本 vs サムネイル | 別スキル |
| 独立して実行できる | 台本生成と動画編集 | 別スキル |
| 3章以上にまたがる | ch06-ch10の内容を1つに | 目的別に分割 |

### 統合すべき場合

| シグナル | 例 | 対応 |
|---------|-----|------|
| 連続した手順で分離不能 | テンプレート選択→パラメータ入力→生成 | 1スキル |
| 同じプロンプトの変形 | 基本版と応用版 | 1スキルのバリエーション |
| 前の出力が次の入力 | プロンプト生成→プロンプト実行 | 1スキル（内部ステップ） |

### 境界判定チェックリスト

以下すべてYESなら1スキル:
- [ ] 同じプロンプト/テンプレートを使うか？
- [ ] 入力の種類は同じか？
- [ ] 出力の種類は同じか？
- [ ] 途中で中断してもユーザーに意味のある成果物があるか？ → NOなら分離不能

1つでもNOなら分割を検討。

---

## 3. 依存関係グラフの構築方法

### Step 1: 概念依存の追跡

```
knowledge-graph.jsonのprerequisite_graphから:
  concept A → prerequisite: concept B

concept Aを使うスキルXは、concept Bを含むスキルYに依存
  → skill X depends_on skill Y
```

### Step 2: 共有知識への依存

ほぼ全てのexecutableスキルは shared_knowledge に依存する。
これは明示的にdepends_onに含める。

### Step 3: スキル間の直接依存

```
スキルAの出力がスキルBの入力になる場合:
  → skill B depends_on skill A
```

### Step 4: 循環依存の検出

```
dependency_graphを深さ優先探索:
  visitedセットにスキル名を追加しながら探索
  既にvisitedにあるスキル名に到達 → 循環依存

循環依存が見つかった場合:
  1. 共通部分をshared_knowledgeに切り出す
  2. 両スキルがshared_knowledgeに依存する形に変更
```

### 依存関係の原則

| 原則 | 説明 |
|------|------|
| 隠れ依存ゼロ | 「知っている前提」は全てdepends_onで明示 |
| 深さ制限 | 依存チェーンは3段階まで。それ以上はshared_knowledgeに分離 |
| 双方向禁止 | AがBに依存かつBがAに依存はNG |

---

## 4. 未解決リソースの扱い

### 分類と対応

| type | 状況 | 推奨アクション |
|------|------|---------------|
| resource_not_fetched | プロンプトやテンプレートが言及されているが未取得 | manabi-ingestの実行を提案 |
| url_inaccessible | URLがあるがアクセスできない（認証必要等） | ユーザーに手動取得を依頼 |
| external_tool_required | 外部ツール（GPTs, Notion等）が必要 | ツールのアクセス方法を確認 |
| permission_needed | 有料コンテンツや限定アクセス | ユーザーに権限確認を依頼 |

### unresolvedがあってもスキルは作れるか？

| 状況 | 判断 |
|------|------|
| プロンプトテンプレート未取得 | executableにするがunresolved記載。テンプレートなしではスキルの核心が欠ける旨を明記 |
| 補足資料のみ未取得 | executableに影響なし。unresolvedに記載するが状態はReady |
| 外部ツール連携が未確認 | スキル自体は作成可能。ツール連携部分はプレースホルダーとして記載 |

---

## 5. Good vs Bad スキル計画の例

### Bad: 巨大スキル

```json
{
  "skill_name": "youtube-booster-all-in-one",
  "purpose": "YouTubeブースター講座の全内容を実行するスキル",
  "procedures": ["p03-01", "p04-01", "p05-01", "p06-01", "p07-01", "p08-01", "p09-01", "p10-01", "p11-01", "p12-01"]
}
```

問題点:
- 10章分の手順を1スキルに詰め込んでいる
- 入力→出力が不明確
- 全てのリソースが必要になりコンテキストを圧迫
- ユーザーが一部だけ使いたい場合に対応できない

### Good: 目的別分割

```json
{
  "planned_skills": [
    {
      "skill_name": "prediction-x-generator",
      "purpose": "PredictionXで参考台本から台本プロンプトを自動生成",
      "procedures": ["p09-01"],
      "resources": [{"id": "r01", "name": "PredictionXプロンプト", "status": "fetched"}],
      "rationale": "PredictionXプロンプトが取得済みで、手順p09-01に5ステップの明確なワークフローがある"
    },
    {
      "skill_name": "fusion-omega-generator",
      "purpose": "FusionOmegaで新規台本をゼロから生成",
      "procedures": ["p10-01"],
      "resources": [{"id": "r02", "name": "FusionOmegaプロンプト", "status": "fetched"}],
      "rationale": "FusionOmegaプロンプトが取得済みで、PredictionXとは入力が異なる（参考動画不要）"
    }
  ]
}
```

良い点:
- 1スキル=1目的
- 別テンプレート=別スキル
- 各スキルの入力→出力が明確
- 個別に実行可能

### Bad: 汎用trigger_words

```json
{
  "trigger_words": ["作成", "生成", "作って"]
}
```

問題点: あらゆるスキルが誤発動する

### Good: 講座固有のtrigger_words

```json
{
  "trigger_words": ["PredictionX", "台本自動生成", "コピー3回", "参考台本"]
}
```

良い点: 講座特有の用語で確実に正しいスキルが発動

### Bad: 未解決リソースの無視

```json
{
  "skill_name": "gpts-template-builder",
  "type": "executable",
  "resources": [{"id": "r05", "name": "GPTsテンプレート", "status": "fetched"}]
}
```

問題点: 実際にはfetchedではないのにfetchedと記載

### Good: 正直な状態報告

```json
{
  "skill_name": "gpts-template-builder",
  "type": "executable",
  "resources": [{"id": "r05", "name": "GPTsテンプレート", "path": "", "status": "not_fetched"}],
  "rationale": "手順p06-01は明確だが、GPTsテンプレートが未取得のため実行にはリソース取得が必要"
}
```

加えてunresolvedに記載:

```json
{
  "unresolved": [
    {
      "type": "resource_not_fetched",
      "name": "GPTsテンプレート",
      "mentioned_in": "ch06",
      "action_needed": "Notionページへのアクセスが必要"
    }
  ]
}
```

---

## 6. shared_knowledgeの設計指針

### 何を含めるか

| カテゴリ | 含める基準 | 例 |
|---------|-----------|-----|
| 基盤概念 | 2つ以上のスキルが参照する概念 | AIマインド、4つの壁 |
| NG/OKパターン | 講座全体に適用される判断基準 | 「AIのせいにする→自分の指示を改善する」 |
| チェックリスト | 品質確認の共通項目 | 「具体例が含まれているか」 |
| 用語定義 | 講座固有の用語 | 「コピー3回」の意味 |

### 何を含めないか

| カテゴリ | 理由 | 行き先 |
|---------|------|--------|
| スキル固有の手順 | 共有する必要がない | 各スキルのprocedures |
| スキル固有のプロンプト | 他スキルでは使わない | 各スキルのresources |
| 章固有の補足説明 | 共有より個別が適切 | 各スキルのmanual_ref |

### 命名規則

shared_knowledgeの名前は `{course-name}-knowledge` とする。
例: `youtube-booster-knowledge`, `ai-marketing-knowledge`
