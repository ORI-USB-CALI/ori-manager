"""HT-08 — Validar las fechas de vigencia al crear o elaborar un convenio.

"Hoy" se fija con monkeypatch para no depender del reloj real: varias fechas
fijas de 2026 en otras pruebas ya quedaron en el pasado.
"""

from datetime import date, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import func, select

from backend.models.convenio import Convenio
from backend.models.enums import EstadoSolicitud, TipoSolicitante
from backend.models.etapa import Etapa
from backend.models.solicitud_convenio import SolicitudConvenio
from backend.models.version_convenio import VersionConvenio
from backend.services import convenios as servicio_convenios
from backend.services.convenios import validar_completitud
from backend.services.vigencia import (
    MOTIVO_INICIO_POSTERIOR,
    MOTIVO_VENCIMIENTO_PASADO,
    validar_vigencia,
)

HOY = date(2030, 6, 15)
AYER = HOY - timedelta(days=1)
MANANA = HOY + timedelta(days=1)


@pytest.fixture(autouse=True)
def hoy_fijo(monkeypatch) -> None:
    monkeypatch.setattr(servicio_convenios, "fecha_actual_dominio", lambda: HOY)


def _motivos(faltantes) -> list[tuple[str, str]]:
    return [(f.campo, f.motivo) for f in faltantes]


def _motivos_api(respuesta) -> list[tuple[str, str]]:
    return [(f["campo"], f["motivo"]) for f in respuesta.json()["detail"]["faltantes"]]


# --- BE-01: función pura, límites de fecha ---


@pytest.mark.parametrize(
    ("inicio", "vencimiento"),
    [
        pytest.param(None, None, id="sin-fechas"),
        pytest.param(AYER, None, id="solo-inicio-pasado"),
        pytest.param(None, HOY, id="vence-hoy"),
        pytest.param(None, MANANA, id="vence-manana"),
        pytest.param(HOY, HOY, id="inicio-igual-vencimiento"),
        pytest.param(AYER, MANANA, id="inicio-pasado-vigente"),
    ],
)
def test_ca03_vigencia_valida_no_reporta_nada(inicio, vencimiento) -> None:
    assert validar_vigencia(inicio, vencimiento, HOY) == []


def test_ca01_vencimiento_de_ayer_no_es_valido() -> None:
    assert _motivos(validar_vigencia(None, AYER, HOY)) == [
        ("fecha_vencimiento", MOTIVO_VENCIMIENTO_PASADO)
    ]


def test_ca02_inicio_un_dia_despues_del_vencimiento_no_es_valido() -> None:
    assert _motivos(validar_vigencia(MANANA + timedelta(days=1), MANANA, HOY)) == [
        ("fecha_vencimiento", MOTIVO_INICIO_POSTERIOR)
    ]


def test_ca01_y_ca02_se_reportan_juntos() -> None:
    assert _motivos(validar_vigencia(HOY, AYER, HOY)) == [
        ("fecha_vencimiento", MOTIVO_VENCIMIENTO_PASADO),
        ("fecha_vencimiento", MOTIVO_INICIO_POSTERIOR),
    ]


def test_completitud_usa_la_fecha_de_referencia_recibida() -> None:
    convenio = Convenio(fecha_inicio=AYER, fecha_vencimiento=HOY)

    assert ("fecha_vencimiento", MOTIVO_VENCIMIENTO_PASADO) in _motivos(
        validar_completitud(convenio, hoy=MANANA)
    )
    assert ("fecha_vencimiento", MOTIVO_VENCIMIENTO_PASADO) not in _motivos(
        validar_completitud(convenio, hoy=HOY)
    )


# --- BE-02: creación desde solicitud ---


@pytest.fixture
def solicitud_aprobada(db, gestor) -> SolicitudConvenio:
    solicitud = SolicitudConvenio(
        consecutivo=f"SOL-{uuid4().hex}",
        tipo_solicitante=TipoSolicitante.INTERNO.value,
        solicitante_id=gestor.id,
        objeto="Objeto solicitado",
        estado=EstadoSolicitud.APROBADA.value,
    )
    db.add(solicitud)
    db.commit()
    return solicitud


def _crear_desde_solicitud(client, solicitud, **fechas):
    return client.post(
        "/api/convenios",
        json={
            "solicitud_id": solicitud.id,
            "objeto": "Objeto del convenio",
            **{campo: valor.isoformat() for campo, valor in fechas.items()},
        },
    )


def _convenios_de(db, solicitud) -> int:
    return db.scalar(
        select(func.count())
        .select_from(Convenio)
        .where(Convenio.solicitud_id == solicitud.id)
    )


def test_ca01_crear_desde_solicitud_rechaza_vencimiento_pasado(
    client, db, solicitud_aprobada
) -> None:
    respuesta = _crear_desde_solicitud(
        client, solicitud_aprobada, fecha_vencimiento=AYER
    )

    assert respuesta.status_code == 422
    assert _motivos_api(respuesta) == [("fecha_vencimiento", MOTIVO_VENCIMIENTO_PASADO)]
    assert _convenios_de(db, solicitud_aprobada) == 0


def test_ca02_crear_desde_solicitud_rechaza_inicio_posterior(
    client, db, solicitud_aprobada
) -> None:
    respuesta = _crear_desde_solicitud(
        client,
        solicitud_aprobada,
        fecha_inicio=MANANA + timedelta(days=1),
        fecha_vencimiento=MANANA,
    )

    assert respuesta.status_code == 422
    assert _motivos_api(respuesta) == [("fecha_vencimiento", MOTIVO_INICIO_POSTERIOR)]
    assert _convenios_de(db, solicitud_aprobada) == 0


def test_ca03_crear_desde_solicitud_acepta_inicio_igual_a_vencimiento_hoy(
    client, solicitud_aprobada
) -> None:
    respuesta = _crear_desde_solicitud(
        client, solicitud_aprobada, fecha_inicio=HOY, fecha_vencimiento=HOY
    )

    assert respuesta.status_code == 201, respuesta.text
    assert respuesta.json()["fecha_vencimiento"] == HOY.isoformat()


# --- BE-02: creación manual (HU-10), fechas opcionales ---


def _crear_manual(client, **fechas):
    return client.post(
        "/api/convenios/manual",
        json={
            "objeto": "Convenio creado por la ORI",
            **{campo: valor.isoformat() for campo, valor in fechas.items()},
        },
    )


def test_ca01_crear_manual_rechaza_vencimiento_pasado(client, db, gestor) -> None:
    antes = db.scalar(select(func.count()).select_from(Convenio))

    respuesta = _crear_manual(client, fecha_vencimiento=AYER)

    assert respuesta.status_code == 422
    assert _motivos_api(respuesta) == [("fecha_vencimiento", MOTIVO_VENCIMIENTO_PASADO)]
    assert db.scalar(select(func.count()).select_from(Convenio)) == antes


def test_ca02_crear_manual_rechaza_inicio_posterior(client, gestor) -> None:
    respuesta = _crear_manual(
        client, fecha_inicio=MANANA + timedelta(days=1), fecha_vencimiento=MANANA
    )

    assert respuesta.status_code == 422
    assert _motivos_api(respuesta) == [("fecha_vencimiento", MOTIVO_INICIO_POSTERIOR)]


@pytest.mark.parametrize(
    "fechas",
    [
        pytest.param({}, id="sin-fechas"),
        pytest.param({"fecha_inicio": AYER, "fecha_vencimiento": HOY}, id="vence-hoy"),
    ],
)
def test_ca03_crear_manual_acepta_vigencia_valida_u_omitida(
    client, gestor, fechas
) -> None:
    respuesta = _crear_manual(client, **fechas)

    assert respuesta.status_code == 201, respuesta.text


# --- BE-02: edición durante la elaboración ---


def test_ca01_actualizar_rechaza_vencimiento_pasado_sin_modificar(
    client, db, gestor, crear_convenio
) -> None:
    convenio = crear_convenio(gestor, fecha_vencimiento=MANANA)

    respuesta = client.patch(
        f"/api/convenios/{convenio.id}",
        json={"fecha_vencimiento": AYER.isoformat()},
    )

    assert respuesta.status_code == 422
    assert _motivos_api(respuesta) == [("fecha_vencimiento", MOTIVO_VENCIMIENTO_PASADO)]
    db.expire_all()
    assert db.get(Convenio, convenio.id).fecha_vencimiento == MANANA


def test_ca02_actualizar_combina_inicio_nuevo_con_vencimiento_guardado(
    client, db, gestor, crear_convenio
) -> None:
    convenio = crear_convenio(gestor, fecha_vencimiento=MANANA)

    respuesta = client.patch(
        f"/api/convenios/{convenio.id}",
        json={"fecha_inicio": (MANANA + timedelta(days=1)).isoformat()},
    )

    assert respuesta.status_code == 422
    assert _motivos_api(respuesta) == [("fecha_vencimiento", MOTIVO_INICIO_POSTERIOR)]
    db.expire_all()
    assert db.get(Convenio, convenio.id).fecha_inicio is None


def test_editar_otro_campo_no_revalida_vigencia_heredada(
    client, db, gestor, crear_convenio
) -> None:
    # Dato cargado antes de HT-08: la regla solo aplica cuando se tocan las fechas.
    convenio = crear_convenio(gestor, fecha_vencimiento=AYER)

    respuesta = client.patch(
        f"/api/convenios/{convenio.id}", json={"objeto": "Objeto ajustado"}
    )

    assert respuesta.status_code == 200, respuesta.text


def test_reenviar_la_misma_vigencia_heredada_no_bloquea_el_guardado(
    client, db, gestor, crear_convenio
) -> None:
    convenio = crear_convenio(gestor, fecha_vencimiento=AYER)

    respuesta = client.patch(
        f"/api/convenios/{convenio.id}",
        json={"objeto": "Objeto ajustado", "fecha_vencimiento": AYER.isoformat()},
    )

    assert respuesta.status_code == 200, respuesta.text


def test_ca02_guardar_elaboracion_bloquea_el_guardado(
    client, db, gestor, crear_convenio
) -> None:
    convenio = crear_convenio(gestor)
    version_antes = convenio.version_actual

    respuesta = client.patch(
        f"/api/convenios/{convenio.id}/elaboracion",
        json={
            "expected_revision": 0,
            "contenido": {"type": "doc", "content": [{"type": "paragraph", "content": [
                {"type": "text", "text": "Cláusula nueva"},
            ]}]},
            "fecha_inicio": (MANANA + timedelta(days=1)).isoformat(),
            "fecha_vencimiento": MANANA.isoformat(),
        },
    )

    assert respuesta.status_code == 422
    assert _motivos_api(respuesta) == [("fecha_vencimiento", MOTIVO_INICIO_POSTERIOR)]
    db.expire_all()
    guardado = db.get(Convenio, convenio.id)
    assert guardado.version_actual == version_antes
    assert guardado.fecha_vencimiento is None
    assert guardado.borrador is None
    assert db.scalar(
        select(func.count())
        .select_from(VersionConvenio)
        .where(VersionConvenio.convenio_id == convenio.id)
    ) == 1


# --- BE-02: finalización de la elaboración y formalización ---


def test_ca01_finalizar_elaboracion_bloquea_vencimiento_que_ya_paso(
    client, db, convenio_listo
) -> None:
    convenio_listo.fecha_inicio = AYER - timedelta(days=30)
    convenio_listo.fecha_vencimiento = AYER
    db.commit()

    validacion = client.get(f"/api/convenios/{convenio_listo.id}/elaboracion/validacion")
    respuesta = client.post(f"/api/convenios/{convenio_listo.id}/elaboracion/finalizar")

    assert ("fecha_vencimiento", MOTIVO_VENCIMIENTO_PASADO) in [
        (f["campo"], f["motivo"]) for f in validacion.json()["faltantes"]
    ]
    assert respuesta.status_code == 422
    assert ("fecha_vencimiento", MOTIVO_VENCIMIENTO_PASADO) in _motivos_api(respuesta)
    db.expire_all()
    assert db.get(Convenio, convenio_listo.id).etapa_actual.codigo == "ELABORACION"


@pytest.fixture
def convenio_en_firmas(db, gestor, crear_convenio) -> Convenio:
    convenio = crear_convenio(gestor, fecha_inicio=AYER, fecha_vencimiento=MANANA)
    convenio.etapa_actual = db.scalar(
        select(Etapa).where(Etapa.codigo == "APROBACION_FIRMAS")
    )
    db.commit()
    return convenio


def test_formalizar_rechaza_vencimiento_que_ya_paso(
    client, db, convenio_en_firmas
) -> None:
    # Decisión HT-08 pendiente de revisión: no se activa un convenio ya vencido.
    convenio_en_firmas.fecha_vencimiento = AYER
    db.commit()

    respuesta = client.post(f"/api/convenios/{convenio_en_firmas.id}/firmas/formalizar")

    assert respuesta.status_code == 422
    assert _motivos_api(respuesta) == [("fecha_vencimiento", MOTIVO_VENCIMIENTO_PASADO)]
    db.expire_all()
    assert db.get(Convenio, convenio_en_firmas.id).estado == "EN_TRAMITE"


def test_formalizar_con_vigencia_valida_sigue_a_las_demas_reglas(
    client, convenio_en_firmas
) -> None:
    respuesta = client.post(f"/api/convenios/{convenio_en_firmas.id}/firmas/formalizar")

    # La vigencia no bloquea: responde la regla siguiente (proceso de firmas).
    assert respuesta.status_code == 409
    assert "proceso de firmas" in respuesta.json()["detail"]
