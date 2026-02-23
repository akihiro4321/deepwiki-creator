---
name: deepwiki
description: コードベースを解析し、DeepWiki のような包括的なWikiドキュメントを自動生成するスキル。ユーザーが「Wikiを作成して」「コードベースをドキュメント化して」と依頼した場合に使用する。アーキテクチャ図（Mermaid）やコードスニペットを活用した詳細なドキュメントを生成する。
---

# DeepWiki - コードベース分析＆ドキュメント生成スキル

リポジトリを深く解析し、包括的なWikiドキュメント（DeepWiki）の自動生成を提供する。

> **品質目標**: 新しい開発者がこの Wiki を読むだけでプロジェクトの全体像を把握し、すぐに開発を開始できること。また、既存機能を拡張・修正する際に、関連モジュールの設計意図・依存関係・データフローをこの Wiki から把握して方針を検討できること。そのために、十分な網羅性・技術的深度・ソースコード参照密度を確保する。
>
> **言語ルール**: ページタイトル・ファイルパスなどは**英語**、本文は**日本語**で記述する。（詳細は [references/01-analysis-prompts.md](references/01-analysis-prompts.md) の「言語ルール」を参照）

**LLMへの指示**: 本ファイル (`SKILL.md`) は**実行手順 (アルゴリズム)** のみを示す。各ステップで要求される「出力フォーマット」「品質基準」「チェックリスト」などの詳細は、必ず以下のフェーズ対応リファレンスを参照しながら作業を進めること。

- **Phase 1 用**: [references/01-analysis-prompts.md](references/01-analysis-prompts.md)
- **Phase 2 用**: [references/02-structure-prompts.md](references/02-structure-prompts.md)

---

## Phase 0: 開始前の確認（必須）

Phase 1 に進む前に、以下の2つのパスを確定する。**ユーザーのメッセージに含まれていない場合は必ず問い合わせること。** ターゲットディレクトリと出力ディレクトリが確定するまで Phase 1 に進んではいけない。

| 項目 | 説明 | 例 |
| :--- | :--- | :--- |
| **ターゲットディレクトリ** | 解析対象のコードベースのルートパス (`$TARGET_DIR`) | `/Users/username/projects/my-app` |
| **出力ディレクトリ** | Wiki ファイルの出力先パス (`$OUTPUT_DIR`) | デフォルト: `<ターゲット>/docs/wiki` |

---

## Phase 1: 構造分析

対象コードベースの全体像を把握する。README等のドキュメントが不十分でも、ソースコードから正確にアーキテクチャを理解する。

### Step 1a: メタデータ収集

1. コンテキスト取得スクリプトの実行:
   ```bash
   bash scripts/collect_structure.sh $TARGET_DIR
   ```
   （ディレクトリツリー、依存関係マップ、主要エクスポート・関数シグネチャの一覧などを取得）
2. 存在する主要ファイル（README, package.json等のパッケージ定義、ビルド設定、CI設定等）の優先的な読み取り。
3. 技術スタック、フレームワーク、主要な依存関係の特定。
4. エントリーポイント（`main.ts`, `index.ts` 等）の特定。
5. （モノレポの場合）各パッケージ間の依存関係の把握。

### Step 1b: ソースコード走査

> [!IMPORTANT]
> ファイル全体の深読みは Phase 3a で行うため、ここでは「浅く広く」各モジュールの責務・依存関係を把握し、**アーキテクチャ概要メモ**を作成することに集中する。

1. **importグラフの構築**: エントリーポイントから import されているモジュールを最大2階層辿り、依存の方向性や循環依存を把握する。
2. **主要ファイルのアウトライン取得**: `collect_structure.sh` で特定したファイルサイズ上位ファイルのアウトラインを取得し、複雑度（クラス数/メソッド数）を確認してページ分割の必要性を判断する。ファイル全体の精読はまだしない。
3. **アーキテクチャパターンの検出**: 主要なデザインパターン（Factory, Middleware, Repository 等）のキーワードをコード検索し、特定する。
4. **アーキテクチャ概要メモの作成**: 分析結果を整理する（フォーマット例については `01-analysis-prompts.md` を参照）。これが Phase 2 の入力となる。

---

## Phase 2: Wiki 構造設計

Step 1 の結果をもとに Wiki 構造を設計し、ユーザーの承認を得る。

### Step 2a: 構成の設計
`02-structure-prompts.md` に記載された「規模ガイドライン」と「セクション構成テンプレート」に従い、Wikiのページ構造（id, title, filePaths, importance, relatedPages 等）を設計する。

### Step 2b: ユーザーへの提案と承認依頼（⚠️ 必須停止ポイント）
> [!CAUTION]
> **ここで完全に処理を一時停止 (STOP) すること。** 設計したWiki構造を提示し、**ユーザーから明示的な許可（「OK」「進めて」など）を得るまでは、絶対に Phase 3 (ページ作成) に進んではいけない。**

提案の際は、JSONではなく**Markdownの表形式**で提示すること。（提示フォーマットの厳密な例は `02-structure-prompts.md` を参照）

### Step 2c: outline.json の出力
ユーザーから承認を得たら、Wiki出力ディレクトリ (`$OUTPUT_DIR/outline.json`) に進捗管理用のアウトラインをJSON形式で書き出す。

> [!IMPORTANT]
> **以下のスキーマを必ず厳守すること。** `generate_pages.py` はこのフィールド構造を前提として動作するため、フィールド名を変えたり省略したりするとスクリプトが正常に動作しない。

```json
{
  "title": "プロジェクト名 Wiki Outline",
  "generatedAt": "2026-02-22T12:00:00+09:00",
  "outputDir": "/path/to/docs/wiki",
  "targetDir": "/path/to/target/project",
  "remoteBaseUrl": "https://github.com/org/repo",
  "pages": [
    {
      "id": "1.1",
      "title": "Architecture Overview",
      "description": "システムの全体アーキテクチャとディレクトリ構成の解説",
      "filename": "1.1-architecture-overview.md",
      "filePaths": ["src/index.ts", "src/core/app.ts"],
      "importance": "high",
      "relatedPages": ["2.1"],
      "status": "pending"
    }
  ]
}
```

**`generate_pages.py` が参照する必須フィールド（絶対に省略・改名不可）:**

| フィールド | 型 | 説明 |
| :--- | :--- | :--- |
| `targetDir` | string | 解析対象コードベースのルートパス（絶対パス） |
| `pages[].id` | string | ページID（例: `"1.1"`, `"2.3"`） |
| `pages[].title` | string | ページタイトル |
| `pages[].description` | string | ページの説明（Geminiへの生成指示として使用） |
| `pages[].filename` | string | 出力ファイル名（例: `"1.1-architecture-overview.md"`） |
| `pages[].filePaths` | string[] | 参照ファイルパスのリスト（5〜15ファイル推奨） |
| `pages[].importance` | string | `"high"` / `"medium"` / `"low"` のいずれか |
| `pages[].status` | string | 初期値は必ず `"pending"`（スクリプトが `"done"` に更新する） |
| `remoteBaseUrl` | string | （省略可）リモートリポジトリのベースURL（例: `"https://github.com/org/repo"`）。`fix_sources.py` が `git remote` から自動取得できない場合のフォールバックとして使用 |

（その他のフィールドの詳細については `02-structure-prompts.md` を参照）

---

## Phase 3: ページ単位の生成ループ（スクリプト委譲）

> [!CAUTION]
> **核心ルール: 親エージェント自身で各ページのコンテキスト（ソースコード）を直接読み込んだり、各Markdownページを直接執筆してはいけない。** 
> ページ生成と品質検証（自己修正）のループは、必ず専用のオーケストレーションスクリプトに委譲すること。

### Step 3a: ページ生成スクリプトの実行
`outline.json` が作成・承認されたら、以下のコマンドを実行してページ生成プロセスを開始する。

```bash
python3 scripts/generate_pages.py $OUTPUT_DIR/outline.json
```

このスクリプトは以下の処理を自動で行う：
*   未生成のページ情報を `outline.json` から取得する
*   複数のページ並列で `gemini` CLI コマンドを非同期発行する
*   生成完了後、`validate_page.py` を呼び出して品質検証を実施する
*   検証で不十分な場合（Grade C以下）、エラー出力と修正指示を用いて再生成（リトライ）を自動で最大2回実行する
*   生成が成功したページのステータスを `outline.json` で `"done"` に更新する

**親エージェント（あなた）は、このスクリプトの実行が完了するのを待つこと。**
スクリプト内で `gemini` CLIが自動承認モード（`auto_edit`）で動作するため、親エージェントが個別にファイル作成をサポートする必要はない。

### Step 3b: 実行結果の確認とリトライ（必要な場合のみ）
スクリプトの実行が終了したら、その標準出力を確認する。
もし `$OUTPUT_DIR/outline.json` 内に、ステータスが `"error"` となっているページ（最大リトライ後も生成に失敗したページ）が残っている場合は、ユーザーにその旨を報告し、どのように対処するか指示を仰ぐ。すべて `"done"` になっていれば Step 3c に進む。

### Step 3c: Mermaidルール一括チェック＆修正
全ページの生成が完了したら、以下のコマンドを実行してMermaidダイアグラムのルール違反を一括検出・修正する。

```bash
python3 scripts/fix_mermaid.py $OUTPUT_DIR/outline.json
```

このスクリプトは以下の処理を自動で行う：
- `outline.json` の全 `done` ページのMarkdownファイルを走査する
- Mermaidブロックを抽出し、以下のルール違反を静的チェックする：
  - `flowchart LR` / `graph LR` の使用（TD強制）
  - ノードIDにハイフンを含む
  - ノードラベル内の括弧（`()`, `[]`）がクォートされていない
  - HTMLタグの使用
  - シーケンス図でのフローチャート風記法
- 違反があればGemini CLIで**違反箇所のみ**を修正する（他の部分は変更しない）
- 修正後に再チェックして確認する

スクリプト完了後、問題なければ Step 3d に進む。

### Step 3d: Sources リンク形式の確認と変換（⚠️ ユーザーへの確認が必要）

> [!CAUTION]
> **実行前に必ずユーザーへ確認すること。** 選択肢を提示して回答を得てから `fix_sources.py` を実行する。

ユーザーに以下の選択肢を提示する：

```
Sources行のリンクをどの形式にしますか？

1. GitHub / GitLab URL（推奨）
   チームで共有できる。ブラウザから行番号付きで開ける。
   例: https://github.com/org/repo/blob/main/src/file.ts#L100-L200

2. vscode:// URL
   ローカルの VSCode から直接ジャンプできる。
   例: vscode://file//absolute/path/to/src/file.ts:100

3. 変換しない（file:/// のまま）
```

ユーザーの回答に応じて以下を実行する：

**① GitHub/GitLab URL を選んだ場合**

`git remote get-url origin` でリモートURLを自動取得する。取得できない場合はユーザーにURLを確認する。

```bash
# リモートURLを自動取得できる場合
python3 scripts/fix_sources.py $OUTPUT_DIR/outline.json --link-style github

# 取得できない場合（ユーザーから URL を聞いた後）
python3 scripts/fix_sources.py $OUTPUT_DIR/outline.json --link-style github --remote-url https://github.com/org/repo
```

**② vscode:// URL を選んだ場合**

```bash
python3 scripts/fix_sources.py $OUTPUT_DIR/outline.json --link-style vscode
```

**③ 変換しないを選んだ場合**

このステップをスキップして Phase 4 に進む。

---

## Phase 4: 結合・整形
（すべてのページの生成ループが完了した後に実行）

1. **インデックスページ (`index.md`) の作成**:
   以下のスクリプトを実行して、`outline.json` からWiki全体の目次ページを自動生成する。
   ```bash
   python3 scripts/create_index.py $OUTPUT_DIR/outline.json
   ```
2. 全体バリデーションの実行（必要に応じて）:
   ```bash
   python3 scripts/validate_page.py $OUTPUT_DIR
   ```

## Phase 5: 完了報告
生成された Wiki の出力先パスと、主要なページのハイライトをユーザーに報告し、処理を終了する。

---

## GitHubリポジトリの場合（特殊ケース）

対象がGitHubリポジトリURLの場合：
1. `git clone --depth 1 <URL> /tmp/deepwiki-<repo-name>` で shallow clone
2. 上記の Phase 1〜4 を実行
3. 成果物を指定の出力先にコピー
4. クローンした一時ディレクトリを削除
