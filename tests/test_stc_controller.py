"""
Test StcControllerShell2GDriver.
"""
import json
import os
import time
from getpass import getuser
from pathlib import Path

import pytest
from _pytest.fixtures import SubRequest
from cloudshell.api.cloudshell_api import AttributeNameValue, CloudShellAPISession, InputNameValue
from cloudshell.shell.core.driver_context import ResourceCommandContext
from cloudshell.traffic.helpers import get_reservation_id, get_resources_from_reservation, set_family_attribute
from cloudshell.traffic.tg import STC_CHASSIS_MODEL, STC_CONTROLLER_MODEL
from shellfoundry_traffic.test_helpers import TestHelpers, create_session_from_config
from trafficgenerator.tgn_utils import TgnError

from src.stc_driver import StcControllerShell2GDriver

server_511 = "localhost:8888"
ports_511 = ["STC-511/Module1/PG1/Port1", "STC-511/Module1/PG1/Port2"]

server_properties = {"windows_511": {"server": server_511, "ports": ports_511}}

ALIAS = "STC Controller"


@pytest.fixture(params=["windows_511"])
def server(request: SubRequest) -> list:
    controller_address = server_properties[request.param]["server"].split(":")[0]
    controller_port = server_properties[request.param]["server"].split(":")[1]
    ports = server_properties[request.param]["ports"]
    return [controller_address, controller_port, ports]


@pytest.fixture(scope="session")
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
    attributes = {
        f"{STC_CONTROLLER_MODEL}.Address": controller_address,
        f"{STC_CONTROLLER_MODEL}.Controller TCP Port": controller_port,
    }
    init_context = test_helpers.service_init_command_context(STC_CONTROLLER_MODEL, attributes)
    driver = StcControllerShell2GDriver()
    driver.initialize(init_context)
    yield driver
    driver.cleanup()


@pytest.fixture()
def context(session: CloudShellAPISession, test_helpers: TestHelpers, server: list) -> ResourceCommandContext:
    controller_address, controller_port, ports = server
    attributes = [
        AttributeNameValue(f"{STC_CONTROLLER_MODEL}.Address", controller_address),
        AttributeNameValue(f"{STC_CONTROLLER_MODEL}.Controller TCP Port", controller_port),
    ]
    session.AddServiceToReservation(test_helpers.reservation_id, STC_CONTROLLER_MODEL, ALIAS, attributes)
    context = test_helpers.resource_command_context(service_name=ALIAS)
    session.AddResourcesToReservation(test_helpers.reservation_id, ports)
    reservation_ports = get_resources_from_reservation(context, f"{STC_CHASSIS_MODEL}.GenericTrafficGeneratorPort")
    set_family_attribute(context, reservation_ports[0].Name, "Logical Name", "Port 1")
    set_family_attribute(context, reservation_ports[1].Name, "Logical Name", "Port 2")
    yield context


@pytest.fixture
def skip_if_offline(server):
    """Skip test on offline ports."""
    if [p for p in server[2] if "offline-debug" in p]:
        pytest.skip("offline-debug port")


class TestStcControllerDriver:
    """Test direct driver calls."""

    def test_get_set(self, driver: StcControllerShell2GDriver, context: ResourceCommandContext) -> None:
        assert getuser().replace("-", "_") in driver.get_session_id(context)
        assert driver.get_children(context, "system1", "project")[0] == "project1"
        assert driver.get_children(context, "system1")

    def test_load_config(self, driver: StcControllerShell2GDriver, context: ResourceCommandContext) -> None:
        config_file = Path(__file__).parent.joinpath("test_config.xml")
        self._load_config(driver, context, config_file)

    def test_set_device_params(self, driver, context) -> None:
        config_file = Path(__file__).parent.joinpath("test_config.tcc")
        self._load_config(driver, context, config_file)
        project = driver.get_children(context, "system1", "project")[0]
        device = driver.get_children(context, project, "EmulatedDevice")[0]
        old_attributes = driver.get_attributes(context, device)
        driver.set_attribute(context, device, "RouterId", "1.2.3.4")
        new_attributes = driver.get_attributes(context, device)
        assert new_attributes["RouterId"] != old_attributes["RouterId"]
        assert new_attributes["RouterId"] == "1.2.3.4"

    def test_negative(self, driver: StcControllerShell2GDriver, context: ResourceCommandContext) -> None:
        reservation_ports = get_resources_from_reservation(context, "STC Chassis Shell 2G.GenericTrafficGeneratorPort")
        assert len(reservation_ports) == 2
        set_family_attribute(context, reservation_ports[0].Name, "Logical Name", "Port 1")
        set_family_attribute(context, reservation_ports[1].Name, "Logical Name", "")
        with pytest.raises(TgnError):
            driver.load_config(context, Path(__file__).parent.joinpath("test_config.tcc"))
        set_family_attribute(context, reservation_ports[1].Name, "Logical Name", "Port 1")
        with pytest.raises(TgnError):
            driver.load_config(context, Path(__file__).parent.joinpath("test_config.tcc"))
        set_family_attribute(context, reservation_ports[1].Name, "Logical Name", "Port x")
        with pytest.raises(TgnError):
            driver.load_config(context, Path(__file__).parent.joinpath("test_config.tcc"))
        set_family_attribute(context, reservation_ports[1].Name, "Logical Name", "Port 2")

    @pytest.mark.usefixtures("skip_if_offline")
    def test_run_traffic(self, driver: StcControllerShell2GDriver, context: ResourceCommandContext) -> None:
        config_file = Path(__file__).parent.joinpath("test_config.tcc")
        self._load_config(driver, context, config_file)
        driver.send_arp(context)
        driver.start_traffic(context, "False")
        driver.stop_traffic(context)
        stats = driver.get_statistics(context, "generatorportresults", "JSON")
        assert int(stats["Port 1"]["TotalFrameCount"]) <= 4000
        driver.start_traffic(context, "True")
        time.sleep(2)
        stats = driver.get_statistics(context, "generatorportresults", "JSON")
        assert int(stats["Port 1"]["TotalFrameCount"]) >= 4000
        driver.get_statistics(context, "generatorportresults", "csv")

    @pytest.mark.usefixtures("skip_if_offline")
    def test_run_sequencer(self, driver: StcControllerShell2GDriver, context: ResourceCommandContext) -> None:
        config_file = Path(__file__).parent.joinpath("test_sequencer.tcc")
        self._load_config(driver, context, config_file)
        driver.run_quick_test(context, "Start")
        driver.run_quick_test(context, "Wait")

    def _load_config(
        self,
        driver: StcControllerShell2GDriver,
        context: ResourceCommandContext,
        config_file: Path,
    ) -> None:
        reservation_ports = get_resources_from_reservation(context, f"{STC_CHASSIS_MODEL}.GenericTrafficGeneratorPort")
        set_family_attribute(context, reservation_ports[0].Name, "Logical Name", "Port 1")
        set_family_attribute(context, reservation_ports[1].Name, "Logical Name", "Port 2")
        driver.load_config(context, config_file.as_posix())


class TestStcControllerShell:
    """Test indirect Shell calls."""

    def test_session_id(self, session: CloudShellAPISession, context: ResourceCommandContext) -> None:
        session_id = session.ExecuteCommand(get_reservation_id(context), ALIAS, "Service", "get_session_id")
        assert os.environ["COMPUTERNAME"].replace("-", "_") in session_id.Output

        cmd_inputs = [
            InputNameValue("obj_ref", "system1"),
            InputNameValue("child_type", "project"),
        ]
        project = session.ExecuteCommand(get_reservation_id(context), ALIAS, "Service", "get_children", cmd_inputs)
        assert len(json.loads(project.Output)) == 1
        assert json.loads(project.Output)[0] == "project1"

        project_obj = json.loads(project.Output)[0]
        cmd_inputs = [InputNameValue("obj_ref", project_obj)]
        project_children = session.ExecuteCommand(get_reservation_id(context), ALIAS, "Service", "get_children", cmd_inputs)
        assert len(json.loads(project_children.Output)) > 1

        cmd_inputs = [
            InputNameValue("obj_ref", "system1"),
            InputNameValue("child_type", "AutomationOptions"),
        ]
        options = session.ExecuteCommand(get_reservation_id(context), ALIAS, "Service", "get_children", cmd_inputs)
        options_ref = json.loads(options.Output)[0]
        cmd_inputs = [InputNameValue("obj_ref", options_ref)]
        old_options_attrs = session.ExecuteCommand(get_reservation_id(context), ALIAS, "Service", "get_attributes", cmd_inputs)

        cmd_inputs = [
            InputNameValue("obj_ref", options_ref),
            InputNameValue("attr_name", "LogLevel"),
            InputNameValue("attr_value", "INFO"),
        ]
        session.ExecuteCommand(get_reservation_id(context), ALIAS, "Service", "set_attribute", cmd_inputs)
        cmd_inputs = [InputNameValue("obj_ref", options_ref)]
        new_options_attrs = session.ExecuteCommand(get_reservation_id(context), ALIAS, "Service", "get_attributes", cmd_inputs)
        assert json.loads(old_options_attrs.Output)["LogLevel"] != json.loads(new_options_attrs.Output)["LogLevel"]
        assert json.loads(new_options_attrs.Output)["LogLevel"] == "INFO"

        parameters = {
            "Parent": project_obj,
            "ResultParent": project_obj,
            "ConfigType": "Generator",
            "ResultType": "GeneratorPortResults",
        }
        cmd_inputs = [
            InputNameValue("command", "ResultsSubscribe"),
            InputNameValue("parameters_json", json.dumps(parameters)),
        ]
        output = session.ExecuteCommand(get_reservation_id(context), ALIAS, "Service", "perform_command", cmd_inputs)
        assert json.loads(output.Output)["State"] == "COMPLETED"

    def test_load_config(self, session: CloudShellAPISession, context: ResourceCommandContext) -> None:
        self._load_config(session, context, Path(__file__).parent.joinpath("test_config.tcc"))

    @pytest.mark.usefixtures("skip_if_offline")
    def test_run_traffic(self, session: CloudShellAPISession, context: ResourceCommandContext) -> None:
        self._load_config(session, context, Path(__file__).parent.joinpath("test_config.tcc"))
        session.ExecuteCommand(get_reservation_id(context), ALIAS, "Service", "send_arp")
        session.ExecuteCommand(get_reservation_id(context), ALIAS, "Service", "start_protocols")
        cmd_inputs = [InputNameValue("blocking", "True")]
        session.ExecuteCommand(get_reservation_id(context), ALIAS, "Service", "start_traffic", cmd_inputs)
        time.sleep(2)
        cmd_inputs = [
            InputNameValue("view_name", "generatorportresults"),
            InputNameValue("output_type", "JSON"),
        ]
        stats = session.ExecuteCommand(get_reservation_id(context), ALIAS, "Service", "get_statistics", cmd_inputs)
        assert int(json.loads(stats.Output)["Port 1"]["TotalFrameCount"]) >= 4000

    @pytest.mark.usefixtures("skip_if_offline")
    def test_run_sequencer(self, session: CloudShellAPISession, context: ResourceCommandContext) -> None:
        self._load_config(session, context, Path(__file__).parent.joinpath("test_sequencer.tcc"))
        cmd_inputs = [InputNameValue("command", "Start")]
        session.ExecuteCommand(get_reservation_id(context), ALIAS, "Service", "run_quick_test", cmd_inputs)
        cmd_inputs = [InputNameValue("command", "Wait")]
        session.ExecuteCommand(get_reservation_id(context), ALIAS, "Service", "run_quick_test", cmd_inputs)
        time.sleep(2)
        cmd_inputs = [
            InputNameValue("view_name", "generatorportresults"),
            InputNameValue("output_type", "JSON"),
        ]
        stats = session.ExecuteCommand(get_reservation_id(context), ALIAS, "Service", "get_statistics", cmd_inputs)
        assert int(json.loads(stats.Output)["Port 1"]["GeneratorIpv4FrameCount"]) == 8000

    def _load_config(
        self,
        session: CloudShellAPISession,
        context: ResourceCommandContext,
        config: Path,
    ) -> None:
        reservation_ports = get_resources_from_reservation(context, "STC Chassis Shell 2G.GenericTrafficGeneratorPort")
        set_family_attribute(context, reservation_ports[0].Name, "Logical Name", "Port 1")
        set_family_attribute(context, reservation_ports[1].Name, "Logical Name", "Port 2")
        cmd_inputs = [InputNameValue("config_file_location", config.as_posix())]
        session.ExecuteCommand(get_reservation_id(context), ALIAS, "Service", "load_config", cmd_inputs)
