"""Unit tests for ToolCallExecutionService pure helpers.

The MCP client is mocked for replay; no live server is needed. These also cover
the data-shaping helpers and the early 503 guard when no MCP URL is configured.
"""

from copy import deepcopy
from dataclasses import dataclass
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from pydantic import BaseModel

from app.dto.message_dto import ToolCallDTO, ToolCallExtractDTO
from app.schema.chat_history_schema import ToolCallSchema
from app.services.chat_history_service import ChatHistoryService
from app.services.tool_call_execution_service import ToolCallExecutionService


@dataclass
class _Point:
    x: int
    y: int


class _Model(BaseModel):
    name: str


class TestToPlainData:
    """Conversion of MCP/Pydantic/dataclass results to JSON-serialisable data."""

    def test_dataclass_to_dict(self) -> None:
        assert ToolCallExecutionService.to_plain_data(_Point(1, 2)) == {"x": 1, "y": 2}

    def test_pydantic_model_to_dict(self) -> None:
        assert ToolCallExecutionService.to_plain_data(_Model(name="a")) == {"name": "a"}

    def test_nested_structures(self) -> None:
        value = {"items": [_Point(1, 2), {"m": _Model(name="b")}]}

        assert ToolCallExecutionService.to_plain_data(value) == {
            "items": [{"x": 1, "y": 2}, {"m": {"name": "b"}}]
        }

    def test_scalar_passthrough(self) -> None:
        assert ToolCallExecutionService.to_plain_data(7) == 7


class TestBaseMeta:
    """scenario_id/project_id are merged into meta only when present."""

    def test_includes_ids_when_present(self) -> None:
        payload = ToolCallExtractDTO(
            tool_call=ToolCallDTO(tool_name="GetServices"),
            scenario_id=772,
            project_id=42,
            meta={"existing": True},
        )

        meta = ToolCallExecutionService._base_meta(payload)

        assert meta == {"existing": True, "scenario_id": 772, "project_id": 42}

    def test_omits_ids_when_absent(self) -> None:
        payload = ToolCallExtractDTO(tool_call=ToolCallDTO(tool_name="GetServices"))

        assert ToolCallExecutionService._base_meta(payload) == {}


class TestMetaForToolCall:
    """Geometry tools receive accumulated layers under tool-specific keys."""

    def test_create_buffers_gets_objects(self) -> None:
        layers = {"school": {"type": "FeatureCollection"}}
        meta = ToolCallExecutionService._meta_for_tool_call(
            ToolCallSchema(tool_name="CreateBuffers"), {"scenario_id": 1}, layers
        )

        assert meta == {"scenario_id": 1, "objects": layers}

    def test_create_restrictions_gets_layers(self) -> None:
        layers = {"road": {"type": "FeatureCollection"}}
        meta = ToolCallExecutionService._meta_for_tool_call(
            ToolCallSchema(tool_name="CreateRestrictions"), {}, layers
        )

        assert meta == {"layers": layers}

    def test_other_tool_gets_base_meta_only(self) -> None:
        base = {"scenario_id": 1}
        meta = ToolCallExecutionService._meta_for_tool_call(
            ToolCallSchema(tool_name="GetServices"), base, {"x": {}}
        )

        assert meta == base

    @pytest.mark.parametrize(
        "tool_name",
        [
            "CheckDistanceFromSource",
            "GetServicesByGeometry",
            "CheckObjectAttributeThreshold",
            "CheckAccessibilityWithin",
        ],
    )
    def test_compliance_tool_gets_layers(self, tool_name: str) -> None:
        layers = {"houses": {"type": "FeatureCollection"}}
        meta = ToolCallExecutionService._meta_for_tool_call(
            ToolCallSchema(tool_name=tool_name), {}, layers
        )
        assert meta == {"layers": layers}


class TestArgumentsForToolCall:
    @pytest.mark.parametrize(
        "tool_name",
        [
            "CheckDistanceFromSource",
            "GetServicesByGeometry",
            "CheckObjectAttributeThreshold",
            "CheckAccessibilityWithin",
        ],
    )
    def test_compliance_replay_injects_layers_without_changing_stored_call(
        self,
        tool_name: str,
    ) -> None:
        layers = {"houses": {"type": "FeatureCollection"}}
        call = ToolCallSchema(
            tool_name=tool_name,
            arguments={"restriction_id": "r1"},
        )
        arguments = ToolCallExecutionService._arguments_for_tool_call(call, layers)
        assert arguments == {"restriction_id": "r1", "layers": layers}
        assert call.arguments == {"restriction_id": "r1"}

    def test_restriction_zones_replay_injects_layers(self) -> None:
        layers = {"Школа": {"type": "FeatureCollection"}}
        call = ToolCallSchema(
            tool_name="CreateRestrictionZones",
            arguments={"source_layer": "Школа", "geometry_mode": "buffer"},
        )
        arguments = ToolCallExecutionService._arguments_for_tool_call(call, layers)
        assert arguments["layers"] == layers
        assert "layers" not in call.arguments


class TestResultData:
    """Result unwrapping into a flat dict."""

    def test_unwraps_nested_data(self) -> None:
        assert ToolCallExecutionService._result_data({"data": {"a": 1}}) == {"a": 1}

    def test_passes_through_plain_dict(self) -> None:
        assert ToolCallExecutionService._result_data({"a": 1}) == {"a": 1}

    def test_wraps_scalar(self) -> None:
        assert ToolCallExecutionService._result_data(5) == {"value": 5}


class TestUpdateAccumulatedLayers:
    """Only dict-valued results are accumulated as layers."""

    def test_keeps_dict_values_only(self) -> None:
        layers: dict[str, dict] = {}
        ToolCallExecutionService._update_accumulated_layers(
            layers, {"school": {"type": "FC"}, "count": 3}
        )

        assert layers == {"school": {"type": "FC"}}


class TestResolveMcpUrl:
    """MCP URL resolution with fallback to the default IDU MCP URL."""

    def _service(self) -> ToolCallExecutionService:
        return ToolCallExecutionService(
            idu_mcp_url="http://idu-mcp/mcp",
            chain_builder=ChatHistoryService(MagicMock()),
            mcp_sources={
                "effects": "http://effects/mcp",
                "objects_effects": "http://objects-effects/mcp",
                "urban_projects": "http://urban/mcp/projects/",
            },
            service_auth=MagicMock(),
        )

    def test_known_source(self) -> None:
        assert self._service()._resolve_mcp_url("effects") == "http://effects/mcp"

    def test_unknown_source_falls_back(self) -> None:
        assert self._service()._resolve_mcp_url("unknown") == "http://idu-mcp/mcp"

    def test_none_source_falls_back(self) -> None:
        assert self._service()._resolve_mcp_url(None) == "http://idu-mcp/mcp"

    def test_env_style_source_is_normalized(self) -> None:
        assert (
            self._service()._resolve_mcp_url("OBJECTS_EFFECTS_MCP_URL")
            == "http://objects-effects/mcp"
        )

    def test_grouped_urban_source_is_normalized(self) -> None:
        assert (
            self._service()._resolve_mcp_url("URBAN_MCP/projects")
            == "http://urban/mcp/projects/"
        )


class TestExecuteGuard:
    """execute_tool_call rejects requests when no MCP URL is configured."""

    async def test_missing_mcp_url_raises_503(self) -> None:
        service = ToolCallExecutionService(
            idu_mcp_url="",
            chain_builder=ChatHistoryService(MagicMock()),
            service_auth=MagicMock(),
        )
        payload = ToolCallExtractDTO(tool_call=ToolCallDTO(tool_name="GetServices"))

        with pytest.raises(HTTPException) as exc_info:
            await service.execute_tool_call(user_id="u", payload=payload)

        assert exc_info.value.status_code == 503


class TestGeometryReplay:
    @pytest.mark.parametrize("with_norm_layer", [True, False])
    async def test_geometry_layers_reach_check_and_norm_is_displayed(
        self,
        geometry_replay_payload: ToolCallExtractDTO,
        with_norm_layer: bool,
    ) -> None:
        territory = {"type": "FeatureCollection", "features": [], "meta": {"id": "p"}}
        sources = {"type": "FeatureCollection", "features": [], "meta": {"id": "s"}}
        zones = {"type": "FeatureCollection", "features": [], "meta": {"id": "z"}}
        targets = {"type": "FeatureCollection", "features": [], "meta": {"id": "t"}}
        norm = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [30, 60]},
                    "properties": {
                        "feature_kind": "zone",
                        "norm_id": "r1",
                        "status": "passed",
                    },
                }
            ],
        }
        check_result = {
            "passed_objects": targets,
            "violated_objects": {"type": "FeatureCollection", "features": []},
            "coverage": {"checked_objects": 1},
            "summary": {"passed_objects": 1},
        }
        if with_norm_layer:
            check_result["norm_layer"] = norm
        zone_name = "Зона ограничения — СП 42, п. 7.1"
        responses = iter(
            [
                {"project_territory": territory},
                {"Источники — Школа": sources},
                {
                    zone_name: zones,
                    "norm_layer": {"type": "FeatureCollection", "features": []},
                },
                {"Цели — Театр": targets},
                check_result,
            ]
        )
        calls = []

        async def call_tool(name, arguments, *, meta):
            # Snapshot before subsequent steps extend the accumulated dictionary.
            calls.append((name, deepcopy(arguments), deepcopy(meta)))
            return SimpleNamespace(data=next(responses))

        mcp = MagicMock()
        mcp.call_tool = AsyncMock(side_effect=call_tool)
        mcp.__aenter__ = AsyncMock(return_value=mcp)
        mcp.__aexit__ = AsyncMock(return_value=False)
        service = ToolCallExecutionService(
            idu_mcp_url="http://idu-mcp/mcp",
            chain_builder=ChatHistoryService(MagicMock()),
            service_auth=MagicMock(),
        )
        with patch("app.services.tool_call_execution_service.Client", return_value=mcp):
            result = await service.execute_tool_call("user", geometry_replay_payload)

        assert [name for name, _, _ in calls] == [
            "GetProjectTerritory",
            "GetServicesByGeometry",
            "CreateRestrictionZones",
            "GetServicesByGeometry",
            "CheckDistanceFromSource",
        ]
        assert calls[1][1]["layers"] == {"project_territory": territory}
        assert calls[1][1]["zones_layers"] == ["project_territory"]
        assert calls[1][1]["buffer_m"] == 500
        assert calls[2][1]["layers"]["Источники — Школа"] == sources
        assert calls[3][1]["zones_layers"] == [zone_name]
        assert calls[3][1]["layers"][zone_name] == zones
        assert "Цели — Театр" not in calls[3][1]["layers"]
        assert calls[4][1]["layers"]["Цели — Театр"] == targets
        assert calls[4][1]["layers"][zone_name] == zones
        assert result.steps[3].result == {"Цели — Театр": targets}
        for _, arguments, meta in calls[1:]:
            assert meta["layers"] == arguments["layers"]
            assert meta["scenario_id"] == 772
        expected = {"norm_layer": norm} if with_norm_layer else check_result
        assert result.steps[-1].result == expected
        assert result.result == expected
        assert all("layers" not in step.tool_call.arguments for step in result.steps)
        assert "layers" not in geometry_replay_payload.tool_call.arguments
