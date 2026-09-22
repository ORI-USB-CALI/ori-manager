from typing import Annotated, NoReturn

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.api.deps import requiere
from backend.core.permisos import Permiso
from backend.core.unidades_organizacionales import TipoUnidad
from backend.db.session import get_db
from backend.models.enums import TipoDocumentoSolicitud
from backend.models.tipo_convenio import TipoConvenio
from backend.models.usuario import Usuario
from backend.schemas.solicitud import (
    CatalogosSolicitud,
    DocumentoSolicitudLeer,
    PerfilSolicitante,
    SolicitudActualizar,
    SolicitudCrear,
    SolicitudLeer,
    SolicitudListado,
    TipoDocumentoOpcion,
)
from backend.services.documentos import (
    TAMANO_MAXIMO_DOCUMENTO,
    TIPOS_DOCUMENTO_REPRESENTACION,
    AlmacenDocumentos,
    get_almacen_documentos,
)
from backend.services.solicitudes import (
    DocumentoInvalido,
    ErrorSolicitud,
    ReferenciaSolicitudInvalida,
    ServicioSolicitudes,
    SolicitudIncompleta,
    SolicitudNoEditable,
    SolicitudNoEncontrada,
)

router = APIRouter(prefix="/solicitudes", tags=["Solicitudes"])
DatabaseSession = Annotated[Session, Depends(get_db)]
Storage = Annotated[AlmacenDocumentos, Depends(get_almacen_documentos)]
PuedeCrear = Annotated[Usuario, requiere(Permiso.SOLICITUDES_CREAR)]
PuedeVerPropias = Annotated[Usuario, requiere(Permiso.SOLICITUDES_VER_PROPIAS)]
PuedeEditarPropias = Annotated[Usuario, requiere(Permiso.SOLICITUDES_EDITAR_PROPIAS)]
PuedeRadicar = Annotated[Usuario, requiere(Permiso.SOLICITUDES_RADICAR)]

NOMBRES_DOCUMENTOS = {
    TipoDocumentoSolicitud.CAMARA_COMERCIO: "Cámara de Comercio",
    TipoDocumentoSolicitud.RUT: "RUT",
    TipoDocumentoSolicitud.CEDULA_REPRESENTANTE_LEGAL: "Cédula del representante legal",
    TipoDocumentoSolicitud.OTRO_DOCUMENTO_REPRESENTACION: (
        "Otro documento de representación legal"
    ),
    TipoDocumentoSolicitud.OTRO_SOPORTE: "Otro soporte",
}


def _lanzar_http(exc: ErrorSolicitud) -> NoReturn:
    if isinstance(exc, SolicitudNoEncontrada):
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    if isinstance(exc, SolicitudNoEditable):
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    if isinstance(exc, (DocumentoInvalido, ReferenciaSolicitudInvalida)):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    if isinstance(exc, SolicitudIncompleta):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            {"message": str(exc), "errors": exc.errores},
        ) from exc
    raise exc


def _perfil(usuario: Usuario) -> PerfilSolicitante:
    unidad = usuario.unidad_organizacional
    nombre_unidad = None
    programa = None
    if unidad is not None and unidad.tipo == TipoUnidad.PROGRAMA:
        programa = unidad.nombre
        nombre_unidad = unidad.unidad_padre.nombre if unidad.unidad_padre else None
    elif unidad is not None:
        nombre_unidad = unidad.nombre
    return PerfilSolicitante(
        tipo_usuario=usuario.tipo_usuario,
        tipo_unidad=unidad.tipo if unidad is not None else None,
        nombre=usuario.nombre_completo,
        correo=usuario.correo,
        identificacion=usuario.documento_identidad,
        entidad=usuario.entidad_externa,
        cargo=usuario.cargo,
        unidad=nombre_unidad,
        programa=programa,
    )


@router.get("/catalogos", response_model=CatalogosSolicitud)
def obtener_catalogos(db: DatabaseSession, usuario: PuedeCrear) -> CatalogosSolicitud:
    tipos = db.scalars(
        select(TipoConvenio)
        .where(TipoConvenio.activo.is_(True))
        .order_by(TipoConvenio.nombre)
    ).all()
    return CatalogosSolicitud(
        solicitante=_perfil(usuario),
        tipos_convenio=tipos,
        tipos_documento=[
            TipoDocumentoOpcion(
                codigo=tipo,
                nombre=NOMBRES_DOCUMENTOS[tipo],
                es_representacion_legal=tipo in TIPOS_DOCUMENTO_REPRESENTACION,
            )
            for tipo in TipoDocumentoSolicitud
        ],
    )


@router.post("", response_model=SolicitudLeer, status_code=status.HTTP_201_CREATED)
def crear_solicitud(datos: SolicitudCrear, db: DatabaseSession, usuario: PuedeCrear):
    try:
        return ServicioSolicitudes(db).crear(datos, usuario)
    except ErrorSolicitud as exc:
        _lanzar_http(exc)


@router.get("/mias", response_model=SolicitudListado)
def listar_solicitudes_propias(
    db: DatabaseSession, usuario: PuedeVerPropias
) -> SolicitudListado:
    items = ServicioSolicitudes(db).listar(usuario)
    return SolicitudListado(items=items, total=len(items))


@router.get("/{solicitud_id}", response_model=SolicitudLeer)
def obtener_solicitud(solicitud_id: int, db: DatabaseSession, usuario: PuedeVerPropias):
    try:
        return ServicioSolicitudes(db).obtener(solicitud_id, usuario)
    except ErrorSolicitud as exc:
        _lanzar_http(exc)


@router.patch("/{solicitud_id}", response_model=SolicitudLeer)
def actualizar_solicitud(
    solicitud_id: int,
    datos: SolicitudActualizar,
    db: DatabaseSession,
    usuario: PuedeEditarPropias,
):
    try:
        return ServicioSolicitudes(db).actualizar(solicitud_id, datos, usuario)
    except ErrorSolicitud as exc:
        _lanzar_http(exc)


@router.post(
    "/{solicitud_id}/documentos",
    response_model=DocumentoSolicitudLeer,
    status_code=status.HTTP_201_CREATED,
)
async def cargar_documento(
    solicitud_id: int,
    db: DatabaseSession,
    almacen: Storage,
    usuario: PuedeEditarPropias,
    tipo_documento: Annotated[TipoDocumentoSolicitud, Form()],
    archivo: Annotated[UploadFile, File()],
):
    contenido = await archivo.read(TAMANO_MAXIMO_DOCUMENTO + 1)
    try:
        return ServicioSolicitudes(db, almacen).agregar_documento(
            solicitud_id,
            usuario,
            tipo_documento,
            archivo.filename or "",
            archivo.content_type or "application/octet-stream",
            contenido,
        )
    except ErrorSolicitud as exc:
        _lanzar_http(exc)


@router.delete(
    "/{solicitud_id}/documentos/{documento_id}", status_code=status.HTTP_204_NO_CONTENT
)
def eliminar_documento(
    solicitud_id: int,
    documento_id: int,
    db: DatabaseSession,
    almacen: Storage,
    usuario: PuedeEditarPropias,
) -> None:
    try:
        ServicioSolicitudes(db, almacen).eliminar_documento(
            solicitud_id, documento_id, usuario
        )
    except ErrorSolicitud as exc:
        _lanzar_http(exc)


@router.post("/{solicitud_id}/radicar", response_model=SolicitudLeer)
def radicar_solicitud(
    solicitud_id: int, db: DatabaseSession, almacen: Storage, usuario: PuedeRadicar
):
    try:
        return ServicioSolicitudes(db, almacen).radicar(solicitud_id, usuario)
    except ErrorSolicitud as exc:
        _lanzar_http(exc)
