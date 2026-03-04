from __future__ import annotations

import json
import socket
import threading
import queue
import time
from dataclasses import dataclass
from typing import Dict, Optional, Set, Tuple
from RPC_Framework import RPCBase, ParkingClientStub

def _load_rpc_port(default: int = 5000) -> int:
    try:
        with open("config.json", "r", encoding="utf-8") as f:
            cfg = json.load(f)
        return int(cfg.get("server_port", default))
    except Exception:
        return int(default)

@dataclass(frozen=True)
class AvailabilityEvent:
    type: str
    lotId: str
    free: int
    reason: str
    ts: float

class _SubscriberConn:
    def __init__(self, client_id: str, conn: socket.socket, addr: Tuple[str, int], max_queue: int, policy: str):
        self.client_id = client_id
        self.conn = conn
        self.addr = addr
        self.queue: "queue.Queue[dict]" = queue.Queue(maxsize=max_queue)
        self.policy = policy
        self._closed = threading.Event()

    def close(self) -> None:
        if self._closed.is_set():
            return
        self._closed.set()
        try:
            self.conn.shutdown(socket.SHUT_RDWR)
        except Exception:
            pass
        try:
            self.conn.close()
        except Exception:
            pass

    def closed(self) -> bool:
        return self._closed.is_set()

class PubSubHub:
    def __init__(self, subscriber_queue_size: int = 256, backpressure_policy: str = "drop_oldest"):
        if backpressure_policy not in ("drop_oldest", "disconnect"):
            raise ValueError("backpressure_policy must be 'drop_oldest' or 'disconnect'")

        self._subs_by_lot: Dict[str, Set[str]] = {}
        self._conn_by_client: Dict[str, _SubscriberConn] = {}
        self._qsize = int(subscriber_queue_size)
        self._policy = backpressure_policy
        self._lock = threading.RLock()

    # RPC subscription methods
    def subscribe(self, client_id: str, lot_id: str) -> bool:
        with self._lock:
            self._subs_by_lot.setdefault(lot_id, set()).add(client_id)
        return True

    def unsubscribe(self, client_id: str, lot_id: str) -> bool:
        with self._lock:
            s = self._subs_by_lot.get(lot_id)
            if not s or client_id not in s:
                return False
            s.remove(client_id)
            if not s:
                self._subs_by_lot.pop(lot_id, None)
        return True

    def unsubscribe_all(self, client_id: str) -> None:
        with self._lock:
            for lot_id in list(self._subs_by_lot.keys()):
                self._subs_by_lot[lot_id].discard(client_id)
                if not self._subs_by_lot[lot_id]:
                    self._subs_by_lot.pop(lot_id, None)

    # event stream connection management
    def register_event_stream(self, client_id: str, conn: socket.socket, addr: Tuple[str, int]) -> _SubscriberConn:
        with self._lock:
            old = self._conn_by_client.get(client_id)
            if old:
                old.close()
            sub = _SubscriberConn(client_id, conn, addr, max_queue=self._qsize, policy=self._policy)
            self._conn_by_client[client_id] = sub
            return sub

    def _drop_event_stream_if_same(self, client_id: str, sub: _SubscriberConn) -> None:
        with self._lock:
            if self._conn_by_client.get(client_id) is sub:
                self._conn_by_client.pop(client_id, None)

    # publishing
    def publish_availability(self, lot_id: str, free: int, reason: str = "update") -> None:
        ev = AvailabilityEvent("availability", str(lot_id), int(free), str(reason), time.time())

        payload = {
            "type": ev.type,
            "lotId": ev.lotId,
            "free": ev.free,
            "reason": ev.reason,
            "ts": ev.ts
        }

        with self._lock:
            client_ids = list(self._subs_by_lot.get(ev.lotId, set()))
            subs = [self._conn_by_client.get(cid) for cid in client_ids]

        for sub in subs:
            if not sub or sub.closed():
                continue
            self._enqueue(sub, payload)

    def _enqueue(self, sub: _SubscriberConn, payload: dict) -> None:
        try:
            sub.queue.put_nowait(payload)
            return
        except queue.Full:
            pass

        if sub.policy == "disconnect":
            sub.close()
            return

        # drop oldest
        try:
            sub.queue.get_nowait()
        except queue.Empty:
            pass
        try:
            sub.queue.put_nowait(payload)
        except queue.Full:
            sub.close()

class EventServer:
    def __init__(self, hub: PubSubHub, host: str = "0.0.0.0", port: int = 8002):
        self.hub = hub
        self.host = host
        self.port = int(port)
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self, daemon: bool = True) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._serve, name="EventServer", daemon=daemon)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _serve(self) -> None:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as srv:
            srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            srv.bind((self.host, self.port))
            srv.listen()

            while not self._stop.is_set():
                try:
                    srv.settimeout(1.0)
                    conn, addr = srv.accept()
                except socket.timeout:
                    continue
                except Exception:
                    continue

                threading.Thread(target=self._handle_conn, args=(conn, addr), daemon=True).start()

    def _handle_conn(self, conn: socket.socket, addr: Tuple[str, int]) -> None:
        client_id: Optional[str] = None
        sub: Optional[_SubscriberConn] = None
        try:
            conn.settimeout(10.0)
            hello = RPCBase.recv_framed(conn)
            if not isinstance(hello, dict) or "clientId" not in hello:
                return

            client_id = str(hello["clientId"])
            conn.settimeout(None)

            sub = self.hub.register_event_stream(client_id, conn, addr)

            while not sub.closed():
                try:
                    payload = sub.queue.get(timeout=1.0)
                except queue.Empty:
                    continue
                try:
                    RPCBase.send_framed(conn, payload)
                except Exception:
                    sub.close()
                    break
        finally:
            if client_id and sub:
                self.hub._drop_event_stream_if_same(client_id, sub)
            try:
                conn.close()
            except Exception:
                pass

class EventStreamClient:
    def __init__(self, client_id: str, host: str = "localhost", port: int = 8002):
        self.client_id = str(client_id)
        self.host = host
        self.port = int(port)
        self.sock: Optional[socket.socket] = None

    def connect(self, timeout: float = 5.0) -> None:
        self.sock = socket.create_connection((self.host, self.port), timeout=timeout)
        RPCBase.send_framed(self.sock, {"clientId": self.client_id})

    def recv_event(self) -> Optional[dict]:
        if not self.sock:
            raise RuntimeError("Not connected")
        return RPCBase.recv_framed(self.sock)

    def close(self) -> None:
        if self.sock:
            self.sock.close()
            self.sock = None

class PubSubServiceMixin:
    pubsub_hub: PubSubHub

    def subscribe(self, clientId: str, lotId: str) -> bool:
        return self.pubsub_hub.subscribe(str(clientId), str(lotId))

    def unsubscribe(self, clientId: str, lotId: str) -> bool:
        return self.pubsub_hub.unsubscribe(str(clientId), str(lotId))

class PubSubClientStub(ParkingClientStub):
    def __init__(self, host: str = "localhost", port: Optional[int] = None):
        if port is None:
            port = _load_rpc_port(5000)
        super().__init__(host=host, port=port)

    def subscribe(self, clientId: str, lotId: str) -> bool:
        return self._call("subscribe", clientId, lotId)

    def unsubscribe(self, clientId: str, lotId: str) -> bool:
        return self._call("unsubscribe", clientId, lotId)