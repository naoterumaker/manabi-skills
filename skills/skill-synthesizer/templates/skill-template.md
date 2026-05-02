# Executable Skill Template

生成するexecutable skillのSKILL.mdテンプレート。`{{placeholder}}` を実データで置換する。

---

```markdown
---
name: {{skill_name}}
description: "{{purpose}}。「{{trigger_words}}」で発動。"
---

# {{skill_display_name}}

## WHAT

{{purpose}} を実行する。

## WHY

{{rationale}}

**このスキルではないもの**:
{{anti_selection}}

## HOW

### 入力

| 項目 | 説明 | 必須 |
|------|------|------|
{{#each inputs}}
| {{name}} | {{description}} | {{required}} |
{{/each}}

### 手順

{{#each steps}}
#### Step {{step_number}}: {{step_name}}

{{step_description}}

{{#if has_template}}
> このステップのテンプレート: `assets/prompts/{{template_name}}.md`
{{/if}}

{{#if has_blocker}}
> **BLOCKER**: {{blocker_condition}}
{{/if}}

{{/each}}

### 出力

| 項目 | 説明 |
|------|------|
{{#each outputs}}
| {{name}} | {{description}} |
{{/each}}

---

## NG/OK テーブル

| NG | OK | 理由 |
|----|-----|------|
{{#each ng_ok_rows}}
| {{ng}} | {{ok}} | {{reason}} |
{{/each}}

---

## 自己検証チェックリスト

{{#each verification_items}}
- [ ] {{item}}
{{/each}}

---

## 詳細な解説

画像付きの詳細説明: `{{manual_ref}}`

---

## 依存

{{#each dependencies}}
- {{skill_name}}: {{reason}}
{{/each}}

---

## 参照ファイル

| ファイル | 内容 | いつ読むか |
|---------|------|----------|
| `assets/prompts/*.md` | プロンプトテンプレート | 手順実行時 |
| `references/concepts.md` | 関連概念の詳細 | 概念を深掘りするとき |
| `references/ng-ok.md` | 拡張NG/OKパターン | 品質改善時 |
```

---

## Shared Knowledge Skill Template

```markdown
---
name: {{course}}-knowledge
description: "{{course}}の基盤概念・ナレッジグラフ・暗黙知を提供。他のスキルが概念を参照する際に使用。「{{course}}の概念」「{{course}}のナレッジ」「{{course}}の知識」で発動。"
---

# {{course}} Knowledge Base

## WHAT

{{course}}の全概念・暗黙知・知識グラフを集約し、
他のexecutable skillが参照するナレッジハブとして機能する。

## WHY

- 概念定義を各スキルに重複させない
- 概念間の依存関係を一元管理する
- 暗黙知・引用を保全する

## 概念インデックス

| カテゴリ | 概念名 | 簡潔な定義 |
|---------|--------|-----------|
{{#each concepts}}
| {{category}} | {{name}} | {{brief_definition}} |
{{/each}}

## 参照ファイル

| ファイル | 内容 | いつ読むか |
|---------|------|----------|
| `references/concepts.md` | 全概念の詳細定義・例・引用 | 概念を深掘りするとき |
| `references/knowledge-graph.md` | 概念間の依存関係マップ | 前提を確認するとき |
| `references/key-quotes.md` | 暗黙知・重要引用 | 根拠が必要なとき |
| `references/checklist.md` | 自己検証チェックリスト | 品質確認時 |
```

---

## テンプレート使用時の注意

### placeholderの置換ルール

| placeholder | データソース | 注意 |
|------------|------------|------|
| `{{skill_name}}` | skill-plan.jsonの各スキルのname | 英数字+ハイフンのみ |
| `{{purpose}}` | skill-plan.jsonのpurpose | 1文で簡潔に |
| `{{trigger_words}}` | skill-plan.jsonのtrigger_words | 日本語・英語両方 |
| `{{rationale}}` | skill-plan.jsonのrationale + concepts | 箇条書き3-5項目 |
| `{{manual_ref}}` | skill-plan.jsonのmanual_ref | 実在パスを検証 |
| `{{dependencies}}` | skill-plan.jsonのdepends_on | 実在スキル名のみ |
| `{{steps}}` | procedures.jsonから該当手順 | テンプレート参照含む |
| `{{ng_ok_rows}}` | tacit_knowledge + 失敗パターン | スキル固有のみ |

### BLOCKER配置の判断基準

手順中に以下の条件があればBLOCKERを配置:

1. **不可逆操作の直前**: やり直しが困難なステップ
2. **前提条件の確認**: 必要な準備が整っていないと後続が無駄になるステップ
3. **品質ゲート**: 出力品質が基準を満たさないと先に進むべきでないステップ
4. **外部依存**: 外部サービスやユーザー入力が必要なステップ

### 行数管理

生成後に `wc -l SKILL.md` で行数を確認。500行を超えた場合:

1. 手順の詳細ステップをassets/に移動
2. NG/OKテーブルの行をreferences/ng-ok.mdに退避（主要5行のみ残す）
3. WHYセクションを簡潔にする
4. 概念詳細をreferences/concepts.mdに完全委譲
