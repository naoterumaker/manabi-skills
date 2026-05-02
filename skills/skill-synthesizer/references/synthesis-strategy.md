# Synthesis Strategy v2: Multi-Skill Generation

skill-plan.jsonに基づき複数の独立スキルを生成する際の詳細戦略。

## 1. v1からの変更点

| 項目 | v1 (モノリシック) | v2 (マルチスキル) |
|------|-----------------|-----------------|
| 入力 | knowledge.json直接 | skill-plan.json (承認済み) |
| 出力 | 1スキル | N個のexecutable + 1 shared knowledge |
| 概念配置 | 基盤→SKILL.md、残→references/ | 関連のみ→各スキルreferences/、全→shared |
| プロンプト | なし | assets/prompts/に格納必須 |
| マニュアル | なし | パス参照（コピーしない） |
| 依存管理 | なし | depends_on宣言+検証 |

## 2. skill-plan.jsonの構造

```json
{
  "course_name": "おさるAIマーケティング",
  "approved": true,
  "skills": [
    {
      "name": "osaru-funnel-builder",
      "type": "executable",
      "purpose": "ファネル構築の実行",
      "trigger_words": ["ファネル構築", "funnel build", "導線設計"],
      "procedures": ["proc_001", "proc_002"],
      "concepts": ["funnel", "lead_generation", "opt_in"],
      "resources": ["funnel-template.md"],
      "manual_ref": "manuals/chapter03.md",
      "depends_on": ["osaru-knowledge"],
      "rationale": "ファネル構築は独立した実行単位として最も頻繁に使われる"
    },
    {
      "name": "osaru-knowledge",
      "type": "shared_knowledge",
      "purpose": "基盤概念の一元管理",
      "concepts": ["all"],
      "rationale": "概念定義の重複を防ぎ、一元管理する"
    }
  ]
}
```

## 3. 概念の分配戦略

### shared knowledge skill

全概念を格納する。knowledge-graph.jsonの依存関係分析を行い:

```
基盤概念 = depended_by_count 上位30% or 被依存3件以上
```

基盤概念はSKILL.md本文の概念インデックスに要約を掲載。
全概念の詳細は references/concepts.md に格納。

### executable skill

skill-plan.jsonの `concepts` リストに該当する概念のみを
`references/concepts.md` に格納する。

**判定フロー**:
```
1. skill-plan.jsonの concepts IDリストを取得
2. knowledge/*.jsonから該当IDの概念を抽出
3. 該当概念のみ references/concepts.md に書き出す
4. SKILL.md本文には概念定義を書かない（shared knowledgeを参照）
```

## 4. プロンプトテンプレートの配置

### リソースからの取得

```
resources-manifest.json の該当エントリ
  → resources/{file} をそのまま assets/prompts/ にコピー
```

### 手順からの生成

リソースにプロンプトテンプレートがない場合:

```
procedures.json の手順
  → ステップ・入力・出力をテンプレート化
  → assets/prompts/{procedure-name}.md として生成
```

### テンプレートの構造

```markdown
# {テンプレート名}

## 目的
{このプロンプトで何を達成するか}

## 入力変数
| 変数 | 説明 | 例 |
|------|------|-----|
| {{var1}} | ... | ... |

## プロンプト本文

{実際のプロンプトテキスト}

## 期待される出力
{出力の形式・構造}
```

## 5. depends_on の設計

### 依存の種類

| 種類 | 例 | 宣言方法 |
|------|-----|---------|
| 知識依存 | executable → shared_knowledge | `depends_on: [{course}-knowledge]` |
| 順序依存 | skill-B は skill-A の出力が必要 | `depends_on: [skill-A]` |
| 共有依存 | 複数スキルが同じリソースを使う | shared_knowledgeに集約 |

### 検証アルゴリズム

```
1. 生成された全スキルのdepends_on を収集
2. 生成された全スキルの name を収集
3. depends_on の各エントリが name リストに存在するか確認
4. 未解決があればエラー報告（生成完了としない）
```

## 6. NG/OKテーブルの生成戦略

### 共通パターン（全スキルに適用しない）

v1では汎用NG/OKを全スキルに適用していた。
v2では各スキルの手順・概念から固有のパターンを生成する。

### 生成手順

```
1. 該当手順の tacit_knowledge を抽出
2. 「〜してはいけない」「〜は間違い」の表現を NG 列に
3. 「代わりに〜」「正しくは〜」の表現を OK 列に
4. 理由を teaching_patterns から補完
5. スキル固有でないパターンは除外
```

## 7. マニュアル参照ルール

マニュアルは参照専用。コピーしない。

### 正しい参照

```markdown
## 詳細な解説
画像付きの詳細説明: `{BUNDLE_DIR}/manuals/chapter03.md`
```

### やってはいけないこと

- マニュアルの内容をSKILL.mdにコピペ
- マニュアルの画像をassets/にコピー
- マニュアルの手順をproceduresの代わりに使う

### 検証

```bash
# manual_refが実在するか確認
for ref in $(cat skill-plan.json | jq -r '.skills[].manual_ref // empty'); do
  test -f "${BUNDLE_DIR}/${ref}" && echo "OK: ${ref}" || echo "MISSING: ${ref}"
done
```

## 8. 500行制限の管理

### executable skill の行数配分

| セクション | 目安行数 |
|-----------|---------|
| frontmatter + WHAT/WHY | 25行 |
| 入力/出力テーブル | 20行 |
| 手順（テンプレート参照含む） | 120行 |
| BLOCKERゲート | 20行 |
| NG/OKテーブル | 30行 |
| 自己検証チェックリスト | 20行 |
| 詳細な解説 + 依存 | 15行 |
| 参照ファイル | 15行 |
| バッファ | 35行 |
| **合計** | **300行目安（上限500行）** |

### shared knowledge skill の行数配分

| セクション | 目安行数 |
|-----------|---------|
| frontmatter + WHAT/WHY | 25行 |
| 概念インデックステーブル | 150行 |
| 参照ファイル | 15行 |
| バッファ | 60行 |
| **合計** | **250行目安（上限500行）** |

概念数が多い場合（50件超）:
- インデックスにはカテゴリ別の件数サマリーのみ
- 個別概念は全て references/concepts.md へ
