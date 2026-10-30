"""Compact compliance history shared by chain and mocked replay tests."""

import pytest

from app.dto.message_dto import ToolCallExtractDTO
from app.services.chat_history_service import ChatHistoryService


@pytest.fixture
def compliance_replay_payload() -> ToolCallExtractDTO:
    """Stored compliance calls with metadata that must not provide layers."""

    calls = [
        ("GetProjectTerritory", {"scenario_id": 772}),
        ("GetPhysicalObjects", {"physical_objects_names": ["Жилой дом"]}),
        (
            "GetServicesByGeometry",
            {
                "scenario_id": 772,
                "services_names": ["Школа"],
                "zones_layers": ["project_territory"],
                "layer_name": "Источники — Школа",
                "intersection_type": "intersects",
            },
        ),
        *[
            (
                "CreateRestrictionZones",
                {
                    "source_layer": "Источники — Школа",
                    "clip_layer": "project_territory",
                    "layer_name": f"Зона ограничения — {index}",
                    "geometry_mode": "buffer",
                    "distance_m": 500,
                    "properties": {
                        "applies_to": "Жилой дом" if index % 2 else "Школа",
                        "restriction_id": f"Норма {index}",
                        "template": "Проверка расстояния",
                        "provenance": {"source": "СП 42", "revision": "Версия 1"},
                    },
                },
            )
            for index in range(1, 6)
        ],
        (
            "GetServicesByGeometry",
            {
                "scenario_id": 772,
                "services_names": ["Школа"],
                "zones_layers": ["Зона ограничения — 1", "Зона ограничения — 3"],
                "layer_name": "Цели — Школа",
                "intersection_type": "intersects",
            },
        ),
        (
            "CheckDistanceFromSource",
            {
                "source_layer": "Источники — Школа",
                "targets": ["Жилой дом"],
                "geometry_mode": "buffered",
                "distance_m": 500,
            },
        ),
    ]
    restored = ChatHistoryService._tool_calls_from_part(
        {
            "payload": {
                "tool_calls": [
                    {"function": {"name": name, "arguments": arguments}}
                    for name, arguments in calls
                ]
            }
        }
    )
    return ToolCallExtractDTO(
        tool_call=restored[-1], previous_tool_calls=restored[:-1], scenario_id=772
    )


@pytest.fixture
def geometry_replay_payload() -> ToolCallExtractDTO:
    """Match gMART's function-wrapped calls, aliases and source buffer."""

    calls = [
        ("GetProjectTerritory", {"scenario_id": 772}),
        (
            "GetServicesByGeometry",
            {
                "scenario_id": 772,
                "services_names": ["Школа"],
                "zones_layers": ["project_territory"],
                "layer_name": "Источники — Школа",
                "buffer_m": 500,
                "intersection_type": "intersects",
            },
        ),
        (
            "CreateRestrictionZones",
            {
                "source_layer": "Источники — Школа",
                "layer_name": "Зона ограничения — СП 42, п. 7.1",
                "geometry_mode": "buffer",
                "distance_m": 500,
                "properties": {"norm_id": "r1"},
            },
        ),
        (
            "GetServicesByGeometry",
            {
                "scenario_id": 772,
                "services_names": ["Театр"],
                "zones_layers": ["Зона ограничения — СП 42, п. 7.1"],
                "layer_name": "Цели — Театр",
                "buffer_m": 0,
                "intersection_type": "intersects",
            },
        ),
        (
            "CheckDistanceFromSource",
            {
                "source_layer": "Источники — Школа",
                "targets": ["Цели — Театр"],
                "geometry_mode": "buffered",
                "distance_m": 500,
                "predicate": "intersects",
                "violation_when": "matched",
                "result_mode": "both",
                "restriction_id": "r1",
                "template_version": 1,
                "provenance": {"restriction_id": "r1"},
                "input_revision": None,
            },
        ),
    ]
    restored = ChatHistoryService._tool_calls_from_part(
        {
            "payload": {
                "tool_calls": [
                    {"function": {"name": name, "arguments": arguments}}
                    for name, arguments in calls
                ]
            }
        }
    )
    return ToolCallExtractDTO(
        tool_call=restored[-1], previous_tool_calls=restored[:-1], scenario_id=772
    )
