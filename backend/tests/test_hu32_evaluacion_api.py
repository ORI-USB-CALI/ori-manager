"""HU-32 — Contrato HTTP de los endpoints de evaluación de convenios.

Nivel API. Las reglas de dominio se cubren en test_hu32_reglas_evaluacion.py y
la matriz de autorización en test_hu32_evaluacion_permisos.py.
"""

from copy import deepcopy
from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select

from backend.models.auditoria import Auditoria
from backend.models.convenio import Convenio
from backend.models.enums import EstadoConvenio
from backend.models.evaluacion_convenio import EvaluacionConvenio

# Enumerados a mano a propósito: derivarlos de ESTADOS_EVALUABLES haría el test
# auto-referencial y ampliar la regla por error reduciría la cobertura en
# silencio en vez de fallar.
ESTADOS_NO_FINALIZADOS = [
    EstadoConvenio.EN_TRAMITE,
    EstadoConvenio.VIGENTE,
    EstadoConvenio.POR_VENCER,
    EstadoConvenio.VENCIDO,
    EstadoConvenio.RENOVADO,
    EstadoConvenio.CANCELADO,
]

OBSERVACIONES = "El convenio cumplió los objetivos pactados con la contraparte."

# Centinela para distinguir "campo ausente" de "campo en null".
AUSENTE = object()


def url(convenio_id: int) -> str:
    return f"/api/convenios/{convenio_id}/evaluacion"


def cuerpo(**cambios) -> dict:
    base = {
        "fue_funcional": True,
        "calificacion": 9,
        "observaciones": OBSERVACIONES,
    }
    datos = {**base, **cambios}
    return {campo: valor for campo, valor in datos.items() if valor is not AUSENTE}


def marca_iso(valor: datetime) -> str:
    """Serialización ISO-8601 en UTC, como la emite la API."""
    return valor.astimezone(UTC).isoformat().replace("+00:00", "Z")


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


# ---- CA-01, CA-03, CA-04, CA-05, CA-06: contrato del POST -----------------


def test_post_registra_la_evaluacion_y_devuelve_el_contrato_completo(
    db, client, gestor, convenio_finalizado
):
    respuesta = client.post(url(convenio_finalizado.id), json=cuerpo())

    assert respuesta.status_code == 201
    almacenada = db.scalar(
        select(EvaluacionConvenio).where(
            EvaluacionConvenio.convenio_id == convenio_finalizado.id
        )
    )
    assert almacenada is not None
    assert respuesta.json() == {
        "id": almacenada.id,
        "convenio_id": convenio_finalizado.id,
        "fue_funcional": True,
        "calificacion": 9,
        "observaciones": OBSERVACIONES,
        "evaluado_por_id": gestor.id,
        "evaluado_por": {
            "id": gestor.id,
            "nombre_completo": gestor.nombre_completo,
            "correo": gestor.correo,
        },
        "creado_en": marca_iso(almacenada.creado_en),
    }


# ---- CA-02: impedir evaluar un convenio que no está finalizado ------------


@pytest.mark.parametrize("estado", ESTADOS_NO_FINALIZADOS)
def test_post_sobre_convenio_no_finalizado_responde_409_sin_escribir_nada(
    db, client, gestor, crear_convenio, estado
):
    convenio = crear_convenio(gestor)
    convenio.estado = estado.value
    db.commit()
    antes_conteos = conteos(db)
    antes_convenio = snapshot(convenio)

    respuesta = client.post(url(convenio.id), json=cuerpo())

    assert respuesta.status_code == 409
    # El motivo lo lee el usuario final: debe decir qué falta y en qué estado está.
    detalle = respuesta.json()["detail"]
    assert "finalizado" in detalle.lower()
    assert estado.value in detalle
    assert conteos(db) == antes_conteos
    db.refresh(convenio)
    assert snapshot(convenio) == antes_convenio


# ---- CA-05: calificación de cumplimiento 1..10 (RN-08) -------------------


@pytest.mark.parametrize(
    "calificacion",
    [
        0,
        11,
        -1,
        1.5,
        "alta",
        None,
        pytest.param(AUSENTE, id="ausente"),
    ],
)
def test_calificacion_invalida_responde_422_sin_escribir_nada(
    db, client, gestor, convenio_finalizado, calificacion
):
    antes = conteos(db)

    respuesta = client.post(
        url(convenio_finalizado.id), json=cuerpo(calificacion=calificacion)
    )

    assert respuesta.status_code == 422
    assert conteos(db) == antes


@pytest.mark.parametrize("calificacion", [1, 10])
def test_calificacion_en_los_extremos_del_rango_se_acepta(
    client, gestor, crear_convenio_finalizado, calificacion
):
    # Un convenio por caso: la relación con la evaluación es 1:1.
    convenio = crear_convenio_finalizado(gestor)

    respuesta = client.post(url(convenio.id), json=cuerpo(calificacion=calificacion))

    assert respuesta.status_code == 201
    assert respuesta.json()["calificacion"] == calificacion


# ---- CA-04: comentarios sobre la experiencia ------------------------------


@pytest.mark.parametrize(
    "observaciones",
    ["", "   ", pytest.param(AUSENTE, id="ausente")],
)
def test_observaciones_vacias_responden_422_sin_escribir_nada(
    db, client, gestor, convenio_finalizado, observaciones
):
    antes = conteos(db)

    respuesta = client.post(
        url(convenio_finalizado.id), json=cuerpo(observaciones=observaciones)
    )

    assert respuesta.status_code == 422
    assert conteos(db) == antes


@pytest.mark.parametrize(
    "fue_funcional",
    [None, "quizas", 2, pytest.param(AUSENTE, id="ausente")],
)
def test_fue_funcional_invalido_responde_422_sin_escribir_nada(
    db, client, gestor, convenio_finalizado, fue_funcional
):
    """CA-03: el booleano es obligatorio también a nivel de contrato HTTP."""
    antes = conteos(db)

    respuesta = client.post(
        url(convenio_finalizado.id), json=cuerpo(fue_funcional=fue_funcional)
    )

    assert respuesta.status_code == 422
    assert conteos(db) == antes


def test_campo_desconocido_responde_422_sin_escribir_nada(
    db, client, gestor, convenio_finalizado
):
    antes = conteos(db)

    respuesta = client.post(
        url(convenio_finalizado.id),
        json=cuerpo(estado_convenio="VIGENTE"),
    )

    assert respuesta.status_code == 422
    assert conteos(db) == antes


# ---- CA-07: consultar la evaluación desde el histórico --------------------


def test_get_devuelve_el_envolvente_con_la_evaluacion_registrada(
    client, gestor, convenio_finalizado
):
    registrada = client.post(url(convenio_finalizado.id), json=cuerpo()).json()

    respuesta = client.get(url(convenio_finalizado.id))

    assert respuesta.status_code == 200
    assert respuesta.json() == {
        "evaluable": True,
        "estado_convenio": "FINALIZADO",
        "evaluacion": registrada,
    }


def test_get_sin_evaluacion_devuelve_evaluable_y_evaluacion_nula(
    client, gestor, convenio_finalizado
):
    respuesta = client.get(url(convenio_finalizado.id))

    assert respuesta.status_code == 200
    assert respuesta.json() == {
        "evaluable": True,
        "estado_convenio": "FINALIZADO",
        "evaluacion": None,
    }


def test_get_sobre_convenio_vigente_devuelve_no_evaluable(
    db, client, gestor, crear_convenio
):
    convenio = crear_convenio(gestor)
    convenio.estado = EstadoConvenio.VIGENTE.value
    db.commit()

    respuesta = client.get(url(convenio.id))

    assert respuesta.status_code == 200
    assert respuesta.json() == {
        "evaluable": False,
        "estado_convenio": "VIGENTE",
        "evaluacion": None,
    }


def test_get_de_convenio_inexistente_responde_404(client, gestor):
    assert client.get(url(2_000_000_000)).status_code == 404


def test_post_sobre_convenio_inexistente_responde_404_sin_escribir_nada(
    db, client, gestor
):
    antes = conteos(db)

    assert client.post(url(2_000_000_000), json=cuerpo()).status_code == 404
    assert conteos(db) == antes


# ---- Cardinalidad 1:1 sobre HTTP -----------------------------------------


def test_segundo_post_responde_409_y_conserva_la_evaluacion_original(
    db, client, gestor, convenio_finalizado
):
    original = client.post(url(convenio_finalizado.id), json=cuerpo()).json()
    antes = conteos(db)

    respuesta = client.post(
        url(convenio_finalizado.id),
        json=cuerpo(
            fue_funcional=False,
            calificacion=2,
            observaciones="Intento de sobrescribir la evaluación",
        ),
    )

    assert respuesta.status_code == 409
    assert "evaluación" in respuesta.json()["detail"].lower()
    assert conteos(db) == antes
    almacenada = db.scalar(
        select(EvaluacionConvenio).where(
            EvaluacionConvenio.convenio_id == convenio_finalizado.id
        )
    )
    db.refresh(almacenada)
    assert almacenada.id == original["id"]
    assert almacenada.fue_funcional is True
    assert almacenada.calificacion == 9
    assert almacenada.observaciones == OBSERVACIONES
    assert almacenada.evaluado_por_id == gestor.id
    assert marca_iso(almacenada.creado_en) == original["creado_en"]
    assert client.get(url(convenio_finalizado.id)).json()["evaluacion"] == original
