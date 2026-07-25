"""
User Results & Data Ingestion Parser.
Parses user project result documents (.docx, .pdf) from the results/ directory,
extracting XML tables (evaluation queries, ground truth vs model predictions),
text paragraphs, and embedded figure images.
"""

import os
import re
import zipfile
import xml.etree.ElementTree as ET
from typing import Dict, List, Any


def parse_user_results_docx(docx_path: str, figures_output_dir: str = "output/figures") -> Dict[str, Any]:
    """
    Parses a Microsoft Word (.docx) project results file.
    Extracts structured evaluation tables (query, ground truth, prediction) and saves images.
    """
    if not os.path.exists(docx_path):
        return {"text": "", "tables": [], "images": []}

    os.makedirs(figures_output_dir, exist_ok=True)

    extracted_images = []
    paragraphs = []
    structured_tables = []

    with zipfile.ZipFile(docx_path, 'r') as z:
        # 1. Extract Embedded Images (graphs, pictures, plots)
        media_files = [f for f in z.namelist() if f.startswith('word/media/')]
        for idx, media_file in enumerate(media_files, start=1):
            ext = os.path.splitext(media_file)[1]
            if not ext:
                ext = ".png"
            target_fig_name = f"fig{idx}{ext}"
            target_fig_path = os.path.join(figures_output_dir, target_fig_name)
            
            with open(target_fig_path, "wb") as f_out:
                f_out.write(z.read(media_file))
            extracted_images.append(target_fig_path)

        # 2. Extract XML Document Text & Structured Tables
        doc_xml = z.read('word/document.xml')
        root = ET.fromstring(doc_xml)
        ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}

        # Extract text paragraphs
        for elem in root.iter():
            if elem.tag.endswith('p'):
                p_text = ''.join(elem.itertext()).strip()
                if p_text:
                    paragraphs.append(p_text)

        # Extract XML tables
        tables = root.findall('.//w:tbl', ns)
        for tbl in tables:
            rows_data = []
            for row in tbl.findall('.//w:tr', ns):
                cells = [''.join(c.itertext()).strip() for c in row.findall('.//w:tc', ns)]
                if cells:
                    rows_data.append(cells)
            if len(rows_data) > 1:
                structured_tables.append(rows_data)

    full_text = "\n".join(paragraphs)

    return {
        "text": full_text[:4000],
        "tables": structured_tables,
        "images": extracted_images
    }


def ingest_all_user_results(results_dir: str = "results", figures_output_dir: str = "output/figures") -> Dict[str, Any]:
    """
    Ingests all project result documents found in the results/ folder.
    """
    if not os.path.exists(results_dir):
        return {"summary": "", "tables": [], "images": []}

    all_docx = [os.path.join(results_dir, f) for f in os.listdir(results_dir) if f.endswith('.docx')]
    
    combined_summary = []
    all_tables = []
    all_images = []

    for docx_path in all_docx:
        res = parse_user_results_docx(docx_path, figures_output_dir=figures_output_dir)
        combined_summary.append(res["text"])
        all_tables.extend(res["tables"])
        all_images.extend(res["images"])

    return {
        "summary": "\n\n".join(combined_summary),
        "tables": all_tables,
        "images": all_images
    }
