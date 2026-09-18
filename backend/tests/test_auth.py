from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.core.config import settings
from backend.core.permisos import PERMISOS_POR_ROL
from backend.core.roles import CodigoRol
from backend.services.sesiones import RepositorioSesionesMemoria


def test_login_valido_crea_cookie_http_only(
    client: TestClient,
    crear_usuario,
) -> None:
    usuario = crear_usuario(
        correo="login@example.com",
        contrasena="ClaveSegura123",
    )

    respuesta = client.post(
        "/api/auth/login",
        json={"correo": usuario.correo, "contrasena": "ClaveSegura123"},
    )

    assert respuesta.status_code == 200
    assert respuesta.cookies.get("session_id")
    cookie = respuesta.headers["set-cookie"].lower()
    assert "httponly" in cookie
    assert "samesite=lax" in cookie
    assert "path=/" in cookie
    assert "max-age=604800" in cookie
    assert ("; secure" in cookie) == (settings.app_env != "development")


def test_login_credenciales_incorrectas_y_usuario_inexistente(
    client: TestClient,
    crear_usuario,
) -> None:
    usuario = crear_usuario(correo="credenciales@example.com")

    incorrecta = client.post(
        "/api/auth/login",
        json={"correo": usuario.correo, "contrasena": "mal"},
    )
    inexistente = client.post(
        "/api/auth/login",
        json={"correo": "nadie@example.com", "contrasena": "Incorrecta123"},
    )

    assert incorrecta.status_code == 401
    assert inexistente.status_code == 401
    assert incorrecta.json()["detail"] == inexistente.json()["detail"]


def test_login_usuario_inactivo_responde_403(client: TestClient, crear_usuario) -> None:
    usuario = crear_usuario(activo=False, correo="inactivo@example.com")

    respuesta = client.post(
        "/api/auth/login",
        json={"correo": usuario.correo, "contrasena": "ClaveSegura123"},
    )

    assert respuesta.status_code == 403


def test_me_requiere_sesion_valida(client: TestClient) -> None:
    assert client.get("/api/auth/me").status_code == 401
    client.cookies.set("session_id", "token-invalido")
    assert client.get("/api/auth/me").status_code == 401


def test_me_devuelve_usuario_rol_y_permisos(
    client: TestClient,
    crear_usuario,
    entrar_como,
) -> None:
    admin = crear_usuario(CodigoRol.ADMINISTRADOR_ORI)
    entrar_como(admin)

    respuesta = client.get("/api/auth/me")

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["id"] == admin.id
    assert cuerpo["correo"] == admin.correo
    assert cuerpo["rol"]["codigo"] == CodigoRol.ADMINISTRADOR_ORI
    assert set(cuerpo["permisos"]) == {
        permiso.value for permiso in PERMISOS_POR_ROL[CodigoRol.ADMINISTRADOR_ORI]
    }


def test_me_invalida_sesion_de_usuario_desactivado(
    client: TestClient,
    crear_usuario,
    entrar_como,
    sesiones: RepositorioSesionesMemoria,
    db: Session,
) -> None:
    usuario = crear_usuario()
    token = entrar_como(usuario)
    usuario.activo = False
    db.commit()

    respuesta = client.get("/api/auth/me")

    assert respuesta.status_code == 403
    assert sesiones.obtener_por_token(token) is None


def test_logout_invalida_sesion(
    client: TestClient,
    crear_usuario,
    entrar_como,
    sesiones: RepositorioSesionesMemoria,
) -> None:
    token = entrar_como(crear_usuario())

    respuesta = client.post("/api/auth/logout")

    assert respuesta.status_code == 200
    assert sesiones.obtener_por_token(token) is None
    assert client.get("/api/auth/me").status_code == 401


def test_token_expirado_no_autentica(
    client: TestClient,
    crear_usuario,
    sesiones: RepositorioSesionesMemoria,
) -> None:
    usuario = crear_usuario()
    token = "token-expirado"
    sesiones.crear(usuario.id, token, datetime.now(UTC) - timedelta(seconds=1))
    client.cookies.set("session_id", token)

    assert client.get("/api/auth/me").status_code == 401


def test_login_actualiza_ultimo_acceso(
    client: TestClient,
    crear_usuario,
    db: Session,
) -> None:
    usuario = crear_usuario(correo="ultimo-acceso@example.com")
    assert usuario.ultimo_acceso is None

    respuesta = client.post(
        "/api/auth/login",
        json={"correo": usuario.correo, "contrasena": "ClaveSegura123"},
    )
    db.refresh(usuario)

    assert respuesta.status_code == 200
    assert usuario.ultimo_acceso is not None
