"""HT-17: cierre tecnico; aceptacion institucional pendiente de traza en #175."""

from copy import deepcopy
from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import func, select

from backend.core.roles import CodigoRol
from backend.models.convenio import Convenio
from backend.models.enums import (
    ContextoVersionConvenio,
    EstadoConvenio,
    EstadoSolicitud,
    TipoSolicitante,
)
from backend.models.etapa import Etapa
from backend.models.solicitud_convenio import SolicitudConvenio
from backend.schemas.convenio import ConvenioCrearManual
from backend.services import convenios as servicio_convenios
from backend.services import renovaciones as servicio_renovaciones
from backend.services import vigencia as servicio_vigencia
from backend.services.convenios import (
    ServicioConvenios,
    VigenciaInvalida,
    exigir_vigencia_valida,
    validar_completitud,
)
from backend.services.vigencia import (
    MOTIVO_DURACION_INCOHERENTE,
    MOTIVO_INICIO_POSTERIOR,
    MOTIVO_VENCIMIENTO_PASADO,
    ZONA_HORARIA_DOMINIO,
    sumar_meses,
    validar_vigencia,
    vencimiento_esperado,
)

HOY = date(2030, 6, 15)
INICIO = date(2031, 1, 1)
VENCIMIENTO_12_MESES = date(2031, 12, 31)
VENCIMIENTO_INCOHERENTE = date(2032, 1, 1)


@pytest.fixture
def hoy_fijo(monkeypatch) -> None:
    monkeypatch.setattr(servicio_convenios, "fecha_actual_dominio", lambda: HOY)
    monkeypatch.setattr(servicio_renovaciones, "fecha_actual_dominio", lambda: HOY)


def _motivos(faltantes) -> list[tuple[str, str]]:
    return [(f.campo, f.motivo) for f in faltantes]


def _motivos_api(respuesta) -> list[tuple[str, str]]:
    return [(f["campo"], f["motivo"]) for f in respuesta.json()["detail"]["faltantes"]]


INCOHERENTE = [("fecha_vencimiento", MOTIVO_DURACION_INCOHERENTE)]


# --- CA-01/CA-05: aritmética de meses ---


@pytest.mark.parametrize(
    ("fecha", "meses", "esperado"),
    [
        pytest.param(date(2031, 1, 31), 1, date(2031, 2, 28), id="fin-de-mes-no-bisiesto"),
        pytest.param(date(2032, 1, 31), 1, date(2032, 2, 29), id="fin-de-mes-bisiesto"),
        pytest.param(date(2032, 2, 29), 12, date(2033, 2, 28), id="29-de-febrero"),
        pytest.param(date(2031, 11, 15), 3, date(2032, 2, 15), id="cambio-de-anio"),
        pytest.param(date(2031, 3, 31), 1, date(2031, 4, 30), id="mes-de-30-dias"),
        pytest.param(date(2031, 1, 15), 0, date(2031, 1, 15), id="cero-meses"),
    ],
)
def test_sumar_meses_usa_el_ultimo_dia_si_el_dia_no_existe(fecha, meses, esperado) -> None:
    assert sumar_meses(fecha, meses) == esperado


@pytest.mark.parametrize(
    ("inicio", "meses", "esperado"),
    [
        pytest.param(date(2027, 1, 1), 12, date(2027, 12, 31), id="ejemplo-de-la-regla"),
        pytest.param(date(2031, 1, 31), 1, date(2031, 2, 28), id="fin-de-mes"),
        pytest.param(date(2032, 2, 29), 12, date(2033, 2, 28), id="29-de-febrero"),
        pytest.param(date(2031, 11, 15), 3, date(2032, 2, 14), id="cambio-de-anio"),
        pytest.param(date(2031, 12, 1), 1, date(2031, 12, 31), id="diciembre-a-enero"),
    ],
)
def test_vencimiento_esperado_es_el_mismo_dia_del_mes(inicio, meses, esperado) -> None:
    assert vencimiento_esperado(inicio, meses) == esperado


# --- CA-02/CA-03: función pura de validación ---


def test_periodo_coherente_no_reporta_nada() -> None:
    assert validar_vigencia(INICIO, VENCIMIENTO_12_MESES, HOY, duracion_meses=12) == []


def test_periodo_incoherente_se_reporta_sobre_fecha_vencimiento() -> None:
    assert _motivos(
        validar_vigencia(INICIO, VENCIMIENTO_INCOHERENTE, HOY, duracion_meses=12)
    ) == INCOHERENTE


@pytest.mark.parametrize(
    ("inicio", "vencimiento", "duracion"),
    [
        pytest.param(INICIO, VENCIMIENTO_INCOHERENTE, None, id="sin-duracion"),
        pytest.param(INICIO, VENCIMIENTO_INCOHERENTE, 0, id="duracion-cero"),
        pytest.param(None, VENCIMIENTO_INCOHERENTE, 12, id="sin-inicio"),
        pytest.param(INICIO, None, 12, id="sin-vencimiento"),
    ],
)
def test_si_falta_un_valor_no_se_valida_la_coherencia(inicio, vencimiento, duracion) -> None:
    assert validar_vigencia(inicio, vencimiento, HOY, duracion_meses=duracion) == []


def test_ca03_inicio_retroactivo_y_periodo_corto_coherentes_se_aceptan() -> None:
    assert validar_vigencia(
        date(2030, 6, 1), date(2030, 6, 30), HOY, duracion_meses=1
    ) == []


def test_ca05_convenio_coherente_que_vence_hoy_sigue_vigente() -> None:
    assert validar_vigencia(date(2030, 5, 16), HOY, HOY, duracion_meses=1) == []


def test_inicio_posterior_no_se_duplica_con_la_incoherencia() -> None:
    assert _motivos(
        validar_vigencia(date(2031, 2, 1), INICIO, HOY, duracion_meses=12)
    ) == [("fecha_vencimiento", MOTIVO_INICIO_POSTERIOR)]


def test_vencimiento_pasado_e_incoherente_se_reportan_juntos() -> None:
    assert _motivos(
        validar_vigencia(date(2029, 1, 1), date(2029, 6, 1), HOY, duracion_meses=12)
    ) == [
        ("fecha_vencimiento", MOTIVO_VENCIMIENTO_PASADO),
        ("fecha_vencimiento", MOTIVO_DURACION_INCOHERENTE),
    ]


def test_duracion_fuera_de_rango_es_incoherente_y_no_falla() -> None:
    assert _motivos(
        validar_vigencia(INICIO, VENCIMIENTO_12_MESES, HOY, duracion_meses=10**9)
    ) == INCOHERENTE


# --- CA-05: medianoche en Bogotá ---


@pytest.mark.parametrize(
    ("instante_utc", "valido"),
    [
        # 04:59 UTC del 1 de julio = 23:59 del 30 de junio en Bogotá: vence hoy.
        pytest.param(datetime(2030, 7, 1, 4, 59, tzinfo=UTC), True, id="23-59-bogota"),
        # 05:00 UTC del 1 de julio = 00:00 del 1 de julio en Bogotá: ya venció.
        pytest.param(datetime(2030, 7, 1, 5, 0, tzinfo=UTC), False, id="00-00-bogota"),
    ],
)
def test_ca05_medianoche_usa_el_dia_de_bogota(monkeypatch, instante_utc, valido) -> None:
    monkeypatch.setattr(
        servicio_vigencia,
        "instante_actual_dominio",
        lambda: instante_utc.astimezone(ZONA_HORARIA_DOMINIO),
    )
    # Coherente: 1 mes desde el 30 de mayo vence el 30 de junio.
    argumentos = (date(2030, 5, 31), date(2030, 6, 30))

    if valido:
        exigir_vigencia_valida(*argumentos, duracion_meses=1)
    else:
        with pytest.raises(VigenciaInvalida) as error:
            exigir_vigencia_valida(*argumentos, duracion_meses=1)
        assert _motivos(error.value.faltantes) == [
            ("fecha_vencimiento", MOTIVO_VENCIMIENTO_PASADO)
        ]


def test_completitud_revisa_la_coherencia() -> None:
    convenio = Convenio(
        vigencia_ht17=True, fecha_inicio=INICIO, fecha_vencimiento=VENCIMIENTO_INCOHERENTE, duracion_meses=12
    )

    assert ("fecha_vencimiento", MOTIVO_DURACION_INCOHERENTE) in _motivos(
        validar_completitud(convenio, hoy=HOY)
    )


# --- CA-02/CA-04: registro en trámite (creación) ---


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


def _crear_desde_solicitud(client, solicitud, vencimiento):
    return client.post(
        "/api/convenios",
        json={
            "solicitud_id": solicitud.id,
            "objeto": "Objeto del convenio",
            "fecha_inicio": INICIO.isoformat(),
            "fecha_vencimiento": vencimiento.isoformat(),
            "duracion_meses": 12,
        },
    )


def test_ca02_crear_desde_solicitud_rechaza_incoherencia_sin_persistir(
    client, db, hoy_fijo, solicitud_aprobada
) -> None:
    respuesta = _crear_desde_solicitud(client, solicitud_aprobada, VENCIMIENTO_INCOHERENTE)

    assert respuesta.status_code == 422
    assert _motivos_api(respuesta) == INCOHERENTE
    assert db.scalar(
        select(func.count())
        .select_from(Convenio)
        .where(Convenio.solicitud_id == solicitud_aprobada.id)
    ) == 0


def test_ca02_crear_desde_solicitud_acepta_periodo_coherente(
    client, hoy_fijo, solicitud_aprobada
) -> None:
    respuesta = _crear_desde_solicitud(client, solicitud_aprobada, VENCIMIENTO_12_MESES)

    assert respuesta.status_code == 201, respuesta.text
    cuerpo = respuesta.json()
    assert cuerpo["fecha_vencimiento"] == VENCIMIENTO_12_MESES.isoformat()
    assert cuerpo["duracion_meses"] == 12


def test_ca02_crear_manual_rechaza_incoherencia_sin_persistir(
    client, db, hoy_fijo, gestor
) -> None:
    antes = db.scalar(select(func.count()).select_from(Convenio))

    respuesta = client.post(
        "/api/convenios/manual",
        json={
            "objeto": "Convenio creado por la ORI",
            "fecha_inicio": INICIO.isoformat(),
            "fecha_vencimiento": VENCIMIENTO_INCOHERENTE.isoformat(),
            "duracion_meses": 12,
        },
    )

    assert respuesta.status_code == 422
    assert _motivos_api(respuesta) == INCOHERENTE
    assert db.scalar(select(func.count()).select_from(Convenio)) == antes


# --- CA-02/BE-04: edición durante la elaboración ---


@pytest.fixture
def convenio_coherente(db, gestor, hoy_fijo, crear_convenio) -> Convenio:
    return crear_convenio(
        gestor,
        fecha_inicio=INICIO,
        fecha_vencimiento=VENCIMIENTO_12_MESES,
        duracion_meses=12,
    )


def test_ca02_cambiar_solo_la_duracion_calcula_y_persiste(
    client, db, convenio_coherente
) -> None:
    respuesta = client.patch(
        f"/api/convenios/{convenio_coherente.id}", json={"duracion_meses": 24}
    )

    assert respuesta.status_code == 200
    db.expire_all()
    assert db.get(Convenio, convenio_coherente.id).duracion_meses == 24
    assert db.get(Convenio, convenio_coherente.id).fecha_vencimiento == date(2032, 12, 31)


def test_ca02_cambiar_duracion_y_vencimiento_coherentes_se_acepta(
    client, convenio_coherente
) -> None:
    respuesta = client.patch(
        f"/api/convenios/{convenio_coherente.id}",
        json={"duracion_meses": 24, "fecha_vencimiento": "2032-12-31"},
    )

    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json()["duracion_meses"] == 24


def test_ca02_guardar_elaboracion_incoherente_no_deja_borrador(
    client, db, convenio_coherente
) -> None:
    version_antes = convenio_coherente.version_actual

    respuesta = client.patch(
        f"/api/convenios/{convenio_coherente.id}/elaboracion",
        json={
            "expected_revision": 0,
            "contenido": {"type": "doc", "content": [{"type": "paragraph", "content": [
                {"type": "text", "text": "Cláusula nueva"},
            ]}]},
            "fecha_inicio": INICIO.isoformat(),
            "fecha_vencimiento": VENCIMIENTO_INCOHERENTE.isoformat(),
            "duracion_meses": 12,
        },
    )

    assert respuesta.status_code == 422
    assert _motivos_api(respuesta) == INCOHERENTE
    db.expire_all()
    guardado = db.get(Convenio, convenio_coherente.id)
    assert guardado.version_actual == version_antes
    assert guardado.fecha_vencimiento == VENCIMIENTO_12_MESES
    assert guardado.borrador is None


def test_ca06_historico_incoherente_se_edita_sin_tocar_vigencia(
    client, db, convenio_coherente
) -> None:
    # Simula un dato cargado antes de HT-17: no se reescribe ni bloquea.
    convenio_coherente.fecha_vencimiento = VENCIMIENTO_INCOHERENTE
    db.commit()

    respuesta = client.patch(
        f"/api/convenios/{convenio_coherente.id}",
        json={
            "objeto": "Objeto ajustado",
            # El editor reenvía los mismos valores: no cuentan como cambio.
            "fecha_inicio": INICIO.isoformat(),
            "fecha_vencimiento": VENCIMIENTO_INCOHERENTE.isoformat(),
            "duracion_meses": 12,
        },
    )

    assert respuesta.status_code == 200, respuesta.text
    db.expire_all()
    guardado = db.get(Convenio, convenio_coherente.id)
    assert guardado.fecha_vencimiento == VENCIMIENTO_INCOHERENTE
    assert guardado.duracion_meses == 12


# --- CA-04: finalización de la elaboración y formalización ---


def test_finalizar_elaboracion_bloquea_periodo_incoherente(
    client, db, hoy_fijo, convenio_listo
) -> None:
    convenio_listo.vigencia_ht17 = True
    convenio_listo.fecha_inicio = INICIO
    convenio_listo.fecha_vencimiento = VENCIMIENTO_INCOHERENTE
    convenio_listo.duracion_meses = 12
    db.commit()

    validacion = client.get(f"/api/convenios/{convenio_listo.id}/elaboracion/validacion")
    respuesta = client.post(f"/api/convenios/{convenio_listo.id}/elaboracion/finalizar")

    assert ("fecha_vencimiento", MOTIVO_DURACION_INCOHERENTE) in [
        (f["campo"], f["motivo"]) for f in validacion.json()["faltantes"]
    ]
    assert respuesta.status_code == 422
    db.expire_all()
    assert db.get(Convenio, convenio_listo.id).etapa_actual.codigo == "ELABORACION"


@pytest.fixture
def convenio_en_firmas(db, convenio_coherente) -> Convenio:
    convenio_coherente.etapa_actual = db.scalar(
        select(Etapa).where(Etapa.codigo == "APROBACION_FIRMAS")
    )
    db.commit()
    return convenio_coherente


def test_ca04_formalizar_rechaza_incoherencia_sin_tocar_fecha_firma(
    client, db, convenio_en_firmas
) -> None:
    convenio_en_firmas.vigencia_ht17 = True
    convenio_en_firmas.fecha_vencimiento = VENCIMIENTO_INCOHERENTE
    db.commit()

    respuesta = client.post(f"/api/convenios/{convenio_en_firmas.id}/firmas/formalizar")

    assert respuesta.status_code == 422
    assert _motivos_api(respuesta) == INCOHERENTE
    db.expire_all()
    guardado = db.get(Convenio, convenio_en_firmas.id)
    assert guardado.estado == EstadoConvenio.EN_TRAMITE.value
    assert guardado.fecha_firma is None


def test_ca04_formalizar_con_periodo_coherente_sigue_a_las_demas_reglas(
    client, convenio_en_firmas
) -> None:
    respuesta = client.post(f"/api/convenios/{convenio_en_firmas.id}/firmas/formalizar")

    # La vigencia no bloquea: responde la regla siguiente (proceso de firmas).
    assert respuesta.status_code == 409
    assert "proceso de firmas" in respuesta.json()["detail"]


# --- CA-04: renovación ---


@pytest.fixture
def convenio_vigente_renovable(db, crear_usuario, hoy_fijo) -> Convenio:
    autor = crear_usuario(CodigoRol.GESTOR_ORI)
    servicio = ServicioConvenios(db)
    convenio = servicio.crear_manual(
        ConvenioCrearManual(
            objeto="Convenio de origen para renovar",
            # Las fechas historicas se cargan despues de crear el borrador.
            implicacion_financiera="Recursos propios",
            duracion_meses=12,
        ),
        autor,
    )
    convenio.fecha_inicio = date(2029, 7, 15)
    convenio.fecha_vencimiento = HOY + timedelta(days=30)
    convenio.vigencia_ht17 = False
    convenio.codigo = f"ORIGEN-{autor.id}"
    convenio.fecha_firma = date(2029, 7, 15)
    convenio.porcentaje_avance = 100
    servicio._crear_version(
        convenio,
        deepcopy({"type": "doc", "content": [{"type": "paragraph", "content": [
            {"type": "text", "text": "Cláusula del convenio vigente"},
        ]}]}),
        autor,
        ContextoVersionConvenio.FINALIZACION,
    )
    convenio.estado = EstadoConvenio.VIGENTE.value
    convenio.etapa_actual = db.scalar(
        select(Etapa).where(Etapa.codigo == "FIRMA_ARCHIVO_SEGUIMIENTO")
    )
    db.commit()
    return convenio


def test_ca04_renovacion_valida_fechas_nuevas_contra_la_duracion_heredada(
    client, db, gestor, convenio_vigente_renovable
) -> None:
    respuesta = client.post(f"/api/convenios/{convenio_vigente_renovable.id}/renovaciones")
    assert respuesta.status_code == 201, respuesta.text
    hijo_id = respuesta.json()["convenio_renovacion_id"]
    hijo = db.get(Convenio, hijo_id)
    # Hereda la duración pero no las fechas del convenio padre.
    assert hijo.duracion_meses == 12
    assert hijo.fecha_inicio is None and hijo.fecha_vencimiento is None

    incoherente = client.patch(
        f"/api/convenios/{hijo_id}",
        json={
            "fecha_inicio": INICIO.isoformat(),
            "fecha_vencimiento": VENCIMIENTO_INCOHERENTE.isoformat(),
        },
    )
    coherente = client.patch(
        f"/api/convenios/{hijo_id}",
        json={
            "fecha_inicio": INICIO.isoformat(),
            "fecha_vencimiento": VENCIMIENTO_12_MESES.isoformat(),
        },
    )

    assert incoherente.status_code == 422
    assert _motivos_api(incoherente) == INCOHERENTE
    assert coherente.status_code == 200, coherente.text


def test_historico_en_firmas_no_bloquea_por_convencion_antigua(client, db, convenio_en_firmas):
    convenio_en_firmas.vigencia_ht17 = False
    convenio_en_firmas.duracion_meses = 1
    convenio_en_firmas.fecha_inicio = date(2020, 1, 1)
    convenio_en_firmas.fecha_vencimiento = VENCIMIENTO_INCOHERENTE
    db.commit()
    respuesta = client.post(f"/api/convenios/{convenio_en_firmas.id}/firmas/formalizar")
    assert respuesta.status_code == 409
    assert "proceso de firmas" in respuesta.json()["detail"]
    assert convenio_en_firmas.fecha_firma is None
