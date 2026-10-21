# Copyright: (c) 2026, Everpure Ansible Team <pure-ansible-team@everpuredata.com>
# GNU General Public License v3.0+ (see COPYING.GPLv3 or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Unit tests for purefa_maintenance module."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import sys
from unittest.mock import Mock, MagicMock, patch

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

from plugins.modules.purefa_maintenance import (
    delete_window,
    set_window,
)


class TestDeleteWindow:
    """Tests for delete_window function"""

    def test_delete_window_no_window(self):
        """Test delete_window when no maintenance window exists"""
        mock_module = Mock()
        mock_module.check_mode = False
        mock_array = Mock()
        mock_array.get_maintenance_windows.return_value = Mock(items=[])

        delete_window(mock_module, mock_array)

        mock_module.exit_json.assert_called_once_with(changed=False)

    def test_delete_window_with_window(self):
        """Test delete_window when a maintenance window exists"""
        mock_module = Mock()
        mock_module.check_mode = True
        mock_array = Mock()
        mock_window = Mock()
        mock_array.get_maintenance_windows.return_value = Mock(items=[mock_window])

        delete_window(mock_module, mock_array)

        mock_module.exit_json.assert_called_once_with(changed=True)

    @patch("plugins.modules.purefa_maintenance.check_response")
    def test_delete_window_checks_response(self, mock_check_response):
        """A failed delete is handed to check_response rather than swallowed"""
        mock_module = Mock()
        mock_module.check_mode = False
        mock_array = Mock()
        mock_array.get_maintenance_windows.return_value = Mock(items=[Mock()])
        delete_response = Mock(status_code=400)
        mock_array.delete_maintenance_windows.return_value = delete_response

        delete_window(mock_module, mock_array)

        mock_array.delete_maintenance_windows.assert_called_once_with(
            names=["environment"]
        )
        mock_check_response.assert_called_once()
        assert mock_check_response.call_args[0][0] is delete_response


class TestSetWindow:
    """Tests for set_window function"""

    def test_set_window_check_mode(self):
        """Test set_window in check mode with no open window"""
        mock_module = Mock()
        mock_module.params = {"timeout": 3600}
        mock_module.check_mode = True
        mock_array = Mock()
        mock_array.get_maintenance_windows.return_value = Mock(items=[])

        set_window(mock_module, mock_array)

        mock_array.post_maintenance_windows.assert_not_called()
        mock_module.exit_json.assert_called_once_with(changed=True)

    @patch("plugins.modules.purefa_maintenance.check_response")
    def test_set_window_creates_when_none_open(self, mock_check_response):
        """A window is created when none is open"""
        mock_module = Mock()
        mock_module.params = {"timeout": 7200}
        mock_module.check_mode = False
        mock_array = Mock()
        mock_array.get_maintenance_windows.return_value = Mock(items=[])
        mock_array.post_maintenance_windows.return_value = Mock(status_code=200)

        set_window(mock_module, mock_array)

        mock_array.post_maintenance_windows.assert_called_once()
        assert mock_array.post_maintenance_windows.call_args[1]["names"] == [
            "environment"
        ]
        mock_module.exit_json.assert_called_once_with(changed=True)

    def test_set_window_already_open(self):
        """An already open window is not recreated"""
        mock_module = Mock()
        mock_module.params = {"timeout": 3600}
        mock_module.check_mode = False
        mock_array = Mock()
        mock_array.get_maintenance_windows.return_value = Mock(items=[Mock()])

        set_window(mock_module, mock_array)

        mock_array.post_maintenance_windows.assert_not_called()
        mock_module.exit_json.assert_called_once_with(changed=False)

    def test_set_window_timeout_out_of_range_low(self):
        """Test set_window with timeout below minimum"""
        import pytest

        mock_module = Mock()
        mock_module.params = {"timeout": 1000}
        mock_module.check_mode = False
        mock_module.fail_json.side_effect = SystemExit(1)
        mock_array = Mock()

        with pytest.raises(SystemExit):
            set_window(mock_module, mock_array)

        mock_module.fail_json.assert_called_once()
        mock_array.get_maintenance_windows.assert_not_called()
