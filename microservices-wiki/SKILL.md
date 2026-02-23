---
name: microservices-wiki
description: マイクロサービスアーキテクチャ全体の俯瞰的なWikiドキュメントを自動生成するスキル。インフラ定義ファイル（docker-compose, k8s, Terraform）・API仕様（OpenAPI, proto）・DB構成・CI/CDを横断的に分析し、サービス間の連携・データフロー・インフラ構成を包括的にドキュメント化する。ユーザーが「マイクロサービスのアーキテクチャをドキュメント化して」「サービス全体の構成を把握したい」と依頼した場合に使用する。
---

# microservices-wiki - マイクロサービス全体アーキテクチャ Wiki 生成スキル

インフラ定義・API仕様・DB構成を分析し、マイクロサービス全体の俯瞰的なWikiドキュメントを生成する。**個別サービスの内部実装ではなく、サービス間の連携・データフロー・インフラ構成に特化する。**

> **品質目標**: このWikiを読むだけで、新規参画者がシステム全体の構成・サービス間の通信経路・データの流れ・デプロイ構成を把握できること。また、障害発生時の影響範囲特定・新規サービス追加時の設計判断に利用できること。

> **スコープの明確化**:
> - ✅ このスキルが扱うもの: サービス間の依存関係・通信プロトコル・データストア構成・インフラ・横断的関心事
> - ❌ このスキルが扱わないもの: 各サービスの内部実装・ビジネスロジックの詳細（それは deepwiki スキルの領域）

> **言語ルール**: ページタイトルは**英語**。本文は**日本語**。コード要素・ファイルパス・コマンドは英語のまま。

**LLMへの指示**: 本ファイル (`SKILL.md`) は**実行手順 (アルゴリズム)** のみを示す。各ステップで要求される「出力フォーマット」「品質基準」などの詳細は、必ず以下のフェーズ対応リファレンスを参照しながら作業を進めること。

- **Phase 1~2 用**: [references/01-analysis-prompts.md](references/01-analysis-prompts.md)
- **Phase 3 用**: [references/02-structure-prompts.md](references/02-structure-prompts.md)
- **Phase 4 用**: [references/03-generation-prompts.md](references/03-generation-prompts.md)（手動生成時のみ参照）
- **Mermaid記述時（必須）**: [references/04-mermaid-rules.md](references/04-mermaid-rules.md)

---

## Phase 0: 開始前の確認（必須）

Phase 1 に進む前に、以下の2つのパスを確定する。**ユーザーのメッセージに含まれていない場合は必ず問い合わせること。** 確定するまで Phase 1 に進んではいけない。

| 項目 | 説明 | 例 |
| :--- | :--- | :--- |
| **ターゲットディレクトリ** | 解析対象のコードベース/インフラのルートパス (`$TARGET_DIR`) | `/Users/username/projects/my-platform` |
| **出力ディレクトリ** | Wiki ファイルの出力先パス (`$OUTPUT_DIR`) | デフォルト: `<ターゲット>/docs/arch-wiki` |

---

## Phase 1: インプット収集

**コンテキスト制御の原則**: ソースコード全体を読まない。インフラ定義・API仕様・DB定義・既存ドキュメントに限定することで、コンテキストウィンドウ内に収める。

### Step 1a: インフラ定義ファイルの収集

まずスクリプトを実行して対象の全体像を把握する：

```bash
bash scripts/collect_infra.sh <ルートパス>
```

**スクリプトが収集する情報**:
- サービス一覧（docker-compose の `services:` / k8s の `Deployment` リソース）
- 各サービスのポートマッピング・環境変数（他サービスのURL等）
- ネットワーク構成（docker network / k8s namespace）
- インフラ関連ファイルの一覧（terraform, helm chart 等）

**スクリプト実行後、以下を手動で読む（存在するものだけ）**:

| 優先度 | ファイル種別 | 対象パターン |
| :--- | :--- | :--- |
| 最高 | コンテナ構成 | `docker-compose*.yml`, `docker-compose*.yaml` |
| 最高 | k8s構成 | `k8s/**/*.yaml`, `kubernetes/**/*.yaml`, `helm/**/values.yaml` |
| 高 | API Gateway | `api-gateway/**/*`, `nginx/**/*.conf`, `traefik/**/*`, `kong/**/*` |
| 高 | インフラ定義 | `terraform/**/*.tf`（`main.tf`, `variables.tf` 優先） |
| 中 | CI/CD | `.github/workflows/*.yml`, `.gitlab-ci.yml`, `Jenkinsfile` |
| 中 | サービスメッシュ | `istio/**/*`, `linkerd/**/*` |

> **注意**: ファイルが多い場合は全て読む必要はない。サービス間の依存関係把握に必要な情報を優先する。

### Step 1b: API仕様の収集

サービス間のI/Fを把握する最重要インプット。

1. OpenAPI/Swagger 仕様を検索して読む：
   ```
   openapi*.yaml, openapi*.json, swagger*.yaml, swagger*.json
   api-docs/*.yaml, docs/api/*.yaml
   ```

2. gRPC を利用している場合は proto ファイルを読む：
   ```
   **/*.proto, proto/**/*.proto
   ```

3. **API仕様が存在しない場合**: 各サービスのルーターファイルを限定的に読む
   - Express: `routes/*.ts`, `src/routes/*.ts`
   - FastAPI/Flask: `routers/*.py`, `api/*.py`
   - Spring: `*Controller.java`
   - 目的はエンドポイントの一覧把握のみ。実装詳細は読まない。

### Step 1c: DB・データストア構成の把握

| 対象 | 優先して読むファイル |
| :--- | :--- |
| RDB スキーマ | `migrations/*.sql`, `schema.sql`, `**/schema.prisma`, `db/migrate/*.rb` |
| NoSQL 構成 | `docker-compose.yml` の MongoDB/DynamoDB 設定 |
| キャッシュ | Redis/Memcached の設定ファイル |
| メッセージキュー | Kafka topic 定義, `**/kafka/**/*.yaml`, RabbitMQ の exchange 定義 |

> **目的**: どのサービスがどのDBを使うか、DBが共有されているかを把握する。スキーマ全体の詳細は不要。

### Step 1d: 既存ドキュメントの収集

以下が存在する場合は読む（コンテキストの補完に使う）：

```
README.md（ルート）, ARCHITECTURE.md, docs/architecture/*, ADR（Architecture Decision Records）
各サービスの docs/wiki/index.md（deepwikiで生成済みの場合）
```

### Step 1e: アーキテクチャ概要メモの整理

Step 1a〜1d の結果を収集したら詳細なメモに整理する。
> **要求フォーマット**: 必ず **[references/01-analysis-prompts.md](references/01-analysis-prompts.md)** の形式に従って「サービス一覧」「通信の記録方式」「データストア・インフラ分析」を書き出すこと。これが Phase 2・3 の入力になる。

---

## Phase 2: アーキテクチャ分析

Phase 1 のメモを基に、以下の分析を深める。

### サービス依存関係グラフの精緻化

1. **環境変数からの依存推定**: `*_URL`, `*_HOST`, `*_ENDPOINT` 等の環境変数を確認し、サービス間のURL参照を特定する
2. **API Gatewayルーティングの確認**: ゲートウェイ設定から外部→内部のルーティングを整理
3. **非同期依存の特定**: Kafka/RabbitMQ のtopic/exchange名を検索し、Publisher/Subscriber の関係を明確化
4. **DBの共有・専有判定**: 同一DB接続文字列・ホスト名が複数サービスで共有されていないか確認

### アーキテクチャパターンの検出

| パターン | 検出シグナル |
| :--- | :--- |
| API Gateway | nginx/kong/traefik の設定, `api-gateway` ディレクトリ |
| BFF (Backend for Frontend) | `web-bff`, `mobile-bff` 等のサービス名 |
| Saga パターン | `saga`, `choreography`, `orchestration` キーワード |
| CQRS | `command`, `query` の分離、読み書きDBの分離 |
| Event Sourcing | `event-store`, `EventStore` キーワード |
| Circuit Breaker | `hystrix`, `resilience4j`, `retry` 設定 |
| Service Mesh | Istio/Linkerd 設定ファイルの存在 |

---

## Phase 3: Wiki構造設計 + ユーザー確認

Phase 1-2 の分析を基に、全体アーキテクチャ Wiki の構造を設計する。

### 構造設計のガイドライン

> **構成・出力形式**: セクション・ページの分割数や、提案時・JSON出力時のフォーマットは、必ず **[references/02-structure-prompts.md](references/02-structure-prompts.md)** に従うこと。

> [!CAUTION]
> **【超重要: ユーザー確認の必須化】**
> 構造設計を行った後、**絶対に次の段階 (Phase 4 ページ生成) に自動で進んではいけません。**
> ユーザーに対して「この要件（Markdown表形式）でページ生成を開始してよいか」の**承認を求めて一旦停止する**こと。（JSONをそのままユーザーに見せないこと）
> 承認を得てから、指定のスキーマで `outline.json` を出力して進行する。

### outline.json の出力

ユーザーから承認を得たら、Wiki出力ディレクトリ (`$OUTPUT_DIR/outline.json`) に進捗管理用のアウトラインをJSON形式で書き出す。

> [!IMPORTANT]
> **以下のスキーマを必ず厳守すること。** `generate_pages.py` はこのフィールド構造を前提として動作するため、フィールド名を変えたり省略したりするとスクリプトが正常に動作しない。

```json
{
  "title": "EC Platform - Microservices Architecture Wiki",
  "description": "ECプラットフォームのマイクロサービス全体アーキテクチャドキュメント",
  "generatedAt": "2026-02-22T12:00:00+09:00",
  "outputDir": "/path/to/docs/arch-wiki",
  "targetDir": "/path/to/target/project",
  "remoteBaseUrl": "https://github.com/org/repo",
  "pages": [
    {
      "id": "1.1",
      "title": "Architecture Overview",
      "description": "システム全体のアーキテクチャ概要。主要ダイアグラム: 全体構成 flowchart TD、リクエストフロー sequenceDiagram",
      "filename": "1.1-architecture-overview.md",
      "filePaths": [
        "docker-compose.yml",
        "k8s/deployments/",
        "README.md"
      ],
      "importance": "high",
      "relatedPages": ["1.2", "2.1"],
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
| `pages[].description` | string | ページの説明。keyDiagrams（欲しいMermaid種類）もここに含める |
| `pages[].filename` | string | 出力ファイル名（例: `"1.1-architecture-overview.md"`） |
| `pages[].filePaths` | string[] | 参照ファイルパスのリスト（5〜15ファイル推奨、相対パスはtargetDir基準） |
| `pages[].importance` | string | `"high"` / `"medium"` / `"low"` のいずれか |
| `pages[].status` | string | 初期値は必ず `"pending"`（スクリプトが `"done"` に更新する） |
| `remoteBaseUrl` | string | （省略可）リモートリポジトリのベースURL。`fix_sources.py` が `git remote` から自動取得できない場合のフォールバックとして使用 |

---

## Phase 4: ページ単位の生成ループ（スクリプト委譲）

> [!CAUTION]
> **核心ルール: 親エージェント自身でインフラ定義ファイルを読み込んだり、各Markdownページを直接執筆してはいけない。**
> ページ生成と品質検証（自己修正）のループは、必ず専用のオーケストレーションスクリプトに委譲すること。

### Step 4a: ページ生成スクリプトの実行

`outline.json` が作成・承認されたら、以下のコマンドを実行してページ生成プロセスを開始する。

```bash
python3 scripts/generate_pages.py $OUTPUT_DIR/outline.json
```

このスクリプトは以下の処理を自動で行う：
* 未生成のページ情報を `outline.json` から取得する
* 複数のページを並列で `gemini` CLI コマンドを非同期発行する
* 生成完了後、`validate_arch_page.py` を呼び出して品質検証を実施する
* 検証で不十分な場合（Grade C以下）、エラー出力と修正指示を用いて再生成（リトライ）を自動で最大2回実行する
* 生成が成功したページのステータスを `outline.json` で `"done"` に更新する

**親エージェント（あなた）は、このスクリプトの実行が完了するのを待つこと。**

### Step 4b: 実行結果の確認とリトライ（必要な場合のみ）

スクリプトの実行が終了したら、その標準出力を確認する。
もし `$OUTPUT_DIR/outline.json` 内に、ステータスが `"error"` となっているページが残っている場合は、ユーザーにその旨を報告し、どのように対処するか指示を仰ぐ。すべて `"done"` になっていれば Step 4c に進む。

### Step 4c: Mermaidルール一括チェック＆修正

全ページの生成が完了したら、以下のコマンドを実行してMermaidダイアグラムのルール違反を一括検出・修正する。

```bash
python3 scripts/fix_mermaid.py $OUTPUT_DIR/outline.json
```

このスクリプトは以下の処理を自動で行う：
- `outline.json` の全 `done` ページのMarkdownファイルを走査する
- Mermaidブロックを抽出し、ルール違反（LR使用・ハイフンID・括弧クォート漏れ・HTMLタグ等）を静的チェックする
- 違反があればGemini CLIで**違反箇所のみ**を修正する
- 修正後に再チェックして確認する

### Step 4d: Sources リンク形式の確認と変換（⚠️ ユーザーへの確認が必要）

> [!CAUTION]
> **実行前に必ずユーザーへ確認すること。**

ユーザーに以下の選択肢を提示する：

```
Sources行のリンクをどの形式にしますか？

1. GitHub / GitLab URL（推奨）
   チームで共有できる。ブラウザから行番号付きで開ける。
   例: https://github.com/org/repo/blob/main/docker-compose.yml#L10-L45

2. vscode:// URL
   ローカルの VSCode から直接ジャンプできる。
   例: vscode://file//absolute/path/to/docker-compose.yml:10

3. 変換しない（file:/// のまま）
```

ユーザーの回答に応じて以下を実行する：

**① GitHub/GitLab URL を選んだ場合**

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

このステップをスキップして Phase 5 に進む。

---

## Phase 5: 出力

デフォルトの出力先: `<ルートパス>/docs/arch-wiki/`

```
docs/arch-wiki/
├── index.md                          # メインインデックス（自動生成）
├── 1.1-architecture-overview.md      # ← 最重要ページ
├── 1.2-service-catalog.md
├── ... （以下生成ファイル）
```

ファイル名規則: `<番号>-<kebab-case-title>.md`

### インデックスページ (`index.md`) の生成

以下のスクリプトを実行して、`outline.json` からWiki全体の目次ページを自動生成する。

```bash
python3 scripts/create_index.py $OUTPUT_DIR/outline.json
```

### 全体バリデーション（必要に応じて）

```bash
python3 scripts/validate_arch_page.py $OUTPUT_DIR --scale <small|medium|large>
```

---

## GitHubリポジトリ / 複数リポジトリの場合

### 単一 GitHub リポジトリ（モノレポ）
```bash
git clone --depth 1 <URL> /tmp/arch-wiki-<repo-name>
# 上記の Phase 1-5 を実行
```

### 複数リポジトリ（分散）
```bash
# 各リポジトリをサービス名ディレクトリにクローン
for svc in user-service order-service notification-service; do
  git clone --depth 1 <org-url>/$svc /tmp/arch-wiki/$svc
done
# collect_infra.sh を各リポジトリに対して実行し、出力を結合して分析
bash scripts/collect_infra.sh /tmp/arch-wiki/user-service > /tmp/infra-user.txt
bash scripts/collect_infra.sh /tmp/arch-wiki/order-service > /tmp/infra-order.txt
# ...各ファイルを順次読んで Phase 2 のアーキテクチャ分析に進む
```
