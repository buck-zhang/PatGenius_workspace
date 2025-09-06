#!/usr/bin/env python3
"""
PatGenius API 検索実例デモ
様々な検索パターンを実演するスクリプト
"""

import requests
import json
import time
from typing import Dict, Any, List

class PatentSearchDemo:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.session = requests.Session()
    
    def print_separator(self, title: str):
        """セクション区切り表示"""
        print("\n" + "="*60)
        print(f"🔍 {title}")
        print("="*60)
    
    def print_results(self, data: Dict[str, Any], max_results: int = 3):
        """検索結果の整形表示"""
        print(f"📊 総件数: {data['total']:,}件")
        print(f"⏱️  検索時間: {data['took']}ms")
        
        if data['hits']:
            print(f"\n📄 上位{min(len(data['hits']), max_results)}件:")
            for i, hit in enumerate(data['hits'][:max_results], 1):
                print(f"\n{i}. 【{hit.get('document_id', 'N/A')}】")
                print(f"   発明名称: {hit.get('invention_title', 'N/A')[:80]}...")
                print(f"   出願人: {hit.get('applicant_name', 'N/A')[:50]}")
                if hit.get('technical_field'):
                    print(f"   技術分野: {hit.get('technical_field', '')[:100]}...")
        else:
            print("❌ 検索結果なし")
    
    def simple_search_demo(self):
        """シンプル検索のデモ"""
        self.print_separator("シンプル検索デモ")
        
        # 1. 発明名称での検索
        print("\n1️⃣ 発明名称での検索例")
        examples = [
            {"q": "画像形成装置", "description": "画像形成装置関連特許"},
            {"q": "バリカン", "description": "バリカン式刈刃装置"},
            {"q": "現像剤", "description": "現像剤関連技術"}
        ]
        
        for example in examples:
            print(f"\n🔎 検索: {example['description']}")
            try:
                response = self.session.get(
                    f"{self.base_url}/search",
                    params={"q": example["q"], "size": 3}
                )
                if response.status_code == 200:
                    data = response.json()
                    self.print_results(data)
                else:
                    print(f"❌ エラー: {response.status_code}")
                time.sleep(1)
            except Exception as e:
                print(f"❌ 接続エラー: {e}")
    
    def field_search_demo(self):
        """フィールド指定検索のデモ"""
        self.print_separator("フィールド指定検索デモ")
        
        field_examples = [
            {"q": "電子写真", "field": "technical_field", "desc": "技術分野から検索"},
            {"q": "京セラミタ", "field": "applicant_name", "desc": "出願人名から検索"},
            {"q": "G03G", "field": "classification_ipc", "desc": "IPC分類から検索"},
            {"q": "トナー", "field": "claims", "desc": "請求項から検索"}
        ]
        
        for example in field_examples:
            print(f"\n🎯 {example['desc']}: {example['q']}")
            try:
                response = self.session.get(
                    f"{self.base_url}/search",
                    params={
                        "q": example["q"],
                        "field": example["field"],
                        "size": 2
                    }
                )
                if response.status_code == 200:
                    data = response.json()
                    self.print_results(data, 2)
                else:
                    print(f"❌ エラー: {response.status_code}")
                time.sleep(1)
            except Exception as e:
                print(f"❌ 接続エラー: {e}")
    
    def advanced_search_demo(self):
        """高度検索のデモ"""
        self.print_separator("高度検索デモ (POST)")
        
        advanced_examples = [
            {
                "query": "印刷",
                "field": "invention_title",
                "size": 3,
                "sort_field": "_score",
                "sort_order": "desc",
                "desc": "発明名称で印刷関連をスコア順"
            },
            {
                "query": "センサ",
                "field": "abstract",
                "size": 2,
                "sort_field": "document_id",
                "sort_order": "asc",
                "desc": "要約でセンサ関連を文献番号順"
            }
        ]
        
        for example in advanced_examples:
            print(f"\n🔬 {example['desc']}")
            try:
                response = self.session.post(
                    f"{self.base_url}/search/advanced",
                    json=example,
                    headers={'Content-Type': 'application/json'}
                )
                if response.status_code == 200:
                    data = response.json()
                    self.print_results(data, 2)
                else:
                    print(f"❌ エラー: {response.status_code}")
                time.sleep(1)
            except Exception as e:
                print(f"❌ 接続エラー: {e}")
    
    def document_detail_demo(self):
        """文書詳細取得のデモ"""
        self.print_separator("文書詳細取得デモ")
        
        # まず検索で文書IDを取得
        print("🔍 バリカンで検索して文書IDを取得...")
        try:
            response = self.session.get(
                f"{self.base_url}/search",
                params={"q": "バリカン", "size": 1}
            )
            
            if response.status_code == 200:
                data = response.json()
                if data['hits']:
                    doc_id = data['hits'][0].get('document_id')
                    print(f"📄 文書ID: {doc_id}")
                    
                    # 文書詳細を取得
                    print(f"\n📋 文書詳細を取得中...")
                    detail_response = self.session.get(f"{self.base_url}/document/{doc_id}")
                    
                    if detail_response.status_code == 200:
                        detail_data = detail_response.json()
                        self.print_document_detail(detail_data)
                    else:
                        print(f"❌ 詳細取得エラー: {detail_response.status_code}")
                else:
                    print("❌ 検索結果が空です")
        except Exception as e:
            print(f"❌ エラー: {e}")
    
    def print_document_detail(self, doc: Dict[str, Any]):
        """文書詳細の表示"""
        print(f"\n📖 特許文書詳細")
        print(f"文献番号: {doc.get('document_id', 'N/A')}")
        print(f"発明名称: {doc.get('invention_title', 'N/A')}")
        print(f"出願人: {doc.get('applicant_name', 'N/A')}")
        print(f"発明者: {doc.get('inventor_names', 'N/A')}")
        
        if doc.get('classification_ipc'):
            print(f"IPC分類: {', '.join(doc['classification_ipc'][:3])}")
        
        if doc.get('technical_field'):
            print(f"技術分野: {doc['technical_field'][:200]}...")
        
        if doc.get('abstract'):
            print(f"要約: {doc['abstract'][:300]}...")
    
    def pagination_demo(self):
        """ページネーション検索のデモ"""
        self.print_separator("ページネーション検索デモ")
        
        query = "装置"
        page_size = 2
        
        print(f"🔍 '{query}' の検索結果をページごとに表示")
        
        # 最初のページ
        for page in range(3):
            from_pos = page * page_size
            print(f"\n📄 ページ {page + 1} (位置 {from_pos + 1}-{from_pos + page_size})")
            
            try:
                response = self.session.get(
                    f"{self.base_url}/search",
                    params={
                        "q": query,
                        "size": page_size,
                        "from": from_pos
                    }
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if data['hits']:
                        for i, hit in enumerate(data['hits'], from_pos + 1):
                            print(f"{i}. {hit.get('invention_title', 'N/A')[:60]}...")
                    else:
                        print("   結果なし")
                time.sleep(0.5)
            except Exception as e:
                print(f"❌ エラー: {e}")
    
    def stats_demo(self):
        """統計情報とフィールド情報のデモ"""
        self.print_separator("システム情報デモ")
        
        # 統計情報
        print("📊 インデックス統計:")
        try:
            response = self.session.get(f"{self.base_url}/stats")
            if response.status_code == 200:
                stats = response.json()
                print(f"   総文書数: {stats.get('total_documents', 'N/A'):,}件")
                print(f"   インデックス名: {stats.get('index_name', 'N/A')}")
            else:
                print(f"   ❌ 統計取得エラー: {response.status_code}")
        except Exception as e:
            print(f"   ❌ エラー: {e}")
        
        # フィールド情報
        print("\n🏷️ 検索可能フィールド:")
        try:
            response = self.session.get(f"{self.base_url}/fields")
            if response.status_code == 200:
                fields_data = response.json()
                fields = fields_data.get('searchable_fields', {})
                for field, desc in list(fields.items())[:8]:
                    print(f"   {field}: {desc}")
                print(f"   ... 他{len(fields)-8}フィールド")
            else:
                print(f"   ❌ フィールド取得エラー: {response.status_code}")
        except Exception as e:
            print(f"   ❌ エラー: {e}")
    
    def performance_demo(self):
        """検索パフォーマンスのデモ"""
        self.print_separator("検索パフォーマンステスト")
        
        test_queries = ["装置", "方法", "システム", "技術", "発明"]
        
        print("⚡ 複数クエリの検索速度測定:")
        total_time = 0
        successful_queries = 0
        
        for i, query in enumerate(test_queries, 1):
            try:
                start_time = time.time()
                response = self.session.get(
                    f"{self.base_url}/search",
                    params={"q": query, "size": 5}
                )
                end_time = time.time()
                
                if response.status_code == 200:
                    data = response.json()
                    search_time = end_time - start_time
                    total_time += search_time
                    successful_queries += 1
                    
                    print(f"{i}. '{query}': {data['total']:,}件 "
                          f"({search_time*1000:.1f}ms, 内部:{data['took']}ms)")
                else:
                    print(f"{i}. '{query}': ❌ エラー {response.status_code}")
                
                time.sleep(0.2)
            except Exception as e:
                print(f"{i}. '{query}': ❌ {e}")
        
        if successful_queries > 0:
            avg_time = total_time / successful_queries
            print(f"\n📈 平均検索時間: {avg_time*1000:.1f}ms")
            print(f"✅ 成功率: {successful_queries}/{len(test_queries)}")
    
    def run_all_demos(self):
        """全デモの実行"""
        print("🚀 PatGenius API 検索実例デモ開始")
        print("API URL:", self.base_url)
        
        # APIサーバーの接続確認
        try:
            response = self.session.get(f"{self.base_url}/health", timeout=5)
            if response.status_code == 200:
                health = response.json()
                print(f"✅ API Status: {health.get('status', 'unknown')}")
            else:
                print("❌ APIサーバーが応答しません")
                return False
        except Exception as e:
            print(f"❌ API接続エラー: {e}")
            print("   python3 -m uvicorn patent_search_api:app --reload でAPIを起動してください")
            return False
        
        # 各デモを順次実行
        demos = [
            ("システム情報", self.stats_demo),
            ("シンプル検索", self.simple_search_demo),
            ("フィールド指定検索", self.field_search_demo),
            ("高度検索", self.advanced_search_demo),
            ("文書詳細取得", self.document_detail_demo),
            ("ページネーション", self.pagination_demo),
            ("パフォーマンステスト", self.performance_demo)
        ]
        
        for demo_name, demo_func in demos:
            try:
                demo_func()
                time.sleep(2)  # デモ間の間隔
            except KeyboardInterrupt:
                print(f"\n\n⏹️  デモを中断しました")
                break
            except Exception as e:
                print(f"\n❌ {demo_name}でエラー: {e}")
                continue
        
        print("\n" + "="*60)
        print("🎉 検索実例デモ完了！")
        print("💡 詳細なAPI仕様: http://localhost:8000/docs")
        print("="*60)
        
        return True

def main():
    """メイン関数"""
    demo = PatentSearchDemo()
    
    print("PatGenius API 検索実例デモツール")
    print("=" * 50)
    
    # 全デモ実行
    demo.run_all_demos()

if __name__ == "__main__":
    main()