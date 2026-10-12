from __future__ import annotations

import io
from datetime import UTC, datetime
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
from backend.models.enums import RolFirmanteConvenio
from backend.models.proceso_firmas_convenio import ProcesoFirmasConvenio
from backend.models.solicitud_convenio import SolicitudConvenio
from backend.models.version_convenio import VersionConvenio
from backend.schemas.exportacion import (
    ConvenioPdfDTO,
    FirmantePdfDTO,
    SeccionContenidoDTO,
)
from backend.services.convenios import ConvenioNoEncontrado

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


class NumberedCanvas(canvas.Canvas):
    """Canvas de dos pasadas para calcular dinámicamente 'Página X de Y' y decorados."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
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
                ancho - 20 * mm, alto - 15 * mm, "Documento Oficial de Convenio"
            )
            self.setStrokeColor(colors.HexColor("#CBD5E1"))
            self.setLineWidth(0.5)
            self.line(20 * mm, alto - 17 * mm, ancho - 20 * mm, alto - 17 * mm)

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
        unidad = (
            convenio.unidad_organizacional.nombre
            if convenio.unidad_organizacional
            else "No informada"
        )

        # Obtener la versión actual o la más reciente
        version_actual: VersionConvenio | None = None
        for v in convenio.versiones:
            if v.numero == convenio.version_actual:
                version_actual = v
                break
        if version_actual is None and convenio.versiones:
            version_actual = max(convenio.versiones, key=lambda item: item.numero)

        # Extraer secciones de contenido estructurado
        secciones: list[SeccionContenidoDTO] = []
        if version_actual and version_actual.contenido:
            secciones = self._extraer_secciones_contenido(version_actual.contenido)

        # Extraer firmantes (del proceso de firmas activo o más reciente)
        firmantes_dto: list[FirmantePdfDTO] = []
        proceso_activo = next(
            (
                p
                for p in convenio.procesos_firmas
                if p.estado in ("CONFIGURACION", "EN_CURSO", "COMPLETADO")
            ),
            None,
        )
        if proceso_activo and proceso_activo.firmas:
            for f in sorted(proceso_activo.firmas, key=lambda item: item.orden):
                firmantes_dto.append(
                    FirmantePdfDTO(
                        orden=f.orden,
                        rol=ETIQUETAS_ROL.get(f.rol_firmante, f.rol_firmante),
                        parte=f.parte,
                        nombre=f.nombre_firmante or "Por definir",
                        cargo=f.cargo_firmante or "Por definir",
                        modalidad=f.modalidad or "Por definir",
                        estado=f.estado,
                    )
                )

        return ConvenioPdfDTO(
            convenio_id=convenio.id,
            codigo=convenio.codigo,
            solicitud_consecutivo=solicitud.consecutivo,
            tipo_convenio=convenio.tipo_convenio.nombre
            if convenio.tipo_convenio
            else "No informado",
            estado=convenio.estado,
            etapa=convenio.etapa_actual.nombre
            if convenio.etapa_actual
            else "No informada",
            alcance=convenio.alcance or "Institucional",
            objeto=convenio.objeto or solicitud.objeto or "No especificado",
            justificacion=solicitud.justificacion or "No especificada",
            implicacion_financiera=convenio.implicacion_financiera
            or solicitud.implicacion_financiera
            or "Sin costo para la Universidad",
            fecha_inicio=convenio.fecha_inicio,
            fecha_vencimiento=convenio.fecha_vencimiento,
            duracion_meses=convenio.duracion_meses,
            porcentaje_avance=convenio.porcentaje_avance,
            version_actual=convenio.version_actual,
            fecha_emision=datetime.now(UTC),
            solicitante_nombre=solicitante.nombre_completo
            if solicitante
            else "No informado",
            solicitante_correo=solicitante.correo if solicitante else "No informado",
            solicitante_unidad=unidad,
            solicitante_tipo=solicitud.tipo_solicitante,
            aliado_nombre=aliado.nombre
            if aliado
            else solicitud.nombre_aliado_propuesto or "No informado",
            aliado_tipo=aliado.tipo_aliado
            if aliado
            else solicitud.tipo_aliado_propuesto or "No informado",
            aliado_identificacion=aliado.identificacion
            if aliado
            else solicitud.identificacion_aliado_propuesto or "No informada",
            aliado_pais=aliado.pais.nombre
            if (aliado and aliado.pais)
            else solicitud.pais_aliado_propuesto or "Colombia",
            aliado_ciudad=aliado.ciudad
            if aliado
            else solicitud.ciudad_aliado_propuesto or "Cali",
            aliado_contacto_nombre=solicitud.contacto_contraparte_nombre or "—",
            aliado_contacto_correo=solicitud.contacto_contraparte_correo or "—",
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
            title=f"Convenio_{dto.codigo or dto.convenio_id}",
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

        doc.build(elementos, canvasmaker=NumberedCanvas)
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
        elementos.append(
            Paragraph("DOCUMENTO OFICIAL DE CONVENIO", estilos["titulo_doc"])
        )
        elementos.append(Spacer(1, 3))

        fecha_texto = dto.fecha_emision.strftime("%d de %B de %Y")
        elementos.append(
            Paragraph(
                f"Fecha de emisión: {fecha_texto} · Identificador: #{dto.convenio_id}",
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
                Paragraph(dto.codigo or "Sin asignar", estilos["tabla_celda"]),
                Paragraph("<b>Solicitud origen:</b>", estilos["tabla_header"]),
                Paragraph(dto.solicitud_consecutivo, estilos["tabla_celda"]),
            ],
            [
                Paragraph("<b>Tipo de convenio:</b>", estilos["tabla_header"]),
                Paragraph(dto.tipo_convenio, estilos["tabla_celda"]),
                Paragraph("<b>Estado actual:</b>", estilos["tabla_header"]),
                Paragraph(dto.estado.replace("_", " "), estilos["tabla_celda"]),
            ],
            [
                Paragraph("<b>Versión contractual:</b>", estilos["tabla_header"]),
                Paragraph(f"Versión {dto.version_actual}", estilos["tabla_celda"]),
                Paragraph("<b>Alcance institucional:</b>", estilos["tabla_header"]),
                Paragraph(dto.alcance, estilos["tabla_celda"]),
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
                    f"<b>Solicitante:</b> {dto.solicitante_nombre}<br/>"
                    f"<b>Unidad / Facultad:</b> {dto.solicitante_unidad}<br/>"
                    f"<b>Correo de contacto:</b> {dto.solicitante_correo}",
                    estilos["tabla_celda"],
                ),
                Paragraph(
                    f"<b>Entidad / Aliado:</b> {dto.aliado_nombre}<br/>"
                    f"<b>Tipo de entidad:</b> {dto.aliado_tipo}<br/>"
                    f"<b>Identificación / NIT:</b> {dto.aliado_identificacion}<br/>"
                    f"<b>Ubicación:</b> {dto.aliado_ciudad}, {dto.aliado_pais}",
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
        elementos.append(Paragraph(dto.objeto, estilos["texto_normal"]))
        elementos.append(Spacer(1, 6))

        if dto.justificacion and dto.justificacion != "No especificada":
            elementos.append(
                Paragraph(
                    "<b>Justificación Institucional:</b>", estilos["tabla_header"]
                )
            )
            elementos.append(Paragraph(dto.justificacion, estilos["texto_normal"]))
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
            dto.fecha_inicio.strftime("%d/%m/%Y") if dto.fecha_inicio else "Por definir"
        )
        f_fin = (
            dto.fecha_vencimiento.strftime("%d/%m/%Y")
            if dto.fecha_vencimiento
            else "Por definir"
        )
        duracion = (
            f"{dto.duracion_meses} meses" if dto.duracion_meses else "No establecida"
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
                Paragraph(dto.implicacion_financiera, estilos["tabla_celda"]),
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

        if dto.secciones_contenido:
            for sec in dto.secciones_contenido:
                if sec.tipo == "heading":
                    elementos.append(Paragraph(sec.texto, estilos["clausula_titulo"]))
                else:
                    elementos.append(Paragraph(sec.texto, estilos["texto_normal"]))
                    elementos.append(Spacer(1, 4))
        else:
            # Estructura supletoria formal
            elementos.append(
                Paragraph(
                    "<b>CLÁUSULA PRIMERA — COMPROMISOS GENERALES:</b> Las partes se comprometen a cooperar activamente para el desarrollo del objeto convenido, actuando bajo principios de buena fe y reciprocidad académica e interinstitucional.",
                    estilos["texto_normal"],
                )
            )
            elementos.append(Spacer(1, 4))
            elementos.append(
                Paragraph(
                    f"<b>CLÁUSULA SEGUNDA — OBLIGACIONES ESPECÍFICAS:</b> La Universidad de San Buenaventura Cali y {dto.aliado_nombre} coordinarán operativamente las actividades correspondientes a través de los supervisores designados.",
                    estilos["texto_normal"],
                )
            )
            elementos.append(Spacer(1, 4))
            elementos.append(
                Paragraph(
                    "<b>CLÁUSULA TERCERA — VIGENCIA:</b> El presente instrumento tendrá vigencia a partir de su suscripción formal y hasta la fecha establecida en el cronograma.",
                    estilos["texto_normal"],
                )
            )

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
                    Paragraph(f.rol, estilos["tabla_celda"]),
                    Paragraph(f.nombre, estilos["tabla_celda"]),
                    Paragraph(f.cargo, estilos["tabla_celda"]),
                    Paragraph(f.modalidad.capitalize(), estilos["tabla_celda"]),
                    Paragraph(f.estado.capitalize(), estilos["tabla_celda"]),
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
        """Convierte recursivamente el JSON ProseMirror a una lista plana de secciones formateadas."""
        secciones: list[SeccionContenidoDTO] = []

        def extraer_texto_nodo(nodo: dict[str, Any]) -> str:
            tipo = nodo.get("type")
            if tipo == "text":
                texto = nodo.get("text", "")
                marcas = {
                    m.get("type") for m in nodo.get("marks", []) if isinstance(m, dict)
                }
                if "bold" in marcas:
                    texto = f"<b>{texto}</b>"
                if "italic" in marcas:
                    texto = f"<i>{texto}</i>"
                return texto
            if tipo == "hardBreak":
                return "<br/>"
            hijos = nodo.get("content", [])
            return "".join(
                extraer_texto_nodo(hijo) for hijo in hijos if isinstance(hijo, dict)
            )

        for bloque in contenido.get("content", []):
            if not isinstance(bloque, dict):
                continue
            tipo = bloque.get("type")
            if tipo == "heading":
                nivel = bloque.get("attrs", {}).get("level", 2)
                texto = extraer_texto_nodo(bloque).strip()
                if texto:
                    secciones.append(
                        SeccionContenidoDTO(tipo="heading", nivel=nivel, texto=texto)
                    )
            elif tipo == "paragraph":
                texto = extraer_texto_nodo(bloque).strip()
                if texto:
                    secciones.append(
                        SeccionContenidoDTO(tipo="paragraph", nivel=1, texto=texto)
                    )
            elif tipo in ("bulletList", "orderedList"):
                items = bloque.get("content", [])
                for i, item in enumerate(items, start=1):
                    if isinstance(item, dict):
                        texto_item = extraer_texto_nodo(item).strip()
                        if texto_item:
                            prefijo = f"{i}. " if tipo == "orderedList" else "&bull; "
                            secciones.append(
                                SeccionContenidoDTO(
                                    tipo="paragraph",
                                    nivel=1,
                                    texto=f"{prefijo}{texto_item}",
                                )
                            )

        return secciones
