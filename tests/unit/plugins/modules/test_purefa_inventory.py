# Copyright: (c) 2025, Simon Dodsley (@sdodsley)
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Unit tests for purefa_inventory module"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import sys
from unittest.mock import MagicMock, Mock, patch

# Mock external dependencies before importing module
sys.modules["grp"] = MagicMock()
sys.modules["pwd"] = MagicMock()
sys.modules["fcntl"] = MagicMock()
sys.modules["ansible"] = MagicMock()
sys.modules["ansible.module_utils"] = MagicMock()
sys.modules["ansible.module_utils.basic"] = MagicMock()
sys.modules["pypureclient"] = MagicMock()
sys.modules["pypureclient.flasharray"] = MagicMock()
sys.modules["ansible_collections"] = MagicMock()
sys.modules["ansible_collections.everpure"] = MagicMock()
sys.modules["ansible_collections.everpure.flasharray"] = MagicMock()
sys.modules["ansible_collections.everpure.flasharray.plugins"] = MagicMock()
sys.modules["ansible_collections.everpure.flasharray.plugins.module_utils"] = (
    MagicMock()
)
sys.modules["ansible_collections.everpure.flasharray.plugins.module_utils.purefa"] = (
    MagicMock()
)
sys.modules["ansible_collections.everpure.flasharray.plugins.module_utils.version"] = (
    MagicMock()
)
sys.modules["ansible_collections.everpure.flasharray.plugins.module_utils.common"] = (
    MagicMock()
)
sys.modules[
    "ansible_collections.everpure.flasharray.plugins.module_utils.api_helpers"
] = MagicMock()
sys.modules[
    "ansible_collections.everpure.flasharray.plugins.module_utils.error_handlers"
] = MagicMock()

# Import after mocking
from plugins.modules.purefa_inventory import main, generate_new_hardware_dict


class TestInventoryMain:
    """Test cases for inventory main function"""

    @patch("plugins.modules.purefa_inventory.generate_new_hardware_dict")
    @patch("plugins.modules.purefa_inventory.get_array")
    @patch("plugins.modules.purefa_inventory.AnsibleModule")
    def test_main_returns_inventory(
        self, mock_ansible_module, mock_get_array, mock_generate
    ):
        """Test main function returns inventory info"""
        mock_module = Mock()
        mock_ansible_module.return_value = mock_module

        mock_array = Mock()
        mock_get_array.return_value = mock_array

        mock_generate.return_value = {
            "fans": {},
            "controllers": {},
            "drives": {},
            "interfaces": {},
            "power": {},
            "chassis": {},
            "temperature": {},
        }

        main()

        mock_module.exit_json.assert_called_once()
        call_args = mock_module.exit_json.call_args
        assert call_args[1]["changed"] is False
        assert "purefa_inv" in call_args[1]


class TestGenerateHardwareDict:
    """Test cases for generate_new_hardware_dict function"""

    @patch("plugins.modules.purefa_inventory.LooseVersion")
    def test_generates_basic_hardware_dict(self, mock_lv):
        """Test generating hardware dict with basic components"""
        mock_array = Mock()

        # Mock old API version (skip SFP details)
        mock_array.get_rest_version.return_value = "2.10"
        mock_lv.side_effect = float

        # Mock hardware components
        mock_chassis = Mock()
        mock_chassis.name = "CH0"
        mock_chassis.type = "chassis"
        mock_chassis.status = "ok"
        mock_chassis.serial = "PCHFL12345"
        mock_chassis.model = "FA-X70"
        mock_chassis.identify_enabled = False

        mock_controller = Mock()
        mock_controller.name = "CT0"
        mock_controller.type = "controller"
        mock_controller.status = "ok"
        mock_controller.serial = "PCTRL001"
        mock_controller.model = "FA-X70-CT0"
        mock_controller.identify_enabled = False

        mock_fan = Mock()
        mock_fan.name = "FAN0"
        mock_fan.type = "cooling"
        mock_fan.status = "ok"

        mock_hardware_response = Mock()
        mock_hardware_response.items = [mock_chassis, mock_controller, mock_fan]
        mock_array.get_hardware.return_value = mock_hardware_response

        # Mock drives
        mock_drive = Mock()
        mock_drive.name = "CH0.BAY0"
        mock_drive.capacity = 1000000000
        mock_drive.status = "healthy"
        mock_drive.type = "SSD"
        mock_drives_response = Mock()
        mock_drives_response.items = [mock_drive]
        mock_array.get_drives.return_value = mock_drives_response

        result = generate_new_hardware_dict(mock_array)

        assert "chassis" in result
        assert "CH0" in result["chassis"]
        assert result["chassis"]["CH0"]["status"] == "ok"
        assert "controllers" in result
        assert "CT0" in result["controllers"]
        assert "fans" in result
        assert "FAN0" in result["fans"]
        assert "drives" in result
        assert "CH0.BAY0" in result["drives"]

    @patch("plugins.modules.purefa_inventory.LooseVersion")
    def test_handles_empty_hardware(self, mock_lv):
        """Test handling of empty hardware list"""
        mock_array = Mock()

        mock_array.get_rest_version.return_value = "2.10"
        mock_lv.side_effect = float

        mock_hardware_response = Mock()
        mock_hardware_response.items = []
        mock_array.get_hardware.return_value = mock_hardware_response

        mock_drives_response = Mock()
        mock_drives_response.items = []
        mock_array.get_drives.return_value = mock_drives_response

        result = generate_new_hardware_dict(mock_array)

        assert result["chassis"] == {}
        assert result["controllers"] == {}
        assert result["fans"] == {}
        assert result["drives"] == {}
        assert result["interfaces"] == {}
        assert result["power"] == {}

    @patch("plugins.modules.purefa_inventory.LooseVersion")
    def test_generates_temp_sensor_dict(self, mock_lv):
        """Test generating hardware dict with temp_sensor components"""
        mock_array = Mock()

        mock_array.get_rest_version.return_value = "2.10"
        mock_lv.side_effect = float

        mock_temp = Mock()
        mock_temp.name = "CT0.TMP0"
        mock_temp.type = "temp_sensor"
        mock_temp.status = "ok"
        mock_temp.temperature = 45

        mock_hardware_response = Mock()
        mock_hardware_response.items = [mock_temp]
        mock_array.get_hardware.return_value = mock_hardware_response

        mock_drives_response = Mock()
        mock_drives_response.items = []
        mock_array.get_drives.return_value = mock_drives_response

        result = generate_new_hardware_dict(mock_array)

        assert "temperature" in result
        assert "CT0.TMP0" in result["temperature"]
        assert result["temperature"]["CT0.TMP0"]["status"] == "ok"
        assert result["temperature"]["CT0.TMP0"]["temperature"] == 45
        # Still reported in controllers as well - deprecated, but removing it
        # would be a breaking change to the returned inventory
        assert result["controllers"]["CT0.TMP0"]["status"] == "ok"
        assert result["controllers"]["CT0.TMP0"]["temperature"] == 45

    @patch("plugins.modules.purefa_inventory.LooseVersion")
    def test_temp_sensor_dicts_are_independent(self, mock_lv):
        """Test the duplicated sensor entries are not the same object"""
        mock_array = Mock()

        mock_array.get_rest_version.return_value = "2.10"
        mock_lv.side_effect = float

        mock_temp = Mock()
        mock_temp.name = "CT0.TMP0"
        mock_temp.type = "temp_sensor"
        mock_temp.status = "ok"
        mock_temp.temperature = 45

        mock_hardware_response = Mock()
        mock_hardware_response.items = [mock_temp]
        mock_array.get_hardware.return_value = mock_hardware_response

        mock_drives_response = Mock()
        mock_drives_response.items = []
        mock_array.get_drives.return_value = mock_drives_response

        result = generate_new_hardware_dict(mock_array)

        assert (
            result["temperature"]["CT0.TMP0"] is not result["controllers"]["CT0.TMP0"]
        )
        assert result["temperature"]["CT0.TMP0"] == result["controllers"]["CT0.TMP0"]

    @patch("plugins.modules.purefa_inventory.LooseVersion")
    def test_generates_drive_bay_dict(self, mock_lv):
        """Test generating hardware dict with drive_bay components"""
        mock_array = Mock()

        mock_array.get_rest_version.return_value = "2.10"
        mock_lv.side_effect = float

        mock_bay = Mock()
        mock_bay.name = "SH0.BAY0"
        mock_bay.type = "drive_bay"
        mock_bay.status = "ok"
        mock_bay.identify_enabled = False
        mock_bay.serial = "BAY001"

        mock_hardware_response = Mock()
        mock_hardware_response.items = [mock_bay]
        mock_array.get_hardware.return_value = mock_hardware_response

        mock_drives_response = Mock()
        mock_drives_response.items = []
        mock_array.get_drives.return_value = mock_drives_response

        result = generate_new_hardware_dict(mock_array)

        assert "drives" in result
        assert "SH0.BAY0" in result["drives"]
        assert result["drives"]["SH0.BAY0"]["status"] == "ok"
        assert result["drives"]["SH0.BAY0"]["serial"] == "BAY001"

    @patch("plugins.modules.purefa_inventory.LooseVersion")
    def test_drive_serial_survives_drives_pass(self, mock_lv):
        """Test drive_bay serial is merged with, not overwritten by, get_drives"""
        mock_array = Mock()

        mock_array.get_rest_version.return_value = "2.10"
        mock_lv.side_effect = float

        mock_bay = Mock()
        mock_bay.name = "CH0.BAY0"
        mock_bay.type = "drive_bay"
        mock_bay.status = "ok"
        mock_bay.identify_enabled = False
        mock_bay.serial = "PFMUH2348229B"

        mock_hardware_response = Mock()
        mock_hardware_response.items = [mock_bay]
        mock_array.get_hardware.return_value = mock_hardware_response

        # Same name as the drive_bay component above - both passes touch this entry
        mock_drive = Mock()
        mock_drive.name = "CH0.BAY0"
        mock_drive.capacity = 2250000000000
        mock_drive.capacity_installed = 2250000000000
        mock_drive.status = "healthy"
        mock_drive.protocol = "NVMe"
        mock_drive.details = None
        mock_drive.type = "SSD"

        mock_drives_response = Mock()
        mock_drives_response.items = [mock_drive]
        mock_array.get_drives.return_value = mock_drives_response

        result = generate_new_hardware_dict(mock_array)

        # From the drive_bay pass
        assert result["drives"]["CH0.BAY0"]["serial"] == "PFMUH2348229B"
        assert result["drives"]["CH0.BAY0"]["identify_enabled"] is False
        # From the get_drives pass
        assert result["drives"]["CH0.BAY0"]["capacity"] == 2250000000000
        assert result["drives"]["CH0.BAY0"]["type"] == "SSD"
        assert result["drives"]["CH0.BAY0"]["status"] == "healthy"

    @patch("plugins.modules.purefa_inventory.LooseVersion")
    def test_generates_nvram_bay_dict(self, mock_lv):
        """Test generating hardware dict with nvram_bay components"""
        mock_array = Mock()

        mock_array.get_rest_version.return_value = "2.10"
        mock_lv.side_effect = float

        mock_nvram_bay = Mock()
        mock_nvram_bay.name = "CH0.NVB0"
        mock_nvram_bay.type = "nvram_bay"
        mock_nvram_bay.status = "ok"
        mock_nvram_bay.identify_enabled = False
        mock_nvram_bay.serial = None

        mock_hardware_response = Mock()
        mock_hardware_response.items = [mock_nvram_bay]
        mock_array.get_hardware.return_value = mock_hardware_response

        mock_drive = Mock()
        mock_drive.name = "CH0.NVB0"
        mock_drive.capacity = 7516192768
        mock_drive.capacity_installed = 7516192768
        mock_drive.status = "healthy"
        mock_drive.protocol = "NVMe"
        mock_drive.details = None
        mock_drive.type = "NVRAM"

        mock_drives_response = Mock()
        mock_drives_response.items = [mock_drive]
        mock_array.get_drives.return_value = mock_drives_response

        result = generate_new_hardware_dict(mock_array)

        assert "CH0.NVB0" in result["drives"]
        assert result["drives"]["CH0.NVB0"]["identify_enabled"] is False
        assert result["drives"]["CH0.NVB0"]["serial"] is None
        assert result["drives"]["CH0.NVB0"]["type"] == "NVRAM"

    @patch("plugins.modules.purefa_inventory.LooseVersion")
    def test_drive_without_hardware_component(self, mock_lv):
        """Test a drive with no matching bay component still has serial keys"""
        mock_array = Mock()

        mock_array.get_rest_version.return_value = "2.10"
        mock_lv.side_effect = float

        mock_hardware_response = Mock()
        mock_hardware_response.items = []
        mock_array.get_hardware.return_value = mock_hardware_response

        mock_drive = Mock()
        mock_drive.name = "CH9.BAY9"
        mock_drive.capacity = 0
        mock_drive.capacity_installed = 0
        mock_drive.status = "unused"
        mock_drive.protocol = None
        mock_drive.details = None
        mock_drive.type = "-"

        mock_drives_response = Mock()
        mock_drives_response.items = [mock_drive]
        mock_array.get_drives.return_value = mock_drives_response

        result = generate_new_hardware_dict(mock_array)

        assert result["drives"]["CH9.BAY9"]["serial"] is None
        assert result["drives"]["CH9.BAY9"]["identify_enabled"] is None
        assert result["drives"]["CH9.BAY9"]["capacity"] == 0

    @patch("plugins.modules.purefa_inventory.LooseVersion")
    def test_generates_network_interfaces_dict(self, mock_lv):
        """Test generating hardware dict with various network port types"""
        mock_array = Mock()

        mock_array.get_rest_version.return_value = "2.10"
        mock_lv.side_effect = float

        mock_fc_port = Mock()
        mock_fc_port.name = "CT0.FC0"
        mock_fc_port.type = "fc_port"
        mock_fc_port.status = "ok"
        mock_fc_port.speed = 32000000000
        mock_fc_port.slot = 3

        mock_eth_port = Mock()
        mock_eth_port.name = "CT0.ETH0"
        mock_eth_port.type = "eth_port"
        mock_eth_port.status = "ok"
        mock_eth_port.speed = 10000000000
        mock_eth_port.slot = None

        mock_hardware_response = Mock()
        mock_hardware_response.items = [mock_fc_port, mock_eth_port]
        mock_array.get_hardware.return_value = mock_hardware_response

        mock_drives_response = Mock()
        mock_drives_response.items = []
        mock_array.get_drives.return_value = mock_drives_response

        result = generate_new_hardware_dict(mock_array)

        assert "interfaces" in result
        assert "CT0.FC0" in result["interfaces"]
        assert result["interfaces"]["CT0.FC0"]["type"] == "fc_port"
        assert "CT0.ETH0" in result["interfaces"]
        assert result["interfaces"]["CT0.ETH0"]["type"] == "eth_port"

    @patch("plugins.modules.purefa_inventory.LooseVersion")
    def test_reports_interface_slot(self, mock_lv):
        """Test slot is reported for PCIe-hosted ports and null for onboard ones"""
        mock_array = Mock()

        mock_array.get_rest_version.return_value = "2.10"
        mock_lv.side_effect = float

        mock_onboard_eth = Mock()
        mock_onboard_eth.name = "CT0.ETH0"
        mock_onboard_eth.type = "eth_port"
        mock_onboard_eth.status = "ok"
        mock_onboard_eth.speed = 0
        mock_onboard_eth.slot = None

        mock_card_eth = Mock()
        mock_card_eth.name = "CT0.ETH8"
        mock_card_eth.type = "eth_port"
        mock_card_eth.status = "ok"
        mock_card_eth.speed = 25000000000
        mock_card_eth.slot = 1

        mock_fc_port = Mock()
        mock_fc_port.name = "CT0.FC0"
        mock_fc_port.type = "fc_port"
        mock_fc_port.status = "ok"
        mock_fc_port.speed = 32000000000
        mock_fc_port.slot = 3

        mock_hardware_response = Mock()
        mock_hardware_response.items = [
            mock_onboard_eth,
            mock_card_eth,
            mock_fc_port,
        ]
        mock_array.get_hardware.return_value = mock_hardware_response

        mock_drives_response = Mock()
        mock_drives_response.items = []
        mock_array.get_drives.return_value = mock_drives_response

        result = generate_new_hardware_dict(mock_array)

        assert result["interfaces"]["CT0.ETH8"]["slot"] == 1
        assert result["interfaces"]["CT0.FC0"]["slot"] == 3
        assert result["interfaces"]["CT0.ETH0"]["slot"] is None

    @patch("plugins.modules.purefa_inventory.LooseVersion")
    def test_generates_power_supply_dict(self, mock_lv):
        """Test generating hardware dict with power_supply components"""
        mock_array = Mock()

        mock_array.get_rest_version.return_value = "2.10"
        mock_lv.side_effect = float

        mock_psu = Mock()
        mock_psu.name = "CH0.PWR0"
        mock_psu.type = "power_supply"
        mock_psu.status = "ok"
        mock_psu.voltage = 12.0
        mock_psu.serial = "PSU001"
        mock_psu.model = "PSU-500W"

        mock_hardware_response = Mock()
        mock_hardware_response.items = [mock_psu]
        mock_array.get_hardware.return_value = mock_hardware_response

        mock_drives_response = Mock()
        mock_drives_response.items = []
        mock_array.get_drives.return_value = mock_drives_response

        result = generate_new_hardware_dict(mock_array)

        assert "power" in result
        assert "CH0.PWR0" in result["power"]
        assert result["power"]["CH0.PWR0"]["status"] == "ok"
        assert result["power"]["CH0.PWR0"]["voltage"] == 12.0
        assert result["power"]["CH0.PWR0"]["serial"] == "PSU001"

    @patch("plugins.modules.purefa_inventory.LooseVersion")
    def test_generates_sfp_port_details(self, mock_lv):
        """Test generating SFP port details when API version >= 2.16"""
        mock_array = Mock()

        # Use API version that supports SFP details
        mock_array.get_rest_version.return_value = "2.20"
        mock_lv.side_effect = float

        # Create an fc_port
        mock_fc_port = Mock()
        mock_fc_port.name = "CT0.FC0"
        mock_fc_port.type = "fc_port"
        mock_fc_port.status = "ok"
        mock_fc_port.speed = 32000000000
        mock_fc_port.slot = 3

        mock_hardware_response = Mock()
        mock_hardware_response.items = [mock_fc_port]
        mock_array.get_hardware.return_value = mock_hardware_response

        mock_drives_response = Mock()
        mock_drives_response.items = []
        mock_array.get_drives.return_value = mock_drives_response

        # Mock port details
        mock_port_detail = Mock()
        mock_port_detail.name = "CT0.FC0"
        mock_port_detail.interface_type = "fc"
        mock_port_detail.rx_los = [Mock(flag=False)]
        mock_port_detail.rx_power = [Mock(measurement=-3.5)]
        mock_port_detail.temperature = [Mock(measurement=40)]
        mock_port_detail.tx_bias = [Mock(measurement=7.5)]
        mock_port_detail.tx_fault = [Mock(flag=False)]
        mock_port_detail.tx_power = [Mock(measurement=-2.5)]
        mock_port_detail.voltage = [Mock(measurement=3.3)]
        mock_port_detail.static = Mock()
        mock_port_detail.static.connector_type = "LC"
        mock_port_detail.static.vendor_name = "Pure Storage"
        mock_port_detail.static.voltage_thresholds = Mock(
            alarm_high=3.6, alarm_low=2.9, warn_high=3.5, warn_low=3.0
        )
        mock_port_detail.static.tx_power_thresholds = Mock(
            alarm_high=0, alarm_low=-10, warn_high=-1, warn_low=-8
        )
        mock_port_detail.static.rx_power_thresholds = Mock(
            alarm_high=0, alarm_low=-15, warn_high=-1, warn_low=-12
        )
        mock_port_detail.static.tx_bias_thresholds = Mock(
            alarm_high=12, alarm_low=1, warn_high=10, warn_low=2
        )
        mock_port_detail.static.temperature_thresholds = Mock(
            alarm_high=75, alarm_low=0, warn_high=70, warn_low=5
        )

        mock_port_details_response = Mock()
        mock_port_details_response.items = [mock_port_detail]
        mock_array.get_network_interfaces_port_details.return_value = (
            mock_port_details_response
        )

        result = generate_new_hardware_dict(mock_array)

        assert "interfaces" in result
        assert "CT0.FC0" in result["interfaces"]
        assert result["interfaces"]["CT0.FC0"]["interface_type"] == "fc"
        assert result["interfaces"]["CT0.FC0"]["rx_los"] is False
        assert result["interfaces"]["CT0.FC0"]["rx_power"] == -3.5
        assert result["interfaces"]["CT0.FC0"]["temperature"] == 40
        assert result["interfaces"]["CT0.FC0"]["tx_bias"] == 7.5
        assert result["interfaces"]["CT0.FC0"]["tx_fault"] is False
        assert result["interfaces"]["CT0.FC0"]["tx_power"] == -2.5
        assert result["interfaces"]["CT0.FC0"]["voltage"] == 3.3

    @patch("plugins.modules.purefa_inventory.LooseVersion")
    def test_port_details_for_port_not_in_hardware(self, mock_lv):
        """Port details can name a port get_hardware did not list (KeyError)"""
        mock_array = Mock()
        mock_array.get_rest_version.return_value = "2.54"
        mock_lv.side_effect = float

        mock_array.get_hardware.return_value = Mock(items=[])
        mock_array.get_drives.return_value = Mock(items=[])

        mock_port_detail = Mock()
        mock_port_detail.name = "CT0.ETH9"
        mock_port_detail.interface_type = "eth"
        mock_port_detail.rx_los = [Mock(flag=False)]
        mock_port_detail.rx_power = [Mock(measurement=-3.5)]
        mock_port_detail.temperature = [Mock(measurement=40)]
        mock_port_detail.tx_bias = [Mock(measurement=7.5)]
        mock_port_detail.tx_fault = [Mock(flag=False)]
        mock_port_detail.tx_power = [Mock(measurement=-2.5)]
        mock_port_detail.voltage = [Mock(measurement=3.3)]
        mock_port_detail.static = Mock()
        mock_port_detail.static.connector_type = "LC"
        mock_array.get_network_interfaces_port_details.return_value = Mock(
            items=[mock_port_detail]
        )

        result = generate_new_hardware_dict(mock_array)

        port = result["interfaces"]["CT0.ETH9"]
        assert port["interface_type"] == "eth"
        assert port["type"] is None
        assert port["status"] is None
        assert port["rx_power"] == -3.5
        assert port["static"]["connector_type"] == "LC"


class FakeComponent:
    """Stand-in for the SDK's Hardware model.

    py-pure-client models raise AttributeError for any field the array
    returned as null rather than returning None. Mock objects do not, so a
    bare attribute access on a field a component leaves unpopulated looks
    fine under Mock and crashes against a real array.
    """

    def __init__(self, **fields):
        self._fields = fields

    def __getattr__(self, name):
        value = self._fields.get(name)
        if value is None:
            raise AttributeError(name)
        return value


class TestOtherHardware:
    """Tests for the other dict - issue #1058"""

    @patch("plugins.modules.purefa_inventory.LooseVersion")
    def test_reports_direct_compress_accelerator(self, mock_lv):
        """Test a DCA is reported in other rather than dropped"""
        mock_array = Mock()

        mock_array.get_rest_version.return_value = "2.54"
        mock_lv.side_effect = float

        # Exactly the payload from issue #1058 - a DCA populates only index,
        # slot, status and type; every other field comes back null
        mock_dca = FakeComponent(
            name="CT0.DCA4",
            type="direct_compress_accelerator",
            status="ok",
            slot=4,
            index=4,
            details=None,
            identify_enabled=None,
            model=None,
            serial=None,
            speed=None,
            temperature=None,
            voltage=None,
        )

        mock_hardware_response = Mock()
        mock_hardware_response.items = [mock_dca]
        mock_array.get_hardware.return_value = mock_hardware_response

        mock_drives_response = Mock()
        mock_drives_response.items = []
        mock_array.get_drives.return_value = mock_drives_response

        # 2.54 is past SFP_API_VERSION, so the port details pass runs
        mock_array.get_network_interfaces_port_details.return_value = Mock(items=[])

        result = generate_new_hardware_dict(mock_array)

        assert "CT0.DCA4" in result["other"]
        dca = result["other"]["CT0.DCA4"]
        assert dca["type"] == "direct_compress_accelerator"
        assert dca["status"] == "ok"
        assert dca["slot"] == 4
        assert dca["index"] == 4
        assert dca["serial"] is None
        assert dca["identify_enabled"] is None
        assert dca["model"] is None
        # and it must not have leaked into any of the other dicts
        assert result["interfaces"] == {}
        assert result["controllers"] == {}
        assert result["drives"] == {}

    @patch("plugins.modules.purefa_inventory.LooseVersion")
    def test_reports_unknown_component_type(self, mock_lv):
        """Test a component type the module has never seen is still reported"""
        mock_array = Mock()

        mock_array.get_rest_version.return_value = "2.54"
        mock_lv.side_effect = float

        mock_widget = FakeComponent(
            name="CT0.WIDGET0",
            type="some_future_component",
            status="healthy",
            index=0,
        )

        mock_hardware_response = Mock()
        mock_hardware_response.items = [mock_widget]
        mock_array.get_hardware.return_value = mock_hardware_response

        mock_drives_response = Mock()
        mock_drives_response.items = []
        mock_array.get_drives.return_value = mock_drives_response

        # 2.54 is past SFP_API_VERSION, so the port details pass runs
        mock_array.get_network_interfaces_port_details.return_value = Mock(items=[])

        result = generate_new_hardware_dict(mock_array)

        assert result["other"]["CT0.WIDGET0"]["type"] == "some_future_component"
        assert result["other"]["CT0.WIDGET0"]["status"] == "healthy"
        assert result["other"]["CT0.WIDGET0"]["voltage"] is None

    @patch("plugins.modules.purefa_inventory.LooseVersion")
    def test_known_component_types_stay_out_of_other(self, mock_lv):
        """Test components with a dedicated dict are not also put in other"""
        mock_array = Mock()

        mock_array.get_rest_version.return_value = "2.54"
        mock_lv.side_effect = float

        known = [
            FakeComponent(
                name="CH0",
                type="chassis",
                status="ok",
                serial="PCHFS12",
                model="FA-X20R3",
                identify_enabled=False,
            ),
            FakeComponent(
                name="CT0",
                type="controller",
                status="ok",
                serial="PCTFS34",
                model="FA-X20R3",
                identify_enabled=False,
            ),
            FakeComponent(name="CT0.FAN0", type="cooling", status="ok"),
            FakeComponent(
                name="CT0.TMP0", type="temp_sensor", status="ok", temperature=45
            ),
            FakeComponent(
                name="CH0.BAY0",
                type="drive_bay",
                status="ok",
                identify_enabled=False,
                serial="BAY001",
            ),
            FakeComponent(
                name="CH0.NVB0",
                type="nvram_bay",
                status="ok",
                identify_enabled=False,
            ),
            FakeComponent(
                name="CT0.ETH0", type="eth_port", status="ok", speed=10000000000
            ),
            FakeComponent(
                name="CT0.FC0", type="fc_port", status="ok", speed=32000000000, slot=3
            ),
            FakeComponent(
                name="CT0.PWR0",
                type="power_supply",
                status="ok",
                voltage=12,
                serial="PWR001",
                model="DS1600",
            ),
        ]

        mock_hardware_response = Mock()
        mock_hardware_response.items = known
        mock_array.get_hardware.return_value = mock_hardware_response

        mock_drives_response = Mock()
        mock_drives_response.items = []
        mock_array.get_drives.return_value = mock_drives_response

        # 2.54 is past SFP_API_VERSION, so the port details pass runs
        mock_array.get_network_interfaces_port_details.return_value = Mock(items=[])

        result = generate_new_hardware_dict(mock_array)

        assert result["other"] == {}
        # spot check the components still landed where they belong
        assert "CH0" in result["chassis"]
        assert "CT0" in result["controllers"]
        assert "CT0.FAN0" in result["fans"]
        assert "CT0.TMP0" in result["temperature"]
        assert "CH0.BAY0" in result["drives"]
        assert "CH0.NVB0" in result["drives"]
        assert "CT0.ETH0" in result["interfaces"]
        assert "CT0.PWR0" in result["power"]

    @patch("plugins.modules.purefa_inventory.LooseVersion")
    def test_other_is_always_present(self, mock_lv):
        """Test other exists even on an array reporting no such components"""
        mock_array = Mock()

        mock_array.get_rest_version.return_value = "2.54"
        mock_lv.side_effect = float

        mock_hardware_response = Mock()
        mock_hardware_response.items = []
        mock_array.get_hardware.return_value = mock_hardware_response

        mock_drives_response = Mock()
        mock_drives_response.items = []
        mock_array.get_drives.return_value = mock_drives_response

        # 2.54 is past SFP_API_VERSION, so the port details pass runs
        mock_array.get_network_interfaces_port_details.return_value = Mock(items=[])

        result = generate_new_hardware_dict(mock_array)

        assert result["other"] == {}
