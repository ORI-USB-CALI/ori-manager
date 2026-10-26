"""HT-06 BE-02: asignación del código dentro de la transacción de formalización.

La cadena completa de firmas necesaria para formalizar ya está montada en
test_hu15_revision_final_firmas.py; se reutiliza en lugar de duplicarla, igual
que test_ht02_historial_solicitud.py reutiliza un helper de HU-07.

El generador en sí se prueba en test_ht06_generador_codigo.py y la concurrencia
en test_ht06_concurrencia_codigo.py.
"""

from datetime import datetime

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from test_hu15_revision_final_firmas import (
    _formalizar,
    _proceso_listo_para_formalizar,
)
from test_hu15_revision_final_firmas import escenario_final as _escenario_hu15

from backend.models.auditoria import Auditoria
from backend.models.contador_codigo_convenio import ContadorCodigoConvenio
from backend.models.convenio import Convenio
from backend.models.enums import EjecucionAuditoria, EstadoConvenio
from backend.models.proceso_firmas_convenio import ProcesoFirmasConvenio
from backend.models.version_convenio import VersionConvenio
from backend.services import firmas as servicio_firmas
from backend.services.vigencia import ZONA_HORARIA_DOMINIO

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


def _instante(anio: int, mes: int, dia: int, hora: int = 12, minuto: int = 0):
    """Instante en la zona del dominio, como lo devuelve el servicio real."""
    return datetime(anio, mes, dia, hora, minuto, tzinfo=ZONA_HORARIA_DOMINIO)


@pytest.fixture(autouse=True)
def anio_fijo(monkeypatch) -> None:
    """Fija el instante de formalización para que nada dependa del reloj.

    HT-06, corrección 2: la formalización toma un único instante y de él
    deriva el año institucional, así que se parchea ese instante y no una
    función de fecha aparte. Se parchea el módulo que lo importó, no `vigencia`.
    """
    monkeypatch.setattr(
        servicio_firmas, "instante_actual_dominio", lambda: _instante(ANIO, 6, 15)
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


@pytest.mark.parametrize(
    ("instante", "anio_esperado"),
    [
        # 31 de diciembre 23:59 en Bogotá: en UTC ya es el 1 de enero, pero el
        # código lleva el año que termina (RN-05).
        pytest.param(_instante(2098, 12, 31, 23, 59), 2098, id="ultimo-minuto-del-anio"),
        pytest.param(_instante(2099, 1, 1, 0, 0), 2099, id="primer-minuto-del-anio"),
    ],
)
def test_ca02_el_anio_sale_del_instante_de_formalizacion(
    client, db, escenario_final, monkeypatch, instante, anio_esperado
):
    monkeypatch.setattr(
        servicio_firmas, "instante_actual_dominio", lambda: instante
    )

    convenio = _formalizado(client, db, escenario_final)

    assert convenio.codigo.startswith(f"USB-ORI-{anio_esperado}-")
    # Corrección 2: el año del código y el instante registrado de formalización
    # salen de la misma lectura del reloj, así que no pueden discrepar.
    assert convenio.activado_en.astimezone(ZONA_HORARIA_DOMINIO).year == anio_esperado


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

    with monkeypatch.context() as inyeccion:
        inyeccion.setattr(
            db,
            "commit",
            lambda: (_ for _ in ()).throw(SQLAlchemyError("falla simulada")),
        )
        with pytest.raises(SQLAlchemyError):
            servicio_firmas.ServicioFirmas(db).formalizar(convenio_id, gestor)

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


def test_ca02_un_fallo_al_reservar_el_consecutivo_revierte_la_formalizacion(
    client, db, escenario_final, monkeypatch, gestor
):
    """Corrección 1: la reserva del consecutivo consulta la base y puede fallar.

    Antes la asignación quedaba fuera del `try` que protege el commit, así que
    una excepción salía sin revertir y dejaba la transacción abortada a merced
    de quien cerrara la sesión. Ahora revierte la formalización completa.
    """
    proceso = _proceso_listo_para_formalizar(client, db, escenario_final)
    proceso_id = int(proceso["id"])
    convenio_id = escenario_final["convenio"].id
    auditorias_antes = db.scalar(select(func.count()).select_from(Auditoria))
    estado_proceso_antes = db.get(ProcesoFirmasConvenio, proceso_id).estado

    def falla_la_reserva(*_args, **_kwargs):
        raise OperationalError("SELECT ...", {}, Exception("candado agotado"))

    # Contexto acotado: `monkeypatch.undo()` desharía también el parche del
    # instante que pone la fixture autouse, porque comparten instancia.
    with monkeypatch.context() as inyeccion:
        inyeccion.setattr(servicio_firmas, "asignar_codigo", falla_la_reserva)
        with pytest.raises(OperationalError):
            servicio_firmas.ServicioFirmas(db).formalizar(convenio_id, gestor)

    # La sesión quedó recuperada: se puede volver a consultar sin reabrirla.
    db.expire_all()
    convenio = db.get(Convenio, convenio_id)
    assert convenio.codigo is None
    assert convenio.estado == EstadoConvenio.EN_TRAMITE.value
    assert convenio.activado_en is None
    assert db.get(ProcesoFirmasConvenio, proceso_id).estado == estado_proceso_antes
    assert db.scalar(select(func.count()).select_from(Auditoria)) == auditorias_antes
    contador = db.scalar(
        select(ContadorCodigoConvenio).where(ContadorCodigoConvenio.anio == ANIO)
    )
    assert contador is None or contador.ultimo_consecutivo == 0


def test_ca02_tras_el_fallo_la_formalizacion_puede_reintentarse(
    client, db, escenario_final, monkeypatch, gestor
):
    """La sesión no queda inservible: el reintento funciona."""
    _proceso_listo_para_formalizar(client, db, escenario_final)
    convenio_id = escenario_final["convenio"].id

    def falla_la_reserva(*_args, **_kwargs):
        raise OperationalError("SELECT ...", {}, Exception("candado agotado"))

    with monkeypatch.context() as inyeccion:
        inyeccion.setattr(servicio_firmas, "asignar_codigo", falla_la_reserva)
        with pytest.raises(OperationalError):
            servicio_firmas.ServicioFirmas(db).formalizar(convenio_id, gestor)

    servicio_firmas.ServicioFirmas(db).formalizar(convenio_id, gestor)

    db.expire_all()
    convenio = db.get(Convenio, convenio_id)
    assert convenio.codigo == PRIMER_CODIGO
    assert convenio.estado == EstadoConvenio.VIGENTE.value


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
