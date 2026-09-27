from __future__ import annotations

import json
import re
from copy import deepcopy
from typing import Any

from backend.models.solicitud_convenio import SolicitudConvenio

MAX_BYTES = 1_000_000
MAX_DEPTH = 24
MAX_NODES = 10_000
MAX_TEXT_LENGTH = 500_000
MAX_ORDERED_LIST_START = 1_000_000

_TIPOS_CONTENEDORES = {
    "doc",
    "paragraph",
    "heading",
    "bulletList",
    "orderedList",
    "listItem",
}
_TIPOS_HOJA = {"text", "hardBreak"}
_MARCAS = {"bold", "italic"}
_HIJOS_PERMITIDOS = {
    "doc": {"paragraph", "heading", "bulletList", "orderedList"},
    "paragraph": {"text", "hardBreak"},
    "heading": {"text", "hardBreak"},
    "bulletList": {"listItem"},
    "orderedList": {"listItem"},
    "listItem": {"paragraph", "heading", "bulletList", "orderedList"},
}
_PLACEHOLDER = re.compile(r"\{\{\s*solicitud\.([a-z_]+)\s*\}\}")


class ContenidoConvenioInvalido(ValueError):
    pass


def validar_contenido(contenido: object) -> dict[str, Any]:
    """Valida el subconjunto de JSON ProseMirror habilitado por HU-12.

    El backend nunca acepta HTML ni extensiones desconocidas. Esto mantiene la
    fuente canónica independiente de lo que un navegador pueda pegar o renderizar.
    """
    if not isinstance(contenido, dict):
        raise ContenidoConvenioInvalido("El contenido debe ser un documento JSON")
    try:
        tamano = len(json.dumps(contenido, ensure_ascii=False).encode("utf-8"))
    except (TypeError, ValueError) as exc:
        raise ContenidoConvenioInvalido("El contenido no es JSON válido") from exc
    if tamano > MAX_BYTES:
        raise ContenidoConvenioInvalido("El documento supera el tamaño permitido")

    metricas = {"nodos": 0, "texto": 0}
    _validar_nodo(contenido, profundidad=1, metricas=metricas, raiz=True)
    return contenido


def _validar_nodo(
    nodo: object,
    *,
    profundidad: int,
    metricas: dict[str, int],
    raiz: bool = False,
) -> None:
    if not isinstance(nodo, dict):
        raise ContenidoConvenioInvalido("Cada nodo del documento debe ser un objeto")
    if profundidad > MAX_DEPTH:
        raise ContenidoConvenioInvalido("El documento supera la profundidad permitida")
    metricas["nodos"] += 1
    if metricas["nodos"] > MAX_NODES:
        raise ContenidoConvenioInvalido("El documento contiene demasiados nodos")

    tipo = nodo.get("type")
    if tipo not in _TIPOS_CONTENEDORES | _TIPOS_HOJA:
        raise ContenidoConvenioInvalido(f"Tipo de nodo no permitido: {tipo!r}")
    if raiz and tipo != "doc":
        raise ContenidoConvenioInvalido("El nodo raíz debe ser de tipo doc")
    if not raiz and tipo == "doc":
        raise ContenidoConvenioInvalido("Un documento no puede contener otro documento")

    permitidas = {"type"}
    if tipo in _TIPOS_CONTENEDORES:
        permitidas.add("content")
    if tipo in {"heading", "orderedList"}:
        permitidas.add("attrs")
    if tipo == "text":
        permitidas.update({"text", "marks"})
    desconocidas = set(nodo) - permitidas
    if desconocidas:
        raise ContenidoConvenioInvalido(
            f"Propiedades no permitidas en {tipo}: {', '.join(sorted(desconocidas))}"
        )

    if tipo == "text":
        texto = nodo.get("text")
        if not isinstance(texto, str):
            raise ContenidoConvenioInvalido("Un nodo text requiere una cadena")
        metricas["texto"] += len(texto)
        if metricas["texto"] > MAX_TEXT_LENGTH:
            raise ContenidoConvenioInvalido("El documento contiene demasiado texto")
        _validar_marcas(nodo.get("marks", []))
        return

    if tipo == "hardBreak":
        return

    _validar_atributos(tipo, nodo.get("attrs"))
    hijos = nodo.get("content", [])
    if not isinstance(hijos, list):
        raise ContenidoConvenioInvalido(f"content de {tipo} debe ser una lista")
    if tipo in {"bulletList", "orderedList"} and not hijos:
        raise ContenidoConvenioInvalido(f"El nodo {tipo} no puede estar vacío")
    if tipo == "listItem" and (
        not hijos
        or not isinstance(hijos[0], dict)
        or hijos[0].get("type") != "paragraph"
    ):
        raise ContenidoConvenioInvalido(
            "Un elemento de lista debe iniciar con un párrafo"
        )
    for hijo in hijos:
        if (
            not isinstance(hijo, dict)
            or hijo.get("type") not in _HIJOS_PERMITIDOS[tipo]
        ):
            raise ContenidoConvenioInvalido(
                f"{tipo} no puede contener un nodo {hijo.get('type') if isinstance(hijo, dict) else 'inválido'}"
            )
        _validar_nodo(
            hijo,
            profundidad=profundidad + 1,
            metricas=metricas,
        )


def _validar_marcas(marcas: object) -> None:
    if not isinstance(marcas, list):
        raise ContenidoConvenioInvalido("marks debe ser una lista")
    for marca in marcas:
        if not isinstance(marca, dict) or set(marca) != {"type"}:
            raise ContenidoConvenioInvalido("La marca contiene atributos no permitidos")
        if marca["type"] not in _MARCAS:
            raise ContenidoConvenioInvalido(f"Marca no permitida: {marca['type']!r}")


def _validar_atributos(tipo: str, atributos: object) -> None:
    if atributos is None:
        return
    if not isinstance(atributos, dict):
        raise ContenidoConvenioInvalido(f"attrs de {tipo} debe ser un objeto")
    if tipo == "heading":
        nivel = atributos.get("level")
        if (
            set(atributos) != {"level"}
            or not isinstance(nivel, int)
            or isinstance(nivel, bool)
            or nivel not in {1, 2}
        ):
            raise ContenidoConvenioInvalido("El nivel del encabezado debe ser 1 o 2")
        return
    if tipo == "orderedList":
        if set(atributos) - {"start", "type"}:
            raise ContenidoConvenioInvalido(
                "La lista numerada contiene atributos no permitidos"
            )
        inicio = atributos.get("start", 1)
        if (
            not isinstance(inicio, int)
            or isinstance(inicio, bool)
            or not 1 <= inicio <= MAX_ORDERED_LIST_START
        ):
            raise ContenidoConvenioInvalido(
                "El inicio de la lista numerada es inválido"
            )
        if atributos.get("type") is not None:
            raise ContenidoConvenioInvalido(
                "El tipo de numeración de la lista no está soportado"
            )
        return
    if atributos:
        raise ContenidoConvenioInvalido(f"{tipo} no admite atributos")


def documento_tiene_texto(contenido: dict[str, Any]) -> bool:
    validar_contenido(contenido)

    def recorrer(nodo: dict[str, Any]) -> bool:
        return bool(str(nodo.get("text", "")).strip()) or any(
            recorrer(hijo) for hijo in nodo.get("content", [])
        )

    return recorrer(contenido)


def expandir_plantilla(
    contenido_base: dict[str, Any],
    solicitud: SolicitudConvenio,
    nombre_tipo_convenio: str | None,
) -> dict[str, Any]:
    validar_contenido(contenido_base)
    valores = _valores_solicitud(solicitud, nombre_tipo_convenio)
    resultado = deepcopy(contenido_base)

    def recorrer(nodo: dict[str, Any]) -> None:
        if nodo.get("type") == "text":
            texto = nodo["text"]

            def sustituir(coincidencia: re.Match[str]) -> str:
                clave = coincidencia.group(1)
                if clave not in valores:
                    raise ContenidoConvenioInvalido(
                        f"Placeholder de plantilla no permitido: solicitud.{clave}"
                    )
                return valores[clave]

            nodo["text"] = _PLACEHOLDER.sub(sustituir, texto)
        for hijo in nodo.get("content", []):
            recorrer(hijo)

    recorrer(resultado)
    validar_contenido(resultado)
    return resultado


def _unir(*partes: str | None) -> str:
    valor = " · ".join(parte.strip() for parte in partes if parte and parte.strip())
    return valor or "No informado"


def _valores_solicitud(
    solicitud: SolicitudConvenio, nombre_tipo_convenio: str | None
) -> dict[str, str]:
    return {
        "consecutivo": solicitud.consecutivo,
        "solicitante": _unir(
            solicitud.solicitante_nombre,
            solicitud.solicitante_cargo,
            solicitud.solicitante_entidad,
            solicitud.solicitante_unidad,
            solicitud.solicitante_programa,
            solicitud.solicitante_correo,
        ),
        "contraparte": _unir(
            solicitud.nombre_aliado_propuesto,
            solicitud.identificacion_aliado_propuesto,
            solicitud.pais_aliado_propuesto,
            solicitud.ciudad_aliado_propuesto,
            solicitud.correo_aliado_propuesto,
        ),
        "contacto_contraparte": _unir(
            solicitud.contacto_contraparte_nombre,
            solicitud.contacto_contraparte_cargo,
            solicitud.contacto_contraparte_telefono,
            solicitud.contacto_contraparte_correo,
        ),
        "tipo_convenio": nombre_tipo_convenio or "No informado",
        "justificacion": solicitud.justificacion or "No informado",
        "objeto": solicitud.objeto or "No informado",
        "actividades": solicitud.actividades_por_parte or "No informado",
        "metas": solicitud.metas_esperadas or "No informado",
        "implicacion_financiera": solicitud.implicacion_financiera or "No informado",
        "vigencia": solicitud.vigencia_estimada or "No informado",
        "renovacion": solicitud.requisitos_renovacion or "No informado",
        "supervisor_usb": _unir(
            solicitud.supervisor_usb_nombre,
            solicitud.supervisor_usb_cargo,
            solicitud.supervisor_usb_telefono,
            solicitud.supervisor_usb_correo,
        ),
        "supervisor_contraparte": _unir(
            solicitud.supervisor_contraparte_nombre,
            solicitud.supervisor_contraparte_cargo,
            solicitud.supervisor_contraparte_telefono,
            solicitud.supervisor_contraparte_correo,
        ),
    }
