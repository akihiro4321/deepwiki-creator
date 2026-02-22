# microservices-wiki: Wiki構造設計・ユーザー提案フォーマット

[SKILL.md](../SKILL.md) の **Phase 3: Wiki構造設計 + ユーザー確認** において、LLMが設計するページの規模、セクション構成、ユーザーへの提案方法、および `outline.json` のスキーマに関するルール。

---

## 1. 規模ガイドライン & セクション構成

対象システムの実態に合わせてセクションとページを設計する。

| サービス数 | 推奨総ページ数 | 備考 |
| :--- | :--- | :--- |
| 3-5 サービス | 10-18ページ | 小規模 |
| 6-15 サービス | 18-30ページ | 中規模 |
| 16 サービス以上 | 30-50ページ | 大規模: サービスグループ単位でページ追加や分割を検討 |

**セクション構成テンプレート（5セクション基本形）**
※対象システムに存在しない（例えば MQ を使っていない）場合は、関連セクションを省略してよい。

```text
1. System Overview（システム概要）
   1.1 Architecture Overview（全体アーキテクチャ概要）  ← 必須・importance: high
   1.2 Service Catalog（サービス一覧・責務定義）       ← 必須・importance: high

2. Service Communication（サービス間通信）
   2.1 API Gateway & Routing（APIゲートウェイ・ルーティング）
   2.2 Synchronous Communication（同期通信: REST/gRPC）
   2.3 Asynchronous Communication（非同期通信: MQ/Event Streaming）

3. Data Architecture（データアーキテクチャ）
   3.1 Database per Service（サービス別DB設計）
   3.2 Data Flow & Consistency（データフロー・整合性）

4. Infrastructure & Deployment（インフラ・デプロイ）
   4.1 Container Orchestration（コンテナ構成）
   4.2 Service Mesh & Networking（ネットワーク構成）
   4.3 CI/CD Pipeline（デプロイパイプライン）

5. Cross-Cutting Concerns（横断的関心事）
   5.1 Authentication & Authorization（認証・認可）
   5.2 Observability（可観測性: ログ・メトリクス・トレーシング）
   5.3 Error Handling & Resilience（エラー処理・耐障害性）
```

---

## 2. ユーザー確認のための提示フォーマット（Markdown表形式）

提案時はJSON構造をそのまま出力するのではなく、必ず人間が読みやすいMarkdownの表形式でユーザーに提示し、「停止（承認待ち）」を行うこと。

```markdown
以下の構造でアーキテクチャWikiを生成します。よろしければ「OK」とお伝えください。

## 提案するWiki構造（全15ページ）

### 1. System Overview
| # | ページタイトル | importance | 主な参照ソース |
|---|---|---|---|
| 1.1 | Architecture Overview | high | `docker-compose.yml`, `docs/architecture` |
| 1.2 | Service Catalog | high | `k8s/deployments/*.yaml` |

### 2. Service Communication
| # | ページタイトル | importance | 主な参照ソース |
|---|---|---|---|
| 2.1 | API Gateway & Routing | high | `nginx/default.conf` |
| 2.2 | Synchronous Communication | medium | `openapi.yaml`, 各サービス環境変数 |

（...全セクション続く）

**修正希望やページの追加・削除、重視してほしい観点があればお知らせください。**
```

---

## 3. `outline.json` スキーマ仕様

ユーザー承認後に指定ディレクトリに出力する進捗管理・構成情報のJSONフォーマット。
`status` は初期値 `"pending"` で生成し、検証通過後に更新される。各ページには `inputSources`, `keyDiagrams` など生成時の指示を含めること。

```json
{
  "title": "EC Platform - Microservices Architecture Wiki",
  "description": "ECプラットフォームのマイクロサービス全体アーキテクチャドキュメント",
  "sections": [
    {
      "id": "1",
      "title": "System Overview",
      "pages": [
        {
          "id": "1.1",
          "title": "Architecture Overview",
          "inputSources": [
            "docker-compose.yml",
            "k8s/deployments/",
            "README.md"
          ],
          "importance": "high",
          "relatedPages": ["1.2", "2.1"],
          "keyDiagrams": ["全体構成 flowchart TD", "リクエストフロー sequenceDiagram"],
          "status": "pending"
        }
      ]
    }
  ]
}
```
