import json
import socket
import struct


class RPCBase:
    """Helper to handle length-prefixed JSON over TCP."""

    @staticmethod
    def send_framed(sock, payload):
        data = json.dumps(payload).encode('utf-8')
        # Header: 4-byte unsigned int (!) Big-Endian (I)
        header = struct.pack('!I', len(data))
        sock.sendall(header + data)

    @staticmethod
    def recv_framed(sock):
        header = sock.recv(4)
        if not header: return None
        length = struct.unpack('!I', header)[0]

        chunks = []
        received = 0
        while received < length:
            chunk = sock.recv(min(length - received, 4096))
            if not chunk: break
            chunks.append(chunk)
            received += len(chunk)
        return json.loads(b''.join(chunks).decode('utf-8'))


class ParkingClientStub(RPCBase):
    """LAYER 1: The Client Proxy (You use this)."""

    def __init__(self, host='localhost', port=8000):
        self.host, self.port = host, port

    def _call(self, method, *args):
        # Packing the Request
        request = {"method": method, "args": args, "rpcId": 1}

        with socket.create_connection((self.host, self.port), timeout=5) as s:
            self.send_framed(s, request)
            response = self.recv_framed(s)

            if response.get("error"):
                raise Exception(response["error"])
            return response.get("result")

    def getAvailability(self, lotId):
        return self._call("getAvailability", lotId)

    def reserve(self, lotId, plate):
        return self._call("reserve", lotId, plate)

class ParkingServerSkeleton(RPCBase):
    """LAYER 2: The Server Dispatcher (Your team uses this)."""

    def __init__(self, service_instance):
        self.service = service_instance

    def handle_client(self, conn):
        request = self.recv_framed(conn)
        if request:
            method_name = request.get("method")
            args = request.get("args", [])

            # Use 'getattr' to find the method on the actual logic class
            try:
                func = getattr(self.service, method_name)
                result = func(*args)
                self.send_framed(conn, {"result": result, "error": None})
            except Exception as e:
                self.send_framed(conn, {"result": None, "error": str(e)})
        conn.close()