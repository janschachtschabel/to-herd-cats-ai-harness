import { hasPermission } from '@/features/auth/queries'
import type { Conversation, Me, Message, Space, SpaceRole } from '@/lib/api'

/** What the person may do in conversations. Decided only from a conversation's
 *  `can_post`, a space's `my_role` and `/auth/me` permissions (CLAUDE.md rule 12);
 *  the server checks every action again. Mirrors `channel.manage` (from moderator). */
const RANK: Record<SpaceRole, number> = { viewer: 0, editor: 1, moderator: 2, admin: 3 }

const manages = (role: SpaceRole | null | undefined) => role != null && RANK[role] >= RANK.moderator

export interface ConversationAbilities {
  /** Write, reply and react. */
  post: boolean
  /** Delete other people's messages (`channel.manage`; never in direct messages). */
  moderate: boolean
}

export function conversationAbilities(
  conversation: Conversation,
  spaceRole: SpaceRole | null | undefined,
): ConversationAbilities {
  return {
    post: conversation.can_post,
    moderate: conversation.kind !== 'dm' && !conversation.archived_at && manages(spaceRole),
  }
}

export interface MessageAbilities {
  edit: boolean
  remove: boolean
  react: boolean
}

export function messageAbilities(
  message: Message,
  abilities: ConversationAbilities,
  meId: string | undefined,
): MessageAbilities {
  const live = message.kind === 'human' && !message.deleted_at
  const own = message.author?.id === meId
  return {
    edit: live && own && abilities.post,
    remove: live && ((own && abilities.post) || abilities.moderate),
    react: live && abilities.post,
  }
}

/** Channels are made in team and open spaces by whoever may manage channels there. */
export function canCreateChannelIn(space: Space): boolean {
  return space.kind !== 'personal' && manages(space.my_role)
}

/** Starting a direct message means finding people in the directory. */
export function canOpenDm(me: Me | null): boolean {
  return hasPermission(me, 'directory.read')
}
