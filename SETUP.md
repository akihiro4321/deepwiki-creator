# DeepWiki Creator セットアップガイド

## 概要

DeepWiki Creator は Gemini CLI の Agent Skill として動作し、ローカルのコードリポジトリから
構造化されたWikiドキュメントを自動生成します。

### v6 の主な改善点

- **15ページ最低ライン強制**: Comprehensiveモードでの最低ページ数を明示的に強制
- **2パス生成戦略**: フォールバック時にパス1（全ページ骨格）→パス2（肉付け）で品質とカバレッジを両立
- **必須カバレッジ領域の明示**: 12の領域（コア、ツール、設定、メモリ、拡張機構等）を列挙し漏れを防止
- **_meta.jsonフィールド検証**: validate_wiki.shでprimary_exports等の必須フィールド欠落を検出
- **v4のサブエージェント委譲**: agents/page-writer.mdによるページ生成委譲（利用可能な場合）
- **一貫性ガイド**: 用語辞書とページ間クロスリファレンスで統一性を確保

## インストール

### 1. スキルの配置

```bash
# プロジェクト用
cp -r deepwiki-creator-skill/ <your-project>/.gemini/skills/deepwiki-creator/

# グローバル用
cp -r deepwiki-creator-skill/ ~/.gemini/skills/deepwiki-creator/
```

### 2. カスタムコマンドの配置（任意）

```bash
mkdir -p ~/.gemini/commands/
cp deepwiki-creator-skill/assets/deepwiki.toml ~/.gemini/commands/deepwiki.toml
```

### 3. スクリプトの実行権限

```bash
chmod +x ~/.gemini/skills/deepwiki-creator/scripts/*.sh
```

## ワークフロー

```
メインエージェント:
  Step 0: パラメータ確認
  Step 1: ファイル収集（collect_files.sh）
  Step 1.5: コード偵察（recon_code.sh）
  Step 2: Wiki構造設計 + カバレッジ検証
  Step 2.5: 一貫性ガイド生成
       ↓ ユーザー確認
  Step 4: index.md 生成
  Step 5: 検証（validate_wiki.sh）

サブエージェント（ページごとに起動）:
  Step 3: 1ページの Markdown 生成
       入力: ページ定義 + relevant_files + 一貫性ガイド + page_prompt.md
       出力: sections/<dir>/<page>.md
```

### サブエージェント委譲の利点

| 問題（v3以前） | 解決（v4） |
|---------------|-----------|
| 後半ページの品質劣化 | 各ページが独立したコンテキストで生成 |
| ページ間の一貫性不足 | 一貫性ガイド（用語辞書+クロスリファレンス）で統一 |
| コンテキスト枯渇 | relevant_filesだけをロードし、コンテキストを最大活用 |

## 品質基準

| チェック項目 | 基準 |
|------------|------|
| JSON構文 | 有効なJSON（コメントなし） |
| コードスニペット | 各ページに最低1つ |
| Mermaid図 | 各ページに最低1つ（矢印にデータ内容記載） |
| ページ行数 | 60行以上（Comprehensive） |
| 異常系記述 | 各ページに含む |
| 設計判断 | 各ページに最低1つの Why 記述 |
| エンドツーエンドフロー | 最低1ページ（Comprehensive） |
| リンク整合性 | 壊れたリンク0 |
| index.md形式 | テーブル形式 |

## 対応言語

TypeScript/JavaScript, Python, Go, Rust, Java, Kotlin, Ruby, C#, PHP, Swift, Dart

## 大規模リポジトリ

1. `--include` で対象を絞る
2. `--mode concise` でページ数を抑える
3. サブエージェント委譲により後半品質劣化を防止
4. 1セッション15〜20ページまで（サブエージェント利用時）

## モデル別の品質傾向

deepwiki-creatorはマルチステップの複雑なワークフロー（偵察→構造設計→サブエージェント委譲→2パス肉付け→検証）を
モデルに実行させるため、モデルの指示遵守能力によって生成品質に大きな差が出ます。

| モデル | 指示遵守 | コードスニペット | Mermaid図 | 60行達成率 | 推奨用途 |
|--------|---------|----------------|-----------|-----------|---------|
| Gemini 2.5 Pro | 高 | 多くのページで生成 | 高品質 | 高い | Comprehensive（推奨） |
| Gemini 2.5 Flash | 中 | 生成されるが一部欠落 | 概ね良好 | 中程度 | Comprehensive / Concise |
| Gemini 3 Flash Preview | 低〜中 | 欠落しやすい | 欠落しやすい | 低い | Concise推奨 |

**Flash系モデルで品質が不足する場合の対策：**

1. **validate_wiki.sh を必ず実行し、ERRORが0になるまで再生成する**
2. サブエージェント委譲が正しく動作しているか確認する（page-writerが起動されているか）
3. 2パス戦略のパス2がスキップされていないか確認する
4. 品質基準未達のページのみ、手動で再生成を指示する（`このページを60行以上に肉付けしてください`）

## トラブルシューティング

| 問題 | 対処 |
|------|------|
| サブエージェントが利用できない | メインエージェントが直接生成にフォールバック |
| ページ間で用語が統一されない | _consistency_guide.md を確認・修正して再生成 |
| 拡張機構が未検出 | recon_code.sh のセクション3を確認。READMEとの突合 |
| 後半ページが薄い | サブエージェント利用を確認。未使用なら有効化 |

## チームへの展開

```bash
cp -r deepwiki-creator-skill/ .gemini/skills/deepwiki-creator/
cp deepwiki-creator-skill/assets/deepwiki.toml .gemini/commands/deepwiki.toml
git add .gemini/
git commit -m "feat: add deepwiki-creator skill v4"
```
