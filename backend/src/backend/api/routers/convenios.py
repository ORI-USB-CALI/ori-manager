from typing import Annotated, NoReturn

from fastapi import APIRouter, Depends, HTTPException, status
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
    CatalogosElaboracionLeer,
    ConvenioCrear,
    ConvenioElaboracionActualizar,
    ConvenioElaboracionLeer,
    ConvenioLeer,
    ConvenioParaRevisionLeer,
    DocumentoConvenioLeer,
    HistorialConvenioLeer,
    HistorialEtapaLeer,
    RevisionConvenioLeer,
    ValidacionElaboracionLeer,
)
from backend.services.convenios import (
    ConvenioDuplicado,
    ConvenioNoEditable,
    ConvenioNoEncontrado,
    ElaboracionIncompleta,
    ErrorConvenio,
    ReferenciaConvenioInvalida,
    ServicioConvenios,
    SolicitudNoAprobada,
    validar_completitud,
)

router = APIRouter(prefix="/convenios", tags=["Convenios"])
DatabaseSession = Annotated[Session, Depends(get_db)]
PuedeVer = Annotated[Usuario, requiere(Permiso.CONVENIOS_VER)]
PuedeCrear = Annotated[Usuario, requiere(Permiso.CONVENIOS_CREAR)]
PuedeEditar = Annotated[Usuario, requiere(Permiso.CONVENIOS_EDITAR)]
PuedeRevisar = Annotated[Usuario, requiere(Permiso.CONVENIOS_REVISAR)]


def _lanzar_http(exc: ErrorConvenio) -> NoReturn:
    if isinstance(exc, ConvenioNoEncontrado):
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    if isinstance(exc, (ConvenioDuplicado, SolicitudNoAprobada, ConvenioNoEditable)):
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
        convenio = ServicioConvenios(db).obtener(convenio_id)
    except ErrorConvenio as exc:
        _lanzar_http(exc)
    faltantes = validar_completitud(convenio)
    return ValidacionElaboracionLeer(completo=not faltantes, faltantes=faltantes)


@router.post("/{convenio_id}/elaboracion/finalizar", response_model=ConvenioLeer)
def finalizar_elaboracion(
    convenio_id: int, db: DatabaseSession, usuario: PuedeEditar
) -> Convenio:
    try:
        return ServicioConvenios(db).finalizar_elaboracion(convenio_id, usuario)
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
    etapa del convenio, ordenados cronológicamente."""
    try:
        convenio = ServicioConvenios(db).obtener_historial(convenio_id)
    except ErrorConvenio as exc:
        _lanzar_http(exc)
    revisiones = sorted(convenio.revisiones, key=lambda revision: revision.creado_en)
    cambios_etapa = sorted(
        convenio.historial_etapas, key=lambda cambio: cambio.fecha_cambio
    )
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
        convenio, revision_pendiente = ServicioConvenios(db).obtener_para_revision(
            convenio_id
        )
    except ErrorConvenio as exc:
        _lanzar_http(exc)
    return ConvenioParaRevisionLeer(
        convenio=ConvenioElaboracionLeer.model_validate(convenio),
        documentos=[
            DocumentoConvenioLeer.model_validate(documento)
            for documento in convenio.documentos
        ],
        revision_pendiente=RevisionConvenioLeer.model_validate(revision_pendiente),
    )
