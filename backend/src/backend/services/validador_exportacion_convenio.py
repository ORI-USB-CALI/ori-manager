"""Validación de completitud previa a la exportación del convenio (CA-03 de HU-24).

El validador no consulta la base de datos ni renderiza: recibe el convenio ya
cargado (aliado, solicitud, versiones y procesos de firmas con sus firmas) y
devuelve qué datos obligatorios faltan para emitir un documento oficial.
"""

from __future__ import annotations

from backend.models.convenio import Convenio
from backend.models.enums import (
    EstadoProcesoFirmasConvenio,
    ParteFirmaConvenio,
    RolFirmanteConvenio,
)
from backend.models.firma_convenio import FirmaConvenio
from backend.models.version_convenio import VersionConvenio
from backend.services.contenido_convenio import (
    ContenidoConvenioInvalido,
    documento_tiene_texto,
)

# Mismo criterio que el mapper del PDF: se imprime el primer proceso de firmas
# que no esté cancelado, así que es el que se valida.
_ESTADOS_PROCESO_EXPORTABLE = frozenset(
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


class ConvenioExportValidator:
    """Indica qué datos obligatorios le faltan al convenio para exportarlo.

    Un dato falta cuando el documento oficial saldría con un texto de relleno
    ("No informado", "Por definir") en su lugar.
    """

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
        if not self._tiene_clausulas(convenio):
            faltantes.append("clausulas")

        firmantes = self._firmantes_con_nombre(convenio)
        if not any(
            firma.rol_firmante == RolFirmanteConvenio.RECTOR.value for firma in firmantes
        ):
            faltantes.append("representante_legal_institucion")
        if not any(firma.parte in _PARTES_ENTIDAD for firma in firmantes):
            faltantes.append("representante_legal_entidad")
        return faltantes

    @staticmethod
    def _version_exportada(convenio: Convenio) -> VersionConvenio | None:
        # Igual que el mapper del PDF: la versión actual y, si no aparece, la última.
        for version in convenio.versiones:
            if version.numero == convenio.version_actual:
                return version
        return max(convenio.versiones, key=lambda version: version.numero, default=None)

    def _tiene_clausulas(self, convenio: Convenio) -> bool:
        version = self._version_exportada(convenio)
        if version is None or not version.contenido:
            return False
        try:
            return documento_tiene_texto(version.contenido)
        except ContenidoConvenioInvalido:
            return False

    @staticmethod
    def _firmantes_con_nombre(convenio: Convenio) -> list[FirmaConvenio]:
        proceso = next(
            (
                proceso
                for proceso in convenio.procesos_firmas
                if proceso.estado in _ESTADOS_PROCESO_EXPORTABLE
            ),
            None,
        )
        if proceso is None:
            return []
        return [firma for firma in proceso.firmas if not _vacio(firma.nombre_firmante)]
