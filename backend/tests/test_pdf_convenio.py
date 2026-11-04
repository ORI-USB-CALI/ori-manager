import pytest
from sqlalchemy import select

from backend.models.tipo_convenio import TipoConvenio
from backend.models.version_convenio import VersionConvenio
from backend.services.convenios import ConvenioNoEncontrado
from backend.services.pdf_convenio import ServicioPdfConvenio


def test_generar_pdf_exitoso_ca_01(db, convenio_listo):
    """CA-01: Generar documento PDF del convenio con información estructurada."""
    servicio = ServicioPdfConvenio()
    pdf_bytes = servicio.generar_pdf(convenio_listo.id, db)

    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 500
    assert pdf_bytes.startswith(b"%PDF-")


def test_generar_pdf_convenio_inexistente_lanza_error(db):
    """Verifica que solicitar un ID inexistente genera ConvenioNoEncontrado."""
    servicio = ServicioPdfConvenio()
    with pytest.raises(ConvenioNoEncontrado):
        servicio.generar_pdf(999999, db)


def test_aislamiento_de_datos_concurrente_ca_02(db, gestor, crear_convenio):
    """CA-02: Garantiza que dos convenios distintos no mezclan su información en el PDF ni en el DTO."""
    tipo = db.scalar(select(TipoConvenio).where(TipoConvenio.codigo == "MARCO"))
    assert tipo is not None

    conv_a = crear_convenio(
        gestor,
        tipo_convenio_id=tipo.id,
        objeto="Convenio Alfa para investigación en IA",
        implicacion_financiera="Financiamiento conjunto 100M",
    )
    conv_b = crear_convenio(
        gestor,
        tipo_convenio_id=tipo.id,
        objeto="Convenio Beta para movilidad estudiantil",
        implicacion_financiera="Sin costos asociados",
    )

    servicio = ServicioPdfConvenio()
    dto_a = servicio.mapear_convenio_a_dto(conv_a.id, db)
    dto_b = servicio.mapear_convenio_a_dto(conv_b.id, db)

    # Validar aislamiento de DTOs
    assert dto_a.convenio_id == conv_a.id
    assert dto_b.convenio_id == conv_b.id
    assert dto_a.objeto == "Convenio Alfa para investigación en IA"
    assert dto_b.objeto == "Convenio Beta para movilidad estudiantil"
    assert dto_a.implicacion_financiera == "Financiamiento conjunto 100M"
    assert dto_b.implicacion_financiera == "Sin costos asociados"

    # Validar generación binaria aislada
    pdf_a = servicio.renderizar_dto_a_pdf(dto_a)
    pdf_b = servicio.renderizar_dto_a_pdf(dto_b)

    assert pdf_a.startswith(b"%PDF-")
    assert pdf_b.startswith(b"%PDF-")
    assert pdf_a != pdf_b


def test_generar_pdf_con_contenido_tiptap_estructurado(db, convenio_listo, gestor):
    """Verifica que el contenido ProseMirror/TipTap se parsea y formatea en cláusulas."""
    etapa = convenio_listo.etapa_actual
    contenido_estructurado = {
        "type": "doc",
        "content": [
            {
                "type": "heading",
                "attrs": {"level": 1},
                "content": [
                    {"type": "text", "text": "CLÁUSULA PRIMERA — OBJETO DEL ACUERDO"}
                ],
            },
            {
                "type": "paragraph",
                "content": [
                    {"type": "text", "text": "El presente convenio busca "},
                    {
                        "type": "text",
                        "marks": [{"type": "bold"}],
                        "text": "fomentar la innovación",
                    },
                    {"type": "text", "text": " tecnológica."},
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
                                "content": [
                                    {"type": "text", "text": "Intercambio de docentes"}
                                ],
                            }
                        ],
                    },
                    {
                        "type": "listItem",
                        "content": [
                            {
                                "type": "paragraph",
                                "content": [
                                    {"type": "text", "text": "Publicaciones conjuntas"}
                                ],
                            }
                        ],
                    },
                ],
            },
        ],
    }

    version_existente = db.scalar(
        select(VersionConvenio).where(
            VersionConvenio.convenio_id == convenio_listo.id,
            VersionConvenio.numero == convenio_listo.version_actual,
        )
    )
    if version_existente is not None:
        version_existente.contenido = contenido_estructurado
    else:
        version_existente = VersionConvenio(
            convenio_id=convenio_listo.id,
            numero=convenio_listo.version_actual,
            contenido=contenido_estructurado,
            snapshot_metadata={},
            autor_id=gestor.id,
            etapa_id=etapa.id,
            contexto="GUARDADO",
        )
        db.add(version_existente)
    db.commit()

    servicio = ServicioPdfConvenio()
    dto = servicio.mapear_convenio_a_dto(convenio_listo.id, db)

    assert len(dto.secciones_contenido) >= 3
    assert dto.secciones_contenido[0].tipo == "heading"
    assert "CLÁUSULA PRIMERA" in dto.secciones_contenido[0].texto

    pdf_bytes = servicio.renderizar_dto_a_pdf(dto)
    assert pdf_bytes.startswith(b"%PDF-")
