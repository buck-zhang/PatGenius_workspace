# 進歩性判断エンジン - 使用ガイド

**作成日**: 2025-12-09
**更新日**: 2025-12-09（Gemini 3.0 Pro実装）
**対応モデル**: **Vertex AI Gemini 3.0 Pro Preview** (デフォルト)
**機能**: X文献・Y文献の自動摘出による進歩性判断支援

---

## 🆕 最新情報（v2.1.0）

### Gemini 3.0 Pro Preview 実装完了

**2025年12月9日実装**:
- ✅ **モデル**: `gemini-3-pro-preview`（推論特化モデル）
- ✅ **リージョン**: `global`（Globalエンドポイント使用）
- ✅ **Temperature**: `0.0`（決定論的判断）
- ✅ **Context Window**: 1M tokens
- ✅ **知識カットオフ**: 2025年1月

**主な特徴**:
1. 🧠 **推論能力**: 数値範囲の包含関係を正確に判断
2. 📊 **実質的同一性判断**: 高度な特許実務判断
3. 🔄 **最新知識**: 2025年1月までの審査基準・判例を反映
4. 🌐 **1M Context Window**: 特許全文を一度に処理可能

---

## 概要

本システムは、特許検索結果の全特許について本願特許との構成対比を自動実行し、以下を摘出します:

- **X文献**: 本願の全構成要素を単独で備える特許（新規性喪失のリスク）
- **Y文献**: 3件以内の組み合わせで全構成要素を備える特許群（進歩性欠如のリスク）

### 優先順位付きフォールバック戦略（2段階システム）

**2025年12月9日更新**: 3段階から2段階に簡素化

```
優先度1: 全ての構成要素（最優先）
  └─ 完全な構成要件での評価（真の新規性喪失リスク）

優先度2: 独立請求項の構成要素（フォールバック）
  ├─ 対象: is_independent=true の構成要素
  └─ 最も重要な発明の本質部分での評価
```

**フォールバック**: 優先度1で見つからない場合、優先度2の結果を採用

---

## セットアップ

### 1. 必要な環境

- Python 3.9以上
- Google Cloud プロジェクト
- Vertex AI APIの有効化

### 2. 依存パッケージのインストール

```bash
pip install google-cloud-aiplatform
pip install vertexai
pip install tenacity
pip install requests
```

### 3. 認証設定

#### A. Google Cloud認証

```bash
# Google Cloud SDKのインストール
# https://cloud.google.com/sdk/docs/install

# 認証
gcloud auth application-default login

# プロジェクトID設定
export GOOGLE_CLOUD_PROJECT='your-project-id'
```

#### B. PatentField APIキー（オプション）

```json
// patentfield_key.json
{
  "api_key": "your-api-key",
  "base_url": "https://api.patentfield.com"
}
```

---

## 使用方法

### 基本的な使用

```python
from novelty_assessment_engine import NoveltyAssessmentEngine

# エンジン初期化
engine = NoveltyAssessmentEngine(
    project_id="your-project-id",
    location="us-central1",
    model_name="gemini-2.0-flash-exp",
    output_dir="./novelty_assessment_results",
    max_workers=5
)

# 進歩性判断の実行
summary = engine.assess_novelty(
    base_patent_structure_file="tests/performance_test/results/test_001_JP2013224028_structure.json",
    search_result_file="tests/performance_test/results/test_001_JP2013224028_search_result.json",
    limit=100  # 最初の100件のみ（None=全件）
)

# 結果確認
print(f"X文献: {summary['x_references']['count']}件")
print(f"Y文献: {summary['y_references']['count']}件")
```

### コマンドライン使用

```bash
# テストスクリプトの実行
cd /Users/ttdc-user/Desktop/patgenius/zhang_opera/v2/src
python test_novelty_assessment.py

# または直接実行
python novelty_assessment_engine.py \
  your-project-id \
  ../tests/performance_test/results/test_001_JP2013224028_structure.json \
  ../tests/performance_test/results/test_001_JP2013224028_search_result.json \
  50  # 最初の50件のみ
```

---

## 出力ファイル

### ディレクトリ構造

```
novelty_assessment_results/
├── novelty_assessment_summary.json  # サマリーレポート
├── comparison_JP2023020908.json     # 個別構成対比結果
├── comparison_JP2019003176.json
└── ...
```

### サマリーファイルの形式

```json
{
  "base_patent_id": "JP2013224028",
  "assessment_date": "2025-12-09 11:30:00",
  "search_results_count": 1000,
  "successful_comparisons": 980,
  "failed_comparisons": 20,
  "priority_level_used": "priority_3_all_elements",

  "x_references": {
    "count": 3,
    "patents": ["JP2023020908", "JP2019003176", "JP2024113956"]
  },

  "y_references": {
    "count": 150,
    "combinations": [
      {
        "patents": ["JP2023020908", "JP2019003176"],
        "combination_count": 2,
        "coverage": {
          "JP2023020908": ["1a", "1b", "1c"],
          "JP2019003176": ["1d", "2a", "2b"]
        }
      }
    ]
  },

  "statistics": {
    "total_comparisons": 1000,
    "successful_comparisons": 980,
    "failed_comparisons": 20,
    "api_errors": 5,
    "total_time_seconds": 3600.5
  }
}
```

### 個別構成対比ファイルの形式

```json
{
  "target_patent_id": "JP2023020908",
  "comparison_date": "2025-12-09",
  "element_comparisons": [
    {
      "element_id": "1a",
      "is_disclosed": true,
      "evidence": {
        "locations": ["請求項1", "段落0015"],
        "quoted_text": "式(1)で表される繰り返し単位を含む樹脂...",
        "reasoning": "本願の式(a4)と実質的に同一の構造が請求項1に明示されている"
      }
    }
  ],
  "overall_assessment": {
    "total_elements": 10,
    "disclosed_elements": 7,
    "disclosure_rate": 0.7,
    "novelty_risk": "medium"
  }
}
```

---

## パフォーマンスと費用

### 処理時間の目安

| 対象特許数 | 並列処理数 | 推定時間 |
|----------|----------|---------|
| 10件 | 5 | 1-2分 |
| 100件 | 5 | 10-20分 |
| 1000件 | 5 | 1.5-3時間 |

### APIコスト（Gemini 2.0 Flash）

- **入力トークン単価**: $0.00001875 / 1K tokens
- **出力トークン単価**: $0.000075 / 1K tokens
- **1特許あたりの推定コスト**: $0.01-0.02
- **1000件の推定コスト**: $10-20

---

## トラブルシューティング

### Q1: "GOOGLE_CLOUD_PROJECT環境変数が設定されていません"

```bash
export GOOGLE_CLOUD_PROJECT='your-project-id'
```

### Q2: "PermissionDenied: Vertex AI API has not been enabled"

```bash
gcloud services enable aiplatform.googleapis.com
```

### Q3: "JSON解析エラーが多発する"

- Gemini 3.0の場合、`temperature=1.0`推奨（デフォルト設定）
- プロンプトを簡潔に保つ（Gemini 3最適化）

### Q4: "処理が遅い"

- `max_workers`を増やす（推奨: 5-10）
- 初期テストは`limit=10`で動作確認
- PatentField APIのレート制限に注意

---

## 2025年ベストプラクティス

### 1. Gemini 3使用時の注意

**出典**: [Gemini 3 Guide](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/start/get-started-with-gemini-3)

- `temperature=1.0`を維持（推論最適化のため）
- 簡潔なプロンプト（冗長な指示は逆効果）
- `max_output_tokens`を十分に設定（長い応答用）

### 2. コスト最適化

- 初期テストは少数件（10-50件）
- 重要度の低い構成要素を除外
- 結果のキャッシング活用

### 3. 精度向上

- Human-in-the-Loop: 重要な判断は人間が最終確認
- エラー率のモニタリング
- フィードバックループの構築

---

## 法的注意事項

本システムは進歩性判断の**支援ツール**であり、最終的な法的判断は必ず専門家（弁理士・特許弁護士）が行ってください。

- ✓ AI判断は参考情報として活用
- ✓ 重要な特許は人間が詳細レビュー
- ✓ 拒絶理由通知への対応は専門家に相談

---

## 参考文献

1. [Vertex AI Gemini API](https://cloud.google.com/vertex-ai/generative-ai/docs)
2. [Google Gen AI SDK](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/sdks/overview)
3. [特許庁 AI関連技術の特許審査事例](https://www.jpo.go.jp/system/laws/rule/guideline/patent/ai_jirei.html)
4. [Gemini for Patent Research](https://sparkco.ai/blog/gemini-3-for-patent-research)

---

**文書バージョン**: v1.0
**最終更新日**: 2025-12-09
**メンテナンス**: 開発チーム
