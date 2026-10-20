# Copyright: (c) 2026, Everpure Ansible Team <pure-ansible-team@everpuredata.com>
# GNU General Public License v3.0+ (see COPYING.GPLv3 or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Unit tests for purefa_ntp module."""

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
sys.modules["ansible_collections.everpure.flasharray.plugins.module_utils.common"] = (
    MagicMock()
)
sys.modules[
    "ansible_collections.everpure.flasharray.plugins.module_utils.api_helpers"
] = MagicMock()
sys.modules[
    "ansible_collections.everpure.flasharray.plugins.module_utils.error_handlers"
] = MagicMock()

from plugins.modules.purefa_ntp import (
    remove,
    _is_cbs,
    delete_ntp,
    test_ntp as ntp_test_func,
    create_ntp,
    update_ntp_key,
    main,
)


def _physical_array(ntp_servers):
    """A non-CBS array whose current NTP servers are ``ntp_servers``"""
    mock_array = Mock()
    mock_array.get_rest_version.return_value = "2.38"
    mock_array.get_controllers.return_value = Mock(items=[Mock(model="FA-X70")])
    mock_array_obj = Mock()
    mock_array_obj.ntp_servers = ntp_servers
    return mock_array, Mock(items=[mock_array_obj])


class TestMain:
    """Test cases for main function"""

    @patch("plugins.modules.purefa_ntp.test_ntp")
    @patch("plugins.modules.purefa_ntp.get_array")
    @patch("plugins.modules.purefa_ntp.AnsibleModule")
    def test_main_state_test_without_context(
        self, mock_ansible_module, mock_get_array, mock_test_ntp
    ):
        """state=test runs the test when no context is given"""
        mock_module = Mock()
        mock_module.params = {
            "state": "test",
            "context": "",
            "ntp_servers": None,
            "ntp_key": None,
        }
        mock_ansible_module.return_value = mock_module
        mock_array, _unused = _physical_array([])
        mock_get_array.return_value = mock_array

        main()

        mock_module.fail_json.assert_not_called()
        mock_test_ntp.assert_called_once_with(mock_module, mock_array)

    @patch("plugins.modules.purefa_ntp.test_ntp")
    @patch("plugins.modules.purefa_ntp.get_array")
    @patch("plugins.modules.purefa_ntp.AnsibleModule")
    def test_main_state_test_with_context_fails(
        self, mock_ansible_module, mock_get_array, mock_test_ntp
    ):
        """state=test is refused for a fleet context"""
        import pytest

        mock_module = Mock()
        mock_module.params = {
            "state": "test",
            "context": "array2",
            "ntp_servers": None,
            "ntp_key": None,
        }
        mock_module.fail_json.side_effect = SystemExit(1)
        mock_ansible_module.return_value = mock_module
        mock_array, _unused = _physical_array([])
        mock_get_array.return_value = mock_array

        with pytest.raises(SystemExit):
            main()

        mock_module.fail_json.assert_called_once_with(
            msg="NTP testing is not supported with context"
        )
        mock_test_ntp.assert_not_called()

    @patch("plugins.modules.purefa_ntp.create_ntp")
    @patch("plugins.modules.purefa_ntp.get_with_context")
    @patch("plugins.modules.purefa_ntp.get_array")
    @patch("plugins.modules.purefa_ntp.AnsibleModule")
    def test_main_present_without_servers_applies_default(
        self, mock_ansible_module, mock_get_array, mock_get_with_context, mock_create
    ):
        """state=present with no list sets the documented default server"""
        mock_module = Mock()
        mock_module.params = {
            "state": "present",
            "context": "",
            "ntp_servers": None,
            "ntp_key": None,
        }
        mock_ansible_module.return_value = mock_module
        mock_array, arrays_response = _physical_array([])
        mock_get_array.return_value = mock_array
        mock_get_with_context.return_value = arrays_response

        main()

        assert mock_module.params["ntp_servers"] == ["0.pool.ntp.org"]
        mock_create.assert_called_once_with(mock_module, mock_array)

    @patch("plugins.modules.purefa_ntp.create_ntp")
    @patch("plugins.modules.purefa_ntp.get_with_context")
    @patch("plugins.modules.purefa_ntp.get_array")
    @patch("plugins.modules.purefa_ntp.AnsibleModule")
    def test_main_present_default_already_set(
        self, mock_ansible_module, mock_get_array, mock_get_with_context, mock_create
    ):
        """state=present with no list is idempotent once the default is set"""
        mock_module = Mock()
        mock_module.params = {
            "state": "present",
            "context": "",
            "ntp_servers": None,
            "ntp_key": None,
        }
        mock_ansible_module.return_value = mock_module
        mock_array, arrays_response = _physical_array(["0.pool.ntp.org"])
        mock_get_array.return_value = mock_array
        mock_get_with_context.return_value = arrays_response

        main()

        mock_create.assert_not_called()
        mock_module.exit_json.assert_called_once_with(changed=False)


class TestRemove:
    """Test cases for remove function"""

    def test_remove_duplicates(self):
        """Test remove function removes duplicates from list"""
        test_list = ["ntp1.example.com", "ntp2.example.com", "ntp1.example.com"]

        result = remove(test_list)

        assert result == ["ntp1.example.com", "ntp2.example.com"]

    def test_remove_no_duplicates(self):
        """Test remove function with no duplicates"""
        test_list = ["ntp1.example.com", "ntp2.example.com"]

        result = remove(test_list)

        assert result == ["ntp1.example.com", "ntp2.example.com"]


class TestIsCbs:
    """Test cases for _is_cbs function"""

    def test_is_cbs_true(self):
        """Test _is_cbs returns True for CBS model"""
        mock_array = Mock()
        mock_array.get_controllers.return_value = Mock(
            status_code=200, items=[Mock(model="CBS-S70")]
        )

        result = _is_cbs(mock_array)

        assert result is True

    def test_is_cbs_false(self):
        """Test _is_cbs returns False for non-CBS model"""
        mock_array = Mock()
        mock_array.get_controllers.return_value = Mock(
            status_code=200, items=[Mock(model="FA-X70")]
        )

        result = _is_cbs(mock_array)

        assert result is False


class TestDeleteNtp:
    """Test cases for delete_ntp function"""

    @patch("plugins.modules.purefa_ntp.get_with_context")
    def test_delete_ntp_check_mode(self, mock_get_with_context):
        """Test delete_ntp in check mode"""
        mock_module = Mock()
        mock_module.check_mode = True
        mock_module.params = {"context": ""}
        mock_array = Mock()
        # Mock NTP servers exist
        mock_array_obj = Mock()
        mock_array_obj.ntp_servers = ["ntp1.example.com"]
        mock_get_with_context.return_value = Mock(items=[mock_array_obj])

        delete_ntp(mock_module, mock_array)

        mock_module.exit_json.assert_called_once_with(changed=True)

    @patch("plugins.modules.purefa_ntp.get_with_context")
    def test_delete_ntp_no_servers(self, mock_get_with_context):
        """Test delete_ntp when no NTP servers configured"""
        mock_module = Mock()
        mock_module.check_mode = False
        mock_module.params = {"context": ""}
        mock_array = Mock()
        # Mock empty NTP servers
        mock_array_obj = Mock()
        mock_array_obj.ntp_servers = []
        mock_get_with_context.return_value = Mock(items=[mock_array_obj])

        delete_ntp(mock_module, mock_array)

        mock_module.exit_json.assert_called_once_with(changed=False)


class TestNtpTest:
    """Test cases for test_ntp function"""

    def test_ntp_test_returns_response(self):
        """Test test_ntp returns test response"""
        mock_module = Mock()
        mock_module.params = {"context": ""}
        mock_array = Mock()

        # Create mock NTP test result
        mock_result = Mock()
        mock_result.enabled = True
        mock_result.success = True
        mock_result.component_address = "10.0.0.1"
        mock_result.component_name = "ntp1"
        mock_result.description = "NTP server test"
        mock_result.destination = "ntp.example.com"
        mock_result.result_details = "OK"
        mock_result.test_type = "connectivity"
        mock_result.resource = Mock()
        mock_result.resource.name = "array1"
        mock_array.get_arrays_ntp_test.return_value.items = [mock_result]

        ntp_test_func(mock_module, mock_array)

        mock_module.exit_json.assert_called_once()
        call_args = mock_module.exit_json.call_args[1]
        # Running a test is read-only
        assert call_args["changed"] is False
        assert len(call_args["test_response"]) == 1
        assert call_args["test_response"][0]["enabled"] == "true"
        assert call_args["test_response"][0]["success"] == "true"

    def test_ntp_test_sparse_result(self):
        """A TestResult without resource or optional fields must not crash"""
        mock_module = Mock()
        mock_module.params = {"context": ""}
        mock_array = Mock()

        mock_result = Mock(spec=["enabled", "success", "component_name"])
        mock_result.enabled = True
        mock_result.success = False
        mock_result.component_name = "ct0"
        mock_array.get_arrays_ntp_test.return_value = Mock(
            status_code=200, items=[mock_result]
        )

        ntp_test_func(mock_module, mock_array)

        result = mock_module.exit_json.call_args[1]["test_response"][0]
        assert result["enabled"] == "true"
        assert result["success"] == "false"
        assert result["component_name"] == "ct0"
        assert result["resource_name"] is None
        assert result["destination"] is None
        assert result["component_address"] is None
        assert result["test_type"] is None
        assert result["result_details"] == ""

    @patch("plugins.modules.purefa_ntp.check_response")
    def test_ntp_test_error_response(self, mock_check_response):
        """An error response is handed to check_response before .items is read"""
        import pytest

        mock_module = Mock()
        mock_module.params = {"context": ""}
        mock_module.fail_json.side_effect = SystemExit(1)
        mock_array = Mock()
        error_response = Mock(spec=["status_code", "errors"])
        error_response.status_code = 400
        error_response.errors = [Mock(message="boom")]
        mock_array.get_arrays_ntp_test.return_value = error_response
        mock_check_response.side_effect = lambda res, module, op: module.fail_json(
            msg=op
        )

        with pytest.raises(SystemExit):
            ntp_test_func(mock_module, mock_array)

        assert mock_check_response.call_args[0][0] is error_response
        mock_module.exit_json.assert_not_called()


class TestCreateNtp:
    """Test cases for create_ntp function"""

    def test_create_ntp_check_mode(self):
        """Test create_ntp in check mode"""
        mock_module = Mock()
        mock_module.check_mode = True
        mock_module.params = {
            "context": "",
            "ntp_servers": ["ntp1.example.com", "ntp2.example.com"],
        }
        mock_array = Mock()

        create_ntp(mock_module, mock_array)

        # In check mode, always returns changed=True without making API calls
        mock_module.exit_json.assert_called_once_with(changed=True)

    @patch("plugins.modules.purefa_ntp.check_response")
    @patch("plugins.modules.purefa_ntp.get_with_context")
    def test_create_ntp_success(self, mock_get_with_context, mock_check_response):
        """Test create_ntp successfully sets NTP servers"""
        mock_module = Mock()
        mock_module.check_mode = False
        mock_module.params = {
            "context": "",
            "ntp_servers": ["ntp1.example.com", "ntp2.example.com"],
        }
        mock_array = Mock()
        mock_get_with_context.return_value = Mock(status_code=200)

        create_ntp(mock_module, mock_array)

        mock_get_with_context.assert_called_once()
        mock_module.exit_json.assert_called_once_with(changed=True)

    @patch("plugins.modules.purefa_ntp.check_response")
    @patch("plugins.modules.purefa_ntp.get_with_context")
    def test_create_ntp_defaults_to_pool(
        self, mock_get_with_context, mock_check_response
    ):
        """Test create_ntp uses default pool when no servers provided"""
        mock_module = Mock()
        mock_module.check_mode = False
        mock_module.params = {
            "context": "",
            "ntp_servers": None,
        }
        mock_array = Mock()
        mock_get_with_context.return_value = Mock(status_code=200)

        create_ntp(mock_module, mock_array)

        # Check that default was set
        assert mock_module.params["ntp_servers"] == ["0.pool.ntp.org"]
        mock_get_with_context.assert_called_once()


class TestDeleteNtpSuccess:
    """Test cases for delete_ntp success paths"""

    @patch("plugins.modules.purefa_ntp.check_response")
    @patch("plugins.modules.purefa_ntp.get_with_context")
    def test_delete_ntp_success(self, mock_get_with_context, mock_check_response):
        """Test delete_ntp successfully removes NTP servers"""
        mock_module = Mock()
        mock_module.check_mode = False
        mock_module.params = {"context": ""}
        mock_array = Mock()
        mock_array_obj = Mock()
        mock_array_obj.ntp_servers = ["ntp1.example.com"]
        mock_get_with_context.return_value = Mock(items=[mock_array_obj])

        delete_ntp(mock_module, mock_array)

        assert mock_get_with_context.call_count == 2
        mock_module.exit_json.assert_called_once_with(changed=True)


class TestUpdateNtpKey:
    """Test cases for update_ntp_key function"""

    @patch("plugins.modules.purefa_ntp.get_with_context")
    def test_update_ntp_key_no_change(self, mock_get_with_context):
        """Test update_ntp_key when no change needed"""
        mock_module = Mock()
        mock_module.params = {"ntp_key": "", "context": ""}
        mock_array = Mock()
        mock_array_obj = Mock(spec=[])  # No ntp_symmetric_key attribute
        mock_get_with_context.return_value = Mock(items=[mock_array_obj])

        update_ntp_key(mock_module, mock_array)

        mock_module.exit_json.assert_called_once_with(changed=False)

    @patch("plugins.modules.purefa_ntp.check_response")
    @patch("plugins.modules.purefa_ntp.get_with_context")
    def test_update_ntp_key_hex_success(
        self, mock_get_with_context, mock_check_response
    ):
        """Test update_ntp_key with valid HEX key"""
        mock_module = Mock()
        mock_module.params = {"ntp_key": "0123456789ABCDEF", "context": ""}
        mock_array = Mock()
        mock_array_obj = Mock()
        mock_array_obj.ntp_symmetric_key = None
        mock_get_with_context.return_value = Mock(items=[mock_array_obj])

        update_ntp_key(mock_module, mock_array)

        assert mock_get_with_context.call_count == 2
        mock_module.exit_json.assert_called_once_with(changed=True)

    @patch("plugins.modules.purefa_ntp.get_with_context")
    def test_update_ntp_key_ascii_too_long(self, mock_get_with_context):
        """Test update_ntp_key fails with ASCII key > 20 chars"""
        import pytest

        mock_module = Mock()
        # Use non-hex characters like 'z' to ensure it's treated as ASCII
        mock_module.params = {"ntp_key": "z" * 21, "context": ""}  # 21 non-hex chars
        mock_module.fail_json.side_effect = SystemExit(1)
        mock_array = Mock()
        mock_array_obj = Mock()
        mock_array_obj.ntp_symmetric_key = None
        mock_get_with_context.return_value = Mock(items=[mock_array_obj])

        with pytest.raises(SystemExit):
            update_ntp_key(mock_module, mock_array)

        mock_module.fail_json.assert_called_once()
