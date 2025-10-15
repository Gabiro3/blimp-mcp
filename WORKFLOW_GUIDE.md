# n8n Webhook-Based Workflow Integration Guide

This guide explains how to create and configure n8n workflows that integrate with the Blimp MCP server using webhook triggers.

## Overview

The MCP server triggers n8n workflows via **webhook GET requests** instead of the n8n API. This approach:

- Simplifies authentication (no API key management)
- Allows direct workflow triggering
- Passes user-specific parameters via query strings
- Enables user-specific OAuth token usage through the proxy endpoints

## Workflow Architecture

\`\`\`
User Dashboard → MCP Server → n8n Webhook → Workflow Execution → Proxy Endpoints → Third-party APIs
\`\`\`

## Database Schema

### workflow_templates Table

Stores workflow templates with their webhook URLs:

\`\`\`sql
CREATE TABLE workflow_templates (
id TEXT PRIMARY KEY, -- Unique workflow identifier
name TEXT NOT NULL, -- Display name
description TEXT, -- Workflow description
webhook_url TEXT NOT NULL, -- n8n webhook URL
required_apps TEXT[] NOT NULL, -- Array of required app connections
category TEXT, -- Workflow category
is_active BOOLEAN DEFAULT true, -- Active status
created_at TIMESTAMP,
updated_at TIMESTAMP
);
\`\`\`

### Example Templates

Three dummy templates are provided:

1. **gmail-to-calendar**: Create calendar events from Gmail emails
2. **slack-to-notion**: Save Slack messages to Notion
3. **email-to-drive**: Save email attachments to Google Drive

## Creating n8n Workflows

### Step 1: Set Up Webhook Trigger

1. Add a **Webhook** node as the first node
2. Configure webhook settings:
   - **HTTP Method**: GET
   - **Path**: `/webhook/your-workflow-name`
   - **Response Mode**: When Last Node Finishes
   - **Response Data**: Last Node

### Step 2: Extract Query Parameters

Add a **Set** node to extract parameters:

\`\`\`json
{
"user_id": "={{ $json.query.user_id }}",
"param1": "={{ $json.query.param1 }}",
"param2": "={{ $json.query.param2 }}"
}
\`\`\`

### Step 3: Call MCP Proxy Endpoints

Use **HTTP Request** nodes to call proxy endpoints:

\`\`\`json
{
"method": "POST",
"url": "https://your-mcp-server.com/proxy/gmail/fetchEmails",
"authentication": "none",
"sendBody": true,
"bodyParameters": {
"parameters": [
{
"name": "user_id",
"value": "={{ $json.user_id }}"
},
{
"name": "maxResults",
"value": "10"
}
]
},
"options": {
"response": {
"response": {
"responseFormat": "json"
}
}
}
}
\`\`\`

### Step 4: Process and Return Results

Add logic nodes to process data and return results:

\`\`\`json
{
"success": true,
"executionId": "={{ $execution.id }}",
"results": "={{ $json }}"
}
\`\`\`

## Example Workflow: Gmail to Calendar

### Workflow Structure

1. **Webhook Trigger** (GET)

   - Path: `/webhook/gmail-to-calendar`
   - Extracts: `user_id`, `maxEmails`

2. **Fetch Emails** (HTTP Request)

   - URL: `{MCP_SERVER}/proxy/gmail/fetchEmails`
   - Body: `{ "user_id": "...", "maxResults": 10 }`

3. **Filter Emails** (IF node)

   - Condition: Email contains calendar-related keywords

4. **Create Calendar Event** (HTTP Request)

   - URL: `{MCP_SERVER}/proxy/calendar/createEvent`
   - Body: `{ "user_id": "...", "summary": "...", "start": "...", "end": "..." }`

5. **Return Response**
   - Success message with created events

### n8n Workflow JSON

\`\`\`json
{
"nodes": [
{
"parameters": {
"httpMethod": "GET",
"path": "gmail-to-calendar",
"responseMode": "lastNode",
"options": {}
},
"name": "Webhook",
"type": "n8n-nodes-base.webhook",
"position": [250, 300]
},
{
"parameters": {
"method": "POST",
"url": "https://your-mcp-server.com/proxy/gmail/fetchEmails",
"sendBody": true,
"bodyParameters": {
"parameters": [
{
"name": "user_id",
"value": "={{ $json.query.user_id }}"
},
{
"name": "maxResults",
"value": "={{ $json.query.maxEmails || 10 }}"
}
]
},
"options": {
"response": {
"response": {
"responseFormat": "json"
}
}
}
},
"name": "Fetch Gmail Emails",
"type": "n8n-nodes-base.httpRequest",
"position": [450, 300]
},
{
"parameters": {
"method": "POST",
"url": "https://your-mcp-server.com/proxy/calendar/createEvent",
"sendBody": true,
"bodyParameters": {
"parameters": [
{
"name": "user_id",
"value": "={{ $json.user_id }}"
},
{
"name": "summary",
"value": "={{ $json.subject }}"
},
{
"name": "description",
"value": "={{ $json.body }}"
},
{
"name": "start",
"value": "={{ $json.suggestedDate }}"
}
]
}
},
"name": "Create Calendar Event",
"type": "n8n-nodes-base.httpRequest",
"position": [650, 300]
}
],
"connections": {
"Webhook": {
"main": [[{ "node": "Fetch Gmail Emails", "type": "main", "index": 0 }]]
},
"Fetch Gmail Emails": {
"main": [[{ "node": "Create Calendar Event", "type": "main", "index": 0 }]]
}
}
}
\`\`\`

## Triggering Workflows from Client

### From Dashboard UI

\`\`\`typescript
const response = await fetch('https://your-mcp-server.com/execute-workflow', {
method: 'POST',
headers: {
'Content-Type': 'application/json',
'Authorization': 'Bearer YOUR_TOKEN'
},
body: JSON.stringify({
workflow_id: 'gmail-to-calendar',
user_id: 'user123',
bearer_token: 'YOUR_TOKEN',
parameters: {
maxEmails: 10
}
})
});
\`\`\`

### MCP Server Flow

1. Receives `/execute-workflow` request
2. Fetches webhook URL from `workflow_templates` table
3. Makes GET request to n8n webhook with query parameters
4. Returns execution result to client

## Adding New Workflow Templates

### 1. Create n8n Workflow

Build your workflow in n8n with webhook trigger

### 2. Get Webhook URL

Copy the webhook URL from n8n (e.g., `https://n8n.example.com/webhook/my-workflow`)

### 3. Insert into Database

\`\`\`sql
INSERT INTO workflow_templates (id, name, description, webhook_url, required_apps, category)
VALUES (
'my-workflow',
'My Custom Workflow',
'Description of what this workflow does',
'https://n8n.example.com/webhook/my-workflow',
ARRAY['gmail', 'slack'],
'automation'
);
\`\`\`

### 4. Test Workflow

\`\`\`bash
curl -X POST https://your-mcp-server.com/execute-workflow \
 -H "Content-Type: application/json" \
 -d '{
"workflow_id": "my-workflow",
"user_id": "test-user",
"bearer_token": "test-token",
"parameters": {}
}'
\`\`\`

## Best Practices

1. **Always use GET webhooks** for consistency with the MCP server
2. **Pass user_id** in all proxy requests for credential lookup
3. **Handle errors gracefully** and return meaningful error messages
4. **Use proxy endpoints** instead of direct API calls to leverage user OAuth tokens
5. **Test workflows** with real user credentials before deploying
6. **Document required_apps** accurately in workflow_templates table
7. **Use meaningful workflow IDs** that describe the automation
8. **Set appropriate timeouts** for long-running workflows

## Troubleshooting

### Webhook Not Triggering

- Verify webhook URL is correct in database
- Check n8n workflow is active
- Ensure webhook path matches exactly

### Missing User Credentials

- Verify user has connected required apps
- Check `user_credentials` table for active credentials
- Ensure app_type matches exactly

### Proxy Request Failing

- Verify OAuth tokens are valid and not expired
- Check proxy endpoint supports the requested action
- Review MCP server logs for detailed error messages

## Security Considerations

1. **Never expose OAuth tokens** in workflow responses
2. **Validate user_id** in all requests
3. **Use HTTPS** for all webhook URLs
4. **Implement rate limiting** on webhook endpoints
5. **Log all workflow executions** for audit trails
6. **Encrypt sensitive data** in database
7. **Use Row Level Security** on workflow_templates table
