.. _ansible_collections.everpure.flasharray.docsite.realm_multitenancy_guide:

*******************************************
Realm multi-tenancy end-to-end walk-through
*******************************************

.. contents::
  :local:

Overview
========

A *realm* is the FlashArray multi-tenancy boundary. Giving a tenant self-service,
realm-scoped administration is a chain of four objects:

#. **Realm** - the tenant boundary, with an optional capacity quota.
#. **Pod** - a data container placed *inside* the realm (named ``realm::pod``).
#. **Management-access policy** - grants a *role* a set of permissions
   *scoped* to the realm (realm-scoped RBAC).
#. **Directory-service role** - maps a directory-service (AD/LDAP) group to that
   management-access policy, so members of the group inherit the scoped role.

This guide shows the whole chain with native modules, and - for environments
that predate the modules, or for objects you want to drive directly - the
equivalent ``ansible.builtin.uri`` calls.

Requirements
============

- Purity//FA 6.6.11 or later (REST 2.36) for realms and management-access
  policies.
- ``everpure.flasharray`` 1.44.0 or later for the ``realm`` parameter of
  ``purefa_pod``, the ``access_policy`` parameter of ``purefa_dsrole`` and the
  ``purefa_policy_management_access`` module.

.. _ansible_collections.everpure.flasharray.docsite.realm_login_path:

.. note::

   On FlashArray the REST login endpoint is **versioned**:
   ``/api/<version>/login`` (for example ``/api/2.39/login``). This differs from
   some FlashBlade examples that use ``/api/login``; the unversioned path
   returns a ``404`` on FlashArray. Always include the REST version when you
   drop down to ``uri``.

Using the native modules
========================

.. code-block:: yaml+jinja

  - name: Realm multi-tenancy setup
    hosts: localhost
    gather_facts: false
    vars:
      fa_url: 10.10.10.2
      api_token: e31060a7-21fc-e277-6240-25983c6c4592
      realm_name: tenant_a
      pod_name: tenant_a_pod1
      policy_name: tenant_a_admin
      role_name: tenant_a_admin_role
      ad_group: tenant-a-admins
      ad_group_base: "OU=PureGroups,OU=Tenants"
    tasks:
      - name: 1. Create the realm with a quota
        everpure.flasharray.purefa_realm:
          name: "{{ realm_name }}"
          quota: 5T
          fa_url: "{{ fa_url }}"
          api_token: "{{ api_token }}"

      - name: 2. Create a pod inside the realm
        everpure.flasharray.purefa_pod:
          name: "{{ pod_name }}"
          realm: "{{ realm_name }}"
          fa_url: "{{ fa_url }}"
          api_token: "{{ api_token }}"

      - name: 3. Create a management-access policy scoped to the realm
        everpure.flasharray.purefa_policy_management_access:
          name: "{{ policy_name }}"
          aggregation_strategy: least-common-permissions
          rules:
            - role: storage
              scope: "{{ realm_name }}"
              resource_type: realms
          fa_url: "{{ fa_url }}"
          api_token: "{{ api_token }}"

      - name: 4. Map an AD group to the policy via a directory-service role
        everpure.flasharray.purefa_dsrole:
          name: "{{ role_name }}"
          access_policy: "{{ policy_name }}"
          group: "{{ ad_group }}"
          group_base: "{{ ad_group_base }}"
          fa_url: "{{ fa_url }}"
          api_token: "{{ api_token }}"

The pod created in step 2 is addressable as ``tenant_a::tenant_a_pod1``. You can
achieve the same by passing the fully-qualified ``name: tenant_a::tenant_a_pod1``
instead of the ``realm`` parameter.

``uri`` fall-backs
==================

If you are on an older collection release, or want to manage an object that has
no module yet, the same steps can be driven directly against the REST API.
First authenticate against the **versioned** login endpoint and reuse the
returned session token:

.. code-block:: yaml+jinja

  - name: Log in to the FlashArray REST API (versioned path)
    ansible.builtin.uri:
      url: "https://{{ fa_url }}/api/2.39/login"
      method: POST
      headers:
        api-token: "{{ api_token }}"
      validate_certs: false
      status_code: 200
    register: fa_login

  - name: Capture the session auth token
    ansible.builtin.set_fact:
      # uri exposes response headers as lower-cased, underscored fields
      x_auth_token: "{{ fa_login.x_auth_token }}"

Create the management-access policy (equivalent to step 3):

.. code-block:: yaml+jinja

  - name: Create realm-scoped management-access policy via uri
    ansible.builtin.uri:
      url: "https://{{ fa_url }}/api/2.39/policies/management-access?names={{ policy_name }}"
      method: POST
      headers:
        x-auth-token: "{{ x_auth_token }}"
      body_format: json
      body:
        enabled: true
        aggregation_strategy: least-common-permissions
        rules:
          - role:
              name: storage
            scope:
              name: "{{ realm_name }}"
              resource_type: realms
      validate_certs: false
      status_code: 200

Create the directory-service role bound to the policy (equivalent to step 4):

.. code-block:: yaml+jinja

  - name: Create directory-service role via uri
    ansible.builtin.uri:
      url: "https://{{ fa_url }}/api/2.39/directory-services/roles?names={{ role_name }}"
      method: POST
      headers:
        x-auth-token: "{{ x_auth_token }}"
      body_format: json
      body:
        group: "{{ ad_group }}"
        group_base: "{{ ad_group_base }}"
        management_access_policies:
          - name: "{{ policy_name }}"
      validate_certs: false
      status_code: 200

Verifying the result
====================

``purefa_info`` reports realms, pods and management-access policies, so you can
confirm the chain was built correctly:

.. code-block:: yaml+jinja

  - name: Collect FlashArray configuration
    everpure.flasharray.purefa_info:
      gather_subset:
        - config
      fa_url: "{{ fa_url }}"
      api_token: "{{ api_token }}"
    register: array_info
