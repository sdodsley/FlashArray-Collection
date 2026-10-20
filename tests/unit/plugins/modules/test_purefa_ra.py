# Copyright: (c) 2026, Everpure Ansible Team <pure-ansible-team@everpuredata.com>
# GNU General Public License v3.0+ (see COPYING.GPLv3 or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Unit tests for purefa_ra module."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import sys
from unittest.mock import Mock, patch, MagicMock

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
sys.modules[
    "ansible_collections.everpure.flasharray.plugins.module_utils.api_helpers"
] = MagicMock()

from plugins.modules.purefa_ra import (
    main,
    enable_ra,
    disable_ra,
    test_ra as ra_test_func,
)


class TestTestRa:
    """Test cases for test_ra function"""

    def test_test_ra_full_result(self):
        """A fully populated TestResult is reported field by field"""
        mock_module = Mock()
        mock_array = Mock()

        mock_component = Mock()
        mock_component.enabled = True
        mock_component.success = True
        mock_component.component_address = "10.0.0.1"
        mock_component.component_name = "ct0"
        mock_component.description = "Remote assist"
        mock_component.destination = "ra.example.com"
        mock_component.result_details = "OK"
        mock_component.test_type = "connectivity"
        mock_component.resource = Mock()
        mock_component.resource.name = "array1"
        mock_array.get_support_test.return_value = Mock(
            status_code=200, items=[mock_component]
        )

        ra_test_func(mock_module, mock_array)

        mock_module.exit_json.assert_called_once()
        call_kwargs = mock_module.exit_json.call_args[1]
        # Running a test is read-only
        assert call_kwargs["changed"] is False
        result = call_kwargs["test_response"][0]
        assert result["enabled"] == "true"
        assert result["success"] == "true"
        assert result["resource_name"] == "array1"
        assert result["component_name"] == "ct0"

    def test_test_ra_sparse_result(self):
        """A TestResult without resource or optional fields must not crash.

        Purity 6.10.6 returns TestResult objects that carry no ``resource``
        and omit several other fields; the SDK model raises AttributeError
        for anything the array did not send.
        """
        mock_module = Mock()
        mock_array = Mock()

        mock_component = Mock(spec=["enabled", "success", "component_name"])
        mock_component.enabled = False
        mock_component.success = False
        mock_component.component_name = "ct1"
        mock_array.get_support_test.return_value = Mock(
            status_code=200, items=[mock_component]
        )

        ra_test_func(mock_module, mock_array)

        mock_module.exit_json.assert_called_once()
        call_kwargs = mock_module.exit_json.call_args[1]
        assert call_kwargs["changed"] is False
        result = call_kwargs["test_response"][0]
        assert result["enabled"] == "false"
        assert result["success"] == "false"
        assert result["component_name"] == "ct1"
        assert result["resource_name"] is None
        assert result["component_address"] is None
        assert result["destination"] is None
        assert result["test_type"] is None
        assert result["result_details"] == ""


class TestEnableRa:
    """Test cases for enable_ra function"""

    @patch("plugins.modules.purefa_ra.LooseVersion")
    def test_enable_ra_success(self, mock_loose_version):
        """Test successful RA enable"""
        mock_loose_version.side_effect = float

        mock_module = Mock()
        mock_module.check_mode = False
        mock_module.params = {"duration": 24}

        mock_array = Mock()
        mock_array.get_rest_version.return_value = "2.38"
        mock_support = Mock()
        mock_support.remote_assist_status = "disabled"
        mock_support_response = Mock()
        mock_support_response.items = [mock_support]
        mock_array.get_support.return_value = mock_support_response

        mock_ra_path = Mock()
        mock_ra_path.component_name = "ct0"
        mock_ra_data = Mock()
        mock_ra_data.remote_assist_paths = [mock_ra_path]
        mock_patch_response = Mock()
        mock_patch_response.status_code = 200
        mock_patch_response.items = [mock_ra_data]
        mock_array.patch_support.return_value = mock_patch_response

        enable_ra(mock_module, mock_array)

        mock_array.patch_support.assert_called_once()
        mock_module.exit_json.assert_called_once()
        call_kwargs = mock_module.exit_json.call_args[1]
        assert call_kwargs["changed"] is True

    def test_enable_ra_already_enabled(self):
        """Test RA enable when already enabled"""
        mock_module = Mock()
        mock_module.check_mode = False
        mock_module.params = {"duration": 24}

        mock_array = Mock()
        mock_support = Mock()
        mock_support.remote_assist_status = "connected"
        mock_ra_path = Mock()
        mock_ra_path.component_name = "ct0"
        mock_support.remote_assist_paths = [mock_ra_path]
        mock_support_response = Mock()
        mock_support_response.status_code = 200
        mock_support_response.items = [mock_support]
        mock_array.get_support.return_value = mock_support_response

        enable_ra(mock_module, mock_array)

        mock_array.patch_support.assert_not_called()
        mock_module.exit_json.assert_called_once()
        call_kwargs = mock_module.exit_json.call_args[1]
        assert call_kwargs["changed"] is False


class TestDisableRa:
    """Test cases for disable_ra function"""

    @patch("plugins.modules.purefa_ra.check_response")
    def test_disable_ra_success(self, mock_check_response):
        """Test successful RA disable"""
        mock_module = Mock()
        mock_module.check_mode = False

        mock_array = Mock()
        mock_support = Mock()
        mock_support.remote_assist_status = "connected"
        mock_support_response = Mock()
        mock_support_response.items = [mock_support]
        mock_array.get_support.return_value = mock_support_response
        mock_patch_response = Mock()
        mock_patch_response.status_code = 200
        mock_array.patch_support.return_value = mock_patch_response

        disable_ra(mock_module, mock_array)

        mock_array.patch_support.assert_called_once()
        mock_check_response.assert_called_once()
        mock_module.exit_json.assert_called_once_with(changed=True)

    def test_disable_ra_already_disabled(self):
        """Test RA disable when already disabled"""
        mock_module = Mock()
        mock_module.check_mode = False

        mock_array = Mock()
        mock_support = Mock()
        mock_support.remote_assist_status = "disabled"
        mock_support_response = Mock()
        mock_support_response.items = [mock_support]
        mock_array.get_support.return_value = mock_support_response

        disable_ra(mock_module, mock_array)

        mock_array.patch_support.assert_not_called()
        mock_module.exit_json.assert_called_once_with(changed=False)


class TestMain:
    """Test cases for main function"""

    @patch("plugins.modules.purefa_ra.get_array")
    @patch("plugins.modules.purefa_ra.AnsibleModule")
    @patch("plugins.modules.purefa_ra.HAS_PURESTORAGE", False)
    def test_main_missing_sdk(self, mock_ansible_module, mock_get_array):
        """Test main when pypureclient SDK is missing"""
        mock_module = Mock()
        mock_module.params = {"state": "present", "duration": 24}
        mock_module.fail_json.side_effect = SystemExit("fail_json called")
        mock_ansible_module.return_value = mock_module

        try:
            main()
        except SystemExit:
            pass

        mock_module.fail_json.assert_called_once()
        call_args = mock_module.fail_json.call_args[1]
        assert "py-pure-client sdk is required" in call_args["msg"]
