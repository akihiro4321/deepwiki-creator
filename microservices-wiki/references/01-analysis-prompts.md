# microservices-wiki: アーキテクチャ概要・分析メモフォーマット

[SKILL.md](../SKILL.md) の **Phase 1: インプット収集** および **Phase 2: アーキテクチャ分析** において、LLMがインフラおよびAPI仕様を読み解き、サービス全体の概要を整理するためのフォーマット。

---

## 1. サービス一覧テーブルの作成形式

収集した情報を元に、各サービスのプロファイルを推定しテーブル化すること。

```text
### 検出されたサービス一覧

| サービス名 | 技術スタック | ポート | データストア | 役割（推定） |
| :--- | :--- | :--- | :--- | :--- |
| user-service | Node.js + Express | 3001 | PostgreSQL (専有) | ユーザー認証・プロファイル管理 |
| order-service | Python + FastAPI | 8000 | MySQL (専有) | 注文ライフサイクル管理 |
| inventory-service | Go | 8001 | PostgreSQL (専有) | 在庫・商品管理 |
| notification-service | Node.js | 8002 | Redis (キャッシュ専有) | メール・Push通知送信 |
| api-gateway | nginx / Kong | 80, 443 | - | 外部ルーティング・認証 |
```

---

## 2. サービス間通信の記録形式

環境変数やAPI仕様（OpenAPI/proto/ルーター）から、サービスがどのように連携しているかを特定し記録すること。

```text
### サービス間通信

#### 同期通信 (REST/gRPC)
- order-service → user-service: GET /users/{id}
  (根拠: docker-compose.yml の USER_SERVICE_URL 環境変数)
- order-service → inventory-service: POST /inventory/reserve
  (根拠: openapi.yaml の paths セクション)

#### 非同期通信 (Kafka / RabbitMQ)
- order-service → [kafka:order-created] → notification-service
  (根拠: docker-compose.yml の KAFKA_TOPIC_ORDER_CREATED)
- order-service → [kafka:order-created] → inventory-service
  (同一 topic に複数 subscriber)

#### API Gateway ルーティング
- /api/users/* → user-service:3001
- /api/orders/* → order-service:8000
- /api/inventory/* → inventory-service:8001
  (根拠: nginx/default.conf のプロキシ設定)
```

---

## 3. データストア・インフラ分析の記録形式

どのサービスがどのDBを使用しているか、共有DBが存在するかなどの依存関係を明確にすること。

```text
### データストア構成

#### 専有データストア（推奨パターン）
- user-service: PostgreSQL (users, sessions テーブル)
- order-service: MySQL (orders, order_items テーブル)
- inventory-service: PostgreSQL (products, stock テーブル)

#### 共有・注意が必要な構成
- ⚠️ user-service と order-service が同一 Redis インスタンスを共有
  (docker-compose: REDIS_HOST が両サービスで一致)
  → セッションキャッシュ目的のみ。スキーマ競合リスク低

#### メッセージキュー
- Kafka: order-created, payment-completed, stock-updated (3 topics 検出)
  (全 topic は docker-compose の kafka サービス定義を参照)
```
