
from os import path
import time
import json
import pytest

from cloudshell.api.cloudshell_api import AttributeNameValue, InputNameValue
from cloudshell.traffic.tg_helper import get_reservation_resources, set_family_attribute
from shellfoundry.releasetools.test_helper import create_session_from_deployment, create_command_context_2g
from src.stc_handler import StcHandler

controller = 'localhost'
port = '8888'

ports = ['offline-debug-STC-494-1/Module1/PG1/Port1', 'offline-debug-STC-494-1/Module1/PG1/Port2']
attributes = [AttributeNameValue(StcHandler.family_name + '.Address', controller),
              AttributeNameValue(StcHandler.family_name + '.Controller TCP Port', port)]


class TestStcControllerShell(object):

    def setup(self):
        self.session = create_session_from_deployment()
        self.context = create_command_context_2g(self.session, ports, StcHandler.family_name, attributes)

    def teardown(self):
        reservation_id = self.context.reservation.reservation_id
        self.session.EndReservation(reservation_id)
        while self.session.GetReservationDetails(reservation_id).ReservationDescription.Status != 'Completed':
            time.sleep(1)
        self.session.DeleteReservation(reservation_id)

    def test_session_id(self):
        session_id = self.session.ExecuteCommand(self.context.reservation.reservation_id, StcHandler.family_name,
                                                 'Service', 'get_session_id')
        print('session_id = {}'.format(session_id.Output))
        project = self.session.ExecuteCommand(self.context.reservation.reservation_id, StcHandler.family_name,
                                              'Service', 'get_children',
                                              [InputNameValue('obj_ref', 'system1'),
                                               InputNameValue('child_type', 'project')])
        print('project = {}'.format(project.Output))
        project_obj = json.loads(project.Output)[0]
        project_childs = self.session.ExecuteCommand(self.context.reservation.reservation_id, StcHandler.family_name,
                                                     'Service', 'get_children',
                                                     [InputNameValue('obj_ref', project_obj)])
        print('Project-Children = {}'.format(project_childs.Output))

        options = self.session.ExecuteCommand(self.context.reservation.reservation_id, StcHandler.family_name,
                                              'Service', 'get_children',
                                              [InputNameValue('obj_ref', 'system1'),
                                               InputNameValue('child_type', 'AutomationOptions')])
        print('AutomationOptions = {}'.format(options.Output))
        options_ref = json.loads(options.Output)[0]
        options_attrs = self.session.ExecuteCommand(self.context.reservation.reservation_id, StcHandler.family_name,
                                                    'Service', 'get_attributes',
                                                    [InputNameValue('obj_ref', options_ref)])
        print('AutomationOptions-Attributes = {}'.format(options_attrs.Output))

        self.session.ExecuteCommand(self.context.reservation.reservation_id, StcHandler.family_name,
                                    'Service', 'set_attribute',
                                    [InputNameValue('obj_ref', options_ref),
                                     InputNameValue('attr_name', 'LogLevel'),
                                     InputNameValue('attr_value', 'INFO')])
        options_attrs = self.session.ExecuteCommand(self.context.reservation.reservation_id, StcHandler.family_name,
                                                    'Service', 'get_attributes',
                                                    [InputNameValue('obj_ref', options_ref)])
        print('AutomationOptions-Attributes = {}'.format(options_attrs.Output))

        parameters = {'Parent': project_obj,
                      'ResultParent': project_obj,
                      'ConfigType': 'Generator',
                      'ResultType': 'GeneratorPortResults'}

        self.session.ExecuteCommand(self.context.reservation.reservation_id, StcHandler.family_name,
                                    'Service', 'perform_command',
                                    [InputNameValue('command', 'ResultsSubscribe'),
                                     InputNameValue('parameters_json', json.dumps(parameters))])

    def test_set_device_params(self):
        self._load_config(path.join(path.dirname(__file__), 'test_config.tcc'))
        project = self.session.ExecuteCommand(self.context.reservation.reservation_id, StcHandler.family_name,
                                              'Service', 'get_children',
                                              [InputNameValue('obj_ref', 'system1'),
                                               InputNameValue('child_type', 'project')])
        project_obj = json.loads(project.Output)[0]

        devices = self.session.ExecuteCommand(self.context.reservation.reservation_id, StcHandler.family_name,
                                              'Service', 'get_children',
                                              [InputNameValue('obj_ref', project_obj),
                                               InputNameValue('child_type', 'EmulatedDevice')])
        devices_obj = json.loads(devices.Output)

        device_obj_1 = devices_obj[0]

        device_1_attrs = self.session.ExecuteCommand(self.context.reservation.reservation_id, StcHandler.family_name,
                                                     'Service', 'get_attributes',
                                                     [InputNameValue('obj_ref', device_obj_1)])
        device_1_attrs_dict = json.loads(device_1_attrs.Output)

        self.session.ExecuteCommand(self.context.reservation.reservation_id, StcHandler.family_name,
                                    'Service', 'set_attribute',
                                    [InputNameValue('obj_ref', device_obj_1),
                                     InputNameValue('attr_name', 'RouterID'),
                                     InputNameValue('attr_value', '1.2.3.4')])

    def test_load_config(self):
        self._load_config(path.join(path.dirname(__file__), 'test_config.tcc'))

    @pytest.mark.skipif([p for p in ports if 'offline-debug' in p], reason='offline-debug port')
    def test_run_traffic(self):
        self._load_config(path.join(path.dirname(__file__), 'test_config.tcc'))
        self.session.ExecuteCommand(self.context.reservation.reservation_id, StcHandler.family_name, 'Service',
                                    'send_arp')
        self.session.ExecuteCommand(self.context.reservation.reservation_id, StcHandler.family_name, 'Service',
                                    'start_devices')
        self.session.ExecuteCommand(self.context.reservation.reservation_id, StcHandler.family_name, 'Service',
                                    'start_traffic', [InputNameValue('blocking', 'True')])
        stats = self.session.ExecuteCommand(self.context.reservation.reservation_id,
                                            StcHandler.family_name, 'Service', 'get_statistics',
                                            [InputNameValue('view_name', 'generatorportresults'),
                                             InputNameValue('output_type', 'JSON')])
        assert(int(json.loads(stats.Output)['Port 1']['TotalFrameCount']) == 4000)

    @pytest.mark.skipif([p for p in ports if 'offline-debug' in p], reason='offline-debug port')
    def test_run_sequencer(self):
        self._load_config(path.join(path.dirname(__file__), 'test_sequencer.tcc'))
        self.session.ExecuteCommand(self.context.reservation.reservation_id, StcHandler.family_name, 'Service',
                                    'sequencer_command', [InputNameValue('command', 'Start')])
        self.session.ExecuteCommand(self.context.reservation.reservation_id, StcHandler.family_name, 'Service',
                                    'sequencer_command', [InputNameValue('command', 'Wait')])
        stats = self.session.ExecuteCommand(self.context.reservation.reservation_id,
                                            StcHandler.family_name, 'Service', 'get_statistics',
                                            [InputNameValue('view_name', 'generatorportresults'),
                                             InputNameValue('output_type', 'JSON')])
        assert(int(json.loads(stats.Output)['Port 1']['GeneratorIpv4FrameCount']) == 8000)

    def _load_config(self, config):
        model = self.context.resource.model
        model = 'STC Chassis Shell 2G'
        reservation_ports = get_reservation_resources(self.session, self.context.reservation.reservation_id,
                                                      'Generic Traffic Generator Port',
                                                      '{}.GenericTrafficGeneratorPort'.format(model))
        set_family_attribute(self.session, reservation_ports[0], 'Logical Name', 'Port 1')
        set_family_attribute(self.session, reservation_ports[1], 'Logical Name', 'Port 2')
        self.session.ExecuteCommand(self.context.reservation.reservation_id, StcHandler.family_name,
                                    'Service', 'load_config', [InputNameValue('config_file_location', config)])
