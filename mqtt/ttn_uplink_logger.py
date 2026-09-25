#!/usr/bin/env python3
"""
Subscribe to The Things Stack (TTN v3) MQTT server and log every uplink
to a daily tab-separated file (YYYYMMDD.txt).

Adapted from:
https://github.com/descartes/TheThingsStack-Integration-Starters (MQTT-to-Tab-Python3)

Credentials are read from environment variables:
  TTN_USER      application id, e.g. my-app@ttn
  TTN_API_KEY   API key generated in TTN console > Integrations > MQTT
  TTN_REGION    cluster host (default: eu1.cloud.thethings.network)
  TTN_DEVICE_ID optional, subscribe to a single device instead of all
"""
import csv
import json
import os
import random
import sys
from datetime import datetime

import paho.mqtt.client as mqtt

USER = os.getenv("TTN_USER", "")
PASSWORD = os.getenv("TTN_API_KEY", "")
PUBLIC_TLS_ADDRESS = os.getenv("TTN_REGION", "eu1.cloud.thethings.network")
PUBLIC_TLS_ADDRESS_PORT = 8883
DEVICE_ID = os.getenv("TTN_DEVICE_ID", "")

# QoS 0 = at most once, 1 = at least once, 2 = exactly once
QOS = 0
DEBUG = False


def get_value(obj, key):
    try:
        return obj[key]
    except (KeyError, TypeError):
        return "-"


def stop(client):
    client.disconnect()
    print("\nExit")
    sys.exit(0)


def save_to_file(uplink):
    """Append one uplink (with radio metadata) to today's log file."""
    ids = uplink["end_device_ids"]
    device_id = ids["device_id"]
    application_id = ids["application_ids"]["application_id"]
    received_at = uplink["received_at"]

    if "uplink_message" not in uplink:
        return
    msg = uplink["uplink_message"]
    f_port = get_value(msg, "f_port")
    if f_port == "-":
        return

    row = [
        received_at, application_id, device_id, f_port,
        get_value(msg, "f_cnt"),
        get_value(msg["rx_metadata"][0], "rssi"),
        get_value(msg["rx_metadata"][0], "snr"),
        get_value(msg["settings"], "data_rate_index"),
        get_value(msg, "consumed_airtime"),
        msg["frm_payload"],
        str(get_value(msg, "decoded_payload")),
    ]

    path = datetime.now().strftime("%Y%m%d") + ".txt"
    new_file = not os.path.isfile(path)
    with open(path, "a", newline="") as f:
        writer = csv.writer(f, dialect="excel-tab")
        if new_file:
            writer.writerow(["received_at", "application_id", "device_id", "f_port", "f_cnt", "rssi", "snr",
                             "data_rate_index", "consumed_airtime", "frm_payload", "decoded_payload"])
        writer.writerow(row)


def on_connect(client, userdata, flags, rc):
    print("\nConnected to MQTT broker" if rc == 0 else f"\nConnection failed, rc = {rc}")


def on_message(client, userdata, message):
    print(f"\nMessage received on '{message.topic}' (QoS {message.qos})")
    parsed = json.loads(message.payload)
    if DEBUG:
        print(json.dumps(parsed, indent=4))
    save_to_file(parsed)


def on_subscribe(client, userdata, mid, granted_qos):
    print(f"\nSubscribed (mid = {mid}, QoS = {granted_qos})")


def on_disconnect(client, userdata, rc):
    print(f"\nDisconnected (rc = {rc})")


def main():
    if not USER or not PASSWORD:
        sys.exit("Set TTN_USER and TTN_API_KEY environment variables first.")

    client = mqtt.Client(f"python-mqtt-{random.randint(0, 1000)}")
    client.on_connect = on_connect
    client.on_subscribe = on_subscribe
    client.on_message = on_message
    client.on_disconnect = on_disconnect

    client.username_pw_set(USER, PASSWORD)
    client.tls_set()  # TLS with the system CA store

    print(f"Connecting to {PUBLIC_TLS_ADDRESS}:{PUBLIC_TLS_ADDRESS_PORT}")
    client.connect(PUBLIC_TLS_ADDRESS, PUBLIC_TLS_ADDRESS_PORT, 60)

    topic = f"v3/{USER}/devices/{DEVICE_ID}/up" if DEVICE_ID else "#"
    print(f"Subscribing to '{topic}'")
    client.subscribe(topic, QOS)

    try:
        while True:
            client.loop(10)
            print(".", end="", flush=True)
    except KeyboardInterrupt:
        stop(client)


if __name__ == "__main__":
    main()
