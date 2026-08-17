from app.common.db.migrations import JOBS_VALIDATOR, MESSAGES_VALIDATOR
from app.schema.chat_context_schema import (
    ChatContextContentSchema,
    ChatContextSchema,
    ContextJobCompletionSchema,
)


def test_context_completion_keeps_structured_and_text_representations():
    payload = ContextJobCompletionSchema(
        worker_id="worker-1",
        content=ChatContextContentSchema(
            summary="Пользователь выбрал сценарий 772.",
            structured={"user_decisions": [{"scenario_id": 772}]},
        ),
    )

    assert payload.content.structured["user_decisions"][0]["scenario_id"] == 772


def test_mongo_validators_allow_typed_trace_and_bound_job_attempts():
    kinds = MESSAGES_VALIDATOR["$jsonSchema"]["properties"]["parts"]["items"][
        "properties"
    ]["kind"]["enum"]
    assert {"plan", "plan_revision", "artifact_ref", "validation", "failure"} <= set(
        kinds
    )
    attempts = JOBS_VALIDATOR["$jsonSchema"]["properties"]["attempts"]
    assert attempts["maximum"] == 3


def test_context_tail_exposes_hierarchical_pagination_cursor():
    context = ChatContextSchema(
        chat_id="00000000-0000-0000-0000-000000000000",
        target_seq=250,
        tail_has_more=True,
        tail_next_after_seq=100,
    )

    assert context.tail_has_more is True
    assert context.tail_next_after_seq == 100
