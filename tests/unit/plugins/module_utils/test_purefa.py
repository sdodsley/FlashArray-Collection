# Copyright: (c) 2026, Everpure Ansible Team <pure-ansible-team@everpuredata.com>
# GNU General Public License v3.0+ (see COPYING.GPLv3 or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Unit tests for purefa module utilities."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import sys
from unittest.mock import Mock, patch, MagicMock

# Mock external dependencies before importing purefa
sys.modules["pypureclient"] = MagicMock()
sys.modules["pypureclient.flasharray"] = MagicMock()
sys.modules["urllib3"] = MagicMock()
sys.modules["distro"] = MagicMock()

from plugins.module_utils.purefa import get_array, purefa_argument_spec


class TestPurefaArgumentSpec:
    """Tests for purefa_argument_spec function."""

    def test_returns_dict(self):
        """Test that function returns a dictionary."""
        assert isinstance(purefa_argument_spec(), dict)

    def test_contains_fa_url(self):
        """Test that spec contains fa_url."""
        result = purefa_argument_spec()
        assert "fa_url" in result
        assert result["fa_url"] == {}

    def test_contains_api_token(self):
        """Test that spec contains api_token with no_log."""
        result = purefa_argument_spec()
        assert "api_token" in result
        assert result["api_token"]["no_log"] is True

    def test_contains_disable_warnings(self):
        """Test that spec contains disable_warnings with defaults."""
        result = purefa_argument_spec()
        assert result["disable_warnings"]["type"] == "bool"
        assert result["disable_warnings"]["default"] is False

    def test_all_expected_keys(self):
        """Test that spec contains exactly the expected keys."""
        result = purefa_argument_spec()
        expected_keys = {
            "fa_url",
            "api_token",
            "id_token",
            "private_key_file",
            "private_key_password",
            "username",
            "client_id",
            "key_id",
            "issuer",
            "disable_warnings",
        }
        assert set(result.keys()) == expected_keys

    def test_token_auth_secrets_no_log(self):
        """Secret token-auth params must be marked no_log."""
        result = purefa_argument_spec()
        assert result["id_token"]["no_log"] is True
        assert result["private_key_password"]["no_log"] is True

    def test_non_secret_params_no_log_false(self):
        """Non-secret params that trip the no_log heuristic are silenced."""
        result = purefa_argument_spec()
        assert result["private_key_file"]["no_log"] is False
        assert result["key_id"]["no_log"] is False


class TestGetArray:
    """Tests for get_array function."""

    @patch("plugins.module_utils.purefa.flasharray.Client")
    @patch("plugins.module_utils.purefa.HAS_PYPURECLIENT", True)
    def test_with_module_params(self, mock_client_class):
        """Test get_array with api_token module parameters."""
        mock_module = Mock()
        mock_module.params = {
            "fa_url": "flasharray.example.com",
            "api_token": "test-token-123",
            "disable_warnings": False,
        }
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        result = get_array(mock_module)

        call_kwargs = mock_client_class.call_args[1]
        assert call_kwargs["target"] == "flasharray.example.com"
        assert call_kwargs["api_token"] == "test-token-123"
        assert "user_agent" in call_kwargs
        mock_client.get_hardware.assert_called_once()
        assert result == mock_client

    @patch("plugins.module_utils.purefa.flasharray.Client")
    @patch("plugins.module_utils.purefa.HAS_PYPURECLIENT", True)
    @patch("plugins.module_utils.purefa.environ")
    def test_with_environment_vars(self, mock_environ, mock_client_class):
        """Test get_array with environment variables."""
        mock_module = Mock()
        mock_module.params = {
            "fa_url": None,
            "api_token": None,
            "disable_warnings": False,
        }
        env_vars = {
            "PUREFA_URL": "env-flasharray.example.com",
            "PUREFA_API": "env-token-456",
        }
        mock_environ.get.side_effect = env_vars.get
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        result = get_array(mock_module)

        call_kwargs = mock_client_class.call_args[1]
        assert call_kwargs["target"] == "env-flasharray.example.com"
        assert call_kwargs["api_token"] == "env-token-456"
        assert result == mock_client

    @patch("plugins.module_utils.purefa.HAS_PYPURECLIENT", True)
    @patch("plugins.module_utils.purefa.environ")
    def test_missing_credentials(self, mock_environ):
        """Test that missing credentials causes failure."""
        mock_module = Mock()
        mock_module.params = {
            "fa_url": None,
            "api_token": None,
            "disable_warnings": False,
        }
        mock_module.fail_json.side_effect = SystemExit("fail_json called")
        mock_environ.get.return_value = None

        try:
            get_array(mock_module)
        except SystemExit:
            pass

        mock_module.fail_json.assert_called_once()
        msg = mock_module.fail_json.call_args[1]["msg"]
        assert "PUREFA_URL" in msg
        assert "PUREFA_API" in msg

    @patch("plugins.module_utils.purefa.HAS_PYPURECLIENT", False)
    def test_missing_pypureclient(self):
        """Test that missing pypureclient causes failure."""
        mock_module = Mock()
        mock_module.params = {
            "fa_url": "flasharray.example.com",
            "api_token": "test-token",
            "disable_warnings": False,
        }
        mock_module.fail_json.side_effect = SystemExit("fail_json called")

        try:
            get_array(mock_module)
        except SystemExit:
            pass

        mock_module.fail_json.assert_called_once()
        assert "py-pure-client" in mock_module.fail_json.call_args[1]["msg"]

    @patch("plugins.module_utils.purefa.flasharray.Client")
    @patch("plugins.module_utils.purefa.HAS_PYPURECLIENT", True)
    def test_authentication_failure(self, mock_client_class):
        """Test that authentication failure is handled."""
        mock_module = Mock()
        mock_module.params = {
            "fa_url": "flasharray.example.com",
            "api_token": "invalid-token",
            "disable_warnings": False,
        }
        mock_module.fail_json.side_effect = SystemExit("fail_json called")
        mock_client = Mock()
        mock_client.get_hardware.side_effect = Exception("auth failed")
        mock_client_class.return_value = mock_client

        try:
            get_array(mock_module)
        except SystemExit:
            pass

        mock_module.fail_json.assert_called_once()
        assert (
            "authentication failed" in mock_module.fail_json.call_args[1]["msg"].lower()
        )

    @patch("plugins.module_utils.purefa.flasharray.Client")
    @patch("plugins.module_utils.purefa.HAS_PYPURECLIENT", True)
    @patch("plugins.module_utils.purefa.environ")
    def test_with_id_token(self, mock_environ, mock_client_class):
        """Test get_array authenticates with a pre-signed id_token."""
        mock_environ.get.return_value = None
        mock_module = Mock()
        mock_module.params = {
            "fa_url": "flasharray.example.com",
            "api_token": None,
            "id_token": "eyJhbGciOiJSUzI1NiJ9.payload.sig",
            "disable_warnings": False,
        }
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        result = get_array(mock_module)

        call_kwargs = mock_client_class.call_args[1]
        assert call_kwargs["target"] == "flasharray.example.com"
        assert call_kwargs["id_token"] == "eyJhbGciOiJSUzI1NiJ9.payload.sig"
        assert "api_token" not in call_kwargs
        assert result == mock_client

    @patch("plugins.module_utils.purefa.flasharray.Client")
    @patch("plugins.module_utils.purefa.HAS_PYPURECLIENT", True)
    @patch("plugins.module_utils.purefa.environ")
    def test_with_private_key(self, mock_environ, mock_client_class):
        """Test get_array authenticates with the private-key app flow."""
        mock_environ.get.return_value = None
        mock_module = Mock()
        mock_module.params = {
            "fa_url": "flasharray.example.com",
            "api_token": None,
            "id_token": None,
            "private_key_file": "/run/secrets/aap.pem",
            "private_key_password": "s3cret",
            "username": "automation",
            "client_id": "cid-123",
            "key_id": "kid-456",
            "issuer": "AAP",
            "disable_warnings": False,
        }
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        result = get_array(mock_module)

        call_kwargs = mock_client_class.call_args[1]
        assert call_kwargs["target"] == "flasharray.example.com"
        assert call_kwargs["private_key_file"] == "/run/secrets/aap.pem"
        assert call_kwargs["private_key_password"] == "s3cret"
        assert call_kwargs["username"] == "automation"
        assert call_kwargs["client_id"] == "cid-123"
        assert call_kwargs["key_id"] == "kid-456"
        assert call_kwargs["issuer"] == "AAP"
        assert "api_token" not in call_kwargs
        assert result == mock_client

    @patch("plugins.module_utils.purefa.flasharray.Client")
    @patch("plugins.module_utils.purefa.HAS_PYPURECLIENT", True)
    @patch("plugins.module_utils.purefa.environ")
    def test_incomplete_private_key_set_fails(self, mock_environ, mock_client_class):
        """An incomplete private-key set (no username) must fail cleanly."""
        mock_module = Mock()
        mock_module.params = {
            "fa_url": "flasharray.example.com",
            "api_token": None,
            "id_token": None,
            "private_key_file": "/run/secrets/aap.pem",
            "private_key_password": None,
            "username": None,  # missing -> not a complete set
            "client_id": "cid-123",
            "key_id": "kid-456",
            "issuer": "AAP",
            "disable_warnings": False,
        }
        mock_module.fail_json.side_effect = SystemExit("fail_json called")
        mock_environ.get.return_value = None

        try:
            get_array(mock_module)
        except SystemExit:
            pass

        mock_module.fail_json.assert_called_once()
        mock_client_class.assert_not_called()
