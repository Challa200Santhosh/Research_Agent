"""
Excel Report Generator & Formatter for Autonomous Deep Academic Literature Agent.
Creates OpenPyXL workbooks formatted with custom headers, zebra striping, autowidths,
native =HYPERLINK() formulas, similarity scores, and PermissionError file locking protection.
"""

import os
import datetime
from typing import List, Dict, Any

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side


def export_papers_to_excel(
    papers: List[Dict[str, Any]],
    output_path: str = "output/Research_Papers_Report.xlsx"
) -> str:
    """
    Exports a list of processed paper metadata dictionaries into a styled Excel workbook.
    Includes Similarity Score %, Citations Count, and paper-specific relevance justifications.
    """
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    wb = Workbook()
    ws = wb.active
    ws.title = "Literature Research Report"

    # Ensure Gridlines are Visible
    ws.views.sheetView[0].showGridLines = True

    # Styling Palette
    header_fill = PatternFill(start_color="1F4E79", end_color="1F4E79", fill_type="solid")
    header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    
    center_align = Alignment(horizontal="center", vertical="center", wrap_text=True)
    left_align = Alignment(horizontal="left", vertical="center", wrap_text=True)
    
    thin_side = Side(border_style="thin", color="D9D9D9")
    thin_border = Border(left=thin_side, right=thin_side, top=thin_side, bottom=thin_side)

    # Headers
    headers = [
        "S.No",
        "Paper Title",
        "Publication Year",
        "Citations Count",
        "Title Similarity %",
        "Relevance Justification",
        "DOI / Paper Link"
    ]

    ws.append(headers)

    # Style Header Row
    for col_idx in range(1, len(headers) + 1):
        cell = ws.cell(row=1, column=col_idx)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = center_align

    ws.row_dimensions[1].height = 28

    # Alternate row shading (Zebra striping)
    zebra_fill = PatternFill(start_color="F2F5F9", end_color="F2F5F9", fill_type="solid")
    link_font = Font(name="Calibri", size=10, color="0066CC", underline="single")
    body_font = Font(name="Calibri", size=10)

    for idx, paper in enumerate(papers, start=1):
        row_num = idx + 1
        link_url = paper.get("doi_or_link", "")
        similarity = paper.get("similarity_score", 100.0)

        # Write cells
        ws.cell(row=row_num, column=1, value=idx).alignment = center_align
        ws.cell(row=row_num, column=2, value=paper.get("title", "")).alignment = left_align
        ws.cell(row=row_num, column=3, value=paper.get("year", "N/A")).alignment = center_align
        ws.cell(row=row_num, column=4, value=paper.get("citations", 0)).alignment = center_align
        ws.cell(row=row_num, column=5, value=f"{similarity}%").alignment = center_align
        ws.cell(row=row_num, column=6, value=paper.get("relevance_justification", "")).alignment = left_align

        # Native Excel Hyperlink formula
        cell_link = ws.cell(row=row_num, column=7)
        if link_url:
            cell_link.value = f'=HYPERLINK("{link_url}", "{link_url}")'
            cell_link.font = link_font
        else:
            cell_link.value = "N/A"
            cell_link.font = body_font
        cell_link.alignment = left_align

        # Row styling & borders
        fill_to_apply = zebra_fill if idx % 2 == 0 else PatternFill(fill_type=None)
        for col_idx in range(1, 8):
            c = ws.cell(row=row_num, column=col_idx)
            if idx % 2 == 0:
                c.fill = fill_to_apply
            c.border = thin_border
            if col_idx != 7:
                c.font = body_font

        ws.row_dimensions[row_num].height = 45

    # Column Widths
    column_widths = {
        "A": 8,   # S.No
        "B": 42,  # Title
        "C": 18,  # Year
        "D": 16,  # Citations Count
        "E": 18,  # Title Similarity %
        "F": 55,  # Relevance Justification
        "G": 45   # Link
    }

    for col_letter, width in column_widths.items():
        ws.column_dimensions[col_letter].width = width

    # File Locking Protection
    final_output_path = output_path
    try:
        wb.save(output_path)
    except PermissionError:
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        base, ext = os.path.splitext(output_path)
        final_output_path = f"{base}_{timestamp}{ext}"
        print(f"[WARNING] {output_path} is open in Excel. Saving to {final_output_path}")
        wb.save(final_output_path)

    return os.path.abspath(final_output_path)
