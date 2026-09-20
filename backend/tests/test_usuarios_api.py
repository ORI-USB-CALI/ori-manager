from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.core.roles import CodigoRol, TipoUsuario
from backend.core.security import verificar_contrasena
from backend.models.usuario import Usuario
from backend.schemas.usuario import UsuarioActualizar
from backend.services.sesiones import RepositorioSesionesMemoria
from backend.services.usuarios import ServicioUsuarios


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


def test_listado_y_detalle_excluyen_usuarios_externos(
    client: TestClient,
    crear_usuario,
    entrar_como,
) -> None:
    admin = _autenticar_admin(client, crear_usuario, entrar_como)
    interno = crear_usuario()
    externo = crear_usuario(
        CodigoRol.SOLICITANTE_EXTERNO,
        TipoUsuario.EXTERNO,
    )

    listado = client.get("/api/usuarios")

    assert listado.status_code == 200
    ids = {usuario["id"] for usuario in listado.json()}
    assert ids >= {admin.id, interno.id}
    assert externo.id not in ids
    assert client.get(f"/api/usuarios/{externo.id}").status_code == 404
    assert (
        client.patch(
            f"/api/usuarios/{externo.id}",
            json={"cargo": "No permitido"},
        ).status_code
        == 404
    )
    assert (
        client.patch(
            f"/api/usuarios/{externo.id}/rol",
            json={"rol": CodigoRol.GESTOR_ORI.value},
        ).status_code
        == 404
    )
    assert (
        client.patch(
            f"/api/usuarios/{externo.id}/estado",
            json={"activo": False},
        ).status_code
        == 404
    )


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


@pytest.mark.parametrize(
    "campo",
    ["correo", "contrasena", "nombre_completo", "rol"],
)
def test_creacion_rechaza_campos_obligatorios_ausentes(
    campo: str,
    client: TestClient,
    crear_usuario,
    entrar_como,
) -> None:
    _autenticar_admin(client, crear_usuario, entrar_como)
    datos = _datos_usuario()
    del datos[campo]

    respuesta = client.post("/api/usuarios", json=datos)

    assert respuesta.status_code == 422


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


def test_contrasena_igual_rechaza_todo_el_patch_y_conserva_sesion(
    client: TestClient,
    crear_usuario,
    entrar_como,
    sesiones: RepositorioSesionesMemoria,
    db: Session,
) -> None:
    admin = crear_usuario(CodigoRol.ADMINISTRADOR_ORI)
    usuario = crear_usuario(correo="misma-clave@example.com")
    token_usuario = entrar_como(usuario)
    hash_anterior = usuario.hash_contrasena
    telefono_anterior = usuario.telefono
    entrar_como(admin)

    respuesta = client.patch(
        f"/api/usuarios/{usuario.id}",
        json={"telefono": "3110000000", "contrasena": "ClaveSegura123"},
    )

    assert respuesta.status_code == 409
    assert respuesta.json()["detail"] == (
        "La nueva contraseña debe ser diferente a la actual"
    )
    db.refresh(usuario)
    assert usuario.hash_contrasena == hash_anterior
    assert usuario.telefono == telefono_anterior
    assert verificar_contrasena("ClaveSegura123", usuario.hash_contrasena)
    assert sesiones.obtener_por_token(token_usuario) is not None
    client.cookies.set("session_id", token_usuario)
    assert client.get("/api/auth/me").status_code == 200
    client.cookies.clear()
    assert client.post(
        "/api/auth/login",
        json={"correo": usuario.correo, "contrasena": "ClaveSegura123"},
    ).status_code == 200


def test_cambio_contrasena_invalida_sesion_y_credencial_anterior(
    client: TestClient,
    crear_usuario,
    entrar_como,
    sesiones: RepositorioSesionesMemoria,
) -> None:
    admin = crear_usuario(CodigoRol.ADMINISTRADOR_ORI)
    usuario = crear_usuario(correo="cambio-clave@example.com")
    token_usuario = entrar_como(usuario)
    entrar_como(admin)

    respuesta = client.patch(
        f"/api/usuarios/{usuario.id}",
        json={"contrasena": "ClaveDistinta123"},
    )

    assert respuesta.status_code == 200
    assert sesiones.obtener_por_token(token_usuario) is None
    client.cookies.set("session_id", token_usuario)
    assert client.get("/api/auth/me").status_code == 401
    client.cookies.clear()
    assert client.post(
        "/api/auth/login",
        json={"correo": usuario.correo, "contrasena": "ClaveSegura123"},
    ).status_code == 401
    assert client.post(
        "/api/auth/login",
        json={"correo": usuario.correo, "contrasena": "ClaveDistinta123"},
    ).status_code == 200


def test_cambio_contrasena_invalida_todas_las_sesiones(
    client: TestClient,
    crear_usuario,
    entrar_como,
    sesiones: RepositorioSesionesMemoria,
) -> None:
    admin = crear_usuario(CodigoRol.ADMINISTRADOR_ORI)
    usuario = crear_usuario()
    primer_token = entrar_como(usuario)
    segundo_token = entrar_como(usuario)
    entrar_como(admin)

    respuesta = client.patch(
        f"/api/usuarios/{usuario.id}",
        json={"contrasena": "ClaveDistinta123"},
    )

    assert respuesta.status_code == 200
    assert sesiones.obtener_por_token(primer_token) is None
    assert sesiones.obtener_por_token(segundo_token) is None


def test_admin_cambia_su_contrasena_e_invalida_su_sesion(
    client: TestClient,
    crear_usuario,
    entrar_como,
    sesiones: RepositorioSesionesMemoria,
) -> None:
    admin = crear_usuario(CodigoRol.ADMINISTRADOR_ORI)
    token = entrar_como(admin)

    respuesta = client.patch(
        f"/api/usuarios/{admin.id}",
        json={"contrasena": "ClaveDistinta123"},
    )

    assert respuesta.status_code == 200
    assert sesiones.obtener_por_token(token) is None
    assert client.get("/api/auth/me").status_code == 401
    client.cookies.clear()
    assert client.post(
        "/api/auth/login",
        json={"correo": admin.correo, "contrasena": "ClaveDistinta123"},
    ).status_code == 200


def test_fallo_al_guardar_contrasena_conserva_sesiones(
    client: TestClient,
    crear_usuario,
    entrar_como,
    sesiones: RepositorioSesionesMemoria,
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    usuario = crear_usuario()
    token = entrar_como(usuario)
    hash_anterior = usuario.hash_contrasena

    def fallar_commit() -> None:
        raise RuntimeError("Fallo de persistencia simulado")

    with monkeypatch.context() as parche:
        parche.setattr(db, "commit", fallar_commit)
        with pytest.raises(RuntimeError, match="Fallo de persistencia simulado"):
            ServicioUsuarios(db, sesiones).actualizar(
                usuario.id,
                UsuarioActualizar(contrasena="ClaveDistinta123"),
            )

    db.rollback()
    db.refresh(usuario)
    assert usuario.hash_contrasena == hash_anterior
    assert sesiones.obtener_por_token(token) is not None
    assert client.get("/api/auth/me").status_code == 200


def test_edicion_parcial_conserva_campos_no_enviados(
    client: TestClient,
    crear_usuario,
    entrar_como,
) -> None:
    _autenticar_admin(client, crear_usuario, entrar_como)
    usuario = crear_usuario(correo="parcial@example.com")
    datos_antes = client.get(f"/api/usuarios/{usuario.id}").json()

    respuesta = client.patch(
        f"/api/usuarios/{usuario.id}",
        json={"cargo": "Coordinador"},
    )

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["cargo"] == "Coordinador"
    for campo in (
        "correo",
        "nombre_completo",
        "documento_identidad",
        "telefono",
        "tipo_usuario",
        "entidad_externa",
        "activo",
        "rol",
        "unidad_organizacional_id",
    ):
        assert cuerpo[campo] == datos_antes[campo]


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
    assert client.get("/api/usuarios").status_code == 403

    token_admin = entrar_como(admin)
    respuesta = client.patch(
        f"/api/usuarios/{usuario.id}/rol",
        json={"rol": CodigoRol.ADMINISTRADOR_ORI.value},
    )
    assert respuesta.status_code == 200

    client.cookies.set("session_id", token_usuario)
    assert client.get("/api/usuarios").status_code == 200

    client.cookies.set("session_id", token_admin)
    respuesta = client.patch(
        f"/api/usuarios/{usuario.id}/rol",
        json={"rol": CodigoRol.GESTOR_ORI.value},
    )
    assert respuesta.status_code == 200

    client.cookies.set("session_id", token_usuario)
    assert client.get("/api/usuarios").status_code == 403


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
    client.cookies.clear()
    login = client.post(
        "/api/auth/login",
        json={"correo": usuario.correo, "contrasena": "ClaveSegura123"},
    )
    assert login.status_code == 403
    assert login.cookies.get("session_id") is None


def test_desactivar_usuario_ya_inactivo_responde_409(
    client: TestClient,
    crear_usuario,
    entrar_como,
) -> None:
    _autenticar_admin(client, crear_usuario, entrar_como)
    usuario = crear_usuario()

    primera = client.patch(
        f"/api/usuarios/{usuario.id}/estado",
        json={"activo": False},
    )
    segunda = client.patch(
        f"/api/usuarios/{usuario.id}/estado",
        json={"activo": False},
    )

    assert primera.status_code == 200
    assert segunda.status_code == 409
    assert segunda.json()["detail"] == "El usuario ya se encuentra inactivo"
    assert client.get(f"/api/usuarios/{usuario.id}").json()["activo"] is False


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
    assert crear.json()["detail"] == "Ya existe un usuario con ese correo"
    assert editar.json()["detail"] == "Ya existe un usuario con ese correo"


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
    invitado = client.post(
        "/api/usuarios",
        json={**_datos_usuario(), "rol": "INVITADO"},
    )

    assert inexistente.status_code == 422
    assert incompatible.status_code == 422
    assert invitado.status_code == 422


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


def test_administracion_rechaza_creacion_de_usuario_externo(
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

    assert respuesta.status_code == 422
    assert respuesta.json()["detail"] == (
        "El módulo administrativo solo permite crear usuarios internos"
    )


def test_usuario_desactivado_conserva_identidad_y_ultimo_acceso(
    client: TestClient,
    crear_usuario,
    entrar_como,
    db: Session,
) -> None:
    admin = crear_usuario(CodigoRol.ADMINISTRADOR_ORI)
    usuario = crear_usuario(correo="trazabilidad@example.com")

    login = client.post(
        "/api/auth/login",
        json={"correo": usuario.correo, "contrasena": "ClaveSegura123"},
    )
    assert login.status_code == 200

    entrar_como(admin)
    antes = client.get(f"/api/usuarios/{usuario.id}").json()
    assert antes["ultimo_acceso"] is not None

    desactivar = client.patch(
        f"/api/usuarios/{usuario.id}/estado",
        json={"activo": False},
    )
    despues = client.get(f"/api/usuarios/{usuario.id}")

    assert desactivar.status_code == 200
    assert despues.status_code == 200
    cuerpo = despues.json()
    assert cuerpo["id"] == antes["id"]
    assert cuerpo["correo"] == antes["correo"]
    assert cuerpo["activo"] is False
    assert cuerpo["ultimo_acceso"] == antes["ultimo_acceso"]
    persistido = db.get(Usuario, usuario.id)
    assert persistido is not None
    assert persistido.id == antes["id"]
    assert client.delete(f"/api/usuarios/{usuario.id}").status_code == 405
