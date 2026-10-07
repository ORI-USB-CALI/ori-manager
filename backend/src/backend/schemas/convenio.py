from datetime import date, datetime
from typing import Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    computed_field,
    field_validator,
)

from backend.models.enums import (
    AlcanceConvenio,
    EstadoConvenio,
    EstadoFirmaConvenio,
    EstadoObservacionRevision,
    EstadoProcesoFirmasConvenio,
    EstadoRevisionConvenio,
    EstadoSolicitud,
    ModalidadFirma,
    OrigenObservacionRevision,
    ParteFirmaConvenio,
    ResultadoRevisionConvenio,
    RolFirmanteConvenio,
    TipoRevisionConvenio,
    TipoSolicitante,
)


class ConvenioCamposEditables(BaseModel):
    codigo: str | None = Field(default=None, max_length=40)
    tipo_convenio_id: int | None = None
    objeto: str | None = None
    alcance: AlcanceConvenio | None = None
    unidad_organizacional_id: int | None = None
    implicacion_financiera: str | None = None
    fecha_inicio: date | None = None
    fecha_vencimiento: date | None = None
    fecha_firma: date | None = None
    duracion_meses: int | None = Field(default=None, ge=0)
    porcentaje_avance: int | None = Field(default=None, ge=0, le=100)
    convenio_origen_id: int | None = None
    numero_renovacion: int | None = Field(default=None, ge=0)


class ConvenioCrear(ConvenioCamposEditables):
    model_config = ConfigDict(extra="forbid")
    solicitud_id: int
    objeto: str = Field(min_length=1)


class ConvenioElaboracionActualizar(BaseModel):
    """Campos que HU-12 permite modificar durante Elaboración."""

    model_config = ConfigDict(extra="forbid")

    tipo_convenio_id: int | None = None
    objeto: str | None = None
    alcance: AlcanceConvenio | None = None
    unidad_organizacional_id: int | None = None
    implicacion_financiera: str | None = None
    fecha_inicio: date | None = None
    fecha_vencimiento: date | None = None
    duracion_meses: int | None = Field(default=None, ge=0)


class ConvenioElaboracionGuardar(ConvenioElaboracionActualizar):
    contenido: dict[str, Any]
    expected_version: int = Field(ge=0)


class ConvenioElaboracionFinalizar(ConvenioElaboracionActualizar):
    contenido: dict[str, Any] | None = None
    expected_version: int | None = Field(default=None, ge=0)


class UsuarioResumen(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    nombre_completo: str
    correo: str


class AliadoResumen(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    nombre: str
    identificacion: str
    activo: bool


class ConvenioLeer(ConvenioCamposEditables):
    model_config = ConfigDict(from_attributes=True)

    id: int
    solicitud_id: int
    aliado_id: int | None
    etapa_actual_id: int | None
    plantilla_origen_id: int | None
    version_actual: int
    estado: EstadoConvenio
    creado_por_id: int
    creado_por: UsuarioResumen
    aliado: AliadoResumen | None
    creado_en: datetime
    actualizado_en: datetime


class EtapaResumen(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    orden: int
    codigo: str
    nombre: str


class TipoConvenioResumen(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    codigo: str
    nombre: str
    naturaleza: str | None


class TipoConvenioElaboracionOpcion(TipoConvenioResumen):
    duracion_meses_defecto: int | None


class UnidadOrganizacionalResumen(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    codigo: str
    nombre: str
    tipo: str


class PlantillaConvenioResumen(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    codigo: str
    nombre: str


class VersionConvenioResumen(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    numero: int
    autor: UsuarioResumen
    etapa: EtapaResumen
    contexto: str
    creado_en: datetime
    plantilla: PlantillaConvenioResumen | None


class VersionConvenioLeer(VersionConvenioResumen):
    contenido: dict[str, Any]
    snapshot_metadata: dict[str, Any]


class SolicitudAntecedenteLeer(BaseModel):
    """Solicitud que originó el convenio, como antecedente de solo lectura.

    HU-12 nunca modifica estos datos: la ORI redacta sobre el convenio y la
    solicitud se conserva tal como la radicó el solicitante (CA-04).
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    consecutivo: str
    tipo_solicitante: TipoSolicitante
    estado: EstadoSolicitud
    objeto: str | None
    justificacion: str | None
    actividades_por_parte: str | None
    metas_esperadas: str | None
    implicacion_financiera: str | None
    vigencia_estimada: str | None
    requisitos_renovacion: str | None
    observaciones: str | None
    fecha_radicacion: datetime | None

    solicitante_nombre: str | None
    solicitante_correo: str | None
    solicitante_cargo: str | None
    solicitante_unidad: str | None
    solicitante_programa: str | None
    solicitante_entidad: str | None

    # Contraparte tal como se propuso: sigue visible aunque ya exista aliado formal.
    nombre_aliado_propuesto: str | None
    identificacion_aliado_propuesto: str | None
    tipo_aliado_propuesto: str | None
    correo_aliado_propuesto: str | None
    pais_aliado_propuesto: str | None
    ciudad_aliado_propuesto: str | None

    contacto_contraparte_nombre: str | None
    contacto_contraparte_cargo: str | None
    contacto_contraparte_telefono: str | None
    contacto_contraparte_correo: str | None

    # Supervisores como contexto. Su registro formal corresponde a HU-19.
    supervisor_usb_nombre: str | None
    supervisor_usb_cargo: str | None
    supervisor_usb_telefono: str | None
    supervisor_usb_correo: str | None
    supervisor_contraparte_nombre: str | None
    supervisor_contraparte_cargo: str | None
    supervisor_contraparte_telefono: str | None
    supervisor_contraparte_correo: str | None


class ConvenioElaboracionLeer(ConvenioLeer):
    """Vista de la etapa de Elaboración: el convenio más su antecedente."""

    solicitud: SolicitudAntecedenteLeer
    etapa_actual: EtapaResumen | None
    tipo_convenio: TipoConvenioResumen | None
    unidad_organizacional: UnidadOrganizacionalResumen | None
    plantilla_origen: PlantillaConvenioResumen | None
    contenido: dict[str, Any] | None


class CampoFaltante(BaseModel):
    campo: str
    motivo: str


class ValidacionElaboracionLeer(BaseModel):
    completo: bool
    faltantes: list[CampoFaltante]


class CatalogosElaboracionLeer(BaseModel):
    tipos_convenio: list[TipoConvenioElaboracionOpcion]
    unidades_organizacionales: list[UnidadOrganizacionalResumen]


class ObservacionRevisionLeer(BaseModel):
    """Una observación registrada durante un ciclo de revisión (CA-04, CA-06)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    origen: OrigenObservacionRevision
    descripcion: str
    respuesta: str | None
    estado: EstadoObservacionRevision
    registrada_por: UsuarioResumen | None
    responsable: UsuarioResumen | None
    atendida_por: UsuarioResumen | None
    fecha_atencion: datetime | None
    creado_en: datetime


class VersionRevisionReferencia(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    numero: int


class InvitacionContraparteTrazabilidad(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    generada_por: UsuarioResumen
    correo_destino: str
    correo_cc: str | None
    expira_en: datetime
    enviado_en: datetime | None
    utilizado_en: datetime | None
    revocado_en: datetime | None
    creado_en: datetime


class RespuestaContraparteTrazabilidad(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    nombre_firmante: str
    cargo_firmante: str
    correo_actor: str
    firma_sha256: str | None
    creado_en: datetime

    @computed_field
    @property
    def tiene_firma(self) -> bool:
        return self.firma_sha256 is not None


class RevisionConvenioLeer(BaseModel):
    """Un ciclo de revisión (jurídica, de contraparte o final) con su resultado
    y las observaciones que dejó, para CA-06 y CA-07."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    version_convenio_id: int | None
    version_resultado_id: int | None
    version_convenio: VersionRevisionReferencia | None
    version_resultado: VersionRevisionReferencia | None
    instancia_juridica: int | None
    numero_ronda: int | None
    tipo: TipoRevisionConvenio
    estado: EstadoRevisionConvenio
    resultado: ResultadoRevisionConvenio | None
    responsable: UsuarioResumen | None
    creada_por: UsuarioResumen | None
    resuelta_por: UsuarioResumen | None
    snapshot_datos: dict[str, Any] | None
    creado_en: datetime
    resuelta_en: datetime | None
    observaciones: list[ObservacionRevisionLeer]
    invitaciones_contraparte: list[InvitacionContraparteTrazabilidad]
    respuesta_contraparte: RespuestaContraparteTrazabilidad | None


class RevisionJuridicaPendienteLeer(BaseModel):
    revision_id: int
    convenio_id: int
    codigo_convenio: str | None
    solicitud_consecutivo: str
    objeto: str | None
    tipo_convenio: TipoConvenioResumen | None
    responsable: UsuarioResumen
    fecha_recepcion: datetime
    instancia_juridica: int | None
    numero_ronda: int | None
    version_numero: int | None


class RevisionContrapartePendienteLeer(BaseModel):
    revision_id: int
    convenio_id: int
    codigo_convenio: str | None
    objeto: str | None
    version_numero: int
    fecha_envio: datetime
    enviada_por: UsuarioResumen


class RevisionContraparteDetalleLeer(BaseModel):
    convenio_id: int
    codigo_convenio: str | None
    objeto: str | None
    revision: RevisionConvenioLeer
    version_recibida: VersionConvenioLeer
    enviada_por: UsuarioResumen
    fecha_envio: datetime


class EtapaTableroLeer(EtapaResumen):
    area_responsable: str | None


class ConvenioTableroLeer(BaseModel):
    id: int
    codigo: str | None
    estado: EstadoConvenio
    etapa_actual: EtapaTableroLeer | None
    aliado: AliadoResumen | None
    aliado_propuesto: str | None
    responsable: UsuarioResumen | None
    puede_ver_detalle: bool


class TableroConveniosLeer(BaseModel):
    etapas: list[EtapaTableroLeer]
    convenios: list[ConvenioTableroLeer]


class AlertaVencimientoLeer(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    convenio_id: int
    codigo: str | None
    objeto: str | None
    fecha_vencimiento: date
    dias_restantes: int
    rango_vencimiento: Literal["0_30", "31_60", "61_90", "91_120"]


class HistorialEtapaLeer(BaseModel):
    """Un cambio de etapa del convenio, para la trazabilidad de CA-07."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    etapa_origen: EtapaResumen | None
    etapa_destino: EtapaResumen
    usuario: UsuarioResumen
    responsable: UsuarioResumen | None
    observacion: str | None
    fecha_cambio: datetime


class HistorialConvenioLeer(BaseModel):
    """Historial completo de un convenio: sus rondas de revisión y sus cambios
    de etapa, ordenados cronológicamente (CA-06, CA-07)."""

    revisiones: list[RevisionConvenioLeer]
    cambios_etapa: list[HistorialEtapaLeer]


class DocumentoConvenioLeer(BaseModel):
    """Un documento cargado al convenio, para CA-01 ('documentos asociados')."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    tipo: str
    nombre_archivo: str
    tipo_mime: str
    tamano_bytes: int
    creado_en: datetime


class VersionRevisionActual(VersionRevisionReferencia):
    contenido: dict[str, Any]


class ConvenioParaRevisionLeer(BaseModel):
    """Convenio preparado para la pantalla principal de revisión jurídica:
    su información, documentos y la ronda de revisión pendiente que el
    Revisor ORI debe resolver (CA-01, CA-02 de HU-13)."""

    convenio: ConvenioElaboracionLeer
    documentos: list[DocumentoConvenioLeer]
    revision_pendiente: RevisionConvenioLeer

    version_recibida: VersionRevisionReferencia
    version_actual: VersionRevisionActual
    version_resultado: VersionRevisionReferencia | None = None


class RevisionContenidoGuardar(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contenido: dict[str, Any]
    expected_version: int = Field(ge=0)


class AprobarRevision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_version: int = Field(ge=0)


class EnviarRevisionContraparte(AprobarRevision):
    pass


class CrearObservacionRevision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    descripcion: str = Field(min_length=1)

    @field_validator("descripcion")
    @classmethod
    def validar_descripcion(cls, valor: str) -> str:
        normalizada = valor.strip()
        if not normalizada:
            raise ValueError("La observación debe tener contenido")
        return normalizada


class DevolverRevision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_version: int = Field(ge=0)
    observaciones: list[str] = Field(default_factory=list)

    @field_validator("observaciones")
    @classmethod
    def validar_observaciones(cls, valores: list[str]) -> list[str]:
        if any(not valor.strip() for valor in valores):
            raise ValueError("Cada observación debe tener contenido")
        return [valor.strip() for valor in valores]


class AtenderObservacion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    respuesta: str = Field(min_length=1)

    @field_validator("respuesta")
    @classmethod
    def validar_respuesta(cls, valor: str) -> str:
        normalizada = valor.strip()
        if not normalizada:
            raise ValueError("La respuesta debe tener contenido")
        return normalizada


class InvitacionFirmaConvenioLeer(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    firma_convenio_id: int
    generada_por_id: int
    expira_en: datetime
    enviado_en: datetime | None
    utilizado_en: datetime | None
    revocado_en: datetime | None
    creado_en: datetime

    @computed_field
    @property
    def estado(self) -> str:
        if self.utilizado_en is not None:
            return "UTILIZADA"
        if self.revocado_en is not None:
            return "REVOCADA"
        if self.expira_en <= datetime.now(self.expira_en.tzinfo):
            return "EXPIRADA"
        if self.enviado_en is None:
            return "ENTREGA_FALLIDA"
        return "PENDIENTE"


class FirmaConvenioLeer(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    proceso_firmas_id: int
    orden: int
    rol_firmante: RolFirmanteConvenio
    parte: ParteFirmaConvenio
    usuario_id: int | None
    nombre_firmante: str | None
    cargo_firmante: str | None
    correo_firmante: str | None
    modalidad: ModalidadFirma | None
    estado: EstadoFirmaConvenio
    fecha_firma: datetime | None
    documento_id: int | None
    documento: DocumentoConvenioLeer | None
    creado_en: datetime
    invitaciones: list[InvitacionFirmaConvenioLeer] = Field(default_factory=list)

    @computed_field
    @property
    def configurada(self) -> bool:
        identidad = bool(self.nombre_firmante and self.cargo_firmante)
        if self.modalidad == ModalidadFirma.ELECTRONICA:
            return identidad and bool(self.correo_firmante)
        return identidad and self.modalidad == ModalidadFirma.FISICA


class ProcesoFirmasConvenioLeer(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    convenio_id: int
    version_convenio_id: int
    version_numero: int
    revision_final_id: int
    creado_por_id: int
    estado: EstadoProcesoFirmasConvenio
    creado_en: datetime
    iniciado_en: datetime | None
    completado_en: datetime | None
    cancelado_en: datetime | None
    firmas: list[FirmaConvenioLeer]


class DocumentoAprobadoFirmaLeer(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    convenio_id: int
    codigo_convenio: str | None
    proceso_firmas_id: int
    version_convenio_id: int
    version_numero: int
    contenido: dict[str, Any]
    creado_en: datetime


class SolicitarCambioSustancialFirmas(BaseModel):
    model_config = ConfigDict(extra="forbid")

    observacion: str = Field(min_length=1, max_length=4000)

    @field_validator("observacion", mode="before")
    @classmethod
    def normalizar_observacion(cls, valor: object) -> object:
        return valor.strip() if isinstance(valor, str) else valor


class RevisionFinalLeer(BaseModel):
    convenio: ConvenioElaboracionLeer
    documentos: list[DocumentoConvenioLeer]
    revision_pendiente: RevisionConvenioLeer
    version_aprobada_contraparte: VersionConvenioLeer
    revisiones_juridicas: list[RevisionConvenioLeer]
    revision_contraparte: RevisionConvenioLeer
    observaciones_pendientes: list[ObservacionRevisionLeer]
    revision_final_aprobada: bool
    proceso_firmas_abierto: bool
    proceso_firmas: ProcesoFirmasConvenioLeer | None


class ConfigurarFirmaConvenio(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nombre: str = Field(min_length=1, max_length=160)
    cargo: str = Field(min_length=1, max_length=160)
    correo: EmailStr | None = None
    modalidad: ModalidadFirma

    @field_validator("nombre", "cargo")
    @classmethod
    def normalizar_texto(cls, valor: str) -> str:
        normalizado = valor.strip()
        if not normalizado:
            raise ValueError("El campo debe tener contenido")
        return normalizado
