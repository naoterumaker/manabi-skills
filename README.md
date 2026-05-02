# Manabi Skills

動画講座・ドキュメント・Notionなどの**学習素材を「取り込む → ナレッジ化 → マニュアル化 → スキル化」**まで一気通貫で処理するClaude Code Skillsパッケージ。

UTAGE / YouTube / Udemy / Loom / ローカル動画 / Notion などに対応。

## Quick Start

```bash
# 全スキル一括インストール（Claude Code向け）
npx skills add naoterumaker/manabi-skills -g -a claude-code -y --copy
```

インストール後、Claude Codeで以下のようにトリガー:

```
講座を取り込んで → manabi-ingest が起動
```

## パイプライン構成

```
入力（動画URL / ファイル / Notion等）
        │
        ▼
┌───────────────────┐
│  manabi-ingest    │ ← 入口・オーケストレーター
│  （入力タイプ判定 │
│   → DL → 文字起こし│
│   → スクショ抽出） │
└─────────┬─────────┘
          │ course-bundle/ 生成
          ▼
   並列実行（3スキル）
   ┌──────────┬──────────────┬──────────────┐
   ▼          ▼              ▼              ▼
concept-    procedure-    visual-      （utage-manual:
extractor   extractor     indexer       マニュアル本文生成）
   │          │              │              │
   └──────────┴──────────────┴──────────────┘
          │ knowledge.json / procedures.json /
          │ visual-index.json
          ▼
┌───────────────────┐
│  skill-planner    │ ← 何のスキルが作れるか計画
│  （ユーザー承認）  │
└─────────┬─────────┘
          │ skill-plan.json
          ▼
┌───────────────────┐
│ skill-synthesizer │ ← 計画に基づき複数スキル自動生成
└─────────┬─────────┘
          │
          ▼
   generated_skills/ （配布可能なSKILL.md群）
```

## 同梱スキル一覧

| スキル | 役割 |
|--------|------|
| **manabi-ingest** | 入口。入力タイプ判定 → 動画DL → 文字起こし → スクショ抽出 → course-bundle作成 → レベル選択（ナレッジのみ/マニュアル/スキル化）|
| **utage-manual** | UTAGE特化の取り込み + 画像付きMarkdownマニュアル生成（Groq Whisperで文字起こし） |
| **concept-extractor** | トランスクリプトから概念・暗黙知・引用を構造化抽出 → `knowledge.json` |
| **procedure-extractor** | UI操作・設定手順を抽出してスクショと紐付け → `procedures.json`（マルチモーダル） |
| **visual-indexer** | 全スクショを分類・OCR・タグ付け → `visual-index.json` |
| **skill-planner** | 抽出結果から「何のスキルが作れるか」計画 → `skill-plan.json`（要承認） |
| **skill-synthesizer** | skill-plan.json から複数のClaude Code Skillを自動生成 |

## セットアップ

### 1. インストール

```bash
# Claude Code向け（全スキル）
npx skills add naoterumaker/manabi-skills -g -a claude-code -y --copy

# 特定スキルだけ入れる場合
npx skills add naoterumaker/manabi-skills -g -a claude-code --skill manabi-ingest -y --copy
```

### 2. 必要なAPIキー設定（utage-manual を使う場合）

文字起こしに **Groq Whisper API** を使用します。各自で無料枠を取得してください。

1. https://console.groq.com/keys でAPIキー発行
2. `.env` ファイルを作成:

```bash
cd ~/.claude/skills/utage-manual
cp .env.example .env
# エディタで .env を開いて GROQ_API_KEY=gsk_... を入れる
```

### 3. 必要なツール

| ツール | 用途 | インストール |
|--------|------|-------------|
| `ffmpeg` | 動画分割・音声抽出 | `brew install ffmpeg` |
| `yt-dlp` | YouTube/Loom DL | `brew install yt-dlp` |
| Python 3.10+ | 各種スクリプト実行 | (標準) |
| `imagehash`, `Pillow` | スクショ重複排除 | `pip install imagehash Pillow` |

## 使い方の例

### 動画講座をスキル化まで一気通貫

```
あなた: この講座 https://example.utage-system.com/... をスキル化までやって
Claude: manabi-ingest が起動 → ヒアリング → 処理計画提示 → 取り込み開始
        → ナレッジ抽出 → skill-planner（承認待ち）→ skill-synthesizer
        → generated_skills/ に複数スキル出力
```

### ナレッジ抽出だけ

```
あなた: この動画を取り込んでナレッジだけ作って
Claude: manabi-ingest → course-bundle作成 → レベル1（ナレッジのみ）実行
```

## コマンドリファレンス

### インストール / 更新 / 削除

```bash
# 全スキル一括インストール（Claude Code）
npx skills add naoterumaker/manabi-skills -g -a claude-code -y --copy

# Codex向け
npx skills add naoterumaker/manabi-skills -g -a codex -y --copy

# 両方向け
npx skills add naoterumaker/manabi-skills -g -a claude-code -a codex -y --copy

# スキル一覧表示
npx skills add naoterumaker/manabi-skills --list

# 更新
npx skills update -g

# 削除
npx skills remove manabi-ingest -g
```

## ライセンス

MIT

## クレジット

- Skills CLI: [Vercel Skills](https://github.com/vercel-labs/skills)
- 文字起こし: [Groq Whisper](https://console.groq.com/)
