from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from backend.models.documento import Documento
from backend.models.solicitud_version import SolicitudVersion
from backend.schemas.comparacion_versiones import (
    CambioCampo,
    CambiosDocumentos,
    ComparacionVersiones,
    DocumentoSustituido,
    DocumentoVersionLeer,
    VersionComparadaLeer,
)
from backend.services.solicitudes import ErrorSolicitud, SolicitudNoEncontrada

# Etiquetas legibles de los campos del formulario (SolicitudCampos). Una clave
# sin etiqueta se muestra con su nombre legible, ver _etiqueta.
ETIQUETAS_CAMPOS: dict[str, str] = {
    "nombre_aliado_propuesto": "Nombre del aliado propuesto",
    "tipo_identificacion_aliado_propuesto": "Tipo de identificación del aliado",
    "identificacion_aliado_propuesto": "Identificación del aliado",
    "tipo_aliado_propuesto": "Tipo de aliado",
    "correo_aliado_propuesto": "Correo del aliado",
    "pais_aliado_propuesto": "País del aliado",
    "ciudad_aliado_propuesto": "Ciudad del aliado",
    "telefono_aliado_propuesto": "Teléfono del aliado",
    "direccion_aliado_propuesto": "Dirección del aliado",
    "sector_economico_aliado_propuesto": "Sector económico del aliado",
    "tipo_convenio_id": "Tipo de convenio",
    "justificacion": "Justificación",
    "objeto": "Objeto",
    "actividades_por_parte": "Actividades por parte",
    "metas_esperadas": "Metas esperadas",
    "implicacion_financiera": "Implicación financiera",
    "vigencia_estimada": "Vigencia estimada",
    "requisitos_renovacion": "Requisitos de renovación",
    "observaciones": "Observaciones",
    "contacto_contraparte_nombre": "Nombre del contacto de la contraparte",
    "contacto_contraparte_cargo": "Cargo del contacto de la contraparte",
    "contacto_contraparte_telefono": "Teléfono del contacto de la contraparte",
    "contacto_contraparte_correo": "Correo del contacto de la contraparte",
    "supervisor_usb_nombre": "Nombre del supervisor USB",
    "supervisor_usb_cargo": "Cargo del supervisor USB",
    "supervisor_usb_telefono": "Teléfono del supervisor USB",
    "supervisor_usb_correo": "Correo del supervisor USB",
    "supervisor_contraparte_nombre": "Nombre del supervisor de la contraparte",
    "supervisor_contraparte_cargo": "Cargo del supervisor de la contraparte",
    "supervisor_contraparte_telefono": "Teléfono del supervisor de la contraparte",
    "supervisor_contraparte_correo": "Correo del supervisor de la contraparte",
    "solicitante_nombre": "Nombre del solicitante",
    "solicitante_correo": "Correo del solicitante",
    "solicitante_documento": "Documento del solicitante",
    "solicitante_cargo": "Cargo del solicitante",
    "solicitante_entidad": "Entidad del solicitante",
    "solicitante_unidad": "Unidad del solicitante",
    "solicitante_programa": "Programa del solicitante",
    "aprobada_por_director": "Aprobada por el director",
    "fecha_aprobacion_director": "Fecha de aprobación del director",
}


class VersionSolicitudNoEncontrada(SolicitudNoEncontrada):
    pass


class ComparacionInvalida(ErrorSolicitud):
    pass


def _etiqueta(campo: str) -> str:
    return ETIQUETAS_CAMPOS.get(campo) or campo.replace("_", " ").capitalize()


def _normalizar(valor: object) -> object:
    return None if valor == "" else valor


def comparar_campos(
    anteriores: dict[str, Any], nuevos: dict[str, Any]
) -> list[CambioCampo]:
    """CA-02: solo los campos que cambiaron; vacío y null cuentan como iguales."""
    # Primero el orden del formulario anterior y luego las claves nuevas.
    claves = list(dict.fromkeys([*anteriores, *nuevos]))
    cambios = []
    for campo in claves:
        anterior = _normalizar(anteriores.get(campo))
        nuevo = _normalizar(nuevos.get(campo))
        if anterior != nuevo:
            cambios.append(
                CambioCampo(
                    campo=campo,
                    etiqueta=_etiqueta(campo),
                    valor_anterior=anterior,
                    valor_nuevo=nuevo,
                )
            )
    return cambios


def _extraer(
    pendientes: list[Documento], criterio: Callable[[Documento], bool]
) -> Documento | None:
    for indice, documento in enumerate(pendientes):
        if criterio(documento):
            return pendientes.pop(indice)
    return None


def clasificar_documentos(
    anteriores: Sequence[Documento], nuevos: Sequence[Documento]
) -> CambiosDocumentos:
    """CA-03: clasifica los documentos de dos versiones.

    Mismo id es el mismo documento. Mismo tipo y nombre con otro id se considera
    el mismo archivo vuelto a cargar: sustituido solo si cambió su tamaño. Lo que
    queda sin pareja se empareja por tipo en orden de id (sale uno y entra otro
    del mismo tipo = sustituido). Lo demás son altas o bajas.
    """
    restantes = sorted(anteriores, key=lambda item: item.id)
    sin_pareja: list[Documento] = []
    sustituidos: list[tuple[Documento, Documento]] = []
    for nuevo in sorted(nuevos, key=lambda item: item.id):
        if _extraer(restantes, lambda item, nuevo=nuevo: item.id == nuevo.id):
            continue
        anterior = _extraer(
            restantes,
            lambda item, nuevo=nuevo: item.tipo == nuevo.tipo
            and item.nombre_archivo == nuevo.nombre_archivo,
        )
        if anterior is None:
            sin_pareja.append(nuevo)
        elif anterior.tamano_bytes != nuevo.tamano_bytes:
            sustituidos.append((anterior, nuevo))

    agregados: list[Documento] = []
    for nuevo in sin_pareja:
        anterior = _extraer(
            restantes, lambda item, nuevo=nuevo: item.tipo == nuevo.tipo
        )
        if anterior is None:
            agregados.append(nuevo)
        else:
            sustituidos.append((anterior, nuevo))

    leer = DocumentoVersionLeer.model_validate
    return CambiosDocumentos(
        agregados=[leer(item) for item in agregados],
        eliminados=[leer(item) for item in restantes],
        sustituidos=[
            DocumentoSustituido(tipo=nuevo.tipo, anterior=leer(anterior), nuevo=leer(nuevo))
            for anterior, nuevo in sorted(sustituidos, key=lambda par: par[1].id)
        ],
    )


class ServicioComparacionVersiones:
    def __init__(self, db: Session):
        self.db = db

    def _version(self, solicitud_id: int, numero: int) -> SolicitudVersion:
        version = self.db.scalar(
            select(SolicitudVersion)
            .where(
                SolicitudVersion.solicitud_id == solicitud_id,
                SolicitudVersion.numero == numero,
            )
            .options(
                selectinload(SolicitudVersion.radicada_por),
                selectinload(SolicitudVersion.documentos),
            )
        )
        if version is None:
            raise VersionSolicitudNoEncontrada(
                f"La versión {numero} de la solicitud no existe"
            )
        return version

    def comparar(
        self, solicitud_id: int, numero: int, base: int | None = None
    ) -> ComparacionVersiones:
        if base is None:
            if numero <= 1:
                raise ComparacionInvalida(
                    "La versión 1 no tiene una versión anterior con la cual compararse"
                )
            base = numero - 1
        if base == numero:
            raise ComparacionInvalida(
                "La versión base debe ser distinta de la versión comparada"
            )
        comparada = self._version(solicitud_id, numero)
        anterior = self._version(solicitud_id, base)
        campos = comparar_campos(anterior.datos, comparada.datos)
        documentos = clasificar_documentos(anterior.documentos, comparada.documentos)
        return ComparacionVersiones(
            solicitud_id=solicitud_id,
            version_base=VersionComparadaLeer.model_validate(anterior),
            version_comparada=VersionComparadaLeer.model_validate(comparada),
            hay_cambios=bool(
                campos
                or documentos.agregados
                or documentos.eliminados
                or documentos.sustituidos
            ),
            campos=campos,
            documentos=documentos,
        )
