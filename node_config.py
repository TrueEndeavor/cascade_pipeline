from typing import TypedDict, Optional, Annotated, Any
from models.metadata import Metadata


def reduce(current: str, new: str) -> str:
    return new or current


def token_reduce(current: Any, new: Any) -> Any:
    return new or current


class AgentStateParallel(TypedDict):
    pdf_path: Annotated[str, reduce]
    Metadata: Annotated[Metadata, reduce]
    SEC_misleading_detect_artifact: Annotated[str, reduce]
    SEC_misleading_ask_artifact: Annotated[str, reduce]
    SEC_misleading_artifact: Annotated[str, reduce]
    SEC_misleading_token_data: Annotated[Any, token_reduce]
