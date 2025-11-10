"""
Patent Classification Data Import Script
Imports IPC, CPC, and FI classification data into OpenSearch with RAG embeddings
"""

import os
import glob
import time
from typing import List, Dict, Any
from pathlib import Path
from tqdm import tqdm

from opensearchpy import OpenSearch, helpers
from sentence_transformers import SentenceTransformer
import torch


def open_with_encoding(file_path: str, encodings=None):
    """
    Try to open a file with multiple encodings

    Args:
        file_path: Path to file
        encodings: List of encodings to try (default: ['utf-8', 'shift-jis', 'euc-jp', 'iso-8859-1'])

    Returns:
        File object
    """
    if encodings is None:
        encodings = ['utf-8', 'shift-jis', 'euc-jp', 'iso-8859-1', 'cp932']

    # Try each encoding
    for encoding in encodings:
        try:
            # Try to read a small portion to verify encoding works
            with open(file_path, 'r', encoding=encoding, errors='strict') as test_file:
                test_file.read(1024)  # Read first 1KB to test
            # If successful, return file with this encoding
            return open(file_path, 'r', encoding=encoding, errors='replace')
        except (UnicodeDecodeError, LookupError):
            continue
        except Exception:
            continue

    # If all fail, use utf-8 with error replacement
    return open(file_path, 'r', encoding='utf-8', errors='replace')


class PatentClassificationImporter:
    """Import patent classification data with embeddings for RAG"""

    def __init__(self,
                 opensearch_host: str = "localhost",
                 opensearch_port: int = 9200,
                 embedding_model: str = "paraphrase-multilingual-mpnet-base-v2"):
        """
        Initialize importer

        Args:
            opensearch_host: OpenSearch host
            opensearch_port: OpenSearch port
            embedding_model: Sentence transformer model for embeddings
        """
        self.client = OpenSearch(
            hosts=[{'host': opensearch_host, 'port': opensearch_port}],
            http_compress=True,
            use_ssl=False,
            verify_certs=False,
            ssl_assert_hostname=False,
            ssl_show_warn=False,
        )

        print(f"Loading embedding model: {embedding_model}")
        self.model = SentenceTransformer(embedding_model)
        self.embedding_dim = self.model.get_sentence_embedding_dimension()
        print(f"Embedding dimension: {self.embedding_dim}")

    def create_indices(self):
        """Create OpenSearch indices for IPC, CPC, and FI classifications"""

        # Common mapping for classification data
        def get_mapping(classification_type: str) -> Dict[str, Any]:
            return {
                "settings": {
                    "number_of_shards": 2,
                    "number_of_replicas": 1,
                    "index": {
                        "knn": True,
                        "knn.algo_param.ef_search": 100
                    }
                },
                "mappings": {
                    "properties": {
                        "code": {"type": "keyword"},
                        "classification_type": {"type": "keyword"},
                        "level": {"type": "integer"},
                        "title_ja": {"type": "text", "analyzer": "standard"},
                        "title_en": {"type": "text", "analyzer": "english"},
                        "title_combined": {"type": "text"},
                        "concordance": {"type": "keyword"},
                        "ipc_part": {"type": "keyword"},
                        "theme": {"type": "text"},
                        "num_families": {"type": "integer"},
                        "num_documents": {"type": "integer"},
                        "is_head": {"type": "boolean"},
                        "subsection_title_ja": {"type": "text"},
                        "subsection_title_en": {"type": "text"},
                        "embedding": {
                            "type": "knn_vector",
                            "dimension": self.embedding_dim,
                            "method": {
                                "name": "hnsw",
                                "space_type": "cosinesimil",
                                "engine": "nmslib",
                                "parameters": {
                                    "ef_construction": 128,
                                    "m": 24
                                }
                            }
                        }
                    }
                }
            }

        # Create indices
        for classification_type in ['ipc', 'cpc', 'fi']:
            index_name = f"patent_classification_{classification_type}"

            if self.client.indices.exists(index=index_name):
                print(f"Deleting existing index: {index_name}")
                self.client.indices.delete(index=index_name)

            print(f"Creating index: {index_name}")
            self.client.indices.create(
                index=index_name,
                body=get_mapping(classification_type)
            )

    def parse_ipc_file(self, file_path: str) -> List[Dict[str, Any]]:
        """Parse IPC classification file"""
        records = []

        with open_with_encoding(file_path) as f:
            for line_num, line in enumerate(f, 1):
                try:
                    parts = line.strip().split('\t')
                    if len(parts) >= 4:  # Minimum: code, level, title_ja, title_en
                        # Parse level safely
                        level = 0
                        if len(parts) > 1 and parts[1].strip():
                            try:
                                level = int(parts[1].strip())
                            except (ValueError, UnicodeDecodeError):
                                level = 0

                        # Parse num_families safely
                        num_families = 0
                        if len(parts) > 4 and parts[4].strip():
                            try:
                                num_families = int(parts[4].strip())
                            except (ValueError, UnicodeDecodeError):
                                num_families = 0

                        record = {
                            'code': parts[0].strip(),
                            'classification_type': 'IPC',
                            'level': level,
                            'title_ja': parts[2].strip() if len(parts) > 2 else '',
                            'title_en': parts[3].strip() if len(parts) > 3 else '',
                            'num_families': num_families,
                            'is_head': False
                        }
                        record['title_combined'] = f"{record['title_en']} {record['title_ja']}"
                        records.append(record)
                except Exception as e:
                    # Skip problematic lines
                    print(f"Skipping line {line_num} in {file_path}: {str(e)[:100]}")
                    continue

        return records

    def parse_ipc_head_file(self, file_path: str) -> List[Dict[str, Any]]:
        """Parse IPC head (subsection) file"""
        records = []

        with open_with_encoding(file_path) as f:
            for line_num, line in enumerate(f, 1):
                try:
                    parts = line.strip().split('\t')
                    if len(parts) >= 3:
                        record = {
                            'code': parts[0].strip(),
                            'classification_type': 'IPC',
                            'subsection_title_ja': parts[1].strip(),
                            'subsection_title_en': parts[2].strip(),
                            'is_head': True,
                            'level': 0
                        }
                        record['title_combined'] = f"{record['subsection_title_en']} {record['subsection_title_ja']}"
                        records.append(record)
                except Exception as e:
                    print(f"Skipping line {line_num} in {file_path}: {str(e)[:100]}")
                    continue

        return records

    def parse_fi_file(self, file_path: str) -> List[Dict[str, Any]]:
        """Parse FI classification file"""
        records = []

        with open_with_encoding(file_path) as f:
            for line_num, line in enumerate(f, 1):
                try:
                    parts = line.strip().split('\t')
                    if len(parts) >= 4:  # Minimum fields
                        # Parse level safely
                        level = 0
                        if len(parts) > 1 and parts[1].strip():
                            try:
                                level = int(parts[1].strip())
                            except (ValueError, UnicodeDecodeError):
                                level = 0

                        # Parse num_documents safely
                        num_documents = 0
                        if len(parts) > 5 and parts[5].strip():
                            try:
                                num_documents = int(parts[5].strip())
                            except (ValueError, UnicodeDecodeError):
                                num_documents = 0

                        record = {
                            'code': parts[0].strip(),
                            'classification_type': 'FI',
                            'level': level,
                            'theme': parts[3].strip() if len(parts) > 3 else '',
                            'concordance': parts[4].strip() if len(parts) > 4 else '',
                            'num_documents': num_documents,
                            'title_ja': parts[6].strip() if len(parts) > 6 else '',
                            'title_en': parts[7].strip() if len(parts) > 7 else '',
                            'is_head': False
                        }
                        record['title_combined'] = f"{record['title_en']} {record['title_ja']} {record['theme']}"
                        records.append(record)
                except Exception as e:
                    print(f"Skipping line {line_num} in {file_path}: {str(e)[:100]}")
                    continue

        return records

    def parse_fi_head_file(self, file_path: str) -> List[Dict[str, Any]]:
        """Parse FI head file"""
        records = []

        with open_with_encoding(file_path) as f:
            for line_num, line in enumerate(f, 1):
                try:
                    parts = line.strip().split('\t')
                    if len(parts) >= 3:
                        record = {
                            'code': parts[0].strip(),
                            'classification_type': 'FI',
                            'subsection_title_ja': parts[1].strip(),
                            'subsection_title_en': parts[2].strip(),
                            'is_head': True,
                            'level': 0
                        }
                        record['title_combined'] = f"{record['subsection_title_en']} {record['subsection_title_ja']}"
                        records.append(record)
                except Exception as e:
                    print(f"Skipping line {line_num} in {file_path}: {str(e)[:100]}")
                    continue

        return records

    def parse_cpc_interleave_file(self, file_path: str) -> List[Dict[str, Any]]:
        """Parse CPC interleave file"""
        records = []

        with open_with_encoding(file_path) as f:
            for line_num, line in enumerate(f, 1):
                try:
                    parts = line.strip().split('\t')
                    if len(parts) >= 4:  # Minimum fields
                        # Parse level safely
                        level = 0
                        if len(parts) > 1 and parts[1].strip():
                            try:
                                level = int(parts[1].strip())
                            except (ValueError, UnicodeDecodeError):
                                level = 0

                        # Parse num_families safely
                        num_families = 0
                        if len(parts) > 6 and parts[6].strip():
                            try:
                                num_families = int(parts[6].strip())
                            except (ValueError, UnicodeDecodeError):
                                num_families = 0

                        record = {
                            'code': parts[0].strip(),
                            'classification_type': 'CPC',
                            'level': level,
                            'title_en': parts[2].strip() if len(parts) > 2 else '',
                            'concordance': parts[3].strip() if len(parts) > 3 else '',
                            'ipc_part': parts[4].strip() if len(parts) > 4 else '',
                            'title_ja': parts[5].strip() if len(parts) > 5 else '',
                            'num_families': num_families,
                            'is_head': False
                        }
                        record['title_combined'] = f"{record['title_en']} {record['title_ja']}"
                        records.append(record)
                except Exception as e:
                    print(f"Skipping line {line_num} in {file_path}: {str(e)[:100]}")
                    continue

        return records

    def parse_cpc_head_file(self, file_path: str) -> List[Dict[str, Any]]:
        """Parse CPC head file"""
        records = []

        with open_with_encoding(file_path) as f:
            for line_num, line in enumerate(f, 1):
                try:
                    parts = line.strip().split('\t')
                    if len(parts) >= 2:
                        record = {
                            'code': parts[0].strip(),
                            'classification_type': 'CPC',
                            'subsection_title_en': parts[1].strip(),
                            'is_head': True,
                            'level': 0
                        }
                        record['title_combined'] = record['subsection_title_en']
                        records.append(record)
                except Exception as e:
                    print(f"Skipping line {line_num} in {file_path}: {str(e)[:100]}")
                    continue

        return records

    def add_embeddings(self, records: List[Dict[str, Any]], batch_size: int = 32) -> List[Dict[str, Any]]:
        """Add embeddings to records"""
        texts = [rec.get('title_combined', '') for rec in records]

        print(f"Generating embeddings for {len(texts)} records...")
        embeddings = self.model.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=True,
            convert_to_numpy=True
        )

        for record, embedding in zip(records, embeddings):
            record['embedding'] = embedding.tolist()

        return records

    def bulk_index(self, records: List[Dict[str, Any]], index_name: str, batch_size: int = 500):
        """Bulk index records into OpenSearch"""

        def generate_actions():
            for record in records:
                yield {
                    '_index': index_name,
                    '_source': record
                }

        print(f"Indexing {len(records)} records into {index_name}...")
        success, failed = helpers.bulk(
            self.client,
            generate_actions(),
            chunk_size=batch_size,
            request_timeout=60
        )

        print(f"Indexed {success} records, {failed} failed")
        return success, failed

    def import_classification_data(self, data_dir: str = "data_20250812"):
        """Import all classification data"""

        # Import IPC data
        print("\n=== Importing IPC Data ===")
        ipc_records = []

        # IPC main data
        ipc_files = glob.glob(os.path.join(data_dir, "data_ipc", "*.txt"))
        for file_path in tqdm(ipc_files, desc="Reading IPC files"):
            ipc_records.extend(self.parse_ipc_file(file_path))

        # IPC head data
        ipc_head_files = glob.glob(os.path.join(data_dir, "data_ipc_head", "*.txt"))
        for file_path in tqdm(ipc_head_files, desc="Reading IPC head files"):
            ipc_records.extend(self.parse_ipc_head_file(file_path))

        # Add embeddings and index
        if ipc_records:
            ipc_records = self.add_embeddings(ipc_records)
            self.bulk_index(ipc_records, "patent_classification_ipc")

        # Import FI data
        print("\n=== Importing FI Data ===")
        fi_records = []

        # FI main data
        fi_files = glob.glob(os.path.join(data_dir, "data_fi", "*.txt"))
        for file_path in tqdm(fi_files, desc="Reading FI files"):
            fi_records.extend(self.parse_fi_file(file_path))

        # FI head data
        fi_head_files = glob.glob(os.path.join(data_dir, "data_fi_head", "*.txt"))
        for file_path in tqdm(fi_head_files, desc="Reading FI head files"):
            fi_records.extend(self.parse_fi_head_file(file_path))

        # Add embeddings and index
        if fi_records:
            fi_records = self.add_embeddings(fi_records)
            self.bulk_index(fi_records, "patent_classification_fi")

        # Import CPC data
        print("\n=== Importing CPC Data ===")
        cpc_records = []

        # CPC interleave data
        cpc_files = glob.glob(os.path.join(data_dir, "data_cpc_interleave", "*.txt"))
        for file_path in tqdm(cpc_files, desc="Reading CPC files"):
            cpc_records.extend(self.parse_cpc_interleave_file(file_path))

        # CPC head data
        cpc_head_files = glob.glob(os.path.join(data_dir, "data_cpc_interleave_head", "*.txt"))
        for file_path in tqdm(cpc_head_files, desc="Reading CPC head files"):
            cpc_records.extend(self.parse_cpc_head_file(file_path))

        # Add embeddings and index
        if cpc_records:
            cpc_records = self.add_embeddings(cpc_records)
            self.bulk_index(cpc_records, "patent_classification_cpc")

        # Refresh indices
        print("\n=== Refreshing indices ===")
        self.client.indices.refresh(index="patent_classification_*")

        # Print statistics
        print("\n=== Import Statistics ===")
        for classification_type in ['ipc', 'cpc', 'fi']:
            index_name = f"patent_classification_{classification_type}"
            count = self.client.count(index=index_name)['count']
            print(f"{classification_type.upper()}: {count:,} records")


def main():
    """Main import function"""
    import argparse

    parser = argparse.ArgumentParser(description="Import patent classification data")
    parser.add_argument("--host", default="localhost", help="OpenSearch host")
    parser.add_argument("--port", type=int, default=9200, help="OpenSearch port")
    parser.add_argument("--data-dir", default="data_20250812", help="Data directory")
    parser.add_argument("--model", default="paraphrase-multilingual-mpnet-base-v2",
                       help="Sentence transformer model")

    args = parser.parse_args()

    # Wait for OpenSearch to be ready
    print("Waiting for OpenSearch to be ready...")
    time.sleep(10)

    # Create importer and run
    importer = PatentClassificationImporter(
        opensearch_host=args.host,
        opensearch_port=args.port,
        embedding_model=args.model
    )

    # Create indices
    importer.create_indices()

    # Import data
    importer.import_classification_data(data_dir=args.data_dir)

    print("\n✓ Import completed successfully!")


if __name__ == "__main__":
    main()
