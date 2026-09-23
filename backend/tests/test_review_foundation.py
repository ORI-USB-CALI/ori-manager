from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import func, select

from backend.models.convenio import Convenio
from backend.models.documento import Documento
from backend.models.enums import (
    EstadoRevisionConvenio,
    ResultadoRevisionConvenio,
    TipoRevisionConvenio,
)
from backend.models.etapa import Etapa
from backend.models.historial_etapa import HistorialEtapa
from backend.models.observacion_revision import ObservacionRevision
from backend.models.revision_convenio import RevisionConvenio
from backend.models.solicitud_convenio import SolicitudConvenio


def _crear_contexto(db, usuario):
    solicitud = SolicitudConvenio(
        consecutivo=f"SOL-{uuid4().hex}",
        tipo_solicitante="INTERNO",
        solicitante_id=usuario.id,
        estado="APROBADA",
    )
    db.add(solicitud)
    db.flush()
    etapa = db.scalar(select(Etapa).where(Etapa.codigo == "ELABORACION"))
    assert etapa is not None
    convenio = Convenio(
        solicitud_id=solicitud.id,
        creado_por_id=usuario.id,
        etapa_actual_id=etapa.id,
        estado="EN_TRAMITE",
    )
    db.add(convenio)
    db.flush()
    historial = HistorialEtapa(
        convenio_id=convenio.id,
        etapa_origen_id=None,
        etapa_destino_id=etapa.id,
        usuario_id=usuario.id,
        responsable_id=usuario.id,
    )
    db.add(historial)
    db.flush()
    return convenio, historial


def _crear_documento(convenio: Convenio, *, version: int) -> Documento:
    return Documento(
        convenio_id=convenio.id,
        tipo="BORRADOR",
        nombre_archivo=f"borrador-v{version}.pdf",
        ruta_almacenamiento=f"revisiones/{uuid4().hex}.pdf",
        tipo_mime="application/pdf",
        tamano_bytes=100,
        version=version,
    )


@pytest.mark.parametrize("tipo", list(TipoRevisionConvenio))
def test_revision_convenio_admite_tipos_y_default_pendiente(
    db, crear_usuario, tipo
):
    usuario = crear_usuario()
    convenio, _ = _crear_contexto(db, usuario)
    revision = RevisionConvenio(convenio_id=convenio.id, tipo=tipo.value)

    db.add(revision)
    db.flush()

    assert revision.tipo == tipo.value
    assert revision.estado == EstadoRevisionConvenio.PENDIENTE.value
    assert revision.resultado is None
    assert revision.documento_id is None
    assert revision.historial_etapa_id is None
    assert revision.responsable_id is None
    assert revision.resuelta_por_id is None
    assert revision.resuelta_en is None


@pytest.mark.parametrize("resultado", list(ResultadoRevisionConvenio))
def test_revision_convenio_admite_resultados_y_actores_de_resolucion(
    db, crear_usuario, resultado
):
    creador = crear_usuario()
    responsable = crear_usuario()
    resolutor = crear_usuario()
    convenio, _ = _crear_contexto(db, creador)
    fecha_resolucion = datetime.now(UTC)
    revision = RevisionConvenio(
        convenio_id=convenio.id,
        tipo=TipoRevisionConvenio.JURIDICA.value,
        responsable_id=responsable.id,
        estado=EstadoRevisionConvenio.RESUELTA.value,
        resultado=resultado.value,
        resuelta_por_id=resolutor.id,
        resuelta_en=fecha_resolucion,
    )

    db.add(revision)
    db.flush()

    assert revision.responsable is responsable
    assert revision.resultado == resultado.value
    assert revision.resuelta_por is resolutor
    assert revision.resuelta_en == fecha_resolucion


def test_revision_convenio_admite_documento_e_historial_opcionales(
    db, crear_usuario
):
    usuario = crear_usuario()
    convenio, historial = _crear_contexto(db, usuario)
    documento = _crear_documento(convenio, version=1)
    db.add(documento)
    db.flush()
    sin_vinculos = RevisionConvenio(
        convenio_id=convenio.id,
        tipo=TipoRevisionConvenio.FINAL.value,
    )
    con_vinculos = RevisionConvenio(
        convenio_id=convenio.id,
        tipo=TipoRevisionConvenio.FINAL.value,
        historial_etapa_id=historial.id,
        documento_id=documento.id,
    )

    db.add_all([sin_vinculos, con_vinculos])
    db.flush()

    assert sin_vinculos.historial_etapa is None
    assert sin_vinculos.documento is None
    assert con_vinculos.historial_etapa is historial
    assert con_vinculos.documento is documento
    assert con_vinculos in convenio.revisiones
    assert con_vinculos in documento.revisiones


def test_varias_rondas_no_requieren_ciclo_ni_nuevo_historial(
    db, crear_usuario
):
    usuario = crear_usuario()
    convenio, _ = _crear_contexto(db, usuario)
    documento_v1 = _crear_documento(convenio, version=1)
    documento_v2 = _crear_documento(convenio, version=2)
    db.add_all([documento_v1, documento_v2])
    db.flush()
    revisiones = [
        RevisionConvenio(
            convenio_id=convenio.id,
            tipo=TipoRevisionConvenio.JURIDICA.value,
            documento_id=documento_v1.id,
        ),
        RevisionConvenio(
            convenio_id=convenio.id,
            tipo=TipoRevisionConvenio.JURIDICA.value,
            documento_id=documento_v1.id,
        ),
        RevisionConvenio(
            convenio_id=convenio.id,
            tipo=TipoRevisionConvenio.JURIDICA.value,
            documento_id=documento_v2.id,
        ),
    ]

    db.add_all(revisiones)
    db.flush()

    assert len({revision.id for revision in revisiones}) == 3
    assert all(revision.historial_etapa_id is None for revision in revisiones)
    assert revisiones[0].documento is revisiones[1].documento
    assert revisiones[2].documento is documento_v2
    assert db.scalar(
        select(func.count())
        .select_from(HistorialEtapa)
        .where(HistorialEtapa.convenio_id == convenio.id)
    ) == 1
    assert "numero_ciclo" not in HistorialEtapa.__table__.columns


def test_observaciones_conservan_historial_y_pueden_agruparse_por_revision(
    db, crear_usuario
):
    usuario = crear_usuario()
    convenio, historial = _crear_contexto(db, usuario)
    revision_a = RevisionConvenio(
        convenio_id=convenio.id,
        tipo=TipoRevisionConvenio.CONTRAPARTE.value,
    )
    revision_b = RevisionConvenio(
        convenio_id=convenio.id,
        tipo=TipoRevisionConvenio.CONTRAPARTE.value,
    )
    db.add_all([revision_a, revision_b])
    db.flush()
    observaciones = [
        ObservacionRevision(
            convenio_id=convenio.id,
            historial_etapa_id=historial.id,
            revision_convenio_id=revision_a.id,
            origen="CONTRAPARTE",
            registrada_por_id=usuario.id,
            descripcion="Primera observación de la ronda A",
        ),
        ObservacionRevision(
            convenio_id=convenio.id,
            historial_etapa_id=historial.id,
            revision_convenio_id=revision_a.id,
            origen="CONTRAPARTE",
            registrada_por_id=usuario.id,
            descripcion="Segunda observación de la ronda A",
        ),
        ObservacionRevision(
            convenio_id=convenio.id,
            historial_etapa_id=historial.id,
            revision_convenio_id=revision_b.id,
            origen="CONTRAPARTE",
            registrada_por_id=usuario.id,
            descripcion="Observación de la ronda B",
        ),
        ObservacionRevision(
            convenio_id=convenio.id,
            historial_etapa_id=historial.id,
            revision_convenio_id=None,
            origen="REVISOR_ORI",
            registrada_por_id=usuario.id,
            descripcion="Observación histórica sin revisión asociada",
        ),
    ]

    db.add_all(observaciones)
    db.flush()

    assert len(revision_a.observaciones) == 2
    assert revision_b.observaciones == [observaciones[2]]
    assert observaciones[3].revision_convenio is None
    assert all(item.historial_etapa is historial for item in observaciones)


def test_politicas_on_delete_de_la_foundation():
    columnas_revision = RevisionConvenio.__table__.columns
    esperadas = {
        "convenio_id": "CASCADE",
        "historial_etapa_id": "RESTRICT",
        "documento_id": "RESTRICT",
        "responsable_id": "RESTRICT",
        "resuelta_por_id": "RESTRICT",
    }

    for columna, politica in esperadas.items():
        fk = next(iter(columnas_revision[columna].foreign_keys))
        assert fk.ondelete == politica

    fk_observacion = next(
        iter(ObservacionRevision.__table__.c.revision_convenio_id.foreign_keys)
    )
    assert fk_observacion.ondelete == "RESTRICT"
