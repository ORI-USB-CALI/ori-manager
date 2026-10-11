from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime, timedelta
from threading import Barrier
from uuid import uuid4

import pytest
from sqlalchemy import delete, event, func, select
from sqlalchemy.orm import Session

from backend.core.roles import CodigoRol, TipoUsuario
from backend.models.convenio import Convenio
from backend.models.enums import EstadoConvenio, EstadoSolicitud, TipoSolicitante
from backend.models.rol import Rol
from backend.models.solicitud_convenio import SolicitudConvenio
from backend.models.transicion_estado_convenio import TransicionEstadoConvenio
from backend.models.usuario import Usuario
from backend.services import renovaciones
from backend.services.alertas_vencimiento import ServicioAlertasVencimiento
from backend.services.ciclo_vida_convenios import conciliar_estados
from backend.services.renovaciones import listar_seguimiento_renovaciones

HOY = date(2026, 10, 8)


@pytest.fixture
def preparar(db, gestor, crear_convenio):
    def crear(estado=EstadoConvenio.VIGENTE, dias=30):
        convenio = crear_convenio(
            gestor,
            fecha_inicio=date(2025, 1, 1),
            fecha_vencimiento=HOY + timedelta(days=dias) if dias is not None else None,
        )
        convenio.estado = estado.value
        db.commit()
        return convenio

    return crear


@pytest.mark.parametrize("estado", [EstadoConvenio.VIGENTE, EstadoConvenio.POR_VENCER])
@pytest.mark.parametrize(
    ("dias", "esperado"),
    [
        (121, "VIGENTE"),
        (120, "POR_VENCER"),
        (1, "POR_VENCER"),
        (0, "POR_VENCER"),
        (-1, "FINALIZADO"),
    ],
)
def test_limites_y_preservacion(db, preparar, estado, dias, esperado):
    convenio = preparar(estado, dias)
    antes = {
        col.name: getattr(convenio, col.name) for col in Convenio.__table__.columns
    }
    version = convenio.versiones[0]
    contenido = version.contenido
    historial = [item.id for item in convenio.historial_etapas]

    resultado = conciliar_estados(db, HOY)

    db.refresh(convenio)
    assert convenio.estado == esperado
    assert {
        col.name: getattr(convenio, col.name)
        for col in Convenio.__table__.columns
        if col.name not in {"estado", "actualizado_en"}
    } == {
        campo: valor
        for campo, valor in antes.items()
        if campo not in {"estado", "actualizado_en"}
    }
    assert version.contenido == contenido
    assert [item.id for item in convenio.historial_etapas] == historial
    eventos = db.scalars(
        select(TransicionEstadoConvenio).where(
            TransicionEstadoConvenio.convenio_id == convenio.id
        )
    ).all()
    assert len(eventos) == len(resultado.cambios) == int(estado.value != esperado)
    if eventos:
        evento = eventos[0]
        assert (evento.actor, evento.estado_anterior, evento.estado_nuevo) == (
            "SISTEMA",
            estado.value,
            esperado,
        )
        assert evento.fecha_referencia == HOY
        assert evento.fecha_vencimiento == antes["fecha_vencimiento"]
        assert evento.ejecutado_en.tzinfo is not None


@pytest.mark.parametrize(
    "estado",
    [
        EstadoConvenio.EN_TRAMITE,
        EstadoConvenio.CANCELADO,
        EstadoConvenio.RENOVADO,
        EstadoConvenio.FINALIZADO,
    ],
)
@pytest.mark.parametrize("dias", [-1, 0, 121, None])
def test_estados_protegidos(db, preparar, estado, dias):
    convenio = preparar(estado, dias)
    actualizado = convenio.actualizado_en
    assert conciliar_estados(db, HOY).cambios == ()
    db.refresh(convenio)
    assert convenio.estado == estado.value
    assert convenio.actualizado_en == actualizado


def test_ciclo_repetido_no_duplica_transiciones(db, preparar):
    convenio = preparar(dias=121)
    assert not conciliar_estados(db, HOY).cambios
    assert len(conciliar_estados(db, HOY + timedelta(days=1)).cambios) == 1
    assert not conciliar_estados(db, HOY + timedelta(days=1)).cambios
    assert len(conciliar_estados(db, HOY + timedelta(days=122)).cambios) == 1
    assert not conciliar_estados(db, HOY + timedelta(days=123)).cambios
    assert convenio.estado == "FINALIZADO"
    assert db.scalar(select(func.count()).select_from(TransicionEstadoConvenio)) == 2


@pytest.mark.parametrize("dias", [-1, 0, 1, None])
def test_legado_controlado(db, preparar, caplog, dias):
    convenio = preparar(EstadoConvenio.VENCIDO, dias)
    resultado = conciliar_estados(db, HOY)
    assert convenio.estado == ("FINALIZADO" if dias == -1 else "VENCIDO")
    assert len(resultado.cambios) == int(dias == -1)
    if dias is None:
        assert resultado.sin_fecha == (convenio.id,)
    elif dias >= 0:
        assert resultado.legado_inconsistente == (convenio.id,)
        assert "VENCIDO_SIN_FECHA_PASADA" in caplog.text


@pytest.mark.parametrize("estado", [EstadoConvenio.VIGENTE, EstadoConvenio.POR_VENCER])
def test_sin_fecha_se_registra_anomalia(db, preparar, caplog, estado):
    convenio = preparar(estado, None)
    resultado = conciliar_estados(db, HOY)
    assert resultado.sin_fecha == (convenio.id,)
    assert convenio.estado == estado.value
    assert "SIN_FECHA_VENCIMIENTO" in caplog.text


def test_simulacion_no_persiste(db, preparar):
    convenio = preparar(dias=-1)
    resultado = conciliar_estados(db, HOY, simular=True)
    assert len(resultado.cambios) == 1
    assert resultado.simulado
    db.refresh(convenio)
    assert convenio.estado == "VIGENTE"
    assert db.scalar(select(func.count()).select_from(TransicionEstadoConvenio)) == 0


def test_error_revierte_estados_y_bitacora(db, preparar, monkeypatch):
    convenios = [preparar(dias=-1), preparar(dias=30)]
    commit = db.commit

    def fallar():
        db.flush()
        assert (
            db.scalar(select(func.count()).select_from(TransicionEstadoConvenio)) == 2
        )
        raise RuntimeError("Fallo tras persistir cambios")

    with monkeypatch.context() as parche:
        parche.setattr(db, "commit", fallar)
        with pytest.raises(RuntimeError):
            conciliar_estados(db, HOY)
    assert db.commit == commit
    for convenio in convenios:
        db.refresh(convenio)
        assert convenio.estado == "VIGENTE"
    assert db.scalar(select(func.count()).select_from(TransicionEstadoConvenio)) == 0


def test_padre_finaliza_sin_cancelar_hijo(db, preparar):
    padre = preparar(dias=-1)
    hijo = preparar(EstadoConvenio.EN_TRAMITE, None)
    hijo.convenio_origen_id = padre.id
    db.commit()
    conciliar_estados(db, HOY)
    assert padre.estado == "FINALIZADO"
    assert hijo.estado == "EN_TRAMITE"
    assert hijo.convenio_origen_id == padre.id
    assert padre.id not in {
        item.convenio_id
        for item in ServicioAlertasVencimiento(db).listar_proximos_vencimientos(HOY)
    }
    seguimiento = listar_seguimiento_renovaciones(db, fecha_referencia=HOY)
    assert seguimiento[0].estado_seguimiento.value == "RENOVACION_INICIADA"


def test_vencimiento_exacto_alerta_y_al_dia_siguiente_finaliza(db, preparar):
    convenio = preparar(dias=0)
    conciliar_estados(db, HOY)
    assert convenio.id in {
        item.convenio_id
        for item in ServicioAlertasVencimiento(db).listar_proximos_vencimientos(HOY)
    }
    conciliar_estados(db, HOY + timedelta(days=1))
    assert convenio.estado == "FINALIZADO"
    assert not ServicioAlertasVencimiento(db).listar_proximos_vencimientos(
        HOY + timedelta(days=1)
    )
    assert not listar_seguimiento_renovaciones(
        db, fecha_referencia=HOY + timedelta(days=1)
    )


def test_get_no_concilia_ni_escribe(db, preparar, client, monkeypatch):
    convenio = preparar(dias=-1)
    sentencias = []

    def registrar(_conn, _cursor, sentencia, *_args):
        sentencias.append(sentencia)

    def prohibido(*args, **kwargs):
        raise AssertionError("GET intentó escribir")

    conexion = db.connection()
    event.listen(conexion, "before_cursor_execute", registrar)
    try:
        with monkeypatch.context() as parche:
            parche.setattr(db, "commit", prohibido)
            assert (
                client.get(f"/api/convenios/{convenio.id}").json()["estado"]
                == "VIGENTE"
            )
            assert client.get("/api/convenios/renovaciones").status_code == 200
            assert client.get("/api/convenios/alertas-vencimiento").status_code == 200
    finally:
        event.remove(conexion, "before_cursor_execute", registrar)
    assert not any(
        sql.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE"))
        for sql in sentencias
    )
    assert not db.scalars(select(TransicionEstadoConvenio)).all()


def test_fecha_por_defecto_usa_bogota(db, preparar, monkeypatch):
    class Reloj:
        @staticmethod
        def now(zona):
            assert zona.key == "America/Bogota"
            return datetime(2026, 10, 9, 2, 0, tzinfo=UTC).astimezone(zona)

    monkeypatch.setattr(renovaciones, "datetime", Reloj)
    convenio = preparar(dias=0)
    assert conciliar_estados(db).fecha_referencia == HOY
    assert convenio.estado == "POR_VENCER"


def test_conciliaciones_concurrentes_registran_una_transicion(db_engine):
    # Filas confirmadas, visibles para dos conexiones PostgreSQL independientes.
    with Session(db_engine) as sesion:
        rol = sesion.scalar(select(Rol).where(Rol.codigo == CodigoRol.GESTOR_ORI.value))
        usuario = Usuario(
            correo=f"ciclo-{uuid4().hex}@example.com",
            hash_contrasena="sin-login",
            nombre_completo="Prueba concurrente",
            rol=rol,
            tipo_usuario=TipoUsuario.INTERNO.value,
        )
        sesion.add(usuario)
        sesion.flush()
        solicitud = SolicitudConvenio(
            consecutivo=f"SOL-{uuid4().hex}",
            solicitante_id=usuario.id,
            tipo_solicitante=TipoSolicitante.INTERNO.value,
            estado=EstadoSolicitud.APROBADA.value,
        )
        sesion.add(solicitud)
        sesion.flush()
        convenio = Convenio(
            solicitud_id=solicitud.id,
            creado_por_id=usuario.id,
            estado="POR_VENCER",
            fecha_vencimiento=HOY - timedelta(days=1),
        )
        sesion.add(convenio)
        sesion.commit()
        ids = (convenio.id, solicitud.id, usuario.id)
    barrera = Barrier(2)

    def ejecutar(_):
        with Session(db_engine) as sesion:
            # Precargar también comprueba que el lock recarga objetos obsoletos.
            precargado = sesion.get(Convenio, ids[0])
            assert precargado.estado == "POR_VENCER"
            barrera.wait(timeout=10)
            return len(conciliar_estados(sesion, HOY).cambios)

    try:
        with ThreadPoolExecutor(max_workers=2) as ejecutor:
            assert sorted(ejecutor.map(ejecutar, range(2))) == [0, 1]
        with Session(db_engine) as sesion:
            assert sesion.get(Convenio, ids[0]).estado == "FINALIZADO"
            assert (
                sesion.scalar(
                    select(func.count())
                    .select_from(TransicionEstadoConvenio)
                    .where(TransicionEstadoConvenio.convenio_id == ids[0])
                )
                == 1
            )
    finally:
        with Session(db_engine) as sesion:
            sesion.execute(
                delete(TransicionEstadoConvenio).where(
                    TransicionEstadoConvenio.convenio_id == ids[0]
                )
            )
            sesion.execute(delete(Convenio).where(Convenio.id == ids[0]))
            sesion.execute(
                delete(SolicitudConvenio).where(SolicitudConvenio.id == ids[1])
            )
            sesion.execute(delete(Usuario).where(Usuario.id == ids[2]))
            sesion.commit()
