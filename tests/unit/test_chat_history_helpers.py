"""Unit tests for ChatHistoryService pure helpers and chain building.

None of these touch MongoDB: ``extract_tool_call_chain`` operates on a DTO, and
the remaining helpers are static/class methods. The service is constructed with
a mock database that is never queried.
"""

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from app.dto.message_dto import (
    MessageCreateDTO,
    MessagePartCreateDTO,
    ToolCallDTO,
    ToolCallExtractDTO,
)
from app.schema.chat_history_schema import ToolCallSchema
from app.services.chat_history_service import ChatHistoryService


@pytest.fixture
def service() -> ChatHistoryService:
    """Service with a mock database (DB is unused by these helpers)."""

    return ChatHistoryService(MagicMock())


class TestExtractToolCallChain:
    """Dependency-chain reconstruction for stored tool calls."""

    async def test_restriction_metadata_does_not_shadow_physical_objects(
        self,
        service: ChatHistoryService,
        compliance_replay_payload: ToolCallExtractDTO,
    ) -> None:
        chain = await service.extract_tool_call_chain(compliance_replay_payload)

        assert chain.missing_dependencies == []
        assert [step.tool_call.tool_name for step in chain.execution_chain] == [
            "GetProjectTerritory",
            "GetServicesByGeometry",
            "GetPhysicalObjects",
            "CheckDistanceFromSource",
        ]
        assert chain.execution_chain[1].tool_call.arguments["layer_name"] == (
            "Источники — Школа"
        )
        assert chain.execution_chain[-1].depends_on == [2, 3]

    async def test_presence_check_replays_only_target_zone_providers(
        self,
        service: ChatHistoryService,
        compliance_replay_payload: ToolCallExtractDTO,
    ) -> None:
        payload = ToolCallExtractDTO(
            tool_call=ToolCallDTO(
                step=10,
                tool_name="CheckPresenceWithin",
                arguments={
                    "objects_layer": "Жилой дом",
                    "required_neighbor_layers": ["Цели — Школа"],
                },
            ),
            previous_tool_calls=compliance_replay_payload.previous_tool_calls,
        )

        chain = await service.extract_tool_call_chain(payload)

        assert chain.missing_dependencies == []
        assert [step.tool_call.tool_name for step in chain.execution_chain] == [
            "GetPhysicalObjects",
            "GetProjectTerritory",
            "GetServicesByGeometry",
            "CreateRestrictionZones",
            "CreateRestrictionZones",
            "GetServicesByGeometry",
            "CheckPresenceWithin",
        ]
        zone_layers = [
            step.tool_call.arguments["layer_name"]
            for step in chain.execution_chain
            if step.tool_call.tool_name == "CreateRestrictionZones"
        ]
        targets = chain.execution_chain[-2]
        assert targets.tool_call.arguments["layer_name"] == "Цели — Школа"
        assert zone_layers == targets.tool_call.arguments["zones_layers"]
        assert targets.depends_on == [4, 5]
        assert chain.execution_chain[-1].depends_on == [1, 6]

    async def test_geometry_fetch_chain(
        self,
        service: ChatHistoryService,
        geometry_replay_payload: ToolCallExtractDTO,
    ) -> None:
        chain = await service.extract_tool_call_chain(geometry_replay_payload)

        assert chain.missing_dependencies == []
        assert [step.tool_call.tool_name for step in chain.execution_chain] == [
            "GetProjectTerritory",
            "GetServicesByGeometry",
            "CreateRestrictionZones",
            "GetServicesByGeometry",
            "CheckDistanceFromSource",
        ]
        assert [step.order for step in chain.execution_chain] == [1, 2, 3, 4, 5]
        assert chain.execution_chain[1].depends_on == [1]
        assert chain.execution_chain[2].depends_on == [2]
        assert chain.execution_chain[3].depends_on == [3]
        assert 4 in chain.execution_chain[4].depends_on

    async def test_single_tool_call_has_no_dependencies(
        self, service: ChatHistoryService
    ) -> None:
        payload = ToolCallExtractDTO(
            tool_call=ToolCallDTO(
                step=1,
                tool_name="GetServices",
                arguments={"services_names": ["school"]},
            )
        )

        chain = await service.extract_tool_call_chain(payload)

        assert chain.target.tool_name == "GetServices"
        assert chain.missing_dependencies == []
        assert len(chain.execution_chain) == 1
        assert chain.execution_chain[0].depends_on == []

    async def test_buffer_depends_on_previous_get_services(
        self, service: ChatHistoryService
    ) -> None:
        payload = ToolCallExtractDTO(
            tool_call=ToolCallDTO(
                step=2,
                tool_name="CreateBuffers",
                arguments={"buffer_info": {"school": {"radius": 500}}},
            ),
            previous_tool_calls=[
                ToolCallDTO(
                    step=1,
                    tool_name="GetServices",
                    arguments={"services_names": ["school"]},
                )
            ],
        )

        chain = await service.extract_tool_call_chain(payload)

        assert chain.missing_dependencies == []
        assert len(chain.execution_chain) == 2
        # GetServices runs first, CreateBuffers depends on it (chain position 1).
        get_services, create_buffers = chain.execution_chain
        assert get_services.tool_call.tool_name == "GetServices"
        assert create_buffers.tool_call.tool_name == "CreateBuffers"
        assert create_buffers.depends_on == [1]
        assert "school" in create_buffers.requires

    async def test_missing_dependency_is_reported(
        self, service: ChatHistoryService
    ) -> None:
        payload = ToolCallExtractDTO(
            tool_call=ToolCallDTO(
                step=1,
                tool_name="CreateBuffers",
                arguments={"buffer_info": {"school": {"radius": 500}}},
            )
        )

        chain = await service.extract_tool_call_chain(payload)

        assert chain.missing_dependencies == ["school"]

    async def test_unrelated_previous_call_is_pruned(
        self, service: ChatHistoryService
    ) -> None:
        """Only the dependency sub-graph of the target is kept."""

        payload = ToolCallExtractDTO(
            tool_call=ToolCallDTO(
                step=3,
                tool_name="CreateBuffers",
                arguments={"buffer_info": {"school": {"radius": 500}}},
            ),
            previous_tool_calls=[
                ToolCallDTO(
                    step=1,
                    tool_name="GetServices",
                    arguments={"services_names": ["school"]},
                ),
                ToolCallDTO(
                    step=2,
                    tool_name="GetPhysicalObjects",
                    arguments={"physical_objects_names": ["river"]},
                ),
            ],
        )

        chain = await service.extract_tool_call_chain(payload)

        tool_names = [step.tool_call.tool_name for step in chain.execution_chain]
        assert tool_names == ["GetServices", "CreateBuffers"]
        assert "GetPhysicalObjects" not in tool_names

    async def test_check_tool_replays_the_layers_it_reads(
        self, service: ChatHistoryService
    ) -> None:
        payload = ToolCallExtractDTO(
            tool_call=ToolCallDTO(
                step=3,
                tool_name="CheckDistanceFromSource",
                arguments={"source_layer": "Школа", "targets": ["Жилой дом"]},
            ),
            previous_tool_calls=[
                ToolCallDTO(
                    step=1,
                    tool_name="GetServices",
                    arguments={"services_names": ["Школа"]},
                ),
                ToolCallDTO(
                    step=2,
                    tool_name="GetPhysicalObjects",
                    arguments={"physical_objects_names": ["Жилой дом"]},
                ),
            ],
        )

        chain = await service.extract_tool_call_chain(payload)

        assert chain.missing_dependencies == []
        tool_names = [step.tool_call.tool_name for step in chain.execution_chain]
        assert tool_names == [
            "GetServices",
            "GetPhysicalObjects",
            "CheckDistanceFromSource",
        ]
        assert chain.execution_chain[-1].depends_on == [1, 2]

    async def test_zone_uses_the_latest_provider_of_a_layer(
        self, service: ChatHistoryService
    ) -> None:
        """Each zonal norm reads the zones fetched for it, not the first ones."""

        payload = ToolCallExtractDTO(
            tool_call=ToolCallDTO(
                step=1,
                tool_name="CreateRestrictionZones",
                arguments={
                    "layer_name": "Зона ограничения — СП 42, п. 7.6",
                    "geometry_mode": "geometry",
                    "source_layer": "functional_zones",
                    "clip_layer": "project_territory",
                },
            ),
            previous_tool_calls=[
                ToolCallDTO(
                    step=1,
                    tool_name="GetProjectTerritory",
                    arguments={"scenario_id": 772},
                ),
                ToolCallDTO(
                    step=1,
                    tool_name="GetFunctionalZones",
                    arguments={"scenario_id": 772, "zone_type_names": ["Жилая"]},
                ),
                ToolCallDTO(
                    step=1,
                    tool_name="GetFunctionalZones",
                    arguments={"scenario_id": 772, "zone_type_names": ["Рекреация"]},
                ),
            ],
        )

        chain = await service.extract_tool_call_chain(payload)

        assert chain.missing_dependencies == []
        calls = {
            step.tool_call.tool_name: step.tool_call for step in chain.execution_chain
        }
        assert len(chain.execution_chain) == 3
        assert chain.execution_chain[-1].tool_call.tool_name == "CreateRestrictionZones"
        assert "GetProjectTerritory" in calls
        assert calls["GetFunctionalZones"].arguments["zone_type_names"] == ["Рекреация"]


class TestProvidedAndRequiredRefs:
    """Special-cased provider/consumer extraction per tool name."""

    def test_restriction_zone_provides_only_output_layer(self) -> None:
        call = ToolCallSchema(
            tool_name="CreateRestrictionZones",
            arguments={
                "layer_name": "Зона ограничения — Школа",
                "source_layer": "Источники — Школа",
                "geometry_mode": "buffer",
                "distance_m": 500,
                "properties": {
                    "applies_to": "Жилой дом",
                    "restriction_id": "Норма 1",
                    "template": "Проверка расстояния",
                    "provenance": {"source": "СП 42"},
                },
            },
        )

        assert ChatHistoryService._provided_refs(call) == ["Зона ограничения — Школа"]

    @pytest.mark.parametrize(
        "tool_name",
        [
            "CheckDistanceFromSource",
            "CheckDistanceTable",
            "CheckPresenceWithin",
            "CheckObjectAttributeThreshold",
            "CheckAccessibilityWithin",
            "CheckZonalAttributeThreshold",
            "CheckZonalRatio",
        ],
    )
    @pytest.mark.parametrize("layer_name", [None, "Результат проверки"])
    def test_check_provides_only_explicit_output_layer(
        self, tool_name: str, layer_name: str | None
    ) -> None:
        arguments = {
            "objects_layer": "Жилой дом",
            "required_neighbor_layers": ["Цели — Школа"],
            "geometry_mode": "buffered",
            "distance_m": 500,
        }
        if layer_name is not None:
            arguments["layer_name"] = layer_name
        call = ToolCallSchema(tool_name=tool_name, arguments=arguments)

        assert ChatHistoryService._provided_refs(call) == (
            [layer_name] if layer_name else []
        )

    @pytest.mark.parametrize("layer_name", ["Источники — Школа", None])
    def test_geometry_fetch_provides_only_output_layer(
        self, layer_name: str | None
    ) -> None:
        call = ToolCallSchema(
            tool_name="GetServicesByGeometry",
            arguments={
                "services_names": ["Школа"],
                "zones_layers": ["project_territory"],
                "layer_name": layer_name,
                "intersection_type": "intersects",
            },
        )

        assert ChatHistoryService._provided_refs(call) == (
            [layer_name] if layer_name else []
        )
        assert ChatHistoryService._required_refs(call) == ["project_territory"]

    def test_geometry_fetch_requires_all_zone_layers(self) -> None:
        call = ToolCallSchema(
            tool_name="GetServicesByGeometry",
            arguments={
                "zones_layers": ["Зона 1", "Зона 2", "Зона 1"],
                "services_names": ["Театр"],
                "layer_name": "Цели — Театр",
            },
        )

        assert ChatHistoryService._required_refs(call) == ["Зона 1", "Зона 2"]

    def test_get_services_provides_service_names(self) -> None:
        call = ToolCallSchema(
            tool_name="GetServices", arguments={"services_names": ["school", "park"]}
        )

        assert ChatHistoryService._provided_refs(call) == ["school", "park"]

    def test_get_physical_objects_provides_object_names(self) -> None:
        call = ToolCallSchema(
            tool_name="GetPhysicalObjects",
            arguments={"physical_objects_names": ["river"]},
        )

        assert ChatHistoryService._provided_refs(call) == ["river"]

    def test_create_buffers_requires_buffer_info_keys(self) -> None:
        call = ToolCallSchema(
            tool_name="CreateBuffers",
            arguments={"buffer_info": {"school": {}, "park": {}}},
        )

        assert ChatHistoryService._required_refs(call) == ["school", "park"]

    def test_create_restrictions_collects_generators_and_objects(self) -> None:
        call = ToolCallSchema(
            tool_name="CreateRestrictions",
            arguments={"generators": ["road"], "objects": ["zone"]},
        )

        refs = ChatHistoryService._required_refs(call)
        assert "road" in refs
        assert "zone" in refs

    @pytest.mark.parametrize(
        ("tool_name", "layer"),
        [
            ("GetFunctionalZones", "functional_zones"),
            ("GetProjectTerritory", "project_territory"),
        ],
    )
    def test_fixed_name_layer_providers(self, tool_name: str, layer: str) -> None:
        call = ToolCallSchema(tool_name=tool_name, arguments={"scenario_id": 772})

        assert ChatHistoryService._provided_refs(call) == [layer]

    def test_layer_tool_requires_named_layers(self) -> None:
        call = ToolCallSchema(
            tool_name="CheckPresenceWithin",
            arguments={
                "objects_layer": "Жилой дом",
                "required_neighbor_layers": ["Школа", "Детский сад"],
                "distance_m": 500.0,
            },
        )

        assert ChatHistoryService._required_refs(call) == [
            "Жилой дом",
            "Школа",
            "Детский сад",
        ]

    @pytest.mark.parametrize(
        "tool_name", ["CheckObjectAttributeThreshold", "CheckAccessibilityWithin"]
    )
    def test_additional_checks_require_input_layers(self, tool_name: str) -> None:
        arguments = {"objects_layer": "Жилой дом"}
        if tool_name == "CheckObjectAttributeThreshold":
            arguments["project_layer"] = "project_territory"
            expected = ["Жилой дом", "project_territory"]
        else:
            arguments["required_neighbor_layers"] = ["Цели — Школа"]
            expected = ["Жилой дом", "Цели — Школа"]
        call = ToolCallSchema(tool_name=tool_name, arguments=arguments)

        assert ChatHistoryService._required_refs(call) == expected

    def test_explicit_depends_on_is_required(self) -> None:
        call = ToolCallSchema(
            tool_name="SomeTool", arguments={"depends_on": ["layer_a"]}
        )

        assert ChatHistoryService._required_refs(call) == ["layer_a"]


class TestToolCallFromPayload:
    """Tool name/arguments resolution from heterogeneous payload shapes."""

    def test_tool_name_field(self) -> None:
        call = ChatHistoryService._tool_call_from_payload(
            {"tool_name": "GetServices", "arguments": {"a": 1}}, 1
        )

        assert call.tool_name == "GetServices"
        assert call.arguments == {"a": 1}

    def test_name_field(self) -> None:
        call = ChatHistoryService._tool_call_from_payload({"name": "GetServices"}, 1)

        assert call.tool_name == "GetServices"

    def test_function_name_field(self) -> None:
        call = ChatHistoryService._tool_call_from_payload(
            {"function": {"name": "GetServices", "arguments": {"b": 2}}}, 1
        )

        assert call.tool_name == "GetServices"
        assert call.arguments == {"b": 2}

    def test_explicit_step_wins_over_fallback(self) -> None:
        call = ChatHistoryService._tool_call_from_payload(
            {"name": "GetServices", "step": 5}, fallback_step=9
        )

        assert call.step == 5

    def test_fallback_step_used_when_absent(self) -> None:
        call = ChatHistoryService._tool_call_from_payload(
            {"name": "GetServices"}, fallback_step=9
        )

        assert call.step == 9

    def test_missing_tool_name_raises_422(self) -> None:
        with pytest.raises(HTTPException) as exc_info:
            ChatHistoryService._tool_call_from_payload({"arguments": {}}, 1)

        assert exc_info.value.status_code == 422


class TestCompactToolCallHistory:
    @pytest.mark.parametrize(
        "tool_name",
        [
            "GetServicesByGeometry",
            "CreateRestrictionZones",
            "CheckDistanceFromSource",
            "CheckObjectAttributeThreshold",
            "CheckAccessibilityWithin",
        ],
    )
    @pytest.mark.parametrize("key", ["calls", "tool_calls"])
    @pytest.mark.parametrize("wrapped", [False, True])
    def test_persisted_arguments_exclude_layers(
        self, tool_name: str, key: str, wrapped: bool
    ) -> None:
        arguments = {
            "layer_name": "Цели — Театр",
            "zones_layers": ["Зона нормы"],
            "layers": {"Зона нормы": {"type": "FeatureCollection", "features": []}},
        }
        function = {"name": tool_name, "arguments": arguments}
        call = {"function": function} if wrapped else function
        payload = {key: [call], "description": "Повтор проверки"}
        message = MessageCreateDTO(
            role="assistant",
            parts=[MessagePartCreateDTO(kind="tool_call", payload=payload)],
        )

        stored = ChatHistoryService._build_parts(message, datetime.now(UTC))[0]
        restored = ChatHistoryService._tool_calls_from_part(stored)[0]

        assert restored.arguments == {
            "layer_name": "Цели — Театр",
            "zones_layers": ["Зона нормы"],
        }
        assert stored["payload"]["description"] == "Повтор проверки"
        assert "layers" in arguments
        assert (
            "layers"
            in message.parts[0]
            .payload[key][0]
            .get("function", message.parts[0].payload[key][0])["arguments"]
        )


class TestSmallHelpers:
    """Misc normalisation helpers."""

    @pytest.mark.parametrize(
        "value,expected",
        [
            (None, []),
            ("school", ["school"]),
            (["a", "b"], ["a", "b"]),
            ([1, None, 2], ["1", "2"]),
        ],
    )
    def test_string_list(self, value: object, expected: list[str]) -> None:
        assert ChatHistoryService._string_list(value) == expected

    def test_filter_candidates_includes_int_form(self) -> None:
        assert ChatHistoryService._filter_candidates("772") == ["772", 772]

    def test_filter_candidates_non_numeric(self) -> None:
        assert ChatHistoryService._filter_candidates("default") == ["default"]

    def test_normalize_ref_is_case_and_space_insensitive(self) -> None:
        assert ChatHistoryService._normalize_ref("  School ") == "school"


class TestDocumentMappers:
    """Mongo document -> response schema mapping."""

    def test_chat_summary_from_document(self) -> None:
        now = datetime.now(UTC)
        document = {
            "chat_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
            "title": "Chat",
            "scenario_id": "772",
            "project_id": 42,
            "metadata": {"source": "web"},
            "created_at": now,
            "updated_at": now,
        }

        summary = ChatHistoryService._chat_summary_from_document(document)

        assert summary.chat_id == document["chat_id"]
        assert summary.project_id == 42
        assert summary.metadata == {"source": "web"}

    def test_message_from_document_with_file_part(self) -> None:
        now = datetime.now(UTC)
        document = {
            "message_id": "8ec7f7b8-ec3f-4bb9-a6c4-89f7a930bda1",
            "chat_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
            "seq": 1,
            "role": "assistant",
            "parts": [
                {
                    "part_seq": 1,
                    "kind": "file",
                    "payload": {"url": "https://x/y.docx"},
                    "created_at": now,
                }
            ],
            "metadata": {},
            "created_at": now,
            "updated_at": now,
        }

        message = ChatHistoryService._message_from_document(document)

        assert message.role == "assistant"
        assert message.parts[0].kind == "file"
        assert message.parts[0].payload["url"] == "https://x/y.docx"
