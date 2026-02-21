# DeepWiki 実出力分析 - ベストプラクティス集

DeepWiki (https://deepwiki.com) が生成するドキュメントの品質を分析し、本スキルが目指すべき基準を定義する。

---

## DeepWiki の構成パターン

大規模リポジトリ（1000+ ファイル）における DeepWiki の典型的な構成：

```
1. Overview（2-3ページ）
   ├── Architecture Overview
   └── Package Structure

2. Getting Started（3-4ページ）
   ├── Installation and Setup
   ├── Authentication
   └── Basic Configuration

3. User Guide（8-12ページ）        ← 最もページ数が多いセクション
   ├── Interactive Mode and Basic Usage
   ├── Slash Commands
   ├── At Commands and File References
   ├── Built-in Tools
   ├── Shell Mode and Command Execution
   ├── Sandbox Environments
   ├── MCP Server Integration
   ├── Non-Interactive Mode
   ├── Session Management
   ├── IDE Integration
   └── Agent Skills

4. Core Systems（8-12ページ）      ← 技術的に最も深いセクション
   ├── Application Lifecycle and Initialization
   ├── Configuration System
   ├── Settings Management
   ├── API Client Architecture
   ├── Streaming and Turn Processing
   ├── Tool System Architecture
   ├── Tool Execution Pipeline
   ├── UI State Management
   ├── Input Handling and Text Buffer
   ├── Command Processing System
   ├── Chat Compression and Context Management
   └── System Prompt Generation

5. Advanced Topics（5-8ページ）
   ├── Extension System
   ├── Extension Configuration and Variables
   ├── MCP Server Management
   ├── Telemetry and Observability
   ├── Security and Approval System
   ├── Model Configuration and Routing
   ├── Hooks System
   └── A2A Server and Agent Protocol

6. Development（2-3ページ）
   ├── Development Setup
   ├── Build System and Bundling
   └── Testing Infrastructure
```

**合計: 約 30-40 ページ（セクション概要ページ含む）**

---

## DeepWiki のページ品質パターン

### パターン1: ソース参照の密度

DeepWiki は**各セクション末尾**にソース参照を配置する。1ページあたり **5-15 個**のソース参照が一般的。

```markdown
## Tool Discovery and Registration

Built-in tools are registered during Config class initialization...

Sources: [packages/core/src/config/config.ts:L1048-L1211](...) 
[packages/core/src/tools/tool-registry.ts](...) 
[packages/core/src/tools/mcp-client-manager.ts](...)
```

**ポイント**: 行番号をつけたソース参照がセクションごとに 1-5 個ある。ページ全体では 5-15 個。

### パターン2: 実名を使ったダイアグラム

DeepWiki のダイアグラムは**汎用名ではなく実際のコード要素名**を使う。

```
✅ 良い例（DeepWiki スタイル）:
  GeminiClient → BaseLlmClient
  ToolRegistry → CoreToolScheduler
  PolicyEngine → MessageBus
  ExtensionLoader → McpClientManager

❌ 悪い例（汎用的すぎる）:
  Client → Base Client
  Registry → Scheduler
  Engine → Bus
  Loader → Manager
```

### パターン3: 設計パターンの明示

DeepWiki は内部アーキテクチャの設計パターンを具体的に説明する。

```markdown
### DeclarativeTool Pattern
The system uses a two-phase pattern:
1. Tool Definition (DeclarativeTool): Defines metadata and validation logic
2. Tool Invocation (ToolInvocation): Encapsulates a validated, ready-to-execute call
```

**ポイント**: パターン名を見出しにし、そのパターンの構成要素を具体的なクラス名で説明。

### パターン4: 優先度・階層の明示

設定や処理の優先度がある場合、DeepWiki は明確にリスト化する。

```markdown
Policy Enforcement:
The PolicyEngine evaluates rules from multiple sources with this priority (highest to lowest):
1. Admin controls from CCPA (remote overrides)
2. TOML policy files (plan.toml, read-only.toml)
3. ApprovalMode setting (DEFAULT, PLAN, YOLO, AUTO_EDIT)
4. Tool-specific allow/deny lists in settings
```

### パターン5: コード要素の分類表

DeepWiki は列挙型やカテゴリを表形式で整理する。

```markdown
### Tool Categories (Kind Enum)
| Kind | Tools | Purpose |
| :--- | :--- | :--- |
| Read | ファイル閲覧・ディレクトリ検索ツール等 | ファイル読み取り |
| Edit | ファイル書き込みツール等 | ファイル変更 |
| Execute | コマンド実行機能 | コマンド実行 |
| Search | コード検索ツール等 | コード検索 |
| Web | Web検索ツール等 | Web アクセス |
```

---

## 本スキルとの差を埋める行動指針

### 1. ページ数の問題

**原因**: 1つのページに複数モジュールを詰め込む傾向
**対策**:
- Core Systems の各主要クラス/モジュールを独立ページにする
- 「Tool System」→「Tool System Architecture」＋「Tool Execution Pipeline」に分割
- User Guide は**ユーザーが使う機能ごと**にページを分ける

### 2. ソース参照の問題

**原因**: 初見のファイル閲覧時に読んだ行番号をメモに残さず、ページ生成時に参照を書けない
**対策**:
- Phase 3a の分析時に行番号を必ずメモする
- ページ生成時にメモからSources行に転記する
- **セクションごとに** Sources 行を書く（ページ末尾だけでは不十分）

### 3. 技術的深度の問題

**原因**: ファイル名とディレクトリ構造だけで推測して書いている
**対策**:
- 内容確認機能等でクラス・関数の実装を確認する
- 「コード検索ツール」で呼び出し元を追跡する
- 設計パターンを特定し、名前を付けて説明する

### 4. ダイアグラムの問題

**原因**: 実際のコードを読まずに概念的なダイアグラムを描いている
**対策**:
- ダイアグラムのノードラベルは、実装を確認した実際のクラス名・関数名を使う
- 矢印のラベルにメソッド名やイベント名を含める
