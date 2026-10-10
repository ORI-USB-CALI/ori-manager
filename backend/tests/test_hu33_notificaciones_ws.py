import pytest
from starlette.testclient import WebSocketDenialResponse

from backend.api.routers import notificaciones as notificaciones_router
from backend.models.enums import EntidadNotificacion, TipoNotificacion
from backend.services.notificaciones import ServicioNotificaciones
from backend.services.notificaciones_realtime import (
    gestor_notificaciones_tiempo_real,
)


def test_ws_requiere_autenticacion(client):
    with (
        pytest.raises(WebSocketDenialResponse) as exc_info,
        client.websocket_connect("/api/notificaciones/ws"),
    ):
        pass
    assert exc_info.value.status_code == 401


def test_ws_avisa_cuando_se_crea_una_notificacion(client, db, gestor, monkeypatch):
    monkeypatch.setattr(notificaciones_router, "INTERVALO_SONDEO_SEGUNDOS", 0.05)

    with client.websocket_connect("/api/notificaciones/ws") as websocket:
        ServicioNotificaciones(db).crear(
            gestor.id,
            TipoNotificacion.REVISION_JURIDICA_PENDIENTE,
            EntidadNotificacion.CONVENIO,
            1,
            "Tiene una revisión jurídica pendiente",
        )

        mensaje = websocket.receive_json()

    assert mensaje == {"evento": "notificaciones_actualizadas"}


def test_crear_notificacion_solo_marca_cambio_para_su_destinatario(
    db, gestor, crear_usuario
):
    otro = crear_usuario()
    version_gestor_antes = gestor_notificaciones_tiempo_real.version_actual(gestor.id)

    ServicioNotificaciones(db).crear(
        otro.id,
        TipoNotificacion.REVISION_JURIDICA_PENDIENTE,
        EntidadNotificacion.CONVENIO,
        1,
        "Tiene una revisión jurídica pendiente",
    )

    assert (
        gestor_notificaciones_tiempo_real.version_actual(gestor.id)
        == version_gestor_antes
    )
    assert gestor_notificaciones_tiempo_real.version_actual(otro.id) > 0
