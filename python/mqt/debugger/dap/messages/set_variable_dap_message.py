"""Represents the 'setVariable' DAP request."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import mqt.debugger

from .dap_message import DAPMessage

if TYPE_CHECKING:
    from ..dap_server import DAPServer


class SetVariableDAPMessage(DAPMessage):
    """Represents the 'setVariable' DAP request."""

    message_type_name: str = "setVariable"

    variables_reference: int
    name: str
    value: str

    def __init__(self, message: dict[str, Any]) -> None:
        """Initializes the 'SetVariableDAPMessage' instance.

        Args:
            message (dict[str, Any]): The object representing the 'setVariable' request.
        """
        super().__init__(message)
        arguments = message["arguments"]
        self.variables_reference = arguments["variablesReference"]
        self.name = arguments["name"]
        # The DAP request schema sends the new value as a string, but be tolerant here.
        self.value = str(arguments.get("value", ""))

    def validate(self) -> None:
        """Validates the 'SetVariableDAPMessage' instance."""

    def handle(self, server: DAPServer) -> dict[str, Any]:
        """Performs the action requested by the 'setVariable' DAP request.

        Args:
            server (DAPServer): The DAP server that received the request.

        Returns:
            dict[str, Any]: The response to the request.
        """
        response = super().handle(server)
        try:
            target_name = self._resolve_target_name()
            variable = server.simulation_state.get_classical_variable(target_name)
            new_value, display_value = _convert_to_value(self.value, variable.type)
            server.simulation_state.set_classical_variable(target_name, variable.type, new_value)
            response["body"] = {"value": display_value}
        except ValueError as exc:
            response["success"] = False
            response["message"] = str(exc)
        except RuntimeError:
            response["success"] = False
            response["message"] = f"Unable to update classical variable '{self.name}'."
        return response

    def _resolve_target_name(self) -> str:
        """Ensure the request references a classical variable and return its name."""
        if self.variables_reference not in (1,) and self.variables_reference < 10:
            raise ValueError("Setting variables is only supported for classical registers.")
        if "[" not in self.name:
            raise ValueError(
                "Updating grouped classical registers is not supported yet. "
                "Expand the register and edit an individual bit."
            )
        return self.name


def _convert_to_value(
    raw_value: str, var_type: mqt.debugger.VariableType
) -> tuple[mqt.debugger.VariableValue, str]:
    """Convert the raw string from the client to a VariableValue."""
    value = mqt.debugger.VariableValue()
    cleaned = raw_value.strip()
    if var_type == mqt.debugger.VariableType.VarBool:
        lowered = cleaned.lower()
        if lowered in {"true", "1"}:
            value.bool_value = True
            display = "True"
        elif lowered in {"false", "0"}:
            value.bool_value = False
            display = "False"
        else:
            raise ValueError("Boolean variables only accept 'true', 'false', '1', or '0'.")
    elif var_type == mqt.debugger.VariableType.VarInt:
        try:
            parsed = int(cleaned, 0)
        except ValueError as exc:
            raise ValueError("Integer variables expect a base-10 or prefixed literal.") from exc
        value.int_value = parsed
        display = str(parsed)
    elif var_type == mqt.debugger.VariableType.VarFloat:
        try:
            parsed = float(cleaned)
        except ValueError as exc:
            raise ValueError("Floating-point variables expect a decimal literal.") from exc
        value.float_value = parsed
        display = str(parsed)
    else:
        raise ValueError("Unsupported variable type.")
    return value, display
