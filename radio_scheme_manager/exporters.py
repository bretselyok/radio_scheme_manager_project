"""Формирование файлов отчетности.

Отчеты формируются без сторонних библиотек: DOCX и XLSX являются zip-архивами
с XML-файлами, поэтому для учебного проекта достаточно стандартной библиотеки.
Это упрощает запуск в PyCharm и демонстрацию в аудитории.
"""
from __future__ import annotations

import csv
import html
import json
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from .app_config import EXPORT_DIR, ensure_directories
from .calculations import calculate_bom_cost, calculate_economic_effect


def _xml(text: Any) -> str:
    return html.escape("" if text is None else str(text), quote=True)


def _safe_filename(text: str) -> str:
    allowed = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-"
    normalized = []
    for char in text:
        if char in allowed:
            normalized.append(char)
        elif char.isspace() or char in ".,:;/\\|":
            normalized.append("_")
        elif "а" <= char.lower() <= "я" or char in "ёЁ":
            normalized.append(char)
    value = "".join(normalized).strip("_")
    return value or "report"


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def export_csv(path: Path, rows: Sequence[Mapping[str, Any]], headers: Sequence[str] | None = None) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    if headers is None:
        headers = list(rows[0].keys()) if rows else []
    with path.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=list(headers), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in headers})
    return path


def export_json(path: Path, data: Mapping[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _docx_paragraph(text: str, bold: bool = False, heading: bool = False) -> str:
    style = ""
    if heading:
        style = '<w:pPr><w:pStyle w:val="Heading1"/></w:pPr>'
    run_props = "<w:rPr><w:b/></w:rPr>" if bold else ""
    return f"<w:p>{style}<w:r>{run_props}<w:t>{_xml(text)}</w:t></w:r></w:p>"


def _docx_table(headers: Sequence[str], rows: Sequence[Sequence[Any]]) -> str:
    def cell(value: Any, bold: bool = False) -> str:
        run_props = "<w:rPr><w:b/></w:rPr>" if bold else ""
        return f"<w:tc><w:tcPr><w:tcW w:w='2400' w:type='dxa'/></w:tcPr><w:p><w:r>{run_props}<w:t>{_xml(value)}</w:t></w:r></w:p></w:tc>"

    xml_rows = ["<w:tr>" + "".join(cell(header, True) for header in headers) + "</w:tr>"]
    for row in rows:
        xml_rows.append("<w:tr>" + "".join(cell(value) for value in row) + "</w:tr>")
    return "<w:tbl><w:tblPr><w:tblW w:w='0' w:type='auto'/><w:tblBorders><w:top w:val='single' w:sz='4'/><w:left w:val='single' w:sz='4'/><w:bottom w:val='single' w:sz='4'/><w:right w:val='single' w:sz='4'/><w:insideH w:val='single' w:sz='4'/><w:insideV w:val='single' w:sz='4'/></w:tblBorders></w:tblPr>" + "".join(xml_rows) + "</w:tbl>"


def write_docx(path: Path, title: str, paragraphs: Sequence[str], tables: Sequence[tuple[Sequence[str], Sequence[Sequence[Any]]]] | None = None) -> Path:
    """Создает простой DOCX-отчет."""
    path.parent.mkdir(parents=True, exist_ok=True)
    body_parts = [_docx_paragraph(title, bold=True, heading=True)]
    body_parts.append(_docx_paragraph(f"Дата формирования: {datetime.now().strftime('%d.%m.%Y %H:%M')}", bold=False))
    for paragraph in paragraphs:
        if paragraph.strip():
            body_parts.append(_docx_paragraph(paragraph))
    for headers, rows in tables or []:
        body_parts.append(_docx_table(headers, rows))
    body = "".join(body_parts)
    document_xml = f"""<?xml version='1.0' encoding='UTF-8' standalone='yes'?>
<w:document xmlns:w='http://schemas.openxmlformats.org/wordprocessingml/2006/main'>
  <w:body>{body}<w:sectPr><w:pgSz w:w='11906' w:h='16838'/><w:pgMar w:top='1134' w:right='850' w:bottom='1134' w:left='1134'/></w:sectPr></w:body>
</w:document>"""
    styles_xml = """<?xml version='1.0' encoding='UTF-8' standalone='yes'?>
<w:styles xmlns:w='http://schemas.openxmlformats.org/wordprocessingml/2006/main'>
  <w:style w:type='paragraph' w:default='1' w:styleId='Normal'><w:name w:val='Normal'/></w:style>
  <w:style w:type='paragraph' w:styleId='Heading1'><w:name w:val='heading 1'/><w:basedOn w:val='Normal'/><w:next w:val='Normal'/><w:pPr><w:keepNext/></w:pPr><w:rPr><w:b/><w:sz w:val='32'/></w:rPr></w:style>
</w:styles>"""
    rels_xml = """<?xml version='1.0' encoding='UTF-8' standalone='yes'?>
<Relationships xmlns='http://schemas.openxmlformats.org/package/2006/relationships'>
  <Relationship Id='rId1' Type='http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument' Target='word/document.xml'/>
</Relationships>"""
    doc_rels_xml = """<?xml version='1.0' encoding='UTF-8' standalone='yes'?>
<Relationships xmlns='http://schemas.openxmlformats.org/package/2006/relationships'/>"""
    content_types_xml = """<?xml version='1.0' encoding='UTF-8' standalone='yes'?>
<Types xmlns='http://schemas.openxmlformats.org/package/2006/content-types'>
  <Default Extension='rels' ContentType='application/vnd.openxmlformats-package.relationships+xml'/>
  <Default Extension='xml' ContentType='application/xml'/>
  <Override PartName='/word/document.xml' ContentType='application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml'/>
  <Override PartName='/word/styles.xml' ContentType='application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml'/>
</Types>"""
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as docx:
        docx.writestr("[Content_Types].xml", content_types_xml)
        docx.writestr("_rels/.rels", rels_xml)
        docx.writestr("word/_rels/document.xml.rels", doc_rels_xml)
        docx.writestr("word/document.xml", document_xml)
        docx.writestr("word/styles.xml", styles_xml)
    return path


def _xlsx_cell(col_index: int, row_index: int, value: Any) -> str:
    column = ""
    index = col_index
    while index:
        index, remainder = divmod(index - 1, 26)
        column = chr(65 + remainder) + column
    ref = f"{column}{row_index}"
    if isinstance(value, (int, float)) and value is not None:
        return f"<c r='{ref}'><v>{value}</v></c>"
    return f"<c r='{ref}' t='inlineStr'><is><t>{_xml(value)}</t></is></c>"


def write_xlsx(path: Path, sheet_name: str, headers: Sequence[str], rows: Sequence[Sequence[Any]]) -> Path:
    """Создает простой XLSX-файл с одним листом."""
    path.parent.mkdir(parents=True, exist_ok=True)
    all_rows: list[Sequence[Any]] = [headers, *rows]
    row_xml: list[str] = []
    for row_index, row in enumerate(all_rows, start=1):
        cells = "".join(_xlsx_cell(col_index, row_index, value) for col_index, value in enumerate(row, start=1))
        row_xml.append(f"<row r='{row_index}'>{cells}</row>")
    worksheet_xml = f"""<?xml version='1.0' encoding='UTF-8' standalone='yes'?>
<worksheet xmlns='http://schemas.openxmlformats.org/spreadsheetml/2006/main'>
  <sheetData>{''.join(row_xml)}</sheetData>
</worksheet>"""
    workbook_xml = f"""<?xml version='1.0' encoding='UTF-8' standalone='yes'?>
<workbook xmlns='http://schemas.openxmlformats.org/spreadsheetml/2006/main' xmlns:r='http://schemas.openxmlformats.org/officeDocument/2006/relationships'>
  <sheets><sheet name='{_xml(sheet_name[:31])}' sheetId='1' r:id='rId1'/></sheets>
</workbook>"""
    workbook_rels = """<?xml version='1.0' encoding='UTF-8' standalone='yes'?>
<Relationships xmlns='http://schemas.openxmlformats.org/package/2006/relationships'>
  <Relationship Id='rId1' Type='http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet' Target='worksheets/sheet1.xml'/>
</Relationships>"""
    rels_xml = """<?xml version='1.0' encoding='UTF-8' standalone='yes'?>
<Relationships xmlns='http://schemas.openxmlformats.org/package/2006/relationships'>
  <Relationship Id='rId1' Type='http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument' Target='xl/workbook.xml'/>
</Relationships>"""
    content_types_xml = """<?xml version='1.0' encoding='UTF-8' standalone='yes'?>
<Types xmlns='http://schemas.openxmlformats.org/package/2006/content-types'>
  <Default Extension='rels' ContentType='application/vnd.openxmlformats-package.relationships+xml'/>
  <Default Extension='xml' ContentType='application/xml'/>
  <Override PartName='/xl/workbook.xml' ContentType='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml'/>
  <Override PartName='/xl/worksheets/sheet1.xml' ContentType='application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml'/>
</Types>"""
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as xlsx:
        xlsx.writestr("[Content_Types].xml", content_types_xml)
        xlsx.writestr("_rels/.rels", rels_xml)
        xlsx.writestr("xl/workbook.xml", workbook_xml)
        xlsx.writestr("xl/_rels/workbook.xml.rels", workbook_rels)
        xlsx.writestr("xl/worksheets/sheet1.xml", worksheet_xml)
    return path


class ReportBuilder:
    """Формирует предметные отчеты системы."""

    def __init__(self, export_dir: Path = EXPORT_DIR) -> None:
        ensure_directories()
        self.export_dir = Path(export_dir)
        self.export_dir.mkdir(parents=True, exist_ok=True)

    def project_passport(self, data: Mapping[str, Any]) -> Path:
        project = data["project"]
        name = _safe_filename(project.get("code", "project"))
        path = self.export_dir / f"passport_{name}_{_timestamp()}.docx"
        paragraphs = [
            f"Код проекта: {project.get('code')}",
            f"Наименование: {project.get('title')}",
            f"Заказчик: {project.get('customer')}",
            f"Руководитель: {project.get('manager_name', '')}",
            f"Статус: {project.get('status')}",
            f"Приоритет: {project.get('priority')}",
            f"Плановые сроки: {project.get('planned_start')} - {project.get('planned_finish')}",
            f"Бюджет: {project.get('budget')} руб.",
            "Назначение проекта: " + str(project.get("description", "")),
        ]
        tables = [
            (
                ["Стейкхолдер", "Роль", "Влияние", "Контакт"],
                [[row.get("name"), row.get("role"), row.get("influence"), row.get("contact")] for row in data.get("stakeholders", [])],
            ),
            (
                ["Код", "Требование", "Приоритет", "Статус"],
                [[row.get("code"), row.get("title"), row.get("priority"), row.get("status")] for row in data.get("requirements", [])],
            ),
            (
                ["Задача", "Статус", "Прогресс", "Срок"],
                [[row.get("title"), row.get("status"), row.get("progress"), row.get("due_date")] for row in data.get("tasks", [])],
            ),
        ]
        return write_docx(path, "Паспорт проекта", paragraphs, tables)

    def bom_report(self, scheme: Mapping[str, Any], bom_rows: Sequence[Mapping[str, Any]]) -> Path:
        name = _safe_filename(str(scheme.get("code", "scheme")))
        path = self.export_dir / f"bom_{name}_{_timestamp()}.xlsx"
        summary = calculate_bom_cost(bom_rows)
        headers = ["Поз. обозн.", "Артикул", "Наименование", "Категория", "Номинал", "Корпус", "Кол-во", "Цена", "Сумма", "Остаток"]
        rows = [
            [
                row.get("refdes"),
                row.get("part_number"),
                row.get("component_name"),
                row.get("category"),
                row.get("nominal"),
                row.get("footprint"),
                row.get("quantity"),
                row.get("price"),
                row.get("total_price"),
                row.get("stock_qty"),
            ]
            for row in bom_rows
        ]
        rows.append(["", "", "Итого", "", "", "", summary["total_quantity"], "", summary["total_cost"], ""])
        return write_xlsx(path, "BOM", headers, rows)

    def tests_report(self, scheme: Mapping[str, Any], test_rows: Sequence[Mapping[str, Any]]) -> Path:
        name = _safe_filename(str(scheme.get("code", "scheme")))
        path = self.export_dir / f"tests_{name}_{_timestamp()}.docx"
        paragraphs = [
            f"Схема: {scheme.get('code')} - {scheme.get('title')}",
            f"Версия: {scheme.get('version')}",
            f"Статус схемы: {scheme.get('status')}",
            "Отчет содержит перечень проверок, связывающих требования с результатами испытаний.",
        ]
        table_rows = [
            [row.get("name"), row.get("requirement_code", row.get("requirement_id")), row.get("method"), row.get("expected_result"), row.get("actual_result"), row.get("status")]
            for row in test_rows
        ]
        return write_docx(path, "Отчет по испытаниям", paragraphs, [(["Проверка", "Требование", "Метод", "Ожидаемый результат", "Фактический результат", "Статус"], table_rows)])

    def economic_report(self, data: Mapping[str, Any]) -> Path:
        project = data["project"]
        economic = data.get("economic") or {}
        result = calculate_economic_effect(economic)
        name = _safe_filename(str(project.get("code", "project")))
        path = self.export_dir / f"economics_{name}_{_timestamp()}.docx"
        paragraphs = [
            f"Проект: {project.get('code')} - {project.get('title')}",
            "Расчет выполнен по укрупненной методике совокупной стоимости владения и дисконтированного денежного потока.",
            f"Капитальные затраты: {result.capital_costs} руб.",
            f"Годовой эффект: {result.annual_effect} руб.",
            f"Годовые эксплуатационные затраты: {result.annual_operation_cost} руб.",
            f"NPV: {result.npv} руб.",
            f"ROI: {result.roi_percent}%",
            f"Срок окупаемости: {result.payback_years if result.payback_years is not None else 'не достигается'} лет.",
            result.recommendation,
        ]
        rows = [[key, value] for key, value in result.to_dict().items()]
        return write_docx(path, "Оценка экономической эффективности", paragraphs, [(["Показатель", "Значение"], rows)])

    def manager_summary(self, dashboard: Mapping[str, Any]) -> Path:
        path = self.export_dir / f"manager_summary_{_timestamp()}.docx"
        paragraphs = [
            f"Всего проектов: {dashboard.get('projects_total')}",
            f"Активных проектов: {dashboard.get('projects_active')}",
            f"Всего схем: {dashboard.get('schemes_total')}",
            f"Всего задач: {dashboard.get('tasks_total')}",
            f"Просроченных задач: {dashboard.get('tasks_overdue')}",
            f"Непройденных испытаний: {dashboard.get('tests_failed')}",
            f"Высоких рисков: {dashboard.get('risks_high')}",
            f"Суммарный бюджет: {dashboard.get('total_budget')} руб.",
        ]
        top_risks = dashboard.get("details", {}).get("top_risks", [])
        return write_docx(path, "Сводный отчет руководителя", paragraphs, [(["Риск", "Оценка"], [[row.get("title"), row.get("score")] for row in top_risks])])
