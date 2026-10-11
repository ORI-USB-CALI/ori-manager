"""Pruebas para TAREA 3: Carga de documentos PDF en convenios (CA-01, CA-02)."""

import pytest

from backend.models.documento import Documento
from backend.services.convenios import (
    DocumentoConvenioInvalido,
    DocumentoDemasiadoGrande,
    ServicioConvenios,
)
from backend.services.documentos import AlmacenDocumentosLocal


def test_cargar_documento_pdf_exitoso(client, gestor, entrar_como, convenio_listo, db) -> None:
    entrar_como(gestor)
    contenido_pdf = b"%PDF-1.4 contenido de prueba para documento soporte"
    archivo = ("documento_prueba.pdf", contenido_pdf, "application/pdf")

    respuesta = client.post(
        f"/api/convenios/{convenio_listo.id}/documentos",
        files={"archivo": archivo},
    )

    assert respuesta.status_code == 201
    datos = respuesta.json()
    assert datos["nombre_archivo"] == "documento_prueba.pdf"
    assert datos["tipo_mime"] == "application/pdf"
    assert datos["tamano_bytes"] == len(contenido_pdf)
    assert datos["tipo"] == "SOPORTE"

    # Verificar registro en BD
    doc_id = datos["id"]
    doc_db = db.get(Documento, doc_id)
    assert doc_db is not None
    assert doc_db.convenio_id == convenio_listo.id
    assert doc_db.es_vigente is True


def test_cargar_documento_no_pdf_rechazado_400(client, gestor, entrar_como, convenio_listo) -> None:
    entrar_como(gestor)
    contenido_invalid = b"Este es un archivo de texto simple no PDF"
    archivo = ("documento.docx", contenido_invalid, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")

    respuesta = client.post(
        f"/api/convenios/{convenio_listo.id}/documentos",
        files={"archivo": archivo},
    )

    assert respuesta.status_code == 400
    assert respuesta.json()["detail"] == "Solo se permiten documentos en formato PDF"


def test_cargar_documento_magic_number_invalido_rechazado_400(client, gestor, entrar_como, convenio_listo) -> None:
    entrar_como(gestor)
    contenido_fake_pdf = b"NOT_A_REAL_PDF_HEADER"
    archivo = ("falso.pdf", contenido_fake_pdf, "application/pdf")

    respuesta = client.post(
        f"/api/convenios/{convenio_listo.id}/documentos",
        files={"archivo": archivo},
    )

    assert respuesta.status_code == 400
    assert respuesta.json()["detail"] == "Solo se permiten documentos en formato PDF"


def test_servicio_validaciones_directas(db, gestor, convenio_listo, tmp_path) -> None:
    almacen = AlmacenDocumentosLocal(tmp_path)
    servicio = ServicioConvenios(db, almacen=almacen)

    # Excede tamaño 20 MB
    limite_20mb = 20 * 1024 * 1024
    contenido_grande = b"%PDF-1.4" + b"\x00" * (limite_20mb + 1)
    with pytest.raises(DocumentoDemasiadoGrande) as exc_info:
        servicio.agregar_documento(
            convenio_id=convenio_listo.id,
            nombre_archivo="grande.pdf",
            tipo_mime="application/pdf",
            contenido=contenido_grande,
            usuario=gestor,
        )
    assert "20 MB" in str(exc_info.value)

    # No PDF
    with pytest.raises(DocumentoConvenioInvalido) as exc_info2:
        servicio.agregar_documento(
            convenio_id=convenio_listo.id,
            nombre_archivo="nota.txt",
            tipo_mime="text/plain",
            contenido=b"texto simple",
            usuario=gestor,
        )
    assert "Solo se permiten documentos en formato PDF" in str(exc_info2.value)


def test_cargar_documento_sin_permiso_rechazado_403(client, solicitante, entrar_como, convenio_listo) -> None:
    entrar_como(solicitante)
    contenido_pdf = b"%PDF-1.4 contenido de prueba"
    archivo = ("documento.pdf", contenido_pdf, "application/pdf")

    respuesta = client.post(
        f"/api/convenios/{convenio_listo.id}/documentos",
        files={"archivo": archivo},
    )

    assert respuesta.status_code == 403
