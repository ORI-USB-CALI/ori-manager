from sqlalchemy.orm import Session

from backend.models.enums import EntidadNotificacion, TipoNotificacion
from backend.models.usuario import Usuario
from backend.services.notificaciones import ServicioNotificaciones

URL_NOTIFICACIONES = "/api/notificaciones"


def _crear_notificacion(db: Session, usuario: Usuario, entidad_id: int = 1):
    return ServicioNotificaciones(db).crear(
        usuario.id,
        TipoNotificacion.REVISION_JURIDICA_PENDIENTE,
        EntidadNotificacion.CONVENIO,
        entidad_id,
        "Tiene una revisión jurídica pendiente",
    )


def test_requiere_autenticacion(client):
    respuesta = client.get(URL_NOTIFICACIONES)
    assert respuesta.status_code == 401


def test_lista_solo_las_notificaciones_propias(client, db, gestor, crear_usuario, entrar_como):
    otro = crear_usuario()
    _crear_notificacion(db, gestor, entidad_id=1)
    _crear_notificacion(db, otro, entidad_id=2)

    respuesta = client.get(URL_NOTIFICACIONES)

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert len(cuerpo) == 1
    assert cuerpo[0]["entidad_id"] == 1
    assert cuerpo[0]["leida"] is False
    assert cuerpo[0]["resuelta"] is False


def test_lista_mas_recientes_primero(client, db, gestor):
    primera = _crear_notificacion(db, gestor, entidad_id=1)
    segunda = _crear_notificacion(db, gestor, entidad_id=2)

    cuerpo = client.get(URL_NOTIFICACIONES).json()

    assert [n["id"] for n in cuerpo] == [segunda.id, primera.id]


def test_marcar_leida(client, db, gestor):
    notificacion = _crear_notificacion(db, gestor)

    respuesta = client.patch(f"{URL_NOTIFICACIONES}/{notificacion.id}/leida")

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["leida"] is True
    assert cuerpo["leida_en"] is not None


def test_no_puede_marcar_leida_una_notificacion_ajena(
    client, db, gestor, crear_usuario
):
    otro = crear_usuario()
    notificacion = _crear_notificacion(db, otro)

    respuesta = client.patch(f"{URL_NOTIFICACIONES}/{notificacion.id}/leida")

    assert respuesta.status_code == 404


def test_marcar_leida_notificacion_inexistente(client, gestor):
    respuesta = client.patch(f"{URL_NOTIFICACIONES}/999999/leida")

    assert respuesta.status_code == 404
