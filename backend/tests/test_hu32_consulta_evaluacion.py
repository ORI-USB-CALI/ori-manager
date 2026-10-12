"""HU-32 / CA-07 y CA-08 — Consulta de la evaluación desde el histórico.

Lo que se protege aquí es el aislamiento: cada convenio debe devolver su propia
evaluación y solo la suya.
"""

from sqlalchemy import func, select

from backend.models.evaluacion_convenio import EvaluacionConvenio
from backend.services.evaluaciones import ServicioEvaluaciones

EVALUACION_A = {
    "fue_funcional": True,
    "calificacion": 9,
    "observaciones": "A: la movilidad docente superó lo proyectado.",
}
EVALUACION_B = {
    "fue_funcional": False,
    "calificacion": 2,
    "observaciones": "B: la contraparte no habilitó los cupos acordados.",
}


def url(convenio_id: int) -> str:
    return f"/api/convenios/{convenio_id}/evaluacion"


def conteo_evaluaciones(db, convenio_id: int) -> int:
    return db.scalar(
        select(func.count())
        .select_from(EvaluacionConvenio)
        .where(EvaluacionConvenio.convenio_id == convenio_id)
    )


# ---- CA-08: solo la evaluación del convenio consultado -------------------


def test_cada_convenio_devuelve_solo_su_propia_evaluacion(
    db, client, gestor, crear_convenio_finalizado
):
    convenio_a = crear_convenio_finalizado(gestor)
    convenio_b = crear_convenio_finalizado(gestor)
    convenio_c = crear_convenio_finalizado(gestor)

    registrada_a = client.post(url(convenio_a.id), json=EVALUACION_A)
    registrada_b = client.post(url(convenio_b.id), json=EVALUACION_B)
    assert registrada_a.status_code == 201
    assert registrada_b.status_code == 201

    respuesta_a = client.get(url(convenio_a.id)).json()
    respuesta_b = client.get(url(convenio_b.id)).json()
    respuesta_c = client.get(url(convenio_c.id)).json()

    assert respuesta_a["evaluacion"] == registrada_a.json()
    assert respuesta_a["evaluacion"]["convenio_id"] == convenio_a.id
    assert respuesta_b["evaluacion"] == registrada_b.json()
    assert respuesta_b["evaluacion"]["convenio_id"] == convenio_b.id
    assert respuesta_c["evaluacion"] is None

    # Lo que no debe pasar: que los datos de un convenio asomen en otro.
    assert respuesta_a["evaluacion"]["id"] != respuesta_b["evaluacion"]["id"]
    assert (
        respuesta_b["evaluacion"]["observaciones"] != EVALUACION_A["observaciones"]
    )
    assert respuesta_b["evaluacion"]["calificacion"] != EVALUACION_A["calificacion"]
    assert (
        respuesta_a["evaluacion"]["observaciones"] != EVALUACION_B["observaciones"]
    )
    assert respuesta_a["evaluacion"]["calificacion"] != EVALUACION_B["calificacion"]
    assert respuesta_a["evaluacion"]["fue_funcional"] is True
    assert respuesta_b["evaluacion"]["fue_funcional"] is False


def test_el_servicio_aisla_la_evaluacion_por_convenio(
    db, client, gestor, crear_convenio_finalizado
):
    convenio_a = crear_convenio_finalizado(gestor)
    convenio_b = crear_convenio_finalizado(gestor)
    convenio_c = crear_convenio_finalizado(gestor)
    assert client.post(url(convenio_a.id), json=EVALUACION_A).status_code == 201
    assert client.post(url(convenio_b.id), json=EVALUACION_B).status_code == 201

    servicio = ServicioEvaluaciones(db)
    evaluacion_a = servicio.obtener(convenio_a.id)
    evaluacion_b = servicio.obtener(convenio_b.id)

    assert evaluacion_a is not None
    assert evaluacion_b is not None
    assert evaluacion_a.id != evaluacion_b.id
    assert evaluacion_a.convenio_id == convenio_a.id
    assert evaluacion_b.convenio_id == convenio_b.id
    assert servicio.obtener(convenio_c.id) is None
    assert conteo_evaluaciones(db, convenio_c.id) == 0


def test_evaluar_un_convenio_no_crea_filas_para_los_demas(
    db, client, gestor, crear_convenio_finalizado
):
    convenio_a = crear_convenio_finalizado(gestor)
    convenio_b = crear_convenio_finalizado(gestor)
    convenio_c = crear_convenio_finalizado(gestor)

    assert client.post(url(convenio_a.id), json=EVALUACION_A).status_code == 201

    assert conteo_evaluaciones(db, convenio_a.id) == 1
    assert conteo_evaluaciones(db, convenio_b.id) == 0
    assert conteo_evaluaciones(db, convenio_c.id) == 0
    assert client.get(url(convenio_b.id)).json()["evaluacion"] is None
    assert client.get(url(convenio_c.id)).json()["evaluacion"] is None


# ---- CA-07: el histórico muestra la información básica -------------------


def test_la_consulta_expone_la_informacion_basica_del_historico(
    db, client, gestor, convenio_finalizado
):
    assert (
        client.post(url(convenio_finalizado.id), json=EVALUACION_A).status_code == 201
    )

    respuesta = client.get(url(convenio_finalizado.id))

    assert respuesta.status_code == 200
    datos = respuesta.json()
    assert datos["evaluable"] is True
    assert datos["estado_convenio"] == "FINALIZADO"
    evaluacion = datos["evaluacion"]
    assert evaluacion["fue_funcional"] is EVALUACION_A["fue_funcional"]
    assert evaluacion["calificacion"] == EVALUACION_A["calificacion"]
    assert evaluacion["observaciones"] == EVALUACION_A["observaciones"]
    assert evaluacion["evaluado_por_id"] == gestor.id
    assert evaluacion["evaluado_por"]["nombre_completo"] == gestor.nombre_completo
    assert evaluacion["evaluado_por"]["correo"] == gestor.correo
    assert evaluacion["creado_en"] is not None
