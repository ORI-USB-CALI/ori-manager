from collections.abc import Mapping
from enum import StrEnum
from types import MappingProxyType

from backend.core.roles import CodigoRol


class Permiso(StrEnum):
    """Capacidades de gestion de usuarios incluidas en el alcance actual."""

    USUARIOS_VER = "usuarios.ver"
    USUARIOS_CREAR = "usuarios.crear"
    USUARIOS_EDITAR = "usuarios.editar"
    USUARIOS_CAMBIAR_ROL = "usuarios.cambiar_rol"
    USUARIOS_CAMBIAR_ESTADO = "usuarios.cambiar_estado"


_PERMISOS_GESTION_USUARIOS = frozenset(Permiso)

PERMISOS_POR_ROL: Mapping[CodigoRol, frozenset[Permiso]] = MappingProxyType(
    {
        CodigoRol.ADMINISTRADOR_ORI: _PERMISOS_GESTION_USUARIOS,
        CodigoRol.GESTOR_ORI: frozenset(),
        CodigoRol.REVISOR_ORI: frozenset(),
        CodigoRol.SOLICITANTE_INTERNO: frozenset(),
        CodigoRol.SOLICITANTE_EXTERNO: frozenset(),
    }
)


def permisos_para_rol(codigo_rol: CodigoRol) -> frozenset[Permiso]:
    """Devuelve el conjunto inmutable de permisos asignado al rol."""

    return PERMISOS_POR_ROL[codigo_rol]


def tiene_permiso(codigo_rol: CodigoRol, permiso: Permiso) -> bool:
    """Indica si el rol tiene asignado el permiso solicitado."""

    return permiso in permisos_para_rol(codigo_rol)
