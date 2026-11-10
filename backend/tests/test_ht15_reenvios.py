from copy import deepcopy

import pytest
from sqlalchemy import func, select

from backend.core.roles import CodigoRol, TipoUsuario
from backend.models.auditoria import Auditoria
from backend.models.convenio import Convenio
from backend.models.enums import TipoRevisionConvenio
from backend.models.observacion_revision import ObservacionRevision
from backend.models.revision_convenio import RevisionConvenio
from backend.models.version_convenio import VersionConvenio
from backend.services.convenios import RevisionNoDisponible, ServicioConvenios

MENSAJE_OBLIGATORIAS = "Deben atenderse las observaciones obligatorias"


def _ruta(convenio_id: int) -> str:
    return f"/api/convenios/{convenio_id}/elaboracion"


def _con_parrafo(contenido: dict, texto: str) -> dict:
    nuevo = deepcopy(contenido)
    nuevo["content"].append(
        {"type": "paragraph", "content": [{"type": "text", "text": texto}]}
    )
    return nuevo


def _versiones(db, convenio_id: int) -> list[int]:
    db.expire_all()
    return list(
        db.scalars(
            select(VersionConvenio.numero)
            .where(VersionConvenio.convenio_id == convenio_id)
            .order_by(VersionConvenio.numero)
        )
    )


def _pendiente(db, convenio_id: int) -> RevisionConvenio | None:
    return db.scalar(
        select(RevisionConvenio).where(
            RevisionConvenio.convenio_id == convenio_id,
            RevisionConvenio.estado == "PENDIENTE",
        )
    )


def _juridicas(db, convenio_id: int) -> int:
    return db.scalar(
        select(func.count())
        .select_from(RevisionConvenio)
        .where(
            RevisionConvenio.convenio_id == convenio_id,
            RevisionConvenio.tipo == TipoRevisionConvenio.JURIDICA.value,
        )
    )


@pytest.fixture
def devolver_con(db, gestor, revisor, convenio_listo):
    """Envía el convenio (V1), lo devuelve con observaciones marcadas por el
    Revisor ORI y el Gestor las atiende sin cambiar el documento."""

    def _devolver(*obligan: bool) -> RevisionConvenio:
        servicio = ServicioConvenios(db)
        servicio.finalizar_elaboracion(convenio_listo.id, gestor)
        revision = _pendiente(db, convenio_listo.id)
        for indice, obliga in enumerate(obligan, start=1):
            servicio.registrar_observacion_revision(
                convenio_listo.id,
                revision.id,
                f"Observación {indice}",
                revisor,
                requiere_correccion=obliga,
            )
        servicio.devolver(
            convenio_listo.id, revision.id, [], convenio_listo.version_actual, revisor
        )
        for observacion in db.scalars(
            select(ObservacionRevision).where(
                ObservacionRevision.revision_convenio_id == revision.id
            )
        ).all():
            servicio.atender_observacion(
                convenio_listo.id, observacion.id, "Revisado sin cambios", gestor
            )
        return revision

    return _devolver


# ---- RN-07: sin observaciones obligatorias se reutiliza la versión --------------


def test_reenvio_sin_cambios_reutiliza_la_version_si_ninguna_observacion_obliga(
    client, db, gestor, convenio_listo, devolver_con
) -> None:
    anterior = devolver_con(False, False)
    rondas = _juridicas(db, convenio_listo.id)

    respuesta = client.post(f"{_ruta(convenio_listo.id)}/finalizar")

    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json()["version_actual"] == 1
    assert _versiones(db, convenio_listo.id) == [1]
    nueva = _pendiente(db, convenio_listo.id)
    assert nueva.id != anterior.id
    assert nueva.numero_ronda == anterior.numero_ronda + 1
    assert nueva.instancia_juridica == 1
    assert nueva.version_convenio_id == anterior.version_convenio_id
    assert _juridicas(db, convenio_listo.id) == rondas + 1
    evento = db.scalar(
        select(Auditoria.evento)
        .where(Auditoria.entidad == "revision_convenio", Auditoria.registro_id == nueva.id)
        .limit(1)
    )
    assert evento == "VERSION_REUTILIZADA"


# ---- RN-08: una observación obligatoria exige corregir -------------------------


@pytest.mark.parametrize("obligan", [(True,), (False, True)], ids=["una", "mixtas"])
def test_reenvio_sin_cambios_se_bloquea_si_alguna_observacion_obliga(
    client, db, convenio_listo, devolver_con, obligan
) -> None:
    devolver_con(*obligan)
    rondas = _juridicas(db, convenio_listo.id)

    respuesta = client.post(f"{_ruta(convenio_listo.id)}/finalizar")

    assert respuesta.status_code == 409
    assert MENSAJE_OBLIGATORIAS in respuesta.json()["detail"]
    db.expire_all()
    assert db.get(Convenio, convenio_listo.id).etapa_actual.codigo == "ELABORACION"
    assert _versiones(db, convenio_listo.id) == [1]
    assert _juridicas(db, convenio_listo.id) == rondas
    assert _pendiente(db, convenio_listo.id) is None


def test_con_observacion_obligatoria_corregir_el_documento_genera_version_nueva(
    client, db, convenio_listo, devolver_con
) -> None:
    devolver_con(True)
    elaboracion = client.get(_ruta(convenio_listo.id)).json()
    corregido = _con_parrafo(elaboracion["contenido"], "Corrección exigida")
    assert client.patch(
        _ruta(convenio_listo.id),
        json={"contenido": corregido, "expected_revision": 0},
    ).status_code == 200

    respuesta = client.post(f"{_ruta(convenio_listo.id)}/finalizar")

    assert respuesta.status_code == 200, respuesta.text
    assert _versiones(db, convenio_listo.id) == [1, 2]
    assert _pendiente(db, convenio_listo.id).version_convenio.numero == 2


def test_un_cambio_en_los_datos_tambien_cumple_la_correccion_obligatoria(
    client, db, convenio_listo, devolver_con
) -> None:
    devolver_con(True)
    elaboracion = client.get(_ruta(convenio_listo.id)).json()
    assert client.patch(
        _ruta(convenio_listo.id),
        json={
            "contenido": elaboracion["contenido"],
            "expected_revision": 0,
            "implicacion_financiera": "Aporte en especie corregido",
        },
    ).status_code == 200

    assert client.post(f"{_ruta(convenio_listo.id)}/finalizar").status_code == 200
    assert _versiones(db, convenio_listo.id) == [1, 2]


def test_las_observaciones_pendientes_impiden_reenviar_aunque_no_obliguen(
    client, db, gestor, revisor, convenio_listo
) -> None:
    servicio = ServicioConvenios(db)
    servicio.finalizar_elaboracion(convenio_listo.id, gestor)
    revision = _pendiente(db, convenio_listo.id)
    servicio.registrar_observacion_revision(
        convenio_listo.id, revision.id, "Solo informativa", revisor,
        requiere_correccion=False,
    )
    servicio.devolver(convenio_listo.id, revision.id, [], 1, revisor)

    respuesta = client.post(f"{_ruta(convenio_listo.id)}/finalizar")

    assert respuesta.status_code == 409
    assert "observaciones pendientes" in respuesta.json()["detail"]
    assert _versiones(db, convenio_listo.id) == [1]


# ---- RN-09: obligatorias por defecto -------------------------------------------


def test_las_observaciones_escritas_al_devolver_cuentan_como_obligatorias(
    client, db, gestor, revisor, convenio_listo
) -> None:
    servicio = ServicioConvenios(db)
    servicio.finalizar_elaboracion(convenio_listo.id, gestor)
    revision = _pendiente(db, convenio_listo.id)
    servicio.devolver(convenio_listo.id, revision.id, ["Precisar el objeto"], 1, revisor)
    (observacion,) = db.scalars(
        select(ObservacionRevision).where(
            ObservacionRevision.revision_convenio_id == revision.id
        )
    ).all()
    assert observacion.requiere_correccion is True
    servicio.atender_observacion(convenio_listo.id, observacion.id, "Revisado", gestor)

    respuesta = client.post(f"{_ruta(convenio_listo.id)}/finalizar")

    assert respuesta.status_code == 409
    assert MENSAJE_OBLIGATORIAS in respuesta.json()["detail"]


@pytest.mark.parametrize(
    "tipo", [TipoRevisionConvenio.CONTRAPARTE, TipoRevisionConvenio.FINAL]
)
def test_las_devoluciones_de_contraparte_y_revision_final_exigen_version_nueva(
    db, tipo
) -> None:
    devuelta = RevisionConvenio(tipo=tipo.value)

    assert ServicioConvenios(db)._exige_correccion(devuelta) is True


def test_el_revisor_marca_por_api_si_la_observacion_obliga_a_corregir(
    client, db, gestor, revisor, convenio_listo, entrar_como
) -> None:
    ServicioConvenios(db).finalizar_elaboracion(convenio_listo.id, gestor)
    revision = _pendiente(db, convenio_listo.id)
    ruta = f"/api/convenios/{convenio_listo.id}/revisiones/{revision.id}/observaciones"
    entrar_como(revisor)

    informativa = client.post(
        ruta, json={"descripcion": "Sugerencia de redacción", "requiere_correccion": False}
    )
    por_defecto = client.post(ruta, json={"descripcion": "Falta la cláusula de vigencia"})

    assert informativa.status_code == 201, informativa.text
    assert informativa.json()["requiere_correccion"] is False
    assert por_defecto.status_code == 201, por_defecto.text
    assert por_defecto.json()["requiere_correccion"] is True
    historial = client.get(f"/api/convenios/{convenio_listo.id}/revisiones").json()
    marcas = {
        item["descripcion"]: item["requiere_correccion"]
        for revision in historial["revisiones"]
        for item in revision["observaciones"]
    }
    assert marcas == {
        "Sugerencia de redacción": False,
        "Falta la cláusula de vigencia": True,
    }


# ---- RN-11: la versión reutilizada repite RJ1 y RJ2 -----------------------------


def test_la_version_reutilizada_vuelve_a_exigir_rj1_y_rj2_en_la_ronda_nueva(
    client, db, gestor, revisor, crear_usuario, convenio_listo, devolver_con
) -> None:
    devolver_con(False)
    assert client.post(f"{_ruta(convenio_listo.id)}/finalizar").status_code == 200
    servicio = ServicioConvenios(db)
    rj1 = _pendiente(db, convenio_listo.id)
    assert rj1.instancia_juridica == 1

    servicio.aprobar(convenio_listo.id, rj1.id, 1, revisor)

    rj2 = _pendiente(db, convenio_listo.id)
    assert (rj2.instancia_juridica, rj2.numero_ronda) == (2, rj1.numero_ronda)
    assert rj2.version_convenio_id == rj1.version_convenio_id
    with pytest.raises(RevisionNoDisponible):
        servicio.aprobar(convenio_listo.id, rj2.id, 1, revisor)
    otro = crear_usuario(CodigoRol.REVISOR_ORI, TipoUsuario.INTERNO)
    servicio.aprobar(convenio_listo.id, rj2.id, 1, otro)
    db.expire_all()
    assert db.get(Convenio, convenio_listo.id).etapa_actual.codigo == (
        "REVISION_CONTRAPARTE"
    )
