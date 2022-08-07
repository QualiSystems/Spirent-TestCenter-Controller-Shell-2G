"""
STC controller shell business logic.
"""
import csv
import io
import json
import logging
from collections import OrderedDict
from typing import Union

from cloudshell.shell.core.driver_context import InitCommandContext, ResourceCommandContext
from cloudshell.traffic.helpers import get_family_attribute, get_location, get_resources_from_reservation
from cloudshell.traffic.tg import STC_CHASSIS_MODEL, attach_stats_csv, is_blocking
from testcenter.stc_app import StcApp, StcSequencerOperation, init_stc
from testcenter.stc_statistics_view import StcStats
from trafficgenerator.tgn_utils import ApiType, TgnError

from stc_data_model import STC_Controller_Shell_2G

OFFLINE_PORT_MARKER = "offline-debug"


class StcHandler:
    """STC controller shell business logic."""

    def __init__(self) -> None:
        """Initialize object variables, actual initialization is performed in initialize method."""
        self.stc: StcApp = None
        self.logger: logging.Logger = None

    def initialize(self, context: InitCommandContext, logger: logging.Logger) -> None:
        """Init StcApp and connect to STC REST server."""
        self.logger = logger

        service = STC_Controller_Shell_2G.create_from_context(context)

        controller = service.address
        port = service.controller_tcp_port if service.controller_tcp_port else "8888"
        self.stc = init_stc(ApiType.rest, self.logger, rest_server=controller, rest_port=int(port))
        self.stc.connect()

    def cleanup(self) -> None:
        """Disconnect from STC REST server."""
        self.stc.disconnect()

    def load_config(self, context: ResourceCommandContext, stc_config_file_name: str) -> None:
        """Load STC configuration file, and map and reserve ports."""
        self.stc.load_config(stc_config_file_name)
        config_ports = self.stc.project.get_ports()

        reservation_ports = {}
        for port in get_resources_from_reservation(context, f"{STC_CHASSIS_MODEL}.GenericTrafficGeneratorPort"):
            reservation_ports[get_family_attribute(context, port.Name, "Logical Name")] = port

        for name, port in config_ports.items():
            if name in reservation_ports:
                address = get_location(reservation_ports[name])
                self.logger.debug(f"Logical Port {name} will be reserved on Physical location {address}")
                if OFFLINE_PORT_MARKER not in reservation_ports[name].Name:
                    port.reserve(address, force=True, wait_for_up=False)
                else:
                    self.logger.debug(f"Offline debug port {address} - no actual reservation")
            else:
                raise TgnError(f'Configuration port "{port}" not found in reservation ports {reservation_ports.keys()}')

        self.logger.info("Port Reservation Completed")

    def send_arp(self) -> None:
        """Send ARP/ND for all devices and streams."""
        self.stc.send_arp_ns()

    def start_devices(self) -> None:
        """Start all emulations on all devices."""
        self.stc.start_devices()

    def stop_devices(self) -> None:
        """Stop all emulations on all devices."""
        self.stc.stop_devices()

    def start_traffic(self, blocking: str) -> None:
        """Start traffic on all ports."""
        self.stc.clear_results()
        self.stc.start_traffic(is_blocking(blocking))

    def stop_traffic(self) -> None:
        """Stop traffic on all ports."""
        self.stc.stop_traffic()

    def get_statistics(self, context: ResourceCommandContext, view_name: str, output_type: str) -> Union[dict, str]:
        """Get statistics for the requested view."""
        stats_obj = StcStats(view_name)
        stats_obj.read_stats()
        statistics = OrderedDict()
        for obj, obj_values in stats_obj.statistics.items():
            statistics[obj.name] = obj_values

        if output_type.strip().lower() == "json":
            statistics_str = json.dumps(statistics, indent=4, sort_keys=True, ensure_ascii=False)
            return json.loads(statistics_str)
        if output_type.strip().lower() == "csv":
            captions = list(list(statistics.values())[0].keys())
            output = io.StringIO()
            writer = csv.DictWriter(output, captions)
            writer.writeheader()
            for obj_values in statistics.values():
                writer.writerow(obj_values)
            attach_stats_csv(context, self.logger, view_name, output.getvalue().strip())
            return output.getvalue().strip()
        raise TgnError(f'Output type should be CSV/JSON - got "{output_type}"')

    def sequencer_command(self, command: str) -> None:
        """Run sequencer command."""
        if StcSequencerOperation[command.lower()] == StcSequencerOperation.start:
            self.stc.clear_results()
        self.stc.sequencer_command(StcSequencerOperation[command.lower()])

    def get_session_id(self) -> str:
        """Return the REST session ID."""
        self.logger.info(f"session_id = {self.stc.api.session_id}")
        return self.stc.api.session_id

    def get_children(self, obj_ref: str, child_type: str) -> list:
        """Return all children, of the requested type, of the requested object."""
        children_attribute = "children-" + child_type if child_type else "children"
        return self.stc.api.client.get(obj_ref, children_attribute).split()

    def get_attributes(self, obj_ref: str) -> dict:
        """Return all attributes of the requested object."""
        return self.stc.api.client.get(obj_ref)

    def set_attribute(self, obj_ref: str, attr_name: str, attr_value: str) -> None:
        """Set object attribute."""
        self.stc.api.client.config(obj_ref, **{attr_name: attr_value})

    def perform_command(self, command: str, parameters_json: str) -> str:
        """Perform STC command."""
        return self.stc.api.client.perform(command, json.loads(parameters_json))
