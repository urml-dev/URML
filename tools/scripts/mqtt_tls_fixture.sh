#!/usr/bin/env bash
# Make a throwaway TLS setup for testing the MQTT runtimes against a real broker.
#
#   tools/scripts/mqtt_tls_fixture.sh OUT_DIR
#
# Writes into OUT_DIR:
#   ca.pem, ca.key            a test CA, valid one day
#   server.pem, server.key    the broker's certificate, for host name "localhost" only
#   client.pem, client.key    a client certificate (CN urml-client), for mutual TLS
#   other-ca.pem              a second CA that signed nothing here (an untrusted CA)
#   mosquitto.conf            listeners: 8883 TLS + password, 8884 TLS + client certificate
#   passwd.txt                "urml:<password>" in clear, for mosquitto_passwd -U
#   password                  the test password
#
# Everything is test material: keys are unencrypted and readable, and nothing
# here belongs on a real broker. CI turns passwd.txt into a hashed password
# file with mosquitto_passwd inside the broker container.
set -euo pipefail

out="${1:?usage: mqtt_tls_fixture.sh OUT_DIR}"
mkdir -p "$out"
cd "$out"

openssl req -x509 -newkey rsa:2048 -nodes -days 1 -subj "/CN=URML test CA" \
  -keyout ca.key -out ca.pem 2>/dev/null
openssl req -x509 -newkey rsa:2048 -nodes -days 1 -subj "/CN=URML other CA" \
  -keyout other-ca.key -out other-ca.pem 2>/dev/null

openssl req -newkey rsa:2048 -nodes -subj "/CN=localhost" -keyout server.key -out server.csr 2>/dev/null
printf "subjectAltName=DNS:localhost\nextendedKeyUsage=serverAuth\n" > server.ext
openssl x509 -req -in server.csr -CA ca.pem -CAkey ca.key -CAcreateserial -days 1 \
  -extfile server.ext -out server.pem 2>/dev/null

openssl req -newkey rsa:2048 -nodes -subj "/CN=urml-client" -keyout client.key -out client.csr 2>/dev/null
printf "extendedKeyUsage=clientAuth\n" > client.ext
openssl x509 -req -in client.csr -CA ca.pem -CAkey ca.key -CAcreateserial -days 1 \
  -extfile client.ext -out client.pem 2>/dev/null

password="test-$(openssl rand -hex 8)"
printf "%s" "$password" > password
printf "urml:%s\n" "$password" > passwd.txt
chmod 644 ./*.key

cat > mosquitto.conf <<'CONF'
per_listener_settings true

listener 8883
cafile /mosquitto/certs/ca.pem
certfile /mosquitto/certs/server.pem
keyfile /mosquitto/certs/server.key
tls_version tlsv1.2
allow_anonymous false
password_file /mosquitto/certs/passwd

listener 8884
cafile /mosquitto/certs/ca.pem
certfile /mosquitto/certs/server.pem
keyfile /mosquitto/certs/server.key
tls_version tlsv1.2
require_certificate true
use_identity_as_username true
allow_anonymous false
CONF

rm -f ./*.csr ./*.ext ./*.srl
echo "TLS test material in $out"
