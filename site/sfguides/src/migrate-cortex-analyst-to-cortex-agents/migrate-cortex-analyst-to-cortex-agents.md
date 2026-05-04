author: Abhinav Vadrevu
id: migrate-cortex-analyst-to-cortex-agents
language: en
summary: Learn how to upgrade your conversational analytics application from the Cortex Analyst API to the Cortex Agents API for improved accuracy and additional capabilities.
categories: snowflake-site:taxonomy/solution-center/ai-ml/quickstart
environments: web
status: Published

# Upgrade from Cortex Analyst to Cortex Agents

## Overview

Cortex Agents is Snowflake's next-generation API for conversational analytics. It builds on everything Cortex Analyst offers — text-to-SQL over semantic views — and adds agentic orchestration that delivers higher accuracy, self-correction, and a unified interface for structured data, unstructured data, and custom tools.

**Your existing semantic views work as-is.** No re-modeling is required. The upgrade is entirely at the API and application layer.

### Why upgrade?

| Capability | Cortex Analyst | Cortex Agents |
| :--- | :--- | :--- |
| Open-ended and complex questions | Limited to single-shot SQL | Reasons through multi-step questions, breaks them into sub-tasks |
| Ambiguous questions | Returns suggestions, requires user to rephrase | Asks clarifying questions naturally in conversation |
| SQL accuracy | High | Higher — agent can inspect results and self-correct errors |
| Recovery from incorrect answers | Requires user to re-ask | Agent detects issues and retries with a different approach |
| Charts and visualizations | Not supported | Generates charts automatically when data benefits from it |
| Unstructured data (RAG) | Not supported | Combines SQL answers with document search via Cortex Search |

### What you'll learn

- How to create a Cortex Agent backed by your semantic view
- How to update your API calls from Analyst to Agents
- How to parse the new response format
- How to use server-managed threads for multi-turn conversations
- How to handle edge cases (legacy models, routing, timeouts)

### What you'll need

- A Snowflake account with Cortex Agents access
- An existing semantic view or semantic model YAML on a stage
- Basic familiarity with REST APIs and Python


## Prerequisites

### Privileges

To create and use a Cortex Agent, your role needs:

```sql
-- Grant privileges to create an agent
GRANT USAGE ON DATABASE <database_name> TO ROLE <role_name>;
GRANT USAGE ON SCHEMA <database_name>.<schema_name> TO ROLE <role_name>;
GRANT CREATE AGENT ON SCHEMA <database_name>.<schema_name> TO ROLE <role_name>;

-- Grant access to the semantic view and underlying tables
GRANT USAGE ON SEMANTIC VIEW <database_name>.<schema_name>.<view_name> TO ROLE <role_name>;
GRANT SELECT ON TABLE <database_name>.<schema_name>.<table_name> TO ROLE <role_name>;
```

### Enable cross-region inference (recommended)

Cross-region inference gives your agent access to the full set of LLMs. An ACCOUNTADMIN must run:

```sql
ALTER ACCOUNT SET CORTEX_ENABLED_CROSS_REGION = 'ANY_REGION';
```

### Python environment

The code examples in this guide use Python with the `requests` library:

```bash
pip install requests
```

### Authentication

Cortex Agents supports the same authentication methods as Cortex Analyst:
- Programmatic Access Tokens (PAT)
- Key pair authentication (JWT)
- OAuth

All examples in this guide use a PAT stored in the `PAT` environment variable.


## How Cortex Agents Works

Cortex Analyst is a single-purpose text-to-SQL endpoint. You send a question and a semantic view; it returns SQL.

Cortex Agents wraps that capability in an orchestrator that can:

1. **Reason** about your question and decide how to approach it
2. **Generate SQL** directly against your semantic view
3. **Execute the SQL** and inspect results
4. **Self-correct** if the SQL errors or returns unexpected results
5. **Combine tools** — answer questions that need both structured data and document search

This architecture is why agents handle open-ended and ambiguous questions better: instead of a single pass, the agent can iterate until it gets the right answer.


## Create a Cortex Agent

The easiest way to create an agent is through the Snowsight UI. You can also use SQL or the REST API — all three methods produce the same agent object.

### Create an agent in Snowsight

1. Sign in to Snowsight
2. In the navigation menu, select **AI & ML → Agents**
3. Select **Create agent**
4. Enter a name and display name for your agent
5. Select **Create agent**

Once the agent is created, add your semantic view as a tool:

1. Select **Edit** on your agent
2. Select **Tools**
3. Find **Cortex Analyst** and select **+ Add**
4. Enter a name for the tool (e.g., "SalesAnalytics")
5. Select **Semantic view**, then choose your semantic view from the picker
6. Select a warehouse for query execution
7. For **Description**, write a clear description of what data this semantic view covers and when to use it — this directly impacts routing accuracy
8. Select **Add**
9. Select **Save**

You can test your agent immediately in the agent playground by entering a question on the agent details page.

For full details, see [Configure and interact with Agents](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-agents-manage).

### Multiple semantic views

If you currently use the `semantic_models` array in Cortex Analyst to route across multiple views, add each as a separate Cortex Analyst tool on the same agent. Repeat the "Add tool" steps above for each semantic view.

The agent automatically routes questions to the correct tool based on the descriptions you provide. Write clear, distinct descriptions for each — for example:

- "Revenue, orders, and customer metrics. Use for sales performance questions."
- "Campaign performance, ad spend, and conversion data. Use for marketing questions."

### Grant access

After creating the agent, grant usage to other roles that need it:

```sql
GRANT USAGE ON AGENT my_db.my_schema.my_analytics_agent TO ROLE analyst_role;
```

You can also do this in Snowsight under **Access** on the agent details page.


## Update Your API Calls

### Request and response: before and after

The key differences between the two APIs:
- **Endpoint**: `/api/v2/cortex/analyst/message` → `/api/v2/databases/{db}/schemas/{schema}/agents/{name}:run`
- **Semantic view**: Specified when creating the agent, not in every request
- **Stream**: Agents stream by default; set `stream: false` for a non-streaming response
- **Response role**: `analyst` → `assistant`
- **SQL delivery**: A `sql` content block → `tool_use` and `tool_result` blocks of type `system_execute_sql`
- **Results included**: Agents execute the SQL and return results directly
- **Final answer**: Agents provide a natural language summary after seeing the data

### Python example: complete before/after

**Before (Cortex Analyst):**

```python
import requests
import os

ACCOUNT_URL = os.environ["SNOWFLAKE_ACCOUNT_BASE_URL"]
PAT = os.environ["PAT"]

def ask_analyst(question: str, semantic_view: str) -> dict:
    response = requests.post(
        f"{ACCOUNT_URL}/api/v2/cortex/analyst/message",
        headers={
            "Authorization": f"Bearer {PAT}",
            "Content-Type": "application/json",
        },
        json={
            "messages": [
                {
                    "role": "user",
                    "content": [{"type": "text", "text": question}],
                }
            ],
            "semantic_view": semantic_view,
        },
    )
    response.raise_for_status()
    return response.json()


result = ask_analyst(
    "What was total revenue last quarter?",
    "MY_DB.MY_SCHEMA.SALES_SEMANTIC_VIEW",
)

# Extract SQL from Analyst response
for block in result["message"]["content"]:
    if block["type"] == "sql":
        print(f"SQL: {block['statement']}")
    elif block["type"] == "text":
        print(f"Text: {block['text']}")
```

**After (Cortex Agents):**

```python
import requests
import os

ACCOUNT_URL = os.environ["SNOWFLAKE_ACCOUNT_BASE_URL"]
PAT = os.environ["PAT"]

def ask_agent(question: str, database: str, schema: str, agent_name: str) -> dict:
    response = requests.post(
        f"{ACCOUNT_URL}/api/v2/databases/{database}/schemas/{schema}/agents/{agent_name}:run",
        headers={
            "Authorization": f"Bearer {PAT}",
            "Content-Type": "application/json",
        },
        json={
            "messages": [
                {
                    "role": "user",
                    "content": [{"type": "text", "text": question}],
                }
            ],
            "stream": False,
        },
    )
    response.raise_for_status()
    return response.json()


result = ask_agent(
    "What was total revenue last quarter?",
    "my_db",
    "my_schema",
    "my_analytics_agent",
)

# Extract information from Agent response
for block in result["message"]["content"]:
    if block["type"] == "text":
        print(f"Text: {block['text']}")
    elif block["type"] == "tool_result":
        tool_content = block["tool_result"]["content"]
        print(f"SQL: {tool_content['sql']}")
        print(f"Query ID: {tool_content['query_id']}")
        print(f"Results: {tool_content['result_set']}")
```


## Parse the New Response Format

### Content block types

Cortex Analyst returns three content types: `text`, `sql`, and `suggestions`.

Cortex Agents returns these content types:

| Type | Description |
| :--- | :--- |
| `text` | Natural language explanation or answer |
| `tool_use` | The agent is invoking a tool (contains tool name and input) |
| `tool_result` | The result of a tool invocation (contains output data) |

### Extracting SQL and results

In Cortex Analyst, SQL lives in a `sql` content block:
```python
# Analyst
statement = block["statement"]
```

In Cortex Agents, SQL appears in both `tool_use` (the generated query) and `tool_result` (the executed query plus results):
```python
# Agent - from tool_use
sql = block["tool_use"]["input"]["sql"]

# Agent - from tool_result (includes execution results)
sql = block["tool_result"]["content"]["sql"]
query_id = block["tool_result"]["content"]["query_id"]
results = block["tool_result"]["content"]["result_set"]
```

### Complete response parser

```python
def parse_agent_response(response: dict) -> dict:
    """Parse a Cortex Agents response into structured components."""
    parsed = {
        "text_blocks": [],
        "sql_statements": [],
        "query_results": [],
        "query_ids": [],
    }

    for block in response["message"]["content"]:
        if block["type"] == "text":
            parsed["text_blocks"].append(block["text"])

        elif block["type"] == "tool_use":
            if block["tool_use"]["name"] == "system_execute_sql":
                parsed["sql_statements"].append(
                    block["tool_use"]["input"]["sql"]
                )

        elif block["type"] == "tool_result":
            if block["tool_result"]["name"] == "system_execute_sql":
                content = block["tool_result"]["content"]
                parsed["query_ids"].append(content["query_id"])
                parsed["query_results"].append(content["result_set"])

    return parsed


# Usage
result = ask_agent("What was total revenue last quarter?", "my_db", "my_schema", "my_analytics_agent")
parsed = parse_agent_response(result)

print(f"Answer: {parsed['text_blocks'][-1]}")  # Final text block is usually the answer
print(f"SQL: {parsed['sql_statements']}")
print(f"Data: {parsed['query_results']}")
```

### Handling streaming responses

Cortex Agents streams responses as server-sent events (SSE) by default. Here's how to consume them:

```python
import json

def ask_agent_streaming(question: str, database: str, schema: str, agent_name: str):
    """Stream a response from Cortex Agents and assemble it."""
    response = requests.post(
        f"{ACCOUNT_URL}/api/v2/databases/{database}/schemas/{schema}/agents/{agent_name}:run",
        headers={
            "Authorization": f"Bearer {PAT}",
            "Content-Type": "application/json",
        },
        json={
            "messages": [
                {
                    "role": "user",
                    "content": [{"type": "text", "text": question}],
                }
            ],
            "stream": True,
        },
        stream=True,
    )
    response.raise_for_status()

    full_text = ""
    for line in response.iter_lines(decode_unicode=True):
        if not line or not line.startswith("data:"):
            continue

        data_str = line[len("data:"):].strip()
        if data_str == "[DONE]":
            break

        event = json.loads(data_str)

        # Handle delta events
        if "delta" in event:
            delta = event["delta"]
            if delta.get("type") == "text":
                text_chunk = delta.get("text", "")
                full_text += text_chunk
                print(text_chunk, end="", flush=True)

    print()  # Newline after streaming completes
    return full_text
```

### Mapping Analyst content types to Agent equivalents

| Analyst | Agent equivalent | How to detect |
| :--- | :--- | :--- |
| `type: "text"` | `type: "text"` | Same — direct text content |
| `type: "sql"` with `statement` | `type: "tool_result"` with `system_execute_sql` | Check `tool_result.name == "system_execute_sql"` |
| `type: "suggestions"` | `type: "text"` with clarification questions | Agent asks follow-up questions as natural text |
| `confidence.verified_query_used` | Not directly exposed | Verified queries still influence SQL generation but are not surfaced in the response |


## Use Multi-Turn Conversations with Threads

### How Cortex Analyst handles multi-turn

In Cortex Analyst, you pass the full conversation history with every request:

```python
# Analyst: you maintain and send full history
messages = [
    {"role": "user", "content": [{"type": "text", "text": "What was revenue last quarter?"}]},
    {"role": "analyst", "content": [{"type": "text", "text": "Revenue was $4.2M..."}, {"type": "sql", "statement": "SELECT ..."}]},
    {"role": "user", "content": [{"type": "text", "text": "Break that down by region"}]},
]

response = requests.post(
    f"{ACCOUNT_URL}/api/v2/cortex/analyst/message",
    json={"messages": messages, "semantic_view": "..."},
    ...
)
```

### How Cortex Agents handles multi-turn

With Cortex Agents, the server maintains conversation context in a **thread**. You create a thread once, then reference it:

**Step 1: Create a thread**

```python
def create_thread() -> str:
    """Create a conversation thread and return its ID."""
    response = requests.post(
        f"{ACCOUNT_URL}/api/v2/cortex/threads",
        headers={
            "Authorization": f"Bearer {PAT}",
            "Content-Type": "application/json",
        },
        json={},
    )
    response.raise_for_status()
    return response.json()["thread_id"]
```

**Step 2: Send messages with thread context**

```python
def ask_agent_with_thread(
    question: str,
    database: str,
    schema: str,
    agent_name: str,
    thread_id: str,
    parent_message_id: str = "0",
) -> dict:
    """Send a message in the context of an existing thread."""
    response = requests.post(
        f"{ACCOUNT_URL}/api/v2/databases/{database}/schemas/{schema}/agents/{agent_name}:run",
        headers={
            "Authorization": f"Bearer {PAT}",
            "Content-Type": "application/json",
        },
        json={
            "thread_id": thread_id,
            "parent_message_id": parent_message_id,
            "messages": [
                {
                    "role": "user",
                    "content": [{"type": "text", "text": question}],
                }
            ],
            "stream": False,
        },
    )
    response.raise_for_status()
    return response.json()


# Multi-turn conversation
thread_id = create_thread()

# First question
result1 = ask_agent_with_thread(
    "What was revenue last quarter?",
    "my_db", "my_schema", "my_analytics_agent",
    thread_id=thread_id,
    parent_message_id="0",
)

# Follow-up (no need to resend history)
result2 = ask_agent_with_thread(
    "Break that down by region",
    "my_db", "my_schema", "my_analytics_agent",
    thread_id=thread_id,
    parent_message_id=result1["request_id"],
)
```

### Benefits of server-managed threads

- **Smaller payloads**: No need to send the full conversation history each time
- **Better context**: The server maintains the full execution trace, including intermediate SQL and results
- **Simpler client code**: No need to manage message arrays or truncate old context


## Handle Edge Cases

### Legacy semantic models on stages

If you still use YAML files on a Snowflake stage (rather than a semantic view object), you can reference them in tool_resources:

```sql
CREATE OR REPLACE AGENT my_analytics_agent
  FROM SPECIFICATION
  $$
  models:
    orchestration: auto

  tools:
    - tool_spec:
        type: "cortex_analyst_text_to_sql"
        name: "SalesAnalytics"
        description: "Analyzes sales data."

  tool_resources:
    SalesAnalytics:
      semantic_model_file: "@my_db.my_schema.my_stage/sales_model.yaml"
  $$;
```

> **Recommendation**: Migrate to semantic views for better governance, RBAC, and sharing. Use `SYSTEM$CREATE_SEMANTIC_VIEW_FROM_YAML` to convert your YAML file to a semantic view.

### Forcing a specific tool

If you want to ensure the agent uses a particular tool (similar to how Analyst always used a specific semantic view), use `tool_choice`:

```json
{
  "messages": [...],
  "tool_choice": {
    "type": "required",
    "name": ["SalesAnalytics"]
  }
}
```

### Budget and timeout configuration

Control how long the agent can spend on a response:

```yaml
orchestration:
  budget:
    seconds: 30    # Max wall-clock time
    tokens: 16000  # Max orchestration tokens
```

For complex questions that need multiple tool calls, increase these values. For simple lookups, lower values reduce latency.

### Using SQL instead of REST

You can also run an agent from SQL using `DATA_AGENT_RUN`:

```sql
SELECT DATA_AGENT_RUN(
  'my_db.my_schema.my_analytics_agent',
  'What was total revenue last quarter?'
);
```

This returns a non-streaming JSON response and is useful for testing, notebooks, or stored procedure integrations.


## Update Monitoring

### Observability changes

| Concept | Cortex Analyst | Cortex Agents |
| :--- | :--- | :--- |
| Usage tracking view | `CORTEX_ANALYST_REQUESTS_V` | `CORTEX_AGENT_USAGE_HISTORY` |
| Credit service type | `cortex_analyst` | `cortex_agents` |
| Feedback endpoint | `POST /api/v2/cortex/analyst/feedback` | `POST /api/v2/databases/{db}/schemas/{schema}/agents/{name}:feedback` |

### Monitoring queries

**Find recent agent usage:**

```sql
SELECT
  request_id,
  user_name,
  start_time,
  end_time,
  DATEDIFF('second', start_time, end_time) AS duration_seconds,
  tokens_granular
FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_AGENT_USAGE_HISTORY
WHERE start_time > DATEADD('day', -7, CURRENT_TIMESTAMP())
ORDER BY start_time DESC;
```

### Sending feedback

```bash
curl -X POST "$SNOWFLAKE_ACCOUNT_BASE_URL/api/v2/databases/my_db/schemas/my_schema/agents/my_analytics_agent:feedback" \
  --header "Authorization: Bearer $PAT" \
  --header 'Content-Type: application/json' \
  --data '{"request_id": "<request_id>", "positive": true, "feedback_message": "Correct answer"}'
```


## Validate Your Migration

Before switching production traffic, confirm:

- Run 10-20 representative questions through both APIs and compare SQL correctness, accuracy, and latency
- Verify your app handles all response types: text-only, SQL + results, multi-step, and errors
- Test multi-turn conversations with threads (ask a question, then follow up)
- Check that ambiguous or unanswerable questions are handled gracefully
- Monitor `CORTEX_AGENT_USAGE_HISTORY` after switching and collect user feedback


## Conclusion and Next Steps

You've upgraded from Cortex Analyst to Cortex Agents. Your application now benefits from:

- **Higher accuracy** through agentic SQL generation and self-correction
- **Server-managed context** via threads
- **A unified API** ready for additional capabilities

### Next steps

Now that your agent is running, consider adding:

- **Cortex Search** for unstructured data (documents, policies, FAQs)
- **Custom tools** for business-specific logic (stored procedures, UDFs)
- **data_to_chart** for automatic visualizations
- **Web search** for real-time external data

### Resources

- [Build agents](https://docs.snowflake.com/en/user-guide/snowflake-cortex/snowflake-intelligence/build-agents)
- [Cortex Agents Run API](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-agents-run)
- [Best Practices for Building Cortex Agents](https://quickstarts.snowflake.com/guide/best-practices-to-building-cortex-agents)
- [Best Practices for Semantic Views](https://quickstarts.snowflake.com/guide/best-practices-semantic-views-cortex-analyst)
- [Overview of Semantic Views](https://docs.snowflake.com/en/user-guide/views-semantic/overview)
