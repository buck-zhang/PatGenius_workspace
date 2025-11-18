"""
特許検索システム - 完全な使用例
Classification API と Google Patents API の両方を使用した実践的なサンプル
"""

import requests
import json
from typing import Dict, Any, List


class PatentSearchClient:
    """統合特許検索クライアント"""

    def __init__(self,
                 classification_api_url: str = "http://localhost:8000",
                 google_patents_api_url: str = "http://localhost:8001"):
        """
        初期化

        Args:
            classification_api_url: 特許分類API URL
            google_patents_api_url: Google Patents API URL
        """
        self.classification_url = classification_api_url.rstrip('/')
        self.google_patents_url = google_patents_api_url.rstrip('/')

    def search_classification(self,
                            query: str,
                            classification_type: str = "all",
                            top_k: int = 10) -> Dict[str, Any]:
        """
        特許分類検索（IPC/CPC/FI）

        Args:
            query: 検索キーワード
            classification_type: 分類タイプ (ipc, cpc, fi, all)
            top_k: 結果数

        Returns:
            検索結果
        """
        url = f"{self.classification_url}/search/keyword"
        params = {
            "q": query,
            "classification_type": classification_type,
            "top_k": top_k
        }

        try:
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"error": str(e), "results": []}

    def search_google_patents(self,
                             query: str,
                             max_results: int = 10) -> Dict[str, Any]:
        """
        Google Patents検索

        Args:
            query: 検索クエリ
            max_results: 最大結果数

        Returns:
            検索結果
        """
        url = f"{self.google_patents_url}/search/simple"
        params = {
            "q": query,
            "max_results": max_results
        }

        try:
            response = requests.get(url, params=params, timeout=60)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"error": str(e), "patents": [], "cpc_ranking": []}

    def get_cpc_ranking(self, query: str, max_results: int = 100, top_k: int = 15):
        """
        CPC ランキング取得

        Args:
            query: 検索クエリ
            max_results: 分析する結果数
            top_k: 上位K個のCPCコード

        Returns:
            CPCランキング
        """
        url = f"{self.google_patents_url}/cpc_ranking"
        params = {
            "q": query,
            "max_results": max_results,
            "top_k": top_k
        }

        try:
            response = requests.get(url, params=params, timeout=60)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"error": str(e), "cpc_ranking": []}


def print_separator(title: str = ""):
    """セパレーター表示"""
    print("\n" + "="*80)
    if title:
        print(f"{title:^80}")
        print("="*80)


def print_classification_results(results: Dict[str, Any]):
    """特許分類検索結果を表示"""
    print_separator("特許分類検索結果 (IPC/CPC/FI)")

    if "error" in results:
        print(f"❌ エラー: {results['error']}")
        return

    print(f"\n検索クエリ: {results.get('query', 'N/A')}")
    print(f"分類タイプ: {results.get('classification_type', 'N/A')}")
    print(f"結果件数: {results.get('count', 0)}")

    classifications = results.get('results', [])

    if not classifications:
        print("\n結果が見つかりませんでした。")
        return

    print(f"\n📋 分類コード一覧 (上位{min(10, len(classifications))}件)")
    print(f"{'No.':<5} {'コード':<15} {'分類':<8} {'スコア':<8} {'タイトル（日本語）'}")
    print("-" * 80)

    for i, item in enumerate(classifications[:10], 1):
        code = item.get('code', 'N/A')
        classification_type = item.get('classification_type', 'N/A')
        score = item.get('score', 0.0)
        title_ja = item.get('title_ja', '')[:40]

        print(f"{i:<5} {code:<15} {classification_type:<8} {score:<8.4f} {title_ja}")


def print_google_patents_results(results: Dict[str, Any]):
    """Google Patents検索結果を表示"""
    print_separator("Google Patents 検索結果")

    if "error" in results:
        print(f"❌ エラー: {results['error']}")
        print(f"ℹ️  Google Patents APIが起動していない可能性があります")
        print(f"   ./start_google_patents_api.sh で起動してください")
        return

    print(f"\n検索クエリ: {results.get('query', 'N/A')}")
    print(f"総ヒット数: {results.get('total_hits', 0):,}")
    print(f"取得結果数: {results.get('results_count', 0)}")

    # CPC ランキング
    cpc_ranking = results.get('cpc_ranking', [])
    if cpc_ranking:
        print(f"\n🏆 CPC コードランキング (上位{min(10, len(cpc_ranking))}件)")
        print(f"{'No.':<5} {'CPCコード':<15} {'件数':<8} {'割合':<10} {'バー'}")
        print("-" * 80)

        for i, cpc in enumerate(cpc_ranking[:10], 1):
            code = cpc.get('cpc_code', 'N/A')
            count = cpc.get('count', 0)
            percentage = cpc.get('percentage', 0.0)
            bar = "█" * int(percentage / 10)

            print(f"{i:<5} {code:<15} {count:<8} {percentage:>5.1f}%     {bar}")

    # 特許詳細
    patents = results.get('patents', [])
    if patents:
        print(f"\n📄 特許詳細 (上位{min(5, len(patents))}件)")
        print("-" * 80)

        for i, patent in enumerate(patents[:5], 1):
            print(f"\n{i}. {patent.get('patent_number', 'N/A')}")
            print(f"   タイトル: {patent.get('title', 'N/A')[:70]}...")
            print(f"   出願人: {patent.get('assignee', 'N/A')}")
            print(f"   公開日: {patent.get('publication_date', 'N/A')}")

            cpc_codes = patent.get('cpc_codes', [])
            if cpc_codes:
                print(f"   CPC: {', '.join(cpc_codes[:5])}")

            print(f"   URL: {patent.get('url', 'N/A')}")


def print_cpc_ranking_only(results: Dict[str, Any]):
    """CPC ランキングのみ表示"""
    print_separator("CPC コード詳細ランキング")

    if "error" in results:
        print(f"❌ エラー: {results['error']}")
        return

    print(f"\n検索クエリ: {results.get('query', 'N/A')}")
    print(f"総ヒット数: {results.get('total_hits', 0):,}")
    print(f"分析した結果数: {results.get('results_analyzed', 0)}")

    cpc_ranking = results.get('cpc_ranking', [])

    if not cpc_ranking:
        print("\nCPCランキングが見つかりませんでした。")
        return

    print(f"\n🏆 上位{len(cpc_ranking)}件のCPCコード")
    print(f"{'順位':<6} {'CPCコード':<15} {'件数':<8} {'割合':<10} {'視覚化'}")
    print("-" * 80)

    for i, cpc in enumerate(cpc_ranking, 1):
        code = cpc.get('cpc_code', 'N/A')
        count = cpc.get('count', 0)
        percentage = cpc.get('percentage', 0.0)
        bar = "█" * int(percentage / 5)  # 5%ごとに1つのブロック

        print(f"{i:<6} {code:<15} {count:<8} {percentage:>5.1f}%     {bar}")


# =============================================================================
# サンプル実行
# =============================================================================

def sample_1_classification_search():
    """サンプル1: 特許分類検索（IPC/CPC/FI）"""
    print_separator("サンプル1: 特許分類検索")

    client = PatentSearchClient()

    # 農業関連の特許分類を検索
    print("\n🔍 検索キーワード: 'agriculture'")
    results = client.search_classification(
        query="agriculture",
        classification_type="all",
        top_k=15
    )

    print_classification_results(results)


def sample_2_google_patents_search():
    """サンプル2: Google Patents検索"""
    print_separator("サンプル2: Google Patents検索")

    client = PatentSearchClient()

    # Google Patentsで農業特許を検索
    print("\n🔍 検索クエリ: 'agriculture AND soil'")
    results = client.search_google_patents(
        query="agriculture AND soil",
        max_results=10
    )

    print_google_patents_results(results)


def sample_3_cpc_ranking():
    """サンプル3: CPC ランキング分析"""
    print_separator("サンプル3: CPC ランキング分析")

    client = PatentSearchClient()

    # より多くの特許を分析してCPCランキングを取得
    print("\n🔍 検索クエリ: 'agriculture'")
    print("📊 100件の特許を分析してCPCランキングを生成...")

    results = client.get_cpc_ranking(
        query="agriculture",
        max_results=100,
        top_k=15
    )

    print_cpc_ranking_only(results)


def sample_4_combined_search():
    """サンプル4: 統合検索（両方のAPIを使用）"""
    print_separator("サンプル4: 統合検索")

    client = PatentSearchClient()
    query = "agriculture"

    print(f"\n🔍 検索キーワード/クエリ: '{query}'")
    print("\n両方のAPIで並行して検索中...")

    # 1. 特許分類検索
    print("\n1️⃣ 特許分類検索 (IPC/CPC/FI)...")
    classification_results = client.search_classification(
        query=query,
        classification_type="all",
        top_k=10
    )

    # 2. Google Patents検索
    print("2️⃣ Google Patents検索...")
    patents_results = client.search_google_patents(
        query=query,
        max_results=10
    )

    # 結果表示
    print_classification_results(classification_results)
    print_google_patents_results(patents_results)

    # まとめ
    print_separator("検索サマリー")

    classification_count = classification_results.get('count', 0)
    patents_count = patents_results.get('results_count', 0)
    total_hits = patents_results.get('total_hits', 0)

    print(f"\n✅ 特許分類検索: {classification_count}件の分類コードを発見")
    print(f"✅ Google Patents: {patents_count}件の特許を取得（総ヒット: {total_hits:,}件）")

    # トップCPCコードを抽出
    cpc_ranking = patents_results.get('cpc_ranking', [])[:3]
    if cpc_ranking:
        print(f"\n🏆 最も関連性の高いCPCコード（トップ3）:")
        for i, cpc in enumerate(cpc_ranking, 1):
            print(f"   {i}. {cpc.get('cpc_code')} - {cpc.get('count')}件 ({cpc.get('percentage')}%)")


def main():
    """メイン実行関数"""
    print("\n" + "="*80)
    print(" "*20 + "特許検索システム - 使用例デモ")
    print("="*80)

    print("\n利用可能なサンプル:")
    print("  1. 特許分類検索 (IPC/CPC/FI)")
    print("  2. Google Patents検索")
    print("  3. CPC ランキング分析")
    print("  4. 統合検索（両方のAPI）")

    samples = [
        sample_1_classification_search,
        sample_2_google_patents_search,
        sample_3_cpc_ranking,
        sample_4_combined_search
    ]

    print("\n📝 注意:")
    print("  - Classification API (ポート8000) が起動している必要があります")
    print("  - Google Patents API (ポート8001) が起動している必要があります")
    print("  - 起動コマンド: ./start_google_patents_api.sh")

    print("\n" + "-"*80)
    print("すべてのサンプルを実行します...")
    print("-"*80)

    for i, sample in enumerate(samples, 1):
        try:
            sample()
        except Exception as e:
            print(f"\n❌ サンプル{i}でエラーが発生: {e}")

    print_separator("全サンプル実行完了")

    print("\n✅ すべてのサンプルが完了しました！")
    print("\n💡 ヒント:")
    print("  - 各関数を個別に実行することもできます")
    print("  - client = PatentSearchClient() でクライアントを作成")
    print("  - client.search_classification('your query') で検索実行")


if __name__ == "__main__":
    main()
