from copy import deepcopy

import pytest
from sqlalchemy import func, select

from backend.models.auditoria import Auditoria
from backend.models.enums import ContextoVersionConvenio
from backend.models.revision_convenio import RevisionConvenio
from backend.models.solicitud_convenio import SolicitudConvenio
from backend.models.version_convenio import VersionConvenio


def _texto(nodo: dict[str, object]) -> str:
    partes = [nodo.get("text", "")]
    for hijo in nodo.get("content", []):
        partes.append(_texto(hijo))
    return " ".join(str(parte) for parte in partes)


def _elaboracion(client, convenio_id: int) -> dict[str, object]:
    respuesta = client.get(f"/api/convenios/{convenio_id}/elaboracion")
    assert respuesta.status_code == 200
    return respuesta.json()


def test_iniciar_crea_plantilla_version_inicial_y_precarga_sin_tocar_solicitud(
    client, db, convenio_listo
) -> None:
    solicitud = db.get(SolicitudConvenio, convenio_listo.solicitud_id)
    original = (solicitud.objeto, solicitud.justificacion, solicitud.actualizado_en)

    cuerpo = _elaboracion(client, convenio_listo.id)
    assert cuerpo["version_actual"] == 1
    assert cuerpo["plantilla_origen"]["codigo"] == "BASE_HU12"
    texto = _texto(cuerpo["contenido"])
    assert solicitud.objeto in texto
    assert solicitud.justificacion in texto
    assert solicitud.nombre_aliado_propuesto in texto

    version = db.scalar(
        select(VersionConvenio).where(
            VersionConvenio.convenio_id == convenio_listo.id,
            VersionConvenio.numero == 1,
        )
    )
    assert version.autor_id == convenio_listo.creado_por_id
    assert version.etapa_id == convenio_listo.etapa_actual_id
    assert version.contexto == ContextoVersionConvenio.INICIALIZACION
    assert version.creado_en is not None
    db.refresh(solicitud)
    assert (
        solicitud.objeto,
        solicitud.justificacion,
        solicitud.actualizado_en,
    ) == original


def test_guardar_crea_version_consecutiva_y_sin_cambios_no_duplica(
    client, db, convenio_listo
) -> None:
    cuerpo = _elaboracion(client, convenio_listo.id)
    contenido = deepcopy(cuerpo["contenido"])
    contenido["content"].append(
        {
            "type": "paragraph",
            "content": [{"type": "text", "text": "Nueva cláusula de prueba"}],
        }
    )
    payload = {"contenido": contenido, "expected_version": 1}

    guardada = client.patch(
        f"/api/convenios/{convenio_listo.id}/elaboracion", json=payload
    )
    assert guardada.status_code == 200
    assert guardada.json()["version_actual"] == 2
    repetida = client.patch(
        f"/api/convenios/{convenio_listo.id}/elaboracion",
        json={"contenido": contenido, "expected_version": 2},
    )
    assert repetida.status_code == 200
    assert repetida.json()["version_actual"] == 2

    versiones = list(
        db.scalars(
            select(VersionConvenio)
            .where(VersionConvenio.convenio_id == convenio_listo.id)
            .order_by(VersionConvenio.numero)
        )
    )
    assert [version.numero for version in versiones] == [1, 2]
    assert "Nueva cláusula" not in _texto(versiones[0].contenido)
    assert "Nueva cláusula" in _texto(versiones[1].contenido)
    auditoria = db.scalar(
        select(Auditoria).where(
            Auditoria.entidad == "convenio",
            Auditoria.registro_id == convenio_listo.id,
            Auditoria.campo == "contenido_proyecto",
        )
    )
    assert (auditoria.valor_anterior, auditoria.valor_nuevo) == (
        "versión 1",
        "versión 2",
    )
    assert "Nueva cláusula" not in (auditoria.valor_nuevo or "")


def test_expected_version_obsoleta_responde_409_sin_sobrescribir(
    client, db, convenio_listo
) -> None:
    original = _elaboracion(client, convenio_listo.id)["contenido"]
    primera = deepcopy(original)
    primera["content"].append(
        {"type": "paragraph", "content": [{"type": "text", "text": "Pestaña A"}]}
    )
    assert (
        client.patch(
            f"/api/convenios/{convenio_listo.id}/elaboracion",
            json={"contenido": primera, "expected_version": 1},
        ).status_code
        == 200
    )
    segunda = deepcopy(original)
    segunda["content"].append(
        {"type": "paragraph", "content": [{"type": "text", "text": "Pestaña B"}]}
    )
    conflicto = client.patch(
        f"/api/convenios/{convenio_listo.id}/elaboracion",
        json={"contenido": segunda, "expected_version": 1},
    )
    assert conflicto.status_code == 409
    assert conflicto.json()["detail"]["current_version"] == 2
    actual = db.scalar(
        select(VersionConvenio).where(
            VersionConvenio.convenio_id == convenio_listo.id,
            VersionConvenio.numero == 2,
        )
    )
    assert "Pestaña A" in _texto(actual.contenido)
    assert "Pestaña B" not in _texto(actual.contenido)


def test_json_desconocido_html_crudo_y_atributos_peligrosos_son_rechazados(
    client, convenio_listo
) -> None:
    casos = [
        {"type": "doc", "content": [{"type": "script", "text": "alert(1)"}]},
        {"type": "doc", "content": [{"type": "html", "text": "<iframe />"}]},
        {
            "type": "doc",
            "content": [{"type": "paragraph", "attrs": {"onclick": "alert(1)"}}],
        },
    ]
    for contenido in casos:
        respuesta = client.patch(
            f"/api/convenios/{convenio_listo.id}/elaboracion",
            json={"contenido": contenido, "expected_version": 1},
        )
        assert respuesta.status_code == 422


def test_contenido_de_todas_las_capacidades_visibles_se_puede_guardar(
    client, convenio_listo
) -> None:
    contenido = {
        "type": "doc",
        "content": [
            {
                "type": "heading",
                "attrs": {"level": 1},
                "content": [
                    {"type": "text", "text": "Título", "marks": [{"type": "bold"}]}
                ],
            },
            {
                "type": "heading",
                "attrs": {"level": 2},
                "content": [
                    {
                        "type": "text",
                        "text": "Subtítulo",
                        "marks": [{"type": "italic"}],
                    }
                ],
            },
            {
                "type": "paragraph",
                "content": [
                    {"type": "text", "text": "Primera línea"},
                    {"type": "hardBreak"},
                    {"type": "text", "text": "Segunda línea"},
                ],
            },
            {
                "type": "bulletList",
                "content": [
                    {
                        "type": "listItem",
                        "content": [
                            {
                                "type": "paragraph",
                                "content": [{"type": "text", "text": "Viñeta"}],
                            }
                        ],
                    }
                ],
            },
            {
                "type": "orderedList",
                "attrs": {"start": 1, "type": None},
                "content": [
                    {
                        "type": "listItem",
                        "content": [
                            {
                                "type": "paragraph",
                                "content": [{"type": "text", "text": "Numerada"}],
                            }
                        ],
                    }
                ],
            },
        ],
    }

    respuesta = client.patch(
        f"/api/convenios/{convenio_listo.id}/elaboracion",
        json={"contenido": contenido, "expected_version": 1},
    )

    assert respuesta.status_code == 200
    assert respuesta.json()["version_actual"] == 2
    assert respuesta.json()["contenido"] == contenido


def _lista_numerada(attrs: dict[str, object]) -> dict[str, object]:
    return {
        "type": "doc",
        "content": [
            {
                "type": "orderedList",
                "attrs": attrs,
                "content": [
                    {
                        "type": "listItem",
                        "content": [
                            {
                                "type": "paragraph",
                                "content": [{"type": "text", "text": "Elemento"}],
                            }
                        ],
                    }
                ],
            }
        ],
    }


@pytest.mark.parametrize(
    "attrs",
    [
        {"start": 1, "type": None},
        {"start": 3, "type": None},
    ],
    ids=["estandar-tiptap", "inicio-personalizado-tiptap"],
)
def test_attrs_reales_de_lista_numerada_tiptap_son_validos(
    client, convenio_listo, attrs
) -> None:
    respuesta = client.patch(
        f"/api/convenios/{convenio_listo.id}/elaboracion",
        json={"contenido": _lista_numerada(attrs), "expected_version": 1},
    )

    assert respuesta.status_code == 200
    assert respuesta.json()["contenido"] == _lista_numerada(attrs)


@pytest.mark.parametrize(
    "attrs",
    [
        {"start": 1, "type": None, "class": "lista"},
        {"start": 0, "type": None},
        {"start": 1_000_001, "type": None},
        {"start": True, "type": None},
        {"start": 1, "type": "A"},
    ],
    ids=[
        "atributo-desconocido",
        "inicio-cero",
        "inicio-sobre-limite",
        "inicio-booleano",
        "tipo-no-soportado",
    ],
)
def test_attrs_invalidos_de_lista_numerada_son_rechazados(
    client, convenio_listo, attrs
) -> None:
    respuesta = client.patch(
        f"/api/convenios/{convenio_listo.id}/elaboracion",
        json={"contenido": _lista_numerada(attrs), "expected_version": 1},
    )

    assert respuesta.status_code == 422


@pytest.mark.parametrize(
    "nodo",
    [
        {
            "type": "paragraph",
            "content": [
                {
                    "type": "text",
                    "text": "https://example.com",
                    "marks": [
                        {"type": "link", "attrs": {"href": "https://example.com"}}
                    ],
                }
            ],
        },
        {
            "type": "paragraph",
            "content": [
                {
                    "type": "text",
                    "text": "Negrita con attrs",
                    "marks": [{"type": "bold", "attrs": {}}],
                }
            ],
        },
        {
            "type": "paragraph",
            "content": [
                {"type": "text", "text": "Subrayado", "marks": [{"type": "underline"}]}
            ],
        },
        {
            "type": "paragraph",
            "content": [
                {"type": "text", "text": "Tachado", "marks": [{"type": "strike"}]}
            ],
        },
        {
            "type": "paragraph",
            "content": [
                {"type": "text", "text": "Código", "marks": [{"type": "code"}]}
            ],
        },
        {
            "type": "table",
            "content": [
                {
                    "type": "tableRow",
                    "content": [
                        {
                            "type": "tableCell",
                            "content": [{"type": "paragraph"}],
                        }
                    ],
                }
            ],
        },
    ],
    ids=["link", "mark-attrs", "underline", "strike", "code", "table"],
)
def test_capacidades_fuera_del_editor_son_rechazadas(
    client, convenio_listo, nodo
) -> None:
    respuesta = client.patch(
        f"/api/convenios/{convenio_listo.id}/elaboracion",
        json={
            "contenido": {"type": "doc", "content": [nodo]},
            "expected_version": 1,
        },
    )

    assert respuesta.status_code == 422


def test_documento_vacio_se_puede_guardar_pero_no_finalizar(
    client, db, convenio_listo
) -> None:
    vacio = {"type": "doc", "content": [{"type": "paragraph"}]}
    guardada = client.patch(
        f"/api/convenios/{convenio_listo.id}/elaboracion",
        json={"contenido": vacio, "expected_version": 1},
    )
    assert guardada.status_code == 200
    finalizada = client.post(
        f"/api/convenios/{convenio_listo.id}/elaboracion/finalizar",
        json={"expected_version": 2},
    )
    assert finalizada.status_code == 422
    assert {item["campo"] for item in finalizada.json()["detail"]["faltantes"]} == {
        "contenido"
    }
    assert (
        db.scalar(
            select(func.count())
            .select_from(RevisionConvenio)
            .where(RevisionConvenio.convenio_id == convenio_listo.id)
        )
        == 0
    )


def test_finalizar_guarda_cambios_y_vincula_una_sola_revision_a_version_exacta(
    client, db, convenio_listo
) -> None:
    contenido = deepcopy(_elaboracion(client, convenio_listo.id)["contenido"])
    contenido["content"].append(
        {
            "type": "paragraph",
            "content": [{"type": "text", "text": "Versión preparada"}],
        }
    )
    respuesta = client.post(
        f"/api/convenios/{convenio_listo.id}/elaboracion/finalizar",
        json={"contenido": contenido, "expected_version": 1},
    )
    assert respuesta.status_code == 200
    assert respuesta.json()["version_actual"] == 2

    revisiones = list(
        db.scalars(
            select(RevisionConvenio).where(
                RevisionConvenio.convenio_id == convenio_listo.id
            )
        )
    )
    assert len(revisiones) == 1
    assert revisiones[0].version_convenio_id is not None
    version = db.get(VersionConvenio, revisiones[0].version_convenio_id)
    assert version.numero == 2
    assert version.contexto == ContextoVersionConvenio.FINALIZACION
    assert "Versión preparada" in _texto(version.contenido)
    assert "contenido" not in revisiones[0].snapshot_datos
