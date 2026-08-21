"""Unit tests for ToolCallExecutionService pure helpers.

The MCP round-trip in ``execute_tool_call`` is not exercised here (that needs a
live MCP server — see the integration tests). These cover the data-shaping and
meta-building helpers, plus the early 503 guard when no MCP URL is configured.
"""

from dataclasses import dataclass
from unittest.mock import MagicMock

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

    def test_compliance_tool_gets_layers(self) -> None:
        layers = {"houses": {"type": "FeatureCollection"}}
        meta = ToolCallExecutionService._meta_for_tool_call(
            ToolCallSchema(tool_name="CheckDistanceFromSource"), {}, layers
        )
        assert meta == {"layers": layers}


class TestArgumentsForToolCall:
    def test_compliance_replay_injects_layers_without_changing_stored_call(
        self,
    ) -> None:
        layers = {"houses": {"type": "FeatureCollection"}}
        call = ToolCallSchema(
            tool_name="CheckDistanceFromSource",
            arguments={"restriction_id": "r1"},
        )
        arguments = ToolCallExecutionService._arguments_for_tool_call(call, layers)
        assert arguments == {"restriction_id": "r1", "layers": layers}
        assert call.arguments == {"restriction_id": "r1"}


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
