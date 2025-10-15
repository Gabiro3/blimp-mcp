# Blimp MCP Server - Proxy API Guide

## Overview

The Blimp MCP Server provides a proxy API that allows n8n workflows to interact with user-specific connected apps using their OAuth tokens. This eliminates the need for n8n to manage individual user credentials and enables true multi-tenant workflow automation.

## Architecture

\`\`\`
n8n Workflow → MCP Proxy Endpoint → User's OAuth Tokens → Third-Party API
\`\`\`

### Flow:
1. n8n workflow sends request to MCP proxy endpoint with `user_id`
2. MCP server fetches user's OAuth tokens from Supabase
3. MCP server makes authenticated request to third-party API
4. Response is returned to n8n workflow

## Proxy Endpoint

### Base URL
\`\`\`
POST /proxy/{app_name}/{action}
\`\`\`

### Request Format
\`\`\`json
{
  "user_id": "user-uuid-here",
  "payload": {
    // Action-specific parameters
  }
}
\`\`\`

### Response Format
\`\`\`json
{
  "success": true,
  "data": {
    // Action-specific response data
  },
  "error": null
}
\`\`\`

## Supported Apps & Actions

### 1. Gmail (`/proxy/gmail/*`)

#### Fetch Emails
\`\`\`
POST /proxy/gmail/fetchEmails
\`\`\`

**Request:**
\`\`\`json
{
  "user_id": "user-123",
  "payload": {
    "query": "is:unread"  // Gmail search query
  }
}
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

#### Send Email
\`\`\`
POST /proxy/gmail/sendEmail
\`\`\`

**Request:**
\`\`\`json
{
  "user_id": "user-123",
  "payload": {
    "to": "recipient@example.com",
    "subject": "Hello",
    "body": "Email content here"
  }
}
\`\`\`

---

### 2. Slack (`/proxy/slack/*`)

#### Post Message
\`\`\`
POST /proxy/slack/postMessage
\`\`\`

**Request:**
\`\`\`json
{
  "user_id": "user-123",
  "payload": {
    "channel": "#general",
    "message": "Hello from Blimp!"
  }
}
\`\`\`

**Response:**
\`\`\`json
{
  "success": true,
  "data": {
    "message": "Message posted to Slack",
    "data": {
      "ok": true,
      "channel": "C123456",
      "ts": "1234567890.123456"
    }
  }
}
\`\`\`

#### List Channels
\`\`\`
POST /proxy/slack/listChannels
\`\`\`

**Request:**
\`\`\`json
{
  "user_id": "user-123",
  "payload": {}
}
\`\`\`

---

### 3. Notion (`/proxy/notion/*`)

#### Create Page
\`\`\`
POST /proxy/notion/createPage
\`\`\`

**Request:**
\`\`\`json
{
  "user_id": "user-123",
  "payload": {
    "parent_id": "page-id-or-null",
    "title": "Daily Report",
    "content": "Summary content here"
  }
}
\`\`\`

**Response:**
\`\`\`json
{
  "success": true,
  "data": {
    "message": "Notion page created",
    "data": {
      "id": "page-uuid",
      "url": "https://notion.so/..."
    }
  }
}
\`\`\`

#### Search Pages
\`\`\`
POST /proxy/notion/searchPages
\`\`\`

**Request:**
\`\`\`json
{
  "user_id": "user-123",
  "payload": {
    "query": "meeting notes"
  }
}
\`\`\`

---

### 4. Google Calendar (`/proxy/calendar/*`)

#### Create Event
\`\`\`
POST /proxy/calendar/createEvent
\`\`\`

**Request:**
\`\`\`json
{
  "user_id": "user-123",
  "payload": {
    "calendar_id": "primary",
    "events": [
      {
        "summary": "Team Meeting",
        "start": {
          "dateTime": "2025-01-15T10:00:00Z"
        },
        "end": {
          "dateTime": "2025-01-15T11:00:00Z"
        }
      }
    ]
  }
}
\`\`\`

**Response:**
\`\`\`json
{
  "success": true,
  "data": {
    "message": "Created 1 events",
    "events": [...]
  }
}
\`\`\`

#### List Events
\`\`\`
POST /proxy/calendar/listEvents
\`\`\`

**Request:**
\`\`\`json
{
  "user_id": "user-123",
  "payload": {
    "calendar_id": "primary",
    "time_min": "2025-01-01T00:00:00Z",
    "time_max": "2025-01-31T23:59:59Z"
  }
}
\`\`\`

---

### 5. Google Drive (`/proxy/gdrive/*`)

#### List Files
\`\`\`
POST /proxy/gdrive/listFiles
\`\`\`

**Request:**
\`\`\`json
{
  "user_id": "user-123",
  "payload": {
    "query": "mimeType='application/pdf'",
    "page_size": 10
  }
}
\`\`\`

**Response:**
\`\`\`json
{
  "success": true,
  "data": {
    "files": [
      {
        "id": "file-id",
        "name": "document.pdf",
        "mimeType": "application/pdf",
        "createdTime": "2025-01-01T00:00:00Z"
      }
    ]
  }
}
\`\`\`

#### Upload File
\`\`\`
POST /proxy/gdrive/uploadFile
\`\`\`

**Request:**
\`\`\`json
{
  "user_id": "user-123",
  "payload": {
    "file_name": "report.txt",
    "file_content": "base64-encoded-content",
    "mime_type": "text/plain"
  }
}
\`\`\`

---

## n8n Workflow Integration

### Example: Gmail to Slack Workflow

\`\`\`json
{
  "nodes": [
    {
      "name": "Webhook",
      "type": "n8n-nodes-base.webhook",
      "parameters": {
        "path": "gmail-to-slack",
        "responseMode": "lastNode"
      }
    },
    {
      "name": "Extract User ID",
      "type": "n8n-nodes-base.set",
      "parameters": {
        "values": {
          "string": [
            {
              "name": "user_id",
              "value": "={{ $json.user_id }}"
            }
          ]
        }
      }
    },
    {
      "name": "Fetch Emails",
      "type": "n8n-nodes-base.httpRequest",
      "parameters": {
        "method": "POST",
        "url": "https://your-mcp-server.com/proxy/gmail/fetchEmails",
        "jsonParameters": true,
        "bodyParametersJson": "{\"user_id\":\"={{ $node['Extract User ID'].json.user_id }}\",\"payload\":{\"query\":\"is:unread\"}}"
      }
    },
    {
      "name": "Post to Slack",
      "type": "n8n-nodes-base.httpRequest",
      "parameters": {
        "method": "POST",
        "url": "https://your-mcp-server.com/proxy/slack/postMessage",
        "jsonParameters": true,
        "bodyParametersJson": "{\"user_id\":\"={{ $node['Extract User ID'].json.user_id }}\",\"payload\":{\"channel\":\"#general\",\"message\":\"You have {{ $node['Fetch Emails'].json.data.count }} unread emails\"}}"
      }
    }
  ]
}
\`\`\`

### Key Points for n8n Workflows:

1. **Always pass `user_id`** in the request body
2. **Use HTTP Request nodes** to call the MCP proxy endpoints
3. **Extract user_id early** in the workflow for reuse
4. **Handle errors** - Check `success` field in response
5. **Use expressions** to pass data between nodes

---

## Error Handling

### Error Response Format
\`\`\`json
{
  "success": false,
  "data": null,
  "error": "Error message here"
}
\`\`\`

### Common Errors:

1. **No credentials found**
   \`\`\`json
   {
     "success": false,
     "error": "No credentials found for gmail. Please connect your account first."
   }
   \`\`\`

2. **Invalid action**
   \`\`\`json
   {
     "success": false,
     "error": "Unsupported Gmail action: invalidAction"
   }
   \`\`\`

3. **API error**
   \`\`\`json
   {
     "success": false,
     "error": "Gmail API error: Invalid credentials"
   }
   \`\`\`

---

## Security Considerations

1. **OAuth Token Storage**: User tokens are stored in Supabase with encryption
2. **Token Refresh**: Implement automatic token refresh for expired tokens
3. **Rate Limiting**: Consider implementing rate limits per user
4. **Audit Logging**: Log all proxy requests for security auditing
5. **Scope Validation**: Ensure users have granted necessary OAuth scopes

---

## Adding New Apps

To add support for a new app:

1. **Add handler method** in `services/proxy_service.py`:
   \`\`\`python
   async def _handle_newapp(self, action, credentials, payload):
       # Implementation here
   \`\`\`

2. **Update routing** in `proxy_request` method:
   \`\`\`python
   elif app_name == "newapp":
       return await self._handle_newapp(action, credentials, payload)
   \`\`\`

3. **Document actions** in this guide

4. **Create n8n workflow template** for common use cases

---

## Testing

### Test with cURL:

\`\`\`bash
curl -X POST https://your-mcp-server.com/proxy/gmail/fetchEmails \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "test-user-123",
    "payload": {
      "query": "is:unread"
    }
  }'
\`\`\`

### Test from n8n:

1. Create a simple workflow with HTTP Request node
2. Point to your MCP server proxy endpoint
3. Pass test user_id and payload
4. Verify response in n8n execution logs

---

## Monitoring & Debugging

### Logs to Monitor:

- `Proxying {app_name}/{action} for user: {user_id}` - Request received
- `Retrieved credentials for {app_name} for user {user_id}` - Credentials found
- `{App} API error: {error}` - API call failed

### Debug Checklist:

1. ✅ User has connected the app in UI
2. ✅ Credentials are stored in Supabase
3. ✅ OAuth tokens are not expired
4. ✅ User has granted necessary scopes
5. ✅ MCP server can reach third-party API
6. ✅ Request payload is correctly formatted

---

## Performance Optimization

1. **Connection Pooling**: httpx AsyncClient reuses connections
2. **Timeout Configuration**: 30s timeout for API calls
3. **Parallel Requests**: Use async/await for concurrent API calls
4. **Caching**: Consider caching frequently accessed data
5. **Batch Operations**: Support batch operations where possible

---

## Next Steps

1. Implement token refresh logic for expired OAuth tokens
2. Add webhook support for real-time app events
3. Create more n8n workflow templates
4. Add support for additional apps (Trello, Asana, etc.)
5. Implement rate limiting and usage analytics
