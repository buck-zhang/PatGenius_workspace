#!/usr/bin/env python3
"""
Script to parse Japanese patent XML file and import to OpenSearch
"""

import xml.etree.ElementTree as ET
import json
import requests
import re
from typing import Dict, List, Any

def extract_text_content(element) -> str:
    """Extract text content from XML element, handling nested elements"""
    if element is None:
        return ""
    
    # Get all text content including from nested elements
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

def parse_patent_xml(xml_file_path: str) -> Dict[str, Any]:
    """Parse Japanese patent XML file and extract relevant information"""
    
    try:
        tree = ET.parse(xml_file_path)
        root = tree.getroot()
        
        # Define namespace (if any)
        ns = {'jp': 'http://www.jpo.go.jp'}
        
        patent_data = {}
        
        # Extract bibliographic data
        biblio_data = root.find('bibliographic-data')
        if biblio_data is not None:
            
            # Publication reference
            pub_ref = biblio_data.find('publication-reference/document-id')
            if pub_ref is not None:
                patent_data['document_id'] = extract_text_content(pub_ref.find('doc-number'))
                patent_data['kind'] = extract_text_content(pub_ref.find('kind'))
                patent_data['date'] = extract_text_content(pub_ref.find('date'))
            
            # Application reference
            app_ref = biblio_data.find('application-reference/document-id')
            if app_ref is not None:
                patent_data['application_number'] = extract_text_content(app_ref.find('doc-number'))
                patent_data['application_date'] = extract_text_content(app_ref.find('date'))
            
            # Invention title
            title_elem = biblio_data.find('invention-title')
            if title_elem is not None:
                patent_data['invention_title'] = extract_text_content(title_elem)
            
            # Applicants
            applicants = []
            for applicant in biblio_data.findall('.//applicant'):
                name_elem = applicant.find('.//n')
                if name_elem is not None:
                    applicants.append(extract_text_content(name_elem))
            patent_data['applicant_name'] = "; ".join(applicants)
            
            # Inventors
            inventors = []
            for inventor in biblio_data.findall('.//inventor'):
                name_elem = inventor.find('.//n')
                if name_elem is not None:
                    inventors.append(extract_text_content(name_elem))
            patent_data['inventor_names'] = "; ".join(inventors)
            
            # Priority claims
            priority_claims = []
            for priority in biblio_data.findall('priority-claims/priority-claim'):
                claim_data = {}
                country_elem = priority.find('country')
                doc_num_elem = priority.find('doc-number')
                date_elem = priority.find('date')
                
                if country_elem is not None:
                    claim_data['country'] = extract_text_content(country_elem)
                if doc_num_elem is not None:
                    claim_data['doc_number'] = extract_text_content(doc_num_elem)
                if date_elem is not None:
                    claim_data['date'] = extract_text_content(date_elem)
                
                if claim_data:
                    priority_claims.append(claim_data)
            
            patent_data['priority_claims'] = priority_claims
            
            # IPC Classification
            ipc_elem = biblio_data.find('classification-ipc')
            if ipc_elem is not None:
                ipc_classes = []
                main_clsf = ipc_elem.find('main-clsf')
                if main_clsf is not None:
                    ipc_classes.append(extract_text_content(main_clsf).strip())
                
                for further_clsf in ipc_elem.findall('further-clsf'):
                    ipc_classes.append(extract_text_content(further_clsf).strip())
                
                patent_data['classification_ipc'] = ipc_classes
            
            # National Classification
            nat_class_elem = biblio_data.find('classification-national')
            if nat_class_elem is not None:
                nat_classes = []
                main_clsf = nat_class_elem.find('main-clsf')
                if main_clsf is not None:
                    nat_classes.append(extract_text_content(main_clsf).strip())
                
                for further_clsf in nat_class_elem.findall('further-clsf'):
                    nat_classes.append(extract_text_content(further_clsf).strip())
                
                patent_data['classification_national'] = nat_classes
            
            # F-terms
            f_terms = []
            f_term_info = biblio_data.find('.//jp:f-term-info', ns)
            if f_term_info is not None:
                for f_term in f_term_info.findall('.//jp:f-term', ns):
                    f_terms.append(extract_text_content(f_term))
            patent_data['f_terms'] = f_terms
        
        # Extract description content
        description = root.find('description')
        if description is not None:
            
            # Technical field
            tech_field = description.find('technical-field')
            if tech_field is not None:
                patent_data['technical_field'] = extract_text_content(tech_field)
            
            # Background art
            bg_art = description.find('background-art')
            if bg_art is not None:
                patent_data['background_art'] = extract_text_content(bg_art)
            
            # Technical problem
            tech_problem = description.find('.//tech-problem')
            if tech_problem is not None:
                patent_data['tech_problem'] = extract_text_content(tech_problem)
            
            # Technical solution 
            tech_solution = description.find('.//tech-solution')
            if tech_solution is not None:
                patent_data['tech_solution'] = extract_text_content(tech_solution)
            
            # Advantageous effects
            adv_effects = description.find('.//advantageous-effects')
            if adv_effects is not None:
                patent_data['advantageous_effects'] = extract_text_content(adv_effects)
            
            # Best mode (detailed description)
            best_mode = description.find('best-mode')
            if best_mode is not None:
                patent_data['description'] = extract_text_content(best_mode)
        
        # Extract claims
        claims_elem = root.find('claims')
        if claims_elem is not None:
            claims_text = []
            for claim in claims_elem.findall('claim'):
                claim_num = claim.get('num', '')
                claim_text = extract_text_content(claim.find('claim-text'))
                if claim_text:
                    claims_text.append(f"Claim {claim_num}: {claim_text}")
            patent_data['claims'] = " ".join(claims_text)
        
        # Extract abstract
        abstract_elem = root.find('abstract')
        if abstract_elem is not None:
            patent_data['abstract'] = extract_text_content(abstract_elem)
        
        return patent_data
        
    except ET.ParseError as e:
        print(f"XML parsing error: {e}")
        return {}
    except Exception as e:
        print(f"Error parsing XML: {e}")
        return {}

def import_to_opensearch(patent_data: Dict[str, Any], opensearch_url: str = "http://localhost:9200") -> bool:
    """Import patent data to OpenSearch"""
    
    if not patent_data:
        print("No data to import")
        return False
    
    # Use document_id as the document ID in OpenSearch
    doc_id = patent_data.get('document_id', 'unknown')
    
    try:
        # Index the document
        response = requests.post(
            f"{opensearch_url}/patents/_doc/{doc_id}",
            json=patent_data,
            headers={'Content-Type': 'application/json'}
        )
        
        if response.status_code in [200, 201]:
            print(f"Successfully imported patent document {doc_id}")
            return True
        else:
            print(f"Failed to import document {doc_id}: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        print(f"Error importing to OpenSearch: {e}")
        return False

def main():
    xml_file_path = "/Users/ttdc-user/Desktop/workset/patgenius/zhang_opera/sample.txt"
    
    print("Parsing XML file...")
    patent_data = parse_patent_xml(xml_file_path)
    
    if patent_data:
        print("Parsed data:")
        print(json.dumps(patent_data, ensure_ascii=False, indent=2))
        
        print("\nImporting to OpenSearch...")
        success = import_to_opensearch(patent_data)
        
        if success:
            print("Import completed successfully!")
        else:
            print("Import failed!")
    else:
        print("Failed to parse XML file")

if __name__ == "__main__":
    main()