"""HT-10: contrato del motor SQL que invocará Supabase Cron.

Estas pruebas usan el PostgreSQL de CI después de `alembic upgrade head`.
No requieren la extensión pg_cron ni ejecutan jobs automáticos.
"""

from datetime import timedelta

import pytest
from sqlalchemy import func, select, text

from backend.models.auditoria import Auditoria
from backend.models.enums import EstadoConvenio
from backend.models.transicion_estado_convenio import TransicionEstadoConvenio
from backend.services.ciclo_vida_convenios import conciliar_estados

SQL_CONCILIACION = text(
    "SELECT ori_internal.conciliar_estados_ht10("
    "CAST(:fecha AS date), CAST(:simular AS boolean))"
)


def _ejecutar(db, *, fecha=None, simular=True):
    return db.scalar(SQL_CONCILIACION, {"fecha": fecha, "simular": simular})


def _hoy_bogota(db):
    return db.scalar(text("SELECT (clock_timestamp() AT TIME ZONE 'America/Bogota')::date"))


def _crear(db, crear_convenio, gestor, *, dias, estado=EstadoConvenio.VIGENTE):
    convenio = crear_convenio(
        gestor,
        fecha_vencimiento=_hoy_bogota(db) + timedelta(days=dias),
    )
    convenio.estado = estado.value
    db.commit()
    return convenio


@pytest.mark.parametrize("dias,esperado", [
    (121, "VIGENTE"),
    (120, "POR_VENCER"),
    (30, "POR_VENCER"),
    (0, "POR_VENCER"),
    (-1, "FINALIZADO"),
])
def test_simulacion_sql_mismos_umbrales_que_python(
    db, gestor, crear_convenio, dias, esperado
):
    convenio = _crear(db, crear_convenio, gestor, dias=dias)
    hoy = _hoy_bogota(db)
    python = conciliar_estados(db, hoy, simular=True)
    sql = _ejecutar(db, fecha=hoy, simular=True)
    cambios_python = {
        (c.convenio_id, c.anterior, c.nuevo) for c in python.cambios
    }
    cambios_sql = {
        (c["convenio_id"], c["anterior"], c["nuevo"])
        for c in sql["transiciones"]
    }
    assert cambios_python == cambios_sql
    assert convenio.estado == EstadoConvenio.VIGENTE.value
    assert sql["fecha_referencia"] == hoy.isoformat()
    assert all(c["nuevo"] == esperado for c in sql["transiciones"])


def test_ejecucion_real_actualiza_estado_ambas_bitacoras_e_idempotencia(
    db, gestor, crear_convenio
):
    convenio = _crear(db, crear_convenio, gestor, dias=-1)
    primero = _ejecutar(db, simular=False)
    db.refresh(convenio)
    assert primero["cambios"] == 1
    assert convenio.estado == EstadoConvenio.FINALIZADO.value

    transicion = db.scalar(select(TransicionEstadoConvenio).where(
        TransicionEstadoConvenio.convenio_id == convenio.id
    ))
    assert transicion is not None
    assert (transicion.estado_anterior, transicion.estado_nuevo, transicion.actor) == (
        "VIGENTE", "FINALIZADO", "SISTEMA"
    )
    auditorias = db.scalars(select(Auditoria).where(
        Auditoria.entidad == "convenio",
        Auditoria.registro_id == convenio.id,
        Auditoria.evento == "CONCILIACION_ESTADO_AUTOMATICA",
    )).all()
    assert len(auditorias) == 1
    assert auditorias[0].usuario_id is None
    assert auditorias[0].ejecucion == "AUTOMATICA"
    assert auditorias[0].campo == "estado"

    segundo = _ejecutar(db, simular=False)
    assert segundo["cambios"] == 0
    assert db.scalar(select(func.count()).select_from(TransicionEstadoConvenio).where(
        TransicionEstadoConvenio.convenio_id == convenio.id
    )) == 1


def test_omite_estados_protegidos(db, gestor, crear_convenio):
    convenio = _crear(
        db, crear_convenio, gestor, dias=-1, estado=EstadoConvenio.RENOVADO
    )
    salida = _ejecutar(db, simular=False)
    db.refresh(convenio)
    assert salida["cambios"] == 0
    assert convenio.estado == EstadoConvenio.RENOVADO.value


def test_no_permite_escritura_con_fecha_inyectada(db):
    fecha = _hoy_bogota(db) - timedelta(days=50)
    with pytest.raises(Exception, match="las ejecuciones reales"), db.begin_nested():
        _ejecutar(db, fecha=fecha, simular=False)


def test_simulacion_nula_es_rechazada(db):
    with pytest.raises(Exception, match="p_simular debe ser true o false"), db.begin_nested():
        db.scalar(text(
            "SELECT ori_internal.conciliar_estados_ht10(NULL, NULL)"
        ))
