from uuid import uuid4

from fastapi.testclient import TestClient

from backend.core.roles import CodigoRol, TipoUsuario
from backend.services.sesiones import RepositorioSesionesMemoria


def _datos_usuario(
    correo: str | None = None,
    rol: CodigoRol = CodigoRol.GESTOR_ORI,
    tipo_usuario: TipoUsuario = TipoUsuario.INTERNO,
) -> dict[str, object]:
    return {
        "correo": correo or f"nuevo-{uuid4().hex}@example.com",
        "contrasena": "ClaveNueva123",
        "nombre_completo": "Usuario nuevo",
        "rol": rol.value,
        "tipo_usuario": tipo_usuario.value,
        "documento_identidad": "123456789",
        "telefono": "3001234567",
        "cargo": "Profesional",
    }


def _autenticar_admin(client: TestClient, crear_usuario, entrar_como):
    admin = crear_usuario(CodigoRol.ADMINISTRADOR_ORI)
    entrar_como(admin)
    return admin


def test_listar_y_obtener_usuario(
    client: TestClient,
    crear_usuario,
    entrar_como,
) -> None:
    admin = _autenticar_admin(client, crear_usuario, entrar_como)
    otro = crear_usuario()

    listado = client.get("/api/usuarios")
    detalle = client.get(f"/api/usuarios/{otro.id}")

    assert listado.status_code == 200
    assert {usuario["id"] for usuario in listado.json()} >= {admin.id, otro.id}
    assert detalle.status_code == 200
    assert detalle.json()["correo"] == otro.correo


def test_crear_usuario_y_no_exponer_hash(
    client: TestClient,
    crear_usuario,
    entrar_como,
) -> None:
    _autenticar_admin(client, crear_usuario, entrar_como)

    respuesta = client.post("/api/usuarios", json=_datos_usuario())

    assert respuesta.status_code == 201
    cuerpo = respuesta.json()
    assert cuerpo["rol"]["codigo"] == CodigoRol.GESTOR_ORI
    assert cuerpo["tipo_usuario"] == TipoUsuario.INTERNO
    assert cuerpo["activo"] is True
    serializado = respuesta.text
    assert "hash_contrasena" not in serializado
    assert "contrasena" not in serializado


def test_creacion_exige_contrasena_minima(
    client: TestClient,
    crear_usuario,
    entrar_como,
) -> None:
    _autenticar_admin(client, crear_usuario, entrar_como)
    datos = {**_datos_usuario(), "contrasena": "corta"}

    assert client.post("/api/usuarios", json=datos).status_code == 422


def test_password_creado_permite_login(
    client: TestClient,
    crear_usuario,
    entrar_como,
) -> None:
    _autenticar_admin(client, crear_usuario, entrar_como)
    datos = _datos_usuario("creado-login@example.com")
    assert client.post("/api/usuarios", json=datos).status_code == 201
    client.cookies.clear()

    login = client.post(
        "/api/auth/login",
        json={"correo": datos["correo"], "contrasena": datos["contrasena"]},
    )

    assert login.status_code == 200


def test_editar_datos_y_contrasena(
    client: TestClient,
    crear_usuario,
    entrar_como,
) -> None:
    _autenticar_admin(client, crear_usuario, entrar_como)
    usuario = crear_usuario(correo="editar@example.com")

    respuesta = client.patch(
        f"/api/usuarios/{usuario.id}",
        json={
            "correo": "editado@example.com",
            "contrasena": "ClaveEditada123",
            "telefono": "3110000000",
            "entidad_externa": "Entidad",
        },
    )

    assert respuesta.status_code == 200
    assert respuesta.json()["telefono"] == "3110000000"
    client.cookies.clear()
    login = client.post(
        "/api/auth/login",
        json={
            "correo": "editado@example.com",
            "contrasena": "ClaveEditada123",
        },
    )
    assert login.status_code == 200


def test_edicion_general_rechaza_rol_estado_y_tipo(
    client: TestClient,
    crear_usuario,
    entrar_como,
) -> None:
    _autenticar_admin(client, crear_usuario, entrar_como)
    usuario = crear_usuario()

    respuesta = client.patch(
        f"/api/usuarios/{usuario.id}",
        json={
            "rol": CodigoRol.ADMINISTRADOR_ORI.value,
            "activo": False,
            "tipo_usuario": TipoUsuario.EXTERNO.value,
        },
    )

    assert respuesta.status_code == 422


def test_cambiar_rol_persistido(
    client: TestClient,
    crear_usuario,
    entrar_como,
) -> None:
    _autenticar_admin(client, crear_usuario, entrar_como)
    usuario = crear_usuario(CodigoRol.GESTOR_ORI)

    respuesta = client.patch(
        f"/api/usuarios/{usuario.id}/rol",
        json={"rol": CodigoRol.REVISOR_ORI.value},
    )

    assert respuesta.status_code == 200
    assert respuesta.json()["rol"]["codigo"] == CodigoRol.REVISOR_ORI
    assert client.get(f"/api/usuarios/{usuario.id}").json()["rol"]["codigo"] == (
        CodigoRol.REVISOR_ORI
    )


def test_cambio_de_rol_aplica_a_sesion_existente(
    client: TestClient,
    crear_usuario,
    entrar_como,
) -> None:
    admin = crear_usuario(CodigoRol.ADMINISTRADOR_ORI)
    usuario = crear_usuario(CodigoRol.GESTOR_ORI)
    token_usuario = entrar_como(usuario)
    entrar_como(admin)
    respuesta = client.patch(
        f"/api/usuarios/{usuario.id}/rol",
        json={"rol": CodigoRol.ADMINISTRADOR_ORI.value},
    )
    assert respuesta.status_code == 200

    client.cookies.set("session_id", token_usuario)
    assert client.get("/api/usuarios").status_code == 200


def test_cambiar_estado_invalida_sesiones(
    client: TestClient,
    crear_usuario,
    entrar_como,
    sesiones: RepositorioSesionesMemoria,
) -> None:
    admin = crear_usuario(CodigoRol.ADMINISTRADOR_ORI)
    usuario = crear_usuario()
    token_usuario = entrar_como(usuario)
    entrar_como(admin)

    respuesta = client.patch(
        f"/api/usuarios/{usuario.id}/estado",
        json={"activo": False},
    )

    assert respuesta.status_code == 200
    assert respuesta.json()["activo"] is False
    assert sesiones.obtener_por_token(token_usuario) is None


def test_correo_duplicado_responde_409(
    client: TestClient,
    crear_usuario,
    entrar_como,
) -> None:
    _autenticar_admin(client, crear_usuario, entrar_como)
    existente = crear_usuario(correo="duplicado@example.com")

    crear = client.post(
        "/api/usuarios",
        json=_datos_usuario(existente.correo),
    )
    otro = crear_usuario()
    editar = client.patch(
        f"/api/usuarios/{otro.id}",
        json={"correo": existente.correo},
    )

    assert crear.status_code == 409
    assert editar.status_code == 409


def test_usuario_inexistente_responde_404(
    client: TestClient,
    crear_usuario,
    entrar_como,
) -> None:
    _autenticar_admin(client, crear_usuario, entrar_como)

    assert client.get("/api/usuarios/2147483647").status_code == 404
    assert (
        client.patch(
            "/api/usuarios/2147483647/estado",
            json={"activo": False},
        ).status_code
        == 404
    )


def test_rol_inexistente_e_incompatibilidad_responden_422(
    client: TestClient,
    crear_usuario,
    entrar_como,
) -> None:
    _autenticar_admin(client, crear_usuario, entrar_como)

    inexistente = client.post(
        "/api/usuarios",
        json={**_datos_usuario(), "rol": "ROL_INEXISTENTE"},
    )
    incompatible = client.post(
        "/api/usuarios",
        json=_datos_usuario(
            rol=CodigoRol.SOLICITANTE_EXTERNO,
            tipo_usuario=TipoUsuario.INTERNO,
        ),
    )

    assert inexistente.status_code == 422
    assert incompatible.status_code == 422


def test_unidad_inexistente_responde_422(
    client: TestClient,
    crear_usuario,
    entrar_como,
) -> None:
    _autenticar_admin(client, crear_usuario, entrar_como)
    datos = {**_datos_usuario(), "unidad_organizacional_id": 2147483647}

    assert client.post("/api/usuarios", json=datos).status_code == 422


def test_admin_no_puede_cambiar_su_rol_ni_desactivarse(
    client: TestClient,
    crear_usuario,
    entrar_como,
) -> None:
    admin = _autenticar_admin(client, crear_usuario, entrar_como)

    rol = client.patch(
        f"/api/usuarios/{admin.id}/rol",
        json={"rol": CodigoRol.GESTOR_ORI.value},
    )
    estado = client.patch(
        f"/api/usuarios/{admin.id}/estado",
        json={"activo": False},
    )

    assert rol.status_code == 409
    assert estado.status_code == 409


def test_usuario_externo_con_rol_externo_es_valido(
    client: TestClient,
    crear_usuario,
    entrar_como,
) -> None:
    _autenticar_admin(client, crear_usuario, entrar_como)

    respuesta = client.post(
        "/api/usuarios",
        json=_datos_usuario(
            rol=CodigoRol.SOLICITANTE_EXTERNO,
            tipo_usuario=TipoUsuario.EXTERNO,
        ),
    )

    assert respuesta.status_code == 201
    assert respuesta.json()["tipo_usuario"] == TipoUsuario.EXTERNO
