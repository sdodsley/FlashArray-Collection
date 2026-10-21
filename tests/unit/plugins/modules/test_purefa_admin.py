# Copyright: (c) 2025, Simon Dodsley (@sdodsley)
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Unit tests for purefa_admin module"""

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
from plugins.modules.purefa_admin import main


class TestAdminValidation:
    """Test cases for admin settings validation"""

    @patch("plugins.modules.purefa_admin.HAS_PURESTORAGE", False)
    @patch("plugins.modules.purefa_admin.AnsibleModule")
    def test_missing_purestorage_dependency_fails(self, mock_ansible_module):
        """Test that missing pypureclient dependency fails"""
        mock_module = Mock()
        mock_module.params = {
            "sso": False,
            "max_login": None,
            "min_password": 1,
            "lockout": None,
        }
        mock_module.fail_json.side_effect = SystemExit(1)
        mock_ansible_module.return_value = mock_module

        with pytest.raises(SystemExit):
            main()

        mock_module.fail_json.assert_called_once_with(
            msg="py-pure-client sdk is required for this module"
        )

    @patch("plugins.modules.purefa_admin.AnsibleModule")
    def test_lockout_out_of_range_fails(self, mock_ansible_module):
        """Test that lockout out of range fails"""
        mock_module = Mock()
        mock_module.params = {
            "sso": False,
            "max_login": None,
            "min_password": 1,
            "lockout": 8000000,  # Too large
        }
        mock_module.fail_json.side_effect = SystemExit(1)
        mock_ansible_module.return_value = mock_module

        with pytest.raises(SystemExit):
            main()

        mock_module.fail_json.assert_called_once_with(
            msg="Lockout must be between 1 and 7776000 seconds"
        )


class TestAdminOldApiVersion:
    """Test cases for unsupported API version"""

    @patch("plugins.modules.purefa_admin.LooseVersion")
    @patch("plugins.modules.purefa_admin.get_array")
    @patch("plugins.modules.purefa_admin.AnsibleModule")
    def test_old_api_version_fails(
        self, mock_ansible_module, mock_get_array, mock_loose_version
    ):
        """Test that old API version fails with appropriate message"""
        mock_module = Mock()
        mock_module.params = {
            "sso": False,
            "max_login": None,
            "min_password": 1,
            "lockout": None,
        }
        mock_module.fail_json.side_effect = SystemExit(1)
        mock_ansible_module.return_value = mock_module

        mock_array = Mock()
        mock_array.get_rest_version.return_value = "2.1"
        mock_get_array.return_value = mock_array

        # Make LooseVersion return comparable values - 2.2 > 2.1
        def mock_version(v):
            versions = {"2.2": 2.2, "2.1": 2.1}
            return versions.get(v, float(v))

        mock_loose_version.side_effect = mock_version

        with pytest.raises(SystemExit):
            main()

        mock_module.fail_json.assert_called_once_with(
            msg="Purity version does not support Global Admin settings"
        )


class TestAdminNoChange:
    """Test cases for no change scenarios"""

    @patch("plugins.modules.purefa_admin.LooseVersion")
    @patch("plugins.modules.purefa_admin.get_array")
    @patch("plugins.modules.purefa_admin.AnsibleModule")
    def test_no_change_when_settings_match(
        self, mock_ansible_module, mock_get_array, mock_lv
    ):
        """Test no change when settings already match"""
        mock_module = Mock()
        mock_module.check_mode = False
        mock_module.params = {
            "sso": False,
            "max_login": None,
            "min_password": 1,
            "lockout": None,
        }
        mock_ansible_module.return_value = mock_module

        mock_array = Mock()
        mock_array.get_rest_version.return_value = "2.3"
        mock_get_array.return_value = mock_array

        # Make LooseVersion comparisons work - 2.2 <= 2.3
        mock_lv.side_effect = float

        # Mock current admin settings matching desired values
        mock_current = Mock()
        mock_current.single_sign_on_enabled = False
        mock_current.min_password_length = 1
        mock_response = Mock()
        mock_response.items = [mock_current]
        mock_array.get_admins_settings.return_value = mock_response

        main()

        mock_module.exit_json.assert_called_once_with(changed=False)


def _run_main(params, current):
    """Run main() against mocked current admin settings, returning the mocks"""
    mock_module = Mock()
    mock_module.check_mode = False
    mock_module.params = params
    mock_module.fail_json.side_effect = SystemExit(1)
    mock_array = Mock()
    mock_array.get_rest_version.return_value = "2.3"
    mock_array.get_admins_settings.return_value = Mock(items=[current])
    mock_array.patch_admins_settings.return_value = Mock(status_code=200)
    with patch(
        "plugins.modules.purefa_admin.AnsibleModule", return_value=mock_module
    ), patch("plugins.modules.purefa_admin.get_array", return_value=mock_array), patch(
        "plugins.modules.purefa_admin.LooseVersion", side_effect=float
    ), patch(
        "plugins.modules.purefa_admin.AdminSettings"
    ) as mock_settings:
        main()
    return mock_module, mock_array, mock_settings


def _current(sso=False, min_password=1, lockout=None, max_login=None):
    """Current admin settings; the array omits unset lockout and max_login"""
    spec = ["single_sign_on_enabled", "min_password_length"]
    if lockout is not None:
        spec.append("lockout_duration")
    if max_login is not None:
        spec.append("max_login_attempts")
    current = Mock(spec=spec)
    current.single_sign_on_enabled = sso
    current.min_password_length = min_password
    if lockout is not None:
        current.lockout_duration = lockout
    if max_login is not None:
        current.max_login_attempts = max_login
    return current


class TestAdminLockoutClear:
    """lockout: 0 clears an existing lockout duration"""

    def test_zero_clears_existing_lockout(self):
        params = {"sso": None, "max_login": None, "min_password": 1, "lockout": 0}
        mock_module, mock_array, mock_settings = _run_main(
            params, _current(lockout=300000)
        )

        mock_module.exit_json.assert_called_once_with(changed=True)
        mock_array.patch_admins_settings.assert_called_once()
        assert mock_settings.call_args[1]["lockout_duration"] == 0

    def test_zero_on_unset_lockout_is_no_change(self):
        params = {"sso": None, "max_login": None, "min_password": 1, "lockout": 0}
        mock_module, mock_array, dummy = _run_main(params, _current())

        mock_module.exit_json.assert_called_once_with(changed=False)
        mock_array.patch_admins_settings.assert_not_called()

    def test_zero_passes_range_check(self):
        params = {"sso": None, "max_login": None, "min_password": 1, "lockout": 0}
        mock_module, dummy, dummy2 = _run_main(params, _current())

        mock_module.fail_json.assert_not_called()

    def test_existing_lockout_is_kept_when_omitted(self):
        params = {"sso": True, "max_login": None, "min_password": 1, "lockout": None}
        mock_module, dummy, mock_settings = _run_main(params, _current(lockout=300000))

        mock_module.exit_json.assert_called_once_with(changed=True)
        assert mock_settings.call_args[1]["lockout_duration"] == 300000


class TestAdminSso:
    """sso is tri-state so that false can switch Single Sign-On off"""

    def test_false_disables_sso(self):
        params = {"sso": False, "max_login": None, "min_password": 1, "lockout": None}
        mock_module, mock_array, mock_settings = _run_main(params, _current(sso=True))

        mock_module.exit_json.assert_called_once_with(changed=True)
        assert mock_settings.call_args[1]["single_sign_on_enabled"] is False

    def test_omitted_leaves_sso_alone(self):
        params = {"sso": None, "max_login": None, "min_password": 1, "lockout": None}
        mock_module, mock_array, dummy = _run_main(params, _current(sso=True))

        mock_module.exit_json.assert_called_once_with(changed=False)
        mock_array.patch_admins_settings.assert_not_called()

    def test_true_enables_sso(self):
        params = {"sso": True, "max_login": None, "min_password": 1, "lockout": None}
        mock_module, dummy, mock_settings = _run_main(params, _current(sso=False))

        mock_module.exit_json.assert_called_once_with(changed=True)
        assert mock_settings.call_args[1]["single_sign_on_enabled"] is True
