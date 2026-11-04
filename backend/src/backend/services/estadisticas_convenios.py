"""HU-36. Reporte estadístico de convenios agrupados por estado contractual,
vigencia activa, estado y tipo del aliado, y país, descargable en PDF o
Excel. Es de solo lectura: no crea, modifica ni resuelve nada.
"""

from __future__ import annotations

import io
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime
from html import escape as _escapar

from openpyxl import Workbook
from openpyxl.styles import Font
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session, contains_eager

from backend.models.aliado import Aliado
from backend.models.convenio import Convenio
from backend.models.enums import EstadoConvenio, TipoAliado
from backend.models.solicitud_convenio import SolicitudConvenio
from backend.services.reportes import ESTADOS_CONVENIO_ACTIVO

_ESTADOS_CONVENIO_ACTIVO = frozenset(e.value for e in ESTADOS_CONVENIO_ACTIVO)

SIN_PAIS = "Sin país registrado"
SIN_ALIADO = "Sin aliado registrado"
SIN_TIPO = "Sin tipo registrado"
CONTRAPARTE_PROPUESTA = "Contraparte propuesta (sin formalizar)"


@dataclass(frozen=True, slots=True)
class Conteo:
    etiqueta: str
    cantidad: int


@dataclass(frozen=True, slots=True)
class ReporteEstadisticoConvenios:
    datos_suficientes: bool
    total_convenios: int
    por_estado_contractual: list[Conteo] = field(default_factory=list)
    por_vigencia_activa: list[Conteo] = field(default_factory=list)
    por_estado_aliado: list[Conteo] = field(default_factory=list)
    por_tipo_aliado: list[Conteo] = field(default_factory=list)
    por_pais: list[Conteo] = field(default_factory=list)


_ETIQUETAS_TIPO_ALIADO = {tipo.value: tipo.value.replace("_", " ").title() for tipo in TipoAliado}


class ServicioEstadisticasConvenios:
    def __init__(self, db: Session):
        self.db = db

    def generar(
        self,
        *,
        estado: EstadoConvenio | None = None,
        aliado_activo: bool | None = None,
        tipo_aliado: TipoAliado | None = None,
        pais: str | None = None,
    ) -> ReporteEstadisticoConvenios:
        consulta = (
            select(Convenio)
            .join(Convenio.aliado, isouter=True)
            .outerjoin(Convenio.solicitud)
            .options(
                contains_eager(Convenio.aliado).joinedload(Aliado.pais),
                contains_eager(Convenio.solicitud),
            )
            .order_by(Convenio.id)
        )
        if estado is not None:
            consulta = consulta.where(Convenio.estado == estado.value)
        if aliado_activo is not None:
            consulta = consulta.where(Aliado.activo == aliado_activo)
        if tipo_aliado is not None:
            consulta = consulta.where(
                or_(
                    Aliado.tipo == tipo_aliado.value,
                    and_(
                        Convenio.aliado_id.is_(None),
                        SolicitudConvenio.tipo_aliado_propuesto == tipo_aliado.value,
                    ),
                )
            )

        convenios = self.db.scalars(consulta).unique().all()

        # El país se filtra en Python (no en SQL) porque es una coincidencia
        # parcial e insensible a mayúsculas sobre el país formal o propuesto.
        # Ambas relaciones se cargan en la misma consulta, sin N+1.

        termino = " ".join((pais or "").split()).casefold()
        if termino:
            convenios = [
                c
                for c in convenios
                if (nombre := _pais_convenio(c)) and termino in nombre.casefold()
            ]

        if not convenios:
            return ReporteEstadisticoConvenios(datos_suficientes=False, total_convenios=0)

        return ReporteEstadisticoConvenios(
            datos_suficientes=True,
            total_convenios=len(convenios),
            por_estado_contractual=_conteos(c.estado for c in convenios),
            por_vigencia_activa=_conteos(
                "Vigencia activa" if c.estado in _ESTADOS_CONVENIO_ACTIVO else "Vigencia no activa"
                for c in convenios
            ),
            por_estado_aliado=_conteos(
                _etiqueta_estado_aliado(c) for c in convenios
            ),
            por_tipo_aliado=_conteos(
                _ETIQUETAS_TIPO_ALIADO.get(tipo, tipo) if (tipo := _tipo_aliado(c)) else SIN_TIPO
                for c in convenios
            ),
            por_pais=_conteos(
                _pais_convenio(c) or SIN_PAIS
                for c in convenios
            ),
        )


def _tipo_aliado(convenio: Convenio) -> str | None:
    if convenio.aliado is not None:
        return convenio.aliado.tipo
    return convenio.solicitud.tipo_aliado_propuesto if convenio.solicitud else None


def _pais_convenio(convenio: Convenio) -> str:
    if convenio.aliado is not None:
        nombre = convenio.aliado.pais.nombre if convenio.aliado.pais else None
    else:
        nombre = convenio.solicitud.pais_aliado_propuesto if convenio.solicitud else None
    return " ".join((nombre or "").split())


def _etiqueta_estado_aliado(convenio: Convenio) -> str:
    if convenio.aliado is not None:
        return "Aliado activo" if convenio.aliado.activo else "Aliado inactivo"
    solicitud = convenio.solicitud
    if solicitud is None:
        return SIN_ALIADO
    if any(
        valor and valor.strip()
        for valor in (
            solicitud.nombre_aliado_propuesto,
            solicitud.tipo_aliado_propuesto,
            solicitud.pais_aliado_propuesto,
        )
    ):
        return CONTRAPARTE_PROPUESTA
    return SIN_ALIADO


def _conteos(valores) -> list[Conteo]:
    etiquetas: dict[str, str] = {}
    contador: Counter[str] = Counter()
    for valor in valores:
        etiqueta = " ".join(valor.split())
        clave = etiqueta.casefold()
        etiquetas.setdefault(clave, etiqueta)
        contador[clave] += 1
    return [
        Conteo(etiqueta=etiquetas[clave], cantidad=cantidad)
        for clave, cantidad in sorted(contador.items(), key=lambda par: (-par[1], par[0]))
    ]


def _texto_seguro(valor: str) -> str:
    # Mismo criterio que HU-34: forzar texto literal sin modificar la BD.
    return f"'{valor}" if valor.startswith(("=", "+", "-", "@")) else valor


def _tabla_conteos(titulo: str, conteos: list[Conteo], estilos, estilo_celda) -> list:
    elementos: list = [Paragraph(titulo, estilos["Heading3"])]
    if not conteos:
        elementos.append(Paragraph("Sin datos para esta agrupación.", estilos["Normal"]))
        return elementos
    datos = [["Categoría", "Convenios"]] + [
        [Paragraph(_escapar(c.etiqueta), estilo_celda), str(c.cantidad)] for c in conteos
    ]
    tabla = Table(datos, colWidths=[10 * cm, 4 * cm])
    tabla.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F36C21")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
            ]
        )
    )
    elementos.append(tabla)
    return elementos


def generar_pdf_estadisticas_convenios(reporte: ReporteEstadisticoConvenios) -> bytes:
    buffer = io.BytesIO()
    documento = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=1.5 * cm,
        rightMargin=1.5 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
        pageCompression=0,
    )
    estilos = getSampleStyleSheet()
    estilo_celda = ParagraphStyle("CeldaEstadisticas", parent=estilos["Normal"], fontSize=8, leading=9.5)
    elementos = [
        Paragraph("ORI USB Cali — Reporte estadístico de convenios", estilos["Title"]),
        Paragraph(
            f"Generado el {datetime.now(UTC).date().isoformat()} · {reporte.total_convenios} convenio(s)",
            estilos["Normal"],
        ),
        Spacer(1, 0.5 * cm),
    ]
    if not reporte.datos_suficientes:
        elementos.append(
            Paragraph(
                "No hay datos suficientes para generar el reporte estadístico.",
                estilos["Normal"],
            )
        )
    else:
        for titulo, conteos in (
            ("Por estado contractual", reporte.por_estado_contractual),
            ("Por vigencia activa", reporte.por_vigencia_activa),
            ("Por estado del aliado", reporte.por_estado_aliado),
            ("Por tipo de aliado", reporte.por_tipo_aliado),
            ("Por país", reporte.por_pais),
        ):
            elementos.extend(_tabla_conteos(titulo, conteos, estilos, estilo_celda))
            elementos.append(Spacer(1, 0.6 * cm))
    documento.build(elementos)
    return buffer.getvalue()


def generar_excel_estadisticas_convenios(reporte: ReporteEstadisticoConvenios) -> bytes:
    libro = Workbook()
    if not reporte.datos_suficientes:
        hoja = libro.active
        hoja.title = "Estadísticas"
        hoja.append(["No hay datos suficientes para generar el reporte estadístico."])
        buffer = io.BytesIO()
        libro.save(buffer)
        return buffer.getvalue()

    primera = True
    agrupaciones = (
        ("Estado contractual", reporte.por_estado_contractual),
        ("Vigencia activa", reporte.por_vigencia_activa),
        ("Estado del aliado", reporte.por_estado_aliado),
        ("Tipo de aliado", reporte.por_tipo_aliado),
        ("País", reporte.por_pais),
    )
    for titulo, conteos in agrupaciones:
        hoja = libro.active if primera else libro.create_sheet(titulo)
        if primera:
            hoja.title = titulo
            primera = False
        hoja.append(["Categoría", "Convenios"])
        for celda in hoja[1]:
            celda.font = Font(bold=True)
        for conteo in conteos:
            hoja.append([_texto_seguro(conteo.etiqueta), conteo.cantidad])

    buffer = io.BytesIO()
    libro.save(buffer)
    return buffer.getvalue()
