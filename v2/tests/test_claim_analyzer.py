#!/usr/bin/env python3
"""
claim_analyzer.pyのテストスイート

小さな関数ごとに独立したテストケースを作成。
"""

import pytest
import sys
from pathlib import Path

# プロジェクトルートをパスに追加
sys.path.insert(0, str(Path(__file__).parent.parent))

from claim_analyzer import identify_independent_claims, identify_core_elements


class TestIdentifyIndependentClaims:
    """identify_independent_claims関数のテスト"""

    def test_basic_independent_claim_extraction(self):
        """基本的な独立請求項の抽出"""
        elements = [
            {'構成要素番号': '1a', 'claim_type': 'independent'},
            {'構成要素番号': '1b', 'claim_type': 'dependent'},
            {'構成要素番号': '2a', 'claim_type': 'independent'},
        ]

        result = identify_independent_claims(elements)

        assert result == ['1a', '2a']
        assert len(result) == 2

    def test_no_independent_claims(self):
        """独立請求項がない場合"""
        elements = [
            {'構成要素番号': '1b', 'claim_type': 'dependent'},
            {'構成要素番号': '1c', 'claim_type': 'dependent'},
        ]

        result = identify_independent_claims(elements)

        assert result == []
        assert len(result) == 0

    def test_all_independent_claims(self):
        """全てが独立請求項の場合"""
        elements = [
            {'構成要素番号': '1a', 'claim_type': 'independent'},
            {'構成要素番号': '2a', 'claim_type': 'independent'},
            {'構成要素番号': '3a', 'claim_type': 'independent'},
        ]

        result = identify_independent_claims(elements)

        assert result == ['1a', '2a', '3a']
        assert len(result) == 3

    def test_missing_claim_type_field(self):
        """claim_typeフィールドがない要素が含まれる場合"""
        elements = [
            {'構成要素番号': '1a', 'claim_type': 'independent'},
            {'構成要素番号': '1b'},  # claim_typeなし
            {'構成要素番号': '2a', 'claim_type': 'independent'},
        ]

        result = identify_independent_claims(elements)

        # claim_typeがない要素は除外される
        assert result == ['1a', '2a']
        assert len(result) == 2

    def test_empty_list(self):
        """空のリストの場合"""
        elements = []

        result = identify_independent_claims(elements)

        assert result == []
        assert len(result) == 0

    def test_preserves_order(self):
        """要素の順序が保持されることを確認"""
        elements = [
            {'構成要素番号': '3a', 'claim_type': 'independent'},
            {'構成要素番号': '1b', 'claim_type': 'dependent'},
            {'構成要素番号': '1a', 'claim_type': 'independent'},
            {'構成要素番号': '2a', 'claim_type': 'independent'},
        ]

        result = identify_independent_claims(elements)

        # リスト順序を保持
        assert result == ['3a', '1a', '2a']


class TestIdentifyCoreElements:
    """identify_core_elements関数のテスト"""

    def test_basic_core_element_extraction(self):
        """基本的なコア要素の抽出"""
        elements = [
            {'構成要素番号': '1a', '構成要素の重要度': 1.0, 'is_core_element': True},
            {'構成要素番号': '1b', '構成要素の重要度': 0.95, 'is_core_element': False},
            {'構成要素番号': '1d', '構成要素の重要度': 1.0, 'is_core_element': True},
        ]

        result = identify_core_elements(elements)

        assert result == ['1a', '1d']
        assert len(result) == 2

    def test_importance_threshold(self):
        """重要度の閾値が機能することを確認"""
        elements = [
            {'構成要素番号': '1a', '構成要素の重要度': 1.0, 'is_core_element': True},
            {'構成要素番号': '1b', '構成要素の重要度': 0.94, 'is_core_element': True},  # 閾値未満
            {'構成要素番号': '1c', '構成要素の重要度': 0.95, 'is_core_element': True},  # 閾値ちょうど
        ]

        result = identify_core_elements(elements, importance_threshold=0.95)

        # 0.95以上のみ
        assert result == ['1a', '1c']
        assert len(result) == 2

    def test_core_flag_false(self):
        """is_core_elementフラグがFalseの場合は除外"""
        elements = [
            {'構成要素番号': '1a', '構成要素の重要度': 1.0, 'is_core_element': True},
            {'構成要素番号': '1b', '構成要素の重要度': 1.0, 'is_core_element': False},  # フラグFalse
        ]

        result = identify_core_elements(elements)

        assert result == ['1a']
        assert len(result) == 1

    def test_custom_threshold(self):
        """カスタム閾値が機能することを確認"""
        elements = [
            {'構成要素番号': '1a', '構成要素の重要度': 1.0, 'is_core_element': True},
            {'構成要素番号': '1b', '構成要素の重要度': 0.90, 'is_core_element': True},
            {'構成要素番号': '1c', '構成要素の重要度': 0.85, 'is_core_element': True},
        ]

        result = identify_core_elements(elements, importance_threshold=0.85)

        # 0.85以上全て
        assert result == ['1a', '1b', '1c']
        assert len(result) == 3

    def test_no_core_elements(self):
        """コア要素がない場合"""
        elements = [
            {'構成要素番号': '1a', '構成要素の重要度': 1.0, 'is_core_element': False},
            {'構成要素番号': '1b', '構成要素の重要度': 0.95, 'is_core_element': False},
        ]

        result = identify_core_elements(elements)

        assert result == []
        assert len(result) == 0

    def test_missing_importance_field(self):
        """重要度フィールドがない場合"""
        elements = [
            {'構成要素番号': '1a', '構成要素の重要度': 1.0, 'is_core_element': True},
            {'構成要素番号': '1b', 'is_core_element': True},  # 重要度なし
        ]

        result = identify_core_elements(elements)

        # 重要度がない要素はデフォルト0として扱われ除外
        assert result == ['1a']
        assert len(result) == 1

    def test_missing_core_flag_field(self):
        """is_core_elementフィールドがない場合"""
        elements = [
            {'構成要素番号': '1a', '構成要素の重要度': 1.0, 'is_core_element': True},
            {'構成要素番号': '1b', '構成要素の重要度': 1.0},  # is_core_elementなし
        ]

        result = identify_core_elements(elements)

        # is_core_elementがない要素はデフォルトFalseとして扱われ除外
        assert result == ['1a']
        assert len(result) == 1

    def test_empty_list(self):
        """空のリストの場合"""
        elements = []

        result = identify_core_elements(elements)

        assert result == []
        assert len(result) == 0

    def test_both_conditions_required(self):
        """重要度とフラグの両方が必要なことを確認"""
        elements = [
            {'構成要素番号': '1a', '構成要素の重要度': 1.0, 'is_core_element': True},   # 両方OK
            {'構成要素番号': '1b', '構成要素の重要度': 0.90, 'is_core_element': True},  # 重要度不足
            {'構成要素番号': '1c', '構成要素の重要度': 1.0, 'is_core_element': False},  # フラグFalse
        ]

        result = identify_core_elements(elements)

        # 両方の条件を満たす1aのみ
        assert result == ['1a']
        assert len(result) == 1


class TestIntegrationWithEnhancedJSON:
    """拡張JSONファイルとの統合テスト"""

    def test_with_enhanced_json_structure(self):
        """tests/test_構成要件_ENHANCED.jsonの構造を模擬"""
        import json

        # Enhanced JSON構造を読み込み
        json_path = Path(__file__).parent / 'test_構成要件_ENHANCED.json'
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        elements = data['構成要件']

        # 独立請求項の抽出
        independent = identify_independent_claims(elements)
        assert '1a' in independent  # Claim 1の独立請求項
        assert '2a' in independent  # Claim 2の独立請求項
        assert '1b' not in independent  # 従属請求項

        # コア要素の抽出
        core = identify_core_elements(elements)
        assert '1a' in core  # コアかつ重要度1.0
        assert '1d' in core  # コアかつ重要度1.0
        assert '1b' not in core  # 非コア
        assert '2a' not in core  # 非コア


if __name__ == '__main__':
    # pytest実行
    pytest.main([__file__, '-v'])
