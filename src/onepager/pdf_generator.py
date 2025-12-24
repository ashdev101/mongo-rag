from reportlab.lib.pagesizes import A4
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle,
    Paragraph, Spacer
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.lib import colors
from reportlab.lib.units import mm
import os


def generate_one_pager(payload: dict):
    if "basic_info" not in payload or "first name" not in payload["basic_info"]:
        raise ValueError("Invalid payload: basic_info with name is required")
    name = f"{payload['basic_info'].get('first name', '')} {payload['basic_info'].get('last name', '')}".strip()
    
    # Create the files directory if it doesn't exist
    file_dir = "onepager/files"
    os.makedirs(file_dir, exist_ok=True)
    
    file_name = os.path.join(file_dir, f"One Pager Doc-{name}.pdf")

    # Footer
    def draw_footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 9)
        canvas.setFillColor(colors.grey)
        canvas.drawCentredString(
            A4[0] / 2,
            15 * mm,
            "Note: This document is system-generated."
        )
        canvas.restoreState()

    doc = SimpleDocTemplate(
        file_name,
        pagesize=A4,
        rightMargin=20,
        leftMargin=20,
        topMargin=20,
        bottomMargin=30
    )

    styles = getSampleStyleSheet()

    heading_style = ParagraphStyle(
        name="MainHeading",
        parent=styles["Heading1"]
    )

    section_style = ParagraphStyle(
        name="SectionHeading",
        parent=styles["Heading4"]
    )

    elements = []

    # Main Heading
    elements.append(Paragraph(f"One Pager Document: {name}", heading_style))
    elements.append(Spacer(1, 10))

    def clean_key(key: str) -> str:
        key = key.replace("_", " ").strip()
        return " ".join(word.capitalize() for word in key.split())
    
    def build_list_as_kv(items: list):
        rows = [["Field", "Data"]]

        for item in items:
            for k, v in item.items():
                if k in ("_id", "employee code"):
                    continue
                rows.append([clean_key(k), "" if v is None else str(v)])

        table = Table(rows, colWidths=[180, 355], rowHeights=20)
        table.setStyle(common_table_style)
        return table


    def build_kv_table(data: dict, allow_employee_code: bool):
        rows = [["Field", "Data"]]
        for k, v in data.items():
            if k == "_id":
                continue
            if k == "employee code" and not allow_employee_code:
                continue
            rows.append([clean_key(k), "" if v is None else str(v)])

        table = Table(rows, colWidths=[180, 355], rowHeights=20)
        table.setStyle(common_table_style)
        return table

    def build_list_table(items: list):
        if not items:
            return None

        keys = [
            k for k in items[0].keys()
            if k != "_id" and k != "employee code"
        ]

        header = [clean_key(k) for k in keys]
        rows = [header]

        for item in items:
            row = ["" if item.get(k) is None else str(item.get(k)) for k in keys]
            rows.append(row)

        col_width = (535 / len(keys))
        table = Table(rows, colWidths=[col_width] * len(keys), rowHeights=20)
        table.setStyle(common_table_style)
        return table

    common_table_style = TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 11),
        ("ALIGN", (0, 0), (-1, 0), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),

        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 1), (-1, -1), 10),

        ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ])

    # Iterate sections
    for section, content in payload.items():
        if section in ["status", "success","employee_code"]:
            continue

        elements.append(Spacer(1, 18))
        elements.append(Paragraph(clean_key(section), section_style))
        elements.append(Spacer(1, 5))

        if isinstance(content, dict):
            allow_emp_code = section == "basic_info"
            elements.append(build_kv_table(content, allow_emp_code))

        elif isinstance(content, list):

            # Render performance education work experience vertically
            if section == "performance_education_work_experience":
                elements.append(build_list_as_kv(content))

            else:
                table = build_list_table(content)
                if table:
                    elements.append(table)


    doc.build(
        elements,
        onFirstPage=draw_footer,
        onLaterPages=draw_footer
    )

    return file_name
 