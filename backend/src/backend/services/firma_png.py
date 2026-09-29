import base64
import binascii
import struct
import zlib
from hashlib import sha256

MAX_FIRMA_PNG_BYTES = 1024 * 1024
MAX_FIRMA_PNG_ANCHO = 8192
MAX_FIRMA_PNG_ALTO = 4096
MAX_FIRMA_PNG_PIXELES = 16_000_000
PREFIJO_FIRMA_PNG = "data:image/png;base64,"


class FirmaPngInvalida(ValueError):
    pass


def decodificar_firma_png(firma: str) -> tuple[bytes, str]:
    if not firma.startswith(PREFIJO_FIRMA_PNG):
        raise FirmaPngInvalida("La firma debe ser una imagen PNG válida")
    try:
        contenido = base64.b64decode(
            firma.removeprefix(PREFIJO_FIRMA_PNG), validate=True
        )
    except (binascii.Error, ValueError) as exc:
        raise FirmaPngInvalida("La firma debe ser una imagen PNG válida") from exc
    if len(contenido) > MAX_FIRMA_PNG_BYTES:
        raise FirmaPngInvalida(
            "La firma PNG está vacía, es inválida o supera el tamaño permitido"
        )
    validar_estructura_png(contenido)
    return contenido, sha256(contenido).hexdigest()


def validar_estructura_png(contenido: bytes) -> None:
    firma_png = b"\x89PNG\r\n\x1a\n"
    if not contenido.startswith(firma_png):
        raise FirmaPngInvalida("La firma debe ser una imagen PNG válida")

    posicion = len(firma_png)
    indice = 0
    tiene_idat = False
    tiene_iend = False
    while posicion < len(contenido):
        if len(contenido) - posicion < 12:
            raise FirmaPngInvalida("La firma PNG está truncada")
        longitud = struct.unpack(">I", contenido[posicion : posicion + 4])[0]
        tipo = contenido[posicion + 4 : posicion + 8]
        inicio_datos = posicion + 8
        fin_datos = inicio_datos + longitud
        fin_chunk = fin_datos + 4
        if fin_chunk > len(contenido):
            raise FirmaPngInvalida("La firma PNG está truncada")
        datos = contenido[inicio_datos:fin_datos]
        crc_esperado = struct.unpack(">I", contenido[fin_datos:fin_chunk])[0]
        crc_real = zlib.crc32(tipo)
        crc_real = zlib.crc32(datos, crc_real) & 0xFFFFFFFF
        if crc_real != crc_esperado:
            raise FirmaPngInvalida("La firma PNG tiene un CRC inválido")

        if indice == 0:
            if tipo != b"IHDR" or longitud != 13:
                raise FirmaPngInvalida("La firma PNG no contiene un IHDR válido")
            ancho, alto = struct.unpack(">II", datos[:8])
            if (
                ancho == 0
                or alto == 0
                or ancho > MAX_FIRMA_PNG_ANCHO
                or alto > MAX_FIRMA_PNG_ALTO
                or ancho * alto > MAX_FIRMA_PNG_PIXELES
            ):
                raise FirmaPngInvalida(
                    "Las dimensiones de la firma PNG no son válidas"
                )
        elif tipo == b"IHDR":
            raise FirmaPngInvalida("La firma PNG contiene más de un IHDR")

        if tipo == b"IDAT":
            tiene_idat = True
        if tipo == b"IEND":
            if longitud != 0 or fin_chunk != len(contenido):
                raise FirmaPngInvalida("La firma PNG no termina correctamente")
            tiene_iend = True
            posicion = fin_chunk
            break
        posicion = fin_chunk
        indice += 1

    if not tiene_idat or not tiene_iend or posicion != len(contenido):
        raise FirmaPngInvalida(
            "La firma PNG no contiene su estructura completa"
        )
