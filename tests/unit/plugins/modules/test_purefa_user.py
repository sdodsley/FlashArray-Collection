# Copyright: (c) 2026, Everpure Ansible Team <pure-ansible-team@everpuredata.com>
# GNU General Public License v3.0+ (see COPYING.GPLv3 or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Unit tests for purefa_user module."""

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

from plugins.modules.purefa_user import (
    get_user,
    create_local_user,
    delete_local_user,
    delete_ad_user,
    update_ad_user,
    main,
    AD_NAME_PATTERN,
    LOCAL_NAME_PATTERN,
)

# Referenced by name so the tests exercise the module's own patterns rather
# than a copy that can drift out of step with them.
AD_PATTERN = AD_NAME_PATTERN


class TestGetUser:
    """Test cases for get_user function"""

    def test_get_user_exists(self):
        """Test get_user returns user when it exists"""
        mock_module = Mock()
        mock_module.params = {"name": "test-user"}
        mock_array = Mock()
        mock_user = Mock()
        mock_user.name = "test-user"
        mock_array.get_admins.return_value = Mock(status_code=200, items=[mock_user])

        result = get_user(mock_module, mock_array)

        assert result == mock_user
        mock_array.get_admins.assert_called_once_with(names=["test-user"])

    def test_get_user_not_exists(self):
        """Test get_user returns None when user doesn't exist"""
        mock_module = Mock()
        mock_module.params = {"name": "nonexistent"}
        mock_array = Mock()
        mock_array.get_admins.return_value = Mock(status_code=404, items=[])

        result = get_user(mock_module, mock_array)

        assert result is None


class TestDeleteLocalUser:
    """Test cases for delete_local_user function"""

    def test_delete_local_user_check_mode(self):
        """Test delete_local_user in check mode"""
        mock_module = Mock()
        mock_module.check_mode = True
        mock_module.params = {"name": "test-user"}
        mock_array = Mock()

        delete_local_user(mock_module, mock_array)

        mock_module.exit_json.assert_called_once_with(changed=True)
        mock_array.delete_admins.assert_not_called()


class TestCreateLocalUser:
    """Test cases for create_local_user function"""

    @patch("plugins.modules.purefa_user.check_response")
    def test_create_local_user_new_user_check_mode(self, mock_check_response):
        """Test create_local_user with new user in check mode"""
        mock_module = Mock()
        mock_module.check_mode = True
        mock_module.params = {
            "name": "new-user",
            "role": "storage_admin",
            "password": "secret123",
            "api": False,
            "public_key": None,
        }
        mock_array = Mock()

        create_local_user(mock_module, mock_array, user=None)

        mock_module.exit_json.assert_called_once()
        mock_array.post_admins.assert_not_called()


class TestDeleteAdUser:
    """Test cases for delete_ad_user function"""

    @patch("plugins.modules.purefa_user.check_response")
    def test_delete_ad_user_with_user(self, mock_check_response):
        """Test delete_ad_user removes API token and public key"""
        mock_module = Mock()
        mock_module.check_mode = False
        mock_module.params = {"name": "ad-user"}
        mock_array = Mock()
        mock_user = Mock()
        mock_user.public_key = "ssh-rsa AAA..."

        delete_ad_user(mock_module, mock_array, user=mock_user)

        mock_module.exit_json.assert_called_once_with(changed=True)
        mock_array.delete_admins_api_tokens.assert_called_once()

    def test_delete_ad_user_no_user(self):
        """Test delete_ad_user when user is None"""
        mock_module = Mock()
        mock_module.check_mode = False
        mock_module.params = {"name": "ad-user"}
        mock_array = Mock()

        delete_ad_user(mock_module, mock_array, user=None)

        mock_module.exit_json.assert_called_once_with(changed=False)
        mock_array.delete_admins_api_tokens.assert_not_called()

    def test_delete_ad_user_check_mode(self):
        """Test delete_ad_user in check mode"""
        mock_module = Mock()
        mock_module.check_mode = True
        mock_module.params = {"name": "ad-user"}
        mock_array = Mock()
        mock_user = Mock()

        delete_ad_user(mock_module, mock_array, user=mock_user)

        mock_module.exit_json.assert_called_once_with(changed=False)
        mock_array.delete_admins_api_tokens.assert_not_called()


class TestCreateLocalUserSuccess:
    """Test cases for create_local_user success paths"""

    @patch("plugins.modules.purefa_user.check_response")
    def test_create_local_user_success(self, mock_check_response):
        """Test create_local_user successfully creates new user"""
        mock_module = Mock()
        mock_module.check_mode = False
        mock_module.params = {
            "name": "testuser",
            "role": "readonly",
            "password": "testpass123",
            "api": False,
            "public_key": None,
        }
        mock_array = Mock()
        mock_array.post_admins.return_value = Mock(status_code=200)

        create_local_user(mock_module, mock_array, user=None)

        mock_array.post_admins.assert_called_once()
        mock_module.exit_json.assert_called_once()

    @patch("plugins.modules.purefa_user.check_response")
    def test_create_local_user_existing_no_password_change(self, mock_check_response):
        """Test create_local_user exits when password change not needed"""
        mock_module = Mock()
        mock_module.check_mode = False
        mock_module.params = {
            "name": "testuser",
            "role": "readonly",
            "password": "newpass",
            "old_password": None,
            "api": False,
            "public_key": None,
        }
        mock_array = Mock()
        mock_user = Mock()
        mock_user.role = None

        create_local_user(mock_module, mock_array, user=mock_user)

        # Function should call exit_json with changed=False since no password change
        assert mock_module.exit_json.called


class TestDeleteLocalUserSuccess:
    """Test cases for delete_local_user success paths"""

    @patch("plugins.modules.purefa_user.check_response")
    def test_delete_local_user_success(self, mock_check_response):
        """Test delete_local_user successfully deletes user"""
        mock_module = Mock()
        mock_module.check_mode = False
        mock_module.params = {"name": "testuser"}
        mock_array = Mock()
        mock_array.delete_admins.return_value = Mock(status_code=200)

        delete_local_user(mock_module, mock_array)

        mock_array.delete_admins.assert_called_once_with(names=["testuser"])
        mock_module.exit_json.assert_called_once_with(changed=True)


class TestUpdateAdUser:
    """Test cases for update_ad_user function"""

    @patch("plugins.modules.purefa_user.check_response")
    @patch("plugins.modules.purefa_user.convert_time_to_millisecs")
    def test_update_ad_user_create_api_token(
        self, mock_convert_time, mock_check_response
    ):
        """Test update_ad_user creates API token for new user"""
        mock_convert_time.return_value = 3600000  # 1 hour in milliseconds
        mock_module = Mock()
        mock_module.params = {
            "name": "ad-user",
            "api": True,
            "timeout": "1h",
            "public_key": None,
        }
        mock_module.check_mode = False
        mock_array = Mock()

        # Mock API token response
        mock_api_token = Mock()
        mock_api_token.api_token = Mock()
        mock_api_token.api_token.token = "test-token-12345"
        mock_array.post_admins_api_tokens.return_value = Mock(
            status_code=200, items=[mock_api_token]
        )

        update_ad_user(mock_module, mock_array, user=None)

        mock_array.post_admins_api_tokens.assert_called_once()
        mock_module.exit_json.assert_called_once()
        # Check that it passed the token to exit_json
        call_kwargs = mock_module.exit_json.call_args[1]
        assert call_kwargs["changed"] is True
        assert call_kwargs["user_info"] == "test-token-12345"

    @patch("plugins.modules.purefa_user.check_response")
    @patch("plugins.modules.purefa_user.convert_time_to_millisecs")
    def test_update_ad_user_refresh_api_token(
        self, mock_convert_time, mock_check_response
    ):
        """Test update_ad_user refreshes API token for existing user"""
        mock_convert_time.return_value = 3600000
        mock_module = Mock()
        mock_module.params = {
            "name": "ad-user",
            "api": True,
            "timeout": "1h",
            "public_key": None,
        }
        mock_module.check_mode = False
        mock_array = Mock()
        mock_user = Mock()

        # Mock API token response
        mock_api_token = Mock()
        mock_api_token.api_token = Mock()
        mock_api_token.api_token.token = "refreshed-token"
        mock_array.post_admins_api_tokens.return_value = Mock(
            status_code=200, items=[mock_api_token]
        )
        mock_array.delete_admins_api_tokens.return_value = Mock(status_code=200)

        update_ad_user(mock_module, mock_array, user=mock_user)

        # Should delete old token first, then create new one
        mock_array.delete_admins_api_tokens.assert_called_once()
        mock_array.post_admins_api_tokens.assert_called_once()
        mock_module.exit_json.assert_called_once()

    @patch("plugins.modules.purefa_user.check_response")
    def test_update_ad_user_add_public_key(self, mock_check_response):
        """Test update_ad_user adds SSH public key"""
        mock_module = Mock()
        mock_module.params = {
            "name": "ad-user",
            "api": False,
            "public_key": "ssh-rsa AAAAB...",
        }
        mock_module.check_mode = False
        mock_array = Mock()
        mock_array.patch_admins.return_value = Mock(status_code=200)

        update_ad_user(mock_module, mock_array, user=None)

        mock_array.patch_admins.assert_called_once()
        mock_module.exit_json.assert_called_once()
        call_kwargs = mock_module.exit_json.call_args[1]
        assert call_kwargs["changed"] is True

    @patch("plugins.modules.purefa_user.check_response")
    def test_update_ad_user_masked_key_always_patches(self, mock_check_response):
        """The array masks a stored key as ****, so setting one always reports changed"""
        mock_module = Mock()
        mock_module.params = {
            "name": "ad-user",
            "api": False,
            "public_key": "ssh-ed25519 AAAAC3...",
        }
        mock_module.check_mode = False
        mock_array = Mock()
        mock_user = Mock()
        mock_user.public_key = "****"

        update_ad_user(mock_module, mock_array, user=mock_user)

        mock_array.patch_admins.assert_called_once()
        call_kwargs = mock_module.exit_json.call_args[1]
        assert call_kwargs["changed"] is True

    @patch("plugins.modules.purefa_user.check_response")
    def test_update_ad_user_removal_is_idempotent(self, mock_check_response):
        """Removing a key that is already absent reports no change"""
        mock_module = Mock()
        mock_module.params = {
            "name": "ad-user",
            "api": False,
            "public_key": "",
        }
        mock_module.check_mode = False
        mock_array = Mock()
        mock_user = Mock()
        mock_user.public_key = ""

        update_ad_user(mock_module, mock_array, user=mock_user)

        mock_array.patch_admins.assert_not_called()
        call_kwargs = mock_module.exit_json.call_args[1]
        assert call_kwargs["changed"] is False

    @patch("plugins.modules.purefa_user.check_response")
    def test_update_ad_user_removal_of_existing_key(self, mock_check_response):
        """Removing a key that is set patches with an empty string"""
        mock_module = Mock()
        mock_module.params = {
            "name": "ad-user",
            "api": False,
            "public_key": "",
        }
        mock_module.check_mode = False
        mock_array = Mock()
        mock_user = Mock()
        mock_user.public_key = "****"

        update_ad_user(mock_module, mock_array, user=mock_user)

        mock_array.patch_admins.assert_called_once()
        call_kwargs = mock_module.exit_json.call_args[1]
        assert call_kwargs["changed"] is True

    @patch("plugins.modules.purefa_user.check_response")
    def test_update_ad_user_public_key_check_mode(self, mock_check_response):
        """Test update_ad_user reports a change without calling the array in check mode"""
        mock_module = Mock()
        mock_module.params = {
            "name": "ad-user",
            "api": False,
            "public_key": "ssh-rsa NEWKEY...",
        }
        mock_module.check_mode = True
        mock_array = Mock()
        mock_user = Mock()
        mock_user.public_key = "****"

        update_ad_user(mock_module, mock_array, user=mock_user)

        mock_array.patch_admins.assert_not_called()
        call_kwargs = mock_module.exit_json.call_args[1]
        assert call_kwargs["changed"] is True

    def test_update_ad_user_no_changes(self):
        """Test update_ad_user with no API or public key"""
        mock_module = Mock()
        mock_module.params = {
            "name": "ad-user",
            "api": False,
            "public_key": None,
        }
        mock_array = Mock()

        update_ad_user(mock_module, mock_array, user=None)

        mock_array.post_admins_api_tokens.assert_not_called()
        mock_array.patch_admins.assert_not_called()
        mock_module.exit_json.assert_called_once()
        call_kwargs = mock_module.exit_json.call_args[1]
        assert call_kwargs["changed"] is False


class TestCreateLocalUserExtended:
    """Extended test cases for create_local_user function"""

    @patch("plugins.modules.purefa_user.check_response")
    def test_create_local_user_with_role_change(self, mock_check_response):
        """Test create_local_user when role changes"""
        mock_module = Mock()
        mock_module.params = {
            "name": "testuser",
            "role": "storage_admin",
            "password": None,
            "api": False,
            "public_key": None,
        }
        mock_module.check_mode = False
        mock_array = Mock()

        # Existing user with different role
        mock_user = Mock()
        mock_user.role = Mock()
        mock_user.role.name = "readonly"
        mock_array.patch_admins.return_value = Mock(status_code=200)

        create_local_user(mock_module, mock_array, mock_user)

        mock_array.patch_admins.assert_called_once()
        mock_module.exit_json.assert_called_once()
        call_kwargs = mock_module.exit_json.call_args[1]
        assert call_kwargs["changed"] is True

    @patch("plugins.modules.purefa_user.check_response")
    @patch("plugins.modules.purefa_user.convert_time_to_millisecs")
    def test_create_local_user_with_api_token(
        self, mock_convert_time, mock_check_response
    ):
        """Test create_local_user creates API token"""
        mock_convert_time.return_value = 3600000
        mock_module = Mock()
        mock_module.params = {
            "name": "testuser",
            "role": "storage_admin",
            "password": "pass123",
            "api": True,
            "public_key": None,
            "timeout": "1h",
        }
        mock_module.check_mode = False
        mock_array = Mock()

        # New user
        mock_array.post_admins.return_value = Mock(status_code=200)
        mock_api_response = Mock()
        mock_api_response.api_token = Mock()
        mock_api_response.api_token.token = "new-token-123"
        mock_array.post_admins_api_tokens.return_value = Mock(
            status_code=200, items=[mock_api_response]
        )

        create_local_user(mock_module, mock_array, user=None)

        mock_array.post_admins.assert_called_once()
        mock_array.post_admins_api_tokens.assert_called_once()
        mock_module.exit_json.assert_called_once()
        call_kwargs = mock_module.exit_json.call_args[1]
        assert call_kwargs["changed"] is True
        assert "new-token-123" in call_kwargs["user_info"]

    @patch("plugins.modules.purefa_user.check_response")
    def test_create_local_user_with_ssh_key(self, mock_check_response):
        """Test create_local_user adds SSH public key"""
        mock_module = Mock()
        mock_module.params = {
            "name": "testuser",
            "role": "readonly",
            "password": "pass123",
            "api": False,
            "public_key": "ssh-rsa AAAAB...",
        }
        mock_module.check_mode = False
        mock_array = Mock()

        # New user
        mock_array.post_admins.return_value = Mock(status_code=200)
        mock_array.patch_admins.return_value = Mock(status_code=200)

        create_local_user(mock_module, mock_array, user=None)

        mock_array.post_admins.assert_called_once()
        # Should call patch_admins to add SSH key
        mock_array.patch_admins.assert_called_once()
        mock_module.exit_json.assert_called_once()

    def test_create_local_user_no_changes(self):
        """Test create_local_user when no changes needed"""
        mock_module = Mock()
        mock_module.params = {
            "name": "testuser",
            "role": "storage_admin",
            "password": None,
            "api": False,
            "public_key": None,
        }
        mock_module.check_mode = False
        mock_array = Mock()

        # Existing user with same role
        mock_user = Mock()
        mock_user.role = Mock()
        mock_user.role.name = "storage_admin"

        create_local_user(mock_module, mock_array, mock_user)

        mock_array.patch_admins.assert_not_called()
        mock_module.exit_json.assert_called_once()
        call_kwargs = mock_module.exit_json.call_args[1]
        assert call_kwargs["changed"] is False


class TestAdUsernameValidation:
    """The AD name pattern from #1060: permissive enough for a directory,
    bounded enough that a name cannot widen which admins a request targets."""

    ACCEPTED = [
        "meagan.gibbons",
        "first.last",
        "EXPEDIENT\\meagan",
        "meagan@expedient.com",
        "svc_account-01",
        "a",
        "A" * 128,
        # A directory service names its own users and is not limited to
        # ASCII. The array looks these up quite happily - it answers with
        # "Unable to find specified user", an existence error, not a
        # complaint about the name.
        "josé.garcía",
        "Ωmega.user",
    ]

    REJECTED = [
        ("alice,bob", "comma splits into two names on the wire"),
        ("alice bob", "whitespace"),
        ("", "empty despite required=True"),
        (" alice", "leading whitespace"),
        ("alice ", "trailing whitespace"),
        ("alice&role=array_admin", "ampersand"),
        ("alice?x=1", "query separator"),
        ("alice/../pureuser", "slash"),
        ("alice#fragment", "fragment separator"),
        ("alice\nbob", "newline"),
        # $ matches before a trailing newline, so this needs \Z. A name read
        # with lookup('file', ...) carries one.
        ("alice\n", "trailing newline"),
        ("A" * 129, "over the length bound"),
    ]

    def test_accepts_real_directory_formats(self):
        for name in self.ACCEPTED:
            assert AD_PATTERN.match(name), "should accept %r" % (name,)

    def test_rejects_separators_and_whitespace(self):
        for name, why in self.REJECTED:
            assert not AD_PATTERN.match(name), "should reject %r (%s)" % (name, why)


class TestNameValidationIsApplied:
    """The patterns reach the real code path - carried from #1061"""

    def _module(self, name, ad_user):
        mock_module = Mock()
        mock_module.check_mode = False
        mock_module.fail_json.side_effect = SystemExit(1)
        mock_module.exit_json.side_effect = SystemExit(0)
        mock_module.params = {
            "name": name,
            "ad_user": ad_user,
            "state": "present",
            "role": "readonly",
            "password": None,
            "old_password": None,
            "api": False,
            "timeout": "0",
            "public_key": None,
        }
        return mock_module

    @patch("plugins.modules.purefa_user.get_array")
    @patch("plugins.modules.purefa_user.AnsibleModule")
    def test_ad_username_with_dot_is_accepted(
        self, mock_ansible_module, mock_get_array
    ):
        """The name in issue #1060 must reach the array"""
        import pytest

        mock_module = self._module("meagan.gibbons", ad_user=True)
        mock_ansible_module.return_value = mock_module
        mock_array = Mock()
        # An AD user with no array-side state is not returned by get_admins
        mock_array.get_admins.return_value = Mock(status_code=400)
        mock_get_array.return_value = mock_array

        with pytest.raises(SystemExit):
            main()

        mock_module.fail_json.assert_not_called()

    @patch("plugins.modules.purefa_user.get_array")
    @patch("plugins.modules.purefa_user.AnsibleModule")
    def test_ad_username_with_comma_is_rejected(
        self, mock_ansible_module, mock_get_array
    ):
        """A comma would target two admins, so it must not reach the array"""
        import pytest

        mock_module = self._module("alice,pureuser", ad_user=True)
        mock_ansible_module.return_value = mock_module
        mock_get_array.return_value = Mock()

        with pytest.raises(SystemExit):
            main()

        mock_module.fail_json.assert_called_once()

    @patch("plugins.modules.purefa_user.get_array")
    @patch("plugins.modules.purefa_user.AnsibleModule")
    def test_local_username_with_dot_is_still_rejected(
        self, mock_ansible_module, mock_get_array
    ):
        """The local account rules still apply to local users"""
        import pytest

        mock_module = self._module("meagan.gibbons", ad_user=False)
        mock_ansible_module.return_value = mock_module
        mock_get_array.return_value = Mock()

        with pytest.raises(SystemExit):
            main()

        mock_module.fail_json.assert_called_once()
        assert "lowercase" in mock_module.fail_json.call_args[1]["msg"]

    @patch("plugins.modules.purefa_user.get_array")
    @patch("plugins.modules.purefa_user.AnsibleModule")
    def test_local_username_uppercase_is_still_rejected(
        self, mock_ansible_module, mock_get_array
    ):
        """Uppercase local names are still rejected"""
        import pytest

        mock_module = self._module("Ansible", ad_user=False)
        mock_ansible_module.return_value = mock_module
        mock_get_array.return_value = Mock()

        with pytest.raises(SystemExit):
            main()

        mock_module.fail_json.assert_called_once()

    def test_local_pattern_is_unchanged(self):
        """The local rules are untouched by the AD work"""
        assert LOCAL_NAME_PATTERN.match("ansible")
        assert LOCAL_NAME_PATTERN.match("svc-ansible")
        assert not LOCAL_NAME_PATTERN.match("meagan.gibbons")
        assert not LOCAL_NAME_PATTERN.match("Ansible")


class TestApiTokenCheckMode:
    """Check mode must not revoke a live API token - carried from #1061"""

    @patch("plugins.modules.purefa_user.check_response")
    @patch("plugins.modules.purefa_user.convert_time_to_millisecs")
    def test_ad_user_token_not_recreated_in_check_mode(
        self, mock_convert_time, mock_check_response
    ):
        """An AD user's token survives a --check run"""
        mock_convert_time.return_value = 3600000
        mock_module = Mock()
        mock_module.check_mode = True
        mock_module.params = {
            "name": "ad-user",
            "api": True,
            "timeout": "1h",
            "public_key": None,
        }
        mock_array = Mock()

        update_ad_user(mock_module, mock_array, user=Mock())

        mock_array.delete_admins_api_tokens.assert_not_called()
        mock_array.post_admins_api_tokens.assert_not_called()
        assert mock_module.exit_json.call_args[1]["changed"] is True

    @patch("plugins.modules.purefa_user.check_response")
    @patch("plugins.modules.purefa_user.convert_time_to_millisecs")
    def test_local_user_token_not_recreated_in_check_mode(
        self, mock_convert_time, mock_check_response
    ):
        """An existing local user's token survives a --check run"""
        mock_convert_time.return_value = 0
        mock_module = Mock()
        mock_module.check_mode = True
        mock_module.params = {
            "name": "ansible",
            "role": "readonly",
            "password": None,
            "old_password": None,
            "api": True,
            "timeout": "0",
            "public_key": None,
        }
        mock_array = Mock()
        mock_user = Mock()
        mock_user.role = Mock()
        mock_user.role.name = "readonly"

        create_local_user(mock_module, mock_array, user=mock_user)

        mock_array.delete_admins_api_tokens.assert_not_called()
        mock_array.post_admins_api_tokens.assert_not_called()
        assert mock_module.exit_json.call_args[1]["changed"] is True
