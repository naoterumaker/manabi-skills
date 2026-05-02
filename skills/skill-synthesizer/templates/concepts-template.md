# Concepts Template

references/concepts.md 生成時のテンプレート。

---

```markdown
# {{course_name}} - 概念リファレンス

> このファイルは `SKILL.md` の補足資料です。特定の概念を深掘りする際に参照してください。

## 概要

- 総概念数: {{total_concepts}}
- カテゴリ数: {{category_count}}
- 基盤概念: {{foundational_count}}件（SKILL.md本文にも記載）

---

{{#each categories}}
## カテゴリ: {{category_name}}

{{#each concepts}}
### {{concept_name}}

**分類**: {{classification}}（基盤 / 補助 / 詳細）
**チャプター**: {{source_chapter}}
**被依存数**: {{depended_by_count}}

#### 定義

{{definition}}

#### 具体例

{{#each examples}}
- {{example}}
{{/each}}

#### 重要引用

{{#each key_quotes}}
> "{{quote}}"
> — {{source}} ({{timestamp}})
{{/each}}

#### 関連概念

| 概念 | 関係 |
|------|------|
{{#each related}}
| {{name}} | {{relation}} |
{{/each}}

#### 暗黙知・補足

{{tacit_knowledge}}

---

{{/each}}
{{/each}}
```

---

## テンプレート使用時の注意

### データマッピング

| placeholder | データソース |
|------------|------------|
| `{{course_name}}` | manifest.json の course_name |
| `{{categories}}` | knowledge.json の concepts を category でグルーピング |
| `{{concept_name}}` | knowledge.json → concepts[].name |
| `{{classification}}` | knowledge-graph依存分析結果（基盤/補助/詳細） |
| `{{definition}}` | knowledge.json → concepts[].definition |
| `{{examples}}` | knowledge.json → concepts[].examples |
| `{{key_quotes}}` | knowledge.json → concepts[].key_quotes + tacit_knowledge |
| `{{related}}` | knowledge-graph.json → edges でこの概念に接続するノード |
| `{{tacit_knowledge}}` | knowledge.json → tacit_knowledge で関連するもの |

### カテゴリの並び順

1. 基盤概念を含むカテゴリを先頭に
2. カテゴリ内では depended_by_count 降順
3. 同数の場合はチャプター順

### 品質チェック

- [ ] 全概念に定義があるか
- [ ] 基盤概念には必ず具体例があるか
- [ ] 引用にはtimestampが付いているか
- [ ] 関連概念テーブルが空でないか（孤立概念は要確認）
