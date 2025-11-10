# データインポート監視ガイド

## 現在の状況

✅ システム起動中
✅ データインポート実行中（バックグラウンド）

**最新進捗**: IPCデータ 264/2,496 バッチ (11%)
**処理速度**: 約1.5-1.7秒/バッチ
**推定残り時間**: 約1時間（IPCのみ、その後FI・CPCも処理）

---

## リアルタイム監視方法

### 方法1: 監視スクリプト使用（推奨）

```bash
./monitor_import.sh
```

インポート関連の進捗のみをフィルタリングして表示します。
- Ctrl+Cで監視停止（インポートは継続）

### 方法2: 状況確認スクリプト

```bash
./check_import_status.sh
```

現在の状況のスナップショットを表示：
- システム状態
- インデックスされたレコード数
- 最新ログ

### 方法3: Dockerログ直接確認

```bash
# すべてのログをリアルタイム表示
docker logs -f patent_classification_api

# 進捗のみをフィルタ表示
docker logs -f patent_classification_api 2>&1 | grep Batches
```

### 方法4: OpenSearch統計確認

```bash
# インデックス統計
curl -s http://localhost:9200/_cat/indices?v | grep patent_classification

# IPC レコード数
curl -s http://localhost:9200/patent_classification_ipc/_count

# CPC レコード数
curl -s http://localhost:9200/patent_classification_cpc/_count

# FI レコード数
curl -s http://localhost:9200/patent_classification_fi/_count
```

---

## インポート進捗の理解

### フェーズ1: データ読み込み
```
Reading IPC files: 100%|██████████| 662/662
```
- 全ファイルからデータを読み込み
- 約79,850レコード

### フェーズ2: 埋め込み生成（現在ここ）
```
Batches: 11%|█ | 264/2496 [08:52<1:01:34, 1.66s/it]
```
- RAG用の埋め込みベクトル生成
- **最も時間がかかるフェーズ**
- 約1.5-1.7秒/バッチ

### フェーズ3: OpenSearchへインデックス
```
Indexing 79850 records into patent_classification_ipc...
```
- 生成された埋め込みをOpenSearchに保存
- 比較的高速

---

## 完了後の確認

インポート完了後、以下で確認できます：

```bash
# 状況確認
./check_import_status.sh

# APIでテスト
python3 api_client_examples.py

# 簡単な検索テスト
curl "http://localhost:8000/search/keyword?q=agriculture&top_k=5"
```

---

## トラブルシューティング

### インポートが停止した場合

```bash
# プロセス確認
docker-compose ps

# ログ確認
docker logs patent_classification_api | tail -50

# 再起動が必要な場合
docker-compose restart api

# 再インポート
docker-compose exec api python import_classification_data.py \
    --host opensearch --port 9200 --data-dir /app/data_20250812
```

### メモリ不足の場合

docker-compose.ymlでメモリ設定を調整：
```yaml
environment:
  - "OPENSEARCH_JAVA_OPTS=-Xms1g -Xmx1g"  # 2g→1gに削減
```

---

## 推定タイムライン

**IPCデータ**（現在処理中）:
- ファイル読み込み: ✅ 完了
- 埋め込み生成: 🔄 11% (残り約1時間)
- インデックス: ⏳ 待機中

**FIデータ**（次のフェーズ）:
- 推定時間: 30-40分

**CPCデータ**（最終フェーズ）:
- 推定時間: 30-40分

**合計推定時間**: 約2-2.5時間

---

## バックグラウンド実行

インポートはバックグラウンドで実行されているため：
- ターミナルを閉じてもOK
- PCをスリープしないこと
- Dockerを停止しないこと

進捗確認はいつでも可能です！
