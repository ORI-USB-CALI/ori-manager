from __future__ import annotations

import io
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from html import escape as _escapar

from openpyxl import Workbook
from openpyxl.styles import Font
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload, selectinload

from backend.models.actividad_convenio import ActividadConvenio
from backend.models.convenio import Convenio
from backend.models.enums import EstadoConvenio
from backend.schemas.exportacion import referencia_provisional

# HU-34, CA-01: "activo" es el convenio cuya ejecución sigue en curso hoy,
# alineado con el ciclo de vida de PR #111. VIGENTE y POR_VENCER son los
# únicos estados que representan eso. VENCIDO es un estado heredado (ya no
# está en ejecución) y RENOVADO no implica por sí mismo que ESTE convenio
# siga activo, así que ninguno de los dos se incluye automáticamente.
ESTADOS_CONVENIO_ACTIVO = (
    EstadoConvenio.VIGENTE,
    EstadoConvenio.POR_VENCER,
)


@dataclass(frozen=True, slots=True)
class ActividadResumen:
    id: int
    titulo: str
    estado: str
    fecha_planificada: date | None
    fecha_ejecucion: date | None


@dataclass(frozen=True, slots=True)
class ConvenioReporteActivo:
    id: int
    codigo: str | None
    objeto: str | None
    estado: str
    aliado: str | None
    tipo_convenio: str | None
    unidad_organizacional: str | None
    responsable: str | None
    fecha_inicio: date | None
    fecha_vencimiento: date | None
    actividades: list[ActividadResumen] = field(default_factory=list)


class ServicioReportes:
    """HU-34. Reporte consolidado de convenios activos, descargable en PDF
    o Excel. Es de solo lectura: no crea, modifica ni resuelve nada, solo
    consulta el estado actual de convenios y actividades (CA-04).
    """

    def __init__(self, db: Session):
        self.db = db

    def listar_convenios_activos(self) -> list[ConvenioReporteActivo]:
        """CA-01/CA-02/CA-03: convenios activos con su información
        principal y sus actividades registradas, incluidos los que no
        tienen ninguna (hoy, todos: el registro de actividades es HU-35).
        """
        convenios = (
            self.db.scalars(
                select(Convenio)
                .where(
                    Convenio.estado.in_([e.value for e in ESTADOS_CONVENIO_ACTIVO])
                )
                .options(
                    joinedload(Convenio.aliado),
                    joinedload(Convenio.solicitud),
                    joinedload(Convenio.tipo_convenio),
                    joinedload(Convenio.unidad_organizacional),
                    joinedload(Convenio.creado_por),
                    selectinload(Convenio.actividades),
                )
                .order_by(Convenio.codigo, Convenio.id)
            )
            .unique()
            .all()
        )
        return [_a_reporte(convenio) for convenio in convenios]


def identificacion(convenio_id: int, codigo: str | None) -> str:
    """CA-02 de HU-34: identificación consistente en pantalla, PDF y Excel.

    Nunca se deja un "—" como único identificador: si no hay código asignado
    todavía, se usa la referencia provisional derivada del id del convenio.

    HT-06: la redacción la fija `referencia_provisional`, la misma que usan el
    documento del convenio y la interfaz. Antes era un texto propio de este
    módulo, y al unificar la interfaz la pantalla y el reporte descargado
    dejaban de coincidir, que es justo lo que este CA-02 prohíbe.
    """
    return codigo if codigo else referencia_provisional(convenio_id)


def _contraparte(convenio: Convenio) -> str | None:
    """Muestra el aliado formal cuando ya existe; si el convenio todavía no
    tiene aliado formal asociado, usa la contraparte propuesta registrada en
    la solicitud de origen en vez de dejar el dato vacío."""
    if convenio.aliado:
        return convenio.aliado.nombre
    return convenio.solicitud.nombre_aliado_propuesto if convenio.solicitud else None


def _a_reporte(convenio: Convenio) -> ConvenioReporteActivo:
    return ConvenioReporteActivo(
        id=convenio.id,
        codigo=convenio.codigo,
        objeto=convenio.objeto,
        estado=convenio.estado,
        aliado=_contraparte(convenio),
        tipo_convenio=convenio.tipo_convenio.nombre if convenio.tipo_convenio else None,
        unidad_organizacional=(
            convenio.unidad_organizacional.nombre
            if convenio.unidad_organizacional
            else None
        ),
        responsable=convenio.creado_por.nombre_completo if convenio.creado_por else None,
        fecha_inicio=convenio.fecha_inicio,
        fecha_vencimiento=convenio.fecha_vencimiento,
        actividades=[_actividad_a_resumen(a) for a in convenio.actividades],
    )


def _actividad_a_resumen(actividad: ActividadConvenio) -> ActividadResumen:
    return ActividadResumen(
        id=actividad.id,
        titulo=actividad.titulo,
        estado=actividad.estado,
        fecha_planificada=actividad.fecha_planificada,
        fecha_ejecucion=actividad.fecha_ejecucion,
    )


_ENCABEZADOS = (
    "Convenio",
    "Objeto",
    "Aliado",
    "Tipo de convenio",
    "Unidad",
    "Registrado por",
    "Fecha inicio",
    "Fecha vencimiento",
    "Actividades",
)

# OWASP CSV/Excel injection: si un texto libre empieza por uno de estos
# caracteres, algunos lectores de hoja de cálculo (y openpyxl mismo, al
# construir la celda) lo interpretan como fórmula. Se antepone un
# apóstrofo para forzar texto literal sin alterar el dato original en BD.
_PREFIJOS_FORMULA = ("=", "+", "-", "@")


def _texto_seguro(valor: str | None) -> str | None:
    if valor and valor.startswith(_PREFIJOS_FORMULA):
        return f"'{valor}"
    return valor

# Suman el ancho útil de una página carta con márgenes de 1.5cm (527pt).
_ANCHOS_COLUMNAS_CM = (1.9, 3.4, 2.4, 1.9, 2.1, 1.9, 1.5, 1.6, 1.5)


def _texto_actividades(convenio: ConvenioReporteActivo) -> str:
    if not convenio.actividades:
        return "Sin actividades registradas"
    return f"{len(convenio.actividades)} registrada(s)"


def _fila(convenio: ConvenioReporteActivo, estilo_celda) -> list:
    valores = [
        identificacion(convenio.id, convenio.codigo),
        convenio.objeto or "—",
        convenio.aliado or "—",
        convenio.tipo_convenio or "—",
        convenio.unidad_organizacional or "—",
        convenio.responsable or "—",
        convenio.fecha_inicio.isoformat() if convenio.fecha_inicio else "—",
        convenio.fecha_vencimiento.isoformat() if convenio.fecha_vencimiento else "—",
        _texto_actividades(convenio),
    ]
    # Cada celda se envuelve en un Paragraph para que reportlab ajuste el
    # texto largo dentro del ancho de la columna en vez de desbordarlo. Se
    # escapa el texto porque Paragraph interpreta un mini-XML propio.
    return [Paragraph(_escapar(str(valor)), estilo_celda) for valor in valores]


def _tabla_convenios(convenios: list[ConvenioReporteActivo], estilo_celda) -> Table:
    datos = [list(_ENCABEZADOS)] + [_fila(c, estilo_celda) for c in convenios]
    tabla = Table(datos, repeatRows=1, colWidths=[a * cm for a in _ANCHOS_COLUMNAS_CM])
    tabla.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F36C21")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTSIZE", (0, 0), (-1, -1), 7),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
            ]
        )
    )
    return tabla


def _tabla_actividades(convenio: ConvenioReporteActivo, estilo_celda) -> Table:
    encabezados = ["Actividad", "Estado", "Fecha planificada", "Fecha ejecución"]
    filas = [
        [
            Paragraph(_escapar(actividad.titulo), estilo_celda),
            Paragraph(_escapar(actividad.estado), estilo_celda),
            Paragraph(
                actividad.fecha_planificada.isoformat() if actividad.fecha_planificada else "—",
                estilo_celda,
            ),
            Paragraph(
                actividad.fecha_ejecucion.isoformat() if actividad.fecha_ejecucion else "—",
                estilo_celda,
            ),
        ]
        for actividad in convenio.actividades
    ]
    tabla = Table(
        [encabezados] + filas,
        colWidths=[a * cm for a in (6.0, 4.0, 4.0, 4.0)],
    )
    tabla.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#64748B")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTSIZE", (0, 0), (-1, -1), 7),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    return tabla


def generar_pdf_convenios_activos(convenios: list[ConvenioReporteActivo]) -> bytes:
    """Plantilla básica (según lo acordado): se estandariza más adelante."""
    buffer = io.BytesIO()
    documento = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=1.5 * cm,
        rightMargin=1.5 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
        # Sin comprimir: reportes pequeños, y permite inspeccionar/validar
        # el texto real del PDF (incluido en pruebas) sin herramientas extra.
        pageCompression=0,
    )
    estilos = getSampleStyleSheet()
    estilo_celda = ParagraphStyle(
        "CeldaReporte", parent=estilos["Normal"], fontSize=7, leading=8.5
    )
    elementos = [
        Paragraph("ORI USB Cali — Reporte de convenios activos", estilos["Title"]),
        Paragraph(
            f"Generado el {datetime.now(UTC).date().isoformat()} · {len(convenios)} convenio(s)",
            estilos["Normal"],
        ),
        Spacer(1, 0.5 * cm),
    ]
    if not convenios:
        elementos.append(Paragraph("No hay convenios activos para mostrar.", estilos["Normal"]))
    else:
        elementos.append(_tabla_convenios(convenios, estilo_celda))
        elementos.append(Spacer(1, 0.8 * cm))
        elementos.append(Paragraph("Actividades por convenio", estilos["Heading2"]))
        for convenio in convenios:
            elementos.append(Spacer(1, 0.3 * cm))
            elementos.append(
                Paragraph(
                    _escapar(identificacion(convenio.id, convenio.codigo)),
                    estilos["Heading3"],
                )
            )
            if convenio.actividades:
                elementos.append(_tabla_actividades(convenio, estilo_celda))
            else:
                elementos.append(Paragraph("Sin actividades registradas.", estilos["Normal"]))
    documento.build(elementos)
    return buffer.getvalue()


def generar_excel_convenios_activos(convenios: list[ConvenioReporteActivo]) -> bytes:
    """.xlsx con dos hojas: convenios (resumen) y actividades (detalle),
    pensado para análisis posterior en herramientas externas.
    """
    libro = Workbook()
    hoja_convenios = libro.active
    hoja_convenios.title = "Convenios activos"
    hoja_convenios.append(list(_ENCABEZADOS[:-1]) + ["N.º de actividades"])
    for celda in hoja_convenios[1]:
        celda.font = Font(bold=True)
    for convenio in convenios:
        hoja_convenios.append(
            [
                _texto_seguro(identificacion(convenio.id, convenio.codigo)),
                _texto_seguro(convenio.objeto),
                _texto_seguro(convenio.aliado),
                _texto_seguro(convenio.tipo_convenio),
                _texto_seguro(convenio.unidad_organizacional),
                _texto_seguro(convenio.responsable),
                convenio.fecha_inicio,
                convenio.fecha_vencimiento,
                len(convenio.actividades),
            ]
        )

    hoja_actividades = libro.create_sheet("Actividades")
    hoja_actividades.append(
        ["Convenio", "Actividad", "Estado", "Fecha planificada", "Fecha ejecución"]
    )
    for celda in hoja_actividades[1]:
        celda.font = Font(bold=True)
    for convenio in convenios:
        identificador = _texto_seguro(identificacion(convenio.id, convenio.codigo))
        for actividad in convenio.actividades:
            hoja_actividades.append(
                [
                    identificador,
                    _texto_seguro(actividad.titulo),
                    actividad.estado,
                    actividad.fecha_planificada,
                    actividad.fecha_ejecucion,
                ]
            )

    buffer = io.BytesIO()
    libro.save(buffer)
    return buffer.getvalue()
