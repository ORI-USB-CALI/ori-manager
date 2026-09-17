from backend.models.enums import RolUsuario
from backend.services.exceptions import PermisoDenegadoError


def validar_rol(rol: RolUsuario, roles_permitidos: set[RolUsuario]) -> None:
    """Corta la operación cuando el rol no está entre los permitidos."""
    if rol not in roles_permitidos:
        raise PermisoDenegadoError(f"El rol '{rol.value}' no tiene permiso para esta operación")
