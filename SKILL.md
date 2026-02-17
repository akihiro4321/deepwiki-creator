---
name: deepwiki
description: コードベースを解析し、DeepWiki のような包括的なWikiドキュメントを自動生成するスキル。ユーザーが「Wikiを作成して」「コードベースをドキュメント化して」「リポジトリの解析ドキュメントを生成して」「コードの全体像をまとめて」等と依頼した場合に使用する。ローカルコードベースまたはGitHubリポジトリを対象に、アーキテクチャ図（Mermaid）付きの構造化されたドキュメントを生成する。
---

# DeepWiki - コードベースWiki自動生成スキル

リポジトリを解析し、DeepWiki 風の包括的なWikiドキュメントを Markdown で生成する。

> **品質目標**: 新しい開発者がこの Wiki を読むだけでプロジェクトの全体像を把握し、すぐに開発を開始できること。また、既存機能を拡張・修正する際に、関連モジュールの設計意図・依存関係・データフローをこの Wiki から把握して方針を検討できること。そのために、十分な網羅性・技術的深度・ソースコード参照密度を確保する。

> **言語ルール**: ページタイトルは**英語**で記述する。本文は**日本語**で記述する。ただし以下は英語のまま維持する：
> - ページタイトル・ファイル名
> - コード内のクラス名・関数名・変数名
> - ファイルパス、コマンド
> - Mermaid ダイアグラムのノードラベル（実際のコード要素名）
> - Sources 行のファイル参照

各フェーズのテンプレートと具体例は [references/prompts.md](references/prompts.md) を参照。出力フォーマットの仕様は [references/output-format.md](references/output-format.md) を参照。DeepWiki の実出力分析は [references/deepwiki-analysis.md](references/deepwiki-analysis.md) を参照。

---

## Phase 1: 構造分析

対象コードベースの全体像を把握する。**ドキュメントが不十分なプライベートリポジトリでも、ソースコードから正確にアーキテクチャを理解できるようにする。**

### Step 1a: メタデータ収集

1. `scripts/collect_structure.sh <対象パス>` を実行し、ディレクトリツリー・ファイル統計・エクスポート情報を取得
2. 以下のファイルを優先的に読み取る（**存在するものだけ**。プライベートリポジトリでは無い場合が多い）：
   - `README.md` / `README`
   - `package.json` / `Cargo.toml` / `pyproject.toml` / `go.mod` 等（パッケージ定義）
   - `tsconfig.json` / `.eslintrc` / `Makefile` 等（ビルド設定）
   - `docker-compose.yml` / `Dockerfile`
   - `.github/workflows/` 下のCI設定
3. 技術スタック、フレームワーク、主要な依存関係を特定する
4. エントリーポイント（`main.ts`, `index.ts`, `app.py` 等）を特定する
5. **モノレポの場合**: 各パッケージ/ワークスペースの `package.json` 等を読み、パッケージ間の依存関係を把握する

### Step 1b: ソースコード走査

> [!IMPORTANT]
> **README や docs が不十分でも、このステップでアーキテクチャの全体像を把握する。** 「浅く広く」走査し、各モジュールの責務・依存関係・複雑さを明らかにする。ファイル全体の深読みは Phase 3a で行うため、ここでは**アウトラインと構造の把握**に集中する。

#### 1. エントリーポイントからの import グラフ構築

エントリーポイントを `view_file` で読み、import されているモジュールを**最大2階層**辿る。

- エントリーポイント → 直接 import しているモジュール → 主要な間接依存
- 各モジュールの import 文を記録し、依存の方向性を把握する
- **循環依存があれば記録する**（Wiki内で言及すべき重要情報）

#### 2. 主要ファイルのアウトライン取得

`collect_structure.sh` のファイルサイズ Top15-20 に対して `view_file_outline` を実行する。

- クラス定義・関数シグネチャ・インターフェースの一覧を把握する（**ファイル全体は読まない**）
- 判断基準：クラス5個以上 or メソッド20個以上のモジュール → **複数ページに分割を検討**
- インターフェース / 抽象クラスが多い場合 → 設計パターンの存在を示唆

#### 3. アーキテクチャパターンの検出

`grep_search` で以下のパターンキーワードを検索する：

| パターン | 検索キーワード例 |
| :--- | :--- |
| Factory | `Factory`, `create` + クラス生成 |
| Strategy | `Strategy`, インターフェース + 複数実装 |
| Observer / Event | `EventEmitter`, `on(`, `emit(`, `subscribe` |
| Middleware / Pipeline | `middleware`, `use(`, `pipe`, `pipeline` |
| Repository | `Repository`, データアクセス層 |
| DI / IoC | `inject`, `provider`, `container`, `@Injectable` |
| State Machine | `state` + `transition`, `StateMachine` |

#### 4. アーキテクチャ概要メモの生成

Step 1b の結果を以下の形式で整理する。**これが Phase 2 の構造設計の主要な入力になる。**

```text
## アーキテクチャ概要メモ

### モジュール構成
- [モジュールA]: [責務の1行説明] (主要クラス: X, Y, Z / 複雑度: 高)
- [モジュールB]: [責務の1行説明] (主要クラス: P, Q / 複雑度: 中)
  - サブモジュール: [名前] (主要クラス: R)

### 依存関係グラフ
エントリーポイント → ModuleA → ModuleB
                   → ModuleC → ModuleD
                              → ModuleB (共有依存)

### 検出された設計パターン
- Factory Pattern: ToolFactory (tools/factory.ts)
- Observer Pattern: EventBus (core/events.ts)
- Middleware: Pipeline (core/pipeline.ts)

### 複雑なモジュール（ページ分割候補）
- tools/ : クラス8個、メソッド45個 → 2-3ページに分割推奨
- core/state/ : StateMachine + 5つの State → 専用ページ推奨

### 主要機能（ユーザー視点）
- [機能A]: [何ができるか] (関連モジュール: X, Y)
- [機能B]: [何ができるか] (関連モジュール: Z)
```

---

## Phase 2: Wiki 構造設計

**Step 1a のメタデータと Step 1b のアーキテクチャ概要メモを基に**、コードベースの規模と複雑さに応じた Wiki 構造を設計する。

### 規模ガイドライン

| 規模 | ファイル数目安 | セクション数 | 総ページ数 |
| :--- | :--- | :--- | :--- |
| 小規模 | < 30 | 3-4 | 8-15 |
| 中規模 | 30-200 | 4-6 | 15-30 |
| 大規模 | > 200 | 6-8+ | **30-50** |

> **重要**: 大規模リポジトリで 15 ページ以下は少なすぎる。Core Systems だけで 5-12 ページ必要な場合がある。**ページ数を削るより増やす方向で設計する。**

### セクション構成テンプレート（6セクション基本形）

すべてのセクションを検討し、対象コードベースに該当しないものだけ省略する。**該当するのに省略してはならない。**

> [!CAUTION]
> **Getting Started** と **User Guide** は省略してはならない。CLI ツールには使い方がある。ライブラリにはインストール手順がある。これらのセクションが欠けた Wiki は不合格とする。

```
1. Overview（概要）
   1.1 Architecture Overview（アーキテクチャ概要）
   1.2 Package/Project Structure（プロジェクト構成）

2. Getting Started（はじめに）
   2.1 Installation and Setup（インストール・セットアップ）
   2.2 Authentication / Configuration（認証・設定）
   2.3 Basic Configuration（基本設定）

3. User Guide（ユーザーガイド）  ← 省略しがちだが重要
   3.x [ユーザー向け機能ごとにページ]
   例: Interactive Mode, Commands, Built-in Tools, Plugin Usage 等

4. Core Systems（コアシステム）
   4.x [内部アーキテクチャのモジュールごとにページ]
   例: Application Lifecycle, API Client, Tool System, State Management,
       Context Management, Streaming Pipeline 等
   ※ 1つのモジュールが複雑な場合は複数ページに分割する

5. Advanced Topics（応用トピック）
   5.x [拡張性、セキュリティ、可観測性等]
   例: Extension System, Security, Telemetry, Hooks, Plugin API 等

6. Development（開発）
   6.1 Development Setup（開発環境構築）
   6.2 Build System（ビルドシステム）
   6.3 Testing Infrastructure（テスト基盤）
```

### ページ定義に含める情報

各ページには以下を割り当てる：
- **id**: `"1.1"` 形式の番号
- **title**: ページタイトル
- **filePaths**: 関連するソースファイルのパス一覧（**5-15ファイル程度を目安に列挙**）
- **importance**: `high` / `medium` / `low`
- **relatedPages**: 関連ページの id 一覧
- **keyClasses**: このページで解説すべき主要なクラス・関数名（わかる範囲で）

> **この構造を JSON 形式でアウトラインとして生成し、必ずユーザーに確認を取る。確認なしに Phase 3 に進まない。**

---

## Phase 3: ページ単位の分析・生成ループ

> **核心ルール: 全ページを一括生成しない。1ページずつ「分析→生成→出力」のループを回す。**

importance の順に処理する: `high` → `medium` → `low`

### 各ページの処理手順

#### Step 3a: ソースコード分析（最重要フェーズ）

> [!IMPORTANT]
> **このフェーズの品質がページ全体の品質を決定する。** ソースコードを十分に読み、分析メモを充実させること。手を抜いてファイル名だけで推測しない。

1. ページの `filePaths` に記載された**全ファイル**を `view_file` で読む
2. **`view_file` で読んだ直後に、参照した行範囲を必ずメモする**（例: `config.ts: L1-L80 読了`）
3. 主要なクラス・関数を `view_code_item` で詳細確認する
4. **`grep_search` でクラス名・関数名の呼び出し元・参照先を必ず追跡する**（省略禁止）
5. **分析メモを以下の形式で整理する**：

```
### ファイル: [パス] (L1-L行数 読了)

■ スニペット候補（5-10個をリストアップ — ここがページ品質の核）
  - [候補1] クラス定義: [クラス名] (L開始-L終了) — [なぜこれが重要か]
  - [候補2] インターフェース: [型名] (L開始-L終了) — [なぜこれが重要か]
  - [候補3] メソッド: [メソッド名] (L開始-L終了) — [何をするか]
  - [候補4] 設定オブジェクト: [名前] (L開始-L終了) — [設定項目一覧]
  - [候補5] ファクトリ/生成ロジック: [名前] (L開始-L終了) — [設計の核心]

■ 継承・インターフェース
  - [クラス名] extends [親クラス] (L行番号)
  - [クラス名] implements [インターフェース] (L行番号)

■ 設計パターン
  - [パターン名]: [該当箇所と理由] (L行番号)
  例: Factory Pattern: ToolFactory.create() (L45-L62) — ツールの種類ごとに異なるインスタンスを生成

■ テーブル化すべきデータ
  - 列挙型: [Enum名] (L行番号) — テーブルにまとめる
  - 定数一覧: [定数グループ] (L行番号) — テーブルにまとめる
  - 優先度/階層: [対象] — テーブルにまとめる

■ データフロー
  - 入力 → 処理 → 出力

■ 依存関係（import）
  - [インポート元]: [使用クラス/関数]
```

> **スニペット候補が 5 個未満の場合は、追加のファイルを `view_file` で読む。**

> **コンテキスト制約に注意**: ページに関連するファイルだけを読む。前のページで読んだファイルの内容はコンテキストから消えている可能性がある。必要なら再度読む。

#### Step 3b: ページ生成

分析メモを基に Markdown ページを生成する。**以下の品質基準を全て満たすこと。**

> [!CAUTION]
> **生成前に分析メモのスニペット候補リストを確認する。** 5個以上のスニペット候補がリストにない場合は Step 3a に戻る。

#### Step 3c: ファイル出力

生成したページを `write_to_file` で即座にファイルに書き出す。**次のページに進む前に必ず書き出す。**

#### Step 3d: 品質検証（バリデーションループ）

生成した各ページに対してバリデーションスクリプトを実行する：

```bash
python3 scripts/validate_page.py <生成したファイル.md> --importance <high|medium|low>
```

1. **Grade B 以上 (75%+)**: 合格。次のページに進む
2. **Grade C (60-74%)**: 指摘された `❌` 項目を修正して再検証。最大2回まで修正ループ
3. **Grade D 以下 (<60%)**: 分析不足。Step 3a に戻ってソースコードを追加で読み、再生成

バリデーターが検出する主な項目：
- 語数不足（importance 別基準: high 1200語+, medium 600語+）
- Mermaid ダイアグラム不足 / **種類の多様性不足**
- **コードスニペット欠落**（最多の失敗原因, high は 5個以上必須）
- **Sources 行に行番号がない / 行番号が不正確（L1-L1000 は不可）**
- **スニペットに出典コメントがない**
- **テーブルがない（high は 1個以上必須）**
- 関連ページリンクの欠落

> **全ページ完了後にも、ディレクトリ全体に対してバリデーションを実行する:**
> ```bash
> python3 scripts/validate_page.py <wiki出力ディレクトリ> --scale large
> ```
> `--scale` に `small` / `medium` / `large` を指定する（ページ数から自動推定も可）。
> 出力には以下が含まれる：
> - 各ページの品質スコアとグレード
> - **Wiki構造チェック**（総ページ数・セクション網羅性・配分比率）
> - **🤖 AIモデル向け修正指示**（Grade C以下のページに対する具体的な改善手順）
>
> **修正指示が出た場合は、優先度順に対応する。** 構造レベルの問題（セクション欠落・ページ数不足）を先に解消し、次にページ単位の品質改善を行う。
> **Grade B 以上が 80% を占めることを目標にする。**

### ページ品質基準（必須）

すべてのページで以下を満たすこと：

1. **概要段落**: ページの目的とスコープを 2-3 文で説明
2. **ソース参照（Sources行）**: **各セクションの末尾に必ず配置**
   - 形式: `**Sources:** [ファイル名:L行番号-L行番号](file:///絶対パス/ファイル名#L開始-L終了)`
   - 1セクションあたり **1-5個** のソース参照
   - **行番号は実際に読んだ範囲を正確に記載**する（200行以内の範囲で）
   - **ページ末尾に総合 Sources 行を配置しない**（各セクション内の Sources で十分。末尾にまとめると L1-L500 のような広範囲になり、バリデーション減点の原因になる）
   - ✅ 良い例: `**Sources:** [local-executor.ts:L45-L120](file:///path/to/local-executor.ts#L45-L120), [agent-scheduler.ts:L10-L35](file:///path/to/agent-scheduler.ts#L10-L35)`
   - ❌ 悪い例: `Sources: [local-executor.ts](file:///path/to/local-executor.ts)` ← 行番号なし
   - ❌ 悪い例: `Sources: [local-executor.ts:L1-L1000]` ← 範囲が広すぎて無意味
3. **Mermaid ダイアグラム**: 各ページに最低1つ（importance: high は **2-3個、2種類以上**）
   - **実際のクラス名・関数名をノードラベルに使用する**（汎用名禁止）
   - 例: `ToolRegistry` `CoreToolScheduler` `PolicyEngine`（× `Registry` `Scheduler` `Engine`）
   - **種類を使い分ける**: `flowchart` + `sequenceDiagram` / `flowchart` + `stateDiagram` 等
4. **コードスニペット（最重要）**: **実際のソースコードからの引用のみ許可**（疑似コード禁止）
   - `view_file` で読んだソースコードの中から、**そのページのトピックを象徴する部分を抜粋**する
   - コメントで出典を示す: `// packages/core/src/tools/tools.ts:L332-L454`
   - 例: クラス定義、主要メソッドのシグネチャ、設定オブジェクト、型定義、ファクトリロジック等
   - **importance: high は 5-8 個、medium は 3-5 個が必須**
   - **スニペットが不足するページはバリデーション不合格になる**
5. **テーブル活用**: 列挙型・定数一覧・カテゴリ分類・優先度リスト等はテーブルで整理する
   - importance: high は最低1つのテーブルを含む
6. **設計パターン明示**: コード内の設計パターン（Factory, Proxy, Strategy, Observer 等）を見出しレベルで言語化
7. **関連ページへのリンク**: フッターに関連ページリストを配置

### importance 別の最低要件

| importance | 語数 | ダイアグラム | Mermaid種類 | コードスニペット | Sources 行 | テーブル |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| high | **1200語以上** | 2-3個 | **2種類以上** | **5-8個** | 全セクション | **1個以上** |
| medium | **600-1000語** | 1-2個 | 1種類以上 | **3-5個** | 全セクション | 推奨 |
| low | 300-500語 | 1個 | 1種類以上 | 1-2個 | 主要セクション | 任意 |

---

## Phase 4: 結合・整形

1. **インデックスページ** (`index.md`) を作成：
   - プロジェクト名、説明、技術スタック概要
   - 全セクション・ページへのリンク付き目次
   - 全体アーキテクチャの Mermaid ダイアグラム
2. 全ページ間の相互リンクを確認・修正
3. ページ番号の一貫性を確認

---

## Phase 5: 出力

デフォルトの出力先: `<対象プロジェクト>/docs/wiki/`

出力構造：
```
docs/wiki/
├── index.md                    # メインインデックス
├── 1-overview.md               # セクション概要ページ
├── 1.1-architecture-overview.md
├── 1.2-project-structure.md
├── 2-getting-started.md
├── 2.1-installation-and-setup.md
├── ...
├── 4-core-systems.md
├── 4.1-application-lifecycle.md
├── 4.2-api-client-architecture.md
├── ...
└── 6.3-testing-infrastructure.md
```

ファイル名規則: `<番号>-<kebab-case-title>.md`

---

## GitHubリポジトリの場合

対象がGitHubリポジトリURLの場合：
1. `git clone --depth 1 <URL> /tmp/deepwiki-<repo-name>` で shallow clone
2. 上記の Phase 1-5 を実行
3. 成果物を指定の出力先にコピー
4. クローンした一時ディレクトリを削除

---

## よくある失敗パターンと対策

| 失敗パターン | 対策 |
| :--- | :--- |
| ページ数が少なすぎる（10ページ以下） | Phase 2 で規模ガイドラインを再確認。Core Systems は 1 モジュール = 1 ページ |
| ソース参照がない / 行番号がない | Phase 3a で **view_file 直後に行番号をメモ**し、3b で Sources 行に転記 |
| **行番号が L1-L1000 のように広範囲** | **実際に参照した関数・クラスの行範囲（200行以内）を正確に記載** |
| ダイアグラムが汎用的 | 実際のクラス名・関数名をノードラベルに使う |
| **ダイアグラムが graph TD のみ** | **sequenceDiagram, stateDiagram, classDiagram も積極的に使い分ける** |
| コードが疑似コード | 実際のソースから `view_file` で抜粋する |
| **コードスニペットが 1-2 個しかない** | **Step 3a でスニペット候補を 5-10 個リスト化してから 3b に進む** |
| 全ページを一気に生成してしまう | Step 3a→3b→3c のループを厳守 |
| User Guide セクションが欠落 | Phase 2 のテンプレートで必ず検討 |
| **テーブルが全くない** | **列挙型、定数一覧、カテゴリ分類をテーブルで整理する** |
| **設計パターンに言及がない** | **Factory, Proxy, Strategy 等のパターンを見出しで明示する** |
