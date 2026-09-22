from urllib.parse import parse_qs

import httpx
import pytest
from pydantic import SecretStr

from backend.services import documentos
from backend.services.documentos import (
    AlmacenDocumentosLocal,
    AlmacenDocumentosMicrosoftGraph,
    ErrorAlmacenDocumentos,
)


class GraphFalso:
    def __init__(self, storage_root: str = "staging", *, fallar_upload: bool = False):
        self.storage_root = storage_root
        self.fallar_upload = fallar_upload
        self.peticiones: list[httpx.Request] = []
        self.carpetas = {("root", "solicitudes"): "folder-solicitudes"}
        self.archivos: dict[str, str] = {}

    def responder(self, request: httpx.Request) -> httpx.Response:
        self.peticiones.append(request)
        ruta = request.url.path
        if request.url.host == "login.microsoftonline.com":
            return httpx.Response(200, json={"access_token": "access-token"})
        if ruta.endswith("/me/drive/special/approot"):
            return httpx.Response(
                200,
                json={"id": "approot", "parentReference": {"driveId": "drive"}},
            )
        if ruta.endswith(f"/items/approot:/{self.storage_root}"):
            return httpx.Response(200, json={"id": "root"})
        if request.method == "GET" and ":/" in ruta:
            item_id, nombre = ruta.rsplit("/items/", 1)[1].split(":/", 1)
            carpeta_id = self.carpetas.get((item_id, nombre))
            if carpeta_id is not None:
                return httpx.Response(200, json={"id": carpeta_id, "folder": {}})
            archivo_id = self.archivos.get(nombre)
            if item_id == "root" and archivo_id is not None:
                return httpx.Response(200, json={"id": archivo_id})
            return httpx.Response(404, json={"error": {"code": "itemNotFound"}})
        if request.method == "POST" and ruta.endswith("/children"):
            parent_id = ruta.rsplit("/items/", 1)[1].split("/", 1)[0]
            nombre = (
                request.extensions["json"]["name"]
                if "json" in request.extensions
                else None
            )
            if nombre is None:
                import json

                nombre = json.loads(request.content)["name"]
            carpeta_id = f"folder-{nombre}"
            self.carpetas[(parent_id, nombre)] = carpeta_id
            return httpx.Response(201, json={"id": carpeta_id, "folder": {}})
        if request.method == "PUT" and ruta.endswith(":/content"):
            if self.fallar_upload:
                return httpx.Response(503, json={"error": {"code": "unavailable"}})
            nombre = ruta.split(":/", 1)[1].removesuffix(":/content")
            self.archivos[f"solicitudes/123/{nombre}"] = "documento"
            return httpx.Response(201, json={"id": "documento"})
        if request.method == "DELETE" and ruta.endswith("/items/documento"):
            self.archivos.clear()
            return httpx.Response(204)
        return httpx.Response(500, json={"ruta_no_simulada": ruta})


def _almacen(graph: GraphFalso) -> AlmacenDocumentosMicrosoftGraph:
    return AlmacenDocumentosMicrosoftGraph(
        "client-id",
        "client-secret",
        "refresh-token",
        graph.storage_root,
        cliente=httpx.Client(transport=httpx.MockTransport(graph.responder)),
    )


@pytest.fixture(autouse=True)
def limpiar_cache_storage():
    documentos.get_almacen_documentos.cache_clear()
    yield
    documentos.get_almacen_documentos.cache_clear()


def test_provider_local_permitido_en_development(monkeypatch, tmp_path):
    monkeypatch.setattr(documentos.settings, "app_env", "development")
    monkeypatch.setattr(documentos.settings, "document_storage_provider", "local")
    monkeypatch.setattr(documentos.settings, "document_storage_path", str(tmp_path))

    assert isinstance(documentos.get_almacen_documentos(), AlmacenDocumentosLocal)


def test_provider_local_rechazado_fuera_de_development(monkeypatch):
    monkeypatch.setattr(documentos.settings, "app_env", "production")
    monkeypatch.setattr(documentos.settings, "document_storage_provider", "local")

    with pytest.raises(RuntimeError, match="solo está permitido en development"):
        documentos.get_almacen_documentos()


def test_provider_graph_exige_configuracion_completa(monkeypatch):
    monkeypatch.setattr(
        documentos.settings, "document_storage_provider", "microsoft_graph"
    )
    monkeypatch.setattr(documentos.settings, "microsoft_client_id", None)
    monkeypatch.setattr(documentos.settings, "microsoft_client_secret", None)
    monkeypatch.setattr(documentos.settings, "microsoft_refresh_token", None)
    monkeypatch.setattr(documentos.settings, "microsoft_storage_root", None)

    with pytest.raises(RuntimeError, match="MICROSOFT_CLIENT_ID"):
        documentos.get_almacen_documentos()


def test_graph_rechaza_storage_root_invalido():
    with pytest.raises(ValueError, match="staging o production"):
        AlmacenDocumentosMicrosoftGraph(
            "client-id", "client-secret", "refresh-token", "development"
        )


def test_graph_renueva_access_token_ante_401():
    tokens_emitidos = 0

    def responder(request):
        nonlocal tokens_emitidos
        if request.url.host == "login.microsoftonline.com":
            tokens_emitidos += 1
            return httpx.Response(
                200, json={"access_token": f"token-{tokens_emitidos}"}
            )
        if request.url.path.endswith("/me/drive/special/approot"):
            if request.headers["Authorization"] == "Bearer token-1":
                return httpx.Response(401)
            return httpx.Response(
                200,
                json={"id": "approot", "parentReference": {"driveId": "drive"}},
            )
        return httpx.Response(200, json={"id": "root"})

    almacen = AlmacenDocumentosMicrosoftGraph(
        "client-id",
        "client-secret",
        "refresh-token",
        "staging",
        cliente=httpx.Client(transport=httpx.MockTransport(responder)),
    )

    assert almacen.storage_root == "staging"
    assert tokens_emitidos == 2


@pytest.mark.parametrize("storage_root", ["staging", "production"])
def test_graph_obtiene_token_approot_guarda_consulta_y_elimina(storage_root):
    graph = GraphFalso(storage_root)
    almacen = _almacen(graph)
    clave = "solicitudes/123/hash.pdf"

    almacen.guardar(clave, b"contenido")
    assert almacen.existe(clave) is True
    almacen.eliminar(clave)
    assert almacen.existe(clave) is False
    almacen.eliminar(clave)

    token_request = graph.peticiones[0]
    formulario = parse_qs(token_request.content.decode())
    assert token_request.url == documentos.AlmacenDocumentosMicrosoftGraph.TOKEN_URL
    assert formulario == {
        "grant_type": ["refresh_token"],
        "client_id": ["client-id"],
        "client_secret": ["client-secret"],
        "refresh_token": ["refresh-token"],
        "scope": [AlmacenDocumentosMicrosoftGraph.SCOPE],
    }
    assert any(
        request.url.path.endswith("/me/drive/special/approot")
        for request in graph.peticiones
    )
    assert any(
        request.url.path.endswith(f"/items/approot:/{storage_root}")
        for request in graph.peticiones
    )
    assert any(request.method == "PUT" for request in graph.peticiones)
    assert any(request.method == "DELETE" for request in graph.peticiones)


@pytest.mark.parametrize(
    "clave", ["/solicitudes/a.pdf", "../a.pdf", "solicitudes/../a.pdf", "C:\\a.pdf"]
)
def test_graph_rechaza_claves_absolutas_y_traversal(clave):
    almacen = _almacen(GraphFalso())

    with pytest.raises(ValueError, match="Clave de almacenamiento inválida"):
        almacen.existe(clave)


def test_error_graph_no_escribe_en_filesystem_local(tmp_path):
    almacen = _almacen(GraphFalso(fallar_upload=True))

    with pytest.raises(ErrorAlmacenDocumentos, match="Microsoft Graph falló"):
        almacen.guardar("solicitudes/123/hash.pdf", b"contenido")

    assert list(tmp_path.iterdir()) == []


def test_provider_graph_construye_adaptador_con_secretos(monkeypatch):
    recibido = {}

    def constructor(**kwargs):
        recibido.update(kwargs)
        return object()

    monkeypatch.setattr(
        documentos.settings, "document_storage_provider", "microsoft_graph"
    )
    monkeypatch.setattr(documentos.settings, "microsoft_client_id", "client-id")
    monkeypatch.setattr(
        documentos.settings, "microsoft_client_secret", SecretStr("client-secret")
    )
    monkeypatch.setattr(
        documentos.settings, "microsoft_refresh_token", SecretStr("refresh-token")
    )
    monkeypatch.setattr(documentos.settings, "microsoft_storage_root", "staging")
    monkeypatch.setattr(documentos, "AlmacenDocumentosMicrosoftGraph", constructor)

    documentos.get_almacen_documentos()

    assert recibido == {
        "client_id": "client-id",
        "client_secret": "client-secret",
        "refresh_token": "refresh-token",
        "storage_root": "staging",
    }
