# Copyright: (c) 2026, Everpure Ansible Team <pure-ansible-team@everpuredata.com>
# GNU General Public License v3.0+ (see COPYING.GPLv3 or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Unit tests for purefa_snmp module."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import sys
from unittest.mock import Mock, MagicMock

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
sys.modules["ansible_collections.everpure.flasharray.plugins.module_utils.common"] = (
    MagicMock()
)
sys.modules[
    "ansible_collections.everpure.flasharray.plugins.module_utils.api_helpers"
] = MagicMock()
sys.modules[
    "ansible_collections.everpure.flasharray.plugins.module_utils.error_handlers"
] = MagicMock()

# Create a mock version module with real LooseVersion
mock_version_module = MagicMock()
from packaging.version import Version as LooseVersion

mock_version_module.LooseVersion = LooseVersion
sys.modules["ansible_collections.everpure.flasharray.plugins.module_utils.version"] = (
    mock_version_module
)

from unittest.mock import patch

from plugins.modules.purefa_snmp import (
    delete_manager,
    create_manager,
    update_manager,
    test_manager as snmp_test_manager,
)


class TestDeleteManager:
    """Tests for delete_manager function"""

    def test_delete_manager_check_mode(self):
        """Test delete_manager in check mode"""
        mock_module = Mock()
        mock_module.params = {"name": "snmp1"}
        mock_module.check_mode = True
        mock_array = Mock()

        delete_manager(mock_module, mock_array)

        mock_module.exit_json.assert_called_once_with(changed=True)
        mock_array.delete_snmp_managers.assert_not_called()

    def test_delete_manager_success(self):
        """Test delete_manager successfully deletes"""
        mock_module = Mock()
        mock_module.params = {"name": "snmp1"}
        mock_module.check_mode = False
        mock_array = Mock()
        mock_array.delete_snmp_managers.return_value = Mock(status_code=200)

        delete_manager(mock_module, mock_array)

        mock_array.delete_snmp_managers.assert_called_once_with(names=["snmp1"])
        mock_module.exit_json.assert_called_with(changed=True)


class TestCreateManager:
    """Tests for create_manager function"""

    def test_create_manager_check_mode(self):
        """Test create_manager in check mode"""
        mock_module = Mock()
        mock_module.params = {
            "name": "snmp1",
            "version": "v2c",
            "host": "192.168.1.100",
            "community": "public",
            "notification": "trap",
        }
        mock_module.check_mode = True
        mock_array = Mock()

        create_manager(mock_module, mock_array)

        mock_module.exit_json.assert_called_once_with(changed=True)
        mock_array.post_snmp_managers.assert_not_called()

    @patch("plugins.modules.purefa_snmp.check_response")
    def test_create_manager_v2c_success(self, mock_check_response):
        """Test create_manager with v2c version"""
        mock_module = Mock()
        mock_module.params = {
            "name": "snmp1",
            "version": "v2c",
            "host": "192.168.1.100",
            "community": "public",
            "notification": "trap",
        }
        mock_module.check_mode = False
        mock_array = Mock()
        mock_array.post_snmp_managers.return_value = Mock(status_code=200)

        create_manager(mock_module, mock_array)

        mock_array.post_snmp_managers.assert_called_once()
        mock_module.exit_json.assert_called_with(changed=True)


class TestSnmpTestManager:
    """Tests for test_manager function"""

    def test_snmp_test_manager_success(self):
        """Test test_manager returns test results"""
        mock_module = Mock()
        mock_module.params = {"name": "snmp1"}
        mock_array = Mock()

        # Create mock test response component
        mock_component = Mock()
        mock_component.enabled = True
        mock_component.success = True
        mock_component.component_address = "192.168.1.100"
        mock_component.component_name = "snmp1"
        mock_component.description = "Test description"
        mock_component.destination = "192.168.1.200"
        mock_component.result_details = "Success"
        mock_component.test_type = "trap"
        mock_component.resource = Mock()
        mock_component.resource.name = "test-resource"

        mock_array.get_snmp_managers_test.return_value.items = [mock_component]

        snmp_test_manager(mock_module, mock_array)

        mock_array.get_snmp_managers_test.assert_called_once_with(names=["snmp1"])
        mock_module.exit_json.assert_called_once()
        call_args = mock_module.exit_json.call_args
        # Running a test is read-only
        assert call_args[1]["changed"] is False
        assert len(call_args[1]["test_response"]) == 1
        assert call_args[1]["test_response"][0]["enabled"] == "true"
        assert call_args[1]["test_response"][0]["success"] == "true"

    def test_snmp_test_manager_disabled_and_failed(self):
        """Test test_manager with disabled and failed component"""
        mock_module = Mock()
        mock_module.params = {"name": "snmp1"}
        mock_array = Mock()

        mock_component = Mock()
        mock_component.enabled = False
        mock_component.success = False
        mock_component.component_address = "192.168.1.100"
        mock_component.component_name = "snmp1"
        mock_component.description = "Test description"
        mock_component.destination = "192.168.1.200"
        mock_component.test_type = "trap"
        mock_component.resource = Mock()
        mock_component.resource.name = "test-resource"
        # No result_details attribute
        del mock_component.result_details

        mock_array.get_snmp_managers_test.return_value.items = [mock_component]

        snmp_test_manager(mock_module, mock_array)

        call_args = mock_module.exit_json.call_args
        assert call_args[1]["test_response"][0]["enabled"] == "false"
        assert call_args[1]["test_response"][0]["success"] == "false"

    def test_snmp_test_manager_sparse_result(self):
        """A TestResult without resource or optional fields must not crash"""
        mock_module = Mock()
        mock_module.params = {"name": "snmp1"}
        mock_array = Mock()

        mock_component = Mock(spec=["enabled", "success", "component_name"])
        mock_component.enabled = True
        mock_component.success = False
        mock_component.component_name = "ct0"
        mock_array.get_snmp_managers_test.return_value = Mock(
            status_code=200, items=[mock_component]
        )

        snmp_test_manager(mock_module, mock_array)

        result = mock_module.exit_json.call_args[1]["test_response"][0]
        assert result["enabled"] == "true"
        assert result["success"] == "false"
        assert result["component_name"] == "ct0"
        assert result["resource_name"] is None
        assert result["destination"] is None
        assert result["component_address"] is None
        assert result["test_type"] is None
        assert result["result_details"] == ""

    @patch("plugins.modules.purefa_snmp.check_response")
    def test_snmp_test_manager_error_response(self, mock_check_response):
        """An error response from the array fails cleanly instead of crashing.

        Testing a manager at an unreachable address makes the array return
        an ErrorResponse, which has no ``items`` attribute.
        """
        import pytest

        mock_module = Mock()
        mock_module.params = {"name": "snmp1"}
        mock_module.fail_json.side_effect = SystemExit(1)
        mock_array = Mock()
        mock_error = Mock()
        mock_error.message = "Unable to reach manager"
        # No "items" in the spec, so touching it would raise AttributeError
        error_response = Mock(spec=["status_code", "errors"])
        error_response.status_code = 400
        error_response.errors = [mock_error]
        mock_array.get_snmp_managers_test.return_value = error_response

        def fail(res, module, operation):
            module.fail_json(msg=f"{operation} failed. Error: {res.errors[0].message}")

        mock_check_response.side_effect = fail

        with pytest.raises(SystemExit):
            snmp_test_manager(mock_module, mock_array)

        mock_check_response.assert_called_once()
        assert mock_check_response.call_args[0][0] is error_response
        mock_module.fail_json.assert_called_once_with(
            msg="Test of SNMP manager snmp1 failed. Error: Unable to reach manager"
        )
        mock_module.exit_json.assert_not_called()


class TestUpdateManager:
    """Test cases for update_manager function"""

    @patch("plugins.modules.purefa_snmp.check_response")
    def test_update_manager_version_change_fails(self, mock_check_response):
        """Test update_manager fails when version changes"""
        import pytest

        mock_module = Mock()
        mock_module.check_mode = False
        mock_module.fail_json.side_effect = SystemExit(1)
        mock_module.params = {
            "name": "snmp1",
            "version": "v3",
        }
        mock_array = Mock()
        mock_mgr = Mock()
        mock_mgr.version = "v2c"  # Different from params
        mock_array.get_snmp_managers.return_value = Mock(
            status_code=200, items=[mock_mgr]
        )

        with pytest.raises(SystemExit):
            update_manager(mock_module, mock_array)

        mock_module.fail_json.assert_called_once()

    @patch("plugins.modules.purefa_snmp.check_response")
    def test_update_manager_v2c_check_mode(self, mock_check_response):
        """Test update_manager v2c in check mode"""
        mock_module = Mock()
        mock_module.check_mode = True
        mock_module.params = {
            "name": "snmp1",
            "version": "v2c",
            "community": "public",
            "notification": "trap",
            "host": "192.168.1.100",
        }
        mock_array = Mock()
        mock_mgr = Mock()
        mock_mgr.version = "v2c"
        mock_array.get_snmp_managers.return_value = Mock(
            status_code=200, items=[mock_mgr]
        )

        update_manager(mock_module, mock_array)

        mock_array.patch_snmp_managers.assert_not_called()
        mock_module.exit_json.assert_called_once_with(changed=True)

    @patch("plugins.modules.purefa_snmp.check_response")
    def test_update_manager_v2c_success(self, mock_check_response):
        """Test update_manager v2c succeeds"""
        mock_module = Mock()
        mock_module.check_mode = False
        mock_module.params = {
            "name": "snmp1",
            "version": "v2c",
            "community": "public",
            "notification": "trap",
            "host": "192.168.1.100",
        }
        mock_array = Mock()
        mock_mgr = Mock()
        mock_mgr.version = "v2c"
        mock_array.get_snmp_managers.return_value = Mock(
            status_code=200, items=[mock_mgr]
        )
        mock_array.patch_snmp_managers.return_value = Mock(status_code=200)

        update_manager(mock_module, mock_array)

        mock_array.patch_snmp_managers.assert_called_once()
        mock_module.exit_json.assert_called_once_with(changed=True)

    @patch("plugins.modules.purefa_snmp.check_response")
    def test_update_manager_v2c_no_change(self, mock_check_response):
        """A v2c manager whose host and notification match is left alone"""
        mock_module = Mock()
        mock_module.check_mode = False
        mock_module.params = {
            "name": "snmp1",
            "version": "v2c",
            "community": "public",
            "notification": "trap",
            "host": "192.168.1.100",
        }
        mock_array = Mock()
        mock_mgr = Mock()
        mock_mgr.version = "v2c"
        mock_mgr.host = "192.168.1.100"
        mock_mgr.notification = "trap"
        mock_array.get_snmp_managers.return_value = Mock(
            status_code=200, items=[mock_mgr]
        )

        update_manager(mock_module, mock_array)

        mock_array.patch_snmp_managers.assert_not_called()
        mock_module.exit_json.assert_called_once_with(changed=False)

    @patch("plugins.modules.purefa_snmp.check_response")
    def test_update_manager_v2c_notification_change(self, mock_check_response):
        """A v2c manager is updated when a readable field differs"""
        mock_module = Mock()
        mock_module.check_mode = False
        mock_module.params = {
            "name": "snmp1",
            "version": "v2c",
            "community": "public",
            "notification": "inform",
            "host": "192.168.1.100",
        }
        mock_array = Mock()
        mock_mgr = Mock()
        mock_mgr.version = "v2c"
        mock_mgr.host = "192.168.1.100"
        mock_mgr.notification = "trap"
        mock_array.get_snmp_managers.return_value = Mock(
            status_code=200, items=[mock_mgr]
        )
        mock_array.patch_snmp_managers.return_value = Mock(status_code=200)

        update_manager(mock_module, mock_array)

        mock_array.patch_snmp_managers.assert_called_once()
        mock_module.exit_json.assert_called_once_with(changed=True)

    @patch("plugins.modules.purefa_snmp.check_response")
    def test_update_manager_v3_auth_and_privacy(self, mock_check_response):
        """Test update_manager v3 with both auth and privacy protocols"""
        mock_module = Mock()
        mock_module.check_mode = False
        mock_module.params = {
            "name": "snmp1",
            "version": "v3",
            "auth_protocol": "SHA",
            "auth_passphrase": "authpass123",
            "privacy_protocol": "AES",
            "privacy_passphrase": "privpass123",
            "user": "snmpuser",
            "notification": "trap",
            "host": "192.168.1.100",
        }
        mock_array = Mock()
        mock_mgr = Mock()
        mock_mgr.version = "v3"
        mock_array.get_snmp_managers.return_value = Mock(
            status_code=200, items=[mock_mgr]
        )
        mock_array.patch_snmp_managers.return_value = Mock(status_code=200)

        update_manager(mock_module, mock_array)

        mock_array.patch_snmp_managers.assert_called_once()
        mock_module.exit_json.assert_called_once_with(changed=True)

    @patch("plugins.modules.purefa_snmp.check_response")
    def test_update_manager_v3_auth_only(self, mock_check_response):
        """Test update_manager v3 with only auth protocol"""
        mock_module = Mock()
        mock_module.check_mode = False
        mock_module.params = {
            "name": "snmp1",
            "version": "v3",
            "auth_protocol": "SHA",
            "auth_passphrase": "authpass123",
            "privacy_protocol": None,
            "user": "snmpuser",
            "notification": "trap",
            "host": "192.168.1.100",
        }
        mock_array = Mock()
        mock_mgr = Mock()
        mock_mgr.version = "v3"
        mock_array.get_snmp_managers.return_value = Mock(
            status_code=200, items=[mock_mgr]
        )
        mock_array.patch_snmp_managers.return_value = Mock(status_code=200)

        update_manager(mock_module, mock_array)

        mock_array.patch_snmp_managers.assert_called_once()
        mock_module.exit_json.assert_called_once_with(changed=True)

    @patch("plugins.modules.purefa_snmp.check_response")
    def test_update_manager_v3_privacy_only(self, mock_check_response):
        """Test update_manager v3 with only privacy protocol"""
        mock_module = Mock()
        mock_module.check_mode = False
        mock_module.params = {
            "name": "snmp1",
            "version": "v3",
            "auth_protocol": None,
            "privacy_protocol": "AES",
            "privacy_passphrase": "privpass123",
            "user": "snmpuser",
            "notification": "trap",
            "host": "192.168.1.100",
        }
        mock_array = Mock()
        mock_mgr = Mock()
        mock_mgr.version = "v3"
        mock_array.get_snmp_managers.return_value = Mock(
            status_code=200, items=[mock_mgr]
        )
        mock_array.patch_snmp_managers.return_value = Mock(status_code=200)

        update_manager(mock_module, mock_array)

        mock_array.patch_snmp_managers.assert_called_once()
        mock_module.exit_json.assert_called_once_with(changed=True)

    @patch("plugins.modules.purefa_snmp.check_response")
    def test_update_manager_v3_no_auth_no_privacy(self, mock_check_response):
        """Test update_manager v3 with neither auth nor privacy protocol"""
        mock_module = Mock()
        mock_module.check_mode = False
        mock_module.params = {
            "name": "snmp1",
            "version": "v3",
            "auth_protocol": None,
            "privacy_protocol": None,
            "user": "snmpuser",
            "notification": "trap",
            "host": "192.168.1.100",
        }
        mock_array = Mock()
        mock_mgr = Mock()
        mock_mgr.version = "v3"
        mock_array.get_snmp_managers.return_value = Mock(
            status_code=200, items=[mock_mgr]
        )
        mock_array.patch_snmp_managers.return_value = Mock(status_code=200)

        update_manager(mock_module, mock_array)

        mock_array.patch_snmp_managers.assert_called_once()
        mock_module.exit_json.assert_called_once_with(changed=True)


class TestCreateManagerV3:
    """Test cases for create_manager function with v3"""

    @patch("plugins.modules.purefa_snmp.check_response")
    def test_create_manager_v3_auth_and_privacy(self, mock_check_response):
        """Test create_manager v3 with both auth and privacy protocols"""
        mock_module = Mock()
        mock_module.check_mode = False
        mock_module.params = {
            "name": "snmp1",
            "version": "v3",
            "host": "192.168.1.100",
            "notification": "trap",
            "auth_protocol": "SHA",
            "auth_passphrase": "authpass123",
            "privacy_protocol": "AES",
            "privacy_passphrase": "privpass123",
            "user": "snmpuser",
        }
        mock_array = Mock()
        mock_array.post_snmp_managers.return_value = Mock(status_code=200)

        create_manager(mock_module, mock_array)

        mock_array.post_snmp_managers.assert_called_once()
        mock_module.exit_json.assert_called_with(changed=True)

    @patch("plugins.modules.purefa_snmp.check_response")
    def test_create_manager_v3_auth_only(self, mock_check_response):
        """Test create_manager v3 with only auth protocol"""
        mock_module = Mock()
        mock_module.check_mode = False
        mock_module.params = {
            "name": "snmp1",
            "version": "v3",
            "host": "192.168.1.100",
            "notification": "trap",
            "auth_protocol": "SHA",
            "auth_passphrase": "authpass123",
            "privacy_protocol": None,
            "user": "snmpuser",
        }
        mock_array = Mock()
        mock_array.post_snmp_managers.return_value = Mock(status_code=200)

        create_manager(mock_module, mock_array)

        mock_array.post_snmp_managers.assert_called_once()
        mock_module.exit_json.assert_called_with(changed=True)

    @patch("plugins.modules.purefa_snmp.check_response")
    def test_create_manager_v3_privacy_only(self, mock_check_response):
        """Test create_manager v3 with only privacy protocol"""
        mock_module = Mock()
        mock_module.check_mode = False
        mock_module.params = {
            "name": "snmp1",
            "version": "v3",
            "host": "192.168.1.100",
            "notification": "trap",
            "auth_protocol": None,
            "privacy_protocol": "AES",
            "privacy_passphrase": "privpass123",
            "user": "snmpuser",
        }
        mock_array = Mock()
        mock_array.post_snmp_managers.return_value = Mock(status_code=200)

        create_manager(mock_module, mock_array)

        mock_array.post_snmp_managers.assert_called_once()
        # host belongs inside the SnmpManagerPost model, not on the call,
        # and the model keyword is snmp_manager
        call_kwargs = mock_array.post_snmp_managers.call_args[1]
        assert set(call_kwargs) == {"names", "snmp_manager"}
        mock_module.exit_json.assert_called_with(changed=True)

    @patch("plugins.modules.purefa_snmp.check_response")
    def test_create_manager_v3_no_auth_no_privacy(self, mock_check_response):
        """Test create_manager v3 with no auth and no privacy protocols"""
        mock_module = Mock()
        mock_module.check_mode = False
        mock_module.params = {
            "name": "snmp1",
            "version": "v3",
            "host": "192.168.1.100",
            "notification": "trap",
            "auth_protocol": None,
            "privacy_protocol": None,
            "user": "snmpuser",
        }
        mock_array = Mock()
        mock_array.post_snmp_managers.return_value = Mock(status_code=200)

        create_manager(mock_module, mock_array)

        mock_array.post_snmp_managers.assert_called_once()
        # host belongs inside the SnmpManagerPost model, not on the call
        call_kwargs = mock_array.post_snmp_managers.call_args[1]
        assert set(call_kwargs) == {"names", "snmp_manager"}
        mock_module.exit_json.assert_called_with(changed=True)

    @patch("plugins.modules.purefa_snmp.SnmpManagerPost")
    @patch("plugins.modules.purefa_snmp.check_response")
    def test_create_manager_v3_privacy_only_host_in_model(
        self, mock_check_response, mock_post_model
    ):
        """The host is passed to SnmpManagerPost for a privacy-only v3 manager"""
        mock_module = Mock()
        mock_module.check_mode = False
        mock_module.params = {
            "name": "snmp1",
            "version": "v3",
            "host": "192.168.1.100",
            "notification": "trap",
            "auth_protocol": None,
            "privacy_protocol": "AES",
            "privacy_passphrase": "privpass123",
            "user": "snmpuser",
        }
        mock_array = Mock()
        mock_array.post_snmp_managers.return_value = Mock(status_code=200)

        create_manager(mock_module, mock_array)

        assert mock_post_model.call_args[1]["host"] == "192.168.1.100"


class TestMain:
    """Test cases for main() function"""

    @patch("plugins.modules.purefa_snmp.get_array")
    @patch("plugins.modules.purefa_snmp.AnsibleModule")
    @patch("plugins.modules.purefa_snmp.HAS_PURESTORAGE", True)
    def test_main_no_purestorage_sdk(self, mock_ansible_module, mock_get_array):
        """Test main() fails when purestorage SDK not available"""
        import pytest
        from plugins.modules.purefa_snmp import main

        with patch("plugins.modules.purefa_snmp.HAS_PURESTORAGE", False):
            mock_module = Mock()
            mock_module.params = {}
            mock_module.fail_json.side_effect = SystemExit(1)
            mock_ansible_module.return_value = mock_module

            with pytest.raises(SystemExit):
                main()

            mock_module.fail_json.assert_called()

    @patch("plugins.modules.purefa_snmp.get_array")
    @patch("plugins.modules.purefa_snmp.AnsibleModule")
    @patch("plugins.modules.purefa_snmp.HAS_PURESTORAGE", True)
    def test_main_no_host(self, mock_ansible_module, mock_get_array):
        """Test main() fails when host is not provided"""
        import pytest
        from plugins.modules.purefa_snmp import main

        mock_module = Mock()
        mock_module.params = {
            "name": "snmp1",
            "state": "present",
            "version": "v2c",
            "host": None,
        }
        mock_module.fail_json.side_effect = SystemExit(1)
        mock_ansible_module.return_value = mock_module
        mock_array = Mock()
        mock_array.get_snmp_managers.return_value = Mock(items=[])
        mock_get_array.return_value = mock_array

        with pytest.raises(SystemExit):
            main()

        mock_module.fail_json.assert_called()

    @patch("plugins.modules.purefa_snmp.get_array")
    @patch("plugins.modules.purefa_snmp.AnsibleModule")
    @patch("plugins.modules.purefa_snmp.HAS_PURESTORAGE", True)
    def test_main_v3_no_user(self, mock_ansible_module, mock_get_array):
        """Test main() fails when v3 and user is not provided"""
        import pytest
        from plugins.modules.purefa_snmp import main

        mock_module = Mock()
        mock_module.params = {
            "name": "snmp1",
            "state": "present",
            "version": "v3",
            "host": "192.168.1.100",
            "user": None,
        }
        mock_module.fail_json.side_effect = SystemExit(1)
        mock_ansible_module.return_value = mock_module
        mock_array = Mock()
        mock_array.get_snmp_managers.return_value = Mock(items=[])
        mock_get_array.return_value = mock_array

        with pytest.raises(SystemExit):
            main()

        mock_module.fail_json.assert_called()

    @patch("plugins.modules.purefa_snmp.get_array")
    @patch("plugins.modules.purefa_snmp.AnsibleModule")
    @patch("plugins.modules.purefa_snmp.HAS_PURESTORAGE", True)
    def test_main_v2c_no_community(self, mock_ansible_module, mock_get_array):
        """Test main() fails when v2c and community is not provided"""
        import pytest
        from plugins.modules.purefa_snmp import main

        mock_module = Mock()
        mock_module.params = {
            "name": "snmp1",
            "state": "present",
            "version": "v2c",
            "host": "192.168.1.100",
            "community": None,
        }
        mock_module.fail_json.side_effect = SystemExit(1)
        mock_ansible_module.return_value = mock_module
        mock_array = Mock()
        mock_array.get_snmp_managers.return_value = Mock(items=[])
        mock_get_array.return_value = mock_array

        with pytest.raises(SystemExit):
            main()

        mock_module.fail_json.assert_called()

    @patch("plugins.modules.purefa_snmp.delete_manager")
    @patch("plugins.modules.purefa_snmp.get_array")
    @patch("plugins.modules.purefa_snmp.AnsibleModule")
    @patch("plugins.modules.purefa_snmp.HAS_PURESTORAGE", True)
    def test_main_delete_existing(
        self, mock_ansible_module, mock_get_array, mock_delete
    ):
        """Test main() calls delete_manager when state=absent and manager exists"""
        from plugins.modules.purefa_snmp import main

        mock_module = Mock()
        mock_module.params = {
            "name": "snmp1",
            "state": "absent",
            "version": "v2c",
            "host": "192.168.1.100",
            "community": "public",
        }
        mock_ansible_module.return_value = mock_module

        mock_mgr = Mock()
        mock_mgr.name = "snmp1"
        mock_array = Mock()
        mock_array.get_snmp_managers.return_value = Mock(items=[mock_mgr])
        mock_get_array.return_value = mock_array

        main()

        mock_delete.assert_called_once()

    @patch("plugins.modules.purefa_snmp.update_manager")
    @patch("plugins.modules.purefa_snmp.get_array")
    @patch("plugins.modules.purefa_snmp.AnsibleModule")
    @patch("plugins.modules.purefa_snmp.HAS_PURESTORAGE", True)
    def test_main_update_existing(
        self, mock_ansible_module, mock_get_array, mock_update
    ):
        """Test main() calls update_manager when state=present and manager exists"""
        from plugins.modules.purefa_snmp import main

        mock_module = Mock()
        mock_module.params = {
            "name": "snmp1",
            "state": "present",
            "version": "v2c",
            "host": "192.168.1.100",
            "community": "public",
        }
        mock_ansible_module.return_value = mock_module

        mock_mgr = Mock()
        mock_mgr.name = "snmp1"
        mock_array = Mock()
        mock_array.get_snmp_managers.return_value = Mock(items=[mock_mgr])
        mock_get_array.return_value = mock_array

        main()

        mock_update.assert_called_once()

    @patch("plugins.modules.purefa_snmp.create_manager")
    @patch("plugins.modules.purefa_snmp.get_array")
    @patch("plugins.modules.purefa_snmp.AnsibleModule")
    @patch("plugins.modules.purefa_snmp.HAS_PURESTORAGE", True)
    def test_main_create_new(self, mock_ansible_module, mock_get_array, mock_create):
        """Test main() calls create_manager when state=present and manager doesn't exist"""
        from plugins.modules.purefa_snmp import main

        mock_module = Mock()
        mock_module.params = {
            "name": "snmp1",
            "state": "present",
            "version": "v2c",
            "host": "192.168.1.100",
            "community": "public",
        }
        mock_ansible_module.return_value = mock_module

        mock_array = Mock()
        mock_array.get_snmp_managers.return_value = Mock(
            items=[]
        )  # No existing managers
        mock_get_array.return_value = mock_array

        main()

        mock_create.assert_called_once()

    @patch("plugins.modules.purefa_snmp.test_manager")
    @patch("plugins.modules.purefa_snmp.get_array")
    @patch("plugins.modules.purefa_snmp.AnsibleModule")
    @patch("plugins.modules.purefa_snmp.HAS_PURESTORAGE", True)
    def test_main_test_existing(self, mock_ansible_module, mock_get_array, mock_test):
        """Test main() calls test_manager when state=test and manager exists"""
        from plugins.modules.purefa_snmp import main

        mock_module = Mock()
        mock_module.params = {
            "name": "snmp1",
            "state": "test",
            "version": "v2c",
            "host": "192.168.1.100",
            "community": "public",
        }
        mock_ansible_module.return_value = mock_module

        mock_mgr = Mock()
        mock_mgr.name = "snmp1"
        mock_array = Mock()
        mock_array.get_snmp_managers.return_value = Mock(items=[mock_mgr])
        mock_get_array.return_value = mock_array

        main()

        mock_test.assert_called_once()

    @patch("plugins.modules.purefa_snmp.get_array")
    @patch("plugins.modules.purefa_snmp.AnsibleModule")
    @patch("plugins.modules.purefa_snmp.HAS_PURESTORAGE", True)
    def test_main_no_change(self, mock_ansible_module, mock_get_array):
        """Test main() exits with no change when nothing to do"""
        from plugins.modules.purefa_snmp import main

        mock_module = Mock()
        mock_module.params = {
            "name": "snmp1",
            "state": "absent",  # Want to delete
            "version": "v2c",
            "host": "192.168.1.100",
            "community": "public",
        }
        mock_ansible_module.return_value = mock_module

        mock_array = Mock()
        mock_array.get_snmp_managers.return_value = Mock(
            items=[]
        )  # Manager doesn't exist
        mock_get_array.return_value = mock_array

        main()

        mock_module.exit_json.assert_called_with(changed=False)

    @patch("plugins.modules.purefa_snmp.get_array")
    @patch("plugins.modules.purefa_snmp.AnsibleModule")
    @patch("plugins.modules.purefa_snmp.HAS_PURESTORAGE", True)
    def test_main_v3_auth_passphrase_too_short(
        self, mock_ansible_module, mock_get_array
    ):
        """A v3 auth passphrase shorter than 8 characters is rejected"""
        import pytest
        from plugins.modules.purefa_snmp import main

        mock_module = Mock()
        mock_module.params = {
            "name": "snmp1",
            "state": "present",
            "version": "v3",
            "host": "192.168.1.100",
            "user": "snmpuser",
            "auth_passphrase": "short",
            "auth_protocol": "SHA",
            "privacy_passphrase": None,
            "privacy_protocol": None,
        }
        mock_module.fail_json.side_effect = SystemExit(1)
        mock_ansible_module.return_value = mock_module
        mock_array = Mock()
        mock_array.get_snmp_managers.return_value = Mock(items=[])
        mock_get_array.return_value = mock_array

        with pytest.raises(SystemExit):
            main()

        mock_module.fail_json.assert_called_once_with(
            msg="auth_password must be between 8 and 32 characters"
        )

    @patch("plugins.modules.purefa_snmp.get_array")
    @patch("plugins.modules.purefa_snmp.AnsibleModule")
    @patch("plugins.modules.purefa_snmp.HAS_PURESTORAGE", True)
    def test_main_v3_privacy_passphrase_too_long(
        self, mock_ansible_module, mock_get_array
    ):
        """A v3 privacy passphrase longer than 63 characters is rejected"""
        import pytest
        from plugins.modules.purefa_snmp import main

        mock_module = Mock()
        mock_module.params = {
            "name": "snmp1",
            "state": "present",
            "version": "v3",
            "host": "192.168.1.100",
            "user": "snmpuser",
            "auth_passphrase": None,
            "auth_protocol": None,
            "privacy_passphrase": "p" * 64,
            "privacy_protocol": "AES",
        }
        mock_module.fail_json.side_effect = SystemExit(1)
        mock_ansible_module.return_value = mock_module
        mock_array = Mock()
        mock_array.get_snmp_managers.return_value = Mock(items=[])
        mock_get_array.return_value = mock_array

        with pytest.raises(SystemExit):
            main()

        mock_module.fail_json.assert_called_once_with(
            msg="privacy_password must be between 8 and 63 characters"
        )

    @patch("plugins.modules.purefa_snmp.create_manager")
    @patch("plugins.modules.purefa_snmp.get_array")
    @patch("plugins.modules.purefa_snmp.AnsibleModule")
    @patch("plugins.modules.purefa_snmp.HAS_PURESTORAGE", True)
    def test_main_v3_valid_passphrases_accepted(
        self, mock_ansible_module, mock_get_array, mock_create
    ):
        """Passphrases inside the allowed ranges pass validation"""
        from plugins.modules.purefa_snmp import main

        mock_module = Mock()
        mock_module.params = {
            "name": "snmp1",
            "state": "present",
            "version": "v3",
            "host": "192.168.1.100",
            "user": "snmpuser",
            "auth_passphrase": "a" * 8,
            "auth_protocol": "SHA",
            "privacy_passphrase": "p" * 63,
            "privacy_protocol": "AES",
        }
        mock_ansible_module.return_value = mock_module
        mock_array = Mock()
        mock_array.get_snmp_managers.return_value = Mock(items=[])
        mock_get_array.return_value = mock_array

        main()

        mock_module.fail_json.assert_not_called()
        mock_create.assert_called_once()
