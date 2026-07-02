---
name: skill-planner
description: "course-bundleの抽出結果（knowledge.json, procedures.json, visual-index.json, resources-manifest.json）を分析し、作成可能なスキルの計画（skill-plan.json）を生成する。各スキルの目的・入出力・必要リソース・依存関係を設計し、ユーザー承認を取ってからスキル生成に進む。「スキル計画」「skill plan」「何のスキルが作れるか」「スキル設計」で発動。skill-synthesizerの前に必ず実行する。"
---

# Skill Planner

## WHAT

course-bundleの全抽出結果を分析し、生成可能なスキルの計画（skill-plan.json）を作成する。
各スキルの目的・入出力・必要リソース・依存関係を設計し、ユーザー承認後にskill-synthesizerへ渡す。

**スコープ外:**
- スキルの実際の生成（skill-synthesizerの責務）
- トランスクリプトの抽出（concept-extractor, procedure-extractor, visual-indexerの責務）
- リソースの取得（manabi-ingestの責務）

---

## WHY

抽出フェーズで得られたknowledge, procedures, resourcesは断片的。そのままではスキル化できない。
計画フェーズで以下を決定する:

1. **何をスキルにするか** - 手順+リソースの組み合わせから実行可能な単位を特定
2. **何を共有知識にするか** - 概念・マインドセットは基盤knowledgeに集約
3. **依存関係は何か** - スキル間の前提関係を明示
4. **何が未解決か** - リソース未取得など、スキル化の障害を特定

**ユーザー承認なしにskill-synthesizerに渡してはならない。** スキル構成はユーザーが決める。

---

## 発動条件

- 「スキル計画」「スキル設計」
- 「何のスキルが作れるか」
- 「skill plan」「plan skills」
- `/skill-planner`

---

## HOW

### 入力要件

| 必須 | 内容 |
|------|------|
| manifest.json | コースメタデータ |
| knowledge/knowledge-graph.json | 概念依存関係グラフ |

| 任意（あれば使う） | 内容 |
|-------------------|------|
| chapters/*/knowledge.json | 各章の概念・暗黙知 |
| chapters/*/procedures.json | 各章のステップバイステップ手順 |
| chapters/*/visual-index.json | 各章のフレーム分類 |
| resources-manifest.json | 取得済み外部リソース |
| manuals/*.md | utage-manual出力（参照のみ、コピーしない） |

### BLOCKER: 前提条件チェック

> **以下を確認するまでStep 2に進むな:**
> 1. knowledge/knowledge-graph.json が存在すること
> 2. 少なくとも1つのprocedures.jsonが存在すること
>
> 存在しない場合はユーザーに報告し、concept-extractorまたはprocedure-extractorの実行を提案すること。

---

### 処理ステップ

```
Step 1: 前提条件チェック ← BLOCKER
Step 2: 全入力ファイル読み込み
Step 3: スキル候補の特定
Step 4: スキルタイプの判定
Step 5: 共有知識の設計
Step 6: 依存関係グラフの構築
Step 7: 未解決項目の特定
Step 8: skill-plan.json生成
Step 9: 自己検証
Step 10: ユーザーへの提示 ← BLOCKER（承認必須）
```

#### Step 2: 全入力ファイル読み込み

以下を全て読み込む（存在するもののみ）:

1. manifest.json → コース名・章リスト
2. knowledge/knowledge-graph.json → 概念依存関係
3. 全chapters/*/knowledge.json → 概念・暗黙知
4. 全chapters/*/procedures.json → 手順
5. resources-manifest.json → 取得済みリソース
6. manuals/ ディレクトリのファイル一覧 → マニュアル参照用

#### Step 3: スキル候補の特定

procedures.jsonの各手順について:
1. 独立した目的（入力→出力）を持つか確認
2. 対応するリソース（プロンプト、テンプレート等）があるか確認
3. 候補としてリストアップ

#### Step 4: スキルタイプの判定

| 条件 | → type |
|------|--------|
| プロンプトテンプレート（取得済み）+ 手順がある | `executable` |
| 手順はあるがリソース未取得 | `executable`（unresolvedに記載） |
| 概念・理論・マインドセット中心、実行物なし | → shared_knowledge に統合 |

#### Step 5: 共有知識の設計

以下を shared_knowledge に集約:
- 基盤概念（複数スキルの前提となる概念）
- NG/OKパターン（講座全体の判断基準）
- チェックリスト項目（品質確認の共通基準）
- マインドセット・価値観（暗黙知から抽出）

#### Step 6: 依存関係グラフの構築

1. knowledge-graph.jsonのprerequisite_graphを参照
2. 各スキルが参照する概念の前提を追跡
3. depends_onとして記録
4. 循環依存がないことを確認

#### Step 7: 未解決項目の特定

以下をunresolvedに記録:
- リソースが言及されているが未取得
- URLが記載されているがアクセスできない
- 外部ツールが必要だが未確認

#### Step 8: skill-plan.json生成

スキーマは `schemas/skill-plan.schema.json` に準拠。
出力先: `{course-bundle}/skill-plan.json`

#### Step 9: 自己検証

以下をすべてチェックし、問題があれば修正:

- [ ] 各executable skillにresourcesまたはproceduresがあるか
- [ ] skill_nameが全体で一意か
- [ ] depends_onが実在するスキル名を参照しているか
- [ ] trigger_wordsが講座固有の具体的なワードか（「作成」「生成」のような汎用語はNG）
- [ ] shared_knowledgeに基盤概念が含まれているか
- [ ] unresolved欄に未取得リソースが全て記載されているか
- [ ] dependency_graphに循環依存がないか
- [ ] 1スキルが3章以上の内容を含んでいないか（巨大スキル禁止）

---

### スキル分割ルール

| ルール | 説明 |
|--------|------|
| 1スキル=1目的 | 入力→出力が明確に定義できる単位 |
| プロンプトテンプレートごとに分離 | 別テンプレート=別スキル |
| 共有知識はknowledge skillに集約 | 概念・NG/OK・チェックリストは共有 |
| 依存関係をdepends_onで明示 | 隠れ依存ゼロ |
| 巨大1スキルは禁止 | 12章→1スキルはNG |

分割の詳細な判断基準は `references/planning-strategy.md` を参照。

---

### NG / OK テーブル

| NG | OK | 理由 |
|----|-----|------|
| 12章を1スキルにまとめる | 目的別に分割 | 巨大スキルは実行不能 |
| リソース未取得なのにexecutableとだけ書く | unresolved欄に記載し取得を促す | プロンプト本文なしでは実行できない |
| 全概念をスキルに入れる | 基盤概念はshared_knowledgeに | Progressive Disclosure |
| ユーザー承認なしでsynthesizerに渡す | 必ずプラン提示→承認 | スキル構成はユーザーが決める |
| trigger_wordsに「作成」「生成」のような汎用語 | 「PredictionX」「FusionOmega」等の講座固有ワード | 汎用語だと誤発動する |
| depends_onに存在しないスキル名 | 実在するスキル名のみ | 壊れた依存は実行時エラー |
| 手順なし・リソースなしでexecutableにする | shared_knowledgeに統合するか、unresolvedに記載 | 実行に必要な材料がない |

---

### BLOCKER: ユーザー承認

> **skill-plan.jsonを生成したら、必ず以下のフォーマットでユーザーに提示し、承認を得ること。**
> **承認を得るまでskill-synthesizerに渡してはならない。**

---

### ユーザーへの提示

処理完了後、以下のフォーマットで提示:

```
## Skill Plan: {course_name}

### ヒアリング仮説との照合
manifest.jsonのuser_context.skill_hypothesesがある場合、仮説との照合結果を表示:

| 仮説 | 結果 | 対応スキル |
|------|------|-----------|
| {hypothesis} | ✅ 検出 / ⚠️ リソース未取得 / ❌ 該当なし | {skill_name or "—"} |

➕ 追加発見: {仮説になかったが作れるスキル}

### Executable Skills ({n}件)

| # | スキル名 | 目的 | リソース | 状態 |
|---|---------|------|---------|------|
| 1 | {skill_name} | {purpose} | {resource_names} | Ready / Unresolved |
| ... |

### Shared Knowledge
- 基盤概念: {n}件
- NG/OKパターン: {n}件
- チェックリスト: {n}件
- 参照マニュアル: {manual_refs}

### 依存関係
```
{dependency_graph as text}
```

### 未解決項目 ({n}件)
| リソース名 | 言及箇所 | 必要なアクション |
|-----------|---------|----------------|
| {name} | {mentioned_in} | {action_needed} |

---

このプランでスキルを生成しますか？（全部 / 選択 / 修正）
```

---

### ユーザーの回答への対応

| 回答 | 対応 |
|------|------|
| 全部 | skill-plan.jsonをそのまま確定。skill-synthesizerの実行を提案 |
| 選択 | ユーザーが選んだスキルのみでskill-plan.jsonを更新 |
| 修正 | ユーザーの修正指示に従いskill-plan.jsonを更新し、再提示 |
