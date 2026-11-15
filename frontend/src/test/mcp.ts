import type { Schemas } from '@/lib/api'

type Server = Schemas['ServerOut']
type Tool = Schemas['ToolOut']
type Connector = Schemas['ConnectorOut']
type Client = Schemas['ClientOut']
type Entry = Schemas['CatalogEntry']
type PersonalServer = Schemas['PersonalServerOut']

let counter = 0
const id = () => `00000000-0000-7000-8000-7${String(++counter).padStart(11, '0')}`

const AT = '2026-11-15T08:00:00Z'

export function makeServer(overrides: Partial<Server> = {}): Server {
  return {
    id: id(),
    name: 'GitHub',
    url: 'https://api.githubcopilot.com/mcp/',
    data_location: 'external',
    connector_scope: 'shared',
    connector_id: null,
    oauth_client_id: null,
    catalog_id: null,
    enabled: true,
    version: 1,
    created_at: AT,
    updated_at: AT,
    ...overrides,
  }
}

export function makeTool(overrides: Partial<Tool> = {}): Tool {
  return {
    id: id(),
    server_id: 'server-1',
    name: 'list_issues',
    description: 'Lists the issues of a repository.',
    input_schema: { type: 'object', properties: { repo: { type: 'string' } } },
    read_only_hint: true,
    fingerprint: 'f1',
    approved_fingerprint: null,
    classification: 'read',
    suggested_classification: null,
    state: 'pending',
    missing: false,
    schema_problem: null,
    version: 1,
    updated_at: AT,
    ...overrides,
  }
}

export function makeConnector(overrides: Partial<Connector> = {}): Connector {
  return {
    id: id(),
    name: 'GitHub-Token',
    scope: 'shared',
    auth_kind: 'bearer',
    header_name: null,
    oauth_client_id: null,
    mcp_server_id: null,
    has_secret: true,
    secret_kind: 'enc',
    version: 1,
    created_at: AT,
    updated_at: AT,
    ...overrides,
  }
}

export function makeClient(overrides: Partial<Client> = {}): Client {
  return {
    id: id(),
    name: 'GitLab-App',
    authorization_endpoint: 'https://gitlab.com/oauth/authorize',
    token_endpoint: 'https://gitlab.com/oauth/token',
    revocation_endpoint: 'https://gitlab.com/oauth/revoke',
    client_id: 'app-123',
    has_client_secret: false,
    client_secret_kind: null,
    token_auth: 'client_secret_post',
    scopes: 'mcp',
    resource: 'https://gitlab.com/api/v4/mcp',
    version: 1,
    created_at: AT,
    updated_at: AT,
    ...overrides,
  }
}

export function makeEntry(overrides: Partial<Entry> = {}): Entry {
  return {
    id: 'gitlab',
    name: 'GitLab',
    description: { de: 'Der MCP-Server von GitLab.', en: "GitLab's MCP server." },
    url: '{base_url}/api/v4/mcp',
    base_url: {
      default: 'https://gitlab.com',
      note: { de: 'Für eine eigene Instanz deren Adresse.', en: 'For your own instance.' },
    },
    data_location: 'external',
    connector_scopes: ['personal', 'shared'],
    auth: [
      {
        kind: 'oauth',
        oauth: {
          authorization_endpoint: '{base_url}/oauth/authorize',
          token_endpoint: '{base_url}/oauth/token',
          scopes: 'mcp',
        },
        note: { de: 'In GitLab eine Anwendung anlegen.', en: 'Create an application.' },
      },
      { kind: 'bearer', note: { de: 'Fein granulares Token.', en: 'Fine-grained token.' } },
    ],
    tools: { get_project: 'read', save_project: 'write' },
    docs: ['https://docs.gitlab.com/user/model_context_protocol/mcp_server/'],
    ...overrides,
  }
}

export function makePersonalServer(overrides: Partial<PersonalServer> = {}): PersonalServer {
  return { id: id(), name: 'GitLab', connected: false, oauth_client_id: null, ...overrides }
}
