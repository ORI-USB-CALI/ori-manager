from collections.abc import Mapping
from enum import StrEnum
from types import MappingProxyType

from backend.core.roles import CodigoRol


class Permiso(StrEnum):
    USUARIOS_VER = "usuarios.ver"
    USUARIOS_CREAR = "usuarios.crear"
    USUARIOS_EDITAR = "usuarios.editar"
    USUARIOS_CAMBIAR_ROL = "usuarios.cambiar_rol"
    USUARIOS_CAMBIAR_ESTADO = "usuarios.cambiar_estado"
    ALIADOS_VER = "aliados.ver"
    ALIADOS_EDITAR = "aliados.editar"
    ALIADOS_CAMBIAR_ESTADO = "aliados.cambiar_estado"
    ALIADOS_CORREGIR_IDENTIFICACION = "aliados.corregir_identificacion"
    CONVENIOS_VER = "convenios.ver"
    CONVENIOS_CREAR = "convenios.crear"
    CONVENIOS_EDITAR = "convenios.editar"
    CONVENIOS_REVISAR = "convenios.revisar"
    SOLICITUDES_CREAR = "solicitudes.crear"
    SOLICITUDES_VER_PROPIAS = "solicitudes.ver_propias"
    SOLICITUDES_EDITAR_PROPIAS = "solicitudes.editar_propias"
    SOLICITUDES_RADICAR = "solicitudes.radicar"
    SOLICITUDES_VER_RECIBIDAS = "solicitudes.ver_recibidas"
    SOLICITUDES_GESTIONAR_RECIBIDAS = "solicitudes.gestionar_recibidas"


_PERMISOS_GESTION_USUARIOS = frozenset(
    {
        Permiso.USUARIOS_VER,
        Permiso.USUARIOS_CREAR,
        Permiso.USUARIOS_EDITAR,
        Permiso.USUARIOS_CAMBIAR_ROL,
        Permiso.USUARIOS_CAMBIAR_ESTADO,
    }
)
_PERMISOS_GESTION_EPICA_02 = frozenset(
    {
        Permiso.ALIADOS_VER,
        Permiso.ALIADOS_EDITAR,
        Permiso.ALIADOS_CAMBIAR_ESTADO,
        Permiso.ALIADOS_CORREGIR_IDENTIFICACION,
        Permiso.CONVENIOS_VER,
        Permiso.CONVENIOS_CREAR,
        Permiso.CONVENIOS_EDITAR,
    }
)
_PERMISOS_SOLICITUDES_PROPIAS = frozenset(
    {
        Permiso.SOLICITUDES_CREAR,
        Permiso.SOLICITUDES_VER_PROPIAS,
        Permiso.SOLICITUDES_EDITAR_PROPIAS,
        Permiso.SOLICITUDES_RADICAR,
    }
)
_PERMISOS_REVISION_JURIDICA = frozenset({Permiso.CONVENIOS_REVISAR})
_PERMISOS_SOLICITUDES_RECIBIDAS = frozenset(
    {
        Permiso.SOLICITUDES_VER_RECIBIDAS,
        Permiso.SOLICITUDES_GESTIONAR_RECIBIDAS,
    }
)

PERMISOS_POR_ROL: Mapping[CodigoRol, frozenset[Permiso]] = MappingProxyType(
    {
        CodigoRol.ADMINISTRADOR_ORI: (
            _PERMISOS_GESTION_USUARIOS
            | _PERMISOS_GESTION_EPICA_02
            | _PERMISOS_SOLICITUDES_RECIBIDAS
        ),
        CodigoRol.GESTOR_ORI: (
            _PERMISOS_GESTION_EPICA_02 | _PERMISOS_SOLICITUDES_RECIBIDAS
        ),
        CodigoRol.REVISOR_ORI: (
            frozenset({Permiso.ALIADOS_VER, Permiso.CONVENIOS_VER})
            | _PERMISOS_REVISION_JURIDICA
        ),
        CodigoRol.SOLICITANTE_INTERNO: _PERMISOS_SOLICITUDES_PROPIAS,
        CodigoRol.SOLICITANTE_EXTERNO: _PERMISOS_SOLICITUDES_PROPIAS,
    }
)


def permisos_para_rol(codigo_rol: CodigoRol) -> frozenset[Permiso]:
    return PERMISOS_POR_ROL[codigo_rol]


def tiene_permiso(codigo_rol: CodigoRol, permiso: Permiso) -> bool:
    return permiso in permisos_para_rol(codigo_rol)
