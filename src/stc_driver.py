"""
STC controller shell driver API. The business logic is implemented in stc_handler.py.
"""
# pylint: disable=unused-argument
from typing import Optional, Union

from cloudshell.shell.core.driver_context import CancellationContext, InitCommandContext, ResourceCommandContext
from cloudshell.traffic.tg import TgControllerDriver, enqueue_keep_alive

from stc_handler import StcHandler


class StcControllerShell2GDriver(TgControllerDriver):
    """STC controller shell driver API."""

    def __init__(self) -> None:
        """Initialize object variables, actual initialization is performed in initialize method."""
        super().__init__()
        self.handler = StcHandler()

    def initialize(self, context: InitCommandContext) -> None:
        """Initialize IxNetwork controller shell (from API)."""
        super().initialize(context)
        self.handler.initialize(context, self.logger)

    def cleanup(self) -> None:
        """Cleanup TestCenter controller shell (from API)."""
        self.handler.cleanup()
        super().cleanup()

    def load_config(self, context: ResourceCommandContext, config_file_location: str) -> None:
        """Load STC configuration file, map and reserve ports."""
        enqueue_keep_alive(context)
        self.handler.load_config(context, config_file_location)

    def send_arp(self, context: ResourceCommandContext) -> None:
        """Send ARP/ND for all devices and streams."""
        self.handler.send_arp()

    def start_protocols(self, context: ResourceCommandContext) -> None:
        """Start all emulations on all devices."""
        self.handler.start_devices()

    def stop_protocols(self, context: ResourceCommandContext) -> None:
        """Stop all emulations on all devices."""
        self.handler.stop_devices()

    def start_traffic(self, context: ResourceCommandContext, blocking: str) -> str:
        """Start traffic on all ports.

        :param blocking: True - return after traffic finish to run, False - return immediately.
        """
        self.handler.start_traffic(blocking)
        return f"traffic started in {blocking} mode"

    def stop_traffic(self, context: ResourceCommandContext) -> None:
        """Stop traffic on all ports."""
        self.handler.stop_traffic()

    def get_statistics(self, context: ResourceCommandContext, view_name: str, output_type: str) -> Union[dict, str]:
        """Get view statistics.

        :param view_name: generatorPortResults, analyzerPortResults etc.
        :param output_type: CSV or JSON.
        """
        return self.handler.get_statistics(context, view_name, output_type)

    def run_quick_test(self, context: ResourceCommandContext, command: str) -> None:
        """Run sequencer command.

        :param command: from GUI - Start/Stop/Wait, from API also available Step/Pause.
        """
        self.handler.sequencer_command(command)

    def keep_alive(self, context: ResourceCommandContext, cancellation_context: CancellationContext) -> None:
        """Keep TestCenter controller shell sessions alive (from TG controller API).

        Parent commands are not visible so we re re-define this method in child.
        """
        super().keep_alive(context, cancellation_context)

    #
    # Hidden commands for developers only.
    #

    def get_session_id(self, context: ResourceCommandContext) -> str:
        """Return the REST session ID."""
        self.logger.info("getting session ID")
        session_id = self.handler.get_session_id()
        self.logger.info(f"session_id = {session_id}")
        return session_id

    def get_children(self, context: ResourceCommandContext, obj_ref: str, child_type: Optional[str] = "") -> list:
        """Return all children, of the requested type, of the requested object.

        :param obj_ref: valid STC object reference.
        :param child_type: requested children type. If None returns all children.
        :return: list of children.
        """
        return self.handler.get_children(obj_ref, child_type)

    def get_attributes(self, context: ResourceCommandContext, obj_ref: str) -> dict:
        """Return all attributes of the requested object.

        :param obj_ref: valid STC object reference.
        :return: list of <attribute, value>.
        """
        return self.handler.get_attributes(obj_ref)

    def set_attribute(self, context: ResourceCommandContext, obj_ref: str, attr_name: str, attr_value: str) -> None:
        """Set object attribute.

        :param obj_ref: valid STC object reference.
        :param attr_name: STC attribute name.
        :param attr_value: STC attribute value.
        """
        self.handler.set_attribute(obj_ref, attr_name, attr_value)

    def perform_command(self, context: ResourceCommandContext, command: str, parameters_json: str) -> str:
        """Perform STC command.

        :param command: valid STC command.
        :param parameters_json: parameters dict {name: value} as serialized json.
        """
        return self.handler.perform_command(command, parameters_json)
