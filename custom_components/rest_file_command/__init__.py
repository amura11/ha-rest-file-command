"""Support for exposing regular REST commands as services."""

from __future__ import annotations

import os
import logging
from http import HTTPStatus
from json.decoder import JSONDecodeError
from typing import Any

import aiohttp
from aiohttp import hdrs
import voluptuous as vol

from homeassistant.const import (
    CONF_HEADERS,
    CONF_METHOD,
    CONF_PASSWORD,
    CONF_PAYLOAD,
    CONF_TIMEOUT,
    CONF_URL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    SERVICE_RELOAD,
)
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.reload import async_integration_yaml_config
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.service import async_set_service_schema

DOMAIN = "rest_file_command"

_LOGGER = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 10
DEFAULT_METHOD = "post"
DEFAULT_VERIFY_SSL = True

SUPPORT_REST_METHODS = ["get", "patch", "post", "put", "delete"]

CONF_CONTENT_TYPE = "content_type"
CONF_FILE = "file"

COMMAND_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_URL): cv.template,
        vol.Optional(CONF_METHOD, default=DEFAULT_METHOD): vol.All(
            vol.Lower, vol.In(SUPPORT_REST_METHODS)
        ),
        vol.Optional(CONF_HEADERS): vol.Schema({cv.string: cv.template}),
        vol.Inclusive(CONF_USERNAME, "authentication"): cv.string,
        vol.Inclusive(CONF_PASSWORD, "authentication"): cv.string,
        vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): vol.Coerce(int),
        vol.Optional(CONF_CONTENT_TYPE): cv.string,
        vol.Optional(CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL): cv.boolean,
    }
)

CALL_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_FILE): cv.string
    }
)

CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: cv.schema_with_slug_keys(COMMAND_SCHEMA)}, extra=vol.ALLOW_EXTRA
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the REST command component."""

    async def reload_service_handler(service: ServiceCall) -> None:
        """Remove all rest_commands and load new ones from config."""
        conf = await async_integration_yaml_config(hass, DOMAIN)

        # conf will be None if the configuration can't be parsed
        if conf is None:
            return

        existing = hass.services.async_services_for_domain(DOMAIN)
        for existing_service in existing:
            if existing_service == SERVICE_RELOAD:
                continue
            hass.services.async_remove(DOMAIN, existing_service)

        for name, command_config in conf[DOMAIN].items():
            async_register_rest_command(name, command_config)

    @callback
    def async_register_rest_command(name: str, command_config: dict[str, Any]) -> None:
        """Create service for rest command."""
        websession = async_get_clientsession(
            hass, command_config[CONF_VERIFY_SSL])
        timeout = command_config[CONF_TIMEOUT]
        method = command_config[CONF_METHOD]
        template_url = command_config[CONF_URL]

        auth = None
        if CONF_USERNAME in command_config:
            username = command_config[CONF_USERNAME]
            password = command_config.get(CONF_PASSWORD, "")
            auth = aiohttp.BasicAuth(username, password=password)

        template_headers = command_config.get(CONF_HEADERS, {})

        content_type = command_config.get(CONF_CONTENT_TYPE)

        async def async_service_handler(service: ServiceCall) -> ServiceResponse:
            """Execute a shell command service."""
            request_url = template_url.async_render(
                variables=service.data, parse_result=False
            )

            file_path = service.data.get("file")
            if not os.path.exists(file_path):
                raise HomeAssistantError(f"File not found: {file_path}")

            headers = {}
            for header_name, template_header in template_headers.items():
                headers[header_name] = template_header.async_render(
                    variables=service.data, parse_result=False
                )

            if content_type:
                headers[hdrs.CONTENT_TYPE] = content_type

            try:
                file = {"file": open(file_path, "rb")}

                async with getattr(websession, method)(
                    request_url,
                    data=file,
                    auth=auth,
                    headers=headers or None,
                    timeout=timeout,
                ) as response:
                    if response.status < HTTPStatus.BAD_REQUEST:
                        _LOGGER.debug(
                            "Success. Url: %s. Status code: %d.",
                            response.url,
                            response.status
                        )
                    else:
                        _LOGGER.warning(
                            "Error. Url: %s. Status code %d.",
                            response.url,
                            response.status
                        )

                    if not service.return_response:
                        return None

                    _content = None
                    try:
                        if response.content_type == "application/json":
                            _content = await response.json()
                        else:
                            _content = await response.text()
                    except (JSONDecodeError, AttributeError) as err:
                        raise HomeAssistantError(
                            translation_domain=DOMAIN,
                            translation_key="decoding_error",
                            translation_placeholders={
                                "request_url": request_url,
                                "decoding_type": "JSON",
                            },
                        ) from err

                    except UnicodeDecodeError as err:
                        raise HomeAssistantError(
                            translation_domain=DOMAIN,
                            translation_key="decoding_error",
                            translation_placeholders={
                                "request_url": request_url,
                                "decoding_type": "text",
                            },
                        ) from err
                    return {"content": _content, "status": response.status}

            except TimeoutError as err:
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="timeout",
                    translation_placeholders={"request_url": request_url},
                ) from err

            except aiohttp.ClientError as err:
                _LOGGER.error("Error fetching data: %s", err)
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="client_error",
                    translation_placeholders={"request_url": request_url},
                ) from err

        # register services
        hass.services.async_register(
            DOMAIN,
            name,
            async_service_handler,
            supports_response=SupportsResponse.OPTIONAL,
        )

        service_schema = {
            "name": name,
            "description": f"Sends a file to the RESTful API endpoint via a {method.upper()} request.",
            "fields": {
                "file": {
                    "name": "Upload File Path",
                    "description": "The path to the file to upload",
                    "required": True,
                    "example": "/config/www/image.jpg"
                }
            }
        }

        async_set_service_schema(hass, DOMAIN, name, service_schema)

    for name, command_config in config[DOMAIN].items():
        async_register_rest_command(name, command_config)

    hass.services.async_register(
        DOMAIN, SERVICE_RELOAD, reload_service_handler, schema=vol.Schema({})
    )

    return True
