"""HT-05. Consulta del contenido de versiones anteriores del convenio.

Verifica el contrato de `GET /convenios/{id}/versiones` y
`GET /convenios/{id}/versiones/{numero}`: metadatos históricos, solo lectura,
permisos, error controlado y compatibilidad con versiones previas a HT-13.
"""

from copy import deepcopy

import pytest
from sqlalchemy import func, select

from backend.core.roles import CodigoRol
from backend.models.auditoria import Auditoria
from backend.models.borrador_convenio import BorradorConvenio
from backend.models.convenio import Convenio
from backend.models.enums import ContextoVersionConvenio
from backend.models.proceso_firmas_convenio import ProcesoFirmasConvenio
from backend.models.revision_convenio import RevisionConvenio
from backend.models.version_convenio import VersionConvenio


def _ruta(convenio_id: int) -> str:
    return f"/api/convenios/{convenio_id}"


def _con_parrafo(contenido: dict, texto: str) -> dict:
    nuevo = deepcopy(contenido)
    nuevo["content"].append(
        {"type": "paragraph", "content": [{"type": "text", "text": texto}]}
    )
    return nuevo


def _guardar_avance(client, convenio_id: int, texto: str) -> dict:
    actual = client.get(f"{_ruta(convenio_id)}/elaboracion").json()
    respuesta = client.patch(
        f"{_ruta(convenio_id)}/elaboracion",
        json={
            "contenido": _con_parrafo(actual["contenido"], texto),
            "expected_revision": actual["revision_borrador"],
        },
    )
    assert respuesta.status_code == 200, respuesta.text
    return respuesta.json()


def _finalizar(client, convenio_id: int, revision_borrador: int) -> None:
    respuesta = client.post(
        f"{_ruta(convenio_id)}/elaboracion/finalizar",
        json={"expected_revision": revision_borrador},
    )
    assert respuesta.status_code == 200, respuesta.text


def _estado_convenio(db, convenio_id: int) -> dict[str, object]:
    """Todo lo que la consulta histórica no debe alterar (CA-06)."""
    db.expire_all()
    convenio = db.get(Convenio, convenio_id)
    borrador = db.scalar(
        select(BorradorConvenio).where(BorradorConvenio.convenio_id == convenio_id)
    )
    return {
        "version_actual": convenio.version_actual,
        "borrador": (
            (borrador.revision, borrador.contenido, borrador.actualizado_en)
            if borrador is not None
            else None
        ),
        "versiones": [
            (v.id, v.numero, v.contenido, v.snapshot_metadata, v.contexto)
            for v in db.scalars(
                select(VersionConvenio)
                .where(VersionConvenio.convenio_id == convenio_id)
                .order_by(VersionConvenio.numero)
            )
        ],
        "revisiones": [
            (r.id, r.estado, r.version_convenio_id, r.version_resultado_id)
            for r in db.scalars(
                select(RevisionConvenio)
                .where(RevisionConvenio.convenio_id == convenio_id)
                .order_by(RevisionConvenio.id)
            )
        ],
        "procesos_firmas": [
            (p.id, p.version_convenio_id)
            for p in db.scalars(
                select(ProcesoFirmasConvenio).where(
                    ProcesoFirmasConvenio.convenio_id == convenio_id
                )
            )
        ],
        "auditoria": db.scalar(select(func.count()).select_from(Auditoria)),
    }


# ---- CA-01, CA-02 y CA-04: consulta con contenido y metadatos -------------------


def test_ca02_ca04_la_version_devuelve_contenido_y_metadatos_del_snapshot(
    client, db, gestor, convenio_listo
) -> None:
    avance = _guardar_avance(client, convenio_listo.id, "Cláusula enviada")
    _finalizar(client, convenio_listo.id, avance["revision_borrador"])
    db.expire_all()
    version = db.scalar(
        select(VersionConvenio).where(
            VersionConvenio.convenio_id == convenio_listo.id,
            VersionConvenio.numero == 2,
        )
    )

    respuesta = client.get(f"{_ruta(convenio_listo.id)}/versiones/2")

    assert respuesta.status_code == 200, respuesta.text
    cuerpo = respuesta.json()
    assert cuerpo["numero"] == 2
    assert cuerpo["autor"] == {
        "id": gestor.id,
        "nombre_completo": gestor.nombre_completo,
        "correo": gestor.correo,
    }
    assert cuerpo["etapa"]["id"] == version.etapa_id
    assert cuerpo["etapa"]["codigo"] == version.etapa.codigo
    assert cuerpo["contexto"] == ContextoVersionConvenio.FINALIZACION.value
    assert cuerpo["creado_en"] is not None
    assert cuerpo["contenido"] == version.contenido
    assert cuerpo["snapshot_metadata"] == version.snapshot_metadata


def test_ca01_una_version_anterior_conserva_su_contenido_original(
    client, db, convenio_listo
) -> None:
    original = client.get(f"{_ruta(convenio_listo.id)}/versiones/1").json()
    avance = _guardar_avance(client, convenio_listo.id, "Texto posterior")
    _finalizar(client, convenio_listo.id, avance["revision_borrador"])

    anterior = client.get(f"{_ruta(convenio_listo.id)}/versiones/1")

    assert anterior.status_code == 200, anterior.text
    assert anterior.json() == original
    assert "Texto posterior" not in str(anterior.json()["contenido"])


# ---- CA-05: el historial solo lista versiones formales --------------------------


def test_ca05_el_historial_excluye_los_guardados_de_avance(
    client, db, convenio_listo
) -> None:
    _guardar_avance(client, convenio_listo.id, "Primer avance")
    avance = _guardar_avance(client, convenio_listo.id, "Segundo avance")

    listado = client.get(f"{_ruta(convenio_listo.id)}/versiones")
    assert listado.status_code == 200, listado.text
    assert [item["numero"] for item in listado.json()] == [1]

    _finalizar(client, convenio_listo.id, avance["revision_borrador"])

    listado = client.get(f"{_ruta(convenio_listo.id)}/versiones").json()
    assert [item["numero"] for item in listado] == [2, 1]
    assert [item["contexto"] for item in listado] == [
        ContextoVersionConvenio.FINALIZACION.value,
        ContextoVersionConvenio.INICIALIZACION.value,
    ]
    # El listado es un resumen: el contenido solo se entrega al abrir la versión.
    assert all("contenido" not in item for item in listado)


# ---- CA-06: la consulta es de solo lectura --------------------------------------


def test_ca06_consultar_versiones_no_modifica_el_convenio(
    client, db, convenio_listo
) -> None:
    avance = _guardar_avance(client, convenio_listo.id, "Enviado a Jurídica")
    _finalizar(client, convenio_listo.id, avance["revision_borrador"])
    # Deja un borrador vivo con trabajo posterior a la versión formal.
    db.expire_all()
    convenio = db.get(Convenio, convenio_listo.id)
    db.add(
        BorradorConvenio(
            convenio_id=convenio.id,
            contenido=_con_parrafo(avance["contenido"], "Borrador en curso"),
            revision=1,
            actualizado_por_id=convenio.creado_por_id,
        )
    )
    db.commit()
    antes = _estado_convenio(db, convenio_listo.id)
    assert antes["borrador"] is not None
    assert antes["revisiones"]

    for _ in range(2):
        assert client.get(f"{_ruta(convenio_listo.id)}/versiones").status_code == 200
        assert client.get(f"{_ruta(convenio_listo.id)}/versiones/1").status_code == 200
        assert client.get(f"{_ruta(convenio_listo.id)}/versiones/2").status_code == 200
    assert client.get(f"{_ruta(convenio_listo.id)}/versiones/99").status_code == 404

    assert _estado_convenio(db, convenio_listo.id) == antes


# ---- CA-07: permisos y error controlado -----------------------------------------


@pytest.mark.parametrize(
    "codigo_rol", [CodigoRol.ADMINISTRADOR_ORI, CodigoRol.GESTOR_ORI]
)
def test_ca07_gestor_y_administrador_consultan_versiones(
    client, crear_usuario, entrar_como, convenio_listo, codigo_rol
) -> None:
    entrar_como(crear_usuario(codigo_rol))

    assert client.get(f"{_ruta(convenio_listo.id)}/versiones").status_code == 200
    assert client.get(f"{_ruta(convenio_listo.id)}/versiones/1").status_code == 200


@pytest.mark.parametrize(
    "codigo_rol", [CodigoRol.SOLICITANTE_INTERNO, CodigoRol.SOLICITANTE_EXTERNO]
)
def test_ca07_un_rol_sin_permiso_recibe_403(
    client, crear_usuario, entrar_como, convenio_listo, codigo_rol
) -> None:
    entrar_como(crear_usuario(codigo_rol))

    for ruta in ("versiones", "versiones/1"):
        respuesta = client.get(f"{_ruta(convenio_listo.id)}/{ruta}")
        assert respuesta.status_code == 403, respuesta.text
        assert "contenido" not in respuesta.text


def test_ca07_sin_sesion_recibe_401(client, convenio_listo) -> None:
    client.cookies.clear()

    for ruta in ("versiones", "versiones/1"):
        assert client.get(f"{_ruta(convenio_listo.id)}/{ruta}").status_code == 401


def test_ca07_revisor_fuera_de_su_alcance_no_ve_las_versiones(
    client, revisor, entrar_como, convenio_listo
) -> None:
    # Revisor ORI tiene `convenios.ver`, pero solo sobre convenios en revisión
    # jurídica que le corresponden; el resto responde como inexistente.
    entrar_como(revisor)

    for ruta in ("versiones", "versiones/1"):
        respuesta = client.get(f"{_ruta(convenio_listo.id)}/{ruta}")
        assert respuesta.status_code == 404, respuesta.text
        assert respuesta.json() == {"detail": "Convenio no encontrado"}


def test_ca07_version_inexistente_responde_404_controlado(
    client, convenio_listo
) -> None:
    for numero in (0, 2, 999):
        respuesta = client.get(f"{_ruta(convenio_listo.id)}/versiones/{numero}")
        assert respuesta.status_code == 404, respuesta.text
        assert respuesta.json() == {"detail": "Versión de convenio no encontrada"}

    invalida = client.get(f"{_ruta(convenio_listo.id)}/versiones/no-numero")
    assert invalida.status_code == 422


def test_ca07_convenio_inexistente_responde_404_controlado(client, gestor) -> None:
    for ruta in ("versiones", "versiones/1"):
        respuesta = client.get(f"{_ruta(999_999_999)}/{ruta}")
        assert respuesta.status_code == 404, respuesta.text
        assert respuesta.json() == {"detail": "Convenio no encontrado"}


def test_ca07_una_version_de_otro_convenio_no_se_expone(
    client, gestor, crear_convenio, convenio_listo
) -> None:
    otro = crear_convenio(
        gestor,
        tipo_convenio_id=convenio_listo.tipo_convenio_id,
        implicacion_financiera=convenio_listo.implicacion_financiera,
        duracion_meses=convenio_listo.duracion_meses,
        fecha_inicio=convenio_listo.fecha_inicio,
        fecha_vencimiento=convenio_listo.fecha_vencimiento,
    )
    texto_exclusivo = "Contenido exclusivo del segundo convenio"
    avance = _guardar_avance(client, otro.id, texto_exclusivo)
    _finalizar(client, otro.id, avance["revision_borrador"])

    otra_version = client.get(f"{_ruta(otro.id)}/versiones/2")
    assert otra_version.status_code == 200, otra_version.text
    assert texto_exclusivo in str(otra_version.json()["contenido"])

    # V2 solo existe en el segundo convenio; su número no permite acceder a ella
    # bajo el ID del primero, aunque el usuario tenga acceso a ambos convenios.
    respuesta = client.get(f"{_ruta(convenio_listo.id)}/versiones/2")
    assert respuesta.status_code == 404, respuesta.text
    assert respuesta.json() == {"detail": "Versión de convenio no encontrada"}
    assert texto_exclusivo not in respuesta.text
    assert "contenido" not in respuesta.json()

    listado = client.get(f"{_ruta(convenio_listo.id)}/versiones")
    assert listado.status_code == 200, listado.text
    assert [version["numero"] for version in listado.json()] == [1]


# ---- CA-08: versiones existentes antes de HT-13 ---------------------------------


def test_ca08_una_version_de_guardado_previa_a_ht13_se_lista_y_se_consulta(
    client, db, convenio_listo
) -> None:
    db.expire_all()
    convenio = db.get(Convenio, convenio_listo.id)
    inicial = db.scalar(
        select(VersionConvenio).where(
            VersionConvenio.convenio_id == convenio.id, VersionConvenio.numero == 1
        )
    )
    # Antes de HT-13 cada guardado creaba una versión formal con contexto
    # GUARDADO, sin plantilla y con un snapshot de menos campos.
    contenido = _con_parrafo(inicial.contenido, "Guardado heredado")
    snapshot_legado = {"objeto": "Objeto heredado", "duracion_meses": 12}
    legado = VersionConvenio(
        convenio_id=convenio.id,
        numero=2,
        contenido=contenido,
        snapshot_metadata=snapshot_legado,
        autor_id=inicial.autor_id,
        etapa_id=inicial.etapa_id,
        contexto=ContextoVersionConvenio.GUARDADO.value,
        plantilla_id=None,
    )
    db.add(legado)
    convenio.version_actual = 2
    db.commit()

    listado = client.get(f"{_ruta(convenio.id)}/versiones")
    assert listado.status_code == 200, listado.text
    assert [item["numero"] for item in listado.json()] == [2, 1]
    assert listado.json()[0]["contexto"] == ContextoVersionConvenio.GUARDADO.value
    assert listado.json()[0]["plantilla"] is None

    detalle = client.get(f"{_ruta(convenio.id)}/versiones/2")
    assert detalle.status_code == 200, detalle.text
    assert detalle.json()["contenido"] == contenido
    assert detalle.json()["snapshot_metadata"] == snapshot_legado
    assert detalle.json()["plantilla"] is None


def test_ca08_un_snapshot_vacio_se_devuelve_tal_cual(
    client, db, convenio_listo
) -> None:
    db.expire_all()
    version = db.scalar(
        select(VersionConvenio).where(
            VersionConvenio.convenio_id == convenio_listo.id,
            VersionConvenio.numero == 1,
        )
    )
    version.snapshot_metadata = {}
    db.commit()

    detalle = client.get(f"{_ruta(convenio_listo.id)}/versiones/1")

    assert detalle.status_code == 200, detalle.text
    assert detalle.json()["snapshot_metadata"] == {}
    db.expire_all()
    assert db.get(VersionConvenio, version.id).snapshot_metadata == {}
