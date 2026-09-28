from datetime import UTC, date, datetime

from pydantic import EmailStr, TypeAdapter, ValidationError
from sqlalchemy import func, or_, select, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, joinedload, selectinload

from backend.models.aliado import Aliado
from backend.models.auditoria import Auditoria
from backend.models.convenio import Convenio
from backend.models.documento import Documento
from backend.models.enums import (
    AccionAuditoria,
    AlcanceConvenio,
    ContextoVersionConvenio,
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
from backend.models.invitacion_revision_contraparte import (
    InvitacionRevisionContraparte,
)
from backend.models.observacion_revision import ObservacionRevision
from backend.models.plantilla_convenio import PlantillaConvenio
from backend.models.respuesta_revision_contraparte import (
    RespuestaRevisionContraparte,
)
from backend.models.revision_convenio import RevisionConvenio
from backend.models.solicitud_convenio import SolicitudConvenio
from backend.models.tipo_convenio import TipoConvenio
from backend.models.unidad_organizacional import UnidadOrganizacional
from backend.models.usuario import Usuario
from backend.models.version_convenio import VersionConvenio
from backend.schemas.convenio import (
    CampoFaltante,
    ConvenioCrear,
    ConvenioElaboracionActualizar,
    ConvenioElaboracionFinalizar,
    ConvenioElaboracionGuardar,
    RevisionContenidoGuardar,
)
from backend.services.contenido_convenio import (
    ContenidoConvenioInvalido,
    documento_tiene_texto,
    expandir_plantilla,
    validar_contenido,
)
from backend.services.contraparte_externa import (
    crear_invitacion_contraparte,
    enviar_invitacion_contraparte,
)
from backend.services.correo import EnviadorCorreo
from backend.services.documentos import AlmacenDocumentos

CODIGO_ETAPA_ELABORACION = "ELABORACION"
CODIGO_ETAPA_REVISION_JURIDICA = "REVISION_AVAL_JURIDICO"
CODIGO_ETAPA_REVISION_CONTRAPARTE = "REVISION_CONTRAPARTE"
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


class ConflictoVersionConvenio(ErrorConvenio):
    def __init__(self, esperada: int, actual: int) -> None:
        self.esperada = esperada
        self.actual = actual
        super().__init__(
            f"La versión esperada era {esperada}, pero la versión actual es {actual}"
        )


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
        self,
        db: Session,
        almacen: AlmacenDocumentos | None = None,
        enviador: EnviadorCorreo | None = None,
        frontend_url: str | None = None,
    ):
        self.db = db
        self.almacen = almacen
        self.enviador = enviador
        self.frontend_url = frontend_url

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

    def _plantilla_base_activa(self) -> PlantillaConvenio:
        plantillas = list(
            self.db.scalars(
                select(PlantillaConvenio)
                .where(PlantillaConvenio.activa.is_(True))
                .order_by(PlantillaConvenio.id)
                .limit(2)
            )
        )
        if len(plantillas) != 1:
            raise ConfiguracionConvenioInvalida(
                "Debe existir exactamente una plantilla de convenio activa"
            )
        return plantillas[0]

    def _crear_version(
        self,
        convenio: Convenio,
        contenido: dict[str, object],
        usuario: Usuario,
        contexto: ContextoVersionConvenio,
        *,
        auditar: bool = True,
    ) -> VersionConvenio:
        try:
            validar_contenido(contenido)
        except ContenidoConvenioInvalido as exc:
            raise ReferenciaConvenioInvalida(str(exc)) from exc
        anterior = convenio.version_actual
        version = VersionConvenio(
            convenio_id=convenio.id,
            numero=anterior + 1,
            contenido=contenido,
            snapshot_metadata=_snapshot_de(convenio),
            autor_id=usuario.id,
            etapa_id=convenio.etapa_actual_id,
            contexto=contexto.value,
            plantilla_id=convenio.plantilla_origen_id,
        )
        self.db.add(version)
        convenio.version_actual = version.numero
        if auditar:
            self.db.add(
                Auditoria(
                    usuario_id=usuario.id,
                    entidad=ENTIDAD_CONVENIO,
                    registro_id=convenio.id,
                    accion=AccionAuditoria.UPDATE.value,
                    campo="contenido_proyecto",
                    valor_anterior=f"versión {anterior}" if anterior else None,
                    valor_nuevo=f"versión {version.numero}",
                )
            )
        self.db.flush()
        return version

    def _version_actual(self, convenio: Convenio) -> VersionConvenio | None:
        if convenio.version_actual == 0:
            return None
        return self.db.scalar(
            select(VersionConvenio).where(
                VersionConvenio.convenio_id == convenio.id,
                VersionConvenio.numero == convenio.version_actual,
            )
        )

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
        # Mantiene coherente la relación ya cargada en la misma sesión (por
        # ejemplo, la bandeja consultada antes de iniciar la elaboración).
        convenio.solicitud = solicitud
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
        plantilla = self._plantilla_base_activa()
        tipo_nombre = self.db.scalar(
            select(TipoConvenio.nombre).where(
                TipoConvenio.id == solicitud.tipo_convenio_id
            )
        )
        try:
            contenido_inicial = expandir_plantilla(
                plantilla.contenido_base, solicitud, tipo_nombre
            )
        except ContenidoConvenioInvalido as exc:
            raise ConfiguracionConvenioInvalida(str(exc)) from exc
        convenio.plantilla_origen_id = plantilla.id
        self._crear_version(
            convenio,
            contenido_inicial,
            usuario,
            ContextoVersionConvenio.INICIALIZACION,
            auditar=False,
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
                    joinedload(RevisionConvenio.version_convenio),
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

    @staticmethod
    def _destinatarios_contraparte(
        solicitud: SolicitudConvenio,
    ) -> tuple[str, str | None]:
        destino = (solicitud.contacto_contraparte_correo or "").strip()
        cc = (solicitud.solicitante.correo or "").strip()
        adaptador = TypeAdapter(EmailStr)
        try:
            adaptador.validate_python(destino)
            adaptador.validate_python(cc)
        except ValidationError as exc:
            raise RevisionNoDisponible(
                "La solicitud no tiene correos válidos para la revisión externa"
            ) from exc
        return destino, None if destino.casefold() == cc.casefold() else cc

    def _entregar_invitacion(
        self,
        invitacion: InvitacionRevisionContraparte,
        token_plano: str,
        convenio: Convenio,
    ) -> None:
        if self.enviador is None or not self.frontend_url:
            raise RuntimeError("El servicio requiere correo y URL pública")
        enviar_invitacion_contraparte(
            self.db,
            self.enviador,
            self.frontend_url,
            invitacion,
            token_plano,
            convenio,
        )

    def enviar_a_contraparte(
        self, convenio_id: int, expected_version: int, usuario: Usuario
    ) -> RevisionConvenio:
        convenio = self.db.scalar(
            select(Convenio)
            .where(Convenio.id == convenio_id)
            .with_for_update()
        )
        if convenio is None:
            raise ConvenioNoEncontrado("Convenio no encontrado")
        if (
            convenio.etapa_actual is None
            or convenio.etapa_actual.codigo != CODIGO_ETAPA_REVISION_CONTRAPARTE
        ):
            raise RevisionNoDisponible(
                "El convenio no está habilitado para revisión de contraparte"
            )
        if expected_version != convenio.version_actual:
            raise ConflictoVersionConvenio(expected_version, convenio.version_actual)

        version = self._version_actual(convenio)
        if version is None:
            raise RevisionNoDisponible("El convenio no tiene una versión disponible")
        segunda = self.db.scalar(
            select(RevisionConvenio)
            .where(
                RevisionConvenio.convenio_id == convenio.id,
                RevisionConvenio.tipo == TipoRevisionConvenio.JURIDICA.value,
                RevisionConvenio.instancia_juridica == 2,
                RevisionConvenio.estado == EstadoRevisionConvenio.RESUELTA.value,
                RevisionConvenio.resultado
                == ResultadoRevisionConvenio.APROBADA.value,
                RevisionConvenio.version_resultado_id == version.id,
            )
            .order_by(RevisionConvenio.numero_ronda.desc())
            .limit(1)
        )
        if segunda is None or segunda.numero_ronda is None:
            raise RevisionNoDisponible(
                "La versión actual no cuenta con la segunda aprobación jurídica"
            )
        primera = self.db.scalar(
            select(RevisionConvenio.id).where(
                RevisionConvenio.convenio_id == convenio.id,
                RevisionConvenio.tipo == TipoRevisionConvenio.JURIDICA.value,
                RevisionConvenio.numero_ronda == segunda.numero_ronda,
                RevisionConvenio.instancia_juridica == 1,
                RevisionConvenio.estado == EstadoRevisionConvenio.RESUELTA.value,
                RevisionConvenio.resultado
                == ResultadoRevisionConvenio.APROBADA.value,
            )
        )
        if primera is None:
            raise RevisionNoDisponible(
                "La ronda jurídica no cuenta con sus dos aprobaciones"
            )
        solicitud = self.db.scalar(
            select(SolicitudConvenio)
            .options(joinedload(SolicitudConvenio.solicitante))
            .where(SolicitudConvenio.id == convenio.solicitud_id)
        )
        if solicitud is None or solicitud.solicitante_id is None:
            raise RevisionNoDisponible("El convenio no tiene un Solicitante asociado")
        correo_destino, correo_cc = self._destinatarios_contraparte(solicitud)
        pendiente = self.db.scalar(
            select(RevisionConvenio.id).where(
                RevisionConvenio.convenio_id == convenio.id,
                RevisionConvenio.tipo
                == TipoRevisionConvenio.CONTRAPARTE.value,
                RevisionConvenio.estado == EstadoRevisionConvenio.PENDIENTE.value,
            )
        )
        if pendiente is not None:
            raise RevisionNoDisponible(
                "Ya existe una revisión de contraparte pendiente"
            )
        historial = self.db.scalar(
            select(HistorialEtapa)
            .join(HistorialEtapa.etapa_destino)
            .where(
                HistorialEtapa.convenio_id == convenio.id,
                Etapa.codigo == CODIGO_ETAPA_REVISION_CONTRAPARTE,
            )
            .order_by(HistorialEtapa.id.desc())
            .limit(1)
        )
        if historial is None:
            raise RevisionNoDisponible(
                "No existe la transición que habilitó la revisión de contraparte"
            )
        revision = RevisionConvenio(
            convenio_id=convenio.id,
            tipo=TipoRevisionConvenio.CONTRAPARTE.value,
            historial_etapa_id=historial.id,
            version_convenio_id=version.id,
            version_resultado_id=None,
            responsable_id=None,
            creada_por_id=usuario.id,
            estado=EstadoRevisionConvenio.PENDIENTE.value,
            resultado=None,
        )
        self.db.add(revision)
        invitacion: InvitacionRevisionContraparte | None = None
        token_plano = ""
        try:
            self.db.flush()
            invitacion, token_plano = crear_invitacion_contraparte(
                self.db,
                revision,
                correo_destino,
                correo_cc,
                usuario.id,
            )
            self.db.add(
                Auditoria(
                    usuario_id=usuario.id,
                    entidad="revision_convenio",
                    registro_id=revision.id,
                    accion=AccionAuditoria.INSERT.value,
                )
            )
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            diagnostico = getattr(exc.orig, "diag", None)
            constraint_name = getattr(diagnostico, "constraint_name", None)
            if constraint_name == "uq_revision_convenio_contraparte_pendiente":
                raise RevisionNoDisponible(
                    "Ya existe una revisión de contraparte pendiente"
                ) from exc
            raise
        except SQLAlchemyError:
            self.db.rollback()
            raise
        assert invitacion is not None
        self._entregar_invitacion(invitacion, token_plano, convenio)
        return revision

    def reenviar_invitacion_contraparte(
        self, convenio_id: int, revision_id: int, usuario: Usuario
    ) -> InvitacionRevisionContraparte:
        convenio = self.db.scalar(
            select(Convenio)
            .where(Convenio.id == convenio_id)
            .execution_options(populate_existing=True)
            .with_for_update()
        )
        if convenio is None:
            raise ConvenioNoEncontrado("Convenio no encontrado")
        revision = self.db.scalar(
            select(RevisionConvenio)
            .where(
                RevisionConvenio.id == revision_id,
                RevisionConvenio.convenio_id == convenio_id,
            )
            .execution_options(populate_existing=True)
            .with_for_update()
        )
        if revision is None:
            raise ConvenioNoEncontrado("Revisión no encontrada para este convenio")
        if (
            revision.tipo != TipoRevisionConvenio.CONTRAPARTE.value
            or revision.estado != EstadoRevisionConvenio.PENDIENTE.value
            or revision.resultado is not None
            or convenio.etapa_actual is None
            or convenio.etapa_actual.codigo != CODIGO_ETAPA_REVISION_CONTRAPARTE
        ):
            raise RevisionNoDisponible(
                "La revisión de contraparte ya no está disponible para reenvío"
            )
        solicitud = self.db.scalar(
            select(SolicitudConvenio)
            .options(joinedload(SolicitudConvenio.solicitante))
            .where(SolicitudConvenio.id == convenio.solicitud_id)
        )
        if solicitud is None:
            raise RevisionNoDisponible("El convenio no tiene una solicitud asociada")
        correo_destino, correo_cc = self._destinatarios_contraparte(solicitud)
        ahora = datetime.now(UTC)
        self.db.execute(
            update(InvitacionRevisionContraparte)
            .where(
                InvitacionRevisionContraparte.revision_convenio_id == revision.id,
                InvitacionRevisionContraparte.utilizado_en.is_(None),
                InvitacionRevisionContraparte.revocado_en.is_(None),
            )
            .values(revocado_en=ahora)
        )
        invitacion, token_plano = crear_invitacion_contraparte(
            self.db, revision, correo_destino, correo_cc, usuario.id
        )
        try:
            self.db.commit()
        except SQLAlchemyError:
            self.db.rollback()
            raise
        self._entregar_invitacion(invitacion, token_plano, convenio)
        return invitacion

    def obtener_para_revision(
        self, convenio_id: int
    ) -> tuple[
        Convenio,
        RevisionConvenio,
        list[Documento],
        VersionConvenio,
        VersionConvenio,
    ]:
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
                joinedload(Convenio.plantilla_origen),
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
                joinedload(RevisionConvenio.version_convenio),
                joinedload(RevisionConvenio.version_resultado),
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
        version_recibida = revision_pendiente.version_convenio
        version_actual = self._version_actual(convenio)
        if version_recibida is None or version_actual is None:
            raise RevisionNoDisponible(
                "La revisión no tiene una versión de convenio disponible"
            )
        convenio.contenido = version_actual.contenido
        return (
            convenio,
            revision_pendiente,
            documentos,
            version_recibida,
            version_actual,
        )

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
                joinedload(Convenio.plantilla_origen),
            )
            .where(Convenio.id == convenio_id)
        )
        if convenio is None:
            raise ConvenioNoEncontrado("Convenio no encontrado")
        version = self._version_actual(convenio)
        convenio.contenido = version.contenido if version is not None else None
        return convenio

    def validar_elaboracion(self, convenio_id: int) -> list[CampoFaltante]:
        convenio = self.obtener(convenio_id)
        version = self._version_actual(convenio)
        return self._faltantes_elaboracion(convenio, version)

    def _faltantes_elaboracion(
        self, convenio: Convenio, version: VersionConvenio | None
    ) -> list[CampoFaltante]:
        faltantes = validar_completitud(convenio)
        if version is None:
            faltantes.append(
                CampoFaltante(
                    campo="contenido",
                    motivo="Debe existir una versión guardada del documento",
                )
            )
            return faltantes
        try:
            tiene_texto = documento_tiene_texto(version.contenido)
        except ContenidoConvenioInvalido:
            faltantes.append(
                CampoFaltante(
                    campo="contenido",
                    motivo="La versión guardada del documento no es válida",
                )
            )
        else:
            if not tiene_texto:
                faltantes.append(
                    CampoFaltante(
                        campo="contenido",
                        motivo="El documento no puede estar vacío",
                    )
                )
        return faltantes

    def listar_versiones(self, convenio_id: int) -> list[VersionConvenio]:
        if self.db.get(Convenio, convenio_id) is None:
            raise ConvenioNoEncontrado("Convenio no encontrado")
        return list(
            self.db.scalars(
                select(VersionConvenio)
                .options(
                    joinedload(VersionConvenio.autor),
                    joinedload(VersionConvenio.etapa),
                    joinedload(VersionConvenio.plantilla),
                )
                .where(VersionConvenio.convenio_id == convenio_id)
                .order_by(VersionConvenio.numero.desc())
            )
        )

    def obtener_version(self, convenio_id: int, numero: int) -> VersionConvenio:
        version = self.db.scalar(
            select(VersionConvenio)
            .options(
                joinedload(VersionConvenio.autor),
                joinedload(VersionConvenio.etapa),
                joinedload(VersionConvenio.plantilla),
            )
            .where(
                VersionConvenio.convenio_id == convenio_id,
                VersionConvenio.numero == numero,
            )
        )
        if version is None:
            raise ConvenioNoEncontrado("Versión de convenio no encontrada")
        return version

    def _aplicar_cambios(
        self,
        convenio: Convenio,
        cambios: dict[str, object],
        usuario: Usuario,
    ) -> bool:
        """Valida y aplica cambios con auditoría, sin cerrar la transacción."""
        combinados = {
            "tipo_convenio_id": convenio.tipo_convenio_id,
            "alcance": convenio.alcance,
            "unidad_organizacional_id": convenio.unidad_organizacional_id,
            "convenio_origen_id": convenio.convenio_origen_id,
            **cambios,
        }
        self._validar_referencias(combinados)
        cambio_realizado = False
        for campo, valor in cambios.items():
            nuevo = valor.value if isinstance(valor, AlcanceConvenio) else valor
            anterior = getattr(convenio, campo)
            if anterior == nuevo:
                continue
            cambio_realizado = True
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
        return cambio_realizado

    def guardar_elaboracion(
        self,
        convenio_id: int,
        datos: ConvenioElaboracionGuardar,
        usuario: Usuario,
    ) -> Convenio:
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
                "Solo se puede editar un convenio en etapa de Elaboración"
            )
        if datos.expected_version != convenio.version_actual:
            self.db.rollback()
            raise ConflictoVersionConvenio(
                datos.expected_version, convenio.version_actual
            )
        try:
            validar_contenido(datos.contenido)
        except ContenidoConvenioInvalido as exc:
            self.db.rollback()
            raise ReferenciaConvenioInvalida(str(exc)) from exc

        actual = self._version_actual(convenio)
        cambios_metadata = datos.model_dump(
            exclude={"contenido", "expected_version"}, exclude_unset=True
        )
        cambio_metadata = self._aplicar_cambios(convenio, cambios_metadata, usuario)
        cambio_contenido = actual is None or actual.contenido != datos.contenido
        if not cambio_metadata and not cambio_contenido:
            self.db.rollback()
            return self.obtener_para_elaboracion(convenio.id)
        try:
            self._crear_version(
                convenio,
                datos.contenido,
                usuario,
                ContextoVersionConvenio.GUARDADO,
            )
            self.db.commit()
        except (IntegrityError, SQLAlchemyError):
            self.db.rollback()
            raise
        return self.obtener_para_elaboracion(convenio.id)

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
        datos: ConvenioElaboracionFinalizar | None = None,
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

        if (
            datos is not None
            and datos.expected_version is not None
            and datos.expected_version != convenio.version_actual
        ):
            self.db.rollback()
            raise ConflictoVersionConvenio(
                datos.expected_version, convenio.version_actual
            )

        actual = self._version_actual(convenio)
        contenido = datos.contenido if datos is not None else None
        if contenido is not None:
            try:
                validar_contenido(contenido)
            except ContenidoConvenioInvalido as exc:
                self.db.rollback()
                raise ReferenciaConvenioInvalida(str(exc)) from exc
        contenido_final = contenido if contenido is not None else (
            actual.contenido if actual is not None else None
        )
        cambios = (
            datos.model_dump(
                exclude={"contenido", "expected_version"}, exclude_unset=True
            )
            if datos is not None
            else {}
        )
        try:
            cambio_metadata = self._aplicar_cambios(convenio, cambios, usuario)
        except ErrorConvenio:
            self.db.rollback()
            raise
        cambio_contenido = (
            contenido is not None
            and (actual is None or contenido != actual.contenido)
        )
        version_para_validar = actual
        if contenido_final is not None and (actual is None or cambio_contenido):
            version_para_validar = VersionConvenio(contenido=contenido_final)
        faltantes = self._faltantes_elaboracion(convenio, version_para_validar)
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
                ObservacionRevision.origen.in_(
                    (
                        OrigenObservacionRevision.REVISOR_ORI.value,
                        OrigenObservacionRevision.CONTRAPARTE.value,
                        OrigenObservacionRevision.REVISION_FINAL_ORI.value,
                    )
                ),
                ObservacionRevision.estado
                == EstadoObservacionRevision.PENDIENTE.value,
            )
            .limit(1)
        )
        if pendiente is not None:
            self.db.rollback()
            raise RevisionNoDisponible(
                "Debe atender todas las observaciones pendientes "
                "antes de reenviar el convenio"
            )

        ultima_devuelta = self.db.scalar(
            select(RevisionConvenio)
            .options(joinedload(RevisionConvenio.version_resultado))
            .where(
                RevisionConvenio.convenio_id == convenio.id,
                RevisionConvenio.tipo.in_(
                    (
                        TipoRevisionConvenio.JURIDICA.value,
                        TipoRevisionConvenio.CONTRAPARTE.value,
                        TipoRevisionConvenio.FINAL.value,
                    )
                ),
                RevisionConvenio.resultado
                == ResultadoRevisionConvenio.DEVUELTA.value,
            )
            .order_by(RevisionConvenio.id.desc())
            .limit(1)
        )
        ultima_ronda = self.db.scalar(
            select(func.max(RevisionConvenio.numero_ronda)).where(
                RevisionConvenio.convenio_id == convenio.id,
                RevisionConvenio.tipo == TipoRevisionConvenio.JURIDICA.value,
            )
        )
        numero_ronda = (ultima_ronda or 0) + 1

        juridica = self.db.scalar(
            select(Etapa).where(Etapa.codigo == CODIGO_ETAPA_REVISION_JURIDICA)
        )
        if juridica is None:
            self.db.rollback()
            raise ConfiguracionConvenioInvalida(
                "No existe la etapa obligatoria REVISION_AVAL_JURIDICO"
            )

        version_final = actual
        if cambio_metadata or cambio_contenido or actual is None:
            version_final = self._crear_version(
                convenio,
                contenido_final,
                usuario,
                ContextoVersionConvenio.FINALIZACION,
            )
        if version_final is None:
            self.db.rollback()
            raise ElaboracionIncompleta(
                [
                    CampoFaltante(
                        campo="contenido",
                        motivo="Debe existir una versión guardada del documento",
                    )
                ]
            )
        if ultima_devuelta is not None:
            version_devuelta = ultima_devuelta.version_resultado
            if version_devuelta is None:
                self.db.rollback()
                raise RevisionNoDisponible(
                    "La revisión devuelta no identifica la versión que debe corregirse"
                )
            if version_final.numero <= version_devuelta.numero:
                self.db.rollback()
                raise RevisionNoDisponible(
                    "Debe crear una nueva versión del proyecto antes de reenviarlo"
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
                    version_convenio_id=version_final.id,
                    version_resultado_id=None,
                    instancia_juridica=1,
                    numero_ronda=numero_ronda,
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
        # Todas las mutaciones jurídicas usan el mismo orden para evitar deadlocks.
        convenio = self.db.scalar(
            select(Convenio).where(Convenio.id == convenio_id).with_for_update()
        )
        if convenio is None:
            raise ConvenioNoEncontrado("Convenio no encontrado")
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
        if (
            revision.tipo != TipoRevisionConvenio.JURIDICA.value
            or revision.estado != EstadoRevisionConvenio.PENDIENTE.value
            or revision.resultado is not None
            or convenio.etapa_actual is None
            or convenio.etapa_actual.codigo != CODIGO_ETAPA_REVISION_JURIDICA
        ):
            raise RevisionNoDisponible("La revisión jurídica ya no está pendiente")
        return convenio, revision

    def _version_actual_revision(
        self, convenio: Convenio, esperada: int
    ) -> VersionConvenio:
        if esperada != convenio.version_actual:
            raise ConflictoVersionConvenio(esperada, convenio.version_actual)
        version = self._version_actual(convenio)
        if version is None:
            raise RevisionNoDisponible("El proyecto no tiene una versión disponible")
        return version

    def guardar_contenido_revision(
        self,
        convenio_id: int,
        revision_id: int,
        datos: RevisionContenidoGuardar,
        usuario: Usuario,
    ) -> VersionConvenio:
        convenio, _ = self._revision_juridica_pendiente(convenio_id, revision_id)
        actual = self._version_actual_revision(convenio, datos.expected_version)
        try:
            validar_contenido(datos.contenido)
        except ContenidoConvenioInvalido as exc:
            self.db.rollback()
            raise ReferenciaConvenioInvalida(str(exc)) from exc
        if actual.contenido == datos.contenido:
            self.db.commit()
            return actual
        try:
            version = self._crear_version(
                convenio,
                datos.contenido,
                usuario,
                ContextoVersionConvenio.CORRECCION_REVISION,
            )
            self.db.commit()
            return version
        except SQLAlchemyError:
            self.db.rollback()
            raise

    def registrar_observacion_revision(
        self,
        convenio_id: int,
        revision_id: int,
        descripcion: str,
        usuario: Usuario,
    ) -> ObservacionRevision:
        convenio, revision = self._revision_juridica_pendiente(
            convenio_id, revision_id
        )
        texto = descripcion.strip()
        if not texto:
            raise ReferenciaConvenioInvalida("La observación debe tener contenido")
        if revision.historial_etapa_id is None:
            raise RevisionNoDisponible(
                "La revisión no tiene una transición de etapa asociada"
            )
        observacion = ObservacionRevision(
            convenio_id=convenio.id,
            historial_etapa_id=revision.historial_etapa_id,
            revision_convenio_id=revision.id,
            origen=OrigenObservacionRevision.REVISOR_ORI.value,
            registrada_por_id=usuario.id,
            responsable_id=convenio.creado_por_id,
            descripcion=texto,
            estado=EstadoObservacionRevision.PENDIENTE.value,
        )
        self.db.add(observacion)
        try:
            self.db.commit()
        except SQLAlchemyError:
            self.db.rollback()
            raise
        return observacion

    def aprobar(
        self,
        convenio_id: int,
        revision_id: int,
        expected_version: int,
        usuario: Usuario,
    ) -> RevisionConvenio:
        convenio, revision = self._revision_juridica_pendiente(
            convenio_id, revision_id
        )
        version_actual = self._version_actual_revision(convenio, expected_version)
        if revision.instancia_juridica not in {1, 2} or revision.numero_ronda is None:
            raise RevisionNoDisponible(
                "La revisión legacy no tiene instancia y ronda jurídicas definidas"
            )
        pendiente = self.db.scalar(
            select(ObservacionRevision.id)
            .where(
                ObservacionRevision.revision_convenio_id == revision.id,
                ObservacionRevision.origen
                == OrigenObservacionRevision.REVISOR_ORI.value,
                ObservacionRevision.estado
                == EstadoObservacionRevision.PENDIENTE.value,
            )
            .limit(1)
        )
        if pendiente is not None:
            raise RevisionNoDisponible("Hay observaciones pendientes por atender")
        if revision.instancia_juridica == 2:
            primera = self.db.scalar(
                select(RevisionConvenio).where(
                    RevisionConvenio.convenio_id == convenio.id,
                    RevisionConvenio.tipo == TipoRevisionConvenio.JURIDICA.value,
                    RevisionConvenio.numero_ronda == revision.numero_ronda,
                    RevisionConvenio.instancia_juridica == 1,
                    RevisionConvenio.resultado
                    == ResultadoRevisionConvenio.APROBADA.value,
                )
            )
            if primera is None:
                raise RevisionNoDisponible(
                    "La primera revisión jurídica de la ronda no está aprobada"
                )
            if primera.resuelta_por_id == usuario.id:
                raise RevisionNoDisponible(
                    "La segunda revisión debe ser aprobada por otro Revisor ORI"
                )
            etapa_destino = self.db.scalar(
                select(Etapa).where(
                    Etapa.codigo == CODIGO_ETAPA_REVISION_CONTRAPARTE
                )
            )
            if etapa_destino is None:
                raise ConfiguracionConvenioInvalida(
                    "No existe la etapa obligatoria REVISION_CONTRAPARTE"
                )
        else:
            etapa_destino = None
        revision.estado = EstadoRevisionConvenio.RESUELTA.value
        revision.resultado = ResultadoRevisionConvenio.APROBADA.value
        revision.resuelta_por_id = usuario.id
        revision.resuelta_en = datetime.now(UTC)
        revision.version_resultado_id = version_actual.id
        self.db.add(
            Auditoria(
                usuario_id=usuario.id,
                entidad="revision_convenio",
                registro_id=revision.id,
                accion=AccionAuditoria.UPDATE.value,
                campo="resultado",
                valor_anterior=None,
                valor_nuevo=ResultadoRevisionConvenio.APROBADA.value,
            )
        )
        try:
            self.db.flush()
            if revision.instancia_juridica == 1:
                self.db.add(
                    RevisionConvenio(
                        convenio_id=convenio.id,
                        tipo=TipoRevisionConvenio.JURIDICA.value,
                        historial_etapa_id=revision.historial_etapa_id,
                        version_convenio_id=version_actual.id,
                        version_resultado_id=None,
                        instancia_juridica=2,
                        numero_ronda=revision.numero_ronda,
                        estado=EstadoRevisionConvenio.PENDIENTE.value,
                        resultado=None,
                        responsable_id=None,
                        snapshot_datos=_snapshot_de(convenio),
                    )
                )
            else:
                assert etapa_destino is not None
                self.db.add(
                    HistorialEtapa(
                        convenio_id=convenio.id,
                        etapa_origen_id=convenio.etapa_actual_id,
                        etapa_destino_id=etapa_destino.id,
                        usuario_id=usuario.id,
                        responsable_id=convenio.creado_por_id,
                        observacion="Dos revisiones jurídicas aprobadas",
                    )
                )
                convenio.etapa_actual = etapa_destino
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise RevisionNoDisponible(
                "La revisión jurídica fue actualizada por otra operación"
            ) from exc
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
        if observacion.origen not in {
            OrigenObservacionRevision.REVISOR_ORI.value,
            OrigenObservacionRevision.CONTRAPARTE.value,
            OrigenObservacionRevision.REVISION_FINAL_ORI.value,
        }:
            raise ObservacionNoDisponible(
                "La observación no corresponde a una revisión atendible"
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
        self,
        convenio_id: int,
        revision_id: int,
        observaciones: list[str],
        expected_version: int,
        usuario: Usuario,
    ) -> RevisionConvenio:
        if any(not texto.strip() for texto in observaciones):
            raise ReferenciaConvenioInvalida(
                "Cada observación debe tener contenido"
            )
        convenio, revision = self._revision_juridica_pendiente(
            convenio_id, revision_id
        )
        version_actual = self._version_actual_revision(convenio, expected_version)
        observaciones_existentes = self.db.scalar(
            select(func.count())
            .select_from(ObservacionRevision)
            .where(ObservacionRevision.revision_convenio_id == revision.id)
        )
        if not observaciones and not observaciones_existentes:
            raise ReferenciaConvenioInvalida("Debe incluir al menos una observación")
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
            revision.version_resultado_id = version_actual.id
            self.db.add(
                Auditoria(
                    usuario_id=usuario.id,
                    entidad="revision_convenio",
                    registro_id=revision.id,
                    accion=AccionAuditoria.UPDATE.value,
                    campo="resultado",
                    valor_anterior=None,
                    valor_nuevo=ResultadoRevisionConvenio.DEVUELTA.value,
                )
            )
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
                    RevisionConvenio.creada_por
                ),
                selectinload(Convenio.revisiones).joinedload(
                    RevisionConvenio.resuelta_por
                ),
                selectinload(Convenio.revisiones).joinedload(
                    RevisionConvenio.version_convenio
                ),
                selectinload(Convenio.revisiones).joinedload(
                    RevisionConvenio.version_resultado
                ),
                selectinload(Convenio.revisiones).selectinload(
                    RevisionConvenio.invitaciones_contraparte
                ).joinedload(InvitacionRevisionContraparte.generada_por),
                selectinload(Convenio.revisiones)
                .joinedload(RevisionConvenio.respuesta_contraparte)
                .defer(RespuestaRevisionContraparte.firma_png),
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
