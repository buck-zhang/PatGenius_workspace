# Vertex AI Migration Guide

## 変更内容

GeminiをVertex AI経由で利用するように変更しました。

### 主な変更点

#### 1. パッケージの変更

**変更前**:
```python
import google.generativeai as genai
```

**変更後**:
```python
import vertexai
from vertexai.generative_models import GenerativeModel, GenerationConfig
```

#### 2. 初期化の変更

**変更前**:
```python
gemini_client = GeminiClient(
    service_account_path="path/to/service-account.json",
    model_name="gemini-2.5-pro"
)
```

**変更後**:
```python
gemini_client = GeminiClient(
    service_account_path="path/to/service-account.json",
    project_id="ttdc-in-house-dev",  # 追加
    location="us-central1",           # 追加
    model_name="gemini-2.5-pro"
)
```

#### 3. 依存パッケージの変更

**requirements_patent_analysis.txt**

変更前:
```
google-generativeai>=0.3.0
```

変更後:
```
google-cloud-aiplatform>=1.38.0
```

### 設定値

- **Project ID**: `ttdc-in-house-dev`
- **Location**: `us-central1`（デフォルト）
- **Model**: `gemini-2.5-pro`

### 必要な権限

サービスアカウントに以下のロールが必要です：
- `Vertex AI User` (roles/aiplatform.user)

### API有効化

Google Cloud Console で以下のAPIを有効化してください：
- Vertex AI API
- Cloud Resource Manager API

### 確認コマンド

```bash
# Vertex AI SDKがインストールされているか確認
pip3 list | grep google-cloud-aiplatform

# サービスアカウントファイルの確認
cat ./ttdc-in-house-dev-3e07247326cb.json | python3 -m json.tool

# プロジェクトIDの確認
grep project_id ./ttdc-in-house-dev-3e07247326cb.json
```

### トラブルシューティング

#### エラー: "Vertex AI API has not been used in project"

**解決方法**:
1. Google Cloud Console を開く
2. プロジェクト `ttdc-in-house-dev` を選択
3. APIs & Services → Enable APIs and Services
4. "Vertex AI API" を検索して有効化

#### エラー: "Permission denied"

**解決方法**:
サービスアカウントに `Vertex AI User` ロールを付与：
```bash
gcloud projects add-iam-policy-binding ttdc-in-house-dev \
    --member="serviceAccount:SERVICE_ACCOUNT_EMAIL" \
    --role="roles/aiplatform.user"
```

#### エラー: "Model not found in location"

**解決方法**:
モデルが指定したリージョンで利用可能か確認。
デフォルトの `us-central1` で利用できない場合は、別のリージョン（例: `us-east1`）を試してください。

### 移行チェックリスト

- [ ] `google-cloud-aiplatform` パッケージをインストール
- [ ] Vertex AI API を有効化
- [ ] サービスアカウントに `Vertex AI User` 権限を付与
- [ ] コード内で `project_id` と `location` を指定
- [ ] 既存のコードをテスト

### 変更されたファイル

1. `patent_component_analyzer.py` - GeminiClientクラスを更新
2. `run_patent_analysis.py` - 初期化コードを更新
3. `test_patent_analysis.py` - 初期化コードを更新
4. `example_usage.py` - 初期化コードを更新
5. `requirements_patent_analysis.txt` - 依存パッケージを更新
6. `PATENT_ANALYSIS_README.md` - ドキュメントを更新
7. `QUICKSTART_PATENT_ANALYSIS.md` - ドキュメントを更新

### 後方互換性

GeminiClientクラスは、`project_id`と`location`にデフォルト値を設定しているため、既存のコード（パラメータなし）でも動作しますが、明示的に指定することを推奨します。

### 参考リンク

- [Vertex AI Documentation](https://cloud.google.com/vertex-ai/docs)
- [Vertex AI Python SDK](https://cloud.google.com/python/docs/reference/aiplatform/latest)
- [Gemini API on Vertex AI](https://cloud.google.com/vertex-ai/docs/generative-ai/model-reference/gemini)
