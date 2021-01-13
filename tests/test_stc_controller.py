"""
Test StcControllerShell2GDriver.
"""
import json
from pathlib import Path

import pytest
from _pytest.fixtures import SubRequest

from cloudshell.api.cloudshell_api import AttributeNameValue, InputNameValue, CloudShellAPISession
from cloudshell.traffic.helpers import get_resources_from_reservation, set_family_attribute, get_reservation_id
from cloudshell.traffic.tg import STC_CONTROLLER_MODEL, STC_CHASSIS_MODEL
from cloudshell.shell.core.driver_context import ResourceCommandContext
from shellfoundry_traffic.test_helpers import create_session_from_config, TestHelpers

from trafficgenerator.tgn_utils import TgnError
from src.stc_driver import StcControllerShell2GDriver


server_505 = '192.168.42.61:8888'
ports_505 = ['STC-511/Module1/PG1/Port1', 'STC-511/Module1/PG1/Port2']

server_properties = {'windows_505': {'server': server_505, 'ports': ports_505}}

ALIAS = 'STC Controller'


@pytest.fixture(params=['windows_505'])
def server(request: SubRequest) -> list:
    controller_address = server_properties[request.param]['server'].split(':')[0]
    controller_port = server_properties[request.param]['server'].split(':')[1]
    ports = server_properties[request.param]['ports']
    return [controller_address, controller_port, ports]


@pytest.fixture(scope='session')
def session() -> CloudShellAPISession:
    yield create_session_from_config()


@pytest.fixture()
def test_helpers(session: CloudShellAPISession) -> TestHelpers:
    test_helpers = TestHelpers(session)
    test_helpers.create_reservation()
    yield test_helpers
    test_helpers.end_reservation()


@pytest.fixture()
def driver(test_helpers: TestHelpers, server: list) -> StcControllerShell2GDriver:
    controller_address, controller_port, _ = server
    attributes = {f'{STC_CONTROLLER_MODEL}.Address': controller_address,
                  f'{STC_CONTROLLER_MODEL}.Controller TCP Port': controller_port}
    init_context = test_helpers.service_init_command_context(STC_CONTROLLER_MODEL, attributes)
    driver = StcControllerShell2GDriver()
    driver.initialize(init_context)
    print(driver.logger.handlers[0].baseFilename)
    yield driver
    driver.cleanup()


@pytest.fixture()
def context(session: CloudShellAPISession, test_helpers: TestHelpers, server: list) -> ResourceCommandContext:
    controller_address, controller_port, ports = server
    attributes = [AttributeNameValue(f'{STC_CONTROLLER_MODEL}.Address', controller_address),
                  AttributeNameValue(f'{STC_CONTROLLER_MODEL}.Controller TCP Port', controller_port)]
    session.AddServiceToReservation(test_helpers.reservation_id, STC_CONTROLLER_MODEL, ALIAS, attributes)
    context = test_helpers.resource_command_context(service_name=ALIAS)
    session.AddResourcesToReservation(test_helpers.reservation_id, ports)
    reservation_ports = get_resources_from_reservation(context, f'{STC_CHASSIS_MODEL}.GenericTrafficGeneratorPort')
    set_family_attribute(context, reservation_ports[0].Name, 'Logical Name', 'Port 1')
    set_family_attribute(context, reservation_ports[1].Name, 'Logical Name', 'Port 2')
    yield context


@pytest.fixture
def skip_if_offline(server):
    """ Skip test on offline ports. """
    if [p for p in server[2] if 'offline-debug' in p]:
        pytest.skip('offline-debug port')


class TestStcControllerDriver:

    def test_get_set(self, driver: StcControllerShell2GDriver, context: ResourceCommandContext) -> None:
        print(f'session_id = {driver.get_session_id(context)}')
        project = driver.get_children(context, 'system1', 'project')[0]
        print(f'project = {project}')
        print(f'all children = {driver.get_children(context, "system1")}')

    def test_load_config(self, driver: StcControllerShell2GDriver, context: ResourceCommandContext) -> None:
        self._load_config(driver, context, Path(__file__).parent.joinpath('test_config.tcc'))

    def test_set_device_params(self, driver, context) -> None:
        self._load_config(driver, context, Path(__file__).parent.joinpath('test_config.tcc'))
        project = driver.get_children(context, 'system1', 'project')[0]
        device = driver.get_children(context, project, 'EmulatedDevice')[0]
        attributes = driver.get_attributes(context, device)
        print(attributes)
        driver.set_attribute(context, device, 'RouterId', '1.2.3.4')

    def test_negative(self, driver: StcControllerShell2GDriver, context: ResourceCommandContext) -> None:
        reservation_ports = get_resources_from_reservation(context, 'STC Chassis Shell 2G.GenericTrafficGeneratorPort')
        assert(len(reservation_ports) == 2)
        set_family_attribute(context, reservation_ports[0].Name, 'Logical Name', 'Port 1')
        set_family_attribute(context, reservation_ports[1].Name, 'Logical Name', '')
        with pytest.raises(TgnError):
            driver.load_config(context, Path(__file__).parent.joinpath('test_config.tcc'))
        set_family_attribute(context, reservation_ports[1].Name, 'Logical Name', 'Port 1')
        with pytest.raises(TgnError):
            driver.load_config(context, Path(__file__).parent.joinpath('test_config.tcc'))
        set_family_attribute(context, reservation_ports[1].Name, 'Logical Name', 'Port x')
        with pytest.raises(TgnError):
            driver.load_config(context, Path(__file__).parent.joinpath('test_config.tcc'))
        set_family_attribute(context, reservation_ports[1].Name, 'Logical Name', 'Port 2')

    @pytest.mark.usefixtures('skip_if_offline')
    def test_run_traffic(self, driver: StcControllerShell2GDriver, context: ResourceCommandContext) -> None:
        self._load_config(driver, context, Path(__file__).parent.joinpath('test_config.tcc'))
        driver.send_arp(context)
        driver.start_traffic(context, 'False')
        driver.stop_traffic(context)
        stats = driver.get_statistics(context, 'generatorportresults', 'JSON')
        assert(int(stats['Port 1']['TotalFrameCount']) <= 4000)
        driver.start_traffic(context, 'True')
        stats = driver.get_statistics(context, 'generatorportresults', 'JSON')
        assert(int(stats['Port 1']['TotalFrameCount']) >= 4000)
        stats = driver.get_statistics(context, 'generatorportresults', 'csv')
        print(stats)

    @pytest.mark.usefixtures('skip_if_offline')
    def test_run_sequencer(self, driver: StcControllerShell2GDriver, context: ResourceCommandContext) -> None:
        self._load_config(driver, context, Path(__file__).parent.joinpath('test_sequencer.tcc'))
        driver.run_quick_test(context, 'Start')
        driver.run_quick_test(context, 'Wait')

    def _load_config(self, driver: StcControllerShell2GDriver, context: ResourceCommandContext,
                     config_file: str) -> None:
        reservation_ports = get_resources_from_reservation(context, f'{STC_CHASSIS_MODEL}.GenericTrafficGeneratorPort')
        set_family_attribute(context, reservation_ports[0].Name, 'Logical Name', 'Port 1')
        set_family_attribute(context, reservation_ports[1].Name, 'Logical Name', 'Port 2')
        driver.load_config(context, config_file)


class TestStcControllerShell:

    def test_session_id(self, session: CloudShellAPISession, context: ResourceCommandContext) -> None:
        session_id = session.ExecuteCommand(get_reservation_id(context), ALIAS, 'Service', 'get_session_id')
        print(f'session_id = {session_id.Output}')
        project = session.ExecuteCommand(get_reservation_id(context), ALIAS,
                                         'Service', 'get_children',
                                         [InputNameValue('obj_ref', 'system1'),
                                          InputNameValue('child_type', 'project')])
        print(f'project = {project.Output}')
        project_obj = json.loads(project.Output)[0]
        project_childs = session.ExecuteCommand(get_reservation_id(context), ALIAS,
                                                'Service', 'get_children',
                                                [InputNameValue('obj_ref', project_obj)])
        print(f'Project-Children = {project_childs.Output}')

        options = session.ExecuteCommand(get_reservation_id(context), ALIAS,
                                         'Service', 'get_children',
                                         [InputNameValue('obj_ref', 'system1'),
                                          InputNameValue('child_type', 'AutomationOptions')])
        print(f'AutomationOptions = {options.Output}')
        options_ref = json.loads(options.Output)[0]
        options_attrs = session.ExecuteCommand(get_reservation_id(context), ALIAS,
                                               'Service', 'get_attributes',
                                               [InputNameValue('obj_ref', options_ref)])
        print(f'AutomationOptions-Attributes = {options_attrs.Output}')

        session.ExecuteCommand(get_reservation_id(context), ALIAS,
                               'Service', 'set_attribute',
                               [InputNameValue('obj_ref', options_ref),
                                InputNameValue('attr_name', 'LogLevel'),
                                InputNameValue('attr_value', 'INFO')])
        options_attrs = session.ExecuteCommand(get_reservation_id(context), ALIAS,
                                               'Service', 'get_attributes',
                                               [InputNameValue('obj_ref', options_ref)])
        print(f'AutomationOptions-Attributes = {options_attrs.Output}')

        parameters = {'Parent': project_obj,
                      'ResultParent': project_obj,
                      'ConfigType': 'Generator',
                      'ResultType': 'GeneratorPortResults'}
        session.ExecuteCommand(get_reservation_id(context), ALIAS,
                               'Service', 'perform_command',
                               [InputNameValue('command', 'ResultsSubscribe'),
                                InputNameValue('parameters_json', json.dumps(parameters))])

    def test_load_config(self, session: CloudShellAPISession, context: ResourceCommandContext) -> None:
        self._load_config(session, context, Path(__file__).parent.joinpath('test_config.tcc'))

    def test_set_device_params(self, session: CloudShellAPISession, context: ResourceCommandContext) -> None:
        self._load_config(session, context, Path(__file__).parent.joinpath('test_config.tcc'))
        project = session.ExecuteCommand(get_reservation_id(context), ALIAS,
                                         'Service', 'get_children',
                                         [InputNameValue('obj_ref', 'system1'),
                                          InputNameValue('child_type', 'project')])
        project_obj = json.loads(project.Output)[0]

        devices = session.ExecuteCommand(get_reservation_id(context), ALIAS,
                                         'Service', 'get_children',
                                         [InputNameValue('obj_ref', project_obj),
                                          InputNameValue('child_type', 'EmulatedDevice')])
        devices_obj = json.loads(devices.Output)

        device_obj_1 = devices_obj[0]
        device_1_attrs = session.ExecuteCommand(get_reservation_id(context), ALIAS,
                                                'Service', 'get_attributes',
                                                [InputNameValue('obj_ref', device_obj_1)])
        device_1_attrs_dict = json.loads(device_1_attrs.Output)
        print(device_1_attrs_dict)
        session.ExecuteCommand(get_reservation_id(context), ALIAS,
                               'Service', 'set_attribute',
                               [InputNameValue('obj_ref', device_obj_1),
                                InputNameValue('attr_name', 'RouterID'),
                                InputNameValue('attr_value', '1.2.3.4')])

    @pytest.mark.usefixtures('skip_if_offline')
    def test_run_traffic(self, session: CloudShellAPISession, context: ResourceCommandContext) -> None:
        self._load_config(session, context, Path(__file__).parent.joinpath('test_config.tcc'))
        session.ExecuteCommand(get_reservation_id(context), ALIAS, 'Service',
                               'send_arp')
        session.ExecuteCommand(get_reservation_id(context), ALIAS, 'Service',
                               'start_protocols')
        session.ExecuteCommand(get_reservation_id(context), ALIAS, 'Service',
                               'start_traffic', [InputNameValue('blocking', 'True')])
        stats = session.ExecuteCommand(get_reservation_id(context),
                                       ALIAS, 'Service', 'get_statistics',
                                       [InputNameValue('view_name', 'generatorportresults'),
                                        InputNameValue('output_type', 'JSON')])
        assert (int(json.loads(stats.Output)['Port 1']['TotalFrameCount']) == 4000)

    @pytest.mark.usefixtures('skip_if_offline')
    def test_run_sequencer(self, session: CloudShellAPISession, context: ResourceCommandContext) -> None:
        self._load_config(session, context, Path(__file__).parent.joinpath('test_sequencer.tcc'))
        session.ExecuteCommand(get_reservation_id(context), ALIAS, 'Service',
                               'run_quick_test', [InputNameValue('command', 'Start')])
        session.ExecuteCommand(get_reservation_id(context), ALIAS, 'Service',
                               'run_quick_test', [InputNameValue('command', 'Wait')])
        stats = session.ExecuteCommand(get_reservation_id(context),
                                       ALIAS, 'Service', 'get_statistics',
                                       [InputNameValue('view_name', 'generatorportresults'),
                                        InputNameValue('output_type', 'JSON')])
        assert (int(json.loads(stats.Output)['Port 1']['GeneratorIpv4FrameCount']) == 8000)

    def _load_config(self, session: CloudShellAPISession, context: ResourceCommandContext, config: Path) -> None:
        reservation_ports = get_resources_from_reservation(context, 'STC Chassis Shell 2G.GenericTrafficGeneratorPort')
        set_family_attribute(context, reservation_ports[0].Name, 'Logical Name', 'Port 1')
        set_family_attribute(context, reservation_ports[1].Name, 'Logical Name', 'Port 2')
        session.ExecuteCommand(get_reservation_id(context), ALIAS, 'Service', 'load_config',
                               [InputNameValue('config_file_location', config.as_posix())])
