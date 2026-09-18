from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

from backend.core.security import digest_token_sesion
from backend.services.sesiones import RepositorioSesionesMemoria


def test_repositorio_solo_almacena_digest() -> None:
    repositorio = RepositorioSesionesMemoria()
    token = "token-crudo-super-secreto"

    creada = repositorio.crear(
        1,
        token,
        datetime.now(UTC) + timedelta(hours=1),
    )
    obtenida = repositorio.obtener_por_token(token)

    assert obtenida == creada
    assert creada.token_digest == digest_token_sesion(token)
    assert creada.token_digest != token
    assert token not in repr(repositorio._sesiones)


def test_invalidar_token_y_usuario() -> None:
    repositorio = RepositorioSesionesMemoria()
    expira = datetime.now(UTC) + timedelta(hours=1)
    repositorio.crear(1, "token-1", expira)
    repositorio.crear(1, "token-2", expira)
    repositorio.crear(2, "token-3", expira)

    assert repositorio.invalidar("token-1")
    assert repositorio.obtener_por_token("token-1") is None
    assert repositorio.invalidar_usuario(1) == 1
    assert repositorio.obtener_por_token("token-2") is None
    assert repositorio.obtener_por_token("token-3") is not None


def test_expiracion_elimina_sesion() -> None:
    repositorio = RepositorioSesionesMemoria()
    repositorio.crear(1, "expirado", datetime.now(UTC) - timedelta(seconds=1))

    assert repositorio.obtener_por_token("expirado") is None
    assert repositorio.eliminar_expiradas() == 0


def test_repositorio_soporta_acceso_concurrente() -> None:
    repositorio = RepositorioSesionesMemoria()
    expira = datetime.now(UTC) + timedelta(hours=1)

    def crear(indice: int) -> None:
        repositorio.crear(indice % 5, f"token-{indice}", expira)

    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(crear, range(100)))

    assert all(
        repositorio.obtener_por_token(f"token-{indice}") is not None
        for indice in range(100)
    )
    assert repositorio.invalidar_usuario(3) == 20
