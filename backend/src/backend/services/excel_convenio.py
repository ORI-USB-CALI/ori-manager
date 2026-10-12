"""Servicio de exportación de convenios en formato Excel (.xlsx)

Genera un libro OpenXML (.xlsx) válido utilizando la biblioteca estándar de Python (zipfile + xml).
"""

from __future__ import annotations

import io
import zipfile
from xml.sax.saxutils import escape

from sqlalchemy.orm import Session

from backend.schemas.exportacion import ConvenioPdfDTO
from backend.services.pdf_convenio import ServicioPdfConvenio


class ServicioExcelConvenio:
    """Generador de libros Excel (.xlsx) para reportes de convenios."""

    def generar_excel(self, convenio_id: int, db: Session) -> bytes:
        """Obtiene la información estructurada del convenio y genera el archivo .xlsx en memoria."""
        # Reutilizamos el mapeo estructurado e invariante a DTO (CA-02: aislamiento de datos)
        dto = ServicioPdfConvenio().mapear_convenio_a_dto(convenio_id, db)
        return self._construir_xlsx(dto)

    def _construir_xlsx(self, dto: ConvenioPdfDTO) -> bytes:
        filas: list[list[str]] = [
            ["UNIVERSIDAD DE SAN BUENAVENTURA CALI - ORI"],
            [f"REPORTE OFICIAL DE CONVENIO - {dto.codigo}"],
            [],
            ["INFORMACIÓN GENERAL", ""],
            ["Código del Convenio", dto.codigo],
            ["Título / Objeto", dto.objeto],
            ["Tipo de Convenio", dto.tipo_convenio],
            ["Alcance Territorial", dto.alcance],
            ["Estado Actual", dto.estado],
            [
                "Fecha de Inicio",
                str(dto.fecha_inicio) if dto.fecha_inicio else "Por definir",
            ],
            [
                "Fecha de Finalización",
                (
                    str(dto.fecha_vencimiento)
                    if dto.fecha_vencimiento
                    else "Por definir"
                ),
            ],
            [
                "Unidad Organizacional",
                dto.solicitante_unidad or "No especificada",
            ],
            ["Entidad Aliada", dto.aliado_nombre or "No especificada"],
            ["País Aliado", dto.aliado_pais or "Colombia"],
            [
                "Compromisos Financieros",
                dto.implicacion_financiera
                or "Sin compromisos financieros declarados",
            ],
            [],
            ["FIRMANTE(S) REGISTRADO(S)", "CARGO", "ENTIDAD", "ESTADO FIRMA"],
        ]

        if dto.firmantes:
            for f in dto.firmantes:
                filas.append(
                    [
                        f"{f.nombre} ({f.rol})",
                        f.cargo or "N/A",
                        f.parte,
                        f.estado,
                    ]
                )
        else:
            filas.append(["No se han configurado firmantes", "", "", ""])

        return self._generar_archivo_xlsx(filas)

    def _generar_archivo_xlsx(self, filas: list[list[str]]) -> bytes:
        sheet_rows: list[str] = []
        for row_idx, fila in enumerate(filas, start=1):
            cell_strs: list[str] = []
            for col_idx, valor in enumerate(fila, start=1):
                col_letter = self._col_num_to_letter(col_idx)
                texto_escapado = escape(str(valor))
                cell_strs.append(
                    f'<c r="{col_letter}{row_idx}" t="inlineStr"><is><t>{texto_escapado}</t></is></c>'
                )
            sheet_rows.append(f'<row r="{row_idx}">{"".join(cell_strs)}</row>')

        sheet_xml = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">\n'
            f"<sheetData>{''.join(sheet_rows)}</sheetData>\n"
            "</worksheet>"
        )

        content_types_xml = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">\n'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>\n'
            '<Default Extension="xml" ContentType="application/xml"/>\n'
            '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>\n'
            '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>\n'
            "</Types>"
        )

        rels_xml = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">\n'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>\n'
            "</Relationships>"
        )

        workbook_rels_xml = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">\n'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>\n'
            "</Relationships>"
        )

        workbook_xml = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">\n'
            '<sheets><sheet name="Convenio" sheetId="1" r:id="rId1"/></sheets>\n'
            "</workbook>"
        )

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("[Content_Types].xml", content_types_xml)
            zf.writestr("_rels/.rels", rels_xml)
            zf.writestr("xl/_rels/workbook.xml.rels", workbook_rels_xml)
            zf.writestr("xl/workbook.xml", workbook_xml)
            zf.writestr("xl/worksheets/sheet1.xml", sheet_xml)

        return buf.getvalue()

    @staticmethod
    def _col_num_to_letter(num: int) -> str:
        letter = ""
        while num > 0:
            num, remainder = divmod(num - 1, 26)
            letter = chr(65 + remainder) + letter
        return letter
