import uuid

import pytest

from backend.core.permisos import Rol
from backend.core.security import get_password_hash
from backend.models.user import User
from backend.services.auth import create_session


@pytest.fixture
def crear_usuario(db):
    def _crear(rol: Rol) -> User:
        usuario = User(
            email=f"{rol.value}-{uuid.uuid4().hex[:8]}@example.com",
            hashed_password=get_password_hash("secret123"),
            rol=rol,
        )
        db.add(usuario)
        db.commit()
        return usuario

    return _crear


@pytest.fixture
def entrar_como(client, db):
    def _entrar(usuario: User) -> None:
        client.cookies.set("session_id", create_session(db, usuario.id).token)

    return _entrar


def test_sin_sesion_responde_401(client, crear_usuario):
    otro = crear_usuario(Rol.USUARIO_ORI)

    assert client.get("/api/usuarios").status_code == 401
    respuesta = client.patch(f"/api/usuarios/{otro.id}", json={"rol": "administrador"})
    assert respuesta.status_code == 401


def test_usuario_ori_responde_403(client, crear_usuario, entrar_como):
    usuario = crear_usuario(Rol.USUARIO_ORI)
    entrar_como(usuario)

    assert client.get("/api/usuarios").status_code == 403
    respuesta = client.patch(f"/api/usuarios/{usuario.id}", json={"rol": "administrador"})
    assert respuesta.status_code == 403


def test_admin_lista_usuarios_con_rol(client, crear_usuario, entrar_como):
    admin = crear_usuario(Rol.ADMINISTRADOR)
    otro = crear_usuario(Rol.USUARIO_ORI)
    entrar_como(admin)

    respuesta = client.get("/api/usuarios")

    assert respuesta.status_code == 200
    roles = {u["email"]: u["rol"] for u in respuesta.json()}
    assert roles[admin.email] == "administrador"
    assert roles[otro.email] == "usuario_ori"


def test_admin_cambia_rol_y_aplica_de_inmediato(client, crear_usuario, entrar_como):
    admin = crear_usuario(Rol.ADMINISTRADOR)
    otro = crear_usuario(Rol.USUARIO_ORI)
    entrar_como(admin)

    respuesta = client.patch(f"/api/usuarios/{otro.id}", json={"rol": "administrador"})
    assert respuesta.status_code == 200
    assert respuesta.json()["rol"] == "administrador"

    entrar_como(otro)
    me = client.get("/api/auth/me").json()
    assert me["rol"] == "administrador"
    assert "usuarios.gestionar" in me["permisos"]


def test_admin_no_puede_cambiar_su_propio_rol(client, crear_usuario, entrar_como):
    admin = crear_usuario(Rol.ADMINISTRADOR)
    entrar_como(admin)

    respuesta = client.patch(f"/api/usuarios/{admin.id}", json={"rol": "usuario_ori"})
    assert respuesta.status_code == 409
    respuesta = client.patch(f"/api/usuarios/{admin.id}", json={"is_active": False})
    assert respuesta.status_code == 409
    # Sí puede editar sus demás datos.
    respuesta = client.patch(f"/api/usuarios/{admin.id}", json={"email": "nuevo-admin@example.com"})
    assert respuesta.status_code == 200


def test_rol_invalido_o_usuario_inexistente(client, crear_usuario, entrar_como):
    admin = crear_usuario(Rol.ADMINISTRADOR)
    otro = crear_usuario(Rol.USUARIO_ORI)
    entrar_como(admin)

    assert client.patch(f"/api/usuarios/{otro.id}", json={"rol": "invitado"}).status_code == 422
    respuesta = client.patch(f"/api/usuarios/{uuid.uuid4()}", json={"rol": "usuario_ori"})
    assert respuesta.status_code == 404


def test_me_de_usuario_ori_solo_permisos_de_lectura(client, crear_usuario, entrar_como):
    entrar_como(crear_usuario(Rol.USUARIO_ORI))

    me = client.get("/api/auth/me").json()

    assert me["rol"] == "usuario_ori"
    assert me["permisos"] == ["aliados.ver", "convenios.ver"]


def test_admin_crea_usuario_que_puede_iniciar_sesion(client, crear_usuario, entrar_como):
    entrar_como(crear_usuario(Rol.ADMINISTRADOR))

    respuesta = client.post(
        "/api/usuarios",
        json={"email": "nuevo@example.com", "password": "secret123", "rol": "usuario_ori"},
    )
    assert respuesta.status_code == 201
    assert respuesta.json()["rol"] == "usuario_ori"
    assert respuesta.json()["is_active"] is True
    assert "password" not in respuesta.json() and "hashed_password" not in respuesta.json()

    client.cookies.clear()
    login = client.post("/api/auth/login", json={"email": "nuevo@example.com", "password": "secret123"})
    assert login.status_code == 200


def test_crear_usuario_valida_datos(client, crear_usuario, entrar_como):
    admin = crear_usuario(Rol.ADMINISTRADOR)
    entrar_como(admin)

    duplicado = {"email": admin.email, "password": "secret123", "rol": "usuario_ori"}
    assert client.post("/api/usuarios", json=duplicado).status_code == 409
    corta = {"email": "x@example.com", "password": "corta", "rol": "usuario_ori"}
    assert client.post("/api/usuarios", json=corta).status_code == 422
    sin_arroba = {"email": "no-es-correo", "password": "secret123", "rol": "usuario_ori"}
    assert client.post("/api/usuarios", json=sin_arroba).status_code == 422


def test_usuario_ori_no_puede_crear(client, crear_usuario, entrar_como):
    entrar_como(crear_usuario(Rol.USUARIO_ORI))

    datos = {"email": "x@example.com", "password": "secret123", "rol": "administrador"}
    assert client.post("/api/usuarios", json=datos).status_code == 403


def test_admin_edita_correo_password_y_desactiva(client, crear_usuario, entrar_como):
    admin = crear_usuario(Rol.ADMINISTRADOR)
    otro = crear_usuario(Rol.USUARIO_ORI)
    entrar_como(admin)

    respuesta = client.patch(
        f"/api/usuarios/{otro.id}",
        json={"email": "editado@example.com", "password": "otraClave1"},
    )
    assert respuesta.status_code == 200
    assert respuesta.json()["email"] == "editado@example.com"

    client.cookies.clear()
    login = client.post("/api/auth/login", json={"email": "editado@example.com", "password": "otraClave1"})
    assert login.status_code == 200
    token_otro = client.cookies.get("session_id")

    entrar_como(admin)
    assert client.patch(f"/api/usuarios/{otro.id}", json={"is_active": False}).status_code == 200

    # La sesión abierta del usuario desactivado deja de servir de inmediato.
    client.cookies.set("session_id", token_otro)
    assert client.get("/api/auth/me").status_code == 403
