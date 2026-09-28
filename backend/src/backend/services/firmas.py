from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from pathlib import Path
from secrets import token_hex

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, joinedload, selectinload

from backend.models.convenio import Convenio
from backend.models.documento import Documento
from backend.models.enums import (
    EstadoConvenio,
    EstadoFirmaConvenio,
    EstadoObservacionRevision,
    EstadoProcesoFirmasConvenio,
    EstadoRevisionConvenio,
    ModalidadFirma,
    OrigenObservacionRevision,
    ParteFirmaConvenio,
    ResultadoRevisionConvenio,
    RolFirmanteConvenio,
    TipoRevisionConvenio,
    TipoSolicitante,
)
from backend.models.etapa import Etapa
from backend.models.firma_convenio import FirmaConvenio
from backend.models.historial_etapa import HistorialEtapa
from backend.models.observacion_revision import ObservacionRevision
from backend.models.proceso_firmas_convenio import ProcesoFirmasConvenio
from backend.models.revision_convenio import RevisionConvenio
from backend.models.usuario import Usuario
from backend.models.version_convenio import VersionConvenio
from backend.services.convenios import (
    ConfiguracionConvenioInvalida,
    ConflictoVersionConvenio,
    ConvenioNoEncontrado,
    ReferenciaConvenioInvalida,
    RevisionNoDisponible,
)
from backend.services.documentos import TAMANO_MAXIMO_DOCUMENTO, AlmacenDocumentos

CODIGO_ETAPA_ELABORACION = "ELABORACION"
CODIGO_ETAPA_REVISION_FINAL = "REVISION_FINAL"
CODIGO_ETAPA_APROBACION_FIRMAS = "APROBACION_FIRMAS"

ROLES_FIRMANTES = (
    RolFirmanteConvenio.ADMINISTRADOR_ORI,
    RolFirmanteConvenio.REVISOR_ORI,
    RolFirmanteConvenio.VICERRECTORIA_FINANCIERA,
    RolFirmanteConvenio.VICERRECTORIA_ACADEMICA,
    RolFirmanteConvenio.SECRETARIA,
    RolFirmanteConvenio.RECTOR,
    RolFirmanteConvenio.PARTE_SOLICITANTE,
)


@dataclass
class ContextoRevisionFinal:
    convenio: Convenio
    revision_final: RevisionConvenio
    revision_contraparte: RevisionConvenio
    revisiones_juridicas: list[RevisionConvenio]
    version: VersionConvenio
    documentos: list[Documento]
    observaciones_pendientes: list[ObservacionRevision]
    proceso_activo: ProcesoFirmasConvenio | None


class ServicioFirmas:
    def __init__(
        self, db: Session, almacen: AlmacenDocumentos | None = None
    ) -> None:
        self.db = db
        self.almacen = almacen

    def _almacen_requerido(self) -> AlmacenDocumentos:
        if self.almacen is None:
            raise RuntimeError("Esta operación requiere un almacén documental")
        return self.almacen

    def _convenio(self, convenio_id: int, *, bloquear: bool) -> Convenio:
        consulta = select(Convenio).where(Convenio.id == convenio_id)
        if bloquear:
            consulta = consulta.with_for_update()
        convenio = self.db.scalar(consulta)
        if convenio is None:
            raise ConvenioNoEncontrado("Convenio no encontrado")
        return convenio

    def _cargar_convenio_para_lectura(self, convenio_id: int) -> Convenio:
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
        return convenio

    @staticmethod
    def _validar_etapa_final(convenio: Convenio) -> None:
        if (
            convenio.etapa_actual is None
            or convenio.etapa_actual.codigo != CODIGO_ETAPA_REVISION_FINAL
        ):
            raise RevisionNoDisponible(
                "El convenio no está en etapa de revisión final"
            )

    def _revision_cargada(self, revision_id: int) -> RevisionConvenio:
        revision = self.db.scalar(
            select(RevisionConvenio)
            .options(
                selectinload(RevisionConvenio.observaciones).joinedload(
                    ObservacionRevision.registrada_por
                ),
                selectinload(RevisionConvenio.invitaciones_contraparte),
                joinedload(RevisionConvenio.respuesta_contraparte),
                joinedload(RevisionConvenio.responsable),
                joinedload(RevisionConvenio.creada_por),
                joinedload(RevisionConvenio.resuelta_por),
                joinedload(RevisionConvenio.version_convenio),
                joinedload(RevisionConvenio.version_resultado),
            )
            .where(RevisionConvenio.id == revision_id)
        )
        if revision is None:
            raise RevisionNoDisponible("La revisión requerida ya no existe")
        return revision

    def _contexto(self, convenio_id: int, *, bloquear: bool) -> ContextoRevisionFinal:
        convenio = self._convenio(convenio_id, bloquear=bloquear)
        self._validar_etapa_final(convenio)

        contraparte = self.db.scalar(
            select(RevisionConvenio)
            .where(
                RevisionConvenio.convenio_id == convenio.id,
                RevisionConvenio.tipo == TipoRevisionConvenio.CONTRAPARTE.value,
                RevisionConvenio.estado == EstadoRevisionConvenio.RESUELTA.value,
                RevisionConvenio.resultado
                == ResultadoRevisionConvenio.APROBADA.value,
                RevisionConvenio.version_resultado_id.is_not(None),
            )
            .order_by(RevisionConvenio.id.desc())
            .limit(1)
        )
        if contraparte is None or contraparte.version_resultado_id is None:
            raise RevisionNoDisponible(
                "No existe una aprobación de contraparte válida para el ciclo actual"
            )
        version = self.db.get(VersionConvenio, contraparte.version_resultado_id)
        if version is None or version.convenio_id != convenio.id:
            raise RevisionNoDisponible(
                "La aprobación de contraparte no identifica una versión válida"
            )
        if contraparte.version_convenio_id != version.id:
            raise RevisionNoDisponible(
                "La contraparte no aprobó la misma versión que recibió"
            )

        revision_final = self.db.scalar(
            select(RevisionConvenio).where(
                RevisionConvenio.convenio_id == convenio.id,
                RevisionConvenio.tipo == TipoRevisionConvenio.FINAL.value,
                RevisionConvenio.estado == EstadoRevisionConvenio.PENDIENTE.value,
            )
        )
        if (
            revision_final is None
            or revision_final.version_convenio_id != version.id
            or revision_final.resultado is not None
        ):
            raise RevisionNoDisponible(
                "No existe una revisión final pendiente para la versión aprobada"
            )

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
                "La versión aprobada por contraparte no tiene dos avales jurídicos"
            )
        primera = self.db.scalar(
            select(RevisionConvenio).where(
                RevisionConvenio.convenio_id == convenio.id,
                RevisionConvenio.tipo == TipoRevisionConvenio.JURIDICA.value,
                RevisionConvenio.numero_ronda == segunda.numero_ronda,
                RevisionConvenio.instancia_juridica == 1,
                RevisionConvenio.estado == EstadoRevisionConvenio.RESUELTA.value,
                RevisionConvenio.resultado
                == ResultadoRevisionConvenio.APROBADA.value,
                RevisionConvenio.version_resultado_id == version.id,
            )
        )
        if primera is None:
            raise RevisionNoDisponible(
                "Los avales jurídicos no corresponden a la misma versión y ronda"
            )

        observaciones = list(
            self.db.scalars(
                select(ObservacionRevision)
                .options(
                    joinedload(ObservacionRevision.registrada_por),
                    joinedload(ObservacionRevision.responsable),
                    joinedload(ObservacionRevision.atendida_por),
                )
                .where(
                    ObservacionRevision.convenio_id == convenio.id,
                    ObservacionRevision.estado
                    == EstadoObservacionRevision.PENDIENTE.value,
                )
                .order_by(ObservacionRevision.id)
            )
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
        proceso = self.db.scalar(
            select(ProcesoFirmasConvenio)
            .options(selectinload(ProcesoFirmasConvenio.firmas))
            .where(
                ProcesoFirmasConvenio.convenio_id == convenio.id,
                ProcesoFirmasConvenio.estado.in_(
                    (
                        EstadoProcesoFirmasConvenio.CONFIGURACION.value,
                        EstadoProcesoFirmasConvenio.EN_CURSO.value,
                    )
                ),
            )
        )
        if proceso is not None:
            raise RevisionNoDisponible(
                "El convenio no puede tener firmas activas durante la revisión final"
            )
        if not bloquear:
            convenio = self._cargar_convenio_para_lectura(convenio.id)
            convenio.contenido = version.contenido
            revision_final = self._revision_cargada(revision_final.id)
            contraparte = self._revision_cargada(contraparte.id)
            primera = self._revision_cargada(primera.id)
            segunda = self._revision_cargada(segunda.id)
        return ContextoRevisionFinal(
            convenio=convenio,
            revision_final=revision_final,
            revision_contraparte=contraparte,
            revisiones_juridicas=[primera, segunda],
            version=version,
            documentos=documentos,
            observaciones_pendientes=observaciones,
            proceso_activo=None,
        )

    def obtener_revision_final(self, convenio_id: int) -> ContextoRevisionFinal:
        return self._contexto(convenio_id, bloquear=False)

    @staticmethod
    def _validar_version(version: VersionConvenio, expected_version: int) -> None:
        if version.numero != expected_version:
            raise ConflictoVersionConvenio(expected_version, version.numero)

    def devolver_revision_final(
        self,
        convenio_id: int,
        observaciones: list[str],
        expected_version: int,
        usuario: Usuario,
    ) -> RevisionConvenio:
        textos = [texto.strip() for texto in observaciones]
        if not textos or any(not texto for texto in textos):
            raise ReferenciaConvenioInvalida(
                "Debe incluir al menos una observación con contenido"
            )
        contexto = self._contexto(convenio_id, bloquear=True)
        self._validar_version(contexto.version, expected_version)
        elaboracion = self.db.scalar(
            select(Etapa).where(Etapa.codigo == CODIGO_ETAPA_ELABORACION)
        )
        if elaboracion is None:
            raise ConfiguracionConvenioInvalida("No existe la etapa ELABORACION")
        historial = HistorialEtapa(
            convenio_id=contexto.convenio.id,
            etapa_origen_id=contexto.convenio.etapa_actual_id,
            etapa_destino_id=elaboracion.id,
            usuario_id=usuario.id,
            responsable_id=contexto.convenio.creado_por_id,
            observacion="Devolución de revisión final ORI",
        )
        self.db.add(historial)
        try:
            self.db.flush()
            for texto in textos:
                self.db.add(
                    ObservacionRevision(
                        convenio_id=contexto.convenio.id,
                        historial_etapa_id=historial.id,
                        revision_convenio_id=contexto.revision_final.id,
                        origen=OrigenObservacionRevision.REVISION_FINAL_ORI.value,
                        registrada_por_id=usuario.id,
                        responsable_id=contexto.convenio.creado_por_id,
                        descripcion=texto,
                        estado=EstadoObservacionRevision.PENDIENTE.value,
                    )
                )
            ahora = datetime.now(UTC)
            contexto.revision_final.estado = EstadoRevisionConvenio.RESUELTA.value
            contexto.revision_final.resultado = (
                ResultadoRevisionConvenio.DEVUELTA.value
            )
            contexto.revision_final.version_resultado_id = contexto.version.id
            contexto.revision_final.resuelta_por_id = usuario.id
            contexto.revision_final.resuelta_en = ahora
            contexto.convenio.etapa_actual = elaboracion
            contexto.convenio.estado = EstadoConvenio.EN_TRAMITE.value
            self.db.commit()
        except SQLAlchemyError:
            self.db.rollback()
            raise
        return contexto.revision_final

    def aprobar_revision_final(
        self, convenio_id: int, expected_version: int, usuario: Usuario
    ) -> ProcesoFirmasConvenio:
        contexto = self._contexto(convenio_id, bloquear=True)
        self._validar_version(contexto.version, expected_version)
        if contexto.observaciones_pendientes:
            raise RevisionNoDisponible("Hay observaciones pendientes por atender")
        otra_pendiente = self.db.scalar(
            select(RevisionConvenio.id)
            .where(
                RevisionConvenio.convenio_id == contexto.convenio.id,
                RevisionConvenio.estado == EstadoRevisionConvenio.PENDIENTE.value,
                RevisionConvenio.id != contexto.revision_final.id,
            )
            .limit(1)
        )
        if otra_pendiente is not None:
            raise RevisionNoDisponible("Existe otra revisión incompatible pendiente")
        etapa_firmas = self.db.scalar(
            select(Etapa).where(Etapa.codigo == CODIGO_ETAPA_APROBACION_FIRMAS)
        )
        if etapa_firmas is None:
            raise ConfiguracionConvenioInvalida(
                "No existe la etapa APROBACION_FIRMAS"
            )
        historial = HistorialEtapa(
            convenio_id=contexto.convenio.id,
            etapa_origen_id=contexto.convenio.etapa_actual_id,
            etapa_destino_id=etapa_firmas.id,
            usuario_id=usuario.id,
            responsable_id=usuario.id,
            observacion="Aprobación de revisión final para firmas",
        )
        proceso = ProcesoFirmasConvenio(
            convenio_id=contexto.convenio.id,
            version_convenio_id=contexto.version.id,
            revision_final_id=contexto.revision_final.id,
            creado_por_id=usuario.id,
            estado=EstadoProcesoFirmasConvenio.CONFIGURACION.value,
        )
        self.db.add_all([historial, proceso])
        try:
            self.db.flush()
            tipo_solicitante = contexto.convenio.solicitud.tipo_solicitante
            parte_solicitante = (
                ParteFirmaConvenio.UNIDAD_SOLICITANTE
                if tipo_solicitante == TipoSolicitante.INTERNO.value
                else ParteFirmaConvenio.REPRESENTANTE_LEGAL_ENTIDAD
            )
            for orden, rol in enumerate(ROLES_FIRMANTES, start=1):
                parte = (
                    parte_solicitante
                    if rol == RolFirmanteConvenio.PARTE_SOLICITANTE
                    else ParteFirmaConvenio.UNIVERSIDAD
                )
                self.db.add(
                    FirmaConvenio(
                        proceso_firmas_id=proceso.id,
                        orden=orden,
                        rol_firmante=rol.value,
                        parte=parte.value,
                        estado=EstadoFirmaConvenio.PENDIENTE.value,
                    )
                )
            ahora = datetime.now(UTC)
            contexto.revision_final.estado = EstadoRevisionConvenio.RESUELTA.value
            contexto.revision_final.resultado = (
                ResultadoRevisionConvenio.APROBADA.value
            )
            contexto.revision_final.version_resultado_id = contexto.version.id
            contexto.revision_final.resuelta_por_id = usuario.id
            contexto.revision_final.resuelta_en = ahora
            contexto.convenio.etapa_actual = etapa_firmas
            contexto.convenio.estado = EstadoConvenio.EN_TRAMITE.value
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise RevisionNoDisponible(
                "La revisión final ya fue aprobada o existe un proceso activo"
            ) from exc
        except SQLAlchemyError:
            self.db.rollback()
            raise
        return self.obtener_proceso_activo(convenio_id)

    def obtener_proceso_activo(
        self, convenio_id: int, *, bloquear: bool = False
    ) -> ProcesoFirmasConvenio:
        consulta = (
            select(ProcesoFirmasConvenio)
            .options(
                selectinload(ProcesoFirmasConvenio.version_convenio),
                selectinload(ProcesoFirmasConvenio.firmas).selectinload(
                    FirmaConvenio.invitaciones
                ),
                selectinload(ProcesoFirmasConvenio.firmas).joinedload(
                    FirmaConvenio.documento
                ),
            )
            .where(
                ProcesoFirmasConvenio.convenio_id == convenio_id,
                ProcesoFirmasConvenio.estado.in_(
                    (
                        EstadoProcesoFirmasConvenio.CONFIGURACION.value,
                        EstadoProcesoFirmasConvenio.EN_CURSO.value,
                    )
                ),
            )
        )
        if bloquear:
            consulta = consulta.execution_options(
                populate_existing=True
            ).with_for_update()
        proceso = self.db.scalar(consulta)
        if proceso is None:
            raise RevisionNoDisponible("No existe un proceso de firmas activo")
        return proceso

    def registrar_firmas_fisicas(
        self,
        convenio_id: int,
        firma_ids: list[int],
        fecha_firma: date,
        nombre_archivo: str,
        tipo_mime: str,
        contenido: bytes,
        usuario: Usuario,
    ) -> ProcesoFirmasConvenio:
        if not firma_ids:
            raise ReferenciaConvenioInvalida(
                "Debe seleccionar al menos una firma física"
            )
        if len(set(firma_ids)) != len(firma_ids):
            raise ReferenciaConvenioInvalida("No se permiten firmas duplicadas")

        convenio = self._convenio(convenio_id, bloquear=True)
        if (
            convenio.etapa_actual is None
            or convenio.etapa_actual.codigo != CODIGO_ETAPA_APROBACION_FIRMAS
        ):
            raise RevisionNoDisponible(
                "El convenio no está en aprobación de firmas"
            )
        proceso = self.obtener_proceso_activo(convenio_id, bloquear=True)
        if proceso.estado != EstadoProcesoFirmasConvenio.EN_CURSO.value:
            raise RevisionNoDisponible("El proceso de firmas no está en curso")

        firmas = list(
            self.db.scalars(
                select(FirmaConvenio)
                .where(FirmaConvenio.id.in_(firma_ids))
                .order_by(FirmaConvenio.orden)
                .execution_options(populate_existing=True)
                .with_for_update()
            )
        )
        if (
            len(firmas) != len(firma_ids)
            or any(firma.proceso_firmas_id != proceso.id for firma in firmas)
        ):
            raise ReferenciaConvenioInvalida(
                "Todas las firmas deben pertenecer al proceso activo del convenio"
            )
        if any(firma.modalidad != ModalidadFirma.FISICA.value for firma in firmas):
            raise ReferenciaConvenioInvalida(
                "Solo pueden registrarse firmas de modalidad física"
            )
        if any(
            firma.estado != EstadoFirmaConvenio.PENDIENTE.value
            or firma.fecha_firma is not None
            or firma.documento_id is not None
            for firma in firmas
        ):
            raise RevisionNoDisponible(
                "Una firma física completada o con evidencia no puede sobrescribirse"
            )

        nombre_seguro = Path(nombre_archivo.replace("\\", "/")).name.strip()
        if not nombre_seguro or Path(nombre_seguro).suffix.lower() != ".pdf":
            raise ReferenciaConvenioInvalida(
                "La evidencia de firma física debe ser un archivo PDF"
            )
        if tipo_mime != "application/pdf":
            raise ReferenciaConvenioInvalida(
                "El tipo de contenido de la evidencia debe ser application/pdf"
            )
        if not contenido:
            raise ReferenciaConvenioInvalida("El documento firmado está vacío")
        if len(contenido) > TAMANO_MAXIMO_DOCUMENTO:
            raise ReferenciaConvenioInvalida(
                "El documento firmado supera el límite de 10 MB"
            )

        clave = f"convenios/{convenio.id}/firmas/{token_hex(20)}.pdf"
        documento = Documento(
            solicitud_id=None,
            convenio_id=convenio.id,
            tipo="CONVENIO_FIRMADO",
            nombre_archivo=nombre_seguro[:255],
            ruta_almacenamiento=clave,
            tipo_mime=tipo_mime,
            tamano_bytes=len(contenido),
            es_vigente=True,
            cargado_por_id=usuario.id,
        )
        almacen = self._almacen_requerido()
        almacen.guardar(clave, contenido)
        self.db.add(documento)
        try:
            self.db.flush()
            instante_firma = datetime.combine(fecha_firma, time.min, tzinfo=UTC)
            for firma in firmas:
                firma.estado = EstadoFirmaConvenio.FIRMADA.value
                firma.fecha_firma = instante_firma
                firma.documento_id = documento.id
            self.db.commit()
        except SQLAlchemyError:
            self.db.rollback()
            almacen.eliminar(clave)
            raise
        return self.obtener_proceso_activo(convenio_id)

    def configurar_firma(
        self,
        convenio_id: int,
        firma_id: int,
        nombre: str,
        cargo: str,
        correo: str | None,
        modalidad: ModalidadFirma,
    ) -> FirmaConvenio:
        convenio = self._convenio(convenio_id, bloquear=True)
        if (
            convenio.etapa_actual is None
            or convenio.etapa_actual.codigo != CODIGO_ETAPA_APROBACION_FIRMAS
        ):
            raise RevisionNoDisponible(
                "El convenio no está configurando su proceso de firmas"
            )
        proceso = self.obtener_proceso_activo(convenio_id, bloquear=True)
        if proceso.estado != EstadoProcesoFirmasConvenio.CONFIGURACION.value:
            raise RevisionNoDisponible(
                "Los firmantes no pueden modificarse después de iniciar el proceso"
            )
        firma = self.db.scalar(
            select(FirmaConvenio)
            .where(
                FirmaConvenio.id == firma_id,
                FirmaConvenio.proceso_firmas_id == proceso.id,
            )
            .with_for_update()
        )
        if firma is None:
            raise ConvenioNoEncontrado("Firma no encontrada para el proceso activo")
        if (
            firma.estado != EstadoFirmaConvenio.PENDIENTE.value
            or firma.fecha_firma is not None
            or firma.documento_id is not None
        ):
            raise RevisionNoDisponible(
                "Una firma completada o con evidencia no puede reconfigurarse"
            )
        nombre_limpio = nombre.strip()
        cargo_limpio = cargo.strip()
        correo_limpio = correo.strip().lower() if correo else None
        if not nombre_limpio or not cargo_limpio:
            raise ReferenciaConvenioInvalida("Nombre y cargo son obligatorios")
        if modalidad == ModalidadFirma.ELECTRONICA and not correo_limpio:
            raise ReferenciaConvenioInvalida(
                "La firma electrónica requiere correo del firmante"
            )
        firma.nombre_firmante = nombre_limpio
        firma.cargo_firmante = cargo_limpio
        firma.correo_firmante = correo_limpio
        firma.modalidad = modalidad.value
        try:
            self.db.commit()
        except SQLAlchemyError:
            self.db.rollback()
            raise
        return firma

    @staticmethod
    def _firma_configurada(firma: FirmaConvenio) -> bool:
        if not firma.nombre_firmante or not firma.cargo_firmante:
            return False
        if firma.modalidad == ModalidadFirma.FISICA.value:
            return True
        return (
            firma.modalidad == ModalidadFirma.ELECTRONICA.value
            and bool(firma.correo_firmante)
        )

    def iniciar(self, convenio_id: int) -> ProcesoFirmasConvenio:
        convenio = self._convenio(convenio_id, bloquear=True)
        if (
            convenio.etapa_actual is None
            or convenio.etapa_actual.codigo != CODIGO_ETAPA_APROBACION_FIRMAS
        ):
            raise RevisionNoDisponible(
                "El convenio no está en aprobación de firmas"
            )
        proceso = self.obtener_proceso_activo(convenio_id, bloquear=True)
        if proceso.estado != EstadoProcesoFirmasConvenio.CONFIGURACION.value:
            raise RevisionNoDisponible("El proceso de firmas ya fue iniciado")
        firmas = list(
            self.db.scalars(
                select(FirmaConvenio)
                .where(FirmaConvenio.proceso_firmas_id == proceso.id)
                .order_by(FirmaConvenio.orden)
                .with_for_update()
            )
        )
        if len(firmas) != len(ROLES_FIRMANTES):
            raise RevisionNoDisponible("El proceso debe tener exactamente 7 firmas")
        esperado = [
            (orden, rol.value) for orden, rol in enumerate(ROLES_FIRMANTES, start=1)
        ]
        if [(firma.orden, firma.rol_firmante) for firma in firmas] != esperado:
            raise RevisionNoDisponible("Los siete slots de firma no son válidos")
        if any(firma.estado != EstadoFirmaConvenio.PENDIENTE.value for firma in firmas):
            raise RevisionNoDisponible("El proceso contiene una firma ya completada")
        if any(not self._firma_configurada(firma) for firma in firmas):
            raise RevisionNoDisponible(
                "Las siete firmas deben estar correctamente configuradas"
            )
        conteo_versiones = self.db.scalar(
            select(func.count())
            .select_from(ProcesoFirmasConvenio)
            .where(
                ProcesoFirmasConvenio.id == proceso.id,
                ProcesoFirmasConvenio.version_convenio_id
                == proceso.version_convenio_id,
            )
        )
        if conteo_versiones != 1:
            raise RevisionNoDisponible("Las firmas no pertenecen a una versión válida")
        proceso.estado = EstadoProcesoFirmasConvenio.EN_CURSO.value
        proceso.iniciado_en = datetime.now(UTC)
        try:
            self.db.commit()
        except SQLAlchemyError:
            self.db.rollback()
            raise
        return self.obtener_proceso_activo(convenio_id)
