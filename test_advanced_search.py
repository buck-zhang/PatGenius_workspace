#!/usr/bin/env python3
"""
分類検索システムの高度検索機能テスト
"""

from classification_search_engine import ClassificationDatabase
import logging

# ログ設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_advanced_search():
    """高度検索機能のテスト"""
    logger.info("=== 分類検索システム 高度検索テスト開始 ===")
    
    # データベース初期化
    db = ClassificationDatabase()
    db.load_data()
    
    # テストケース
    test_cases = [
        {
            "name": "AND検索テスト",
            "query": "画像 AND 形成",
            "expected_desc": "画像と形成の両方を含む分類"
        },
        {
            "name": "OR検索テスト", 
            "query": "トナー OR 現像剤",
            "expected_desc": "トナーまたは現像剤を含む分類"
        },
        {
            "name": "NEAR検索テスト",
            "query": "車 NEAR3 両",
            "expected_desc": "車と両が3語以内の距離にある分類"
        },
        {
            "name": "NOT検索テスト",
            "query": "レーザー NOT プリンター",
            "expected_desc": "レーザーを含むがプリンターを含まない分類"
        },
        {
            "name": "シンプル検索テスト",
            "query": "電子写真",
            "expected_desc": "電子写真を含む分類"
        }
    ]
    
    # 各テストケースを実行
    for test_case in test_cases:
        logger.info(f"\n--- {test_case['name']} ---")
        logger.info(f"クエリ: '{test_case['query']}'")
        logger.info(f"期待される結果: {test_case['expected_desc']}")
        
        try:
            results = db.search_by_keyword(
                keyword=test_case['query'],
                systems=['IPC', 'FI', 'CPC'],
                limit=5,
                include_hierarchy=True
            )
            
            logger.info(f"検索結果: {len(results)}件")
            
            # 上位3件の結果を表示
            for i, result in enumerate(results[:3]):
                logger.info(f"  {i+1}. {result['classification_system']} {result['code']}")
                logger.info(f"     日本語: {result.get('title_ja', 'N/A')}")
                logger.info(f"     英語: {result.get('title_en', 'N/A')}")
                logger.info(f"     スコア: {result.get('match_score', 0):.2f}")
                logger.info(f"     文書数: {result.get('num_documents', 0)}")
                
                # 階層情報の表示
                if result.get('hierarchy_path'):
                    path = " → ".join([h['code'] for h in result['hierarchy_path']])
                    logger.info(f"     階層パス: {path}")
                
                if result.get('child_classifications'):
                    child_codes = [c['code'] for c in result['child_classifications'][:3]]
                    logger.info(f"     下位分類: {', '.join(child_codes)}")
                
                logger.info("")
                
        except Exception as e:
            logger.error(f"  エラー: {e}")
    
    logger.info("=== 高度検索テスト完了 ===")

def test_hierarchy_search():
    """階層検索のテスト"""
    logger.info("\n=== 階層検索テスト開始 ===")
    
    db = ClassificationDatabase()
    db.load_data()
    
    # 階層検索テストケース
    hierarchy_tests = [
        {"code": "A01D", "system": "IPC"},
        {"code": "G03G", "system": "IPC"},
        {"code": "A01D34/13", "system": "FI"}
    ]
    
    for test in hierarchy_tests:
        logger.info(f"\n--- 階層検索: {test['system']} {test['code']} ---")
        
        try:
            hierarchy = db.get_hierarchical_info(
                code=test['code'],
                system=test['system'],
                include_parents=True,
                include_children=True
            )
            
            if hierarchy['current']:
                current = hierarchy['current']
                logger.info(f"現在の分類: {current['code']}")
                logger.info(f"  日本語: {current.get('title_ja', 'N/A')}")
                logger.info(f"  英語: {current.get('title_en', 'N/A')}")
                logger.info(f"  文書数: {current.get('num_documents', 0)}")
            
            if hierarchy['parents']:
                logger.info(f"上位分類: {len(hierarchy['parents'])}件")
                for parent in hierarchy['parents'][:3]:
                    logger.info(f"  {parent['code']}: {parent.get('title_ja', parent.get('title_en', 'N/A'))}")
            
            if hierarchy['children']:
                logger.info(f"下位分類: {len(hierarchy['children'])}件")
                for child in hierarchy['children'][:5]:
                    logger.info(f"  {child['code']}: {child.get('title_ja', child.get('title_en', 'N/A'))}")
                    
        except Exception as e:
            logger.error(f"  エラー: {e}")
    
    logger.info("=== 階層検索テスト完了 ===")

if __name__ == "__main__":
    test_advanced_search()
    test_hierarchy_search()