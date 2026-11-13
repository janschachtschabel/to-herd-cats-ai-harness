export interface paths {
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
    "/api/messages/{message_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
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
         * @description Pages the caller may see, best first; empty `q` gives an empty list.
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
}
export type webhooks = Record<string, never>;
export interface components {
    schemas: {
        /**
         * Action
         * @enum {string}
         */
        Action: "space.read" | "space.manage" | "page.create" | "page.edit" | "page.publish" | "page.trash" | "page.moderate" | "channel.post" | "channel.manage" | "space.create" | "directory.read" | "user.manage" | "group.manage" | "audit.read" | "page.purge" | "tag.manage";
        /**
         * AttachmentOut
         * @description `url` downloads it (`?inline=1` shows raster images in the page). `mime` is what
         *     the content is, whatever the upload declared.
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
         * ConversationKind
         * @enum {string}
         */
        ConversationKind: "channel";
        /**
         * ConversationOut
         * @description `can_post`: whether the caller may write here now (the right in the space, and
         *     the channel not archived). `created_by` is null for what the system set up.
         *     `version` guards writes (send it back; stale → 409).
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
            kind: components["schemas"]["ConversationKind"];
            /** Name */
            name: string | null;
            /** Space Id */
            space_id: string | null;
            /** Topic */
            topic: string | null;
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
        /** GroupCreate */
        GroupCreate: {
            /** Description */
            description?: string | null;
            /** Name */
            name: string;
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
        /** HTTPValidationError */
        HTTPValidationError: {
            /** Detail */
            detail?: components["schemas"]["ValidationError"][];
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
         */
        MeOut: {
            org: components["schemas"]["OrgOut"];
            /** Permissions */
            permissions: components["schemas"]["Action"][];
            user: components["schemas"]["UserOut"];
        };
        /**
         * MessageCreate
         * @description `parent_id`: a top-level message of the same conversation, to reply in its
         *     thread. `client_id`: the client's key for this message; sending again with the
         *     same key returns the first message (200) instead of a second one.
         */
        MessageCreate: {
            /**
             * Body Md
             * @description Markdown
             */
            body_md: string;
            /** Client Id */
            client_id?: string | null;
            /** Parent Id */
            parent_id?: string | null;
        };
        /**
         * MessageKind
         * @enum {string}
         */
        MessageKind: "human" | "system";
        /**
         * MessageOut
         * @description `author` is null for system messages. A deleted message keeps its place with
         *     `deleted_at` set and an empty `body_md`. `reply_count` and `last_reply_at` belong
         *     to top-level messages (their thread).
         */
        MessageOut: {
            author: components["schemas"]["PrincipalRef"] | null;
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
            /** Parent Id */
            parent_id: string | null;
            /** Reply Count */
            reply_count: number;
        };
        /** MessageUpdate */
        MessageUpdate: {
            /**
             * Body Md
             * @description Markdown
             */
            body_md: string;
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
        /** Page[MessageOut] */
        Page_MessageOut_: {
            /** Items */
            items: components["schemas"]["MessageOut"][];
            /** Next Cursor */
            next_cursor?: string | null;
        };
        /** Page[SearchHitOut] */
        Page_SearchHitOut_: {
            /** Items */
            items: components["schemas"]["SearchHitOut"][];
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
        /** Page[TagOut] */
        Page_TagOut_: {
            /** Items */
            items: components["schemas"]["TagOut"][];
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
         * PasswordChangeIn
         * @description A person's own new password; the current one proves it is them.
         */
        PasswordChangeIn: {
            /** Current Password */
            current_password: string;
            /** New Password */
            new_password: string;
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
        /** ProfileUpdateIn */
        ProfileUpdateIn: {
            /** Locale */
            locale: string;
            /** Version */
            version: number;
        };
        /**
         * SearchHitOut
         * @description `snippet` is plain text: render it as text and highlight what stands between
         *     `⟦` and `⟧`. `score` orders the hits (higher is better); it has no unit.
         */
        SearchHitOut: {
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
             * Type
             * @constant
             */
            type: "page";
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
         */
        SpaceOut: {
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
         * SystemRole
         * @description A person's organisation-wide role. There is always at least one active owner.
         * @enum {string}
         */
        SystemRole: "owner" | "admin" | "member" | "guest";
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
                    "application/json": components["schemas"]["MessageOut"];
                };
            };
            /** @description Successful Response */
            201: {
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
                    "application/json": components["schemas"]["Page_SearchHitOut_"];
                };
            };
            /** @description Validation Error */
            422: {
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
}
