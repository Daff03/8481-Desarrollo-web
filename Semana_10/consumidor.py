import stomp
import argparse
import json
import xml.etree.ElementTree as ET
import time

Destino = "/queue/pedidos"

def main():
    parser = argparse.ArgumentParser(description="Consumidor STOMP")
    parser.add_argument("--host", default="127.0.0.1", help="Host del broker STOMP")
    parser.add_argument("--port", type = int, default=61613, help="Puerto del broker STOMP")
    parser.add_argument("--usuario", default="demo", help="Usuario de autenticación")
    parser.add_argument("--clave", default="demo123", help="Clave de autenticación")
    args = parser.parse_args()

    conexion = stomp.Connection12([(args.host, args.port)], vhost="/")
    conexion.set_listener("pedido", Listener(conexion))

    try:
        conexion.connect(args.usuario, args.clave, wait=True)
        conexion.subscribe(destination=Destino, id="lector-pedidos", ack="client-individual", headers={"prefetch-count": "1"})
        print(f"Escuchando {Destino}. Presione Ctrl+C para salir.")
        while conexion.is_connected():
            time.sleep(0.5)

    except KeyboardInterrupt:   
        print("Deteniendo al consumidor...")
    finally:
        if conexion.is_connected():
            conexion.disconnect()






if __name__ == "__main__":
    main()