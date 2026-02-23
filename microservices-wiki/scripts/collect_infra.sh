#!/usr/bin/env bash
# collect_infra.sh - マイクロサービスアーキテクチャのインフラ定義ファイルを収集するスクリプト
#
# 使用方法: ./collect_infra.sh <対象ルートディレクトリ>
# 例:       ./collect_infra.sh /path/to/monorepo
#           ./collect_infra.sh /path/to/service-root
#
# 出力: サービス一覧・ポートマッピング・インフラ定義ファイルの一覧

set -euo pipefail

TARGET_DIR="${1:-.}"

# 対象ディレクトリの検証
if [ ! -d "$TARGET_DIR" ]; then
  echo "ERROR: ディレクトリが存在しません: $TARGET_DIR" >&2
  exit 1
fi

TARGET_DIR="$(cd "$TARGET_DIR" && pwd)"

echo "=== microservices-wiki インフラ分析 ==="
echo "対象: $TARGET_DIR"
echo "日時: $(date '+%Y-%m-%d %H:%M:%S')"
echo ""

# --- セクション 1: ディレクトリ概要 ---
echo "## ディレクトリ概要"
echo '```'
if command -v tree &>/dev/null; then
  tree "$TARGET_DIR" \
    -I "node_modules|.git|__pycache__|.next|dist|build|vendor|.venv|venv|target|Pods" \
    --dirsfirst -L 3 -F --noreport 2>/dev/null || \
    echo "(tree コマンドの実行に失敗しました)"
else
  find "$TARGET_DIR" -maxdepth 3 \
    \( -name "node_modules" -o -name ".git" -o -name "__pycache__" \
       -o -name ".next" -o -name "dist" -o -name "build" \
       -o -name "vendor" -o -name ".venv" -o -name "target" \) -prune \
    -o \( -type f -o -type d \) -print 2>/dev/null | \
    sed "s|^$TARGET_DIR/||" | sort
fi
echo '```'
echo ""

# --- セクション 2: docker-compose の検出 ---
echo "## Docker Compose ファイル"

COMPOSE_FILES=$(find "$TARGET_DIR" -maxdepth 4 \
  \( -name "docker-compose*.yml" -o -name "docker-compose*.yaml" \) \
  -not -path "*/node_modules/*" -not -path "*/.git/*" \
  2>/dev/null | sort)

if [ -n "$COMPOSE_FILES" ]; then
  echo ""
  echo "### 検出されたファイル"
  echo '```'
  echo "$COMPOSE_FILES" | sed "s|^$TARGET_DIR/||"
  echo '```'

  echo ""
  echo "### サービス一覧（docker-compose から抽出）"
  echo '```'
  for f in $COMPOSE_FILES; do
    echo "--- $(echo "$f" | sed "s|^$TARGET_DIR/||") ---"
    # services: セクション内のサービス名を抽出（インデント1レベル）
    grep -E "^  [a-zA-Z][a-zA-Z0-9_-]*:" "$f" 2>/dev/null | \
      sed 's/://g' | sed 's/^  /  - /' || true
    echo ""
  done
  echo '```'

  echo ""
  echo "### ポートマッピング（docker-compose から抽出）"
  echo '```'
  for f in $COMPOSE_FILES; do
    echo "--- $(echo "$f" | sed "s|^$TARGET_DIR/||") ---"
    grep -A1 "ports:" "$f" 2>/dev/null | grep -E '^\s+- "[0-9]|^\s+- [0-9]' | \
      sed 's/^\s*/  /' || true
    echo ""
  done
  echo '```'

  echo ""
  echo "### 環境変数抜粋（サービス間URLの検出）"
  echo '```'
  for f in $COMPOSE_FILES; do
    echo "--- $(echo "$f" | sed "s|^$TARGET_DIR/||") ---"
    grep -E "(URL|HOST|ENDPOINT|SERVICE|ADDR|PORT)\s*[:=]" "$f" 2>/dev/null | \
      grep -v "^#" | sed 's/^\s*/  /' | head -30 || true
    echo ""
  done
  echo '```'

  echo ""
  echo "### データストア（DB・MQ・キャッシュ）"
  echo '```'
  for f in $COMPOSE_FILES; do
    echo "--- $(echo "$f" | sed "s|^$TARGET_DIR/||") ---"
    grep -iE "postgres|mysql|mongodb|redis|elasticsearch|kafka|rabbitmq|memcached|dynamodb|cassandra|nats" "$f" 2>/dev/null | \
      grep -v "^#" | sed 's/^\s*/  /' || true
    echo ""
  done
  echo '```'

  echo ""
  echo "### ネットワーク定義"
  echo '```'
  for f in $COMPOSE_FILES; do
    local_networks=$(grep -A1 "networks:" "$f" 2>/dev/null | head -10 || true)
    if [ -n "$local_networks" ]; then
      echo "--- $(echo "$f" | sed "s|^$TARGET_DIR/||") ---"
      echo "$local_networks"
      echo ""
    fi
  done
  echo '```'
else
  echo "(docker-compose ファイルが見つかりませんでした)"
fi
echo ""

# --- セクション 3: Kubernetes マニフェスト ---
echo "## Kubernetes マニフェスト"

K8S_DIRS=$(find "$TARGET_DIR" -maxdepth 4 -type d \
  \( -name "k8s" -o -name "kubernetes" -o -name "manifests" -o -name "helm" \) \
  -not -path "*/node_modules/*" -not -path "*/.git/*" \
  2>/dev/null | sort)

if [ -n "$K8S_DIRS" ]; then
  echo ""
  echo "### k8s ディレクトリ"
  echo '```'
  echo "$K8S_DIRS" | sed "s|^$TARGET_DIR/||"
  echo '```'

  echo ""
  echo "### Deployment リソース（サービス一覧）"
  echo '```'
  find "$TARGET_DIR" -maxdepth 6 \
    \( -name "*.yaml" -o -name "*.yml" \) \
    -not -path "*/node_modules/*" -not -path "*/.git/*" \
    2>/dev/null | xargs grep -l "kind: Deployment" 2>/dev/null | while read -r f; do
    echo "--- $(echo "$f" | sed "s|^$TARGET_DIR/||") ---"
    grep -E "(^  name:|image:|containerPort:)" "$f" 2>/dev/null | sed 's/^\s*/  /' | head -20
    echo ""
  done
  echo '```'

  echo ""
  echo "### Service / Ingress リソース（ルーティング）"
  echo '```'
  find "$TARGET_DIR" -maxdepth 6 \
    \( -name "*.yaml" -o -name "*.yml" \) \
    -not -path "*/node_modules/*" -not -path "*/.git/*" \
    2>/dev/null | xargs grep -l "kind: Ingress" 2>/dev/null | while read -r f; do
    echo "--- $(echo "$f" | sed "s|^$TARGET_DIR/||") ---"
    grep -E "(host:|path:|serviceName:|service:)" "$f" 2>/dev/null | \
      sed 's/^\s*/  /' | head -20
    echo ""
  done
  echo '```'
else
  echo "(Kubernetes マニフェストが見つかりませんでした)"
fi
echo ""

# --- セクション 4: API 仕様ファイル ---
echo "## API 仕様ファイル"
echo ""

echo "### OpenAPI / Swagger"
echo '```'
find "$TARGET_DIR" -maxdepth 5 \
  \( -name "openapi*.yaml" -o -name "openapi*.json" -o -name "openapi*.yml" \
     -o -name "swagger*.yaml" -o -name "swagger*.json" -o -name "swagger*.yml" \
     -o -name "api-docs.yaml" -o -name "api-docs.json" -o -name "api-spec.yaml" \) \
  -not -path "*/node_modules/*" -not -path "*/.git/*" -not -path "*/dist/*" \
  2>/dev/null | sed "s|^$TARGET_DIR/||" | sort
echo '```'
echo ""

echo "### gRPC / Protocol Buffers"
echo '```'
find "$TARGET_DIR" -maxdepth 6 -name "*.proto" \
  -not -path "*/node_modules/*" -not -path "*/.git/*" -not -path "*/vendor/*" \
  2>/dev/null | sed "s|^$TARGET_DIR/||" | sort
echo '```'
echo ""

# --- セクション 5: DB・マイグレーション ---
echo "## データベース定義"
echo ""

echo "### スキーマ・マイグレーションファイル"
echo '```'
find "$TARGET_DIR" -maxdepth 6 \
  \( -name "schema.sql" -o -name "schema.prisma" -o -name "*.prisma" \
     -o -name "*.sql" -o -name "V*.sql" \) \
  -not -path "*/node_modules/*" -not -path "*/.git/*" \
  2>/dev/null | sed "s|^$TARGET_DIR/||" | sort | head -30
echo '```'
echo ""

echo "### マイグレーションディレクトリ"
echo '```'
find "$TARGET_DIR" -maxdepth 4 -type d \
  \( -name "migrations" -o -name "migrate" -o -name "db" \) \
  -not -path "*/node_modules/*" -not -path "*/.git/*" \
  2>/dev/null | sed "s|^$TARGET_DIR/||" | sort
echo '```'
echo ""

# --- セクション 6: API Gateway / リバースプロキシ ---
echo "## API Gateway / リバースプロキシ"
echo ""

echo "### 設定ファイル"
echo '```'
find "$TARGET_DIR" -maxdepth 5 \
  \( \
    -name "nginx.conf" -o -name "nginx*.conf" -o -name "default.conf" \
    -o -name "kong.yml" -o -name "kong.yaml" \
    -o -name "traefik*.yml" -o -name "traefik*.yaml" \
    -o -name "envoy*.yaml" -o -name "envoy*.yml" \
    -o -name "gateway.yaml" -o -name "api-gateway.yaml" \
  \) \
  -not -path "*/node_modules/*" -not -path "*/.git/*" \
  2>/dev/null | sed "s|^$TARGET_DIR/||" | sort
echo '```'
echo ""

# --- セクション 7: CI/CD ---
echo "## CI/CD パイプライン"
echo ""

echo "### CI/CD 設定ファイル"
echo '```'
find "$TARGET_DIR" -maxdepth 4 \
  \( \
    -path "*/.github/workflows/*.yml" -o -path "*/.github/workflows/*.yaml" \
    -o -name ".gitlab-ci.yml" -o -name "Jenkinsfile" \
    -o -name "cloudbuild.yaml" -o -name "buildspec.yml" \
    -o -name ".circleci/config.yml" \
  \) \
  -not -path "*/node_modules/*" \
  2>/dev/null | sed "s|^$TARGET_DIR/||" | sort
echo '```'
echo ""

# --- セクション 8: インフラ定義（IaC）---
echo "## インフラ定義 (IaC)"
echo ""

echo "### Terraform"
echo '```'
find "$TARGET_DIR" -maxdepth 4 -name "*.tf" \
  -not -path "*/node_modules/*" -not -path "*/.git/*" \
  2>/dev/null | sed "s|^$TARGET_DIR/||" | sort | head -20
echo '```'
echo ""

echo "### Helm Charts"
echo '```'
find "$TARGET_DIR" -maxdepth 5 -name "Chart.yaml" \
  -not -path "*/node_modules/*" -not -path "*/.git/*" \
  2>/dev/null | sed "s|^$TARGET_DIR/||" | sort
echo '```'
echo ""

# --- セクション 9: 既存 Wiki ドキュメント ---
echo "## 既存ドキュメント"
echo ""

echo "### README / アーキテクチャドキュメント"
echo '```'
find "$TARGET_DIR" -maxdepth 3 \
  \( -name "README.md" -o -name "README" -o -name "ARCHITECTURE.md" \
     -o -name "CONTRIBUTING.md" -o -name "ADR*.md" \) \
  -not -path "*/node_modules/*" -not -path "*/.git/*" \
  2>/dev/null | sed "s|^$TARGET_DIR/||" | sort | head -20
echo '```'
echo ""

echo "### docs/wiki（deepwikiで生成済みの場合）"
echo '```'
find "$TARGET_DIR" -maxdepth 5 -path "*/docs/wiki/*.md" \
  -not -path "*/node_modules/*" \
  2>/dev/null | sed "s|^$TARGET_DIR/||" | sort | head -30
echo '```'
echo ""

# --- セクション 10: サービスメッシュ ---
echo "## サービスメッシュ"
echo '```'
find "$TARGET_DIR" -maxdepth 5 \
  \( -path "*/istio/*" -o -path "*/linkerd/*" -o -path "*/consul/*" \
     -o -name "*.istio.yaml" -o -name "virtualservice*.yaml" \
     -o -name "destinationrule*.yaml" \) \
  -not -path "*/node_modules/*" -not -path "*/.git/*" \
  2>/dev/null | sed "s|^$TARGET_DIR/||" | sort | head -20
echo '```'
echo ""

echo "=== 分析完了 ==="
