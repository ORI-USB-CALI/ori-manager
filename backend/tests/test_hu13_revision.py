"""HU-13: consulta de la ronda jurídica y sus documentos."""

from uuid import uuid4

from sqlalchemy import select

from backend.models.documento import Documento
from backend.models.revision_convenio import RevisionConvenio
from backend.services.documentos import AlmacenDocumentosLocal


def test_usuario_sin_permiso_no_puede_acceder_a_la_revision(
    client, solicitante, entrar_como, convenio_listo
) -> None:
    client.post(f"/api/convenios/{convenio_listo.id}/elaboracion/finalizar")
    entrar_como(solicitante)
    assert client.get(f"/api/convenios/{convenio_listo.id}/revision").status_code == 403


def test_bandeja_juridica_refleja_solo_revisiones_pendientes(
    client, db, gestor, revisor, entrar_como, convenio_listo
) -> None:
    entrar_como(revisor)
    assert client.get("/api/convenios/revisiones-juridicas/pendientes").json() == []

    entrar_como(gestor)
    assert client.post(
        f"/api/convenios/{convenio_listo.id}/elaboracion/finalizar"
    ).status_code == 200
    revision = db.scalar(
        select(RevisionConvenio).where(
            RevisionConvenio.convenio_id == convenio_listo.id
        )
    )

    entrar_como(revisor)
    respuesta = client.get("/api/convenios/revisiones-juridicas/pendientes")
    assert respuesta.status_code == 200
    assert respuesta.json()[0]["revision_id"] == revision.id
    assert respuesta.json()[0]["convenio_id"] == convenio_listo.id
    assert respuesta.json()[0]["solicitud_consecutivo"]
    assert respuesta.json()[0]["responsable"]["id"] == gestor.id
    assert client.get(f"/api/convenios/{convenio_listo.id}/revision").status_code == 200

    assert client.post(
        f"/api/convenios/{convenio_listo.id}/revisiones/{revision.id}/aprobar"
    ).status_code == 200
    assert client.get("/api/convenios/revisiones-juridicas/pendientes").json() == []


def test_convenio_inexistente_devuelve_404(client, revisor, entrar_como) -> None:
    entrar_como(revisor)
    assert client.get("/api/convenios/999999999/revision").status_code == 404


def test_convenio_que_no_esta_en_revision_juridica_devuelve_409(
    client, revisor, entrar_como, convenio_listo
) -> None:
    entrar_como(revisor)
    assert client.get(f"/api/convenios/{convenio_listo.id}/revision").status_code == 409


def test_revisor_consulta_revision_y_documento_de_solicitud(
    client, db, revisor, entrar_como, convenio_listo, tmp_path
) -> None:
    contenido = b"%PDF-1.4 documento de la solicitud"
    clave = f"solicitudes/{convenio_listo.solicitud_id}/{uuid4().hex}.pdf"
    AlmacenDocumentosLocal(tmp_path / "documentos").guardar(clave, contenido)
    documento = Documento(
        solicitud_id=convenio_listo.solicitud_id,
        tipo="RUT",
        nombre_archivo="rut_empresa.pdf",
        ruta_almacenamiento=clave,
        tipo_mime="application/pdf",
        tamano_bytes=len(contenido),
        es_vigente=True,
    )
    db.add(documento)
    db.commit()
    client.post(f"/api/convenios/{convenio_listo.id}/elaboracion/finalizar")
    entrar_como(revisor)

    respuesta = client.get(f"/api/convenios/{convenio_listo.id}/revision")

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["convenio"]["id"] == convenio_listo.id
    assert cuerpo["convenio"]["etapa_actual"]["codigo"] == "REVISION_AVAL_JURIDICO"
    assert [item["id"] for item in cuerpo["documentos"]] == [documento.id]
    assert cuerpo["documentos"][0]["nombre_archivo"] == "rut_empresa.pdf"
    assert "ruta_almacenamiento" not in cuerpo["documentos"][0]
    assert cuerpo["revision_pendiente"]["tipo"] == "JURIDICA"
    assert cuerpo["revision_pendiente"]["estado"] == "PENDIENTE"
    assert (
        cuerpo["revision_pendiente"]["snapshot_datos"]["objeto"]
        == convenio_listo.objeto
    )

    descarga = client.get(
        f"/api/convenios/{convenio_listo.id}/documentos/{documento.id}/contenido"
    )
    assert descarga.status_code == 200
    assert descarga.content == contenido
    assert descarga.headers["content-type"] == "application/pdf"
    assert descarga.headers["content-disposition"].startswith("inline;")


def test_segunda_ronda_muestra_solo_la_revision_pendiente_vigente(
    client, db, gestor, revisor, entrar_como, convenio_listo
) -> None:
    client.post(f"/api/convenios/{convenio_listo.id}/elaboracion/finalizar")
    primera = db.scalar(
        select(RevisionConvenio).where(
            RevisionConvenio.convenio_id == convenio_listo.id
        )
    )
    entrar_como(revisor)
    devolucion = client.post(
        f"/api/convenios/{convenio_listo.id}/revisiones/{primera.id}/devolver",
        json={"observaciones": ["Corregir objeto"]},
    )
    observacion_id = devolucion.json()["observaciones"][0]["id"]
    entrar_como(gestor)
    assert client.patch(
        f"/api/convenios/{convenio_listo.id}",
        json={"objeto": "Objeto corregido"},
    ).status_code == 200
    assert client.patch(
        f"/api/convenios/{convenio_listo.id}/observaciones/"
        f"{observacion_id}/atender",
        json={"respuesta": "Se corrigió el objeto"},
    ).status_code == 200
    assert client.post(
        f"/api/convenios/{convenio_listo.id}/elaboracion/finalizar"
    ).status_code == 200
    entrar_como(revisor)

    respuesta = client.get(f"/api/convenios/{convenio_listo.id}/revision")

    assert respuesta.status_code == 200
    revision_pendiente = respuesta.json()["revision_pendiente"]
    assert revision_pendiente["id"] != primera.id
    assert revision_pendiente["estado"] == "PENDIENTE"
    assert revision_pendiente["resultado"] is None


def test_documento_ajeno_no_se_expone_y_solicitante_no_puede_consultarlo(
    client,
    db,
    gestor,
    revisor,
    solicitante,
    entrar_como,
    crear_convenio,
    convenio_listo,
    tmp_path,
) -> None:
    convenio_ajeno = crear_convenio(gestor)
    clave = f"solicitudes/{convenio_ajeno.solicitud_id}/{uuid4().hex}.pdf"
    AlmacenDocumentosLocal(tmp_path / "documentos").guardar(clave, b"ajeno")
    documento = Documento(
        solicitud_id=convenio_ajeno.solicitud_id,
        tipo="RUT",
        nombre_archivo="ajeno.pdf",
        ruta_almacenamiento=clave,
        tipo_mime="application/pdf",
        tamano_bytes=5,
    )
    db.add(documento)
    db.commit()
    ruta = (
        f"/api/convenios/{convenio_listo.id}/documentos/"
        f"{documento.id}/contenido"
    )

    entrar_como(revisor)
    assert client.get(ruta).status_code == 404

    entrar_como(solicitante)
    assert client.get(ruta).status_code == 403
