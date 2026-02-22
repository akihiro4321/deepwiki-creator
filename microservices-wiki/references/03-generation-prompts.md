# microservices-wiki: ページ生成と品質基準フォーマット

[SKILL.md](../SKILL.md) の **Phase 4: ページ生成ループ** において、LLMが各Markdownページを生成する際の品質要件およびフォーマット、セルフレビューチェックリスト。

> **Mermaidダイアグラムの記述基準については、致命的なパースエラーを防ぐため必ず [04-mermaid-rules.md](04-mermaid-rules.md) を参照すること。**

---

## 1. ソース固有分析メモの出力フォーマット
ページ生成前に、`inputSources` に記載されたファイルを読み込み、以下のように整理してからMarkdownページ本文を書き始める。

```text
### ページ [1.1 Architecture Overview] 向けの分析メモ

■ スニペット候補（実際のファイル引用）
  1. docker-compose.yml (L12-L35): user-service の環境変数（他サービスURL定義）
  2. docker-compose.yml (L100-L130): kafka の topic と依存関係設定
  ...

■ 検出されたサービスとデータストア
  user-service, order-service, inventory-service, postgres-user, redis, kafka

■ 注目すべき特徴（ページに盛り込むべき事項）
  - Database per Service が基本だが、Redis は一部共有されている
```

---

## 2. importance 別の最低要件（品質基準マトリクス）

| importance | 語数 | ダイアグラム | Mermaid種類 | コードスニペット | Sources 行 | テーブル |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| high | **1200語以上** | 2-3個 | **2種類以上** | **5-8個必須** | 全セクション | **1個以上** |
| medium | **600-1000語**| 1-2個 | 1種類以上 | **3-5個必須** | 全セクション | 推奨 |
| low | 300-500語 | 1個 | 1種類以上 | 1-2個 | 主要セクション | 任意 |

---

## 3. ページ生成の模範構成テンプレート

```markdown
# Architecture Overview

[概要: このページで対象アーキテクチャシステム、またはサービスの通信フローについて等、目的とスコープを2-3文程度で明確に説明する。個別の内部実装は書かない。]

## システム概要

[サービス数・技術スタック・アーキテクチャパターンの概説]

| サービス | 技術 | 役割 |
|:---|:---|:---|
| `user-service` | Node.js + Express | ユーザー認証・プロファイル |
| `order-service` | Python + FastAPI | 注文ライフサイクル |

` ` `mermaid
flowchart TD
    Client["Client (Web/Mobile)"] --> GW["api_gateway (nginx)"]
    GW --> US["user_service :3001"]
    US --> PG1["postgres_user"]
` ` `

**Sources:** [docker-compose.yml:L1-L80](file:///path/docker-compose.yml#L1-L80)

## サービス間通信フロー

[機能やリクエストごとの通信フローの説明]

` ` `mermaid
sequenceDiagram
    participant Client
    participant GW as api_gateway
    participant OS as order_service

    Client->>GW: POST /api/orders
    GW->>OS: POST /orders
    OS-->>GW: 201 Created
    GW-->>Client: OrderId
` ` `

**Sources:** [docker-compose.yml:L45-L65](file:///path/docker-compose.yml#L45-L65), [openapi.yaml:L1-L50](file:///path/openapi.yaml#L1-L50)
```

---

## 4. コードスニペットと Sources 行のルール

- スニペットは疑似コードや推測コードを書いてはいけない。`docker-compose.yml`, k8sマニフェスト, `openapi.yaml`, `nginx.conf` 等の「設定・定義ファイル」から実際の行を引用すること。
- **Sources 行の絶対ルール**:
  - 必ず行番号（200行以内の範囲）を含める（例: `[docker-compose.yml:L12-L45]`）。
  - deepwiki で生成した個別サービスのWikiがある場合はそこへのリンクも許可する（例: `[user-service Architecture](file:///path/docs/wiki...)`）。

---

## 5. よくある失敗パターンとセルフレビューリスト

| 失敗パターン | 対策 |
| :--- | :--- |
| **全体検証・バッチ処理の強行** | 必ず**1ページ生成ごとに `validate_arch_page.py` を通過させてから次へ進む**。 |
| 個別サービスの内部実装を書いてしまう | API、DB間の矢印、通信プロトコルといった「サービス間」の繋ぎ方に限定する。 |
| スニペットが疑似コード | インフラ定義や Swagger などファイルの中身からの直接引用のみを記載する。 |
| ダイアグラムのノード名が汎用的 | `Backend Service` ではなく実際の環境に存在する `order-service` などの名前を用いる。 |

**セルフレビューチェックリスト (検証スクリプト呼び出し前)**
- [ ] スコープの逸脱はないか（個別サービスのロジック内部の解説を書いていないか）
- [ ] 全セクションに `**Sources:**` 行があり、かつ適切な行番号が付与されているか
- [ ] コードスニペットは実際の設定ファイル・環境変数・API定義からの引用になっているか
- [ ] importance に指定された数以上のスニペットとテーブル・図が含まれているか
- [ ] Mermaid のノードラベルには実際のサービス名が使われているか（[04-mermaid-rules.md](04-mermaid-rules.md)の構文チェックを満たしているか）
