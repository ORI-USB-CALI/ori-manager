def crear_usuario(client, correo: str, rol: str = "GESTOR_ORI") -> dict:
    respuesta = client.post(
        "/usuarios/",
        json={
            "correo": correo,
            "contrasena": "Prueba12345",
            "nombre_completo": "Usuario de Prueba",
            "rol": rol,
        },
    )
    return respuesta.json()


def test_listar_usuarios_muestra_rol_y_estado(client):
    """CA-01: el listado incluye rol y estado activo de cada usuario."""
    crear_usuario(client, "listado.uno@usbcali.edu.co", "ADMINISTRADOR_ORI")
    crear_usuario(client, "listado.dos@usbcali.edu.co", "REVISOR_ORI")

    respuesta = client.get("/usuarios/")

    assert respuesta.status_code == 200
    usuarios = respuesta.json()
    assert len(usuarios) >= 2
    for usuario in usuarios:
        assert "id" in usuario
        assert "rol" in usuario
        assert "codigo" in usuario["rol"]
        assert "activo" in usuario


def test_obtener_usuario_por_id(client):
    """Devuelve el detalle completo del usuario solicitado."""
    creado = crear_usuario(client, "detalle@usbcali.edu.co")

    respuesta = client.get(f"/usuarios/{creado['id']}")

    assert respuesta.status_code == 200
    assert respuesta.json()["correo"] == "detalle@usbcali.edu.co"


def test_obtener_usuario_inexistente(client):
    """Un id que no existe responde 404."""
    respuesta = client.get("/usuarios/999999")

    assert respuesta.status_code == 404