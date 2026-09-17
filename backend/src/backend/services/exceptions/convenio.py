from backend.services.exceptions.base import NoEncontradoError


class ConvenioNoEncontradoError(NoEncontradoError):
    """No existe un convenio con el identificador solicitado."""


class SolicitudInvalidaError(ValueError):
    """CA-07 (aplicado a solicitud): la solicitud indicada no existe."""


class AliadoInvalidoError(ValueError):
    """CA-07: el aliado seleccionado no existe."""


class ConvenioDuplicadoError(ValueError):
    """RN-07: una solicitud origina a lo sumo un convenio (1:1)."""


class UnidadOrganizacionalRequeridaError(ValueError):
    """MER, regla de aplicacion 2: obligatoria cuando alcance = PROGRAMA."""
