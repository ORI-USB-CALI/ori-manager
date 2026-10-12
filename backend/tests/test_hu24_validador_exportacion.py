"""HU-24 BE-01: validación de completitud antes de exportar el convenio (CA-03)."""
from datetime import date

import pytest
from sqlalchemy import func, select

from backend.models.aliado import Aliado
from backend.models.convenio import Convenio
from backend.models.documento import Documento
from backend.models.firma_convenio import FirmaConvenio
from backend.models.proceso_firmas_convenio import ProcesoFirmasConvenio
from backend.models.solicitud_convenio import SolicitudConvenio
from backend.models.version_convenio import VersionConvenio
from backend.services.exportacion_convenio import (
    MENSAJE_CONVENIO_INCOMPLETO,
    ErrorValidacionExportacion,
)
from backend.services.validador_exportacion_convenio import ConvenioExportValidator

DOCUMENTO_CON_TEXTO = {
    "type": "doc",
    "content": [
        {"type": "paragraph", "content": [{"type": "text", "text": "Cláusula primera"}]}
    ],
}
DOCUMENTO_VACIO = {"type": "doc", "content": [{"type": "paragraph"}]}


def _firma(rol, parte, nombre="Nombre del firmante"):
    return FirmaConvenio(rol_firmante=rol, parte=parte, nombre_firmante=nombre)


def _convenio_completo(**cambios) -> Convenio:
    """Convenio en memoria (sin BD) con todo lo que exige la exportación."""
    datos = {
        "codigo": "CONV-0001",
        "objeto": "Cooperación académica",
        "tipo_convenio_id": 1,
        "fecha_inicio": date(2026, 1, 1),
        "fecha_vencimiento": date(2028, 1, 1),
        "version_actual": 1,
        "aliado": Aliado(nombre="Universidad Aliada"),
        "solicitud": SolicitudConvenio(nombre_aliado_propuesto=None),
        "versiones": [VersionConvenio(numero=1, contenido=DOCUMENTO_CON_TEXTO)],
        "procesos_firmas": [
            ProcesoFirmasConvenio(
                estado="CONFIGURACION",
                firmas=[
                    _firma("RECTOR", "UNIVERSIDAD"),
                    _firma("PARTE_SOLICITANTE", "REPRESENTANTE_LEGAL_ENTIDAD"),
                ],
            )
        ],
    }
    datos.update(cambios)
    return Convenio(**datos)


def _faltantes(convenio: Convenio) -> list[str]:
    return ConvenioExportValidator().campos_faltantes(convenio)


# ---- Validador: reglas de cada campo -------------------------------------------


def test_convenio_completo_no_tiene_faltantes():
    assert _faltantes(_convenio_completo()) == []


@pytest.mark.parametrize(
    ("cambios", "campo"),
    [
        ({"codigo": None}, "codigo_convenio"),
        ({"codigo": "   "}, "codigo_convenio"),
        ({"aliado": None}, "entidad_participante"),
        ({"fecha_inicio": None}, "fecha_inicio_vigencia"),
        ({"fecha_vencimiento": None}, "fecha_fin_vigencia"),
        ({"objeto": "  "}, "objeto"),
        ({"tipo_convenio_id": None}, "tipo_convenio"),
        ({"versiones": []}, "clausulas"),
        (
            {"versiones": [VersionConvenio(numero=1, contenido=DOCUMENTO_VACIO)]},
            "clausulas",
        ),
        (
            {"versiones": [VersionConvenio(numero=1, contenido={"type": "html"})]},
            "clausulas",
        ),
    ],
)
def test_cada_campo_obligatorio_se_reporta_solo(cambios, campo):
    assert _faltantes(_convenio_completo(**cambios)) == [campo]


def test_aliado_propuesto_en_la_solicitud_cuenta_como_entidad():
    convenio = _convenio_completo(
        aliado=None,
        solicitud=SolicitudConvenio(nombre_aliado_propuesto="Empresa propuesta"),
    )
    assert _faltantes(convenio) == []


def test_usa_la_ultima_version_si_no_aparece_la_actual():
    convenio = _convenio_completo(
        version_actual=3,
        versiones=[
            VersionConvenio(numero=1, contenido=DOCUMENTO_VACIO),
            VersionConvenio(numero=2, contenido=DOCUMENTO_CON_TEXTO),
        ],
    )
    assert _faltantes(convenio) == []


def test_sin_proceso_de_firmas_faltan_ambos_representantes():
    assert _faltantes(_convenio_completo(procesos_firmas=[])) == [
        "representante_legal_institucion",
        "representante_legal_entidad",
    ]


def test_proceso_cancelado_no_cuenta_para_los_representantes():
    proceso = _convenio_completo().procesos_firmas[0]
    proceso.estado = "CANCELADO"
    convenio = _convenio_completo(procesos_firmas=[proceso])
    assert _faltantes(convenio) == [
        "representante_legal_institucion",
        "representante_legal_entidad",
    ]


def test_firmante_sin_nombre_no_cuenta_como_representante():
    proceso = ProcesoFirmasConvenio(
        estado="EN_CURSO",
        firmas=[
            _firma("RECTOR", "UNIVERSIDAD", nombre="   "),
            _firma("PARTE_SOLICITANTE", "REPRESENTANTE_LEGAL_ENTIDAD"),
        ],
    )
    assert _faltantes(_convenio_completo(procesos_firmas=[proceso])) == [
        "representante_legal_institucion"
    ]


def test_unidad_solicitante_representa_a_la_contraparte_interna():
    proceso = ProcesoFirmasConvenio(
        estado="COMPLETADO",
        firmas=[
            _firma("RECTOR", "UNIVERSIDAD"),
            _firma("PARTE_SOLICITANTE", "UNIDAD_SOLICITANTE"),
        ],
    )
    assert _faltantes(_convenio_completo(procesos_firmas=[proceso])) == []


def test_error_expone_el_contrato_de_la_tarea():
    error = ErrorValidacionExportacion(["fecha_fin_vigencia", "objeto"])

    assert error.como_respuesta() == {
        "error": "CONVENIO_INCOMPLETO",
        "message": "No es posible generar el documento oficial. Faltan datos obligatorios.",
        "campos_faltantes": ["fecha_fin_vigencia", "objeto"],
    }


# ---- Endpoint de exportación ---------------------------------------------------


@pytest.mark.parametrize("formato", ["pdf", "excel"])
def test_convenio_incompleto_responde_422_con_el_json_de_la_tarea(
    client, gestor, convenio_listo, formato
):
    respuesta = client.get(
        f"/api/convenios/{convenio_listo.id}/exportar?formato={formato}"
    )

    assert respuesta.status_code == 422
    cuerpo = respuesta.json()
    # El error va en el nivel superior del cuerpo, no dentro de "detail".
    assert set(cuerpo) == {"error", "message", "campos_faltantes"}
    assert cuerpo["error"] == "CONVENIO_INCOMPLETO"
    assert cuerpo["message"] == MENSAJE_CONVENIO_INCOMPLETO
    assert "codigo_convenio" in cuerpo["campos_faltantes"]
    assert "representante_legal_institucion" in cuerpo["campos_faltantes"]


def test_convenio_incompleto_no_renderiza_ni_guarda_archivos(
    client, db, gestor, convenio_listo, monkeypatch
):
    def no_debe_renderizar(*_args, **_kwargs):
        raise AssertionError("No se debe renderizar un convenio incompleto")

    monkeypatch.setattr(
        "backend.services.exportacion_convenio.ServicioPdfConvenio.generar_pdf",
        no_debe_renderizar,
    )
    monkeypatch.setattr(
        "backend.services.exportacion_convenio.ConvenioExcelExportService.generar_excel",
        no_debe_renderizar,
    )
    documentos = select(func.count()).select_from(Documento)
    antes = db.scalar(documentos)

    for formato in ("pdf", "excel"):
        respuesta = client.get(
            f"/api/convenios/{convenio_listo.id}/exportar?formato={formato}"
        )
        assert respuesta.status_code == 422

    assert db.scalar(documentos) == antes


def test_convenio_completo_se_exporta(client, gestor, convenio_exportable):
    respuesta = client.get(
        f"/api/convenios/{convenio_exportable.id}/exportar?formato=pdf"
    )

    assert respuesta.status_code == 200
    assert respuesta.headers["content-type"] == "application/pdf"
