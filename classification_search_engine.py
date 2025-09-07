#!/usr/bin/env python3
"""
独立した特許分類検索データベース
OpenSearchに依存しない分類検索システム
"""

import os
import glob
import json
import re
import pickle
from typing import Dict, List, Any, Optional, Tuple
import logging
from datetime import datetime
from collections import defaultdict
import difflib

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ClassificationDatabase:
    def __init__(self, data_dir: str = None):
        """
        独立した分類データベースの初期化
        """
        if data_dir is None:
            data_dir = "/Users/ttdc-user/Desktop/workset/patgenius/zhang_opera/分類データ/data_20250812"
        
        self.data_dir = data_dir
        self.classifications = {}  # code -> classification_data
        self.keyword_index = defaultdict(set)  # keyword -> set of codes
        self.hierarchy_index = {}  # code -> {parents: [], children: []}
        self.title_index = {}  # code -> title info
        
        # データが既にロードされているかチェック
        self.cache_file = "classification_cache.pkl"
        
    def load_data(self):
        """分類データを読み込み・構築"""
        if os.path.exists(self.cache_file):
            logger.info("キャッシュファイルからデータを読み込み中...")
            with open(self.cache_file, 'rb') as f:
                cache_data = pickle.load(f)
                self.classifications = cache_data['classifications']
                self.keyword_index = cache_data['keyword_index']
                self.hierarchy_index = cache_data['hierarchy_index']
                self.title_index = cache_data['title_index']
            logger.info(f"キャッシュから {len(self.classifications)} 件の分類データを読み込み完了")
            return
        
        logger.info("分類データファイルからデータを構築中...")
        
        # IPCデータ読み込み
        self._load_ipc_data()
        
        # FIデータ読み込み
        self._load_fi_data()
        
        # CPCデータ読み込み
        self._load_cpc_data()
        
        # 階層関係を構築
        self._build_hierarchy()
        
        # キーワードインデックスを構築
        self._build_keyword_index()
        
        # キャッシュに保存
        self._save_cache()
        
        logger.info(f"データ構築完了: {len(self.classifications)} 件の分類データ")
    
    def read_file_with_encoding(self, file_path: str) -> str:
        """複数エンコーディングでファイルを読み込み"""
        encodings = ['utf-8', 'shift_jis', 'euc-jp', 'iso-2022-jp', 'cp932']
        
        for encoding in encodings:
            try:
                with open(file_path, 'r', encoding=encoding) as f:
                    return f.read()
            except UnicodeDecodeError:
                continue
        
        logger.warning(f"Could not decode file: {file_path}")
        return ""
    
    def clean_text(self, text: str) -> str:
        """テキストクリーンアップ"""
        if not text:
            return ""
        
        text = re.sub(r'<[^>]+>', '', text)
        text = re.sub(r'\s+', ' ', text)
        return text.strip()
    
    def _load_ipc_data(self):
        """IPCデータ読み込み - data_ipc と data_ipc_head フォルダ"""
        # data_ipc フォルダ
        ipc_files = glob.glob(f"{self.data_dir}/data_ipc/*.txt")
        logger.info(f"IPCファイル処理中: {len(ipc_files)} 件")
        
        for file_path in ipc_files:
            content = self.read_file_with_encoding(file_path)
            if not content:
                continue
                
            for line in content.split('\n'):
                line = line.strip()
                if not line:
                    continue
                
                parts = line.split('\t')
                if len(parts) >= 4:
                    code = parts[0].strip()
                    dot_count = len(parts[1]) if parts[1] else 0
                    title_ja = self.clean_text(parts[2])
                    title_en = self.clean_text(parts[3])
                    num_docs = int(parts[4]) if len(parts) > 4 and parts[4].isdigit() else 0
                    
                    classification = {
                        'classification_system': 'IPC',
                        'code': code,
                        'level': dot_count,
                        'title_ja': title_ja,
                        'title_en': title_en,
                        'num_documents': num_docs,
                        'keywords_ja': self._extract_keywords_ja(title_ja),
                        'keywords_en': self._extract_keywords_en(title_en)
                    }
                    
                    self.classifications[f"IPC_{code}"] = classification
                    self.title_index[f"IPC_{code}"] = {
                        'title_ja': title_ja,
                        'title_en': title_en,
                        'system': 'IPC'
                    }
        
        # data_ipc_head フォルダ
        ipc_head_files = glob.glob(f"{self.data_dir}/data_ipc_head/*.txt")
        logger.info(f"IPC head ファイル処理中: {len(ipc_head_files)} 件")
        
        for file_path in ipc_head_files:
            content = self.read_file_with_encoding(file_path)
            if not content:
                continue
                
            for line in content.split('\n'):
                line = line.strip()
                if not line:
                    continue
                
                parts = line.split('\t')
                if len(parts) >= 3:
                    code = parts[0].strip()
                    title_ja = self.clean_text(parts[1])
                    title_en = self.clean_text(parts[2])
                    
                    # ヘッダー情報として追加または更新
                    full_code = f"IPC_{code}"
                    if full_code in self.classifications:
                        # 既存のデータを更新
                        self.classifications[full_code]['subsection_title_ja'] = title_ja
                        self.classifications[full_code]['subsection_title_en'] = title_en
                    else:
                        # 新規作成
                        classification = {
                            'classification_system': 'IPC',
                            'code': code,
                            'level': 0,
                            'title_ja': title_ja,
                            'title_en': title_en,
                            'subsection_title_ja': title_ja,
                            'subsection_title_en': title_en,
                            'num_documents': 0,
                            'keywords_ja': self._extract_keywords_ja(title_ja),
                            'keywords_en': self._extract_keywords_en(title_en)
                        }
                        
                        self.classifications[full_code] = classification
                        self.title_index[full_code] = {
                            'title_ja': title_ja,
                            'title_en': title_en,
                            'system': 'IPC'
                        }
    
    def _load_fi_data(self):
        """FIデータ読み込み - data_fi と data_fi_head フォルダ"""
        # data_fi フォルダ
        fi_files = glob.glob(f"{self.data_dir}/data_fi/*.txt")
        logger.info(f"FIファイル処理中: {len(fi_files)} 件")
        
        for file_path in fi_files:
            content = self.read_file_with_encoding(file_path)
            if not content:
                continue
                
            for line in content.split('\n'):
                line = line.strip()
                if not line:
                    continue
                
                parts = line.split('\t')
                if len(parts) >= 7:
                    code = parts[0].strip()
                    dot_count = int(parts[1]) if parts[1].isdigit() else 0
                    theme = parts[3].strip()
                    concordance = parts[4].strip()
                    num_docs = int(parts[5]) if parts[5].isdigit() else 0
                    title_ja = self.clean_text(parts[6])
                    title_en = self.clean_text(parts[7]) if len(parts) > 7 else ""
                    
                    classification = {
                        'classification_system': 'FI',
                        'code': code,
                        'level': dot_count,
                        'title_ja': title_ja,
                        'title_en': title_en,
                        'theme': theme,
                        'concordance': concordance,
                        'num_documents': num_docs,
                        'keywords_ja': self._extract_keywords_ja(title_ja),
                        'keywords_en': self._extract_keywords_en(title_en)
                    }
                    
                    self.classifications[f"FI_{code}"] = classification
                    self.title_index[f"FI_{code}"] = {
                        'title_ja': title_ja,
                        'title_en': title_en,
                        'system': 'FI'
                    }
        
        # data_fi_head フォルダ
        fi_head_files = glob.glob(f"{self.data_dir}/data_fi_head/*.txt")
        logger.info(f"FI head ファイル処理中: {len(fi_head_files)} 件")
        
        for file_path in fi_head_files:
            content = self.read_file_with_encoding(file_path)
            if not content:
                continue
                
            for line in content.split('\n'):
                line = line.strip()
                if not line:
                    continue
                
                parts = line.split('\t')
                if len(parts) >= 3:
                    code = parts[0].strip()
                    title_ja = self.clean_text(parts[1])
                    title_en = self.clean_text(parts[2])
                    
                    # ヘッダー情報として追加または更新
                    full_code = f"FI_{code}"
                    if full_code in self.classifications:
                        # 既存のデータを更新
                        self.classifications[full_code]['subsection_title_ja'] = title_ja
                        self.classifications[full_code]['subsection_title_en'] = title_en
                    else:
                        # 新規作成
                        classification = {
                            'classification_system': 'FI',
                            'code': code,
                            'level': 0,
                            'title_ja': title_ja,
                            'title_en': title_en,
                            'subsection_title_ja': title_ja,
                            'subsection_title_en': title_en,
                            'num_documents': 0,
                            'keywords_ja': self._extract_keywords_ja(title_ja),
                            'keywords_en': self._extract_keywords_en(title_en)
                        }
                        
                        self.classifications[full_code] = classification
                        self.title_index[full_code] = {
                            'title_ja': title_ja,
                            'title_en': title_en,
                            'system': 'FI'
                        }
    
    def _load_cpc_data(self):
        """CPCデータ読み込み - 全CPCフォルダ"""
        # data_cpc_interleave フォルダ
        cpc_files = glob.glob(f"{self.data_dir}/data_cpc_interleave/*.txt")
        logger.info(f"CPC interleave ファイル処理中: {len(cpc_files)} 件")
        
        for file_path in cpc_files:
            content = self.read_file_with_encoding(file_path)
            if not content:
                continue
                
            for line in content.split('\n'):
                line = line.strip()
                if not line:
                    continue
                
                parts = line.split('\t')
                if len(parts) >= 6:
                    code = parts[0].strip()
                    dot_count = int(parts[1]) if parts[1].isdigit() else 0
                    title_en = self.clean_text(parts[2])
                    concordance = parts[3].strip() if len(parts) > 3 else ""
                    title_ja = self.clean_text(parts[5]) if len(parts) > 5 else ""
                    num_docs = int(parts[6]) if len(parts) > 6 and parts[6].isdigit() else 0
                    
                    classification = {
                        'classification_system': 'CPC',
                        'code': code,
                        'level': dot_count,
                        'title_ja': title_ja,
                        'title_en': title_en,
                        'concordance': concordance,
                        'num_documents': num_docs,
                        'keywords_ja': self._extract_keywords_ja(title_ja),
                        'keywords_en': self._extract_keywords_en(title_en)
                    }
                    
                    self.classifications[f"CPC_{code}"] = classification
                    self.title_index[f"CPC_{code}"] = {
                        'title_ja': title_ja,
                        'title_en': title_en,
                        'system': 'CPC'
                    }
        
        # data_cpc_interleave_head フォルダ
        cpc_head_files = glob.glob(f"{self.data_dir}/data_cpc_interleave_head/*.txt")
        logger.info(f"CPC interleave head ファイル処理中: {len(cpc_head_files)} 件")
        
        for file_path in cpc_head_files:
            content = self.read_file_with_encoding(file_path)
            if not content:
                continue
                
            for line in content.split('\n'):
                line = line.strip()
                if not line:
                    continue
                
                parts = line.split('\t')
                if len(parts) >= 2:
                    code = parts[0].strip()
                    title_en = self.clean_text(parts[1])
                    
                    # ヘッダー情報として追加または更新
                    full_code = f"CPC_{code}"
                    if full_code in self.classifications:
                        # 既存のデータを更新
                        self.classifications[full_code]['subsection_title_en'] = title_en
                    else:
                        # 新規作成
                        classification = {
                            'classification_system': 'CPC',
                            'code': code,
                            'level': 0,
                            'title_ja': '',
                            'title_en': title_en,
                            'subsection_title_en': title_en,
                            'num_documents': 0,
                            'keywords_ja': '',
                            'keywords_en': self._extract_keywords_en(title_en)
                        }
                        
                        self.classifications[full_code] = classification
                        self.title_index[full_code] = {
                            'title_ja': '',
                            'title_en': title_en,
                            'system': 'CPC'
                        }
        
        # data_cpc_wayaku フォルダ
        cpc_wayaku_files = glob.glob(f"{self.data_dir}/data_cpc_wayaku/*.txt")
        logger.info(f"CPC wayaku ファイル処理中: {len(cpc_wayaku_files)} 件")
        
        for file_path in cpc_wayaku_files:
            content = self.read_file_with_encoding(file_path)
            if not content:
                continue
                
            for line in content.split('\n'):
                line = line.strip()
                if not line:
                    continue
                
                parts = line.split('\t')
                if len(parts) >= 2:
                    code = parts[0].strip()
                    title_ja = self.clean_text(parts[1])
                    
                    # 和訳情報として追加または更新
                    full_code = f"CPC_{code}"
                    if full_code in self.classifications:
                        # 既存のデータの和訳を更新
                        if not self.classifications[full_code]['title_ja']:
                            self.classifications[full_code]['title_ja'] = title_ja
                            self.classifications[full_code]['keywords_ja'] = self._extract_keywords_ja(title_ja)
                            self.title_index[full_code]['title_ja'] = title_ja
                    else:
                        # 新規作成（和訳のみ）
                        classification = {
                            'classification_system': 'CPC',
                            'code': code,
                            'level': 0,
                            'title_ja': title_ja,
                            'title_en': '',
                            'num_documents': 0,
                            'keywords_ja': self._extract_keywords_ja(title_ja),
                            'keywords_en': ''
                        }
                        
                        self.classifications[full_code] = classification
                        self.title_index[full_code] = {
                            'title_ja': title_ja,
                            'title_en': '',
                            'system': 'CPC'
                        }
    
    def _extract_keywords_ja(self, text: str) -> str:
        """日本語キーワード抽出"""
        if not text:
            return ""
        
        keywords = []
        matches = re.findall(r'[ァ-ヶー]+|[ぁ-ゞー]+|[一-龯]+', text)
        keywords.extend([m for m in matches if len(m) > 1])
        
        return " ".join(set(keywords))
    
    def _extract_keywords_en(self, text: str) -> str:
        """英語キーワード抽出"""
        if not text:
            return ""
        
        keywords = re.findall(r'\b[A-Za-z]{3,}\b', text.upper())
        return " ".join(set(keywords))
    
    def _generate_parent_codes(self, code: str, system: str) -> List[str]:
        """上位分類コード生成"""
        parents = []
        
        if system in ["IPC", "FI", "CPC"]:
            if "/" in code:
                base_code = code.split("/")[0]
                parents.append(base_code)
                
                if len(base_code) > 4:
                    parents.append(base_code[:4])
                if len(base_code) > 3:
                    parents.append(base_code[:3])
                if len(base_code) > 1:
                    parents.append(base_code[:1])
            else:
                if len(code) > 3:
                    parents.append(code[:3])
                if len(code) > 1:
                    parents.append(code[:1])
        
        return parents
    
    def _build_hierarchy(self):
        """階層関係を構築"""
        logger.info("階層関係を構築中...")
        
        for full_code, classification in self.classifications.items():
            code = classification['code']
            system = classification['classification_system']
            
            parent_codes = self._generate_parent_codes(code, system)
            
            # 現在のコードの親子関係を初期化
            if full_code not in self.hierarchy_index:
                self.hierarchy_index[full_code] = {'parents': [], 'children': []}
            
            # 親コードを設定
            for parent_code in parent_codes:
                parent_full_code = f"{system}_{parent_code}"
                if parent_full_code in self.classifications:
                    self.hierarchy_index[full_code]['parents'].append(parent_full_code)
                    
                    # 親コードに子として追加
                    if parent_full_code not in self.hierarchy_index:
                        self.hierarchy_index[parent_full_code] = {'parents': [], 'children': []}
                    self.hierarchy_index[parent_full_code]['children'].append(full_code)
    
    def _build_keyword_index(self):
        """キーワードインデックス構築"""
        logger.info("キーワードインデックス構築中...")
        
        for full_code, classification in self.classifications.items():
            # 日本語タイトルから
            if classification.get('title_ja'):
                words = self._tokenize_japanese(classification['title_ja'])
                for word in words:
                    if len(word) > 1:
                        self.keyword_index[word.lower()].add(full_code)
            
            # 英語タイトルから
            if classification.get('title_en'):
                words = re.findall(r'\b[A-Za-z]{2,}\b', classification['title_en'])
                for word in words:
                    self.keyword_index[word.lower()].add(full_code)
            
            # キーワードから
            if classification.get('keywords_ja'):
                for word in classification['keywords_ja'].split():
                    if len(word) > 1:
                        self.keyword_index[word.lower()].add(full_code)
            
            if classification.get('keywords_en'):
                for word in classification['keywords_en'].split():
                    self.keyword_index[word.lower()].add(full_code)
    
    def _tokenize_japanese(self, text: str) -> List[str]:
        """簡易日本語トークン化"""
        if not text:
            return []
        
        # カタカナ、ひらがな、漢字の連続を抽出
        tokens = re.findall(r'[ァ-ヶー]+|[ぁ-ゞー]+|[一-龯]+|[A-Za-z]+', text)
        return [t for t in tokens if len(t) > 1]
    
    def _save_cache(self):
        """データをキャッシュに保存"""
        cache_data = {
            'classifications': dict(self.classifications),
            'keyword_index': dict(self.keyword_index),
            'hierarchy_index': dict(self.hierarchy_index),
            'title_index': dict(self.title_index),
            'cached_at': datetime.now().isoformat()
        }
        
        with open(self.cache_file, 'wb') as f:
            pickle.dump(cache_data, f)
        
        logger.info(f"データをキャッシュに保存: {self.cache_file}")
    
    def search_by_keyword(self, keyword: str, systems: List[str] = None, limit: int = 20, include_hierarchy: bool = True, highlight: bool = False) -> List[Dict[str, Any]]:
        """
        キーワードで分類コードを検索 - 高度な検索機能付き
        
        Args:
            keyword: 検索キーワード（高度な検索演算子対応）
            systems: 検索対象システム (IPC, FI, CPC)
            limit: 結果数制限
            include_hierarchy: 階層情報を含めるか
        
        Returns:
            マッチした分類のリスト（階層情報付き）
        
        高度検索例:
        - "画像 AND 形成" : ANDで結合
        - "トナー OR 現像剤" : ORで結合  
        - "車 NEAR3 両" : 車と両が3語以内の距離
        - "レーザー NOT プリンター" : レーザーを含むがプリンターを含まない
        """
        if systems is None:
            systems = ['IPC', 'FI', 'CPC']
        
        # 高度検索クエリ解析
        if self._is_advanced_query(keyword):
            matched_codes = self._parse_advanced_query(keyword)
        else:
            # シンプルキーワード検索
            matched_codes = self._simple_keyword_search(keyword)
        
        # 結果を構築
        results = []
        for full_code in matched_codes:
            if full_code in self.classifications:
                classification = self.classifications[full_code].copy()
                if classification['classification_system'] in systems:
                    # 階層情報を追加
                    if include_hierarchy:
                        hierarchy_info = self._get_hierarchy_info_for_classification(full_code)
                        classification.update(hierarchy_info)
                    
                    # スコア計算（マッチした理由を記録）
                    classification['match_score'] = self._calculate_match_score(full_code, keyword)
                    
                    # ハイライト機能
                    if highlight:
                        classification = self._add_highlights(classification, keyword)
                    
                    results.append(classification)
        
        # スコアと文書数でソート
        results.sort(key=lambda x: (x.get('match_score', 0), x.get('num_documents', 0)), reverse=True)
        
        return results[:limit]
    
    def _is_advanced_query(self, keyword: str) -> bool:
        """高度検索クエリかどうか判定"""
        advanced_operators = ['AND', 'OR', 'NOT', 'NEAR']
        keyword_upper = keyword.upper()
        return any(op in keyword_upper for op in advanced_operators)
    
    def _parse_advanced_query(self, keyword: str) -> set:
        """高度検索クエリを解析して結果を返す"""
        keyword = keyword.strip()
        
        # NOT演算子を最初に処理
        if ' NOT ' in keyword.upper():
            return self._parse_not_query(keyword)
        
        # NEAR演算子を処理
        if 'NEAR' in keyword.upper():
            return self._parse_near_query(keyword)
        
        # AND演算子を処理
        if ' AND ' in keyword.upper():
            return self._parse_and_query(keyword)
        
        # OR演算子を処理
        if ' OR ' in keyword.upper():
            return self._parse_or_query(keyword)
        
        # デフォルトはシンプル検索
        return self._simple_keyword_search(keyword)
    
    def _parse_and_query(self, keyword: str) -> set:
        """AND検索を処理"""
        import re
        terms = re.split(r'\s+AND\s+', keyword, flags=re.IGNORECASE)
        
        if len(terms) < 2:
            return self._simple_keyword_search(keyword)
        
        # 最初のキーワードで検索
        result_sets = []
        for term in terms:
            term = term.strip()
            if term:
                matches = self._simple_keyword_search(term)
                result_sets.append(matches)
        
        # 全ての結果セットの積集合を計算
        if result_sets:
            final_results = result_sets[0]
            for result_set in result_sets[1:]:
                final_results = final_results.intersection(result_set)
            return final_results
        
        return set()
    
    def _parse_or_query(self, keyword: str) -> set:
        """OR検索を処理"""
        import re
        terms = re.split(r'\s+OR\s+', keyword, flags=re.IGNORECASE)
        
        final_results = set()
        for term in terms:
            term = term.strip()
            if term:
                matches = self._simple_keyword_search(term)
                final_results.update(matches)
        
        return final_results
    
    def _parse_not_query(self, keyword: str) -> set:
        """NOT検索を処理"""
        import re
        parts = re.split(r'\s+NOT\s+', keyword, flags=re.IGNORECASE)
        
        if len(parts) != 2:
            return self._simple_keyword_search(keyword)
        
        include_term = parts[0].strip()
        exclude_term = parts[1].strip()
        
        include_results = self._simple_keyword_search(include_term)
        exclude_results = self._simple_keyword_search(exclude_term)
        
        # 包含結果から除外結果を引く
        return include_results - exclude_results
    
    def _parse_near_query(self, keyword: str) -> set:
        """NEAR検索を処理"""
        import re
        
        # NEAR3, NEAR5 などの形式をサポート
        near_pattern = r'(.+?)\s+NEAR(\d*)\s+(.+)'
        match = re.search(near_pattern, keyword, re.IGNORECASE)
        
        if not match:
            return self._simple_keyword_search(keyword)
        
        term1 = match.group(1).strip()
        distance = int(match.group(2)) if match.group(2) else 3  # デフォルト距離は3
        term2 = match.group(3).strip()
        
        # NEAR検索の実装：両方のキーワードを含む分類を検索し、
        # テキスト内での距離をチェック
        term1_matches = self._simple_keyword_search(term1)
        term2_matches = self._simple_keyword_search(term2)
        
        # 両方のキーワードを含む分類
        common_matches = term1_matches.intersection(term2_matches)
        
        # 距離チェック（簡易実装）
        near_results = set()
        for full_code in common_matches:
            if self._check_word_proximity(full_code, term1, term2, distance):
                near_results.add(full_code)
        
        return near_results
    
    def _check_word_proximity(self, full_code: str, term1: str, term2: str, distance: int) -> bool:
        """語句の近接性をチェック"""
        if full_code not in self.classifications:
            return False
        
        classification = self.classifications[full_code]
        
        # タイトルテキストを結合
        text_parts = []
        if classification.get('title_ja'):
            text_parts.append(classification['title_ja'])
        if classification.get('title_en'):
            text_parts.append(classification['title_en'])
        
        combined_text = ' '.join(text_parts).lower()
        
        # 簡易な近接性チェック
        words = combined_text.split()
        term1_lower = term1.lower()
        term2_lower = term2.lower()
        
        term1_positions = [i for i, word in enumerate(words) if term1_lower in word]
        term2_positions = [i for i, word in enumerate(words) if term2_lower in word]
        
        # 距離内に両方の語句があるかチェック
        for pos1 in term1_positions:
            for pos2 in term2_positions:
                if abs(pos1 - pos2) <= distance:
                    return True
        
        return False
    
    def _simple_keyword_search(self, keyword: str) -> set:
        """シンプルキーワード検索"""
        matched_codes = set()
        keyword_lower = keyword.lower()
        
        # 分類解釈（タイトル・説明）からの検索を優先
        for full_code, classification in self.classifications.items():
            text_to_search = []
            
            # 日本語タイトル・英語タイトルから検索
            if classification.get('title_ja'):
                text_to_search.append(classification['title_ja'].lower())
            if classification.get('title_en'):
                text_to_search.append(classification['title_en'].lower())
            
            # テキスト内でキーワードが含まれているかチェック
            for text in text_to_search:
                if keyword_lower in text:
                    matched_codes.add(full_code)
                    break
        
        # キーワードインデックスからも検索（補助的）
        if keyword_lower in self.keyword_index:
            matched_codes.update(self.keyword_index[keyword_lower])
        
        # 部分一致検索
        for indexed_keyword, codes in self.keyword_index.items():
            if keyword_lower in indexed_keyword or indexed_keyword in keyword_lower:
                matched_codes.update(codes)
        
        return matched_codes
    
    def _calculate_match_score(self, full_code: str, keyword: str) -> float:
        """マッチスコアを計算"""
        if full_code not in self.classifications:
            return 0.0
        
        classification = self.classifications[full_code]
        score = 0.0
        
        # 高度検索の場合、基本キーワードを抽出
        highlight_terms = self._extract_highlight_terms(keyword)
        
        # 各キーワードについてスコア計算
        for term in highlight_terms:
            term_lower = term.lower()
            
            # タイトル完全一致は高スコア
            if classification.get('title_ja') and term_lower == classification['title_ja'].lower():
                score += 10.0
            if classification.get('title_en') and term_lower == classification['title_en'].lower():
                score += 10.0
            
            # タイトル部分一致
            if classification.get('title_ja') and term_lower in classification['title_ja'].lower():
                score += 5.0
            if classification.get('title_en') and term_lower in classification['title_en'].lower():
                score += 5.0
            
            # キーワード一致
            if classification.get('keywords_ja') and term_lower in classification['keywords_ja'].lower():
                score += 2.0
            if classification.get('keywords_en') and term_lower in classification['keywords_en'].lower():
                score += 2.0
        
        # AND検索の場合はボーナス
        if ' AND ' in keyword.upper() and len(highlight_terms) > 1:
            score *= 1.5
        
        # 文書数による重み付け（対数スケール）
        num_docs = classification.get('num_documents', 0)
        if num_docs > 0:
            import math
            score += math.log10(num_docs) * 0.1
        
        # 基本スコアを追加（検索でヒットした場合の最低スコア）
        if score == 0.0:
            score = 1.0
        
        return round(score, 2)
    
    def _get_hierarchy_info_for_classification(self, full_code: str) -> Dict[str, Any]:
        """分類の階層情報を取得"""
        hierarchy_info = {
            'parent_classifications': [],
            'child_classifications': [],
            'hierarchy_path': []
        }
        
        if full_code in self.hierarchy_index:
            hierarchy = self.hierarchy_index[full_code]
            
            # 上位分類情報
            for parent_code in hierarchy['parents']:
                if parent_code in self.classifications:
                    parent_info = self.classifications[parent_code]
                    hierarchy_info['parent_classifications'].append({
                        'code': parent_info['code'],
                        'title_ja': parent_info.get('title_ja', ''),
                        'title_en': parent_info.get('title_en', ''),
                        'level': parent_info.get('level', 0)
                    })
            
            # 下位分類情報（上位10件）
            child_count = 0
            for child_code in hierarchy['children']:
                if child_code in self.classifications and child_count < 10:
                    child_info = self.classifications[child_code]
                    hierarchy_info['child_classifications'].append({
                        'code': child_info['code'],
                        'title_ja': child_info.get('title_ja', ''),
                        'title_en': child_info.get('title_en', ''),
                        'level': child_info.get('level', 0),
                        'num_documents': child_info.get('num_documents', 0)
                    })
                    child_count += 1
            
            # 階層パスを構築（A → A01 → A01D → A01D34 のような）
            current_classification = self.classifications[full_code]
            system = current_classification['classification_system']
            code = current_classification['code']
            
            # 階層パスを生成
            path_codes = self._generate_hierarchy_path(code, system)
            for path_code in path_codes:
                path_full_code = f"{system}_{path_code}"
                if path_full_code in self.classifications:
                    path_info = self.classifications[path_full_code]
                    hierarchy_info['hierarchy_path'].append({
                        'code': path_info['code'],
                        'title_ja': path_info.get('title_ja', ''),
                        'title_en': path_info.get('title_en', ''),
                        'level': path_info.get('level', 0)
                    })
            
            # 階層統計
            hierarchy_info['total_children'] = len(hierarchy['children'])
            hierarchy_info['total_parents'] = len(hierarchy['parents'])
        
        return hierarchy_info
    
    def _generate_hierarchy_path(self, code: str, system: str) -> List[str]:
        """階層パスを生成（上位から現在まで）"""
        path = []
        
        if system in ["IPC", "FI", "CPC"]:
            if "/" in code:
                base_code = code.split("/")[0]
                # A01D34/13 → [A, A01, A01D, A01D34, A01D34/13]
                if len(base_code) > 1:
                    path.append(base_code[:1])  # A
                if len(base_code) > 3:
                    path.append(base_code[:3])  # A01
                if len(base_code) > 4:
                    path.append(base_code[:4])  # A01D
                path.append(base_code)  # A01D34
                path.append(code)  # A01D34/13
            else:
                # A01D → [A, A01, A01D]
                if len(code) > 1:
                    path.append(code[:1])  # A
                if len(code) > 3:
                    path.append(code[:3])  # A01
                path.append(code)  # A01D
        
        return path
    
    def _add_highlights(self, classification: Dict[str, Any], keyword: str) -> Dict[str, Any]:
        """検索キーワードをハイライト表示用に処理"""
        import re
        
        # 高度検索の場合、基本キーワードを抽出
        highlight_terms = self._extract_highlight_terms(keyword)
        
        # ハイライト対象フィールド
        highlight_fields = ['title_ja', 'title_en']
        
        for field in highlight_fields:
            if field in classification and classification[field]:
                original_text = classification[field]
                highlighted_text = self._highlight_text(original_text, highlight_terms)
                classification[f"{field}_highlighted"] = highlighted_text
        
        return classification
    
    def _extract_highlight_terms(self, keyword: str) -> List[str]:
        """検索クエリからハイライト用キーワードを抽出"""
        import re
        
        # 高度演算子を除去してキーワードを抽出
        terms = []
        
        # AND, OR, NOT, NEARを除去
        cleaned = re.sub(r'\b(AND|OR|NOT|NEAR\d*)\b', ' ', keyword, flags=re.IGNORECASE)
        
        # 単語を抽出
        words = re.findall(r'\b\w+\b', cleaned)
        terms.extend([w for w in words if len(w) > 1])
        
        return list(set(terms))  # 重複除去
    
    def _highlight_text(self, text: str, terms: List[str]) -> str:
        """テキスト内の用語をハイライト"""
        import re
        
        if not text or not terms:
            return text
        
        highlighted_text = text
        
        for term in terms:
            # 日本語・英語両対応の大文字小文字を区別しない検索
            pattern = re.compile(re.escape(term), re.IGNORECASE)
            highlighted_text = pattern.sub(lambda m: f'<mark>{m.group()}</mark>', highlighted_text)
        
        return highlighted_text
    
    def get_classification_info(self, code: str, system: str) -> Optional[Dict[str, Any]]:
        """
        分類コードの詳細情報を取得
        
        Args:
            code: 分類コード
            system: 分類システム
        
        Returns:
            分類情報
        """
        full_code = f"{system}_{code}"
        return self.classifications.get(full_code)
    
    def get_hierarchical_info(self, code: str, system: str, include_parents: bool = True, include_children: bool = True) -> Dict[str, Any]:
        """
        階層情報を取得（上位・下位概念を考慮）
        
        Args:
            code: 分類コード
            system: 分類システム
            include_parents: 上位分類を含めるか
            include_children: 下位分類を含めるか
        
        Returns:
            階層情報
        """
        full_code = f"{system}_{code}"
        result = {
            'current': None,
            'parents': [],
            'children': []
        }
        
        # 現在の分類情報
        if full_code in self.classifications:
            result['current'] = self.classifications[full_code]
        
        # 階層情報を取得
        if full_code in self.hierarchy_index:
            hierarchy = self.hierarchy_index[full_code]
            
            # 上位分類
            if include_parents:
                for parent_code in hierarchy['parents']:
                    if parent_code in self.classifications:
                        result['parents'].append(self.classifications[parent_code])
            
            # 下位分類
            if include_children:
                for child_code in hierarchy['children']:
                    if child_code in self.classifications:
                        result['children'].append(self.classifications[child_code])
        
        return result
    
    def get_statistics(self) -> Dict[str, Any]:
        """統計情報を取得"""
        stats = {
            'total_classifications': len(self.classifications),
            'by_system': {},
            'total_keywords': len(self.keyword_index)
        }
        
        for classification in self.classifications.values():
            system = classification['classification_system']
            if system not in stats['by_system']:
                stats['by_system'][system] = 0
            stats['by_system'][system] += 1
        
        return stats

def main():
    """メイン関数 - データベース構築のテスト"""
    db = ClassificationDatabase()
    
    logger.info("=== 分類検索データベース構築開始 ===")
    start_time = datetime.now()
    
    # データ読み込み
    db.load_data()
    
    end_time = datetime.now()
    total_time = (end_time - start_time).total_seconds()
    
    # 統計情報表示
    stats = db.get_statistics()
    logger.info(f"=== 構築完了: {total_time:.1f}秒 ===")
    logger.info(f"総分類数: {stats['total_classifications']:,}")
    for system, count in stats['by_system'].items():
        logger.info(f"  {system}: {count:,}")
    logger.info(f"総キーワード数: {stats['total_keywords']:,}")
    
    # 検索テスト
    logger.info("\n=== 検索テスト ===")
    
    # キーワード検索テスト
    results = db.search_by_keyword("画像形成装置", limit=3)
    logger.info(f"「画像形成装置」検索結果: {len(results)}件")
    for r in results:
        logger.info(f"  {r['classification_system']} {r['code']}: {r['title_ja']}")
    
    # 階層検索テスト
    hierarchy = db.get_hierarchical_info("A01D", "IPC")
    if hierarchy['current']:
        logger.info(f"\nA01D階層情報:")
        logger.info(f"  現在: {hierarchy['current']['title_ja']}")
        logger.info(f"  上位: {len(hierarchy['parents'])}件")
        logger.info(f"  下位: {len(hierarchy['children'])}件")

if __name__ == "__main__":
    main()