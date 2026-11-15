"""Fuentes congeladas y reconocimiento conservador de la precarga historica HU-12."""

import re
from datetime import date

from backend.models.convenio import Convenio
from backend.models.version_convenio import VersionConvenio

# Firma estructural de la plantilla original (7f2a4c9d1e30), no de la plantilla
# activa mutable. Nunca se usa para eliminar o reconstruir contenido aprobado.
_PRECARGA_HU12 = (
    ("heading", 1, "PROYECTO DE CONVENIO"),
    ("paragraph", None, "Solicitud de origen: {{solicitud.consecutivo}}"),
    ("heading", 2, "Información de origen"),
    ("paragraph", None, "Solicitante: {{solicitud.solicitante}}"),
    ("paragraph", None, "Contraparte propuesta: {{solicitud.contraparte}}"),
    ("paragraph", None, "Contacto de contraparte: {{solicitud.contacto_contraparte}}"),
    ("paragraph", None, "Tipo de convenio: {{solicitud.tipo_convenio}}"),
    ("heading", 2, "Justificación"),
    ("paragraph", None, "{{solicitud.justificacion}}"),
    ("heading", 2, "Objeto propuesto"),
    ("paragraph", None, "{{solicitud.objeto}}"),
    ("heading", 2, "Actividades"),
    ("paragraph", None, "{{solicitud.actividades}}"),
    ("heading", 2, "Metas"),
    ("paragraph", None, "{{solicitud.metas}}"),
    ("heading", 2, "Implicación financiera"),
    ("paragraph", None, "{{solicitud.implicacion_financiera}}"),
    ("heading", 2, "Vigencia y renovación"),
    ("paragraph", None, "Vigencia estimada: {{solicitud.vigencia}}"),
    ("paragraph", None, "Renovación: {{solicitud.renovacion}}"),
    ("heading", 2, "Supervisión propuesta"),
    ("paragraph", None, "Supervisor USB: {{solicitud.supervisor_usb}}"),
    (
        "paragraph",
        None,
        "Supervisor de contraparte: {{solicitud.supervisor_contraparte}}",
    ),
)
ERROR_PRECARGA = (
    "contenido_contractual_ambiguo: precarga de solicitud HU-12; "
    "requiere revision juridica, no sustitucion de texto aprobado"
)
_CAMPOS = (
    "tipo_convenio_id",
    "unidad_organizacional_id",
    "objeto",
    "alcance",
    "implicacion_financiera",
    "fecha_inicio",
    "fecha_vencimiento",
    "duracion_meses",
)


def datos_definitivos(convenio: Convenio, version: VersionConvenio | None) -> dict:
    snapshot = (version.snapshot_metadata or {}) if version else {}
    datos = {
        campo: snapshot[campo] if campo in snapshot else getattr(convenio, campo)
        for campo in _CAMPOS
    }
    for campo in ("fecha_inicio", "fecha_vencimiento"):
        if isinstance(datos[campo], str):
            datos[campo] = date.fromisoformat(datos[campo])
    return datos


def precarga_hu12_reconocible(contenido: dict) -> bool:
    if not isinstance(contenido, dict):
        return False
    bloques = contenido.get("content", [])
    if not isinstance(bloques, list):
        return False

    def coincide(bloque, patron):
        if not isinstance(bloque, dict):
            return False
        tipo, nivel, texto = patron
        if bloque.get("type") != tipo or bloque.get("attrs", {}) != (
            {"level": nivel} if nivel else {}
        ):
            return False
        hijos = bloque.get("content", [])
        if not isinstance(hijos, list) or len(hijos) != 1 or not isinstance(hijos[0], dict):
            return False
        if hijos[0].get("type") != "text" or hijos[0].get("marks"):
            return False
        partes = re.split(r"(\{\{solicitud\.[a-z_]+\}\})", texto)
        regex = "".join(
            r"[\s\S]*" if p.startswith("{{solicitud.") else re.escape(p) for p in partes
        )
        return re.fullmatch(regex, hijos[0].get("text", "")) is not None

    return any(
        all(coincide(b, p) for b, p in zip(bloques[inicio:], _PRECARGA_HU12))
        for inicio in range(len(bloques) - len(_PRECARGA_HU12) + 1)
    )
