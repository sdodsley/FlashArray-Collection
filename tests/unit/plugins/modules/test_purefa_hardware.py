# Copyright: (c) 2025, Simon Dodsley (@sdodsley)
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Unit tests for purefa_hardware module"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import sys
from unittest.mock import MagicMock, Mock, patch

import pytest

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
from plugins.modules.purefa_hardware import main, wait_for_identify_state


class TestHardwareValidation:
    """Test cases for hardware validation"""

    @patch("plugins.modules.purefa_hardware.HAS_PURESTORAGE", False)
    @patch("plugins.modules.purefa_hardware.AnsibleModule")
    def test_missing_purestorage_dependency_fails(self, mock_ansible_module):
        """Test that missing pypureclient dependency fails"""
        mock_module = Mock()
        mock_module.params = {
            "name": "CH1.FB1",
            "enabled": True,
        }
        mock_module.fail_json.side_effect = SystemExit(1)
        mock_ansible_module.return_value = mock_module

        with pytest.raises(SystemExit):
            main()

        mock_module.fail_json.assert_called_once_with(
            msg="py-pure-client sdk is required for this module"
        )


class TestHardwareNoChange:
    """Test cases for no change scenarios"""

    @patch("plugins.modules.purefa_hardware.get_array")
    @patch("plugins.modules.purefa_hardware.AnsibleModule")
    def test_no_change_when_led_already_matches(
        self, mock_ansible_module, mock_get_array
    ):
        """Test no change when LED state already matches"""
        mock_module = Mock()
        mock_module.check_mode = False
        mock_module.params = {
            "name": "CH1.FB1",
            "enabled": True,
        }
        mock_ansible_module.return_value = mock_module

        mock_array = Mock()
        mock_get_array.return_value = mock_array

        # Mock hardware get response with LED already enabled
        mock_hardware = Mock()
        mock_hardware.identify_enabled = True
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.items = [mock_hardware]
        mock_array.get_hardware.return_value = mock_response

        main()

        mock_module.exit_json.assert_called_once_with(changed=False)

    @patch("plugins.modules.purefa_hardware.get_array")
    @patch("plugins.modules.purefa_hardware.AnsibleModule")
    def test_no_change_when_identify_not_supported(
        self, mock_ansible_module, mock_get_array
    ):
        """Test no change when hardware doesn't support identify LED"""
        mock_module = Mock()
        mock_module.check_mode = False
        mock_module.params = {
            "name": "CH1.FB1",
            "enabled": True,
        }
        mock_ansible_module.return_value = mock_module

        mock_array = Mock()
        mock_get_array.return_value = mock_array

        # Mock hardware without identify_enabled attribute
        mock_hardware = Mock(spec=[])  # Empty spec means no attributes
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.items = [mock_hardware]
        mock_array.get_hardware.return_value = mock_response

        main()

        mock_module.exit_json.assert_called_once_with(changed=False)


class TestHardwareCheckMode:
    """Test cases for check mode"""

    @patch("plugins.modules.purefa_hardware.get_array")
    @patch("plugins.modules.purefa_hardware.AnsibleModule")
    def test_check_mode_reports_change(self, mock_ansible_module, mock_get_array):
        """Test check mode reports change without making it"""
        mock_module = Mock()
        mock_module.check_mode = True
        mock_module.params = {
            "name": "CH1.FB1",
            "enabled": True,
        }
        mock_ansible_module.return_value = mock_module

        mock_array = Mock()
        mock_get_array.return_value = mock_array

        # Mock hardware with LED disabled (different from desired)
        mock_hardware = Mock()
        mock_hardware.identify_enabled = False
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.items = [mock_hardware]
        mock_array.get_hardware.return_value = mock_response

        main()

        mock_module.exit_json.assert_called_once_with(changed=True)
        mock_array.patch_hardware.assert_not_called()


class TestHardwarePatch:
    """The LED is patched with HardwarePatch, and a missing component fails"""

    @patch("plugins.modules.purefa_hardware.time")
    @patch("plugins.modules.purefa_hardware.check_response")
    @patch("plugins.modules.purefa_hardware.flasharray")
    @patch("plugins.modules.purefa_hardware.get_array")
    @patch("plugins.modules.purefa_hardware.AnsibleModule")
    def test_patch_uses_hardware_patch_model(
        self,
        mock_ansible_module,
        mock_get_array,
        mock_flasharray,
        mock_check,
        mock_time,
    ):
        mock_time.monotonic.side_effect = [0, 0, 10]
        """Hardware.identify_enabled is read-only and serialises to an empty
        body, which the array rejects with "No operation was specified"
        """
        mock_module = Mock()
        mock_module.check_mode = False
        mock_module.params = {"name": "CH1.FB1", "enabled": True}
        mock_ansible_module.return_value = mock_module
        mock_array = Mock()
        mock_get_array.return_value = mock_array
        mock_hardware = Mock()
        mock_hardware.identify_enabled = False
        mock_array.get_hardware.return_value = Mock(
            status_code=200, items=[mock_hardware]
        )
        mock_array.patch_hardware.return_value = Mock(status_code=200)

        main()

        mock_flasharray.HardwarePatch.assert_called_once_with(identify_enabled=True)
        mock_flasharray.Hardware.assert_not_called()
        sent = mock_array.patch_hardware.call_args[1]["hardware"]
        assert sent is mock_flasharray.HardwarePatch.return_value
        mock_module.exit_json.assert_called_once_with(changed=True)

    @patch("plugins.modules.purefa_hardware.get_array")
    @patch("plugins.modules.purefa_hardware.AnsibleModule")
    def test_missing_component_fails(self, mock_ansible_module, mock_get_array):
        """A component the array does not know used to exit changed=False"""
        mock_module = Mock()
        mock_module.check_mode = False
        mock_module.params = {"name": "CH9.FB99", "enabled": True}
        mock_module.fail_json.side_effect = SystemExit(1)
        mock_ansible_module.return_value = mock_module
        mock_array = Mock()
        mock_get_array.return_value = mock_array
        mock_array.get_hardware.return_value = Mock(status_code=400, items=[])

        with pytest.raises(SystemExit):
            main()

        mock_module.fail_json.assert_called_once()
        assert "CH9.FB99 does not exist" in mock_module.fail_json.call_args[1]["msg"]
        mock_array.patch_hardware.assert_not_called()


class TestIdentifyStateSettles:
    """The array can report the old identify_enabled right after the PATCH,
    so a repeat run patched again; the module now waits for it to settle
    """

    def _hardware(self, identify_enabled):
        hw = Mock()
        hw.identify_enabled = identify_enabled
        return Mock(status_code=200, items=[hw])

    @patch("plugins.modules.purefa_hardware.time")
    def test_returns_as_soon_as_the_state_matches(self, mock_time):
        mock_time.monotonic.side_effect = [0, 0, 1]
        mock_array = Mock()
        mock_array.get_hardware.side_effect = [
            self._hardware(True),  # stale
            self._hardware(False),  # settled
        ]

        state = wait_for_identify_state(mock_array, "CH1.FB1", False)

        assert state is False
        assert mock_array.get_hardware.call_count == 2
        mock_time.sleep.assert_called_once()

    @patch("plugins.modules.purefa_hardware.time")
    def test_no_wait_when_already_reported(self, mock_time):
        mock_time.monotonic.return_value = 0
        mock_array = Mock()
        mock_array.get_hardware.return_value = self._hardware(False)

        wait_for_identify_state(mock_array, "CH1.FB1", False)

        assert mock_array.get_hardware.call_count == 1
        mock_time.sleep.assert_not_called()

    @patch("plugins.modules.purefa_hardware.time")
    def test_gives_up_after_the_deadline_without_failing(self, mock_time):
        # deadline = 0 + 5; checks at 1 and 6
        mock_time.monotonic.side_effect = [0, 1, 6]
        mock_array = Mock()
        mock_array.get_hardware.return_value = self._hardware(True)

        state = wait_for_identify_state(mock_array, "CH1.FB1", False)

        assert state is True
        assert mock_array.get_hardware.call_count == 2

    @patch("plugins.modules.purefa_hardware.time")
    @patch("plugins.modules.purefa_hardware.check_response")
    @patch("plugins.modules.purefa_hardware.flasharray")
    @patch("plugins.modules.purefa_hardware.get_array")
    @patch("plugins.modules.purefa_hardware.AnsibleModule")
    def test_main_rereads_after_patch_and_stays_changed_when_lagging(
        self,
        mock_ansible_module,
        mock_get_array,
        mock_flasharray,
        mock_check,
        mock_time,
    ):
        mock_time.monotonic.side_effect = [0, 0, 10]
        mock_module = Mock()
        mock_module.check_mode = False
        mock_module.params = {"name": "CH1.FB1", "enabled": False}
        mock_ansible_module.return_value = mock_module
        mock_array = Mock()
        mock_get_array.return_value = mock_array
        mock_array.get_hardware.return_value = self._hardware(True)
        mock_array.patch_hardware.return_value = Mock(status_code=200)

        main()

        mock_array.patch_hardware.assert_called_once()
        # initial read + two settle polls
        assert mock_array.get_hardware.call_count == 3
        mock_module.fail_json.assert_not_called()
        mock_module.exit_json.assert_called_once_with(changed=True)

    @patch("plugins.modules.purefa_hardware.time")
    @patch("plugins.modules.purefa_hardware.get_array")
    @patch("plugins.modules.purefa_hardware.AnsibleModule")
    def test_check_mode_does_not_poll(
        self, mock_ansible_module, mock_get_array, mock_time
    ):
        mock_module = Mock()
        mock_module.check_mode = True
        mock_module.params = {"name": "CH1.FB1", "enabled": False}
        mock_ansible_module.return_value = mock_module
        mock_array = Mock()
        mock_get_array.return_value = mock_array
        mock_array.get_hardware.return_value = self._hardware(True)

        main()

        assert mock_array.get_hardware.call_count == 1
        mock_time.sleep.assert_not_called()
        mock_module.exit_json.assert_called_once_with(changed=True)
