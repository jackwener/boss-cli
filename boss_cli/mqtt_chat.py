"""MQTT-based chat for geek (job seeker) side.

BOSS 直聘 uses MQTT over WSS for real-time messaging.
- Server: ws6.zhipin.com:443/chatws  (or ws.zhipin.com / ws2.zhipin.com)
- Auth:   userName = wt2_cookie + "|0",  password = wt2_cookie
- Topic:  "chat"  (QoS 1, retain=True)
- Payload: Protobuf-encoded TechwolfChatProtocol

Proto schema (reverse-engineered from JS bundle):
  TechwolfChatProtocol { type=1, messages=[TechwolfMessage] }
  TechwolfMessage { from=User, to=User, type=1, mid, cmid, body=Body }
  TechwolfUser    { uid, name, source }
  TechwolfMessageBody { type=1, templateId=1, text }
"""

from __future__ import annotations

import logging
import struct
import threading
import time
from typing import Callable

logger = logging.getLogger(__name__)


# ── Minimal Protobuf encoder ──────────────────────────────────────────────────
# Wire types: 0=varint, 1=64-bit, 2=length-delimited, 5=32-bit

def _varint(value: int) -> bytes:
    """Encode a non-negative integer as a protobuf varint."""
    bits = []
    value = int(value)
    while True:
        b = value & 0x7F
        value >>= 7
        if value:
            bits.append(b | 0x80)
        else:
            bits.append(b)
            break
    return bytes(bits)


def _field(field_num: int, wire_type: int, data: bytes) -> bytes:
    tag = (field_num << 3) | wire_type
    return _varint(tag) + data


def _field_varint(field_num: int, value: int) -> bytes:
    return _field(field_num, 0, _varint(value))


def _field_bytes(field_num: int, data: bytes) -> bytes:
    return _field(field_num, 2, _varint(len(data)) + data)


def _field_string(field_num: int, s: str) -> bytes:
    return _field_bytes(field_num, s.encode("utf-8"))


def encode_user(uid: int, encrypt_uid: str = "", source: int = 0) -> bytes:
    """TechwolfUser { uid=1, name=2, source=7 }"""
    buf = _field_varint(1, uid)
    if encrypt_uid:
        buf += _field_string(2, encrypt_uid)
    if source:
        buf += _field_varint(7, source)
    return buf


def encode_body(text: str) -> bytes:
    """TechwolfMessageBody { type=1, templateId=2, text=3 }"""
    buf = _field_varint(1, 1)   # type = 1 (text)
    buf += _field_varint(2, 1)  # templateId = 1
    buf += _field_string(3, text)
    return buf


def encode_message(
    from_uid: int,
    from_encrypt_uid: str,
    to_uid: int,
    to_encrypt_uid: str,
    text: str,
    temp_id: int,
) -> bytes:
    """TechwolfMessage { from=1, to=2, type=3, mid=4, cmid=11, body=6 }"""
    from_bytes = encode_user(from_uid, from_encrypt_uid)
    to_bytes = encode_user(to_uid, to_encrypt_uid)
    body_bytes = encode_body(text)

    buf = _field_bytes(1, from_bytes)   # from
    buf += _field_bytes(2, to_bytes)    # to
    buf += _field_varint(3, 1)          # type = 1 (text)
    buf += _field_varint(4, temp_id)    # mid
    buf += _field_varint(11, temp_id)   # cmid
    buf += _field_bytes(6, body_bytes)  # body
    return buf


def encode_chat_protocol(message_bytes: bytes) -> bytes:
    """TechwolfChatProtocol { type=1, messages=3 }"""
    buf = _field_varint(1, 1)               # type = 1 (message)
    buf += _field_bytes(3, message_bytes)   # messages[0]
    return buf


def build_text_message(
    from_uid: int,
    from_encrypt_uid: str,
    to_uid: int,
    to_encrypt_uid: str,
    text: str,
) -> bytes:
    """Build a complete Protobuf-encoded chat message payload."""
    temp_id = int(time.time() * 1000)
    msg = encode_message(from_uid, from_encrypt_uid, to_uid, to_encrypt_uid, text, temp_id)
    return encode_chat_protocol(msg)


# ── MQTT client ───────────────────────────────────────────────────────────────

class BossMQTTChat:
    """MQTT over WSS client for sending messages as a geek (job seeker).

    Auth:
        userName = page_token + "|0"   (from /wapi/zpuser/wap/getUserInfo.json → token)
        password = wt2                 (from /wapi/zppassport/get/wt → zpData.wt2)
        Cookie header required for WS 101 upgrade (403 without it)

    Usage:
        with BossMQTTChat(page_token, wt2, cookies) as chat:
            chat.send(from_uid, from_enc, to_uid, to_enc, "Hello!")
    """

    WS_SERVERS = ["ws6.zhipin.com", "ws.zhipin.com", "ws2.zhipin.com"]
    PORT = 443
    PATH = "/chatws"
    TOPIC = "chat"

    def __init__(self, page_token: str, wt2: str, cookies: dict | None = None, timeout: float = 10.0):
        self._page_token = page_token
        self._wt2 = wt2
        self._cookies = cookies or {}
        self._timeout = timeout
        self._client = None
        self._connected = threading.Event()
        self._error: str | None = None

    def _make_client(self):
        try:
            import paho.mqtt.client as mqtt
        except ImportError as exc:
            raise RuntimeError(
                "paho-mqtt is required for chat. Run: pip install paho-mqtt"
            ) from exc

        import uuid
        client_id = f"ws-{''.join(str(uuid.uuid4()).replace('-','').upper()[:16])}"

        # paho-mqtt 2.x requires CallbackAPIVersion
        try:
            client = mqtt.Client(
                callback_api_version=mqtt.CallbackAPIVersion.VERSION1,
                client_id=client_id,
                transport="websockets",
            )
        except AttributeError:
            # paho-mqtt 1.x
            client = mqtt.Client(client_id=client_id, transport="websockets")

        client.tls_set()

        # Build Cookie header — required for 101 upgrade (403 without it)
        cookie_str = "; ".join(f"{k}={v}" for k, v in self._cookies.items())
        client.ws_set_options(
            path=self.PATH,
            headers={
                "Origin": "https://www.zhipin.com",
                "Cookie": cookie_str,
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36"
                ),
            },
        )
        client.username_pw_set(
            username=f"{self._page_token}|0",
            password=self._wt2,
        )
        client.on_connect = self._on_connect
        client.on_disconnect = self._on_disconnect
        client.on_message = self._on_message
        return client

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            logger.debug("MQTT connected")
            self._connected.set()
        else:
            self._error = f"MQTT connect failed: rc={rc}"
            self._connected.set()

    def _on_disconnect(self, client, userdata, rc):
        logger.debug("MQTT disconnected: rc=%d", rc)

    def _on_message(self, client, userdata, msg):
        logger.debug("MQTT message on %s: %d bytes", msg.topic, len(msg.payload))

    def __enter__(self) -> "BossMQTTChat":
        self._client = self._make_client()
        server = self.WS_SERVERS[0]
        logger.debug("Connecting to %s:%d%s", server, self.PORT, self.PATH)
        self._client.connect(server, self.PORT, keepalive=25)
        self._client.loop_start()
        if not self._connected.wait(timeout=self._timeout):
            self._client.loop_stop()
            raise RuntimeError(f"MQTT connection timed out after {self._timeout}s")
        if self._error:
            self._client.loop_stop()
            raise RuntimeError(self._error)
        return self

    def __exit__(self, *args):
        if self._client:
            self._client.loop_stop()
            self._client.disconnect()
            self._client = None

    def send(
        self,
        from_uid: int,
        from_encrypt_uid: str,
        to_uid: int,
        to_encrypt_uid: str,
        text: str,
    ) -> None:
        """Send a text message via MQTT."""
        if not self._client:
            raise RuntimeError("Not connected. Use as context manager.")
        payload = build_text_message(from_uid, from_encrypt_uid, to_uid, to_encrypt_uid, text)
        result = self._client.publish(self.TOPIC, payload, qos=1, retain=False)
        result.wait_for_publish(timeout=self._timeout)
        logger.debug("Message published: mid=%d", result.mid)
