---
name: skill-synthesizer
description: "skill-plannerが生成したskill-plan.jsonに基づき、複数の独立したClaude Codeスキルを自動生成する。executable skillにはassets/にプロンプトテンプレートを格納し、shared knowledgeスキルに基盤概念を集約する。「スキル合成」「skill synthesize」「ナレッジからスキル生成」「スキル自動生成」「planからスキル生成」で発動。skill-plannerの完了後に実行。"
---

# Skill Synthesizer v2

## WHAT

skill-plan.json（skill-plannerが生成しユーザーが承認済み）を読み込み、
複数の独立したClaude Codeスキルを自動生成する。
1スキル=1目的。executable skillにはプロンプトテンプレートを、
shared knowledgeスキルには基盤概念を格納する。

## WHY

- v1は1講座=1モノリシックスキルだった → スキルが肥大化し発火精度が下がる
- skill-plannerでユーザーが構成を承認済み → その設計を忠実に実装する
- 各スキルが独立していれば、個別に改善・テスト・差し替えできる
- プロンプトテンプレートがないexecutable skillは実行不能 → assets/必須

## ⚠️ 重要: Write権限の制約と回避策

`~/.claude/skills/` への直接Writeは権限ブロックされる。
**必ずstaging directory経由で生成する。**

### 生成フロー

```bash
# Step 1: staging dir に生成
STAGING="${COURSE_BUNDLE_DIR:-$(pwd)}/generated_skills"
mkdir -p $STAGING
# → 全SKILL.md, references/, assets/ をここに書く

# Step 2: ユーザーまたはメインセッションがcpで移動
cp -r $STAGING/* ~/.claude/skills/
```

### Agent委譲時の必須指示

skill-synthesizerをAgentで実行する場合、プロンプトに必ず明記する:

「**STAGING OUTPUT**: /path/to/generated_skills/
Write all skill files under this staging directory.
After completion, the user will move them to ~/.claude/skills/.」

---

## HOW

### 入力ファイル

| ファイル | 提供元 | 必須 |
|---------|--------|------|
| `skill-plan.json` | skill-planner | Yes |
| `knowledge/*.json` | concept-extractor | Yes |
| `chapters/*/procedures.json` | procedure-extractor | Yes |
| `resources/` | resource-fetcher | 条件付き |
| `resources-manifest.json` | resource-fetcher | 条件付き |
| `manuals/*.md` パス | utage-manual | No（参照のみ） |

### 出力構造

**executable skill（計画の各スキルごと）**:
```
~/.claude/skills/{skill-name}/
  SKILL.md                    ← 単一目的、プロンプト埋込またはassets参照
  assets/
    prompts/{template}.md     ← 実際のプロンプトテンプレート本文
  references/
    concepts.md               ← このスキルに関連する概念のみ
    ng-ok.md                  ← このスキル固有の失敗パターン
```

**shared knowledge skill**:
```
~/.claude/skills/{course}-knowledge/
  SKILL.md                    ← インデックス + 基盤概念
  references/
    concepts.md               ← 全概念
    knowledge-graph.md        ← 依存関係マップ
    key-quotes.md             ← 暗黙知・引用
    checklist.md              ← 自己検証チェックリスト
```

---

## 処理ステップ

### Step 1: skill-plan.json の読み込みと検証

> **BLOCKER**: skill-plan.json が存在し、`approved: true` でなければ先に進むな

```bash
cat "${BUNDLE_DIR}/skill-plan.json" | jq '.approved'
```

検証項目:

| チェック | 条件 |
|---------|------|
| skill-plan.json存在 | ファイルが存在する |
| approved フラグ | `true` である |
| skills 配列 | 1件以上のスキル定義がある |
| 各スキルに name | 全スキルに `name` フィールドがある |
| 各スキルに type | `executable` or `shared_knowledge` |
| 各スキルに procedures | executable には手順IDリストがある |
| 各スキルに concepts | 関連概念IDリストがある |
| 各スキルに trigger_words | executable には発動ワードがある |

**検証失敗時**: skill-plannerの再実行を促す。plan未承認ならユーザーに承認を求める。

### Step 2: ソースデータの収集

全 `knowledge/*.json` と `chapters/*/procedures.json` を読み込む。

```bash
# 概念の総数確認
find "${BUNDLE_DIR}/knowledge" -name "*.json" -exec cat {} \; | jq '[.concepts[]] | length' 2>/dev/null

# 手順の総数確認
find "${BUNDLE_DIR}/chapters" -name "procedures.json" -exec cat {} \; | jq '[.procedures[]] | length' | paste -sd+ | bc
```

resources/ が存在する場合、`resources-manifest.json` も読み込む。

### Step 3: 各executable skillの生成

skill-plan.jsonの各 `type: "executable"` スキルについて:

#### 3a. データ収集

- `procedures` IDリストから該当手順を `chapters/*/procedures.json` から抽出
- `concepts` IDリストから該当概念を `knowledge/*.json` から抽出
- `resources` リストから該当リソースを `resources/` から特定

#### 3b. assets/ の生成

> **BLOCKER**: executable skillにプロンプトテンプレートが1つもない場合、生成を中止

リソースからプロンプトテンプレートを `assets/prompts/` にコピー:

```bash
mkdir -p "${SKILL_DIR}/assets/prompts"
# resources-manifest.json の該当エントリからコピー
cp "${BUNDLE_DIR}/resources/${resource_file}" "${SKILL_DIR}/assets/prompts/"
```

プロンプトテンプレートがresourcesに存在しない場合:
- procedures.jsonの手順内容からプロンプトテンプレートを生成
- 手順のステップ・入力・出力をテンプレート化
- `assets/prompts/{procedure-name}.md` として保存

#### 3c. SKILL.md の生成

`templates/skill-template.md` のパターンに従い生成。以下の構造:

```markdown
---
name: {skill_name}
description: "{purpose}。「{trigger_words}」で発動。"
---

# {skill_name}

## WHAT
{purpose} を実行する。

## WHY
{rationale}

## HOW

### 入力
{input description from plan}

### 手順
{steps from procedures.json}
各ステップでプロンプトテンプレートを参照:
> このステップのテンプレート: `assets/prompts/{template}.md`

> BLOCKER: {critical check from procedures}

### 出力
{output description from plan}

## NG/OK テーブル
{skill-specific failure patterns from concepts + procedures}

## 自己検証チェックリスト
{skill-specific checks}

## 詳細な解説
画像付きの詳細説明: `{manual_ref}`

## 依存
- {depends_on skill name}: {why}
```

#### 3d. references/ の生成

```bash
mkdir -p "${SKILL_DIR}/references"
```

| ファイル | 内容 |
|---------|------|
| `concepts.md` | このスキルの `concepts` IDに対応する概念のみ |
| `ng-ok.md` | この手順固有の失敗パターン（tacit_knowledgeから抽出） |

### Step 4: shared knowledge skillの生成

skill-plan.jsonの `type: "shared_knowledge"` エントリに基づき生成。

#### 4a. SKILL.md

```markdown
---
name: {course}-knowledge
description: "{course}の基盤概念・ナレッジグラフ・暗黙知を提供。他のスキルが概念を参照する際に使用。「{course}の概念」「{course}のナレッジ」で発動。"
---

# {course} Knowledge Base

## WHAT
{course}の全概念・暗黙知・知識グラフを集約し、
他のexecutable skillが参照するナレッジハブとして機能する。

## WHY
- 概念定義を各スキルに重複させない
- 概念間の依存関係を一元管理する
- 暗黙知・引用を保全する

## 概念インデックス
{全概念の名前・カテゴリ・簡潔な定義のテーブル}

## 参照ファイル
| ファイル | 内容 | いつ読むか |
|---------|------|----------|
| `references/concepts.md` | 全概念の詳細 | 概念を深掘りするとき |
| `references/knowledge-graph.md` | 依存関係マップ | 前提を確認するとき |
| `references/key-quotes.md` | 暗黙知・引用 | 根拠が必要なとき |
| `references/checklist.md` | 自己検証チェックリスト | 品質確認時 |
```

#### 4b. references/

| ファイル | 内容ソース |
|---------|----------|
| `concepts.md` | 全knowledge/*.jsonの全概念（カテゴリ別） |
| `knowledge-graph.md` | knowledge-graph.jsonからMermaid図 + テーブル |
| `key-quotes.md` | tacit_knowledge + 重要引用 |
| `checklist.md` | 全スキル横断の自己検証チェックリスト |

### Step 5: depends_on の検証

> **BLOCKER**: 未解決のdepends_onがあれば生成完了としない

```bash
STAGING_DIR="${COURSE_BUNDLE_DIR:-$(pwd)}/generated_skills"

# 生成された全SKILL.mdからdepends_onを抽出
grep -r "^- " "${STAGING_DIR}"/*/SKILL.md | grep "depends_on"

# stagingに存在するスキル名のリスト
ls -d "${STAGING_DIR}"/*/
```

全depends_on参照が実在するスキルディレクトリを指していることを確認。
未解決の参照があれば:
1. 参照先スキルがplanに含まれているか確認
2. 含まれていれば生成順序の問題 → 生成を続行
3. 含まれていなければエラー報告

### Step 6: staging への書き出し確認

全ファイルが `STAGING_DIR="${COURSE_BUNDLE_DIR:-$(pwd)}/generated_skills"` 以下に書かれていることを確認する。
`~/.claude/skills/` への直接書き込みは行わない。

### Step 7: ユーザーへの報告

以下の形式で提示:

```
## 生成結果

### 生成されたスキル

| スキル名 | タイプ | SKILL.md行数 | assets数 | depends_on |
|---------|--------|-------------|---------|-----------|
| {name}  | executable | {lines} | {count} | {deps}    |
| {name}-knowledge | shared | {lines} | - | - |

### 検証結果
- [ ] 全SKILL.mdが500行以下: {result}
- [ ] 全executable skillにassets/またはインラインプロンプトあり: {result}
- [ ] 全depends_onが実在するスキル名: {result}
- [ ] shared_knowledgeに基盤概念あり: {result}
- [ ] trigger_wordsが講座固有: {result}
- [ ] manual_refのパスが実在: {result}

### ファイル一覧
{generated file tree}
```

---

## マニュアル参照ルール

マニュアル（manuals/*.md）はコピーしない。パスで参照する。

```markdown
## 詳細な解説
画像付きの詳細説明: `{BUNDLE_DIR}/manuals/{chapter}.md`
```

マニュアルパスが実在するかを検証:
```bash
test -f "${BUNDLE_DIR}/manuals/${manual_file}" && echo "OK" || echo "MISSING"
```

---

## NG/OK テーブル

| NG | OK | 理由 |
|----|-----|------|
| 全データを1スキルに詰める | plan通りに分割 | 1スキル=1目的 |
| プロンプト本文なしでexecutable | assets/にテンプレート格納 | 実行できないスキルは作らない |
| マニュアルをコピーする | パスで参照 | 重複を避ける |
| plan未承認で生成開始 | skill-plan.jsonの承認確認 | ユーザーが構成を決める |
| depends_onが未解決 | 全参照が実在するか検証 | 隠れ依存ゼロ |
| 全概念を各スキルにコピー | 関連概念のみreferences/に | shared_knowledgeに一元化 |
| 汎用的なNG/OKテーブル | 手順固有の失敗パターンを分析 | 実用性に直結 |

---

## 自己検証チェックリスト

生成完了後、以下をすべて確認:

- [ ] 各スキルのSKILL.mdが500行以下か
- [ ] 各executable skillにassets/またはインラインプロンプトがあるか
- [ ] depends_onが全て実在するスキル名か
- [ ] shared_knowledgeに基盤概念が含まれているか
- [ ] trigger_wordsが講座固有か
- [ ] manual_refのパスが実在するか
- [ ] 各executable skillのreferences/concepts.mdがそのスキルの関連概念のみ含むか
- [ ] shared knowledge skillのreferences/concepts.mdが全概念を含むか
- [ ] resources-manifest.jsonの該当リソースがassets/にコピーされているか

---

## スコープ外

| やらないこと | 代わりに使うもの |
|------------|----------------|
| スキル構成の設計・分割判断 | skill-planner |
| 講座動画の取り込み | course-ingest |
| 概念の抽出 | concept-extractor |
| 手順の抽出 | procedure-extractor |
| リソースの取得 | resource-fetcher |
| マニュアル生成 | utage-manual |
| スキル設計の相談 | teru-skill-creator |
