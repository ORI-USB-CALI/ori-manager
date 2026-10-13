"""HU-24 BE-01: validación de completitud antes de exportar el convenio (CA-03)."""
from datetime import date

import pytest
from sqlalchemy import func, select

from backend.models.aliado import Aliado
from backend.models.convenio import Convenio
from backend.models.documento import Documento
from backend.models.etapa import Etapa
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


def _version(id_, numero, contenido=DOCUMENTO_CON_TEXTO):
    # Ids explícitos: el validador asocia procesos y versiones por id.
    return VersionConvenio(id=id_, numero=numero, contenido=contenido)


def _proceso(version_id=1, estado="CONFIGURACION", firmas=None):
    return ProcesoFirmasConvenio(
        version_convenio_id=version_id,
        estado=estado,
        firmas=firmas
        if firmas is not None
        else [
            _firma("RECTOR", "UNIVERSIDAD"),
            _firma("PARTE_SOLICITANTE", "REPRESENTANTE_LEGAL_ENTIDAD"),
        ],
    )


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
        "versiones": [_version(1, 1)],
        "procesos_firmas": [_proceso()],
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
        ({"versiones": [_version(1, 1, DOCUMENTO_VACIO)]}, "clausulas"),
        ({"versiones": [_version(1, 1, {"type": "html"})]}, "clausulas"),
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


# ---- Versión contractual -------------------------------------------------------


def test_sin_versiones_falta_la_version_contractual():
    faltantes = _faltantes(_convenio_completo(versiones=[]))

    assert "version_contractual" in faltantes
    # Sin la versión no se pueden evaluar sus cláusulas ni sus firmas.
    assert "clausulas" not in faltantes


def test_no_usa_otra_version_cuando_falta_la_indicada():
    # El convenio indica la versión 3; existen la 1 y la 2, ambas con texto.
    convenio = _convenio_completo(
        version_actual=3,
        versiones=[_version(1, 1), _version(2, 2)],
        procesos_firmas=[_proceso(version_id=2)],
    )

    # Ni el texto ni las firmas de la versión 2 sustituyen a la 3.
    assert _faltantes(convenio) == [
        "version_contractual",
        "representante_legal_institucion",
        "representante_legal_entidad",
    ]


def test_proceso_completado_de_la_v1_no_bloquea_la_v2_con_su_proceso():
    convenio = _convenio_completo(
        version_actual=2,
        versiones=[_version(1, 1), _version(2, 2)],
        procesos_firmas=[
            _proceso(version_id=1, estado="COMPLETADO"),
            _proceso(version_id=2, estado="CONFIGURACION"),
        ],
    )

    assert _faltantes(convenio) == []


def test_v2_sin_proceso_no_usa_los_firmantes_de_la_v1_completada():
    convenio = _convenio_completo(
        version_actual=2,
        versiones=[_version(1, 1), _version(2, 2)],
        procesos_firmas=[_proceso(version_id=1, estado="COMPLETADO")],
    )

    # Se rechaza por los requisitos de la versión actual, no por el histórico.
    assert _faltantes(convenio) == [
        "representante_legal_institucion",
        "representante_legal_entidad",
    ]


def test_proceso_cancelado_de_otra_version_no_afecta_al_vigente():
    convenio = _convenio_completo(
        version_actual=2,
        versiones=[_version(1, 1), _version(2, 2)],
        procesos_firmas=[
            _proceso(version_id=1, estado="CANCELADO"),
            _proceso(version_id=2, estado="EN_CURSO"),
        ],
    )

    assert _faltantes(convenio) == []


def test_version_sin_id_no_se_asocia_a_ningun_proceso():
    convenio = _convenio_completo(
        versiones=[VersionConvenio(numero=1, contenido=DOCUMENTO_CON_TEXTO)],
        procesos_firmas=[_proceso(version_id=None)],
    )

    assert "representante_legal_institucion" in _faltantes(convenio)


# ---- Representantes legales ----------------------------------------------------


def test_sin_proceso_de_firmas_faltan_ambos_representantes():
    assert _faltantes(_convenio_completo(procesos_firmas=[])) == [
        "representante_legal_institucion",
        "representante_legal_entidad",
    ]


def test_proceso_cancelado_no_cuenta_para_los_representantes():
    convenio = _convenio_completo(procesos_firmas=[_proceso(estado="CANCELADO")])
    assert _faltantes(convenio) == [
        "representante_legal_institucion",
        "representante_legal_entidad",
    ]


def test_firmante_sin_nombre_no_cuenta_como_representante():
    proceso = _proceso(
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
    proceso = _proceso(
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


@pytest.fixture
def convenio_oficial_incompleto(db, convenio_listo):
    """Fuera de ELABORACION rige la validación completa del documento oficial."""
    convenio_listo.etapa_actual = db.scalar(
        select(Etapa).where(Etapa.codigo == "REVISION_AVAL_JURIDICO")
    )
    db.commit()
    return convenio_listo


@pytest.mark.parametrize("formato", ["pdf", "excel"])
def test_convenio_incompleto_responde_422_con_el_json_de_la_tarea(
    client, gestor, convenio_oficial_incompleto, formato
):
    respuesta = client.get(
        f"/api/convenios/{convenio_oficial_incompleto.id}/exportar?formato={formato}"
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
    client, db, gestor, convenio_oficial_incompleto, monkeypatch
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
            f"/api/convenios/{convenio_oficial_incompleto.id}/exportar?formato={formato}"
        )
        assert respuesta.status_code == 422

    assert db.scalar(documentos) == antes


def test_convenio_completo_se_exporta(client, gestor, convenio_exportable):
    respuesta = client.get(
        f"/api/convenios/{convenio_exportable.id}/exportar?formato=pdf"
    )

    assert respuesta.status_code == 200
    assert respuesta.headers["content-type"] == "application/pdf"
