# Copyright: (c) 2026, Everpure Ansible Team <pure-ansible-team@everpuredata.com>
# GNU General Public License v3.0+ (see COPYING.GPLv3 or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Unit tests for purefa_token module."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import os
import sys
from unittest.mock import Mock, MagicMock, patch

import pytest

# Mock external dependencies before importing module
sys.modules["grp"] = MagicMock()
sys.modules["pwd"] = MagicMock()
sys.modules["fcntl"] = MagicMock()
sys.modules["ansible"] = MagicMock()
sys.modules["ansible.module_utils"] = MagicMock()
sys.modules["ansible.module_utils.basic"] = MagicMock()
sys.modules["purestorage"] = MagicMock()
sys.modules["distro"] = MagicMock()
sys.modules["urllib3"] = MagicMock()
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

from plugins.modules.purefa_token import get_session, main


def _module(**overrides):
    mock_module = Mock()
    mock_module.params = {
        "fa_url": "10.10.10.2",
        "username": "pureuser",
        "password": "secret",
        "state": "present",
        "recreate": False,
        "timeout": None,
        "disable_warnings": False,
    }
    mock_module.params.update(overrides)
    mock_module.fail_json.side_effect = SystemExit(1)
    return mock_module


class TestGetSession:
    """Tests for get_session credential handling"""

    @patch("plugins.modules.purefa_token.HAS_PURESTORAGE", True)
    def test_env_url_without_credentials_fails_clearly(self):
        """PUREFA_URL alone used to leave `system` unbound (UnboundLocalError)"""
        mock_module = _module(fa_url=None, username=None, password=None)

        with patch.dict(os.environ, {"PUREFA_URL": "10.10.10.2"}, clear=True):
            with pytest.raises(SystemExit):
                get_session(mock_module)

        msg = mock_module.fail_json.call_args[1]["msg"]
        assert "PUREFA_USERNAME" in msg


class TestMain:
    """Tests for the create/recreate/delete decision and the changed flag"""

    @patch("plugins.modules.purefa_token.get_array")
    @patch("plugins.modules.purefa_token.get_session")
    @patch("plugins.modules.purefa_token.AnsibleModule")
    def test_create_for_admin_without_token_is_a_change(
        self, mock_ansible_module, mock_get_session, mock_get_array
    ):
        mock_module = _module()
        mock_ansible_module.return_value = mock_module
        session = Mock()
        session.get_api_token.return_value = {"api_token": None}
        session.create_api_token.return_value = {"api_token": "new-token"}
        mock_get_session.return_value = session

        main()

        session.create_api_token.assert_called_once_with(admin="pureuser")
        mock_module.exit_json.assert_called_once_with(
            changed=True, purefa_token="new-token"
        )
        mock_get_array.assert_not_called()

    @patch("plugins.modules.purefa_token.get_array")
    @patch("plugins.modules.purefa_token.get_session")
    @patch("plugins.modules.purefa_token.AnsibleModule")
    def test_empty_string_token_counts_as_absent(
        self, mock_ansible_module, mock_get_session, mock_get_array
    ):
        mock_module = _module()
        mock_ansible_module.return_value = mock_module
        session = Mock()
        session.get_api_token.return_value = {"api_token": ""}
        session.create_api_token.return_value = {"api_token": "new-token"}
        mock_get_session.return_value = session

        main()

        session.create_api_token.assert_called_once()
        mock_module.exit_json.assert_called_once_with(
            changed=True, purefa_token="new-token"
        )

    @patch("plugins.modules.purefa_token.get_array")
    @patch("plugins.modules.purefa_token.get_session")
    @patch("plugins.modules.purefa_token.AnsibleModule")
    def test_existing_token_without_recreate_is_not_a_change(
        self, mock_ansible_module, mock_get_session, mock_get_array
    ):
        mock_module = _module()
        mock_ansible_module.return_value = mock_module
        session = Mock()
        session.get_api_token.return_value = {"api_token": "old-token"}
        mock_get_session.return_value = session

        main()

        session.create_api_token.assert_not_called()
        session.delete_api_token.assert_not_called()
        mock_module.exit_json.assert_called_once_with(
            changed=False, purefa_token="old-token"
        )

    @patch("plugins.modules.purefa_token.get_array")
    @patch("plugins.modules.purefa_token.get_session")
    @patch("plugins.modules.purefa_token.AnsibleModule")
    def test_recreate_is_a_change(
        self, mock_ansible_module, mock_get_session, mock_get_array
    ):
        mock_module = _module(recreate=True)
        mock_ansible_module.return_value = mock_module
        session = Mock()
        session.get_api_token.return_value = {"api_token": "old-token"}
        session.create_api_token.return_value = {"api_token": "new-token"}
        mock_get_session.return_value = session

        main()

        session.delete_api_token.assert_called_once_with(admin="pureuser")
        mock_module.exit_json.assert_called_once_with(
            changed=True, purefa_token="new-token"
        )

    @patch("plugins.modules.purefa_token.get_array")
    @patch("plugins.modules.purefa_token.get_session")
    @patch("plugins.modules.purefa_token.AnsibleModule")
    def test_absent_without_token_is_not_a_change(
        self, mock_ansible_module, mock_get_session, mock_get_array
    ):
        mock_module = _module(state="absent")
        mock_ansible_module.return_value = mock_module
        session = Mock()
        session.get_api_token.return_value = {"api_token": None}
        mock_get_session.return_value = session

        main()

        session.delete_api_token.assert_not_called()
        mock_module.exit_json.assert_called_once_with(changed=False, purefa_token=None)


class TestTimeout:
    """timeout is a REST 2 feature and must be gated on the REST 2 version"""

    @patch("plugins.modules.purefa_token.check_response")
    @patch("plugins.modules.purefa_token.convert_time_to_millisecs")
    @patch("plugins.modules.purefa_token.get_array")
    @patch("plugins.modules.purefa_token.get_session")
    @patch("plugins.modules.purefa_token.AnsibleModule")
    def test_timeout_applied_on_current_rest(
        self,
        mock_ansible_module,
        mock_get_session,
        mock_get_array,
        mock_convert,
        mock_check_response,
    ):
        """ "2.2" in [REST 1 versions] was never true, so timeout was ignored"""
        mock_module = _module(timeout="1d")
        mock_ansible_module.return_value = mock_module
        session = Mock()
        session.get_api_token.return_value = {"api_token": "old-token"}
        mock_get_session.return_value = session
        mock_convert.return_value = 86400000
        array6 = Mock()
        array6.get_rest_version.return_value = "2.54"
        item = Mock()
        item.api_token.token = "timed-token"
        array6.post_admins_api_tokens.return_value = Mock(status_code=200, items=[item])
        mock_get_array.return_value = array6

        main()

        array6.delete_admins_api_tokens.assert_called_once_with(names=["pureuser"])
        array6.post_admins_api_tokens.assert_called_once_with(
            names=["pureuser"], timeout=86400000
        )
        mock_module.exit_json.assert_called_once_with(
            changed=True, purefa_token="timed-token"
        )

    @patch("plugins.modules.purefa_token.get_array")
    @patch("plugins.modules.purefa_token.get_session")
    @patch("plugins.modules.purefa_token.AnsibleModule")
    def test_timeout_warns_below_rest_2_2(
        self, mock_ansible_module, mock_get_session, mock_get_array
    ):
        mock_module = _module(timeout="1d")
        mock_ansible_module.return_value = mock_module
        session = Mock()
        session.get_api_token.return_value = {"api_token": "old-token"}
        mock_get_session.return_value = session
        array6 = Mock()
        array6.get_rest_version.return_value = "2.1"
        mock_get_array.return_value = array6

        main()

        array6.delete_admins_api_tokens.assert_not_called()
        array6.post_admins_api_tokens.assert_not_called()
        mock_module.warn.assert_called_once()
        mock_module.exit_json.assert_called_once_with(
            changed=False, purefa_token="old-token"
        )
