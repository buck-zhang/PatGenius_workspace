#!/usr/bin/env python3
"""
PatGenius API テストスクリプト
"""

import requests
import json
import time
from typing import Dict, Any

class APITester:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.session = requests.Session()
    
    def test_health(self) -> bool:
        """ヘルスチェックテスト"""
        print("🏥 ヘルスチェックテスト...")
        try:
            response = self.session.get(f"{self.base_url}/health")
            if response.status_code == 200:
                data = response.json()
                print(f"✅ API健康状態: {data['status']}")
                print(f"   OpenSearch状態: {data['opensearch_status']}")
                return True
            else:
                print(f"❌ ヘルスチェック失敗: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ ヘルスチェックエラー: {e}")
            return False
    
    def test_stats(self) -> bool:
        """統計情報テスト"""
        print("\n📊 統計情報テスト...")
        try:
            response = self.session.get(f"{self.base_url}/stats")
            if response.status_code == 200:
                data = response.json()
                print(f"✅ 総文書数: {data['total_documents']:,}")
                print(f"   インデックスサイズ: {data['index_size']:,} bytes")
                return True
            else:
                print(f"❌ 統計取得失敗: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ 統計取得エラー: {e}")
            return False
    
    def test_fields(self) -> bool:
        """フィールド情報テスト"""
        print("\n🏷️  フィールド情報テスト...")
        try:
            response = self.session.get(f"{self.base_url}/fields")
            if response.status_code == 200:
                data = response.json()
                fields = data['searchable_fields']
                print(f"✅ 検索可能フィールド数: {len(fields)}")
                for field, desc in list(fields.items())[:5]:
                    print(f"   {field}: {desc}")
                print("   ...")
                return True
            else:
                print(f"❌ フィールド取得失敗: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ フィールド取得エラー: {e}")
            return False
    
    def test_simple_search(self) -> bool:
        """シンプル検索テスト"""
        print("\n🔍 シンプル検索テスト...")
        
        test_queries = [
            {"q": "画像形成装置", "description": "発明名称検索"},
            {"q": "電子写真", "field": "technical_field", "description": "技術分野検索"},
            {"q": "バリカン", "description": "全文検索"}
        ]
        
        success_count = 0
        for query in test_queries:
            try:
                params = {"q": query["q"]}
                if "field" in query:
                    params["field"] = query["field"]
                
                start_time = time.time()
                response = self.session.get(f"{self.base_url}/search", params=params)
                end_time = time.time()
                
                if response.status_code == 200:
                    data = response.json()
                    print(f"✅ {query['description']}: {data['total']}件 ({end_time-start_time:.2f}s)")
                    if data['hits']:
                        hit = data['hits'][0]
                        print(f"   例: {hit.get('invention_title', 'N/A')[:50]}...")
                    success_count += 1
                else:
                    print(f"❌ {query['description']} 失敗: {response.status_code}")
            except Exception as e:
                print(f"❌ {query['description']} エラー: {e}")
        
        return success_count == len(test_queries)
    
    def test_advanced_search(self) -> bool:
        """高度検索テスト"""
        print("\n🔬 高度検索テスト...")
        
        try:
            payload = {
                "query": "現像剤",
                "field": "invention_title",
                "size": 5,
                "from": 0,
                "sort_field": "_score",
                "sort_order": "desc"
            }
            
            start_time = time.time()
            response = self.session.post(
                f"{self.base_url}/search/advanced",
                json=payload,
                headers={'Content-Type': 'application/json'}
            )
            end_time = time.time()
            
            if response.status_code == 200:
                data = response.json()
                print(f"✅ 高度検索: {data['total']}件 ({end_time-start_time:.2f}s)")
                print(f"   検索時間: {data['took']}ms")
                return True
            else:
                print(f"❌ 高度検索失敗: {response.status_code}")
                print(f"   レスポンス: {response.text}")
                return False
        except Exception as e:
            print(f"❌ 高度検索エラー: {e}")
            return False
    
    def test_document_retrieval(self) -> bool:
        """文書取得テスト"""
        print("\n📄 文書取得テスト...")
        
        # まず検索で文書IDを取得
        try:
            response = self.session.get(f"{self.base_url}/search", params={"q": "バリカン", "size": 1})
            if response.status_code != 200:
                print("❌ 文書ID取得用検索失敗")
                return False
            
            search_data = response.json()
            if not search_data['hits']:
                print("❌ 検索結果が空")
                return False
            
            document_id = search_data['hits'][0].get('document_id')
            if not document_id:
                print("❌ 文書IDが見つからない")
                return False
            
            # 文書詳細取得
            response = self.session.get(f"{self.base_url}/document/{document_id}")
            if response.status_code == 200:
                data = response.json()
                print(f"✅ 文書取得成功: {document_id}")
                print(f"   発明名称: {data.get('invention_title', 'N/A')}")
                return True
            else:
                print(f"❌ 文書取得失敗: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ 文書取得エラー: {e}")
            return False
    
    def test_suggestions(self) -> bool:
        """サジェスト機能テスト"""
        print("\n💡 サジェスト機能テスト...")
        
        try:
            response = self.session.get(
                f"{self.base_url}/search/suggest",
                params={"q": "画像", "field": "invention_title"}
            )
            
            if response.status_code == 200:
                data = response.json()
                print(f"✅ サジェスト取得成功")
                suggestions = data.get('suggestions', [])
                if suggestions:
                    print(f"   候補数: {len(suggestions)}")
                    for suggestion in suggestions[:3]:
                        print(f"   - {suggestion['text']} (score: {suggestion['score']:.2f})")
                else:
                    print("   候補なし")
                return True
            else:
                print(f"❌ サジェスト取得失敗: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ サジェストエラー: {e}")
            return False
    
    def run_all_tests(self) -> bool:
        """全テスト実行"""
        print("🚀 PatGenius API 総合テスト開始\n")
        
        tests = [
            ("ヘルスチェック", self.test_health),
            ("統計情報", self.test_stats),
            ("フィールド情報", self.test_fields),
            ("シンプル検索", self.test_simple_search),
            ("高度検索", self.test_advanced_search),
            ("文書取得", self.test_document_retrieval),
            ("サジェスト機能", self.test_suggestions)
        ]
        
        passed = 0
        total = len(tests)
        
        for test_name, test_func in tests:
            try:
                if test_func():
                    passed += 1
            except Exception as e:
                print(f"❌ {test_name} で予期しないエラー: {e}")
        
        print(f"\n📋 テスト結果: {passed}/{total} 通過")
        
        if passed == total:
            print("🎉 全テスト通過！APIは正常に動作しています。")
            return True
        else:
            print("⚠️  一部テストが失敗しました。")
            return False

def main():
    """メイン関数"""
    tester = APITester()
    
    print("PatGenius API テストツール")
    print("=" * 50)
    
    # APIサーバーの起動チェック
    try:
        response = requests.get("http://localhost:8000/", timeout=5)
        if response.status_code != 200:
            print("❌ APIサーバーが起動していません。")
            print("   python patent_search_api.py を実行してください。")
            return
    except requests.exceptions.RequestException:
        print("❌ APIサーバーに接続できません。")
        print("   http://localhost:8000 でサーバーが起動していることを確認してください。")
        return
    
    # 全テスト実行
    success = tester.run_all_tests()
    
    if success:
        print("\n🔗 API利用可能:")
        print("   - Swagger UI: http://localhost:8000/docs")
        print("   - ReDoc: http://localhost:8000/redoc")
        print("   - API Root: http://localhost:8000/")
    
    return success

if __name__ == "__main__":
    main()