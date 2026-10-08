from copy import deepcopy

import pytest
from sqlalchemy import select

from backend.core.roles import CodigoRol, TipoUsuario
from backend.models.revision_convenio import RevisionConvenio
from backend.services.convenios import ServicioConvenios

OBSERVACIONES_RONDA_1 = ["Precisar el objeto del convenio", "Ajustar la vigencia"]
CORRECCIONES_RONDA_1 = ["Objeto precisado con las actividades", "Vigencia ajustada a 24 meses"]
OBSERVACION_RJ2 = "Revisar la cláusula de confidencialidad"


def _pendiente(db, convenio_id: int) -> RevisionConvenio:
    return db.scalar(
        select(RevisionConvenio).where(
            RevisionConvenio.convenio_id == convenio_id,
            RevisionConvenio.estado == "PENDIENTE",
        )
    )


def _contenido_editado(contenido: dict, texto: str) -> dict:
    nuevo = deepcopy(contenido)
    nuevo["content"].append(
        {"type": "paragraph", "content": [{"type": "text", "text": texto}]}
    )
    return nuevo


@pytest.fixture
def historial_juridico(
    client, db, gestor, revisor, crear_usuario, convenio_listo, entrar_como
) -> dict:
    """Ronda 1: RJ1 devuelve con dos observaciones y el Gestor las corrige.
    Ronda 2: RJ1 aprueba y RJ2, con otro revisor, devuelve con una observación."""
    convenio = convenio_listo
    base = f"/api/convenios/{convenio.id}"

    ServicioConvenios(db).finalizar_elaboracion(convenio.id, gestor)
    rj1_ronda_1 = _pendiente(db, convenio.id)
    entrar_como(revisor)
    devolucion = client.post(
        f"{base}/revisiones/{rj1_ronda_1.id}/devolver",
        json={
            "expected_version": convenio.version_actual,
            "observaciones": OBSERVACIONES_RONDA_1,
        },
    )
    assert devolucion.status_code == 200

    entrar_como(gestor)
    for observacion, correccion in zip(
        devolucion.json()["observaciones"], CORRECCIONES_RONDA_1, strict=True
    ):
        assert client.patch(
            f"{base}/observaciones/{observacion['id']}/atender",
            json={"respuesta": correccion},
        ).status_code == 200
    elaboracion = client.get(f"{base}/elaboracion").json()
    assert client.patch(
        f"{base}/elaboracion",
        json={
            "contenido": _contenido_editado(elaboracion["contenido"], "Corrección"),
            "expected_version": elaboracion["version_actual"],
        },
    ).status_code == 200
    assert client.post(f"{base}/elaboracion/finalizar").status_code == 200

    db.refresh(convenio)
    rj1_ronda_2 = _pendiente(db, convenio.id)
    entrar_como(revisor)
    assert client.post(
        f"{base}/revisiones/{rj1_ronda_2.id}/aprobar",
        json={"expected_version": convenio.version_actual},
    ).status_code == 200

    rj2_ronda_2 = _pendiente(db, convenio.id)
    segundo_revisor = crear_usuario(CodigoRol.REVISOR_ORI, TipoUsuario.INTERNO)
    entrar_como(segundo_revisor)
    assert client.post(
        f"{base}/revisiones/{rj2_ronda_2.id}/devolver",
        json={
            "expected_version": convenio.version_actual,
            "observaciones": [OBSERVACION_RJ2],
        },
    ).status_code == 200

    entrar_como(gestor)
    return {
        "convenio": convenio,
        "gestor": gestor,
        "revisor": revisor,
        "segundo_revisor": segundo_revisor,
    }


def _revisiones_juridicas(client, convenio_id: int) -> list[dict]:
    respuesta = client.get(f"/api/convenios/{convenio_id}/revisiones")
    assert respuesta.status_code == 200
    return [r for r in respuesta.json()["revisiones"] if r["tipo"] == "JURIDICA"]


def _por_ronda_e_instancia(revisiones: list[dict]) -> dict[tuple[int, int], dict]:
    return {(r["numero_ronda"], r["instancia_juridica"]): r for r in revisiones}


def test_ca01_observaciones_juridicas_en_orden_cronologico(
    client, historial_juridico
) -> None:
    revisiones = _revisiones_juridicas(client, historial_juridico["convenio"].id)

    assert [r["id"] for r in revisiones] == sorted(r["id"] for r in revisiones)
    observaciones = [o for r in revisiones for o in r["observaciones"]]
    assert [o["descripcion"] for o in observaciones] == [
        *OBSERVACIONES_RONDA_1,
        OBSERVACION_RJ2,
    ]
    fechas = [o["creado_en"] for o in observaciones]
    assert fechas == sorted(fechas)


def test_ca02_identifica_al_revisor_y_la_fecha_de_cada_observacion(
    client, historial_juridico
) -> None:
    revisiones = _por_ronda_e_instancia(
        _revisiones_juridicas(client, historial_juridico["convenio"].id)
    )

    for observacion in revisiones[(1, 1)]["observaciones"]:
        assert observacion["registrada_por"]["id"] == historial_juridico["revisor"].id
        assert observacion["creado_en"] is not None
    (observacion_rj2,) = revisiones[(2, 2)]["observaciones"]
    assert (
        observacion_rj2["registrada_por"]["id"]
        == historial_juridico["segundo_revisor"].id
    )


def test_ca03_muestra_el_contenido_de_cada_observacion(
    client, historial_juridico
) -> None:
    revisiones = _por_ronda_e_instancia(
        _revisiones_juridicas(client, historial_juridico["convenio"].id)
    )

    assert [o["descripcion"] for o in revisiones[(1, 1)]["observaciones"]] == (
        OBSERVACIONES_RONDA_1
    )


def test_ca04_no_mezcla_observaciones_de_revisiones_juridicas_distintas(
    client, historial_juridico
) -> None:
    revisiones = _por_ronda_e_instancia(
        _revisiones_juridicas(client, historial_juridico["convenio"].id)
    )

    assert {
        clave: [o["descripcion"] for o in revision["observaciones"]]
        for clave, revision in revisiones.items()
    } == {
        (1, 1): OBSERVACIONES_RONDA_1,
        (2, 1): [],
        (2, 2): [OBSERVACION_RJ2],
    }


def test_ca05_conserva_y_diferencia_los_ciclos_de_revision(
    client, historial_juridico
) -> None:
    revisiones = _por_ronda_e_instancia(
        _revisiones_juridicas(client, historial_juridico["convenio"].id)
    )

    assert {ronda for ronda, _ in revisiones} == {1, 2}
    assert revisiones[(1, 1)]["resultado"] == "DEVUELTA"
    assert revisiones[(2, 1)]["resultado"] == "APROBADA"
    assert revisiones[(2, 2)]["resultado"] == "DEVUELTA"


def test_ca06_muestra_la_atencion_y_conserva_la_observacion_original(
    client, historial_juridico
) -> None:
    revisiones = _por_ronda_e_instancia(
        _revisiones_juridicas(client, historial_juridico["convenio"].id)
    )

    atendidas = revisiones[(1, 1)]["observaciones"]
    assert [o["estado"] for o in atendidas] == ["ATENDIDA", "ATENDIDA"]
    assert [o["descripcion"] for o in atendidas] == OBSERVACIONES_RONDA_1
    assert [o["respuesta"] for o in atendidas] == CORRECCIONES_RONDA_1
    for observacion in atendidas:
        assert observacion["atendida_por"]["id"] == historial_juridico["gestor"].id
        assert observacion["fecha_atencion"] is not None
    (pendiente,) = revisiones[(2, 2)]["observaciones"]
    assert pendiente["estado"] == "PENDIENTE"
    assert pendiente["respuesta"] is None
    assert pendiente["atendida_por"] is None


@pytest.mark.parametrize("codigo_rol", [CodigoRol.ADMINISTRADOR_ORI, CodigoRol.GESTOR_ORI])
def test_administrador_y_gestor_consultan_el_historial(
    client, crear_usuario, entrar_como, historial_juridico, codigo_rol
) -> None:
    entrar_como(crear_usuario(codigo_rol, TipoUsuario.INTERNO))

    revisiones = _revisiones_juridicas(client, historial_juridico["convenio"].id)

    assert len(revisiones) == 3


def test_revisor_sin_revision_juridica_asignada_no_consulta_el_historial(
    client, entrar_como, historial_juridico
) -> None:
    entrar_como(historial_juridico["revisor"])

    respuesta = client.get(
        f"/api/convenios/{historial_juridico['convenio'].id}/revisiones"
    )

    assert respuesta.status_code == 404


@pytest.mark.parametrize(
    ("codigo_rol", "tipo_usuario"),
    [
        (CodigoRol.SOLICITANTE_INTERNO, TipoUsuario.INTERNO),
        (CodigoRol.SOLICITANTE_EXTERNO, TipoUsuario.EXTERNO),
    ],
)
def test_solicitantes_no_consultan_el_historial(
    client, crear_usuario, entrar_como, historial_juridico, codigo_rol, tipo_usuario
) -> None:
    entrar_como(crear_usuario(codigo_rol, tipo_usuario))

    respuesta = client.get(
        f"/api/convenios/{historial_juridico['convenio'].id}/revisiones"
    )

    assert respuesta.status_code == 403


def test_sin_sesion_no_se_consulta_el_historial(client, historial_juridico) -> None:
    client.cookies.clear()

    respuesta = client.get(
        f"/api/convenios/{historial_juridico['convenio'].id}/revisiones"
    )

    assert respuesta.status_code == 401
