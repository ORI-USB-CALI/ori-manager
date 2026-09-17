def crear_usuario(client, correo: str, rol: str = "GESTOR_ORI") -> dict:
    respuesta = client.post(
        "/usuarios/",
        json={
            "correo": correo,
            "contrasena": "Prueba12345",
            "nombre_completo": "Usuario Editable",
            "rol": rol,
            "documento_identidad": "1100200300",
            "telefono": "3001112233",
            "cargo": "Cargo Original",
        },
    )
    return respuesta.json()


def test_editar_conserva_datos_no_modificados(client):
    """CA-06: enviar solo un campo no borra los demas."""
    creado = crear_usuario(client, "edicion.parcial@usbcali.edu.co")

    respuesta = client.patch(
        f"/usuarios/{creado['id']}", json={"telefono": "3109998877"}
    )

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["telefono"] == "3109998877"
    assert cuerpo["nombre_completo"] == "Usuario Editable"
    assert cuerpo["cargo"] == "Cargo Original"
    assert cuerpo["documento_identidad"] == "1100200300"


def test_editar_usuario_inexistente(client):
    respuesta = client.patch("/usuarios/999999", json={"telefono": "3000000000"})

    assert respuesta.status_code == 404


def test_cambiar_rol_actualiza_el_rol(client):
    """CA-07: el rol cambia y se refleja en la respuesta."""
    creado = crear_usuario(client, "cambio.rol@usbcali.edu.co", "REVISOR_ORI")

    respuesta = client.patch(
        f"/usuarios/{creado['id']}/rol", json={"rol": "ADMINISTRADOR_ORI"}
    )

    assert respuesta.status_code == 200
    assert respuesta.json()["rol"]["codigo"] == "ADMINISTRADOR_ORI"


def test_cambiar_rol_persiste_en_consulta_posterior(client):
    """El cambio de rol queda guardado, no solo en la respuesta."""
    creado = crear_usuario(client, "rol.persiste@usbcali.edu.co", "REVISOR_ORI")

    client.patch(f"/usuarios/{creado['id']}/rol", json={"rol": "GESTOR_ORI"})
    respuesta = client.get(f"/usuarios/{creado['id']}")

    assert respuesta.json()["rol"]["codigo"] == "GESTOR_ORI"


def test_cambiar_rol_no_interno(client):
    """CA-05: no se puede asignar un rol fuera del catalogo interno."""
    creado = crear_usuario(client, "rol.invalido@usbcali.edu.co")

    respuesta = client.patch(f"/usuarios/{creado['id']}/rol", json={"rol": "INVITADO"})

    assert respuesta.status_code == 422


def test_desactivar_usuario(client):
    """CA-08: la desactivacion es logica y conserva la informacion."""
    creado = crear_usuario(client, "desactivar@usbcali.edu.co")

    respuesta = client.post(f"/usuarios/{creado['id']}/desactivar")

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["activo"] is False
    assert cuerpo["correo"] == "desactivar@usbcali.edu.co"
    assert cuerpo["nombre_completo"] == "Usuario Editable"


def test_desactivar_usuario_ya_inactivo(client):
    """CA-11: no se permite desactivar dos veces."""
    creado = crear_usuario(client, "doble.desactivar@usbcali.edu.co")
    client.post(f"/usuarios/{creado['id']}/desactivar")

    respuesta = client.post(f"/usuarios/{creado['id']}/desactivar")

    assert respuesta.status_code == 400
    assert "inactivo" in respuesta.json()["detail"].lower()


def test_usuario_desactivado_sigue_consultable(client):
    """CA-10: el registro se conserva para la trazabilidad."""
    creado = crear_usuario(client, "trazabilidad@usbcali.edu.co")
    client.post(f"/usuarios/{creado['id']}/desactivar")

    respuesta = client.get(f"/usuarios/{creado['id']}")

    assert respuesta.status_code == 200
    assert respuesta.json()["activo"] is False