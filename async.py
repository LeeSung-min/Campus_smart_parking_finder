import socket
import time
from RPC_Framework import RPCBase

class ParkingSensor(RPCBase):
    def __init__(self, host= 'localhost', port=8001):
        self.host = host
        self.port = port

    def send_update(self, lot_id, delta):
        """sends non-blocking occupency update (+1 or -1)"""
        payload = {
            "type": "UPDATE"
            "lostId": lot_id,
            "delta": delta,
        "timestamp": time.time()
        }

        try:
            with socket.create_connection((self.host, self.port), timeout=2) as s:
                self.send_framed(s, payload)
                print(f"[SENSOR] Sent: {lot_id} {delta:+d}")
        except Exception as e:
            print(f"[SENSOR] Error: {e}")

if __name__ == "__main__":
    sensor = ParkingSensor()
    sensor.send_update("Lot_A", 1)
