#!/usr/bin/env python3
"""
ハイライトとスコア機能のテスト
"""

from classification_search_engine import ClassificationDatabase
import logging

# ログ設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_highlight_and_score():
    """ハイライトとスコア機能のテスト"""
    logger.info("=== ハイライト・スコア機能テスト開始 ===")
    
    # データベース初期化
    db = ClassificationDatabase()
    db.load_data()
    
    # テストケース
    test_queries = [
        "画像 AND 形成",
        "画像形成装置", 
        "電子写真"
    ]
    
    for query in test_queries:
        logger.info(f"\n--- テスト: '{query}' ---")
        
        try:
            results = db.search_by_keyword(
                keyword=query,
                systems=['IPC', 'FI', 'CPC'],
                limit=2,
                include_hierarchy=True,
                highlight=True
            )
            
            logger.info(f"検索結果: {len(results)}件")
            
            for i, result in enumerate(results):
                logger.info(f"  {i+1}. {result['classification_system']} {result['code']}")
                logger.info(f"     日本語: {result.get('title_ja', 'N/A')}")
                
                if 'title_ja_highlighted' in result:
                    logger.info(f"     ハイライト: {result['title_ja_highlighted']}")
                else:
                    logger.info(f"     ハイライト: なし")
                    
                score = result.get('match_score', 'N/A')
                logger.info(f"     スコア: {score}")
                logger.info(f"     文書数: {result.get('num_documents', 0)}")
                logger.info("")
                
        except Exception as e:
            logger.error(f"  エラー: {e}")
            import traceback
            traceback.print_exc()
    
    logger.info("=== ハイライト・スコア機能テスト完了 ===")

if __name__ == "__main__":
    test_highlight_and_score()