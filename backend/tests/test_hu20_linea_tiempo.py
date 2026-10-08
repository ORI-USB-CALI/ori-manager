from datetime import UTC, date, datetime, timedelta

from backend.core.roles import CodigoRol
from backend.models.convenio import Convenio
from backend.models.enums import EstadoConvenio
from backend.services.linea_tiempo import construir_linea_tiempo

HOY = date(2026, 10, 8)
INICIO = datetime(2026, 9, 1, 15, 0, tzinfo=UTC)
ACTIVACION = datetime(2026, 10, 1, 15, 0, tzinfo=UTC)


def _hitos(**datos):
    return [
        (hito.codigo, hito.estado, hito.fecha)
        for hito in construir_linea_tiempo(Convenio(**datos), HOY)
    ]


def test_en_tramite_muestra_activacion_pendiente():
    assert _hitos(
        estado=EstadoConvenio.EN_TRAMITE.value, elaboracion_iniciada_en=INICIO
    ) == [
        ("INICIO_ELABORACION", "COMPLETADO", INICIO),
        ("ACTIVACION", "PENDIENTE", None),
    ]


def test_vigente_muestra_los_tres_hitos_en_orden_y_vencimiento_futuro():
    vencimiento = date(2028, 9, 30)
    assert _hitos(
        estado=EstadoConvenio.VIGENTE.value,
        elaboracion_iniciada_en=INICIO,
        activado_en=ACTIVACION,
        fecha_vencimiento=vencimiento,
    ) == [
        ("INICIO_ELABORACION", "COMPLETADO", INICIO),
        ("ACTIVACION", "COMPLETADO", ACTIVACION),
        ("VENCIMIENTO", "PROGRAMADO", vencimiento),
    ]


def test_vencimiento_hoy_no_es_futuro():
    hitos = _hitos(
        estado=EstadoConvenio.VENCIDO.value,
        elaboracion_iniciada_en=INICIO,
        activado_en=ACTIVACION,
        fecha_vencimiento=HOY,
    )
    assert hitos[-1] == ("VENCIMIENTO", "COMPLETADO", HOY)


def test_cancelado_sin_activar_omite_activacion_y_vencimiento():
    # Nunca entrará en vigor: ni activación pendiente ni vencimiento programado.
    assert _hitos(
        estado=EstadoConvenio.CANCELADO.value,
        elaboracion_iniciada_en=INICIO,
        fecha_vencimiento=date(2028, 9, 30),
    ) == [("INICIO_ELABORACION", "COMPLETADO", INICIO)]


def test_api_gestor_consulta_linea_de_tiempo(client, db, gestor, crear_convenio):
    convenio = crear_convenio(gestor)
    convenio.fecha_vencimiento = datetime.now(UTC).date() + timedelta(days=400)
    db.commit()

    respuesta = client.get(f"/api/convenios/{convenio.id}/linea-tiempo")

    assert respuesta.status_code == 200, respuesta.text
    hitos = respuesta.json()
    assert [hito["codigo"] for hito in hitos][-2:] == ["ACTIVACION", "VENCIMIENTO"]
    assert hitos[-2]["estado"] == "PENDIENTE"
    assert hitos[-2]["fecha"] is None
    assert hitos[-1]["estado"] == "PROGRAMADO"


def test_api_solicitante_no_accede(
    client, crear_usuario, entrar_como, gestor, crear_convenio
):
    convenio = crear_convenio(gestor)
    entrar_como(crear_usuario(CodigoRol.SOLICITANTE_INTERNO))
    assert client.get(f"/api/convenios/{convenio.id}/linea-tiempo").status_code == 403


def test_api_revisor_fuera_de_alcance_recibe_404(
    client, crear_usuario, entrar_como, gestor, crear_convenio
):
    convenio = crear_convenio(gestor)  # en Elaboración: fuera del alcance del Revisor
    entrar_como(crear_usuario(CodigoRol.REVISOR_ORI))
    assert client.get(f"/api/convenios/{convenio.id}/linea-tiempo").status_code == 404
