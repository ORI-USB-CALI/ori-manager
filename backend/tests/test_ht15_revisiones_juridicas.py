"""HT-15, Tarea 5: integridad de RJ1/RJ2 (CA-05) en los tres orígenes.

Las reglas ya existen en `aprobar` y `enviar_a_contraparte`; lo que faltaba
era probarlas con convenios manuales y renovados, no solo con los que vienen
de una solicitud (ver guía de la HT).
"""

from copy import deepcopy
from datetime import date

import pytest
from sqlalchemy import select

from backend.core.roles import CodigoRol, TipoUsuario
from backend.models.borrador_convenio import BorradorConvenio
from backend.models.convenio import Convenio
from backend.models.enums import EstadoConvenio
from backend.models.observacion_revision import ObservacionRevision
from backend.models.revision_convenio import RevisionConvenio
from backend.models.tipo_convenio import TipoConvenio
from backend.models.version_convenio import VersionConvenio
from backend.schemas.convenio import ConvenioCrearManual, RevisionContenidoGuardar
from backend.services import renovaciones
from backend.services.convenios import RevisionNoDisponible, ServicioConvenios
from backend.services.renovaciones import ServicioRenovaciones

DOCUMENTO_ELABORADO = {
    "type": "doc",
    "content": [
        {"type": "paragraph", "content": [{"type": "text", "text": "Cláusula original"}]},
    ],
}

ORIGENES = ["manual", "solicitud", "renovacion"]


def _contenido_editado(contenido: dict, texto: str) -> dict:
    nuevo = deepcopy(contenido)
    nuevo["content"].append(
        {"type": "paragraph", "content": [{"type": "text", "text": texto}]}
    )
    return nuevo


def _borrador(db, convenio_id: int) -> BorradorConvenio:
    return db.scalar(
        select(BorradorConvenio).where(BorradorConvenio.convenio_id == convenio_id)
    )


def _pendiente(db, convenio_id: int) -> RevisionConvenio | None:
    return db.scalar(
        select(RevisionConvenio).where(
            RevisionConvenio.convenio_id == convenio_id,
            RevisionConvenio.estado == "PENDIENTE",
        )
    )


@pytest.fixture
def tipo_marco(db):
    return db.scalar(select(TipoConvenio).where(TipoConvenio.codigo == "MARCO"))


@pytest.fixture
def convenio_por_origen(
    db, gestor, convenio_listo, formalizar_version, tipo_marco, monkeypatch
):
    """Entrega un convenio listo para enviarse a revisión jurídica, según el
    origen pedido. Los tres quedan con la misma metadata completa de
    `convenio_listo` (tipo, implicación financiera, duración, vigencia) para
    que `finalizar_elaboracion` no falle por datos faltantes."""

    def _crear(origen: str) -> Convenio:
        if origen == "solicitud":
            return convenio_listo
        if origen == "manual":
            convenio = ServicioConvenios(db).crear_manual(
                ConvenioCrearManual(
                    objeto="Cooperación académica",
                    alcance="INSTITUCIONAL",
                    implicacion_financiera="Sin costo para la Universidad",
                    duracion_meses=24,
                    tipo_convenio_id=tipo_marco.id,
                ),
                gestor,
            )
            _borrador(db, convenio.id).contenido = deepcopy(DOCUMENTO_ELABORADO)
            db.commit()
            return convenio
        if origen == "renovacion":
            monkeypatch.setattr(
                renovaciones, "fecha_actual_dominio", lambda: date(2026, 1, 1)
            )
            _borrador(db, convenio_listo.id).contenido = deepcopy(DOCUMENTO_ELABORADO)
            db.commit()
            formalizar_version(convenio_listo, gestor)
            convenio_listo.estado = EstadoConvenio.FINALIZADO.value
            convenio_listo.fecha_vencimiento = date(2025, 12, 31)
            db.commit()
            return ServicioRenovaciones(db).iniciar_renovacion(
                convenio_listo.id, gestor
            )
        raise ValueError(f"Origen no soportado: {origen}")

    return _crear


# ---- RN-11: reutilizar la versión abre una ronda nueva, sin heredar avales -----


@pytest.mark.parametrize("origen", ORIGENES)
def test_reutilizar_version_abre_ronda_nueva_sin_heredar_avales(
    db, gestor, revisor, crear_usuario, convenio_por_origen, origen
) -> None:
    convenio = convenio_por_origen(origen)
    servicio = ServicioConvenios(db)
    servicio.finalizar_elaboracion(convenio.id, gestor)
    primera_ronda = _pendiente(db, convenio.id)
    servicio.registrar_observacion_revision(
        convenio.id,
        primera_ronda.id,
        "Observación no obligatoria",
        revisor,
        requiere_correccion=False,
    )
    servicio.devolver(
        convenio.id, primera_ronda.id, [], convenio.version_actual, revisor
    )
    for observacion in db.scalars(
        select(ObservacionRevision).where(
            ObservacionRevision.revision_convenio_id == primera_ronda.id
        )
    ).all():
        servicio.atender_observacion(
            convenio.id, observacion.id, "Revisado sin cambios", gestor
        )

    # Reenvío sin cambios: reutiliza la versión (RN-07) y abre una ronda nueva.
    servicio.finalizar_elaboracion(convenio.id, gestor)

    nueva_rj1 = _pendiente(db, convenio.id)
    assert nueva_rj1.id != primera_ronda.id
    assert nueva_rj1.numero_ronda == primera_ronda.numero_ronda + 1
    assert nueva_rj1.instancia_juridica == 1
    assert nueva_rj1.version_convenio_id == primera_ronda.version_convenio_id

    # El aval de la ronda anterior no sirve para esta: RJ1 y RJ2 se exigen de nuevo.
    servicio.aprobar(convenio.id, nueva_rj1.id, convenio.version_actual, revisor)
    nueva_rj2 = _pendiente(db, convenio.id)
    assert nueva_rj2.instancia_juridica == 2
    assert nueva_rj2.numero_ronda == nueva_rj1.numero_ronda
    with pytest.raises(RevisionNoDisponible):
        servicio.aprobar(convenio.id, nueva_rj2.id, convenio.version_actual, revisor)
    otro = crear_usuario(CodigoRol.REVISOR_ORI, TipoUsuario.INTERNO)
    servicio.aprobar(convenio.id, nueva_rj2.id, convenio.version_actual, otro)

    db.expire_all()
    assert db.get(Convenio, convenio.id).etapa_actual.codigo == "REVISION_CONTRAPARTE"


# ---- CA-05, segundo escenario: un aval no sirve para una versión distinta -------


@pytest.mark.parametrize("origen", ORIGENES)
def test_aval_de_rj1_no_sirve_para_una_version_distinta(
    db, gestor, revisor, crear_usuario, convenio_por_origen, origen
) -> None:
    convenio = convenio_por_origen(origen)
    servicio = ServicioConvenios(db)
    servicio.finalizar_elaboracion(convenio.id, gestor)
    rj1 = _pendiente(db, convenio.id)
    version_avalada_por_rj1 = convenio.version_actual

    servicio.aprobar(convenio.id, rj1.id, convenio.version_actual, revisor)
    rj2 = _pendiente(db, convenio.id)
    assert rj2.version_convenio_id == rj1.version_resultado_id

    # Se edita el contenido durante RJ2: crea una versión nueva distinta a la
    # que avaló RJ1.
    otro_revisor = crear_usuario(CodigoRol.REVISOR_ORI, TipoUsuario.INTERNO)
    contenido_avalado = db.get(VersionConvenio, rj1.version_resultado_id)
    version_nueva = servicio.guardar_contenido_revision(
        convenio.id,
        rj2.id,
        RevisionContenidoGuardar(
            contenido=_contenido_editado(contenido_avalado.contenido, "Cambio en RJ2"),
            expected_version=convenio.version_actual,
        ),
        otro_revisor,
    )
    db.refresh(convenio)
    assert convenio.version_actual == version_nueva.numero
    assert convenio.version_actual != version_avalada_por_rj1

    with pytest.raises(RevisionNoDisponible, match="requiere reiniciar"):
        servicio.aprobar(convenio.id, rj2.id, convenio.version_actual, otro_revisor)

    db.expire_all()
    rj2_actual = db.get(RevisionConvenio, rj2.id)
    assert rj2_actual.estado == "PENDIENTE"
    assert rj2_actual.resultado is None
    assert rj2_actual.version_resultado_id is None
