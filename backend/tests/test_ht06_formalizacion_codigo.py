"""HT-06 BE-02: asignación del código dentro de la transacción de formalización.

La cadena completa de firmas necesaria para formalizar ya está montada en
test_hu15_revision_final_firmas.py; se reutiliza en lugar de duplicarla, igual
que test_ht02_historial_solicitud.py reutiliza un helper de HU-07.

El generador en sí se prueba en test_ht06_generador_codigo.py y la concurrencia
en test_ht06_concurrencia_codigo.py.
"""

from datetime import date

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from test_hu15_revision_final_firmas import (
    _formalizar,
    _proceso_listo_para_formalizar,
)
from test_hu15_revision_final_firmas import escenario_final as _escenario_hu15

from backend.models.auditoria import Auditoria
from backend.models.contador_codigo_convenio import ContadorCodigoConvenio
from backend.models.convenio import Convenio
from backend.models.enums import EjecucionAuditoria, EstadoConvenio
from backend.models.version_convenio import VersionConvenio
from backend.services import firmas as servicio_firmas

# Año propio, que ninguna otra prueba usa. El consecutivo es global por año y
# hay pruebas que formalizan con commits reales sobre `db_engine` (la de
# concurrencia de HU-15), cuyas consecutivos no se revierten al terminar. Sin un
# año propio estas aserciones dependerían del orden de ejecución de la suite.
ANIO = 2099
PRIMER_CODIGO = "USB-ORI-2099-00001"
SEGUNDO_CODIGO = "USB-ORI-2099-00002"

# Se reexpone con su nombre para que pytest la descubra en este módulo. El
# alias del import evita que los parámetros de las pruebas parezcan redefinirlo.
escenario_final = _escenario_hu15


@pytest.fixture(autouse=True)
def anio_fijo(monkeypatch) -> None:
    """Fija el año del dominio para que las aserciones no dependan del reloj.

    Se parchea el módulo que importó la función, no `vigencia`.
    """
    monkeypatch.setattr(
        servicio_firmas, "fecha_actual_dominio", lambda: date(ANIO, 6, 15)
    )


def _formalizado(client, db, escenario) -> Convenio:
    _proceso_listo_para_formalizar(client, db, escenario)
    respuesta = _formalizar(client, escenario)
    assert respuesta.status_code == 200, respuesta.text
    db.expire_all()
    return db.get(Convenio, escenario["convenio"].id)


def _auditorias_de_codigo(db, convenio_id) -> list[Auditoria]:
    return list(
        db.scalars(
            select(Auditoria)
            .where(
                Auditoria.entidad == "convenio",
                Auditoria.registro_id == convenio_id,
                Auditoria.campo == "codigo",
            )
            .order_by(Auditoria.id)
        ).all()
    )


# --- CA-02: generación automática al formalizar ---------------------------


def test_ca02_formalizar_asigna_el_codigo_institucional(client, db, escenario_final):
    assert escenario_final["convenio"].codigo is None

    convenio = _formalizado(client, db, escenario_final)

    assert convenio.codigo == PRIMER_CODIGO
    assert convenio.estado == EstadoConvenio.VIGENTE.value


def test_ca02_el_anio_es_el_calendario_de_bogota(
    client, db, escenario_final, monkeypatch
):
    # 31 de diciembre a las 23:00 en Bogotá son las 04:00 del 1 de enero en UTC.
    # El código debe llevar el año de Bogotá (RN-05), no el de `datetime.now(UTC)`
    # que la formalización ya usa para `activado_en`.
    monkeypatch.setattr(
        servicio_firmas, "fecha_actual_dominio", lambda: date(ANIO, 12, 31)
    )

    convenio = _formalizado(client, db, escenario_final)

    assert convenio.codigo.startswith(f"USB-ORI-{ANIO}-")
    # `activado_en` sigue siendo el instante real en UTC: el año del código no
    # sale de ahí.
    assert convenio.activado_en.year != ANIO


def test_rn13_formalizar_conserva_un_codigo_heredado(client, db, escenario_final):
    """Un convenio en trámite puede traer código de antes de CA-05.

    HU-10 permitía teclearlo, y esos convenios siguen en trámite. Formalizarlos
    no debe reemplazar su código ni gastar un consecutivo del año.
    """
    escenario_final["convenio"].codigo = "CONV-CARGADO-A-MANO"
    db.commit()

    convenio = _formalizado(client, db, escenario_final)

    assert convenio.codigo == "CONV-CARGADO-A-MANO"
    # No se estrenó el año: no hubo nada que numerar.
    assert (
        db.scalar(
            select(func.count())
            .select_from(ContadorCodigoConvenio)
            .where(ContadorCodigoConvenio.anio == ANIO)
        )
        == 0
    )


def test_rn13_un_codigo_heredado_no_deja_fila_de_auditoria_del_campo(
    client, db, escenario_final
):
    # Si el código no cambió, el efecto automático no inventa un registro.
    escenario_final["convenio"].codigo = "CONV-CARGADO-A-MANO"
    db.commit()

    convenio = _formalizado(client, db, escenario_final)

    assert _auditorias_de_codigo(db, convenio.id) == []


# --- CA-04, RN-08: persistencia e inmutabilidad --------------------------


def test_ca04_el_codigo_sobrevive_a_los_cambios_de_estado(
    client, db, escenario_final
):
    convenio = _formalizado(client, db, escenario_final)

    for estado in (
        EstadoConvenio.POR_VENCER,
        EstadoConvenio.VENCIDO,
        EstadoConvenio.FINALIZADO,
    ):
        convenio.estado = estado.value
        db.commit()
        db.expire_all()
        assert db.get(Convenio, convenio.id).codigo == PRIMER_CODIGO


def test_ca04_consultar_el_convenio_no_genera_un_codigo_nuevo(
    client, db, escenario_final
):
    convenio = _formalizado(client, db, escenario_final)

    for _ in range(3):
        respuesta = client.get(f"/api/convenios/{convenio.id}")
        assert respuesta.status_code == 200, respuesta.text
        assert respuesta.json()["codigo"] == PRIMER_CODIGO

    db.expire_all()
    contador = db.scalar(
        select(ContadorCodigoConvenio).where(ContadorCodigoConvenio.anio == ANIO)
    )
    assert contador.ultimo_consecutivo == 1


# --- CA-03, RN-07: consecutivo compartido -------------------------------


def test_ca03_dos_formalizaciones_consumen_consecutivos_distintos(
    client, db, escenario_final, gestor, crear_convenio
):
    primero = _formalizado(client, db, escenario_final)
    assert primero.codigo == PRIMER_CODIGO

    # Segundo convenio con otro alcance y otro tipo: el consecutivo es uno solo
    # para todos (RN-07), así que continúa la misma serie.
    segundo = crear_convenio(gestor)
    from backend.services.codigo_convenio import asignar_codigo

    assert asignar_codigo(db, segundo, ANIO) == SEGUNDO_CODIGO


# --- CA-09, RN-15: integridad transaccional -----------------------------


def test_ca09_un_fallo_en_el_commit_no_deja_codigo_ni_auditoria(
    client, db, escenario_final, monkeypatch, gestor
):
    _proceso_listo_para_formalizar(client, db, escenario_final)
    convenio_id = escenario_final["convenio"].id
    auditorias_antes = db.scalar(select(func.count()).select_from(Auditoria))

    monkeypatch.setattr(
        db,
        "commit",
        lambda: (_ for _ in ()).throw(SQLAlchemyError("falla simulada")),
    )
    with pytest.raises(SQLAlchemyError):
        servicio_firmas.ServicioFirmas(db).formalizar(convenio_id, gestor)
    monkeypatch.undo()

    db.expire_all()
    convenio = db.get(Convenio, convenio_id)
    assert convenio.codigo is None
    assert convenio.estado == EstadoConvenio.EN_TRAMITE.value
    assert db.scalar(select(func.count()).select_from(Auditoria)) == auditorias_antes
    # El consecutivo tampoco se gastó: la reversión lo libera.
    contador = db.scalar(
        select(ContadorCodigoConvenio).where(ContadorCodigoConvenio.anio == ANIO)
    )
    assert contador is None or contador.ultimo_consecutivo == 0


# --- CA-09: trazabilidad ------------------------------------------------


def test_ca09_el_codigo_queda_auditado_como_efecto_automatico(
    client, db, escenario_final, gestor
):
    convenio = _formalizado(client, db, escenario_final)

    auditorias = _auditorias_de_codigo(db, convenio.id)
    assert len(auditorias) == 1
    registro = auditorias[0]
    assert registro.valor_anterior is None
    assert registro.valor_nuevo == PRIMER_CODIGO
    # El cambio es automático, pero conserva a quien originó la formalización
    # (HT-09, CA-02 y CA-03): no se sustituye por un usuario ficticio.
    assert registro.ejecucion == EjecucionAuditoria.AUTOMATICA.value
    assert registro.usuario_id == gestor.id
    assert registro.evento == "CONVENIO_FORMALIZADO"


def test_ca09_la_formalizacion_declara_su_evento_de_negocio(
    client, db, escenario_final
):
    convenio = _formalizado(client, db, escenario_final)

    eventos = db.scalars(
        select(Auditoria.evento).where(
            Auditoria.entidad == "convenio",
            Auditoria.registro_id == convenio.id,
            Auditoria.evento == "CONVENIO_FORMALIZADO",
        )
    ).all()
    assert eventos, "la formalización debe declarar su evento de negocio"


# --- CA-09, RN-16: no se reescriben los snapshots aprobados -------------


def test_rn16_los_snapshots_previos_conservan_el_codigo_nulo(
    client, db, escenario_final
):
    convenio = _formalizado(client, db, escenario_final)

    versiones = db.scalars(
        select(VersionConvenio)
        .where(VersionConvenio.convenio_id == convenio.id)
        .order_by(VersionConvenio.numero)
    ).all()
    assert versiones, "el escenario debe tener al menos una versión formal"
    for version in versiones:
        # Las versiones se congelaron antes de existir el código y no se
        # completan retroactivamente.
        assert version.snapshot_metadata["codigo"] is None
