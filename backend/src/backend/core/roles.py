from enum import StrEnum


class CodigoRol(StrEnum):
    """Codigos de los roles autenticados definidos por el MER."""

    ADMINISTRADOR_ORI = "ADMINISTRADOR_ORI"
    GESTOR_ORI = "GESTOR_ORI"
    REVISOR_ORI = "REVISOR_ORI"
    SOLICITANTE_INTERNO = "SOLICITANTE_INTERNO"
    SOLICITANTE_EXTERNO = "SOLICITANTE_EXTERNO"


class TipoUsuario(StrEnum):
    """Tipos de usuario definidos por el MER."""

    INTERNO = "INTERNO"
    EXTERNO = "EXTERNO"
