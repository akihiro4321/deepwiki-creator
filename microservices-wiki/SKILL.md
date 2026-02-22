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
- **Phase 4 用**: [references/03-generation-prompts.md](references/03-generation-prompts.md)
- **Mermaid記述時（必須）**: [references/04-mermaid-rules.md](references/04-mermaid-rules.md)
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
> 構造設計を行った後、**絶対に次の段階 (Phase 4 ページ作成) に自動で進んではいけません。**
> ユーザーに対して「この要件（Markdown表形式）でページ生成を開始してよいか」の**承認を求めて一旦停止する**こと。（JSONをそのままユーザーに見せないこと）
> 承認を得てから、指定のスキーマで `outline.json` を出力して進行する。

---

## Phase 4: ページ生成ループ

> **核心ルール: 全ページを一括生成しない。1ページずつ「分析→生成→出力→検証」のループを回す。**

importance の順に処理: `high` → `medium` → `low`

### 各ページの処理手順

#### Step 4a: ソース再確認（ページ固有の分析）

各ページの `inputSources` に記載されたファイルを再確認する。

1. Phase 1 で読んだ情報で足りなければ、該当設定ファイルを再度読む
2. **スニペット候補を 5-10 個リストアップ** してから生成に進む（インフラ定義やOpenAPIのパスなど）
> **フォーマット要件**: 分析メモは **[references/03-generation-prompts.md](references/03-generation-prompts.md)** の「1. ソース固有分析メモの出力フォーマット」に従うこと。

#### Step 4b: ページ生成

分析メモを基に Markdown ページを生成する。

> **生成時の品質・文字数要件と構成**:
> 生成時は **[references/03-generation-prompts.md](references/03-generation-prompts.md)** に従い、文字数水準、スニペット数、および疑似コード禁止のルールを守ること。
> 出力時は、必ず「セルフレビューリスト」でルールを満たせているか確認する。

> [!CAUTION]
> **【Mermaid パースエラー防止: 絶対厳守】**
> Mermaidダイアグラムを書く際は、必ず **[references/04-mermaid-rules.md](references/04-mermaid-rules.md)** を遵守すること。ここでの規約（クォート漏れ、ハイフン使用禁止など）を破るとシステムで利用できないWikiになる。

#### Step 4c: ファイル出力

生成したページを即座にファイルに書き出す。

#### Step 4d: バリデーション

```bash
python3 scripts/validate_arch_page.py <生成したファイル.md> --importance <high|medium|low>
```

- **Grade B 以上 (75%+)**: 合格。次のページへ進む。
- **Grade C (60-74%)**: 指摘項目を修正して再検証。最大2回まで修正ループ。
- **Grade D 以下 (<60%)**: Step 4a に戻り、ソース再確認・再生成。

> [!CAUTION]
> バリデーションを後回しにして複数ページを一気に生成することを**絶対に行ってはいけません**。

**全ページ完了後のディレクトリ全体検証**:

```bash
python3 scripts/validate_arch_page.py <arch-wiki出力ディレクトリ> --scale <small|medium|large>
```

---

## Phase 5: 出力

デフォルトの出力先: `<ルートパス>/docs/arch-wiki/`

```
docs/arch-wiki/
├── index.md                          # メインインデックス
├── 1-system-overview.md
├── 1.1-architecture-overview.md      # ← 最重要ページ
├── 1.2-service-catalog.md
├── ... （以下生成ファイル）
```

ファイル名規則: `<番号>-<kebab-case-title>.md`

**index.md に含める必須内容**:
1. システム名・概要（2-3段落）
2. 技術スタック全体テーブル
3. 全体アーキテクチャの Mermaid ダイアグラム（最上位俯瞰図）
4. 全セクション・ページへのリンク付き目次

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
