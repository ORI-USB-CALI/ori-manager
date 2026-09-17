def test_crear_usuario_exitoso(client):
    """CA-02: el usuario se crea activo y con el rol asignado."""
    respuesta = client.post(
        "/usuarios/",
        json={
            "correo": "nuevo.gestor@usbcali.edu.co",
            "contrasena": "Prueba12345",
            "nombre_completo": "Nuevo Gestor",
            "rol": "GESTOR_ORI",
        },
    )

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["correo"] == "nuevo.gestor@usbcali.edu.co"
    assert cuerpo["rol"]["codigo"] == "GESTOR_ORI"
    assert cuerpo["activo"] is True
    assert "id" in cuerpo


def test_crear_usuario_no_expone_contrasena(client):
    """La respuesta nunca debe incluir el hash de la contrasena."""
    respuesta = client.post(
        "/usuarios/",
        json={
            "correo": "sin.hash@usbcali.edu.co",
            "contrasena": "Prueba12345",
            "nombre_completo": "Sin Hash",
            "rol": "REVISOR_ORI",
        },
    )

    assert "hash_contrasena" not in respuesta.json()
    assert "contrasena" not in respuesta.json()


def test_crear_usuario_sin_campos_obligatorios(client):
    """CA-03: falta nombre_completo y rol."""
    respuesta = client.post(
        "/usuarios/",
        json={"correo": "incompleto@usbcali.edu.co", "contrasena": "Prueba12345"},
    )

    assert respuesta.status_code == 422
    campos = {error["loc"][-1] for error in respuesta.json()["detail"]}
    assert "nombre_completo" in campos
    assert "rol" in campos


def test_crear_usuario_contrasena_corta(client):
    """CA-03: la contrasena exige minimo 8 caracteres."""
    respuesta = client.post(
        "/usuarios/",
        json={
            "correo": "corta@usbcali.edu.co",
            "contrasena": "1234",
            "nombre_completo": "Contrasena Corta",
            "rol": "GESTOR_ORI",
        },
    )

    assert respuesta.status_code == 422


def test_crear_usuario_correo_duplicado(client):
    """CA-04: no se permiten dos usuarios con el mismo correo."""
    datos = {
        "correo": "duplicado@usbcali.edu.co",
        "contrasena": "Prueba12345",
        "nombre_completo": "Primer Usuario",
        "rol": "GESTOR_ORI",
    }
    client.post("/usuarios/", json=datos)

    respuesta = client.post("/usuarios/", json={**datos, "nombre_completo": "Segundo"})

    assert respuesta.status_code == 400
    assert "ya existe" in respuesta.json()["detail"].lower()


def test_crear_usuario_rol_no_interno(client):
    """CA-05: solo se aceptan los tres roles internos."""
    respuesta = client.post(
        "/usuarios/",
        json={
            "correo": "invitado@usbcali.edu.co",
            "contrasena": "Prueba12345",
            "nombre_completo": "Rol Invalido",
            "rol": "INVITADO",
        },
    )

    assert respuesta.status_code == 422