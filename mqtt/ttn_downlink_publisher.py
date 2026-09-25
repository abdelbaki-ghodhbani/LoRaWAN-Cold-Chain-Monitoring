#!/usr/bin/env python3
"""
Publish a downlink to a LoRaWAN end device through The Things Stack (TTN v3) MQTT server.

Credentials are read from environment variables:
  TTN_USER, TTN_API_KEY, TTN_REGION (optional), TTN_DEVICE_ID (required)

Usage:
  python ttn_downlink_publisher.py [hex_payload] [f_port]
  python ttn_downlink_publisher.py 01 3
"""
import json
import os
import random
import sys
from base64 import b64encode

import paho.mqtt.client as mqtt

USER = os.getenv("TTN_USER", "")
PASSWORD = os.getenv("TTN_API_KEY", "")
PUBLIC_TLS_ADDRESS = os.getenv("TTN_REGION", "eu1.cloud.thethings.network")
PUBLIC_TLS_ADDRESS_PORT = 8883
DEVICE_ID = os.getenv("TTN_DEVICE_ID", "")
QOS = 0


def main():
    if not (USER and PASSWORD and DEVICE_ID):
        sys.exit("Set TTN_USER, TTN_API_KEY and TTN_DEVICE_ID environment variables first.")

    hex_payload = sys.argv[1] if len(sys.argv) > 1 else "00"
    f_port = int(sys.argv[2]) if len(sys.argv) > 2 else 3

    client = mqtt.Client(f"python-mqtt-{random.randint(0, 1000)}")
    client.username_pw_set(USER, PASSWORD)
    client.tls_set()
    client.connect(PUBLIC_TLS_ADDRESS, PUBLIC_TLS_ADDRESS_PORT, 60)
    client.loop_start()

    topic = f"v3/{USER}/devices/{DEVICE_ID}/down/push"
    b64 = b64encode(bytes.fromhex(hex_payload)).decode()
    msg = json.dumps({"downlinks": [{"f_port": f_port, "frm_payload": b64, "priority": "NORMAL"}]})

    info = client.publish(topic, msg, QOS)
    info.wait_for_publish()
    print(("Sent " if info.rc == 0 else "Failed to send ") + msg + " to " + topic)

    client.loop_stop()
    client.disconnect()


if __name__ == "__main__":
    main()
