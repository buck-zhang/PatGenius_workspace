# PatGenius - 日本特許OpenSearch検索システム

30,002件の日本特許データを対象とした高速検索システム

## 🎯 **プロジェクト概要**

PatGeniusは、日本特許庁の特許XML データをOpenSearchに効率的にインポートし、高度な検索・分析機能を提供するシステムです。

### **主要機能**
- ✅ **30,002件の特許データ** - 完全にインデックス済み
- ✅ **15フィールド対応** - 発明名称から技術内容まで包括的検索
- ✅ **高速一括処理** - 183.0ファイル/秒の処理性能
- ✅ **REST API & Web UI** - プログラマブルアクセスとビジュアル検索

## 🔧 **システム構成**

### **コアファイル**
```
├── bulk_import_patents.py           # 一括インポートエンジン
├── opensearch_tags_analysis.json    # フィールド定義・最適化設定
├── docker-compose.yml              # OpenSearch環境構築
├── opensearch_dashboards.yml       # 日本語化設定
└── import_xml_to_opensearch.py     # 単体インポート用
```

### **データ構造**
```
source_data/                        # 30,002件のXMLファイル
├── 0/JP2010000001A/text.txt       # 特許XML (バリカン式刈刃装置)
├── 0/JP2010000002A/text.txt       # 特許XML (燃料電池)
└── ...                            # 29,999件の特許データ
```

## 🚀 **使い方**

### **1. 環境構築**
```bash
# OpenSearchクラスター起動
docker-compose up -d

# 依存関係インストール
pip install -r requirements.txt
```

### **2. データインポート**
```bash
# 全特許データの一括インポート（約2.7分）
python3 bulk_import_patents.py

# インポート結果確認
curl "localhost:9200/patents/_count"
```

### **3. 検索方法**

#### **REST API検索**
```bash
# 発明名称で検索
curl -X GET "localhost:9200/patents/_search" -H 'Content-Type: application/json' -d '{
  "query": {"match": {"invention_title": "画像形成装置"}}
}'

# 技術分野で検索
curl -X GET "localhost:9200/patents/_search" -H 'Content-Type: application/json' -d '{
  "query": {"match": {"technical_field": "電子写真"}}
}'

# 複合条件検索
curl -X GET "localhost:9200/patents/_search" -H 'Content-Type: application/json' -d '{
  "query": {
    "bool": {
      "must": [
        {"match": {"invention_title": "バリカン"}},
        {"match": {"technical_field": "刈刃"}}
      ]
    }
  }
}'
```

#### **Web UI検索**
ブラウザで http://localhost:5601 にアクセス

## 📊 **検索可能フィールド**

| フィールド名 | 内容 | 例 |
|-------------|------|-----|
| `invention_title` | 発明名称 | "現像剤搬送装置" |
| `applicant_name` | 出願人名 | "京セラミタ株式会社" |
| `inventor_names` | 発明者名 | "遠藤 裕久" |
| `technical_field` | 技術分野 | "電子写真方式を利用した..." |
| `background_art` | 背景技術 | "従来、電子写真プロセス..." |
| `tech_problem` | 解決課題 | "しかしながら、従来技術では..." |
| `tech_solution` | 解決手段 | "本発明は、上記問題点に鑑み..." |
| `advantageous_effects` | 発明の効果 | "本発明の第１の構成によれば..." |
| `description` | 詳細説明 | "以下、図面を参照しながら..." |
| `claims` | 請求項 | "Claim 1: 現像剤を収容する筐体と..." |
| `abstract` | 要約 | "【課題】トナーを除去するための..." |
| `classification_ipc` | IPC分類 | ["G03G 15/08"] |
| `classification_national` | 国内分類 | ["G03G15/08 507D"] |
| `f_terms` | Fターム | ["2H073AA09", "2H073BA04"] |
| `document_id` | 文献番号 | "2010008759" |

## 📈 **パフォーマンス実績**

### **インポート性能**
- **データ量**: 30,002件の特許XML
- **処理時間**: 2.7分
- **処理速度**: 183.0ファイル/秒
- **成功率**: 100% (失敗0件)

### **検索性能**
- **インデックスサイズ**: 3シャード、1レプリカ
- **レスポンス時間**: < 100ms (典型的なクエリ)
- **同時接続**: 複数クライアント対応

## 🛠 **開発・運用**

### **ログ確認**
```bash
# インポートログ
tail -f patent_import.log

# OpenSearchログ
docker logs opensearch-node
```

### **データメンテナンス**
```bash
# インデックス再作成
curl -X DELETE "localhost:9200/patents"
python3 bulk_import_patents.py

# クラスター健康状態確認
curl "localhost:9200/_cluster/health"
```

### **拡張方法**
1. `opensearch_tags_analysis.json` でフィールド追加
2. `bulk_import_patents.py` でパーサー更新
3. インデックス再作成・データ再投入

## 📋 **技術仕様**

- **OpenSearch**: 2.11.1
- **Python**: 3.9+
- **解析エンジン**: Standard Analyzer (日本語対応)
- **データ形式**: Japanese Patent XML (JPO形式)
- **文字エンコーディング**: UTF-8

## 🤝 **貢献**

1. Fork the repository
2. Create your feature branch
3. Commit your changes  
4. Push to the branch
5. Create a Pull Request

## 📄 **ライセンス**

本プロジェクトはMITライセンスの下で公開されています。

---

**PatGenius** - Powered by OpenSearch & 日本特許データ