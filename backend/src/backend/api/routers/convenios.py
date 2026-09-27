from typing import Annotated, NoReturn
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.api.deps import requiere
from backend.core.permisos import Permiso
from backend.db.session import get_db
from backend.models.convenio import Convenio
from backend.models.tipo_convenio import TipoConvenio
from backend.models.unidad_organizacional import UnidadOrganizacional
from backend.models.usuario import Usuario
from backend.schemas.convenio import (
    AprobarRevision,
    AtenderObservacion,
    CatalogosElaboracionLeer,
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
    DocumentoConvenioLeer,
    HistorialConvenioLeer,
    HistorialEtapaLeer,
    ObservacionRevisionLeer,
    RevisionContenidoGuardar,
    RevisionConvenioLeer,
    RevisionJuridicaPendienteLeer,
    TableroConveniosLeer,
    ValidacionElaboracionLeer,
    VersionConvenioLeer,
    VersionConvenioResumen,
    VersionRevisionActual,
    VersionRevisionReferencia,
)
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
from backend.services.documentos import (
    AlmacenDocumentos,
    ErrorAlmacenDocumentos,
    get_almacen_documentos,
)

router = APIRouter(prefix="/convenios", tags=["Convenios"])
DatabaseSession = Annotated[Session, Depends(get_db)]
Storage = Annotated[AlmacenDocumentos, Depends(get_almacen_documentos)]
PuedeVer = Annotated[Usuario, requiere(Permiso.CONVENIOS_VER)]
PuedeCrear = Annotated[Usuario, requiere(Permiso.CONVENIOS_CREAR)]
PuedeEditar = Annotated[Usuario, requiere(Permiso.CONVENIOS_EDITAR)]
PuedeRevisar = Annotated[Usuario, requiere(Permiso.CONVENIOS_REVISAR)]


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
    db: DatabaseSession, _: PuedeRevisar
) -> list[RevisionJuridicaPendienteLeer]:
    revisiones = ServicioConvenios(db).listar_revisiones_juridicas_pendientes()
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


@router.get("/tablero", response_model=TableroConveniosLeer)
def obtener_tablero(db: DatabaseSession, _: PuedeVer) -> TableroConveniosLeer:
    etapas, convenios = ServicioConvenios(db).listar_tablero()
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
            )
            for convenio, responsable in convenios
        ],
    )


@router.get("/{convenio_id}", response_model=ConvenioLeer)
def obtener_convenio(
    convenio_id: int, db: DatabaseSession, _: PuedeVer
) -> Convenio:
    try:
        return ServicioConvenios(db).obtener(convenio_id)
    except ErrorConvenio as exc:
        _lanzar_http(exc)


@router.get("/{convenio_id}/elaboracion", response_model=ConvenioElaboracionLeer)
def obtener_elaboracion(
    convenio_id: int, db: DatabaseSession, _: PuedeVer
) -> Convenio:
    try:
        return ServicioConvenios(db).obtener_para_elaboracion(convenio_id)
    except ErrorConvenio as exc:
        _lanzar_http(exc)


@router.get(
    "/{convenio_id}/elaboracion/validacion", response_model=ValidacionElaboracionLeer
)
def validar_elaboracion(
    convenio_id: int, db: DatabaseSession, _: PuedeVer
) -> ValidacionElaboracionLeer:
    try:
        faltantes = ServicioConvenios(db).validar_elaboracion(convenio_id)
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
    convenio_id: int, db: DatabaseSession, _: PuedeVer
) -> list[VersionConvenioResumen]:
    try:
        return ServicioConvenios(db).listar_versiones(convenio_id)
    except ErrorConvenio as exc:
        _lanzar_http(exc)


@router.get(
    "/{convenio_id}/versiones/{numero}", response_model=VersionConvenioLeer
)
def obtener_version(
    convenio_id: int, numero: int, db: DatabaseSession, _: PuedeVer
) -> VersionConvenioLeer:
    try:
        return ServicioConvenios(db).obtener_version(convenio_id, numero)
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
    convenio_id: int, db: DatabaseSession, _: PuedeVer
) -> HistorialConvenioLeer:
    """CA-06/CA-07 de HU-13: historial de rondas de revisión y cambios de
    etapa del convenio, ordenados cronológicamente.

    Se ordena por `id` (autoincremental), no por el timestamp: dentro de una
    misma transacción, `now()` en Postgres devuelve siempre el mismo valor
    para todas las filas insertadas, así que `creado_en`/`fecha_cambio`
    pueden empatar entre sí y no garantizan el orden real de inserción.
    """
    try:
        convenio = ServicioConvenios(db).obtener_historial(convenio_id)
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
    convenio_id: int, db: DatabaseSession, _: PuedeRevisar
) -> ConvenioParaRevisionLeer:
    """CA-01/CA-02 de HU-13: pantalla principal de revisión jurídica — el
    convenio preparado para revisión, sus documentos y la ronda de revisión
    pendiente que el Revisor ORI debe resolver."""
    try:
        (
            convenio,
            revision_pendiente,
            documentos,
            version_recibida,
            version_actual,
        ) = ServicioConvenios(db).obtener_para_revision(convenio_id)
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
    _: PuedeVer,
) -> Response:
    try:
        documento, contenido = ServicioConvenios(
            db, almacen
        ).obtener_contenido_documento(convenio_id, documento_id)
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
