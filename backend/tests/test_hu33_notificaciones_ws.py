import pytest
from starlette.websockets import WebSocketDisconnect

from backend.api.routers import notificaciones as notificaciones_router
from backend.models.enums import EntidadNotificacion, TipoNotificacion
from backend.services.notificaciones import ServicioNotificaciones
from backend.services.notificaciones_realtime import (
    gestor_notificaciones_tiempo_real,
)


def _pedir_ticket(client) -> str:
    respuesta = client.post("/api/notificaciones/ws-ticket")
    assert respuesta.status_code == 200, respuesta.text
    return respuesta.json()["ticket"]


def test_ws_sin_ticket_se_rechaza(client):
    with (
        pytest.raises(WebSocketDisconnect) as exc_info,
        client.websocket_connect("/api/notificaciones/ws"),
    ):
        pass
    assert exc_info.value.code == 1008


def test_ws_con_ticket_invalido_se_rechaza(client):
    with (
        pytest.raises(WebSocketDisconnect) as exc_info,
        client.websocket_connect("/api/notificaciones/ws?ticket=no-existe"),
    ):
        pass
    assert exc_info.value.code == 1008


def test_ws_ticket_requiere_autenticacion(client):
    respuesta = client.post("/api/notificaciones/ws-ticket")
    assert respuesta.status_code == 401


def test_ticket_es_de_un_solo_uso(client, gestor):
    ticket = _pedir_ticket(client)

    with client.websocket_connect(f"/api/notificaciones/ws?ticket={ticket}"):
        pass

    with (
        pytest.raises(WebSocketDisconnect) as exc_info,
        client.websocket_connect(f"/api/notificaciones/ws?ticket={ticket}"),
    ):
        pass
    assert exc_info.value.code == 1008


def test_ws_se_cierra_si_la_sesion_se_invalida_a_mitad_de_conexion(
    client, crear_usuario, entrar_como, sesiones, monkeypatch
):
    """Code review HU-33 PR, punto 3: el ticket solo prueba identidad al
    conectar, no sustituye el control de expiración de sesión. Si la
    sesión original se invalida (logout en otra pestaña, desactivación de
    cuenta, expiración), la próxima revalidación debe cortar la conexión.
    """
    monkeypatch.setattr(notificaciones_router, "INTERVALO_SONDEO_SEGUNDOS", 0.05)
    monkeypatch.setattr(notificaciones_router, "SONDEOS_POR_REVALIDACION", 1)
    usuario = crear_usuario()
    token = entrar_como(usuario)
    ticket = _pedir_ticket(client)

    with (
        pytest.raises(WebSocketDisconnect) as exc_info,
        client.websocket_connect(f"/api/notificaciones/ws?ticket={ticket}") as websocket,
    ):
        sesiones.invalidar(token)
        websocket.receive_text()

    assert exc_info.value.code == 1008


def test_ws_avisa_cuando_se_crea_una_notificacion(client, db, gestor, monkeypatch):
    monkeypatch.setattr(notificaciones_router, "INTERVALO_SONDEO_SEGUNDOS", 0.05)
    ticket = _pedir_ticket(client)

    with client.websocket_connect(
        f"/api/notificaciones/ws?ticket={ticket}"
    ) as websocket:
        servicio = ServicioNotificaciones(db)
        servicio.crear(
            gestor.id,
            TipoNotificacion.REVISION_JURIDICA_PENDIENTE,
            EntidadNotificacion.CONVENIO,
            1,
            "Tiene una revisión jurídica pendiente",
        )
        # El servicio nunca avisa por si solo: lo hace el llamador tras su
        # propio commit, para no avisar de un cambio que podria revertirse.
        servicio.avisar_tiempo_real()

        mensaje = websocket.receive_json()

    assert mensaje == {"evento": "notificaciones_actualizadas"}


def test_crear_sin_avisar_tiempo_real_no_incrementa_version(db, gestor):
    version_antes = gestor_notificaciones_tiempo_real.version_actual(gestor.id)

    ServicioNotificaciones(db).crear(
        gestor.id,
        TipoNotificacion.REVISION_JURIDICA_PENDIENTE,
        EntidadNotificacion.CONVENIO,
        2,
        "Tiene una revisión jurídica pendiente",
    )

    assert gestor_notificaciones_tiempo_real.version_actual(gestor.id) == version_antes


def test_avisar_tiempo_real_marca_cambio_solo_para_el_destinatario(
    db, gestor, crear_usuario
):
    otro = crear_usuario()
    version_gestor_antes = gestor_notificaciones_tiempo_real.version_actual(gestor.id)
    version_otro_antes = gestor_notificaciones_tiempo_real.version_actual(otro.id)

    servicio = ServicioNotificaciones(db)
    servicio.crear(
        otro.id,
        TipoNotificacion.REVISION_JURIDICA_PENDIENTE,
        EntidadNotificacion.CONVENIO,
        3,
        "Tiene una revisión jurídica pendiente",
    )
    servicio.avisar_tiempo_real()

    assert (
        gestor_notificaciones_tiempo_real.version_actual(gestor.id)
        == version_gestor_antes
    )
    assert gestor_notificaciones_tiempo_real.version_actual(otro.id) > version_otro_antes
