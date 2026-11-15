"""Decisiones del cierre tecnico de HT-17 y compatibilidad CA-06."""

from datetime import UTC, date, datetime, timedelta

import pytest

from backend.models.enums import EstadoConvenio
from backend.services import convenios, vigencia
from backend.services.alertas_vencimiento import ServicioAlertasVencimiento
from backend.services.ciclo_vida_convenios import conciliar_estados
from backend.services.vigencia import preparar_vigencia, vencimiento_esperado


@pytest.mark.parametrize(
    "inicio,meses,fin",
    [
        (date(2027, 1, 1), 12, date(2027, 12, 31)),
        (date(2027, 1, 15), 4, date(2027, 5, 14)),
        (date(2027, 1, 31), 4, date(2027, 5, 31)),
        (date(2026, 10, 31), 4, date(2027, 2, 28)),
        (date(2028, 2, 29), 12, date(2029, 2, 28)),
    ],
)
def test_ejemplos_obligatorios(inicio, meses, fin):
    assert preparar_vigencia(inicio, meses, None, inicio) == (fin, [])


@pytest.mark.parametrize("duracion", [0, 1, 2, 3])
def test_minimo_incluso_en_borrador(duracion):
    _, errores = preparar_vigencia(None, duracion, None, date(2027, 1, 1))
    assert [e.campo for e in errores] == ["duracion_meses"]


def test_borrador_parcial_y_desbordamiento():
    hoy = date(2027, 1, 1)
    assert preparar_vigencia(None, None, None, hoy) == (None, [])
    assert preparar_vigencia(hoy, None, None, hoy) == (None, [])
    _, errores = preparar_vigencia(hoy, 10**9, None, hoy)
    assert [e.campo for e in errores] == ["duracion_meses"]


@pytest.mark.parametrize(
    "instante,acepta",
    [
        (datetime(2027, 1, 2, 4, 59, tzinfo=UTC), True),
        (datetime(2027, 1, 2, 5, tzinfo=UTC), False),
    ],
)
def test_inicio_antes_y_despues_de_medianoche(monkeypatch, instante, acepta):
    monkeypatch.setattr(
        vigencia,
        "instante_actual_dominio",
        lambda: instante.astimezone(vigencia.ZONA_HORARIA_DOMINIO),
    )
    _, errores = preparar_vigencia(
        date(2027, 1, 1), 4, None, vigencia.fecha_actual_dominio()
    )
    assert (not errores) == acepta


def test_api_calcula_y_rechaza_sin_cambiar_datos(client, db, gestor, monkeypatch):
    monkeypatch.setattr(convenios, "fecha_actual_dominio", lambda: date(2031, 1, 1))
    creado = client.post(
        "/api/convenios/manual",
        json={"fecha_inicio": "2031-01-31", "duracion_meses": 4},
    )
    assert creado.status_code == 201, creado.text
    datos = creado.json()
    assert datos["fecha_vencimiento"] == "2031-05-31"
    ruta = f"/api/convenios/{datos['id']}"
    rechazo = client.patch(
        ruta, json={"duracion_meses": 5, "fecha_vencimiento": "2031-06-30"}
    )
    # Inicio a fin de mes: junio 30 es coherente para cinco meses.
    assert rechazo.status_code == 200
    rechazo = client.patch(
        ruta, json={"duracion_meses": 6, "fecha_vencimiento": "2031-06-30"}
    )
    assert rechazo.status_code == 422
    consultado = client.get(ruta).json()
    assert consultado["duracion_meses"] == 5
    assert consultado["fecha_inicio"] == "2031-01-31"
    assert consultado["fecha_vencimiento"] == "2031-06-30"


def test_historico_corto_finaliza_y_llega_a_firmas_sin_recalculo(
    client, db, convenio_listo
):
    convenio_listo.duracion_meses = 1
    convenio_listo.fecha_inicio = date(2020, 1, 1)
    convenio_listo.fecha_vencimiento = date(2099, 1, 1)
    convenio_listo.vigencia_ht17 = False
    db.commit()
    ruta = f"/api/convenios/{convenio_listo.id}"
    assert client.get(ruta + "/elaboracion/validacion").json()["completo"] is True
    respuesta = client.post(ruta + "/elaboracion/finalizar")
    assert respuesta.status_code == 200, respuesta.text
    assert client.get(ruta).json()["fecha_vencimiento"] == "2099-01-01"


def test_alertas_y_ht10_consumen_vencimiento_calculado(db, gestor, crear_convenio):
    fin = vencimiento_esperado(date(2031, 1, 31), 4)
    convenio = crear_convenio(
        gestor, fecha_inicio=date(2031, 1, 31), duracion_meses=4, fecha_vencimiento=fin
    )
    convenio.estado = EstadoConvenio.VIGENTE.value
    db.commit()
    alertas = ServicioAlertasVencimiento(db).listar_proximos_vencimientos(fin)
    assert next(a for a in alertas if a.convenio_id == convenio.id).dias_restantes == 0
    conciliar_estados(db, fin)
    db.refresh(convenio)
    assert convenio.estado == EstadoConvenio.POR_VENCER.value
    conciliar_estados(db, fin + timedelta(days=1))
    db.refresh(convenio)
    assert convenio.estado == EstadoConvenio.FINALIZADO.value
    assert convenio.fecha_vencimiento == fin


def test_borrador_nuevo_exige_fechas_antes_de_finalizar(client, gestor):
    respuesta = client.post("/api/convenios/manual", json={"objeto": "Borrador parcial", "duracion_meses": 4})
    assert respuesta.status_code == 201
    ruta = f"/api/convenios/{respuesta.json()['id']}"
    assert respuesta.json()["fecha_vencimiento"] is None
    faltantes = client.get(ruta + "/elaboracion/validacion").json()["faltantes"]
    assert {"fecha_inicio", "fecha_vencimiento"} <= {f["campo"] for f in faltantes}
    assert client.post(ruta + "/elaboracion/finalizar").status_code == 422


def test_factory_nueva_aplica_ht17_y_carga_historica_es_explicita(gestor, crear_convenio):
    from backend.services.convenios import VigenciaInvalida

    nuevo = crear_convenio(gestor, duracion_meses=4)
    assert nuevo.vigencia_ht17 is True
    assert nuevo.fecha_inicio == convenios.fecha_actual_dominio()
    assert nuevo.fecha_vencimiento == vencimiento_esperado(nuevo.fecha_inicio, 4)
    with pytest.raises(VigenciaInvalida):
        crear_convenio(gestor, fecha_inicio=date(2020, 1, 1), duracion_meses=1)
    historico = crear_convenio(
        gestor, historico=True, fecha_inicio=date(2020, 1, 1),
        fecha_vencimiento=date(2020, 2, 1), duracion_meses=1,
    )
    assert historico.vigencia_ht17 is False
    assert historico.fecha_vencimiento == date(2020, 2, 1)
