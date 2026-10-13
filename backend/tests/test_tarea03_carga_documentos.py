"""Pruebas para TAREA 3: Carga de documentos PDF en convenios (CA-01, CA-02)."""

import pytest

from backend.models.documento import Documento
from backend.models.enums import EstadoConvenio
from backend.services.convenios import (
    DocumentoConvenioInvalido,
    DocumentoDemasiadoGrande,
    ServicioConvenios,
)
from backend.services.documentos import AlmacenDocumentosLocal


@pytest.fixture
def convenio_listo(convenio_listo, db):
    """Desde CA-04 de HU-22C solo se cargan soportes en convenios vigentes o
    por vencer; estas pruebas validan el archivo sobre un convenio vigente."""
    convenio_listo.estado = EstadoConvenio.VIGENTE.value
    db.commit()
    return convenio_listo


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


def test_cargar_documento_nombre_espacios_rechazado_400(client, gestor, entrar_como, convenio_listo) -> None:
    entrar_como(gestor)
    archivo = ("   ", b"%PDF-1.4 contenido", "application/pdf")
    respuesta = client.post(
        f"/api/convenios/{convenio_listo.id}/documentos",
        files={"archivo": archivo},
    )
    assert respuesta.status_code == 400
    assert "El nombre del archivo no puede estar vacío" in respuesta.json()["detail"]


def test_cargar_documento_nombre_demasiado_largo_rechazado_400(client, gestor, entrar_como, convenio_listo) -> None:
    entrar_como(gestor)
    nombre_largo = "a" * 252 + ".pdf"  # 256 chars
    archivo = (nombre_largo, b"%PDF-1.4 contenido", "application/pdf")
    respuesta = client.post(
        f"/api/convenios/{convenio_listo.id}/documentos",
        files={"archivo": archivo},
    )
    assert respuesta.status_code == 400
    assert "superar 255 caracteres" in respuesta.json()["detail"]


def test_servicio_validaciones_nombre_archivo(db, gestor, convenio_listo, tmp_path) -> None:
    almacen = AlmacenDocumentosLocal(tmp_path)
    servicio = ServicioConvenios(db, almacen=almacen)

    # Nombre vacío o solo espacios
    for nombre_invalido in ["", "   "]:
        with pytest.raises(DocumentoConvenioInvalido) as exc:
            servicio.agregar_documento(
                convenio_id=convenio_listo.id,
                nombre_archivo=nombre_invalido,
                tipo_mime="application/pdf",
                contenido=b"%PDF-1.4 valido",
                usuario=gestor,
            )
        assert "no puede estar vacío" in str(exc.value)

    # Nombre con caracteres nulos
    with pytest.raises(DocumentoConvenioInvalido) as exc_nulo:
        servicio.agregar_documento(
            convenio_id=convenio_listo.id,
            nombre_archivo="documento\x00.pdf",
            tipo_mime="application/pdf",
            contenido=b"%PDF-1.4 valido",
            usuario=gestor,
        )
    assert "caracteres inválidos" in str(exc_nulo.value)

    # Nombre superior a 255 caracteres
    with pytest.raises(DocumentoConvenioInvalido) as exc_largo:
        servicio.agregar_documento(
            convenio_id=convenio_listo.id,
            nombre_archivo="a" * 252 + ".pdf",
            tipo_mime="application/pdf",
            contenido=b"%PDF-1.4 valido",
            usuario=gestor,
        )
    assert "superar 255 caracteres" in str(exc_largo.value)


def test_servicio_falla_almacenamiento_no_persiste_metadata(db, gestor, convenio_listo) -> None:
    from backend.services.documentos import ErrorAlmacenDocumentos

    class AlmacenQueFalla:
        def guardar(self, clave: str, contenido: bytes) -> None:
            raise ErrorAlmacenDocumentos("Error simulado de OneDrive / Storage")

        def eliminar(self, clave: str) -> None:
            pass

    servicio = ServicioConvenios(db, almacen=AlmacenQueFalla())
    with pytest.raises(ErrorAlmacenDocumentos):
        servicio.agregar_documento(
            convenio_id=convenio_listo.id,
            nombre_archivo="prueba.pdf",
            tipo_mime="application/pdf",
            contenido=b"%PDF-1.4 contenido",
            usuario=gestor,
        )

    # Verificar que no se creó ningún documento en la base de datos
    docs = db.query(Documento).filter(Documento.convenio_id == convenio_listo.id).all()
    assert len(docs) == 0


def test_servicio_compensacion_por_error_en_persistencia(db, gestor, convenio_listo, tmp_path, monkeypatch) -> None:
    almacen = AlmacenDocumentosLocal(tmp_path)
    servicio = ServicioConvenios(db, almacen=almacen)

    def commit_que_falla():
        raise RuntimeError("Fallo inesperado al hacer commit en PostgreSQL")

    monkeypatch.setattr(db, "commit", commit_que_falla)

    with pytest.raises(RuntimeError, match="Fallo inesperado al hacer commit"):
        servicio.agregar_documento(
            convenio_id=convenio_listo.id,
            nombre_archivo="soporte_compensado.pdf",
            tipo_mime="application/pdf",
            contenido=b"%PDF-1.4 contenido",
            usuario=gestor,
        )

    # Verificar compensación: ningún archivo huérfano quedó en almacenamiento
    archivos_almacenados = list(tmp_path.rglob("*.pdf"))
    assert archivos_almacenados == []


def test_servicio_compensacion_falla_limpieza_registra_incidente_en_log(
    db, gestor, convenio_listo, monkeypatch, caplog
) -> None:
    import logging

    claves_guardadas = []

    class AlmacenConFalloEnLimpieza:
        def guardar(self, clave: str, contenido: bytes) -> None:
            claves_guardadas.append(clave)

        def eliminar(self, clave: str) -> None:
            raise RuntimeError("Error de red al intentar eliminar archivo en OneDrive")

    def commit_que_falla():
        raise RuntimeError("Fallo de BD en commit")

    monkeypatch.setattr(db, "commit", commit_que_falla)
    servicio = ServicioConvenios(db, almacen=AlmacenConFalloEnLimpieza())

    with (
        caplog.at_level(logging.CRITICAL),
        pytest.raises(RuntimeError, match="Fallo de BD en commit"),
    ):
        servicio.agregar_documento(
            convenio_id=convenio_listo.id,
            nombre_archivo="soporte.pdf",
            tipo_mime="application/pdf",
            contenido=b"%PDF-1.4 contenido",
            usuario=gestor,
        )

    assert len(claves_guardadas) == 1
    assert "FALLO_COMPENSACION_ALMACENAMIENTO" in caplog.text
    assert claves_guardadas[0] in caplog.text


def test_servicio_rechaza_y_compensa_si_convenio_cambia_de_estado_durante_carga(
    db, gestor, convenio_listo, tmp_path, monkeypatch
) -> None:
    from backend.services.soportes_convenio import ConvenioNoAdmiteSoportes

    almacen = AlmacenDocumentosLocal(tmp_path)
    servicio = ServicioConvenios(db, almacen=almacen)

    # Simulamos que justo después de guardar el archivo en almacenamiento, el convenio cambia a FINALIZADO
    guardar_original = almacen.guardar

    def guardar_con_cambio_concurrente(clave, contenido):
        guardar_original(clave, contenido)
        convenio_listo.estado = EstadoConvenio.FINALIZADO.value
        db.commit()

    monkeypatch.setattr(almacen, "guardar", guardar_con_cambio_concurrente)

    with pytest.raises(ConvenioNoAdmiteSoportes):
        servicio.agregar_documento(
            convenio_id=convenio_listo.id,
            nombre_archivo="soporte.pdf",
            tipo_mime="application/pdf",
            contenido=b"%PDF-1.4 contenido",
            usuario=gestor,
        )

    # Verificar que el archivo fue eliminado por compensación y no hay documentos en BD
    archivos = list(tmp_path.rglob("*.pdf"))
    assert archivos == []
    docs = db.query(Documento).filter(Documento.convenio_id == convenio_listo.id).all()
    assert len(docs) == 0


def test_concurrencia_dos_sesiones_independientes_detecta_cambio_estado(
    db, gestor, convenio_listo, tmp_path
) -> None:
    """Valida que la comprobación posterior a la subida no use datos obsoletos
    del identity map de SQLAlchemy cuando otra sesión independiente en PostgreSQL
    actualiza y comitea el estado del convenio concurrentemente."""
    from sqlalchemy.orm import Session

    from backend.models.convenio import Convenio
    from backend.services.soportes_convenio import ConvenioNoAdmiteSoportes

    almacen = AlmacenDocumentosLocal(tmp_path)
    servicio = ServicioConvenios(db, almacen=almacen)

    # 1. Aseguramos que el convenio esté cargado en el identity map de la sesión principal 'db'
    convenio_sesion_1 = servicio.obtener(convenio_listo.id)
    assert convenio_sesion_1.estado == EstadoConvenio.VIGENTE.value

    # Interceptamos el almacenamiento para simular que otra sesión independiente (sesion_2)
    # modifica el convenio en la base de datos mientras ocurre la subida
    guardar_original = almacen.guardar

    def subida_con_modificacion_en_segunda_sesion(clave: str, contenido: bytes) -> None:
        guardar_original(clave, contenido)
        # Segunda sesión independiente conectada al mismo bind/engine
        with Session(db.bind) as sesion_2:
            c2 = sesion_2.get(Convenio, convenio_listo.id)
            assert c2 is not None
            c2.estado = EstadoConvenio.FINALIZADO.value
            sesion_2.commit()

    almacen.guardar = subida_con_modificacion_en_segunda_sesion

    # La sesión 1 debe leer el estado actualizado de la base de datos y rechazar la carga
    with pytest.raises(ConvenioNoAdmiteSoportes):
        servicio.agregar_documento(
            convenio_id=convenio_listo.id,
            nombre_archivo="soporte_concurrente.pdf",
            tipo_mime="application/pdf",
            contenido=b"%PDF-1.4 contenido",
            usuario=gestor,
        )

    # Comprobar que el archivo se compensó y no se persistió documento
    archivos = list(tmp_path.rglob("*.pdf"))
    assert archivos == []
    docs = db.query(Documento).filter(Documento.convenio_id == convenio_listo.id).all()
    assert len(docs) == 0


def test_error_post_commit_en_refresh_no_elimina_archivo_referenciado(
    db, gestor, convenio_listo, tmp_path, monkeypatch, caplog
) -> None:
    """Valida que un fallo en db.refresh() tras un commit exitoso no dispare
    la compensación de almacenamiento, preservando el archivo referenciado en la BD."""
    import logging

    almacen = AlmacenDocumentosLocal(tmp_path)
    servicio = ServicioConvenios(db, almacen=almacen)

    def refresh_que_falla(instance):
        raise RuntimeError("Fallo transitorio de conexión durante db.refresh()")

    monkeypatch.setattr(db, "refresh", refresh_que_falla)

    with caplog.at_level(logging.WARNING):
        doc = servicio.agregar_documento(
            convenio_id=convenio_listo.id,
            nombre_archivo="soporte_post_commit.pdf",
            tipo_mime="application/pdf",
            contenido=b"%PDF-1.4 contenido",
            usuario=gestor,
        )

    # 1. El registro EXISTE en la base de datos
    docs = db.query(Documento).filter(Documento.convenio_id == convenio_listo.id).all()
    assert len(docs) == 1
    assert docs[0].id == doc.id

    # 2. El archivo físico EXISTE en el almacenamiento (NO se eliminó)
    archivos = list(tmp_path.rglob("*.pdf"))
    assert len(archivos) == 1
    assert almacen.existe(doc.ruta_almacenamiento) is True


def test_servicio_falla_guardado_almacenamiento_compensa_para_evitar_huerfanos(
    db, gestor, convenio_listo
) -> None:
    """Si guardar en almacenamiento remoto falla por timeout o error de red,
    no se asume automáticamente que el archivo no existe: se ejecuta la compensación
    para asegurar que ningún archivo huérfano quede en almacenamiento remoto."""
    from backend.services.documentos import ErrorAlmacenDocumentos

    limpiezas = []

    class AlmacenConTimeout:
        def guardar(self, clave: str, contenido: bytes) -> None:
            raise ErrorAlmacenDocumentos("Timeout en subida a OneDrive")

        def eliminar(self, clave: str) -> None:
            limpiezas.append(clave)

    servicio = ServicioConvenios(db, almacen=AlmacenConTimeout())
    with pytest.raises(ErrorAlmacenDocumentos):
        servicio.agregar_documento(
            convenio_id=convenio_listo.id,
            nombre_archivo="soporte.pdf",
            tipo_mime="application/pdf",
            contenido=b"%PDF-1.4 contenido",
            usuario=gestor,
        )

    # Se verificó que se intentó eliminar la clave para no dejar huérfanos
    assert len(limpiezas) == 1
    docs = db.query(Documento).filter(Documento.convenio_id == convenio_listo.id).all()
    assert len(docs) == 0


def test_caso_a_commit_realmente_fallido_compensa_archivo(
    db, gestor, convenio_listo, tmp_path, monkeypatch
) -> None:
    """Caso A: Commit realmente fallido (PostgreSQL no persiste el registro).
    Resultado esperado: el archivo se elimina mediante compensación y no queda metadata."""
    almacen = AlmacenDocumentosLocal(tmp_path)
    servicio = ServicioConvenios(db, almacen=almacen)

    def commit_que_falla():
        raise RuntimeError("Fallo real al persistir transacción en PostgreSQL")

    monkeypatch.setattr(db, "commit", commit_que_falla)

    with pytest.raises(RuntimeError, match="Fallo real al persistir"):
        servicio.agregar_documento(
            convenio_id=convenio_listo.id,
            nombre_archivo="soporte_caso_a.pdf",
            tipo_mime="application/pdf",
            contenido=b"%PDF-1.4 contenido",
            usuario=gestor,
        )

    # El archivo físico se elimina por compensación
    archivos = list(tmp_path.rglob("*.pdf"))
    assert archivos == []

    # No queda metadata en la base de datos
    docs = db.query(Documento).filter(Documento.convenio_id == convenio_listo.id).all()
    assert len(docs) == 0


def test_caso_b_commit_exitoso_con_error_comunicacion_conserva_archivo(
    db, gestor, convenio_listo, tmp_path, monkeypatch
) -> None:
    """Caso B: Commit exitoso con error de comunicación.
    Simular que el registro se confirma en PostgreSQL, pero luego db.commit() lanza excepción.
    Resultado esperado: la metadata existe en BD, el archivo se conserva intacto en almacenamiento
    sin compensación, y la llamada falla informando el error."""
    almacen = AlmacenDocumentosLocal(tmp_path)
    servicio = ServicioConvenios(db, almacen=almacen)

    commit_real = db.commit

    def commit_con_desconexion():
        commit_real()
        raise RuntimeError("Conexión perdida después de confirmar la transacción en PostgreSQL")

    monkeypatch.setattr(db, "commit", commit_con_desconexion)

    with pytest.raises(RuntimeError, match="Conexión perdida después de confirmar"):
        servicio.agregar_documento(
            convenio_id=convenio_listo.id,
            nombre_archivo="soporte_caso_b.pdf",
            tipo_mime="application/pdf",
            contenido=b"%PDF-1.4 contenido",
            usuario=gestor,
        )

    # La metadata EXISTE en la base de datos
    docs = db.query(Documento).filter(Documento.convenio_id == convenio_listo.id).all()
    assert len(docs) == 1
    doc = docs[0]
    assert doc.nombre_archivo == "soporte_caso_b.pdf"

    # El archivo físico se CONSERVA en almacenamiento (NO se ejecutó compensación)
    archivos = list(tmp_path.rglob("*.pdf"))
    assert len(archivos) == 1
    assert almacen.existe(doc.ruta_almacenamiento) is True


def test_caso_c_resultado_incierto_postgresql_no_disponible_no_elimina_archivo(
    db, gestor, convenio_listo, tmp_path, monkeypatch, caplog
) -> None:
    """Caso C: Resultado incierto / PostgreSQL no disponible tras el fallo.
    Simular que la verificación independiente no puede conectarse o falla al consultar PostgreSQL.
    Resultado esperado: no eliminar el PDF automáticamente (conservarlo), registrar log CRITICAL
    con convenio_id y clave de almacenamiento, y la llamada falla."""
    import logging

    from sqlalchemy.exc import OperationalError

    almacen = AlmacenDocumentosLocal(tmp_path)
    servicio = ServicioConvenios(db, almacen=almacen)

    def commit_que_falla():
        raise OperationalError("Fallo de red durante commit", {}, None)

    monkeypatch.setattr(db, "commit", commit_que_falla)

    # Simular que al abrir la sesión independiente para verificar en PostgreSQL, la conexión falla
    class SessionInaccesible:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            raise OperationalError("No se puede conectar al servidor PostgreSQL", {}, None)

        def __exit__(self, *args):
            pass

    monkeypatch.setattr("backend.services.convenios.Session", SessionInaccesible)

    with (
        caplog.at_level(logging.CRITICAL),
        pytest.raises(OperationalError),
    ):
        servicio.agregar_documento(
            convenio_id=convenio_listo.id,
            nombre_archivo="soporte_caso_c.pdf",
            tipo_mime="application/pdf",
            contenido=b"%PDF-1.4 contenido",
            usuario=gestor,
        )

    # 1. No eliminar automáticamente el PDF: el archivo físico se conserva intacto
    archivos = list(tmp_path.rglob("*.pdf"))
    assert len(archivos) == 1

    # 2. Registrar el incidente con nivel crítico incluyendo convenio_id y clave de almacenamiento
    assert "INCIDENTE_PERSISTENCIA_INCIERTA" in caplog.text
    assert f"convenio_id={convenio_listo.id}" in caplog.text
    assert "convenios/" in caplog.text and archivos[0].name in caplog.text
