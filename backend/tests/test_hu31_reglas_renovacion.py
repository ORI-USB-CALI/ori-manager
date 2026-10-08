from collections.abc import Callable
from datetime import date, timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.models.auditoria import Auditoria
from backend.models.convenio import Convenio
from backend.models.decision_no_renovacion import DecisionNoRenovacion
from backend.models.enums import EstadoConvenio, EstadoSeguimientoRenovacion
from backend.models.solicitud_convenio import SolicitudConvenio
from backend.models.usuario import Usuario
from backend.services.renovaciones import (
    calcular_estado_seguimiento,
    es_elegible_para_renovacion,
    existe_decision_no_renovacion_vigente,
    existe_renovacion_activa,
    puede_iniciar_renovacion,
)

FECHA_REFERENCIA = date(2026, 10, 7)


@pytest.fixture
def crear_convenio_renovable(
    db: Session, gestor: Usuario, crear_convenio
) -> Callable[..., Convenio]:
    def _crear(
        *,
        dias: int | None,
        estado: EstadoConvenio = EstadoConvenio.VIGENTE,
    ) -> Convenio:
        convenio = crear_convenio(
            gestor,
            fecha_vencimiento=(
                FECHA_REFERENCIA + timedelta(days=dias) if dias is not None else None
            ),
        )
        convenio.estado = estado.value
        db.commit()
        db.refresh(convenio)
        return convenio

    return _crear


@pytest.fixture
def crear_intento_renovacion(
    db: Session, gestor: Usuario, crear_convenio
) -> Callable[..., Convenio]:
    def _crear(
        origen: Convenio,
        estado: EstadoConvenio = EstadoConvenio.EN_TRAMITE,
    ) -> Convenio:
        intento = crear_convenio(gestor)
        intento.convenio_origen_id = origen.id
        intento.estado = estado.value
        db.commit()
        db.refresh(intento)
        return intento

    return _crear


def registrar_no_renovacion(
    db: Session, convenio: Convenio, usuario: Usuario
) -> DecisionNoRenovacion:
    assert convenio.fecha_vencimiento is not None
    decision = DecisionNoRenovacion(
        convenio_id=convenio.id,
        fecha_vencimiento_origen=convenio.fecha_vencimiento,
        decidida_por_id=usuario.id,
    )
    db.add(decision)
    db.commit()
    db.refresh(decision)
    return decision


@pytest.mark.parametrize(
    ("dias", "estado", "esperado"),
    [
        (120, EstadoConvenio.VIGENTE, True),
        (121, EstadoConvenio.VIGENTE, False),
        (0, EstadoConvenio.VIGENTE, True),
        (-1, EstadoConvenio.VIGENTE, False),
        (None, EstadoConvenio.VIGENTE, False),
        (30, EstadoConvenio.POR_VENCER, True),
        (30, EstadoConvenio.EN_TRAMITE, False),
        (30, EstadoConvenio.FINALIZADO, False),
        (30, EstadoConvenio.CANCELADO, False),
        (30, EstadoConvenio.RENOVADO, False),
    ],
)
def test_elegibilidad_temporal_y_por_estado(
    crear_convenio_renovable,
    dias: int | None,
    estado: EstadoConvenio,
    esperado: bool,
) -> None:
    convenio = crear_convenio_renovable(dias=dias, estado=estado)

    assert es_elegible_para_renovacion(convenio, FECHA_REFERENCIA) is esperado


def test_elegible_sin_hijo_ni_decision_esta_pendiente(
    db, crear_convenio_renovable
) -> None:
    convenio = crear_convenio_renovable(dias=60)

    assert calcular_estado_seguimiento(db, convenio, FECHA_REFERENCIA) == (
        EstadoSeguimientoRenovacion.PENDIENTE_DE_DECISION
    )


def test_hijo_en_tramite_representa_renovacion_iniciada(
    db, crear_convenio_renovable, crear_intento_renovacion
) -> None:
    convenio = crear_convenio_renovable(dias=60)
    crear_intento_renovacion(convenio)

    assert existe_renovacion_activa(db, convenio.id)
    assert calcular_estado_seguimiento(db, convenio, FECHA_REFERENCIA) == (
        EstadoSeguimientoRenovacion.RENOVACION_INICIADA
    )


def test_hijo_cancelado_no_es_activo_y_permanece_pendiente(
    db, crear_convenio_renovable, crear_intento_renovacion
) -> None:
    convenio = crear_convenio_renovable(dias=60)
    crear_intento_renovacion(convenio, EstadoConvenio.CANCELADO)

    assert not existe_renovacion_activa(db, convenio.id)
    assert calcular_estado_seguimiento(db, convenio, FECHA_REFERENCIA) == (
        EstadoSeguimientoRenovacion.PENDIENTE_DE_DECISION
    )


def test_decision_vigente_representa_no_se_renovara(
    db, gestor, crear_convenio_renovable
) -> None:
    convenio = crear_convenio_renovable(dias=60)
    registrar_no_renovacion(db, convenio, gestor)

    assert existe_decision_no_renovacion_vigente(db, convenio)
    assert calcular_estado_seguimiento(db, convenio, FECHA_REFERENCIA) == (
        EstadoSeguimientoRenovacion.NO_SE_RENOVARA
    )


def test_hijo_activo_tiene_prioridad_sobre_decision_negativa(
    db, gestor, crear_convenio_renovable, crear_intento_renovacion
) -> None:
    convenio = crear_convenio_renovable(dias=60)
    registrar_no_renovacion(db, convenio, gestor)
    crear_intento_renovacion(convenio)

    assert calcular_estado_seguimiento(db, convenio, FECHA_REFERENCIA) == (
        EstadoSeguimientoRenovacion.RENOVACION_INICIADA
    )


def test_decision_conserva_convenio_periodo_usuario_y_timestamp(
    db, gestor, crear_convenio_renovable
) -> None:
    convenio = crear_convenio_renovable(dias=90)

    decision = registrar_no_renovacion(db, convenio, gestor)

    assert decision.convenio_id == convenio.id
    assert decision.fecha_vencimiento_origen == convenio.fecha_vencimiento
    assert decision.decidida_por_id == gestor.id
    assert decision.decidida_en is not None


def test_no_permite_dos_decisiones_para_mismo_convenio_y_periodo(
    db, gestor, crear_convenio_renovable
) -> None:
    convenio = crear_convenio_renovable(dias=90)
    registrar_no_renovacion(db, convenio, gestor)
    duplicada = DecisionNoRenovacion(
        convenio_id=convenio.id,
        fecha_vencimiento_origen=convenio.fecha_vencimiento,
        decidida_por_id=gestor.id,
    )
    db.add(duplicada)

    with pytest.raises(IntegrityError):
        db.commit()


def test_decision_de_periodo_anterior_no_silencia_nuevo_periodo(
    db, gestor, crear_convenio_renovable
) -> None:
    convenio = crear_convenio_renovable(dias=90)
    decision = registrar_no_renovacion(db, convenio, gestor)

    convenio.fecha_vencimiento = FECHA_REFERENCIA + timedelta(days=30)
    db.commit()

    assert decision.fecha_vencimiento_origen == FECHA_REFERENCIA + timedelta(days=90)
    assert not existe_decision_no_renovacion_vigente(db, convenio)
    assert calcular_estado_seguimiento(db, convenio, FECHA_REFERENCIA) == (
        EstadoSeguimientoRenovacion.PENDIENTE_DE_DECISION
    )


def test_permite_varios_intentos_cancelados_historicos(
    db, crear_convenio_renovable, crear_intento_renovacion
) -> None:
    convenio = crear_convenio_renovable(dias=90)

    primero = crear_intento_renovacion(convenio, EstadoConvenio.CANCELADO)
    segundo = crear_intento_renovacion(convenio, EstadoConvenio.CANCELADO)

    assert primero.convenio_origen_id == convenio.id
    assert segundo.convenio_origen_id == convenio.id
    assert primero.id != segundo.id


def test_indice_parcial_impide_dos_intentos_activos_por_origen(
    db, gestor, crear_convenio, crear_convenio_renovable
) -> None:
    convenio = crear_convenio_renovable(dias=90)
    primer_intento = crear_convenio(gestor)
    primer_intento.convenio_origen_id = convenio.id
    db.commit()

    segundo_intento = crear_convenio(gestor)
    segundo_intento.convenio_origen_id = convenio.id

    with pytest.raises(IntegrityError):
        db.commit()


def test_calculo_es_read_only_y_sin_efectos_secundarios(
    db, crear_convenio_renovable, monkeypatch
) -> None:
    convenio = crear_convenio_renovable(dias=45)
    estado_inicial = convenio.estado
    actualizado_inicial = convenio.actualizado_en
    conteos_iniciales = {
        "auditorias": db.scalar(select(func.count()).select_from(Auditoria)),
        "solicitudes": db.scalar(
            select(func.count()).select_from(SolicitudConvenio)
        ),
        "convenios": db.scalar(select(func.count()).select_from(Convenio)),
    }

    def operacion_prohibida(*args, **kwargs) -> None:
        raise AssertionError("El cálculo de renovación intentó escribir")

    with monkeypatch.context() as contexto:
        contexto.setattr(db, "commit", operacion_prohibida)
        contexto.setattr(db, "flush", operacion_prohibida)
        estado = calcular_estado_seguimiento(db, convenio, FECHA_REFERENCIA)
        puede_iniciar = puede_iniciar_renovacion(db, convenio)

    db.expire(convenio)
    assert estado == EstadoSeguimientoRenovacion.PENDIENTE_DE_DECISION
    assert puede_iniciar
    assert convenio.estado == estado_inicial
    assert convenio.actualizado_en == actualizado_inicial
    assert db.scalar(select(func.count()).select_from(Auditoria)) == (
        conteos_iniciales["auditorias"]
    )
    assert db.scalar(select(func.count()).select_from(SolicitudConvenio)) == (
        conteos_iniciales["solicitudes"]
    )
    assert db.scalar(select(func.count()).select_from(Convenio)) == (
        conteos_iniciales["convenios"]
    )


@pytest.mark.parametrize(
    "estado",
    [
        EstadoConvenio.VIGENTE,
        EstadoConvenio.POR_VENCER,
        EstadoConvenio.VENCIDO,
    ],
)
def test_estados_permitidos_pueden_iniciar_renovacion(
    db, crear_convenio_renovable, estado: EstadoConvenio
) -> None:
    convenio = crear_convenio_renovable(dias=-10, estado=estado)

    assert puede_iniciar_renovacion(db, convenio)


def test_vencido_no_aparece_como_pendiente_del_panel(
    db, crear_convenio_renovable
) -> None:
    convenio = crear_convenio_renovable(dias=-1, estado=EstadoConvenio.VENCIDO)

    assert calcular_estado_seguimiento(db, convenio, FECHA_REFERENCIA) is None


@pytest.mark.parametrize(
    "estado",
    [EstadoConvenio.VIGENTE, EstadoConvenio.VENCIDO],
)
def test_decision_no_renovacion_no_bloquea_iniciar_renovacion(
    db, gestor, crear_convenio_renovable, estado: EstadoConvenio
) -> None:
    convenio = crear_convenio_renovable(dias=-1, estado=estado)
    registrar_no_renovacion(db, convenio, gestor)

    assert puede_iniciar_renovacion(db, convenio)


def test_hijo_en_tramite_impide_iniciar_otro_intento(
    db, crear_convenio_renovable, crear_intento_renovacion
) -> None:
    convenio = crear_convenio_renovable(dias=30)
    crear_intento_renovacion(convenio)

    assert not puede_iniciar_renovacion(db, convenio)


def test_hijo_cancelado_permite_iniciar_otro_intento(
    db, crear_convenio_renovable, crear_intento_renovacion
) -> None:
    convenio = crear_convenio_renovable(dias=30)
    crear_intento_renovacion(convenio, EstadoConvenio.CANCELADO)

    assert puede_iniciar_renovacion(db, convenio)


@pytest.mark.parametrize(
    "estado",
    [
        EstadoConvenio.RENOVADO,
        EstadoConvenio.EN_TRAMITE,
        EstadoConvenio.CANCELADO,
        EstadoConvenio.FINALIZADO,
    ],
)
def test_estados_terminales_o_en_tramite_no_pueden_ser_origen(
    db, crear_convenio_renovable, estado: EstadoConvenio
) -> None:
    convenio = crear_convenio_renovable(dias=30, estado=estado)

    assert not puede_iniciar_renovacion(db, convenio)


def test_fecha_nula_no_permite_iniciar_renovacion(
    db, crear_convenio_renovable
) -> None:
    convenio = crear_convenio_renovable(dias=None)

    assert not puede_iniciar_renovacion(db, convenio)
