"""HT-07: maquetación del PDF del reporte de convenios activos (QA #137, HU-34).

Se prueba el generador sin base de datos: el endpoint, el permiso y los datos
ya los cubre `test_hu34_reporte_convenios_activos.py`.
"""

import re
from datetime import date
from io import BytesIO

import pytest
from openpyxl import load_workbook
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph

from backend.services import reportes
from backend.services.reportes import (
    ActividadResumen,
    ConvenioReporteActivo,
    generar_excel_convenios_activos,
    generar_pdf_convenios_activos,
)

ANCHO_UTIL = reportes._PAGINA[0] - 2 * reportes._MARGEN
ENCABEZADO_PRINCIPAL = b"(Registrado por)"
ENCABEZADO_ACTIVIDADES = b"(Fecha planificada)"


def _convenio(id_: int = 1, **cambios) -> ConvenioReporteActivo:
    datos = {
        "id": id_,
        "codigo": f"USB-ORI-2026-{id_:05d}",
        "objeto": "Movilidad académica",
        "estado": "VIGENTE",
        "aliado": "Universidad Aliada",
        "tipo_convenio": "Marco",
        "unidad_organizacional": "Facultad de Ingeniería",
        "responsable": "Gestora ORI",
        "fecha_inicio": date(2026, 1, 1),
        "fecha_vencimiento": date(2027, 12, 31),
        "actividades": [],
    }
    datos.update(cambios)
    return ConvenioReporteActivo(**datos)


def _actividad(id_: int) -> ActividadResumen:
    return ActividadResumen(
        id=id_,
        titulo=f"Taller de internacionalización {id_}",
        estado="REALIZADA",
        fecha_planificada=date(2026, 2, 1),
        fecha_ejecucion=date(2026, 3, 2),
    )


def _paginas(pdf: bytes) -> list[bytes]:
    """Contenido de cada página. El PDF va sin comprimir y cada página tiene
    un único flujo de contenido, en orden."""
    flujos = re.findall(rb"stream\r?\n(.*?)endstream", pdf, re.DOTALL)
    assert len(flujos) == len(re.findall(rb"/Type /Page\b", pdf))
    return flujos


def _interior(ancho_cm: float) -> float:
    return ancho_cm * cm - 2 * reportes._RELLENO_HORIZONTAL


def _lineas(texto: str, ancho_cm: float) -> int:
    parrafo = Paragraph(texto, reportes._ESTILO_CELDA)
    parrafo.wrap(_interior(ancho_cm), 10_000)
    return len(parrafo.blPara.lines)


# ---- CA-01 / CA-02: encabezados y anchos -------------------------------------


def test_el_pdf_usa_carta_horizontal() -> None:
    pdf = generar_pdf_convenios_activos([_convenio()])

    assert b"/MediaBox [ 0 0 792 612 ]" in pdf


@pytest.mark.parametrize(
    "anchos", [reportes._ANCHOS_COLUMNAS_CM, reportes._ANCHOS_ACTIVIDADES_CM]
)
def test_las_columnas_caben_en_el_area_imprimible(anchos) -> None:
    assert sum(anchos) * cm <= ANCHO_UTIL


@pytest.mark.parametrize(
    ("encabezado", "ancho_cm"),
    [
        *zip(reportes._ENCABEZADOS, reportes._ANCHOS_COLUMNAS_CM, strict=True),
        *zip(
            ["Actividad", "Estado", "Fecha planificada", "Fecha ejecución"],
            reportes._ANCHOS_ACTIVIDADES_CM,
            strict=True,
        ),
    ],
)
def test_cada_encabezado_cabe_completo_en_su_columna(encabezado, ancho_cm) -> None:
    (parrafo,) = reportes._encabezados([encabezado])

    # Si la palabra más larga cabe, el encabezado se ajusta por palabras
    # completas y no invade la columna vecina.
    assert parrafo.minWidth() <= _interior(ancho_cm)


# ---- CA-03: campos cortos compactos y textos extensos ------------------------


@pytest.mark.parametrize(
    ("columna", "texto"),
    [
        ("Convenio", "USB-ORI-2026-00001"),
        ("Fecha inicio", "2026-12-31"),
        ("Fecha vencimiento", "2026-12-31"),
        ("Actividades", "12 registrada(s)"),
    ],
)
def test_los_campos_cortos_ocupan_una_sola_linea(columna, texto) -> None:
    ancho_cm = reportes._ANCHOS_COLUMNAS_CM[reportes._ENCABEZADOS.index(columna)]

    assert _lineas(texto, ancho_cm) == 1


def test_un_objeto_muy_extenso_se_genera_completo_y_sin_partir_filas() -> None:
    palabras = [f"P{k:05d}" for k in range(3000)]
    convenios = [_convenio(1), _convenio(2, objeto=" ".join(palabras)), _convenio(3)]

    pdf = generar_pdf_convenios_activos(convenios)

    assert set(re.findall(rb"P\d{5}", pdf)) == {p.encode() for p in palabras}
    paginas = _paginas(pdf)
    assert len(paginas) > 1
    # Nunca hay un encabezado repetido a mitad de página, que es lo que deja
    # una fila partida entre páginas.
    assert max(p.count(ENCABEZADO_PRINCIPAL) for p in paginas) == 1


def test_las_filas_de_continuacion_identifican_su_convenio() -> None:
    objeto = " ".join(f"Cláusula{k}" for k in range(1500))

    filas = reportes._filas(_convenio(2, objeto=objeto))

    # Que el texto llegue completo al PDF lo verifica la prueba anterior.
    assert len(filas) > 1
    assert {f[0].getPlainText() for f in filas[1:]} == {"USB-ORI-2026-00002 (continuación)"}


def test_un_objeto_normal_no_genera_filas_de_continuacion() -> None:
    objeto = "Cooperación académica y movilidad estudiantil. " * 20

    assert len(reportes._filas(_convenio(objeto=objeto))) == 1


# ---- CA-04: reportes multipágina ---------------------------------------------


def test_muchos_convenios_repiten_el_encabezado_en_cada_pagina_de_la_tabla() -> None:
    convenios = [
        _convenio(i, objeto="Cooperación académica. " * (i % 7 + 1)) for i in range(1, 61)
    ]

    paginas = _paginas(generar_pdf_convenios_activos(convenios))

    encabezados = [p.count(ENCABEZADO_PRINCIPAL) for p in paginas]
    assert sum(encabezados) > 1
    assert max(encabezados) == 1


def test_muchas_actividades_repiten_el_encabezado_de_su_tabla() -> None:
    convenio = _convenio(actividades=[_actividad(i) for i in range(1, 81)])

    paginas = _paginas(generar_pdf_convenios_activos([convenio]))

    encabezados = [p.count(ENCABEZADO_ACTIVIDADES) for p in paginas]
    assert sum(encabezados) > 1
    assert max(encabezados) == 1


# ---- CA-06: caracteres especiales y reporte vacío ----------------------------


def test_caracteres_especiales_se_muestran_como_texto() -> None:
    objeto = 'Convenio "especial" & <b>técnico</b> — ñandú \'citas\''
    aliado = "Aliado & Cía <S.A.>"
    convenio = _convenio(
        objeto=objeto,
        aliado=aliado,
        actividades=[
            ActividadResumen(1, 'Taller "IA" & <datos>', "REALIZADA", None, date(2026, 3, 2))
        ],
    )

    pdf = generar_pdf_convenios_activos([convenio])

    assert pdf.startswith(b"%PDF")
    # Se escapan para Paragraph: se ven literales, no como marcado.
    fila = reportes._fila(convenio)
    assert [fila[1].getPlainText(), fila[2].getPlainText()] == [objeto, aliado]


def test_reporte_vacio_genera_una_pagina_con_el_aviso() -> None:
    pdf = generar_pdf_convenios_activos([])

    assert len(_paginas(pdf)) == 1
    assert b"No hay convenios activos para mostrar." in pdf


# ---- CA-05: el Excel queda fuera de la corrección ----------------------------


def test_el_excel_conserva_sus_encabezados() -> None:
    libro = load_workbook(BytesIO(generar_excel_convenios_activos([_convenio()])))

    assert [c.value for c in libro["Convenios activos"][1]] == [
        "Convenio",
        "Objeto",
        "Aliado",
        "Tipo de convenio",
        "Unidad",
        "Registrado por",
        "Fecha inicio",
        "Fecha vencimiento",
        "N.º de actividades",
    ]
    assert [c.value for c in libro["Actividades"][1]] == [
        "Convenio",
        "Actividad",
        "Estado",
        "Fecha planificada",
        "Fecha ejecución",
    ]
