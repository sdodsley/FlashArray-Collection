# Copyright: (c) 2025, Simon Dodsley (@sdodsley)
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Unit tests for purefa_eradication module"""

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

# Create mock version module with real LooseVersion
mock_version_module = MagicMock()
from packaging.version import Version as LooseVersion

mock_version_module.LooseVersion = LooseVersion
sys.modules["ansible_collections.everpure.flasharray.plugins.module_utils.version"] = (
    mock_version_module
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
from plugins.modules.purefa_eradication import main


class TestEradicationTimerValidation:
    """Test cases for eradication timer validation"""

    @patch("plugins.modules.purefa_eradication.AnsibleModule")
    def test_timer_out_of_range_fails(self, mock_ansible_module):
        """Test that timer value outside 1-30 range fails"""
        mock_module = Mock()
        mock_module.params = {
            "timer": 31,  # Out of range
            "disabled_delay": 1,
            "enabled_delay": 1,
            "context": "",
        }
        mock_module.fail_json.side_effect = SystemExit(1)
        mock_ansible_module.return_value = mock_module

        with pytest.raises(SystemExit):
            main()

        mock_module.fail_json.assert_called_once_with(
            msg="Eradication Timer must be between 1 and 30 days."
        )

    @patch("plugins.modules.purefa_eradication.AnsibleModule")
    def test_disabled_delay_out_of_range_fails(self, mock_ansible_module):
        """Test that disabled_delay value outside 1-30 range fails"""
        mock_module = Mock()
        mock_module.params = {
            "timer": None,
            "disabled_delay": 31,  # Out of range
            "enabled_delay": 1,
            "context": "",
        }
        mock_module.fail_json.side_effect = SystemExit(1)
        mock_ansible_module.return_value = mock_module

        with pytest.raises(SystemExit):
            main()

        mock_module.fail_json.assert_called_once_with(
            msg="disabled_delay must be between 1 and 30 days."
        )

    @patch("plugins.modules.purefa_eradication.AnsibleModule")
    def test_enabled_delay_out_of_range_fails(self, mock_ansible_module):
        """Test that enabled_delay value outside 1-30 range fails"""
        mock_module = Mock()
        mock_module.params = {
            "timer": None,
            "disabled_delay": 1,
            "enabled_delay": 31,  # Out of range
            "context": "",
        }
        mock_module.fail_json.side_effect = SystemExit(1)
        mock_ansible_module.return_value = mock_module

        with pytest.raises(SystemExit):
            main()

        mock_module.fail_json.assert_called_once_with(
            msg="enabled_delay must be between 1 and 30 days."
        )


class TestEradicationOldApiVersion:
    """Test cases for unsupported API version"""

    @patch("plugins.modules.purefa_eradication.get_with_context")
    @patch("plugins.modules.purefa_eradication.get_array")
    @patch("plugins.modules.purefa_eradication.AnsibleModule")
    def test_old_api_version_fails(
        self,
        mock_ansible_module,
        mock_get_array,
        mock_get_with_context,
    ):
        """Test that old API version fails with appropriate message"""
        mock_module = Mock()
        mock_module.check_mode = False
        mock_module.params = {
            "timer": 7,
            "disabled_delay": 1,
            "enabled_delay": 1,
            "context": "",
        }
        mock_module.fail_json.side_effect = SystemExit(1)
        mock_ansible_module.return_value = mock_module

        mock_array = Mock()
        mock_array.get_rest_version.return_value = "2.4"
        mock_get_array.return_value = mock_array

        # Mock get_with_context for getting config
        mock_eradication_config = Mock()
        mock_eradication_config.eradication_delay = None
        mock_array_info = Mock()
        mock_array_info.eradication_config = mock_eradication_config
        mock_response = Mock()
        mock_response.items = [mock_array_info]
        mock_get_with_context.return_value = mock_response

        with pytest.raises(SystemExit):
            main()

        mock_module.fail_json.assert_called_once_with(
            msg="Purity version does not support changing Eradication Timer"
        )


class TestEradicationMissingDependency:
    """Test cases for missing dependency"""

    @patch("plugins.modules.purefa_eradication.HAS_PURESTORAGE", False)
    @patch("plugins.modules.purefa_eradication.AnsibleModule")
    def test_missing_purestorage_dependency_fails(self, mock_ansible_module):
        """Test that missing pypureclient dependency fails"""
        mock_module = Mock()
        mock_module.params = {
            "timer": 7,
            "disabled_delay": 1,
            "enabled_delay": 1,
            "context": "",
        }
        mock_module.fail_json.side_effect = SystemExit(1)
        mock_ansible_module.return_value = mock_module

        with pytest.raises(SystemExit):
            main()

        mock_module.fail_json.assert_called_once_with(
            msg="py-pure-client sdk is required for this module"
        )


class TestEradicationTimerChange:
    """Test cases for eradication timer changes"""

    @patch("plugins.modules.purefa_eradication.EradicationConfig")
    @patch("plugins.modules.purefa_eradication.Arrays")
    @patch("plugins.modules.purefa_eradication.check_response")
    @patch("plugins.modules.purefa_eradication.get_with_context")
    @patch("plugins.modules.purefa_eradication.get_array")
    @patch("plugins.modules.purefa_eradication.AnsibleModule")
    def test_timer_change_success(
        self,
        mock_ansible_module,
        mock_get_array,
        mock_get_with_context,
        mock_check_response,
        mock_arrays,
        mock_erad_config,
    ):
        """Test that timer change is applied correctly"""
        mock_module = Mock()
        mock_module.check_mode = False
        mock_module.params = {
            "timer": 14,
            "disabled_delay": 1,
            "enabled_delay": 1,
            "context": "",
        }
        mock_ansible_module.return_value = mock_module

        mock_array = Mock()
        mock_array.get_rest_version.return_value = "2.10"
        mock_get_array.return_value = mock_array

        # Mock current eradication config - timer is 7 days (in ms)
        mock_eradication_config = Mock()
        mock_eradication_config.eradication_delay = 7 * 86400000
        mock_eradication_config.disabled_delay = None
        mock_eradication_config.enabled_delay = None
        mock_array_info = Mock()
        mock_array_info.eradication_config = mock_eradication_config
        mock_response = Mock()
        mock_response.items = [mock_array_info]
        mock_get_with_context.return_value = mock_response

        main()

        # Should have changed
        mock_module.exit_json.assert_called_once_with(changed=True)

    @patch("plugins.modules.purefa_eradication.get_with_context")
    @patch("plugins.modules.purefa_eradication.get_array")
    @patch("plugins.modules.purefa_eradication.AnsibleModule")
    def test_timer_no_change_when_same(
        self,
        mock_ansible_module,
        mock_get_array,
        mock_get_with_context,
    ):
        """Test that no change occurs when timer is already at target value"""
        mock_module = Mock()
        mock_module.check_mode = False
        mock_module.params = {
            "timer": 7,
            "disabled_delay": 1,
            "enabled_delay": 1,
            "context": "",
        }
        mock_ansible_module.return_value = mock_module

        mock_array = Mock()
        mock_array.get_rest_version.return_value = "2.10"
        mock_get_array.return_value = mock_array

        # Mock current eradication config - timer is already 7 days
        mock_eradication_config = Mock()
        mock_eradication_config.eradication_delay = 7 * 86400000
        mock_eradication_config.disabled_delay = None
        mock_eradication_config.enabled_delay = None
        mock_array_info = Mock()
        mock_array_info.eradication_config = mock_eradication_config
        mock_response = Mock()
        mock_response.items = [mock_array_info]
        mock_get_with_context.return_value = mock_response

        main()

        mock_module.exit_json.assert_called_once_with(changed=False)

    @patch("plugins.modules.purefa_eradication.get_with_context")
    @patch("plugins.modules.purefa_eradication.get_array")
    @patch("plugins.modules.purefa_eradication.AnsibleModule")
    def test_timer_no_timer_uses_current(
        self,
        mock_ansible_module,
        mock_get_array,
        mock_get_with_context,
    ):
        """Test that no timer param uses current value"""
        mock_module = Mock()
        mock_module.check_mode = False
        mock_module.params = {
            "timer": None,
            "disabled_delay": 1,
            "enabled_delay": 1,
            "context": "",
        }
        mock_ansible_module.return_value = mock_module

        mock_array = Mock()
        mock_array.get_rest_version.return_value = "2.10"
        mock_get_array.return_value = mock_array

        # Mock current eradication config
        mock_eradication_config = Mock()
        mock_eradication_config.eradication_delay = 14 * 86400000
        mock_eradication_config.disabled_delay = None
        mock_eradication_config.enabled_delay = None
        mock_array_info = Mock()
        mock_array_info.eradication_config = mock_eradication_config
        mock_response = Mock()
        mock_response.items = [mock_array_info]
        mock_get_with_context.return_value = mock_response

        main()

        # Timer should be set to current value
        assert mock_module.params["timer"] == 14


class TestEradicationDelayChange:
    """Test cases for eradication delay changes (API >= 2.26)"""

    @patch("plugins.modules.purefa_eradication.EradicationConfig")
    @patch("plugins.modules.purefa_eradication.Arrays")
    @patch("plugins.modules.purefa_eradication.check_response")
    @patch("plugins.modules.purefa_eradication.get_with_context")
    @patch("plugins.modules.purefa_eradication.get_array")
    @patch("plugins.modules.purefa_eradication.AnsibleModule")
    def test_delay_change_success(
        self,
        mock_ansible_module,
        mock_get_array,
        mock_get_with_context,
        mock_check_response,
        mock_arrays,
        mock_erad_config,
    ):
        """Test that delay changes are applied correctly"""
        mock_module = Mock()
        mock_module.check_mode = False
        mock_module.params = {
            "timer": None,
            "disabled_delay": 14,
            "enabled_delay": 7,
            "context": "",
        }
        mock_ansible_module.return_value = mock_module

        mock_array = Mock()
        mock_array.get_rest_version.return_value = "2.30"
        mock_get_array.return_value = mock_array

        # Mock current eradication config with delays (API 2.26+)
        mock_eradication_config = Mock()
        mock_eradication_config.eradication_delay = 7 * 86400000
        mock_eradication_config.disabled_delay = 7 * 86400000
        mock_eradication_config.enabled_delay = 7 * 86400000
        mock_array_info = Mock()
        mock_array_info.eradication_config = mock_eradication_config
        mock_response = Mock()
        mock_response.items = [mock_array_info]
        mock_get_with_context.return_value = mock_response

        main()

        mock_module.exit_json.assert_called_once_with(changed=True)

    @patch("plugins.modules.purefa_eradication.get_with_context")
    @patch("plugins.modules.purefa_eradication.get_array")
    @patch("plugins.modules.purefa_eradication.AnsibleModule")
    def test_delay_no_change_when_same(
        self,
        mock_ansible_module,
        mock_get_array,
        mock_get_with_context,
    ):
        """Test that no change occurs when delays are already at target value"""
        mock_module = Mock()
        mock_module.check_mode = False
        mock_module.params = {
            "timer": None,
            "disabled_delay": 7,
            "enabled_delay": 14,
            "context": "",
        }
        mock_ansible_module.return_value = mock_module

        mock_array = Mock()
        mock_array.get_rest_version.return_value = "2.30"
        mock_get_array.return_value = mock_array

        # Mock current eradication config with same values
        mock_eradication_config = Mock()
        mock_eradication_config.eradication_delay = 7 * 86400000
        mock_eradication_config.disabled_delay = 7 * 86400000
        mock_eradication_config.enabled_delay = 14 * 86400000
        mock_array_info = Mock()
        mock_array_info.eradication_config = mock_eradication_config
        mock_response = Mock()
        mock_response.items = [mock_array_info]
        mock_get_with_context.return_value = mock_response

        main()

        mock_module.exit_json.assert_called_once_with(changed=False)

    @patch("plugins.modules.purefa_eradication.EradicationConfig")
    @patch("plugins.modules.purefa_eradication.Arrays")
    @patch("plugins.modules.purefa_eradication.get_with_context")
    @patch("plugins.modules.purefa_eradication.get_array")
    @patch("plugins.modules.purefa_eradication.AnsibleModule")
    def test_check_mode_no_api_call(
        self,
        mock_ansible_module,
        mock_get_array,
        mock_get_with_context,
        mock_arrays,
        mock_erad_config,
    ):
        """Test that check mode doesn't make API changes"""
        mock_module = Mock()
        mock_module.check_mode = True
        mock_module.params = {
            "timer": 14,
            "disabled_delay": 1,
            "enabled_delay": 1,
            "context": "",
        }
        mock_ansible_module.return_value = mock_module

        mock_array = Mock()
        mock_array.get_rest_version.return_value = "2.30"
        mock_get_array.return_value = mock_array

        # Mock current eradication config - timer needs to change
        mock_eradication_config = Mock()
        mock_eradication_config.eradication_delay = 7 * 86400000
        mock_eradication_config.disabled_delay = 1 * 86400000
        mock_eradication_config.enabled_delay = 1 * 86400000
        mock_array_info = Mock()
        mock_array_info.eradication_config = mock_eradication_config
        mock_response = Mock()
        mock_response.items = [mock_array_info]
        mock_get_with_context.return_value = mock_response

        main()

        # Should report changed=True but not make actual API call
        mock_module.exit_json.assert_called_once_with(changed=True)
        # EradicationConfig should not have been instantiated in check_mode
        mock_erad_config.assert_not_called()


class TestEradicationOneDelayAtATime:
    """Delays not given keep the array's value; diverged delays still work"""

    def _run(self, params, current, check_mode=False):
        with patch(
            "plugins.modules.purefa_eradication.AnsibleModule"
        ) as mock_am, patch(
            "plugins.modules.purefa_eradication.get_array"
        ) as mock_get_array, patch(
            "plugins.modules.purefa_eradication.get_with_context"
        ) as mock_gwc, patch(
            "plugins.modules.purefa_eradication.check_response"
        ), patch(
            "plugins.modules.purefa_eradication.Arrays"
        ), patch(
            "plugins.modules.purefa_eradication.EradicationConfig"
        ) as mock_cfg:
            mock_module = Mock()
            mock_module.check_mode = check_mode
            mock_module.params = {
                "timer": None,
                "disabled_delay": None,
                "enabled_delay": None,
                "context": "",
                **params,
            }
            mock_am.return_value = mock_module
            mock_array = Mock()
            mock_array.get_rest_version.return_value = "2.30"
            mock_get_array.return_value = mock_array
            cfg = Mock()
            cfg.eradication_delay = current.get("eradication_delay")
            cfg.disabled_delay = current["disabled_delay"] * 86400000
            cfg.enabled_delay = current["enabled_delay"] * 86400000
            info = Mock()
            info.eradication_config = cfg
            mock_gwc.return_value = Mock(items=[info])
            main()
            return mock_module, mock_cfg

    def test_only_enabled_delay_keeps_disabled_delay(self):
        """Test enabled_delay alone lengthens it and resends the current disabled_delay"""
        module, cfg = self._run(
            {"enabled_delay": 2}, {"enabled_delay": 1, "disabled_delay": 12}
        )
        cfg.assert_called_once_with(
            enabled_delay=2 * 86400000, disabled_delay=12 * 86400000
        )
        module.exit_json.assert_called_once_with(changed=True)

    def test_only_disabled_delay_keeps_enabled_delay(self):
        """Test disabled_delay alone keeps the current enabled_delay"""
        module, cfg = self._run(
            {"disabled_delay": 14}, {"enabled_delay": 3, "disabled_delay": 12}
        )
        cfg.assert_called_once_with(
            enabled_delay=3 * 86400000, disabled_delay=14 * 86400000
        )
        module.exit_json.assert_called_once_with(changed=True)

    def test_no_parameters_change_nothing(self):
        """Test a call with no timer and no delays is a no-op (it used to set both to a day)"""
        module, cfg = self._run({}, {"enabled_delay": 1, "disabled_delay": 12})
        cfg.assert_not_called()
        module.exit_json.assert_called_once_with(changed=False)

    def test_timer_when_delays_have_diverged_sets_both(self):
        """Test timer still works when the array no longer reports eradication_delay"""
        module, cfg = self._run(
            {"timer": 5}, {"enabled_delay": 1, "disabled_delay": 12}
        )
        cfg.assert_called_once_with(
            enabled_delay=5 * 86400000, disabled_delay=5 * 86400000
        )
        module.exit_json.assert_called_once_with(changed=True)

    def test_out_of_range_delay_still_fails(self):
        """Test the range check still applies to a delay that is given"""
        with patch("plugins.modules.purefa_eradication.AnsibleModule") as mock_am:
            mock_module = Mock()
            mock_module.params = {
                "timer": None,
                "disabled_delay": None,
                "enabled_delay": 31,
                "context": "",
            }
            mock_module.fail_json.side_effect = SystemExit(1)
            mock_am.return_value = mock_module
            with pytest.raises(SystemExit):
                main()
            mock_module.fail_json.assert_called_once_with(
                msg="enabled_delay must be between 1 and 30 days."
            )
