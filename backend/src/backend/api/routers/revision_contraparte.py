from typing import Annotated, NoReturn

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Response,
    UploadFile,
    status,
)
from sqlalchemy.orm import Session

from backend.api.deps import UsuarioActual, requiere
from backend.core.permisos import Permiso
from backend.db.session import get_db
from backend.models.historial_etapa import HistorialEtapa
from backend.models.revision_pendiente import RevisionPendiente
from backend.models.usuario import Usuario
from backend.schemas.revision_contraparte import (
    DevolucionContraparteCrear,
    HistorialEtapaLeer,
    RevisionPendienteLeer,
)
from backend.services.documentos import (
    AlmacenDocumentos,
    get_almacen_documentos,
)
from backend.services.revision_contraparte import (
    ConvenioNoEncontrado,
    DocumentoInvalido,
    DocumentoNoEncontrado,
    ErrorRevisionContraparte,
    ObservacionesRequeridas,
    RevisionJuridicaNoAprobada,
    RevisionPendienteNoEncontrada,
    ServicioRevisionContraparte,
    UsuarioNoAutorizado,
)

router = APIRouter(prefix="/convenios/{convenio_id}/revision-contraparte", tags=["Revisión de contraparte"])
router_pendientes = APIRouter(prefix="/revision-contraparte", tags=["Revisión de contraparte"])
DatabaseSession = Annotated[Session, Depends(get_db)]
Storage = Annotated[AlmacenDocumentos, Depends(get_almacen_documentos)]
PuedeGestionar = Annotated[Usuario, requiere(Permiso.CONVENIOS_GESTIONAR_REVISION_CONTRAPARTE)]
PuedeRevisarPropia = Annotated[Usuario, requiere(Permiso.CONVENIOS_REVISAR_CONTRAPARTE_PROPIA)]


def _lanzar_http(exc: ErrorRevisionContraparte) -> NoReturn:
    if isinstance(exc, (ConvenioNoEncontrado, RevisionPendienteNoEncontrada, DocumentoNoEncontrado)):
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    if isinstance(exc, UsuarioNoAutorizado):
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc)) from exc
    if isinstance(exc, RevisionJuridicaNoAprobada):
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    if isinstance(exc, (ObservacionesRequeridas, DocumentoInvalido)):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    raise exc


@router.post("/envios", response_model=HistorialEtapaLeer, status_code=status.HTTP_201_CREATED)
async def registrar_envio(
    convenio_id: int,
    db: DatabaseSession,
    almacen: Storage,
    usuario: PuedeGestionar,
    archivo: Annotated[UploadFile, File()],
) -> HistorialEtapa:
    contenido = await archivo.read()
    try:
        return ServicioRevisionContraparte(db, almacen).registrar_envio(
            convenio_id,
            usuario,
            nombre=archivo.filename or "",
            tipo_mime=archivo.content_type or "",
            contenido=contenido,
        )
    except ErrorRevisionContraparte as exc:
        _lanzar_http(exc)


@router.get("/documento")
def descargar_documento_vigente(
    convenio_id: int, db: DatabaseSession, almacen: Storage, usuario: UsuarioActual
) -> Response:
    try:
        documento = ServicioRevisionContraparte(db, almacen).obtener_documento_vigente(convenio_id, usuario)
        contenido = almacen.leer(documento.ruta_almacenamiento)
    except ErrorRevisionContraparte as exc:
        _lanzar_http(exc)
    return Response(
        content=contenido,
        media_type=documento.tipo_mime,
        headers={"Content-Disposition": f'attachment; filename="{documento.nombre_archivo}"'},
    )


@router.post("/aprobacion", response_model=RevisionPendienteLeer, status_code=status.HTTP_201_CREATED)
def aprobar(
    convenio_id: int, db: DatabaseSession, usuario: PuedeRevisarPropia
) -> RevisionPendiente:
    try:
        return ServicioRevisionContraparte(db).aprobar(convenio_id, usuario)
    except ErrorRevisionContraparte as exc:
        _lanzar_http(exc)


@router.post("/devolucion", response_model=RevisionPendienteLeer, status_code=status.HTTP_201_CREATED)
def devolver_con_observaciones(
    convenio_id: int, datos: DevolucionContraparteCrear, db: DatabaseSession, usuario: PuedeRevisarPropia
) -> RevisionPendiente:
    try:
        return ServicioRevisionContraparte(db).devolver_con_observaciones(
            convenio_id, datos.observaciones, usuario
        )
    except ErrorRevisionContraparte as exc:
        _lanzar_http(exc)


@router_pendientes.get("/pendientes", response_model=list[RevisionPendienteLeer])
def listar_pendientes(db: DatabaseSession, usuario: UsuarioActual) -> list[RevisionPendiente]:
    return ServicioRevisionContraparte(db).listar_pendientes(usuario)
