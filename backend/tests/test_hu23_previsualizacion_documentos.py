"""Pruebas backend de HU-23 (HU23-BE02):
Previsualización y descarga de documentos protegidos:
- Contratos autenticados y cabeceras seguras (nosniff, no-store, RFC 5987).
- Permisos por rol y alcance operativo (Gestor, Administrador, Revisor, Solicitante, Anónimo).
- Aislamiento de documentos (prevención de IDOR y acceso a no vigentes).
- Manejo de fallos en el servicio de almacenamiento durable (502 Bad Gateway).
- Formatos compatibles (PDF) y no PDF en solicitudes recibidas (JPEG, PNG).
- Carácter de solo lectura (RN-09).
"""
from urllib.parse import quote
from uuid import uuid4

import pytest
from sqlalchemy import select

from backend.core.roles import CodigoRol, TipoUsuario
from backend.models.convenio import Convenio
from backend.models.documento import Documento
from backend.models.enums import EstadoSolicitud
from backend.models.solicitud_convenio import SolicitudConvenio
from backend.models.tipo_convenio import TipoConvenio
from backend.models.usuario import Usuario
from backend.services.convenios import ServicioConvenios
from backend.services.documentos import AlmacenDocumentosLocal

PDF_BYTES = b"%PDF-1.4\n% Documento PDF institucional ORI\n%%EOF"
PNG_BYTES = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
JPEG_BYTES = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00\xff\xdb"


@pytest.fixture
def convenio(gestor, crear_convenio) -> Convenio:
    return crear_convenio(gestor)


def _crear_documento_convenio(
    db,
    convenio: Convenio,
    tmp_path,
    *,
    contenido: bytes = PDF_BYTES,
    tipo: str = "BORRADOR",
    nombre: str = "borrador-convenio.pdf",
    tipo_mime: str = "application/pdf",
    es_vigente: bool = True,
    cargado_por: Usuario | None = None,
) -> Documento:
    clave = f"convenios/{convenio.id}/documentos/{uuid4().hex}_{nombre}"
    AlmacenDocumentosLocal(tmp_path / "documentos").guardar(clave, contenido)
    documento = Documento(
        convenio_id=convenio.id,
        tipo=tipo,
        nombre_archivo=nombre,
        ruta_almacenamiento=clave,
        tipo_mime=tipo_mime,
        tamano_bytes=len(contenido),
        es_vigente=es_vigente,
        cargado_por_id=cargado_por.id if cargado_por else None,
    )
    db.add(documento)
    db.commit()
    db.refresh(documento)
    return documento


def _crear_documento_solicitud(
    db,
    solicitud: SolicitudConvenio,
    tmp_path,
    *,
    contenido: bytes = PDF_BYTES,
    tipo: str = "RUT",
    nombre: str = "rut.pdf",
    tipo_mime: str = "application/pdf",
    es_vigente: bool = True,
    cargado_por: Usuario | None = None,
) -> Documento:
    clave = f"solicitudes/{solicitud.id}/documentos/{uuid4().hex}_{nombre}"
    AlmacenDocumentosLocal(tmp_path / "documentos").guardar(clave, contenido)
    documento = Documento(
        solicitud_id=solicitud.id,
        tipo=tipo,
        nombre_archivo=nombre,
        ruta_almacenamiento=clave,
        tipo_mime=tipo_mime,
        tamano_bytes=len(contenido),
        es_vigente=es_vigente,
        cargado_por_id=cargado_por.id if cargado_por else None,
    )
    db.add(documento)
    db.commit()
    db.refresh(documento)
    return documento


def _crear_solicitud_recibida(
    db,
    autor: Usuario,
    *,
    estado: str = EstadoSolicitud.RADICADA.value,
) -> SolicitudConvenio:
    tipo = db.scalar(select(TipoConvenio).where(TipoConvenio.codigo == "MARCO"))
    solicitud = SolicitudConvenio(
        consecutivo=f"SOL-{uuid4().hex[:8].upper()}",
        tipo_solicitante=autor.tipo_usuario,
        solicitante_id=autor.id,
        tipo_convenio_id=tipo.id if tipo else None,
        objeto="Cooperación institucional y movilidad",
        justificacion="Ampliación de redes internacionales",
        vigencia_estimada="24 meses",
        estado=estado,
        nombre_aliado_propuesto="Universidad Aliada Internacional",
        correo_aliado_propuesto="contacto@aliada.example",
    )
    db.add(solicitud)
    db.commit()
    db.refresh(solicitud)
    return solicitud


# ==============================================================================
# 1. Permisos y autenticación (CA-05, RN-04, RN-05, RN-06)
# ==============================================================================


def test_acceso_anonimo_denegado_en_convenios_y_solicitudes(
    client, db, gestor, crear_convenio, tmp_path
):
    """RN-06: Los documentos se entregan a través de endpoints autenticados."""
    convenio = crear_convenio(gestor)
    doc_convenio = _crear_documento_convenio(db, convenio, tmp_path)
    solicitud = _crear_solicitud_recibida(db, gestor)
    doc_solicitud = _crear_documento_solicitud(db, solicitud, tmp_path)

    # Eliminar cookies de sesión para simular anónimo
    client.cookies.clear()

    resp_convenio = client.get(
        f"/api/convenios/{convenio.id}/documentos/{doc_convenio.id}/contenido"
    )
    assert resp_convenio.status_code == 401

    resp_solicitud = client.get(
        f"/api/solicitudes/recibidas/{solicitud.id}/documentos/{doc_solicitud.id}/contenido"
    )
    assert resp_solicitud.status_code == 401


def test_solicitantes_denegados_en_convenios_y_recibidas(
    client, db, gestor, crear_usuario, entrar_como, crear_convenio, tmp_path
):
    """RN-04: Solicitantes internos y externos no tienen acceso a documentos de convenios
    ni a solicitudes recibidas."""
    convenio = crear_convenio(gestor)
    doc_convenio = _crear_documento_convenio(db, convenio, tmp_path)
    solicitud = _crear_solicitud_recibida(db, gestor)
    doc_solicitud = _crear_documento_solicitud(db, solicitud, tmp_path)

    sol_interno = crear_usuario(CodigoRol.SOLICITANTE_INTERNO, TipoUsuario.INTERNO)
    sol_externo = crear_usuario(CodigoRol.SOLICITANTE_EXTERNO, TipoUsuario.EXTERNO)

    for usuario in (sol_interno, sol_externo):
        entrar_como(usuario)
        resp_c = client.get(
            f"/api/convenios/{convenio.id}/documentos/{doc_convenio.id}/contenido"
        )
        assert resp_c.status_code == 403

        resp_s = client.get(
            f"/api/solicitudes/recibidas/{solicitud.id}/documentos/{doc_solicitud.id}/contenido"
        )
        assert resp_s.status_code == 403


def test_revisor_ori_denegado_en_solicitudes_recibidas_rn05(
    client, db, gestor, revisor, entrar_como, tmp_path
):
    """RN-05: El rol Revisor ORI no tiene acceso general a solicitudes recibidas."""
    solicitud = _crear_solicitud_recibida(db, gestor)
    doc_solicitud = _crear_documento_solicitud(db, solicitud, tmp_path)

    entrar_como(revisor)
    resp = client.get(
        f"/api/solicitudes/recibidas/{solicitud.id}/documentos/{doc_solicitud.id}/contenido"
    )
    assert resp.status_code == 403


def test_revisor_ori_denegado_en_descargar_soportes_rn05(
    client, db, gestor, revisor, entrar_como, crear_convenio, tmp_path
):
    """RN-05: El rol Revisor ORI no tiene permiso de gestión de soportes."""
    convenio = crear_convenio(gestor)
    soporte = _crear_documento_convenio(
        db, convenio, tmp_path, tipo="SOPORTE", nombre="soporte.pdf"
    )

    entrar_como(revisor)
    resp = client.get(
        f"/api/convenios/{convenio.id}/documentos/{soporte.id}/descargar"
    )
    assert resp.status_code == 403


def test_revisor_ori_accede_a_documentos_en_convenio_en_etapa_juridica(
    client, db, gestor, revisor, entrar_como, crear_convenio, tmp_path
):
    """RN-04 y RN-05: Revisor ORI accede a documentos de convenios para los que
    tenga autorización (etapa de revisión jurídica pendiente)."""
    tipo = db.scalar(select(TipoConvenio).where(TipoConvenio.codigo == "MARCO"))
    convenio = crear_convenio(
        gestor,
        tipo_convenio_id=tipo.id,
        implicacion_financiera="Sin costo",
        duracion_meses=12,
    )
    doc = _crear_documento_convenio(db, convenio, tmp_path)

    # El gestor entrega a Jurídica
    ServicioConvenios(db).finalizar_elaboracion(convenio.id, gestor)

    # El revisor consulta el contenido del documento del convenio
    entrar_como(revisor)
    resp = client.get(
        f"/api/convenios/{convenio.id}/documentos/{doc.id}/contenido"
    )
    assert resp.status_code == 200
    assert resp.content == PDF_BYTES


def test_revisor_ori_denegado_en_convenio_fuera_de_su_alcance(
    client, db, gestor, revisor, entrar_como, crear_convenio, tmp_path
):
    """RN-05: Revisor ORI solo accede a convenios asignados/elegibles. En elaboración da 404."""
    convenio = crear_convenio(gestor)
    doc = _crear_documento_convenio(db, convenio, tmp_path)

    entrar_como(revisor)
    resp = client.get(
        f"/api/convenios/{convenio.id}/documentos/{doc.id}/contenido"
    )
    assert resp.status_code == 404


def test_gestor_y_administrador_acceden_a_convenios_y_solicitudes_recibidas(
    client, db, gestor, crear_usuario, entrar_como, crear_convenio, tmp_path
):
    """CA-01, CA-05: Gestor ORI y Administrador ORI tienen acceso operativo completo."""
    admin = crear_usuario(CodigoRol.ADMINISTRADOR_ORI, TipoUsuario.INTERNO)
    convenio = crear_convenio(gestor)
    doc_c = _crear_documento_convenio(db, convenio, tmp_path)

    solicitud = _crear_solicitud_recibida(db, gestor)
    doc_s = _crear_documento_solicitud(db, solicitud, tmp_path)

    for usuario in (gestor, admin):
        entrar_como(usuario)
        resp_c = client.get(
            f"/api/convenios/{convenio.id}/documentos/{doc_c.id}/contenido"
        )
        assert resp_c.status_code == 200
        assert resp_c.content == PDF_BYTES

        resp_s = client.get(
            f"/api/solicitudes/recibidas/{solicitud.id}/documentos/{doc_s.id}/contenido"
        )
        assert resp_s.status_code == 200
        assert resp_s.content == PDF_BYTES


# ==============================================================================
# 2. Cabeceras seguras y contratos de entrega (CA-01, CA-02, CA-04, RN-06, RN-07)
# ==============================================================================


def test_convenio_contenido_por_defecto_inline_con_cabeceras_seguras(
    client, db, gestor, convenio, tmp_path
):
    """CA-01, CA-02: Por defecto inline para previsualización, con nosniff y no-store."""
    doc = _crear_documento_convenio(
        db, convenio, tmp_path, nombre="minuta_aprobada.pdf"
    )

    resp = client.get(
        f"/api/convenios/{convenio.id}/documentos/{doc.id}/contenido"
    )
    assert resp.status_code == 200
    assert resp.content == PDF_BYTES
    assert resp.headers["content-type"] == "application/pdf"
    assert resp.headers["content-disposition"] == (
        "inline; filename*=UTF-8''minuta_aprobada.pdf"
    )
    assert resp.headers["x-content-type-options"] == "nosniff"
    assert resp.headers["cache-control"] == "no-store"


def test_convenio_contenido_descarga_attachment(
    client, db, gestor, convenio, tmp_path
):
    """CA-04: Acción de descarga con disposicion=attachment."""
    doc = _crear_documento_convenio(
        db, convenio, tmp_path, nombre="convenio_firmado.pdf"
    )

    resp = client.get(
        f"/api/convenios/{convenio.id}/documentos/{doc.id}/contenido",
        params={"disposicion": "attachment"},
    )
    assert resp.status_code == 200
    assert resp.headers["content-disposition"] == (
        "attachment; filename*=UTF-8''convenio_firmado.pdf"
    )
    assert resp.headers["x-content-type-options"] == "nosniff"
    assert resp.headers["cache-control"] == "no-store"


def test_solicitud_recibida_contenido_inline_y_attachment_con_cabeceras_seguras(
    client, db, gestor, tmp_path
):
    """CA-01, CA-04: Solicitud recibida soporta inline y attachment con cabeceras seguras."""
    solicitud = _crear_solicitud_recibida(db, gestor)
    doc = _crear_documento_solicitud(
        db, solicitud, tmp_path, nombre="camara_comercio.pdf"
    )

    # Previsualización por defecto (inline)
    resp_inline = client.get(
        f"/api/solicitudes/recibidas/{solicitud.id}/documentos/{doc.id}/contenido"
    )
    assert resp_inline.status_code == 200
    assert resp_inline.headers["content-disposition"] == (
        "inline; filename*=UTF-8''camara_comercio.pdf"
    )
    assert resp_inline.headers["x-content-type-options"] == "nosniff"
    assert resp_inline.headers["cache-control"] == "no-store"

    # Descarga (attachment)
    resp_attach = client.get(
        f"/api/solicitudes/recibidas/{solicitud.id}/documentos/{doc.id}/contenido",
        params={"disposicion": "attachment"},
    )
    assert resp_attach.status_code == 200
    assert resp_attach.headers["content-disposition"] == (
        "attachment; filename*=UTF-8''camara_comercio.pdf"
    )
    assert resp_attach.headers["x-content-type-options"] == "nosniff"
    assert resp_attach.headers["cache-control"] == "no-store"


def test_nombre_archivo_con_espacios_y_tildes_codificado_rfc5987(
    client, db, gestor, convenio, tmp_path
):
    """RN-07: Nombres con espacios o acentos se codifican en UTF-8 según RFC 5987."""
    nombre_complejo = "Resolución de Creación & Acta #1.pdf"
    doc = _crear_documento_convenio(
        db, convenio, tmp_path, nombre=nombre_complejo
    )

    resp = client.get(
        f"/api/convenios/{convenio.id}/documentos/{doc.id}/contenido"
    )
    assert resp.status_code == 200
    esperado = f"inline; filename*=UTF-8''{quote(nombre_complejo, safe='')}"
    assert resp.headers["content-disposition"] == esperado


def test_disposicion_invalida_responde_422(
    client, db, gestor, convenio, tmp_path
):
    """Validación de parámetro: disposicion debe ser inline o attachment."""
    doc_c = _crear_documento_convenio(db, convenio, tmp_path)
    solicitud = _crear_solicitud_recibida(db, gestor)
    doc_s = _crear_documento_solicitud(db, solicitud, tmp_path)

    resp_c = client.get(
        f"/api/convenios/{convenio.id}/documentos/{doc_c.id}/contenido",
        params={"disposicion": "otra_cosa"},
    )
    assert resp_c.status_code == 422

    resp_s = client.get(
        f"/api/solicitudes/recibidas/{solicitud.id}/documentos/{doc_s.id}/contenido",
        params={"disposicion": "otra_cosa"},
    )
    assert resp_s.status_code == 422


# ==============================================================================
# 3. Aislamiento de documentos e integridad de referencias (CA-05, RN-07)
# ==============================================================================


def test_convenio_no_permite_documento_de_otro_convenio(
    client, db, gestor, crear_convenio, tmp_path
):
    """CA-05, RN-07: Impide acceder a documentos ajenos modificando el ID en la URL (IDOR)."""
    convenio_a = crear_convenio(gestor)
    convenio_b = crear_convenio(gestor)
    doc_b = _crear_documento_convenio(db, convenio_b, tmp_path)

    # Intentar acceder al documento de B a través de la URL de A
    resp = client.get(
        f"/api/convenios/{convenio_a.id}/documentos/{doc_b.id}/contenido"
    )
    assert resp.status_code == 404


def test_solicitud_no_permite_documento_de_otra_solicitud(
    client, db, gestor, tmp_path
):
    """CA-05, RN-07: Impide acceder a documentos de otra solicitud en /recibidas."""
    solicitud_a = _crear_solicitud_recibida(db, gestor)
    solicitud_b = _crear_solicitud_recibida(db, gestor)
    doc_b = _crear_documento_solicitud(db, solicitud_b, tmp_path)

    # Intentar acceder al documento de B a través de la URL de A
    resp = client.get(
        f"/api/solicitudes/recibidas/{solicitud_a.id}/documentos/{doc_b.id}/contenido"
    )
    assert resp.status_code == 404


def test_documento_no_vigente_no_es_accesible(
    client, db, gestor, convenio, tmp_path
):
    """CA-05: Documentos no vigentes (es_vigente=False) no se retornan en /contenido."""
    doc_c_inactivo = _crear_documento_convenio(
        db, convenio, tmp_path, es_vigente=False
    )
    solicitud = _crear_solicitud_recibida(db, gestor)
    doc_s_inactivo = _crear_documento_solicitud(
        db, solicitud, tmp_path, es_vigente=False
    )

    resp_c = client.get(
        f"/api/convenios/{convenio.id}/documentos/{doc_c_inactivo.id}/contenido"
    )
    assert resp_c.status_code == 404

    resp_s = client.get(
        f"/api/solicitudes/recibidas/{solicitud.id}/documentos/{doc_s_inactivo.id}/contenido"
    )
    assert resp_s.status_code == 404


def test_solicitud_en_borrador_no_permite_descarga_por_recibidas(
    client, db, gestor, tmp_path
):
    """CA-05: Una solicitud en BORRADOR no es visible ni descargable por /recibidas."""
    solicitud_borrador = _crear_solicitud_recibida(
        db, gestor, estado=EstadoSolicitud.BORRADOR.value
    )
    doc = _crear_documento_solicitud(db, solicitud_borrador, tmp_path)

    resp = client.get(
        f"/api/solicitudes/recibidas/{solicitud_borrador.id}/documentos/{doc.id}/contenido"
    )
    assert resp.status_code == 404


def test_no_se_expone_ruta_almacenamiento_ni_enlaces_publicos(
    client, db, gestor, convenio, tmp_path
):
    """RN-06, CA-05: No genera enlaces públicos permanentes ni expone rutas internas."""
    doc = _crear_documento_convenio(db, convenio, tmp_path)
    solicitud = _crear_solicitud_recibida(db, gestor)
    doc_s = _crear_documento_solicitud(db, solicitud, tmp_path)

    for ruta in (
        f"/api/convenios/{convenio.id}/documentos/{doc.id}/contenido",
        f"/api/solicitudes/recibidas/{solicitud.id}/documentos/{doc_s.id}/contenido",
    ):
        resp = client.get(ruta)
        assert resp.status_code == 200
        # No debe haber referencias a la ruta física interna en cabeceras
        for valor in resp.headers.values():
            assert "convenios/" not in valor
            assert "solicitudes/" not in valor


# ==============================================================================
# 4. Errores de almacenamiento (CA-07)
# ==============================================================================


def test_convenio_responde_502_si_archivo_no_esta_en_almacen(
    client, db, gestor, convenio, tmp_path
):
    """CA-07: Si el archivo no está en el almacenamiento, responde 502 Bad Gateway comprensible."""
    doc = _crear_documento_convenio(db, convenio, tmp_path)
    # Eliminar deliberadamente el archivo físico del almacenamiento
    AlmacenDocumentosLocal(tmp_path / "documentos").eliminar(
        doc.ruta_almacenamiento
    )

    resp = client.get(
        f"/api/convenios/{convenio.id}/documentos/{doc.id}/contenido"
    )
    assert resp.status_code == 502
    assert resp.json()["detail"] == "No fue posible recuperar el documento almacenado"


def test_solicitud_recibida_responde_502_si_archivo_no_esta_en_almacen(
    client, db, gestor, tmp_path
):
    """CA-07: Si el soporte de la solicitud no está en el almacén, responde 502."""
    solicitud = _crear_solicitud_recibida(db, gestor)
    doc = _crear_documento_solicitud(db, solicitud, tmp_path)
    AlmacenDocumentosLocal(tmp_path / "documentos").eliminar(
        doc.ruta_almacenamiento
    )

    resp = client.get(
        f"/api/solicitudes/recibidas/{solicitud.id}/documentos/{doc.id}/contenido"
    )
    assert resp.status_code == 502
    assert resp.json()["detail"] == "No fue posible recuperar el documento almacenado"


# ==============================================================================
# 5. Formatos y tipos MIME (RN-01, RN-08, CA-06)
# ==============================================================================


def test_solicitudes_recibidas_soportan_formatos_imagen_png_y_jpeg(
    client, db, gestor, tmp_path
):
    """RN-08, CA-06: Formatos no PDF (ej. PNG, JPEG) en solicitudes mantienen descarga y contenido."""
    solicitud = _crear_solicitud_recibida(db, gestor)
    doc_png = _crear_documento_solicitud(
        db,
        solicitud,
        tmp_path,
        contenido=PNG_BYTES,
        tipo="RUT",
        nombre="rut_digital.png",
        tipo_mime="image/png",
    )
    doc_jpeg = _crear_documento_solicitud(
        db,
        solicitud,
        tmp_path,
        contenido=JPEG_BYTES,
        tipo="CEDULA_REPRESENTANTE_LEGAL",
        nombre="cedula_escaneada.jpg",
        tipo_mime="image/jpeg",
    )

    # Previsualizar / consultar PNG
    resp_png = client.get(
        f"/api/solicitudes/recibidas/{solicitud.id}/documentos/{doc_png.id}/contenido"
    )
    assert resp_png.status_code == 200
    assert resp_png.headers["content-type"] == "image/png"
    assert resp_png.content == PNG_BYTES

    # Descargar JPEG
    resp_jpeg = client.get(
        f"/api/solicitudes/recibidas/{solicitud.id}/documentos/{doc_jpeg.id}/contenido",
        params={"disposicion": "attachment"},
    )
    assert resp_jpeg.status_code == 200
    assert resp_jpeg.headers["content-type"] == "image/jpeg"
    assert resp_jpeg.headers["content-disposition"].startswith("attachment;")
    assert resp_jpeg.content == JPEG_BYTES


# ==============================================================================
# 6. Solo lectura e inmutabilidad (RN-09)
# ==============================================================================


def test_consulta_documental_es_de_solo_lectura_rn09(
    client, db, gestor, convenio, tmp_path
):
    """RN-09: La consulta documental no produce cambios en el historial ni en versiones."""
    doc = _crear_documento_convenio(db, convenio, tmp_path)
    version_inicial = convenio.version_actual
    estado_inicial = convenio.estado

    # Múltiples consultas inline y attachment
    client.get(f"/api/convenios/{convenio.id}/documentos/{doc.id}/contenido")
    client.get(
        f"/api/convenios/{convenio.id}/documentos/{doc.id}/contenido",
        params={"disposicion": "attachment"},
    )

    db.refresh(convenio)
    assert convenio.version_actual == version_inicial
    assert convenio.estado == estado_inicial
