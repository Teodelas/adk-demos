# Blueprint: Building Web Interfaces for ADK Agents

This blueprint provides a technical template for building a Node.js/Express backend that proxies requests to a **Vertex AI ADK (Agent Development Kit)** Reasoning Engine.

## 1. REST API Contract
ADK agents running on Reasoning Engine use a specific interaction pattern that differs from standard LangChain templates.

- **Endpoint**: `https://[LOCATION]-aiplatform.googleapis.com/v1/projects/[PROJECT_ID]/locations/[LOCATION]/reasoningEngines/[RE_ID]:streamQuery?alt=sse`
- **Method**: `POST`
- **Authentication**: Bearer Token (`roles/aiplatform.user` permission required).
- **Request Body**:
```json
{
  "class_method": "async_stream_query",
  "input": {
    "user_id": "unique_user_id",
    "message": "User query here",
    "session_id": "optional_session_id"
  }
}
```

## 2. Robust Backend Proxy (Node.js)
The most critical part of the integration is handling **stream fragmentation**. Large fields like `thought_signature` can cause JSON parsing failures if chunks are processed raw.

### Implementation Pattern
```javascript
const { GoogleAuth } = require('google-auth-library');
const auth = new GoogleAuth({ scopes: 'https://www.googleapis.com/auth/cloud-platform' });

app.post('/api/chat', async (req, res) => {
    const client = await auth.getClient();
    const accessToken = await client.getAccessToken();
    
    const response = await fetch(ENDPOINT_URL, {
        method: 'POST',
        headers: {
            'Authorization': `Bearer ${accessToken.token}`,
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            class_method: "async_stream_query",
            input: { message: req.body.message, user_id: "web-user" }
        })
    });

    const reader = response.body.getReader();
    let fullText = "";
    let buffer = "";

    while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        // 1. Buffer the raw stream data
        buffer += new TextDecoder().decode(value, { stream: true });
        
        // 2. Process complete lines only
        let lines = buffer.split('\n');
        buffer = lines.pop(); // Keep partial line in buffer

        for (let line of lines) {
            line = line.trim();
            if (!line) continue;

            // 3. Remove 'data: ' prefix if using alt=sse
            const dataStr = line.startsWith('data: ') ? line.substring(6).trim() : line;
            if (dataStr === '[DONE]') continue;

            try {
                const data = JSON.parse(dataStr);
                
                // 4. Extract text from Gemini structure
                if (data.content && data.content.parts) {
                    data.content.parts.forEach(part => {
                        if (part.text) fullText += part.text;
                    });
                }
            } catch (e) {
                // Prepend back to buffer if line split inside JSON
                buffer = line + '\n' + buffer;
            }
        }
    }
    res.json({ output: fullText });
});
```

## 3. Key Findings & Gotchas
- **Stream alt=sse**: Using `?alt=sse` returns lines prefixed with `data: `, which is standard for EventSource/SSE but requires trimming on the backend.
- **Thought Signatures**: Gemini models often return extremely long `thought_signature` strings. These WILL fragment over TCP/HTTP, making the line-based buffer mandatory.
- **Method Name**: Always verify if the agent uses `async_stream_query` or `stream_query`. ADK defaults to the async variant for modern engines.
- **IAM**: Ensure the Cloud Run/Server Service Account has `aiplatform.user` permissions.
