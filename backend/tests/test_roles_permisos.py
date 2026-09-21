import ast
import inspect
from types import ModuleType

import pytest

from backend.core import permisos, roles
from backend.core.permisos import (
    PERMISOS_POR_ROL,
    Permiso,
    permisos_para_rol,
    tiene_permiso,
)
from backend.core.roles import CodigoRol, TipoUsuario

CODIGOS_ROL_OFICIALES = {
    "ADMINISTRADOR_ORI",
    "GESTOR_ORI",
    "REVISOR_ORI",
    "SOLICITANTE_INTERNO",
    "SOLICITANTE_EXTERNO",
}
PERMISOS_GESTION_USUARIOS = {
    "usuarios.ver",
    "usuarios.crear",
    "usuarios.editar",
    "usuarios.cambiar_rol",
    "usuarios.cambiar_estado",
}
PERMISOS_EPICA_02 = {
    "aliados.ver",
    "aliados.editar",
    "aliados.cambiar_estado",
    "convenios.ver",
    "convenios.crear",
    "convenios.editar",
    "aliados.corregir_identificacion",
}


def test_codigo_rol_coincide_exactamente_con_el_mer() -> None:
    assert len(CodigoRol) == 5
    assert {rol.value for rol in CodigoRol} == CODIGOS_ROL_OFICIALES


def test_invitado_no_es_un_codigo_rol() -> None:
    assert "INVITADO" not in CodigoRol.__members__
    assert "INVITADO" not in {rol.value for rol in CodigoRol}


def test_tipo_usuario_solo_contiene_interno_y_externo() -> None:
    assert len(TipoUsuario) == 2
    assert {tipo.value for tipo in TipoUsuario} == {"INTERNO", "EXTERNO"}


def test_permisos_coinciden_con_los_alcances_integrados() -> None:
    valores = [permiso.value for permiso in Permiso.__members__.values()]
    assert set(valores) == PERMISOS_GESTION_USUARIOS | PERMISOS_EPICA_02
    assert len(valores) == len(set(valores))


def test_matriz_contiene_exactamente_todos_los_roles() -> None:
    assert set(PERMISOS_POR_ROL) == set(CodigoRol)


def test_todos_los_valores_de_la_matriz_son_inmutables() -> None:
    assert all(
        isinstance(permisos_rol, frozenset)
        for permisos_rol in PERMISOS_POR_ROL.values()
    )


def test_contenedor_de_la_matriz_es_inmutable() -> None:
    with pytest.raises(TypeError):
        PERMISOS_POR_ROL[CodigoRol.GESTOR_ORI] = frozenset(  # type: ignore[index]
            {Permiso.USUARIOS_VER}
        )


def test_administrador_ori_posee_todos_los_permisos_definidos() -> None:
    assert permisos_para_rol(CodigoRol.ADMINISTRADOR_ORI) == frozenset(Permiso)


def test_roles_reciben_solo_los_permisos_definidos_para_epica_02() -> None:
    assert permisos_para_rol(CodigoRol.GESTOR_ORI) == frozenset(Permiso) - {
        Permiso.USUARIOS_VER,
        Permiso.USUARIOS_CREAR,
        Permiso.USUARIOS_EDITAR,
        Permiso.USUARIOS_CAMBIAR_ROL,
        Permiso.USUARIOS_CAMBIAR_ESTADO,
    }
    assert Permiso.ALIADOS_CORREGIR_IDENTIFICACION in permisos_para_rol(
        CodigoRol.GESTOR_ORI
    )
    assert permisos_para_rol(CodigoRol.REVISOR_ORI) == frozenset(
        {Permiso.ALIADOS_VER, Permiso.CONVENIOS_VER}
    )
    assert permisos_para_rol(CodigoRol.SOLICITANTE_INTERNO) == frozenset()
    assert permisos_para_rol(CodigoRol.SOLICITANTE_EXTERNO) == frozenset()


def test_permisos_para_rol_devuelve_un_conjunto_inmutable() -> None:
    resultado = permisos_para_rol(CodigoRol.ADMINISTRADOR_ORI)
    assert isinstance(resultado, frozenset)
    with pytest.raises(AttributeError):
        resultado.add(Permiso.USUARIOS_VER)  # type: ignore[attr-defined]


def test_tiene_permiso_devuelve_true_o_false_segun_la_matriz() -> None:
    assert tiene_permiso(CodigoRol.ADMINISTRADOR_ORI, Permiso.USUARIOS_CREAR)
    assert not tiene_permiso(CodigoRol.GESTOR_ORI, Permiso.USUARIOS_CREAR)


@pytest.mark.parametrize("modulo", [roles, permisos])
def test_contratos_no_dependen_de_frameworks_ni_persistencia(
    modulo: ModuleType,
) -> None:
    arbol = ast.parse(inspect.getsource(modulo))
    imports = {
        nombre for nodo in ast.walk(arbol) for nombre in _nombres_importados(nodo)
    }
    prefijos_prohibidos = (
        "alembic",
        "fastapi",
        "sqlalchemy",
        "backend.db",
        "backend.migrations",
        "backend.models",
    )
    assert not any(
        nombre == prefijo or nombre.startswith(f"{prefijo}.")
        for nombre in imports
        for prefijo in prefijos_prohibidos
    )


def _nombres_importados(nodo: ast.AST) -> set[str]:
    if isinstance(nodo, ast.Import):
        return {alias.name for alias in nodo.names}
    if isinstance(nodo, ast.ImportFrom) and nodo.module:
        return {nodo.module}
    return set()
