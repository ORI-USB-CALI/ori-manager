from __future__ import annotations

import io
from datetime import UTC, datetime
from functools import partial
from html import escape
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    HRFlowable,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload, selectinload

from backend.models.convenio import Convenio
from backend.models.enums import OrigenConvenio, RolFirmanteConvenio
from backend.models.proceso_firmas_convenio import ProcesoFirmasConvenio
from backend.models.solicitud_convenio import SolicitudConvenio
from backend.models.version_convenio import VersionConvenio
from backend.schemas.exportacion import (
    INFORMACION_NO_DISPONIBLE,
    MARCA_BORRADOR,
    ConvenioPdfDTO,
    FirmantePdfDTO,
    ModoEmision,
    SeccionContenidoDTO,
)
from backend.services.convenios import ConvenioNoEncontrado
from backend.services.validador_exportacion_convenio import (
    modo_emision,
    proceso_firmas_de_version,
    version_exportable,
)

# Los antecedentes exclusivos de solicitudes no están pendientes de completar
# cuando el convenio fue creado directamente por ORI.
NO_APLICA_CREACION_MANUAL = "No aplica (creación directa ORI)"

# Nombres amigables para los roles institucionales
ETIQUETAS_ROL: dict[str, str] = {
    RolFirmanteConvenio.ADMINISTRADOR_ORI.value: "Administrador ORI",
    RolFirmanteConvenio.REVISOR_ORI.value: "Revisor ORI",
    RolFirmanteConvenio.VICERRECTORIA_FINANCIERA.value: "Vicerrectoría Financiera",
    RolFirmanteConvenio.VICERRECTORIA_ACADEMICA.value: "Vicerrectoría Académica",
    RolFirmanteConvenio.SECRETARIA.value: "Secretaría General",
    RolFirmanteConvenio.RECTOR.value: "Rectoría",
    RolFirmanteConvenio.PARTE_SOLICITANTE.value: "Representante Parte Solicitante",
}


def _o_no_disponible(valor: str | None) -> str:
    """El dato tal cual o la representación explícita de que no está."""
    if valor is None or not str(valor).strip():
        return INFORMACION_NO_DISPONIBLE
    return str(valor)


def _e(valor: object) -> str:
    """Escapa texto de usuario: Paragraph interpreta un mini-XML propio
    (mismo criterio que el reporte de HU-34)."""
    return escape(str(valor))


class NumberedCanvas(canvas.Canvas):
    """Canvas de dos pasadas para calcular dinámicamente 'Página X de Y' y decorados."""

    def __init__(self, *args: Any, borrador: bool = False, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._borrador = borrador
        self._saved_page_states: list[dict[str, Any]] = []

    def showPage(self) -> None:
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self) -> None:
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self._dibujar_decoraciones(num_pages)
            super().showPage()
        super().save()

    def _dibujar_decoraciones(self, total_pages: int) -> None:
        self.saveState()
        ancho, alto = letter

        # Encabezado secundario en páginas posteriores (>= 2)
        if self._pageNumber > 1:
            self.setFont("Helvetica", 8)
            self.setFillColor(colors.HexColor("#64748B"))
            self.drawString(
                20 * mm, alto - 15 * mm, "UNIVERSIDAD DE SAN BUENAVENTURA CALI · ORI"
            )
            self.drawRightString(
                ancho - 20 * mm,
                alto - 15 * mm,
                "Borrador de convenio" if self._borrador else "Documento Oficial de Convenio",
            )
            self.setStrokeColor(colors.HexColor("#CBD5E1"))
            self.setLineWidth(0.5)
            self.line(20 * mm, alto - 17 * mm, ancho - 20 * mm, alto - 17 * mm)

        # Un borrador lleva su marca en todas las páginas, no solo en la primera.
        if self._borrador:
            self.setFont("Helvetica-Bold", 9)
            self.setFillColor(colors.HexColor("#B91C1C"))
            self.drawCentredString(ancho / 2, alto - 10 * mm, MARCA_BORRADOR)
            self.drawCentredString(ancho / 2, 8 * mm, MARCA_BORRADOR)

        # Pie de página en todas las páginas
        self.setStrokeColor(colors.HexColor("#CBD5E1"))
        self.setLineWidth(0.5)
        self.line(20 * mm, 18 * mm, ancho - 20 * mm, 18 * mm)

        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#64748B"))
        self.drawString(
            20 * mm, 13 * mm, "Universidad de San Buenaventura Cali · ORI Manager"
        )
        self.drawRightString(
            ancho - 20 * mm, 13 * mm, f"Página {self._pageNumber} de {total_pages}"
        )

        self.restoreState()


class ServicioPdfConvenio:
    """Motor de renderizado de convenios a formato PDF (BE-02)."""

    def mapear_convenio_a_dto(self, convenio_id: int, db: Session) -> ConvenioPdfDTO:
        """Consulta el convenio estrictamente por su ID primario y genera el DTO inmutable (CA-02)."""
        consulta = (
            select(Convenio)
            .options(
                joinedload(Convenio.solicitud).joinedload(
                    SolicitudConvenio.solicitante
                ),
                joinedload(Convenio.aliado),
                joinedload(Convenio.tipo_convenio),
                joinedload(Convenio.etapa_actual),
                joinedload(Convenio.unidad_organizacional),
                joinedload(Convenio.creado_por),
                selectinload(Convenio.versiones).joinedload(VersionConvenio.autor),
                selectinload(Convenio.borrador),
                selectinload(Convenio.procesos_firmas).selectinload(
                    ProcesoFirmasConvenio.firmas
                ),
            )
            .where(Convenio.id == convenio_id)
        )
        convenio = db.scalar(consulta)
        if convenio is None:
            raise ConvenioNoEncontrado(
                f"No se encontró el convenio con identificador {convenio_id}"
            )

        solicitud = convenio.solicitud
        aliado = convenio.aliado
        solicitante = solicitud.solicitante if solicitud else None
        sin_antecedente = (
            NO_APLICA_CREACION_MANUAL
            if convenio.origen == OrigenConvenio.MANUAL_ORI.value
            else INFORMACION_NO_DISPONIBLE
        )

        # Solo la versión que indica el convenio (o el avance guardado, si es un
        # borrador) y los firmantes del proceso de esa versión: lo mismo que
        # validó ConvenioExportValidator.
        version = version_exportable(convenio)
        secciones: list[SeccionContenidoDTO] = []
        if version is not None and version.contenido:
            secciones = self._extraer_secciones_contenido(version.contenido)

        # Un borrador no está formalizado: nunca muestra firmas, ni siquiera
        # las de un proceso configurado, para no presentarlas como completadas.
        modo = modo_emision(convenio)
        firmantes_dto: list[FirmantePdfDTO] = []
        proceso = proceso_firmas_de_version(convenio, version)
        if proceso is not None and modo is ModoEmision.OFICIAL:
            for f in sorted(proceso.firmas, key=lambda item: item.orden):
                firmantes_dto.append(
                    FirmantePdfDTO(
                        orden=f.orden,
                        rol=ETIQUETAS_ROL.get(f.rol_firmante, f.rol_firmante),
                        parte=f.parte,
                        nombre=_o_no_disponible(f.nombre_firmante),
                        cargo=_o_no_disponible(f.cargo_firmante),
                        modalidad=_o_no_disponible(f.modalidad),
                        estado=f.estado,
                    )
                )

        # Con aliado registrado se usan sus datos; si no, los propuestos en la
        # solicitud. Nunca se mezclan ni se completan con valores supuestos.
        if aliado is not None:
            aliado_datos = {
                "aliado_nombre": aliado.nombre,
                "aliado_tipo": aliado.tipo,
                "aliado_identificacion": aliado.identificacion,
                "aliado_pais": aliado.pais.nombre if aliado.pais else None,
                "aliado_ciudad": aliado.ciudad,
            }
        else:
            aliado_datos = {
                "aliado_nombre": solicitud.nombre_aliado_propuesto if solicitud else None,
                "aliado_tipo": solicitud.tipo_aliado_propuesto if solicitud else None,
                "aliado_identificacion": solicitud.identificacion_aliado_propuesto if solicitud else None,
                "aliado_pais": solicitud.pais_aliado_propuesto if solicitud else None,
                "aliado_ciudad": solicitud.ciudad_aliado_propuesto if solicitud else None,
            }

        return ConvenioPdfDTO(
            convenio_id=convenio.id,
            modo_emision=modo,
            codigo=convenio.codigo,
            solicitud_consecutivo=solicitud.consecutivo if solicitud else sin_antecedente,
            tipo_convenio=_o_no_disponible(
                convenio.tipo_convenio.nombre if convenio.tipo_convenio else None
            ),
            estado=convenio.estado,
            etapa=_o_no_disponible(
                convenio.etapa_actual.nombre if convenio.etapa_actual else None
            ),
            alcance=_o_no_disponible(convenio.alcance),
            objeto=_o_no_disponible(convenio.objeto),
            justificacion=_o_no_disponible(solicitud.justificacion) if solicitud else sin_antecedente,
            implicacion_financiera=_o_no_disponible(convenio.implicacion_financiera),
            fecha_inicio=convenio.fecha_inicio,
            fecha_vencimiento=convenio.fecha_vencimiento,
            duracion_meses=convenio.duracion_meses,
            porcentaje_avance=convenio.porcentaje_avance,
            version_actual=convenio.version_actual,
            fecha_emision=datetime.now(UTC),
            solicitante_nombre=_o_no_disponible(
                solicitante.nombre_completo if solicitante else sin_antecedente
            ),
            solicitante_correo=_o_no_disponible(
                solicitante.correo if solicitante else sin_antecedente
            ),
            solicitante_unidad=_o_no_disponible(
                convenio.unidad_organizacional.nombre
                if convenio.unidad_organizacional
                else None
            ),
            solicitante_tipo=solicitud.tipo_solicitante if solicitud else sin_antecedente,
            **{campo: _o_no_disponible(valor) for campo, valor in aliado_datos.items()},
            aliado_contacto_nombre=_o_no_disponible(
                solicitud.contacto_contraparte_nombre if solicitud else None
            ),
            aliado_contacto_correo=_o_no_disponible(
                solicitud.contacto_contraparte_correo
                if solicitud else (aliado.correo if aliado else None)
            ),
            secciones_contenido=secciones,
            firmantes=firmantes_dto,
        )

    def generar_pdf(self, convenio_id: int, db: Session) -> bytes:
        """Consulta el convenio con aislamiento estricto y renderiza el documento PDF (CA-01, CA-02)."""
        dto = self.mapear_convenio_a_dto(convenio_id, db)
        return self.renderizar_dto_a_pdf(dto)

    def renderizar_dto_a_pdf(self, dto: ConvenioPdfDTO) -> bytes:
        """Renderiza un DTO de convenio a binario PDF con maquetación oficial e institucional."""
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            leftMargin=20 * mm,
            rightMargin=20 * mm,
            topMargin=22 * mm,
            bottomMargin=24 * mm,
            title=(
                f"Borrador_Convenio_{dto.codigo or dto.convenio_id}"
                if dto.modo_emision is ModoEmision.BORRADOR
                else f"Convenio_{dto.codigo or dto.convenio_id}"
            ),
            author="Universidad de San Buenaventura Cali - ORI",
        )

        estilos = self._configurar_estilos()
        elementos: list[Any] = []

        # 1. Encabezado Institucional
        self._construir_encabezado_institucional(dto, estilos, elementos)

        # 2. Resumen Identificación del Convenio
        self._construir_identificacion_convenio(dto, estilos, elementos)

        # 3. Partes Involucradas
        self._construir_partes_involucradas(dto, estilos, elementos)

        # 4. Objeto y Justificación
        self._construir_objeto_y_justificacion(dto, estilos, elementos)

        # 5. Vigencia y Condiciones Financieras
        self._construir_vigencia_y_finanzas(dto, estilos, elementos)

        # 6. Cláusulas y Contenido Contractual
        self._construir_clausulas_contractuales(dto, estilos, elementos)

        # 7. Relación de Firmantes Requeridos
        if dto.firmantes:
            self._construir_firmantes(dto, estilos, elementos)

        doc.build(
            elementos,
            canvasmaker=partial(
                NumberedCanvas, borrador=dto.modo_emision is ModoEmision.BORRADOR
            ),
        )
        return buffer.getvalue()

    def _configurar_estilos(self) -> dict[str, ParagraphStyle]:
        base = getSampleStyleSheet()

        return {
            "institucion": ParagraphStyle(
                "Institucion",
                parent=base["Normal"],
                fontName="Helvetica-Bold",
                fontSize=13,
                leading=16,
                textColor=colors.HexColor("#7F1D1D"),  # Burdeos institucional USB
                alignment=1,  # Centrado
            ),
            "unidad": ParagraphStyle(
                "Unidad",
                parent=base["Normal"],
                fontName="Helvetica-Bold",
                fontSize=10,
                leading=13,
                textColor=colors.HexColor("#1E293B"),
                alignment=1,
            ),
            "titulo_doc": ParagraphStyle(
                "TituloDoc",
                parent=base["Normal"],
                fontName="Helvetica-Bold",
                fontSize=12,
                leading=15,
                textColor=colors.HexColor("#0F172A"),
                alignment=1,
            ),
            "marca_borrador": ParagraphStyle(
                "MarcaBorrador",
                parent=base["Normal"],
                fontName="Helvetica-Bold",
                fontSize=11,
                leading=14,
                textColor=colors.HexColor("#B91C1C"),
                alignment=1,
            ),
            "fecha_emision": ParagraphStyle(
                "FechaEmision",
                parent=base["Normal"],
                fontName="Helvetica",
                fontSize=8.5,
                leading=11,
                textColor=colors.HexColor("#64748B"),
                alignment=1,
            ),
            "seccion_titulo": ParagraphStyle(
                "SeccionTitulo",
                parent=base["Normal"],
                fontName="Helvetica-Bold",
                fontSize=10.5,
                leading=14,
                textColor=colors.HexColor("#7F1D1D"),
                spaceBefore=10,
                spaceAfter=5,
            ),
            "texto_normal": ParagraphStyle(
                "TextoNormal",
                parent=base["Normal"],
                fontName="Helvetica",
                fontSize=9,
                leading=13,
                textColor=colors.HexColor("#334155"),
                alignment=4,  # Justificado
            ),
            "texto_pequeno": ParagraphStyle(
                "TextoPequeno",
                parent=base["Normal"],
                fontName="Helvetica",
                fontSize=8,
                leading=11,
                textColor=colors.HexColor("#475569"),
            ),
            "tabla_header": ParagraphStyle(
                "TablaHeader",
                parent=base["Normal"],
                fontName="Helvetica-Bold",
                fontSize=8.5,
                leading=11,
                textColor=colors.HexColor("#0F172A"),
            ),
            "tabla_celda": ParagraphStyle(
                "TablaCelda",
                parent=base["Normal"],
                fontName="Helvetica",
                fontSize=8.5,
                leading=11,
                textColor=colors.HexColor("#334155"),
            ),
            "clausula_titulo": ParagraphStyle(
                "ClausulaTitulo",
                parent=base["Normal"],
                fontName="Helvetica-Bold",
                fontSize=9.5,
                leading=13,
                textColor=colors.HexColor("#0F172A"),
                spaceBefore=6,
                spaceAfter=3,
            ),
        }

    def _construir_encabezado_institucional(
        self,
        dto: ConvenioPdfDTO,
        estilos: dict[str, ParagraphStyle],
        elementos: list[Any],
    ) -> None:
        elementos.append(
            Paragraph("UNIVERSIDAD DE SAN BUENAVENTURA CALI", estilos["institucion"])
        )
        elementos.append(Spacer(1, 2))
        elementos.append(
            Paragraph("OFICINA DE RELACIONES INTERNACIONALES (ORI)", estilos["unidad"])
        )
        elementos.append(Spacer(1, 2))
        borrador = dto.modo_emision is ModoEmision.BORRADOR
        elementos.append(
            Paragraph(
                "BORRADOR DE CONVENIO" if borrador else "DOCUMENTO OFICIAL DE CONVENIO",
                estilos["titulo_doc"],
            )
        )
        if borrador:
            elementos.append(Spacer(1, 2))
            elementos.append(Paragraph(MARCA_BORRADOR, estilos["marca_borrador"]))
        elementos.append(Spacer(1, 3))

        fecha_texto = dto.fecha_emision.strftime("%d de %B de %Y")
        elementos.append(
            Paragraph(
                f"{'Fecha de generación' if borrador else 'Fecha de emisión'}: "
                f"{fecha_texto} · Identificador: #{dto.convenio_id} · "
                f"Versión contractual: {dto.version_actual}",
                estilos["fecha_emision"],
            )
        )
        elementos.append(Spacer(1, 6))
        elementos.append(
            HRFlowable(
                width="100%",
                thickness=1.5,
                color=colors.HexColor("#7F1D1D"),
                spaceBefore=2,
                spaceAfter=10,
            )
        )

    def _construir_identificacion_convenio(
        self,
        dto: ConvenioPdfDTO,
        estilos: dict[str, ParagraphStyle],
        elementos: list[Any],
    ) -> None:
        elementos.append(
            Paragraph(
                "1. IDENTIFICACIÓN GENERAL DEL CONVENIO", estilos["seccion_titulo"]
            )
        )

        filas = [
            [
                Paragraph("<b>Código oficial:</b>", estilos["tabla_header"]),
                Paragraph(_e(_o_no_disponible(dto.codigo)), estilos["tabla_celda"]),
                Paragraph("<b>Solicitud origen:</b>", estilos["tabla_header"]),
                Paragraph(_e(dto.solicitud_consecutivo), estilos["tabla_celda"]),
            ],
            [
                Paragraph("<b>Tipo de convenio:</b>", estilos["tabla_header"]),
                Paragraph(_e(dto.tipo_convenio), estilos["tabla_celda"]),
                Paragraph("<b>Estado actual:</b>", estilos["tabla_header"]),
                Paragraph(_e(dto.estado.replace("_", " ")), estilos["tabla_celda"]),
            ],
            [
                Paragraph("<b>Versión contractual:</b>", estilos["tabla_header"]),
                Paragraph(f"Versión {dto.version_actual}", estilos["tabla_celda"]),
                Paragraph("<b>Alcance institucional:</b>", estilos["tabla_header"]),
                Paragraph(_e(dto.alcance), estilos["tabla_celda"]),
            ],
        ]

        ancho_total = letter[0] - 40 * mm
        ancho_col = ancho_total / 4
        tabla = Table(filas, colWidths=[ancho_col] * 4)
        tabla.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
                    ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                    ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        elementos.append(tabla)
        elementos.append(Spacer(1, 10))

    def _construir_partes_involucradas(
        self,
        dto: ConvenioPdfDTO,
        estilos: dict[str, ParagraphStyle],
        elementos: list[Any],
    ) -> None:
        elementos.append(
            Paragraph("2. PARTES INTERVINIENTES", estilos["seccion_titulo"])
        )

        ancho_mitad = (letter[0] - 40 * mm) / 2
        filas = [
            [
                Paragraph(
                    "<b>PARTE INSTITUCIONAL (USB CALI)</b>", estilos["tabla_header"]
                ),
                Paragraph("<b>PARTE CONTRAPARTE / ALIADO</b>", estilos["tabla_header"]),
            ],
            [
                Paragraph(
                    f"<b>Institución:</b> Universidad de San Buenaventura Cali<br/>"
                    f"<b>Solicitante:</b> {_e(dto.solicitante_nombre)}<br/>"
                    f"<b>Unidad / Facultad:</b> {_e(dto.solicitante_unidad)}<br/>"
                    f"<b>Correo de contacto:</b> {_e(dto.solicitante_correo)}",
                    estilos["tabla_celda"],
                ),
                Paragraph(
                    f"<b>Entidad / Aliado:</b> {_e(dto.aliado_nombre)}<br/>"
                    f"<b>Tipo de entidad:</b> {_e(dto.aliado_tipo)}<br/>"
                    f"<b>Identificación / NIT:</b> {_e(dto.aliado_identificacion)}<br/>"
                    f"<b>Ciudad:</b> {_e(dto.aliado_ciudad)}<br/>"
                    f"<b>País:</b> {_e(dto.aliado_pais)}",
                    estilos["tabla_celda"],
                ),
            ],
        ]

        tabla = Table(filas, colWidths=[ancho_mitad, ancho_mitad])
        tabla.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (1, 0), colors.HexColor("#F1F5F9")),
                    ("BACKGROUND", (0, 1), (1, 1), colors.HexColor("#FFFFFF")),
                    ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                    ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        elementos.append(tabla)
        elementos.append(Spacer(1, 10))

    def _construir_objeto_y_justificacion(
        self,
        dto: ConvenioPdfDTO,
        estilos: dict[str, ParagraphStyle],
        elementos: list[Any],
    ) -> None:
        elementos.append(
            Paragraph("3. OBJETO Y JUSTIFICACIÓN", estilos["seccion_titulo"])
        )
        elementos.append(
            Paragraph("<b>Objeto del Convenio:</b>", estilos["tabla_header"])
        )
        elementos.append(Paragraph(_e(dto.objeto), estilos["texto_normal"]))
        elementos.append(Spacer(1, 6))

        if dto.justificacion != INFORMACION_NO_DISPONIBLE:
            elementos.append(
                Paragraph(
                    "<b>Justificación Institucional:</b>", estilos["tabla_header"]
                )
            )
            elementos.append(Paragraph(_e(dto.justificacion), estilos["texto_normal"]))
            elementos.append(Spacer(1, 10))

    def _construir_vigencia_y_finanzas(
        self,
        dto: ConvenioPdfDTO,
        estilos: dict[str, ParagraphStyle],
        elementos: list[Any],
    ) -> None:
        elementos.append(
            Paragraph(
                "4. VIGENCIA Y CONDICIONES FINANCIERAS", estilos["seccion_titulo"]
            )
        )

        f_inicio = (
            dto.fecha_inicio.strftime("%d/%m/%Y")
            if dto.fecha_inicio
            else INFORMACION_NO_DISPONIBLE
        )
        f_fin = (
            dto.fecha_vencimiento.strftime("%d/%m/%Y")
            if dto.fecha_vencimiento
            else INFORMACION_NO_DISPONIBLE
        )
        duracion = (
            f"{dto.duracion_meses} meses"
            if dto.duracion_meses
            else INFORMACION_NO_DISPONIBLE
        )

        filas = [
            [
                Paragraph("<b>Fecha inicio:</b>", estilos["tabla_header"]),
                Paragraph(f_inicio, estilos["tabla_celda"]),
                Paragraph("<b>Fecha vencimiento:</b>", estilos["tabla_header"]),
                Paragraph(f_fin, estilos["tabla_celda"]),
                Paragraph("<b>Duración estimada:</b>", estilos["tabla_header"]),
                Paragraph(duracion, estilos["tabla_celda"]),
            ],
            [
                Paragraph("<b>Implicación financiera:</b>", estilos["tabla_header"]),
                Paragraph(_e(dto.implicacion_financiera), estilos["tabla_celda"]),
                Paragraph("", estilos["tabla_celda"]),
                Paragraph("", estilos["tabla_celda"]),
                Paragraph("", estilos["tabla_celda"]),
                Paragraph("", estilos["tabla_celda"]),
            ],
        ]

        ancho_total = letter[0] - 40 * mm
        ancho_col = ancho_total / 6
        tabla = Table(filas, colWidths=[ancho_col] * 6)
        tabla.setStyle(
            TableStyle(
                [
                    ("SPAN", (1, 1), (5, 1)),
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
                    ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                    ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ("LEFTPADDING", (0, 0), (-1, -1), 5),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ]
            )
        )
        elementos.append(tabla)
        elementos.append(Spacer(1, 10))

    def _construir_clausulas_contractuales(
        self,
        dto: ConvenioPdfDTO,
        estilos: dict[str, ParagraphStyle],
        elementos: list[Any],
    ) -> None:
        elementos.append(
            Paragraph(
                "5. CONTENIDO CONTRACTUAL Y OBLIGACIONES", estilos["seccion_titulo"]
            )
        )

        if not dto.secciones_contenido:
            # Sin cláusulas reales no se redacta contenido supletorio.
            elementos.append(
                Paragraph("Contenido contractual no disponible.", estilos["texto_normal"])
            )
        for sec in dto.secciones_contenido:
            if sec.tipo == "heading":
                elementos.append(
                    Paragraph(sec.texto_formateado, estilos["clausula_titulo"])
                )
            else:
                elementos.append(Paragraph(sec.texto_formateado, estilos["texto_normal"]))
                elementos.append(Spacer(1, 4))

        elementos.append(Spacer(1, 10))

    def _construir_firmantes(
        self,
        dto: ConvenioPdfDTO,
        estilos: dict[str, ParagraphStyle],
        elementos: list[Any],
    ) -> None:
        filas = [
            [
                Paragraph("<b>#</b>", estilos["tabla_header"]),
                Paragraph("<b>Rol Institucional</b>", estilos["tabla_header"]),
                Paragraph("<b>Firmante Asignado</b>", estilos["tabla_header"]),
                Paragraph("<b>Cargo</b>", estilos["tabla_header"]),
                Paragraph("<b>Modalidad</b>", estilos["tabla_header"]),
                Paragraph("<b>Estado</b>", estilos["tabla_header"]),
            ]
        ]

        for f in dto.firmantes:
            filas.append(
                [
                    Paragraph(str(f.orden), estilos["tabla_celda"]),
                    Paragraph(_e(f.rol), estilos["tabla_celda"]),
                    Paragraph(_e(f.nombre), estilos["tabla_celda"]),
                    Paragraph(_e(f.cargo), estilos["tabla_celda"]),
                    Paragraph(_e(f.modalidad.capitalize()), estilos["tabla_celda"]),
                    Paragraph(_e(f.estado.capitalize()), estilos["tabla_celda"]),
                ]
            )

        ancho_total = letter[0] - 40 * mm
        tabla = Table(
            filas,
            colWidths=[
                10 * mm,
                ancho_total * 0.28,
                ancho_total * 0.24,
                ancho_total * 0.22,
                ancho_total * 0.12,
                ancho_total * 0.10,
            ],
        )
        tabla.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F1F5F9")),
                    ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                    ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ("LEFTPADDING", (0, 0), (-1, -1), 4),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )

        bloque_firmas = KeepTogether(
            [
                Paragraph(
                    "6. RELACIÓN OFICIAL DE FIRMANTES REQUERIDOS (7 FIRMAS)",
                    estilos["seccion_titulo"],
                ),
                Paragraph(
                    "De conformidad con las normas institucionales, el convenio requiere la formalización de las firmas estipuladas:",
                    estilos["texto_pequeno"],
                ),
                Spacer(1, 4),
                tabla,
            ]
        )
        elementos.append(bloque_firmas)

    def _extraer_secciones_contenido(
        self, contenido: dict[str, Any]
    ) -> list[SeccionContenidoDTO]:
        """Aplana el documento ProseMirror (subconjunto de HU-12) en secciones.

        Cada texto se escapa antes de aplicar el marcado válido del documento
        (negrita, cursiva, saltos de línea y listas): lo que escribe el usuario
        nunca se interpreta como marcado de ReportLab.
        """
        secciones: list[SeccionContenidoDTO] = []

        def en_linea(nodo: dict[str, Any]) -> tuple[str, str]:
            """Texto plano y texto formateado de un párrafo o un título."""
            planos: list[str] = []
            formateados: list[str] = []
            for hijo in nodo.get("content", []):
                if not isinstance(hijo, dict):
                    continue
                if hijo.get("type") == "hardBreak":
                    planos.append("\n")
                    formateados.append("<br/>")
                elif hijo.get("type") == "text":
                    texto = str(hijo.get("text", ""))
                    marcas = {
                        marca.get("type")
                        for marca in hijo.get("marks", [])
                        if isinstance(marca, dict)
                    }
                    seguro = escape(texto)
                    if "bold" in marcas:
                        seguro = f"<b>{seguro}</b>"
                    if "italic" in marcas:
                        seguro = f"<i>{seguro}</i>"
                    planos.append(texto)
                    formateados.append(seguro)
            return "".join(planos).strip(), "".join(formateados).strip()

        def recorrer(bloques: Any, profundidad: int = 0, vineta: str | None = None) -> None:
            for bloque in bloques if isinstance(bloques, list) else []:
                if not isinstance(bloque, dict):
                    continue
                tipo = bloque.get("type")
                if tipo in ("paragraph", "heading"):
                    plano, formateado = en_linea(bloque)
                    if not plano:
                        continue
                    if profundidad:
                        # Solo el primer bloque del ítem lleva la viñeta o el número.
                        marca = vineta or "  "
                        vineta = None
                        plano = f"{'  ' * (profundidad - 1)}{marca}{plano}"
                        formateado = (
                            f"{'&nbsp;' * 4 * (profundidad - 1)}{escape(marca)}{formateado}"
                        )
                    es_titulo = tipo == "heading" and not profundidad
                    secciones.append(
                        SeccionContenidoDTO(
                            tipo="heading" if es_titulo else "paragraph",
                            nivel=int(bloque.get("attrs", {}).get("level", 2))
                            if es_titulo
                            else 1,
                            texto=plano,
                            texto_formateado=formateado,
                        )
                    )
                elif tipo in ("bulletList", "orderedList"):
                    numerada = tipo == "orderedList"
                    inicio = int(bloque.get("attrs", {}).get("start", 1)) if numerada else 1
                    for numero, item in enumerate(bloque.get("content", []), start=inicio):
                        if isinstance(item, dict):
                            recorrer(
                                item.get("content", []),
                                profundidad + 1,
                                f"{numero}. " if numerada else "• ",
                            )

        recorrer(contenido.get("content", []))
        return secciones
