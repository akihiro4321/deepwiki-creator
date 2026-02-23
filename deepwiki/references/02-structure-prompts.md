# DeepWiki: Wiki構造設計・ユーザー提案フォーマット

[SKILL.md](../SKILL.md) の **Phase 2: Wiki 構造設計** において、LLMが設計するページの規模、セクション構成、ユーザーへの提案方法、および `outline.json` のスキーマに関するルール。

---

## 1. 規模ガイドライン & セクション構成

設計するWikiは対象の規模に応じたページ数を確保すること。大規模リポジトリで15ページ以下は不可。

| 規模 | ファイル数目安 | セクション数 | 総ページ数 |
| :--- | :--- | :--- | :--- |
| 小規模 | < 30 | 3-4 | 8-15 |
| 中規模 | 30-200 | 4-6 | 15-30 |
| 大規模 | > 200 | 6-8+ | **30-50** |

**セクション構成テンプレート（6セクション基本形）**
※対象に該当しないもの以外は省略不可。「User Guide」などは特に省略しがちだが極めて重要。

1. `Overview（概要）`: Architecture Overview / Project Structure
2. `Getting Started（はじめに）`: Installation / Authentication / Basic Setup
3. `User Guide（ユーザーガイド）`: CLI Usage / Modes / Plugin Usage など
4. `Core Systems（コアシステム）`: 各アーキテクチャ・モジュールごとにページを生成
5. `Advanced Topics（応用トピック）`: Extension System / Security / Observability など
6. `Development（開発）`: Dev Setup / Build System / Testing Env

各ページには `id`, `title`, `filePaths` (5〜15ファイル程度を列挙), `importance` (high/medium/low), `relatedPages`, `keyClasses` のパラメータを含めて設計する。

---

## 2. ユーザー確認のための提示フォーマット（Markdown表形式）

提案時はJSON構造をそのまま出力するのではなく、必ず人間が読みやすいMarkdownの箇条書きや表形式でユーザーに提示して「停止」する。

```markdown
以下の構造でWikiを生成します。よろしければ「OK」とお伝えください。

## 提案するWiki構造（全17ページ）

### Section 1: Architecture Overview（アーキテクチャ概要）
| # | ページタイトル | importance | 主な参照ファイル |
|---|---|---|---|
| 1.1 | System Architecture | high | `src/index.ts`, `src/core/app.ts` |
| 1.2 | Core Abstractions | high | `src/core/*.ts` |

### Section 2: Data Layer（データ層）
| # | ページタイトル | importance | 主な参照ファイル |
|---|---|---|---|
| 2.1 | Data Models | medium | `src/models/*.ts` |

（以下、全セクション続く）

**修正希望やページの追加・削除があればお知らせください。**
```

> [!WARNING]
> Phase 2b（ユーザー提案時）の段階では、**絶対に JSON フォーマット（後の outline.json として使うもの）を出力してはいけません**。提案は全てMarkdown形式で行ってください。

---

## 3. `outline.json` スキーマ仕様

ユーザー承認後に指定ディレクトリに出力する進捗管理用のJSONフォーマット。
`status` 項目は初期値 `"pending"` で生成し、以降の Phase 3c（検証合格後）で逐次 `"done"` に更新する。

> [!WARNING]
> **`generate_pages.py` が直接参照するフィールドは変更・省略禁止。** フィールド名を変えると（例: `title` を `projectName` にするなど）スクリプトが正常動作しない。

```json
{
  "title": "プロジェクト名 Wiki Outline",
  "generatedAt": "2026-02-22T12:00:00+09:00",
  "outputDir": "/path/to/docs/wiki",
  "targetDir": "/path/to/target/project",
  "pages": [
    {
      "id": "1.1",
      "title": "Architecture Overview",
      "description": "システムの全体アーキテクチャとディレクトリ構成の解説",
      "filename": "1.1-architecture-overview.md",
      "filePaths": [
        "/absolute/path/to/src/index.ts",
        "/absolute/path/to/src/core/app.ts"
      ],
      "importance": "high",
      "relatedPages": ["2.1"],
      "status": "pending"
    }
  ]
}
```

**各フィールドの詳細:**

| フィールド | 必須 | 型 | 説明・注意事項 |
| :--- | :---: | :--- | :--- |
| `title` | ○ | string | Wiki全体のタイトル。`projectName` など別名は使わないこと |
| `generatedAt` | ○ | string | ISO 8601形式のタイムスタンプ |
| `outputDir` | ○ | string | Wikiファイルの出力先（絶対パス） |
| `targetDir` | ○ | string | 解析対象コードベースのルート（絶対パス）。`generate_pages.py` が参照 |
| `pages[].id` | ○ | string | `"1.1"` のようなセクション番号形式 |
| `pages[].title` | ○ | string | ページタイトル（英語） |
| `pages[].description` | ○ | string | Geminiへの生成指示として使用。具体的に記述するほど品質が上がる |
| `pages[].filename` | ○ | string | `"1.1-architecture-overview.md"` 形式。省略すると id から自動生成 |
| `pages[].filePaths` | ○ | string[] | 参照ファイルパスのリスト（5〜15ファイル推奨）。絶対パスを推奨 |
| `pages[].importance` | ○ | string | `"high"` / `"medium"` / `"low"` のいずれか（小文字必須） |
| `pages[].relatedPages` | △ | string[] | 関連ページのIDリスト（省略可） |
| `pages[].status` | ○ | string | 初期値は必ず `"pending"`。スクリプトが `"done"` または `"error"` に更新する |
