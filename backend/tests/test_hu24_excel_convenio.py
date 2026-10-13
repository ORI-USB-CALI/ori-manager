"""HU-24 BE-03: exportación del convenio a Excel con openpyxl."""
from datetime import date
from io import BytesIO

import pytest
from openpyxl import load_workbook

from backend.schemas.exportacion import (
    ConvenioPdfDTO,
    FirmantePdfDTO,
    SeccionContenidoDTO,
)
from backend.services.excel_convenio import (
    HOJA_DATOS_GENERALES,
    HOJA_PARTICIPANTES_COMPROMISOS,
    ConvenioExcelExportService,
)

MEDIA_TYPE_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
OBJETO_LARGO = "Cooperación académica e investigativa entre ambas instituciones " * 3


def _dto(**cambios) -> ConvenioPdfDTO:
    datos = {
        "convenio_id": 1,
        "codigo": "CONV-0001",
        "solicitud_consecutivo": "SOL-0001",
        "tipo_convenio": "Marco",
        "estado": "VIGENTE",
        "etapa": "Firma, archivo y seguimiento",
        "alcance": "INSTITUCIONAL",
        "objeto": OBJETO_LARGO,
        "justificacion": "Fortalecer la movilidad",
        "implicacion_financiera": "Sin costo para la Universidad",
        "fecha_inicio": date(2026, 1, 1),
        "fecha_vencimiento": date(2028, 1, 1),
        "duracion_meses": 24,
        "porcentaje_avance": 10,
        "version_actual": 2,
        "solicitante_nombre": "Ana Gestora",
        "solicitante_correo": "ana@usbcali.edu.co",
        "solicitante_unidad": "Facultad de Ingeniería",
        "solicitante_tipo": "INTERNO",
        "aliado_nombre": "Universidad Aliada",
        "aliado_tipo": "UNIVERSIDAD",
        "aliado_identificacion": "900123456",
        "aliado_pais": "Colombia",
        "aliado_ciudad": "Bogotá",
        "aliado_contacto_nombre": "Luis Contacto",
        "aliado_contacto_correo": "luis@aliada.edu.co",
        "secciones_contenido": [
            SeccionContenidoDTO(
                tipo="heading", texto="Cláusulas", texto_formateado="Cláusulas"
            ),
            SeccionContenidoDTO(
                tipo="paragraph",
                texto="Primera: objeto del convenio",
                texto_formateado="<b>Primera:</b> objeto del convenio",
            ),
        ],
        "firmantes": [
            FirmantePdfDTO(
                orden=6,
                rol="Rector",
                parte="UNIVERSIDAD",
                nombre="Rector de Prueba",
                cargo="Rector",
                modalidad="FISICA",
                estado="PENDIENTE",
            )
        ],
    }
    datos.update(cambios)
    return ConvenioPdfDTO(**datos)


def _libro(contenido: bytes):
    return load_workbook(BytesIO(contenido))


def _datos_generales(hoja) -> dict[str, object]:
    return {
        fila[0].value: fila[1].value for fila in hoja.iter_rows(min_row=2) if fila[0].value
    }


def _textos(hoja) -> set[str]:
    return {str(celda.value) for fila in hoja.iter_rows() for celda in fila if celda.value}


@pytest.fixture
def libro():
    return _libro(ConvenioExcelExportService().construir_libro(_dto()))


def test_genera_dos_hojas_con_los_nombres_de_la_tarea(libro):
    assert libro.sheetnames == [HOJA_DATOS_GENERALES, HOJA_PARTICIPANTES_COMPROMISOS]
    assert libro.sheetnames == ["Datos Generales", "Participantes y Compromisos"]


def test_datos_generales_vuelca_los_datos_del_convenio(libro):
    datos = _datos_generales(libro[HOJA_DATOS_GENERALES])

    assert datos["Código del convenio"] == "CONV-0001"
    assert datos["Objeto"] == OBJETO_LARGO
    assert datos["Tipo de convenio"] == "Marco"
    # Las fechas se guardan como fechas de Excel, no como texto.
    assert datos["Fecha de inicio de vigencia"].date() == date(2026, 1, 1)
    assert datos["Fecha de fin de vigencia"].date() == date(2028, 1, 1)
    assert datos["Duración (meses)"] == 24


def test_participantes_y_compromisos(libro):
    textos = _textos(libro[HOJA_PARTICIPANTES_COMPROMISOS])

    assert {"Participantes", "Firmantes", "Compromisos"} <= textos
    assert {"Universidad Aliada", "900123456", "Ana Gestora"} <= textos
    assert {"Rector de Prueba", "PENDIENTE"} <= textos
    assert {"Sin costo para la Universidad", "Primera: objeto del convenio"} <= textos


def test_cabeceras_en_negrita_con_fondo_neutro(libro):
    for hoja, celda in (
        (libro[HOJA_DATOS_GENERALES], "A1"),
        (libro[HOJA_DATOS_GENERALES], "B1"),
        (libro[HOJA_PARTICIPANTES_COMPROMISOS], "A2"),
    ):
        assert hoja[celda].font.bold is True
        assert hoja[celda].fill.fgColor.rgb.endswith("D9D9D9")


def test_ancho_de_columna_se_ajusta_al_contenido(libro):
    hoja = libro[HOJA_DATOS_GENERALES]
    ancho_objeto = hoja.column_dimensions["B"].width

    # 13 es el ancho por defecto de Excel; el objeto largo lo supera, con tope.
    assert 13 < ancho_objeto <= 80
    assert hoja.column_dimensions["A"].width >= len("Consecutivo de la solicitud")


def test_convenio_sin_firmantes_se_indica_en_la_tabla():
    contenido = ConvenioExcelExportService().construir_libro(_dto(firmantes=[]))

    textos = _textos(_libro(contenido)[HOJA_PARTICIPANTES_COMPROMISOS])
    assert "Sin firmantes registrados" in textos


def test_endpoint_descarga_xlsx_con_los_datos_del_convenio(
    client, gestor, convenio_exportable
):
    respuesta = client.get(
        f"/api/convenios/{convenio_exportable.id}/exportar?formato=excel"
    )

    assert respuesta.status_code == 200
    assert respuesta.headers["content-type"] == MEDIA_TYPE_XLSX
    assert respuesta.headers["content-disposition"].endswith('.xlsx"')
    libro = _libro(respuesta.content)
    datos = _datos_generales(libro[HOJA_DATOS_GENERALES])
    assert datos["Código del convenio"] == convenio_exportable.codigo
    assert datos["Objeto"] == convenio_exportable.objeto
    textos = _textos(libro[HOJA_PARTICIPANTES_COMPROMISOS])
    assert {"Rector de Prueba", "Representante Legal de Prueba"} <= textos
