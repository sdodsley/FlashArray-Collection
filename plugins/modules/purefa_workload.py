#!/usr/bin/python
# -*- coding: utf-8 -*-

# (c) 2025, Simon Dodsley (simon@everpuredata.com)
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
module: purefa_workload
version_added: '1.33.0'
short_description: Manage Fusion Fleet Workloads
description:
- Apply/Rename/Delete Fusion fleet workloads
author:
- Everpure Ansible Team (@sdodsley) <pure-ansible-team@everpuredata.com>
options:
  context:
    description:
    - Name of the fleet member on which to perform the workload operation, or
      the name of the fleet itself.
    - There is no default. Either this or I(placement) must be given, except on
      a create with I(recommendation), where Fusion chooses the member. 
    - A workload is identified by its name B(and) its member. The same name on
      two fleet members is two separate workloads, so naming a different member
      creates a second one rather than moving the first.
    - Naming the B(fleet) instead means "the workload with this name, wherever
      it is in the fleet". It is resolved to the member holding the workload, so
      a task is idempotent without having to know which member that is. If two
      or more members hold the same name it is ambiguous and the task fails.
    - The fleet says where to look, not where to create. If no such workload
      exists anywhere, a create fails asking for a member, unless
      I(recommendation) is set.
    type: str
    default: ""
  host:
    type: str
    description:
    - Host to connect to every volume in the workload after provisioning.
    - With I(state=absent) the host is disconnected from the workload's volumes
      instead of the workload being deleted.
    - Only the workload's own volumes are affected. Volumes the host is connected
      to outside this workload are never changed.
    default: ""
  name:
    description:
    - Name of the workload.
    type: str
    required: true
  state:
    description:
    - Define whether to create or delete a fleet workload.
    - Using the expand option will add volume(s) to the workload.
    - If absent is specified together with a host, rather than deleting the workload, the host will be disconnected from the workload
    default: present
    choices: [ absent, present, expand]
    type: str
  preset:
    description:
    - Name of an existing workload preset to build the workload from.
    - Required to create a workload, and to expand one
    - Presets are fleet objects, named C(<fleet>:<preset>) by the API. Give the
      bare name; the fleet is prefixed automatically.
    type: str
  rename:
    description:
    - new name for a workload
    type: str
  eradicate:
    description:
    - whether to eradicate a workload
    type: bool
    default: false
  placement:
    description:
    - Name of the fleet member on which the workload will be deployed.
    - A workload is deployed on its I(context), and the API has no separate
      placement, so the two mean the same thing and this accepts everything
      I(context) does, including the fleet's own name. Setting both to different
      members fails; set one, or set both to the same value.
    - Ignored when I(recommendation) is true, as the recommended target
      replaces it.
    type: str
  recommendation:
    description:
    - whether to use the Fusion placement recommendation based
      on the workload preset definitions.
    - This will use the first recommended placement if more than
      one is available
    default: false
    type: bool
  parameters:
    description:
    - Parameter values to apply when creating a workload from the preset.
    - Parameters are only applied on the create path and are not applied
      when recovering an existing destroyed workload.
    type: list
    elements: dict
    suboptions:
      name:
        description:
        - Name of the preset parameter to set.
        type: str
        required: true
      value:
        description:
        - Value for the preset parameter.
        - Exactly one of C(string), C(integer), C(boolean), or
          C(resource_reference) must be provided.
        type: dict
        required: true
        suboptions:
          string:
            description:
            - String parameter value.
            type: str
          integer:
            description:
            - Integer parameter value.
            type: int
          boolean:
            description:
            - Boolean parameter value.
            type: bool
          resource_reference:
            description:
            - Reference to another resource.
            type: dict
            suboptions:
              id:
                description:
                - ID of the referenced resource.
                type: str
              name:
                description:
                - Name of the referenced resource.
                type: str
              resource_type:
                description:
                - Optional resource type for the reference.
                type: str
  volume_count:
    description:
    - Number of additional volumes to add to an existing workload
    - Only used with I(state=expand), where it is required.
    - Must be a positive integer. Zero is rejected.
    type: int
  volume_configuration:
    description:
    - Name of the volume configuration to use for adding volumes
      to a workload
    type: str
  wait:
    description:
    - Whether to wait for the array to finish provisioning before returning.
    - Cannot be disabled when I(host) is set. A host can only be connected to
      every volume in a workload once the volume set has settled.
    type: bool
    default: true
    version_added: '1.45.0'
  wait_timeout:
    description:
    - Maximum number of seconds to wait for a single array operation when
      I(wait) is true. The task fails if that operation has not finished within
      this time.
    - This bounds each operation individually rather than the task as a whole, so
      a task that waits for more than one can take a multiple of it. Creating a
      workload with I(recommendation) and a I(host) waits three times - for the
      placement to be calculated, for the workload to become ready, and for the
      host connections - and so can take up to three times this value.
    type: int
    default: 300
    version_added: '1.45.0'
extends_documentation_fragment:
- everpure.flasharray.everpure.fa
"""

EXAMPLES = r"""
- name: Create a workload using an existing preset on a specific placement target and connect to host myhost
  everpure.flasharray.purefa_workload:
    name: foo
    preset: bar
    host: myhost
    placement: arrayB
    fa_url: 10.10.10.2
    api_token: e31060a7-21fc-e277-6240-25983c6c4592

- name: Create a workload using an existing preset using the recommended target and connect to host myhost
  everpure.flasharray.purefa_workload:
    name: foo
    preset: bar
    host: myhost
    recommendation: true
    fa_url: 10.10.10.2
    api_token: e31060a7-21fc-e277-6240-25983c6c4592

- name: Create a workload on the recommended target, waiting for it to be ready
  everpure.flasharray.purefa_workload:
    name: foo
    preset: bar
    recommendation: true
    wait: true
    wait_timeout: 600
    fa_url: 10.10.10.2
    api_token: e31060a7-21fc-e277-6240-25983c6c4592
  register: new_workload

- name: Report the fleet member Fusion placed the workload on
  ansible.builtin.debug:
    msg: "{{ new_workload.workload.name }} placed on {{ new_workload.workload.context }}"

- name: Report the volumes the array provisioned
  ansible.builtin.debug:
    msg: "{{ new_workload.workload.volumes }}"

- name: Create a workload using preset parameters
  everpure.flasharray.purefa_workload:
    name: foo
    preset: bar
    context: arr1
    parameters:
      - name: replication_target
        value:
          resource_reference:
            name: arr2
    fa_url: 10.10.10.2
    api_token: e31060a7-21fc-e277-6240-25983c6c4592

- name: Add volumes to workload foo based on volume configuration fin and connect to host myhost
  everpure.flasharray.purefa_workload:
    name: foo
    preset: bar
    volume_configuration: fin
    volume_count: 3
    host: myhost
    state: expand
    fa_url: 10.10.10.2
    api_token: e31060a7-21fc-e277-6240-25983c6c4592

- name: Rename an existing workload
  everpure.flasharray.purefa_workload:
    name: foo
    rename: bar
    context: arr1
    fa_url: 10.10.10.2
    api_token: e31060a7-21fc-e277-6240-25983c6c4592

- name: Disconnect an existing workload from host
  everpure.flasharray.purefa_workload:
    name: foo
    host: myhost
    state: absent
    fa_url: 10.10.10.2
    api_token: e31060a7-21fc-e277-6240-25983c6c4592

- name: Delete an existing workload
  everpure.flasharray.purefa_workload:
    name: foo
    state: absent
    fa_url: 10.10.10.2
    api_token: e31060a7-21fc-e277-6240-25983c6c4592

- name: Eradicate an existing workload
  everpure.flasharray.purefa_workload:
    name: foo
    state: absent
    eradicate: true
    fa_url: 10.10.10.2
    api_token: e31060a7-21fc-e277-6240-25983c6c4592

- name: Recover a deleted workload
  everpure.flasharray.purefa_workload:
    name: foo
    state: present
    fa_url: 10.10.10.2
    api_token: e31060a7-21fc-e277-6240-25983c6c4592

- name: Reconnect an existing workload to a host
  everpure.flasharray.purefa_workload:
    name: foo
    host: myhost
    fa_url: 10.10.10.2
    api_token: e31060a7-21fc-e277-6240-25983c6c4592
"""

RETURN = r"""
workload:
    description: Describes what a task did to the workload.
        Returned on every action that leaves a workload in place, and empty only
        when no workload remains to describe, as after an eradication. More detail
        is available from array by M(everpure.flasharray.purefa_info) rather than
        repeated here.
    type: dict
    returned: success
    contains:
        name:
            description: Name of the workload. This is the new name after a
                rename.
            type: str
            sample: 'foo'
        context:
            description: Name of the fleet member the workload is placed on.
                When I(recommendation) is used this is the target chosen by
                Fusion. Together with I(name) it identifies the workload - 
                the same name on another fleet member is a different workload.
            type: str
            sample: 'arrayB'
        status:
            description: Status of the workload, as reported by the array.
                Normally one of C(creating), C(ready), C(destroying),
                C(destroyed), C(eradicating) or C(recovering). Passed through
                unmodified, so a future Purity release may report a value not in
                this list, and null when the array reports no status at all. Use
                I(completed) to test for completion rather than comparing this
                field - a null or unrecognised status counts as still in flight
                and raises a warning.
            type: str
            sample: 'ready'
        completed:
            description: Whether the array has finished the operation in flight
                for this workload. A destroyed workload is complete but still pending
                eradication - see I(time_remaining).
            type: bool
            sample: false
        destroyed:
            description: Whether deletion of the workload has been requested.
                This says nothing about whether the deletion has finished - see
                I(completed).
            type: bool
            sample: false
        time_remaining:
            description: Milliseconds until a destroyed workload is eradicated.
                Null unless I(destroyed) is true, and null in check mode.
            type: int
            sample: 86400000
        volumes:
            description: Names of the volumes belonging to this workload, as they
                stand after the action. In check mode a create reports an empty
                list and an expand reports only the volumes that already exist.
            type: list
            elements: str
            sample: ['foo-vol1', 'foo-vol2']
"""

HAS_PURESTORAGE = True
try:
    from pypureclient.flasharray import (
        WorkloadConfigurationReference,
        WorkloadParameter,
        WorkloadParameterValue,
        WorkloadParameterValueResourceReference,
        WorkloadPatch,
        WorkloadPost,
        WorkloadPlacementRecommendation,
        VolumePost,
        ConnectionPost,
    )
except ImportError:
    HAS_PURESTORAGE = False

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.everpure.flasharray.plugins.module_utils.purefa import (
    get_array,
    purefa_argument_spec,
)
from ansible_collections.everpure.flasharray.plugins.module_utils.version import (
    LooseVersion,
)
from ansible_collections.everpure.flasharray.plugins.module_utils.api_helpers import (
    check_response,
    get_local_array_name,
    wait_for,
)

VERSION = 1.5
USER_AGENT_BASE = "Ansible"
MIN_REQUIRED_API_VERSION = "2.40"
SUPPORTED_PARAMETER_VALUE_TYPES = (
    "string",
    "integer",
    "boolean",
    "resource_reference",
)

# The API reports exactly these six statuses. Only two are terminal. There is NO
# failure state, so a broken provision is indistinguishable from a slow one and
# is caught by wait_timeout rather than reported as a failure.
TERMINAL_STATUSES = frozenset({"ready", "destroyed"})
TRANSIENT_STATUSES = frozenset({"creating", "destroying", "eradicating", "recovering"})

# A read by name reports a missing object as an error rather than as an empty
# result, so absence has to be recognised from the error itself. These two statuses
# are the only candidates - every other status, 5xx above all, is surfaced rather
# than quietly reported as absence.
NOT_FOUND_STATUSES = frozenset({400, 404})

# ...but the status alone will not do. The array answers with 400 for several
# different mistakes, only one of which means the workload is not there.
# so additionally we match on a lowercase substring so wording and punctuation
# can drift without breaking.
NOT_FOUND_TEXT = "does not exist"


def _parameter_fail(module, parameter_name, message):
    module.fail_json(msg=f"Invalid workload parameter '{parameter_name}': {message}")


def _coerce_parameter_list(parameter_items):
    if parameter_items is None:
        return []
    try:
        return list(parameter_items)
    except TypeError:
        return []


def _supplied_option_keys(value_definition, allowed_keys):
    return [
        key
        for key in allowed_keys
        if key in value_definition and value_definition[key] is not None
    ]


def _build_resource_reference(module, parameter_name, resource_reference):
    if not isinstance(resource_reference, dict):
        _parameter_fail(
            module,
            parameter_name,
            "resource_reference must be a dictionary",
        )
    unknown_keys = set(resource_reference) - {"id", "name", "resource_type"}
    if unknown_keys:
        _parameter_fail(
            module,
            parameter_name,
            "resource_reference contains unsupported keys: {0}".format(
                ", ".join(sorted(unknown_keys))
            ),
        )
    identifier_keys = _supplied_option_keys(resource_reference, ("id", "name"))
    if len(identifier_keys) != 1:
        _parameter_fail(
            module,
            parameter_name,
            "resource_reference must include exactly one of id or name",
        )
    return WorkloadParameterValueResourceReference(
        **{
            key: resource_reference[key]
            for key in resource_reference
            if resource_reference[key] is not None
        }
    )


def _build_parameter_value(module, parameter_name, value_definition):
    if not isinstance(value_definition, dict):
        _parameter_fail(module, parameter_name, "value must be a dictionary")
    unknown_keys = set(value_definition) - set(SUPPORTED_PARAMETER_VALUE_TYPES)
    if unknown_keys:
        _parameter_fail(
            module,
            parameter_name,
            "value contains unsupported keys: {0}".format(
                ", ".join(sorted(unknown_keys))
            ),
        )
    supplied_value_types = _supplied_option_keys(
        value_definition, SUPPORTED_PARAMETER_VALUE_TYPES
    )
    if len(supplied_value_types) != 1:
        _parameter_fail(
            module,
            parameter_name,
            "value must include exactly one of {0}".format(
                ", ".join(SUPPORTED_PARAMETER_VALUE_TYPES)
            ),
        )

    value_type = supplied_value_types[0]
    normalized_value = value_definition[value_type]
    if value_type == "string":
        if not isinstance(normalized_value, str):
            _parameter_fail(module, parameter_name, "string value must be a string")
    elif value_type == "integer":
        if isinstance(normalized_value, bool) or not isinstance(normalized_value, int):
            _parameter_fail(module, parameter_name, "integer value must be an integer")
    elif value_type == "boolean":
        if not isinstance(normalized_value, bool):
            _parameter_fail(
                module, parameter_name, "boolean value must be true or false"
            )
    elif value_type == "resource_reference":
        normalized_value = _build_resource_reference(
            module, parameter_name, normalized_value
        )

    return value_type, WorkloadParameterValue(**{value_type: normalized_value})


def _build_workload_parameters(module, preset_config):
    raw_parameters = module.params.get("parameters") or []
    if not raw_parameters:
        return None

    preset_parameters = {}
    for preset_parameter in _coerce_parameter_list(
        getattr(preset_config, "parameters", [])
    ):
        if getattr(preset_parameter, "name", None):
            preset_parameters[preset_parameter.name] = preset_parameter

    normalized_parameters = []
    seen_parameters = set()
    for raw_parameter in raw_parameters:
        if not isinstance(raw_parameter, dict):
            module.fail_json(msg="Each workload parameter must be a dictionary")
        parameter_name = raw_parameter.get("name")
        if not parameter_name:
            module.fail_json(msg="Each workload parameter requires a name")
        if parameter_name in seen_parameters:
            _parameter_fail(module, parameter_name, "parameter names must be unique")
        if parameter_name not in preset_parameters:
            _parameter_fail(
                module,
                parameter_name,
                "parameter is not defined by preset {0}".format(
                    module.params["preset"]
                ),
            )
        if "value" not in raw_parameter:
            _parameter_fail(module, parameter_name, "parameter requires a value")

        value_type, parameter_value = _build_parameter_value(
            module, parameter_name, raw_parameter["value"]
        )
        preset_type = getattr(preset_parameters[parameter_name], "type", None)
        if preset_type and preset_type != value_type:
            _parameter_fail(
                module,
                parameter_name,
                "expected type {0}, got {1}".format(preset_type, value_type),
            )

        normalized_parameters.append(
            WorkloadParameter(name=parameter_name, value=parameter_value)
        )
        seen_parameters.add(parameter_name)
    return normalized_parameters


def _status_completed(module, name, status):
    """True when the array has no operation in flight for a workload

    Anything unrecognised counts as in-flight, so a status added by a future
    Purity release can never be mistaken for success.
    """
    if status in TERMINAL_STATUSES:
        return True
    if status not in TRANSIENT_STATUSES:
        module.warn(
            f"Workload {name} reported unrecognised status {status!r}. "
            f"Treating as in progress. This collection may need updating."
        )
    return False


def _workload_completed(module, workload):
    """_status_completed() for an already-read Workload"""
    return _status_completed(
        module,
        getattr(workload, "name", None),
        getattr(workload, "status", None),
    )


# Check mode has two rules in this module. An action function decides what to
# report, since only it knows what its own action would have produced. Every other
# function guards its own writes, so that a write cannot escape by being called
# from somewhere new. Waiting is handled once, in wait_for().


def _workload_volume_names(module, array, name, context):
    """Sorted names of the volumes belonging to a workload"""
    res = array.get_volumes(
        filter="workload.name='{0}'".format(name),
        context_names=[context],
    )
    check_response(res, module, f"Failed to get volumes for workload {name}")
    return sorted(volume.name for volume in list(res.items))


def _connected_volume_names(module, array, context, volume_names, host):
    """Which of the given volumes the host can currently see

    Scoped to volume_names, so connections the host has outside this workload are
    never even read, let alone changed. get_connections rejects multiple names on
    two objects at once, so the host is the single name and the volumes the many.
    """
    if not volume_names:
        return set()
    res = array.get_connections(
        host_names=[host],
        volume_names=volume_names,
        context_names=[context],
    )
    check_response(res, module, f"Failed to get connections for host {host}")
    # The volume, and the name on it, are both optional, so a connection naming no
    # volume is dropped rather than raising
    names = {
        getattr(getattr(connection, "volume", None), "name", None)
        for connection in list(res.items)
    }
    names.discard(None)
    return names


def _facts(
    module,
    context,
    name=None,
    status=None,
    volumes=None,
    destroyed=False,
    time_remaining=None,
):
    """The workload contract

    What the task did, rather than everything the array knows about the workload.
    A workload's own properties - the preset it came from, when it was created, the
    array's free-form status text - are what purefa_info reports, and repeating
    them here would only invite the two to disagree.

    The defaults are what a workload that does not exist yet can honestly report,
    so a predicted create only has to name what it knows.
    """
    return {
        "name": name,
        "context": context,
        "status": status,
        # Derived here, so it can never disagree with the status beside it
        "completed": _status_completed(module, name, status),
        "destroyed": destroyed,
        "time_remaining": time_remaining,
        "volumes": volumes or [],
    }


def _workload_facts(module, array, workload, context, volume_names=None, **changes):
    """Describe a workload the array reported

    volume_names is passed in by callers that have already read them, so a path
    doing host work does not read the same list twice.

    changes replaces fields the caller knows differ from what the array said,
    which is how check mode reports a state it has not applied. They land on the
    values _facts() is given rather than the dict it returns, so that everything
    _facts() derives is derived from the changed values.
    """
    if not workload:
        return {}
    # In the SDK every field on a workload is optional, if we try to read one that
    # is not defined it will raise, so we use getattr()
    workload_context = getattr(workload, "context", None)

    name = getattr(workload, "name", None) or module.params["name"]
    if volume_names is None:
        # Read under the name the workload still answers to, which for a rename is
        # the old one
        volume_names = _workload_volume_names(module, array, name, context)
    values = {
        "name": name,
        "context": getattr(workload_context, "name", None) or context,
        "status": getattr(workload, "status", None),
        "destroyed": getattr(workload, "destroyed", False),
        "time_remaining": getattr(workload, "time_remaining", None),
    }
    return _facts(module, volumes=volume_names, **{**values, **changes})


def _is_absent(response):
    """A response the array explained as the workload not being there

    Matching on message text is unpleasant, and was avoided for as long as the
    status code alone could carry it. It cannot: the array answers 400 for several
    different mistakes, and only one of them means absence. The match is
    deliberately loose - lowercase substring, across every error rather than the
    first - and if it ever stops matching, a missing workload surfaces as a task
    failure quoting the array. That is the safe direction to be wrong in: loud
    rather than silent.

    A response carrying no errors at all is not absence either, and falls through
    to be surfaced rather than assumed benign.
    """
    if getattr(response, "status_code", None) not in NOT_FOUND_STATUSES:
        return False
    return any(
        NOT_FOUND_TEXT in (getattr(error, "message", "") or "").lower()
        for error in getattr(response, "errors", None) or []
    )


def _read_workload(module, array, context):
    """Read the workload in the given context, or None if it does not exist

    A workload that is not there is reported as an error rather than as an empty
    result - with or without allow_errors - so absence is recognised by
    _is_absent(), which reads the array's own explanation. A server error can
    therefore never be mistaken for a missing workload and reported as success by
    a caller waiting for one to go away.

    allow_errors is required whenever the context is a fleet member other than the
    local array being addressed.
    """
    res = array.get_workloads(
        names=[module.params["name"]],
        context_names=[context],
        allow_errors=True,
    )
    if res.status_code == 200:
        return list(res.items)[0]
    if _is_absent(res):
        return None
    check_response(res, module, f"Failed to read workload {module.params['name']}")


def _find_across_fleet(module, array, fleet):
    """Every fleet member reporting a workload of this name, as {member: workload}

    Names are not unique across a fleet: the same name on two members is two
    separate workloads, and both are returned.

    "<fleet>.arrays" is a context that spans every member, and answers this in one
    call. The bare fleet name does not - the array rejects it with "Cannot specify
    context that is a fleet" - and the form used here is not in the SDK's
    documentation, so a member-by-member sweep backs it up. That fallback is not
    only for old releases: a rejection of the fleet-wide query is indistinguishable
    from the workload being absent, and reading "unsupported" as "not there" would
    let a create make a duplicate.
    """
    res = array.get_workloads(
        names=[module.params["name"]],
        context_names=[f"{fleet}.arrays"],
        allow_errors=True,
    )
    if res.status_code == 200:
        return {
            member: workload
            for workload in list(res.items)
            for member in [getattr(getattr(workload, "context", None), "name", None)]
            if member
        }

    found = {}
    for member in _fleet_members(module, array):
        workload = _read_workload(module, array, member)
        if workload is not None:
            found[member] = workload
    return found


def _warn_about_copies_elsewhere(module, array, fleet):
    """Say when a name being removed here also exists on other fleet members

    Reporting only. The module destroys exactly the (name, context) it was given,
    and this must never widen that: eradication cannot be undone, so a fleet-wide
    search informs the operator rather than choosing a target for them.
    """
    others = sorted(
        member
        for member in _find_across_fleet(module, array, fleet)
        if member != module.params["context"]
    )
    if others:
        module.warn(
            f"A workload named {module.params['name']} also exists on "
            f"{', '.join(others)}. Only the one on {module.params['context']} is "
            "affected here - a name is unique per fleet member, not across the "
            "fleet."
        )


def _status_detail(workload):
    """Render the array's own diagnostics for a timeout message"""
    if not workload:
        return ""
    return ", ".join(getattr(workload, "status_details", None) or [])


def _wait_for_status(module, array, context, status):
    """Wait until the workload has settled into the given status

    The context is passed in rather than read from module.params, so that a
    recommendation-resolved placement stays fixed for the life of the poll.
    """
    return wait_for(
        module,
        probe=lambda: _read_workload(module, array, context),
        is_done=lambda workload: (
            workload is not None
            and _workload_completed(module, workload)
            and workload.status == status
        ),
        timeout=module.params["wait_timeout"],
        description=f"workload {module.params['name']} to become {status}",
        detail=_status_detail,
    )


def _wait_for_absent(module, array, context):
    """Wait until the workload has been fully eradicated

    Done here is the absence of a status rather than a value of one, so this is
    the one path that cannot use _workload_completed().
    """
    return wait_for(
        module,
        probe=lambda: _read_workload(module, array, context),
        is_done=lambda workload: workload is None,
        timeout=module.params["wait_timeout"],
        description=f"workload {module.params['name']} to be eradicated",
        detail=_status_detail,
    )


def _wait_for_connections(module, array, name, context, connected):
    """Wait until the host sees all of the workload's volumes, or none of them

    connected=True after a connect, False after a disconnect. Both the volume
    list and the connections are re-read each iteration, so a volume that
    appears late is caught rather than missed, and the poll never looks at
    connections outside this workload.
    """
    host = module.params["host"]

    def probe():
        volume_names = _workload_volume_names(module, array, name, context)
        return {
            "volumes": volume_names,
            "seen": _connected_volume_names(module, array, context, volume_names, host),
        }

    def is_done(state):
        if connected:
            return set(state["volumes"]) == state["seen"]
        # Done is the host seeing none of *these* volumes, not the host having
        # no connections at all
        return not state["seen"]

    def detail(state):
        if connected:
            outstanding = sorted(set(state["volumes"]) - state["seen"])
        else:
            outstanding = sorted(state["seen"])
        return ", ".join(outstanding)

    return wait_for(
        module,
        probe=probe,
        is_done=is_done,
        timeout=module.params["wait_timeout"],
        description=(
            f"host {host} to be {'connected to' if connected else 'disconnected from'} "
            f"the volumes of workload {name}"
        ),
        detail=detail,
    )


def _wait_for_recommendation(module, array, context, calculation):
    """Wait for Fusion to finish calculating a placement recommendation

    Unlike a workload, this endpoint reports a real failure state, so this is the
    one waiter with something for wait_for's is_failed hook. Runs under check
    mode: it reads a calculation and changes nothing on the array.
    """

    def probe():
        res = array.get_workloads_placement_recommendations(
            names=[calculation], context_names=[context]
        )
        check_response(res, module, "Failed to read placement recommendation")
        return list(res.items)[0]

    return wait_for(
        module,
        probe=probe,
        # status is optional, and a calculation reporting none is still in flight as
        # far as this is concerned, so both tests read it with a default
        is_done=lambda result: getattr(result, "status", None) == "completed",
        is_failed=lambda result: (
            f"Fusion could not find a placement for preset "
            f"{module.params['preset']}"
            if getattr(result, "status", None) == "failed"
            else None
        ),
        timeout=module.params["wait_timeout"],
        description=(
            f"a placement recommendation for preset {module.params['preset']}"
        ),
        # Polled in check mode too: a calculation changes nothing on the array,
        # and it is what lets a check run report the target Fusion would choose
        skip_in_check_mode=False,
    )


def _wait_for_volumes(module, array, context, volume_names, workload):
    """Wait until new volumes exist and the workload has settled back to ready

    Volumes carry no lifecycle status of their own, so the volume half of this
    can only test existence, and the POST that created them has already
    returned. The workload half is what covers the configuration the preset
    derives from those volumes.

    Falls back to the workload it was given when there was nothing to wait for,
    so callers never have to handle an absent result.
    """

    def probe():
        res = array.get_volumes(names=volume_names, context_names=[context])
        # A name that does not resolve yet is an error rather than an empty
        # result, and here means "not created yet" rather than a real failure
        found = (
            {volume.name for volume in list(res.items)}
            if res.status_code == 200
            else set()
        )
        return {"workload": _read_workload(module, array, context), "volumes": found}

    def is_done(state):
        workload = state["workload"]
        return (
            not set(volume_names) - state["volumes"]
            and workload is not None
            and _workload_completed(module, workload)
            and workload.status == "ready"
        )

    state = wait_for(
        module,
        probe=probe,
        is_done=is_done,
        timeout=module.params["wait_timeout"],
        description=(
            f"volumes added to workload {module.params['name']} to become ready"
        ),
        detail=lambda state: _status_detail(state["workload"]),
    )
    return state["workload"] if state else workload


def _create_volume(module, array):
    """Create an actual volume in a workload

    Returns the array-generated volume name, so that a later wait can target
    exactly the volumes this task created, or None in check mode where no volume
    was created and so none can be named.

    The check-mode guard below is the second of two: expand_workload does not call
    this at all in check mode. It is kept rather than removed as unreachable so
    that no future caller can create a volume by forgetting to guard.
    """
    if module.check_mode:
        return None
    res = array.post_volumes(
        volume=VolumePost(
            workload=WorkloadConfigurationReference(
                name=module.params["name"],
                configuration=module.params["volume_configuration"],
            ),
        ),
        context_names=[module.params["context"]],
    )
    check_response(res, module, "Workload volume creation failed")
    return list(res.items)[0].name


def _connect_host(module, array, name, context, volume_names):
    """Connect the host to any of the workload's volumes it cannot already see

    Additive only, and only within this workload: the host keeps every connection
    it has elsewhere. post_connections has no allow_errors, so reposting an
    existing connection is an error rather than a no-op, which is why only the
    difference is sent.

    Returns whether a connection was missing.
    """
    host = module.params["host"]
    missing = sorted(
        set(volume_names)
        - _connected_volume_names(module, array, context, volume_names, host)
    )
    if missing and not module.check_mode:
        res = array.post_connections(
            host_names=[host],
            volume_names=missing,
            context_names=[context],
            connection=ConnectionPost(),
        )
        check_response(res, module, f"Failed to connect volumes to host {host}")
        if module.params["wait"]:
            _wait_for_connections(module, array, name, context, connected=True)
    return bool(missing)


def _disconnect_host(module, array, name, context, volume_names):
    """Disconnect the host from the workload's volumes, and only those

    Subtractive only, and only within this workload. volume_names is always
    passed, so connections the host has elsewhere are left alone.

    Returns whether there was a connection to remove.
    """
    host = module.params["host"]
    attached = sorted(
        _connected_volume_names(module, array, context, volume_names, host)
        & set(volume_names)
    )
    if attached and not module.check_mode:
        res = array.delete_connections(
            host_names=[host],
            volume_names=attached,
            context_names=[context],
        )
        check_response(res, module, f"Failed to disconnect volumes from host {host}")
        if module.params["wait"]:
            _wait_for_connections(module, array, name, context, connected=False)
    return bool(attached)


def create_workload(module, array, fleet, preset_config):
    """Create fleet workload using existing preset"""
    changed = True
    workload_parameters = _build_workload_parameters(module, preset_config)
    # This is only reached when the workload was not found on the named context, so
    # anything the sweep turns up is a copy of the name on some other member
    elsewhere = _find_across_fleet(module, array, fleet)
    if module.params["recommendation"]:
        if len(elsewhere) > 1:
            # Nothing in the task says which of them is meant, and picking one
            # would be arbitrary and wrong about half the time
            module.fail_json(
                msg=f"Workload {module.params['name']} already exists on more than "
                f"one fleet member: {', '.join(sorted(elsewhere))}. recommendation "
                "cannot choose between them. Set context to the one you mean."
            )
        if elsewhere:
            # Fusion chose the placement last time and may choose differently now,
            # so a second run must find what the first one made rather than ask for
            # another placement
            member, existing = next(iter(elsewhere.items()))
            module.exit_json(
                changed=False,
                workload=_workload_facts(module, array, existing, member),
            )
            # exit_json ends the module by raising, but this is the one place it is
            # not the last statement - the return says so rather than leaving the
            # rest of the function looking reachable
            return
        # Asking Fusion where to put a workload is the one call with no member for
        # its context to name: it is the route the question travels, not the answer,
        # which is why falling back to the array addressed is safe here and is not a
        # default placement - Fusion's choice replaces it a few lines down. Without
        # the fallback a task that named neither context nor placement sends an empty
        # context, which the array rejects with an internal error.
        recommendation_context = module.params["context"] or get_local_array_name(
            array, module
        )
        # Start the workload calculation for the preset being used
        res = array.post_workloads_placement_recommendations(
            inputs=WorkloadPlacementRecommendation(parameters=workload_parameters),
            preset_names=[module.params["preset"]],
            context_names=[recommendation_context],
        )
        check_response(res, module, "Recommendation calculation failure")
        workload_calc = getattr(list(res.items)[0], "name", None)
        # A calculation, not a change, so this runs in check mode too - it is what
        # lets a check-mode run report the target Fusion would have chosen
        result = _wait_for_recommendation(
            module, array, recommendation_context, workload_calc
        )
        # Replace any defined placement with the result from the recommendation.
        # Every link on the way to the target is optional and every list can come
        # back empty, so the walk is guarded as a whole and a gap is reported as the
        # missing recommendation it is, rather than as an error further downstream.
        try:
            target = result.results[0].placements[0].targets[0].name
        except (AttributeError, IndexError):
            target = None
        if not target:
            module.fail_json(
                msg="Fusion reported a completed placement recommendation for preset "
                f"{module.params['preset']} but named no target to deploy on."
            )
        module.params["placement"] = target
        module.params["context"] = module.params["placement"]
    elif elsewhere:
        # The user named a context, so this is a different workload that happens to
        # share a name - which the array permits. Reported rather than refused.
        module.warn(
            f"A workload named {module.params['name']} already exists on "
            f"{', '.join(sorted(elsewhere))}. Creating on "
            f"{module.params['context']} makes a separate workload: a name is "
            "unique per fleet member, not across the fleet."
        )
    context = module.params["context"]
    if module.check_mode:
        # Nothing exists to read, so everything reported is predicted. The context
        # is the resolved one, which for a recommendation is Fusion's choice. Only
        # what a create can know is named here; volumes are left to _facts() to
        # default, because the array generates their names.
        workload_facts = _facts(
            module,
            name=module.params["name"],
            context=context,
            status="ready" if module.params["wait"] else "creating",
        )
    else:
        res = array.post_workloads(
            names=[module.params["name"]],
            preset_names=[module.params["preset"]],
            workload=WorkloadPost(parameters=workload_parameters),
            context_names=[context],
        )
        check_response(
            res, module, f"Failed to create workload {module.params['name']}"
        )
        workload = list(res.items)[0]
        if module.params["wait"]:
            workload = _wait_for_status(module, array, context, "ready")
        # Read once, after the wait, so the host sees the settled volume set and
        # the facts report the same list the connect worked from
        volume_names = _workload_volume_names(module, array, workload.name, context)
        if module.params["host"] != "":
            _connect_host(module, array, workload.name, context, volume_names)
        workload_facts = _workload_facts(module, array, workload, context, volume_names)

    module.exit_json(changed=changed, workload=workload_facts)


def expand_workload(module, array, fleet, volume_configs, workload):
    """Add new volumes to workload"""
    changed = False
    matched = False
    volume_names = []
    for vol_config in volume_configs:
        if vol_config.name == module.params["volume_configuration"]:
            matched = True
            for _volume in range(module.params["volume_count"]):
                changed = True
                # Creating storage is the costliest thing this module does, so it
                # is guarded here as well as inside _create_volume
                if module.check_mode:
                    continue
                volume_names.append(_create_volume(module, array))
    if not matched:
        module.fail_json(
            msg="Volume Configuration {0} does not exist for preset {1}.".format(
                module.params["volume_configuration"], module.params["preset"]
            )
        )
    context = module.params["context"]
    if module.params["wait"]:
        # Re-read rather than reuse main()'s workload, which predates the volumes
        workload = _wait_for_volumes(module, array, context, volume_names, workload)
    # The full set, not just the volumes this task added - the host must end up
    # able to see all of them, and the facts report the grown set
    all_volume_names = _workload_volume_names(module, array, workload.name, context)
    if module.params["host"] != "":
        _connect_host(module, array, workload.name, context, all_volume_names)

    if module.check_mode:
        # The volumes that would be added cannot be named in advance, so only the
        # existing ones are listed
        workload_facts = _workload_facts(
            module,
            array,
            workload,
            context,
            all_volume_names,
            status=(
                "ready" if module.params["wait"] else getattr(workload, "status", None)
            ),
        )
    else:
        # Without a wait this is still main()'s pre-expand read, which is accurate
        # because only the workload's volumes changed here
        workload_facts = _workload_facts(
            module, array, workload, context, all_volume_names
        )
    module.exit_json(changed=changed, workload=workload_facts)


def delete_workload(module, array, workload=None):
    """Delete the workload"""
    changed = True
    context = module.params["context"]
    if module.check_mode:
        # Nothing is sent, so report the state this run would have produced
        if module.params["eradicate"]:
            # An eradicate leaves nothing behind, as the real run also reports
            workload_facts = {}
        else:
            workload_facts = _workload_facts(
                module,
                array,
                workload,
                context,
                destroyed=True,
                status="destroyed" if module.params["wait"] else "destroying",
            )
    else:
        res = array.patch_workloads(
            names=[module.params["name"]],
            workload=WorkloadPatch(destroyed=True),
            context_names=[context],
        )
        check_response(res, module, "Workload deletion failed")
        # The PATCH response reports destroyed=True and the time_remaining
        # countdown until eradication, so use it rather than the pre-delete read
        deleted = list(res.items)[0]
        if module.params["wait"]:
            deleted = _wait_for_status(module, array, context, "destroyed")
        workload_facts = _workload_facts(module, array, deleted, context)
        if module.params["eradicate"]:
            eradicate_workload(module, array)
    module.exit_json(changed=changed, workload=workload_facts)


def eradicate_workload(module, array):
    """Eradicate the workload"""
    changed = True
    if not module.check_mode:
        res = array.delete_workloads(
            names=[module.params["name"]],
            context_names=[module.params["context"]],
        )
        check_response(res, module, "Workload eradication failed")
        if module.params["wait"]:
            _wait_for_absent(module, array, module.params["context"])
    # The workload no longer exists, so there is nothing to describe. The same is
    # true of the run this predicts, so check mode reports it identically.
    module.exit_json(changed=changed, workload={})


def recover_workload(module, array, workload=None):
    """Recover the workload and optionally reconnect to host"""
    changed = True
    context = module.params["context"]
    if module.check_mode:
        # Nothing is sent, so report the state this run would have produced
        workload_facts = _workload_facts(
            module,
            array,
            workload,
            context,
            destroyed=False,
            status="ready" if module.params["wait"] else "recovering",
        )
    else:
        res = array.patch_workloads(
            names=[module.params["name"]],
            workload=WorkloadPatch(destroyed=False),
            context_names=[context],
        )
        check_response(res, module, "Workload recovery failed")
        recovered = list(res.items)[0]
        if module.params["wait"]:
            recovered = _wait_for_status(module, array, context, "ready")
        # Recovered volumes may have kept their connections, so the diff inside
        # _connect_host is what makes reconnecting work rather than error
        volume_names = _workload_volume_names(module, array, recovered.name, context)
        if module.params["host"] != "":
            _connect_host(module, array, recovered.name, context, volume_names)
        workload_facts = _workload_facts(
            module, array, recovered, context, volume_names
        )

    module.exit_json(changed=changed, workload=workload_facts)


def rename_workload(module, array, workload=None):
    """Rename the workload

    Nothing about a rename is asynchronous, so wait does not apply, and a rename
    does not disturb connections, so there is no host work either. The volumes
    and host are still reported, read under whichever name is current.
    """
    changed = True
    context = module.params["context"]
    if module.check_mode:
        # Nothing is sent, so report the name this run would have given it
        workload_facts = _workload_facts(
            module, array, workload, context, name=module.params["rename"]
        )
    else:
        res = array.patch_workloads(
            names=[module.params["name"]],
            workload=WorkloadPatch(name=module.params["rename"]),
            context_names=[context],
        )
        check_response(res, module, "Workload rename failed")
        # Reports the new name, as returned by the PATCH response
        workload_facts = _workload_facts(module, array, list(res.items)[0], context)
    module.exit_json(changed=changed, workload=workload_facts)


def connect_or_disconnect_volumes(module, array, mode, workload):
    """Connect the host to the workload's volumes, or disconnect it from them

    Both directions are scoped to this workload's volumes. The host keeps every
    connection it has outside the workload either way.
    """
    context = module.params["context"]
    if mode == "connect" and module.params["wait"]:
        # "All connected" only means something once the volume set has settled
        workload = _wait_for_status(module, array, context, "ready") or workload
    volume_names = _workload_volume_names(module, array, workload.name, context)

    if mode == "connect":
        changed = _connect_host(module, array, workload.name, context, volume_names)
    else:
        changed = _disconnect_host(module, array, workload.name, context, volume_names)

    # Only host connections change here, not the workload itself
    module.exit_json(
        changed=changed,
        workload=_workload_facts(module, array, workload, context, volume_names),
    )


def _fleet_members(module, array):
    """Names of every member of the fleet this array belongs to"""
    res = array.get_fleets_members()
    check_response(res, module, "Failed to list fleet members")
    members = []
    for member in list(res.items):
        name = getattr(getattr(member, "member", None), "name", None)
        if name:
            members.append(name)
    return members


def _check_placement_options(module, array, fleet, state):
    """Settle where this task applies before anything is read or written.

    There is deliberately no default. A workload belongs to a fleet member, and
    falling back to whichever array the request happened to reach makes the same
    playbook mean different things depending on fa_url - which is how a re-run ends
    up creating a second workload rather than finding the first.
    """
    chosen = [option for option in ("context", "placement") if module.params[option]]

    # recommendation only decides where a *new* workload goes, so it stands in for
    # a context on a create and nowhere else. Naming an existing workload to
    # delete, expand or rename always needs the member it is on.
    may_recommend = (
        state == "present"
        and module.params["recommendation"]
        and not module.params["rename"]
    )
    if not chosen and not may_recommend:
        module.fail_json(
            msg="Name which fleet member this applies to by setting context or "
            "placement"
            + (
                ", or set recommendation to let Fusion choose"
                if state == "present"
                else ""
            )
            + ". There is no default: it would otherwise fall to whichever array "
            "the request was sent to, which changes with fa_url."
        )

    if len(chosen) == 2 and module.params["context"] != module.params["placement"]:
        module.fail_json(
            msg=f"context '{module.params['context']}' and placement "
            f"'{module.params['placement']}' name different fleet members. They "
            "are the same thing to the array, so set one of them, or set both to "
            "the same member."
        )

    if not chosen:
        return
    # The fleet itself is allowed and means "wherever in the fleet this workload
    # is" - _resolve_fleet_context() turns it into the member holding it before
    # anything looks the workload up.
    allowed = set(_fleet_members(module, array)) | {fleet}
    for option in chosen:
        value = module.params[option]
        if value not in allowed:
            module.fail_json(
                msg=f"{option} '{value}' is not a member of fleet {fleet}, nor the "
                f"fleet itself. Valid: {', '.join(sorted(allowed))}."
            )


def _resolve_fleet_context(module, array, fleet, state):
    """Turn a context of the fleet into the member the workload is actually on

    Naming the fleet says where to look, not where to put things. A single match
    is resolved and everything downstream then works on that member as though it
    had been named directly, which is what makes a task idempotent across the
    fleet - including a delete.

    More than one match is refused rather than guessed at. A name is unique to a
    member, not to a fleet, so two of them are two workloads and nothing in the
    task says which is meant.

    This runs before any lookup, so the bare fleet name is never used as a query
    context - the array rejects it there with a 400 that reads exactly like the
    workload being absent.
    """
    found = _find_across_fleet(module, array, fleet)
    if len(found) > 1:
        module.fail_json(
            msg=f"Workload {module.params['name']} exists on more than one member "
            f"of {fleet}: {', '.join(sorted(found))}. Set context to the one you "
            "mean."
        )
    if found:
        module.params["context"] = next(iter(found))
        return

    if state == "expand":
        module.fail_json(
            msg=f"Workload {module.params['name']} was not found anywhere in "
            f"{fleet}, so there is nothing to add volumes to."
        )
    if state == "present":
        if module.params["recommendation"]:
            # Nothing to update and Fusion was asked to choose, so leave the
            # context unset and let create_workload() get a placement
            module.params["context"] = ""
            return
        module.fail_json(
            msg=f"Workload {module.params['name']} was not found anywhere in "
            f"{fleet}, and {fleet} names the fleet rather than a member, so there "
            "is nowhere to create it. Set context or placement to a member, or set "
            "recommendation to let Fusion choose."
        )
    # state=absent with nothing anywhere in the fleet: already the desired end
    module.exit_json(changed=False, workload={})


def main():
    argument_spec = purefa_argument_spec()
    argument_spec.update(
        dict(
            name=dict(type="str", required=True),
            state=dict(
                type="str",
                default="present",
                choices=["absent", "present", "expand"],
            ),
            preset=dict(type="str"),
            rename=dict(type="str"),
            eradicate=dict(type="bool", default=False),
            placement=dict(type="str"),
            parameters=dict(
                type="list",
                elements="dict",
                options=dict(
                    name=dict(type="str", required=True),
                    value=dict(
                        type="dict",
                        required=True,
                        options=dict(
                            string=dict(type="str"),
                            integer=dict(type="int"),
                            boolean=dict(type="bool"),
                            resource_reference=dict(
                                type="dict",
                                options=dict(
                                    id=dict(type="str"),
                                    name=dict(type="str"),
                                    resource_type=dict(type="str"),
                                ),
                            ),
                        ),
                    ),
                ),
            ),
            volume_count=dict(type="int"),
            volume_configuration=dict(type="str"),
            recommendation=dict(type="bool", default=False),
            context=dict(type="str", default=""),
            host=dict(type="str", default=""),
            # Deliberately not in purefa_argument_spec(), which would land these
            # on every module in the collection
            wait=dict(type="bool", default=True),
            wait_timeout=dict(type="int", default=300),
        )
    )

    required_if = [
        ["state", "expand", ["volume_count", "volume_configuration", "preset"]]
    ]

    module = AnsibleModule(
        argument_spec, supports_check_mode=True, required_if=required_if
    )

    if not HAS_PURESTORAGE:
        module.fail_json(msg="py-pure-client sdk is required for this module")

    # Checked before any API call. A host has to be connected to every volume in
    # the workload, which cannot be established while the volume set is still
    # growing, so there is no correct way to honour host without waiting.
    if module.params["host"] and not module.params["wait"]:
        module.fail_json(
            msg="host cannot be used with wait: false. Connecting or "
            "disconnecting a host requires the workload's volume set to have "
            "settled first, which only happens when waiting."
        )

    volume_count = module.params["volume_count"]
    if volume_count is not None and volume_count <= 0:
        module.fail_json(msg="volume_count must be a positive integer.")

    array = get_array(module)
    api_version = array.get_rest_version()
    if LooseVersion(MIN_REQUIRED_API_VERSION) > LooseVersion(api_version):
        module.fail_json(
            msg="FlashArray REST version not supported. "
            "Minimum version required: {0}".format(MIN_REQUIRED_API_VERSION)
        )
    state = module.params["state"]
    fleet_res = array.get_fleets()
    fleet_items = list(fleet_res.items) if fleet_res.status_code == 200 else []
    if not fleet_items:
        module.fail_json(
            msg="purefa_workload requires a Fusion fleet environment, but this "
            "array is not a member of a fleet."
        )
    fleet = fleet_items[0].name
    _check_placement_options(module, array, fleet, state)
    # context and placement mean the same thing to the API - a workload is created
    # on its context, and there is no separate placement to send - and they have
    # been checked to agree, so either may stand for both. The trailing "" keeps an
    # unset one as the empty string the argument spec declares and
    # _resolve_fleet_context() writes, so "no context yet" has one spelling rather
    # than two - placement defaults to None, and "" or None is None.
    module.params["context"] = (
        module.params["context"] or module.params["placement"] or ""
    )
    if module.params["context"] == fleet:
        _resolve_fleet_context(module, array, fleet, state)

    workload_destroyed = False
    workload_exists = False
    workload = None
    preset_config = {}
    # allow_errors, as in _read_workload: without it the array rejects a read by
    # name outright when the context is a fleet member other than this one, and a
    # workload that already exists there would be reported as absent and created
    # a second time
    if module.params["context"]:
        res = array.get_workloads(
            names=[module.params["name"]],
            context_names=[module.params["context"]],
            allow_errors=True,
        )
        if res.status_code == 200:
            workload_exists = True
            workload = list(res.items)[0]
            workload_destroyed = getattr(workload, "destroyed", False)
    # Otherwise this is a recommendation-led create with no context yet, so there is
    # nowhere to look. create_workload() sweeps the fleet instead, which is also what
    # stops a second run asking Fusion for another placement.

    if (
        state == "present"
        and not workload_destroyed
        and not workload_exists
        and not module.params["rename"]
    ) or (state == "expand" and not workload_destroyed):
        # preset is only read here, and by the create and expand paths this gates.
        # Every other outcome - delete, eradicate, rename, recover, host connect or
        # disconnect - works from the workload the array already has, so a task that
        # does not name a preset is not incomplete. required_if cannot express this:
        # whether a create is happening is only known from the read above.
        if not module.params["preset"]:
            module.fail_json(
                msg="preset required to create a new workload or to expand an "
                "existing one."
            )
        # Presets are fleet objects, and the API names them "<fleet>:<preset>", so
        # qualify it here rather than at the top of main(): it is meaningless on
        # every path that does not reach this block.
        module.params["preset"] = fleet + ":" + module.params["preset"]
        res = array.get_presets_workload(
            names=[module.params["preset"]],
        )
        check_response(
            res,
            module,
            f"Preset {module.params['preset']} does not exist in fleet {fleet}",
        )
        preset_config = list(res.items)[0]
    if (
        state == "present"
        and workload_exists
        and module.params["rename"]
        and not workload_destroyed
    ):
        rename_workload(module, array, workload)
    elif state == "present" and not workload_exists and module.params["rename"]:
        module.fail_json(
            msg=f"Workload {module.params['name']} does not exist on "
            f"{module.params['context']}, so there is nothing to rename to "
            f"{module.params['rename']}."
        )
    elif state == "present" and workload_destroyed and module.params["rename"]:
        module.fail_json(
            msg=f"Workload {module.params['name']} on {module.params['context']} is "
            f"destroyed, so there is nothing to rename to {module.params['rename']}. "
            "Recover it first with a separate task (state: present, no rename), "
            "then rename it."
        )
    elif state == "present" and not workload_exists:
        create_workload(module, array, fleet, preset_config)
    elif state == "expand" and workload_exists and not workload_destroyed:
        expand_workload(
            module, array, fleet, preset_config.volume_configurations, workload
        )
    elif state == "present" and workload_exists and workload_destroyed:
        recover_workload(module, array, workload)
    elif (
        state == "present"
        and workload_exists
        and not workload_destroyed
        and module.params["host"] != ""
    ):
        connect_or_disconnect_volumes(module, array, "connect", workload)
    elif (
        state == "absent"
        and workload_exists
        and not workload_destroyed
        and module.params["host"] != ""
    ):
        connect_or_disconnect_volumes(module, array, "disconnect", workload)
    elif state == "absent" and workload_exists and not workload_destroyed:
        _warn_about_copies_elsewhere(module, array, fleet)
        delete_workload(module, array, workload)
    elif state == "absent" and workload_destroyed and module.params["eradicate"]:
        _warn_about_copies_elsewhere(module, array, fleet)
        eradicate_workload(module, array)
    elif state == "expand" and not workload_exists:
        # Unlike absent, where not being there is the requested end state, expand
        # asks to add volumes to something that has to exist. Reporting no change
        # would read as "already expanded".
        module.fail_json(
            msg=f"Workload {module.params['name']} does not exist on "
            f"{module.params['context']}, so there is nothing to add volumes to."
        )
    else:
        # Nothing to do. If this was a removal, the workload not being on the named
        # context reads as "already gone" - so say when it is in fact sitting on
        # another member, untouched, rather than letting ok imply it was removed.
        if state == "absent" and not workload_exists:
            _warn_about_copies_elsewhere(module, array, fleet)
        module.exit_json(
            changed=False,
            workload=_workload_facts(module, array, workload, module.params["context"]),
        )


if __name__ == "__main__":
    main()
