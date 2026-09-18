from enum import StrEnum


class TipoAliado(StrEnum):
    UNIVERSIDAD = "UNIVERSIDAD"
    COLEGIO = "COLEGIO"
    EMPRESA = "EMPRESA"
    ENTIDAD_GUBERNAMENTAL = "ENTIDAD_GUBERNAMENTAL"


class NaturalezaConvenio(StrEnum):
    MARCO = "MARCO"
    ESPECIFICO = "ESPECIFICO"


class TipoSolicitante(StrEnum):
    INTERNO = "INTERNO"
    EXTERNO = "EXTERNO"


class EstadoSolicitud(StrEnum):
    BORRADOR = "BORRADOR"
    RADICADA = "RADICADA"
    EN_ESTUDIO = "EN_ESTUDIO"
    DEVUELTA = "DEVUELTA"
    APROBADA = "APROBADA"
    RECHAZADA = "RECHAZADA"


class EstadoConvenio(StrEnum):
    EN_TRAMITE = "EN_TRAMITE"
    VIGENTE = "VIGENTE"
    POR_VENCER = "POR_VENCER"
    VENCIDO = "VENCIDO"
    RENOVADO = "RENOVADO"
    FINALIZADO = "FINALIZADO"
    CANCELADO = "CANCELADO"


class AlcanceConvenio(StrEnum):
    PROGRAMA = "PROGRAMA"
    INSTITUCIONAL = "INSTITUCIONAL"
