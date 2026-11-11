# Agent Gateway Architecture Deep Dive (Gemini Enterprise Agent Platform)

<div class="subnav">
  <a href="/ai-gateway/">Apigee AI Gateway</a>
  <a href="/ai-gateway/agent-gateway-comparison">Compare &amp; Combine: Agent Gateway</a>
  <span class="current">Agent Gateway Deep Dive</span>
</div>

Infrastructure and identity specification for **Gemini Enterprise Agent Platform: Agent Gateway** — covering its underlying GCP control-plane APIs, deployment models, Private CA `TrustConfig` handling, per-agent cryptographic identity (`SPIFFE`), IAM Unified Access Policies, Service Extensions (`Semantic Governance` and `Model Armor`), and operational limits *(last reviewed November 6, 2026)*.

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

Beneath the **Gemini Enterprise** Console branding, Agent Gateway is a managed network and security proxy built on **Cloud Network Services (`networkservices.googleapis.com`)** and **Private Service Connect (`compute.googleapis.com`)**, wired into **Identity-Aware Proxy (`iap.googleapis.com`)** and **Service Extensions** ([Agent Gateway overview](https://docs.cloud.google.com/gemini-enterprise-agent-platform/govern/gateways/agent-gateway-overview#core-governance-components), [Set up Agent Gateway](https://docs.cloud.google.com/gemini-enterprise-agent-platform/govern/gateways/set-up-agent-gateway), [Set up VPC connectivity](https://docs.cloud.google.com/gemini-enterprise-agent-platform/govern/gateways/set-up-vpc-connectivity#how-it-works)).

> *"Agent Gateway is a managed proxy service that provides a centralized enforcement point to help secure, govern, and monitor all network traffic for your AI agents. It mediates connections to and from agents deployed in Agent Runtime and Gemini Enterprise, helping to ensure that interactions with users, other agents, and external tools adhere to your organization's security standards."*
> ([Agent Gateway overview](https://docs.cloud.google.com/gemini-enterprise-agent-platform/govern/gateways/agent-gateway-overview))

<details>
<summary>Seven Collaborating Google Cloud Subsystems</summary>
<div markdown="1">

1. **Compute Engine Network Attachment (`compute.networkAttachments`):** Placed in a dedicated subnet (`connection-preference=ACCEPT_AUTOMATIC`, minimum `/28` CIDR) in the same region as your agent to bridge the Google-managed agent runtime VPC to your consumer VPC and the Agent Gateway data plane.
2. **Agent Connectivity Template (`networkservices.agentConnectivityTemplates`):** Encapsulates VPC egress mode (`PRIVATE_RANGES_ONLY` default vs. `ALL_TRAFFIC` for VPC-SC or Cloud NAT static egress), Cloud DNS peering domains (`dnsPeeringConfig`, without chained DNS peering), and private CA trust anchors (`tlsConfig.trustConfig` referencing Certificate Manager `TrustConfig`).
3. **Network Services Agent Gateway (`networkservices.agentGateways`):** The Envoy-based proxy resource configured with `"protocols": ["MCP"]`, a `googleManaged.governedAccessPath` (`AGENT_TO_ANYWHERE` or `CLIENT_TO_AGENT`), and an optional `networkConfig.egress` reference.
4. **Agent Identity:** A per-agent cryptographic workload identity provisioned automatically at creation time (`identity_type="AGENT_IDENTITY"`) for agents in Agent Runtime, Gemini Enterprise, and Cloud Run.
5. **Agent Registry (`agentregistry.googleapis.com`):** Central inventory of agents (`AGENT`), MCP servers (`MCP_SERVER`), skills (`SKILL`), and endpoints (`ENDPOINT`) attached to the gateway via `"registries"`.
6. **IAM Unified Access Policies (`iam.googleapis.com` v3 + `iap.googleapis.com`):** Evaluates identity-and-destination CEL rules (`iap.googleapis.com/resources.egressViaIAP`, role `roles/iap.egressor`, with mandatory `iapPolicyVersion: "V2"` metadata on the `iap.googleapis.com` extension) on every outbound call.
7. **Network Security Authorization Policies & Service Extensions (`networksecurity.authzPolicies` + `networkservices.authzExtensions`):** Hooks into Envoy (`ext_proc` in `FULL_DUPLEX_STREAMED` mode) for `REQUEST_AUTHZ` and `CONTENT_AUTHZ`, delegating to Model Armor, the Semantic Governance Policy Engine, `Apigee Extension Processor`, or any of 15 supported ISV security partners.

</div>
</details>

---

## 2. Traffic Topologies, Deployment Models & Private CA Connectivity

Each Agent Gateway instance operates in one of two mutually exclusive access paths (`governedAccessPath`):

#### Outbound Egress Governance (`AGENT_TO_ANYWHERE`)

Acts as an outbound forward proxy for an agent. Every outbound request the agent makes—calling an MCP server (`tools/list`, `tools/call`), invoking another agent over A2A, calling an LLM endpoint, or talking to Google Cloud telemetry and storage APIs—traverses the gateway.

* **Vertex AI Agent Runtime (`aiplatform.googleapis.com` Reasoning Engine):** Bound during deployment via `pscInterfaceConfig` and `agentGatewayConfig.agentToAnywhereConfig.agentGateway`. Supports cross-project sharing (an agent in Project A can bind to an egress gateway in Project B in the **same region**, granted via `roles/networkservices.viewer`).
* **Gemini Enterprise (`discoveryengine.googleapis.com`):** Bound at the engine level via `agentGatewaySetting.defaultEgressAgentGateway` (`GOOGLE_MANAGED` / `AGENT_TO_ANYWHERE`).
* **VPC egress modes ([`set-up-vpc-connectivity#vpc-egress-modes`](https://docs.cloud.google.com/gemini-enterprise-agent-platform/govern/gateways/set-up-vpc-connectivity#vpc-egress-modes)):** `PRIVATE_RANGES_ONLY` (default) routes RFC 1918 / privately used public IPs and peered Cloud DNS private zones into your VPC while sending public HTTPS directly via Google's edge. `ALL_TRAFFIC` forces all outbound traffic (including `restricted.googleapis.com` at `199.36.153.4/30`) into your VPC for static Cloud NAT IP allowlisting, Cloud NGFW inspection, and VPC Service Controls (VPC-SC) enforcement.

#### Inbound Ingress Governance (`CLIENT_TO_AGENT`)

Acts as an inbound reverse proxy in front of **Vertex AI Agent Runtime** (`query` and `streamQuery` methods only; `asyncQuery` is unsupported), applying inbound `CONTENT_AUTHZ` in the same project and region as the runtime. Inbound `CLIENT_TO_AGENT` mode is not supported on Gemini Enterprise ([`set-up-agent-gateway#choose-runtime-region`](https://docs.cloud.google.com/gemini-enterprise-agent-platform/govern/gateways/set-up-agent-gateway#choose-runtime-region)).

#### Deployment Models: 1 GA vs. 3 Early Preview

Google Cloud defines four Agent Gateway deployment models under a shared control plane ([`agent-gateway-overview#deployment-models`](https://docs.cloud.google.com/gemini-enterprise-agent-platform/govern/gateways/agent-gateway-overview#deployment-models)); only the Google-managed model is Generally Available today:

| Deployment Model | Launch Stage | Underlying Data Plane Mechanics | Supported Access Paths |
| :--- | :--- | :--- | :--- |
| **1. Google-Managed Agent Gateway** ([`#managed-agw`](https://docs.cloud.google.com/gemini-enterprise-agent-platform/govern/gateways/agent-gateway-overview#managed-agw)) | **GA** | Google-managed Envoy proxy attached via PSC Network Attachment in Google Cloud. | `Agent Runtime`: Ingress + Egress<br>`Gemini Enterprise`: Egress ONLY |
| **2. Self-Managed on GKE** ([`#gke-agw`](https://docs.cloud.google.com/gemini-enterprise-agent-platform/govern/gateways/agent-gateway-overview#gke-agw)) | **Early Preview** *("Coming soon")* | **Ingress:** GKE Gateway API (Regional ALB).<br>**Egress:** Sidecar-less GKE ambient networking routing pod egress to a customer-managed **Secure Web Proxy (`SWP`)**, plus per-namespace ambient proxies for pod-to-pod A2A/MCP calls. | `Client-to-Agent` + `Agent-to-Anywhere` |
| **3. Self-Managed on Cloud Run** ([`#cloud-run-agw`](https://docs.cloud.google.com/gemini-enterprise-agent-platform/govern/gateways/agent-gateway-overview#cloud-run-agw)) | **Early Preview** *("Coming soon")* | **Ingress:** Regional External or Internal ALB (`RXLB` / `RILB`).<br>**Egress:** Cloud Run ambient networking over Direct VPC egress mTLS tunnel to a customer-managed **Secure Web Proxy (`SWP`)**. | `Client-to-Agent` + `Agent-to-Anywhere` |
| **4. Agent Gateway for Cross-Cloud** ([`#cross-cloud-agw`](https://docs.cloud.google.com/gemini-enterprise-agent-platform/govern/gateways/agent-gateway-overview#cross-cloud-agw)) | **Early Preview** *("Coming soon")* | Customer-deployed lightweight Envoy gateway running inside **Amazon EKS, Azure AKS, OpenShift, or on-premises Kubernetes**. Request traffic stays local while control plane (WIF -> Agent Identity, Agent Registry, Model Armor, observability) connects to Google Cloud. | `Client-to-Agent` + `Agent-to-Anywhere` |

#### Private CAs & Self-Signed Certificates via `TrustConfig`

For VPC destinations (internal MCP servers, Apigee PSC endpoints, private LLMs) using internal PKI or self-signed certificates, Agent Gateway supports custom trust anchors via Certificate Manager `TrustConfig` referenced by `tlsConfig.trustConfig` ([`set-up-vpc-connectivity#tls-certificate-requirements`](https://docs.cloud.google.com/gemini-enterprise-agent-platform/govern/gateways/set-up-vpc-connectivity#tls-certificate-requirements)), subject to three constraints:

1. **Always include `additionalRoots: PUBLICLY_TRUSTED_ROOTS`:** Omitting it or setting `NO_ADDITIONAL_ROOTS` breaks outbound agent calls to `*.googleapis.com` (Vertex AI Gemini, Cloud Logging, Telemetry).
2. **Manual PEM rotation:** Secret Manager automated PEM rotation is not supported on `TrustConfig`; certificates must be updated manually.
3. **Immutable connectivity templates:** `trustConfig` and `networkAttachment` cannot be edited in place once bound—changing `tlsConfig`, `dnsPeeringConfig`, or `vpcEgress` requires creating a new `AgentConnectivityTemplate` and updating the gateway reference ([`#updating-egress-settings`](https://docs.cloud.google.com/gemini-enterprise-agent-platform/govern/gateways/set-up-vpc-connectivity#updating-egress-settings)).

<details>
<summary>Official TrustConfig TLS Behavior Excerpt</summary>
<div markdown="1">

> *"Private CAs and self-signed certificates: If your target destination (agents, tools, or MCP servers in your VPC network) uses a private CA or internal PKI, you can configure custom trust anchors using the tlsConfig setting in your connectivity template. By referencing a Certificate Manager TrustConfig resource, you can configure Agent Gateway to trust only specific private CAs, or combine private root CAs with publicly trusted CAs (PUBLICLY_TRUSTED_ROOTS)... If your agents connect to Google Cloud APIs (*.googleapis.com) or other public HTTPS endpoints, you must set additionalRoots to PUBLICLY_TRUSTED_ROOTS; without this setting, Agent Gateway doesn't trust Google-signed certificates for googleapis.com."*
> ([Set up Agent Gateway with VPC connectivity](https://docs.cloud.google.com/gemini-enterprise-agent-platform/govern/gateways/set-up-vpc-connectivity#tls-certificate-requirements))

</div>
</details>

---

## 3. Cryptographic Agent Identity (`SPIFFE`, `mTLS`, `DPoP`) & Auth Manager

Traditionally on Google Cloud, multiple workloads share a coarse Service Account whose credentials can be mis-scoped across agents or stolen via downloaded keys. Google Cloud solves this with **Agent Identity**, which gives each deployed agent its own un-impersonatable cryptographic workload identity built on **SPIFFE** (*Secure Production Identity Framework for Everyone* — the CNCF X.509 workload identity standard used across modern service meshes) ([Agent Identity overview](https://docs.cloud.google.com/gemini-enterprise-agent-platform/govern/agent-identity-overview)):

1. **SPIFFE ID format and creation-time requirement:** Deploying an agent in Agent Runtime, Gemini Enterprise, or Cloud Run with `identity_type="AGENT_IDENTITY"` provisions an identity formatted as:
   ```
   spiffe://agents.global.org-<ORG_ID>.system.id.goog/resources/<SERVICE_NAME>/<RESOURCE_PATH>
   ```
   In IAM policies, reference it as `principal://agents.global.org-<ORG_ID>.system.id.goog/resources/<SERVICE>/<PATH>` (or project-wide via `principalSet://agents.global.org-<ORG_ID>.system.id.goog/cloudresourcemanager.googleapis.com/projects/<PROJECT_NUMBER>`). Because `identity_type="AGENT_IDENTITY"` **must be set when the agent is created**, existing Service-Account-based Reasoning Engines cannot be retrofitted.
2. **Auto-rotated 24-hour certificates (no static keys):** Backed by Google-managed X.509 certificates with a 24-hour validity period rotated automatically. There are no user-managed keys to download, store, or leak, and users cannot impersonate an Agent Identity from a workstation.
3. **Two-hop cryptographic verification (`mTLS` + `DPoP`):** The agent authenticates to Agent Gateway using mutual TLS (`mTLS`) with its SPIFFE X.509 certificate. From Agent Gateway onward, calls use **Demonstrating Proof of Possession (`DPoP`)** via Context-Aware Access so downstream destinations confirm the token is bound to that agent *(targets that reject certificate-bound tokens can opt out via [`auth-agent-own-identity#opt-out-caa`](https://docs.cloud.google.com/iam/docs/auth-agent-own-identity#opt-out-caa))*.
4. **Agent Identity Auth Manager (zero-trust token decryption):** Manages user-delegated 3-legged OAuth (3LO) alongside agent-owned credentials (2LO, API keys, HTTP basic auth) ([`agent-identity-overview#agent-auth-manager`](https://docs.cloud.google.com/gemini-enterprise-agent-platform/govern/agent-identity-overview#agent-auth-manager)):
   > *"When used with Agent Gateway and Gemini Enterprise, end-user credentials are encrypted by auth manager and decrypted at the gateway, so the agent never handles raw credentials."*

---

## 4. IAM Unified Access Policies

Agent Gateway's outbound allow/deny engine builds on **IAM v3 Unified Access Policies** backed by Google Cloud's **Identity-Aware Proxy (`iap.googleapis.com`) v2** policy engine—which is why its outbound permission carries the `egressViaIAP` name ([IAM Unified Access Policies overview](https://docs.cloud.google.com/gemini-enterprise-agent-platform/govern/policies/iam-overview-uap), [Create IAM Unified Access Policies](https://docs.cloud.google.com/gemini-enterprise-agent-platform/govern/policies/configure-iam-policies-uap)):

* Evaluates permission `iap.googleapis.com/resources.egressViaIAP` via predefined role **`roles/iap.egressor`**, requiring `metadata.iapPolicyVersion: "V2"` on the `iap.googleapis.com` `authzExtension` ([`delegate-authorization#combine-iap-ma`](https://docs.cloud.google.com/gemini-enterprise-agent-platform/govern/gateways/delegate-authorization#combine-iap-ma)).
* Supports `"Effect": "ALLOW"` and `"Effect": "DENY"` inside the same policy alongside **`iamEnforcementMode: "DRY_RUN"`** so teams can audit real outbound agent dependencies in Cloud Audit Logs before switching to `ENFORCE`.
* For GCP organizations created after March 4, 2026, disable `constraints/iam.managed.disableAccessPolicyBindings` before binding Unified Access Policies.

<details>
<summary>CEL Attribute Reference (Registered Agent Registry vs. Unregistered Endpoints)</summary>
<div markdown="1">

* **Registered Resources (in `Agent Registry`):** Write CEL conditions against canonical metadata without hardcoding IPs or URLs:
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

Agent Gateway pairs **Network Security Authorization Policies (`networksecurity.authzPolicies`)** with **Service Extensions (`networkservices.authzExtensions`)** over Envoy `ext_proc` (`FULL_DUPLEX_STREAMED`) across two hooks ([Delegate authorization with Service Extensions](https://docs.cloud.google.com/gemini-enterprise-agent-platform/govern/gateways/delegate-authorization)):

* **`REQUEST_AUTHZ` (header and MCP method matching):** Inspects HTTP headers and `httpRules.to.operations.mcp` (`methods: ["tools/call"]`, `params.exact: "bigquery_query"`). Include `baseProtocolMethodsOption: MATCH_BASE_PROTOCOL_METHODS` on `ALLOW` rules so base MCP control calls (`initialize`, `ping`, `notifications`) succeed.
* **`CONTENT_AUTHZ` (deep payload and prompt inspection):** Streams request and response payloads to Model Armor, the Semantic Governance Policy Engine, `Apigee Extension Processor` ([Inline Extension Processor Topology](agent-gateway-comparison.md#topology-3-inline-authorization-extension)), or a custom/partner `ext_proc` service.

### Semantic Governance Intent Gate & Streaming Limitations

Evaluated in **Preview**, [Semantic governance policies](https://docs.cloud.google.com/gemini-enterprise-agent-platform/govern/policies/semantic-governance-overview) run an LLM at the gateway to judge whether an agent's next proposed tool call genuinely aligns with the user's request and complies with plain-English business rules:

> *"Semantic governance policies use a large language model (LLM) to evaluate agent traffic against natural language rules at runtime... Semantic governance acts as an intent gate. It evaluates whether the proposed action aligns with the user's original prompt and complies with the defined natural language constraints."*

The engine evaluates **five runtime inputs**: the current user prompt, Natural Language Constraints (`NLC`), the tools manifest, chat history, and the suggested tool invocation. It supports **Gemini (`:generateContent`)**, **Anthropic Messages API (`/v1/messages`)**, **Claude on GEAP (`:rawPredict`)**, **OpenAI Chat Completions**, **Mistral AI**, **GEAP OpenAI-compatible endpoints (including Llama)**, and **self-hosted vLLM** ([supported model families](https://docs.cloud.google.com/gemini-enterprise-agent-platform/govern/policies/semantic-governance-overview#supported-providers)), with Preview VPC-SC support ([September 25, 2026 release notes](https://docs.cloud.google.com/gemini-enterprise-agent-platform/release-notes#September_25_2026)). User-intent alignment checking can also be toggled (`sgpUserIntentMatching: DISABLED`, logged in `sgpUserIntentMatchingMode`, October 26, 2026) when only static NLC business rules are needed.

Keep two operational caveats in mind:
1. **Streaming model calls are not evaluated:** Endpoints using `:streamGenerateContent`, `:streamRawPredict`, or `"stream": true` bypass Semantic Governance; pair non-streaming calls or deterministic controls where tool-call gating is mandatory.
2. **Default denial messages quote business rules:** Customize `agentResponseCustomization.denialMessage` (up to `1,000` characters) so default denials do not expose internal policy thresholds (such as exact dollar limits) back to callers.

### Model Armor Payload & Token Boundaries

Documented in [`configure-model-armor#supported-unsupported-payloads`](https://docs.cloud.google.com/gemini-enterprise-agent-platform/govern/configure-model-armor#supported-unsupported-payloads):

* **Ingress (`Client-to-Agent`):** Sanitizes `reasoningEngines.streamQuery` for **ADK agents only**. `asyncQuery` and non-ADK frameworks pass through unsanitized.
* **Egress (`Agent-to-Anywhere`):** Sanitizes **non-streaming** OpenAI API calls, non-streaming MCP `tools/call` / `prompts/get` / tool error responses, and A2A v1 `SendMessage` calls. It passes through MCP `tools/list`, `resources/*`, MCP Streamable HTTP / SSE streams, A2A `SendStreamingMessage`, and A2A gRPC without inspection.
* **Unary token limits (`EXECUTION_SKIPPED`):** Payloads over **`65,536` tokens** for prompt-injection/jailbreak/RAI/CSAM (`130,000` tokens for SDP; `4 MB` max payload) return `EXECUTION_SKIPPED` and pass through. Direct Vertex AI `generateContent` Model Armor floor settings also fail open on internal errors and block rather than inline-redacting SDP matches ([`model-armor-vertex-integration#limitations`](https://docs.cloud.google.com/model-armor/model-armor-vertex-integration#limitations)).

---

## 6. Scope Boundaries & Operational Limits

From [Agent Gateway overview](https://docs.cloud.google.com/gemini-enterprise-agent-platform/govern/gateways/agent-gateway-overview#limitations), [Set up VPC connectivity](https://docs.cloud.google.com/gemini-enterprise-agent-platform/govern/gateways/set-up-vpc-connectivity#vpc-sc-compliance), and [Route Agent Runtime traffic](https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/runtime/agent-gateway-runtime-deploy#restrict-ae):

* **No REST-to-MCP translation, API Products, or per-tool rate limits:** Agent Gateway is a passthrough proxy; it does not translate OpenAPI specs into MCP, filter `tools/list` JSON arrays per consumer tier, or enforce token/tool quotas.
* **Default-deny startup (`HTTP 498`) & exact hostname registration:** Because 100% of outbound runtime traffic routes through the gateway, an empty IAM Unified Access Policy blocks `logging.googleapis.com`, `monitoring.googleapis.com`, `telemetry.googleapis.com`, `storage.googleapis.com`, and `aiplatform.googleapis.com` with `HTTP 498`. Agent Registry does **not** match `*.googleapis.com` wildcards—register exact standard, `.mtls.`, and `.rep.` endpoints (or start IAP in `DRY_RUN` mode; [`register-endpoints#google-apis-endpoint`](https://docs.cloud.google.com/agent-registry/register-endpoints#google-apis-endpoint)).
* **VPC-SC cutoff & prerequisites:** Enforced only for gateways created after **September 8, 2026** configured with `vpcEgress: ALL_TRAFFIC`, private DNS mapping `googleapis.com.` to `restricted.googleapis.com` (`199.36.153.4/30`), and Shared VPC host/DNS projects inside the same perimeter.
* **Agent Runtime binding & lifecycle constraints:** Cannot attach to Reasoning Engines created before **April 29, 2026** or lacking `identity_type="AGENT_IDENTITY"`. All Agent Runtime engines in a single project and region must share the same ingress/egress Agent Gateways, updating a gateway binding irreversibly archives prior revisions (allowed only when 100% traffic serves the latest revision), and enabling Agent Gateway disables Security Command Center *Agent Engine Threat Detection*.
* **Gemini Enterprise regional registry rule:** Binds to one regional Agent Registry (`us-central1` for `global`/`us`; `europe-west1` for `eu`) with no `Client-to-Agent` ingress.
* **Scale, policy, and network quotas:** Maximum **5,000 registered resources** per gateway; maximum **4 `authzPolicies`** on egress (execution order across same-profile policies is not guaranteed); maximum **1 `CONTENT_AUTHZ` policy** on ingress; **`1,500`-byte MTU** on PSC attachments; custom FQDN `authzExtensions` connect over TLS `:443` without validating server certificates (keep custom extensions inside private VPCs).

---

## 7. Official Agent Gateway Documentation References

1. [Agent Gateway overview (`#governed-access-paths`, `#deployment-models`, `#limitations`)](https://docs.cloud.google.com/gemini-enterprise-agent-platform/govern/gateways/agent-gateway-overview)
2. [Set up Agent Gateway (`#choose-mode`, `#choose-runtime-region`, `#route-traffic`)](https://docs.cloud.google.com/gemini-enterprise-agent-platform/govern/gateways/set-up-agent-gateway)
3. [Set up Agent Gateway with VPC connectivity (`#vpc-egress-modes`, `#tls-certificate-requirements`, `#set-up-tls-trust-config`, `#vpc-sc-compliance`)](https://docs.cloud.google.com/gemini-enterprise-agent-platform/govern/gateways/set-up-vpc-connectivity)
4. [Route Agent Runtime traffic through Agent Gateway (`#essential_platform_endpoints`, `#configure-byoc`, `#restrict-ae`)](https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/runtime/agent-gateway-runtime-deploy)
5. [Delegate authorization with Service Extensions (`#combine-iap-ma`, `#mcp-attributes`, `#limitations`)](https://docs.cloud.google.com/gemini-enterprise-agent-platform/govern/gateways/delegate-authorization)
6. [Agent Gateway ISV partners (15 security & identity partners)](https://docs.cloud.google.com/gemini-enterprise-agent-platform/govern/gateways/agw-partners)
7. [Agent Identity overview (`#spiffe-identity`, `#agent-auth-manager`)](https://docs.cloud.google.com/gemini-enterprise-agent-platform/govern/agent-identity-overview) · [Authenticate using an agent's own identity (`#opt-out-caa`)](https://docs.cloud.google.com/iam/docs/auth-agent-own-identity) · [Agent Identity locations](https://docs.cloud.google.com/iam/docs/agent-identity-locations)
8. [Agent Registry overview](https://docs.cloud.google.com/gemini-enterprise-agent-platform/govern/agent-registry) · [Register endpoints (`#google-apis-endpoint`)](https://docs.cloud.google.com/agent-registry/register-endpoints)
9. [IAM Unified Access Policies overview (`#cel-attributes`)](https://docs.cloud.google.com/gemini-enterprise-agent-platform/govern/policies/iam-overview-uap) · [Create IAM Unified Access Policies](https://docs.cloud.google.com/gemini-enterprise-agent-platform/govern/policies/configure-iam-policies-uap)
10. [Semantic governance policies overview (`#supported-providers`, `#natural-language-constraints-nlc`)](https://docs.cloud.google.com/gemini-enterprise-agent-platform/govern/policies/semantic-governance-overview)
11. [Configure Model Armor on a gateway (`#supported-unsupported-payloads`, `#quotas-limits`)](https://docs.cloud.google.com/gemini-enterprise-agent-platform/govern/configure-model-armor) · [Integrate Model Armor with GEAP (`#configure-floor-settings`, `#limitations`)](https://docs.cloud.google.com/model-armor/model-armor-vertex-integration)
12. [Service Extensions callouts overview (`#limitations_with_body_processing`)](https://docs.cloud.google.com/service-extensions/docs/callouts-overview) · [Gemini Enterprise Agent Platform release notes](https://docs.cloud.google.com/gemini-enterprise-agent-platform/release-notes)

---

[← Back to Compare & Combine Guide](agent-gateway-comparison.md) · [Apigee AI Gateway Home ->](README.md)
