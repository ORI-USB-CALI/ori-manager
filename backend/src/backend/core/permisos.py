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
    CONVENIOS_GESTIONAR_REVISION_CONTRAPARTE = "convenios.gestionar_revision_contraparte"
    CONVENIOS_REVISAR_CONTRAPARTE_PROPIA = "convenios.revisar_contraparte_propia"
    SOLICITUDES_CREAR = "solicitudes.crear"
    SOLICITUDES_VER_PROPIAS = "solicitudes.ver_propias"
    SOLICITUDES_EDITAR_PROPIAS = "solicitudes.editar_propias"
    SOLICITUDES_RADICAR = "solicitudes.radicar"


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
        Permiso.CONVENIOS_GESTIONAR_REVISION_CONTRAPARTE,
    }
)
_PERMISOS_SOLICITUDES_PROPIAS = frozenset(
    {
        Permiso.SOLICITUDES_CREAR,
        Permiso.SOLICITUDES_VER_PROPIAS,
        Permiso.SOLICITUDES_EDITAR_PROPIAS,
        Permiso.SOLICITUDES_RADICAR,
        Permiso.CONVENIOS_REVISAR_CONTRAPARTE_PROPIA,
    }
)

PERMISOS_POR_ROL: Mapping[CodigoRol, frozenset[Permiso]] = MappingProxyType(
    {
        CodigoRol.ADMINISTRADOR_ORI: (
            _PERMISOS_GESTION_USUARIOS
            | _PERMISOS_GESTION_EPICA_02
            | _PERMISOS_SOLICITUDES_PROPIAS
        ),
        CodigoRol.GESTOR_ORI: _PERMISOS_GESTION_EPICA_02,
        CodigoRol.REVISOR_ORI: frozenset({Permiso.ALIADOS_VER, Permiso.CONVENIOS_VER}),
        CodigoRol.SOLICITANTE_INTERNO: _PERMISOS_SOLICITUDES_PROPIAS,
        CodigoRol.SOLICITANTE_EXTERNO: _PERMISOS_SOLICITUDES_PROPIAS,
    }
)


def permisos_para_rol(codigo_rol: CodigoRol) -> frozenset[Permiso]:
    return PERMISOS_POR_ROL[codigo_rol]


def tiene_permiso(codigo_rol: CodigoRol, permiso: Permiso) -> bool:
    return permiso in permisos_para_rol(codigo_rol)
