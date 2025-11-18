"""
検索履歴学習モジュール
Search History Learning Module

過去の検索履歴から学習し、最適なパラメータを推奨します。
"""

from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class SearchSession:
    """検索セッションの記録"""
    session_id: str
    target_patent_id: str
    timestamp: datetime

    # 検索パラメータ
    strategy_used: str
    classification_level: int
    keyword_level: int
    cross_logic: str

    # 入力データ
    num_classifications: int
    num_keywords: int
    num_components: int

    # 検索結果
    total_hits: int
    relevant_hits: int = 0
    precision: float = 0.0
    recall: float = 0.0

    # ユーザーフィードバック
    user_satisfaction: Optional[int] = None  # 1-5
    selected_patents: List[str] = field(default_factory=list)

    # 技術領域
    technical_domain: Optional[str] = None

    def to_dict(self) -> Dict:
        """辞書形式に変換"""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        return data

    @staticmethod
    def from_dict(data: Dict) -> 'SearchSession':
        """辞書から SearchSession を作成"""
        data['timestamp'] = datetime.fromisoformat(data['timestamp'])
        return SearchSession(**data)


class SearchHistoryDatabase:
    """検索履歴データベース"""

    def __init__(self, db_path: str = "data/search_history.json"):
        self.db_path = Path(db_path)
        self.sessions: List[SearchSession] = []
        self._load()

    def _load(self):
        """履歴をロード"""
        if self.db_path.exists():
            try:
                with open(self.db_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.sessions = [SearchSession.from_dict(s) for s in data]
                logger.info(f"Loaded {len(self.sessions)} search sessions from {self.db_path}")
            except Exception as e:
                logger.error(f"Error loading search history: {e}")
                self.sessions = []
        else:
            logger.info(f"No existing search history found at {self.db_path}")
            self.sessions = []

    def save(self):
        """履歴を保存"""
        try:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.db_path, 'w', encoding='utf-8') as f:
                data = [s.to_dict() for s in self.sessions]
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.info(f"Saved {len(self.sessions)} search sessions to {self.db_path}")
        except Exception as e:
            logger.error(f"Error saving search history: {e}")

    def add_session(self, session: SearchSession):
        """セッションを追加"""
        self.sessions.append(session)
        self.save()

    def get_sessions_by_strategy(self, strategy: str) -> List[SearchSession]:
        """戦略別のセッションを取得"""
        return [s for s in self.sessions if s.strategy_used == strategy]

    def get_sessions_by_domain(self, domain: str) -> List[SearchSession]:
        """技術領域別のセッションを取得"""
        return [s for s in self.sessions if s.technical_domain == domain]

    def get_recent_sessions(self, n: int = 10) -> List[SearchSession]:
        """最近のセッションを取得"""
        sorted_sessions = sorted(self.sessions, key=lambda s: s.timestamp, reverse=True)
        return sorted_sessions[:n]


class SearchHistoryLearner:
    """検索履歴から学習するクラス"""

    def __init__(self, db_path: str = "data/search_history.json"):
        self.db = SearchHistoryDatabase(db_path)
        self.strategy_stats: Dict[str, Dict[str, float]] = {}
        self.parameter_stats: Dict[str, Dict] = {}
        self._initialize_stats()

    def _initialize_stats(self):
        """統計情報を初期化"""
        if self.db.sessions:
            self._update_all_stats()

    def _update_all_stats(self):
        """全統計情報を更新"""
        self._update_strategy_success_rates()
        self._update_optimal_parameters()

    def learn_from_session(self, session: SearchSession):
        """
        検索セッションから学習

        Args:
            session: 検索セッション
        """
        # セッションを履歴に追加
        self.db.add_session(session)

        # 統計情報を更新
        self._update_strategy_success_rate(session)
        self._update_optimal_parameters_for_session(session)

        logger.info(f"Learned from session {session.session_id}: "
                   f"strategy={session.strategy_used}, hits={session.total_hits}")

    def _update_strategy_success_rates(self):
        """戦略ごとの成功率を更新"""
        strategies = set(s.strategy_used for s in self.db.sessions)

        for strategy in strategies:
            sessions = self.db.get_sessions_by_strategy(strategy)
            success_rate = self._calculate_success_rate(sessions)

            self.strategy_stats[strategy] = {
                "success_rate": success_rate,
                "total_sessions": len(sessions),
                "avg_hits": sum(s.total_hits for s in sessions) / len(sessions) if sessions else 0
            }

    def _update_strategy_success_rate(self, session: SearchSession):
        """単一セッションから戦略の成功率を更新"""
        strategy = session.strategy_used
        sessions = self.db.get_sessions_by_strategy(strategy)
        success_rate = self._calculate_success_rate(sessions)

        self.strategy_stats[strategy] = {
            "success_rate": success_rate,
            "total_sessions": len(sessions),
            "avg_hits": sum(s.total_hits for s in sessions) / len(sessions) if sessions else 0
        }

    def _calculate_success_rate(self, sessions: List[SearchSession]) -> float:
        """セッションリストから成功率を計算"""
        if not sessions:
            return 0.5  # デフォルト

        # F1スコアを計算（Precision と Recall の調和平均）
        f1_scores = []

        for s in sessions:
            if s.precision > 0 or s.recall > 0:
                f1 = 2 * (s.precision * s.recall) / (s.precision + s.recall) \
                    if (s.precision + s.recall) > 0 else 0
            else:
                # Precision/Recall が未設定の場合、ヒット数で評価
                # 目標範囲(10-300)内なら高スコア
                if 10 <= s.total_hits <= 300:
                    f1 = 0.8
                elif 1 <= s.total_hits < 10:
                    f1 = 0.5
                elif 300 < s.total_hits <= 1000:
                    f1 = 0.6
                else:
                    f1 = 0.3

            # ユーザー満足度が設定されている場合は反映
            if s.user_satisfaction is not None:
                user_factor = s.user_satisfaction / 5.0
                f1 = f1 * 0.7 + user_factor * 0.3

            f1_scores.append(f1)

        return sum(f1_scores) / len(f1_scores)

    def _update_optimal_parameters(self):
        """最適パラメータを更新"""
        # 技術領域ごとに最適パラメータを集計
        domains = set(s.technical_domain for s in self.db.sessions if s.technical_domain)

        for domain in domains:
            sessions = self.db.get_sessions_by_domain(domain)
            optimal_params = self._find_optimal_parameters(sessions)
            self.parameter_stats[domain] = optimal_params

    def _update_optimal_parameters_for_session(self, session: SearchSession):
        """単一セッションから最適パラメータを更新"""
        if session.technical_domain:
            sessions = self.db.get_sessions_by_domain(session.technical_domain)
            optimal_params = self._find_optimal_parameters(sessions)
            self.parameter_stats[session.technical_domain] = optimal_params

    def _find_optimal_parameters(self, sessions: List[SearchSession]) -> Dict[str, Any]:
        """セッションリストから最適パラメータを見つける"""
        if not sessions:
            return self._get_default_parameters()

        # 成功したセッション（ヒット数が目標範囲内）を抽出
        successful_sessions = [
            s for s in sessions
            if 10 <= s.total_hits <= 300
        ]

        if not successful_sessions:
            # 成功セッションがない場合は全体から
            successful_sessions = sessions

        # 各パラメータの頻度を集計
        classification_levels = [s.classification_level for s in successful_sessions]
        keyword_levels = [s.keyword_level for s in successful_sessions]
        strategies = [s.strategy_used for s in successful_sessions]

        return {
            "classification_level": self._most_common(classification_levels),
            "keyword_level": self._most_common(keyword_levels),
            "strategy": self._most_common(strategies),
            "confidence": len(successful_sessions) / len(sessions),
            "based_on_sessions": len(successful_sessions)
        }

    def _most_common(self, items: List[Any]) -> Any:
        """最頻値を取得"""
        if not items:
            return None
        return max(set(items), key=items.count)

    def _get_default_parameters(self) -> Dict[str, Any]:
        """デフォルトパラメータを取得"""
        return {
            "classification_level": 2,
            "keyword_level": 2,
            "strategy": "hybrid_balanced",
            "confidence": 0.5,
            "based_on_sessions": 0
        }

    def recommend_parameters(self,
                            technical_domain: Optional[str] = None,
                            num_classifications: int = 0,
                            num_keywords: int = 0) -> Dict[str, Any]:
        """
        最適なパラメータを推奨

        Args:
            technical_domain: 技術領域
            num_classifications: 分類コード数
            num_keywords: キーワード数

        Returns:
            推奨パラメータ辞書
        """
        # 技術領域が指定されている場合、その領域の最適パラメータを使用
        if technical_domain and technical_domain in self.parameter_stats:
            params = self.parameter_stats[technical_domain].copy()
            logger.info(f"Using learned parameters for domain {technical_domain}: {params}")
            return params

        # 技術領域が不明、または履歴がない場合は、全体の傾向から推奨
        if self.db.sessions:
            all_params = self._find_optimal_parameters(self.db.sessions)
            logger.info(f"Using learned parameters from all sessions: {all_params}")
            return all_params

        # 履歴がない場合はデフォルト
        default_params = self._get_default_parameters()
        logger.info(f"No learning history, using default parameters: {default_params}")
        return default_params

    def get_strategy_success_rate(self, strategy: str) -> float:
        """
        戦略の過去の成功率を取得

        Args:
            strategy: 戦略名

        Returns:
            成功率 (0-1)
        """
        if strategy in self.strategy_stats:
            return self.strategy_stats[strategy]["success_rate"]
        else:
            return 0.5  # デフォルト

    def get_strategy_stats(self, strategy: str) -> Dict[str, Any]:
        """
        戦略の統計情報を取得

        Args:
            strategy: 戦略名

        Returns:
            統計情報辞書
        """
        return self.strategy_stats.get(strategy, {
            "success_rate": 0.5,
            "total_sessions": 0,
            "avg_hits": 0
        })

    def find_similar_sessions(self,
                             num_classifications: int,
                             num_keywords: int,
                             technical_domain: Optional[str] = None,
                             top_n: int = 5) -> List[SearchSession]:
        """
        類似したセッションを検索

        Args:
            num_classifications: 分類コード数
            num_keywords: キーワード数
            technical_domain: 技術領域
            top_n: 上位N件を返す

        Returns:
            類似セッションのリスト
        """
        # 技術領域が一致するセッションを優先
        if technical_domain:
            domain_sessions = self.db.get_sessions_by_domain(technical_domain)
            if domain_sessions:
                return sorted(
                    domain_sessions,
                    key=lambda s: abs(s.num_classifications - num_classifications) +
                                 abs(s.num_keywords - num_keywords)
                )[:top_n]

        # 技術領域が不明、または一致するセッションがない場合は全体から
        return sorted(
            self.db.sessions,
            key=lambda s: abs(s.num_classifications - num_classifications) +
                         abs(s.num_keywords - num_keywords)
        )[:top_n]

    def get_learning_summary(self) -> Dict[str, Any]:
        """
        学習状況のサマリーを取得

        Returns:
            学習サマリー辞書
        """
        return {
            "total_sessions": len(self.db.sessions),
            "strategies_learned": list(self.strategy_stats.keys()),
            "domains_learned": list(self.parameter_stats.keys()),
            "strategy_stats": self.strategy_stats,
            "recent_sessions": len(self.db.get_recent_sessions(10))
        }


# テスト用のコード
if __name__ == "__main__":
    print("=" * 80)
    print("検索履歴学習機能のテスト")
    print("=" * 80)

    # 学習エンジンを作成
    learner = SearchHistoryLearner("data/test_search_history.json")

    # テストセッションを作成
    print("\n【テスト1】検索セッションの記録と学習")
    print("-" * 80)

    test_sessions = [
        SearchSession(
            session_id="test_001",
            target_patent_id="JP2014007731A",
            timestamp=datetime.now(),
            strategy_used="hierarchical_cpc",
            classification_level=2,
            keyword_level=2,
            cross_logic="AND",
            num_classifications=4,
            num_keywords=5,
            num_components=3,
            total_hits=150,
            relevant_hits=30,
            precision=0.2,
            recall=0.8,
            technical_domain="memory_storage"
        ),
        SearchSession(
            session_id="test_002",
            target_patent_id="JP2014007731A",
            timestamp=datetime.now(),
            strategy_used="keyword_centric",
            classification_level=1,
            keyword_level=2,
            cross_logic="AND",
            num_classifications=4,
            num_keywords=5,
            num_components=3,
            total_hits=500,
            relevant_hits=50,
            precision=0.1,
            recall=0.9,
            technical_domain="memory_storage"
        ),
        SearchSession(
            session_id="test_003",
            target_patent_id="JP2014007731A",
            timestamp=datetime.now(),
            strategy_used="hybrid_balanced",
            classification_level=2,
            keyword_level=2,
            cross_logic="AND",
            num_classifications=4,
            num_keywords=5,
            num_components=3,
            total_hits=200,
            relevant_hits=60,
            precision=0.3,
            recall=0.85,
            technical_domain="memory_storage"
        ),
    ]

    # セッションを学習
    for session in test_sessions:
        learner.learn_from_session(session)
        print(f"✓ セッション {session.session_id} を学習しました")

    # 戦略の成功率を表示
    print("\n【テスト2】戦略ごとの成功率")
    print("-" * 80)
    for strategy in ["hierarchical_cpc", "keyword_centric", "hybrid_balanced"]:
        stats = learner.get_strategy_stats(strategy)
        print(f"{strategy:20}: 成功率={stats['success_rate']:.2f}, "
              f"セッション数={stats['total_sessions']}, "
              f"平均ヒット数={stats['avg_hits']:.0f}")

    # パラメータ推奨
    print("\n【テスト3】パラメータ推奨")
    print("-" * 80)
    recommended = learner.recommend_parameters(
        technical_domain="memory_storage",
        num_classifications=4,
        num_keywords=5
    )
    print(f"推奨パラメータ:")
    print(f"  戦略: {recommended['strategy']}")
    print(f"  分類レベル: {recommended['classification_level']}")
    print(f"  キーワードレベル: {recommended['keyword_level']}")
    print(f"  信頼度: {recommended['confidence']:.2f}")
    print(f"  ベースセッション数: {recommended['based_on_sessions']}")

    # 類似セッション検索
    print("\n【テスト4】類似セッション検索")
    print("-" * 80)
    similar = learner.find_similar_sessions(
        num_classifications=4,
        num_keywords=5,
        technical_domain="memory_storage",
        top_n=3
    )
    print(f"類似セッション {len(similar)}件:")
    for s in similar:
        print(f"  {s.session_id}: {s.strategy_used}, hits={s.total_hits}")

    # 学習サマリー
    print("\n【テスト5】学習サマリー")
    print("-" * 80)
    summary = learner.get_learning_summary()
    print(f"総セッション数: {summary['total_sessions']}")
    print(f"学習済み戦略: {', '.join(summary['strategies_learned'])}")
    print(f"学習済み技術領域: {', '.join(summary['domains_learned'])}")

    print("\n" + "=" * 80)
    print("✓ 検索履歴学習機能のテスト完了")
    print("=" * 80)
