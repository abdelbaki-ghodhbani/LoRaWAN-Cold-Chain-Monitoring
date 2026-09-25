/*
 * LoRaWAN Temperature Node - Cold Chain Monitoring
 *
 * Board   : Arduino Uno + Dragino LoRa Shield (SX1276, EU868)
 * Sensor  : DS18B20 digital temperature sensor (1-Wire, pin 8)
 * Stack   : IBM LMIC (Arduino port)
 * Network : The Things Network (TTN), ABP activation
 *
 * Reads the temperature every TX_INTERVAL seconds and sends it as a
 * 4-byte IEEE-754 float (little-endian) uplink on FPort 1.
 */

#include <lmic.h>
#include <hal/hal.h>
#include <OneWire.h>
#include <DallasTemperature.h>

/*************************************
 * LoRaWAN configuration (ABP)
 * Replace with the keys of your device from the TTN console
 * (MSB format for NWKSKEY / APPSKEY).
 *************************************/
static const u1_t NWKSKEY[16] = { 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00 };
static const u1_t APPSKEY[16] = { 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00 };
static const u4_t DEVADDR = 0x00000000;

static osjob_t sendjob;
const unsigned TX_INTERVAL = 60;   // seconds between uplinks

/* Dragino LoRa Shield pin mapping */
const lmic_pinmap lmic_pins = {
    .nss = 10,
    .rxtx = LMIC_UNUSED_PIN,
    .rst = 9,
    .dio = {2, 6, 7},
};

/*************************************
 * Temperature sensor configuration
 *************************************/
OneWire ow(8);                       // DS18B20 data pin
DallasTemperature temp_sensor(&ow);

/* OTAA callbacks: unused with ABP, but required by LMIC */
void os_getArtEui(u1_t* buf) { }
void os_getDevEui(u1_t* buf) { }
void os_getDevKey(u1_t* buf) { }

void do_send(osjob_t* j);

/* LoRaWAN event callback: schedule the next uplink after each transmission */
void onEvent(ev_t ev) {
    if (ev == EV_TXCOMPLETE) {
        Serial.println(F("EV_TXCOMPLETE (includes waiting for RX windows)"));
        os_setTimedCallback(&sendjob, os_getTime() + sec2osticks(TX_INTERVAL), do_send);
    }
}

/* Read the sensor and queue an uplink */
void do_send(osjob_t* j) {
    temp_sensor.requestTemperatures();
    float temperatureC = temp_sensor.getTempCByIndex(0);

    Serial.print(F("Temperature: "));
    Serial.println(temperatureC);

    /* Payload: temperature as a 4-byte float */
    static uint8_t message[4];
    memcpy(&message[0], &temperatureC, sizeof(temperatureC));

    if (LMIC.opmode & OP_TXRXPEND) {
        Serial.println(F("OP_TXRXPEND, not sending"));
    } else {
        LMIC_setTxData2(1, message, sizeof(message), 0);   // FPort 1, unconfirmed
        Serial.println(F("Sending uplink packet..."));
    }
}

void setup() {
    Serial.begin(115200);
    Serial.println(F("Starting..."));

    /* LMIC initialisation */
    os_init();
    LMIC_reset();
    LMIC_setSession(0x1, DEVADDR, (xref2u1_t)NWKSKEY, (xref2u1_t)APPSKEY);
    LMIC_setLinkCheckMode(0);         // disable link-check validation
    LMIC.dn2Dr = DR_SF9;              // TTN uses SF9 for the RX2 window
    LMIC_setDrTxpow(DR_SF7, 14);      // SF7, 14 dBm

    temp_sensor.begin();

    do_send(&sendjob);                // first uplink
}

void loop() {
    os_runloop_once();                // run the LMIC scheduler
}
