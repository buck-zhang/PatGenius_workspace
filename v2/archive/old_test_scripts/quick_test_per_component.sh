#!/bin/bash
# 構成要素ごと検索の簡易テストスクリプト

set -e

echo "======================================"
echo "構成要素ごと検索システム 簡易テスト"
echo "======================================"
echo ""

# テストデータの確認
KEYWORDS_FILE="tests/performance_test/JP2013224028A_keywords.json"
CLASSIFICATION_FILE="tests/performance_test/JP2013224028A_classification.json"
PF_KEY="../patentfield_key.json"

if [ ! -f "$KEYWORDS_FILE" ]; then
    echo "エラー: キーワードファイルが見つかりません: $KEYWORDS_FILE"
    exit 1
fi

if [ ! -f "$CLASSIFICATION_FILE" ]; then
    echo "エラー: 分類ファイルが見つかりません: $CLASSIFICATION_FILE"
    exit 1
fi

if [ ! -f "$PF_KEY" ]; then
    echo "エラー: PatentField APIキーファイルが見つかりません: $PF_KEY"
    exit 1
fi

echo "ステップ1: 独立請求項フラグを追加"
echo "--------------------------------------"
KEYWORDS_WITH_FLAG="tests/performance_test/JP2013224028A_keywords_with_flag.json"

python add_independent_claim_flag.py \
    --keywords "$KEYWORDS_FILE" \
    --output "$KEYWORDS_WITH_FLAG" \
    --claims "1,6"

echo ""
echo "ステップ2: テスト実行"
echo "--------------------------------------"

# テスト1: 単一構成要素検索
echo ""
echo "[テスト1] 単一構成要素検索"
python test_per_component_search.py \
    --keywords "$KEYWORDS_WITH_FLAG" \
    --classifications "$CLASSIFICATION_FILE" \
    --pf-key "$PF_KEY" \
    --test 1

# テスト2: 並行検索（最初の3要素）
echo ""
echo "[テスト2] 並行検索（最初の3要素）"
python test_per_component_search.py \
    --keywords "$KEYWORDS_WITH_FLAG" \
    --classifications "$CLASSIFICATION_FILE" \
    --pf-key "$PF_KEY" \
    --test 2

# テスト3: 結果統合・重複削除
echo ""
echo "[テスト3] 結果統合・重複削除"
python test_per_component_search.py \
    --keywords "$KEYWORDS_WITH_FLAG" \
    --classifications "$CLASSIFICATION_FILE" \
    --pf-key "$PF_KEY" \
    --test 3

# テスト4: 完全実行
echo ""
echo "[テスト4] 完全実行（全構成要素、並行処理、結果統合）"
python test_per_component_search.py \
    --keywords "$KEYWORDS_WITH_FLAG" \
    --classifications "$CLASSIFICATION_FILE" \
    --pf-key "$PF_KEY" \
    --test 4 \
    --output "test_search_result.json"

echo ""
echo "======================================"
echo "全テスト完了！"
echo "======================================"
echo ""
echo "結果ファイル: test_search_result.json"
