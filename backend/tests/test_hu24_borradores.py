"""HU-24: exportación de borradores (BORRADOR — NO FORMALIZADO).

Un convenio EN_TRAMITE en la etapa ELABORACION se exporta como borrador, con
validación propia. Fuera de esa etapa se conserva la exportación existente.
"""
import re
from datetime import date
from io import BytesIO

import pytest
from openpyxl import load_workbook
from sqlalchemy import func, select

from backend.core.roles import CodigoRol, TipoUsuario
from backend.models.aliado import Aliado
from backend.models.convenio import Convenio
from backend.models.documento import Documento
from backend.models.etapa import Etapa
from backend.models.solicitud_convenio import SolicitudConvenio
from backend.models.version_convenio import VersionConvenio
from backend.schemas.exportacion import (
    ETIQUETA_REFERENCIA_PROVISIONAL,
    INFORMACION_NO_DISPONIBLE,
    MARCA_BORRADOR,
    ConvenioPdfDTO,
    ModoEmision,
    SeccionContenidoDTO,
    referencia_provisional,
)
from backend.services.excel_convenio import (
    HOJA_DATOS_GENERALES,
    HOJA_PARTICIPANTES_COMPROMISOS,
)
from backend.services.pdf_convenio import NumberedCanvas, ServicioPdfConvenio
from backend.services.validador_exportacion_convenio import (
    ConvenioExportValidator,
    modo_emision,
)

DOCUMENTO_CON_TEXTO = {
    "type": "doc",
    "content": [
        {"type": "paragraph", "content": [{"type": "text", "text": "Cláusula primera"}]}
    ],
}
DOCUMENTO_VACIO = {"type": "doc", "content": [{"type": "paragraph"}]}


def _exportar(client, convenio_id, formato):
    return client.get(f"/api/convenios/{convenio_id}/exportar?formato={formato}")


def _libro(contenido: bytes):
    return load_workbook(BytesIO(contenido))


def _textos(libro) -> set[str]:
    return {
        str(celda.value)
        for hoja in libro.worksheets
        for fila in hoja.iter_rows()
        for celda in fila
        if celda.value is not None
    }


def _guardar_contenido(client, convenio, contenido) -> None:
    """Nueva versión mediante el editor de HU-12 (solo en ELABORACION)."""
    elaboracion = client.get(f"/api/convenios/{convenio.id}/elaboracion").json()
    respuesta = client.patch(
        f"/api/convenios/{convenio.id}/elaboracion",
        json={"contenido": contenido, "expected_revision": elaboracion["revision_borrador"]},
    )
    assert respuesta.status_code == 200


def _parrafo(texto: str) -> dict:
    return {"type": "doc", "content": [
        {"type": "paragraph", "content": [{"type": "text", "text": texto}]}
    ]}


@pytest.fixture
def borrador(gestor, crear_convenio) -> Convenio:
    """Convenio recién creado: EN_TRAMITE en ELABORACION, sin código, sin
    fechas de vigencia y sin proceso de firmas, con objeto, entidad propuesta
    y la versión inicial con contenido."""
    convenio = crear_convenio(gestor)
    assert convenio.etapa_actual.codigo == "ELABORACION"
    assert convenio.codigo is None and convenio.fecha_inicio is None
    assert convenio.procesos_firmas == []
    return convenio


# ---- Modo de emisión (backend, a partir de los datos reales) ------------------


# HT-06, CA-06 y CA-07: el modo ya no depende de la etapa sino de la
# formalización. Antes solo ELABORACION emitía borrador y las revisiones y
# firmas emitían oficial, lo que las dejaba sin poder exportar: el documento
# oficial exige el código institucional, que no existe hasta formalizar
# (QA #136). Ahora todo convenio en trámite emite documento de trabajo.
@pytest.mark.parametrize(
    ("etapa", "estado", "fecha_firma", "modo"),
    [
        ("ELABORACION", "EN_TRAMITE", None, ModoEmision.BORRADOR),
        ("REVISION_AVAL_JURIDICO", "EN_TRAMITE", None, ModoEmision.BORRADOR),
        ("REVISION_CONTRAPARTE", "EN_TRAMITE", None, ModoEmision.BORRADOR),
        ("APROBACION_FIRMAS", "EN_TRAMITE", None, ModoEmision.BORRADOR),
        (None, "EN_TRAMITE", None, ModoEmision.BORRADOR),
        # Una fecha de firma diligenciada a mano durante la elaboración no
        # formaliza nada: el convenio sigue en trámite.
        ("ELABORACION", "EN_TRAMITE", date(2026, 1, 15), ModoEmision.BORRADOR),
        # Un convenio cancelado tampoco emite documento oficial.
        ("ELABORACION", "CANCELADO", date(2026, 1, 15), ModoEmision.BORRADOR),
        # Formalizado: estado fuera de trámite y con fecha de firma.
        ("FIRMA_ARCHIVO_SEGUIMIENTO", "VIGENTE", date(2026, 1, 15), ModoEmision.OFICIAL),
        ("FIRMA_ARCHIVO_SEGUIMIENTO", "FINALIZADO", date(2026, 1, 15), ModoEmision.OFICIAL),
        # Sin fecha de firma no está formalizado, aunque el estado lo sugiera.
        ("FIRMA_ARCHIVO_SEGUIMIENTO", "VIGENTE", None, ModoEmision.BORRADOR),
    ],
)
def test_modo_oficial_solo_cuando_el_convenio_esta_formalizado(
    etapa, estado, fecha_firma, modo
):
    convenio = Convenio(
        estado=estado,
        fecha_firma=fecha_firma,
        etapa_actual=Etapa(codigo=etapa) if etapa else None,
    )
    assert modo_emision(convenio) is modo


def test_el_cliente_no_puede_forzar_el_modo(client, db, gestor, convenio_exportable):
    # El convenio se formaliza para que su modo real sea oficial; un parámetro
    # inventado por el cliente no lo cambia.
    convenio_exportable.estado = "VIGENTE"
    convenio_exportable.fecha_firma = date(2026, 1, 15)
    db.commit()

    respuesta = client.get(
        f"/api/convenios/{convenio_exportable.id}/exportar"
        "?formato=pdf&modo=BORRADOR&modo_emision=BORRADOR"
    )

    assert respuesta.status_code == 200
    assert 'filename="Convenio_' in respuesta.headers["content-disposition"]


# ---- Validación separada del borrador (unitaria) ------------------------------


def _borrador_en_memoria(**cambios) -> Convenio:
    datos = {
        "estado": "EN_TRAMITE",
        "etapa_actual": Etapa(codigo="ELABORACION"),
        "objeto": "Cooperación académica",
        "version_actual": 1,
        "aliado": None,
        "solicitud": SolicitudConvenio(nombre_aliado_propuesto="Universidad Propuesta"),
        "versiones": [VersionConvenio(id=1, numero=1, contenido=DOCUMENTO_CON_TEXTO)],
        "procesos_firmas": [],
    }
    datos.update(cambios)
    return Convenio(**datos)


def test_borrador_no_exige_codigo_vigencia_tipo_ni_firmas():
    convenio = _borrador_en_memoria(
        codigo=None, fecha_inicio=None, fecha_vencimiento=None, tipo_convenio_id=None
    )
    assert ConvenioExportValidator().campos_faltantes(convenio) == []


@pytest.mark.parametrize(
    ("cambios", "esperado"),
    [
        ({"objeto": "  "}, ["objeto"]),
        (
            {"solicitud": SolicitudConvenio(nombre_aliado_propuesto=None)},
            ["entidad_participante"],
        ),
        ({"versiones": []}, ["version_contractual"]),
        (
            {"versiones": [VersionConvenio(id=1, numero=1, contenido=DOCUMENTO_VACIO)]},
            ["clausulas"],
        ),
        (
            {"versiones": [VersionConvenio(id=1, numero=1, contenido={"type": "html"})]},
            ["clausulas"],
        ),
        ({"solicitud": None}, ["solicitud_origen", "entidad_participante"]),
    ],
)
def test_borrador_exige_solo_los_datos_esenciales(cambios, esperado):
    convenio = _borrador_en_memoria(**cambios)
    assert ConvenioExportValidator().campos_faltantes(convenio) == esperado


def test_aliado_registrado_identifica_la_entidad_del_borrador():
    convenio = _borrador_en_memoria(
        aliado=Aliado(nombre="Aliado registrado"),
        solicitud=SolicitudConvenio(nombre_aliado_propuesto=None),
    )
    assert ConvenioExportValidator().campos_faltantes(convenio) == []


# ---- Borrador válido (API, ambos formatos por separado) -----------------------


@pytest.mark.parametrize(
    ("formato", "extension", "media_type"),
    [
        ("pdf", "pdf", "application/pdf"),
        (
            "excel",
            "xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ),
    ],
)
def test_borrador_valido_se_exporta_con_prefijo_borrador(
    client, gestor, borrador, formato, extension, media_type
):
    respuesta = _exportar(client, borrador.id, formato)

    assert respuesta.status_code == 200
    assert respuesta.headers["content-type"] == media_type
    # Sin código oficial se usa el identificador interno saneado.
    assert re.fullmatch(
        rf'attachment; filename="BORRADOR_Convenio_ID-{borrador.id}_\d{{4}}-\d{{2}}-\d{{2}}\.{extension}"',
        respuesta.headers["content-disposition"],
    )


def test_excel_del_borrador_identificado_en_ambas_hojas(client, gestor, borrador):
    libro = _libro(_exportar(client, borrador.id, "excel").content)

    assert libro.sheetnames == [HOJA_DATOS_GENERALES, HOJA_PARTICIPANTES_COMPROMISOS]
    for hoja in libro.worksheets:
        assert hoja["A1"].value == MARCA_BORRADOR
        assert hoja["A1"].font.bold is True
    # La tabla empieza después de la marca; los datos ausentes se declaran.
    datos = libro[HOJA_DATOS_GENERALES]
    assert datos["A3"].value == "Campo"
    valores = {fila[0].value: fila[1].value for fila in datos.iter_rows(min_row=4)}
    # HT-06, CA-01 y CA-07: el documento de trabajo no anuncia un código oficial
    # inexistente; lleva la referencia provisional del identificador interno.
    assert "Código oficial" not in valores
    assert valores[ETIQUETA_REFERENCIA_PROVISIONAL] == referencia_provisional(
        borrador.id
    )
    assert valores["Fecha de inicio de vigencia"] == INFORMACION_NO_DISPONIBLE
    assert valores["Fecha de fin de vigencia"] == INFORMACION_NO_DISPONIBLE
    assert valores["Objeto"] == borrador.objeto
    assert "Sin firmantes registrados" in _textos(libro)


def test_dto_del_borrador_no_inventa_firmas_ni_vigencia(db, gestor, borrador):
    dto = ServicioPdfConvenio().mapear_convenio_a_dto(borrador.id, db)

    assert dto.modo_emision is ModoEmision.BORRADOR
    assert dto.firmantes == []
    assert dto.codigo is None
    assert dto.fecha_inicio is None and dto.fecha_vencimiento is None
    assert dto.aliado_nombre == "Universidad Contraparte"


# ---- Identificación del borrador en el PDF ------------------------------------


def _dto(modo, secciones=1) -> ConvenioPdfDTO:
    return ConvenioPdfDTO(
        convenio_id=7,
        modo_emision=modo,
        codigo=None,
        solicitud_consecutivo="SOL-7",
        tipo_convenio=INFORMACION_NO_DISPONIBLE,
        estado="EN_TRAMITE",
        etapa="Elaboración",
        alcance="INSTITUCIONAL",
        objeto="Objeto del borrador",
        justificacion=INFORMACION_NO_DISPONIBLE,
        implicacion_financiera=INFORMACION_NO_DISPONIBLE,
        fecha_inicio=None,
        fecha_vencimiento=None,
        duracion_meses=None,
        porcentaje_avance=None,
        version_actual=3,
        solicitante_nombre="Ana Gestora",
        solicitante_correo="ana@usbcali.edu.co",
        solicitante_unidad=INFORMACION_NO_DISPONIBLE,
        solicitante_tipo="INTERNO",
        aliado_nombre="Universidad Propuesta",
        aliado_tipo=INFORMACION_NO_DISPONIBLE,
        aliado_identificacion=INFORMACION_NO_DISPONIBLE,
        aliado_pais=INFORMACION_NO_DISPONIBLE,
        aliado_ciudad=INFORMACION_NO_DISPONIBLE,
        aliado_contacto_nombre=INFORMACION_NO_DISPONIBLE,
        aliado_contacto_correo=INFORMACION_NO_DISPONIBLE,
        secciones_contenido=[
            SeccionContenidoDTO(
                tipo="paragraph",
                texto=f"Cláusula {n}: " + "texto contractual " * 40,
                texto_formateado=f"Cláusula {n}: " + "texto contractual " * 40,
            )
            for n in range(secciones)
        ],
        firmantes=[],
    )


def _textos_por_pagina(monkeypatch, dto) -> dict[int, list[str]]:
    """Registra lo que el canvas dibuja en cada página (marca, encabezado, pie)."""
    dibujado: dict[int, list[str]] = {}
    for metodo in ("drawString", "drawRightString", "drawCentredString"):
        original = getattr(NumberedCanvas, metodo)

        def espia(self, x, y, texto, *args, _original=original, **kwargs):
            dibujado.setdefault(self._pageNumber, []).append(texto)
            return _original(self, x, y, texto, *args, **kwargs)

        monkeypatch.setattr(NumberedCanvas, metodo, espia)
    ServicioPdfConvenio().renderizar_dto_a_pdf(dto)
    return dibujado


def test_pdf_del_borrador_lleva_la_marca_en_todas_las_paginas(monkeypatch):
    paginas = _textos_por_pagina(monkeypatch, _dto(ModoEmision.BORRADOR, secciones=40))

    assert len(paginas) >= 3
    assert all(MARCA_BORRADOR in textos for textos in paginas.values())
    # Las páginas posteriores no se presentan como documento oficial.
    assert not any(
        "Documento Oficial de Convenio" in textos for textos in paginas.values()
    )


def test_pdf_oficial_no_lleva_la_marca_de_borrador(monkeypatch):
    paginas = _textos_por_pagina(monkeypatch, _dto(ModoEmision.OFICIAL, secciones=40))

    assert not any(MARCA_BORRADOR in textos for textos in paginas.values())


def test_encabezado_del_borrador_sustituye_el_titulo_oficial():
    servicio = ServicioPdfConvenio()
    elementos: list = []

    servicio._construir_encabezado_institucional(
        _dto(ModoEmision.BORRADOR), servicio._configurar_estilos(), elementos
    )

    textos = [getattr(elemento, "text", "") for elemento in elementos]
    assert "BORRADOR DE CONVENIO" in textos
    assert MARCA_BORRADOR in textos
    assert "DOCUMENTO OFICIAL DE CONVENIO" not in textos
    fecha = next(texto for texto in textos if texto.startswith("Fecha de generación"))
    assert "Identificador: #7" in fecha and "Versión contractual: 3" in fecha


def test_pdf_del_borrador_sin_firmantes_no_muestra_tabla_de_firmas(monkeypatch):
    construidas: list = []
    monkeypatch.setattr(
        ServicioPdfConvenio,
        "_construir_firmantes",
        lambda self, *args: construidas.append(args),
    )

    ServicioPdfConvenio().renderizar_dto_a_pdf(_dto(ModoEmision.BORRADOR))

    assert construidas == []


# ---- Borrador inválido: 422 sin generar archivos ------------------------------


@pytest.fixture
def sin_renderizado(monkeypatch):
    def no_debe_renderizar(*_args, **_kwargs):
        raise AssertionError("No se debe generar el archivo de un borrador inválido")

    monkeypatch.setattr(
        "backend.services.exportacion_convenio.ServicioPdfConvenio.generar_pdf",
        no_debe_renderizar,
    )
    monkeypatch.setattr(
        "backend.services.exportacion_convenio.ConvenioExcelExportService.generar_excel",
        no_debe_renderizar,
    )


def _sin_objeto(db, client, convenio):
    convenio.objeto = None
    db.commit()


def _sin_entidad(db, client, convenio):
    convenio.solicitud.nombre_aliado_propuesto = None
    db.commit()


def _sin_version(db, client, convenio):
    convenio.version_actual = 99
    db.commit()


def _contenido_vacio(db, client, convenio):
    _guardar_contenido(client, convenio, DOCUMENTO_VACIO)


@pytest.mark.parametrize("formato", ["pdf", "excel"])
@pytest.mark.parametrize(
    ("preparar", "campo"),
    [
        (_sin_objeto, "objeto"),
        (_sin_entidad, "entidad_participante"),
        (_sin_version, "version_contractual"),
        (_contenido_vacio, "clausulas"),
    ],
)
def test_borrador_invalido_responde_422_sin_generar_archivo(
    db, client, gestor, borrador, sin_renderizado, preparar, campo, formato
):
    preparar(db, client, borrador)
    documentos = select(func.count()).select_from(Documento)
    antes = db.scalar(documentos)

    respuesta = _exportar(client, borrador.id, formato)

    assert respuesta.status_code == 422
    assert respuesta.json() == {
        "error": "CONVENIO_INCOMPLETO",
        "message": "No es posible generar el documento oficial. Faltan datos obligatorios.",
        "campos_faltantes": [campo],
    }
    assert db.scalar(documentos) == antes


# ---- Seguridad y aislamiento en borradores -------------------------------------


def test_usuario_sin_permiso_no_exporta_el_borrador(
    client, crear_usuario, entrar_como, borrador
):
    entrar_como(crear_usuario(CodigoRol.SOLICITANTE_INTERNO, TipoUsuario.INTERNO))

    assert _exportar(client, borrador.id, "pdf").status_code == 403


@pytest.mark.parametrize("formato", ["pdf", "excel"])
def test_revisor_fuera_de_alcance_no_exporta_el_borrador(
    client, crear_usuario, entrar_como, borrador, formato
):
    entrar_como(crear_usuario(CodigoRol.REVISOR_ORI, TipoUsuario.INTERNO))

    respuesta = _exportar(client, borrador.id, formato)

    assert respuesta.status_code == 404
    assert borrador.objeto not in respuesta.text


def test_borrador_solo_contiene_su_convenio_y_su_version_actual(
    db, client, gestor, crear_convenio, borrador
):
    otro = crear_convenio(gestor, objeto="Objeto exclusivo de otro borrador")
    _guardar_contenido(client, borrador, _parrafo("Texto de la versión 2"))
    _guardar_contenido(client, borrador, _parrafo("Texto de la versión 3"))

    textos = _textos(_libro(_exportar(client, borrador.id, "excel").content))

    assert "Texto de la versión 3" in textos
    assert "Texto de la versión 2" not in textos
    assert otro.objeto not in textos


def test_borrador_con_texto_especial_genera_pdf_seguro(db, client, gestor, borrador):
    borrador.objeto = 'Objeto <b>sin cerrar & "comillas" <script>x</script>'
    db.commit()
    _guardar_contenido(client, borrador, _parrafo("Cláusula <i> & <para>"))

    respuesta = _exportar(client, borrador.id, "pdf")

    assert respuesta.status_code == 200
    assert respuesta.content.startswith(b"%PDF-")


def test_excel_del_borrador_no_interpreta_formulas(db, client, gestor, borrador):
    borrador.objeto = '=HYPERLINK("http://malicioso")'
    db.commit()

    libro = _libro(_exportar(client, borrador.id, "excel").content)

    valores = {
        fila[0].value: fila[1]
        for fila in libro[HOJA_DATOS_GENERALES].iter_rows(min_row=4)
    }
    assert valores["Objeto"].value == '\'=HYPERLINK("http://malicioso")'
    assert valores["Objeto"].data_type == "s"


# ---- Regresión de la exportación existente -------------------------------------


@pytest.mark.parametrize("formato", ["pdf", "excel"])
def test_un_convenio_formalizado_se_exporta_como_documento_oficial(
    client, db, gestor, convenio_exportable, formato
):
    # HT-06, CA-06: lo que habilita el documento oficial es la formalización,
    # no haber salido de la etapa de elaboración.
    convenio_exportable.estado = "VIGENTE"
    convenio_exportable.fecha_firma = date(2026, 1, 15)
    db.commit()

    respuesta = _exportar(client, convenio_exportable.id, formato)

    assert respuesta.status_code == 200
    disposicion = respuesta.headers["content-disposition"]
    assert 'filename="Convenio_' in disposicion and "BORRADOR" not in disposicion
    if formato == "excel":
        libro = _libro(respuesta.content)
        assert all(hoja["A1"].value != MARCA_BORRADOR for hoja in libro.worksheets)
        assert {"Rector de Prueba", "Representante Legal de Prueba"} <= _textos(libro)


def test_un_convenio_formalizado_conserva_las_validaciones_oficiales(
    db, client, gestor, borrador
):
    # El mismo convenio válido como documento de trabajo no basta para el
    # oficial. Se formaliza sin código: es el caso heredado que la
    # regularización de HT-06 (CA-08) todavía no cubrió, y el validador sigue
    # siendo la red de seguridad.
    borrador.etapa_actual = db.scalar(
        select(Etapa).where(Etapa.codigo == "FIRMA_ARCHIVO_SEGUIMIENTO")
    )
    borrador.estado = "VIGENTE"
    borrador.fecha_firma = date(2026, 1, 15)
    db.commit()

    respuesta = _exportar(client, borrador.id, "pdf")

    assert respuesta.status_code == 422
    campos = respuesta.json()["campos_faltantes"]
    assert {"codigo_convenio", "fecha_inicio_vigencia", "representante_legal_institucion"} <= set(campos)


def test_borrador_con_proceso_de_firmas_no_presenta_firmas(
    db, client, gestor, convenio_exportable
):
    # Si un convenio con proceso configurado vuelve a trámite y a ELABORACION,
    # el documento de trabajo no muestra a sus firmantes como si estuviera
    # formalizado. HT-06: deshacer la formalización exige también el estado,
    # porque el modo ya no depende solo de la etapa.
    convenio_exportable.etapa_actual = db.scalar(
        select(Etapa).where(Etapa.codigo == "ELABORACION")
    )
    convenio_exportable.estado = "EN_TRAMITE"
    convenio_exportable.fecha_firma = None
    db.commit()

    respuesta = _exportar(client, convenio_exportable.id, "excel")

    assert respuesta.status_code == 200
    textos = _textos(_libro(respuesta.content))
    assert MARCA_BORRADOR in textos
    assert "Rector de Prueba" not in textos
    assert "Representante Legal de Prueba" not in textos
