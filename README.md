# Blimp MCP Server

AI-powered automation platform MCP server built with FastAPI, integrating Gemini 2.5 Flash, Supabase, and n8n workflows.

## Features

- 🤖 **AI-Powered Analysis**: Uses Gemini 2.5 Flash to analyze user prompts and determine required apps
- 🔗 **App Connection Verification**: Checks Supabase database for user's connected apps
- ⚡ **Workflow Automation**: Triggers n8n workflows based on user requests
- 🔐 **Bearer Token Authentication**: Secure API access with bearer tokens
- 📊 **Workflow Tracking**: Saves and tracks workflow executions in Supabase
- 🔌 **Proxy API**: Routes n8n requests to third-party APIs using user-specific OAuth tokens
- 🐳 **Docker Ready**: Includes Dockerfile for easy deployment

## Architecture

\`\`\`
User Request → FastAPI Server → Gemini Analysis → Supabase Check → n8n Workflow
                                                                         ↓
n8n Workflow → MCP Proxy → User OAuth Tokens → Third-Party APIs (Gmail, Slack, etc.)
\`\`\`

## API Endpoints

### `POST /prompt`
Process user prompt and analyze required apps.

**Request Body:**
\`\`\`json
{
  "prompt": "Send a Slack message when I receive an email",
  "user_id": "user_123",
  "bearer_token": "your_bearer_token"
}
\`\`\`

**Response:**
\`\`\`json
{
  "status": "ready",
  "message": "All required apps are connected. Ready to execute workflow.",
  "required_apps": [
    {
      "app_name": "Gmail",
      "is_connected": true
    },
    {
      "app_name": "Slack",
      "is_connected": true
    }
  ],
  "workflow_id": "workflow_1234",
  "gemini_analysis": {
    "workflow_type": "email_to_slack",
    "workflow_description": "...",
    "suggested_actions": [...]
  }
}
\`\`\`

### `POST /execute-workflow`
Execute an n8n workflow after receiving go-ahead.

**Request Body:**
\`\`\`json
{
  "workflow_id": "workflow_1234",
  "user_id": "user_123",
  "bearer_token": "your_bearer_token",
  "parameters": {
    "channel": "#general",
    "filter": "important"
  }
}
\`\`\`

**Response:**
\`\`\`json
{
  "status": "success",
  "message": "Workflow execution initiated successfully",
  "execution_id": "exec_5678",
  "workflow_result": {
    "success": true,
    "data": {...}
  }
}
\`\`\`

### `GET /workflow/{workflow_id}/status`
Get the status of a workflow execution.

**Query Parameters:**
- `user_id`: User's unique identifier

**Response:**
\`\`\`json
{
  "status": "success",
  "workflow_id": "workflow_1234",
  "n8n_status": {
    "status": "running",
    "data": {...}
  },
  "database_record": {...}
}
\`\`\`

### `POST /api/mcp/connect-app`
Connect a user's app with OAuth credentials.

**Request Body:**
\`\`\`json
{
  "user_id": "user_123",
  "app_name": "Gmail",
  "app_type": "gmail",
  "credentials": {
    "access_token": "ya29.xxx",
    "refresh_token": "1//xxx",
    "token_type": "Bearer",
    "expiry_date": 1234567890,
    "scope": "https://www.googleapis.com/auth/gmail.readonly"
  },
  "metadata": {
    "email": "user@example.com",
    "connected_at": "2025-01-14T10:00:00Z",
    "scopes": ["gmail.readonly"]
  }
}
\`\`\`

**Response:**
\`\`\`json
{
  "success": true,
  "message": "App connected successfully",
  "credential_id": "cred_uuid",
  "app_name": "Gmail"
}
\`\`\`

### `POST /proxy/{app_name}/{action}`
Proxy requests to third-party APIs using user-specific OAuth tokens.

**Supported Apps:**
- `gmail`: fetchEmails, sendEmail
- `slack`: postMessage, listChannels
- `notion`: createPage, searchPages
- `calendar`: createEvent, listEvents
- `gdrive`: listFiles, uploadFile

**Request Body:**
\`\`\`json
{
  "user_id": "user_123",
  "payload": {
    // Action-specific parameters
  }
}
\`\`\`

**Example - Fetch Gmail Emails:**
\`\`\`bash
curl -X POST http://localhost:8000/proxy/gmail/fetchEmails \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user_123",
    "payload": {
      "query": "is:unread"
    }
  }'
\`\`\`

**Response:**
\`\`\`json
{
  "success": true,
  "data": {
    "emails": [...],
    "count": 5
  }
}
\`\`\`

See [PROXY_API_GUIDE.md](./PROXY_API_GUIDE.md) for complete proxy API documentation.

## Setup

### Local Development

1. **Clone the repository**
\`\`\`bash
git clone <repository-url>
cd blimp-mcp-server
\`\`\`

2. **Create virtual environment**
\`\`\`bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
\`\`\`

3. **Install dependencies**
\`\`\`bash
pip install -r requirements.txt
\`\`\`

4. **Configure environment variables**
\`\`\`bash
cp .env.example .env
# Edit .env with your actual credentials
\`\`\`

5. **Run the server**
\`\`\`bash
uvicorn main:app --reload --port 8000
\`\`\`

The server will be available at `http://localhost:8000`

### Docker Deployment

1. **Build the Docker image**
\`\`\`bash
docker build -t blimp-mcp-server .
\`\`\`

2. **Run the container**
\`\`\`bash
docker run -d \
  --name blimp-mcp \
  -p 8000:8000 \
  -e GEMINI_API_KEY=your_key \
  -e SUPABASE_URL=your_url \
  -e SUPABASE_SERVICE_ROLE_KEY=your_key \
  -e N8N_BASE_URL=your_n8n_url \
  -e N8N_API_KEY=your_n8n_key \
  blimp-mcp-server
\`\`\`

Or use docker-compose:

\`\`\`yaml
version: '3.8'
services:
  mcp-server:
    build: .
    ports:
      - "8000:8000"
    env_file:
      - .env
    restart: unless-stopped
\`\`\`

## Database Schema

### Required Supabase Tables

**user_connected_apps**
\`\`\`sql
CREATE TABLE user_connected_apps (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  user_id TEXT NOT NULL,
  app_name TEXT NOT NULL,
  app_type TEXT NOT NULL,
  is_active BOOLEAN DEFAULT true,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  UNIQUE(user_id, app_type)
);

CREATE INDEX idx_user_connected_apps_user_id ON user_connected_apps(user_id);
CREATE INDEX idx_user_connected_apps_active ON user_connected_apps(user_id, is_active);
\`\`\`

**user_credentials**
\`\`\`sql
CREATE TABLE user_credentials (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  user_id TEXT NOT NULL,
  app_name TEXT NOT NULL,
  app_type TEXT NOT NULL,
  credentials JSONB NOT NULL,
  metadata JSONB,
  is_active BOOLEAN DEFAULT true,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  UNIQUE(user_id, app_type)
);

CREATE INDEX idx_user_credentials_user_id ON user_credentials(user_id);
CREATE INDEX idx_user_credentials_active ON user_credentials(user_id, is_active);

-- Enable Row Level Security
ALTER TABLE user_credentials ENABLE ROW LEVEL SECURITY;

-- Policy: Users can only access their own credentials
CREATE POLICY user_credentials_policy ON user_credentials
  FOR ALL
  USING (auth.uid()::text = user_id);
\`\`\`

**workflow_executions**
\`\`\`sql
CREATE TABLE workflow_executions (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  user_id TEXT NOT NULL,
  workflow_id TEXT NOT NULL,
  execution_id TEXT NOT NULL,
  status TEXT NOT NULL,
  parameters JSONB,
  result JSONB,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_workflow_executions_user_id ON workflow_executions(user_id);
CREATE INDEX idx_workflow_executions_execution_id ON workflow_executions(execution_id);
\`\`\`

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `GEMINI_API_KEY` | Google Gemini API key | Yes |
| `SUPABASE_URL` | Supabase project URL | Yes |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase service role key | Yes |
| `N8N_BASE_URL` | n8n instance URL | Yes |
| `N8N_API_KEY` | n8n API key | Yes |
| `PORT` | Server port (default: 8000) | No |

## API Documentation

Once the server is running, visit:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Documentation

- [Proxy API Guide](./PROXY_API_GUIDE.md) - Complete guide for using the proxy API with n8n workflows
- [n8n Workflow Setup Guide](./N8N_WORKFLOW_SETUP_GUIDE.md) - How to configure n8n workflows for token-based authentication
- [Dashboard Prompt](./DASHBOARD_PROMPT.md) - Specifications for building the frontend dashboard

## Testing

\`\`\`bash
# Test health endpoint
curl http://localhost:8000/health

# Test prompt endpoint
curl -X POST http://localhost:8000/prompt \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Send a Slack message when I receive an email",
    "user_id": "user_123",
    "bearer_token": "test_token"
  }'

# Test proxy endpoint
curl -X POST http://localhost:8000/proxy/gmail/fetchEmails \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user_123",
    "payload": {
      "query": "is:unread"
    }
  }'
\`\`\`

## License

MIT
