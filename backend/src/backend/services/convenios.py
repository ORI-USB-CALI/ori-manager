from datetime import UTC, date, datetime

from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, joinedload, selectinload

from backend.models.aliado import Aliado
from backend.models.auditoria import Auditoria
from backend.models.convenio import Convenio
from backend.models.documento import Documento
from backend.models.enums import (
    AccionAuditoria,
    AlcanceConvenio,
    EstadoConvenio,
    EstadoObservacionRevision,
    EstadoRevisionConvenio,
    EstadoSolicitud,
    OrigenObservacionRevision,
    ResultadoRevisionConvenio,
    TipoRevisionConvenio,
)
from backend.models.etapa import Etapa
from backend.models.historial_etapa import HistorialEtapa
from backend.models.observacion_revision import ObservacionRevision
from backend.models.revision_convenio import RevisionConvenio
from backend.models.solicitud_convenio import SolicitudConvenio
from backend.models.tipo_convenio import TipoConvenio
from backend.models.unidad_organizacional import UnidadOrganizacional
from backend.models.usuario import Usuario
from backend.schemas.convenio import (
    CampoFaltante,
    ConvenioCrear,
    ConvenioElaboracionActualizar,
)
from backend.services.documentos import AlmacenDocumentos

CODIGO_ETAPA_ELABORACION = "ELABORACION"
CODIGO_ETAPA_REVISION_JURIDICA = "REVISION_AVAL_JURIDICO"
ENTIDAD_CONVENIO = "convenio"

# Campos del proyecto de convenio que se congelan al entregarlo a Jurídica. No se
# incluyen datos de etapas posteriores (fecha_firma, porcentaje_avance) ni objetos
# ORM: el snapshot es el estado exacto de lo presentado, nada más.
CAMPOS_SNAPSHOT = (
    "codigo",
    "solicitud_id",
    "aliado_id",
    "tipo_convenio_id",
    "objeto",
    "alcance",
    "unidad_organizacional_id",
    "implicacion_financiera",
    "fecha_inicio",
    "fecha_vencimiento",
    "duracion_meses",
    "convenio_origen_id",
    "numero_renovacion",
)


def _snapshot_de(convenio: Convenio) -> dict[str, object]:
    """Congela los datos del convenio tal como se envían a revisión jurídica."""
    snapshot: dict[str, object] = {}
    for campo in CAMPOS_SNAPSHOT:
        valor = getattr(convenio, campo)
        # Las fechas van como ISO para que el JSONB las conserve legibles.
        snapshot[campo] = valor.isoformat() if isinstance(valor, date) else valor
    return snapshot

# Lo mínimo para entregar el proyecto a Jurídica. Los campos de etapas posteriores
# (fecha_firma, porcentaje_avance, firmas) no se exigen aquí, y `codigo` puede
# seguir en NULL al entrar a revisión jurídica.
CAMPOS_REQUERIDOS_ELABORACION = (
    "objeto",
    "tipo_convenio_id",
    "alcance",
    "implicacion_financiera",
    "duracion_meses",
)


def validar_completitud(convenio: Convenio) -> list[CampoFaltante]:
    """Indica qué falta para poder finalizar la elaboración. Sin efectos secundarios."""
    faltantes: list[CampoFaltante] = []

    for campo in CAMPOS_REQUERIDOS_ELABORACION:
        valor = getattr(convenio, campo)
        if valor is None or (isinstance(valor, str) and not valor.strip()):
            faltantes.append(
                CampoFaltante(
                    campo=campo,
                    motivo="Es obligatorio para finalizar la elaboración",
                )
            )

    if (
        convenio.alcance == AlcanceConvenio.PROGRAMA
        and convenio.unidad_organizacional_id is None
    ):
        faltantes.append(
            CampoFaltante(
                campo="unidad_organizacional_id",
                motivo="Es obligatorio cuando el alcance es PROGRAMA",
            )
        )

    if (
        convenio.fecha_inicio is not None
        and convenio.fecha_vencimiento is not None
        and convenio.fecha_vencimiento <= convenio.fecha_inicio
    ):
        faltantes.append(
            CampoFaltante(
                campo="fecha_vencimiento",
                motivo="Debe ser posterior a la fecha de inicio",
            )
        )

    return faltantes


def _a_texto(valor: object) -> str | None:
    """Serializa un valor de campo para guardarlo en auditoria (columnas text)."""
    if valor is None:
        return None
    if isinstance(valor, AlcanceConvenio):
        return valor.value
    if isinstance(valor, (date, datetime)):
        return valor.isoformat()
    return str(valor)


class ErrorConvenio(Exception):
    pass


class ConvenioNoEncontrado(ErrorConvenio):
    pass


class ConvenioDuplicado(ErrorConvenio):
    pass


class ReferenciaConvenioInvalida(ErrorConvenio):
    pass


class SolicitudNoAprobada(ErrorConvenio):
    pass


class ConvenioNoEditable(ErrorConvenio):
    pass


class RevisionNoDisponible(ErrorConvenio):
    pass


class ObservacionNoDisponible(ErrorConvenio):
    pass


class ElaboracionIncompleta(ErrorConvenio):
    def __init__(self, faltantes: list[CampoFaltante]) -> None:
        self.faltantes = faltantes
        super().__init__("Falta información requerida para finalizar la elaboración")


class ConfiguracionConvenioInvalida(RuntimeError):
    pass


class ServicioConvenios:
    def __init__(
        self, db: Session, almacen: AlmacenDocumentos | None = None
    ):
        self.db = db
        self.almacen = almacen

    def _almacen_requerido(self) -> AlmacenDocumentos:
        if self.almacen is None:
            raise RuntimeError("El servicio requiere almacenamiento documental")
        return self.almacen

    def _validar_referencias(self, datos: dict[str, object]) -> None:
        tipo_id = datos.get("tipo_convenio_id")
        if tipo_id is not None and self.db.get(TipoConvenio, tipo_id) is None:
            raise ReferenciaConvenioInvalida("El tipo de convenio no existe")
        unidad_id = datos.get("unidad_organizacional_id")
        if unidad_id is not None and self.db.get(UnidadOrganizacional, unidad_id) is None:
            raise ReferenciaConvenioInvalida("La unidad organizacional no existe")
        origen_id = datos.get("convenio_origen_id")
        if origen_id is not None and self.db.get(Convenio, origen_id) is None:
            raise ReferenciaConvenioInvalida("El convenio de origen no existe")

    def _crear_en_transaccion(
        self,
        datos: ConvenioCrear,
        usuario: Usuario,
        solicitud: SolicitudConvenio,
    ) -> Convenio:
        """Construye el convenio y su historial inicial sin hacer commit."""
        if solicitud.estado != EstadoSolicitud.APROBADA:
            raise SolicitudNoAprobada(
                "Solo una solicitud APROBADA puede originar un convenio"
            )
        aliado_id = solicitud.aliado_id
        if aliado_id is not None:
            aliado = self.db.get(Aliado, aliado_id)
            if aliado is None:
                raise ReferenciaConvenioInvalida(
                    "El aliado asociado a la solicitud no existe"
                )
            if not aliado.activo:
                raise ReferenciaConvenioInvalida(
                    "El aliado asociado a la solicitud está inactivo"
                )
        if self.db.scalar(
            select(Convenio.id).where(Convenio.solicitud_id == datos.solicitud_id)
        ) is not None:
            raise ConvenioDuplicado("La solicitud ya tiene un convenio registrado")
        elaboracion = self.db.scalar(
            select(Etapa).where(Etapa.codigo == CODIGO_ETAPA_ELABORACION)
        )
        if elaboracion is None:
            raise ConfiguracionConvenioInvalida(
                "No existe la etapa obligatoria ELABORACION"
            )
        valores = datos.model_dump()
        self._validar_referencias(valores)
        valores = {
            campo: valor.value if isinstance(valor, AlcanceConvenio) else valor
            for campo, valor in valores.items()
        }
        convenio = Convenio(
            **valores,
            aliado_id=aliado_id,
            etapa_actual_id=elaboracion.id,
            estado=EstadoConvenio.EN_TRAMITE.value,
            creado_por_id=usuario.id,
        )
        self.db.add(convenio)
        self.db.flush()
        self.db.add(
            HistorialEtapa(
                convenio_id=convenio.id,
                etapa_origen_id=None,
                etapa_destino_id=elaboracion.id,
                usuario_id=usuario.id,
                responsable_id=usuario.id,
                observacion=None,
            )
        )
        return convenio

    def crear(self, datos: ConvenioCrear, usuario: Usuario) -> Convenio:
        solicitud = self.db.get(SolicitudConvenio, datos.solicitud_id)
        if solicitud is None:
            raise ReferenciaConvenioInvalida("La solicitud indicada no existe")
        try:
            convenio = self._crear_en_transaccion(datos, usuario, solicitud)
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ConvenioDuplicado(
                "La solicitud o el código ya están asociados a otro convenio"
            ) from exc
        except SQLAlchemyError:
            self.db.rollback()
            raise
        return self.obtener(convenio.id)

    def iniciar_desde_solicitud(
        self, solicitud_id: int, usuario: Usuario
    ) -> Convenio:
        solicitud = self.db.scalar(
            select(SolicitudConvenio)
            .where(SolicitudConvenio.id == solicitud_id)
            .with_for_update()
        )
        if solicitud is None:
            raise ReferenciaConvenioInvalida("La solicitud indicada no existe")
        estados_admitidos = {
            EstadoSolicitud.RADICADA.value,
            EstadoSolicitud.EN_ESTUDIO.value,
            EstadoSolicitud.APROBADA.value,
        }
        if solicitud.estado not in estados_admitidos:
            raise SolicitudNoAprobada(
                "Solo una solicitud RADICADA, EN_ESTUDIO o APROBADA puede iniciar elaboración"
            )
        estado_anterior = solicitud.estado
        if estado_anterior != EstadoSolicitud.APROBADA.value:
            solicitud.estado = EstadoSolicitud.APROBADA.value
            self.db.add(
                Auditoria(
                    usuario_id=usuario.id,
                    entidad="solicitud",
                    registro_id=solicitud.id,
                    accion=AccionAuditoria.UPDATE.value,
                    campo="estado",
                    valor_anterior=estado_anterior,
                    valor_nuevo=EstadoSolicitud.APROBADA.value,
                )
            )
        existente = self.db.scalar(
            select(Convenio).where(Convenio.solicitud_id == solicitud_id)
        )
        if existente is not None:
            self.db.commit()
            return self.obtener(existente.id)
        datos = ConvenioCrear(
            solicitud_id=solicitud.id,
            tipo_convenio_id=solicitud.tipo_convenio_id,
            objeto=solicitud.objeto or "",
            implicacion_financiera=solicitud.implicacion_financiera,
        )
        try:
            convenio = self._crear_en_transaccion(datos, usuario, solicitud)
            self.db.commit()
            return self.obtener(convenio.id)
        except IntegrityError:
            self.db.rollback()
            existente = self.db.scalar(
                select(Convenio).where(Convenio.solicitud_id == solicitud_id)
            )
            if existente is None:
                raise ConvenioDuplicado(
                    "La solicitud o el código ya están asociados a otro convenio"
                )
            return self.obtener(existente.id)
        except (ErrorConvenio, SQLAlchemyError):
            self.db.rollback()
            raise

    def obtener(self, convenio_id: int) -> Convenio:
        convenio = self.db.scalar(
            select(Convenio)
            .options(
                joinedload(Convenio.aliado),
                joinedload(Convenio.creado_por),
                joinedload(Convenio.etapa_actual),
            )
            .where(Convenio.id == convenio_id)
        )
        if convenio is None:
            raise ConvenioNoEncontrado("Convenio no encontrado")
        return convenio

    def listar_revisiones_juridicas_pendientes(self) -> list[RevisionConvenio]:
        return list(
            self.db.scalars(
                select(RevisionConvenio)
                .join(RevisionConvenio.convenio)
                .join(Convenio.etapa_actual)
                .options(
                    joinedload(RevisionConvenio.convenio).joinedload(
                        Convenio.solicitud
                    ),
                    joinedload(RevisionConvenio.convenio).joinedload(
                        Convenio.tipo_convenio
                    ),
                    joinedload(RevisionConvenio.convenio).joinedload(
                        Convenio.creado_por
                    ),
                )
                .where(
                    RevisionConvenio.tipo == TipoRevisionConvenio.JURIDICA.value,
                    RevisionConvenio.estado
                    == EstadoRevisionConvenio.PENDIENTE.value,
                    Etapa.codigo == CODIGO_ETAPA_REVISION_JURIDICA,
                )
                .order_by(RevisionConvenio.creado_en, RevisionConvenio.id)
            )
        )

    def obtener_para_revision(
        self, convenio_id: int
    ) -> tuple[Convenio, RevisionConvenio, list[Documento]]:
        """Convenio con su documentación y la ronda de revisión jurídica
        pendiente, para la pantalla principal de revisión (CA-01 de HU-13)."""
        convenio = self.db.scalar(
            select(Convenio)
            .options(
                joinedload(Convenio.solicitud),
                joinedload(Convenio.aliado),
                joinedload(Convenio.creado_por),
                joinedload(Convenio.etapa_actual),
                joinedload(Convenio.tipo_convenio),
                joinedload(Convenio.unidad_organizacional),
            )
            .where(Convenio.id == convenio_id)
        )
        if convenio is None:
            raise ConvenioNoEncontrado("Convenio no encontrado")
        if (
            convenio.etapa_actual is None
            or convenio.etapa_actual.codigo != CODIGO_ETAPA_REVISION_JURIDICA
        ):
            raise ConvenioNoEditable(
                "El convenio no está en etapa de revisión jurídica"
            )

        revision_pendiente = self.db.scalar(
            select(RevisionConvenio)
            .options(
                selectinload(RevisionConvenio.observaciones),
                joinedload(RevisionConvenio.responsable),
                joinedload(RevisionConvenio.resuelta_por),
            )
            .where(
                RevisionConvenio.convenio_id == convenio.id,
                RevisionConvenio.tipo == TipoRevisionConvenio.JURIDICA.value,
                RevisionConvenio.estado == EstadoRevisionConvenio.PENDIENTE.value,
            )
        )
        if revision_pendiente is None:
            # En la práctica esto solo pasa cuando aprobar()/devolver() ya
            # resolvieron la ronda pero el convenio todavía no avanzó de
            # etapa (aprobar() no la mueve): no es un error de configuración,
            # es que ya no hay nada pendiente que revisar.
            raise RevisionNoDisponible(
                "No hay una ronda de revisión jurídica pendiente para este convenio"
            )
        documentos = list(
            self.db.scalars(
                select(Documento)
                .where(
                    Documento.es_vigente.is_(True),
                    or_(
                        Documento.solicitud_id == convenio.solicitud_id,
                        Documento.convenio_id == convenio.id,
                    ),
                )
                .order_by(Documento.creado_en, Documento.id)
            )
        )
        return convenio, revision_pendiente, documentos

    def obtener_contenido_documento(
        self, convenio_id: int, documento_id: int
    ) -> tuple[Documento, bytes]:
        convenio = self.obtener(convenio_id)
        documento = self.db.scalar(
            select(Documento).where(
                Documento.id == documento_id,
                Documento.es_vigente.is_(True),
                or_(
                    Documento.solicitud_id == convenio.solicitud_id,
                    Documento.convenio_id == convenio.id,
                ),
            )
        )
        if documento is None:
            raise ConvenioNoEncontrado("Documento no encontrado")
        contenido = self._almacen_requerido().leer(documento.ruta_almacenamiento)
        return documento, contenido

    def obtener_para_elaboracion(self, convenio_id: int) -> Convenio:
        """Convenio con su antecedente y catálogos, para la pantalla de Elaboración."""
        convenio = self.db.scalar(
            select(Convenio)
            .options(
                joinedload(Convenio.solicitud),
                joinedload(Convenio.aliado),
                joinedload(Convenio.creado_por),
                joinedload(Convenio.etapa_actual),
                joinedload(Convenio.tipo_convenio),
                joinedload(Convenio.unidad_organizacional),
            )
            .where(Convenio.id == convenio_id)
        )
        if convenio is None:
            raise ConvenioNoEncontrado("Convenio no encontrado")
        return convenio

    def _aplicar_cambios(
        self,
        convenio: Convenio,
        cambios: dict[str, object],
        usuario: Usuario,
    ) -> None:
        """Valida y aplica cambios con auditoría, sin cerrar la transacción."""
        combinados = {
            "tipo_convenio_id": convenio.tipo_convenio_id,
            "alcance": convenio.alcance,
            "unidad_organizacional_id": convenio.unidad_organizacional_id,
            "convenio_origen_id": convenio.convenio_origen_id,
            **cambios,
        }
        self._validar_referencias(combinados)
        for campo, valor in cambios.items():
            nuevo = valor.value if isinstance(valor, AlcanceConvenio) else valor
            anterior = getattr(convenio, campo)
            if anterior == nuevo:
                continue
            setattr(convenio, campo, nuevo)
            self.db.add(
                Auditoria(
                    usuario_id=usuario.id,
                    entidad=ENTIDAD_CONVENIO,
                    registro_id=convenio.id,
                    accion=AccionAuditoria.UPDATE.value,
                    campo=campo,
                    valor_anterior=_a_texto(anterior),
                    valor_nuevo=_a_texto(nuevo),
                )
            )

    def actualizar(
        self,
        convenio_id: int,
        datos: ConvenioElaboracionActualizar,
        usuario: Usuario,
    ) -> Convenio:
        convenio = self.obtener(convenio_id)
        if (
            convenio.etapa_actual is None
            or convenio.etapa_actual.codigo != CODIGO_ETAPA_ELABORACION
        ):
            raise ConvenioNoEditable(
                "Solo se puede editar un convenio en etapa de Elaboración"
            )
        self._aplicar_cambios(
            convenio, datos.model_dump(exclude_unset=True), usuario
        )
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ConvenioDuplicado("El código ya pertenece a otro convenio") from exc
        return self.obtener(convenio.id)

    def finalizar_elaboracion(
        self,
        convenio_id: int,
        usuario: Usuario,
        datos: ConvenioElaboracionActualizar | None = None,
    ) -> Convenio:
        """Congela el proyecto y abre la ronda de revisión jurídica.

        La transición de etapa, el historial y la revisión se escriben en un solo
        commit: o el convenio queda entregado a Jurídica, o no cambia nada.
        """
        convenio = self.db.scalar(
            select(Convenio).where(Convenio.id == convenio_id).with_for_update()
        )
        if convenio is None:
            raise ConvenioNoEncontrado("Convenio no encontrado")
        if (
            convenio.etapa_actual is None
            or convenio.etapa_actual.codigo != CODIGO_ETAPA_ELABORACION
        ):
            raise ConvenioNoEditable(
                "Solo se puede finalizar un convenio en etapa de Elaboración"
            )

        try:
            self._aplicar_cambios(
                convenio,
                datos.model_dump(exclude_unset=True) if datos is not None else {},
                usuario,
            )
        except ErrorConvenio:
            self.db.rollback()
            raise

        faltantes = validar_completitud(convenio)
        if faltantes:
            self.db.rollback()
            raise ElaboracionIncompleta(faltantes)

        pendiente = self.db.scalar(
            select(ObservacionRevision.id)
            .join(
                RevisionConvenio,
                RevisionConvenio.id == ObservacionRevision.revision_convenio_id,
            )
            .where(
                ObservacionRevision.convenio_id == convenio.id,
                ObservacionRevision.origen
                == OrigenObservacionRevision.REVISOR_ORI.value,
                ObservacionRevision.estado
                == EstadoObservacionRevision.PENDIENTE.value,
                RevisionConvenio.tipo == TipoRevisionConvenio.JURIDICA.value,
            )
            .limit(1)
        )
        if pendiente is not None:
            self.db.rollback()
            raise RevisionNoDisponible(
                "Debe atender todas las observaciones jurídicas pendientes "
                "antes de reenviar el convenio"
            )

        juridica = self.db.scalar(
            select(Etapa).where(Etapa.codigo == CODIGO_ETAPA_REVISION_JURIDICA)
        )
        if juridica is None:
            raise ConfiguracionConvenioInvalida(
                "No existe la etapa obligatoria REVISION_AVAL_JURIDICO"
            )

        historial = HistorialEtapa(
            convenio_id=convenio.id,
            etapa_origen_id=convenio.etapa_actual_id,
            etapa_destino_id=juridica.id,
            usuario_id=usuario.id,
            responsable_id=None,
            observacion=None,
        )
        self.db.add(historial)
        try:
            # Se necesita el id del historial para enlazar la revisión con la
            # transición real que la originó.
            self.db.flush()
            self.db.add(
                RevisionConvenio(
                    convenio_id=convenio.id,
                    tipo=TipoRevisionConvenio.JURIDICA.value,
                    historial_etapa_id=historial.id,
                    estado=EstadoRevisionConvenio.PENDIENTE.value,
                    resultado=None,
                    documento_id=None,
                    responsable_id=None,
                    snapshot_datos=_snapshot_de(convenio),
                )
            )
            # Se asigna la relación, no solo el FK: si quedara desincronizada, una
            # sesión reutilizada seguiría viendo la etapa anterior.
            convenio.etapa_actual = juridica
            self.db.commit()
        except SQLAlchemyError:
            self.db.rollback()
            raise
        return self.obtener(convenio.id)

    def _revision_juridica_pendiente(
        self, convenio_id: int, revision_id: int
    ) -> tuple[Convenio, RevisionConvenio]:
        # Bloquear la fila evita que dos acciones resuelvan la misma ronda.
        revision = self.db.scalar(
            select(RevisionConvenio)
            .where(
                RevisionConvenio.id == revision_id,
                RevisionConvenio.convenio_id == convenio_id,
            )
            .with_for_update()
        )
        if revision is None:
            raise ConvenioNoEncontrado("Revisión no encontrada para este convenio")
        convenio = self.obtener(convenio_id)
        if (
            revision.tipo != TipoRevisionConvenio.JURIDICA.value
            or revision.estado != EstadoRevisionConvenio.PENDIENTE.value
            or revision.resultado is not None
            or convenio.etapa_actual is None
            or convenio.etapa_actual.codigo != CODIGO_ETAPA_REVISION_JURIDICA
        ):
            raise RevisionNoDisponible("La revisión jurídica ya no está pendiente")
        return convenio, revision

    def aprobar(
        self, convenio_id: int, revision_id: int, usuario: Usuario
    ) -> RevisionConvenio:
        convenio, revision = self._revision_juridica_pendiente(
            convenio_id, revision_id
        )
        pendiente = self.db.scalar(
            select(ObservacionRevision.id)
            .join(
                RevisionConvenio,
                RevisionConvenio.id == ObservacionRevision.revision_convenio_id,
            )
            .where(
                ObservacionRevision.convenio_id == convenio.id,
                ObservacionRevision.origen
                == OrigenObservacionRevision.REVISOR_ORI.value,
                ObservacionRevision.estado
                == EstadoObservacionRevision.PENDIENTE.value,
                RevisionConvenio.tipo == TipoRevisionConvenio.JURIDICA.value,
            )
            .limit(1)
        )
        if pendiente is not None:
            raise RevisionNoDisponible("Hay observaciones pendientes por atender")
        revision.estado = EstadoRevisionConvenio.RESUELTA.value
        revision.resultado = ResultadoRevisionConvenio.APROBADA.value
        revision.resuelta_por_id = usuario.id
        revision.resuelta_en = datetime.now(UTC)
        try:
            self.db.commit()
        except SQLAlchemyError:
            self.db.rollback()
            raise
        return revision

    def atender_observacion(
        self,
        convenio_id: int,
        observacion_id: int,
        respuesta: str,
        usuario: Usuario,
    ) -> ObservacionRevision:
        texto = respuesta.strip()
        if not texto:
            raise ReferenciaConvenioInvalida("La respuesta debe tener contenido")

        observacion = self.db.scalar(
            select(ObservacionRevision)
            .where(
                ObservacionRevision.id == observacion_id,
                ObservacionRevision.convenio_id == convenio_id,
            )
            .with_for_update()
        )
        if observacion is None:
            raise ConvenioNoEncontrado(
                "Observación no encontrada para este convenio"
            )

        convenio = self.obtener(convenio_id)
        if (
            convenio.etapa_actual is None
            or convenio.etapa_actual.codigo != CODIGO_ETAPA_ELABORACION
        ):
            raise ObservacionNoDisponible(
                "Las observaciones solo pueden atenderse durante la Elaboración"
            )
        if observacion.origen != OrigenObservacionRevision.REVISOR_ORI.value:
            raise ObservacionNoDisponible(
                "La observación no corresponde a la revisión jurídica"
            )
        if observacion.estado != EstadoObservacionRevision.PENDIENTE.value:
            raise ObservacionNoDisponible("La observación ya fue atendida")

        observacion.respuesta = texto
        observacion.atendida_por = usuario
        observacion.fecha_atencion = datetime.now(UTC)
        observacion.estado = EstadoObservacionRevision.ATENDIDA.value
        try:
            self.db.commit()
        except SQLAlchemyError:
            self.db.rollback()
            raise
        return observacion

    def devolver(
        self, convenio_id: int, revision_id: int, observaciones: list[str],
        usuario: Usuario,
    ) -> RevisionConvenio:
        if not observaciones or any(not texto.strip() for texto in observaciones):
            raise ReferenciaConvenioInvalida("Debe incluir al menos una observación")
        convenio, revision = self._revision_juridica_pendiente(
            convenio_id, revision_id
        )
        elaboracion = self.db.scalar(
            select(Etapa).where(Etapa.codigo == CODIGO_ETAPA_ELABORACION)
        )
        if elaboracion is None:
            raise ConfiguracionConvenioInvalida("No existe la etapa ELABORACION")
        historial = HistorialEtapa(
            convenio_id=convenio.id,
            etapa_origen_id=convenio.etapa_actual_id,
            etapa_destino_id=elaboracion.id,
            usuario_id=usuario.id,
            responsable_id=convenio.creado_por_id,
            observacion="Devolución de revisión jurídica",
        )
        self.db.add(historial)
        try:
            self.db.flush()
            for texto in observaciones:
                self.db.add(ObservacionRevision(
                    convenio_id=convenio.id,
                    historial_etapa_id=historial.id,
                    revision_convenio_id=revision.id,
                    origen=OrigenObservacionRevision.REVISOR_ORI.value,
                    registrada_por_id=usuario.id,
                    responsable_id=convenio.creado_por_id,
                    descripcion=texto.strip(),
                    estado=EstadoObservacionRevision.PENDIENTE.value,
                ))
            revision.estado = EstadoRevisionConvenio.RESUELTA.value
            revision.resultado = ResultadoRevisionConvenio.DEVUELTA.value
            revision.resuelta_por_id = usuario.id
            revision.resuelta_en = datetime.now(UTC)
            convenio.etapa_actual = elaboracion
            self.db.commit()
        except SQLAlchemyError:
            self.db.rollback()
            raise
        return revision

    def obtener_historial(self, convenio_id: int) -> Convenio:
        """Convenio con sus rondas de revisión, observaciones y cambios de etapa,
        para la vista de historial y trazabilidad (CA-06, CA-07 de HU-13).

        No filtra por tipo de revisión a propósito: aunque hoy solo existe la
        ronda jurídica (HU-13), el historial debe seguir siendo válido cuando
        HU-14/HU-15 agreguen sus propias rondas sobre el mismo convenio.
        """
        convenio = self.db.scalar(
            select(Convenio)
            .options(
                selectinload(Convenio.revisiones)
                .selectinload(RevisionConvenio.observaciones)
                .joinedload(ObservacionRevision.registrada_por),
                selectinload(Convenio.revisiones)
                .selectinload(RevisionConvenio.observaciones)
                .joinedload(ObservacionRevision.responsable),
                selectinload(Convenio.revisiones)
                .selectinload(RevisionConvenio.observaciones)
                .joinedload(ObservacionRevision.atendida_por),
                selectinload(Convenio.revisiones).joinedload(
                    RevisionConvenio.responsable
                ),
                selectinload(Convenio.revisiones).joinedload(
                    RevisionConvenio.resuelta_por
                ),
                selectinload(Convenio.historial_etapas).joinedload(
                    HistorialEtapa.etapa_origen
                ),
                selectinload(Convenio.historial_etapas).joinedload(
                    HistorialEtapa.etapa_destino
                ),
                selectinload(Convenio.historial_etapas).joinedload(
                    HistorialEtapa.usuario
                ),
                selectinload(Convenio.historial_etapas).joinedload(
                    HistorialEtapa.responsable
                ),
            )
            .execution_options(populate_existing=True)
            .where(Convenio.id == convenio_id)
        )
        if convenio is None:
            raise ConvenioNoEncontrado("Convenio no encontrado")
        return convenio
