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
         * @description The caller's conversation with these people: new (201) or the one they have.
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
         *     cell.
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
        Action: "space.read" | "space.manage" | "page.create" | "page.edit" | "page.publish" | "page.trash" | "page.moderate" | "channel.post" | "channel.manage" | "ticket.read" | "ticket.create" | "ticket.edit" | "ticket.assign" | "space.create" | "directory.read" | "user.manage" | "group.manage" | "audit.read" | "page.purge" | "tag.manage" | "dm.inspect" | "ai.manage" | "ai.use";
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
         *     `author` is who assigned, `snippet` is empty.
         */
        ActivityOut: {
            author: components["schemas"]["ActivityAuthor"] | null;
            conversation: components["schemas"]["ActivityConversation"];
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
            /**
             * Message Id
             * Format: uuid
             */
            message_id: string;
            /** Parent Id */
            parent_id: string | null;
            /** Read At */
            read_at: string | null;
            reason: components["schemas"]["NotificationReason"];
            /** Snippet */
            snippet: string;
        };
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
         * AssigneeIn
         * @description M4 assigns people only.
         */
        AssigneeIn: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Type
             * @constant
             */
            type: "user";
        };
        /**
         * AssignmentsOut
         * @description The standard assignment; `version` guards it and the group list.
         */
        AssignmentsOut: {
            default: components["schemas"]["TargetOut"] | null;
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
         * @description Who can be added to a space. Deliberately no email or role: any member may read it.
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
            type: "user" | "group";
        };
        /**
         * DmOpen
         * @description The other people (the caller is added); 2 to 9 people in all.
         */
        DmOpen: {
            /** User Ids */
            user_ids: string[];
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
        MessageKind: "human" | "system";
        /**
         * MessageOut
         * @description `author` is null for system messages; those carry `system` instead (null for
         *     all others) and an empty `body_md`: their stored body holds ids the reader may not
         *     be allowed to see, `system` only what is named for the reader (review M4 P1). A
         *     deleted message keeps its place with `deleted_at` set and an empty `body_md`.
         *     `reply_count` and `last_reply_at` belong to top-level messages (their thread).
         *     `mentions`: the people mentioned who may see the conversation; `reactions`: by
         *     emoji, the first reacted with first.
         */
        MessageOut: {
            author: components["schemas"]["MessageAuthorOut"] | null;
            /** Body Md */
            body_md: string;
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
         *     the conversation, and ids of nobody (indistinguishable on purpose).
         */
        MessageWriteOut: {
            author: components["schemas"]["MessageAuthorOut"] | null;
            /** Body Md */
            body_md: string;
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
        NotificationReason: "mention" | "reply" | "assignment" | "ticket_comment";
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
         * @description A person in a direct message; one who was deactivated stays listed.
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
        /** PersonNameOut */
        PersonNameOut: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Name */
            name: string;
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
         * Purpose
         * @enum {string}
         */
        Purpose: "chat" | "embedding" | "both";
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
            member_type: "user" | "group";
            role: components["schemas"]["SpaceRole"];
        };
        /**
         * SpaceMemberOut
         * @description `name`: the person's or group's display name.
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
         */
        SpaceOut: {
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
         * @description A new sprint, planned; `ends_on` is no earlier than `starts_on`.
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
         *     change (409 `sprint.state_invalid`).
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
         * SystemEntryOut
         * @description A system message's timeline entry, for the client to word: `key` is the page or
         *     ticket event (`page.published`, `ticket.status_changed`, ...), `actor` who caused
         *     it (null if unknown), `number` the restored version (only for
         *     `page.version_restored`), `old`/`new` what a ticket field changed from and to
         *     (null where there was nothing, and always for title and description).
         */
        SystemEntryOut: {
            actor: components["schemas"]["PersonNameOut"] | null;
            /** Key */
            key: string;
            new: components["schemas"]["SystemValueOut"] | null;
            /** Number */
            number: number | null;
            old: components["schemas"]["SystemValueOut"] | null;
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
         * @description A ticket with its description and how many children it has per category.
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
            source: components["schemas"]["VersionSource"];
            /** Title */
            title: string;
        };
        /**
         * VersionSource
         * @enum {string}
         */
        VersionSource: "human" | "import" | "restore" | "collab";
        /**
         * VersionSummaryOut
         * @description `change_summary` is free text, or `restore:<n>` for a version that brought
         *     version n back (the client words it).
         */
        VersionSummaryOut: {
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
                type?: ("user" | "group") | null;
                /** @description only people who read this space */
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
                /** @description tickets per column */
                limit?: number;
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
                member_type: "user" | "group";
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
