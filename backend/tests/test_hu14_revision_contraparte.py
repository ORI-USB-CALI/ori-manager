"""HU-14: envío y resolución de la revisión de contraparte."""

from copy import deepcopy
from types import SimpleNamespace

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from backend.core.roles import CodigoRol, TipoUsuario
from backend.models.auditoria import Auditoria
from backend.models.enums import ContextoVersionConvenio
from backend.models.etapa import Etapa
from backend.models.historial_etapa import HistorialEtapa
from backend.models.observacion_revision import ObservacionRevision
from backend.models.revision_convenio import RevisionConvenio
from backend.models.solicitud_convenio import SolicitudConvenio
from backend.models.version_convenio import VersionConvenio
from backend.services.convenios import RevisionNoDisponible, ServicioConvenios


def _habilitar_contraparte(
    db, convenio, gestor, solicitante, revisor, crear_usuario
) -> VersionConvenio:
    solicitud = db.get(SolicitudConvenio, convenio.solicitud_id)
    solicitud.solicitante_id = solicitante.id
    db.commit()
    ServicioConvenios(db).finalizar_elaboracion(convenio.id, gestor)
    primera = db.scalar(
        select(RevisionConvenio).where(
            RevisionConvenio.convenio_id == convenio.id,
            RevisionConvenio.estado == "PENDIENTE",
        )
    )
    ServicioConvenios(db).aprobar(
        convenio.id, primera.id, convenio.version_actual, revisor
    )
    segunda = db.scalar(
        select(RevisionConvenio).where(
            RevisionConvenio.convenio_id == convenio.id,
            RevisionConvenio.estado == "PENDIENTE",
        )
    )
    otro_revisor = crear_usuario(CodigoRol.REVISOR_ORI, TipoUsuario.INTERNO)
    ServicioConvenios(db).aprobar(
        convenio.id, segunda.id, convenio.version_actual, otro_revisor
    )
    db.refresh(convenio)
    return db.scalar(
        select(VersionConvenio).where(
            VersionConvenio.convenio_id == convenio.id,
            VersionConvenio.numero == convenio.version_actual,
        )
    )


def _enviar(client, convenio, gestor, entrar_como):
    entrar_como(gestor)
    return client.post(
        f"/api/convenios/{convenio.id}/revision-contraparte/enviar",
        json={"expected_version": convenio.version_actual},
    )


def _contenido_corregido(contenido: dict) -> dict:
    nuevo = deepcopy(contenido)
    nuevo["content"].append(
        {
            "type": "paragraph",
            "content": [{"type": "text", "text": "Corrección de contraparte"}],
        }
    )
    return nuevo


def test_ca01_envio_bandeja_y_consulta_conservan_actor_y_version_exacta(
    client,
    db,
    gestor,
    solicitante,
    revisor,
    crear_usuario,
    convenio_listo,
    entrar_como,
) -> None:
    version = _habilitar_contraparte(
        db, convenio_listo, gestor, solicitante, revisor, crear_usuario
    )
    respuesta = _enviar(client, convenio_listo, gestor, entrar_como)

    assert respuesta.status_code == 201
    revision = respuesta.json()
    assert revision["tipo"] == "CONTRAPARTE"
    assert revision["estado"] == "PENDIENTE"
    assert revision["creada_por"]["id"] == gestor.id
    assert revision["responsable"]["id"] == solicitante.id
    assert revision["version_convenio_id"] == version.id
    assert revision["version_resultado_id"] is None
    assert db.scalar(
        select(func.count())
        .select_from(RevisionConvenio)
        .where(
            RevisionConvenio.convenio_id == convenio_listo.id,
            RevisionConvenio.tipo == "CONTRAPARTE",
            RevisionConvenio.estado == "PENDIENTE",
        )
    ) == 1

    ajeno = crear_usuario(CodigoRol.SOLICITANTE_INTERNO, TipoUsuario.INTERNO)
    entrar_como(ajeno)
    assert client.get(
        "/api/convenios/revisiones-contraparte/pendientes"
    ).json() == []
    assert client.get(
        f"/api/convenios/{convenio_listo.id}/revisiones/"
        f"{revision['id']}/contraparte"
    ).status_code == 403

    entrar_como(solicitante)
    bandeja = client.get("/api/convenios/revisiones-contraparte/pendientes")
    assert bandeja.status_code == 200
    assert [item["revision_id"] for item in bandeja.json()] == [revision["id"]]
    assert bandeja.json()[0]["enviada_por"]["id"] == gestor.id
    detalle = client.get(
        f"/api/convenios/{convenio_listo.id}/revisiones/"
        f"{revision['id']}/contraparte"
    )
    assert detalle.status_code == 200
    assert detalle.json()["version_recibida"]["id"] == version.id
    assert detalle.json()["version_recibida"]["contenido"] == version.contenido


def test_ca02_rechaza_sin_doble_aval_version_incorrecta_y_envio_duplicado(
    client,
    db,
    gestor,
    solicitante,
    revisor,
    crear_usuario,
    convenio_listo,
    crear_convenio,
    entrar_como,
) -> None:
    sin_aval = crear_convenio(gestor)
    etapa_contraparte = db.scalar(
        select(Etapa).where(Etapa.codigo == "REVISION_CONTRAPARTE")
    )
    sin_aval.etapa_actual = etapa_contraparte
    db.commit()
    entrar_como(gestor)
    assert client.post(
        f"/api/convenios/{sin_aval.id}/revision-contraparte/enviar",
        json={"expected_version": sin_aval.version_actual},
    ).status_code == 409

    _habilitar_contraparte(
        db, convenio_listo, gestor, solicitante, revisor, crear_usuario
    )
    segunda = db.scalar(
        select(RevisionConvenio).where(
            RevisionConvenio.convenio_id == convenio_listo.id,
            RevisionConvenio.instancia_juridica == 2,
        )
    )
    version_aprobada_id = segunda.version_resultado_id
    segunda.version_resultado_id = None
    db.commit()
    assert _enviar(client, convenio_listo, gestor, entrar_como).status_code == 409
    segunda.version_resultado_id = version_aprobada_id
    db.commit()
    assert client.post(
        f"/api/convenios/{convenio_listo.id}/revision-contraparte/enviar",
        json={"expected_version": convenio_listo.version_actual - 1},
    ).status_code == 409
    assert _enviar(client, convenio_listo, gestor, entrar_como).status_code == 201
    assert _enviar(client, convenio_listo, gestor, entrar_como).status_code == 409


def test_ca03_solo_responsable_aprueba_y_avanza_a_revision_final(
    client,
    db,
    gestor,
    solicitante,
    revisor,
    crear_usuario,
    convenio_listo,
    entrar_como,
) -> None:
    version = _habilitar_contraparte(
        db, convenio_listo, gestor, solicitante, revisor, crear_usuario
    )
    revision = _enviar(client, convenio_listo, gestor, entrar_como).json()
    ruta = (
        f"/api/convenios/{convenio_listo.id}/revisiones/{revision['id']}"
        "/contraparte/aprobar"
    )
    ajeno = crear_usuario(CodigoRol.SOLICITANTE_INTERNO, TipoUsuario.INTERNO)
    entrar_como(ajeno)
    assert client.post(
        ruta, json={"expected_version": convenio_listo.version_actual}
    ).status_code == 403

    entrar_como(solicitante)
    assert client.post(
        ruta, json={"expected_version": convenio_listo.version_actual - 1}
    ).status_code == 409
    respuesta = client.post(
        ruta, json={"expected_version": convenio_listo.version_actual}
    )
    assert respuesta.status_code == 200
    assert respuesta.json()["estado"] == "RESUELTA"
    assert respuesta.json()["resultado"] == "APROBADA"
    assert respuesta.json()["resuelta_por"]["id"] == solicitante.id
    assert respuesta.json()["version_resultado_id"] == version.id
    db.refresh(convenio_listo)
    assert convenio_listo.etapa_actual.codigo == "REVISION_FINAL"
    assert convenio_listo.estado == "EN_TRAMITE"
    assert client.post(
        ruta, json={"expected_version": convenio_listo.version_actual}
    ).status_code == 409


def test_ca04_ca05_devolucion_atomica_crea_observaciones_y_vuelve_a_elaboracion(
    client,
    db,
    gestor,
    solicitante,
    revisor,
    crear_usuario,
    convenio_listo,
    entrar_como,
) -> None:
    _habilitar_contraparte(
        db, convenio_listo, gestor, solicitante, revisor, crear_usuario
    )
    revision = _enviar(client, convenio_listo, gestor, entrar_como).json()
    ruta = (
        f"/api/convenios/{convenio_listo.id}/revisiones/{revision['id']}"
        "/contraparte/devolver"
    )
    entrar_como(solicitante)
    assert client.post(
        ruta,
        json={
            "expected_version": convenio_listo.version_actual,
            "observaciones": [],
        },
    ).status_code == 422
    persistida = db.get(RevisionConvenio, revision["id"])
    db.refresh(persistida)
    assert persistida.estado == "PENDIENTE"
    assert not persistida.observaciones

    respuesta = client.post(
        ruta,
        json={
            "expected_version": convenio_listo.version_actual,
            "observaciones": [" Ajustar cláusula quinta ", "Precisar vigencia"],
        },
    )
    assert respuesta.status_code == 200
    assert respuesta.json()["resultado"] == "DEVUELTA"
    assert {item["origen"] for item in respuesta.json()["observaciones"]} == {
        "CONTRAPARTE"
    }
    assert all(
        item["responsable"]["id"] == gestor.id
        for item in respuesta.json()["observaciones"]
    )
    db.refresh(convenio_listo)
    assert convenio_listo.etapa_actual.codigo == "ELABORACION"


def test_ca06_ca08_correccion_reingresa_por_rj1_rj2_y_conserva_dos_ciclos(
    client,
    db,
    gestor,
    solicitante,
    revisor,
    crear_usuario,
    convenio_listo,
    entrar_como,
) -> None:
    _habilitar_contraparte(
        db, convenio_listo, gestor, solicitante, revisor, crear_usuario
    )
    primera = _enviar(client, convenio_listo, gestor, entrar_como).json()
    entrar_como(solicitante)
    devuelta = client.post(
        f"/api/convenios/{convenio_listo.id}/revisiones/{primera['id']}"
        "/contraparte/devolver",
        json={
            "expected_version": convenio_listo.version_actual,
            "observaciones": ["Corregir alcance"],
        },
    ).json()
    observacion_id = devuelta["observaciones"][0]["id"]

    entrar_como(gestor)
    assert client.post(
        f"/api/convenios/{convenio_listo.id}/elaboracion/finalizar"
    ).status_code == 409
    atendida = client.patch(
        f"/api/convenios/{convenio_listo.id}/observaciones/"
        f"{observacion_id}/atender",
        json={"respuesta": "Se ajustó el alcance"},
    )
    assert atendida.status_code == 200
    assert atendida.json()["origen"] == "CONTRAPARTE"
    assert atendida.json()["estado"] == "ATENDIDA"
    assert atendida.json()["descripcion"] == "Corregir alcance"
    assert client.post(
        f"/api/convenios/{convenio_listo.id}/elaboracion/finalizar"
    ).status_code == 409

    elaboracion = client.get(
        f"/api/convenios/{convenio_listo.id}/elaboracion"
    ).json()
    guardada = client.patch(
        f"/api/convenios/{convenio_listo.id}/elaboracion",
        json={
            "contenido": _contenido_corregido(elaboracion["contenido"]),
            "expected_version": elaboracion["version_actual"],
        },
    )
    assert guardada.status_code == 200
    version_corregida = guardada.json()["version_actual"]
    assert db.scalar(
        select(VersionConvenio.contexto).where(
            VersionConvenio.convenio_id == convenio_listo.id,
            VersionConvenio.numero == version_corregida,
        )
    ) == ContextoVersionConvenio.GUARDADO.value
    assert client.post(
        f"/api/convenios/{convenio_listo.id}/elaboracion/finalizar"
    ).status_code == 200
    db.refresh(convenio_listo)
    assert convenio_listo.etapa_actual.codigo == "REVISION_AVAL_JURIDICO"
    assert _enviar(client, convenio_listo, gestor, entrar_como).status_code == 409

    nueva_rj1 = db.scalar(
        select(RevisionConvenio).where(
            RevisionConvenio.convenio_id == convenio_listo.id,
            RevisionConvenio.estado == "PENDIENTE",
        )
    )
    assert (nueva_rj1.numero_ronda, nueva_rj1.instancia_juridica) == (2, 1)
    ServicioConvenios(db).aprobar(
        convenio_listo.id,
        nueva_rj1.id,
        convenio_listo.version_actual,
        revisor,
    )
    nueva_rj2 = db.scalar(
        select(RevisionConvenio).where(
            RevisionConvenio.convenio_id == convenio_listo.id,
            RevisionConvenio.estado == "PENDIENTE",
        )
    )
    tercer_revisor = crear_usuario(CodigoRol.REVISOR_ORI, TipoUsuario.INTERNO)
    ServicioConvenios(db).aprobar(
        convenio_listo.id,
        nueva_rj2.id,
        convenio_listo.version_actual,
        tercer_revisor,
    )
    segunda = _enviar(client, convenio_listo, gestor, entrar_como)
    assert segunda.status_code == 201
    assert segunda.json()["id"] != primera["id"]

    historial = client.get(
        f"/api/convenios/{convenio_listo.id}/revisiones"
    ).json()
    ciclos = [r for r in historial["revisiones"] if r["tipo"] == "CONTRAPARTE"]
    assert len(ciclos) == 2
    assert ciclos[0]["resultado"] == "DEVUELTA"
    assert ciclos[0]["creada_por"]["id"] == gestor.id
    assert ciclos[0]["resuelta_por"]["id"] == solicitante.id
    assert ciclos[0]["observaciones"][0]["respuesta"] == "Se ajustó el alcance"
    assert ciclos[1]["estado"] == "PENDIENTE"


def test_revision_id_de_otro_convenio_devuelve_404(
    client,
    db,
    gestor,
    solicitante,
    revisor,
    crear_usuario,
    convenio_listo,
    crear_convenio,
    entrar_como,
) -> None:
    _habilitar_contraparte(
        db, convenio_listo, gestor, solicitante, revisor, crear_usuario
    )
    revision = _enviar(client, convenio_listo, gestor, entrar_como).json()
    otro = crear_convenio(gestor)
    entrar_como(solicitante)
    assert client.get(
        f"/api/convenios/{otro.id}/revisiones/{revision['id']}/contraparte"
    ).status_code == 404


class _ErrorPostgresSimulado(Exception):
    def __init__(self, constraint_name: str) -> None:
        self.diag = SimpleNamespace(constraint_name=constraint_name)


def test_integrity_error_del_indice_parcial_se_convierte_en_conflicto_de_dominio(
    db,
    gestor,
    solicitante,
    revisor,
    crear_usuario,
    convenio_listo,
    monkeypatch,
) -> None:
    _habilitar_contraparte(
        db, convenio_listo, gestor, solicitante, revisor, crear_usuario
    )
    error = IntegrityError(
        "INSERT revision_convenio",
        {},
        _ErrorPostgresSimulado("uq_revision_convenio_contraparte_pendiente"),
    )
    flush_real = db.flush

    def fallar_flush(*args, **kwargs) -> None:
        if any(
            isinstance(item, RevisionConvenio)
            and item.tipo == "CONTRAPARTE"
            and item.id is None
            for item in db.new
        ):
            raise error
        flush_real(*args, **kwargs)

    monkeypatch.setattr(db, "flush", fallar_flush)
    with pytest.raises(RevisionNoDisponible, match="Ya existe una revisión") as exc:
        ServicioConvenios(db).enviar_a_contraparte(
            convenio_listo.id, convenio_listo.version_actual, gestor
        )
    assert exc.value.__cause__ is error


def test_integrity_error_ajeno_no_se_enmascara_como_envio_duplicado(
    db,
    gestor,
    solicitante,
    revisor,
    crear_usuario,
    convenio_listo,
    monkeypatch,
) -> None:
    _habilitar_contraparte(
        db, convenio_listo, gestor, solicitante, revisor, crear_usuario
    )
    error = IntegrityError(
        "INSERT revision_convenio",
        {},
        _ErrorPostgresSimulado("fk_revision_convenio_creada_por_id"),
    )
    flush_real = db.flush

    def fallar_flush(*args, **kwargs) -> None:
        if any(
            isinstance(item, RevisionConvenio)
            and item.tipo == "CONTRAPARTE"
            and item.id is None
            for item in db.new
        ):
            raise error
        flush_real(*args, **kwargs)

    monkeypatch.setattr(db, "flush", fallar_flush)
    with pytest.raises(IntegrityError) as exc:
        ServicioConvenios(db).enviar_a_contraparte(
            convenio_listo.id, convenio_listo.version_actual, gestor
        )
    assert exc.value is error


def test_fallo_sql_en_devolucion_revierte_todas_las_escrituras(
    db,
    gestor,
    solicitante,
    revisor,
    crear_usuario,
    convenio_listo,
    monkeypatch,
) -> None:
    _habilitar_contraparte(
        db, convenio_listo, gestor, solicitante, revisor, crear_usuario
    )
    revision = ServicioConvenios(db).enviar_a_contraparte(
        convenio_listo.id, convenio_listo.version_actual, gestor
    )
    observaciones_antes = db.scalar(
        select(func.count())
        .select_from(ObservacionRevision)
        .where(ObservacionRevision.revision_convenio_id == revision.id)
    )
    historial_antes = db.scalar(
        select(func.count())
        .select_from(HistorialEtapa)
        .where(
            HistorialEtapa.convenio_id == convenio_listo.id,
            HistorialEtapa.observacion == "Devolución de revisión de contraparte",
        )
    )
    auditorias_antes = db.scalar(
        select(func.count())
        .select_from(Auditoria)
        .where(
            Auditoria.entidad == "revision_convenio",
            Auditoria.registro_id == revision.id,
        )
    )
    commit_real = db.commit

    def fallar_commit() -> None:
        db.flush()
        raise SQLAlchemyError("fallo simulado después de preparar la devolución")

    monkeypatch.setattr(db, "commit", fallar_commit)
    with pytest.raises(SQLAlchemyError):
        ServicioConvenios(db).devolver_contraparte(
            convenio_listo.id,
            revision.id,
            ["Primera observación", "Segunda observación"],
            convenio_listo.version_actual,
            solicitante,
        )
    monkeypatch.setattr(db, "commit", commit_real)
    db.expire_all()

    persistida = db.get(RevisionConvenio, revision.id)
    convenio_persistido = db.get(type(convenio_listo), convenio_listo.id)
    assert db.scalar(
        select(func.count())
        .select_from(ObservacionRevision)
        .where(ObservacionRevision.revision_convenio_id == revision.id)
    ) == observaciones_antes
    assert persistida.estado == "PENDIENTE"
    assert persistida.resultado is None
    assert persistida.resuelta_por_id is None
    assert persistida.resuelta_en is None
    assert convenio_persistido.etapa_actual.codigo == "REVISION_CONTRAPARTE"
    assert db.scalar(
        select(func.count())
        .select_from(HistorialEtapa)
        .where(
            HistorialEtapa.convenio_id == convenio_listo.id,
            HistorialEtapa.observacion == "Devolución de revisión de contraparte",
        )
    ) == historial_antes
    assert db.scalar(
        select(func.count())
        .select_from(Auditoria)
        .where(
            Auditoria.entidad == "revision_convenio",
            Auditoria.registro_id == revision.id,
        )
    ) == auditorias_antes
