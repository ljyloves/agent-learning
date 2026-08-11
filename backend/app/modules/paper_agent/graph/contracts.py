"""Pydantic input/output contracts for LangGraph nodes."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from functools import wraps
from inspect import iscoroutinefunction
from typing import Any, Generic, TypeVar, cast

from pydantic import BaseModel


StateModelT = TypeVar("StateModelT", bound=BaseModel)
InputModelT = TypeVar("InputModelT", bound=BaseModel)
OutputModelT = TypeVar("OutputModelT", bound=BaseModel)
NodeCallable = Callable[[Any], Any]
CONTRACT_ATTRIBUTE = "__paper_graph_contract__"


def _model_payload(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="python")
    if isinstance(value, Mapping):
        return dict(value)
    return value


@dataclass(frozen=True, slots=True)
class GraphNodeContract(Generic[StateModelT, InputModelT, OutputModelT]):
    """Models used to validate one node's state input and partial state output."""

    name: str
    state_model: type[StateModelT]
    input_model: type[InputModelT]
    output_model: type[OutputModelT]

    def __post_init__(self) -> None:
        if not self.name.strip() or self.name != self.name.strip():
            raise ValueError("graph node contract name must be non-empty and trimmed")
        for model in (self.state_model, self.input_model, self.output_model):
            if not isinstance(model, type) or not issubclass(model, BaseModel):
                raise TypeError("graph node contract models must extend BaseModel")

    def validate_input(self, state: Any) -> InputModelT:
        state_payload = _model_payload(state)
        validated_state = self.state_model.model_validate(state_payload)
        validated_payload = validated_state.model_dump(mode="python")
        input_payload = {
            field_name: validated_payload[field_name]
            for field_name in self.input_model.model_fields
            if field_name in validated_payload
        }
        return self.input_model.model_validate(input_payload)

    def validate_output(self, output: Any) -> OutputModelT:
        return self.output_model.model_validate(_model_payload(output))

    def build_state_update(
        self,
        state: Any,
        output: Any,
    ) -> dict[str, Any]:
        validated_state = self.state_model.model_validate(_model_payload(state))
        validated_output = self.validate_output(output)
        update = validated_output.model_dump(mode="python")
        merged_state = validated_state.model_dump(mode="python")
        merged_state.update(update)
        self.state_model.model_validate(merged_state)
        return update


def validated_node(
    contract: GraphNodeContract[Any, Any, Any],
) -> Callable[[NodeCallable], NodeCallable]:
    """Validate a node before execution, after execution, and after state merge."""

    def decorator(handler: NodeCallable) -> NodeCallable:
        if iscoroutinefunction(handler):

            @wraps(handler)
            async def async_wrapper(state: Any) -> dict[str, Any]:
                node_input = contract.validate_input(state)
                raw_output = await handler(node_input)
                return contract.build_state_update(state, raw_output)

            wrapper = cast(NodeCallable, async_wrapper)
        else:

            @wraps(handler)
            def sync_wrapper(state: Any) -> dict[str, Any]:
                node_input = contract.validate_input(state)
                raw_output = handler(node_input)
                return contract.build_state_update(state, raw_output)

            wrapper = cast(NodeCallable, sync_wrapper)

        setattr(wrapper, CONTRACT_ATTRIBUTE, contract)
        return wrapper

    return decorator


def get_node_contract(node: NodeCallable) -> GraphNodeContract[Any, Any, Any]:
    contract = getattr(node, CONTRACT_ATTRIBUTE, None)
    if not isinstance(contract, GraphNodeContract):
        raise TypeError("graph nodes must be decorated with validated_node")
    return contract


def add_contract_node(graph: Any, node: NodeCallable) -> str:
    """Register only nodes that declare Pydantic input and output contracts."""

    contract = get_node_contract(node)
    graph.add_node(
        contract.name,
        node,
        input_schema=contract.state_model,
    )
    return contract.name
