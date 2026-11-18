from datetime import UTC, date, datetime

import pytest
from test_hu10_exportacion import _texto_pdf
from test_hu24_exportacion_segura import _dto

from backend.models.firma_convenio import FirmaConvenio
from backend.services import exportacion_convenio, pdf_convenio
from backend.services.firmas import _fecha_contractual_firma
from backend.services.pdf_convenio import ServicioPdfConvenio
from backend.services.vigencia import ZONA_HORARIA_DOMINIO, fecha_civil_dominio


@pytest.mark.parametrize(
    "utc,esperada",
    [
        ("2026-11-16T00:04:53+00:00", date(2026, 11, 15)),
        ("2026-11-16T04:59:59+00:00", date(2026, 11, 15)),
        ("2026-11-16T05:00:00+00:00", date(2026, 11, 16)),
        ("2027-01-01T00:04:53+00:00", date(2026, 12, 31)),
        ("2027-01-01T05:00:00+00:00", date(2027, 1, 1)),
    ],
)
def test_firma_electronica_y_proceso_mixto_usan_fecha_civil(utc, esperada):
    instante = datetime.fromisoformat(utc)
    electronica = FirmaConvenio(modalidad="ELECTRONICA", fecha_firma=instante)
    fisicas = [
        FirmaConvenio(
            modalidad="FISICA", fecha_firma=datetime(2026, 11, 15, tzinfo=UTC)
        )
        for _ in range(6)
    ]
    assert fecha_civil_dominio(instante) == esperada
    assert _fecha_contractual_firma(electronica) == esperada
    assert max(_fecha_contractual_firma(f) for f in [electronica, *fisicas]) == esperada
    assert electronica.fecha_firma == instante


@pytest.mark.parametrize("zona", [UTC, ZONA_HORARIA_DOMINIO])
@pytest.mark.parametrize("declarada", [date(2026, 11, 15), date(2027, 1, 1)])
def test_fisica_conserva_fecha_declarada_incluso_si_la_sesion_devuelve_otra_zona(
    zona, declarada
):
    instante = datetime(
        declarada.year, declarada.month, declarada.day, tzinfo=UTC
    ).astimezone(zona)
    assert (
        _fecha_contractual_firma(
            FirmaConvenio(modalidad="FISICA", fecha_firma=instante)
        )
        == declarada
    )


def test_fecha_fisica_posterior_prevalece_sobre_instante_electronico():
    firmas = [
        FirmaConvenio(
            modalidad="FISICA", fecha_firma=datetime(2026, 11, 16, tzinfo=UTC)
        )
        for _ in range(6)
    ]
    firmas.append(
        FirmaConvenio(
            modalidad="ELECTRONICA",
            fecha_firma=datetime(2026, 11, 16, 0, 4, 53, tzinfo=UTC),
        )
    )
    assert max(_fecha_contractual_firma(f) for f in firmas) == date(2026, 11, 16)


def test_instante_historico_sin_zona_se_interpreta_como_utc():
    instante = datetime(2026, 11, 16, 0, 4, 53, tzinfo=UTC).replace(tzinfo=None)
    assert fecha_civil_dominio(instante) == date(2026, 11, 15)


@pytest.mark.parametrize(
    "mes,nombre",
    enumerate(
        [
            "enero",
            "febrero",
            "marzo",
            "abril",
            "mayo",
            "junio",
            "julio",
            "agosto",
            "septiembre",
            "octubre",
            "noviembre",
            "diciembre",
        ],
        start=1,
    ),
)
def test_pdf_renderiza_meses_en_espanol_sin_locale(mes, nombre):
    dto = _dto(fecha_emision=datetime(2026, mes, 16, 0, 4, 53, tzinfo=UTC))
    pdf = ServicioPdfConvenio().renderizar_dto_a_pdf(dto)
    assert f"15 de {nombre} de 2026" in _texto_pdf(pdf)


@pytest.mark.parametrize(
    "utc,civil",
    [
        ("2026-11-16T00:04:53+00:00", "2026-11-15"),
        ("2027-01-01T00:04:53+00:00", "2026-12-31"),
        ("2027-01-01T05:00:00+00:00", "2027-01-01"),
    ],
)
@pytest.mark.parametrize("formato", ["pdf", "excel"])
def test_emision_y_descarga_usan_bogota(
    db, client, convenio_exportable, monkeypatch, utc, civil, formato
):
    instante = datetime.fromisoformat(utc).astimezone(ZONA_HORARIA_DOMINIO)
    monkeypatch.setattr(pdf_convenio, "instante_actual_dominio", lambda: instante)
    monkeypatch.setattr(
        exportacion_convenio, "fecha_actual_dominio", lambda: instante.date()
    )
    dto = ServicioPdfConvenio().mapear_convenio_a_dto(convenio_exportable.id, db)
    assert dto.fecha_emision == instante
    assert dto.fecha_emision.isoformat().endswith("-05:00")
    respuesta = client.get(
        f"/api/convenios/{convenio_exportable.id}/exportar?formato={formato}"
    )
    assert respuesta.status_code == 200
    extension = "pdf" if formato == "pdf" else "xlsx"
    assert (
        f"Convenio_{convenio_exportable.codigo}_{civil}.{extension}"
        in respuesta.headers["content-disposition"]
    )
