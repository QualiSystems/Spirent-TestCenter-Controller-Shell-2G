
from pathlib import Path

import pytest

from cloudshell.api.cloudshell_api import AttributeNameValue
from cloudshell.traffic.helpers import add_resources_to_reservation, get_resources_from_reservation, set_family_attribute, get_reservation_id
from cloudshell.traffic.tg import STC_CONTROLLER_MODEL
from shellfoundry.releasetools.test_helper import create_session_from_deployment, create_init_command_context, create_service_command_context, end_reservation

from trafficgenerator.tgn_utils import TgnError
from src.stc_driver import StcControllerShell2GDriver


server_505 = 'localhost:8888'
ports_505 = ['offline-debug-STC-505/Module1/PG1/Port1', 'offline-debug-STC-505/Module1/PG1/Port2']

server_properties = {'windows_505': {'server': server_505, 'ports': ports_505}}


@pytest.fixture()
def alias() -> str:
    yield 'STC Controller'


@pytest.fixture(params=['windows_505'])
def server(request):
    controller_address = server_properties[request.param]['server'].split(':')[0]
    controller_port = server_properties[request.param]['server'].split(':')[1]
    ports = server_properties[request.param]['ports']
    yield controller_address, controller_port, ports


@pytest.fixture()
def session():
    yield create_session_from_deployment()


@pytest.fixture()
def driver(session, server):
    controller_address, controller_port, _ = server
    attributes = {f'{STC_CONTROLLER_MODEL}.Address': controller_address,
                  f'{STC_CONTROLLER_MODEL}.Controller TCP Port': controller_port}
    init_context = create_init_command_context(session, 'CS_TrafficGeneratorController', STC_CONTROLLER_MODEL,
                                               controller_address, attributes, 'Service')
    driver = StcControllerShell2GDriver()
    driver.initialize(init_context)
    print(driver.logger.handlers[0].baseFilename)
    yield driver
    driver.cleanup()


@pytest.fixture()
def context(session, alias, server):
    controller_address, controller_port, ports = server
    attributes = [AttributeNameValue(f'{STC_CONTROLLER_MODEL}.Address', controller_address),
                  AttributeNameValue(f'{STC_CONTROLLER_MODEL}.Controller TCP Port', controller_port)]
    context = create_service_command_context(session, STC_CONTROLLER_MODEL, alias, attributes)
    add_resources_to_reservation(context, *ports)
    reservation_ports = get_resources_from_reservation(context, 'STC Chassis Shell 2G.GenericTrafficGeneratorPort')
    set_family_attribute(context, reservation_ports[0].Name, 'Logical Name', 'Port 1')
    set_family_attribute(context, reservation_ports[1].Name, 'Logical Name', 'Port 2')
    yield context
    end_reservation(session, get_reservation_id(context))


@pytest.fixture
def skip_if_offline(server):
    """ Skip test on offline ports. """
    if [p for p in server[2] if 'offline-debug' in p]:
        pytest.skip('offline-debug port')


class TestStcControllerDriver:

    def test_get_set(self, driver, context):
        print(f'session_id = {driver.get_session_id(context)}')
        project = driver.get_children(context, 'system1', 'project')[0]
        print(f'project = {project}')
        print(f'all children = {driver.get_children(context, "system1")}')

    def test_load_config(self, driver, context):
        self._load_config(driver, context, Path(__file__).parent.joinpath('test_config.tcc'))

    def test_set_device_params(self, driver, context):
        self._load_config(driver, context, Path(__file__).parent.joinpath('test_config.tcc'))
        project = driver.get_children(context, 'system1', 'project')[0]
        device = driver.get_children(context, project, 'EmulatedDevice')[0]
        attributes = driver.get_attributes(context, device)
        print(attributes)
        driver.set_attribute(context, device, 'RouterId', '1.2.3.4')

    def test_negative(self, driver, context):
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
    def test_run_traffic(self, driver, context):
        self._load_config(driver, context, Path(__file__).parent.joinpath('test_config.tcc'))
        driver.send_arp(context)
        driver.start_traffic(context, 'False')
        driver.stop_traffic(context)
        stats = driver.get_statistics(context, 'generatorportresults', 'JSON')
        assert(int(stats['Port 1']['TotalFrameCount']) <= 4000)
        driver.start_traffic(context, 'True')
        stats = driver.get_statistics(context, 'generatorportresults', 'JSON')
        assert(int(stats['Port 1']['TotalFrameCount']) == 4000)
        stats = driver.get_statistics(context, 'generatorportresults', 'csv')
        print(stats)

    @pytest.mark.usefixtures('skip_if_offline')
    def test_run_sequencer(self, driver, context):
        self._load_config(driver, context, Path(__file__).parent.joinpath('test_sequencer.tcc'))
        driver.run_quick_test(context, 'Start')
        driver.run_quick_test(context, 'Wait')

    def _load_config(self, driver, context, config_file):
        reservation_ports = get_resources_from_reservation(context, 'STC Chassis Shell 2G.GenericTrafficGeneratorPort')
        set_family_attribute(context, reservation_ports[0].Name, 'Logical Name', 'Port 1')
        set_family_attribute(context, reservation_ports[1].Name, 'Logical Name', 'Port 2')
        driver.load_config(context, config_file)
