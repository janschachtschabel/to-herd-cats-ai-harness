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
        /** Login */
        post: operations["login_api_auth_login_post"];
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
        get?: never;
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
}
export type webhooks = Record<string, never>;
export interface components {
    schemas: {
        /**
         * Action
         * @enum {string}
         */
        Action: "space.read" | "space.manage" | "page.create" | "page.edit" | "page.publish" | "page.trash" | "page.moderate" | "channel.post" | "channel.manage" | "ticket.read" | "ticket.create" | "ticket.edit" | "ticket.assign" | "space.create" | "directory.read" | "user.manage" | "group.manage" | "audit.read" | "page.purge" | "tag.manage" | "dm.inspect" | "ai.manage" | "agent.manage" | "skill.manage" | "ai.use" | "agent.create_personal";
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
         *     level has no conversation and no message, but `proposal` (plan M6); `author` may be
         *     an agent (`type`).
         */
        ActivityOut: {
            author: components["schemas"]["ActivityAuthor"] | null;
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
         * AgentCreate
         * @description `connection_id`/`model`: a chat connection of the organisation and one of its
         *     models. `responsible_user_id`: an active person (no guest) who answers for it.
         *     Both are needed for the organisation's agents (`agent.manage`). `personal`: the
         *     caller's own agent (`agent.create_personal`), which takes the caller's connection
         *     and model and has the caller as responsible person (given, they must be those).
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
         * AgentOut
         * @description An agent as those who manage it see it (`agent.manage`; a personal agent's
         *     owner); `responsible_name`: the responsible person's name; `owner_user_id`: a
         *     personal agent's owner (null: the organisation's).
         */
        AgentOut: {
            /**
             * Connection Id
             * Format: uuid
             */
            connection_id: string;
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
            /** Level */
            level: number;
            /** Max Runtime Seconds */
            max_runtime_seconds: number;
            /** Max Steps */
            max_steps: number;
            /** Model */
            model: string;
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
         * AgentProfileOut
         * @description What a person with `ai.use` learns of an agent to talk to: no instructions, no
         *     connection.
         */
        AgentProfileOut: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Intro */
            intro: string;
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
         * @description One tool of the catalog for this agent: its own `level` (the lowest that allows
         *     it) and `effect`; `default` (from the agent's level), `entry` (the agent's, or
         *     null) and `effective` (the stricter of both; what a run gets).
         */
        AgentToolOut: {
            default: components["schemas"]["Grant"];
            effect: components["schemas"]["Effect"];
            effective: components["schemas"]["Grant"];
            entry: components["schemas"]["Grant"] | null;
            /** Level */
            level: number;
            /** Name */
            name: string;
        };
        /**
         * AgentToolsOut
         * @description An agent's tool grants: every tool of the catalog (a fixed, short list, so not
         *     paged). `version`: the agent's. `max_level`: the highest level the caller may give
         *     the agent (above 2: admins, or whoever manages every space of the agent).
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
         *     personal agent takes its owner's connection and model anew with every change.
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
         * ApprovalOut
         * @description A tool call waiting for (or given) a person's release. `summary`: the tool and
         *     the ids the call names. `args`: the call's arguments, only for the person asked
         *     (null for others). `diff_url`: for a page's new content, where that person reads
         *     the diff against the page as it is now (`GET`), instead of the text.
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
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Message Id */
            message_id: string | null;
            /** Reason */
            reason: string | null;
            /**
             * Run Id
             * Format: uuid
             */
            run_id: string;
            state: components["schemas"]["ApprovalState"];
            /** Summary */
            summary: string;
            /** Tool */
            tool: string;
            /** Version */
            version: number;
        };
        /**
         * ApprovalState
         * @enum {string}
         */
        ApprovalState: "pending" | "approved" | "rejected" | "expired";
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
        /** ChannelCreate */
        ChannelCreate: {
            /** Name */
            name: string;
            /** Topic */
            topic?: string | null;
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
         *     page (null for other kinds).
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
        /**
         * DailyCardOut
         * @description A ticket of the daily view; `changed`: its status changed (or it was made) since
         *     the board's `changed_since`.
         */
        DailyCardOut: {
            assignee: components["schemas"]["PersonOut"] | null;
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
         *     member may read it.
         */
        DirectoryEntryOut: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Name */
            name: string;
            /**
             * Type
             * @enum {string}
             */
            type: "user" | "group" | "agent";
        };
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
        };
        /**
         * EventKind
         * @enum {string}
         */
        EventKind: "model_call" | "tool_call" | "stop";
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
        /**
         * MeOut
         * @description `permissions`: the system-wide actions the caller holds; clients decide what to
         *     show from these (and from a space's `my_role`), never from the role's name.
         *     `ai_model`: with `ai.use`, the name of the model the caller's AI assignment gives
         *     them (nothing else about the connection); null without.
         */
        MeOut: {
            /** Ai Model */
            ai_model: string | null;
            org: components["schemas"]["OrgOut"];
            /** Permissions */
            permissions: components["schemas"]["Action"][];
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
         *     `mentions`: the people mentioned who may see the conversation; `reactions`: by
         *     emoji, the first reacted with first. `card`: set for a run's card (`kind`
         *     `approval` or `question`).
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
            /** Reactions */
            reactions: components["schemas"]["ReactionOut"][];
            /** Reply Count */
            reply_count: number;
            /** Run Id */
            run_id?: string | null;
            system: components["schemas"]["SystemEntryOut"] | null;
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
            /** Reactions */
            reactions: components["schemas"]["ReactionOut"][];
            /** Reply Count */
            reply_count: number;
            /** Run Id */
            run_id?: string | null;
            system: components["schemas"]["SystemEntryOut"] | null;
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
        /**
         * NotificationReason
         * @enum {string}
         */
        NotificationReason: "mention" | "reply" | "assignment" | "ticket_comment" | "proposal" | "approval" | "question" | "run_stopped";
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
         *     `no_ai`: locked for AI (spec 11).
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
        /** Page[AgentOut] */
        Page_AgentOut_: {
            /** Items */
            items: components["schemas"]["AgentOut"][];
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
        /** Page[ConnectionOut] */
        Page_ConnectionOut_: {
            /** Items */
            items: components["schemas"]["ConnectionOut"][];
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
        /** Page[MessageOut] */
        Page_MessageOut_: {
            /** Items */
            items: components["schemas"]["MessageOut"][];
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
        /** Page[SkillOut] */
        Page_SkillOut_: {
            /** Items */
            items: components["schemas"]["SkillOut"][];
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
        /** Page[UserOut] */
        Page_UserOut_: {
            /** Items */
            items: components["schemas"]["UserOut"][];
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
         *     (`run_id`: its run). `decided_by`/`decided_at`: who accepted, rejected or (its
         *     author's person) withdrew it, and when; `decision_reason`: a rejection's reason;
         *     `result_version`: the page version an acceptance wrote (null if the page held
         *     that content already). `version`: name it when deciding (stale → 409).
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
         * @description An agent's question; `answer` only for the person asked.
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
            question: string;
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
         * SkillState
         * @enum {string}
         */
        SkillState: "active" | "archived";
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
         *     pages directly (`direct`, plan M6 decision 8).
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
        StopReason: "completed" | "max_steps" | "deadline" | "no_progress" | "rights_revoked" | "policy_blocked" | "provider_refused" | "error" | "cancelled" | "waiting_timeout" | "approval_expired";
        /**
         * SystemEntryOut
         * @description A system message's timeline entry, for the client to word: `key` is the page or
         *     ticket event (`page.published`, `ticket.status_changed`, ...), `actor` who caused
         *     it (null if unknown; an agent with `type` `agent`), `number` the restored version
         *     (only for `page.version_restored`), `old`/`new` what a ticket field changed from
         *     and to (null where there was nothing, and always for title and description),
         *     `run_id` the agent's run that made a ticket change (plan M6 task 6).
         */
        SystemEntryOut: {
            actor: components["schemas"]["PersonNameOut"] | null;
            /** Key */
            key: string;
            new: components["schemas"]["SystemValueOut"] | null;
            /** Number */
            number: number | null;
            old: components["schemas"]["SystemValueOut"] | null;
            /** Run Id */
            run_id?: string | null;
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
         *     `status_changed_at`: when its status last changed (or it was made).
         */
        TicketSummaryOut: {
            assignee: components["schemas"]["PersonOut"] | null;
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
         *     `tags`: tag ids, by name.
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
        };
        /**
         * VersionSource
         * @enum {string}
         */
        VersionSource: "human" | "import" | "restore" | "collab" | "agent";
        /**
         * VersionSummaryOut
         * @description `change_summary` is free text, or `restore:<n>` for a version that brought
         *     version n back (the client words it). `ai`: written for an agent (the AI mark,
         *     spec 9: its author is an agent); `run_id`: the agent's run that wrote it.
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
    list_users_api_admin_users_get: {
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
                    "application/json": components["schemas"]["Page_UserOut_"];
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
            /** @description Validation Error */
            422: {
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
}
