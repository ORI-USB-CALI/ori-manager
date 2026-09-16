from enum import StrEnum


class Rol(StrEnum):
    ADMINISTRADOR = "administrador"
    USUARIO_ORI = "usuario_ori"


class Permiso(StrEnum):
    USUARIOS_GESTIONAR = "usuarios.gestionar"
    ALIADOS_VER = "aliados.ver"
    ALIADOS_GESTIONAR = "aliados.gestionar"
    CONVENIOS_VER = "convenios.ver"
    CONVENIOS_GESTIONAR = "convenios.gestionar"


# Los endpoints chequean permisos, nunca roles: agregar un rol es una entrada aquí.
# El Invitado no es un rol almacenado: es una petición sin sesión.
PERMISOS_POR_ROL: dict[Rol, frozenset[Permiso]] = {
    Rol.ADMINISTRADOR: frozenset(Permiso),
    Rol.USUARIO_ORI: frozenset({Permiso.ALIADOS_VER, Permiso.CONVENIOS_VER}),
}
