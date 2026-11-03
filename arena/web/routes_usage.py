"""POST /api/usage: one hit from a page (app/src/usage.js), checked and held by the usage log."""

from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Request, Response
from pydantic import BaseModel, Field

from .routes_auth import current_user

router = APIRouter(prefix="/api")

Id = Annotated[str, Field(pattern=r"^[A-Za-z0-9-]{8,40}$")]


class Hit(BaseModel):
    """What a page may report. Any other field is dropped, so nothing it sends can name anyone."""

    visitor: Id
    visit: Id
    kind: Literal["view", "out", "time"]
    page: Annotated[str, Field(max_length=200)]
    href: Annotated[str, Field(max_length=300)] | None = None
    seconds: Annotated[int, Field(ge=0, le=86_400)] | None = None
    # The first view of a visit says where it came from and on what.
    referrer: Annotated[str, Field(max_length=100)] | None = None
    embedded: bool | None = None
    mobile: bool | None = None


@router.post("/usage")
def usage(hit: Hit, request: Request) -> Response:
    request.app.state.usage.record({
        "at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        **hit.model_dump(exclude_none=True),
        "signed_in": current_user(request) is not None,
    })
    return Response(status_code=204)
