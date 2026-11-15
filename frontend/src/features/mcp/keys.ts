/** The query keys of external MCP servers, connectors and the catalogue. Every key
 *  starts with `mcp`. */
export const mcpKeys = {
  all: ['mcp'] as const,
  servers: ['mcp', 'servers'] as const,
  server: (id: string) => ['mcp', 'server', id] as const,
  tools: (serverId: string) => ['mcp', 'server', serverId, 'tools'] as const,
  connectors: ['mcp', 'connectors'] as const,
  connector: (id: string) => ['mcp', 'connectors', id] as const,
  myConnectors: ['mcp', 'my', 'connectors'] as const,
  myServers: ['mcp', 'my', 'servers'] as const,
  clients: ['mcp', 'clients'] as const,
  catalog: ['mcp', 'catalog'] as const,
  catalogProblems: ['mcp', 'catalog', 'problems'] as const,
}
