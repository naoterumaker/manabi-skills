# Procedures Template

references/procedures.md 生成時のテンプレート。

---

```markdown
# {{course_name}} - 手順リファレンス

> このファイルは `SKILL.md` の補足資料です。手順を実行する際に参照してください。

## 概要

- 総手順数: {{total_procedures}}
- 主要手順（SKILL.md記載）: {{main_procedure_count}}件
- 補助手順: {{sub_procedure_count}}件

---

{{#each procedures}}
## {{procedure_name}}

**ID**: {{procedure_id}}
**複雑度**: {{complexity}}（low / medium / high）
**チャプター**: {{source_chapter}}
**関連概念**: {{related_concepts}}
**タグ**: {{tags}}

### 目的

{{objective}}

### 前提条件

{{#each prerequisites}}
- [ ] {{condition}}
{{/each}}

### 手順

{{#each steps}}
#### Step {{step_number}}: {{step_title}}

{{step_description}}

{{#if screenshot}}
**参考スクリーンショット**: `assets/selected_screenshots/{{screenshot}}`
{{/if}}

{{#if blocker}}
> **BLOCKER**: {{blocker_condition}}
> {{blocker_message}}
{{/if}}

{{#if warning}}
> **WARNING**: {{warning}}
{{/if}}

{{/each}}

### 期待される成果

{{outcome}}

### よくある失敗

| 失敗パターン | 原因 | 対処法 |
|------------|------|--------|
{{#each common_failures}}
| {{pattern}} | {{cause}} | {{solution}} |
{{/each}}

---

{{/each}}
```

---

## テンプレート使用時の注意

### データマッピング

| placeholder | データソース |
|------------|------------|
| `{{course_name}}` | manifest.json の course_name |
| `{{procedures}}` | 全chapters/*/procedures.json を結合 |
| `{{procedure_name}}` | procedures.json → procedures[].name |
| `{{complexity}}` | procedures.json → procedures[].complexity |
| `{{steps}}` | procedures.json → procedures[].steps |
| `{{screenshot}}` | visual-index.json で related_procedures にマッチするフレーム |
| `{{outcome}}` | procedures.json → procedures[].expected_outcome |
| `{{common_failures}}` | procedures.json → procedures[].common_failures + teaching_patterns |

### 手順の並び順

1. SKILL.mdに記載された主要手順を先頭に
2. 次に complexity = "high" → "medium" → "low" の順
3. 同じ complexity 内ではチャプター順

### スクショの紐づけ

visual-index.jsonの `related_procedures` フィールドでマッチング:
- マッチするスクショが複数ある場合: value_rating が最も高いものを選択
- マッチするスクショがない場合: スクショなしで記載（無理に追加しない）

### BLOCKERの配置基準

procedures.jsonから以下を検出してBLOCKERに変換:
- `is_critical: true` のステップ
- `reversible: false` のステップ
- 前提条件チェックを含むステップ

### 品質チェック

- [ ] 全手順に目的が記載されているか
- [ ] 前提条件が具体的か（「準備する」ではなく「Xをインストールする」）
- [ ] 各ステップが実行可能な粒度か
- [ ] 期待される成果が検証可能な形で書かれているか
- [ ] よくある失敗テーブルに対処法があるか
