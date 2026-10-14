from datetime import date, datetime
from typing import Annotated, Literal, NoReturn
from urllib.parse import quote

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from fastapi.responses import JSONResponse, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.api.deps import requiere
from backend.core.config import settings
from backend.core.permisos import Permiso
from backend.core.unidades_organizacionales import TipoUnidad
from backend.db.session import get_db
from backend.models.actividad_convenio import ActividadConvenio
from backend.models.convenio import Convenio
from backend.models.enums import (
    AlcanceConvenio,
    EstadoConvenio,
    EstadoSeguimientoRenovacion,
    TipoAliado,
)
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
    CatalogosConsultaLeer,
    CatalogosElaboracionLeer,
    ConfigurarFirmaConvenio,
    ContraparteConsultaLeer,
    ConvenioConsultaItem,
    ConvenioConsultaListado,
    ConvenioCrear,
    ConvenioCrearManual,
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
    HitoLineaTiempoLeer,
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
from backend.schemas.estadisticas_convenios import ReporteEstadisticoConveniosLeer
from backend.schemas.evaluacion import (
    EstadoEvaluacionLeer,
    EvaluacionConvenioCrear,
    EvaluacionConvenioLeer,
)
from backend.schemas.renovacion import (
    DecisionNoRenovacionLeer,
    RenovacionIniciadaLeer,
    SeguimientoRenovacionLeer,
)
from backend.schemas.reportes import ConvenioReporteActivoLeer
from backend.schemas.soporte_convenio import SoporteConvenioLeer
from backend.services.actividades_utilizacion import ServicioActividadesUtilizacion
from backend.services.alertas_vencimiento import (
    ZONA_HORARIA_DOMINIO,
    ServicioAlertasVencimiento,
)
from backend.services.convenios import (
    ESTADOS_SIN_FORMALIZAR,
    ConflictoVersionConvenio,
    ConvenioDuplicado,
    ConvenioNoEditable,
    ConvenioNoEncontrado,
    DocumentoConvenioInvalido,
    DocumentoDemasiadoGrande,
    ElaboracionIncompleta,
    ErrorConvenio,
    FiltroConsultaInvalido,
    FiltrosConsultaConvenio,
    ObservacionNoDisponible,
    ReferenciaConvenioInvalida,
    RevisionNoDisponible,
    ServicioConvenios,
    SolicitudNoAprobada,
    TipoFiltroFecha,
    convenio_esta_formalizado,
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
from backend.services.estadisticas_convenios import (
    ServicioEstadisticasConvenios,
    generar_excel_estadisticas_convenios,
    generar_pdf_estadisticas_convenios,
)
from backend.services.evaluaciones import (
    ConvenioNoEvaluable,
    ServicioEvaluaciones,
    es_evaluable,
)
from backend.services.exportacion_convenio import (
    ErrorValidacionExportacion,
    ServicioExportacionConvenio,
)
from backend.services.firma_electronica import (
    EntregaInvitacionesFirmaError,
    ServicioFirmaElectronica,
)
from backend.services.firmas import ServicioFirmas
from backend.services.linea_tiempo import construir_linea_tiempo
from backend.services.renovaciones import (
    ServicioRenovaciones,
    listar_seguimiento_renovaciones,
)
from backend.services.reportes import (
    ServicioReportes,
    generar_excel_convenios_activos,
    generar_pdf_convenios_activos,
)
from backend.services.soportes_convenio import (
    ConvenioNoAdmiteSoportes,
    ServicioSoportesConvenio,
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
PuedeGestionarFirmas = Annotated[Usuario, requiere(Permiso.CONVENIOS_GESTIONAR_FIRMAS)]
PuedeEvaluar = Annotated[Usuario, requiere(Permiso.CONVENIOS_EVALUAR)]
# Guard de CA-04 de HU-22C: solo Gestor ORI y Administrador ORI; otro rol, 403.
PuedeGestionarSoportes = Annotated[
    Usuario, requiere(Permiso.CONVENIOS_GESTIONAR_SOPORTES)
]
PuedeVerReportes = Annotated[Usuario, requiere(Permiso.CONVENIOS_VER_REPORTES)]


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
            ConvenioNoEvaluable,
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
    if isinstance(exc, DocumentoConvenioInvalido):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    if isinstance(exc, DocumentoDemasiadoGrande):
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, str(exc)
        ) from exc
    if isinstance(
        exc,
        (
            ReferenciaConvenioInvalida,
            ConvenioNoAdmiteSoportes,
            FiltroConsultaInvalido,
        ),
    ):
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


@router.post("/manual", response_model=ConvenioLeer, status_code=status.HTTP_201_CREATED)
def crear_convenio_manual(
    datos: ConvenioCrearManual, db: DatabaseSession, usuario: PuedeCrear
) -> Convenio:
    try:
        return ServicioConvenios(db).crear_manual(datos, usuario)
    except ErrorConvenio as exc:
        _lanzar_http(exc)


def _contraparte_de(convenio: Convenio) -> ContraparteConsultaLeer:
    """HU-26 BE-1: del Aliado formal si ya existe; si no (convenio en
    trámite, sin aliado_id todavía), de los *_aliado_propuesto de la
    solicitud de origen."""
    if convenio.aliado is not None:
        return ContraparteConsultaLeer(
            nombre=convenio.aliado.nombre,
            tipo=convenio.aliado.tipo,
            identificacion=convenio.aliado.identificacion,
            es_aliado_formal=True,
        )
    solicitud = convenio.solicitud
    return ContraparteConsultaLeer(
        nombre=solicitud.nombre_aliado_propuesto if solicitud else None,
        tipo=solicitud.tipo_aliado_propuesto if solicitud else None,
        identificacion=solicitud.identificacion_aliado_propuesto if solicitud else None,
        es_aliado_formal=False,
    )


def _programa_de(convenio: Convenio):
    """HU-26 BE-1: solo se llena cuando la unidad organizacional del
    convenio es de tipo PROGRAMA; en otro caso va null."""
    unidad = convenio.unidad_organizacional
    if unidad is not None and unidad.tipo == TipoUnidad.PROGRAMA.value:
        return unidad
    return None


def _a_item_consulta(convenio: Convenio, puede_ver_detalle: bool) -> ConvenioConsultaItem:
    return ConvenioConsultaItem(
        id=convenio.id,
        codigo=convenio.codigo,
        objeto=convenio.objeto,
        estado=convenio.estado,
        etapa=convenio.etapa_actual,
        tipo_convenio=convenio.tipo_convenio,
        contraparte=_contraparte_de(convenio),
        programa=_programa_de(convenio),
        fecha_inicio=convenio.fecha_inicio,
        fecha_vencimiento=convenio.fecha_vencimiento,
        # HU-27 BE-2: null cuando el convenio no está formalizado, para que
        # la tabla no muestre fechas de firma diligenciadas a mano.
        fecha_formalizacion=(
            convenio.fecha_firma if convenio_esta_formalizado(convenio) else None
        ),
        puede_ver_detalle=puede_ver_detalle,
    )


@router.get("", response_model=ConvenioConsultaListado)
def consultar_convenios(
    db: DatabaseSession,
    usuario: PuedeVer,
    buscar: Annotated[str | None, Query(max_length=200)] = None,
    limite: Annotated[int, Query(ge=1, le=100)] = 20,
    desplazamiento: Annotated[int, Query(ge=0)] = 0,
    tipo_fecha: Annotated[TipoFiltroFecha | None, Query()] = None,
    fecha_desde: Annotated[date | None, Query()] = None,
    fecha_hasta: Annotated[date | None, Query()] = None,
    estado: Annotated[list[EstadoConvenio] | None, Query()] = None,
    tipo_contraparte: Annotated[list[TipoAliado] | None, Query()] = None,
    programa_id: Annotated[int | None, Query(ge=1)] = None,
    alcance: Annotated[AlcanceConvenio | None, Query()] = None,
    solo_formalizados: Annotated[bool, Query()] = False,
) -> ConvenioConsultaListado:
    filtros = FiltrosConsultaConvenio(
        buscar=buscar,
        limite=limite,
        desplazamiento=desplazamiento,
        tipo_fecha=tipo_fecha,
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
        # HU-28: FiltrosConsultaConvenio exige tuplas porque es frozen (hashable).
        estados=tuple(estado) if estado else None,
        tipos_contraparte=tuple(tipo_contraparte) if tipo_contraparte else None,
        programa_id=programa_id,
        alcance=alcance,
        solo_formalizados=solo_formalizados,
    )
    try:
        items, total = ServicioConvenios(db).consultar(usuario, filtros)
    except ErrorConvenio as exc:
        _lanzar_http(exc)
    return ConvenioConsultaListado(
        items=[
            _a_item_consulta(convenio, bool(puede_ver_detalle))
            for convenio, puede_ver_detalle in items
        ],
        total=total,
    )


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


@router.get("/catalogos/consulta", response_model=CatalogosConsultaLeer)
def obtener_catalogos_consulta(
    db: DatabaseSession,
    _: PuedeVer,
    solo_formalizados: Annotated[bool, Query()] = False,
) -> CatalogosConsultaLeer:
    programas = db.scalars(
        select(UnidadOrganizacional)
        .where(
            UnidadOrganizacional.tipo == TipoUnidad.PROGRAMA.value,
            UnidadOrganizacional.activa.is_(True),
        )
        .order_by(UnidadOrganizacional.nombre)
    ).all()
    return CatalogosConsultaLeer(
        estados=[
            estado for estado in EstadoConvenio
            if not solo_formalizados or estado.value not in ESTADOS_SIN_FORMALIZAR
        ],
        tipos_contraparte=list(TipoAliado),
        programas=programas,
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
            solicitud_consecutivo=(
                revision.convenio.solicitud.consecutivo
                if revision.convenio.solicitud is not None else None
            ),
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
    revisiones = ServicioConvenios(db).listar_revisiones_contraparte_pendientes(usuario)
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
        version_recibida=VersionConvenioLeer.model_validate(revision.version_convenio),
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
                aliado_propuesto=(
                    convenio.solicitud.nombre_aliado_propuesto
                    if convenio.solicitud is not None else None
                ),
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


@router.get(
    "/reportes/activos", response_model=list[ConvenioReporteActivoLeer]
)
def obtener_reporte_convenios_activos(
    db: DatabaseSession,
    _: PuedeVerReportes,
) -> list[ConvenioReporteActivoLeer]:
    convenios = ServicioReportes(db).listar_convenios_activos()
    return [ConvenioReporteActivoLeer.model_validate(c) for c in convenios]


@router.get("/reportes/activos/pdf")
def descargar_reporte_convenios_activos_pdf(
    db: DatabaseSession,
    _: PuedeVerReportes,
) -> Response:
    convenios = ServicioReportes(db).listar_convenios_activos()
    contenido = generar_pdf_convenios_activos(convenios)
    return Response(
        content=contenido,
        media_type="application/pdf",
        headers={
            "Content-Disposition": "attachment; filename=convenios-activos.pdf"
        },
    )


@router.get("/reportes/activos/excel")
def descargar_reporte_convenios_activos_excel(
    db: DatabaseSession,
    _: PuedeVerReportes,
) -> Response:
    convenios = ServicioReportes(db).listar_convenios_activos()
    contenido = generar_excel_convenios_activos(convenios)
    return Response(
        content=contenido,
        media_type=(
            "application/vnd.openxmlformats-officedocument"
            ".spreadsheetml.sheet"
        ),
        headers={
            "Content-Disposition": "attachment; filename=convenios-activos.xlsx"
        },
    )


def _filtros_estadisticas_convenios(
    estado: Annotated[EstadoConvenio | None, Query()] = None,
    aliado_activo: Annotated[bool | None, Query()] = None,
    tipo_aliado: Annotated[TipoAliado | None, Query()] = None,
    pais: Annotated[str | None, Query(max_length=80)] = None,
) -> dict:
    return {
        "estado": estado,
        "aliado_activo": aliado_activo,
        "tipo_aliado": tipo_aliado,
        "pais": pais,
    }


FiltrosEstadisticasConvenios = Annotated[dict, Depends(_filtros_estadisticas_convenios)]


@router.get(
    "/reportes/estadisticas", response_model=ReporteEstadisticoConveniosLeer
)
def obtener_reporte_estadisticas_convenios(
    db: DatabaseSession,
    _: PuedeVerReportes,
    filtros: FiltrosEstadisticasConvenios,
) -> ReporteEstadisticoConveniosLeer:
    reporte = ServicioEstadisticasConvenios(db).generar(**filtros)
    return ReporteEstadisticoConveniosLeer.model_validate(reporte)


@router.get("/reportes/estadisticas/pdf")
def descargar_reporte_estadisticas_convenios_pdf(
    db: DatabaseSession,
    _: PuedeVerReportes,
    filtros: FiltrosEstadisticasConvenios,
) -> Response:
    reporte = ServicioEstadisticasConvenios(db).generar(**filtros)
    contenido = generar_pdf_estadisticas_convenios(reporte)
    return Response(
        content=contenido,
        media_type="application/pdf",
        headers={
            "Content-Disposition": "attachment; filename=estadisticas-convenios.pdf"
        },
    )


@router.get("/reportes/estadisticas/excel")
def descargar_reporte_estadisticas_convenios_excel(
    db: DatabaseSession,
    _: PuedeVerReportes,
    filtros: FiltrosEstadisticasConvenios,
) -> Response:
    reporte = ServicioEstadisticasConvenios(db).generar(**filtros)
    contenido = generar_excel_estadisticas_convenios(reporte)
    return Response(
        content=contenido,
        media_type=(
            "application/vnd.openxmlformats-officedocument"
            ".spreadsheetml.sheet"
        ),
        headers={
            "Content-Disposition": "attachment; filename=estadisticas-convenios.xlsx"
        },
    )


@router.get("/{convenio_id}", response_model=ConvenioLeer)
def obtener_convenio(
    convenio_id: int, db: DatabaseSession, usuario: PuedeVer
) -> Convenio:
    try:
        return ServicioConvenios(db).obtener_en_alcance_operativo(convenio_id, usuario)
    except ErrorConvenio as exc:
        _lanzar_http(exc)


@router.get(
    "/{convenio_id}/actividades-utilizacion",
    response_model=list[ActividadUtilizacionLeer],
)
def listar_actividades_utilizacion(
    convenio_id: int, db: DatabaseSession, usuario: PuedeVer
) -> list[ActividadConvenio]:
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
) -> ActividadConvenio:
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
        decision = ServicioRenovaciones(db).registrar_no_renovacion(
            convenio_id, usuario
        )
    except ErrorConvenio as exc:
        _lanzar_http(exc)
    return DecisionNoRenovacionLeer.model_validate(decision)


@router.post(
    "/{convenio_id}/evaluacion",
    response_model=EvaluacionConvenioLeer,
    status_code=status.HTTP_201_CREATED,
)
def registrar_evaluacion(
    convenio_id: int,
    datos: EvaluacionConvenioCrear,
    db: DatabaseSession,
    usuario: PuedeEvaluar,
) -> EvaluacionConvenioLeer:
    try:
        evaluacion = ServicioEvaluaciones(db).registrar(convenio_id, datos, usuario)
    except ErrorConvenio as exc:
        _lanzar_http(exc)
    return EvaluacionConvenioLeer.model_validate(evaluacion)


@router.get("/{convenio_id}/evaluacion", response_model=EstadoEvaluacionLeer)
def obtener_evaluacion(
    convenio_id: int, db: DatabaseSession, usuario: PuedeVer
) -> EstadoEvaluacionLeer:
    """Estado de la evaluación de un convenio.

    Devuelve `evaluable` además de la evaluación para que la interfaz no
    reimplemente la regla de elegibilidad y siga funcionando sin cambios cuando
    se amplíen los estados evaluables.
    """
    try:
        convenio = ServicioConvenios(db).obtener_en_alcance_operativo(
            convenio_id, usuario
        )
        evaluacion = ServicioEvaluaciones(db).obtener(convenio_id)
    except ErrorConvenio as exc:
        _lanzar_http(exc)
    return EstadoEvaluacionLeer(
        evaluable=es_evaluable(convenio),
        estado_convenio=convenio.estado,
        evaluacion=(
            EvaluacionConvenioLeer.model_validate(evaluacion)
            if evaluacion is not None
            else None
        ),
    )


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


@router.patch("/{convenio_id}/elaboracion", response_model=ConvenioElaboracionLeer)
def guardar_elaboracion(
    convenio_id: int,
    datos: ConvenioElaboracionGuardar,
    db: DatabaseSession,
    usuario: PuedeEditar,
) -> Convenio:
    try:
        return ServicioConvenios(db).guardar_elaboracion(convenio_id, datos, usuario)
    except ErrorConvenio as exc:
        _lanzar_http(exc)


@router.get("/{convenio_id}/versiones", response_model=list[VersionConvenioResumen])
def listar_versiones(
    convenio_id: int, db: DatabaseSession, usuario: PuedeVer
) -> list[VersionConvenioResumen]:
    try:
        servicio = ServicioConvenios(db)
        servicio.verificar_alcance_operativo(convenio_id, usuario)
        return servicio.listar_versiones(convenio_id)
    except ErrorConvenio as exc:
        _lanzar_http(exc)


@router.get("/{convenio_id}/versiones/{numero}", response_model=VersionConvenioLeer)
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
        return ServicioConvenios(db).finalizar_elaboracion(convenio_id, usuario, datos)
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

    HU-21: la consulta usa la autorización de solo lectura del historial, no
    el alcance operativo, para que el Revisor ORI conserve el acceso a los
    convenios en cuya revisión jurídica participó.
    """
    try:
        servicio = ServicioConvenios(db)
        servicio.verificar_acceso_historial(convenio_id, usuario)
        convenio = servicio.obtener_historial(convenio_id)
    except ErrorConvenio as exc:
        _lanzar_http(exc)
    revisiones = sorted(convenio.revisiones, key=lambda revision: revision.id)
    cambios_etapa = sorted(convenio.historial_etapas, key=lambda cambio: cambio.id)
    return HistorialConvenioLeer(
        revisiones=[RevisionConvenioLeer.model_validate(r) for r in revisiones],
        cambios_etapa=[HistorialEtapaLeer.model_validate(h) for h in cambios_etapa],
    )


@router.get(
    "/{convenio_id}/linea-tiempo", response_model=list[HitoLineaTiempoLeer]
)
def obtener_linea_tiempo(
    convenio_id: int, db: DatabaseSession, usuario: PuedeVer
) -> list[HitoLineaTiempoLeer]:
    try:
        servicio = ServicioConvenios(db)
        servicio.verificar_acceso_historial(convenio_id, usuario)
        convenio = servicio.obtener(convenio_id)
    except ErrorConvenio as exc:
        _lanzar_http(exc)
    return construir_linea_tiempo(convenio, datetime.now(ZONA_HORARIA_DOMINIO).date())


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
            DocumentoConvenioLeer.model_validate(documento) for documento in documentos
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


@router.post(
    "/{convenio_id}/documentos",
    response_model=DocumentoConvenioLeer,
    status_code=status.HTTP_201_CREATED,
)
async def cargar_documento_convenio(
    convenio_id: int,
    db: DatabaseSession,
    almacen: Storage,
    usuario: PuedeGestionarSoportes,
    archivo: Annotated[UploadFile, File()],
) -> DocumentoConvenioLeer:
    # CA-04 de HU-22C: el guard deja pasar solo a Gestor y Administrador ORI
    # (403) y el estado del convenio se valida antes de leer el archivo (422).
    try:
        ServicioSoportesConvenio(db).verificar_carga(convenio_id)
    except ErrorConvenio as exc:
        _lanzar_http(exc)
    LIMITE_20MB = 20 * 1024 * 1024
    contenido = await archivo.read(LIMITE_20MB + 1)
    try:
        documento = ServicioConvenios(db, almacen=almacen).agregar_documento(
            convenio_id=convenio_id,
            nombre_archivo=archivo.filename or "",
            tipo_mime=archivo.content_type,
            contenido=contenido,
            usuario=usuario,
        )
        return DocumentoConvenioLeer.model_validate(documento)
    except ErrorConvenio as exc:
        _lanzar_http(exc)
    except ErrorAlmacenDocumentos as exc:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            "No fue posible almacenar el documento",
        ) from exc


@router.get("/{convenio_id}/documentos", response_model=list[SoporteConvenioLeer])
def listar_soportes(
    convenio_id: int, db: DatabaseSession, _: PuedeGestionarSoportes
) -> list[SoporteConvenioLeer]:
    """CA-03 de HU-22C: soportes vigentes del convenio, del más reciente al
    más antiguo."""
    try:
        documentos = ServicioSoportesConvenio(db).listar(convenio_id)
    except ErrorConvenio as exc:
        _lanzar_http(exc)
    return [SoporteConvenioLeer.desde_documento(documento) for documento in documentos]


@router.get("/{convenio_id}/documentos/{documento_id}/descargar")
def descargar_soporte(
    convenio_id: int,
    documento_id: int,
    db: DatabaseSession,
    almacen: Storage,
    _: PuedeGestionarSoportes,
    disposicion: Literal["inline", "attachment"] = "attachment",
) -> Response:
    """CA-03 de HU-22C: entrega el soporte por el backend; `inline` lo abre en
    el navegador y `attachment` lo descarga."""
    try:
        documento, contenido = ServicioSoportesConvenio(db).obtener_contenido(
            convenio_id, documento_id, almacen
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
        headers={
            "Content-Disposition": f"{disposicion}; filename*=UTF-8''{nombre}",
            # Sin sniffing el navegador respeta el tipo declarado, y sin caché
            # el soporte no queda guardado en proxies ni en equipos compartidos.
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "no-store",
        },
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
    correo: Correo,
) -> RevisionConvenioLeer:
    try:
        servicio = ServicioConvenios(
            db, enviador=correo, frontend_url=settings.public_frontend_url
        )
        # No crear una revisión manual que no pueda recibir su enlace público.
        convenio_previo = servicio.obtener(convenio_id)
        if convenio_previo.origen == "MANUAL_ORI" and not settings.public_frontend_url:
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Falta PUBLIC_FRONTEND_URL")
        revision = servicio.enviar_a_contraparte(
            convenio_id, datos.expected_version, usuario
        )
        if convenio_previo.origen == "MANUAL_ORI":
            servicio.reenviar_invitacion_contraparte(convenio_id, revision.id, usuario)
        convenio = servicio.obtener_historial(convenio_id)
        return RevisionConvenioLeer.model_validate(
            next(item for item in convenio.revisiones if item.id == revision.id)
        )
    except ErrorConvenio as exc:
        _lanzar_http(exc)


@router.post("/{convenio_id}/revision-contraparte/{revision_id}/reenviar-invitacion")
def reenviar_invitacion_manual(
    convenio_id: int,
    revision_id: int,
    db: DatabaseSession,
    usuario: PuedeGestionarContraparte,
    correo: Correo,
):
    if not settings.public_frontend_url:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Falta PUBLIC_FRONTEND_URL")
    try:
        servicio = ServicioConvenios(db, enviador=correo, frontend_url=settings.public_frontend_url)
        convenio = servicio.obtener(convenio_id)
        if convenio.origen != "MANUAL_ORI":
            raise ReferenciaConvenioInvalida("Solo para convenios de origen manual")
        invitacion = servicio.reenviar_invitacion_contraparte(convenio_id, revision_id, usuario)
        return {"id": invitacion.id, "enviado_en": invitacion.enviado_en}
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
            revision_final_aprobada=(contexto.revision_final.resultado == "APROBADA"),
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


@router.patch("/{convenio_id}/firmas/{firma_id}", response_model=FirmaConvenioLeer)
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


@router.get(
    "/{convenio_id}/exportar",
    summary="Exportar convenio en formato PDF o Excel",
)
def exportar_convenio(
    convenio_id: int,
    db: DatabaseSession,
    usuario: PuedeVer,
    formato: str = "pdf",
) -> Response:
    formato_normalizado = (formato or "").strip().lower()
    if formato_normalizado not in ("pdf", "excel"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Formato no válido: '{formato}'. Formatos soportados: 'pdf', 'excel'.",
        )

    try:
        # Además de convenios.ver, el convenio debe estar en el alcance
        # operativo del usuario (la misma regla del detalle): fuera de él, 404.
        # Va antes de validar para no revelar qué datos le faltan.
        ServicioConvenios(db).verificar_alcance_operativo(convenio_id, usuario)
        contenido, media_type, filename = ServicioExportacionConvenio().exportar(
            convenio_id=convenio_id,
            formato=formato_normalizado,
            db=db,
        )
        return Response(
            content=contenido,
            media_type=media_type,
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
            },
        )
    except ErrorValidacionExportacion as exc:
        # CA-03 de HU-24: el contrato pide el error en el nivel superior del
        # cuerpo, no dentro de "detail".
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content=exc.como_respuesta(),
        )
    except ErrorConvenio as exc:
        _lanzar_http(exc)
