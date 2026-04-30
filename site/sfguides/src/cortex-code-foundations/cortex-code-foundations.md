author: Cortex Code Team
id: cortex-code-foundations
language: en
summary: A hands-on guide to installing, configuring, and using Cortex Code (CoCo) — Snowflake's AI coding agent — including CLI setup and workshop demos for building data pipelines, agents, and semantic views.
categories: snowflake-site:taxonomy/solution-center/certification/quickstart
environments: web
status: Published
feedback link: https://github.com/Snowflake-Labs/sfguides/issues

# Getting Started with Cortex Code
<!-- ------------------------ -->
## Overview

Cortex Code (CoCo) is Snowflake's AI coding agent built to accelerate data and AI workflows directly inside your Snowflake environment. It understands your data catalog, executes SQL as your identity, and integrates natively with dbt, Git, Python, and Streamlit.

This guide walks you through installing the CoCo CLI, configuring your Snowflake connection, and completing a hands-on workshop covering three real-world scenarios: building a Dynamic Table pipeline, maintaining and evolving it, and creating a Cortex Agent with a semantic view.

### Prerequisites
- A Snowflake account with Cortex Code enabled

### What You'll Learn
- How to access Cortex Code via Snowsight (UI) and CLI
- How to install and configure the CoCo CLI 
- How to authenticate your Snowflake connection
- How to build a Dynamic Table pipeline with CoCo
- How to maintain a pipeline 
- How to create a Cortex Agent with a semantic view and evaluate its performance

### What You'll Build
- A configured Cortex Code CLI connected to your Snowflake environment
- A multi-source AP invoice pipeline using Dynamic Tables 
- A Cortex Agent grounded on a semantic view, with an evaluation framework

<!-- ------------------------ -->
## Access Cortex Code in Snowsight

Before setting up the CLI, you can access Cortex Code directly from the Snowflake UI.

In Snowsight, click the **blue star icon** in the bottom right corner to open the Cortex Code panel.

This gives you immediate access to CoCo without any local installation and is useful for quick queries, schema exploration, and testing.

<!-- ------------------------ -->
## Install the CoCo CLI on Mac

### Supported Architectures
- **x64** — Fully supported
- **ARM64** — Fully supported

### Install via Terminal

```bash
curl -LsS https://ai.snowflake.com/static/cc-scripts/install.sh | sh
```

When prompted to add `cortex` to your PATH, respond with **y**.

If the `cortex` command is not recognized after installation, close and reopen your terminal, or restart your machine.

### Verify Installation

```bash
cortex --version
```

### Configure Your Snowflake Connection

Cortex Code uses the same connection files as SnowCLI, located at:

```
~/.snowflake/config.toml
```

(or `connections.toml` if you already use that)

Minimal example, adapt to your accounts and roles:

```toml
default_connection_name = "DEMO"

[connections.DEMO]
account   = "<YOUR_DEMO_ACCOUNT>"    # e.g. SFSENORTHAMERICA-XXXXX
user      = "<YOUR_DEMO_USERNAME>"
password  = "<YOUR_DEMO_PAT>"
role      = "<YOUR_DEMO_ROLE>"
warehouse = "<YOUR_DEMO_WAREHOUSE>"
```

### Create the Config File 

Run the following in your terminal to create and open the config file:

```bash
mkdir -p ~/.snowflake
touch ~/.snowflake/config.toml
chmod 600 ~/.snowflake/config.toml
open -e ~/.snowflake/config.toml
```

<!-- ------------------------ -->
## Install the CoCo CLI on Windows

### Supported Architectures
- **x64** — Fully supported
- **ARM64** — Support is in progress; not yet recommended for production use

### Install via PowerShell

```powershell
irm https://ai.snowflake.com/static/cc-scripts/install.ps1 | iex
```

When prompted to add `cortex` to your PATH, respond with **y**.

If the `cortex` command is not recognized after installation, close and reopen your terminal or restart your machine.

### Verify Installation

```powershell
cortex --version
```

### Configure Your Snowflake Connection

On Windows, the config file is located at:

```
%USERPROFILE%\.snowflake\config.toml
```

Minimal example:

```toml
default_connection_name = "DEMO"    # Name for default Snowflake connection

[connections.DEMO]                  # Name for Snowflake connection (same as above if default)
account   = "<YOUR_DEMO_ACCOUNT>"  # e.g. Account identifier
user      = "<YOUR_DEMO_USERNAME>" # e.g. Authentication variable
password  = "<YOUR_DEMO_PAT>"
role      = "<YOUR_DEMO_ROLE>"     # e.g. Need a role for connection
warehouse = "<YOUR_DEMO_WAREHOUSE>"
```

### Create the Config File

Run the following in PowerShell:

```powershell
mkdir $env:USERPROFILE\.snowflake -Force
New-Item -ItemType File -Path $env:USERPROFILE\.snowflake\config.toml -Force
notepad $env:USERPROFILE\.snowflake\config.toml
```

<!-- ------------------------ -->
## Find Your Connection Details

To fill out your config, you'll need your Snowflake account identifier, role, and warehouse.

1. Log in to Snowsight
2. Click your username in the bottom left → **Account**
3. Note your **Account Identifier** (e.g. `SFSENORTHAMERICA-XXXXX`)
4. Go to **Admin → Warehouses** to find your warehouse name
5. Check **Admin → Users & Roles** for your role

### Authentication Options

There are several ways to authenticate your connection. Common environment variables include:

| Variable | Description |
|---|---|
| `SNOWFLAKE_ACCOUNT` | Your account identifier |
| `SNOWFLAKE_USER` | Your username |
| `SNOWFLAKE_PASSWORD` | Password authentication |
| `SNOWFLAKE_TOKEN` | OAuth token |
| `SNOWFLAKE_TOKEN_FILE_PATH` | Path to token file |
| `SNOWFLAKE_OAUTH_CLIENT_ID` | OAuth client ID |

For a full list, see the [Manage Snowflake connections guide](https://docs.snowflake.com/en/user-guide/snowsql-connect).

<!-- ------------------------ -->
## Launch Cortex Code

Once your connection is configured, launch the CLI:

```bash
cortex -c DEMO    # connect using connection name
```

After connecting, you'll see the Cortex Code CLI interface. Test your connection by asking a simple question — for example:

```
What databases do I have access to?
```

<!-- ------------------------ -->
## Workshop Overview

This workshop covers three progressive scenarios using a fictional company with two ERP systems (SAP for manufacturing in Germany, Oracle for operations in the US).

| Demo | Scenario | Skills |
|---|---|---|
| **Vignette 1** | Pipeline Builder — Bronze → Silver → Gold AP invoice pipeline | `$dynamic-tables` |
| **Vignette 2** | Pipeline Maintainer — Debug stale data, onboard 2 new ERP sources | `$skill-development` |
| **Vignette 3** | Build First Agent — Semantic view + Cortex Agent + evaluation framework | `$cortex-agent`, `$semantic-view` |

### Execution Modes

Before starting, familiarize yourself with CoCo's three execution modes:

| Mode | Description |
|---|---|
| **Confirm Mode** (default) | Prompts before file edits, bash commands, etc. All operations show risk level for approval. |
| **Plan Mode** (`/plan`) | Agent proposes a plan but doesn't execute until you approve. |
| **Bypass Mode** (`/bypass`) | Auto-approves all operations — not recommended. Can be disabled via managed settings. |

<!-- ------------------------ -->
## Vignette 1: Pipeline Builder

### The Story

Your company runs two ERP systems: SAP for manufacturing in Germany and Oracle for operations in the US. Both generate AP invoices with completely different column names and conventions.

Finance needs a single, consolidated view of all payables for reporting. Today this is done with manual SQL scripts that break every time a column changes.

You'll use Cortex Code to build a declarative pipeline using Dynamic Tables — **Bronze → Silver (consolidation) → Gold (aggregation)** — with automatic refresh and no orchestration code.

### What You'll Learn
- Ground CoCo on live schema context
- Generate consolidation DDL from cross-source metadata
- Generate downstream aggregation DDL + verification queries
- Save the workflow as a team skill

### Demo Steps

| Step | Task |
|---|---|
| Demo 1.1 | Setup: Explore the source data |
| Demo 1.2 | Compare SAP and Oracle invoice schemas |
| Demo 1.3 | Generate Silver Dynamic Table |
| Demo 1.4 | Use the `$dynamic-tables` skill |
| Demo 1.5 | Save one proof query |

<!-- ------------------------ -->
## Vignette 2: Pipeline Maintainer

### The Story

It's a month after launch. The Silver pipeline is live, but something's wrong — data looks stale and stakeholders are asking questions.

Meanwhile, the Finance Transformation PMO just sent over an Excel file: they want to onboard two more ERP systems (Baan from EMEA and Workday from Americas). The spreadsheet has column mappings, business rules, and open questions.

You need to diagnose the issue, translate business requirements into technical specs, evolve the pipeline to handle 4 sources, and set up monitoring.

### What You'll Learn
- Turn an Excel requirements doc into executable change steps
- Capture the workflow as a reusable team skill/runbook
- Run a local skill
- Save materials to share updates with team members

### Demo Steps

| Step | Task |
|---|---|
| Demo 2.1 | Read the local PRD |
| Demo 2.2 | Scaffold a Custom Skill |
| Demo 2.3 | Run the PRD Evaluator Skill |
| Demo 2.4 | Apply the changes |
| Demo 2.5 | *(Optional)* Save handoff materials |

> **Note:** Requires Vignette 1 to be completed first. Uses a local (or staged) Excel file.

<!-- ------------------------ -->
## Vignette 3: Build First Agent

### The Story

The AP consolidation pipeline is running smoothly with 4 source systems. But only engineers can query it — business users can't write SQL.

You'll create a semantic view that translates the Silver table into business-friendly dimensions and measures, then wrap it in a Cortex Agent that answers natural language questions about AP invoices.

You'll also build an evaluation framework — test questions, logged responses, and human feedback — to audit and improve the agent iteratively.

### What You'll Learn
- Generate a semantic view from live table metadata
- Create an agent with verifiable responses (answer + SQL + assumptions)
- Run evaluation on a stakeholder-created golden dataset
- Optimize the data agent based on wrong responses

### Demo Steps

| Step | Task |
|---|---|
| Demo 3.1 | Create Semantic View on Silver data |
| Demo 3.2 | Create a Cortex Agent grounded on the semantic view |
| Demo 3.3 | Evaluate against a business-user curated dataset |
| Demo 3.4 | Iterate on Agent from evaluation feedback |

> **Note:** Requires Vignettes 1–2 completed.

<!-- ------------------------ -->
## Agent Evaluation Deep Dive

The bundled **`$agent-optimize`** skill supports four evaluation approaches:

| Approach | Description |
|---|---|
| **Ad-Hoc Testing** | Interactively ask questions and manually review responses to explore agent behavior |
| **Curated Dataset Testing** | Run business-stakeholder-provided questions with expected answers; score with LLM judge |
| **Feedback-Based Testing** | Review production queries in a Streamlit app and annotate responses |
| **Evaluation Dataset Curation** | Build a representative question set from production logs or create from scratch |

The workshop uses **Approach #2: Curated Dataset Testing** — business stakeholders provide 15–20 realistic questions with expected answers. This is the most common starting point for teams building data agents.

### `$semantic-view` Skill Capabilities

| Mode | Trigger Example |
|---|---|
| **Create** | "Create a semantic view for my sales table" |
| **Audit** | "Test all my VQRs still work after schema changes" |
| **Debug** | "Why does 'revenue by region' generate the wrong SQL?" |

### `$agent-optimize` Skill Capabilities

| Mode | Trigger Example |
|---|---|
| **Create** | "Build customer support agent to query data + respond" |
| **Ad-Hoc Test** | "I want to test on 20 common questions" |
| **Debug Query** | "Why does 'show me last quarter's revenue' fail?" |
| **Optimize** | "Agent only works 60% accuracy on my test set" |

<!-- ------------------------ -->
## Conclusion And Resources

By completing this guide you have:
- Installed and configured the Cortex Code CLI on your machine
- Connected CoCo to your Snowflake environment
- Built a multi-source Dynamic Table pipeline (Bronze → Silver → Gold)
- Maintained and evolved a live pipeline using an Excel PRD
- Created a Cortex Agent backed by a semantic view, with a full evaluation framework

### What You Learned
- CLI installation on Mac and Windows
- Snowflake connection configuration and authentication options
- Using execution modes (Confirm, Plan, Bypass) safely
- Building declarative pipelines with `$dynamic-tables`
- Creating and evaluating Cortex Agents with `$cortex-agent` and `$semantic-view`

### Related Resources
- [Cortex Code Documentation](https://docs.snowflake.com/en/user-guide/cortex-code)
- [Snowflake Guide: Get Started with Guides](https://www.snowflake.com/en/developers/guides/get-started-with-guides)
- [Manage Snowflake Connections](https://docs.snowflake.com/en/user-guide/snowsql-connect)
- [Dynamic Tables Overview](https://docs.snowflake.com/en/user-guide/dynamic-tables-intro)
- [Cortex Agents Overview](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-agent)
- [sfguides GitHub Issues](https://github.com/Snowflake-Labs/sfguides/issues)
