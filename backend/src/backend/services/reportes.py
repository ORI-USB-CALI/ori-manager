from __future__ import annotations

import io
from dataclasses import dataclass, field
from datetime import UTC, date, datetime

from openpyxl import Workbook
from openpyxl.styles import Font
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload, selectinload

from backend.models.actividad_convenio import ActividadConvenio
from backend.models.convenio import Convenio
from backend.models.enums import EstadoConvenio

# HU-34, CA-01: "activo" es cualquier convenio que no esté en trámite,
# finalizado o cancelado (decisión confirmada con el cliente en reuniones
# posteriores a la redacción del CA). POR_VENCER, VENCIDO y RENOVADO se
# consideran convenios cuya ejecución sigue vigente o acaba de concluir y
# por eso siguen siendo relevantes para este reporte.
ESTADOS_CONVENIO_ACTIVO = (
    EstadoConvenio.VIGENTE,
    EstadoConvenio.POR_VENCER,
    EstadoConvenio.VENCIDO,
    EstadoConvenio.RENOVADO,
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


def _a_reporte(convenio: Convenio) -> ConvenioReporteActivo:
    return ConvenioReporteActivo(
        id=convenio.id,
        codigo=convenio.codigo,
        objeto=convenio.objeto,
        estado=convenio.estado,
        aliado=convenio.aliado.nombre if convenio.aliado else None,
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
    "Código",
    "Objeto",
    "Aliado",
    "Tipo de convenio",
    "Unidad",
    "Responsable",
    "Fecha inicio",
    "Fecha vencimiento",
    "Actividades",
)


def _texto_actividades(convenio: ConvenioReporteActivo) -> str:
    if not convenio.actividades:
        return "Sin actividades registradas"
    return f"{len(convenio.actividades)} registrada(s)"


def _fila(convenio: ConvenioReporteActivo) -> list[str]:
    return [
        convenio.codigo or "—",
        convenio.objeto or "—",
        convenio.aliado or "—",
        convenio.tipo_convenio or "—",
        convenio.unidad_organizacional or "—",
        convenio.responsable or "—",
        convenio.fecha_inicio.isoformat() if convenio.fecha_inicio else "—",
        convenio.fecha_vencimiento.isoformat() if convenio.fecha_vencimiento else "—",
        _texto_actividades(convenio),
    ]


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
    )
    estilos = getSampleStyleSheet()
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
        datos = [list(_ENCABEZADOS)] + [_fila(c) for c in convenios]
        tabla = Table(datos, repeatRows=1)
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
        elementos.append(tabla)
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
                convenio.codigo,
                convenio.objeto,
                convenio.aliado,
                convenio.tipo_convenio,
                convenio.unidad_organizacional,
                convenio.responsable,
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
        identificador = convenio.codigo or f"#{convenio.id}"
        for actividad in convenio.actividades:
            hoja_actividades.append(
                [
                    identificador,
                    actividad.titulo,
                    actividad.estado,
                    actividad.fecha_planificada,
                    actividad.fecha_ejecucion,
                ]
            )

    buffer = io.BytesIO()
    libro.save(buffer)
    return buffer.getvalue()
