from fastapi.testclient import TestClient

from backend.api.deps import permisos_de_usuario
from backend.core.permisos import PERMISOS_POR_ROL, Permiso
from backend.core.roles import CodigoRol


def test_endpoint_protegido_sin_sesion_responde_401(client: TestClient) -> None:
    assert client.get("/api/usuarios").status_code == 401


def test_usuario_sin_permiso_responde_403(
    client: TestClient,
    crear_usuario,
    entrar_como,
) -> None:
    entrar_como(crear_usuario(CodigoRol.GESTOR_ORI))

    assert client.get("/api/usuarios").status_code == 403


def test_admin_con_permiso_puede_acceder(
    client: TestClient,
    crear_usuario,
    entrar_como,
) -> None:
    entrar_como(crear_usuario(CodigoRol.ADMINISTRADOR_ORI))

    assert client.get("/api/usuarios").status_code == 200


def test_permisos_se_resuelven_desde_contrato_canonico(
    crear_usuario,
) -> None:
    usuario = crear_usuario(CodigoRol.ADMINISTRADOR_ORI)

    assert permisos_de_usuario(usuario) == PERMISOS_POR_ROL[CodigoRol.ADMINISTRADOR_ORI]
    assert Permiso.USUARIOS_CAMBIAR_ROL in permisos_de_usuario(usuario)
