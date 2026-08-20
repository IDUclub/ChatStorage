import pytest
from pydantic import ValidationError

from app.dto.message_dto import MessagePartCreateDTO


def test_check_plan_part_is_typed_and_keeps_extended_requirements():
    part = MessagePartCreateDTO(
        kind="check_plan",
        payload={
            "schema_version": "1.0",
            "template": "distance_from_source",
            "template_version": 1,
            "params": {"distance_m": 50},
            "source": {"restriction_id": "r1"},
            "planner_status": "auto",
            "declared_requirements": {"layers": [], "attributes": []},
        },
    )
    assert part.payload["source"]["restriction_id"] == "r1"


def test_compliance_result_requires_reproducibility_versions():
    with pytest.raises(ValidationError):
        MessagePartCreateDTO(
            kind="compliance_result",
            payload={
                "restriction_id": "r1",
                "template": "distance_from_source",
                "template_version": 1,
                "verification_status": "complete",
                "compliance_status": "passed",
                "coverage": {},
                "summary": {},
            },
        )
