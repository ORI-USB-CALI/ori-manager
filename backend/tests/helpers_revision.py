"""Revision vigente para clientes HTTP de prueba que no simulan ediciones obsoletas."""


def revision_actual(client, ruta_finalizar: str) -> int:
    respuesta = client.get(ruta_finalizar.removesuffix("/finalizar"))
    # Los escenarios de permisos/entidades inexistentes no pueden leer el editor.
    if respuesta.status_code != 200:
        return 0
    return respuesta.json()["revision_borrador"]
