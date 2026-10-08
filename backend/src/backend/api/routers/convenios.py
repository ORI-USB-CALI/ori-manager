from datetime import date
from typing import Annotated, NoReturn
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.api.deps import requiere
from backend.core.config import settings
from backend.core.permisos import Permiso
from backend.db.session import get_db
from backend.models.actividad_utilizacion import ActividadUtilizacion
from backend.models.convenio import Convenio
from backend.models.enums import EstadoSeguimientoRenovacion
from backend.models.tipo_convenio import TipoConvenio
from backend.models.unidad_organizacional import UnidadOrganizacional
from backend.models.usuario import Usuario
from backend.schemas.actividad_utilizacion import (
    ActividadUtilizacionCrear,
    ActividadUtilizacionLeer,
)
from backend.schemas.convenio import (
    AlertaVencimientoLeer,
    AprobarRevision,
    AtenderObservacion,
    CatalogosElaboracionLeer,
    ConfigurarFirmaConvenio,
    ConvenioCrear,
    ConvenioElaboracionActualizar,
    ConvenioElaboracionFinalizar,
    ConvenioElaboracionGuardar,
    ConvenioElaboracionLeer,
    ConvenioLeer,
    ConvenioParaRevisionLeer,
    ConvenioTableroLeer,
    CrearObservacionRevision,
    DevolverRevision,
    DocumentoAprobadoFirmaLeer,
    DocumentoConvenioLeer,
    EnviarRevisionContraparte,
    FirmaConvenioLeer,
    HistorialConvenioLeer,
    HistorialEtapaLeer,
    InvitacionFirmaConvenioLeer,
    ObservacionRevisionLeer,
    ProcesoFirmasConvenioLeer,
    RevisionContenidoGuardar,
    RevisionContraparteDetalleLeer,
    RevisionContrapartePendienteLeer,
    RevisionConvenioLeer,
    RevisionFinalLeer,
    RevisionJuridicaPendienteLeer,
    SolicitarCambioSustancialFirmas,
    TableroConveniosLeer,
    ValidacionElaboracionLeer,
    VersionConvenioLeer,
    VersionConvenioResumen,
    VersionRevisionActual,
    VersionRevisionReferencia,
)
from backend.schemas.renovacion import (
    DecisionNoRenovacionLeer,
    RenovacionIniciadaLeer,
    SeguimientoRenovacionLeer,
)
from backend.services.actividades_utilizacion import ServicioActividadesUtilizacion
from backend.services.alertas_vencimiento import ServicioAlertasVencimiento
from backend.services.convenios import (
    ConflictoVersionConvenio,
    ConvenioDuplicado,
    ConvenioNoEditable,
    ConvenioNoEncontrado,
    ElaboracionIncompleta,
    ErrorConvenio,
    ObservacionNoDisponible,
    ReferenciaConvenioInvalida,
    RevisionNoDisponible,
    ServicioConvenios,
    SolicitudNoAprobada,
)
from backend.services.correo import (
    EnviadorCorreo,
    ErrorEnvioCorreo,
    get_enviador_correo,
)
from backend.services.documentos import (
    TAMANO_MAXIMO_DOCUMENTO,
    AlmacenDocumentos,
    ErrorAlmacenDocumentos,
    get_almacen_documentos,
)
from backend.services.firma_electronica import (
    EntregaInvitacionesFirmaError,
    ServicioFirmaElectronica,
)
from backend.services.firmas import ServicioFirmas
from backend.services.renovaciones import (
    ServicioRenovaciones,
    listar_seguimiento_renovaciones,
)

router = APIRouter(prefix="/convenios", tags=["Convenios"])
DatabaseSession = Annotated[Session, Depends(get_db)]
Storage = Annotated[AlmacenDocumentos, Depends(get_almacen_documentos)]
Correo = Annotated[EnviadorCorreo, Depends(get_enviador_correo)]
PuedeVer = Annotated[Usuario, requiere(Permiso.CONVENIOS_VER)]
PuedeVerAlertasVencimiento = Annotated[
    Usuario, requiere(Permiso.CONVENIOS_VER_ALERTAS_VENCIMIENTO)
]
PuedeGestionarRenovaciones = Annotated[
    Usuario, requiere(Permiso.CONVENIOS_GESTIONAR_RENOVACIONES)
]
PuedeCrear = Annotated[Usuario, requiere(Permiso.CONVENIOS_CREAR)]
PuedeEditar = Annotated[Usuario, requiere(Permiso.CONVENIOS_EDITAR)]
PuedeRevisar = Annotated[Usuario, requiere(Permiso.CONVENIOS_REVISAR)]
PuedeGestionarContraparte = Annotated[
    Usuario, requiere(Permiso.CONVENIOS_GESTIONAR_REVISION_CONTRAPARTE)
]
PuedeRevisarContrapartePropia = Annotated[
    Usuario, requiere(Permiso.CONVENIOS_REVISAR_CONTRAPARTE_PROPIA)
]
PuedeGestionarFirmas = Annotated[
    Usuario, requiere(Permiso.CONVENIOS_GESTIONAR_FIRMAS)
]


def _lanzar_http(exc: ErrorConvenio) -> NoReturn:
    if isinstance(exc, ConvenioNoEncontrado):
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    if isinstance(exc, ConflictoVersionConvenio):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail={
                "message": str(exc),
                "expected_version": exc.esperada,
                "current_version": exc.actual,
            },
        ) from exc
    if isinstance(
        exc,
        (
            ConvenioDuplicado,
            SolicitudNoAprobada,
            ConvenioNoEditable,
            RevisionNoDisponible,
            ObservacionNoDisponible,
        ),
    ):
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    if isinstance(exc, ElaboracionIncompleta):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={
                "message": str(exc),
                "faltantes": [campo.model_dump() for campo in exc.faltantes],
            },
        ) from exc
    if isinstance(exc, ReferenciaConvenioInvalida):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    raise exc


@router.post("", response_model=ConvenioLeer, status_code=status.HTTP_201_CREATED)
def crear_convenio(
    datos: ConvenioCrear, db: DatabaseSession, usuario: PuedeCrear
) -> Convenio:
    try:
        return ServicioConvenios(db).crear(datos, usuario)
    except ErrorConvenio as exc:
        _lanzar_http(exc)


@router.get("/catalogos/elaboracion", response_model=CatalogosElaboracionLeer)
def obtener_catalogos_elaboracion(
    db: DatabaseSession, _: PuedeVer
) -> CatalogosElaboracionLeer:
    tipos = db.scalars(
        select(TipoConvenio)
        .where(TipoConvenio.activo.is_(True))
        .order_by(TipoConvenio.nombre)
    ).all()
    unidades = db.scalars(
        select(UnidadOrganizacional)
        .where(UnidadOrganizacional.activa.is_(True))
        .order_by(UnidadOrganizacional.nombre)
    ).all()
    return CatalogosElaboracionLeer(
        tipos_convenio=tipos,
        unidades_organizacionales=unidades,
    )


@router.get(
    "/revisiones-juridicas/pendientes",
    response_model=list[RevisionJuridicaPendienteLeer],
)
def listar_revisiones_juridicas_pendientes(
    db: DatabaseSession, usuario: PuedeRevisar
) -> list[RevisionJuridicaPendienteLeer]:
    revisiones = ServicioConvenios(db).listar_revisiones_juridicas_pendientes(usuario)
    return [
        RevisionJuridicaPendienteLeer(
            revision_id=revision.id,
            convenio_id=revision.convenio.id,
            codigo_convenio=revision.convenio.codigo,
            solicitud_consecutivo=revision.convenio.solicitud.consecutivo,
            objeto=revision.convenio.objeto,
            tipo_convenio=revision.convenio.tipo_convenio,
            responsable=revision.convenio.creado_por,
            fecha_recepcion=revision.creado_en,
            instancia_juridica=revision.instancia_juridica,
            numero_ronda=revision.numero_ronda,
            version_numero=(
                revision.version_convenio.numero
                if revision.version_convenio is not None
                else None
            ),
        )
        for revision in revisiones
    ]


@router.get(
    "/revisiones-contraparte/pendientes",
    response_model=list[RevisionContrapartePendienteLeer],
)
def listar_revisiones_contraparte_pendientes(
    db: DatabaseSession, usuario: PuedeRevisarContrapartePropia
) -> list[RevisionContrapartePendienteLeer]:
    revisiones = ServicioConvenios(db).listar_revisiones_contraparte_pendientes(
        usuario
    )
    return [
        RevisionContrapartePendienteLeer(
            revision_id=revision.id,
            convenio_id=revision.convenio_id,
            codigo_convenio=revision.convenio.codigo,
            objeto=revision.convenio.objeto,
            version_numero=revision.version_convenio.numero,
            fecha_envio=revision.creado_en,
            enviada_por=revision.creada_por,
        )
        for revision in revisiones
    ]


@router.get(
    "/revisiones-contraparte/{revision_id}",
    response_model=RevisionContraparteDetalleLeer,
)
def obtener_revision_contraparte_propia(
    revision_id: int,
    db: DatabaseSession,
    usuario: PuedeRevisarContrapartePropia,
) -> RevisionContraparteDetalleLeer:
    try:
        revision = ServicioConvenios(db).obtener_revision_contraparte_propia(
            revision_id, usuario
        )
    except ErrorConvenio as exc:
        _lanzar_http(exc)
    return RevisionContraparteDetalleLeer(
        convenio_id=revision.convenio_id,
        codigo_convenio=revision.convenio.codigo,
        objeto=revision.convenio.objeto,
        revision=RevisionConvenioLeer.model_validate(revision),
        version_recibida=VersionConvenioLeer.model_validate(
            revision.version_convenio
        ),
        enviada_por=revision.creada_por,
        fecha_envio=revision.creado_en,
    )


@router.post(
    "/revisiones-contraparte/{revision_id}/aprobar",
    response_model=RevisionConvenioLeer,
)
def aprobar_revision_contraparte_propia(
    revision_id: int,
    datos: AprobarRevision,
    db: DatabaseSession,
    usuario: PuedeRevisarContrapartePropia,
) -> RevisionConvenioLeer:
    try:
        servicio = ServicioConvenios(db)
        servicio.aprobar_revision_contraparte(
            revision_id, datos.expected_version, usuario
        )
        return RevisionConvenioLeer.model_validate(
            servicio.obtener_revision_contraparte_propia(revision_id, usuario)
        )
    except ErrorConvenio as exc:
        _lanzar_http(exc)


@router.post(
    "/revisiones-contraparte/{revision_id}/devolver",
    response_model=RevisionConvenioLeer,
)
def devolver_revision_contraparte_propia(
    revision_id: int,
    datos: DevolverRevision,
    db: DatabaseSession,
    usuario: PuedeRevisarContrapartePropia,
) -> RevisionConvenioLeer:
    try:
        servicio = ServicioConvenios(db)
        servicio.devolver_revision_contraparte(
            revision_id,
            datos.expected_version,
            datos.observaciones,
            usuario,
        )
        return RevisionConvenioLeer.model_validate(
            servicio.obtener_revision_contraparte_propia(revision_id, usuario)
        )
    except ErrorConvenio as exc:
        _lanzar_http(exc)


@router.get("/tablero", response_model=TableroConveniosLeer)
def obtener_tablero(db: DatabaseSession, usuario: PuedeVer) -> TableroConveniosLeer:
    etapas, convenios = ServicioConvenios(db).listar_tablero(usuario)
    return TableroConveniosLeer(
        etapas=etapas,
        convenios=[
            ConvenioTableroLeer(
                id=convenio.id,
                codigo=convenio.codigo,
                estado=convenio.estado,
                etapa_actual=convenio.etapa_actual,
                aliado=convenio.aliado,
                aliado_propuesto=convenio.solicitud.nombre_aliado_propuesto,
                responsable=responsable,
                puede_ver_detalle=puede_ver_detalle,
            )
            for convenio, responsable, puede_ver_detalle in convenios
        ],
    )


@router.get("/alertas-vencimiento", response_model=list[AlertaVencimientoLeer])
def listar_alertas_vencimiento(
    db: DatabaseSession, _: PuedeVerAlertasVencimiento
) -> list[AlertaVencimientoLeer]:
    alertas = ServicioAlertasVencimiento(db).listar_proximos_vencimientos()
    return [AlertaVencimientoLeer.model_validate(alerta) for alerta in alertas]


@router.get("/renovaciones", response_model=list[SeguimientoRenovacionLeer])
def listar_renovaciones(
    db: DatabaseSession,
    _: PuedeGestionarRenovaciones,
    estado: EstadoSeguimientoRenovacion | None = None,
) -> list[SeguimientoRenovacionLeer]:
    seguimientos = listar_seguimiento_renovaciones(db, estado=estado)
    return [
        SeguimientoRenovacionLeer.model_validate(seguimiento)
        for seguimiento in seguimientos
    ]


@router.get("/{convenio_id}", response_model=ConvenioLeer)
def obtener_convenio(
    convenio_id: int, db: DatabaseSession, usuario: PuedeVer
) -> Convenio:
    try:
        return ServicioConvenios(db).obtener_en_alcance_operativo(
            convenio_id, usuario
        )
    except ErrorConvenio as exc:
        _lanzar_http(exc)


@router.get(
    "/{convenio_id}/actividades-utilizacion",
    response_model=list[ActividadUtilizacionLeer],
)
def listar_actividades_utilizacion(
    convenio_id: int, db: DatabaseSession, usuario: PuedeVer
) -> list[ActividadUtilizacion]:
    try:
        return ServicioActividadesUtilizacion(db).listar(convenio_id, usuario)
    except ErrorConvenio as exc:
        _lanzar_http(exc)


@router.post(
    "/{convenio_id}/actividades-utilizacion",
    response_model=ActividadUtilizacionLeer,
    status_code=status.HTTP_201_CREATED,
)
def registrar_actividad_utilizacion(
    convenio_id: int,
    payload: ActividadUtilizacionCrear,
    db: DatabaseSession,
    usuario: PuedeEditar,
) -> ActividadUtilizacion:
    try:
        return ServicioActividadesUtilizacion(db).registrar(
            convenio_id, payload, usuario
        )
    except ErrorConvenio as exc:
        _lanzar_http(exc)


@router.post(
    "/{convenio_id}/renovaciones",
    response_model=RenovacionIniciadaLeer,
    status_code=status.HTTP_201_CREATED,
)
def iniciar_renovacion(
    convenio_id: int, db: DatabaseSession, usuario: PuedeGestionarRenovaciones
) -> RenovacionIniciadaLeer:
    try:
        hijo = ServicioRenovaciones(db).iniciar_renovacion(convenio_id, usuario)
    except ErrorConvenio as exc:
        _lanzar_http(exc)
    return RenovacionIniciadaLeer(
        convenio_origen_id=hijo.convenio_origen_id,
        convenio_renovacion_id=hijo.id,
        codigo=hijo.codigo,
        numero_renovacion=hijo.numero_renovacion,
        estado=hijo.estado,
        etapa=hijo.etapa_actual.codigo,
    )


@router.post(
    "/{convenio_id}/no-renovar",
    response_model=DecisionNoRenovacionLeer,
    status_code=status.HTTP_201_CREATED,
)
def registrar_no_renovacion(
    convenio_id: int, db: DatabaseSession, usuario: PuedeGestionarRenovaciones
) -> DecisionNoRenovacionLeer:
    try:
        decision = ServicioRenovaciones(db).registrar_no_renovacion(convenio_id, usuario)
    except ErrorConvenio as exc:
        _lanzar_http(exc)
    return DecisionNoRenovacionLeer.model_validate(decision)


@router.get("/{convenio_id}/elaboracion", response_model=ConvenioElaboracionLeer)
def obtener_elaboracion(
    convenio_id: int, db: DatabaseSession, usuario: PuedeVer
) -> Convenio:
    try:
        servicio = ServicioConvenios(db)
        servicio.verificar_alcance_operativo(convenio_id, usuario)
        return servicio.obtener_para_elaboracion(convenio_id)
    except ErrorConvenio as exc:
        _lanzar_http(exc)


@router.get(
    "/{convenio_id}/elaboracion/validacion", response_model=ValidacionElaboracionLeer
)
def validar_elaboracion(
    convenio_id: int, db: DatabaseSession, usuario: PuedeVer
) -> ValidacionElaboracionLeer:
    try:
        servicio = ServicioConvenios(db)
        servicio.verificar_alcance_operativo(convenio_id, usuario)
        faltantes = servicio.validar_elaboracion(convenio_id)
    except ErrorConvenio as exc:
        _lanzar_http(exc)
    return ValidacionElaboracionLeer(completo=not faltantes, faltantes=faltantes)


@router.patch(
    "/{convenio_id}/elaboracion", response_model=ConvenioElaboracionLeer
)
def guardar_elaboracion(
    convenio_id: int,
    datos: ConvenioElaboracionGuardar,
    db: DatabaseSession,
    usuario: PuedeEditar,
) -> Convenio:
    try:
        return ServicioConvenios(db).guardar_elaboracion(
            convenio_id, datos, usuario
        )
    except ErrorConvenio as exc:
        _lanzar_http(exc)


@router.get(
    "/{convenio_id}/versiones", response_model=list[VersionConvenioResumen]
)
def listar_versiones(
    convenio_id: int, db: DatabaseSession, usuario: PuedeVer
) -> list[VersionConvenioResumen]:
    try:
        servicio = ServicioConvenios(db)
        servicio.verificar_alcance_operativo(convenio_id, usuario)
        return servicio.listar_versiones(convenio_id)
    except ErrorConvenio as exc:
        _lanzar_http(exc)


@router.get(
    "/{convenio_id}/versiones/{numero}", response_model=VersionConvenioLeer
)
def obtener_version(
    convenio_id: int, numero: int, db: DatabaseSession, usuario: PuedeVer
) -> VersionConvenioLeer:
    try:
        servicio = ServicioConvenios(db)
        servicio.verificar_alcance_operativo(convenio_id, usuario)
        return servicio.obtener_version(convenio_id, numero)
    except ErrorConvenio as exc:
        _lanzar_http(exc)


@router.post("/{convenio_id}/elaboracion/finalizar", response_model=ConvenioLeer)
def finalizar_elaboracion(
    convenio_id: int,
    db: DatabaseSession,
    usuario: PuedeEditar,
    datos: ConvenioElaboracionFinalizar | None = None,
) -> Convenio:
    try:
        return ServicioConvenios(db).finalizar_elaboracion(
            convenio_id, usuario, datos
        )
    except ErrorConvenio as exc:
        _lanzar_http(exc)


@router.patch("/{convenio_id}", response_model=ConvenioLeer)
def actualizar_convenio(
    convenio_id: int,
    datos: ConvenioElaboracionActualizar,
    db: DatabaseSession,
    usuario: PuedeEditar,
) -> Convenio:
    try:
        return ServicioConvenios(db).actualizar(convenio_id, datos, usuario)
    except ErrorConvenio as exc:
        _lanzar_http(exc)


@router.get("/{convenio_id}/revisiones", response_model=HistorialConvenioLeer)
def obtener_historial_convenio(
    convenio_id: int, db: DatabaseSession, usuario: PuedeVer
) -> HistorialConvenioLeer:
    """CA-06/CA-07 de HU-13: historial de rondas de revisión y cambios de
    etapa del convenio, ordenados cronológicamente.

    Se ordena por `id` (autoincremental), no por el timestamp: dentro de una
    misma transacción, `now()` en Postgres devuelve siempre el mismo valor
    para todas las filas insertadas, así que `creado_en`/`fecha_cambio`
    pueden empatar entre sí y no garantizan el orden real de inserción.
    """
    try:
        servicio = ServicioConvenios(db)
        servicio.verificar_alcance_operativo(convenio_id, usuario)
        convenio = servicio.obtener_historial(convenio_id)
    except ErrorConvenio as exc:
        _lanzar_http(exc)
    revisiones = sorted(convenio.revisiones, key=lambda revision: revision.id)
    cambios_etapa = sorted(convenio.historial_etapas, key=lambda cambio: cambio.id)
    return HistorialConvenioLeer(
        revisiones=[RevisionConvenioLeer.model_validate(r) for r in revisiones],
        cambios_etapa=[HistorialEtapaLeer.model_validate(h) for h in cambios_etapa],
    )


@router.get("/{convenio_id}/revision", response_model=ConvenioParaRevisionLeer)
def obtener_revision_pendiente(
    convenio_id: int, db: DatabaseSession, usuario: PuedeRevisar
) -> ConvenioParaRevisionLeer:
    """CA-01/CA-02 de HU-13: pantalla principal de revisión jurídica — el
    convenio preparado para revisión, sus documentos y la ronda de revisión
    pendiente que el Revisor ORI debe resolver."""
    try:
        servicio = ServicioConvenios(db)
        servicio.verificar_alcance_operativo(convenio_id, usuario)
        (
            convenio,
            revision_pendiente,
            documentos,
            version_recibida,
            version_actual,
        ) = servicio.obtener_para_revision(convenio_id)
    except ErrorConvenio as exc:
        _lanzar_http(exc)
    return ConvenioParaRevisionLeer(
        convenio=ConvenioElaboracionLeer.model_validate(convenio),
        documentos=[
            DocumentoConvenioLeer.model_validate(documento)
            for documento in documentos
        ],
        revision_pendiente=RevisionConvenioLeer.model_validate(revision_pendiente),
        version_recibida=VersionRevisionReferencia.model_validate(version_recibida),
        version_actual=VersionRevisionActual.model_validate(version_actual),
        version_resultado=(
            VersionRevisionReferencia.model_validate(
                revision_pendiente.version_resultado
            )
            if revision_pendiente.version_resultado is not None
            else None
        ),
    )


@router.patch(
    "/{convenio_id}/revisiones/{revision_id}/contenido",
    response_model=VersionRevisionActual,
)
def guardar_contenido_revision(
    convenio_id: int,
    revision_id: int,
    datos: RevisionContenidoGuardar,
    db: DatabaseSession,
    usuario: PuedeRevisar,
) -> VersionRevisionActual:
    try:
        version = ServicioConvenios(db).guardar_contenido_revision(
            convenio_id, revision_id, datos, usuario
        )
        return VersionRevisionActual.model_validate(version)
    except ErrorConvenio as exc:
        _lanzar_http(exc)


@router.post(
    "/{convenio_id}/revisiones/{revision_id}/observaciones",
    response_model=ObservacionRevisionLeer,
    status_code=status.HTTP_201_CREATED,
)
def registrar_observacion_revision(
    convenio_id: int,
    revision_id: int,
    datos: CrearObservacionRevision,
    db: DatabaseSession,
    usuario: PuedeRevisar,
) -> ObservacionRevisionLeer:
    try:
        observacion = ServicioConvenios(db).registrar_observacion_revision(
            convenio_id, revision_id, datos.descripcion, usuario
        )
        convenio = ServicioConvenios(db).obtener_historial(convenio_id)
        cargada = next(
            item
            for revision in convenio.revisiones
            for item in revision.observaciones
            if item.id == observacion.id
        )
        return ObservacionRevisionLeer.model_validate(cargada)
    except ErrorConvenio as exc:
        _lanzar_http(exc)


@router.get("/{convenio_id}/documentos/{documento_id}/contenido")
def obtener_contenido_documento(
    convenio_id: int,
    documento_id: int,
    db: DatabaseSession,
    almacen: Storage,
    usuario: PuedeVer,
) -> Response:
    try:
        servicio = ServicioConvenios(db, almacen)
        servicio.verificar_alcance_operativo(convenio_id, usuario)
        documento, contenido = servicio.obtener_contenido_documento(
            convenio_id, documento_id
        )
    except ErrorConvenio as exc:
        _lanzar_http(exc)
    except ErrorAlmacenDocumentos as exc:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            "No fue posible recuperar el documento almacenado",
        ) from exc
    nombre = quote(documento.nombre_archivo, safe="")
    return Response(
        content=contenido,
        media_type=documento.tipo_mime,
        headers={"Content-Disposition": f"inline; filename*=UTF-8''{nombre}"},
    )


@router.patch(
    "/{convenio_id}/observaciones/{observacion_id}/atender",
    response_model=ObservacionRevisionLeer,
)
def atender_observacion(
    convenio_id: int,
    observacion_id: int,
    datos: AtenderObservacion,
    db: DatabaseSession,
    usuario: PuedeEditar,
) -> ObservacionRevisionLeer:
    try:
        observacion = ServicioConvenios(db).atender_observacion(
            convenio_id, observacion_id, datos.respuesta, usuario
        )
        convenio = ServicioConvenios(db).obtener_historial(convenio_id)
        cargada = next(
            observacion_historial
            for revision in convenio.revisiones
            for observacion_historial in revision.observaciones
            if observacion_historial.id == observacion.id
        )
        return ObservacionRevisionLeer.model_validate(cargada)
    except ErrorConvenio as exc:
        _lanzar_http(exc)


@router.post(
    "/{convenio_id}/revisiones/{revision_id}/aprobar",
    response_model=RevisionConvenioLeer,
)
def aprobar_revision(
    convenio_id: int,
    revision_id: int,
    datos: AprobarRevision,
    db: DatabaseSession,
    usuario: PuedeRevisar,
) -> RevisionConvenioLeer:
    try:
        ServicioConvenios(db).aprobar(
            convenio_id, revision_id, datos.expected_version, usuario
        )
        convenio = ServicioConvenios(db).obtener_historial(convenio_id)
        return RevisionConvenioLeer.model_validate(
            next(r for r in convenio.revisiones if r.id == revision_id)
        )
    except ErrorConvenio as exc:
        _lanzar_http(exc)


@router.post(
    "/{convenio_id}/revisiones/{revision_id}/devolver",
    response_model=RevisionConvenioLeer,
)
def devolver_revision(
    convenio_id: int,
    revision_id: int,
    datos: DevolverRevision,
    db: DatabaseSession,
    usuario: PuedeRevisar,
) -> RevisionConvenioLeer:
    try:
        ServicioConvenios(db).devolver(
            convenio_id,
            revision_id,
            datos.observaciones,
            datos.expected_version,
            usuario,
        )
        convenio = ServicioConvenios(db).obtener_historial(convenio_id)
        return RevisionConvenioLeer.model_validate(
            next(r for r in convenio.revisiones if r.id == revision_id)
        )
    except ErrorConvenio as exc:
        _lanzar_http(exc)


@router.post(
    "/{convenio_id}/revision-contraparte/enviar",
    response_model=RevisionConvenioLeer,
    status_code=status.HTTP_201_CREATED,
)
def enviar_revision_contraparte(
    convenio_id: int,
    datos: EnviarRevisionContraparte,
    db: DatabaseSession,
    usuario: PuedeGestionarContraparte,
) -> RevisionConvenioLeer:
    try:
        revision = ServicioConvenios(db).enviar_a_contraparte(
            convenio_id, datos.expected_version, usuario
        )
        convenio = ServicioConvenios(db).obtener_historial(convenio_id)
        return RevisionConvenioLeer.model_validate(
            next(item for item in convenio.revisiones if item.id == revision.id)
        )
    except ErrorConvenio as exc:
        _lanzar_http(exc)


@router.get("/{convenio_id}/revision-final", response_model=RevisionFinalLeer)
def obtener_revision_final(
    convenio_id: int, db: DatabaseSession, _: PuedeGestionarFirmas
) -> RevisionFinalLeer:
    try:
        contexto = ServicioFirmas(db).obtener_revision_final(convenio_id)
        return RevisionFinalLeer(
            convenio=ConvenioElaboracionLeer.model_validate(contexto.convenio),
            documentos=[
                DocumentoConvenioLeer.model_validate(documento)
                for documento in contexto.documentos
            ],
            revision_pendiente=RevisionConvenioLeer.model_validate(
                contexto.revision_final
            ),
            version_aprobada_contraparte=VersionConvenioLeer.model_validate(
                contexto.version
            ),
            revisiones_juridicas=[
                RevisionConvenioLeer.model_validate(revision)
                for revision in contexto.revisiones_juridicas
            ],
            revision_contraparte=RevisionConvenioLeer.model_validate(
                contexto.revision_contraparte
            ),
            observaciones_pendientes=[
                ObservacionRevisionLeer.model_validate(observacion)
                for observacion in contexto.observaciones_pendientes
            ],
            revision_final_aprobada=(
                contexto.revision_final.resultado == "APROBADA"
            ),
            proceso_firmas_abierto=contexto.proceso_activo is not None,
            proceso_firmas=(
                ProcesoFirmasConvenioLeer.model_validate(contexto.proceso_activo)
                if contexto.proceso_activo is not None
                else None
            ),
        )
    except ErrorConvenio as exc:
        _lanzar_http(exc)


@router.post(
    "/{convenio_id}/revision-final/aprobar",
    response_model=ProcesoFirmasConvenioLeer,
    status_code=status.HTTP_201_CREATED,
)
def aprobar_revision_final(
    convenio_id: int,
    datos: AprobarRevision,
    db: DatabaseSession,
    usuario: PuedeGestionarFirmas,
) -> ProcesoFirmasConvenioLeer:
    try:
        proceso = ServicioFirmas(db).aprobar_revision_final(
            convenio_id, datos.expected_version, usuario
        )
        return ProcesoFirmasConvenioLeer.model_validate(proceso)
    except ErrorConvenio as exc:
        _lanzar_http(exc)


@router.post(
    "/{convenio_id}/revision-final/devolver",
    response_model=RevisionConvenioLeer,
)
def devolver_revision_final(
    convenio_id: int,
    datos: DevolverRevision,
    db: DatabaseSession,
    usuario: PuedeGestionarFirmas,
) -> RevisionConvenioLeer:
    try:
        revision = ServicioFirmas(db).devolver_revision_final(
            convenio_id, datos.observaciones, datos.expected_version, usuario
        )
        convenio = ServicioConvenios(db).obtener_historial(convenio_id)
        return RevisionConvenioLeer.model_validate(
            next(item for item in convenio.revisiones if item.id == revision.id)
        )
    except ErrorConvenio as exc:
        _lanzar_http(exc)


@router.get(
    "/{convenio_id}/firmas/documento-aprobado",
    response_model=DocumentoAprobadoFirmaLeer,
)
def obtener_documento_aprobado_firma(
    convenio_id: int, db: DatabaseSession, _: PuedeGestionarFirmas
) -> DocumentoAprobadoFirmaLeer:
    try:
        documento = ServicioFirmas(db).obtener_documento_aprobado_para_firma(
            convenio_id
        )
        return DocumentoAprobadoFirmaLeer.model_validate(documento)
    except ErrorConvenio as exc:
        _lanzar_http(exc)


@router.post(
    "/{convenio_id}/firmas/cambio-sustancial",
    response_model=ProcesoFirmasConvenioLeer,
)
def solicitar_cambio_sustancial_firmas(
    convenio_id: int,
    datos: SolicitarCambioSustancialFirmas,
    db: DatabaseSession,
    usuario: PuedeGestionarFirmas,
) -> ProcesoFirmasConvenioLeer:
    try:
        proceso = ServicioFirmas(db).solicitar_cambio_sustancial(
            convenio_id, datos.observacion, usuario
        )
        return ProcesoFirmasConvenioLeer.model_validate(proceso)
    except ErrorConvenio as exc:
        _lanzar_http(exc)


@router.patch(
    "/{convenio_id}/firmas/{firma_id}", response_model=FirmaConvenioLeer
)
def configurar_firma(
    convenio_id: int,
    firma_id: int,
    datos: ConfigurarFirmaConvenio,
    db: DatabaseSession,
    _: PuedeGestionarFirmas,
) -> FirmaConvenioLeer:
    try:
        firma = ServicioFirmas(db).configurar_firma(
            convenio_id,
            firma_id,
            datos.nombre,
            datos.cargo,
            str(datos.correo) if datos.correo is not None else None,
            datos.modalidad,
        )
        return FirmaConvenioLeer.model_validate(firma)
    except ErrorConvenio as exc:
        _lanzar_http(exc)


@router.post(
    "/{convenio_id}/firmas/fisicas",
    response_model=ProcesoFirmasConvenioLeer,
    status_code=status.HTTP_201_CREATED,
)
async def registrar_firmas_fisicas(
    convenio_id: int,
    db: DatabaseSession,
    almacen: Storage,
    usuario: PuedeGestionarFirmas,
    firma_ids: Annotated[list[int], Form()],
    fecha_firma: Annotated[date, Form()],
    archivo: Annotated[UploadFile, File()],
) -> ProcesoFirmasConvenioLeer:
    contenido = await archivo.read(TAMANO_MAXIMO_DOCUMENTO + 1)
    try:
        proceso = ServicioFirmas(db, almacen).registrar_firmas_fisicas(
            convenio_id=convenio_id,
            firma_ids=firma_ids,
            fecha_firma=fecha_firma,
            nombre_archivo=archivo.filename or "",
            tipo_mime=archivo.content_type or "application/octet-stream",
            contenido=contenido,
            usuario=usuario,
        )
        return ProcesoFirmasConvenioLeer.model_validate(proceso)
    except ErrorConvenio as exc:
        _lanzar_http(exc)
    except ErrorAlmacenDocumentos as exc:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            "No fue posible almacenar el documento firmado",
        ) from exc


@router.post(
    "/{convenio_id}/firmas/formalizar",
    response_model=ProcesoFirmasConvenioLeer,
)
def formalizar_convenio(
    convenio_id: int,
    db: DatabaseSession,
    usuario: PuedeGestionarFirmas,
) -> ProcesoFirmasConvenioLeer:
    try:
        proceso = ServicioFirmas(db).formalizar(convenio_id, usuario)
        return ProcesoFirmasConvenioLeer.model_validate(proceso)
    except ErrorConvenio as exc:
        _lanzar_http(exc)


@router.post(
    "/{convenio_id}/firmas/iniciar",
    response_model=ProcesoFirmasConvenioLeer,
)
def iniciar_firmas(
    convenio_id: int, db: DatabaseSession, _: PuedeGestionarFirmas
) -> ProcesoFirmasConvenioLeer:
    try:
        return ProcesoFirmasConvenioLeer.model_validate(
            ServicioFirmas(db).iniciar(convenio_id)
        )
    except ErrorConvenio as exc:
        _lanzar_http(exc)


@router.get(
    "/{convenio_id}/firmas",
    response_model=ProcesoFirmasConvenioLeer,
)
def obtener_firmas(
    convenio_id: int, db: DatabaseSession, _: PuedeGestionarFirmas
) -> ProcesoFirmasConvenioLeer:
    try:
        proceso = ServicioFirmas(db).obtener_proceso_seguimiento(convenio_id)
        return ProcesoFirmasConvenioLeer.model_validate(proceso)
    except ErrorConvenio as exc:
        _lanzar_http(exc)


@router.post(
    "/{convenio_id}/firmas/enviar",
    response_model=ProcesoFirmasConvenioLeer,
)
def enviar_invitaciones_firma(
    convenio_id: int,
    db: DatabaseSession,
    correo: Correo,
    usuario: PuedeGestionarFirmas,
) -> ProcesoFirmasConvenioLeer:
    try:
        proceso = ServicioFirmaElectronica(
            db,
            enviador=correo,
            frontend_url=settings.public_frontend_url,
        ).enviar_invitaciones(convenio_id, usuario)
        return ProcesoFirmasConvenioLeer.model_validate(proceso)
    except EntregaInvitacionesFirmaError as exc:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            detail={
                "message": "Las invitaciones fueron creadas, pero hubo fallos de entrega",
                "firmas_fallidas": exc.firmas_fallidas,
            },
        ) from exc
    except ErrorConvenio as exc:
        _lanzar_http(exc)


@router.post(
    "/{convenio_id}/firmas/{firma_id}/reenviar",
    response_model=InvitacionFirmaConvenioLeer,
)
def reenviar_invitacion_firma(
    convenio_id: int,
    firma_id: int,
    db: DatabaseSession,
    correo: Correo,
    usuario: PuedeGestionarFirmas,
) -> InvitacionFirmaConvenioLeer:
    try:
        invitacion = ServicioFirmaElectronica(
            db,
            enviador=correo,
            frontend_url=settings.public_frontend_url,
        ).reenviar(convenio_id, firma_id, usuario)
        return InvitacionFirmaConvenioLeer.model_validate(invitacion)
    except ErrorConvenio as exc:
        _lanzar_http(exc)
    except ErrorEnvioCorreo as exc:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            "La invitación fue creada, pero no fue posible entregar el correo",
        ) from exc
