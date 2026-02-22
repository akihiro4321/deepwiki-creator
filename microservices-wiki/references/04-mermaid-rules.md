# microservices-wiki: Mermaidダイアグラム記述の厳密なルール

[SKILL.md](../SKILL.md) 等でMermaidを書く際は、MarkdownパーサーおよびMermaidレンダリングエンジンでの**パースエラー・描画不能を絶対に防ぐため、以下のルールを完全に遵守すること。**

---

### 1. ダイアグラム種類の使い分け

| 目的 | ダイアグラム種類 | 使用場面 |
| :--- | :--- | :--- |
| 全体構成 | `graph TD` / `flowchart TD` | サービス依存関係、コンポーネント構成 |
| 時系列処理 | `sequenceDiagram` | サービス間のAPI呼び出し、リクエストフロー |
| DB構成 | `erDiagram` | データストアの関係、テーブル構成 |
| 状態遷移 | `stateDiagram-v2` | デプロイ状態、サービスライフサイクル |

---

### 2. 縦方向 (Vertical) レイアウトの強制

- フローダイアグラムの指定には必ず `graph TD` (top-down) または `flowchart TD` を使用すること。
- **絶対に `graph LR` (left-right) や `flowchart LR` を使用しないこと。**
- ノード内のテキストは最大でも3-4単語に収め、横幅が長くなりすぎないようにすること。

---

### 3. シーケンス図 (Sequence Diagrams) の厳格なルール

- 先頭行に必ず単独で `sequenceDiagram` を配置すること。
- その直後に、使用する全参加者を `participant` キーワードで定義すること（例: `participant GW as api-gateway`）。
- 以下のアロー構文から意図に合ったものを正確に使用すること:
  - `->>` : 実線・矢じりあり (**リクエストや呼び出しに最も使用**)
  - `-->>` : 破線・矢じりあり (**レスポンスや戻り値に最も使用**)
  - `-x` : 実線・末尾がX (エラー・失敗)
  - `--x` : 破線・末尾がX (エラーレスポンス)
  - `-)` : 実線・オープンアロー (非同期、投げっぱなし)
- アクティベーションボックスには必ず `+`/`-` プレフィックスを使用すること（例: `A->>+B: Start`, `B-->>-A: End`）。
- メッセージへのラベル付与にはコロン（`:`）を用いること。**絶対にフローチャート風の `A--|label|-->B` 表記を使用しないこと。**

---

### 4. サービス名の命名規則と通信プロトコルの明記

```text
✅ 良い例（実際のサービス名）:
  user_service["user-service"], order_service["order-service"],
  api_gw["api-gateway"], kafka["Kafka"], pg_user["postgres-user"]

❌ 悪い例（汎用的な名前 / IDにハイフンが含まれている）:
  ServiceA, Backend, Database, Message Queue
  order-service["order-service"]  ← ❌ ノードIDにハイフンはNG
```

```text
✅ 通信プロトコルの良い例:
  user_svc["user-service"] -->|"REST GET /users/{id}"| pg_user["postgres-user"]
  order_svc["order-service"] -->|"Kafka: order-created"| notify_svc["notification-service"]

❌ 悪い例（プロトコル不明）:
  UserService --> Database
  OrderService --> NotificationService
```

---

### 5. 【🔥 致命的エラー防止: 全般的な構文ルール（絶対厳守）】

> [!CAUTION]
> **以下のルールに違反すると、生成されたWikiの図がすべて表示されなくなる致命的なエラーを引き起こす。**

- ノードラベルに `()`、`[]`、`{}` などの括弧や記号類が含まれる場合は、**例外なく必ず `["ラベル"]` のようにダブルクォーテーションで囲む**こと。クォート忘れは致命的なパースエラーを引き起こします。
- **【頻出エラー1】** `D[Data Pipeline (api/data_pipeline.py)]` のように `[]` の内側に `()` を含むとパースエラーで図が崩壊します。**必ず `D["Data Pipeline (api.py)"]` とクォートで囲むか、括弧を使用しないでください。**
- **【頻出エラー2】** サービス名にハイフンを含む場合もクォートが必要です。例: `order-service["order-service"]`（繰り返しになりますがノードIDにもハイフン不可）。
- HTMLタグは使用不可（`<` や `>` などの記号もパースエラーの原因）。
- ノード ID にハイフンを含めない（アンダースコアを使用すること。例: `order-service` ❌ → `order_service` ⭕️）。
- サンプルの汎用名ではなく、**実際のサービス名・コンポーネント名**をノードラベルに用いること。
