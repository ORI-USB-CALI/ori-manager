"""Validación de completitud previa a la exportación del convenio (CA-03 de HU-24).

El validador no consulta la base de datos ni renderiza: recibe el convenio ya
cargado (aliado, solicitud, versiones y procesos de firmas con sus firmas) y
devuelve qué datos obligatorios faltan para emitir un documento oficial.

`version_contractual` y `proceso_firmas_de_version` también los usa el mapeo
del PDF y del Excel, para que lo validado sea exactamente lo que se exporta.
"""

from __future__ import annotations

from backend.models.convenio import Convenio
from backend.models.enums import (
    EstadoProcesoFirmasConvenio,
    ParteFirmaConvenio,
    RolFirmanteConvenio,
)
from backend.models.firma_convenio import FirmaConvenio
from backend.models.proceso_firmas_convenio import ProcesoFirmasConvenio
from backend.models.version_convenio import VersionConvenio
from backend.services.contenido_convenio import (
    ContenidoConvenioInvalido,
    documento_tiene_texto,
)

# Un proceso cancelado (por ejemplo, tras un cambio sustancial) ya no vale.
_ESTADOS_PROCESO_VIGENTE = frozenset(
    {
        EstadoProcesoFirmasConvenio.CONFIGURACION.value,
        EstadoProcesoFirmasConvenio.EN_CURSO.value,
        EstadoProcesoFirmasConvenio.COMPLETADO.value,
    }
)
# La contraparte la representa la entidad externa o la unidad solicitante interna.
_PARTES_ENTIDAD = frozenset(
    {
        ParteFirmaConvenio.REPRESENTANTE_LEGAL_ENTIDAD.value,
        ParteFirmaConvenio.UNIDAD_SOLICITANTE.value,
    }
)


def _vacio(valor: str | None) -> bool:
    return valor is None or not valor.strip()


def version_contractual(convenio: Convenio) -> VersionConvenio | None:
    """La versión que indica el convenio. Nunca se sustituye por otra."""
    return next(
        (
            version
            for version in convenio.versiones
            if version.numero == convenio.version_actual
        ),
        None,
    )


def _procesos_vigentes(convenio: Convenio) -> list[ProcesoFirmasConvenio]:
    return [
        proceso
        for proceso in convenio.procesos_firmas
        if proceso.estado in _ESTADOS_PROCESO_VIGENTE
    ]


def proceso_firmas_de_version(
    convenio: Convenio, version: VersionConvenio | None
) -> ProcesoFirmasConvenio | None:
    """Proceso de firmas vigente de esa versión: sus firmantes son los únicos
    que corresponden al documento que se exporta."""
    # Sin id (objeto aún no persistido) no hay forma de asociarla a un proceso.
    if version is None or version.id is None:
        return None
    return next(
        (
            proceso
            for proceso in _procesos_vigentes(convenio)
            if proceso.version_convenio_id == version.id
        ),
        None,
    )


class ConvenioExportValidator:
    """Indica qué datos obligatorios le faltan al convenio para exportarlo."""

    def campos_faltantes(self, convenio: Convenio) -> list[str]:
        faltantes: list[str] = []
        if _vacio(convenio.codigo):
            faltantes.append("codigo_convenio")
        if convenio.aliado is None and _vacio(convenio.solicitud.nombre_aliado_propuesto):
            faltantes.append("entidad_participante")
        if convenio.fecha_inicio is None:
            faltantes.append("fecha_inicio_vigencia")
        if convenio.fecha_vencimiento is None:
            faltantes.append("fecha_fin_vigencia")
        if _vacio(convenio.objeto):
            faltantes.append("objeto")
        if convenio.tipo_convenio_id is None and convenio.tipo_convenio is None:
            faltantes.append("tipo_convenio")

        version = version_contractual(convenio)
        if version is None:
            faltantes.append("version_contractual")
        elif not self._tiene_texto(version):
            faltantes.append("clausulas")

        # Solo cuentan los firmantes del proceso de la versión actual. Los
        # procesos de otras versiones (por ejemplo, uno COMPLETADO de la v1) no
        # bloquean la exportación ni sustituyen a los de la versión actual.
        firmantes = self._firmantes_con_nombre(convenio, version)
        if not any(
            firma.rol_firmante == RolFirmanteConvenio.RECTOR.value for firma in firmantes
        ):
            faltantes.append("representante_legal_institucion")
        if not any(firma.parte in _PARTES_ENTIDAD for firma in firmantes):
            faltantes.append("representante_legal_entidad")
        return faltantes

    @staticmethod
    def _tiene_texto(version: VersionConvenio) -> bool:
        if not version.contenido:
            return False
        try:
            return documento_tiene_texto(version.contenido)
        except ContenidoConvenioInvalido:
            return False

    @staticmethod
    def _firmantes_con_nombre(
        convenio: Convenio, version: VersionConvenio | None
    ) -> list[FirmaConvenio]:
        proceso = proceso_firmas_de_version(convenio, version)
        if proceso is None:
            return []
        return [firma for firma in proceso.firmas if not _vacio(firma.nombre_firmante)]
