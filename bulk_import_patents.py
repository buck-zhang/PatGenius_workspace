#!/usr/bin/env python3
"""
Bulk import script for Japanese patent XML files to OpenSearch
Based on opensearch_tags_analysis.json recommendations
"""

import xml.etree.ElementTree as ET
import json
import requests
import os
import sys
import glob
from typing import Dict, List, Any, Iterator
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import logging
from datetime import datetime

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('patent_import.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class PatentBulkImporter:
    def __init__(self, opensearch_url: str = "http://localhost:9200", index_name: str = "patents"):
        self.opensearch_url = opensearch_url
        self.index_name = index_name
        self.session = requests.Session()
        self.batch_size = 100
        self.max_workers = 4
        
    def extract_text_content(self, element) -> str:
        """Extract text content from XML element, handling nested elements"""
        if element is None:
            return ""
        
        text_parts = []
        
        def collect_text(elem):
            if elem.text:
                text_parts.append(elem.text.strip())
            for child in elem:
                collect_text(child)
                if child.tail:
                    text_parts.append(child.tail.strip())
        
        collect_text(element)
        return " ".join(text_parts).strip()

    def parse_patent_xml(self, xml_file_path: str) -> Dict[str, Any]:
        """Parse Japanese patent XML file with optimized field extraction"""
        
        try:
            tree = ET.parse(xml_file_path)
            root = tree.getroot()
            
            # Define namespace
            ns = {'jp': 'http://www.jpo.go.jp'}
            
            patent_data = {}
            
            # Extract bibliographic data
            biblio_data = root.find('bibliographic-data')
            if biblio_data is not None:
                
                # Publication reference - 基本文献情報
                pub_ref = biblio_data.find('publication-reference/document-id')
                if pub_ref is not None:
                    patent_data['document_id'] = self.extract_text_content(pub_ref.find('doc-number'))
                    patent_data['kind'] = self.extract_text_content(pub_ref.find('kind'))
                    patent_data['date'] = self.extract_text_content(pub_ref.find('date'))
                    patent_data['country'] = self.extract_text_content(pub_ref.find('country'))
                
                # Application reference - 出願情報
                app_ref = biblio_data.find('application-reference/document-id')
                if app_ref is not None:
                    patent_data['application_number'] = self.extract_text_content(app_ref.find('doc-number'))
                    patent_data['application_date'] = self.extract_text_content(app_ref.find('date'))
                
                # Invention title - 発明名称
                title_elem = biblio_data.find('invention-title')
                if title_elem is not None:
                    patent_data['invention_title'] = self.extract_text_content(title_elem)
                
                # Parties - 出願人・発明者情報
                parties = biblio_data.find('parties')
                if parties is not None:
                    # Applicants - 出願人
                    applicants = []
                    for applicant in biblio_data.findall('.//applicant'):
                        name_elem = applicant.find('.//name') or applicant.find('.//n')
                        if name_elem is not None:
                            applicants.append(self.extract_text_content(name_elem))
                    patent_data['applicant_name'] = "; ".join(applicants) if applicants else ""
                    
                    # Inventors - 発明者
                    inventors = []
                    for inventor in biblio_data.findall('.//inventor'):
                        name_elem = inventor.find('.//name') or inventor.find('.//n')
                        if name_elem is not None:
                            inventors.append(self.extract_text_content(name_elem))
                    patent_data['inventor_names'] = "; ".join(inventors) if inventors else ""
                
                # Priority claims - 優先権情報
                priority_claims = []
                for priority in biblio_data.findall('priority-claims/priority-claim'):
                    claim_data = {}
                    country_elem = priority.find('country')
                    doc_num_elem = priority.find('doc-number')
                    date_elem = priority.find('date')
                    
                    if country_elem is not None:
                        claim_data['country'] = self.extract_text_content(country_elem)
                    if doc_num_elem is not None:
                        claim_data['doc_number'] = self.extract_text_content(doc_num_elem)
                    if date_elem is not None:
                        claim_data['date'] = self.extract_text_content(date_elem)
                    
                    if claim_data:
                        priority_claims.append(claim_data)
                
                patent_data['priority_claims'] = priority_claims
                
                # IPC Classification - 国際特許分類
                ipc_elem = biblio_data.find('classification-ipc')
                if ipc_elem is not None:
                    ipc_classes = []
                    main_clsf = ipc_elem.find('main-clsf')
                    if main_clsf is not None:
                        ipc_classes.append(self.extract_text_content(main_clsf).strip())
                    
                    for further_clsf in ipc_elem.findall('further-clsf'):
                        ipc_classes.append(self.extract_text_content(further_clsf).strip())
                    
                    patent_data['classification_ipc'] = ipc_classes
                
                # National Classification - 国内分類
                nat_class_elem = biblio_data.find('classification-national')
                if nat_class_elem is not None:
                    nat_classes = []
                    main_clsf = nat_class_elem.find('main-clsf')
                    if main_clsf is not None:
                        nat_classes.append(self.extract_text_content(main_clsf).strip())
                    
                    for further_clsf in nat_class_elem.findall('further-clsf'):
                        nat_classes.append(self.extract_text_content(further_clsf).strip())
                    
                    patent_data['classification_national'] = nat_classes
                
                # F-terms - Fターム
                f_terms = []
                f_term_info = biblio_data.find('.//jp:f-term-info', ns)
                if f_term_info is not None:
                    for f_term in f_term_info.findall('.//jp:f-term', ns):
                        f_terms.append(self.extract_text_content(f_term))
                patent_data['f_terms'] = f_terms
            
            # Extract description content - 明細書内容
            description = root.find('description')
            if description is not None:
                
                # Technical field - 技術分野
                tech_field = description.find('technical-field')
                if tech_field is not None:
                    patent_data['technical_field'] = self.extract_text_content(tech_field)
                
                # Background art - 背景技術
                bg_art = description.find('background-art')
                if bg_art is not None:
                    patent_data['background_art'] = self.extract_text_content(bg_art)
                
                # Technical problem - 解決課題
                tech_problem = description.find('.//tech-problem')
                if tech_problem is not None:
                    patent_data['tech_problem'] = self.extract_text_content(tech_problem)
                
                # Technical solution - 解決手段
                tech_solution = description.find('.//tech-solution')
                if tech_solution is not None:
                    patent_data['tech_solution'] = self.extract_text_content(tech_solution)
                
                # Advantageous effects - 発明の効果
                adv_effects = description.find('.//advantageous-effects')
                if adv_effects is not None:
                    patent_data['advantageous_effects'] = self.extract_text_content(adv_effects)
                
                # Best mode (detailed description) - 実施例
                best_mode = description.find('best-mode')
                if best_mode is not None:
                    patent_data['description'] = self.extract_text_content(best_mode)
            
            # Extract claims - 請求項
            claims_elem = root.find('claims')
            if claims_elem is not None:
                claims_text = []
                for claim in claims_elem.findall('claim'):
                    claim_num = claim.get('num', '')
                    claim_text = self.extract_text_content(claim.find('claim-text'))
                    if claim_text:
                        claims_text.append(f"Claim {claim_num}: {claim_text}")
                patent_data['claims'] = " ".join(claims_text)
            
            # Extract abstract - 要約
            abstract_elem = root.find('abstract')
            if abstract_elem is not None:
                patent_data['abstract'] = self.extract_text_content(abstract_elem)
            
            return patent_data
            
        except ET.ParseError as e:
            logger.error(f"XML parsing error in {xml_file_path}: {e}")
            return {}
        except Exception as e:
            logger.error(f"Error parsing XML {xml_file_path}: {e}")
            return {}

    def create_optimized_index(self):
        """Create optimized index based on opensearch_tags_analysis.json"""
        
        index_settings = {
            "settings": {
                "number_of_shards": 3,
                "number_of_replicas": 1,
                "analysis": {
                    "analyzer": {
                        "japanese_analyzer": {
                            "type": "standard",
                            "stopwords": "_japanese_"
                        }
                    }
                }
            },
            "mappings": {
                "properties": {
                    "document_id": {"type": "keyword"},
                    "invention_title": {"type": "text", "analyzer": "japanese_analyzer"},
                    "applicant_name": {"type": "text", "analyzer": "japanese_analyzer"},
                    "inventor_names": {"type": "text", "analyzer": "japanese_analyzer"},
                    "classification_ipc": {"type": "keyword"},
                    "classification_national": {"type": "keyword"},
                    "f_terms": {"type": "keyword"},
                    "technical_field": {"type": "text", "analyzer": "japanese_analyzer"},
                    "background_art": {"type": "text", "analyzer": "japanese_analyzer"},
                    "tech_problem": {"type": "text", "analyzer": "japanese_analyzer"},
                    "tech_solution": {"type": "text", "analyzer": "japanese_analyzer"},
                    "advantageous_effects": {"type": "text", "analyzer": "japanese_analyzer"},
                    "description": {"type": "text", "analyzer": "japanese_analyzer"},
                    "claims": {"type": "text", "analyzer": "japanese_analyzer"},
                    "abstract": {"type": "text", "analyzer": "japanese_analyzer"},
                    "date": {"type": "date", "format": "yyyyMMdd"},
                    "application_date": {"type": "date", "format": "yyyyMMdd"},
                    "priority_claims": {"type": "nested"},
                    "kind": {"type": "keyword"},
                    "country": {"type": "keyword"},
                    "application_number": {"type": "keyword"}
                }
            }
        }
        
        try:
            # Delete existing index if it exists
            response = self.session.delete(f"{self.opensearch_url}/{self.index_name}")
            logger.info(f"Deleted existing index: {response.status_code}")
        except:
            pass
        
        # Create new optimized index
        response = self.session.put(
            f"{self.opensearch_url}/{self.index_name}",
            json=index_settings,
            headers={'Content-Type': 'application/json'}
        )
        
        if response.status_code in [200, 201]:
            logger.info(f"Successfully created optimized index '{self.index_name}'")
            return True
        else:
            logger.error(f"Failed to create index: {response.status_code} - {response.text}")
            return False

    def bulk_index_documents(self, documents: List[Dict[str, Any]]) -> bool:
        """Bulk index documents to OpenSearch"""
        
        if not documents:
            return True
        
        # Prepare bulk request body
        bulk_body = []
        for doc in documents:
            doc_id = doc.get('document_id', 'unknown')
            
            # Add index action
            bulk_body.append(json.dumps({
                "index": {
                    "_index": self.index_name,
                    "_id": doc_id
                }
            }))
            
            # Add document
            bulk_body.append(json.dumps(doc, ensure_ascii=False))
        
        bulk_data = "\n".join(bulk_body) + "\n"
        
        try:
            response = self.session.post(
                f"{self.opensearch_url}/_bulk",
                data=bulk_data,
                headers={'Content-Type': 'application/x-ndjson'}
            )
            
            if response.status_code == 200:
                result = response.json()
                errors = result.get('errors', False)
                if not errors:
                    logger.info(f"Successfully indexed {len(documents)} documents")
                    return True
                else:
                    logger.warning(f"Some documents had indexing errors")
                    return False
            else:
                logger.error(f"Bulk index failed: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Error during bulk indexing: {e}")
            return False

    def process_xml_file(self, xml_file_path: str) -> Dict[str, Any]:
        """Process a single XML file"""
        try:
            return self.parse_patent_xml(xml_file_path)
        except Exception as e:
            logger.error(f"Error processing {xml_file_path}: {e}")
            return {}

    def find_xml_files(self, source_dir: str) -> List[str]:
        """Find all XML files in source directory"""
        xml_files = []
        pattern = os.path.join(source_dir, "**", "*.txt")
        
        for file_path in glob.glob(pattern, recursive=True):
            # Skip hidden files
            if not os.path.basename(file_path).startswith('._'):
                xml_files.append(file_path)
        
        return xml_files

    def import_all_patents(self, source_dir: str = "source_data"):
        """Import all patent XML files from source directory"""
        
        logger.info("Starting bulk patent import process...")
        
        # Create optimized index
        if not self.create_optimized_index():
            logger.error("Failed to create index. Aborting import.")
            return False
        
        # Find all XML files
        xml_files = self.find_xml_files(source_dir)
        total_files = len(xml_files)
        
        logger.info(f"Found {total_files} XML files to process")
        
        if total_files == 0:
            logger.warning("No XML files found")
            return False
        
        # Process files in batches
        processed_count = 0
        failed_count = 0
        batch_documents = []
        
        start_time = time.time()
        
        for i, xml_file in enumerate(xml_files):
            
            # Process XML file
            patent_data = self.process_xml_file(xml_file)
            
            if patent_data:
                batch_documents.append(patent_data)
                processed_count += 1
            else:
                failed_count += 1
            
            # Bulk index when batch is full or at the end
            if len(batch_documents) >= self.batch_size or i == total_files - 1:
                if batch_documents:
                    success = self.bulk_index_documents(batch_documents)
                    if not success:
                        logger.error(f"Failed to index batch at file {i}")
                    
                    batch_documents = []
            
            # Progress logging
            if (i + 1) % 1000 == 0:
                elapsed = time.time() - start_time
                rate = (i + 1) / elapsed
                eta = (total_files - i - 1) / rate if rate > 0 else 0
                
                logger.info(f"Progress: {i+1}/{total_files} ({((i+1)/total_files)*100:.1f}%) "
                          f"- Rate: {rate:.1f} files/sec - ETA: {eta/60:.1f} min")
        
        # Final statistics
        total_time = time.time() - start_time
        
        logger.info(f"Import completed!")
        logger.info(f"Total files: {total_files}")
        logger.info(f"Successfully processed: {processed_count}")
        logger.info(f"Failed: {failed_count}")
        logger.info(f"Total time: {total_time/60:.1f} minutes")
        logger.info(f"Average rate: {total_files/total_time:.1f} files/second")
        
        return True

def main():
    """Main function"""
    
    if len(sys.argv) > 1:
        source_dir = sys.argv[1]
    else:
        source_dir = "source_data"
    
    logger.info(f"Starting patent import from directory: {source_dir}")
    
    # Initialize importer
    importer = PatentBulkImporter()
    
    # Start import process
    success = importer.import_all_patents(source_dir)
    
    if success:
        logger.info("Patent import process completed successfully!")
        sys.exit(0)
    else:
        logger.error("Patent import process failed!")
        sys.exit(1)

if __name__ == "__main__":
    main()