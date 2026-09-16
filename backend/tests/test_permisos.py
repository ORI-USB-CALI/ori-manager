from fastapi.routing import APIRoute

from backend.api.deps import get_current_user
from backend.core.permisos import PERMISOS_POR_ROL, Rol
from backend.main import app

RUTAS_PUBLICAS = {"/", "/health", "/ready", "/api/auth/login", "/api/auth/logout"}


def _usa_dependencia(dependant, dependencia) -> bool:
    return any(
        d.call is dependencia or _usa_dependencia(d, dependencia) for d in dependant.dependencies
    )


def test_todo_rol_tiene_permisos_definidos() -> None:
    assert set(PERMISOS_POR_ROL) == set(Rol)


def test_rutas_no_publicas_exigen_sesion() -> None:
    sin_proteger = [
        route.path
        for route in app.routes
        if isinstance(route, APIRoute)
        and route.path not in RUTAS_PUBLICAS
        and not _usa_dependencia(route.dependant, get_current_user)
    ]
    assert sin_proteger == []
