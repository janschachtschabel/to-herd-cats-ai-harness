export interface paths {
    "/api/activity": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Activity
         * @description The caller's notifications, newest first.
         */
        get: operations["list_activity_api_activity_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/activity/count": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Count Activity */
        get: operations["count_activity_api_activity_count_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/activity/read-all": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Read All */
        post: operations["read_all_api_activity_read_all_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/activity/{notification_id}/done": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Mark Done */
        post: operations["mark_done_api_activity__notification_id__done_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/activity/{notification_id}/read": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Mark Read */
        post: operations["mark_read_api_activity__notification_id__read_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/admin/audit": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Audit */
        get: operations["list_audit_api_admin_audit_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/admin/calendar-settings": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Calendar Settings */
        get: operations["get_calendar_settings_api_admin_calendar_settings_get"];
        /** Set Calendar Settings */
        put: operations["set_calendar_settings_api_admin_calendar_settings_put"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/admin/dm-inspect": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Find Dms
         * @description `dm.inspect`: a person's DMs, participants and times only (audited).
         */
        get: operations["find_dms_api_admin_dm_inspect_get"];
        put?: never;
        /**
         * Grant Inspection
         * @description `dm.inspect`: read one DM for 60 minutes, with a reason (audited, and shown to
         *     its participants).
         */
        post: operations["grant_inspection_api_admin_dm_inspect_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/admin/dm-inspect/{inspection_id}/messages": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Inspected Messages
         * @description The inspected DM's messages, replies included, newest first; 404 once the
         *     inspection has expired.
         */
        get: operations["inspected_messages_api_admin_dm_inspect__inspection_id__messages_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/admin/groups": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Groups */
        get: operations["list_groups_api_admin_groups_get"];
        put?: never;
        /** Create Group */
        post: operations["create_group_api_admin_groups_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/admin/groups/{group_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Group */
        get: operations["get_group_api_admin_groups__group_id__get"];
        put?: never;
        post?: never;
        /** Delete Group */
        delete: operations["delete_group_api_admin_groups__group_id__delete"];
        options?: never;
        head?: never;
        /** Update Group */
        patch: operations["update_group_api_admin_groups__group_id__patch"];
        trace?: never;
    };
    "/api/admin/groups/{group_id}/members": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Group Members */
        get: operations["list_group_members_api_admin_groups__group_id__members_get"];
        put?: never;
        /** Add Group Member */
        post: operations["add_group_member_api_admin_groups__group_id__members_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/admin/groups/{group_id}/members/{member_type}/{member_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        /** Remove Group Member */
        delete: operations["remove_group_member_api_admin_groups__group_id__members__member_type___member_id__delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/admin/oidc-providers": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Providers */
        get: operations["list_providers_api_admin_oidc_providers_get"];
        put?: never;
        /** Create Provider */
        post: operations["create_provider_api_admin_oidc_providers_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/admin/oidc-providers/{provider_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Provider */
        get: operations["get_provider_api_admin_oidc_providers__provider_id__get"];
        put?: never;
        post?: never;
        /**
         * Delete Provider
         * @description Also ends the sessions of the people linked through it, but the caller's own.
         */
        delete: operations["delete_provider_api_admin_oidc_providers__provider_id__delete"];
        options?: never;
        head?: never;
        /** Update Provider */
        patch: operations["update_provider_api_admin_oidc_providers__provider_id__patch"];
        trace?: never;
    };
    "/api/admin/oidc-providers/{provider_id}/check": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Check Provider
         * @description Discovery and the JWKS, fetched now through the egress guard; a fixed code.
         */
        post: operations["check_provider_api_admin_oidc_providers__provider_id__check_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/admin/users": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Users */
        get: operations["list_users_api_admin_users_get"];
        put?: never;
        /** Create User */
        post: operations["create_user_api_admin_users_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/admin/users/pending/count": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Count Pending
         * @description How many self-registered accounts wait for approval (the admin navigation's badge).
         */
        get: operations["count_pending_api_admin_users_pending_count_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/admin/users/{user_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        /** Update User */
        patch: operations["update_user_api_admin_users__user_id__patch"];
        trace?: never;
    };
    "/api/admin/users/{user_id}/approve": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Approve Signup
         * @description Let a self-registered account in (409 `users.not_pending` once decided).
         */
        post: operations["approve_signup_api_admin_users__user_id__approve_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/admin/users/{user_id}/deactivate": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Deactivate User */
        post: operations["deactivate_user_api_admin_users__user_id__deactivate_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/admin/users/{user_id}/identities": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List User Identities */
        get: operations["list_user_identities_api_admin_users__user_id__identities_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/admin/users/{user_id}/identities/{identity_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        /** Unlink User Identity */
        delete: operations["unlink_user_identity_api_admin_users__user_id__identities__identity_id__delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/admin/users/{user_id}/reactivate": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Reactivate User */
        post: operations["reactivate_user_api_admin_users__user_id__reactivate_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/admin/users/{user_id}/reject": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Reject Signup
         * @description Refuse a self-registered account: it is deleted (it never was active), with
         *     what signing up created; its address is free again.
         */
        post: operations["reject_signup_api_admin_users__user_id__reject_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/admin/users/{user_id}/sign-out": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Sign Out User
         * @description Ends every session of the person; they stay active and may sign in again.
         */
        post: operations["sign_out_user_api_admin_users__user_id__sign_out_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/admin/users/{user_id}/totp/reset": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Reset Totp
         * @description Turns the person's TOTP off (a lost device); they sign in with the password
         *     alone until they set it up again. Idempotent.
         */
        post: operations["reset_totp_api_admin_users__user_id__totp_reset_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/agents": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Agents */
        get: operations["list_agents_api_agents_get"];
        put?: never;
        /** Create Agent */
        post: operations["create_agent_api_agents_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/agents/{agent_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Agent */
        get: operations["get_agent_api_agents__agent_id__get"];
        put?: never;
        post?: never;
        /**
         * Delete Agent
         * @description Only an agent that never talked or ran (409 `agent.in_use`: pause it instead).
         */
        delete: operations["delete_agent_api_agents__agent_id__delete"];
        options?: never;
        head?: never;
        /** Update Agent */
        patch: operations["update_agent_api_agents__agent_id__patch"];
        trace?: never;
    };
    "/api/agents/{agent_id}/automations": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Automations Of Agent
         * @description Every automation of the agent (`agent.manage`).
         */
        get: operations["automations_of_agent_api_agents__agent_id__automations_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/agents/{agent_id}/profile": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Agent Profile
         * @description For a person with `ai.use`: name, introduction and status (no draft).
         */
        get: operations["agent_profile_api_agents__agent_id__profile_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/agents/{agent_id}/runs": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Runs Of Agent
         * @description The agent's runs, newest first (its responsible person, `agent.manage`).
         */
        get: operations["runs_of_agent_api_agents__agent_id__runs_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/agents/{agent_id}/skills": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Agent Skills
         * @description The agent's skills the caller sees, by name.
         */
        get: operations["get_agent_skills_api_agents__agent_id__skills_get"];
        /**
         * Set Agent Skills
         * @description Replace the agent's skills (those the caller sees), with the agent's `version`.
         */
        put: operations["set_agent_skills_api_agents__agent_id__skills_put"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/agents/{agent_id}/spaces": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Agent Spaces
         * @description The agent's memberships by name (open spaces it only reads are not listed).
         */
        get: operations["list_agent_spaces_api_agents__agent_id__spaces_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/agents/{agent_id}/tokens": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Agent Tokens
         * @description An external agent's tokens, newest first (`agent.manage`).
         */
        get: operations["list_agent_tokens_api_agents__agent_id__tokens_get"];
        put?: never;
        /**
         * Create Agent Token
         * @description A token for an external agent (`herd_agt_…`); `secret` is shown this once.
         */
        post: operations["create_agent_token_api_agents__agent_id__tokens_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/agents/{agent_id}/tokens/{token_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        /** Revoke Agent Token */
        delete: operations["revoke_agent_token_api_agents__agent_id__tokens__token_id__delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/agents/{agent_id}/tokens/{token_id}/calls": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Agent Token Calls
         * @description The agent token's tool calls through `/mcp`, newest first.
         */
        get: operations["list_agent_token_calls_api_agents__agent_id__tokens__token_id__calls_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/agents/{agent_id}/tools": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Agent Tools
         * @description Every tool of the catalog with the agent's grant (`agent.manage`).
         */
        get: operations["agent_tools_api_agents__agent_id__tools_get"];
        /**
         * Set Agent Tools
         * @description Replace the agent's entries (they only tighten), with its `version`.
         */
        put: operations["set_agent_tools_api_agents__agent_id__tools_put"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/ai/assignments": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Assignments */
        get: operations["get_assignments_api_ai_assignments_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/ai/assignments/default": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        /** Set Default Assignment */
        put: operations["set_default_assignment_api_ai_assignments_default_put"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/ai/assignments/groups": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Group Assignments */
        get: operations["list_group_assignments_api_ai_assignments_groups_get"];
        /**
         * Set Group Assignments
         * @description Replace the ordered list (at most 100); names the version of `GET` (409).
         */
        put: operations["set_group_assignments_api_ai_assignments_groups_put"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/ai/assignments/personal-agents": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        /**
         * Set Personal Agents
         * @description Allow or stop personal agents (`agent.create_personal`), with the version.
         */
        put: operations["set_personal_agents_api_ai_assignments_personal_agents_put"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/ai/assignments/users": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List User Assignments */
        get: operations["list_user_assignments_api_ai_assignments_users_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/ai/assignments/users/{user_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        /** Set User Assignment */
        put: operations["set_user_assignment_api_ai_assignments_users__user_id__put"];
        post?: never;
        /**
         * Remove User Assignment
         * @description The person falls back to their groups' or the standard assignment.
         */
        delete: operations["remove_user_assignment_api_ai_assignments_users__user_id__delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/ai/budgets": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Budgets
         * @description Every budget with today's use (UTC day).
         */
        get: operations["list_budgets_api_ai_budgets_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/ai/budgets/agents": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Budget Agents
         * @description Every agent (id and name, by name) a budget may be set for.
         */
        get: operations["budget_agents_api_ai_budgets_agents_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/ai/budgets/agents/{agent_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        /** Set Agent Budget */
        put: operations["set_agent_budget_api_ai_budgets_agents__agent_id__put"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/ai/budgets/organisation": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        /** Set Organisation Budget */
        put: operations["set_organisation_budget_api_ai_budgets_organisation_put"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/ai/budgets/users/{user_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        /** Set User Budget */
        put: operations["set_user_budget_api_ai_budgets_users__user_id__put"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/ai/budgets/{budget_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        /** Delete Budget */
        delete: operations["delete_budget_api_ai_budgets__budget_id__delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/ai/connections": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Connections */
        get: operations["list_connections_api_ai_connections_get"];
        put?: never;
        /** Create Connection */
        post: operations["create_connection_api_ai_connections_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/ai/connections/{connection_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Connection */
        get: operations["get_connection_api_ai_connections__connection_id__get"];
        put?: never;
        post?: never;
        /**
         * Delete Connection
         * @description 409 `ai.connection_in_use` while an assignment uses it.
         */
        delete: operations["delete_connection_api_ai_connections__connection_id__delete"];
        options?: never;
        head?: never;
        /** Update Connection */
        patch: operations["update_connection_api_ai_connections__connection_id__patch"];
        trace?: never;
    };
    "/api/ai/connections/{connection_id}/models": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Fetch Models
         * @description Read the models from the provider's `/models`; 502 `ai.provider_failed` with
         *     `details.status` when it does not answer with a list.
         */
        post: operations["fetch_models_api_ai_connections__connection_id__models_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/ai/connections/{connection_id}/test": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Test Connection
         * @description One small call to the provider; the outcome as a state, never its answer.
         */
        post: operations["test_connection_api_ai_connections__connection_id__test_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/ai/connectors": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Connectors */
        get: operations["list_connectors_api_ai_connectors_get"];
        put?: never;
        /** Create Connector */
        post: operations["create_connector_api_ai_connectors_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/ai/connectors/{connector_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Connector */
        get: operations["get_connector_api_ai_connectors__connector_id__get"];
        put?: never;
        post?: never;
        /** Delete Connector */
        delete: operations["delete_connector_api_ai_connectors__connector_id__delete"];
        options?: never;
        head?: never;
        /** Update Connector */
        patch: operations["update_connector_api_ai_connectors__connector_id__patch"];
        trace?: never;
    };
    "/api/ai/connectors/{connector_id}/authorize": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Authorize Connector
         * @description OAuth: where the browser goes to approve; it comes back to the callback.
         */
        post: operations["authorize_connector_api_ai_connectors__connector_id__authorize_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/ai/connectors/{connector_id}/disconnect": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Disconnect Connector
         * @description OAuth: forget the tokens and revoke them at the provider.
         */
        post: operations["disconnect_connector_api_ai_connectors__connector_id__disconnect_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/ai/mcp": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Mcp Settings */
        get: operations["get_mcp_settings_api_ai_mcp_get"];
        /**
         * Set Mcp Settings
         * @description The switch for `mcp.use` and the data location, with the version read (409).
         */
        put: operations["set_mcp_settings_api_ai_mcp_put"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/ai/mcp-catalog": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Entries */
        get: operations["list_entries_api_ai_mcp_catalog_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/ai/mcp-catalog/problems": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Problems
         * @description Files that could not be loaded and were skipped: which, and why.
         */
        get: operations["list_problems_api_ai_mcp_catalog_problems_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/ai/mcp-catalog/{entry_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Entry */
        get: operations["get_entry_api_ai_mcp_catalog__entry_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/ai/mcp-catalog/{entry_id}/install": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Install Entry
         * @description Create the server (and its OAuth client and shared connector, as the scope and
         *     kind need) from the entry; `server.refresh` says how reading its tools went.
         */
        post: operations["install_entry_api_ai_mcp_catalog__entry_id__install_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/ai/mcp-servers": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Servers */
        get: operations["list_servers_api_ai_mcp_servers_get"];
        put?: never;
        /**
         * Create Server
         * @description Saves the server, then reads its tool list; `refresh` says how that went.
         */
        post: operations["create_server_api_ai_mcp_servers_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/ai/mcp-servers/{server_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Server */
        get: operations["get_server_api_ai_mcp_servers__server_id__get"];
        put?: never;
        post?: never;
        /** Delete Server */
        delete: operations["delete_server_api_ai_mcp_servers__server_id__delete"];
        options?: never;
        head?: never;
        /** Update Server */
        patch: operations["update_server_api_ai_mcp_servers__server_id__patch"];
        trace?: never;
    };
    "/api/ai/mcp-servers/{server_id}/refresh": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Refresh Tools
         * @description Read the tool list again; a failure is a state, never the server's answer.
         */
        post: operations["refresh_tools_api_ai_mcp_servers__server_id__refresh_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/ai/mcp-servers/{server_id}/test": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Test Server
         * @description Connect and list the tools; nothing is stored.
         */
        post: operations["test_server_api_ai_mcp_servers__server_id__test_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/ai/mcp-servers/{server_id}/tools": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Tools */
        get: operations["list_tools_api_ai_mcp_servers__server_id__tools_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/ai/mcp-servers/{server_id}/tools/{tool_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        /** Classify Tool */
        patch: operations["classify_tool_api_ai_mcp_servers__server_id__tools__tool_id__patch"];
        trace?: never;
    };
    "/api/ai/mcp-servers/{server_id}/tools/{tool_id}/approve": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Approve Tool
         * @description Approve exactly the tool as last read (its fingerprint).
         */
        post: operations["approve_tool_api_ai_mcp_servers__server_id__tools__tool_id__approve_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/ai/mcp-servers/{server_id}/tools/{tool_id}/block": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Block Tool */
        post: operations["block_tool_api_ai_mcp_servers__server_id__tools__tool_id__block_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/ai/mcp/tokens": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List All Tokens
         * @description Every token of the organisation, newest first: metadata only.
         */
        get: operations["list_all_tokens_api_ai_mcp_tokens_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/ai/mcp/tokens/{token_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        /** Revoke Any Token */
        delete: operations["revoke_any_token_api_ai_mcp_tokens__token_id__delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/ai/mcp/tokens/{token_id}/calls": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Any Token Calls
         * @description Any token's tool calls through `/mcp`, newest first: metadata only.
         */
        get: operations["list_any_token_calls_api_ai_mcp_tokens__token_id__calls_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/ai/my-connectors": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Connectors */
        get: operations["list_connectors_api_ai_my_connectors_get"];
        put?: never;
        /** Create Connector */
        post: operations["create_connector_api_ai_my_connectors_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/ai/my-connectors/{connector_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Connector */
        get: operations["get_connector_api_ai_my_connectors__connector_id__get"];
        put?: never;
        post?: never;
        /** Delete Connector */
        delete: operations["delete_connector_api_ai_my_connectors__connector_id__delete"];
        options?: never;
        head?: never;
        /** Update Connector */
        patch: operations["update_connector_api_ai_my_connectors__connector_id__patch"];
        trace?: never;
    };
    "/api/ai/my-connectors/{connector_id}/authorize": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Authorize Connector
         * @description OAuth: where the browser goes to approve; it comes back to the callback.
         */
        post: operations["authorize_connector_api_ai_my_connectors__connector_id__authorize_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/ai/my-connectors/{connector_id}/disconnect": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Disconnect Connector
         * @description OAuth: forget the tokens and revoke them at the provider.
         */
        post: operations["disconnect_connector_api_ai_my_connectors__connector_id__disconnect_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/ai/my-mcp-servers": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Personal Servers */
        get: operations["list_personal_servers_api_ai_my_mcp_servers_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/ai/oauth-clients": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Clients */
        get: operations["list_clients_api_ai_oauth_clients_get"];
        put?: never;
        /** Create Client */
        post: operations["create_client_api_ai_oauth_clients_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/ai/oauth-clients/discover": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Discover Client
         * @description Find an MCP server's authorization server (RFC 9728, RFC 8414): a proposal for
         *     a client; nothing is stored, every request goes through the egress guard.
         */
        post: operations["discover_client_api_ai_oauth_clients_discover_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/ai/oauth-clients/{client_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Client */
        get: operations["get_client_api_ai_oauth_clients__client_id__get"];
        put?: never;
        post?: never;
        /** Delete Client */
        delete: operations["delete_client_api_ai_oauth_clients__client_id__delete"];
        options?: never;
        head?: never;
        /** Update Client */
        patch: operations["update_client_api_ai_oauth_clients__client_id__patch"];
        trace?: never;
    };
    "/api/ai/oauth/callback": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Oauth Legacy Callback
         * @description The shared callback of earlier releases: only for flows started with it.
         */
        get: operations["oauth_legacy_callback_api_ai_oauth_callback_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/ai/oauth/{client_id}/callback": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Oauth Callback
         * @description An app's authorization server's redirect: finish the flow started with this
         *     callback, then send the browser to the result page (`/ai/oauth/done?status=...`).
         */
        get: operations["oauth_callback_api_ai_oauth__client_id__callback_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/ai/usage": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Usage
         * @description Sums per UTC day (newest first), at most 366 days.
         */
        get: operations["list_usage_api_ai_usage_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/ai/usage/me": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** My Usage */
        get: operations["my_usage_api_ai_usage_me_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/approvals": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * My Approvals
         * @description Those addressed to the caller, newest first (`state=pending`: to decide).
         */
        get: operations["my_approvals_api_approvals_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/approvals/{approval_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Approval */
        get: operations["get_approval_api_approvals__approval_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/approvals/{approval_id}/decide": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Decide Approval */
        post: operations["decide_approval_api_approvals__approval_id__decide_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/approvals/{approval_id}/diff": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Approval Diff
         * @description The page as it is now against the call's content, for the person asked (null:
         *     too large to compare).
         */
        get: operations["approval_diff_api_approvals__approval_id__diff_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/attachments/{attachment_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Download Attachment */
        get: operations["download_attachment_api_attachments__attachment_id__get"];
        put?: never;
        post?: never;
        /**
         * Delete Attachment
         * @description `page.edit` on its page; the file goes when no other attachment uses it.
         */
        delete: operations["delete_attachment_api_attachments__attachment_id__delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/attachments/{attachment_id}/ai-lock": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        /**
         * Set Attachment Ai Lock
         * @description `page.moderate` in its page's space; the attachment's `version` (stale → 409).
         */
        put: operations["set_attachment_ai_lock_api_attachments__attachment_id__ai_lock_put"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/auth/login": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Login
         * @description Signed in (200, the session cookie), or, for a person with TOTP, 202: the
         *     password was right and the sign-in waits for the second factor
         *     (`/auth/login/second-factor`, with the cookie set here); no session yet.
         */
        post: operations["login_api_auth_login_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/auth/login/second-factor": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Second Factor
         * @description The second step of a sign-in: the browser's waiting sign-in (cookie) and a code
         *     or a recovery code; the login session opens only now.
         */
        post: operations["second_factor_api_auth_login_second_factor_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/auth/logout": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Logout */
        post: operations["logout_api_auth_logout_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/auth/me": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Me */
        get: operations["me_api_auth_me_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        /**
         * Update Me
         * @description The caller's own settings (the language).
         */
        patch: operations["update_me_api_auth_me_patch"];
        trace?: never;
    };
    "/api/auth/me/identities": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** My Identities */
        get: operations["my_identities_api_auth_me_identities_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/auth/me/identities/{identity_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        /** Unlink Mine */
        delete: operations["unlink_mine_api_auth_me_identities__identity_id__delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/auth/me/identities/{key}/link": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Link
         * @description Start linking the caller's account at the provider (from the profile): the
         *     browser goes to the returned address; the binding cookie comes with this answer.
         *     Needs the current password, or a sign-in through a provider of this session at
         *     most 10 minutes old (403 `auth.reauth_required`).
         */
        post: operations["link_api_auth_me_identities__key__link_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/auth/me/password": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Change My Password
         * @description The caller's own password; this session stays, every other one ends.
         */
        post: operations["change_my_password_api_auth_me_password_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/auth/me/sessions": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Own Sessions
         * @description The caller's running sessions, newest first.
         */
        get: operations["list_own_sessions_api_auth_me_sessions_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/auth/me/sessions/sign-out-others": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Sign Out Others
         * @description Every session of the caller ends but this one.
         */
        post: operations["sign_out_others_api_auth_me_sessions_sign_out_others_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/auth/me/sessions/{session_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        /**
         * End Own Session
         * @description One of the caller's sessions ends (this one too: then the cookie goes).
         */
        delete: operations["end_own_session_api_auth_me_sessions__session_id__delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/auth/me/totp": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** My Totp */
        get: operations["my_totp_api_auth_me_totp_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/auth/me/totp/confirm": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Confirm Totp
         * @description The first code turns TOTP on; every other session of the person ends.
         */
        post: operations["confirm_totp_api_auth_me_totp_confirm_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/auth/me/totp/disable": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Disable Totp */
        post: operations["disable_totp_api_auth_me_totp_disable_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/auth/me/totp/recovery-codes": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Renew Recovery Codes
         * @description A new set in place of the old one (a current code proves the device).
         */
        post: operations["renew_recovery_codes_api_auth_me_totp_recovery_codes_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/auth/me/totp/setup": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Set Up Totp
         * @description A new secret (the current password proves it is the person); it protects
         *     nothing until `/me/totp/confirm`. Shown this once.
         */
        post: operations["set_up_totp_api_auth_me_totp_setup_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/auth/me/touch": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Touch Me
         * @description The person works in this tab (typing in the live editor, say) though it asked
         *     the API nothing for a while: a use of the session (J7, R18-4), nothing else. No
         *     write for the write limit.
         */
        post: operations["touch_me_api_auth_me_touch_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/auth/oidc/{key}/callback": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Callback
         * @description The provider's redirect: finish the flow, then the app's start page signed in,
         *     or the sign-in (profile) page with `?error=` (`?link_error=`) and a fixed code.
         */
        get: operations["callback_api_auth_oidc__key__callback_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/auth/oidc/{key}/start": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Start
         * @description To the provider's sign-in page, with the browser binding as a cookie; a provider
         *     that is unknown, off or unreachable sends the browser back to the sign-in page.
         *     `reauth`: the sign-in is the proof before linking (`fresh.py`): the provider is
         *     asked for a fresh login, and the browser comes back to the profile.
         */
        get: operations["start_api_auth_oidc__key__start_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/auth/providers": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Providers
         * @description The enabled providers (key, name, kind) for the sign-in page; no session needed.
         */
        get: operations["list_providers_api_auth_providers_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/automations": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * My Automations
         * @description The caller's own automations, newest first.
         */
        get: operations["my_automations_api_automations_get"];
        put?: never;
        /** Create Automation */
        post: operations["create_automation_api_automations_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/automations/preview": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Preview Terms
         * @description The next five terms of a schedule, refused like a save would refuse it.
         */
        post: operations["preview_terms_api_automations_preview_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/automations/{automation_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Automation */
        get: operations["get_automation_api_automations__automation_id__get"];
        put?: never;
        post?: never;
        /**
         * Delete Automation
         * @description Gone for the API and never due again; its runs stay as history.
         */
        delete: operations["delete_automation_api_automations__automation_id__delete"];
        options?: never;
        head?: never;
        /**
         * Update Automation
         * @description Its words or its schedule (its owner only; the kind stays).
         */
        patch: operations["update_automation_api_automations__automation_id__patch"];
        trace?: never;
    };
    "/api/automations/{automation_id}/firings": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Automation Log
         * @description Its terms, newest first: how each went and the run it started.
         */
        get: operations["automation_log_api_automations__automation_id__firings_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/automations/{automation_id}/pause": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Pause Automation */
        post: operations["pause_automation_api_automations__automation_id__pause_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/automations/{automation_id}/resume": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Resume Automation
         * @description Runs again (`paused_reason` cleared, failures counted anew).
         */
        post: operations["resume_automation_api_automations__automation_id__resume_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/automations/{automation_id}/run": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Run Automation Now
         * @description One term out of turn (its owner; not an event rule): `last_run` tells how it
         *     went (`started`, or why not, e.g. `skipped_busy`).
         */
        post: operations["run_automation_now_api_automations__automation_id__run_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/automations/{automation_id}/take-over": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Take Over Automation
         * @description The caller becomes its owner (who sees it and could make it); a paused one
         *     resumes.
         */
        post: operations["take_over_automation_api_automations__automation_id__take_over_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/backups": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Backups
         * @description The backups, newest first.
         */
        get: operations["list_backups_api_backups_get"];
        put?: never;
        /**
         * Start Backup
         * @description Back up now: a worker makes the backup; `backup.changed` tells its progress.
         *     409 `backup.already_running` while one runs or waits, `backup.busy` while another
         *     request is being handled.
         */
        post: operations["start_backup_api_backups_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/backups/archives": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Archives
         * @description The archives in the backups directory, newest first.
         */
        get: operations["list_archives_api_backups_archives_get"];
        put?: never;
        /**
         * Upload Archive
         * @description An archive from elsewhere, checked: 413 `backup.upload_too_large`, 422
         *     `backup.archive_invalid` with the problems.
         */
        post: operations["upload_archive_api_backups_archives_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/backups/archives/{name}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Download Archive */
        get: operations["download_archive_api_backups_archives__name__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/backups/archives/{name}/check": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Check Archive
         * @description The archive against this installation; `can_replace` when nothing blocks.
         */
        post: operations["check_archive_api_backups_archives__name__check_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/backups/archives/{name}/replace": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Replace Installation
         * @description Replace the whole installation with the archive (a safety archive first, then
         *     maintenance, then everyone signed out). 422 `backup.confirm_mismatch`, 409
         *     `backup.already_running`, `backup.busy`, `backup.restore_running`,
         *     `backup.replace_refused`.
         */
        post: operations["replace_installation_api_backups_archives__name__replace_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/backups/restore": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Restore Status
         * @description The last attempt to replace the installation from the administration.
         */
        get: operations["restore_status_api_backups_restore_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/calendars": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Calendars
         * @description The calendars of the spaces one belongs to (or open spaces one reads), the same
         *     for admins; another space's calendars only by naming it.
         */
        get: operations["list_calendars_api_calendars_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/calendars/{calendar_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        /**
         * Archive Calendar
         * @description Archives the calendar: out of every list, 404 by id.
         */
        delete: operations["archive_calendar_api_calendars__calendar_id__delete"];
        options?: never;
        head?: never;
        /** Update Calendar */
        patch: operations["update_calendar_api_calendars__calendar_id__patch"];
        trace?: never;
    };
    "/api/channels": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Channels
         * @description The channels of every space the caller may read, by name.
         */
        get: operations["list_channels_api_channels_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/conversations/unread": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Unread
         * @description Every conversation the caller sees with something unread, by id.
         */
        get: operations["list_unread_api_conversations_unread_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/conversations/{conversation_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Conversation */
        get: operations["get_conversation_api_conversations__conversation_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        /** Update Channel */
        patch: operations["update_channel_api_conversations__conversation_id__patch"];
        trace?: never;
    };
    "/api/conversations/{conversation_id}/archive": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Archive Channel */
        post: operations["archive_channel_api_conversations__conversation_id__archive_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/conversations/{conversation_id}/fresh-start": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Start Conversation Afresh
         * @description Start her DM alone with an agent afresh: its runs read nothing from before now
         *     (the personal mark of what came before ends for them); open runs are cancelled.
         *     403 `conversation.not_alone_with_agent` anywhere else.
         */
        post: operations["start_conversation_afresh_api_conversations__conversation_id__fresh_start_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/conversations/{conversation_id}/messages": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Messages
         * @description Top-level messages with their reply counts, newest first.
         */
        get: operations["list_messages_api_conversations__conversation_id__messages_get"];
        put?: never;
        /** Post Message */
        post: operations["post_message_api_conversations__conversation_id__messages_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/conversations/{conversation_id}/read": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Read Position
         * @description The caller's read position in the conversation (nulls before she read any).
         */
        get: operations["read_position_api_conversations__conversation_id__read_get"];
        put?: never;
        /**
         * Mark Read
         * @description Read up to a message of the conversation (never backwards).
         */
        post: operations["mark_read_api_conversations__conversation_id__read_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/conversations/{conversation_id}/unarchive": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Unarchive Channel */
        post: operations["unarchive_channel_api_conversations__conversation_id__unarchive_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/directory": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Search Directory */
        get: operations["search_directory_api_directory_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/dms": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Dms
         * @description The caller's direct messages, the most recently active first.
         */
        get: operations["list_dms_api_dms_get"];
        put?: never;
        /**
         * Open Dm
         * @description The caller's conversation with these people, or with an agent (`ai.use`): new
         *     (201) or the one they have.
         */
        post: operations["open_dm_api_dms_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/maintenance": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Maintenance State */
        get: operations["maintenance_state_api_maintenance_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/messages/{message_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Message
         * @description One message (a thread's parent, a link to a message), for whoever sees its
         *     conversation; 404 `message.not_found` for anyone else.
         */
        get: operations["get_message_api_messages__message_id__get"];
        put?: never;
        post?: never;
        /** Delete Message */
        delete: operations["delete_message_api_messages__message_id__delete"];
        options?: never;
        head?: never;
        /** Edit Message */
        patch: operations["edit_message_api_messages__message_id__patch"];
        trace?: never;
    };
    "/api/messages/{message_id}/reactions/{emoji}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        /**
         * React
         * @description Add the caller's reaction (again: no change); the message's reactions.
         */
        put: operations["react_api_messages__message_id__reactions__emoji__put"];
        post?: never;
        /**
         * Unreact
         * @description Take the caller's reaction back (none: no change); the message's reactions.
         */
        delete: operations["unreact_api_messages__message_id__reactions__emoji__delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/messages/{message_id}/replies": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Replies
         * @description The message's thread, oldest first.
         */
        get: operations["list_replies_api_messages__message_id__replies_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/pages/{page_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Page */
        get: operations["get_page_api_pages__page_id__get"];
        put?: never;
        post?: never;
        /**
         * Purge Page
         * @description Delete a page in the trash for good, with everything below it (system admins).
         */
        delete: operations["purge_page_api_pages__page_id__delete"];
        options?: never;
        head?: never;
        /** Update Page */
        patch: operations["update_page_api_pages__page_id__patch"];
        trace?: never;
    };
    "/api/pages/{page_id}/ai-lock": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        /**
         * Set Page Ai Lock
         * @description `page.moderate` in its space; the page's `version` (stale → 409).
         */
        put: operations["set_page_ai_lock_api_pages__page_id__ai_lock_put"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/pages/{page_id}/attachments": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Attachments */
        get: operations["list_attachments_api_pages__page_id__attachments_get"];
        put?: never;
        /**
         * Upload Attachment
         * @description Upload a file (`page.edit`): PNG, JPEG, GIF, WebP, PDF, TXT, Markdown, CSV, JSON,
         *     DOCX, XLSX, PPTX or ZIP, decided by the content; 415 otherwise or when the name's
         *     extension does not fit it; 413 over the size limit.
         */
        post: operations["upload_attachment_api_pages__page_id__attachments_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/pages/{page_id}/diff": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Diff Versions */
        get: operations["diff_versions_api_pages__page_id__diff_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/pages/{page_id}/export": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Export Page */
        get: operations["export_page_api_pages__page_id__export_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/pages/{page_id}/move": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Move Page */
        post: operations["move_page_api_pages__page_id__move_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/pages/{page_id}/publish": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Publish Page */
        post: operations["publish_page_api_pages__page_id__publish_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/pages/{page_id}/restore": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Restore Page */
        post: operations["restore_page_api_pages__page_id__restore_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/pages/{page_id}/reviewed": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Mark Page Reviewed
         * @description Mark a published page as reviewed now (`page.edit`); takes and bumps no version.
         */
        post: operations["mark_page_reviewed_api_pages__page_id__reviewed_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/pages/{page_id}/tags": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        /**
         * Set Page Tags
         * @description Replace the page's tags (`page.edit`); bumps the page version.
         */
        put: operations["set_page_tags_api_pages__page_id__tags_put"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/pages/{page_id}/thread": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Page Thread
         * @description The page's discussion (created on first access), for whoever sees the page;
         *     its messages come from `/conversations/{id}/messages`.
         */
        get: operations["get_page_thread_api_pages__page_id__thread_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/pages/{page_id}/tickets": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Page Tickets
         * @description The tickets linking the page that the caller may see, newest first.
         */
        get: operations["list_page_tickets_api_pages__page_id__tickets_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/pages/{page_id}/trash": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Trash Page */
        post: operations["trash_page_api_pages__page_id__trash_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/pages/{page_id}/versions": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Versions */
        get: operations["list_versions_api_pages__page_id__versions_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/pages/{page_id}/versions/{number}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Version */
        get: operations["get_version_api_pages__page_id__versions__number__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        /** Label Version */
        patch: operations["label_version_api_pages__page_id__versions__number__patch"];
        trace?: never;
    };
    "/api/pages/{page_id}/versions/{number}/restore": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Restore Version */
        post: operations["restore_version_api_pages__page_id__versions__number__restore_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/proposals/{proposal_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Proposal */
        get: operations["get_proposal_api_proposals__proposal_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/proposals/{proposal_id}/accept": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Accept Proposal
         * @description 409 `proposal.base_outdated` when the page moved on (see the merge in the
         *     error's `details`); accept again with `merged_content` and `page_version`.
         */
        post: operations["accept_proposal_api_proposals__proposal_id__accept_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/proposals/{proposal_id}/reject": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Reject Proposal */
        post: operations["reject_proposal_api_proposals__proposal_id__reject_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/questions/{question_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Question */
        get: operations["get_question_api_questions__question_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/questions/{question_id}/answer": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Answer Question */
        post: operations["answer_question_api_questions__question_id__answer_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/runs": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * My Runs
         * @description The runs the caller asked for, newest first (`ai.use` or `agent.manage`).
         */
        get: operations["my_runs_api_runs_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/runs/{run_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Run */
        get: operations["get_run_api_runs__run_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/runs/{run_id}/cancel": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Cancel Run
         * @description Stop the run (once; asking again answers the same); 409 `run.finished` if it
         *     ended otherwise.
         */
        post: operations["cancel_run_api_runs__run_id__cancel_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/runs/{run_id}/events": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Run Events */
        get: operations["run_events_api_runs__run_id__events_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/search": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Search
         * @description Pages, messages and tickets the caller may see, best first; empty `q` gives an
         *     empty list. Tags narrow to pages and tickets.
         */
        get: operations["search_api_search_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/skill-proposals": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Skill Proposals
         * @description Newest first: those the caller may decide, and their own.
         */
        get: operations["list_skill_proposals_api_skill_proposals_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/skill-proposals/{proposal_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Skill Proposal */
        get: operations["get_skill_proposal_api_skill_proposals__proposal_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/skill-proposals/{proposal_id}/accept": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Accept Skill Proposal
         * @description 403 unless the caller may manage skills in its scope; 409
         *     `skill_proposal.not_open`, `skill_proposal.version_conflict`,
         *     `skill_proposal.base_outdated` (the skill moved on: `details` holds its `version`
         *     and both texts; accept again with `skill_version`), `skill_proposal.skill_archived`,
         *     `skill.name_taken`.
         */
        post: operations["accept_skill_proposal_api_skill_proposals__proposal_id__accept_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/skill-proposals/{proposal_id}/reject": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Reject Skill Proposal */
        post: operations["reject_skill_proposal_api_skill_proposals__proposal_id__reject_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/skills": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Skills
         * @description By name: organisation-wide skills and those of the spaces the caller reads.
         */
        get: operations["list_skills_api_skills_get"];
        put?: never;
        /**
         * Create Skill
         * @description Organisation-wide: `skill.manage`; in a space: `page.moderate` there. 409
         *     `skill.name_taken` when the scope has a skill of that name (archived included).
         */
        post: operations["create_skill_api_skills_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/skills/import": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Import Skills
         * @description Skills from a SKILL.md or a ZIP of skill folders (`skill.manage`, or
         *     `page.moderate` in the space); 413 `import.too_large` over 10 MB or the archive's
         *     limits, 422 `import.invalid_zip` for a broken ZIP. Each skill is reported.
         */
        post: operations["import_skills_api_skills_import_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/skills/{skill_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Skill */
        get: operations["get_skill_api_skills__skill_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        /**
         * Update Skill
         * @description A change of description or content makes a new version.
         */
        patch: operations["update_skill_api_skills__skill_id__patch"];
        trace?: never;
    };
    "/api/skills/{skill_id}/archive": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Archive Skill
         * @description No run uses an archived skill; 409 `skill.state_conflict` if it is archived.
         */
        post: operations["archive_skill_api_skills__skill_id__archive_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/skills/{skill_id}/export": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Export Skill
         * @description The skill's SKILL.md.
         */
        get: operations["export_skill_api_skills__skill_id__export_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/skills/{skill_id}/unarchive": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Unarchive Skill */
        post: operations["unarchive_skill_api_skills__skill_id__unarchive_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/skills/{skill_id}/versions": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Skill Versions
         * @description Newest first, without their text.
         */
        get: operations["list_skill_versions_api_skills__skill_id__versions_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/skills/{skill_id}/versions/{number}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Skill Version */
        get: operations["get_skill_version_api_skills__skill_id__versions__number__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/skills/{skill_id}/versions/{number}/restore": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Restore Skill Version
         * @description A new version with that version's description and content.
         */
        post: operations["restore_skill_version_api_skills__skill_id__versions__number__restore_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/spaces": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Spaces */
        get: operations["list_spaces_api_spaces_get"];
        put?: never;
        /** Create Space */
        post: operations["create_space_api_spaces_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/spaces/{space_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Space */
        get: operations["get_space_api_spaces__space_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        /** Update Space */
        patch: operations["update_space_api_spaces__space_id__patch"];
        trace?: never;
    };
    "/api/spaces/{space_id}/automations": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Automations Of Space
         * @description The automations at places in the space that the caller may see.
         */
        get: operations["automations_of_space_api_spaces__space_id__automations_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/spaces/{space_id}/board": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Board
         * @description The space's statuses in order, each with its count and first tickets; with
         *     `group_by=assignee` (the daily view) a row per person instead, `limit` tickets per
         *     cell (20 unless asked, at most 20, else 422).
         */
        get: operations["board_api_spaces__space_id__board_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/spaces/{space_id}/board/{status_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Board Column
         * @description More of one column, in board order (the column's `next_cursor`).
         */
        get: operations["board_column_api_spaces__space_id__board__status_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/spaces/{space_id}/calendars": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Space Calendars */
        get: operations["list_space_calendars_api_spaces__space_id__calendars_get"];
        put?: never;
        /** Create Calendar */
        post: operations["create_calendar_api_spaces__space_id__calendars_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/spaces/{space_id}/channels": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Space Channels */
        get: operations["list_space_channels_api_spaces__space_id__channels_get"];
        put?: never;
        /** Create Channel */
        post: operations["create_channel_api_spaces__space_id__channels_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/spaces/{space_id}/epics": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Epics
         * @description The space's epics, newest first, with their progress; an epic's children come
         *     from the list (`parent`).
         */
        get: operations["epics_api_spaces__space_id__epics_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/spaces/{space_id}/export": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Export Space
         * @description The pages the caller may read (drafts with `page.edit`) and their attachments.
         */
        get: operations["export_space_api_spaces__space_id__export_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/spaces/{space_id}/import": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Import Space
         * @description Pages from a Markdown ZIP (`space.manage`); 413 `import.too_large` over 2,000
         *     entries or 200 MB unpacked, 422 `import.invalid_zip` for anything else.
         */
        post: operations["import_space_api_spaces__space_id__import_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/spaces/{space_id}/members": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Space Members */
        get: operations["list_space_members_api_spaces__space_id__members_get"];
        /** Set Space Member */
        put: operations["set_space_member_api_spaces__space_id__members_put"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/spaces/{space_id}/members/{member_type}/{member_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        /** Remove Space Member */
        delete: operations["remove_space_member_api_spaces__space_id__members__member_type___member_id__delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/spaces/{space_id}/pages": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Create Page */
        post: operations["create_page_api_spaces__space_id__pages_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/spaces/{space_id}/pages/by-path": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Page By Path */
        get: operations["page_by_path_api_spaces__space_id__pages_by_path_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/spaces/{space_id}/pages/tree": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Page Tree */
        get: operations["page_tree_api_spaces__space_id__pages_tree_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/spaces/{space_id}/proposals": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Proposals
         * @description Newest first: those of the space the caller may see (page editors, and an
         *     author their own).
         */
        get: operations["list_proposals_api_spaces__space_id__proposals_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/spaces/{space_id}/sprints": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Sprints
         * @description The space's sprints: the active one, then the planned ones (earliest start
         *     first), then the closed ones (latest end first); `state` narrows them.
         */
        get: operations["list_sprints_api_spaces__space_id__sprints_get"];
        put?: never;
        /** Create Sprint */
        post: operations["create_sprint_api_spaces__space_id__sprints_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/spaces/{space_id}/ticket-statuses": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Statuses
         * @description The space's statuses in order.
         */
        get: operations["list_statuses_api_spaces__space_id__ticket_statuses_get"];
        put?: never;
        /** Create Status */
        post: operations["create_status_api_spaces__space_id__ticket_statuses_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/spaces/{space_id}/tickets": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Create Ticket */
        post: operations["create_ticket_api_spaces__space_id__tickets_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/spaces/{space_id}/trash": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Trash */
        get: operations["list_trash_api_spaces__space_id__trash_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/sprints/{sprint_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        /** Update Sprint */
        patch: operations["update_sprint_api_sprints__sprint_id__patch"];
        trace?: never;
    };
    "/api/sprints/{sprint_id}/close": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Close Sprint
         * @description Active → closed: unfinished tickets go to the next planned sprint or the
         *     backlog; the sprint keeps its tally.
         */
        post: operations["close_sprint_api_sprints__sprint_id__close_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/sprints/{sprint_id}/start": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Start Sprint
         * @description Planned → active; 409 `sprint.active_exists` while the space has an active one.
         */
        post: operations["start_sprint_api_sprints__sprint_id__start_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/stream": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Stream */
        get: operations["stream_api_stream_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/tags": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Tags */
        get: operations["list_tags_api_tags_get"];
        put?: never;
        /** Create Tag */
        post: operations["create_tag_api_tags_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/tags/{tag_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        /**
         * Delete Tag
         * @description Also takes the tag off everything that carries it.
         */
        delete: operations["delete_tag_api_tags__tag_id__delete"];
        options?: never;
        head?: never;
        /** Update Tag */
        patch: operations["update_tag_api_tags__tag_id__patch"];
        trace?: never;
    };
    "/api/ticket-statuses/{status_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        /** Delete Status */
        delete: operations["delete_status_api_ticket_statuses__status_id__delete"];
        options?: never;
        head?: never;
        /** Update Status */
        patch: operations["update_status_api_ticket_statuses__status_id__patch"];
        trace?: never;
    };
    "/api/tickets": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Tickets
         * @description The tickets of every space where the caller may read them.
         */
        get: operations["list_tickets_api_tickets_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/tickets/counts": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Counts */
        get: operations["counts_api_tickets_counts_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/tickets/my-board": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get My Board
         * @description My tickets of every space where I may read tickets, by status category.
         */
        get: operations["get_my_board_api_tickets_my_board_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/tickets/my-board/{category}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * My Board Column
         * @description More of one column (its `next_cursor`); `open`, `active`, `review` or `done`.
         */
        get: operations["my_board_column_api_tickets_my_board__category__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/tickets/{number}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Ticket */
        get: operations["get_ticket_api_tickets__number__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        /** Update Ticket */
        patch: operations["update_ticket_api_tickets__number__patch"];
        trace?: never;
    };
    "/api/tickets/{number}/move-category": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Move Category
         * @description Into the first status of the category in the ticket's own space (`ticket.edit`).
         */
        post: operations["move_category_api_tickets__number__move_category_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/tickets/{number}/pages": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Ticket Pages
         * @description The pages the ticket links that the caller sees, last linked first.
         */
        get: operations["list_ticket_pages_api_tickets__number__pages_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/tickets/{number}/pages/{page_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        /**
         * Link Page
         * @description Link a page the caller sees, of any space (`ticket.edit`); linking again
         *     changes nothing.
         */
        put: operations["link_page_api_tickets__number__pages__page_id__put"];
        post?: never;
        /**
         * Unlink Page
         * @description Remove the link to a page the caller sees (`ticket.edit`); 204 also when there
         *     was none.
         */
        delete: operations["unlink_page_api_tickets__number__pages__page_id__delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/tickets/{number}/tags": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        /**
         * Set Ticket Tags
         * @description Replace the ticket's tags (`ticket.edit`); bumps the ticket version.
         */
        put: operations["set_ticket_tags_api_tickets__number__tags_put"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/tickets/{number}/thread": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Ticket Thread
         * @description The ticket's thread (made with the ticket), for whoever sees the ticket; its
         *     messages, the system timeline among them, come from
         *     `/conversations/{id}/messages`.
         */
        get: operations["get_ticket_thread_api_tickets__number__thread_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/tokens": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List My Tokens
         * @description My tokens, newest first (revoked and expired ones too).
         */
        get: operations["list_my_tokens_api_tokens_get"];
        put?: never;
        /**
         * Create Token
         * @description A new token; `secret` is its clear text, shown this once.
         */
        post: operations["create_token_api_tokens_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/tokens/{token_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        /** Revoke My Token */
        delete: operations["revoke_my_token_api_tokens__token_id__delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/tokens/{token_id}/calls": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List My Token Calls
         * @description The token's tool calls through `/mcp`, newest first (its usage).
         */
        get: operations["list_my_token_calls_api_tokens__token_id__calls_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
}
export type webhooks = Record<string, never>;
export interface components {
    schemas: {
        /**
         * AbilitiesOut
         * @description What the caller may do with it now (`abilities.py`): the same rules the actions
         *     enforce.
         */
        AbilitiesOut: {
            /** Delete */
            delete: boolean;
            /** Edit */
            edit: boolean;
            /** Pause */
            pause: boolean;
            /** Resume */
            resume: boolean;
            /** Run */
            run: boolean;
            /** Take Over */
            take_over: boolean;
        };
        /**
         * Action
         * @enum {string}
         */
        Action: "space.read" | "space.manage" | "page.create" | "page.edit" | "page.publish" | "page.trash" | "page.moderate" | "channel.post" | "channel.manage" | "ticket.read" | "ticket.create" | "ticket.edit" | "ticket.assign" | "calendar.read" | "calendar.write" | "calendar.moderate" | "space.create" | "directory.read" | "user.manage" | "group.manage" | "audit.read" | "page.purge" | "tag.manage" | "dm.inspect" | "ai.manage" | "agent.manage" | "skill.manage" | "backup.manage" | "calendar.manage" | "ai.use" | "agent.create_personal" | "mcp.use" | "calendar.sync";
        /**
         * ActivityAccount
         * @description The self-registered account a `signup` notification is about (plan M9 task 5b;
         *     its address: the user administration's waiting accounts); the account is also the
         *     entry's `author`. `awaiting`: whether it still waits for approval.
         */
        ActivityAccount: {
            /** Awaiting */
            awaiting: boolean;
            /**
             * Id
             * Format: uuid
             */
            id: string;
        };
        /** ActivityAuthor */
        ActivityAuthor: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Name */
            name: string;
            type: components["schemas"]["PrincipalType"];
        };
        /**
         * ActivityAutomation
         * @description The automation a notification is about (it was paused: plan M7); its agent is
         *     the entry's `author`; `paused_reason` why it is paused now (`owner`, `failing`,
         *     `manual`), null once it runs again.
         */
        ActivityAutomation: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Paused Reason */
            paused_reason: string | null;
        };
        /**
         * ActivityConversation
         * @description `name` is null for a direct message and a page or ticket thread; `page_id` names
         *     a page thread's page, `ticket_number` a ticket thread's ticket (null for other
         *     kinds; the ticket's address is `/tickets/<number>`).
         */
        ActivityConversation: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            kind: components["schemas"]["ConversationKind"];
            /** Name */
            name: string | null;
            /** Page Id */
            page_id: string | null;
            /** Space Id */
            space_id: string | null;
            /** Ticket Number */
            ticket_number: number | null;
        };
        /**
         * ActivityCountOut
         * @description `open`: not done; `unread`: not done and not read (the badge).
         */
        ActivityCountOut: {
            /** Open */
            open: number;
            /** Unread */
            unread: number;
        };
        /**
         * ActivityOut
         * @description A notification: why, where, from whom, and the first 140 characters of the
         *     message's Markdown. `parent_id`: the thread the message is in (null: top level).
         *     `read_at`/`done_at`: null until marked. An `assignment` points at a timeline entry:
         *     `author` is who assigned, `snippet` is empty. A `proposal` for a new page at the top
         *     level has no conversation and no message, but `proposal` (plan M6); a
         *     `skill_proposal` has `skill_proposal` instead (plan M6 task 9), an `automation`
         *     the automation (plan M7), a `signup` the waiting account (plan M9); `author` may be
         *     an agent (`type`).
         */
        ActivityOut: {
            account?: components["schemas"]["ActivityAccount"] | null;
            author: components["schemas"]["ActivityAuthor"] | null;
            automation?: components["schemas"]["ActivityAutomation"] | null;
            conversation: components["schemas"]["ActivityConversation"] | null;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /** Done At */
            done_at: string | null;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Message Id */
            message_id: string | null;
            /** Parent Id */
            parent_id: string | null;
            proposal?: components["schemas"]["ActivityProposal"] | null;
            /** Read At */
            read_at: string | null;
            reason: components["schemas"]["NotificationReason"];
            skill_proposal?: components["schemas"]["ActivitySkillProposal"] | null;
            /** Snippet */
            snippet: string;
        };
        /**
         * ActivityProposal
         * @description The proposal a notification is about when it has no thread to point at (a new
         *     page at the top level; its address: the space's proposals).
         */
        ActivityProposal: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Space Id
             * Format: uuid
             */
            space_id: string;
        };
        /**
         * ActivitySkillProposal
         * @description The skill proposal a notification is about (a skill has no thread; its address:
         *     `/api/skill-proposals/{id}`); `space_id` none: organisation-wide.
         */
        ActivitySkillProposal: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Space Id */
            space_id: string | null;
        };
        /**
         * AdminTokenOut
         * @description A token in the admins' list: its metadata and whose it is (`user`: its person;
         *     for an agent token the agent's responsible person, and `agent` the agent).
         */
        AdminTokenOut: {
            agent?: components["schemas"]["TokenAgentOut"] | null;
            /** Agent Id */
            agent_id?: string | null;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /**
             * Expires At
             * Format: date-time
             */
            expires_at: string;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            kind: components["schemas"]["TokenKind"];
            /** Last Used At */
            last_used_at: string | null;
            mode: components["schemas"]["TokenMode"];
            /** Name */
            name: string;
            /** Revoked At */
            revoked_at: string | null;
            /** Space Ids */
            space_ids: string[] | null;
            user: components["schemas"]["TokenUserOut"];
        };
        /**
         * AdminUserOut
         * @description A person as the people administration lists them: with whether TOTP is on.
         */
        AdminUserOut: {
            /** Awaiting Approval Since */
            awaiting_approval_since: string | null;
            /** Email */
            email: string;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Is Active */
            is_active: boolean;
            /** Last Login At */
            last_login_at: string | null;
            /** Locale */
            locale: string;
            /** Name */
            name: string;
            system_role: components["schemas"]["SystemRole"];
            /** Totp Enabled */
            totp_enabled: boolean;
            /** Version */
            version: number;
        };
        /**
         * AgentCreate
         * @description `connection_id`/`model`: a chat connection of the organisation and one of its
         *     models. `responsible_user_id`: an active person (no guest) who answers for it.
         *     Both are needed for the organisation's agents (`agent.manage`). `personal`: the
         *     caller's own agent (`agent.create_personal`), which takes the caller's connection
         *     and model and has the caller as responsible person (given, they must be those).
         *     `kind: external` (plan M8 decision 11, `agent.manage`): an agent that works from
         *     outside through `/mcp`; no connection, no model, not personal, level at most 2
         *     (else 422 `agent.external_invalid`), a responsible person required.
         */
        AgentCreate: {
            /** Connection Id */
            connection_id?: string | null;
            /**
             * Instructions
             * @default
             */
            instructions?: string;
            /**
             * Intro
             * @default
             */
            intro?: string;
            /** @default internal */
            kind?: components["schemas"]["AgentKind"];
            /**
             * Level
             * @description autonomy level (spec 8.2); above 2: admins
             * @default 2
             */
            level?: number;
            /**
             * Max Runtime Seconds
             * @description seconds
             * @default 600
             */
            max_runtime_seconds?: number;
            /**
             * Max Steps
             * @default 25
             */
            max_steps?: number;
            /** Model */
            model?: string | null;
            /** Name */
            name: string;
            /**
             * Personal
             * @default false
             */
            personal?: boolean;
            /** Responsible User Id */
            responsible_user_id?: string | null;
            /** @default draft */
            status?: components["schemas"]["AgentStatus"];
        };
        /**
         * AgentExternalToolOut
         * @description What an external tool is (plan M8 decision 8): its server and its name there;
         *     `usable`: approved, unchanged and on an enabled server (else a run never gets it,
         *     whatever the entry says). `left_out`: granted and usable, but left out of every
         *     model call by the bound on all of the agent's external tool definitions (module
         *     review M8 2, finding G5): the tools listed first come first.
         */
        AgentExternalToolOut: {
            /**
             * Left Out
             * @default false
             */
            left_out?: boolean;
            /**
             * Server Id
             * Format: uuid
             */
            server_id: string;
            /** Server Name */
            server_name: string;
            /**
             * Tool Id
             * Format: uuid
             */
            tool_id: string;
            /** Tool Name */
            tool_name: string;
            /** Usable */
            usable: boolean;
        };
        /**
         * AgentKind
         * @enum {string}
         */
        AgentKind: "internal" | "external";
        /**
         * AgentOut
         * @description An agent as those who manage it see it (`agent.manage`; a personal agent's
         *     owner); `responsible_name`: the responsible person's name; `owner_user_id`: a
         *     personal agent's owner (null: the organisation's). `kind`: `external` for an
         *     agent that works from outside through `/mcp` (plan M8): no connection or model
         *     (both null).
         */
        AgentOut: {
            /** Connection Id */
            connection_id: string | null;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Instructions */
            instructions: string;
            /** Intro */
            intro: string;
            kind: components["schemas"]["AgentKind"];
            /** Level */
            level: number;
            /** Max Runtime Seconds */
            max_runtime_seconds: number;
            /** Max Steps */
            max_steps: number;
            /** Model */
            model: string | null;
            /** Name */
            name: string;
            /** Owner User Id */
            owner_user_id: string | null;
            /** Responsible Name */
            responsible_name: string | null;
            /**
             * Responsible User Id
             * Format: uuid
             */
            responsible_user_id: string;
            status: components["schemas"]["AgentStatus"];
            /**
             * Updated At
             * Format: date-time
             */
            updated_at: string;
            /** Version */
            version: number;
        };
        /**
         * AgentPickOut
         * @description An agent to set a budget for.
         */
        AgentPickOut: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Name */
            name: string;
        };
        /**
         * AgentProfileOut
         * @description What a person with `ai.use` learns of an agent to talk to: no instructions, no
         *     connection. `kind`: `external` for one that works from outside (plan M8): it
         *     answers no message here.
         */
        AgentProfileOut: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Intro */
            intro: string;
            kind: components["schemas"]["AgentKind"];
            /** Name */
            name: string;
            status: components["schemas"]["AgentStatus"];
        };
        /**
         * AgentRunOut
         * @description What a message to an agent started: its run (`id`; possibly one already waiting,
         *     which answers this message too), or no run and why (`reason`: `ai.unavailable`,
         *     `agent.draft`, `agent.paused`, `agent.responsible_inactive`,
         *     `agent.connection_unavailable`, `run.thread_reply`, `run.waiting`). `agent_id`:
         *     the agent it asked (the DM's, or the one a mention named).
         */
        AgentRunOut: {
            /** Agent Id */
            agent_id?: string | null;
            /** Id */
            id: string | null;
            /** Reason */
            reason: string | null;
        };
        /**
         * AgentSkillOut
         * @description `available`: whether the agent may use it now (active, and organisation-wide or
         *     of a space the agent reads); a run also needs the person and the place to read it.
         */
        AgentSkillOut: {
            author: components["schemas"]["SkillAuthorOut"];
            /** Available */
            available: boolean;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /** Description */
            description: string;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Name */
            name: string;
            /** Space Id */
            space_id: string | null;
            state: components["schemas"]["SkillState"];
            /**
             * Updated At
             * Format: date-time
             */
            updated_at: string;
            /** Version */
            version: number;
        };
        /**
         * AgentSkillsOut
         * @description `version`: the agent's (setting the skills changes it).
         */
        AgentSkillsOut: {
            /** Skills */
            skills: components["schemas"]["AgentSkillOut"][];
            /** Version */
            version: number;
        };
        /** AgentSkillsPut */
        AgentSkillsPut: {
            /** Skill Ids */
            skill_ids: string[];
            /** Version */
            version: number;
        };
        /**
         * AgentSpaceOut
         * @description A space the agent is a member of, with its `role` there.
         */
        AgentSpaceOut: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            kind: components["schemas"]["SpaceKind"];
            /** Name */
            name: string;
            role: components["schemas"]["SpaceRole"];
        };
        /**
         * AgentStatus
         * @enum {string}
         */
        AgentStatus: "draft" | "active" | "paused";
        /** AgentToolEntry */
        AgentToolEntry: {
            policy: components["schemas"]["Grant"];
            /** Tool */
            tool: string;
        };
        /**
         * AgentToolOut
         * @description One tool for this agent: its own `level` (the lowest that allows it) and
         *     `effect`; `default` (from the agent's level; an external tool's is `block`: it
         *     needs an entry), `entry` (the agent's, or null) and `effective` (what a run gets).
         *     `external`: set for an external MCP server's tool (name `ext_…`; a write tool is
         *     level 4 and at most `confirm`), null for the catalog's. `via_mcp`: only for an
         *     external agent (plan M8): the catalog tool can reach its token over `/mcp` (offered
         *     there, level 2 at most); false for every other agent and tool.
         */
        AgentToolOut: {
            default: components["schemas"]["Grant"];
            effect: components["schemas"]["Effect"];
            effective: components["schemas"]["Grant"];
            entry: components["schemas"]["Grant"] | null;
            external?: components["schemas"]["AgentExternalToolOut"] | null;
            /** Level */
            level: number;
            /** Name */
            name: string;
            /**
             * Via Mcp
             * @default false
             */
            via_mcp?: boolean;
        };
        /**
         * AgentToolsOut
         * @description An agent's tool grants: every tool of the catalog (a fixed, short list, so not
         *     paged), then the organisation's usable external tools and those with an entry
         *     (approved ones only, at most `mcp_servers/tools.MAX_APPROVED_TOOLS` of them, plus at
         *     most 100 entries: a hard cap instead of pages, as the list is one versioned
         *     document the PUT replaces whole). `version`: the agent's.
         *     `max_level`: the highest level the caller may give the agent (above 2: admins
         *     only).
         */
        AgentToolsOut: {
            /**
             * Agent Id
             * Format: uuid
             */
            agent_id: string;
            /** Level */
            level: number;
            /** Max Level */
            max_level: number;
            /** Tools */
            tools: components["schemas"]["AgentToolOut"][];
            /** Version */
            version: number;
        };
        /**
         * AgentToolsPut
         * @description All of the agent's entries (those left out are removed); each can only tighten
         *     what the level allows. With the agent's `version`.
         */
        AgentToolsPut: {
            /** Tools */
            tools: components["schemas"]["AgentToolEntry"][];
            /** Version */
            version: number;
        };
        /**
         * AgentUpdate
         * @description Fields left out stay as they are; `connection_id` and `model` go together. A
         *     personal agent takes its owner's connection and model anew with every change. The
         *     kind stays; an external agent takes no connection or model and no level above 2
         *     (422 `agent.external_invalid`).
         */
        AgentUpdate: {
            /** Connection Id */
            connection_id?: string | null;
            /** Instructions */
            instructions?: string | null;
            /** Intro */
            intro?: string | null;
            /** Level */
            level?: number | null;
            /** Max Runtime Seconds */
            max_runtime_seconds?: number | null;
            /** Max Steps */
            max_steps?: number | null;
            /** Model */
            model?: string | null;
            /** Name */
            name?: string | null;
            /** Responsible User Id */
            responsible_user_id?: string | null;
            status?: components["schemas"]["AgentStatus"] | null;
            /** Version */
            version: number;
        };
        /**
         * AgentWritePolicy
         * @description How agents write pages in a space (plan M6 decision 8).
         * @enum {string}
         */
        AgentWritePolicy: "propose" | "direct";
        /**
         * AiLockIn
         * @description Lock a page or a file for AI, or lift the lock; `version` as read (stale → 409).
         */
        AiLockIn: {
            /** No Ai */
            no_ai: boolean;
            /** Version */
            version: number;
        };
        /**
         * AiPolicy
         * @description A space's AI policy (spec 7.3), stored on `space` (`modules/ai/policy.py`).
         * @enum {string}
         */
        AiPolicy: "any" | "restricted" | "none";
        /**
         * ApprovalDecide
         * @description `approve` or `reject`; `reason` goes to the model (as untrusted text) on a
         *     rejection; `version`: the approval's, as read.
         */
        ApprovalDecide: {
            /**
             * Decision
             * @enum {string}
             */
            decision: "approve" | "reject";
            /** Reason */
            reason?: string | null;
            /** Version */
            version: number;
        };
        /**
         * ApprovalExternalOut
         * @description The external MCP server and tool an approval's call goes to (plan M8 decision
         *     8); their names are in `summary` ("<server> · <tool>").
         */
        ApprovalExternalOut: {
            /**
             * Server Id
             * Format: uuid
             */
            server_id: string;
            /**
             * Tool Id
             * Format: uuid
             */
            tool_id: string;
        };
        /**
         * ApprovalOut
         * @description A tool call waiting for (or given) a person's release. `summary`: the tool and
         *     what the system resolved of the call's arguments (a ticket's key, a status's name,
         *     the ids of what it changes; never a text the model chose), or for an external
         *     tool its server and tool; only for the person asked (null for others, module
         *     review M8 5, L1). `args`: the call's arguments, only for the person asked
         *     (null for others). `diff_url`: for a page's new content, where that person reads
         *     the diff against the page as it is now (`GET`), instead of the text. `step` and
         *     `call_id`: the call it waits for, as the run's journal names it (the step a run
         *     link points at). `outcome`: what became of the call once released: `ran`, or
         *     `stale` (what it would change had changed, so nothing ran); null before.
         *     `reason`: the person's reason for a rejection, and `args`, only for the person
         *     asked; for everyone else both are null and `redacted` is true (as in the run
         *     view, review M6 finding 6). `external`: for a call of an external tool (it sends
         *     `args` to that server once released), else null. `personal`: asked because the
         *     run carries the asker's personal mark (every release then but a message into its
         *     DM alone with her): what is released is written (or sent) where others can read
         *     it now or later (module review M8 2; M8 5, L2). `reads`: the call only reads (a
         *     catalog tool that writes nothing); under the mark its card says so instead of
         *     that others can read what is released.
         */
        ApprovalOut: {
            /**
             * Addressed To
             * Format: uuid
             */
            addressed_to: string;
            /** Args */
            args: {
                [key: string]: unknown;
            } | null;
            /** Call Id */
            call_id: string;
            /**
             * Conversation Id
             * Format: uuid
             */
            conversation_id: string;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /** Decided At */
            decided_at: string | null;
            /** Decided By */
            decided_by: string | null;
            /** Diff Url */
            diff_url: string | null;
            /**
             * Expires At
             * Format: date-time
             */
            expires_at: string;
            external: components["schemas"]["ApprovalExternalOut"] | null;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Message Id */
            message_id: string | null;
            outcome: components["schemas"]["ApprovalOutcome"] | null;
            /**
             * Personal
             * @default false
             */
            personal?: boolean;
            /**
             * Reads
             * @default false
             */
            reads?: boolean;
            /** Reason */
            reason: string | null;
            /** Redacted */
            redacted: boolean;
            /**
             * Run Id
             * Format: uuid
             */
            run_id: string;
            state: components["schemas"]["ApprovalState"];
            /** Step */
            step: number;
            /** Summary */
            summary: string | null;
            /** Tool */
            tool: string;
            /** Version */
            version: number;
        };
        /**
         * ApprovalOutcome
         * @enum {string}
         */
        ApprovalOutcome: "ran" | "stale" | "failed";
        /**
         * ApprovalState
         * @enum {string}
         */
        ApprovalState: "pending" | "approved" | "rejected" | "expired";
        /**
         * ArchiveCheckOut
         * @description `problems`: codes, any one blocks replacing (`can_replace` false); `key`:
         *     whether HERD_SECRET_KEY fits the archive's `enc:` values.
         */
        ArchiveCheckOut: {
            archive: components["schemas"]["FiguresOut"] | null;
            /** Archive Name */
            archive_name: string;
            /** Can Replace */
            can_replace: boolean;
            /** Created At */
            created_at: string | null;
            installation: components["schemas"]["FiguresOut"] | null;
            /** Key */
            key: ("match" | "mismatch" | "missing" | "not_needed") | null;
            /** Problems */
            problems: string[];
            /** Warnings */
            warnings: string[];
        };
        /**
         * ArchiveOut
         * @description An archive in the backups directory; `uploaded`: an owner uploaded it.
         */
        ArchiveOut: {
            /** Bytes */
            bytes: number;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /** Name */
            name: string;
            /** Uploaded */
            uploaded: boolean;
        };
        /**
         * AssigneeIn
         * @description A person, or (plan M6 decision 7) an agent: assigning an agent needs `ai.use`
         *     and `ticket.assign`, and starts its work on the ticket.
         */
        AssigneeIn: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Type
             * @enum {string}
             */
            type: "user" | "agent";
        };
        /**
         * AssignmentsOut
         * @description The standard assignment and whether people with `ai.use` may create personal
         *     agents; `version` guards both and the group list.
         */
        AssignmentsOut: {
            default: components["schemas"]["TargetOut"] | null;
            /** Personal Agents */
            personal_agents: boolean;
            /** Version */
            version: number;
        };
        /**
         * AttachmentOut
         * @description `url` downloads it (`?inline=1` shows raster images in the page). `mime` is what
         *     the content is, whatever the upload declared. `no_ai`: locked for AI (spec 11);
         *     `version` guards that lock.
         */
        AttachmentOut: {
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /** Filename */
            filename: string;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Mime */
            mime: string;
            /** No Ai */
            no_ai: boolean;
            /**
             * Page Id
             * Format: uuid
             */
            page_id: string;
            /** Sha256 */
            sha256: string;
            /** Size */
            size: number;
            uploaded_by: components["schemas"]["PrincipalRef"];
            /** Url */
            url: string;
            /** Version */
            version: number;
        };
        /**
         * AuditOut
         * @description `actor_name`: the acting person's display name (None for other principals).
         */
        AuditOut: {
            /** Action */
            action: string;
            /**
             * Actor Id
             * Format: uuid
             */
            actor_id: string;
            /** Actor Name */
            actor_name: string | null;
            /** Actor Type */
            actor_type: string;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /** Details */
            details: {
                [key: string]: unknown;
            } | null;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Ip */
            ip: string | null;
            /**
             * Target Id
             * Format: uuid
             */
            target_id: string;
            /** Target Type */
            target_type: string;
        };
        /**
         * AuthKind
         * @enum {string}
         */
        AuthKind: "bearer" | "header" | "oauth";
        /** AuthOption */
        AuthOption: {
            /** Header Name */
            header_name?: string | null;
            kind: components["schemas"]["AuthKind"];
            note?: components["schemas"]["Localized"] | null;
            oauth?: components["schemas"]["OAuthSpec"] | null;
        };
        /**
         * AuthorizeOut
         * @description Where the browser goes to approve the connection.
         */
        AuthorizeOut: {
            /** Authorization Url */
            authorization_url: string;
        };
        /** AutomationCreate */
        AutomationCreate: {
            /**
             * Agent Id
             * Format: uuid
             */
            agent_id: string;
            /** Instruction */
            instruction: string;
            /** Place */
            place: components["schemas"]["DmPlaceIn"] | components["schemas"]["ChannelPlaceIn"] | components["schemas"]["TicketPlaceIn"];
            /** Schedule */
            schedule: components["schemas"]["OnceIn"] | components["schemas"]["RecurringIn"] | components["schemas"]["HeartbeatIn"] | components["schemas"]["EventIn"];
        };
        /**
         * AutomationKind
         * @enum {string}
         */
        AutomationKind: "once" | "recurring" | "heartbeat" | "event";
        /**
         * AutomationOut
         * @description `abilities`: what the caller may do with it now. `upcoming`: its next terms from
         *     now (none for an event rule, or once done). `redacted`: the caller sees it but
         *     may not read its place, so `instruction`, `place.name` and `place.ticket_number`
         *     are null (`words.py`). `term_errors`: terms in a row the due loop could not fire
         *     and set aside (0: none).
         */
        AutomationOut: {
            abilities: components["schemas"]["AbilitiesOut"];
            /** Active Days */
            active_days: number[] | null;
            /** Active From */
            active_from: string | null;
            /** Active Until */
            active_until: string | null;
            agent: components["schemas"]["NamedOut"];
            /** Cron */
            cron: string | null;
            event_type: components["schemas"]["EventType"] | null;
            /** Filter Tag Id */
            filter_tag_id: string | null;
            filter_ticket_kind: components["schemas"]["TicketKind"] | null;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Instruction */
            instruction: string | null;
            /** Interval Minutes */
            interval_minutes: number | null;
            kind: components["schemas"]["AutomationKind"];
            last_run: components["schemas"]["LastRunOut"] | null;
            /** Next Due At */
            next_due_at: string | null;
            owner: components["schemas"]["NamedOut"];
            paused_reason: components["schemas"]["PausedReason"] | null;
            place: components["schemas"]["PlaceOut"];
            /** Quiet Seconds */
            quiet_seconds: number | null;
            /** Redacted */
            redacted: boolean;
            state: components["schemas"]["AutomationState"];
            /** Term Errors */
            term_errors: number;
            /** Time Zone */
            time_zone: string | null;
            /** Upcoming */
            upcoming: string[];
            /** Version */
            version: number;
        };
        /**
         * AutomationState
         * @enum {string}
         */
        AutomationState: "active" | "paused" | "done" | "deleted";
        /**
         * AutomationUpdate
         * @description Only its owner; the kind stays (422 `automation.kind_immutable`); a new schedule
         *     computes the next term anew.
         */
        AutomationUpdate: {
            /** Instruction */
            instruction?: string | null;
            /** Schedule */
            schedule?: (components["schemas"]["OnceIn"] | components["schemas"]["RecurringIn"] | components["schemas"]["HeartbeatIn"] | components["schemas"]["EventIn"]) | null;
            /** Version */
            version: number;
        };
        /**
         * BackupRunOut
         * @description One backup. A run with trigger `admin` in state `running` and no archive yet may
         *     still wait for a worker.
         */
        BackupRunOut: {
            /** Archive */
            archive: string | null;
            /** Archive Sha256 */
            archive_sha256: string | null;
            /** Bytes */
            bytes: number | null;
            /** Error Code */
            error_code: string | null;
            /** Finished At */
            finished_at: string | null;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            offsite_state: components["schemas"]["OffsiteState"];
            /**
             * Started At
             * Format: date-time
             */
            started_at: string;
            state: components["schemas"]["BackupState"];
            trigger: components["schemas"]["BackupTrigger"];
        };
        /**
         * BackupState
         * @enum {string}
         */
        BackupState: "running" | "ok" | "failed" | "interrupted";
        /**
         * BackupTrigger
         * @enum {string}
         */
        BackupTrigger: "schedule" | "cli" | "admin" | "pre_restore";
        /**
         * BaseUrlSpec
         * @description The instance's address, which the admin may change (a self-managed GitLab).
         */
        BaseUrlSpec: {
            /** Default */
            default: string;
            note?: components["schemas"]["Localized"] | null;
        };
        /**
         * BoardCellOut
         * @description A person's tickets in one status: how many, how many changed status since the
         *     board's `changed_since`, the first of them in board order, and the cursor for more
         *     (`GET /api/spaces/{space_id}/board/{status_id}?assignee=<id>|none`).
         */
        BoardCellOut: {
            /** Changed */
            changed: number;
            /** Count */
            count: number;
            /** Items */
            items: components["schemas"]["DailyCardOut"][];
            /** Next Cursor */
            next_cursor: string | null;
            /**
             * Status Id
             * Format: uuid
             */
            status_id: string;
        };
        /**
         * BoardColumnOut
         * @description A status of the board: how many tickets it holds under the filters, the first
         *     of them in board order (priority, due date with none last, number), and the
         *     cursor for more (`GET /api/spaces/{space_id}/board/{status_id}`).
         */
        BoardColumnOut: {
            /** Count */
            count: number;
            /** Items */
            items: components["schemas"]["TicketSummaryOut"][];
            /** Next Cursor */
            next_cursor: string | null;
            status: components["schemas"]["StatusRef"];
        };
        /**
         * BoardOut
         * @description The space's statuses in their order, each a column. Grouped by assignee
         *     (`group_by=assignee`, the daily view): `columns` carry the statuses and their
         *     counts only (no tickets), `rows` the people (by name, at most 100,
         *     `rows_truncated` beyond; the row of the unassigned last) and `changed_since` the
         *     moment the last working day began (0:00 UTC; on a Monday: Friday's).
         */
        BoardOut: {
            /** Changed Since */
            changed_since?: string | null;
            /** Columns */
            columns: components["schemas"]["BoardColumnOut"][];
            /** Rows */
            rows?: components["schemas"]["BoardRowOut"][] | null;
            /**
             * Rows Truncated
             * @default false
             */
            rows_truncated?: boolean;
        };
        /**
         * BoardRowOut
         * @description A person's row (`assignee` null: the tickets assigned to nobody), a cell per
         *     status of the space in order.
         */
        BoardRowOut: {
            assignee: components["schemas"]["PersonOut"] | null;
            /** Cells */
            cells: components["schemas"]["BoardCellOut"][];
        };
        /**
         * BudgetIn
         * @description At least one limit (422 `ai.budget_limit_missing`); `version`: the one read, or
         *     null to create (409 `ai.budget_version_conflict` if the subject has one meanwhile).
         */
        BudgetIn: {
            /** Cost Per Day */
            cost_per_day?: number | string | null;
            /** Tokens Per Day */
            tokens_per_day?: number | null;
            /** Version */
            version: number | null;
        };
        /** BudgetOut */
        BudgetOut: {
            /** Cost Per Day */
            cost_per_day: string | null;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Name */
            name: string | null;
            scope: components["schemas"]["BudgetScope"];
            /** Subject Id */
            subject_id: string | null;
            today: components["schemas"]["TodayOut"];
            /** Tokens Per Day */
            tokens_per_day: number | null;
            /** Version */
            version: number;
        };
        /**
         * BudgetScope
         * @enum {string}
         */
        BudgetScope: "organisation" | "user" | "agent";
        /**
         * CalendarColor
         * @description The eight fixed tones a calendar is drawn in (plan M10 decision 17).
         * @enum {string}
         */
        CalendarColor: "blue" | "green" | "amber" | "red" | "violet" | "teal" | "pink" | "slate";
        /**
         * CalendarCreate
         * @description A new calendar of the space (`calendar.moderate`); at most 20 per space (409
         *     `calendar.limit`).
         */
        CalendarCreate: {
            /** @default blue */
            color?: components["schemas"]["CalendarColor"];
            /** Name */
            name: string;
        };
        /**
         * CalendarOut
         * @description `is_default`: made by the system for a personal space („Mein Kalender“) or the
         *     general space; there is at most one per space.
         */
        CalendarOut: {
            color: components["schemas"]["CalendarColor"];
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Is Default */
            is_default: boolean;
            /** Name */
            name: string;
            /**
             * Space Id
             * Format: uuid
             */
            space_id: string;
            /** Version */
            version: number;
        };
        /**
         * CalendarSettingsIn
         * @description `sync_enabled`: whether people may connect their own external calendars
         *     (`calendar.sync`; data leaves the house).
         */
        CalendarSettingsIn: {
            /** Sync Enabled */
            sync_enabled: boolean;
            /** Version */
            version: number;
        };
        /** CalendarSettingsOut */
        CalendarSettingsOut: {
            /** Sync Enabled */
            sync_enabled: boolean;
            /** Version */
            version: number;
        };
        /**
         * CalendarUpdate
         * @description Fields left out stay as they are (none can be null).
         */
        CalendarUpdate: {
            color?: components["schemas"]["CalendarColor"] | null;
            /** Name */
            name?: string | null;
            /** Version */
            version: number;
        };
        /**
         * CardOut
         * @description A run's card (plan M6 task 7): what it waits for, `approval` or `question`, by
         *     id (`GET /api/approvals/{id}`, `GET /api/questions/{id}`, for those who may see
         *     it). The message's `body_md` is the card's summary or the question.
         */
        CardOut: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            type: components["schemas"]["MessageKind"];
        };
        /** CatalogEntry */
        CatalogEntry: {
            /** Auth */
            auth?: components["schemas"]["AuthOption"][];
            base_url?: components["schemas"]["BaseUrlSpec"] | null;
            /** Connector Scopes */
            connector_scopes: components["schemas"]["ConnectorUse"][];
            /** @default external */
            data_location?: components["schemas"]["DataLocation"];
            description: components["schemas"]["Localized"];
            /** Docs */
            docs?: string[];
            /** Id */
            id: string;
            /** Name */
            name: string;
            /** Tools */
            tools?: {
                [key: string]: components["schemas"]["Classification"];
            };
            /** Url */
            url: string;
        };
        /** ChannelCreate */
        ChannelCreate: {
            /** Name */
            name: string;
            /** Topic */
            topic?: string | null;
        };
        /** ChannelPlaceIn */
        ChannelPlaceIn: {
            /**
             * Conversation Id
             * Format: uuid
             */
            conversation_id: string;
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            type: "channel";
        };
        /**
         * ChannelUpdate
         * @description Fields left out stay as they are; null clears the topic. A name cannot be null.
         */
        ChannelUpdate: {
            /** Name */
            name?: string | null;
            /** Topic */
            topic?: string | null;
            /** Version */
            version: number;
        };
        /**
         * CheckIn
         * @description `model`: which model (route) to try; left out, the connection's standard model.
         */
        CheckIn: {
            /** Model */
            model?: string | null;
        };
        /**
         * CheckOut
         * @description The outcome as a state, never with the provider's own words.
         */
        CheckOut: {
            /** Duration Ms */
            duration_ms: number;
            /** Model */
            model: string | null;
            status: components["schemas"]["CheckStatus"];
        };
        /**
         * CheckStatus
         * @enum {string}
         */
        CheckStatus: "ok" | "unauthorized" | "payment_required" | "forbidden" | "not_found" | "rate_limited" | "provider_error" | "redirect" | "timeout" | "unreachable" | "blocked" | "invalid_response" | "secret_unavailable" | "no_model";
        /**
         * ChildCounts
         * @description How many children the ticket has, per status category.
         */
        ChildCounts: {
            /** Active */
            active: number;
            /** Cancelled */
            cancelled: number;
            /** Done */
            done: number;
            /** Open */
            open: number;
            /** Review */
            review: number;
        };
        /**
         * Classification
         * @enum {string}
         */
        Classification: "read" | "write";
        /** ClientCreate */
        ClientCreate: {
            /** Authorization Endpoint */
            authorization_endpoint: string;
            /** Client Id */
            client_id: string;
            client_secret?: components["schemas"]["SecretIn"] | null;
            /** Issuer */
            issuer?: string | null;
            /**
             * Issuer In Response
             * @default false
             */
            issuer_in_response?: boolean;
            /** Name */
            name: string;
            /** Resource */
            resource?: string | null;
            /** Revocation Endpoint */
            revocation_endpoint?: string | null;
            /**
             * Scopes
             * @default
             */
            scopes?: string;
            /** @default client_secret_post */
            token_auth?: components["schemas"]["TokenAuth"];
            /** Token Endpoint */
            token_endpoint: string;
        };
        /** ClientOut */
        ClientOut: {
            /** Authorization Endpoint */
            authorization_endpoint: string;
            /** Callback Url */
            callback_url: string | null;
            /** Client Id */
            client_id: string;
            client_secret_kind: components["schemas"]["SecretKind"] | null;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /** Has Client Secret */
            has_client_secret: boolean;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Issuer */
            issuer: string | null;
            /** Issuer In Response */
            issuer_in_response: boolean;
            /** Name */
            name: string;
            /** Resource */
            resource: string | null;
            /** Revocation Endpoint */
            revocation_endpoint: string | null;
            /** Scopes */
            scopes: string;
            token_auth: components["schemas"]["TokenAuth"];
            /** Token Endpoint */
            token_endpoint: string;
            /**
             * Updated At
             * Format: date-time
             */
            updated_at: string;
            /** Version */
            version: number;
        };
        /**
         * ClientUpdate
         * @description Only the fields sent change; `client_secret` replaces the stored one, `null`
         *     removes it (a public client).
         */
        ClientUpdate: {
            /** Authorization Endpoint */
            authorization_endpoint?: string | null;
            /** Client Id */
            client_id?: string | null;
            client_secret?: components["schemas"]["SecretIn"] | null;
            /** Issuer */
            issuer?: string | null;
            /** Issuer In Response */
            issuer_in_response?: boolean | null;
            /**
             * Keep Shared Connectors
             * @default false
             */
            keep_shared_connectors?: boolean;
            /** Name */
            name?: string | null;
            /** Resource */
            resource?: string | null;
            /** Revocation Endpoint */
            revocation_endpoint?: string | null;
            /** Scopes */
            scopes?: string | null;
            token_auth?: components["schemas"]["TokenAuth"] | null;
            /** Token Endpoint */
            token_endpoint?: string | null;
            /** Version */
            version: number;
        };
        /**
         * ConnectionCreate
         * @description Left out: `base_url` is OpenAI's; `models` is `gpt-6-luna` for `openai`, else
         *     empty; `param_family` is `max_completion_tokens` for `openai`, else `max_tokens`;
         *     `data_location` is `local` for `local`, else `external`. The first model is the
         *     connection's standard model.
         */
        ConnectionCreate: {
            /** Base Url */
            base_url?: string | null;
            data_location?: components["schemas"]["DataLocation"] | null;
            /**
             * Enabled
             * @default true
             */
            enabled?: boolean;
            /** Extra Body */
            extra_body?: {
                [key: string]: unknown;
            } | null;
            /** @default openai */
            kind?: components["schemas"]["ConnectionKind"];
            /**
             * Max Concurrency
             * @default 4
             */
            max_concurrency?: number;
            /** Models */
            models?: string[] | null;
            /** Name */
            name: string;
            param_family?: components["schemas"]["ParamFamily"] | null;
            /** Prices */
            prices?: {
                [key: string]: components["schemas"]["Price-Input"];
            } | null;
            /** @default chat */
            purpose?: components["schemas"]["Purpose"];
            /**
             * Requests Per Minute
             * @default 60
             */
            requests_per_minute?: number;
            secret?: components["schemas"]["SecretIn"] | null;
            /**
             * Supports Tools
             * @default true
             */
            supports_tools?: boolean;
        };
        /**
         * ConnectionKind
         * @enum {string}
         */
        ConnectionKind: "openai" | "openai_compatible" | "b_api" | "local";
        /**
         * ConnectionOut
         * @description `streaming`: whether calls to it may stream (never for `b_api`). `prices`: per
         *     model, where set (usage costs stay empty without).
         */
        ConnectionOut: {
            /** Base Url */
            base_url: string;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            data_location: components["schemas"]["DataLocation"];
            /** Enabled */
            enabled: boolean;
            /** Extra Body */
            extra_body: {
                [key: string]: unknown;
            };
            /**
             * Id
             * Format: uuid
             */
            id: string;
            kind: components["schemas"]["ConnectionKind"];
            /** Max Concurrency */
            max_concurrency: number;
            /** Models */
            models: string[];
            /** Name */
            name: string;
            param_family: components["schemas"]["ParamFamily"];
            /** Prices */
            prices: {
                [key: string]: components["schemas"]["Price-Output"];
            };
            purpose: components["schemas"]["Purpose"];
            /** Requests Per Minute */
            requests_per_minute: number;
            secret: components["schemas"]["SecretOut"];
            /** Streaming */
            streaming: boolean;
            /** Supports Tools */
            supports_tools: boolean;
            /**
             * Updated At
             * Format: date-time
             */
            updated_at: string;
            /** Version */
            version: number;
        };
        /**
         * ConnectionUpdate
         * @description Fields left out stay as they are; `secret: null` removes the secret. The kind
         *     never changes (sending it is 422).
         */
        ConnectionUpdate: {
            /** Base Url */
            base_url?: string | null;
            data_location?: components["schemas"]["DataLocation"] | null;
            /** Enabled */
            enabled?: boolean | null;
            /** Extra Body */
            extra_body?: {
                [key: string]: unknown;
            } | null;
            /** Max Concurrency */
            max_concurrency?: number | null;
            /** Models */
            models?: string[] | null;
            /** Name */
            name?: string | null;
            param_family?: components["schemas"]["ParamFamily"] | null;
            /** Prices */
            prices?: {
                [key: string]: components["schemas"]["Price-Input"];
            } | null;
            purpose?: components["schemas"]["Purpose"] | null;
            /** Requests Per Minute */
            requests_per_minute?: number | null;
            secret?: components["schemas"]["SecretIn"] | null;
            /** Supports Tools */
            supports_tools?: boolean | null;
            /** Version */
            version: number;
        };
        /** ConnectorCreate */
        ConnectorCreate: {
            auth_kind: components["schemas"]["AuthKind"];
            /** Header Name */
            header_name?: string | null;
            /** Mcp Server Id */
            mcp_server_id?: string | null;
            /** Name */
            name: string;
            /** Oauth Client Id */
            oauth_client_id?: string | null;
            secret?: components["schemas"]["SecretIn"] | null;
        };
        /** ConnectorOut */
        ConnectorOut: {
            auth_kind: components["schemas"]["AuthKind"];
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /** Has Secret */
            has_secret: boolean;
            /** Header Name */
            header_name: string | null;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Mcp Server Id */
            mcp_server_id: string | null;
            /** Name */
            name: string;
            /** Oauth Client Id */
            oauth_client_id: string | null;
            scope: components["schemas"]["ConnectorScope"];
            secret_kind: components["schemas"]["SecretKind"] | null;
            /** Server Urls */
            server_urls: string[];
            /**
             * Updated At
             * Format: date-time
             */
            updated_at: string;
            /** Version */
            version: number;
        };
        /**
         * ConnectorScope
         * @enum {string}
         */
        ConnectorScope: "shared" | "personal";
        /**
         * ConnectorUpdate
         * @description Only the fields sent change; `secret` replaces the stored one. An `oauth`
         *     connector stays one (its tokens change by connecting and disconnecting), and no
         *     other connector becomes one.
         */
        ConnectorUpdate: {
            auth_kind?: components["schemas"]["AuthKind"] | null;
            /** Header Name */
            header_name?: string | null;
            /** Name */
            name?: string | null;
            secret?: components["schemas"]["SecretIn"] | null;
            /** Version */
            version: number;
        };
        /**
         * ConnectorUse
         * @enum {string}
         */
        ConnectorUse: "none" | "shared" | "personal";
        /**
         * ConversationKind
         * @enum {string}
         */
        ConversationKind: "channel" | "dm" | "thread_page" | "thread_ticket";
        /**
         * ConversationOut
         * @description `can_post`: whether the caller may write here now (the right in the space, and
         *     the channel not archived). `created_by` is null for what the system set up.
         *     `version` guards writes (send it back; stale → 409). A direct message lists its
         *     `participants` and, on its own (`GET /conversations/{id}`), every admin
         *     `inspections` of it; both are empty for other kinds. `page_id`: a page thread's
         *     page (null for other kinds). `fresh_start_at`: where the person started her DM
         *     alone with an agent afresh (its agent sees nothing from before; null: never).
         */
        ConversationOut: {
            /** Archived At */
            archived_at: string | null;
            /** Can Post */
            can_post: boolean;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            created_by: components["schemas"]["PrincipalRef"] | null;
            /** Fresh Start At */
            fresh_start_at?: string | null;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Inspections */
            inspections?: components["schemas"]["InspectionNoteOut"][];
            kind: components["schemas"]["ConversationKind"];
            /** Name */
            name: string | null;
            /** Page Id */
            page_id: string | null;
            /** Participants */
            participants?: components["schemas"]["ParticipantOut"][];
            /** Space Id */
            space_id: string | null;
            /** Topic */
            topic: string | null;
            /** Version */
            version: number;
        };
        /** CreatedServerOut */
        CreatedServerOut: {
            /** Catalog Id */
            catalog_id: string | null;
            /** Connector Id */
            connector_id: string | null;
            connector_scope: components["schemas"]["ConnectorUse"];
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            data_location: components["schemas"]["DataLocation"];
            /** Enabled */
            enabled: boolean;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Name */
            name: string;
            /** Oauth Client Id */
            oauth_client_id: string | null;
            refresh: components["schemas"]["RefreshOut"];
            /**
             * Updated At
             * Format: date-time
             */
            updated_at: string;
            /** Url */
            url: string;
            /** Version */
            version: number;
        };
        /**
         * DailyCardOut
         * @description A ticket of the daily view; `changed`: its status changed (or it was made) since
         *     the board's `changed_since`.
         */
        DailyCardOut: {
            assignee: components["schemas"]["PersonOut"] | null;
            /**
             * Awaiting Pickup
             * @default false
             */
            awaiting_pickup?: boolean;
            /** Changed */
            changed: boolean;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /** Due On */
            due_on: string | null;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Key */
            key: string;
            kind: components["schemas"]["TicketKind"];
            /** Number */
            number: number;
            parent: components["schemas"]["ParentOut"] | null;
            priority: components["schemas"]["Priority"];
            reporter: components["schemas"]["PersonOut"];
            /**
             * Space Id
             * Format: uuid
             */
            space_id: string;
            /** Sprint Id */
            sprint_id: string | null;
            status: components["schemas"]["StatusRef"];
            /**
             * Status Changed At
             * Format: date-time
             */
            status_changed_at: string;
            /** Tags */
            tags: components["schemas"]["TagOut"][];
            /** Title */
            title: string;
            /**
             * Updated At
             * Format: date-time
             */
            updated_at: string;
            /** Version */
            version: number;
            /** Via Token */
            via_token?: string | null;
        };
        /**
         * DataLocation
         * @enum {string}
         */
        DataLocation: "local" | "eu" | "external";
        /**
         * DefaultIn
         * @description `target: null`: no standard, so only people and groups with an assignment have AI.
         */
        DefaultIn: {
            target: components["schemas"]["TargetIn"] | null;
            /** Version */
            version: number;
        };
        /**
         * DiffOut
         * @description Line by line from `from_number` to `to_number`; a changed line is a `delete`
         *     followed by an `insert`.
         */
        DiffOut: {
            /** From Number */
            from_number: number;
            /** From Title */
            from_title: string;
            /** Hunks */
            hunks: components["schemas"]["HunkOut"][];
            /** Title Changed */
            title_changed: boolean;
            /** To Number */
            to_number: number;
            /** To Title */
            to_title: string;
        };
        /**
         * DirectoryEntryOut
         * @description Who can be added to a space or written to. Deliberately no email or role: any
         *     member may read it. `kind`: an agent's kind (`external`: it works from outside
         *     through `/mcp` and answers nothing here by itself, plan M8); null for people and
         *     groups.
         */
        DirectoryEntryOut: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            kind?: components["schemas"]["AgentKind"] | null;
            /** Name */
            name: string;
            /**
             * Type
             * @enum {string}
             */
            type: "user" | "group" | "agent";
        };
        /** DiscoverIn */
        DiscoverIn: {
            /** Url */
            url: string;
        };
        /**
         * DiscoveryOut
         * @description A proposal for an OAuth client, found from an MCP server's address; the
         *     endpoints are None unless `status` is `ok` (`modules/oauth/discovery.py`).
         */
        DiscoveryOut: {
            /** Authorization Endpoint */
            authorization_endpoint: string | null;
            /** Issuer */
            issuer: string | null;
            /** Issuer In Response */
            issuer_in_response: boolean;
            /** Pkce */
            pkce: boolean;
            /** Registration */
            registration: boolean;
            /** Resource */
            resource: string | null;
            /** Revocation Endpoint */
            revocation_endpoint: string | null;
            /** Scopes */
            scopes: string;
            status: components["schemas"]["DiscoveryStatus"];
            /** Token Endpoint */
            token_endpoint: string | null;
        };
        /**
         * DiscoveryStatus
         * @enum {string}
         */
        DiscoveryStatus: "ok" | "blocked" | "timeout" | "unreachable" | "no_metadata" | "resource_mismatch" | "no_authorization_server" | "invalid_metadata";
        /**
         * DmOpen
         * @description The other people (the caller is added); 2 to 9 people in all. Or, with
         *     `agent_id` and no `user_ids`, the caller's conversation with that agent.
         */
        DmOpen: {
            /** Agent Id */
            agent_id?: string | null;
            /** User Ids */
            user_ids?: string[];
        };
        /**
         * DmOut
         * @description A direct message in the caller's list: `last_message_at` is its newest
         *     top-level message (null before the first).
         */
        DmOut: {
            /** Archived At */
            archived_at: string | null;
            /** Can Post */
            can_post: boolean;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            created_by: components["schemas"]["PrincipalRef"] | null;
            /** Fresh Start At */
            fresh_start_at?: string | null;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Inspections */
            inspections?: components["schemas"]["InspectionNoteOut"][];
            kind: components["schemas"]["ConversationKind"];
            /** Last Message At */
            last_message_at: string | null;
            /** Name */
            name: string | null;
            /** Page Id */
            page_id: string | null;
            /** Participants */
            participants?: components["schemas"]["ParticipantOut"][];
            /** Space Id */
            space_id: string | null;
            /** Topic */
            topic: string | null;
            /** Version */
            version: number;
        };
        /** DmPlaceIn */
        DmPlaceIn: {
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            type: "dm";
        };
        /**
         * Effect
         * @description What a tool does: reads, proposes (a human decides), or writes.
         * @enum {string}
         */
        Effect: "read" | "propose" | "write";
        /**
         * EpicOut
         * @description An epic with how many children it has per status category (its progress).
         */
        EpicOut: {
            assignee: components["schemas"]["PersonOut"] | null;
            /**
             * Awaiting Pickup
             * @default false
             */
            awaiting_pickup?: boolean;
            children: components["schemas"]["ChildCounts"];
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /** Due On */
            due_on: string | null;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Key */
            key: string;
            kind: components["schemas"]["TicketKind"];
            /** Number */
            number: number;
            parent: components["schemas"]["ParentOut"] | null;
            priority: components["schemas"]["Priority"];
            reporter: components["schemas"]["PersonOut"];
            /**
             * Space Id
             * Format: uuid
             */
            space_id: string;
            /** Sprint Id */
            sprint_id: string | null;
            status: components["schemas"]["StatusRef"];
            /**
             * Status Changed At
             * Format: date-time
             */
            status_changed_at: string;
            /** Tags */
            tags: components["schemas"]["TagOut"][];
            /** Title */
            title: string;
            /**
             * Updated At
             * Format: date-time
             */
            updated_at: string;
            /** Version */
            version: number;
            /** Via Token */
            via_token?: string | null;
        };
        /** EventIn */
        EventIn: {
            event_type: components["schemas"]["EventType"];
            /** Filter Tag Id */
            filter_tag_id?: string | null;
            filter_ticket_kind?: components["schemas"]["TicketKind"] | null;
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            kind: "event";
            /**
             * Quiet Seconds
             * @default 300
             */
            quiet_seconds?: number;
        };
        /**
         * EventKind
         * @enum {string}
         */
        EventKind: "model_call" | "tool_call" | "stop" | "mark";
        /**
         * EventType
         * @description What an event rule listens to (decision 8).
         * @enum {string}
         */
        EventType: "page.published" | "ticket.created" | "attachment.uploaded" | "page.review_due";
        /**
         * FiguresOut
         * @description `tools_major`: the archive's pg_dump, this installation's pg_restore.
         */
        FiguresOut: {
            /** Alembic Revision */
            alembic_revision: string;
            /** App Version */
            app_version: string;
            /** File Bytes */
            file_bytes: number;
            /** Files */
            files: number;
            /** Rows */
            rows: number;
            /** Server Major */
            server_major: number;
            /** Storage */
            storage: string;
            /** Tables */
            tables: number;
            /** Tools Major */
            tools_major: number | null;
        };
        /**
         * FiringOut
         * @description One term of the log: how it went, the run it started, whether a heartbeat's
         *     run answered `HEARTBEAT_OK` (nothing delivered).
         */
        FiringOut: {
            /**
             * Due At
             * Format: date-time
             */
            due_at: string;
            /**
             * Fired At
             * Format: date-time
             */
            fired_at: string;
            /** Heartbeat Ok */
            heartbeat_ok: boolean;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            outcome: components["schemas"]["FiringOutcome"];
            /** Run Id */
            run_id: string | null;
        };
        /**
         * FiringOutcome
         * @enum {string}
         */
        FiringOutcome: "started" | "skipped_busy" | "skipped_paused_agent" | "skipped_budget" | "skipped_policy" | "skipped_off_hours" | "skipped_depth";
        /**
         * Grant
         * @description How an agent may use a tool (spec 8.1), from loose to strict.
         * @enum {string}
         */
        Grant: "allow" | "confirm" | "block";
        /** GroupAssignmentOut */
        GroupAssignmentOut: {
            /**
             * Group Id
             * Format: uuid
             */
            group_id: string;
            /** Group Name */
            group_name: string;
            /** Position */
            position: number;
            target: components["schemas"]["TargetOut"];
        };
        /**
         * GroupBy
         * @enum {string}
         */
        GroupBy: "user" | "agent" | "space" | "connection";
        /** GroupCreate */
        GroupCreate: {
            /** Description */
            description?: string | null;
            /** Name */
            name: string;
        };
        /** GroupItemIn */
        GroupItemIn: {
            /**
             * Connection Id
             * Format: uuid
             */
            connection_id: string;
            /**
             * Group Id
             * Format: uuid
             */
            group_id: string;
            /** Model */
            model: string;
        };
        /**
         * GroupMemberIn
         * @description People only in M1; agents join in M6.
         */
        GroupMemberIn: {
            /**
             * Member Id
             * Format: uuid
             */
            member_id: string;
            /**
             * Member Type
             * @constant
             */
            member_type: "user";
        };
        /**
         * GroupMemberOut
         * @description `name`: the person's display name.
         */
        GroupMemberOut: {
            /**
             * Member Id
             * Format: uuid
             */
            member_id: string;
            member_type: components["schemas"]["PrincipalType"];
            /** Name */
            name: string;
        };
        /** GroupOut */
        GroupOut: {
            /** Description */
            description: string | null;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Name */
            name: string;
            /** Version */
            version: number;
        };
        /** GroupUpdateIn */
        GroupUpdateIn: {
            /** Description */
            description?: string | null;
            /** Name */
            name?: string | null;
            /** Version */
            version: number;
        };
        /**
         * GroupsIn
         * @description The whole ordered list; for a person in several groups the first one wins.
         */
        GroupsIn: {
            /** Items */
            items: components["schemas"]["GroupItemIn"][];
            /** Version */
            version: number;
        };
        /** HTTPValidationError */
        HTTPValidationError: {
            /** Detail */
            detail?: components["schemas"]["ValidationError"][];
        };
        /** HeartbeatIn */
        HeartbeatIn: {
            /** Active Days */
            active_days: number[];
            /**
             * Active From
             * Format: time
             */
            active_from: string;
            /**
             * Active Until
             * Format: time
             */
            active_until: string;
            /** Interval Minutes */
            interval_minutes: number;
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            kind: "heartbeat";
            /** Time Zone */
            time_zone: string;
        };
        /** HitAuthor */
        HitAuthor: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Name */
            name: string;
            type: components["schemas"]["PrincipalType"];
        };
        /**
         * HitConversation
         * @description Where a message stands. `name`: a channel's (null otherwise); `page_id`: a page
         *     thread's page, `ticket_number`: a ticket thread's ticket (null otherwise);
         *     `space_id`: null for a direct message.
         */
        HitConversation: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            kind: components["schemas"]["ConversationKind"];
            /** Name */
            name: string | null;
            /** Page Id */
            page_id: string | null;
            /** Space Id */
            space_id: string | null;
            /** Ticket Number */
            ticket_number: number | null;
        };
        /** HunkOut */
        HunkOut: {
            /**
             * Kind
             * @enum {string}
             */
            kind: "equal" | "insert" | "delete";
            /** Lines */
            lines: string[];
        };
        /** IdentityOut */
        IdentityOut: {
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Last Login At */
            last_login_at: string | null;
            /** Provider Key */
            provider_key: string;
            provider_kind: components["schemas"]["ProviderKind"];
            /** Provider Name */
            provider_name: string;
        };
        /**
         * ImportResultOut
         * @description `created`: pages, folders without a file of their own included.
         */
        ImportResultOut: {
            /** Attachments */
            attachments: number;
            /** Created */
            created: number;
            /** Skipped */
            skipped: components["schemas"]["SkippedOut"][];
        };
        /**
         * InspectableDmOut
         * @description What an inspecting admin learns before an inspection: who, and when, no content.
         */
        InspectableDmOut: {
            /**
             * Conversation Id
             * Format: uuid
             */
            conversation_id: string;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /** Last Message At */
            last_message_at: string | null;
            /** Participants */
            participants: components["schemas"]["ParticipantOut"][];
        };
        /** InspectionCreate */
        InspectionCreate: {
            /**
             * Conversation Id
             * Format: uuid
             */
            conversation_id: string;
            /** Reason */
            reason: string;
        };
        /**
         * InspectionNoteOut
         * @description An admin looked into this direct message (spec 5.5): when, and who.
         */
        InspectionNoteOut: {
            /** Admin Name */
            admin_name: string;
            /**
             * At
             * Format: date-time
             */
            at: string;
        };
        /**
         * InspectionOut
         * @description Read the DM's messages at `/admin/dm-inspect/{id}/messages` until `expires_at`.
         */
        InspectionOut: {
            /**
             * Conversation Id
             * Format: uuid
             */
            conversation_id: string;
            /**
             * Expires At
             * Format: date-time
             */
            expires_at: string;
            /**
             * Granted At
             * Format: date-time
             */
            granted_at: string;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Reason */
            reason: string;
        };
        /**
         * InstallIn
         * @description A server (and what it needs) from a catalogue entry. The admin brings only the
         *     access and its scope; every tool is still approved one by one.
         *
         *     - `none`: no credential.
         *     - `shared`: one shared connector, created here: `bearer`/`header` with `secret`,
         *       `oauth` with an OAuth client (`client_id`, `client_secret` if confidential),
         *       connected afterwards (`POST /api/ai/connectors/{id}/authorize`).
         *     - `personal`: each person connects their own; `oauth` creates the OAuth client
         *       they connect with, `bearer`/`header` need nothing more here.
         */
        InstallIn: {
            auth_kind?: components["schemas"]["AuthKind"] | null;
            /** Base Url */
            base_url?: string | null;
            /** Client Id */
            client_id?: string | null;
            client_secret?: components["schemas"]["SecretIn"] | null;
            connector_scope: components["schemas"]["ConnectorUse"];
            data_location?: components["schemas"]["DataLocation"] | null;
            /**
             * Enabled
             * @default true
             */
            enabled?: boolean;
            /** Name */
            name?: string | null;
            secret?: components["schemas"]["SecretIn"] | null;
        };
        /** InstallOut */
        InstallOut: {
            /** Connector Id */
            connector_id: string | null;
            /** Oauth Client Id */
            oauth_client_id: string | null;
            server: components["schemas"]["CreatedServerOut"];
        };
        /**
         * LastRunOut
         * @description The latest term: how it went (`outcome`), its run and how that ended.
         */
        LastRunOut: {
            /**
             * Due At
             * Format: date-time
             */
            due_at: string;
            /**
             * Fired At
             * Format: date-time
             */
            fired_at: string;
            /**
             * Firing Id
             * Format: uuid
             */
            firing_id: string;
            /** Heartbeat Ok */
            heartbeat_ok: boolean;
            outcome: components["schemas"]["FiringOutcome"];
            /** Run Id */
            run_id: string | null;
            run_state: components["schemas"]["RunState"] | null;
            stop_reason: components["schemas"]["StopReason"] | null;
        };
        /**
         * LinkStartIn
         * @description Linking a new account proves the person again (J9): her current password, or
         *     none right after a sign-in through a provider (at most 10 minutes ago).
         */
        LinkStartIn: {
            /** Password */
            password?: string | null;
        };
        /**
         * LinkStartOut
         * @description Where the browser goes to link an account (the provider's sign-in page).
         */
        LinkStartOut: {
            /** Url */
            url: string;
        };
        /**
         * LinkedPageOut
         * @description A page the ticket links (one the caller sees).
         */
        LinkedPageOut: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Linked At
             * Format: date-time
             */
            linked_at: string;
            /** Path */
            path: string;
            /**
             * Space Id
             * Format: uuid
             */
            space_id: string;
            /** Space Name */
            space_name: string;
            /** Title */
            title: string;
        };
        /** Localized */
        Localized: {
            /** De */
            de: string;
            /** En */
            en: string;
        };
        /** LoginRequest */
        LoginRequest: {
            /**
             * Email
             * Format: email
             */
            email: string;
            /** Password */
            password: string;
        };
        /** MaintenanceOut */
        MaintenanceOut: {
            /** Active */
            active: boolean;
            reason: components["schemas"]["MaintenanceReason"] | null;
            /** Started At */
            started_at: string | null;
        };
        /**
         * MaintenanceReason
         * @enum {string}
         */
        MaintenanceReason: "restore";
        /** McpCallOut */
        McpCallOut: {
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /** Duration Ms */
            duration_ms: number;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            outcome: components["schemas"]["Outcome"];
            /** Tool */
            tool: string;
        };
        /** McpSettingsIn */
        McpSettingsIn: {
            data_location: components["schemas"]["DataLocation"];
            /** Enabled */
            enabled: boolean;
            /** Version */
            version: number;
        };
        /**
         * McpSettingsOut
         * @description `enabled`: whether every active person but guests holds `mcp.use`.
         *     `data_location`: what an MCP client counts as for the spaces' AI policy.
         */
        McpSettingsOut: {
            data_location: components["schemas"]["DataLocation"];
            /** Enabled */
            enabled: boolean;
            /** Version */
            version: number;
        };
        /**
         * MeOut
         * @description `permissions`: the system-wide actions the caller holds; clients decide what to
         *     show from these (and from a space's `my_role`), never from the role's name.
         *     `ai_model`: with `ai.use`, the name of the model the caller's AI assignment gives
         *     them (nothing else about the connection); null without. `session_limits`: what the
         *     sessions list tells the person (R18-11).
         */
        MeOut: {
            /** Ai Model */
            ai_model: string | null;
            org: components["schemas"]["OrgOut"];
            /** Permissions */
            permissions: components["schemas"]["Action"][];
            session_limits: components["schemas"]["SessionLimitsOut"];
            user: components["schemas"]["UserOut"];
        };
        /**
         * MessageAuthorOut
         * @description Who wrote a message, with the name to show (null if unknown).
         */
        MessageAuthorOut: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Name */
            name: string | null;
            type: components["schemas"]["PrincipalType"];
        };
        /**
         * MessageCreate
         * @description `parent_id`: a top-level message of the same conversation, to reply in its
         *     thread. `client_id`: the client's key for this message; sending again with the
         *     same key returns the first message (200) instead of a second one. `mentions`:
         *     whom the text mentions (`@[Name](user:<id>)`); at most 50.
         */
        MessageCreate: {
            /**
             * Body Md
             * @description Markdown
             */
            body_md: string;
            /** Client Id */
            client_id?: string | null;
            /**
             * Mentions
             * @description the people the message mentions (user ids)
             */
            mentions?: string[];
            /** Parent Id */
            parent_id?: string | null;
        };
        /**
         * MessageHitOut
         * @description A message (`id`); `parent_id`: the thread it is a reply in (null: top level).
         *     `snippet` and `score` as for pages.
         */
        MessageHitOut: {
            author: components["schemas"]["HitAuthor"] | null;
            conversation: components["schemas"]["HitConversation"];
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Parent Id */
            parent_id: string | null;
            /** Score */
            score: number;
            /** Snippet */
            snippet: string;
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            type: "message";
        };
        /**
         * MessageKind
         * @enum {string}
         */
        MessageKind: "human" | "system" | "agent" | "approval" | "question";
        /**
         * MessageOut
         * @description `author` is null for system messages; those carry `system` instead (null for
         *     all others) and an empty `body_md`: their stored body holds ids the reader may not
         *     be allowed to see, `system` only what is named for the reader (review M4 P1). A
         *     deleted message keeps its place with `deleted_at` set and an empty `body_md`.
         *     `reply_count` and `last_reply_at` belong to top-level messages (their thread).
         *     `run_id`: an agent's message names the run that wrote it (AI mark: `kind=agent`).
         *     `via_token`: a person's message written through an access token at `/mcp`, the
         *     token's name (AI mark of an external AI client, plan M8).
         *     `mentions`: the people mentioned who may see the conversation; `reactions`: by
         *     emoji, the first reacted with first. `card`: set for a run's card (`kind`
         *     `approval` or `question`). `personal`: an agent's message that holds what the
         *     person read through her own connector (module review M8 2); only where she is
         *     alone with the agent.
         */
        MessageOut: {
            author: components["schemas"]["MessageAuthorOut"] | null;
            /** Body Md */
            body_md: string;
            card?: components["schemas"]["CardOut"] | null;
            /** Client Id */
            client_id: string | null;
            /**
             * Conversation Id
             * Format: uuid
             */
            conversation_id: string;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /** Deleted At */
            deleted_at: string | null;
            /** Edited At */
            edited_at: string | null;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            kind: components["schemas"]["MessageKind"];
            /** Last Reply At */
            last_reply_at: string | null;
            /** Mentions */
            mentions: string[];
            /** Parent Id */
            parent_id: string | null;
            /**
             * Personal
             * @default false
             */
            personal?: boolean;
            /** Reactions */
            reactions: components["schemas"]["ReactionOut"][];
            /** Reply Count */
            reply_count: number;
            /** Run Id */
            run_id?: string | null;
            system: components["schemas"]["SystemEntryOut"] | null;
            /** Via Token */
            via_token?: string | null;
        };
        /**
         * MessageUpdate
         * @description `mentions` left out: the message keeps whom it mentions; given: replaces it.
         */
        MessageUpdate: {
            /**
             * Body Md
             * @description Markdown
             */
            body_md: string;
            /** Mentions */
            mentions?: string[] | null;
        };
        /**
         * MessageWriteOut
         * @description `not_notified`: the mentioned ids that were not stored: people who may not see
         *     the conversation, and ids of nobody (indistinguishable on purpose; an agent a
         *     mention asked is not among them). `agent_run`: for a new message in a DM with an
         *     agent, or one that mentions an agent the writer may ask, the run it started or why
         *     none (null otherwise, and for a resend).
         */
        MessageWriteOut: {
            agent_run?: components["schemas"]["AgentRunOut"] | null;
            author: components["schemas"]["MessageAuthorOut"] | null;
            /** Body Md */
            body_md: string;
            card?: components["schemas"]["CardOut"] | null;
            /** Client Id */
            client_id: string | null;
            /**
             * Conversation Id
             * Format: uuid
             */
            conversation_id: string;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /** Deleted At */
            deleted_at: string | null;
            /** Edited At */
            edited_at: string | null;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            kind: components["schemas"]["MessageKind"];
            /** Last Reply At */
            last_reply_at: string | null;
            /** Mentions */
            mentions: string[];
            /** Not Notified */
            not_notified: string[];
            /** Parent Id */
            parent_id: string | null;
            /**
             * Personal
             * @default false
             */
            personal?: boolean;
            /** Reactions */
            reactions: components["schemas"]["ReactionOut"][];
            /** Reply Count */
            reply_count: number;
            /** Run Id */
            run_id?: string | null;
            system: components["schemas"]["SystemEntryOut"] | null;
            /** Via Token */
            via_token?: string | null;
        };
        /**
         * MoveCategory
         * @description Into the first status of `category` in the ticket's space (422
         *     `ticket.category_empty` without one); `version` is the ticket version read.
         */
        MoveCategory: {
            category: components["schemas"]["StatusCategory"];
            /** Version */
            version: number;
        };
        /**
         * MoveOpenTo
         * @enum {string}
         */
        MoveOpenTo: "next" | "backlog";
        /**
         * MyBoardOut
         * @description My tickets of every space I may read, by category: open, active, review, done
         *     (done: finished in the last 14 days; cancelled ones are not shown).
         */
        MyBoardOut: {
            /** Columns */
            columns: components["schemas"]["MyColumnOut"][];
        };
        /**
         * MyCardOut
         * @description A ticket on my board, with the name of its space.
         */
        MyCardOut: {
            assignee: components["schemas"]["PersonOut"] | null;
            /**
             * Awaiting Pickup
             * @default false
             */
            awaiting_pickup?: boolean;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /** Due On */
            due_on: string | null;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Key */
            key: string;
            kind: components["schemas"]["TicketKind"];
            /** Number */
            number: number;
            parent: components["schemas"]["ParentOut"] | null;
            priority: components["schemas"]["Priority"];
            reporter: components["schemas"]["PersonOut"];
            /**
             * Space Id
             * Format: uuid
             */
            space_id: string;
            /** Space Name */
            space_name: string;
            /** Sprint Id */
            sprint_id: string | null;
            status: components["schemas"]["StatusRef"];
            /**
             * Status Changed At
             * Format: date-time
             */
            status_changed_at: string;
            /** Tags */
            tags: components["schemas"]["TagOut"][];
            /** Title */
            title: string;
            /**
             * Updated At
             * Format: date-time
             */
            updated_at: string;
            /** Version */
            version: number;
            /** Via Token */
            via_token?: string | null;
        };
        /** MyCardPage */
        MyCardPage: {
            /** Items */
            items: components["schemas"]["MyCardOut"][];
            /** Next Cursor */
            next_cursor: string | null;
        };
        /**
         * MyColumnOut
         * @description A status category: how many of my tickets it holds, the first of them in board
         *     order (priority, due date with none last, number), and the cursor for more
         *     (`GET /api/tickets/my-board/{category}`).
         */
        MyColumnOut: {
            category: components["schemas"]["StatusCategory"];
            /** Count */
            count: number;
            /** Items */
            items: components["schemas"]["MyCardOut"][];
            /** Next Cursor */
            next_cursor: string | null;
        };
        /**
         * MyUsageOut
         * @description The caller's own usage in the period (whole UTC days).
         */
        MyUsageOut: {
            /** Calls */
            calls: number;
            /** Cost */
            cost: string | null;
            /** Duration Ms */
            duration_ms: number;
            /**
             * First Day
             * Format: date
             */
            first_day: string;
            /**
             * Last Day
             * Format: date
             */
            last_day: string;
            /** Tokens Cached */
            tokens_cached: number;
            /** Tokens In */
            tokens_in: number;
            /** Tokens Out */
            tokens_out: number;
            /** Unpriced Calls */
            unpriced_calls: number;
        };
        /** NamedOut */
        NamedOut: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Name */
            name: string | null;
        };
        /**
         * NotificationReason
         * @enum {string}
         */
        NotificationReason: "mention" | "reply" | "assignment" | "ticket_comment" | "proposal" | "approval" | "question" | "run_stopped" | "skill_proposal" | "automation" | "review_due" | "signup" | "totp_locked";
        /** OAuthSpec */
        OAuthSpec: {
            /** Authorization Endpoint */
            authorization_endpoint: string;
            /**
             * Resource
             * @default true
             */
            resource?: boolean;
            /** Revocation Endpoint */
            revocation_endpoint?: string | null;
            /**
             * Scopes
             * @default
             */
            scopes?: string;
            /** @default client_secret_post */
            token_auth?: components["schemas"]["TokenAuth"];
            /** Token Endpoint */
            token_endpoint: string;
        };
        /**
         * OffsiteState
         * @enum {string}
         */
        OffsiteState: "off" | "ok" | "failed";
        /**
         * OidcSecretIn
         * @description Either the secret itself (`value`, stored encrypted; needs `HERD_SECRET_KEY`) or
         *     the name of an environment variable `HERD_OIDC_*` (`env`).
         */
        OidcSecretIn: {
            /** Env */
            env?: string | null;
            /** Value */
            value?: string | null;
        };
        /** OnceIn */
        OnceIn: {
            /**
             * At
             * Format: date-time
             */
            at: string;
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            kind: "once";
        };
        /** OrgOut */
        OrgOut: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Name */
            name: string;
        };
        /**
         * Outcome
         * @enum {string}
         */
        Outcome: "ok" | "refused" | "invalid" | "failed";
        /**
         * OwnSessionOut
         * @description One of the caller's running login sessions. `device`: browser and system, no
         *     version (null for an unknown client); `current`: the session of this request.
         */
        OwnSessionOut: {
            /** Current */
            current: boolean;
            /** Device */
            device: string | null;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Last Used At
             * Format: date-time
             */
            last_used_at: string;
            /**
             * Signed In At
             * Format: date-time
             */
            signed_in_at: string;
        };
        /** OwnSessionPage */
        OwnSessionPage: {
            /** Items */
            items: components["schemas"]["OwnSessionOut"][];
            /** Next Cursor */
            next_cursor: string | null;
        };
        /** PageCreate */
        PageCreate: {
            /**
             * Content Md
             * @default
             */
            content_md?: string;
            /** Parent Id */
            parent_id?: string | null;
            /** Title */
            title: string;
        };
        /**
         * PageHitOut
         * @description A page. `snippet` is plain text: render it as text and highlight what stands
         *     between `⟦` and `⟧`. `score` orders the hits (higher is better); it has no unit.
         */
        PageHitOut: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Path */
            path: string;
            /** Score */
            score: number;
            /** Snippet */
            snippet: string;
            /**
             * Space Id
             * Format: uuid
             */
            space_id: string;
            /** Space Name */
            space_name: string;
            /** Title */
            title: string;
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            type: "page";
        };
        /**
         * PageMove
         * @description `parent_id` null: the top level. `position` among the new siblings, 0 first;
         *     left out: at the end, or where the page is if its parent stays.
         */
        PageMove: {
            /** Parent Id */
            parent_id: string | null;
            /** Position */
            position?: number | null;
            /** Version */
            version: number;
        };
        /**
         * PageOut
         * @description `version` guards writes (send it back; stale → 409). `collab_generation` changes
         *     whenever open live-editing sessions of the page end. `tags`: tag ids, by name.
         *     `no_ai`: locked for AI (spec 11). `reviewed_at`: the last review (publishing or
         *     "mark as reviewed"; null for a draft); `review_due`: the space's review interval
         *     has passed since (plan M7 decision 11).
         */
        PageOut: {
            /** Collab Generation */
            collab_generation: number;
            /** Content Md */
            content_md: string;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            created_by: components["schemas"]["PrincipalRef"];
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** No Ai */
            no_ai: boolean;
            /** Parent Id */
            parent_id: string | null;
            /** Path */
            path: string;
            /** Published At */
            published_at: string | null;
            /** Review Due */
            review_due: boolean;
            /** Reviewed At */
            reviewed_at: string | null;
            /** Slug */
            slug: string;
            /** Sort Order */
            sort_order: number;
            /**
             * Space Id
             * Format: uuid
             */
            space_id: string;
            status: components["schemas"]["PageStatus"];
            /** Tags */
            tags: string[];
            /** Title */
            title: string;
            /**
             * Updated At
             * Format: date-time
             */
            updated_at: string;
            updated_by: components["schemas"]["PrincipalRef"];
            /** Version */
            version: number;
        };
        /**
         * PageStatus
         * @enum {string}
         */
        PageStatus: "draft" | "published";
        /**
         * PageUpdate
         * @description Fields left out stay as they are; neither may be null.
         */
        PageUpdate: {
            /** Change Summary */
            change_summary?: string | null;
            /** Content Md */
            content_md?: string | null;
            /** Title */
            title?: string | null;
            /** Version */
            version: number;
        };
        /** Page[ActivityOut] */
        Page_ActivityOut_: {
            /** Items */
            items: components["schemas"]["ActivityOut"][];
            /** Next Cursor */
            next_cursor?: string | null;
        };
        /** Page[AdminTokenOut] */
        Page_AdminTokenOut_: {
            /** Items */
            items: components["schemas"]["AdminTokenOut"][];
            /** Next Cursor */
            next_cursor?: string | null;
        };
        /** Page[AdminUserOut] */
        Page_AdminUserOut_: {
            /** Items */
            items: components["schemas"]["AdminUserOut"][];
            /** Next Cursor */
            next_cursor?: string | null;
        };
        /** Page[AgentOut] */
        Page_AgentOut_: {
            /** Items */
            items: components["schemas"]["AgentOut"][];
            /** Next Cursor */
            next_cursor?: string | null;
        };
        /** Page[AgentPickOut] */
        Page_AgentPickOut_: {
            /** Items */
            items: components["schemas"]["AgentPickOut"][];
            /** Next Cursor */
            next_cursor?: string | null;
        };
        /** Page[AgentSpaceOut] */
        Page_AgentSpaceOut_: {
            /** Items */
            items: components["schemas"]["AgentSpaceOut"][];
            /** Next Cursor */
            next_cursor?: string | null;
        };
        /** Page[ApprovalOut] */
        Page_ApprovalOut_: {
            /** Items */
            items: components["schemas"]["ApprovalOut"][];
            /** Next Cursor */
            next_cursor?: string | null;
        };
        /** Page[ArchiveOut] */
        Page_ArchiveOut_: {
            /** Items */
            items: components["schemas"]["ArchiveOut"][];
            /** Next Cursor */
            next_cursor?: string | null;
        };
        /** Page[AttachmentOut] */
        Page_AttachmentOut_: {
            /** Items */
            items: components["schemas"]["AttachmentOut"][];
            /** Next Cursor */
            next_cursor?: string | null;
        };
        /** Page[AuditOut] */
        Page_AuditOut_: {
            /** Items */
            items: components["schemas"]["AuditOut"][];
            /** Next Cursor */
            next_cursor?: string | null;
        };
        /** Page[AutomationOut] */
        Page_AutomationOut_: {
            /** Items */
            items: components["schemas"]["AutomationOut"][];
            /** Next Cursor */
            next_cursor?: string | null;
        };
        /** Page[BackupRunOut] */
        Page_BackupRunOut_: {
            /** Items */
            items: components["schemas"]["BackupRunOut"][];
            /** Next Cursor */
            next_cursor?: string | null;
        };
        /** Page[BudgetOut] */
        Page_BudgetOut_: {
            /** Items */
            items: components["schemas"]["BudgetOut"][];
            /** Next Cursor */
            next_cursor?: string | null;
        };
        /** Page[CalendarOut] */
        Page_CalendarOut_: {
            /** Items */
            items: components["schemas"]["CalendarOut"][];
            /** Next Cursor */
            next_cursor?: string | null;
        };
        /** Page[CatalogEntry] */
        Page_CatalogEntry_: {
            /** Items */
            items: components["schemas"]["CatalogEntry"][];
            /** Next Cursor */
            next_cursor?: string | null;
        };
        /** Page[ClientOut] */
        Page_ClientOut_: {
            /** Items */
            items: components["schemas"]["ClientOut"][];
            /** Next Cursor */
            next_cursor?: string | null;
        };
        /** Page[ConnectionOut] */
        Page_ConnectionOut_: {
            /** Items */
            items: components["schemas"]["ConnectionOut"][];
            /** Next Cursor */
            next_cursor?: string | null;
        };
        /** Page[ConnectorOut] */
        Page_ConnectorOut_: {
            /** Items */
            items: components["schemas"]["ConnectorOut"][];
            /** Next Cursor */
            next_cursor?: string | null;
        };
        /** Page[ConversationOut] */
        Page_ConversationOut_: {
            /** Items */
            items: components["schemas"]["ConversationOut"][];
            /** Next Cursor */
            next_cursor?: string | null;
        };
        /** Page[DirectoryEntryOut] */
        Page_DirectoryEntryOut_: {
            /** Items */
            items: components["schemas"]["DirectoryEntryOut"][];
            /** Next Cursor */
            next_cursor?: string | null;
        };
        /** Page[DmOut] */
        Page_DmOut_: {
            /** Items */
            items: components["schemas"]["DmOut"][];
            /** Next Cursor */
            next_cursor?: string | null;
        };
        /** Page[EpicOut] */
        Page_EpicOut_: {
            /** Items */
            items: components["schemas"]["EpicOut"][];
            /** Next Cursor */
            next_cursor?: string | null;
        };
        /** Page[FiringOut] */
        Page_FiringOut_: {
            /** Items */
            items: components["schemas"]["FiringOut"][];
            /** Next Cursor */
            next_cursor?: string | null;
        };
        /** Page[GroupAssignmentOut] */
        Page_GroupAssignmentOut_: {
            /** Items */
            items: components["schemas"]["GroupAssignmentOut"][];
            /** Next Cursor */
            next_cursor?: string | null;
        };
        /** Page[GroupMemberOut] */
        Page_GroupMemberOut_: {
            /** Items */
            items: components["schemas"]["GroupMemberOut"][];
            /** Next Cursor */
            next_cursor?: string | null;
        };
        /** Page[GroupOut] */
        Page_GroupOut_: {
            /** Items */
            items: components["schemas"]["GroupOut"][];
            /** Next Cursor */
            next_cursor?: string | null;
        };
        /** Page[IdentityOut] */
        Page_IdentityOut_: {
            /** Items */
            items: components["schemas"]["IdentityOut"][];
            /** Next Cursor */
            next_cursor?: string | null;
        };
        /** Page[InspectableDmOut] */
        Page_InspectableDmOut_: {
            /** Items */
            items: components["schemas"]["InspectableDmOut"][];
            /** Next Cursor */
            next_cursor?: string | null;
        };
        /** Page[LinkedPageOut] */
        Page_LinkedPageOut_: {
            /** Items */
            items: components["schemas"]["LinkedPageOut"][];
            /** Next Cursor */
            next_cursor?: string | null;
        };
        /** Page[McpCallOut] */
        Page_McpCallOut_: {
            /** Items */
            items: components["schemas"]["McpCallOut"][];
            /** Next Cursor */
            next_cursor?: string | null;
        };
        /** Page[MessageOut] */
        Page_MessageOut_: {
            /** Items */
            items: components["schemas"]["MessageOut"][];
            /** Next Cursor */
            next_cursor?: string | null;
        };
        /** Page[PersonalServerOut] */
        Page_PersonalServerOut_: {
            /** Items */
            items: components["schemas"]["PersonalServerOut"][];
            /** Next Cursor */
            next_cursor?: string | null;
        };
        /** Page[ProblemOut] */
        Page_ProblemOut_: {
            /** Items */
            items: components["schemas"]["ProblemOut"][];
            /** Next Cursor */
            next_cursor?: string | null;
        };
        /** Page[ProposalOut] */
        Page_ProposalOut_: {
            /** Items */
            items: components["schemas"]["ProposalOut"][];
            /** Next Cursor */
            next_cursor?: string | null;
        };
        /** Page[ProviderOut] */
        Page_ProviderOut_: {
            /** Items */
            items: components["schemas"]["ProviderOut"][];
            /** Next Cursor */
            next_cursor?: string | null;
        };
        /** Page[PublicProviderOut] */
        Page_PublicProviderOut_: {
            /** Items */
            items: components["schemas"]["PublicProviderOut"][];
            /** Next Cursor */
            next_cursor?: string | null;
        };
        /** Page[RunEventOut] */
        Page_RunEventOut_: {
            /** Items */
            items: components["schemas"]["RunEventOut"][];
            /** Next Cursor */
            next_cursor?: string | null;
        };
        /** Page[RunOut] */
        Page_RunOut_: {
            /** Items */
            items: components["schemas"]["RunOut"][];
            /** Next Cursor */
            next_cursor?: string | null;
        };
        /** Page[ServerOut] */
        Page_ServerOut_: {
            /** Items */
            items: components["schemas"]["ServerOut"][];
            /** Next Cursor */
            next_cursor?: string | null;
        };
        /** Page[SkillOut] */
        Page_SkillOut_: {
            /** Items */
            items: components["schemas"]["SkillOut"][];
            /** Next Cursor */
            next_cursor?: string | null;
        };
        /** Page[SkillProposalOut] */
        Page_SkillProposalOut_: {
            /** Items */
            items: components["schemas"]["SkillProposalOut"][];
            /** Next Cursor */
            next_cursor?: string | null;
        };
        /** Page[SkillVersionOut] */
        Page_SkillVersionOut_: {
            /** Items */
            items: components["schemas"]["SkillVersionOut"][];
            /** Next Cursor */
            next_cursor?: string | null;
        };
        /** Page[SpaceMemberOut] */
        Page_SpaceMemberOut_: {
            /** Items */
            items: components["schemas"]["SpaceMemberOut"][];
            /** Next Cursor */
            next_cursor?: string | null;
        };
        /** Page[SpaceOut] */
        Page_SpaceOut_: {
            /** Items */
            items: components["schemas"]["SpaceOut"][];
            /** Next Cursor */
            next_cursor?: string | null;
        };
        /** Page[SprintOut] */
        Page_SprintOut_: {
            /** Items */
            items: components["schemas"]["SprintOut"][];
            /** Next Cursor */
            next_cursor?: string | null;
        };
        /** Page[StatusOut] */
        Page_StatusOut_: {
            /** Items */
            items: components["schemas"]["StatusOut"][];
            /** Next Cursor */
            next_cursor?: string | null;
        };
        /** Page[TagOut] */
        Page_TagOut_: {
            /** Items */
            items: components["schemas"]["TagOut"][];
            /** Next Cursor */
            next_cursor?: string | null;
        };
        /** Page[TicketSummaryOut] */
        Page_TicketSummaryOut_: {
            /** Items */
            items: components["schemas"]["TicketSummaryOut"][];
            /** Next Cursor */
            next_cursor?: string | null;
        };
        /** Page[TokenOut] */
        Page_TokenOut_: {
            /** Items */
            items: components["schemas"]["TokenOut"][];
            /** Next Cursor */
            next_cursor?: string | null;
        };
        /** Page[ToolOut] */
        Page_ToolOut_: {
            /** Items */
            items: components["schemas"]["ToolOut"][];
            /** Next Cursor */
            next_cursor?: string | null;
        };
        /** Page[TrashedPageOut] */
        Page_TrashedPageOut_: {
            /** Items */
            items: components["schemas"]["TrashedPageOut"][];
            /** Next Cursor */
            next_cursor?: string | null;
        };
        /** Page[TreeNodeOut] */
        Page_TreeNodeOut_: {
            /** Items */
            items: components["schemas"]["TreeNodeOut"][];
            /** Next Cursor */
            next_cursor?: string | null;
        };
        /** Page[UnreadOut] */
        Page_UnreadOut_: {
            /** Items */
            items: components["schemas"]["UnreadOut"][];
            /** Next Cursor */
            next_cursor?: string | null;
        };
        /** Page[UsageRowOut] */
        Page_UsageRowOut_: {
            /** Items */
            items: components["schemas"]["UsageRowOut"][];
            /** Next Cursor */
            next_cursor?: string | null;
        };
        /** Page[UserAssignmentOut] */
        Page_UserAssignmentOut_: {
            /** Items */
            items: components["schemas"]["UserAssignmentOut"][];
            /** Next Cursor */
            next_cursor?: string | null;
        };
        /** Page[VersionSummaryOut] */
        Page_VersionSummaryOut_: {
            /** Items */
            items: components["schemas"]["VersionSummaryOut"][];
            /** Next Cursor */
            next_cursor?: string | null;
        };
        /**
         * ParamFamily
         * @enum {string}
         */
        ParamFamily: "max_completion_tokens" | "max_tokens";
        /** ParentOut */
        ParentOut: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Key */
            key: string;
            kind: components["schemas"]["TicketKind"];
            /** Number */
            number: number;
            /** Title */
            title: string;
        };
        /**
         * ParticipantOut
         * @description A person in a direct message (one who was deactivated stays listed), or its
         *     agent (`type` `agent`, listed after the people).
         */
        ParticipantOut: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Is Active */
            is_active: boolean;
            /** Name */
            name: string;
            /** @default user */
            type?: components["schemas"]["PrincipalType"];
        };
        /**
         * PasswordChangeIn
         * @description A person's own new password; the current one proves it is them.
         */
        PasswordChangeIn: {
            /** Current Password */
            current_password: string;
            /** New Password */
            new_password: string;
        };
        /**
         * PausedReason
         * @enum {string}
         */
        PausedReason: "manual" | "owner" | "failing";
        /**
         * PendingCountOut
         * @description How many self-registered accounts wait for approval.
         */
        PendingCountOut: {
            /** Count */
            count: number;
        };
        /**
         * PersonNameOut
         * @description Who caused a timeline entry: a person, or (plan M6) an agent (`type`).
         */
        PersonNameOut: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Name */
            name: string;
            /** @default user */
            type?: components["schemas"]["PrincipalType"];
        };
        /**
         * PersonOut
         * @description `name` is null only for someone the organisation does not know (any more).
         */
        PersonOut: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Name */
            name: string | null;
            type: components["schemas"]["PrincipalType"];
        };
        /**
         * PersonalAgentsIn
         * @description Allow (or stop) personal agents for everyone with `ai.use`; off, existing
         *     personal agents stop working (`agent.personal_disabled`).
         */
        PersonalAgentsIn: {
            /** Enabled */
            enabled: boolean;
            /** Version */
            version: number;
        };
        /**
         * PersonalServerOut
         * @description A server that acts with each person's own connector, and whether the caller
         *     has connected theirs.
         */
        PersonalServerOut: {
            /** Connected */
            connected: boolean;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Name */
            name: string;
            /** Oauth Client Id */
            oauth_client_id: string | null;
            /** Url */
            url: string;
        };
        /** PlaceOut */
        PlaceOut: {
            /**
             * Conversation Id
             * Format: uuid
             */
            conversation_id: string;
            /** Name */
            name: string | null;
            /** Space Id */
            space_id: string | null;
            /** Ticket Number */
            ticket_number: number | null;
            /**
             * Type
             * @enum {string}
             */
            type: "dm" | "channel" | "ticket";
        };
        /** PreviewIn */
        PreviewIn: {
            /** Schedule */
            schedule: components["schemas"]["OnceIn"] | components["schemas"]["RecurringIn"] | components["schemas"]["HeartbeatIn"] | components["schemas"]["EventIn"];
        };
        /** PreviewOut */
        PreviewOut: {
            /** Terms */
            terms: string[];
        };
        /**
         * Price
         * @description A model's price per million tokens (EUR); cached tokens count as input.
         */
        "Price-Input": {
            /** Input */
            input: number | string;
            /** Output */
            output: number | string;
        };
        /**
         * Price
         * @description A model's price per million tokens (EUR); cached tokens count as input.
         */
        "Price-Output": {
            /** Input */
            input: string;
            /** Output */
            output: string;
        };
        /** PrincipalRef */
        PrincipalRef: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            type: components["schemas"]["PrincipalType"];
        };
        /**
         * PrincipalType
         * @enum {string}
         */
        PrincipalType: "user" | "agent" | "group";
        /**
         * Priority
         * @enum {string}
         */
        Priority: "low" | "normal" | "high" | "urgent";
        /** ProblemOut */
        ProblemOut: {
            /** File */
            file: string;
            /** Reason */
            reason: string;
            source: components["schemas"]["Source"];
        };
        /** ProfileUpdateIn */
        ProfileUpdateIn: {
            /** Locale */
            locale: string;
            /** Version */
            version: number;
        };
        /**
         * ProposalAcceptIn
         * @description `version`: the proposal's. `merged_content` with `page_version` (the page's
         *     version it was merged against): the text to write instead of the proposal, after
         *     a 409 `proposal.base_outdated`.
         */
        ProposalAcceptIn: {
            /** Merged Content */
            merged_content?: string | null;
            /** Page Version */
            page_version?: number | null;
            /** Version */
            version: number;
        };
        /**
         * ProposalAuthorOut
         * @description A person or an agent, by name (null if it is gone).
         */
        ProposalAuthorOut: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Name */
            name: string | null;
            type: components["schemas"]["PrincipalType"];
        };
        /** ProposalDeciderOut */
        ProposalDeciderOut: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Name */
            name: string | null;
        };
        /**
         * ProposalDetailOut
         * @description With the proposed `content_md` and `diff`, line by line from the base (empty for
         *     a new page) to it; null when the texts are beyond `HERD_DIFF_MAX_LINES`
         *     (`too_large`). For an open change: `page_version`, the page's version now (name it
         *     with `merged_content` when accepting); and when the page's content is no longer
         *     the base, `current_content_md` and `merge` (null when too large).
         */
        ProposalDetailOut: {
            /** Ai */
            ai: boolean;
            author: components["schemas"]["ProposalAuthorOut"];
            /** Base Version */
            base_version: number | null;
            /** Content Md */
            content_md: string;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /** Current Content Md */
            current_content_md: string | null;
            /** Decided At */
            decided_at: string | null;
            decided_by: components["schemas"]["ProposalDeciderOut"] | null;
            /** Decision Reason */
            decision_reason: string | null;
            /** Diff */
            diff: components["schemas"]["HunkOut"][] | null;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            kind: components["schemas"]["ProposalKind"];
            merge: components["schemas"]["ProposalMergeOut"] | null;
            /** Page Id */
            page_id: string | null;
            /** Page Version */
            page_version: number | null;
            /** Parent Id */
            parent_id: string | null;
            /** Reason */
            reason: string;
            /** Result Version */
            result_version: number | null;
            /** Run Id */
            run_id: string | null;
            /**
             * Space Id
             * Format: uuid
             */
            space_id: string;
            state: components["schemas"]["ProposalState"];
            /** Title */
            title: string | null;
            /** Too Large */
            too_large: boolean;
            /** Version */
            version: number;
            /** Via Token */
            via_token?: string | null;
        };
        /**
         * ProposalKind
         * @enum {string}
         */
        ProposalKind: "change" | "new";
        /**
         * ProposalMergeOut
         * @description The three-way merge of base, proposal and the page now: `merged_content` when it
         *     merges cleanly (null with conflicts), and the merge in `segments`.
         */
        ProposalMergeOut: {
            /** Clean */
            clean: boolean;
            /** Merged Content */
            merged_content: string | null;
            /** Segments */
            segments: components["schemas"]["ProposalSegmentOut"][];
        };
        /**
         * ProposalOut
         * @description A proposal without its content. `kind`: `change` of `page_id`, based on its
         *     version `base_version`; or `new`, a page `title` under `parent_id` (null: the top
         *     level), whose `page_id` is the page it became once accepted. `ai`: made by an agent
         *     (`run_id`: its run) or by a person's AI client through an access token
         *     (`via_token`: the token's name, plan M8). `decided_by`/`decided_at`: who
         *     accepted, rejected or (its author's person) withdrew it, and when;
         *     `decision_reason`: a rejection's reason; `result_version`: the page version an
         *     acceptance wrote (null if the page held that content already). `version`: name
         *     it when deciding (stale → 409).
         */
        ProposalOut: {
            /** Ai */
            ai: boolean;
            author: components["schemas"]["ProposalAuthorOut"];
            /** Base Version */
            base_version: number | null;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /** Decided At */
            decided_at: string | null;
            decided_by: components["schemas"]["ProposalDeciderOut"] | null;
            /** Decision Reason */
            decision_reason: string | null;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            kind: components["schemas"]["ProposalKind"];
            /** Page Id */
            page_id: string | null;
            /** Parent Id */
            parent_id: string | null;
            /** Reason */
            reason: string;
            /** Result Version */
            result_version: number | null;
            /** Run Id */
            run_id: string | null;
            /**
             * Space Id
             * Format: uuid
             */
            space_id: string;
            state: components["schemas"]["ProposalState"];
            /** Title */
            title: string | null;
            /** Version */
            version: number;
            /** Via Token */
            via_token?: string | null;
        };
        /** ProposalRejectIn */
        ProposalRejectIn: {
            /** Reason */
            reason?: string | null;
            /** Version */
            version: number;
        };
        /**
         * ProposalSegmentOut
         * @description `clean`: merged `lines`; `conflict`: the stretch as in the base, as proposed and
         *     as on the page now (the other three lists are empty for the other kind).
         */
        ProposalSegmentOut: {
            /** Base */
            base: string[];
            /** Current */
            current: string[];
            /**
             * Kind
             * @enum {string}
             */
            kind: "clean" | "conflict";
            /** Lines */
            lines: string[];
            /** Proposed */
            proposed: string[];
        };
        /**
         * ProposalState
         * @enum {string}
         */
        ProposalState: "open" | "accepted" | "rejected" | "withdrawn";
        /**
         * ProviderCheckOut
         * @description `code` is None when discovery and the JWKS answered as OIDC promises.
         */
        ProviderCheckOut: {
            /** Code */
            code: string | null;
            /** Ok */
            ok: boolean;
        };
        /**
         * ProviderCreate
         * @description `google`: issuer and scopes are the preset's (`issuer`, `scopes`, `trust_email`
         *     are refused); `generic`: `issuer` is required, `scopes` must hold `openid`.
         */
        ProviderCreate: {
            /**
             * Allow Signup
             * @default false
             */
            allow_signup?: boolean;
            /**
             * Allowed Domains
             * @default []
             */
            allowed_domains?: string[];
            /** Client Id */
            client_id: string;
            client_secret?: components["schemas"]["OidcSecretIn"] | null;
            /**
             * Enabled
             * @default false
             */
            enabled?: boolean;
            /** Issuer */
            issuer?: string | null;
            /** Key */
            key?: string | null;
            kind: components["schemas"]["ProviderKind"];
            /** Name */
            name?: string | null;
            /** Scopes */
            scopes?: string | null;
            /**
             * Trust Email
             * @default false
             */
            trust_email?: boolean;
        };
        /**
         * ProviderKind
         * @enum {string}
         */
        ProviderKind: "google" | "generic";
        /** ProviderOut */
        ProviderOut: {
            /** Allow Signup */
            allow_signup: boolean;
            /** Allowed Domains */
            allowed_domains: string[];
            /** Callback Url */
            callback_url: string | null;
            /** Client Id */
            client_id: string;
            client_secret: components["schemas"]["SecretState"];
            /** Discovered */
            discovered: boolean;
            /** Enabled */
            enabled: boolean;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Issuer */
            issuer: string;
            /** Key */
            key: string;
            kind: components["schemas"]["ProviderKind"];
            /** Name */
            name: string;
            /** Scopes */
            scopes: string;
            /** Trust Email */
            trust_email: boolean;
            /** Version */
            version: number;
        };
        /**
         * ProviderUpdate
         * @description Only the fields sent change; `client_secret` replaces the stored one.
         */
        ProviderUpdate: {
            /** Allow Signup */
            allow_signup?: boolean | null;
            /** Allowed Domains */
            allowed_domains?: string[] | null;
            /** Client Id */
            client_id?: string | null;
            client_secret?: components["schemas"]["OidcSecretIn"] | null;
            /** Enabled */
            enabled?: boolean | null;
            /** Issuer */
            issuer?: string | null;
            /** Name */
            name?: string | null;
            /** Scopes */
            scopes?: string | null;
            /** Trust Email */
            trust_email?: boolean | null;
            /** Version */
            version: number;
        };
        /** PublicProviderOut */
        PublicProviderOut: {
            /** Key */
            key: string;
            kind: components["schemas"]["ProviderKind"];
            /** Name */
            name: string;
        };
        /**
         * Purpose
         * @enum {string}
         */
        Purpose: "chat" | "embedding" | "both";
        /** QuestionAnswer */
        QuestionAnswer: {
            /** Text */
            text: string;
            /** Version */
            version: number;
        };
        /**
         * QuestionOut
         * @description An agent's question; `question` and `answer` only for the person asked (for
         *     everyone else null, with `redacted` true: the model's words, as in the run view).
         */
        QuestionOut: {
            /**
             * Addressed To
             * Format: uuid
             */
            addressed_to: string;
            /** Answer */
            answer: string | null;
            /** Answered At */
            answered_at: string | null;
            /**
             * Conversation Id
             * Format: uuid
             */
            conversation_id: string;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /**
             * Expires At
             * Format: date-time
             */
            expires_at: string;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Message Id */
            message_id: string | null;
            /** Question */
            question: string | null;
            /** Redacted */
            redacted: boolean;
            /**
             * Run Id
             * Format: uuid
             */
            run_id: string;
            state: components["schemas"]["QuestionState"];
            /** Version */
            version: number;
        };
        /**
         * QuestionState
         * @enum {string}
         */
        QuestionState: "pending" | "answered" | "expired";
        /**
         * ReactionOut
         * @description People who reacted with `emoji`; `mine`: the caller among them.
         */
        ReactionOut: {
            /** Count */
            count: number;
            /** Emoji */
            emoji: string;
            /** Mine */
            mine: boolean;
        };
        /** ReadPosition */
        ReadPosition: {
            /**
             * Message Id
             * Format: uuid
             */
            message_id: string;
        };
        /**
         * ReadPositionOut
         * @description The caller's read position: the message she read up to and when it was written;
         *     both null before she read anything there.
         */
        ReadPositionOut: {
            /** Last Read Message At */
            last_read_message_at: string | null;
            /** Last Read Message Id */
            last_read_message_id: string | null;
        };
        /**
         * RecoveryCodesOut
         * @description Ten recovery codes, shown this once; each signs in once instead of a code.
         */
        RecoveryCodesOut: {
            /** Recovery Codes */
            recovery_codes: string[];
        };
        /** RecurringIn */
        RecurringIn: {
            /** Cron */
            cron: string;
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            kind: "recurring";
            /** Time Zone */
            time_zone: string;
        };
        /**
         * RefreshOut
         * @description How reading the tool list went: counts of tools new, with another fingerprint
         *     and no longer listed; all 0 unless `status` is `ok`.
         */
        RefreshOut: {
            /**
             * Changed
             * @default 0
             */
            changed?: number;
            /**
             * Missing
             * @default 0
             */
            missing?: number;
            /**
             * New
             * @default 0
             */
            new?: number;
            status: components["schemas"]["RemoteStatus"];
        };
        /**
         * RemoteStatus
         * @enum {string}
         */
        RemoteStatus: "ok" | "blocked" | "timeout" | "unreachable" | "unauthorized" | "forbidden" | "not_found" | "rate_limited" | "redirect" | "server_error" | "too_large" | "protocol_error" | "secret_unavailable";
        /**
         * ReplaceIn
         * @description The organisation's name, exactly, as the confirmation.
         */
        ReplaceIn: {
            /** Confirm */
            confirm: string;
        };
        /** ReplaceOut */
        ReplaceOut: {
            /** Archive Name */
            archive_name: string;
        };
        /**
         * RestoreAttemptOut
         * @description The last attempt to replace the installation from here: `requested` (under way,
         *     or its process ended), `failed` with a code.
         */
        RestoreAttemptOut: {
            /** Archive Name */
            archive_name: string | null;
            /**
             * At
             * Format: date-time
             */
            at: string;
            /** Code */
            code: string | null;
            /**
             * State
             * @enum {string}
             */
            state: "requested" | "failed";
        };
        /** RestoreStatusOut */
        RestoreStatusOut: {
            attempt: components["schemas"]["RestoreAttemptOut"] | null;
        };
        /**
         * RunEventOut
         * @description One step of a run (model call: usage and the answer's parts; tool call: name,
         *     arguments, result, the spaces it came from; stop: the reason). `redacted`: parts
         *     the reader may not read are left out (`agents/runs.py`); the asking person always
         *     gets everything. `tokens_*`, `cost` (model calls with a price) and `duration_ms`
         *     (model and tool calls) where the step recorded them, null otherwise.
         */
        RunEventOut: {
            /** Attempt */
            attempt: number;
            /** Content */
            content: {
                [key: string]: unknown;
            };
            /** Cost */
            cost: string | null;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /** Duration Ms */
            duration_ms: number | null;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            kind: components["schemas"]["EventKind"];
            /** Redacted */
            redacted: boolean;
            /** Seq */
            seq: number;
            /** Tokens Cached */
            tokens_cached: number | null;
            /** Tokens In */
            tokens_in: number | null;
            /** Tokens Out */
            tokens_out: number | null;
        };
        /**
         * RunOut
         * @description A run as the run view shows it. `asker_*`: the person who asked (whose rights it
         *     read with, who is billed); `steps`: its model calls; `attempt`: its take-ups by a
         *     worker, `recoveries` those after a lost worker; `wait_until`: while `waiting`,
         *     when it ends unanswered; `stop_reason` once `done`; `cancel_requested`: someone
         *     asked it to stop. `trigger_message_id`: the message that asked (a DM's message or
         *     a mention; null for a run on a ticket assigned to the agent); `chain_depth`: the
         *     handovers from agent to agent that led to it (0: a person asked it).
         */
        RunOut: {
            /**
             * Agent Id
             * Format: uuid
             */
            agent_id: string;
            /** Agent Name */
            agent_name: string;
            /**
             * Asker Id
             * Format: uuid
             */
            asker_id: string;
            /** Asker Name */
            asker_name: string;
            /** Attempt */
            attempt: number;
            /** Cancel Requested */
            cancel_requested: boolean;
            /** Chain Depth */
            chain_depth: number;
            /**
             * Conversation Id
             * Format: uuid
             */
            conversation_id: string;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /** Finished At */
            finished_at: string | null;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            place: components["schemas"]["RunPlaceOut"];
            /** Recoveries */
            recoveries: number;
            /** Started At */
            started_at: string | null;
            state: components["schemas"]["RunState"];
            /** Steps */
            steps: number;
            stop_reason: components["schemas"]["StopReason"] | null;
            /** Trigger Message Id */
            trigger_message_id: string | null;
            usage: components["schemas"]["RunUsageOut"];
            /** Wait Until */
            wait_until: string | null;
        };
        /**
         * RunPlaceOut
         * @description Where the run answers: the conversation's kind and id; its space, and for a
         *     thread its page or ticket, only where the reader reads that space (else null).
         */
        RunPlaceOut: {
            /**
             * Conversation Id
             * Format: uuid
             */
            conversation_id: string;
            kind: components["schemas"]["ConversationKind"];
            /** Page Id */
            page_id: string | null;
            /** Space Id */
            space_id: string | null;
            /** Ticket Number */
            ticket_number: number | null;
        };
        /**
         * RunState
         * @enum {string}
         */
        RunState: "queued" | "running" | "waiting" | "done";
        /**
         * RunUsageOut
         * @description The run's usage records summed: model calls, tokens (`tokens_in` includes the
         *     cached ones), `cost` of the priced calls (null if none had a price).
         */
        RunUsageOut: {
            /** Calls */
            calls: number;
            /** Cost */
            cost: string | null;
            /** Tokens Cached */
            tokens_cached: number;
            /** Tokens In */
            tokens_in: number;
            /** Tokens Out */
            tokens_out: number;
        };
        /**
         * SchemaProblem
         * @enum {string}
         */
        SchemaProblem: "schema_too_large" | "schema_unsupported" | "schema_property_names";
        /**
         * SearchResults
         * @description A page of hits of every kind, told apart by `type`.
         */
        SearchResults: {
            /** Items */
            items: (components["schemas"]["PageHitOut"] | components["schemas"]["MessageHitOut"] | components["schemas"]["TicketHitOut"])[];
            /** Next Cursor */
            next_cursor?: string | null;
        };
        /**
         * SecondFactorIn
         * @description Exactly one of `code` (six digits from the authenticator) and `recovery_code`.
         */
        SecondFactorIn: {
            /** Code */
            code?: string | null;
            /** Recovery Code */
            recovery_code?: string | null;
        };
        /**
         * SecondFactorNeededOut
         * @description The password (or the provider) was right; the sign-in waits for the second
         *     factor until `expires_at` (`POST /api/auth/login/second-factor`).
         */
        SecondFactorNeededOut: {
            /**
             * Expires At
             * Format: date-time
             */
            expires_at: string;
            /**
             * Second Factor
             * @default totp
             * @constant
             */
            second_factor?: "totp";
        };
        /**
         * SecretIn
         * @description Either the key itself (`value`, stored encrypted; needs `HERD_SECRET_KEY`) or
         *     the name of an environment variable `HERD_AI_*` (`env`).
         */
        SecretIn: {
            /** Env */
            env?: string | null;
            /** Value */
            value?: string | null;
        };
        /**
         * SecretKind
         * @enum {string}
         */
        SecretKind: "env" | "enc";
        /** SecretOut */
        SecretOut: {
            kind: components["schemas"]["SecretKind"] | null;
            /** Set */
            set: boolean;
        };
        /** SecretState */
        SecretState: {
            kind: components["schemas"]["SecretKind"] | null;
            /** Set */
            set: boolean;
        };
        /** ServerCreate */
        ServerCreate: {
            /** Connector Id */
            connector_id?: string | null;
            /** @default none */
            connector_scope?: components["schemas"]["ConnectorUse"];
            /** @default external */
            data_location?: components["schemas"]["DataLocation"];
            /**
             * Enabled
             * @default true
             */
            enabled?: boolean;
            /** Name */
            name: string;
            /** Oauth Client Id */
            oauth_client_id?: string | null;
            /** Url */
            url: string;
        };
        /** ServerOut */
        ServerOut: {
            /** Catalog Id */
            catalog_id: string | null;
            /** Connector Id */
            connector_id: string | null;
            connector_scope: components["schemas"]["ConnectorUse"];
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            data_location: components["schemas"]["DataLocation"];
            /** Enabled */
            enabled: boolean;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Name */
            name: string;
            /** Oauth Client Id */
            oauth_client_id: string | null;
            /**
             * Updated At
             * Format: date-time
             */
            updated_at: string;
            /** Url */
            url: string;
            /** Version */
            version: number;
        };
        /**
         * ServerUpdate
         * @description Only the fields sent change. A new URL withdraws every approval; a new origin
         *     also disconnects every personal connector of the server and detaches its shared
         *     connector, unless `keep_shared_connector` says to keep it or the change names
         *     another shared connector (`connectors/moving.py`).
         */
        ServerUpdate: {
            /** Connector Id */
            connector_id?: string | null;
            connector_scope?: components["schemas"]["ConnectorUse"] | null;
            data_location?: components["schemas"]["DataLocation"] | null;
            /** Enabled */
            enabled?: boolean | null;
            /**
             * Keep Shared Connector
             * @default false
             */
            keep_shared_connector?: boolean;
            /** Name */
            name?: string | null;
            /** Oauth Client Id */
            oauth_client_id?: string | null;
            /** Url */
            url?: string | null;
            /** Version */
            version: number;
        };
        /**
         * SessionLimitsOut
         * @description The installation's limits of a login session: it ends after `idle_hours` without
         *     use (null: no idle limit, HERD_SESSION_IDLE_HOURS=0) and at the latest after
         *     `ttl_hours` (HERD_SESSION_TTL_HOURS).
         */
        SessionLimitsOut: {
            /** Idle Hours */
            idle_hours: number | null;
            /** Ttl Hours */
            ttl_hours: number;
        };
        /**
         * SignupDecisionIn
         * @description Approve or reject a waiting account: the version the client read (409).
         */
        SignupDecisionIn: {
            /** Version */
            version: number;
        };
        /**
         * SkillAuthorOut
         * @description `name`: the person's or agent's name (none if it is gone).
         */
        SkillAuthorOut: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Name */
            name: string | null;
            type: components["schemas"]["PrincipalType"];
        };
        /**
         * SkillCreate
         * @description `space_id`: the space the skill belongs to; none: organisation-wide.
         */
        SkillCreate: {
            /** Content */
            content: string;
            /** Description */
            description: string;
            /** Name */
            name: string;
            /** Space Id */
            space_id?: string | null;
        };
        /**
         * SkillDetailOut
         * @description A skill with its instructions (`content`, Markdown).
         */
        SkillDetailOut: {
            author: components["schemas"]["SkillAuthorOut"];
            /** Content */
            content: string;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /** Description */
            description: string;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Name */
            name: string;
            /** Space Id */
            space_id: string | null;
            state: components["schemas"]["SkillState"];
            /**
             * Updated At
             * Format: date-time
             */
            updated_at: string;
            /** Version */
            version: number;
        };
        /**
         * SkillImportCreatedOut
         * @description `ignored_fields`: optional front matter fields of the format that are not kept.
         */
        SkillImportCreatedOut: {
            /** Ignored Fields */
            ignored_fields: string[];
            /** Name */
            name: string;
            /** Path */
            path: string;
            /**
             * Skill Id
             * Format: uuid
             */
            skill_id: string;
        };
        /** SkillImportOut */
        SkillImportOut: {
            /** Created */
            created: components["schemas"]["SkillImportCreatedOut"][];
            /** Skipped */
            skipped: components["schemas"]["SkillImportSkippedOut"][];
        };
        /**
         * SkillImportSkippedOut
         * @description `path`: the entry's name in the archive (`SKILL.md` for a single file).
         *     `reason`: unsafe_path, not_in_skill, file_unsupported (a skill is its SKILL.md
         *     only), too_deep, too_many, too_large, unreadable, invalid_text,
         *     frontmatter_invalid, name_invalid, description_invalid, content_invalid,
         *     name_mismatch (name and folder differ), duplicate (twice in the import), exists
         *     (the scope has a skill of that name).
         */
        SkillImportSkippedOut: {
            /** Path */
            path: string;
            /** Reason */
            reason: string;
        };
        /**
         * SkillNowOut
         * @description The changed skill as it is now: `version` is what accepting a moved-on
         *     proposal sends as `skill_version`; `number` its newest version.
         */
        SkillNowOut: {
            /** Content */
            content: string;
            /** Description */
            description: string;
            /** Number */
            number: number;
            /** Version */
            version: number;
        };
        /**
         * SkillOut
         * @description A skill without its text (lists).
         */
        SkillOut: {
            author: components["schemas"]["SkillAuthorOut"];
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /** Description */
            description: string;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Name */
            name: string;
            /** Space Id */
            space_id: string | null;
            state: components["schemas"]["SkillState"];
            /**
             * Updated At
             * Format: date-time
             */
            updated_at: string;
            /** Version */
            version: number;
        };
        /**
         * SkillProposalAccept
         * @description `description`/`content`: the final text (none: as proposed). `skill_version`:
         *     the skill's `version` the moderator decided on; needed once the skill moved on
         *     (409 `skill_proposal.base_outdated` names it).
         */
        SkillProposalAccept: {
            /** Content */
            content?: string | null;
            /** Description */
            description?: string | null;
            /** Skill Version */
            skill_version?: number | null;
            /** Version */
            version: number;
        };
        /**
         * SkillProposalDetailOut
         * @description With the proposed text and, for a change, the skill now (`outdated`: it has a
         *     newer version than `base_number`; accepting then needs `skill_version`).
         */
        SkillProposalDetailOut: {
            author: components["schemas"]["SkillAuthorOut"];
            /** Base Number */
            base_number: number | null;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            current: components["schemas"]["SkillNowOut"] | null;
            /** Decided At */
            decided_at: string | null;
            decided_by: components["schemas"]["SkillAuthorOut"] | null;
            /** Decision Reason */
            decision_reason: string | null;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            kind: components["schemas"]["SkillProposalKind"];
            /** Name */
            name: string | null;
            /** Outdated */
            outdated: boolean;
            proposed: components["schemas"]["SkillTextOut"];
            /** Reason */
            reason: string;
            /** Result Number */
            result_number: number | null;
            /** Run Id */
            run_id: string | null;
            /** Skill Id */
            skill_id: string | null;
            /** Space Id */
            space_id: string | null;
            state: components["schemas"]["SkillProposalState"];
            /** Version */
            version: number;
        };
        /**
         * SkillProposalKind
         * @enum {string}
         */
        SkillProposalKind: "change" | "new";
        /**
         * SkillProposalOut
         * @description `name`: a new skill's name, or the changed skill's name now. `base_number`: the
         *     skill's newest version when it was proposed (a change). `result_number`: the
         *     version an accepted proposal made (none if the skill already held its text).
         */
        SkillProposalOut: {
            author: components["schemas"]["SkillAuthorOut"];
            /** Base Number */
            base_number: number | null;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /** Decided At */
            decided_at: string | null;
            decided_by: components["schemas"]["SkillAuthorOut"] | null;
            /** Decision Reason */
            decision_reason: string | null;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            kind: components["schemas"]["SkillProposalKind"];
            /** Name */
            name: string | null;
            /** Reason */
            reason: string;
            /** Result Number */
            result_number: number | null;
            /** Run Id */
            run_id: string | null;
            /** Skill Id */
            skill_id: string | null;
            /** Space Id */
            space_id: string | null;
            state: components["schemas"]["SkillProposalState"];
            /** Version */
            version: number;
        };
        /** SkillProposalReject */
        SkillProposalReject: {
            /** Reason */
            reason?: string | null;
            /** Version */
            version: number;
        };
        /**
         * SkillProposalState
         * @enum {string}
         */
        SkillProposalState: "open" | "accepted" | "rejected";
        /**
         * SkillState
         * @enum {string}
         */
        SkillState: "active" | "archived";
        /** SkillTextOut */
        SkillTextOut: {
            /** Content */
            content: string;
            /** Description */
            description: string;
        };
        /**
         * SkillUpdate
         * @description Only what is given changes; a given field cannot be null.
         */
        SkillUpdate: {
            /** Content */
            content?: string | null;
            /** Description */
            description?: string | null;
            /** Name */
            name?: string | null;
            /** Version */
            version: number;
        };
        /** SkillVersionDetailOut */
        SkillVersionDetailOut: {
            author: components["schemas"]["SkillAuthorOut"];
            /** Content */
            content: string;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /** Description */
            description: string;
            /** Number */
            number: number;
        };
        /** SkillVersionIn */
        SkillVersionIn: {
            /** Version */
            version: number;
        };
        /** SkillVersionOut */
        SkillVersionOut: {
            author: components["schemas"]["SkillAuthorOut"];
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /** Description */
            description: string;
            /** Number */
            number: number;
        };
        /**
         * SkippedOut
         * @description `path`: the entry's name in the archive. `reason`: unsafe_path, not_markdown,
         *     exists, duplicate, too_deep, too_large, invalid_text, unreadable, no_page, or why an
         *     attachment was refused (type_not_allowed, type_mismatch, filename_invalid).
         */
        SkippedOut: {
            /** Path */
            path: string;
            /** Reason */
            reason: string;
        };
        /**
         * Sort
         * @enum {string}
         */
        Sort: "updated" | "due" | "priority" | "number";
        /**
         * Source
         * @enum {string}
         */
        Source: "shipped" | "operator";
        /**
         * SpaceCreate
         * @description `personal` is a valid kind but not one the API creates (422 spaces.kind_not_allowed).
         */
        SpaceCreate: {
            /** Description */
            description?: string | null;
            /** Icon */
            icon?: string | null;
            kind: components["schemas"]["SpaceKind"];
            /** Name */
            name: string;
        };
        /**
         * SpaceKind
         * @enum {string}
         */
        SpaceKind: "open" | "team" | "personal";
        /** SpaceMemberIn */
        SpaceMemberIn: {
            /**
             * Member Id
             * Format: uuid
             */
            member_id: string;
            /**
             * Member Type
             * @enum {string}
             */
            member_type: "user" | "group" | "agent";
            role: components["schemas"]["SpaceRole"];
        };
        /**
         * SpaceMemberOut
         * @description `name`: the person's, group's or agent's display name.
         */
        SpaceMemberOut: {
            /**
             * Member Id
             * Format: uuid
             */
            member_id: string;
            member_type: components["schemas"]["PrincipalType"];
            /** Name */
            name: string;
            role: components["schemas"]["SpaceRole"];
        };
        /**
         * SpaceOut
         * @description `my_role` is the caller's role there, for display (system admins: `admin`).
         *     `ai_policy`/`allowed_locations`: what AI may receive of the space (spec 7.3).
         *     `agent_write_policy`: whether agents propose page changes (`propose`) or may write
         *     pages directly (`direct`, plan M6 decision 8). `review_interval_days`: pages not
         *     reviewed for that many days are due for review (null: off; plan M7 decision 11).
         */
        SpaceOut: {
            agent_write_policy: components["schemas"]["AgentWritePolicy"];
            ai_policy: components["schemas"]["AiPolicy"];
            /** Allowed Locations */
            allowed_locations: components["schemas"]["DataLocation"][];
            /** Description */
            description: string | null;
            /** Icon */
            icon: string | null;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            kind: components["schemas"]["SpaceKind"];
            my_role: components["schemas"]["SpaceRole"] | null;
            /** Name */
            name: string;
            /** Owner User Id */
            owner_user_id: string | null;
            /** Review Interval Days */
            review_interval_days: number | null;
            /** Version */
            version: number;
        };
        /**
         * SpaceRole
         * @description A role inside one space, ordered `viewer < editor < moderator < admin` (by rank,
         *     not alphabetically, so `max()` gives the strongest).
         * @enum {string}
         */
        SpaceRole: "viewer" | "editor" | "moderator" | "admin";
        /** SpaceUpdateIn */
        SpaceUpdateIn: {
            agent_write_policy?: components["schemas"]["AgentWritePolicy"] | null;
            ai_policy?: components["schemas"]["AiPolicy"] | null;
            /** Allowed Locations */
            allowed_locations?: components["schemas"]["DataLocation"][] | null;
            /** Description */
            description?: string | null;
            /** Icon */
            icon?: string | null;
            /** Name */
            name?: string | null;
            /** Review Interval Days */
            review_interval_days?: number | null;
            /** Version */
            version: number;
        };
        /**
         * SprintClose
         * @description Where the sprint's unfinished tickets go: the space's next planned sprint (the
         *     one that starts first) or the backlog.
         */
        SprintClose: {
            move_open_to: components["schemas"]["MoveOpenTo"];
            /** Version */
            version: number;
        };
        /**
         * SprintCreate
         * @description A new sprint, planned; `ends_on` is no earlier than `starts_on`, both between
         *     2000-01-01 and 2100-12-31 (else 422 `sprint.dates_invalid`).
         */
        SprintCreate: {
            /**
             * Ends On
             * Format: date
             */
            ends_on: string;
            /**
             * Goal
             * @description a short text
             * @default
             */
            goal?: string;
            /** Name */
            name: string;
            /**
             * Starts On
             * Format: date
             */
            starts_on: string;
        };
        /**
         * SprintOut
         * @description `tally` only for a closed sprint. `version` guards writes (stale → 409).
         */
        SprintOut: {
            /**
             * Ends On
             * Format: date
             */
            ends_on: string;
            /** Goal */
            goal: string;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Name */
            name: string;
            /**
             * Space Id
             * Format: uuid
             */
            space_id: string;
            /**
             * Starts On
             * Format: date
             */
            starts_on: string;
            state: components["schemas"]["SprintState"];
            tally: components["schemas"]["SprintTally"] | null;
            /** Version */
            version: number;
        };
        /** SprintStart */
        SprintStart: {
            /** Version */
            version: number;
        };
        /**
         * SprintState
         * @enum {string}
         */
        SprintState: "planned" | "active" | "closed";
        /**
         * SprintTally
         * @description Recorded when the sprint closed: the tickets it held then, those done, and those
         *     carried on (to the next sprint or the backlog).
         */
        SprintTally: {
            /** Carried */
            carried: number;
            /** Done */
            done: number;
            /** Planned */
            planned: number;
        };
        /**
         * SprintUpdate
         * @description Fields left out stay as they are (none can be null); a closed sprint does not
         *     change (409 `sprint.state_invalid`). Dates as for a new sprint.
         */
        SprintUpdate: {
            /** Ends On */
            ends_on?: string | null;
            /** Goal */
            goal?: string | null;
            /** Name */
            name?: string | null;
            /** Starts On */
            starts_on?: string | null;
            /** Version */
            version: number;
        };
        /**
         * StatusCategory
         * @enum {string}
         */
        StatusCategory: "open" | "active" | "review" | "done" | "cancelled";
        /**
         * StatusCreate
         * @description Without `position`, the new status comes last.
         */
        StatusCreate: {
            category: components["schemas"]["StatusCategory"];
            /** Name */
            name: string;
            /** Position */
            position?: number | null;
        };
        /**
         * StatusOut
         * @description A status of a space's workflow; `position` orders a space's statuses (0 first);
         *     the logic reads only `category`.
         */
        StatusOut: {
            category: components["schemas"]["StatusCategory"];
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Name */
            name: string;
            /** Position */
            position: number;
            /**
             * Space Id
             * Format: uuid
             */
            space_id: string;
            /** Version */
            version: number;
        };
        /** StatusRef */
        StatusRef: {
            category: components["schemas"]["StatusCategory"];
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Name */
            name: string;
        };
        /**
         * StatusUpdate
         * @description Fields left out stay as they are; none of them can be null. `position` moves
         *     the status there, the others close up.
         */
        StatusUpdate: {
            category?: components["schemas"]["StatusCategory"] | null;
            /** Name */
            name?: string | null;
            /** Position */
            position?: number | null;
            /** Version */
            version: number;
        };
        /**
         * StopReason
         * @enum {string}
         */
        StopReason: "completed" | "max_steps" | "deadline" | "no_progress" | "rights_revoked" | "policy_blocked" | "provider_refused" | "error" | "cancelled" | "waiting_timeout" | "approval_expired" | "budget";
        /**
         * SystemEntryOut
         * @description A system message's timeline entry, for the client to word: `key` is the page or
         *     ticket event (`page.published`, `ticket.status_changed`, ...), `actor` who caused
         *     it (null if unknown; an agent with `type` `agent`), `number` the restored version
         *     (only for `page.version_restored`), `old`/`new` what a ticket field changed from
         *     and to (null where there was nothing, and always for title and description),
         *     `run_id` the agent's run that made a ticket change (plan M6 task 6),
         *     `automation_id` the automation whose term `automation.started` opened (plan M7;
         *     `actor` is its owner), `budget_scope` whose daily limit stopped a run
         *     (`run.stopped` to `budget`: `user`, `agent` or `organisation`), `stop_detail` why
         *     beyond the reason (`run.stopped` to `policy_blocked`: `personal_connector`, the
         *     answer held what the asking person read with her own connector).
         */
        SystemEntryOut: {
            actor: components["schemas"]["PersonNameOut"] | null;
            /** Automation Id */
            automation_id?: string | null;
            budget_scope?: components["schemas"]["BudgetScope"] | null;
            /** Key */
            key: string;
            new: components["schemas"]["SystemValueOut"] | null;
            /** Number */
            number: number | null;
            old: components["schemas"]["SystemValueOut"] | null;
            /** Run Id */
            run_id?: string | null;
            /** Stop Detail */
            stop_detail?: "personal_connector" | null;
        };
        /**
         * SystemRole
         * @description A person's organisation-wide role. There is always at least one active owner.
         * @enum {string}
         */
        SystemRole: "owner" | "admin" | "member" | "guest";
        /**
         * SystemValueOut
         * @description A value a ticket changed from or to: an id (person, status, parent ticket), an
         *     enumeration value or a date; `name` names an id (the person, the status, the
         *     parent's key `HC-<n>`), null for other values and for what is gone.
         */
        SystemValueOut: {
            /** Name */
            name: string | null;
            /** Value */
            value: string;
        };
        /**
         * TagCreate
         * @description Without `space_id` a system-wide tag (`tag.manage`); with one, a tag of that
         *     space (`page.moderate` there).
         */
        TagCreate: {
            /**
             * Color
             * @default #64748b
             */
            color?: string;
            /** Name */
            name: string;
            /** Space Id */
            space_id?: string | null;
        };
        /**
         * TagOut
         * @description `space_id` null: a system-wide tag.
         */
        TagOut: {
            /** Color */
            color: string;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Name */
            name: string;
            /** Space Id */
            space_id: string | null;
            /** Version */
            version: number;
        };
        /**
         * TagUpdate
         * @description Fields left out stay as they are; neither may be null. A tag keeps its scope.
         */
        TagUpdate: {
            /** Color */
            color?: string | null;
            /** Name */
            name?: string | null;
            /** Version */
            version: number;
        };
        /**
         * TagsSet
         * @description The object's tags from now on (the set replaces the old one); `version` is the
         *     page version the client read.
         */
        TagsSet: {
            /** Tag Ids */
            tag_ids: string[];
            /** Version */
            version: number;
        };
        /**
         * TargetIn
         * @description A chat connection and one of its models (route names for the b-api).
         */
        TargetIn: {
            /**
             * Connection Id
             * Format: uuid
             */
            connection_id: string;
            /** Model */
            model: string;
        };
        /** TargetOut */
        TargetOut: {
            /**
             * Connection Id
             * Format: uuid
             */
            connection_id: string;
            /** Connection Name */
            connection_name: string;
            /** Model */
            model: string;
        };
        /** TestOut */
        TestOut: {
            /** Duration Ms */
            duration_ms: number;
            status: components["schemas"]["RemoteStatus"];
            /** Tools */
            tools: number | null;
        };
        /**
         * TicketCountsOut
         * @description For the sidebar: the caller's tickets that are open, active or in review.
         */
        TicketCountsOut: {
            /** Assigned Open */
            assigned_open: number;
        };
        /**
         * TicketCreate
         * @description Without `status_id`, the space's first status of category `open`. An assignee
         *     other than oneself needs `ticket.assign`.
         */
        TicketCreate: {
            assignee?: components["schemas"]["AssigneeIn"] | null;
            /**
             * Description Md
             * @description Markdown
             * @default
             */
            description_md?: string;
            /** Due On */
            due_on?: string | null;
            /** @default task */
            kind?: components["schemas"]["TicketKind"];
            /** Parent Id */
            parent_id?: string | null;
            /** @default normal */
            priority?: components["schemas"]["Priority"];
            /** Status Id */
            status_id?: string | null;
            /** Title */
            title: string;
        };
        /**
         * TicketHitOut
         * @description A ticket (`id`; addresses use `number`, people read `key`). `snippet` (from the
         *     description) and `score` as for pages; input shaped like a visible ticket's key
         *     ranks that ticket first.
         */
        TicketHitOut: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Key */
            key: string;
            kind: components["schemas"]["TicketKind"];
            /** Number */
            number: number;
            /** Score */
            score: number;
            /** Snippet */
            snippet: string;
            /**
             * Space Id
             * Format: uuid
             */
            space_id: string;
            /** Space Name */
            space_name: string;
            status: components["schemas"]["StatusRef"];
            /** Title */
            title: string;
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            type: "ticket";
        };
        /**
         * TicketKind
         * @enum {string}
         */
        TicketKind: "epic" | "story" | "task" | "bug";
        /**
         * TicketOut
         * @description A ticket with its description, how many children it has per category and its
         *     sprint by name (module review M4b, finding 10).
         */
        TicketOut: {
            assignee: components["schemas"]["PersonOut"] | null;
            /**
             * Awaiting Pickup
             * @default false
             */
            awaiting_pickup?: boolean;
            children: components["schemas"]["ChildCounts"];
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /** Description Md */
            description_md: string;
            /** Due On */
            due_on: string | null;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Key */
            key: string;
            kind: components["schemas"]["TicketKind"];
            /** Number */
            number: number;
            parent: components["schemas"]["ParentOut"] | null;
            priority: components["schemas"]["Priority"];
            reporter: components["schemas"]["PersonOut"];
            /**
             * Space Id
             * Format: uuid
             */
            space_id: string;
            sprint: components["schemas"]["TicketSprintOut"] | null;
            /** Sprint Id */
            sprint_id: string | null;
            status: components["schemas"]["StatusRef"];
            /**
             * Status Changed At
             * Format: date-time
             */
            status_changed_at: string;
            /** Tags */
            tags: components["schemas"]["TagOut"][];
            /** Title */
            title: string;
            /**
             * Updated At
             * Format: date-time
             */
            updated_at: string;
            /** Version */
            version: number;
            /** Via Token */
            via_token?: string | null;
        };
        /** TicketPlaceIn */
        TicketPlaceIn: {
            /** Ticket Number */
            ticket_number: number;
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            type: "ticket";
        };
        /**
         * TicketSprintOut
         * @description The ticket's sprint (one of its own space).
         */
        TicketSprintOut: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Name */
            name: string;
            state: components["schemas"]["SprintState"];
        };
        /**
         * TicketSummaryOut
         * @description A ticket as a list row shows it. `key` is `HC-<number>`; addresses use the
         *     number. `version` guards writes (send it back; stale → 409). `tags` by name.
         *     `status_changed_at`: when its status last changed (or it was made). `via_token`:
         *     made by its reporter's AI client through an access token at `/mcp` (the token's
         *     name, the AI mark; plan M8). `awaiting_pickup`: assigned to an external agent and
         *     still open: it waits for the agent to pick it up through `/mcp` (plan M8).
         */
        TicketSummaryOut: {
            assignee: components["schemas"]["PersonOut"] | null;
            /**
             * Awaiting Pickup
             * @default false
             */
            awaiting_pickup?: boolean;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /** Due On */
            due_on: string | null;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Key */
            key: string;
            kind: components["schemas"]["TicketKind"];
            /** Number */
            number: number;
            parent: components["schemas"]["ParentOut"] | null;
            priority: components["schemas"]["Priority"];
            reporter: components["schemas"]["PersonOut"];
            /**
             * Space Id
             * Format: uuid
             */
            space_id: string;
            /** Sprint Id */
            sprint_id: string | null;
            status: components["schemas"]["StatusRef"];
            /**
             * Status Changed At
             * Format: date-time
             */
            status_changed_at: string;
            /** Tags */
            tags: components["schemas"]["TagOut"][];
            /** Title */
            title: string;
            /**
             * Updated At
             * Format: date-time
             */
            updated_at: string;
            /** Version */
            version: number;
            /** Via Token */
            via_token?: string | null;
        };
        /**
         * TicketTagsSet
         * @description The ticket's tags from now on (the set replaces the old one): system-wide tags
         *     and tags of the ticket's space; `version` is the ticket version the client read.
         */
        TicketTagsSet: {
            /** Tag Ids */
            tag_ids: string[];
            /** Version */
            version: number;
        };
        /**
         * TicketUpdate
         * @description Fields left out stay as they are; null clears `due_on`, `parent_id`, `assignee`
         *     and `sprint_id` (the others cannot be null). Taking an unassigned ticket or letting go
         *     of one's own needs `ticket.edit`; any other assignment `ticket.assign`.
         */
        TicketUpdate: {
            assignee?: components["schemas"]["AssigneeIn"] | null;
            /** Description Md */
            description_md?: string | null;
            /** Due On */
            due_on?: string | null;
            kind?: components["schemas"]["TicketKind"] | null;
            /** Parent Id */
            parent_id?: string | null;
            priority?: components["schemas"]["Priority"] | null;
            /**
             * Sprint Id
             * @description a planned or active sprint of the space; null: the backlog
             */
            sprint_id?: string | null;
            /** Status Id */
            status_id?: string | null;
            /** Title */
            title?: string | null;
            /** Version */
            version: number;
        };
        /**
         * TodayOut
         * @description Today's use (UTC day) in the budget's scope. `tokens_reached`: its token limit
         *     is reached (every call stops); `cost_reached`: its currency limit is reached
         *     (calls with a price stop, those without still count toward tokens only);
         *     `exhausted`: either (a priced call stops).
         */
        TodayOut: {
            /** Cost */
            cost: string;
            /** Cost Reached */
            cost_reached: boolean;
            /** Exhausted */
            exhausted: boolean;
            /** Tokens */
            tokens: number;
            /** Tokens Reached */
            tokens_reached: boolean;
            /** Unpriced Calls */
            unpriced_calls: number;
        };
        /** TokenAgentOut */
        TokenAgentOut: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Name */
            name: string;
        };
        /**
         * TokenAuth
         * @description How a client secret goes to the token endpoint (RFC 6749 2.3.1).
         * @enum {string}
         */
        TokenAuth: "client_secret_basic" | "client_secret_post";
        /**
         * TokenCreatedOut
         * @description `secret`: the token's clear text, shown this once and stored nowhere.
         */
        TokenCreatedOut: {
            /** Agent Id */
            agent_id?: string | null;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /**
             * Expires At
             * Format: date-time
             */
            expires_at: string;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            kind: components["schemas"]["TokenKind"];
            /** Last Used At */
            last_used_at: string | null;
            mode: components["schemas"]["TokenMode"];
            /** Name */
            name: string;
            /** Revoked At */
            revoked_at: string | null;
            /** Secret */
            secret: string;
            /** Space Ids */
            space_ids: string[] | null;
        };
        /**
         * TokenIn
         * @description `space_ids`: the spaces the token may reach (each one the person reads, else
         *     422 `token.space_invalid`); left out or null: all the person's spaces.
         *     `expires_in_days`: required, 1 to 365.
         */
        TokenIn: {
            /** Expires In Days */
            expires_in_days: number;
            mode: components["schemas"]["TokenMode"];
            /** Name */
            name: string;
            /** Second Factor Code */
            second_factor_code?: string | null;
            /** Space Ids */
            space_ids?: string[] | null;
        };
        /**
         * TokenKind
         * @enum {string}
         */
        TokenKind: "personal" | "agent";
        /**
         * TokenMode
         * @enum {string}
         */
        TokenMode: "read" | "write";
        /**
         * TokenOut
         * @description `agent_id`: an agent token's external agent (kind `agent`), else null.
         */
        TokenOut: {
            /** Agent Id */
            agent_id?: string | null;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /**
             * Expires At
             * Format: date-time
             */
            expires_at: string;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            kind: components["schemas"]["TokenKind"];
            /** Last Used At */
            last_used_at: string | null;
            mode: components["schemas"]["TokenMode"];
            /** Name */
            name: string;
            /** Revoked At */
            revoked_at: string | null;
            /** Space Ids */
            space_ids: string[] | null;
        };
        /** TokenUserOut */
        TokenUserOut: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Name */
            name: string;
        };
        /**
         * ToolClassify
         * @description `read` for a tool the server does not annotate read-only loosens what the admin
         *     was offered: it needs `confirm_loosen`.
         */
        ToolClassify: {
            classification: components["schemas"]["Classification"];
            /**
             * Confirm Loosen
             * @default false
             */
            confirm_loosen?: boolean;
            /** Version */
            version: number;
        };
        /** ToolOut */
        ToolOut: {
            /** Approved Description */
            approved_description: string | null;
            /** Approved Fingerprint */
            approved_fingerprint: string | null;
            /** Approved Input Schema */
            approved_input_schema: {
                [key: string]: unknown;
            } | null;
            classification: components["schemas"]["Classification"];
            /** Description */
            description: string;
            /** Fingerprint */
            fingerprint: string;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Input Schema */
            input_schema: {
                [key: string]: unknown;
            };
            /** Missing */
            missing: boolean;
            /** Name */
            name: string;
            /** Read Only Hint */
            read_only_hint: boolean;
            schema_problem: components["schemas"]["SchemaProblem"] | null;
            /**
             * Server Id
             * Format: uuid
             */
            server_id: string;
            state: components["schemas"]["ToolState"];
            suggested_classification: components["schemas"]["Classification"] | null;
            /**
             * Updated At
             * Format: date-time
             */
            updated_at: string;
            /** Version */
            version: number;
        };
        /**
         * ToolState
         * @enum {string}
         */
        ToolState: "pending" | "approved" | "blocked" | "changed";
        /** ToolVersionIn */
        ToolVersionIn: {
            /** Version */
            version: number;
        };
        /** TotpCodeIn */
        TotpCodeIn: {
            /** Code */
            code: string;
        };
        /** TotpSetupIn */
        TotpSetupIn: {
            /** Password */
            password: string;
        };
        /**
         * TotpSetupOut
         * @description The secret in base32 and as an `otpauth://` URI (for a QR code), shown this once.
         */
        TotpSetupOut: {
            /** Secret */
            secret: string;
            /** Uri */
            uri: string;
        };
        /**
         * TotpStatusOut
         * @description `enabled_at`: when TOTP was turned on (null: off). `unavailable`: why it cannot
         *     be set up (`no_password`: an account without a password signs in through its
         *     provider, whose MFA applies; `no_secret_key`: the operator set no
         *     `HERD_SECRET_KEY`); null when it can.
         */
        TotpStatusOut: {
            /** Enabled At */
            enabled_at: string | null;
            /** Recovery Codes Left */
            recovery_codes_left: number;
            /** Unavailable */
            unavailable: ("no_password" | "no_secret_key") | null;
        };
        /**
         * TrashedPageOut
         * @description A page that went into the trash on its own or with the pages below it; `path`
         *     and `parent_id` are where it was.
         */
        TrashedPageOut: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Parent Id */
            parent_id: string | null;
            /** Path */
            path: string;
            status: components["schemas"]["PageStatus"];
            /** Title */
            title: string;
            /**
             * Trashed At
             * Format: date-time
             */
            trashed_at: string;
        };
        /**
         * TreeNodeOut
         * @description A page in the flat tree: nest by `parent_id`, order siblings by `sort_order`.
         *     `tags`: tag ids, by name. `review_due`: as on the page.
         */
        TreeNodeOut: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Parent Id */
            parent_id: string | null;
            /** Path */
            path: string;
            /** Review Due */
            review_due: boolean;
            /** Slug */
            slug: string;
            /** Sort Order */
            sort_order: number;
            status: components["schemas"]["PageStatus"];
            /** Tags */
            tags: string[];
            /** Title */
            title: string;
        };
        /**
         * UnreadOut
         * @description `unread`: others' top-level messages after the read position (not deleted);
         *     `mentions`: mentions of the caller after it, in threads too.
         */
        UnreadOut: {
            /**
             * Conversation Id
             * Format: uuid
             */
            conversation_id: string;
            /** Mentions */
            mentions: number;
            /** Unread */
            unread: number;
        };
        /**
         * UsageRowOut
         * @description One UTC day and, when grouped, one person, agent, space or connection (`key_id`;
         *     null for calls without one, such as an embedding batch). `name`: the key's
         *     display name where known.
         */
        UsageRowOut: {
            /** Calls */
            calls: number;
            /** Cost */
            cost: string | null;
            /**
             * Day
             * Format: date
             */
            day: string;
            /** Duration Ms */
            duration_ms: number;
            /** Key Id */
            key_id: string | null;
            /** Name */
            name: string | null;
            /** Tokens Cached */
            tokens_cached: number;
            /** Tokens In */
            tokens_in: number;
            /** Tokens Out */
            tokens_out: number;
            /** Unpriced Calls */
            unpriced_calls: number;
        };
        /**
         * UserAssignmentIn
         * @description A connection and model, or `no_ai: true`. `version`: the one read, or null to
         *     create (409 if the person has one meanwhile).
         */
        UserAssignmentIn: {
            /**
             * No Ai
             * @default false
             */
            no_ai?: boolean;
            target?: components["schemas"]["TargetIn"] | null;
            /** Version */
            version: number | null;
        };
        /** UserAssignmentOut */
        UserAssignmentOut: {
            /** No Ai */
            no_ai: boolean;
            target: components["schemas"]["TargetOut"] | null;
            /**
             * User Id
             * Format: uuid
             */
            user_id: string;
            /** User Name */
            user_name: string;
            /** Version */
            version: number;
        };
        /** UserCreate */
        UserCreate: {
            /**
             * Email
             * Format: email
             */
            email: string;
            /**
             * Locale
             * @default de
             */
            locale?: string;
            /** Name */
            name: string;
            /** Password */
            password?: string | null;
            /** @default member */
            system_role?: components["schemas"]["SystemRole"];
        };
        /** UserOut */
        UserOut: {
            /** Awaiting Approval Since */
            awaiting_approval_since: string | null;
            /** Email */
            email: string;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Is Active */
            is_active: boolean;
            /** Last Login At */
            last_login_at: string | null;
            /** Locale */
            locale: string;
            /** Name */
            name: string;
            system_role: components["schemas"]["SystemRole"];
            /** Version */
            version: number;
        };
        /**
         * UserUpdateIn
         * @description The PATCH body: the changes plus the version the client read.
         */
        UserUpdateIn: {
            /** Locale */
            locale?: string | null;
            /** Name */
            name?: string | null;
            /** Password */
            password?: string | null;
            system_role?: components["schemas"]["SystemRole"] | null;
            /** Version */
            version: number;
        };
        /** ValidationError */
        ValidationError: {
            /** Context */
            ctx?: Record<string, never>;
            /** Input */
            input?: unknown;
            /** Location */
            loc: (string | number)[];
            /** Message */
            msg: string;
            /** Error Type */
            type: string;
        };
        /**
         * VersionAuthor
         * @description `name` is None for an author that is not a person.
         */
        VersionAuthor: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Name */
            name: string | null;
            type: components["schemas"]["PrincipalType"];
        };
        /** VersionIn */
        VersionIn: {
            /** Version */
            version: number;
        };
        /**
         * VersionLabelIn
         * @description null takes the label away.
         */
        VersionLabelIn: {
            /** Label */
            label: string | null;
        };
        /** VersionOut */
        VersionOut: {
            /** Ai */
            ai: boolean;
            author: components["schemas"]["VersionAuthor"];
            /** Change Summary */
            change_summary: string | null;
            /** Content Md */
            content_md: string;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /** Label */
            label: string | null;
            /** Number */
            number: number;
            /** Run Id */
            run_id: string | null;
            source: components["schemas"]["VersionSource"];
            /** Title */
            title: string;
            /** Via Token */
            via_token?: string | null;
        };
        /**
         * VersionSource
         * @enum {string}
         */
        VersionSource: "human" | "import" | "restore" | "collab" | "agent" | "mcp";
        /**
         * VersionSummaryOut
         * @description `change_summary` is free text, or `restore:<n>` for a version that brought
         *     version n back (the client words it). `ai`: the AI mark (spec 9): written for an
         *     agent (`run_id`: its run), or a person's version through an access token
         *     (`via_token`: the token's name; source `mcp`, plan M8).
         */
        VersionSummaryOut: {
            /** Ai */
            ai: boolean;
            author: components["schemas"]["VersionAuthor"];
            /** Change Summary */
            change_summary: string | null;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /** Label */
            label: string | null;
            /** Number */
            number: number;
            /** Run Id */
            run_id: string | null;
            source: components["schemas"]["VersionSource"];
            /** Title */
            title: string;
            /** Via Token */
            via_token?: string | null;
        };
        /** ExpectedVersion */
        app__modules__messaging__schemas__ExpectedVersion: {
            /** Version */
            version: number;
        };
        /**
         * ExpectedVersion
         * @description The page version the client read (stale → 409 `page.version_conflict`).
         */
        app__modules__wiki__schemas__ExpectedVersion: {
            /** Version */
            version: number;
        };
    };
    responses: never;
    parameters: never;
    requestBodies: never;
    headers: never;
    pathItems: never;
}
export type $defs = Record<string, never>;
export interface operations {
    list_activity_api_activity_get: {
        parameters: {
            query?: {
                limit?: number;
                cursor?: string | null;
                /** @description true: done entries too */
                include_done?: boolean;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Page_ActivityOut_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    count_activity_api_activity_count_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ActivityCountOut"];
                };
            };
        };
    };
    read_all_api_activity_read_all_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
        };
    };
    mark_done_api_activity__notification_id__done_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                notification_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    mark_read_api_activity__notification_id__read_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                notification_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_audit_api_admin_audit_get: {
        parameters: {
            query?: {
                limit?: number;
                cursor?: string | null;
                actor_id?: string | null;
                action?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Page_AuditOut_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_calendar_settings_api_admin_calendar_settings_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CalendarSettingsOut"];
                };
            };
        };
    };
    set_calendar_settings_api_admin_calendar_settings_put: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["CalendarSettingsIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CalendarSettingsOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    find_dms_api_admin_dm_inspect_get: {
        parameters: {
            query: {
                /** @description whose direct messages */
                user_id: string;
                limit?: number;
                cursor?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Page_InspectableDmOut_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    grant_inspection_api_admin_dm_inspect_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["InspectionCreate"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["InspectionOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    inspected_messages_api_admin_dm_inspect__inspection_id__messages_get: {
        parameters: {
            query?: {
                limit?: number;
                cursor?: string | null;
            };
            header?: never;
            path: {
                inspection_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Page_MessageOut_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_groups_api_admin_groups_get: {
        parameters: {
            query?: {
                limit?: number;
                cursor?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Page_GroupOut_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    create_group_api_admin_groups_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["GroupCreate"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["GroupOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_group_api_admin_groups__group_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                group_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["GroupOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    delete_group_api_admin_groups__group_id__delete: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                group_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    update_group_api_admin_groups__group_id__patch: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                group_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["GroupUpdateIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["GroupOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_group_members_api_admin_groups__group_id__members_get: {
        parameters: {
            query?: {
                limit?: number;
                cursor?: string | null;
            };
            header?: never;
            path: {
                group_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Page_GroupMemberOut_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    add_group_member_api_admin_groups__group_id__members_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                group_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["GroupMemberIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    remove_group_member_api_admin_groups__group_id__members__member_type___member_id__delete: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                group_id: string;
                member_type: "user";
                member_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_providers_api_admin_oidc_providers_get: {
        parameters: {
            query?: {
                limit?: number;
                cursor?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Page_ProviderOut_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    create_provider_api_admin_oidc_providers_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ProviderCreate"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProviderOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_provider_api_admin_oidc_providers__provider_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                provider_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProviderOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    delete_provider_api_admin_oidc_providers__provider_id__delete: {
        parameters: {
            query: {
                version: number;
            };
            header?: never;
            path: {
                provider_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    update_provider_api_admin_oidc_providers__provider_id__patch: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                provider_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ProviderUpdate"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProviderOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    check_provider_api_admin_oidc_providers__provider_id__check_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                provider_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProviderCheckOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_users_api_admin_users_get: {
        parameters: {
            query?: {
                limit?: number;
                cursor?: string | null;
                /** @description true: only accounts awaiting approval */
                pending?: boolean;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Page_AdminUserOut_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    create_user_api_admin_users_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["UserCreate"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["UserOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    count_pending_api_admin_users_pending_count_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PendingCountOut"];
                };
            };
        };
    };
    update_user_api_admin_users__user_id__patch: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                user_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["UserUpdateIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["UserOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    approve_signup_api_admin_users__user_id__approve_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                user_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SignupDecisionIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["UserOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    deactivate_user_api_admin_users__user_id__deactivate_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                user_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_user_identities_api_admin_users__user_id__identities_get: {
        parameters: {
            query?: {
                limit?: number;
                cursor?: string | null;
            };
            header?: never;
            path: {
                user_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Page_IdentityOut_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    unlink_user_identity_api_admin_users__user_id__identities__identity_id__delete: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                user_id: string;
                identity_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    reactivate_user_api_admin_users__user_id__reactivate_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                user_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    reject_signup_api_admin_users__user_id__reject_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                user_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SignupDecisionIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    sign_out_user_api_admin_users__user_id__sign_out_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                user_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    reset_totp_api_admin_users__user_id__totp_reset_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                user_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_agents_api_agents_get: {
        parameters: {
            query?: {
                limit?: number;
                cursor?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Page_AgentOut_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    create_agent_api_agents_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["AgentCreate"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AgentOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_agent_api_agents__agent_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                agent_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AgentOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    delete_agent_api_agents__agent_id__delete: {
        parameters: {
            query: {
                version: number;
            };
            header?: never;
            path: {
                agent_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    update_agent_api_agents__agent_id__patch: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                agent_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["AgentUpdate"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AgentOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    automations_of_agent_api_agents__agent_id__automations_get: {
        parameters: {
            query?: {
                limit?: number;
                cursor?: string | null;
            };
            header?: never;
            path: {
                agent_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Page_AutomationOut_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    agent_profile_api_agents__agent_id__profile_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                agent_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AgentProfileOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    runs_of_agent_api_agents__agent_id__runs_get: {
        parameters: {
            query?: {
                limit?: number;
                cursor?: string | null;
                state?: components["schemas"]["RunState"] | null;
                stop_reason?: components["schemas"]["StopReason"] | null;
                since?: string | null;
                until?: string | null;
            };
            header?: never;
            path: {
                agent_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Page_RunOut_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_agent_skills_api_agents__agent_id__skills_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                agent_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AgentSkillsOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    set_agent_skills_api_agents__agent_id__skills_put: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                agent_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["AgentSkillsPut"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AgentSkillsOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_agent_spaces_api_agents__agent_id__spaces_get: {
        parameters: {
            query?: {
                limit?: number;
                cursor?: string | null;
            };
            header?: never;
            path: {
                agent_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Page_AgentSpaceOut_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_agent_tokens_api_agents__agent_id__tokens_get: {
        parameters: {
            query?: {
                limit?: number;
                cursor?: string | null;
            };
            header?: never;
            path: {
                agent_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Page_TokenOut_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    create_agent_token_api_agents__agent_id__tokens_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                agent_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["TokenIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["TokenCreatedOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    revoke_agent_token_api_agents__agent_id__tokens__token_id__delete: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                agent_id: string;
                token_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_agent_token_calls_api_agents__agent_id__tokens__token_id__calls_get: {
        parameters: {
            query?: {
                limit?: number;
                cursor?: string | null;
            };
            header?: never;
            path: {
                agent_id: string;
                token_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Page_McpCallOut_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    agent_tools_api_agents__agent_id__tools_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                agent_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AgentToolsOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    set_agent_tools_api_agents__agent_id__tools_put: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                agent_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["AgentToolsPut"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AgentToolsOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_assignments_api_ai_assignments_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AssignmentsOut"];
                };
            };
        };
    };
    set_default_assignment_api_ai_assignments_default_put: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["DefaultIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AssignmentsOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_group_assignments_api_ai_assignments_groups_get: {
        parameters: {
            query?: {
                limit?: number;
                cursor?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Page_GroupAssignmentOut_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    set_group_assignments_api_ai_assignments_groups_put: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["GroupsIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AssignmentsOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    set_personal_agents_api_ai_assignments_personal_agents_put: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["PersonalAgentsIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AssignmentsOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_user_assignments_api_ai_assignments_users_get: {
        parameters: {
            query?: {
                limit?: number;
                cursor?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Page_UserAssignmentOut_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    set_user_assignment_api_ai_assignments_users__user_id__put: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                user_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["UserAssignmentIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["UserAssignmentOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    remove_user_assignment_api_ai_assignments_users__user_id__delete: {
        parameters: {
            query: {
                version: number;
            };
            header?: never;
            path: {
                user_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_budgets_api_ai_budgets_get: {
        parameters: {
            query?: {
                limit?: number;
                cursor?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Page_BudgetOut_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    budget_agents_api_ai_budgets_agents_get: {
        parameters: {
            query?: {
                limit?: number;
                cursor?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Page_AgentPickOut_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    set_agent_budget_api_ai_budgets_agents__agent_id__put: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                agent_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["BudgetIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BudgetOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    set_organisation_budget_api_ai_budgets_organisation_put: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["BudgetIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BudgetOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    set_user_budget_api_ai_budgets_users__user_id__put: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                user_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["BudgetIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BudgetOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    delete_budget_api_ai_budgets__budget_id__delete: {
        parameters: {
            query: {
                version: number;
            };
            header?: never;
            path: {
                budget_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_connections_api_ai_connections_get: {
        parameters: {
            query?: {
                limit?: number;
                cursor?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Page_ConnectionOut_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    create_connection_api_ai_connections_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ConnectionCreate"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ConnectionOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_connection_api_ai_connections__connection_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                connection_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ConnectionOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    delete_connection_api_ai_connections__connection_id__delete: {
        parameters: {
            query: {
                version: number;
            };
            header?: never;
            path: {
                connection_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    update_connection_api_ai_connections__connection_id__patch: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                connection_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ConnectionUpdate"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ConnectionOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    fetch_models_api_ai_connections__connection_id__models_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                connection_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["VersionIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ConnectionOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    test_connection_api_ai_connections__connection_id__test_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                connection_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["CheckIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CheckOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_connectors_api_ai_connectors_get: {
        parameters: {
            query?: {
                limit?: number;
                cursor?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Page_ConnectorOut_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    create_connector_api_ai_connectors_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ConnectorCreate"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ConnectorOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_connector_api_ai_connectors__connector_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                connector_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ConnectorOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    delete_connector_api_ai_connectors__connector_id__delete: {
        parameters: {
            query: {
                version: number;
            };
            header?: never;
            path: {
                connector_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    update_connector_api_ai_connectors__connector_id__patch: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                connector_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ConnectorUpdate"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ConnectorOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    authorize_connector_api_ai_connectors__connector_id__authorize_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                connector_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AuthorizeOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    disconnect_connector_api_ai_connectors__connector_id__disconnect_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                connector_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["VersionIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ConnectorOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_mcp_settings_api_ai_mcp_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["McpSettingsOut"];
                };
            };
        };
    };
    set_mcp_settings_api_ai_mcp_put: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["McpSettingsIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["McpSettingsOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_entries_api_ai_mcp_catalog_get: {
        parameters: {
            query?: {
                limit?: number;
                cursor?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Page_CatalogEntry_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_problems_api_ai_mcp_catalog_problems_get: {
        parameters: {
            query?: {
                limit?: number;
                cursor?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Page_ProblemOut_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_entry_api_ai_mcp_catalog__entry_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                entry_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CatalogEntry"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    install_entry_api_ai_mcp_catalog__entry_id__install_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                entry_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["InstallIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["InstallOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_servers_api_ai_mcp_servers_get: {
        parameters: {
            query?: {
                limit?: number;
                cursor?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Page_ServerOut_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    create_server_api_ai_mcp_servers_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ServerCreate"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CreatedServerOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_server_api_ai_mcp_servers__server_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                server_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ServerOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    delete_server_api_ai_mcp_servers__server_id__delete: {
        parameters: {
            query: {
                version: number;
            };
            header?: never;
            path: {
                server_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    update_server_api_ai_mcp_servers__server_id__patch: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                server_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ServerUpdate"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ServerOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    refresh_tools_api_ai_mcp_servers__server_id__refresh_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                server_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RefreshOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    test_server_api_ai_mcp_servers__server_id__test_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                server_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["TestOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_tools_api_ai_mcp_servers__server_id__tools_get: {
        parameters: {
            query?: {
                limit?: number;
                cursor?: string | null;
            };
            header?: never;
            path: {
                server_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Page_ToolOut_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    classify_tool_api_ai_mcp_servers__server_id__tools__tool_id__patch: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                server_id: string;
                tool_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ToolClassify"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ToolOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    approve_tool_api_ai_mcp_servers__server_id__tools__tool_id__approve_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                server_id: string;
                tool_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ToolVersionIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ToolOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    block_tool_api_ai_mcp_servers__server_id__tools__tool_id__block_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                server_id: string;
                tool_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ToolVersionIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ToolOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_all_tokens_api_ai_mcp_tokens_get: {
        parameters: {
            query?: {
                limit?: number;
                cursor?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Page_AdminTokenOut_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    revoke_any_token_api_ai_mcp_tokens__token_id__delete: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                token_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_any_token_calls_api_ai_mcp_tokens__token_id__calls_get: {
        parameters: {
            query?: {
                limit?: number;
                cursor?: string | null;
            };
            header?: never;
            path: {
                token_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Page_McpCallOut_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_connectors_api_ai_my_connectors_get: {
        parameters: {
            query?: {
                limit?: number;
                cursor?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Page_ConnectorOut_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    create_connector_api_ai_my_connectors_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ConnectorCreate"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ConnectorOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_connector_api_ai_my_connectors__connector_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                connector_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ConnectorOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    delete_connector_api_ai_my_connectors__connector_id__delete: {
        parameters: {
            query: {
                version: number;
            };
            header?: never;
            path: {
                connector_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    update_connector_api_ai_my_connectors__connector_id__patch: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                connector_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ConnectorUpdate"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ConnectorOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    authorize_connector_api_ai_my_connectors__connector_id__authorize_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                connector_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AuthorizeOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    disconnect_connector_api_ai_my_connectors__connector_id__disconnect_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                connector_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["VersionIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ConnectorOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_personal_servers_api_ai_my_mcp_servers_get: {
        parameters: {
            query?: {
                limit?: number;
                cursor?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Page_PersonalServerOut_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_clients_api_ai_oauth_clients_get: {
        parameters: {
            query?: {
                limit?: number;
                cursor?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Page_ClientOut_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    create_client_api_ai_oauth_clients_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ClientCreate"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ClientOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    discover_client_api_ai_oauth_clients_discover_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["DiscoverIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["DiscoveryOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_client_api_ai_oauth_clients__client_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                client_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ClientOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    delete_client_api_ai_oauth_clients__client_id__delete: {
        parameters: {
            query: {
                version: number;
            };
            header?: never;
            path: {
                client_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    update_client_api_ai_oauth_clients__client_id__patch: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                client_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ClientUpdate"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ClientOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    oauth_legacy_callback_api_ai_oauth_callback_get: {
        parameters: {
            query?: {
                state?: string | null;
                code?: string | null;
                error?: string | null;
                iss?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            303: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    oauth_callback_api_ai_oauth__client_id__callback_get: {
        parameters: {
            query?: {
                state?: string | null;
                code?: string | null;
                error?: string | null;
                iss?: string | null;
            };
            header?: never;
            path: {
                client_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            303: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_usage_api_ai_usage_get: {
        parameters: {
            query?: {
                limit?: number;
                cursor?: string | null;
                /** @description first UTC day; default: 29 days before `to` */
                from?: string | null;
                /** @description last UTC day; default: today */
                to?: string | null;
                /** @description group each day further */
                by?: components["schemas"]["GroupBy"] | null;
                /** @description only this run's calls */
                run_id?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Page_UsageRowOut_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    my_usage_api_ai_usage_me_get: {
        parameters: {
            query?: {
                /** @description first UTC day; default: 29 days before `to` */
                from?: string | null;
                /** @description last UTC day; default: today */
                to?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["MyUsageOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    my_approvals_api_approvals_get: {
        parameters: {
            query?: {
                limit?: number;
                cursor?: string | null;
                /** @description only this state */
                state?: components["schemas"]["ApprovalState"] | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Page_ApprovalOut_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_approval_api_approvals__approval_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                approval_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApprovalOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    decide_approval_api_approvals__approval_id__decide_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                approval_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ApprovalDecide"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApprovalOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    approval_diff_api_approvals__approval_id__diff_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                approval_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HunkOut"][] | null;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    download_attachment_api_attachments__attachment_id__get: {
        parameters: {
            query?: {
                /** @description show a raster image in the page */
                inline?: boolean;
            };
            header?: never;
            path: {
                attachment_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/octet-stream": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    delete_attachment_api_attachments__attachment_id__delete: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                attachment_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    set_attachment_ai_lock_api_attachments__attachment_id__ai_lock_put: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                attachment_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["AiLockIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AttachmentOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    login_api_auth_login_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["LoginRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["MeOut"];
                };
            };
            /** @description Second factor needed */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SecondFactorNeededOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    second_factor_api_auth_login_second_factor_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SecondFactorIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["MeOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    logout_api_auth_logout_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
        };
    };
    me_api_auth_me_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["MeOut"];
                };
            };
        };
    };
    update_me_api_auth_me_patch: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ProfileUpdateIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["MeOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    my_identities_api_auth_me_identities_get: {
        parameters: {
            query?: {
                limit?: number;
                cursor?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Page_IdentityOut_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    unlink_mine_api_auth_me_identities__identity_id__delete: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                identity_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    link_api_auth_me_identities__key__link_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                key: string;
            };
            cookie?: never;
        };
        requestBody?: {
            content: {
                "application/json": components["schemas"]["LinkStartIn"] | null;
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["LinkStartOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    change_my_password_api_auth_me_password_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["PasswordChangeIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_own_sessions_api_auth_me_sessions_get: {
        parameters: {
            query?: {
                limit?: number;
                cursor?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["OwnSessionPage"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    sign_out_others_api_auth_me_sessions_sign_out_others_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
        };
    };
    end_own_session_api_auth_me_sessions__session_id__delete: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                session_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    my_totp_api_auth_me_totp_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["TotpStatusOut"];
                };
            };
        };
    };
    confirm_totp_api_auth_me_totp_confirm_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["TotpCodeIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RecoveryCodesOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    disable_totp_api_auth_me_totp_disable_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SecondFactorIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    renew_recovery_codes_api_auth_me_totp_recovery_codes_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["TotpCodeIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RecoveryCodesOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    set_up_totp_api_auth_me_totp_setup_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["TotpSetupIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["TotpSetupOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    touch_me_api_auth_me_touch_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
        };
    };
    callback_api_auth_oidc__key__callback_get: {
        parameters: {
            query?: {
                state?: string | null;
                code?: string | null;
                error?: string | null;
            };
            header?: never;
            path: {
                key: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            302: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    start_api_auth_oidc__key__start_get: {
        parameters: {
            query?: {
                /** @description a fresh login as the proof before linking */
                reauth?: boolean;
            };
            header?: never;
            path: {
                key: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            302: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_providers_api_auth_providers_get: {
        parameters: {
            query?: {
                limit?: number;
                cursor?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Page_PublicProviderOut_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    my_automations_api_automations_get: {
        parameters: {
            query?: {
                limit?: number;
                cursor?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Page_AutomationOut_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    create_automation_api_automations_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["AutomationCreate"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AutomationOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    preview_terms_api_automations_preview_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["PreviewIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PreviewOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_automation_api_automations__automation_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                automation_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AutomationOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    delete_automation_api_automations__automation_id__delete: {
        parameters: {
            query: {
                version: number;
            };
            header?: never;
            path: {
                automation_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    update_automation_api_automations__automation_id__patch: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                automation_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["AutomationUpdate"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AutomationOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    automation_log_api_automations__automation_id__firings_get: {
        parameters: {
            query?: {
                limit?: number;
                cursor?: string | null;
            };
            header?: never;
            path: {
                automation_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Page_FiringOut_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    pause_automation_api_automations__automation_id__pause_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                automation_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["VersionIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AutomationOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    resume_automation_api_automations__automation_id__resume_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                automation_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["VersionIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AutomationOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    run_automation_now_api_automations__automation_id__run_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                automation_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AutomationOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    take_over_automation_api_automations__automation_id__take_over_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                automation_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["VersionIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AutomationOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_backups_api_backups_get: {
        parameters: {
            query?: {
                limit?: number;
                cursor?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Page_BackupRunOut_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    start_backup_api_backups_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BackupRunOut"];
                };
            };
        };
    };
    list_archives_api_backups_archives_get: {
        parameters: {
            query?: {
                limit?: number;
                cursor?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Page_ArchiveOut_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    upload_archive_api_backups_archives_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/x-tar": string;
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ArchiveOut"];
                };
            };
        };
    };
    download_archive_api_backups_archives__name__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                name: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/x-tar": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    check_archive_api_backups_archives__name__check_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                name: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ArchiveCheckOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    replace_installation_api_backups_archives__name__replace_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                name: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ReplaceIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ReplaceOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    restore_status_api_backups_restore_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RestoreStatusOut"];
                };
            };
        };
    };
    list_calendars_api_calendars_get: {
        parameters: {
            query?: {
                limit?: number;
                cursor?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Page_CalendarOut_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    archive_calendar_api_calendars__calendar_id__delete: {
        parameters: {
            query: {
                version: number;
            };
            header?: never;
            path: {
                calendar_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    update_calendar_api_calendars__calendar_id__patch: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                calendar_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["CalendarUpdate"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CalendarOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_channels_api_channels_get: {
        parameters: {
            query?: {
                limit?: number;
                cursor?: string | null;
                /** @description true: archived channels too */
                include_archived?: boolean;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Page_ConversationOut_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_unread_api_conversations_unread_get: {
        parameters: {
            query?: {
                limit?: number;
                cursor?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Page_UnreadOut_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_conversation_api_conversations__conversation_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                conversation_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ConversationOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    update_channel_api_conversations__conversation_id__patch: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                conversation_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ChannelUpdate"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ConversationOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    archive_channel_api_conversations__conversation_id__archive_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                conversation_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["app__modules__messaging__schemas__ExpectedVersion"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ConversationOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    start_conversation_afresh_api_conversations__conversation_id__fresh_start_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                conversation_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["app__modules__messaging__schemas__ExpectedVersion"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ConversationOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_messages_api_conversations__conversation_id__messages_get: {
        parameters: {
            query?: {
                limit?: number;
                cursor?: string | null;
                /** @description start below this message (newest first) */
                before?: string | null;
                /** @description oldest first, from just after this message */
                after?: string | null;
                /** @description false: without system messages (page threads) */
                include_system?: boolean;
            };
            header?: never;
            path: {
                conversation_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Page_MessageOut_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    post_message_api_conversations__conversation_id__messages_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                conversation_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["MessageCreate"];
            };
        };
        responses: {
            /** @description sent before with this client_id */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["MessageWriteOut"];
                };
            };
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["MessageWriteOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    read_position_api_conversations__conversation_id__read_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                conversation_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ReadPositionOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    mark_read_api_conversations__conversation_id__read_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                conversation_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ReadPosition"];
            };
        };
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    unarchive_channel_api_conversations__conversation_id__unarchive_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                conversation_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["app__modules__messaging__schemas__ExpectedVersion"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ConversationOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    search_directory_api_directory_get: {
        parameters: {
            query?: {
                limit?: number;
                cursor?: string | null;
                q?: string;
                type?: ("user" | "group" | "agent") | null;
                /** @description only people who read this space, and its member agents */
                space_id?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Page_DirectoryEntryOut_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_dms_api_dms_get: {
        parameters: {
            query?: {
                limit?: number;
                cursor?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Page_DmOut_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    open_dm_api_dms_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["DmOpen"];
            };
        };
        responses: {
            /** @description the group's conversation */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ConversationOut"];
                };
            };
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ConversationOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    maintenance_state_api_maintenance_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["MaintenanceOut"];
                };
            };
        };
    };
    get_message_api_messages__message_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                message_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["MessageOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    delete_message_api_messages__message_id__delete: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                message_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    edit_message_api_messages__message_id__patch: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                message_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["MessageUpdate"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["MessageWriteOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    react_api_messages__message_id__reactions__emoji__put: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                message_id: string;
                /** @description exactly one emoji (URL-encoded) */
                emoji: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ReactionOut"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    unreact_api_messages__message_id__reactions__emoji__delete: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                message_id: string;
                /** @description exactly one emoji (URL-encoded) */
                emoji: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ReactionOut"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_replies_api_messages__message_id__replies_get: {
        parameters: {
            query?: {
                limit?: number;
                cursor?: string | null;
            };
            header?: never;
            path: {
                message_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Page_MessageOut_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_page_api_pages__page_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                page_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PageOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    purge_page_api_pages__page_id__delete: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                page_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    update_page_api_pages__page_id__patch: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                page_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["PageUpdate"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PageOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    set_page_ai_lock_api_pages__page_id__ai_lock_put: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                page_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["AiLockIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PageOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_attachments_api_pages__page_id__attachments_get: {
        parameters: {
            query?: {
                limit?: number;
                cursor?: string | null;
            };
            header?: never;
            path: {
                page_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Page_AttachmentOut_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    upload_attachment_api_pages__page_id__attachments_post: {
        parameters: {
            query: {
                filename: string;
            };
            header?: never;
            path: {
                page_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/octet-stream": string;
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AttachmentOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    diff_versions_api_pages__page_id__diff_get: {
        parameters: {
            query: {
                from: number;
                to: number;
            };
            header?: never;
            path: {
                page_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["DiffOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    export_page_api_pages__page_id__export_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                page_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "text/markdown": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    move_page_api_pages__page_id__move_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                page_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["PageMove"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PageOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    publish_page_api_pages__page_id__publish_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                page_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["app__modules__wiki__schemas__ExpectedVersion"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PageOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    restore_page_api_pages__page_id__restore_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                page_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PageOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    mark_page_reviewed_api_pages__page_id__reviewed_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                page_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PageOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    set_page_tags_api_pages__page_id__tags_put: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                page_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["TagsSet"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PageOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_page_thread_api_pages__page_id__thread_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                page_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ConversationOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_page_tickets_api_pages__page_id__tickets_get: {
        parameters: {
            query?: {
                limit?: number;
                cursor?: string | null;
            };
            header?: never;
            path: {
                page_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Page_TicketSummaryOut_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    trash_page_api_pages__page_id__trash_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                page_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["app__modules__wiki__schemas__ExpectedVersion"];
            };
        };
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_versions_api_pages__page_id__versions_get: {
        parameters: {
            query?: {
                limit?: number;
                cursor?: string | null;
            };
            header?: never;
            path: {
                page_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Page_VersionSummaryOut_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_version_api_pages__page_id__versions__number__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                page_id: string;
                number: number;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["VersionOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    label_version_api_pages__page_id__versions__number__patch: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                page_id: string;
                number: number;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["VersionLabelIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["VersionSummaryOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    restore_version_api_pages__page_id__versions__number__restore_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                page_id: string;
                number: number;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["app__modules__wiki__schemas__ExpectedVersion"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PageOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_proposal_api_proposals__proposal_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                proposal_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProposalDetailOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    accept_proposal_api_proposals__proposal_id__accept_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                proposal_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ProposalAcceptIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProposalOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    reject_proposal_api_proposals__proposal_id__reject_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                proposal_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ProposalRejectIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProposalOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_question_api_questions__question_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                question_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["QuestionOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    answer_question_api_questions__question_id__answer_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                question_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["QuestionAnswer"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["QuestionOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    my_runs_api_runs_get: {
        parameters: {
            query?: {
                limit?: number;
                cursor?: string | null;
                state?: components["schemas"]["RunState"] | null;
                stop_reason?: components["schemas"]["StopReason"] | null;
                since?: string | null;
                until?: string | null;
                agent_id?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Page_RunOut_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_run_api_runs__run_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                run_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RunOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    cancel_run_api_runs__run_id__cancel_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                run_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RunOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    run_events_api_runs__run_id__events_get: {
        parameters: {
            query?: {
                limit?: number;
                cursor?: string | null;
            };
            header?: never;
            path: {
                run_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Page_RunEventOut_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    search_api_search_get: {
        parameters: {
            query?: {
                limit?: number;
                cursor?: string | null;
                q?: string;
                /** @description only this space */
                space_id?: string | null;
                /** @description only with every tag */
                tag?: string[] | null;
                /** @description what to find: page, message, ticket (comma-separated) */
                types?: string;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SearchResults"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_skill_proposals_api_skill_proposals_get: {
        parameters: {
            query?: {
                limit?: number;
                cursor?: string | null;
                /** @description only this space's */
                space_id?: string | null;
                /** @description true: only organisation-wide; false: only spaces' */
                org_wide?: boolean | null;
                /** @description only this state */
                state?: components["schemas"]["SkillProposalState"] | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Page_SkillProposalOut_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_skill_proposal_api_skill_proposals__proposal_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                proposal_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SkillProposalDetailOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    accept_skill_proposal_api_skill_proposals__proposal_id__accept_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                proposal_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SkillProposalAccept"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SkillProposalDetailOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    reject_skill_proposal_api_skill_proposals__proposal_id__reject_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                proposal_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SkillProposalReject"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SkillProposalDetailOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_skills_api_skills_get: {
        parameters: {
            query?: {
                limit?: number;
                cursor?: string | null;
                /** @description only this space's */
                space_id?: string | null;
                /** @description true: only organisation-wide; false: only spaces' */
                org_wide?: boolean | null;
                /** @description only this state */
                state?: components["schemas"]["SkillState"] | null;
                /** @description a part of the name */
                q?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Page_SkillOut_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    create_skill_api_skills_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SkillCreate"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SkillDetailOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    import_skills_api_skills_import_post: {
        parameters: {
            query?: {
                /** @description none: organisation-wide */
                space_id?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/zip": string;
                "text/markdown": string;
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SkillImportOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_skill_api_skills__skill_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                skill_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SkillDetailOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    update_skill_api_skills__skill_id__patch: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                skill_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SkillUpdate"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SkillDetailOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    archive_skill_api_skills__skill_id__archive_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                skill_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SkillVersionIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SkillDetailOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    export_skill_api_skills__skill_id__export_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                skill_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "text/markdown": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    unarchive_skill_api_skills__skill_id__unarchive_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                skill_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SkillVersionIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SkillDetailOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_skill_versions_api_skills__skill_id__versions_get: {
        parameters: {
            query?: {
                limit?: number;
                cursor?: string | null;
            };
            header?: never;
            path: {
                skill_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Page_SkillVersionOut_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_skill_version_api_skills__skill_id__versions__number__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                skill_id: string;
                number: number;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SkillVersionDetailOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    restore_skill_version_api_skills__skill_id__versions__number__restore_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                skill_id: string;
                number: number;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SkillVersionIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SkillDetailOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_spaces_api_spaces_get: {
        parameters: {
            query?: {
                limit?: number;
                cursor?: string | null;
                /** @description false: leave out other people's personal spaces */
                include_others_personal?: boolean;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Page_SpaceOut_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    create_space_api_spaces_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SpaceCreate"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SpaceOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_space_api_spaces__space_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                space_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SpaceOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    update_space_api_spaces__space_id__patch: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                space_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SpaceUpdateIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SpaceOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    automations_of_space_api_spaces__space_id__automations_get: {
        parameters: {
            query?: {
                limit?: number;
                cursor?: string | null;
            };
            header?: never;
            path: {
                space_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Page_AutomationOut_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    board_api_spaces__space_id__board_get: {
        parameters: {
            query?: {
                /** @description tickets per column (50) or per cell (20, at most 20) */
                limit?: number | null;
                /** @description `me`, a person's id, or `none`: assigned to nobody */
                assignee?: string | null;
                kind?: components["schemas"]["TicketKind"] | null;
                /** @description only with every tag */
                tag?: string[] | null;
                /** @description only an epic's children and their children */
                epic?: string | null;
                /** @description a sprint's id, or `none`: the backlog */
                sprint?: string | null;
                /** @description `assignee`: a row per person */
                group_by?: "assignee" | null;
            };
            header?: never;
            path: {
                space_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BoardOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    board_column_api_spaces__space_id__board__status_id__get: {
        parameters: {
            query?: {
                limit?: number;
                cursor?: string | null;
                /** @description `me`, a person's id, or `none`: assigned to nobody */
                assignee?: string | null;
                kind?: components["schemas"]["TicketKind"] | null;
                /** @description only with every tag */
                tag?: string[] | null;
                /** @description only an epic's children and their children */
                epic?: string | null;
                /** @description a sprint's id, or `none`: the backlog */
                sprint?: string | null;
            };
            header?: never;
            path: {
                space_id: string;
                status_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Page_TicketSummaryOut_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_space_calendars_api_spaces__space_id__calendars_get: {
        parameters: {
            query?: {
                limit?: number;
                cursor?: string | null;
            };
            header?: never;
            path: {
                space_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Page_CalendarOut_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    create_calendar_api_spaces__space_id__calendars_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                space_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["CalendarCreate"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CalendarOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_space_channels_api_spaces__space_id__channels_get: {
        parameters: {
            query?: {
                limit?: number;
                cursor?: string | null;
                /** @description true: archived channels too */
                include_archived?: boolean;
            };
            header?: never;
            path: {
                space_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Page_ConversationOut_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    create_channel_api_spaces__space_id__channels_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                space_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ChannelCreate"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ConversationOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    epics_api_spaces__space_id__epics_get: {
        parameters: {
            query?: {
                limit?: number;
                cursor?: string | null;
            };
            header?: never;
            path: {
                space_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Page_EpicOut_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    export_space_api_spaces__space_id__export_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                space_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/zip": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    import_space_api_spaces__space_id__import_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                space_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/zip": string;
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ImportResultOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_space_members_api_spaces__space_id__members_get: {
        parameters: {
            query?: {
                limit?: number;
                cursor?: string | null;
            };
            header?: never;
            path: {
                space_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Page_SpaceMemberOut_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    set_space_member_api_spaces__space_id__members_put: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                space_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SpaceMemberIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SpaceMemberOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    remove_space_member_api_spaces__space_id__members__member_type___member_id__delete: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                space_id: string;
                member_type: "user" | "group" | "agent";
                member_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    create_page_api_spaces__space_id__pages_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                space_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["PageCreate"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PageOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    page_by_path_api_spaces__space_id__pages_by_path_get: {
        parameters: {
            query: {
                /** @description e.g. `it/zugaenge` */
                path: string;
            };
            header?: never;
            path: {
                space_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PageOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    page_tree_api_spaces__space_id__pages_tree_get: {
        parameters: {
            query?: {
                limit?: number;
                cursor?: string | null;
                /** @description only pages with this tag */
                tag?: string | null;
                /** @description only pages whose review is due (plan M7 decision 11) */
                review_due?: boolean;
            };
            header?: never;
            path: {
                space_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Page_TreeNodeOut_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_proposals_api_spaces__space_id__proposals_get: {
        parameters: {
            query?: {
                limit?: number;
                cursor?: string | null;
                /** @description only this state */
                state?: components["schemas"]["ProposalState"] | null;
            };
            header?: never;
            path: {
                space_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Page_ProposalOut_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_sprints_api_spaces__space_id__sprints_get: {
        parameters: {
            query?: {
                limit?: number;
                cursor?: string | null;
                state?: components["schemas"]["SprintState"][] | null;
            };
            header?: never;
            path: {
                space_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Page_SprintOut_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    create_sprint_api_spaces__space_id__sprints_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                space_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SprintCreate"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SprintOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_statuses_api_spaces__space_id__ticket_statuses_get: {
        parameters: {
            query?: {
                limit?: number;
                cursor?: string | null;
            };
            header?: never;
            path: {
                space_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Page_StatusOut_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    create_status_api_spaces__space_id__ticket_statuses_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                space_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["StatusCreate"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["StatusOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    create_ticket_api_spaces__space_id__tickets_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                space_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["TicketCreate"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["TicketOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_trash_api_spaces__space_id__trash_get: {
        parameters: {
            query?: {
                limit?: number;
                cursor?: string | null;
            };
            header?: never;
            path: {
                space_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Page_TrashedPageOut_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    update_sprint_api_sprints__sprint_id__patch: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                sprint_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SprintUpdate"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SprintOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    close_sprint_api_sprints__sprint_id__close_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                sprint_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SprintClose"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SprintOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    start_sprint_api_sprints__sprint_id__start_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                sprint_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SprintStart"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SprintOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    stream_api_stream_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Server-sent events */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "text/event-stream": unknown;
                };
            };
            /** @description Too many streams of this login session */
            429: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
        };
    };
    list_tags_api_tags_get: {
        parameters: {
            query?: {
                limit?: number;
                cursor?: string | null;
                /** @description only system-wide tags and this space's */
                space_id?: string | null;
                /** @description only system-wide tags; not together with space_id */
                system?: boolean;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Page_TagOut_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    create_tag_api_tags_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["TagCreate"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["TagOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    delete_tag_api_tags__tag_id__delete: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                tag_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    update_tag_api_tags__tag_id__patch: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                tag_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["TagUpdate"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["TagOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    delete_status_api_ticket_statuses__status_id__delete: {
        parameters: {
            query: {
                /** @description the version read */
                version: number;
                /** @description another status of the space, for its tickets */
                replace_with?: string | null;
            };
            header?: never;
            path: {
                status_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    update_status_api_ticket_statuses__status_id__patch: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                status_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["StatusUpdate"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["StatusOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_tickets_api_tickets_get: {
        parameters: {
            query?: {
                limit?: number;
                cursor?: string | null;
                space_id?: string | null;
                status_category?: components["schemas"]["StatusCategory"][] | null;
                status_id?: string | null;
                /** @description `me`, a person's id, or `none`: assigned to nobody */
                assignee?: string | null;
                /** @description `me` or a person's id */
                reporter?: string | null;
                kind?: components["schemas"]["TicketKind"] | null;
                priority?: components["schemas"]["Priority"] | null;
                /** @description the parent's id */
                parent?: string | null;
                q?: string | null;
                due_before?: string | null;
                /** @description only with every tag */
                tag?: string[] | null;
                /** @description a sprint's id, or `none`: the backlog */
                sprint?: string | null;
                sort?: components["schemas"]["Sort"];
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Page_TicketSummaryOut_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    counts_api_tickets_counts_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["TicketCountsOut"];
                };
            };
        };
    };
    get_my_board_api_tickets_my_board_get: {
        parameters: {
            query?: {
                /** @description tickets per column */
                limit?: number;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["MyBoardOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    my_board_column_api_tickets_my_board__category__get: {
        parameters: {
            query?: {
                limit?: number;
                cursor?: string | null;
            };
            header?: never;
            path: {
                category: components["schemas"]["StatusCategory"];
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["MyCardPage"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_ticket_api_tickets__number__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                number: number;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["TicketOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    update_ticket_api_tickets__number__patch: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                number: number;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["TicketUpdate"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["TicketOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    move_category_api_tickets__number__move_category_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                number: number;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["MoveCategory"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["TicketOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_ticket_pages_api_tickets__number__pages_get: {
        parameters: {
            query?: {
                limit?: number;
                cursor?: string | null;
            };
            header?: never;
            path: {
                number: number;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Page_LinkedPageOut_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    link_page_api_tickets__number__pages__page_id__put: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                number: number;
                page_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    unlink_page_api_tickets__number__pages__page_id__delete: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                number: number;
                page_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    set_ticket_tags_api_tickets__number__tags_put: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                number: number;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["TicketTagsSet"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["TicketOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_ticket_thread_api_tickets__number__thread_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                number: number;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ConversationOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_my_tokens_api_tokens_get: {
        parameters: {
            query?: {
                limit?: number;
                cursor?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Page_TokenOut_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    create_token_api_tokens_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["TokenIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["TokenCreatedOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    revoke_my_token_api_tokens__token_id__delete: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                token_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_my_token_calls_api_tokens__token_id__calls_get: {
        parameters: {
            query?: {
                limit?: number;
                cursor?: string | null;
            };
            header?: never;
            path: {
                token_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Page_McpCallOut_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
}
