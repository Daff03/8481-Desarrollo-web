import stomp
import argparse
import json
from decimal import Decimal, InvalidOperation
import xml.etree.ElementTree as ET

DESTINO = "/queue/pedidos"

def crear_mensaje(formato: str, pedido: dict, texto: str) -> tuple[str, str]:
    if formato == "texto":
        return texto, "text/plain; charset=utf-8"

def main():
    parser = argparse.ArgumentParser(description="Productor STOMP")
    parser.add_argument("--formato", choices=["texto", "fijo", "xml", "json"], required=True, help="Formato del mensaje a enviar")
    parser.add_argument("--mensaje", default="Hola desde el productor STOMP", help="Mensaje de texto libre")
    parser.add_argument("--cliente", default="Mario Rossi", help="Nombre del cliente (ASCII, max 20 caracteres)")
    parser.add_argument("--monto", default="123.45", help="Monto del pedido (decimal, max 99999999.99)")
    parser.add_argument("--host", default="127.0.0.1", help="Host del broker STOMP")
    parser.add_argument("--port", type = int, default=61613, help="Puerto del broker STOMP")
    parser.add_argument("--usuario", default="demo", help="Usuario de autenticación")
    parser.add_argument("--clave", default="demo123", help="Clave de autenticación")
    args = parser.parse_args()

    try:
        monto = Decimal(args.monto)
        if not monto.is_finite():
            raise ValueError("El monto debe ser un número finito")
    except InvalidOperation as exc:
        parser.error(f"Monto no es válido: {args.monto}")
    pedido = {"id": args.id, "cliente": args.cliente, "monto": str(monto)}
    try:
        cuerpo, mime = crear_mensaje(args.formato, pedido, args.mensaje)
    except ValueError as exc:
        parser.error(str(exc))

    # Enviar mensaje al broker STOMP
    conexion = stomp.Connection12([(args.host, args.port)], vhost="/")
    try:
        conexion.connect(args.usuario, args.clave, wait=True)
        conexion.send(
            destination=DESTINO,
            body=cuerpo,
            headers={
                "content-type": mime,
                "x-formato": args.formato,
                "persistent": "true",
            },
        )
        print(f"Mensaje enviado a {DESTINO} (formato={args.formato}):\n{cuerpo}")
    finally:
        if conexion.is_connected():
            conexion.disconnect()


if __name__ == "__main__":
    main()