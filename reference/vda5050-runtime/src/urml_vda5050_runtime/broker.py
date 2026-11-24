"""Broker security: TLS and credentials for the MQTT connection.

A deployment that protects the conduit between the URML host and the
broker (IEC 62443 zones and conduits, docs/security/iec-62443.md) sets, in
the adapter config:

    broker_port: 8883
    broker_tls:
      ca_file: certs/broker-ca.pem        # omit to trust the system store
      client_cert_file: certs/urml.pem    # both or neither: mutual TLS
      client_key_file: certs/urml.key
    broker_username: urml-fleet
    broker_password_env: URML_BROKER_PASSWORD

TLS is 1.2 or newer, and the broker's certificate and host name are always
checked; there is no switch to turn either off. The password never appears
in the config file: `broker_password_env` names the environment variable
that holds it, read when the adapter connects. Relative certificate paths
resolve against the config file's folder.
"""

from __future__ import annotations

import ipaddress
import os
import re
import ssl
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, model_validator

_ENV_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class BrokerTls(BaseModel):
    """TLS settings for the broker connection."""

    model_config = ConfigDict(extra="forbid")

    ca_file: str | None = Field(
        None, description="PEM file of the CA that signed the broker's certificate. None: the system trust store."
    )
    client_cert_file: str | None = Field(None, description="PEM client certificate, for mutual TLS.")
    client_key_file: str | None = Field(None, description="PEM key of the client certificate.")

    @model_validator(mode="after")
    def _cert_and_key_together(self) -> BrokerTls:
        if (self.client_cert_file is None) != (self.client_key_file is None):
            raise ValueError("broker_tls: give client_cert_file and client_key_file together, or neither")
        return self

    def resolved(self, base: Path) -> BrokerTls:
        """A copy whose relative paths are taken from `base`."""

        def fix(path: str | None) -> str | None:
            if path is None or Path(path).is_absolute():
                return path
            return str(base / path)

        return BrokerTls(
            ca_file=fix(self.ca_file),
            client_cert_file=fix(self.client_cert_file),
            client_key_file=fix(self.client_key_file),
        )

    def context(self) -> ssl.SSLContext:
        """A client context: TLS 1.2 or newer, certificate and host name verified."""
        for path in (self.ca_file, self.client_cert_file, self.client_key_file):
            if path is not None and not Path(path).is_file():
                raise ValueError(f"broker_tls: file not found: {path}")
        context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH, cafile=self.ca_file)
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        context.check_hostname = True
        context.verify_mode = ssl.CERT_REQUIRED
        if self.client_cert_file is not None and self.client_key_file is not None:
            context.load_cert_chain(self.client_cert_file, self.client_key_file)
        return context


def check_env_name(name: str | None) -> str | None:
    if name is not None and not _ENV_NAME.match(name):
        raise ValueError(f"broker_password_env must name an environment variable, not {name!r}")
    return name


def password_from_env(name: str | None) -> str | None:
    """The password the named environment variable holds; an error when it is not set."""
    if name is None:
        return None
    value = os.environ.get(name)
    if value is None:
        raise ValueError(f"broker_password_env names {name}, which is not set in the environment")
    return value


def is_loopback(host: str) -> bool:
    """Whether `host` is this machine, where plain MQTT never leaves the host."""
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


__all__ = ["BrokerTls", "check_env_name", "is_loopback", "password_from_env"]
