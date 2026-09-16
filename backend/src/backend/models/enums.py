from enum import Enum


class TipoAliado(str, Enum):
    UNIVERSIDAD = "universidad"
    COLEGIO = "colegio"
    EMPRESA = "empresa"
    ENTIDAD_GUBERNAMENTAL = "entidad_gubernamental"


class EstadoAliado(str, Enum):
    ACTIVO = "activo"
    INACTIVO = "inactivo"


class EstadoConvenio(str, Enum):
    EN_TRAMITE = "en_tramite"
    VIGENTE = "vigente"
    POR_VENCER = "por_vencer"
    VENCIDO = "vencido"
    RENOVADO = "renovado"
    FINALIZADO = "finalizado"
    CANCELADO = "cancelado"


class RolUsuario(str, Enum):
    ADMINISTRADOR_ORI = "administrador_ori"
    GESTOR_ORI = "gestor_ori"
    REVISOR_ORI = "revisor_ori"
    SOLICITANTE_INTERNO = "solicitante_interno"
    SOLICITANTE_EXTERNO = "solicitante_externo"
    INVITADO = "invitado"
