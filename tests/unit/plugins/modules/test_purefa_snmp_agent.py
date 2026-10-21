# Copyright: (c) 2026, Everpure Ansible Team <pure-ansible-team@everpuredata.com>
# GNU General Public License v3.0+ (see COPYING.GPLv3 or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Unit tests for purefa_snmp_agent module."""

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

from plugins.modules.purefa_snmp_agent import (
    main,
    update_agent,
)


def _agent(version="v2c", community=None, user=None, auth=None, priv=None):
    """Build the current SNMP agent as the SDK model exposes it.

    Fields the array did not send are absent (reading them raises
    AttributeError), which is how py-pure-client models behave for null
    values. The community and passphrases come back masked as "****".
    """
    v2c_fields = {"community": community}
    v2c = Mock(spec=[k for k, v in v2c_fields.items() if v is not None])
    for key, value in v2c_fields.items():
        if value is not None:
            setattr(v2c, key, value)
    v3_fields = {"user": user, "auth_protocol": auth, "privacy_protocol": priv}
    v3 = Mock(spec=[k for k, v in v3_fields.items() if v is not None])
    for key, value in v3_fields.items():
        if value is not None:
            setattr(v3, key, value)
    agent = Mock(spec=["name", "version", "v2c", "v3"])
    agent.name = "localhost"
    agent.version = version
    agent.v2c = v2c
    agent.v3 = v3
    return agent


def _array_with(agent):
    """A mock array whose SNMP agent is ``agent``"""
    mock_array = Mock()
    mock_array.get_snmp_agents.return_value = Mock(status_code=200, items=[agent])
    mock_array.patch_snmp_agents.return_value = Mock(status_code=200)
    return mock_array


def _v3_params(state="present", user="snmpuser", auth=None, priv=None):
    """update_agent parameters for a v3 play"""
    return {
        "version": "v3",
        "state": state,
        "user": user,
        "community": None,
        "auth_protocol": auth,
        "auth_passphrase": "authpass123" if auth else None,
        "privacy_protocol": priv,
        "privacy_passphrase": "privpass123" if priv else None,
    }


class TestUpdateAgentV2c:
    """Tests for update_agent with version v2c"""

    def test_v2c_check_mode(self):
        """A pending change in check mode is reported but not applied"""
        mock_module = Mock()
        mock_module.params = {
            "version": "v2c",
            "community": "public",
            "state": "present",
        }
        mock_module.check_mode = True
        mock_array = _array_with(_agent(version="v3", user="snmpuser"))

        update_agent(mock_module, mock_array)

        mock_module.exit_json.assert_called_once_with(changed=True)
        mock_array.patch_snmp_agents.assert_not_called()

    @patch("plugins.modules.purefa_snmp_agent.check_response")
    def test_v2c_set_community_from_cleared(self, mock_check_response):
        """Setting a community where none is set is a change"""
        mock_module = Mock()
        mock_module.params = {
            "version": "v2c",
            "community": "public",
            "state": "present",
        }
        mock_module.check_mode = False
        mock_array = _array_with(_agent(version="v2c"))

        update_agent(mock_module, mock_array)

        mock_array.patch_snmp_agents.assert_called_once()
        mock_module.exit_json.assert_called_once_with(changed=True)

    def test_v2c_repeated_is_idempotent(self):
        """v2c -> v2c with a community already set reports no change"""
        mock_module = Mock()
        mock_module.params = {
            "version": "v2c",
            "community": "public",
            "state": "present",
        }
        mock_module.check_mode = False
        mock_array = _array_with(_agent(version="v2c", community="****"))

        update_agent(mock_module, mock_array)

        mock_array.patch_snmp_agents.assert_not_called()
        mock_module.exit_json.assert_called_once_with(changed=False)

    @patch("plugins.modules.purefa_snmp_agent.check_response")
    def test_v2c_switch_from_v3(self, mock_check_response):
        """Switching the agent from v3 to v2c is a change"""
        mock_module = Mock()
        mock_module.params = {
            "version": "v2c",
            "community": "public",
            "state": "present",
        }
        mock_module.check_mode = False
        mock_array = _array_with(
            _agent(version="v3", community="****", user="snmpuser")
        )

        update_agent(mock_module, mock_array)

        mock_array.patch_snmp_agents.assert_called_once()
        mock_module.exit_json.assert_called_once_with(changed=True)

    @patch("plugins.modules.purefa_snmp_agent.check_response")
    def test_v2c_clear_community(self, mock_check_response):
        """state=absent clears a set community"""
        mock_module = Mock()
        mock_module.params = {
            "version": "v2c",
            "community": "public",
            "state": "absent",
        }
        mock_module.check_mode = False
        mock_array = _array_with(_agent(version="v2c", community="****"))

        update_agent(mock_module, mock_array)

        mock_array.patch_snmp_agents.assert_called_once()
        mock_module.exit_json.assert_called_once_with(changed=True)

    def test_v2c_clear_already_cleared(self):
        """clear -> clear reports no change"""
        mock_module = Mock()
        mock_module.params = {
            "version": "v2c",
            "community": None,
            "state": "absent",
        }
        mock_module.check_mode = False
        mock_array = _array_with(_agent(version="v2c"))

        update_agent(mock_module, mock_array)

        mock_array.patch_snmp_agents.assert_not_called()
        mock_module.exit_json.assert_called_once_with(changed=False)

    def test_v2c_present_without_community_already_cleared(self):
        """state=present with no community behaves as a clear"""
        mock_module = Mock()
        mock_module.params = {
            "version": "v2c",
            "community": None,
            "state": "present",
        }
        mock_module.check_mode = False
        mock_array = _array_with(_agent(version="v2c"))

        update_agent(mock_module, mock_array)

        mock_array.patch_snmp_agents.assert_not_called()
        mock_module.exit_json.assert_called_once_with(changed=False)


class TestUpdateAgentV3:
    """Tests for update_agent with version v3"""

    def test_v3_check_mode(self):
        """A pending change in check mode is reported but not applied"""
        mock_module = Mock()
        mock_module.params = _v3_params(auth="SHA", priv="AES")
        mock_module.check_mode = True
        mock_array = _array_with(_agent(version="v2c", community="****"))

        update_agent(mock_module, mock_array)

        mock_module.exit_json.assert_called_once_with(changed=True)
        mock_array.patch_snmp_agents.assert_not_called()

    @patch("plugins.modules.purefa_snmp_agent.check_response")
    def test_v3_full_from_v2c(self, mock_check_response):
        """Switching to v3 with auth and privacy is a change"""
        mock_module = Mock()
        mock_module.params = _v3_params(auth="SHA", priv="AES")
        mock_module.check_mode = False
        mock_array = _array_with(_agent(version="v2c", community="****"))

        update_agent(mock_module, mock_array)

        mock_array.patch_snmp_agents.assert_called_once()
        mock_module.exit_json.assert_called_once_with(changed=True)

    def test_v3_repeated_is_idempotent(self):
        """v3 -> v3 with the same user and protocols reports no change"""
        mock_module = Mock()
        mock_module.params = _v3_params(auth="SHA", priv="AES")
        mock_module.check_mode = False
        mock_array = _array_with(
            _agent(version="v3", user="snmpuser", auth="SHA", priv="AES")
        )

        update_agent(mock_module, mock_array)

        mock_array.patch_snmp_agents.assert_not_called()
        mock_module.exit_json.assert_called_once_with(changed=False)

    @patch("plugins.modules.purefa_snmp_agent.check_response")
    def test_v3_auth_only_protocol_change(self, mock_check_response):
        """A different auth protocol is a change"""
        mock_module = Mock()
        mock_module.params = _v3_params(auth="SHA")
        mock_module.check_mode = False
        mock_array = _array_with(_agent(version="v3", user="snmpuser", auth="MD5"))

        update_agent(mock_module, mock_array)

        mock_array.patch_snmp_agents.assert_called_once()
        mock_module.exit_json.assert_called_once_with(changed=True)

    def test_v3_auth_only_ignores_unsupplied_privacy(self):
        """An unsupplied privacy protocol is neither compared nor cleared"""
        mock_module = Mock()
        mock_module.params = _v3_params(auth="SHA")
        mock_module.check_mode = False
        mock_array = _array_with(
            _agent(version="v3", user="snmpuser", auth="SHA", priv="AES")
        )

        update_agent(mock_module, mock_array)

        mock_array.patch_snmp_agents.assert_not_called()
        mock_module.exit_json.assert_called_once_with(changed=False)

    @patch("plugins.modules.purefa_snmp_agent.check_response")
    def test_v3_privacy_only_protocol_change(self, mock_check_response):
        """A different privacy protocol is a change"""
        mock_module = Mock()
        mock_module.params = _v3_params(priv="AES")
        mock_module.check_mode = False
        mock_array = _array_with(_agent(version="v3", user="snmpuser", priv="DES"))

        update_agent(mock_module, mock_array)

        mock_array.patch_snmp_agents.assert_called_once()
        mock_module.exit_json.assert_called_once_with(changed=True)

    @patch("plugins.modules.purefa_snmp_agent.check_response")
    def test_v3_user_change(self, mock_check_response):
        """A different v3 user is a change"""
        mock_module = Mock()
        mock_module.params = _v3_params(user="newuser")
        mock_module.check_mode = False
        mock_array = _array_with(_agent(version="v3", user="snmpuser"))

        update_agent(mock_module, mock_array)

        mock_array.patch_snmp_agents.assert_called_once()
        mock_module.exit_json.assert_called_once_with(changed=True)

    def test_v3_user_only_same_user(self):
        """The same v3 user with no protocols reports no change"""
        mock_module = Mock()
        mock_module.params = _v3_params()
        mock_module.check_mode = False
        mock_array = _array_with(_agent(version="v3", user="snmpuser"))

        update_agent(mock_module, mock_array)

        mock_array.patch_snmp_agents.assert_not_called()
        mock_module.exit_json.assert_called_once_with(changed=False)

    @patch("plugins.modules.purefa_snmp_agent.flasharray")
    @patch("plugins.modules.purefa_snmp_agent.check_response")
    def test_v3_absent_clears_protocols(self, mock_check_response, mock_flasharray):
        """state=absent clears set protocols"""
        mock_module = Mock()
        mock_module.params = _v3_params(state="absent")
        mock_module.check_mode = False
        mock_array = _array_with(
            _agent(version="v3", user="snmpuser", auth="SHA", priv="AES")
        )

        update_agent(mock_module, mock_array)

        mock_array.patch_snmp_agents.assert_called_once()
        mock_flasharray.SnmpV3Patch.assert_called_once_with(
            auth_protocol="", privacy_protocol="", user="snmpuser"
        )
        mock_module.exit_json.assert_called_once_with(changed=True)

    def test_v3_absent_already_cleared(self):
        """clear -> clear reports no change"""
        mock_module = Mock()
        mock_module.params = _v3_params(state="absent")
        mock_module.check_mode = False
        mock_array = _array_with(_agent(version="v3", user="snmpuser"))

        update_agent(mock_module, mock_array)

        mock_array.patch_snmp_agents.assert_not_called()
        mock_module.exit_json.assert_called_once_with(changed=False)


class TestMain:
    """Tests for main function"""

    @patch("plugins.modules.purefa_snmp_agent.AnsibleModule")
    @patch("plugins.modules.purefa_snmp_agent.get_array")
    @patch("plugins.modules.purefa_snmp_agent.update_agent")
    def test_main_v2c_success(
        self, mock_update_agent, mock_get_array, mock_ansible_module
    ):
        """Test main function with v2c version"""
        mock_module = Mock()
        mock_module.params = {
            "version": "v2c",
            "community": "public",
            "state": "present",
            "user": None,
            "auth_passphrase": None,
            "auth_protocol": None,
            "privacy_passphrase": None,
            "privacy_protocol": None,
        }
        mock_ansible_module.return_value = mock_module
        mock_array = Mock()
        mock_array.get_rest_version.return_value = "2.38"
        mock_get_array.return_value = mock_array

        import plugins.modules.purefa_snmp_agent as agent_module

        original_has = agent_module.HAS_PURESTORAGE
        agent_module.HAS_PURESTORAGE = True

        try:
            agent_module.main()
            mock_update_agent.assert_called_once_with(mock_module, mock_array)
        finally:
            agent_module.HAS_PURESTORAGE = original_has

    @patch("plugins.modules.purefa_snmp_agent.AnsibleModule")
    @patch("plugins.modules.purefa_snmp_agent.get_array")
    @patch("plugins.modules.purefa_snmp_agent.update_agent")
    def test_main_v3_success(
        self, mock_update_agent, mock_get_array, mock_ansible_module
    ):
        """Test main function with v3 version and valid user"""
        mock_module = Mock()
        mock_module.params = {
            "version": "v3",
            "community": None,
            "state": "present",
            "user": "snmpuser",
            "auth_passphrase": "authpassphrase",
            "auth_protocol": "SHA",
            "privacy_passphrase": "privpassphrase",
            "privacy_protocol": "AES",
        }
        mock_ansible_module.return_value = mock_module
        mock_array = Mock()
        mock_array.get_rest_version.return_value = "2.38"
        mock_get_array.return_value = mock_array

        import plugins.modules.purefa_snmp_agent as agent_module

        original_has = agent_module.HAS_PURESTORAGE
        agent_module.HAS_PURESTORAGE = True

        try:
            agent_module.main()
            mock_update_agent.assert_called_once_with(mock_module, mock_array)
        finally:
            agent_module.HAS_PURESTORAGE = original_has

    @patch("plugins.modules.purefa_snmp_agent.AnsibleModule")
    @patch("plugins.modules.purefa_snmp_agent.get_array")
    def test_main_v3_missing_user(self, mock_get_array, mock_ansible_module):
        """Test main function fails when v3 is used without user"""
        import pytest

        mock_module = Mock()
        mock_module.params = {
            "version": "v3",
            "community": None,
            "state": "present",
            "user": None,
            "auth_passphrase": None,
            "auth_protocol": None,
            "privacy_passphrase": None,
            "privacy_protocol": None,
        }
        mock_module.fail_json.side_effect = SystemExit(1)
        mock_ansible_module.return_value = mock_module
        mock_array = Mock()
        mock_array.get_rest_version.return_value = "2.38"
        mock_get_array.return_value = mock_array

        import plugins.modules.purefa_snmp_agent as agent_module

        original_has = agent_module.HAS_PURESTORAGE
        agent_module.HAS_PURESTORAGE = True

        try:
            with pytest.raises(SystemExit):
                agent_module.main()
            mock_module.fail_json.assert_called_once()
            assert "user" in mock_module.fail_json.call_args[1]["msg"]
        finally:
            agent_module.HAS_PURESTORAGE = original_has

    @patch("plugins.modules.purefa_snmp_agent.AnsibleModule")
    @patch("plugins.modules.purefa_snmp_agent.get_array")
    @patch("plugins.modules.purefa_snmp_agent.LooseVersion")
    def test_main_v3_missing_user(
        self, mock_loose_version, mock_get_array, mock_ansible_module
    ):
        """Test main function fails when v3 is used without user"""
        import pytest

        mock_loose_version.side_effect = lambda x: x
        mock_module = Mock()
        mock_module.params = {
            "version": "v3",
            "community": None,
            "state": "present",
            "user": None,  # Missing user for v3
            "auth_passphrase": "validpassphrase",
            "auth_protocol": "SHA",
            "privacy_passphrase": None,
            "privacy_protocol": None,
        }
        mock_module.fail_json.side_effect = SystemExit(1)
        mock_ansible_module.return_value = mock_module
        mock_array = Mock()
        mock_array.get_rest_version.return_value = "2.38"
        mock_get_array.return_value = mock_array

        import plugins.modules.purefa_snmp_agent as agent_module

        original_has = agent_module.HAS_PURESTORAGE
        agent_module.HAS_PURESTORAGE = True

        try:
            with pytest.raises(SystemExit):
                agent_module.main()
            mock_module.fail_json.assert_called_once()
            assert "user" in mock_module.fail_json.call_args[1]["msg"]
        finally:
            agent_module.HAS_PURESTORAGE = original_has

    @patch("plugins.modules.purefa_snmp_agent.AnsibleModule")
    @patch("plugins.modules.purefa_snmp_agent.get_array")
    @patch("plugins.modules.purefa_snmp_agent.LooseVersion")
    def test_main_api_version_too_low(
        self, mock_loose_version, mock_get_array, mock_ansible_module
    ):
        """Test main function fails when API version is too low"""
        import pytest

        mock_loose_version.side_effect = lambda x: x
        mock_module = Mock()
        mock_module.params = {
            "version": "v2c",
            "community": "public",
            "state": "present",
            "user": None,
            "auth_passphrase": None,
            "auth_protocol": None,
            "privacy_passphrase": None,
            "privacy_protocol": None,
        }
        mock_module.fail_json.side_effect = SystemExit(1)
        mock_ansible_module.return_value = mock_module
        mock_array = Mock()
        mock_array.get_rest_version.return_value = "1.0"
        mock_get_array.return_value = mock_array

        import plugins.modules.purefa_snmp_agent as agent_module

        original_has = agent_module.HAS_PURESTORAGE
        agent_module.HAS_PURESTORAGE = True

        try:
            with pytest.raises(SystemExit):
                agent_module.main()
            mock_module.fail_json.assert_called_once()
        finally:
            agent_module.HAS_PURESTORAGE = original_has

    @patch("plugins.modules.purefa_snmp_agent.AnsibleModule")
    @patch("plugins.modules.purefa_snmp_agent.get_array")
    def test_main_v3_auth_passphrase_too_short(
        self, mock_get_array, mock_ansible_module
    ):
        """A v3 auth passphrase shorter than 8 characters is rejected"""
        import pytest

        mock_module = Mock()
        mock_module.params = {
            "version": "v3",
            "community": None,
            "state": "present",
            "user": "snmpuser",
            "auth_passphrase": "short",
            "auth_protocol": "SHA",
            "privacy_passphrase": None,
            "privacy_protocol": None,
        }
        mock_module.fail_json.side_effect = SystemExit(1)
        mock_ansible_module.return_value = mock_module
        mock_array = Mock()
        mock_array.get_rest_version.return_value = "2.38"
        mock_get_array.return_value = mock_array

        with pytest.raises(SystemExit):
            main()

        mock_module.fail_json.assert_called_once_with(
            msg="auth_password must be between 8 and 32 characters"
        )

    @patch("plugins.modules.purefa_snmp_agent.AnsibleModule")
    @patch("plugins.modules.purefa_snmp_agent.get_array")
    def test_main_v3_privacy_passphrase_too_long(
        self, mock_get_array, mock_ansible_module
    ):
        """A v3 privacy passphrase longer than 63 characters is rejected"""
        import pytest

        mock_module = Mock()
        mock_module.params = {
            "version": "v3",
            "community": None,
            "state": "present",
            "user": "snmpuser",
            "auth_passphrase": None,
            "auth_protocol": None,
            "privacy_passphrase": "p" * 64,
            "privacy_protocol": "AES",
        }
        mock_module.fail_json.side_effect = SystemExit(1)
        mock_ansible_module.return_value = mock_module
        mock_array = Mock()
        mock_array.get_rest_version.return_value = "2.38"
        mock_get_array.return_value = mock_array

        with pytest.raises(SystemExit):
            main()

        mock_module.fail_json.assert_called_once_with(
            msg="privacy_password must be between 8 and 63 characters"
        )
