#!/usr/bin/python
# -*- coding: utf-8 -*-

# (c) 2018, Simon Dodsley (simon@everpuredata.com)
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function

__metaclass__ = type

ANSIBLE_METADATA = {
    "metadata_version": "1.1",
    "status": ["preview"],
    "supported_by": "community",
}

DOCUMENTATION = r"""
---
module: purefa_token
version_added: '1.0.0'
short_description: Create or delete an API token for an existing admin user
description:
- Create or delete an API token for an existing admin user.
- Uses username/password to create/delete the API token.
- Logging in with a username and password creates the user's API token
  when none exists yet, so by the time the module inspects the user the
  token is always present. I(state=present) therefore returns the token
  and reports no change; it cannot tell a token created by this run from
  one that already existed.
- Use I(recreate=true) to force a new token. This always reports a change.
- I(state=absent) deletes the token and reports a change.
author:
- Everpure Ansible Team (@sdodsley) <pure-ansible-team@everpuredata.com>
options:
  state:
    description:
    - Create or delete API token
    type: str
    default: present
    choices: [ present, absent ]
  recreate:
    description:
    - Recreates the API token, overwriting the existing API token if present.
    - This is the only way to be sure of a new token and is always reported
      as a change.
    type: bool
    default: false
  username:
    description:
    - Username of the admin user to create API token for
    type: str
  password:
    description:
    - Password of the admin user to create API token for.
    type: str
  fa_url:
    description:
      - FlashArray management IPv4 address or Hostname.
    type: str
  timeout:
    description:
      - The duration of API token validity.
      - Valid values are weeks (w), days(d), hours(h), minutes(m) and seconds(s).
    type: str
  disable_warnings:
    description:
     - Disable insecure certificate warnings in debug logs
    type: bool
    default: false
    version_added: '1.31.0'
"""

EXAMPLES = r"""
- name: Create API token with no expiration
  purefa_token:
    username: pureuser
    password: secret
    state: present
    fa_url: 10.10.10.2
- name: Create API token with 23 days expiration
  purefa_token:
    username: pureuser
    password: secret
    state: present
    timeout: 23d
    fa_url: 10.10.10.2
- name: Delete API token
  purefa_token:
    username: pureuser
    password: secret
    state: absent
    fa_url: 10.10.10.2
"""

RETURN = r"""
purefa_token:
  description: API token for user
  returned: when I(state=present), whether or not the module reports a change
  type: str
  sample: e649f439-49be-3806-f774-a35cbbc4c2d2
"""

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.everpure.flasharray.plugins.module_utils.purefa import (
    get_array,
)
from ansible_collections.everpure.flasharray.plugins.module_utils.common import (
    convert_time_to_millisecs,
)
from ansible_collections.everpure.flasharray.plugins.module_utils.api_helpers import (
    check_response,
)
from ansible_collections.everpure.flasharray.plugins.module_utils.version import (
    LooseVersion,
)
from os import environ
import platform
from types import SimpleNamespace

VERSION = 1.5
USER_AGENT_BASE = "Ansible_token"
TIMEOUT_API_VERSION = "2.2"

HAS_URLLIB3 = True
try:
    import urllib3
except ImportError:
    HAS_URLLIB3 = False

HAS_DISTRO = True
try:
    import distro
except ImportError:
    HAS_DISTRO = False

HAS_PURESTORAGE = True
try:
    from purestorage import purestorage
except ImportError:
    HAS_PURESTORAGE = False


def get_session(module):
    """Return System Object or Fail"""
    if HAS_URLLIB3 and module.params["disable_warnings"]:
        urllib3.disable_warnings()
    if HAS_DISTRO:
        user_agent = "%(base)s %(class)s/%(version)s (%(platform)s)" % {
            "base": USER_AGENT_BASE,
            "class": __name__,
            "version": VERSION,
            "platform": distro.name(pretty=True),
        }
    else:
        user_agent = "%(base)s %(class)s/%(version)s (%(platform)s)" % {
            "base": USER_AGENT_BASE,
            "class": __name__,
            "version": VERSION,
            "platform": platform.platform(),
        }

    array_name = module.params["fa_url"]
    username = module.params["username"]
    password = module.params["password"]

    if HAS_PURESTORAGE:
        if array_name and username and password:
            system = purestorage.FlashArray(
                array_name, username=username, password=password, user_agent=user_agent
            )
        elif (
            environ.get("PUREFA_URL")
            and environ.get("PUREFA_USERNAME")
            and environ.get("PUREFA_PASSWORD")
        ):
            url = environ.get("PUREFA_URL")
            username = environ.get("PUREFA_USERNAME")
            password = environ.get("PUREFA_PASSWORD")
            system = purestorage.FlashArray(
                url, username=username, password=password, user_agent=user_agent
            )
        else:
            module.fail_json(
                msg="You must set PUREFA_URL and PUREFA_USERNAME, PUREFA_PASSWORD "
                "environment variables or the fa_url, username and password "
                "module arguments"
            )
        try:
            system.get()
        except Exception:
            module.fail_json(
                msg="Everpure FlashArray authentication failed. Check your credentials"
            )
    else:
        module.fail_json(msg="purestorage SDK is not installed.")
    return system


def token_exists(array, username):
    """Return True when the admin already has an API token.

    ``GET admin/<name>/apitoken`` (``array.get_api_token``) creates a token
    for a user who has none, so it cannot tell whether one exists.
    ``GET admin?api_token=true`` (``array.list_admins``) only reports them:
    ``api_token.created`` is null for a user without a token.

    The purestorage client logs in with ``POST auth/apitoken``, which itself
    creates the token of the user it logs in as, so for the session user this
    normally answers True: the module cannot detect a token it caused to be
    created. When the listing cannot be read or does not mention the user,
    the token is assumed to exist for the same reason - that assumption can
    only ever lead to a read or a delete, never to an implicit create.
    """
    try:
        admins = array.list_admins(api_token=True)
    except Exception:
        return True
    if isinstance(admins, dict):
        admins = [admins]
    info = next(
        (admin for admin in admins or [] if admin.get("name") == username), None
    )
    if info is None:
        return True
    token_info = info.get("api_token")
    if isinstance(token_info, dict):
        return bool(token_info.get("created"))
    if "created" in info:
        return bool(info.get("created"))
    return bool(token_info)


def token_from(result):
    """The api_token in a purestorage (REST 1) token response.

    ``get_api_token``, ``create_api_token`` and ``delete_api_token`` answer
    with a dict carrying ``api_token``; a one-item list is unwrapped so the
    shape of the answer cannot hide the token that was just created.
    """
    if isinstance(result, list):
        result = result[0] if result else None
    if isinstance(result, dict):
        return result.get("api_token")
    return None


def get_token_array(module, api_token):
    """Open the REST 2 client for the timeout path with ``api_token`` only.

    ``get_array`` reads every credential it finds in the module parameters,
    and this module's ``username``/``password`` must not take part in the
    REST 2 login: the array refuses them ("Unable to list user for API
    token") while a login with the user's own API token works, even for a
    readonly user. ``get_array`` is therefore given a view of the module
    that carries only the array address, the token just created or read
    back, and the warnings switch; ``fail_json`` is the module's own.
    """
    view = SimpleNamespace(
        params={
            "fa_url": module.params["fa_url"],
            "api_token": api_token,
            "disable_warnings": module.params["disable_warnings"],
        },
        fail_json=module.fail_json,
        warn=module.warn,
    )
    return get_array(view)


def main():
    argument_spec = dict(
        fa_url=dict(required=False),
        username=dict(type="str", required=False),
        password=dict(no_log=True, required=False),
        state=dict(type="str", default="present", choices=["absent", "present"]),
        recreate=dict(type="bool", default=False),
        timeout=dict(type="str"),
        disable_warnings=dict(type="bool", default=False),
    )

    module = AnsibleModule(argument_spec, supports_check_mode=False)
    array = get_session(module)
    changed = False

    if module.params["username"]:
        username = module.params["username"]
    else:
        username = environ.get("PUREFA_USERNAME")
    state = module.params["state"]
    recreate = module.params["recreate"]

    # Reading the token with get_api_token creates one when the user has
    # none, so find out whether a token exists first and only read it back
    # once it is known to exist. Note that get_session has already logged
    # in with username/password, which creates the token when the user had
    # none, so for state=present this normally reads back and reports no
    # change; recreate is the way to force a new token.
    has_token = token_exists(array, username)
    result = {}
    if state == "present" and not has_token:
        result = array.create_api_token(admin=username)
        changed = True
    elif state == "present" and recreate:
        array.delete_api_token(admin=username)
        result = array.create_api_token(admin=username)
        changed = True
    elif state == "present":
        result = array.get_api_token(admin=username)
    elif state == "absent" and has_token:
        result = array.delete_api_token(admin=username)
        changed = True

    api_token = token_from(result)

    if module.params["timeout"] and state == "present":
        if not api_token:
            module.fail_json(
                msg="Failed to read back the API token for {0}, so its "
                "lifetime cannot be set".format(username)
            )
        # Log in to REST 2 with the token just created or read back, and
        # with nothing else: username/password are refused there.
        array6 = get_token_array(module, api_token)
        # The lifetime is a REST 2 feature, so compare against the REST 2
        # version, not the REST 1 list the purestorage client reports.
        if LooseVersion(TIMEOUT_API_VERSION) <= LooseVersion(array6.get_rest_version()):
            ttl = convert_time_to_millisecs(module.params["timeout"])
            if ttl != 0:
                changed = True
                array6.delete_admins_api_tokens(names=[username])
                res = array6.post_admins_api_tokens(names=[username], timeout=ttl)
                check_response(res, module, "Failed to set token lifetime")
                api_token = list(res.items)[0].api_token.token
        else:
            module.warn(
                "timeout ignored: token lifetimes need REST {0} or higher".format(
                    TIMEOUT_API_VERSION
                )
            )
    module.exit_json(changed=changed, purefa_token=api_token)


if __name__ == "__main__":
    main()
