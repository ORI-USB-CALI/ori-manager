"""HU-32 — Reglas de dominio de la evaluación de convenios.

Nivel servicio, sin HTTP. La capa de API se cubre en test_hu32_evaluacion_api.py.
"""

from copy import deepcopy

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from backend.models.auditoria import Auditoria
from backend.models.convenio import Convenio
from backend.models.enums import AccionAuditoria, EstadoConvenio
from backend.models.evaluacion_convenio import EvaluacionConvenio
from backend.schemas.evaluacion import EvaluacionConvenioCrear
from backend.services.convenios import ConvenioDuplicado, ConvenioNoEncontrado
from backend.services.evaluaciones import (
    ESTADOS_EVALUABLES,
    ConvenioNoEvaluable,
    ServicioEvaluaciones,
    es_evaluable,
)

# Enumerados a mano a propósito: derivarlos de ESTADOS_EVALUABLES haría el test
# auto-referencial y ampliar la regla por error reduciría la cobertura en
# silencio en vez de fallar.
ESTADOS_NO_EVALUABLES = [
    EstadoConvenio.EN_TRAMITE,
    EstadoConvenio.VIGENTE,
    EstadoConvenio.POR_VENCER,
    EstadoConvenio.VENCIDO,
    EstadoConvenio.RENOVADO,
    EstadoConvenio.CANCELADO,
]


def datos(**cambios) -> EvaluacionConvenioCrear:
    base = {
        "fue_funcional": True,
        "calificacion": 8,
        "observaciones": "El convenio cumplió los objetivos pactados.",
    }
    return EvaluacionConvenioCrear.model_validate({**base, **cambios})


def snapshot(convenio: Convenio) -> dict:
    return {
        col.name: deepcopy(getattr(convenio, col.name))
        for col in Convenio.__table__.columns
    }


def conteos(db) -> dict:
    return {
        modelo.__tablename__: db.scalar(select(func.count()).select_from(modelo))
        for modelo in (EvaluacionConvenio, Auditoria, Convenio)
    }


# ---- CA-01: evaluar un convenio finalizado --------------------------------


def test_registrar_persiste_la_evaluacion_del_convenio_finalizado(
    db, gestor, convenio_finalizado
):
    evaluacion = ServicioEvaluaciones(db).registrar(
        convenio_finalizado.id, datos(), gestor
    )

    almacenada = db.scalar(
        select(EvaluacionConvenio).where(
            EvaluacionConvenio.convenio_id == convenio_finalizado.id
        )
    )
    assert almacenada is not None
    assert almacenada.id == evaluacion.id
    assert almacenada.calificacion == 8
    assert almacenada.observaciones == "El convenio cumplió los objetivos pactados."


def test_la_regla_de_elegibilidad_esta_fijada_en_finalizado():
    """Ampliar los estados evaluables debe ser deliberado y visible.

    El líder técnico dejó pendiente revisar cuándo se permite evaluar; mientras
    tanto este test obliga a que cualquier cambio pase por aquí.
    """
    assert ESTADOS_EVALUABLES == frozenset({EstadoConvenio.FINALIZADO})
    assert set(ESTADOS_NO_EVALUABLES) == set(EstadoConvenio) - ESTADOS_EVALUABLES


def test_solo_finalizado_es_evaluable(db, gestor, crear_convenio_finalizado):
    convenio = crear_convenio_finalizado(gestor)
    assert es_evaluable(convenio) is True

    for estado in ESTADOS_NO_EVALUABLES:
        convenio.estado = estado.value
        assert es_evaluable(convenio) is False


# ---- CA-02: impedir evaluación antes de finalizar -------------------------


@pytest.mark.parametrize("estado", ESTADOS_NO_EVALUABLES)
def test_estado_no_finalizado_rechaza_la_evaluacion_sin_escribir_nada(
    db, gestor, crear_convenio, estado
):
    convenio = crear_convenio(gestor)
    convenio.estado = estado.value
    db.commit()
    antes_conteos = conteos(db)
    antes_convenio = snapshot(convenio)

    with pytest.raises(ConvenioNoEvaluable) as excinfo:
        ServicioEvaluaciones(db).registrar(convenio.id, datos(), gestor)

    # El motivo se le muestra al usuario final: debe decir qué pasa y por qué.
    assert "finalizado" in str(excinfo.value).lower()
    assert estado.value in str(excinfo.value)
    assert conteos(db) == antes_conteos
    db.refresh(convenio)
    assert snapshot(convenio) == antes_convenio


# ---- CA-03: registrar si fue funcional ------------------------------------


@pytest.mark.parametrize("fue_funcional", [True, False])
def test_fue_funcional_se_conserva_en_ambos_valores(
    db, gestor, crear_convenio_finalizado, fue_funcional
):
    convenio = crear_convenio_finalizado(gestor)

    ServicioEvaluaciones(db).registrar(
        convenio.id, datos(fue_funcional=fue_funcional), gestor
    )

    almacenada = db.scalar(
        select(EvaluacionConvenio).where(
            EvaluacionConvenio.convenio_id == convenio.id
        )
    )
    # Importa distinguir False de None: un nulo haría inútil el histórico.
    assert almacenada.fue_funcional is fue_funcional


# ---- CA-04: comentarios sobre la experiencia ------------------------------


def test_observaciones_se_conservan_literalmente(db, gestor, convenio_finalizado):
    comentario = (
        "Hubo dificultades de coordinación en el primer año.\n"
        "La contraparte respondió con agilidad; se recomienda señalización previa."
    )

    ServicioEvaluaciones(db).registrar(
        convenio_finalizado.id, datos(observaciones=comentario), gestor
    )

    # Filtrado por convenio a propósito: sin el where, la consulta toma la
    # primera fila de la tabla y la prueba depende de que esté vacía.
    almacenada = db.scalar(
        select(EvaluacionConvenio).where(
            EvaluacionConvenio.convenio_id == convenio_finalizado.id
        )
    )
    assert almacenada.observaciones == comentario


def test_observaciones_se_normalizan_y_no_admiten_vacio():
    assert datos(observaciones="  Cumplió lo pactado.  ").observaciones == (
        "Cumplió lo pactado."
    )
    with pytest.raises(ValueError):
        datos(observaciones="   ")


# ---- CA-05: calificación de cumplimiento 1..10 (RN-08) --------------------


@pytest.mark.parametrize("calificacion", [1, 10])
def test_calificacion_acepta_los_extremos_del_rango(
    db, gestor, crear_convenio_finalizado, calificacion
):
    convenio = crear_convenio_finalizado(gestor)

    evaluacion = ServicioEvaluaciones(db).registrar(
        convenio.id, datos(calificacion=calificacion), gestor
    )

    assert evaluacion.calificacion == calificacion


@pytest.mark.parametrize("calificacion", [0, 11, -1])
def test_pydantic_rechaza_calificaciones_fuera_de_rango(calificacion):
    with pytest.raises(ValueError):
        datos(calificacion=calificacion)


@pytest.mark.parametrize("calificacion", [0, 11])
def test_la_base_de_datos_tambien_rechaza_calificaciones_fuera_de_rango(
    db, gestor, convenio_finalizado, calificacion
):
    """Mitad en BD de la doble validación: se salta Pydantic a propósito."""
    db.add(
        EvaluacionConvenio(
            convenio_id=convenio_finalizado.id,
            evaluado_por_id=gestor.id,
            fue_funcional=True,
            calificacion=calificacion,
            observaciones="Fuera de rango",
        )
    )
    with pytest.raises(IntegrityError):
        db.flush()
    db.rollback()


# ---- CA-06: usuario responsable, fecha y trazabilidad ---------------------


def test_registra_usuario_responsable_fecha_y_auditoria(
    db, gestor, convenio_finalizado
):
    evaluacion = ServicioEvaluaciones(db).registrar(
        convenio_finalizado.id, datos(), gestor
    )

    assert evaluacion.evaluado_por_id == gestor.id
    assert evaluacion.evaluado_por.id == gestor.id
    assert evaluacion.creado_en is not None
    assert evaluacion.creado_en.tzinfo is not None

    auditoria = db.scalar(
        select(Auditoria).where(
            Auditoria.entidad == "evaluacion_convenio",
            Auditoria.registro_id == evaluacion.id,
        )
    )
    assert auditoria is not None
    assert auditoria.usuario_id == gestor.id
    assert auditoria.accion == AccionAuditoria.INSERT.value


# ---- Cardinalidad 1:1 e integridad transaccional --------------------------


def test_segunda_evaluacion_del_mismo_convenio_es_rechazada(
    db, gestor, convenio_finalizado
):
    primera = ServicioEvaluaciones(db).registrar(
        convenio_finalizado.id, datos(), gestor
    )
    antes = conteos(db)

    with pytest.raises(ConvenioDuplicado):
        ServicioEvaluaciones(db).registrar(
            convenio_finalizado.id,
            datos(calificacion=2, observaciones="Intento de sobrescribir"),
            gestor,
        )

    assert conteos(db) == antes
    db.refresh(primera)
    assert primera.calificacion == 8
    assert primera.observaciones == "El convenio cumplió los objetivos pactados."


def test_la_evaluacion_sobrevive_a_un_cambio_de_estado_posterior(
    db, gestor, convenio_finalizado
):
    """La evaluación es histórico: una renovación posterior no debe borrarla."""
    evaluacion = ServicioEvaluaciones(db).registrar(
        convenio_finalizado.id, datos(), gestor
    )

    convenio_finalizado.estado = EstadoConvenio.RENOVADO.value
    db.commit()

    almacenada = db.scalar(
        select(EvaluacionConvenio).where(
            EvaluacionConvenio.convenio_id == convenio_finalizado.id
        )
    )
    assert almacenada is not None
    assert almacenada.id == evaluacion.id
    assert almacenada.calificacion == 8
    assert almacenada.observaciones == "El convenio cumplió los objetivos pactados."


def test_convenio_inexistente_levanta_no_encontrado(db, gestor):
    with pytest.raises(ConvenioNoEncontrado):
        ServicioEvaluaciones(db).registrar(999999, datos(), gestor)


def test_error_al_confirmar_revierte_la_evaluacion_completa(
    db, gestor, convenio_finalizado, monkeypatch
):
    antes = conteos(db)
    monkeypatch.setattr(
        db, "commit", lambda: (_ for _ in ()).throw(SQLAlchemyError("falla"))
    )

    with pytest.raises(SQLAlchemyError):
        ServicioEvaluaciones(db).registrar(convenio_finalizado.id, datos(), gestor)

    monkeypatch.undo()
    # Ni la evaluación ni su fila de auditoría deben quedar a medias.
    assert conteos(db) == antes
