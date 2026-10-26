"""HT-06 BE-04: contrato de exportación según documento en trámite u oficial.

Cubre el callejón sin salida de QA #136 y el punto en que HT-06 se toca con el
borrador persistente de HT-13. Las reglas de completitud de cada modo siguen
viviendo en test_hu24_validador_exportacion.py y test_hu24_borradores.py.
"""

from datetime import date

import pytest
from sqlalchemy import func, select

from backend.models.contador_codigo_convenio import ContadorCodigoConvenio
from backend.models.convenio import Convenio
from backend.models.etapa import Etapa
from backend.schemas.exportacion import (
    ETIQUETA_CODIGO_OFICIAL,
    ETIQUETA_CODIGO_SIN_FORMALIZAR,
    ETIQUETA_REFERENCIA_PROVISIONAL,
    ModoEmision,
    referencia_provisional,
)
from backend.services.pdf_convenio import ServicioPdfConvenio
from backend.services.validador_exportacion_convenio import (
    ConvenioExportValidator,
    modo_emision,
    version_exportable,
)

# Etapas en las que el convenio sigue en trámite y antes emitía documento
# oficial, lo que lo dejaba sin poder exportarse por falta de código (QA #136).
ETAPAS_INTERMEDIAS = [
    "REVISION_AVAL_JURIDICO",
    "REVISION_CONTRAPARTE",
    "REVISION_FINAL",
    "APROBACION_FIRMAS",
]


def _en_etapa(db, convenio: Convenio, codigo_etapa: str) -> Convenio:
    convenio.etapa_actual = db.scalar(
        select(Etapa).where(Etapa.codigo == codigo_etapa)
    )
    db.commit()
    db.expire_all()
    return db.get(Convenio, convenio.id)


# --- CA-07: el convenio en trámite emite documento de trabajo ------------


@pytest.mark.parametrize("etapa", ETAPAS_INTERMEDIAS)
def test_ca07_las_etapas_intermedias_emiten_documento_de_trabajo(
    db, gestor, convenio_listo, etapa
):
    convenio = _en_etapa(db, convenio_listo, etapa)

    assert convenio.codigo is None
    assert modo_emision(convenio) is ModoEmision.BORRADOR
    # Y por tanto no se le exige un código que todavía no existe.
    assert "codigo_convenio" not in ConvenioExportValidator().campos_faltantes(convenio)


@pytest.mark.parametrize("etapa", ETAPAS_INTERMEDIAS)
@pytest.mark.parametrize("formato", ["pdf", "excel"])
def test_ca07_qa136_un_convenio_en_tramite_si_se_exporta(
    client, db, gestor, convenio_listo, etapa, formato
):
    """La regresión de QA #136: antes esto respondía 422 para siempre.

    El documento oficial exige el código institucional y el código solo existe
    al formalizar, así que estas etapas quedaban sin salida.
    """
    convenio = _en_etapa(db, convenio_listo, etapa)

    respuesta = client.get(
        f"/api/convenios/{convenio.id}/exportar", params={"formato": formato}
    )

    assert respuesta.status_code == 200, respuesta.text
    assert "BORRADOR" in respuesta.headers["content-disposition"]


# --- CA-01, CA-07: identificación provisional frente a código oficial ----


def test_ca01_el_documento_de_trabajo_lleva_la_referencia_provisional(
    db, gestor, convenio_listo
):
    convenio = _en_etapa(db, convenio_listo, "REVISION_AVAL_JURIDICO")

    dto = ServicioPdfConvenio().mapear_convenio_a_dto(convenio.id, db)
    etiqueta, valor = dto.identificacion()

    assert etiqueta == ETIQUETA_REFERENCIA_PROVISIONAL
    assert valor == referencia_provisional(convenio.id)
    # No se presenta como un código institucional.
    assert not valor.startswith("USB-ORI-")


def test_ca06_el_documento_oficial_lleva_el_codigo_institucional(
    db, gestor, convenio_exportable
):
    dto = ServicioPdfConvenio().mapear_convenio_a_dto(convenio_exportable.id, db)
    etiqueta, valor = dto.identificacion()

    assert etiqueta == ETIQUETA_CODIGO_OFICIAL
    assert valor == convenio_exportable.codigo


def test_un_codigo_heredado_no_se_presenta_como_oficial(
    db, gestor, convenio_listo
):
    """Corrección 5: tener código no prueba que el convenio esté formalizado.

    Un convenio en trámite puede traer código de antes de CA-05. El documento
    de trabajo lo muestra —identifica al convenio— pero sin rotularlo como
    código oficial, y sin ocultarlo tras la referencia provisional.
    """
    convenio = _en_etapa(db, convenio_listo, "REVISION_AVAL_JURIDICO")
    convenio.codigo = "CONV-CARGADO-A-MANO"
    db.commit()

    dto = ServicioPdfConvenio().mapear_convenio_a_dto(convenio.id, db)
    etiqueta, valor = dto.identificacion()

    assert dto.modo_emision is ModoEmision.BORRADOR
    assert etiqueta == ETIQUETA_CODIGO_SIN_FORMALIZAR
    assert valor == "CONV-CARGADO-A-MANO"
    assert etiqueta != ETIQUETA_CODIGO_OFICIAL


@pytest.mark.parametrize("vacio", ["", "   "])
def test_un_codigo_en_blanco_cae_en_la_referencia_provisional(
    db, gestor, convenio_listo, vacio
):
    convenio = _en_etapa(db, convenio_listo, "REVISION_AVAL_JURIDICO")
    convenio.codigo = vacio
    db.commit()

    dto = ServicioPdfConvenio().mapear_convenio_a_dto(convenio.id, db)
    etiqueta, valor = dto.identificacion()

    assert etiqueta == ETIQUETA_REFERENCIA_PROVISIONAL
    assert valor == referencia_provisional(convenio.id)


# --- CA-04, RN-14: exportar nunca genera un código -----------------------


@pytest.mark.parametrize("formato", ["pdf", "excel"])
def test_rn14_exportar_no_asigna_codigo_ni_consume_consecutivo(
    client, db, gestor, convenio_listo, formato
):
    convenio = _en_etapa(db, convenio_listo, "REVISION_AVAL_JURIDICO")
    contadores_antes = db.scalar(
        select(func.count()).select_from(ContadorCodigoConvenio)
    )

    for _ in range(3):
        respuesta = client.get(
            f"/api/convenios/{convenio.id}/exportar", params={"formato": formato}
        )
        assert respuesta.status_code == 200, respuesta.text

    db.expire_all()
    assert db.get(Convenio, convenio.id).codigo is None
    assert (
        db.scalar(select(func.count()).select_from(ContadorCodigoConvenio))
        == contadores_antes
    )


def test_rn14_exportar_un_convenio_formalizado_conserva_su_codigo(
    client, db, gestor, convenio_exportable
):
    codigo = convenio_exportable.codigo

    for _ in range(3):
        respuesta = client.get(
            f"/api/convenios/{convenio_exportable.id}/exportar",
            params={"formato": "pdf"},
        )
        assert respuesta.status_code == 200, respuesta.text

    db.expire_all()
    assert db.get(Convenio, convenio_exportable.id).codigo == codigo


# --- Punto de contacto con HT-13 ----------------------------------------


def test_en_etapa_intermedia_se_exporta_la_version_formal_no_un_borrador(
    db, gestor, convenio_listo
):
    """HT-06 amplía el modo borrador; HT-13 decide qué contenido se exporta.

    `version_exportable()` devuelve el borrador persistido solo si el modo es
    BORRADOR **y** existe la fila de borrador. Al ampliar el modo, las etapas
    intermedias entran por esa rama, pero allí el borrador ya no existe: se
    elimina al crear la versión formal. Así que caen en la versión contractual,
    que es lo correcto: una revisión jurídica no se hace sobre un avance sin
    versionar.
    """
    convenio = _en_etapa(db, convenio_listo, "REVISION_AVAL_JURIDICO")

    assert modo_emision(convenio) is ModoEmision.BORRADOR
    assert convenio.borrador is None
    version = version_exportable(convenio)
    assert version is not None
    # Es una versión formal persistida, no un envoltorio sin id del borrador.
    assert version.id is not None
    assert version.numero == convenio.version_actual


def test_un_convenio_formalizado_no_exporta_el_borrador(
    db, gestor, convenio_exportable
):
    # Aunque quedara una fila de borrador, el documento oficial nunca la usa.
    assert modo_emision(convenio_exportable) is ModoEmision.OFICIAL
    version = version_exportable(convenio_exportable)

    assert version is not None
    assert version.numero == convenio_exportable.version_actual


# --- CA-05 por la vía del convenio ya formalizado ------------------------


def test_ca04_un_cambio_de_estado_posterior_no_altera_el_codigo(
    db, gestor, convenio_exportable
):
    codigo = convenio_exportable.codigo
    convenio_exportable.estado = "FINALIZADO"
    convenio_exportable.fecha_firma = date(2026, 1, 15)
    db.commit()
    db.expire_all()

    convenio = db.get(Convenio, convenio_exportable.id)
    assert convenio.codigo == codigo
    assert modo_emision(convenio) is ModoEmision.OFICIAL
