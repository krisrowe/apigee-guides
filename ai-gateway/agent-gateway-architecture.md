# Agent Gateway Architecture Deep Dive (Gemini Enterprise Agent Platform)

<div class="subnav">
  <a href="/ai-gateway/">Apigee AI Gateway</a>
  <a href="/ai-gateway/agent-gateway-comparison">Compare &amp; Combine: Agent Gateway</a>
  <span class="current">Agent Gateway Deep Dive</span>
</div>

Infrastructure and identity reference for **Gemini Enterprise Agent Platform: Agent Gateway**, covering its underlying GCP control-plane APIs, deployment models, Private CA trust configuration, per-agent [SPIFFE](https://spiffe.io/) identity, IAM Unified Access Policies, Service Extensions (`Semantic Governance` and [Model Armor](https://docs.cloud.google.com/model-armor/overview)), and operational limits *(last reviewed November 6, 2026)*.

<div class="toc-box" markdown="1">

**On This Page**

* [1. What Agent Gateway Is Under the Hood](#1-what-agent-gateway-is-under-the-hood)
* [2. Traffic Topologies, Deployment Models & Private CA Connectivity](#2-traffic-topologies-deployment-models--private-ca-connectivity)
  * [Outbound Egress Governance (`AGENT_TO_ANYWHERE`)](#outbound-egress-governance-agent_to_anywhere) · [Inbound Ingress Governance (`CLIENT_TO_AGENT`)](#inbound-ingress-governance-client_to_agent)
  * [Deployment Models: 1 GA vs. 3 Early Preview](#deployment-models-1-ga-vs-3-early-preview)
  * [Private CAs & Self-Signed Certificates via `TrustConfig`](#private-cas--self-signed-certificates-via-trustconfig)
* [3. Cryptographic Agent Identity (`SPIFFE`, `mTLS`, `DPoP`) & Auth Manager](#3-cryptographic-agent-identity-spiffe-mtls-dpop--auth-manager)
* [4. IAM Unified Access Policies](#4-iam-unified-access-policies)
* [5. Service Extensions, Model Armor & Semantic Governance](#5-service-extensions-model-armor--semantic-governance)
* [6. Scope Boundaries & Operational Limits](#6-scope-boundaries--operational-limits)
* [7. Official Agent Gateway Documentation References](#7-official-agent-gateway-documentation-references)

</div>

---

## 1. What Agent Gateway Is Under the Hood

Beneath the **Gemini Enterprise** Console branding, Agent Gateway is a managed network and security proxy built on **Cloud Network Services** and [Private Service Connect (`PSC`)](https://docs.cloud.google.com/vpc/docs/private-service-connect), wired into **Identity-Aware Proxy (`IAP`)** and **Service Extensions** ([Agent Gateway overview](https://docs.cloud.google.com/gemini-enterprise-agent-platform/govern/gateways/agent-gateway-overview), [Set up Agent Gateway](https://docs.cloud.google.com/gemini-enterprise-agent-platform/govern/gateways/set-up-agent-gateway), [Set up VPC connectivity](https://docs.cloud.google.com/gemini-enterprise-agent-platform/govern/gateways/set-up-vpc-connectivity)):

> *"Agent Gateway is a managed proxy service that provides a centralized enforcement point to help secure, govern, and monitor all network traffic for your AI agents. It mediates connections to and from agents deployed in Agent Runtime and Gemini Enterprise, helping to ensure that interactions with users, other agents, and external tools adhere to your organization's security standards."*
> ([Agent Gateway overview](https://docs.cloud.google.com/gemini-enterprise-agent-platform/govern/gateways/agent-gateway-overview))

<details>
<summary>Seven Collaborating Google Cloud Subsystems</summary>
<div markdown="1">

1. **Compute Engine Network Attachment:** Bridges the Google-managed agent runtime VPC to your consumer VPC and the Agent Gateway data plane inside a dedicated regional subnet (minimum `/28` CIDR, automatic connection acceptance).
2. **Agent Connectivity Template:** Bundles your [VPC egress mode](https://docs.cloud.google.com/gemini-enterprise-agent-platform/govern/gateways/set-up-vpc-connectivity#vpc-egress-modes), peered Cloud DNS private zones (non-transitive), and [Certificate Manager trust anchors](https://docs.cloud.google.com/certificate-manager/docs/trust-configs).
3. **Network Services Agent Gateway:** The managed Envoy proxy handling [MCP](https://modelcontextprotocol.io/introduction) and HTTPS traffic in either outbound egress mode or inbound ingress mode.
4. **Agent Identity:** Automatically mints a per-agent cryptographic workload identity when agents are created in Vertex AI Agent Runtime, Gemini Enterprise, or Cloud Run ([Agent Identity overview](https://docs.cloud.google.com/gemini-enterprise-agent-platform/govern/agent-identity-overview)).
5. **[Agent Registry](https://docs.cloud.google.com/gemini-enterprise-agent-platform/govern/agent-registry):** Central directory of agents, MCP servers, agent skills, and custom endpoints bound to the gateway for policy evaluation.
6. **[IAM Unified Access Policies](https://docs.cloud.google.com/gemini-enterprise-agent-platform/govern/policies/iam-overview-uap):** Evaluates identity-and-destination CEL conditions backed by the IAP v2 engine on every outbound call.
7. **[Network Security Authorization Policies & Service Extensions](https://docs.cloud.google.com/gemini-enterprise-agent-platform/govern/gateways/delegate-authorization):** Streams headers or full payloads over Envoy `ext_proc` to Model Armor, Semantic Governance, `Apigee Extension Processor`, or 15 supported ISV security partners.

</div>
</details>

---

## 2. Traffic Topologies, Deployment Models & Private CA Connectivity

Every Agent Gateway instance runs in one of two mutually exclusive modes covering egress or ingress traffic.

#### Outbound Egress Governance (`AGENT_TO_ANYWHERE`)

In egress mode, the gateway acts as an outbound forward proxy for a Google-hosted agent. Every call the agent makes—invoking an MCP server, calling another [A2A](https://a2a-protocol.org/latest/) agent, reaching an LLM endpoint, or emitting Google Cloud telemetry—passes through the proxy.

You attach an egress gateway during deployment on [Vertex AI Agent Runtime](https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/runtime/agent-gateway-runtime-deploy) (including cross-project gateways in the same region) or set it at the engine level on Gemini Enterprise (`defaultEgressAgentGateway`). In the gateway's [VPC egress configuration](https://docs.cloud.google.com/gemini-enterprise-agent-platform/govern/gateways/set-up-vpc-connectivity#vpc-egress-modes), private-ranges mode routes RFC 1918 and peered Cloud DNS private zones into your VPC while sending public HTTPS out through Google's edge; all-traffic mode forces every outbound flow (including `restricted.googleapis.com`) through your VPC so you can apply static Cloud NAT IPs, Cloud NGFW inspection, and [VPC Service Controls](https://docs.cloud.google.com/vpc-service-controls/docs/overview).

#### Inbound Ingress Governance (`CLIENT_TO_AGENT`)

In ingress mode, Agent Gateway acts as an inbound reverse proxy in front of **Vertex AI Agent Runtime** (`query` and `streamQuery` only; async queries are unsupported), enforcing inbound content authorization in the same project and region. Inbound ingress mode is not supported on Gemini Enterprise ([runtime region guide](https://docs.cloud.google.com/gemini-enterprise-agent-platform/govern/gateways/set-up-agent-gateway#choose-runtime-region)).

#### Deployment Models: 1 GA vs. 3 Early Preview

Google Cloud defines four Agent Gateway deployment models under a shared control plane ([deployment models overview](https://docs.cloud.google.com/gemini-enterprise-agent-platform/govern/gateways/agent-gateway-overview#deployment-models)), though only the Google-managed model is Generally Available today:

| Deployment Model | Launch Stage | Underlying Data Plane Mechanics | Supported Access Paths |
| :--- | :--- | :--- | :--- |
| **[1. Google-Managed Agent Gateway](https://docs.cloud.google.com/gemini-enterprise-agent-platform/govern/gateways/agent-gateway-overview#managed-agw)** | **GA** | Google-managed Envoy proxy attached via a Private Service Connect network attachment in Google Cloud. | Agent Runtime (ingress + egress)<br>Gemini Enterprise (egress only) |
| **[2. Self-Managed on GKE](https://docs.cloud.google.com/gemini-enterprise-agent-platform/govern/gateways/agent-gateway-overview#gke-agw)** | **Early Preview** | **Ingress:** GKE Gateway API (Regional ALB).<br>**Egress:** Sidecar-less GKE ambient networking routing pod egress to a customer-managed Secure Web Proxy, plus namespace ambient proxies for pod-to-pod calls. | Ingress + Egress |
| **[3. Self-Managed on Cloud Run](https://docs.cloud.google.com/gemini-enterprise-agent-platform/govern/gateways/agent-gateway-overview#cloud-run-agw)** | **Early Preview** | **Ingress:** Regional External or Internal ALB.<br>**Egress:** Cloud Run ambient networking over Direct VPC egress mTLS tunnels to a customer-managed Secure Web Proxy. | Ingress + Egress |
| **[4. Agent Gateway for Cross-Cloud](https://docs.cloud.google.com/gemini-enterprise-agent-platform/govern/gateways/agent-gateway-overview#cross-cloud-agw)** | **Early Preview** | Customer-deployed Envoy proxy running in **Amazon EKS, Azure AKS, OpenShift, or on-premises Kubernetes**. Data-plane traffic stays local while control-plane auth, registry, and guardrails connect back to Google Cloud. | Ingress + Egress |

#### Private CAs & Self-Signed Certificates via `TrustConfig`

When internal destinations (VPC MCP servers, direct Apigee PSC endpoints, or private LLMs) use internal PKI or self-signed certificates, Agent Gateway accepts custom anchors via a [Certificate Manager TrustConfig](https://docs.cloud.google.com/certificate-manager/docs/trust-configs) referenced by the connectivity template ([TLS certificate requirements](https://docs.cloud.google.com/gemini-enterprise-agent-platform/govern/gateways/set-up-vpc-connectivity#tls-certificate-requirements)), with three operational constraints:

1. **Keep publicly trusted roots enabled (`PUBLICLY_TRUSTED_ROOTS`):** Disabling public roots breaks outbound agent calls to `*.googleapis.com` (Vertex AI Gemini, Cloud Logging, and telemetry).
2. **Rotate PEM certificates manually:** Secret Manager automatic certificate rotation is not wired into Agent Gateway trust configs yet.
3. **Treat connectivity templates as immutable:** Changing TLS anchors, DNS peering, or VPC egress modes requires creating a new connectivity template and re-pointing the gateway ([updating egress settings](https://docs.cloud.google.com/gemini-enterprise-agent-platform/govern/gateways/set-up-vpc-connectivity#updating-egress-settings)).

<details>
<summary>Official TrustConfig TLS Behavior Excerpt</summary>
<div markdown="1">

> *"Private CAs and self-signed certificates: If your target destination (agents, tools, or MCP servers in your VPC network) uses a private CA or internal PKI, you can configure custom trust anchors using the tlsConfig setting in your connectivity template. By referencing a Certificate Manager TrustConfig resource, you can configure Agent Gateway to trust only specific private CAs, or combine private root CAs with publicly trusted CAs (PUBLICLY_TRUSTED_ROOTS)... If your agents connect to Google Cloud APIs (*.googleapis.com) or other public HTTPS endpoints, you must set additionalRoots to PUBLICLY_TRUSTED_ROOTS; without this setting, Agent Gateway doesn't trust Google-signed certificates for googleapis.com."*
> ([Set up Agent Gateway with VPC connectivity](https://docs.cloud.google.com/gemini-enterprise-agent-platform/govern/gateways/set-up-vpc-connectivity#tls-certificate-requirements))

</div>
</details>

---

## 3. Cryptographic Agent Identity (`SPIFFE`, `mTLS`, `DPoP`) & Auth Manager

Instead of sharing one coarse Google Cloud Service Account across multiple agents—where static keys or broad IAM roles create blast-radius risk—**Agent Identity** issues every deployed agent its own un-impersonatable cryptographic identity based on [SPIFFE](https://spiffe.io/), the CNCF X.509 workload identity standard ([Agent Identity overview](https://docs.cloud.google.com/gemini-enterprise-agent-platform/govern/agent-identity-overview)):

1. **Creation-time provisioning (`identity_type="AGENT_IDENTITY"`):** Enabling agent identity when creating an agent in Vertex AI Agent Runtime, Gemini Enterprise, or Cloud Run provisions a workload identity formatted as:
   ```
   spiffe://agents.global.org-<ORG_ID>.system.id.goog/resources/<SERVICE_NAME>/<RESOURCE_PATH>
   ```
   IAM policies match either a single agent principal or an entire project principal set, and because identity type is fixed at creation time, existing Service-Account-based agents cannot be retrofitted.
2. **Short-lived 24-hour certificates with zero static keys:** Google rotates the underlying X.509 certificates automatically every 24 hours; there are no private keys to download, and humans cannot impersonate an Agent Identity from a laptop.
3. **Two-hop cryptographic binding (`mTLS` + `DPoP`):** The agent authenticates to Agent Gateway over mutual TLS (`mTLS`), and Agent Gateway binds downstream tokens using Demonstrating Proof of Possession (`DPoP`) through Context-Aware Access—so targets verify tokens belong to that specific agent ([opt-out guidance](https://docs.cloud.google.com/iam/docs/auth-agent-own-identity#opt-out-caa) exists for destinations that reject proof-of-possession tokens).
4. **Auth Manager zero-trust token handling:** [Agent Identity Auth Manager](https://docs.cloud.google.com/gemini-enterprise-agent-platform/govern/agent-identity-overview#agent-auth-manager) secures both user-delegated 3-legged OAuth (3LO) tokens and agent-owned credentials:
   > *"When used with Agent Gateway and Gemini Enterprise, end-user credentials are encrypted by auth manager and decrypted at the gateway, so the agent never handles raw credentials."*

---

## 4. IAM Unified Access Policies

Agent Gateway enforces allow/deny egress rules through [IAM v3 Unified Access Policies](https://docs.cloud.google.com/gemini-enterprise-agent-platform/govern/policies/iam-overview-uap) built on Identity-Aware Proxy's v2 policy engine ([configuration guide](https://docs.cloud.google.com/gemini-enterprise-agent-platform/govern/policies/configure-iam-policies-uap)).

Policies grant or deny the IAP egress permission using `roles/iap.egressor` (requiring IAP `V2` policy metadata on the IAP extension when combined with Service Extensions, see [combining IAP and Model Armor](https://docs.cloud.google.com/gemini-enterprise-agent-platform/govern/gateways/delegate-authorization#combine-iap-ma)). Both Allow and Deny rules coexist in a single policy, and teams can start in **dry-run enforcement** to inspect real outbound agent dependencies in Cloud Audit Logs before flipping to strict enforcement. For Google Cloud organizations created after March 4, 2026, remove the managed org constraint blocking access-policy bindings before attaching rules.

<details>
<summary>CEL Attribute Reference (Registered Agent Registry vs. Unregistered Endpoints)</summary>
<div markdown="1">

* **Registered Resources (in Agent Registry):** Write CEL conditions against canonical metadata without hardcoding IPs or URLs:
  * `destination.agent_registry.resource_type` (`'AGENT'`, `'ENDPOINT'`, `'MCP_SERVER'`, `'SKILL'`)
  * `destination.agent_registry.mcp_server.name` (e.g., `'projects/123456/locations/us-central1/mcpServers/apihub:bigquery-mcp'`)
  * `destination.agent_registry.mcp_server.method` (e.g., `'tools/call'`, `'tools/list'`)
  * `destination.agent_registry.mcp_server.tool.name` (e.g., `'execute_sql'`)
  * **MCP Tool Annotations:**
    * `destination.agent_registry.mcp_server.tool.annotations.read_only_hint` (`bool`)
    * `destination.agent_registry.mcp_server.tool.annotations.destructive_hint` (`bool`)
    * `destination.agent_registry.mcp_server.tool.annotations.idempotent_hint` (`bool`)
    * `destination.agent_registry.mcp_server.tool.annotations.open_world_hint` (`bool`)
* **Unregistered Resources (Arbitrary HTTP/MCP Endpoints):**
  * `destination.unregistered.host` (e.g., `'api.github.com'`)
  * `destination.unregistered.path` (e.g., `'/v1/QueryData'`)
  * `destination.unregistered.method` (e.g., `'GET'`, `'POST'`)

</div>
</details>

<details>
<summary>Example: IAM Unified Access Policy Blocking Destructive MCP Tools (JSON)</summary>
<div markdown="1">

```json
{
  "details": {
    "rules": [
      {
        "description": "Allow agent to call read-only tools on registered MCP servers",
        "Effect": "ALLOW",
        "principals": [
          "principal://agents.global.org-987654321.system.id.goog/resources/aiplatform/projects/123456789/locations/us-central1/reasoningEngines/555555"
        ],
        "permissions": ["iap.googleapis.com/resources.egressViaIAP"],
        "condition": {
          "title": "AllowReadOnlyMcpTools",
          "expression": "destination.agent_registry.resource_type == 'MCP_SERVER' && destination.agent_registry.mcp_server.tool.annotations.read_only_hint == true"
        }
      },
      {
        "description": "Deny destructive MCP tools",
        "Effect": "DENY",
        "principals": [
          "principal://agents.global.org-987654321.system.id.goog/resources/aiplatform/projects/123456789/locations/us-central1/reasoningEngines/555555"
        ],
        "permissions": ["iap.googleapis.com/resources.egressViaIAP"],
        "condition": {
          "title": "BlockDestructiveMcpTools",
          "expression": "destination.agent_registry.resource_type == 'MCP_SERVER' && destination.agent_registry.mcp_server.tool.annotations.destructive_hint == true"
        }
      }
    ]
  }
}
```

</div>
</details>

---

## 5. Service Extensions, Model Armor & Semantic Governance

For deeper header matching and payload inspection, Agent Gateway pairs Network Security authorization policies with full-duplex streaming Service Extensions across two lifecycle hooks ([delegate authorization](https://docs.cloud.google.com/gemini-enterprise-agent-platform/govern/gateways/delegate-authorization)):

* **Request authorization (`REQUEST_AUTHZ`):** Matches HTTP headers and MCP methods/tool names. Always allow base MCP protocol lifecycle methods (`initialize`, `ping`, `notifications`) on allow rules so client sessions do not fail during handshake.
* **Content authorization (`CONTENT_AUTHZ`):** Streams request and response bodies to [Model Armor](https://docs.cloud.google.com/model-armor/overview), the Semantic Governance Policy Engine, `Apigee Extension Processor` ([Topology 3](agent-gateway-comparison.md#topology-3-inline-authorization-extension)), or any custom or partner callout.

### Semantic Governance Intent Gate & Streaming Limitations

Available in **Preview**, [Semantic governance policies](https://docs.cloud.google.com/gemini-enterprise-agent-platform/govern/policies/semantic-governance-overview) run an LLM at the gateway to evaluate whether an agent's next proposed action matches the user's original intent and plain-English business constraints:

> *"Semantic governance policies use a large language model (LLM) to evaluate agent traffic against natural language rules at runtime... Semantic governance acts as an intent gate. It evaluates whether the proposed action aligns with the user's original prompt and complies with the defined natural language constraints."*

The intent engine evaluates five runtime inputs—the current user prompt, Natural Language Constraints, the tools manifest, conversation history, and the suggested tool call—across Gemini, Anthropic, Claude on Vertex/GEAP, OpenAI, Mistral, Llama on GEAP, and self-hosted vLLM ([supported model families](https://docs.cloud.google.com/gemini-enterprise-agent-platform/govern/policies/semantic-governance-overview#supported-providers)), with Preview VPC-SC support ([September 25, 2026 release notes](https://docs.cloud.google.com/gemini-enterprise-agent-platform/release-notes#September_25_2026)). Teams can also disable prompt-alignment matching when they only want deterministic evaluation of static natural-language rules.

Keep two caveats in mind when designing controls:

1. **Streaming model calls bypass Semantic Governance:** Server-sent streaming responses are not evaluated today; enforce non-streaming model routes or deterministic gateway quotas wherever tool-call intent gating is mandatory.
2. **Customize denial messages before going live:** Default denials echo the internal business rule back to callers; configure a custom `denialMessage` (up to `1,000` characters) so internal dollar thresholds or risk rules are never leaked.

### Model Armor Payload & Token Boundaries

Model Armor coverage on Agent Gateway has strict payload and streaming boundaries ([supported and unsupported payloads](https://docs.cloud.google.com/gemini-enterprise-agent-platform/govern/configure-model-armor#supported-unsupported-payloads)):

* **Ingress:** Scans streaming queries for ADK agents on Vertex AI Agent Runtime only; async queries and non-ADK frameworks pass through uninspected.
* **Egress:** Scans non-streaming OpenAI calls, non-streaming MCP tool calls/prompts, and unary A2A messages, while passing through MCP `tools/list`, MCP resources, SSE/Streamable HTTP MCP streams, streaming A2A, and A2A gRPC without scanning.
* **Token size cutoffs:** Payloads exceeding **`65,536` tokens** for prompt injection, jailbreak, RAI, or CSAM (`130,000` tokens for sensitive-data protection; `4 MB` max payload) skip scanning (`EXECUTION_SKIPPED`) and pass through. Direct Vertex AI Model Armor floor settings also fail open on internal errors and block rather than inline-redacting matches ([Vertex AI integration limits](https://docs.cloud.google.com/model-armor/model-armor-vertex-integration#limitations)).

---

## 6. Scope Boundaries & Operational Limits

Architects planning Agent Gateway deployments should account for six documented operational boundaries ([Agent Gateway limitations](https://docs.cloud.google.com/gemini-enterprise-agent-platform/govern/gateways/agent-gateway-overview#limitations), [VPC-SC compliance](https://docs.cloud.google.com/gemini-enterprise-agent-platform/govern/gateways/set-up-vpc-connectivity#vpc-sc-compliance), and [restricting Agent Runtime](https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/runtime/agent-gateway-runtime-deploy#restrict-ae)):

* **No REST-to-MCP translation, API Products, or rate quotas:** Agent Gateway is a passthrough network proxy; it cannot compile OpenAPI specs into MCP servers, trim `tools/list` arrays per consumer tier, or enforce per-tool or token quotas.
* **Default-deny startup (`HTTP 498`) & exact Google API registration:** Because 100% of outbound runtime traffic goes through the gateway, an empty IAM policy blocks `logging`, `monitoring`, `telemetry`, `storage`, and `aiplatform` endpoints with `HTTP 498`. Agent Registry does not support `*.googleapis.com` wildcards—register exact standard, mTLS, and regional Google API hostnames or launch IAP in dry-run mode first ([registering Google API endpoints](https://docs.cloud.google.com/agent-registry/register-endpoints#google-apis-endpoint)).
* **VPC-SC cutoff & prerequisites:** VPC Service Controls compliance applies only to gateways created after **September 8, 2026** running in all-traffic VPC egress mode, with private DNS mapping Google APIs to `restricted.googleapis.com` (`199.36.153.4/30`) inside the same perimeter as Shared VPC hosts.
* **Agent Runtime binding & lifecycle constraints:** Cannot attach to Reasoning Engines built before **April 29, 2026** or without Agent Identity enabled at creation. All Agent Runtime engines in a single project and region share the same ingress and egress gateways, updating a binding permanently archives earlier revisions (only allowed at 100% latest-revision traffic), and attaching Agent Gateway disables Security Command Center *Agent Engine Threat Detection*.
* **Gemini Enterprise registry binding:** Gemini Enterprise attaches only in egress mode and binds to one regional Agent Registry (`us-central1` for `global`/`us`; `europe-west1` for `eu`).
* **Scale, policy, and network limits:** Maximum **`5,000` registered resources** per gateway, **`4` authorization policies** on egress (same-profile execution order is not guaranteed), **`1` content authorization policy** on ingress, **`1,500`-byte MTU** on PSC network attachments, and custom FQDN callout extensions connect over TLS `:443` without verifying server certificates (keep custom extensions inside private VPCs).

---

## 7. Official Agent Gateway Documentation References

1. [Agent Gateway overview](https://docs.cloud.google.com/gemini-enterprise-agent-platform/govern/gateways/agent-gateway-overview) · [Set up Agent Gateway](https://docs.cloud.google.com/gemini-enterprise-agent-platform/govern/gateways/set-up-agent-gateway)
2. [Set up Agent Gateway with VPC connectivity](https://docs.cloud.google.com/gemini-enterprise-agent-platform/govern/gateways/set-up-vpc-connectivity) · [VPC Service Controls overview](https://docs.cloud.google.com/vpc-service-controls/docs/overview) · [Certificate Manager TrustConfig](https://docs.cloud.google.com/certificate-manager/docs/trust-configs)
3. [Route Agent Runtime traffic through Agent Gateway](https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/runtime/agent-gateway-runtime-deploy) · [Agent Gateway ISV partners (15 partners)](https://docs.cloud.google.com/gemini-enterprise-agent-platform/govern/gateways/agw-partners)
4. [Delegate authorization with Service Extensions](https://docs.cloud.google.com/gemini-enterprise-agent-platform/govern/gateways/delegate-authorization) · [Service Extensions callout limits](https://docs.cloud.google.com/service-extensions/docs/callouts-overview#limitations_with_body_processing)
5. [Agent Identity overview](https://docs.cloud.google.com/gemini-enterprise-agent-platform/govern/agent-identity-overview) · [Authenticate using an agent's own identity](https://docs.cloud.google.com/iam/docs/auth-agent-own-identity) · [Agent Identity locations](https://docs.cloud.google.com/iam/docs/agent-identity-locations)
6. [Agent Registry overview](https://docs.cloud.google.com/gemini-enterprise-agent-platform/govern/agent-registry) · [Register Google API endpoints](https://docs.cloud.google.com/agent-registry/register-endpoints#google-apis-endpoint)
7. [IAM Unified Access Policies overview](https://docs.cloud.google.com/gemini-enterprise-agent-platform/govern/policies/iam-overview-uap) · [Create IAM Unified Access Policies](https://docs.cloud.google.com/gemini-enterprise-agent-platform/govern/policies/configure-iam-policies-uap)
8. [Semantic governance policies overview](https://docs.cloud.google.com/gemini-enterprise-agent-platform/govern/policies/semantic-governance-overview) · [Gemini Enterprise Agent Platform release notes](https://docs.cloud.google.com/gemini-enterprise-agent-platform/release-notes)
9. [Configure Model Armor on a gateway](https://docs.cloud.google.com/gemini-enterprise-agent-platform/govern/configure-model-armor) · [Integrate Model Armor with Vertex AI](https://docs.cloud.google.com/model-armor/model-armor-vertex-integration)

---

[← Back to Compare & Combine Guide](agent-gateway-comparison.md) · [Apigee AI Gateway Home ->](README.md)
