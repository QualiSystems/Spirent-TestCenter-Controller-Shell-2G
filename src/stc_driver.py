from cloudshell.traffic.tg import TgControllerDriver

from stc_handler import StcHandler


class StcControllerShell2GDriver(TgControllerDriver):
    def __init__(self):
        self.handler = StcHandler()

    def load_config(self, context, config_file_location):
        """Load STC configuration file and reserve ports."""
        super().load_config(context, config_file_location)

    def send_arp(self, context):
        """Send ARP/ND for all devices and streams."""
        self.handler.send_arp()

    def start_protocols(self, context):
        """Start all emulations on all devices."""
        self.handler.start_devices()

    def stop_protocols(self, context):
        """Stop all emulations on all devices."""
        self.handler.stop_devices()

    def start_traffic(self, context, blocking):
        """Start traffic on all ports.

        :param blocking: True - return after traffic finish to run, False - return immediately.
        """
        self.handler.start_traffic(blocking)
        return f"traffic started in {blocking} mode"

    def stop_traffic(self, context):
        """Stop traffic on all ports."""
        self.handler.stop_traffic()

    def get_statistics(self, context, view_name, output_type):
        """Get view statistics.

        :param view_name: generatorPortResults, analyzerPortResults etc.
        :param output_type: CSV or JSON.
        """
        return self.handler.get_statistics(context, view_name, output_type)

    def run_quick_test(self, context, command):
        """Get view statistics.

        :param command: from GUI - Start/Stop/Wait, from API also available Step/Pause.
        """
        self.handler.sequencer_command(command)

    #
    # Parent commands are not visible so we re define them in child.
    #

    def initialize(self, context):
        super().initialize(context)

    def cleanup(self):
        super().cleanup()

    def keep_alive(self, context, cancellation_context):
        super().keep_alive(context, cancellation_context)

    #
    # Hidden commands for developers only.
    #

    def get_session_id(self, context):
        """Returns the REST session ID."""
        self.logger.info("getting session ID")
        session_id = self.handler.get_session_id()
        self.logger.info(f"session_id = {session_id}")
        return session_id

    def get_children(self, context, obj_ref, child_type=""):
        """Returns all children of object.

        :param obj_ref: valid STC object reference.
        :param child_type: requested children type. If None returns all children.
        :return: list of children.
        """
        return self.handler.get_children(obj_ref, child_type)

    def get_attributes(self, context, obj_ref):
        """Returns all children of object.

        :param obj_ref: valid STC object reference.
        :return: list of <attribute, value>.
        """
        return self.handler.get_attributes(obj_ref)

    def set_attribute(self, context, obj_ref, attr_name, attr_value):
        """Set object attribute.

        :param obj_ref: valid STC object reference.
        :param attr_name: STC attribue name.
        :param attr_value: STC attribue value.
        """
        self.handler.set_attribute(obj_ref, attr_name, attr_value)

    def perform_command(self, context, command, parameters_json):
        """Perform STC command.

        :param command: valid STC command.
        :param parameters_json: parameters dict {name: value} as serialized json.
        """
        return self.handler.perform_command(command, parameters_json)
