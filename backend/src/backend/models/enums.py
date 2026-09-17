from enum import Enum

# NOTA DE INTEGRACION: este enum debe coincidir exactamente con
# backend.models.enums.RolUsuario definido en feature/HU-04-aliados.
# Se declara aqui duplicado porque esa rama aun no esta fusionada con
# feature/hu-06-registro-base-convenio; al integrar ambas ramas, dejar
# una sola definicion (en models/enums.py) y actualizar los imports.


class RolUsuario(str, Enum):
    ADMINISTRADOR_ORI = "administrador_ori"
    GESTOR_ORI = "gestor_ori"
    REVISOR_ORI = "revisor_ori"
    SOLICITANTE_INTERNO = "solicitante_interno"
    SOLICITANTE_EXTERNO = "solicitante_externo"
    INVITADO = "invitado"
