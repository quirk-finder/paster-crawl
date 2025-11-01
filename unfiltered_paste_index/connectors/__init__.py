"""Connector registry."""

from __future__ import annotations

from unfiltered_paste_index.connectors.base import BaseConnector, ConnectorConfig
from unfiltered_paste_index.connectors.controlc_com import ControlCConnector
from unfiltered_paste_index.connectors.paste_rs import PasteRSConnector
from unfiltered_paste_index.connectors.plaster_tymoon_eu import PlasterConnector
from unfiltered_paste_index.connectors.rentry_co import RentryConnector
from unfiltered_paste_index.connectors.snippet_host import SnippetHostConnector
from unfiltered_paste_index.connectors.text_is import TextIsConnector
from unfiltered_paste_index.connectors.textup_fr import TextUpConnector

CONNECTOR_REGISTRY: dict[str, type[BaseConnector]] = {
    TextIsConnector.site: TextIsConnector,
    SnippetHostConnector.site: SnippetHostConnector,
    RentryConnector.site: RentryConnector,
    ControlCConnector.site: ControlCConnector,
    TextUpConnector.site: TextUpConnector,
    PasteRSConnector.site: PasteRSConnector,
    PlasterConnector.site: PlasterConnector,
}

__all__ = ["CONNECTOR_REGISTRY", "BaseConnector", "ConnectorConfig"]
