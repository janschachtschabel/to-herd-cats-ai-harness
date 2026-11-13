/** The query keys of tickets. Every key starts with `tickets`, so one live event about
 *  a ticket (`ticket.created`, `ticket.updated`) refreshes every ticket view at once:
 *  lists, the ticket, the board, the epics, the counter, the links of a page. */
export const ticketKeys = {
  all: ['tickets'] as const,
  lists: ['tickets', 'list'] as const,
  list: (filters: object) => ['tickets', 'list', filters] as const,
  detail: (number: number) => ['tickets', 'detail', number] as const,
  thread: (number: number) => ['tickets', 'thread', number] as const,
  pages: (number: number) => ['tickets', 'pages', number] as const,
  children: (parentId: string) => ['tickets', 'children', parentId] as const,
  counts: ['tickets', 'counts'] as const,
  statuses: (spaceId: string) => ['tickets', 'statuses', spaceId] as const,
  board: (spaceId: string, filters: object = {}) => ['tickets', 'board', spaceId, filters] as const,
  column: (spaceId: string, statusId: string, filters: object) =>
    ['tickets', 'column', spaceId, statusId, filters] as const,
  epics: (spaceId: string) => ['tickets', 'epics', spaceId] as const,
  pageTickets: (pageId: string) => ['tickets', 'page', pageId] as const,
  parents: (spaceId: string, q: string) => ['tickets', 'parents', spaceId, q] as const,
}
