"""Tool call execution through IDU MCP."""

from dataclasses import asdict, is_dataclass
from typing import Any

from fastapi import HTTPException, status
from fastmcp import Client
from pydantic import BaseModel

from app.dto.message_dto import ToolCallExtractDTO
from app.schema.chat_history_schema import (
    ToolCallExecutionResultSchema,
    ToolCallResultStepSchema,
    ToolCallSchema,
)
from app.services.chat_history_service import ChatHistoryService


class ToolCallExecutionService:
    """
    Class fpr execution direct tool calls and their required previous calls.
    Attributes:
        _idu_mcp_url (str): IDU MCP server url (default fallback).
        _mcp_sources (dict[str, str]): Mapping from MCP server name to URL.
        _chain_builder (ChatHistoryService): ChatStorageService instance with functions for building tool chains.
    """

    def __init__(
        self,
        idu_mcp_url: str,
        chain_builder: ChatHistoryService,
        mcp_sources: dict[str, str] | None = None,
    ) -> None:
        """
        Initialization function for ToolCallExecutor class.
        Args:
            idu_mcp_url (str): IDU MCP server url (default fallback).
            chain_builder (ChatHistoryService): ChatStorageService instance with functions for building tool chains.
            mcp_sources (dict[str, str] | None): Mapping from MCP server name to URL.
        """

        self._idu_mcp_url = idu_mcp_url
        self._mcp_sources = mcp_sources or {}
        self._chain_builder = chain_builder

    async def execute_tool_call(
        self,
        token: str,
        payload: ToolCallExtractDTO,
    ) -> ToolCallExecutionResultSchema:
        """
        Execute the requested tool call after its dependencies.
        Args:
            token (str): User token from Urban API.
            payload (ToolCallExtractDTO): Pydantic model with tool extraction data.
        Returns:
            ToolCallExecutionResultSchema: Executed tool results.
        """

        mcp_url = self._resolve_mcp_url(payload.mcp_source)
        if not mcp_url:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="IDU_MCP_URL is not configured",
            )

        chain = await self._chain_builder.extract_tool_call_chain(payload)
        if chain.missing_dependencies:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "message": "Tool call dependencies are missing",
                    "missing_dependencies": chain.missing_dependencies,
                    "execution_chain": chain.model_dump(mode="json")["execution_chain"],
                },
            )

        base_meta = self._base_meta(payload)
        accumulated_layers: dict[str, dict[str, Any]] = {}
        steps: list[ToolCallResultStepSchema] = []

        async with Client(mcp_url, auth=token) as mcp:
            for execution_step in chain.execution_chain:
                tool_call = execution_step.tool_call
                meta = self._meta_for_tool_call(
                    tool_call,
                    base_meta,
                    accumulated_layers,
                )
                raw_result = await mcp.call_tool(
                    tool_call.tool_name,
                    tool_call.arguments,
                    meta=meta,
                )
                result = self.to_plain_data(getattr(raw_result, "data", raw_result))
                result_data = self._result_data(result)
                self._update_accumulated_layers(accumulated_layers, result_data)
                steps.append(
                    ToolCallResultStepSchema(
                        order=execution_step.order,
                        tool_call=tool_call,
                        meta=meta,
                        result=result_data,
                    )
                )

        return ToolCallExecutionResultSchema(
            target=chain.target,
            execution_chain=chain.execution_chain,
            missing_dependencies=chain.missing_dependencies,
            steps=steps,
            result=steps[-1].result if steps else None,
        )

    async def execute_stored_tool_call(
        self,
        user_id: str,
        token: str,
        message_id: str,
        part_seq: int,
        tool_call_step: int,
        scenario_id: int | None = None,
        project_id: int | None = None,
    ) -> ToolCallExecutionResultSchema:
        """Execute a tool call restored from chat history."""

        payload = await self._chain_builder.build_tool_call_extract_payload(
            user_id=user_id,
            message_id=message_id,
            part_seq=part_seq,
            tool_call_step=tool_call_step,
            scenario_id=scenario_id,
            project_id=project_id,
        )
        return await self.execute_tool_call(token, payload)

    @staticmethod
    def to_plain_data(value: Any) -> Any:
        """Convert MCP/Pydantic/dataclass responses to JSON-serializable data."""

        if is_dataclass(value):
            return asdict(value)
        if isinstance(value, BaseModel):
            return value.model_dump(mode="json")
        if isinstance(value, dict):
            return {
                key: ToolCallExecutionService.to_plain_data(item)
                for key, item in value.items()
            }
        if isinstance(value, list):
            return [ToolCallExecutionService.to_plain_data(item) for item in value]
        return value

    @staticmethod
    def _base_meta(payload: ToolCallExtractDTO) -> dict[str, Any]:
        meta = dict(payload.meta)
        if payload.scenario_id is not None:
            meta["scenario_id"] = payload.scenario_id
        if payload.project_id is not None:
            meta["project_id"] = payload.project_id
        return meta

    @staticmethod
    def _meta_for_tool_call(
        tool_call: ToolCallSchema,
        base_meta: dict[str, Any],
        accumulated_layers: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        if tool_call.tool_name == "CreateBuffers":
            return {**base_meta, "objects": accumulated_layers}
        if tool_call.tool_name == "CreateRestrictions":
            return {**base_meta, "layers": accumulated_layers}
        return base_meta

    @staticmethod
    def _result_data(result: Any) -> dict[str, Any]:
        if isinstance(result, dict) and isinstance(result.get("data"), dict):
            return result["data"]
        if isinstance(result, dict):
            return result
        return {"value": result}

    @staticmethod
    def _update_accumulated_layers(
        accumulated_layers: dict[str, dict[str, Any]],
        result: dict[str, Any],
    ) -> None:
        for key, value in result.items():
            if isinstance(value, dict):
                accumulated_layers[key] = value

    def _resolve_mcp_url(self, mcp_source: str | None) -> str:
        """Return the MCP server URL for the given source name, falling back to IDU_MCP_URL."""
        if mcp_source and mcp_source in self._mcp_sources:
            return self._mcp_sources[mcp_source]
        return self._idu_mcp_url
