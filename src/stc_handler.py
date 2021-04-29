
import json
import csv
import io
from collections import OrderedDict

from cloudshell.traffic.helpers import get_resources_from_reservation, get_location, get_family_attribute
from cloudshell.traffic.tg import TgControllerHandler, is_blocking, attach_stats_csv, STC_CHASSIS_MODEL

from trafficgenerator.tgn_utils import ApiType, TgnError
from testcenter.stc_app import init_stc, StcSequencerOperation
from testcenter.stc_statistics_view import StcStats

from stc_data_model import STC_Controller_Shell_2G


class StcHandler(TgControllerHandler):

    def __init__(self):
        self.stc = None

    def initialize(self, context, logger):

        service = STC_Controller_Shell_2G.create_from_context(context)
        super().initialize(context, logger, service)

        controller = self.service.address
        port = self.service.controller_tcp_port if self.service.controller_tcp_port else '8888'
        self.stc = init_stc(ApiType.rest, self.logger, rest_server=controller, rest_port=int(port))
        self.stc.connect()

    def cleanup(self):
        self.stc.disconnect()

    def load_config(self, context, stc_config_file_name):

        self.stc.load_config(stc_config_file_name)
        config_ports = self.stc.project.get_ports()

        reservation_ports = {}
        for port in get_resources_from_reservation(context, f'{STC_CHASSIS_MODEL}.GenericTrafficGeneratorPort'):
            reservation_ports[get_family_attribute(context, port.Name, 'Logical Name')] = port

        for name, port in config_ports.items():
            if name in reservation_ports:
                address = get_location(reservation_ports[name])
                self.logger.debug(f'Logical Port {name} will be reserved on Physical location {address}')
                if 'offline-debug' not in reservation_ports[name].Name:
                    port.reserve(address, force=True, wait_for_up=False)
                else:
                    self.logger.debug(f'Offline debug port {address} - no actual reservation')
            else:
                raise TgnError(f'Configuration port "{port}" not found in reservation ports {reservation_ports.keys()}')

        self.logger.info('Port Reservation Completed')

    def send_arp(self):
        self.stc.send_arp_ns()

    def start_devices(self):
        self.stc.start_devices()

    def stop_devices(self):
        self.stc.stop_devices()

    def start_traffic(self, blocking):
        self.stc.clear_results()
        self.stc.start_traffic(is_blocking(blocking))

    def stop_traffic(self):
        self.stc.stop_traffic()

    def get_statistics(self, context, view_name, output_type):

        stats_obj = StcStats(view_name)
        stats_obj.read_stats()
        statistics = OrderedDict()
        for obj_name in stats_obj.statistics['topLevelName']:
            statistics[obj_name] = stats_obj.get_object_stats(obj_name)

        if output_type.strip().lower() == 'json':
            statistics_str = json.dumps(statistics, indent=4, sort_keys=True, ensure_ascii=False)
            return json.loads(statistics_str)
        elif output_type.strip().lower() == 'csv':
            captions = statistics[stats_obj.statistics['topLevelName'][0]].keys()
            output = io.StringIO()
            w = csv.DictWriter(output, captions)
            w.writeheader()
            for obj_name in statistics:
                w.writerow(statistics[obj_name])
            attach_stats_csv(context, self.logger, view_name, output.getvalue().strip())
            return output.getvalue().strip()
        else:
            raise TgnError(f'Output type should be CSV/JSON - got "{output_type}"')

    def sequencer_command(self, command):
        if StcSequencerOperation[command.lower()] == StcSequencerOperation.start:
            self.stc.clear_results()
        self.stc.sequencer_command(StcSequencerOperation[command.lower()])

    def get_session_id(self):
        self.logger.info(f'session_id = {self.stc.api.session_id}')
        return self.stc.api.session_id

    def get_children(self, obj_ref, child_type):
        children_attribute = 'children-' + child_type if child_type else 'children'
        return self.stc.api.ls.get(obj_ref, children_attribute).split()

    def get_attributes(self, obj_ref):
        return self.stc.api.ls.get(obj_ref)

    def set_attribute(self, obj_ref, attr_name, attr_value):
        return self.stc.api.ls.config(obj_ref, **{attr_name: attr_value})

    def perform_command(self, command, parameters_json):
        return self.stc.api.ls.perform(command, json.loads(parameters_json))
