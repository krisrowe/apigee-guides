# Agent Gateway Architecture Deep Dive (`Gemini Enterprise Agent Platform`)

<div class="subnav">
  <a href="README.md">Apigee AI Gateway</a>
  <a href="agent-gateway-comparison.md">Compare &amp; Combine: Agent Gateway</a>
  <span class="current">Agent Gateway Deep Dive</span>
</div>

> **Deep-Dive Scope (`Last Verified: November 6, 2026`):** Covers the internal architecture, seven GCP subsystems, deployment models (`1 GA` vs. `3 Early Preview`), `TrustConfig` private CA handling, `SPIFFE` (`mTLS` + `DPoP`), IAM Unified Access Policies, Service Extensions (`Semantic Governance` + `Model Armor`), and operational limits of **Gemini Enterprise Agent Platform: Agent Gateway**.

<div class="toc-box" markdown="1">

**On This Page (Jump to Section)**

* [1. What Agent Gateway Is Under the Hood](#1-what-agent-gateway-is-under-the-hood)
* [2. Traffic Topologies, Deployment Models & Private CA Connectivity](#2-traffic-topologies-deployment-models--private-ca-connectivity)
  * [`AGENT_TO_ANYWHERE` (Outbound Egress)](#1-agent_to_anywhere-outbound--egress-governance) · [`CLIENT_TO_AGENT` (Inbound Ingress)](#2-client_to_agent-inbound--ingress-governance)
  * [Deployment Models: 1 GA vs. 3 Early Preview](#3-official-agent-gateway-deployment-models-1-ga-vs-3-early-preview-verified--caveat)
  * [Private CAs & Self-Signed Certificates (`TrustConfig`)](#private-cas--self-signed-certificates-via-trustconfig-verified-correction)
* [3. Cryptographic Agent Identity (`SPIFFE`, `mTLS`, `DPoP`) & Auth Manager](#3-cryptographic-agent-identity-spiffe-mtls-dpop--auth-manager)
* [4. IAM Unified Access Policies (`egressViaIAP`)](#4-iam-unified-access-policies-egressviaiap)
* [5. Service Extensions, Model Armor & Semantic Governance](#5-service-extensions-model-armor--semantic-governance)
* [6. Scope Boundaries & Operational Considerations](#6-scope-boundaries--operational-considerations)
* [7. Verified Official Agent Gateway Documentation References](#7-verified-official-agent-gateway-documentation-references)

</div>

---

## 1. What Agent Gateway Is Under the Hood

According to the [Agent Gateway overview](https://docs.cloud.google.com/gemini-enterprise-agent-platform/govern/gateways/agent-gateway-overview#core-governance-components), [Set up Agent Gateway](https://docs.cloud.google.com/gemini-enterprise-agent-platform/govern/gateways/set-up-agent-gateway), and [Set up Agent Gateway with VPC connectivity](https://docs.cloud.google.com/gemini-enterprise-agent-platform/govern/gateways/set-up-vpc-connectivity#how-it-works), Agent Gateway is a network and security proxy provisioned via the **Network Services API** (`networkservices.googleapis.com/v1alpha1` / `v1`) that attaches directly to an agent runtime via a **Compute Engine Private Service Connect (PSC) Network Attachment** (`compute.googleapis.com`) and an **`AgentConnectivityTemplate`** (`networkservices.agentConnectivityTemplates`).

> *"Agent Gateway is a managed proxy service that provides a centralized enforcement point to help secure, govern, and monitor all network traffic for your AI agents. It mediates connections to and from agents deployed in Agent Runtime and Gemini Enterprise, helping to ensure that interactions with users, other agents, and external tools adhere to your organization's security standards."*
> ([Agent Gateway overview](https://docs.cloud.google.com/gemini-enterprise-agent-platform/govern/gateways/agent-gateway-overview))

<details>
<summary>⚙️ Seven Collaborating Google Cloud Subsystems (Click to expand)</summary>
<div markdown="1">

1. **Compute Engine Network Attachment (`compute.networkAttachments`):** Placed in a dedicated subnet (`connection-preference=ACCEPT_AUTOMATIC`, minimum `/28` CIDR) in the same region as your agent. It bridges the Google-managed agent runtime VPC to your consumer VPC and the Agent Gateway data plane.
2. **Agent Connectivity Template (`networkservices.agentConnectivityTemplates`):** Encapsulates VPC egress mode (`PRIVATE_RANGES_ONLY` default vs. `ALL_TRAFFIC` for VPC-SC or Cloud NAT static egress), Cloud DNS peering domains (`dnsPeeringConfig`, without chained DNS peering), and custom private CA trust anchors (`tlsConfig.trustConfig` referencing Certificate Manager `TrustConfig`).
3. **Network Services Agent Gateway (`networkservices.agentGateways`):** The Envoy-based proxy instance configured with `"protocols": ["MCP"]`, a `googleManaged.governedAccessPath` (`AGENT_TO_ANYWHERE` or `CLIENT_TO_AGENT`), and an optional `networkConfig.egress` reference.
4. **Agent Identity (`spiffe://...`):** Cryptographic workload identity automatically provisioned at creation time (`identity_type="AGENT_IDENTITY"`) for agents in `Agent Runtime`, `Gemini Enterprise`, and `Cloud Run`.
5. **Agent Registry (`agentregistry.googleapis.com`):** A central inventory of agents (`AGENT`), MCP servers (`MCP_SERVER`), skills (`SKILL`), and endpoints (`ENDPOINT`) linked to the gateway via `"registries"`.
6. **IAM Unified Access Policies (`iam.googleapis.com` v3 + `iap.googleapis.com`):** Evaluates identity-and-destination CEL policies (`iap.googleapis.com/resources.egressViaIAP`, role `roles/iap.egressor`, with mandatory `iapPolicyVersion: "V2"` on the `iap.googleapis.com` extension) on every outbound call.
7. **Network Security Authorization Policies & Service Extensions (`networksecurity.authzPolicies` + `networkservices.authzExtensions`):** Hooks into the Envoy data plane (`ext_proc` in `FULL_DUPLEX_STREAMED` mode) for `REQUEST_AUTHZ` and `CONTENT_AUTHZ` (delegating to **Model Armor**, the **Semantic Governance Policy Engine**, **Apigee Extension Processor**, or **15 named ISV security partners**).

</div>
</details>

---

## 2. Traffic Topologies, Deployment Models & Private CA Connectivity

Agent Gateway operates in two mutually exclusive governance modes per gateway instance (`governedAccessPath`):

#### 1. `AGENT_TO_ANYWHERE` (Outbound / Egress Governance)
* **How it works:** Acts as an **outbound forward proxy** for an agent. **100% of outbound traffic** the agent makes (calling an MCP server via `tools/list` or `tools/call`, invoking a sub-agent over `A2A`, calling an LLM API, or reaching Google Cloud telemetry/storage APIs) traverses the Agent Gateway.
* **Supported Runtimes (GA):**
  * **Vertex AI Agent Runtime (`aiplatform.googleapis.com` Reasoning Engine):** Bound during deployment via `"pscInterfaceConfig"` and `"agentGatewayConfig": {"agentToAnywhereConfig": {"agentGateway": "..."}}`. Supports cross-project governance (an agent in Project A can use an `Agent-to-Anywhere` gateway in Project B as long as both are in the **same region**; configured via REST/gcloud using a Google security group with `roles/networkservices.viewer` to scale across service projects).
  * **Gemini Enterprise (`discoveryengine.googleapis.com`):** Bound at the engine level by patching `features.agent-Session-agent-gateway` and setting `agentGatewaySetting.defaultEgressAgentGateway`.
* **Routing Destinations & VPC Egress Modes ([`set-up-vpc-connectivity#vpc-egress-modes`](https://docs.cloud.google.com/gemini-enterprise-agent-platform/govern/gateways/set-up-vpc-connectivity#vpc-egress-modes)):**
  * `PRIVATE_RANGES_ONLY` (Default): Routes RFC 1918 / privately used public IPs and peered Cloud DNS private zones into your VPC while sending public internet traffic directly via Google's edge.
  * `ALL_TRAFFIC`: Forces **all** outbound agent traffic (both private and public, including `restricted.googleapis.com` at `199.36.153.4/30`) into your VPC, enabling customer Cloud NAT static IP allowlisting, Cloud NGFW inspection, and **VPC Service Controls (VPC-SC)** compliance.

#### 2. `CLIENT_TO_AGENT` (Inbound / Ingress Governance)
* **How it works:** Acts as an **inbound reverse proxy** in front of an agent deployed in `Agent Runtime` (`query` and `streamQuery` methods only; `asyncQuery` is unsupported), protecting the agent from external callers and applying inbound `CONTENT_AUTHZ`.
* **Supported Runtimes:** **Vertex AI Agent Runtime ONLY** (same project and same region as the Agent Gateway).
* **Explicitly Unsupported on Gemini Enterprise:** As stated in [Set up Agent Gateway](https://docs.cloud.google.com/gemini-enterprise-agent-platform/govern/gateways/set-up-agent-gateway#choose-runtime-region):
  > *"For Gemini Enterprise: Client-to-Agent mode is not supported."*

#### 3. Official Agent Gateway Deployment Models: 1 GA vs. 3 Early Preview (`[VERIFIED]` + `[CAVEAT]`)
As documented in [Agent Gateway overview: Deployment models](https://docs.cloud.google.com/gemini-enterprise-agent-platform/govern/gateways/agent-gateway-overview#deployment-models), Google Cloud now defines **four deployment models** under a unified control plane (**only Google-Managed is GA today**):

| Deployment Model | Launch Stage | Underlying Data Plane Mechanics | Supported Access Paths |
| :--- | :--- | :--- | :--- |
| **1. Google-Managed Agent Gateway** ([`#managed-agw`](https://docs.cloud.google.com/gemini-enterprise-agent-platform/govern/gateways/agent-gateway-overview#managed-agw)) | **GA** | Google-managed Envoy proxy attached via PSC Network Attachment in Google Cloud. | `Agent Runtime`: Ingress + Egress<br>`Gemini Enterprise`: Egress ONLY |
| **2. Self-Managed on GKE** ([`#gke-agw`](https://docs.cloud.google.com/gemini-enterprise-agent-platform/govern/gateways/agent-gateway-overview#gke-agw)) | **Early Preview** *("Coming soon")* | **Ingress:** GKE Gateway API (Regional Application Load Balancer).<br>**Egress:** GKE ambient networking (sidecar-less) routing pod egress to a customer-managed **Secure Web Proxy (`SWP`)**, plus L7 per-namespace ambient proxies for pod-to-pod A2A/MCP calls. | `Client-to-Agent` + `Agent-to-Anywhere` |
| **3. Self-Managed on Cloud Run** ([`#cloud-run-agw`](https://docs.cloud.google.com/gemini-enterprise-agent-platform/govern/gateways/agent-gateway-overview#cloud-run-agw)) | **Early Preview** *("Coming soon")* | **Ingress:** Regional External or Internal Application Load Balancer (`RXLB` / `RILB`).<br>**Egress:** Cloud Run ambient networking over Direct VPC egress mTLS tunnel to a customer-managed **Secure Web Proxy (`SWP`)**. | `Client-to-Agent` + `Agent-to-Anywhere` |
| **4. Agent Gateway for Cross-Cloud** ([`#cross-cloud-agw`](https://docs.cloud.google.com/gemini-enterprise-agent-platform/govern/gateways/agent-gateway-overview#cross-cloud-agw)) | **Early Preview** *("Coming soon")* | Customer-deployed lightweight Envoy-based Agent Gateway running inside **Amazon EKS, Azure AKS, OpenShift, or on-premises Kubernetes**. Data plane traffic stays local while control plane (WIF -> Agent Identity, Agent Registry, Model Armor callouts, observability) connects to Google Cloud. | `Client-to-Agent` + `Agent-to-Anywhere` |

#### Private CAs & Self-Signed Certificates via `TrustConfig` (`[VERIFIED]` Correction)
Earlier Agent Gateway releases required publicly trusted CAs for all destinations. Per [Set up Agent Gateway with VPC connectivity: TLS certificate requirements](https://docs.cloud.google.com/gemini-enterprise-agent-platform/govern/gateways/set-up-vpc-connectivity#tls-certificate-requirements), Agent Gateway **now supports private CAs and allowlisted self-signed server certificates** for VPC destinations via Certificate Manager `TrustConfig` (`tlsConfig.trustConfig`), subject to **three mandatory guardrails**:

1. **Always Set `additionalRoots: PUBLICLY_TRUSTED_ROOTS`:** Omitting or setting `NO_ADDITIONAL_ROOTS` breaks outbound agent calls to `*.googleapis.com` (Vertex AI Gemini, Cloud Logging, Telemetry).
2. **Manual PEM Rotation Only:** Automated PEM rotation via Google Cloud Secret Manager is unsupported on `TrustConfig`; certificates must be rotated manually.
3. **Immutability Requires Template Replacement:** `trustConfig` and `networkAttachment` are **immutable** once attached. Updating `tlsConfig`, `dnsPeeringConfig`, or `vpcEgress` requires creating a **new** `AgentConnectivityTemplate` and updating the gateway reference ([`#updating-egress-settings`](https://docs.cloud.google.com/gemini-enterprise-agent-platform/govern/gateways/set-up-vpc-connectivity#updating-egress-settings)).

<details>
<summary>📜 Official <code>TrustConfig</code> TLS Behavior Quote (Click to expand)</summary>
<div markdown="1">

> *"Private CAs and self-signed certificates: If your target destination (agents, tools, or MCP servers in your VPC network) uses a private CA or internal PKI, you can configure custom trust anchors using the tlsConfig setting in your connectivity template. By referencing a Certificate Manager TrustConfig resource, you can configure Agent Gateway to trust only specific private CAs, or combine private root CAs with publicly trusted CAs (PUBLICLY_TRUSTED_ROOTS)... If your agents connect to Google Cloud APIs (*.googleapis.com) or other public HTTPS endpoints, you must set additionalRoots to PUBLICLY_TRUSTED_ROOTS; without this setting, Agent Gateway doesn't trust Google-signed certificates for googleapis.com."*
> ([Set up Agent Gateway with VPC connectivity](https://docs.cloud.google.com/gemini-enterprise-agent-platform/govern/gateways/set-up-vpc-connectivity#tls-certificate-requirements))

</div>
</details>

---

## 3. Cryptographic Agent Identity (`SPIFFE`, `mTLS`, `DPoP`) & Auth Manager

One of the clearest differentiators of the Gemini Enterprise Agent Platform is **Agent Identity** ([Agent Identity overview](https://docs.cloud.google.com/gemini-enterprise-agent-platform/govern/agent-identity-overview)):

1. **SPIFFE ID Structure & Creation-Time Requirement:**
   When you deploy an agent in `Agent Runtime`, `Gemini Enterprise`, or `Cloud Run` with `identity_type="AGENT_IDENTITY"`, Google Cloud provisions a cryptographic workload identity:
   ```
   spiffe://agents.global.org-<ORG_ID>.system.id.goog/resources/<SERVICE_NAME>/<RESOURCE_PATH>
   ```
   *(In IAM policies, referenced as `principal://agents.global.org-<ORG_ID>.system.id.goog/resources/<SERVICE>/<PATH>` or across a project via `principalSet://agents.global.org-<ORG_ID>.system.id.goog/cloudresourcemanager.googleapis.com/projects/<PROJECT_NUMBER>`. `identity_type="AGENT_IDENTITY"` **must be set at agent creation time**; existing service-account Reasoning Engines cannot be retrofitted).*
2. **Lifecycle & Zero-Key Security:**
   * Backed by Google-managed X.509 certificates with a **24-hour validity period** rotated automatically.
   * **No user-managed keys** to download, store, or leak; users cannot impersonate an Agent Identity from a local laptop, preventing shared-SA confused-deputy confusion across agents.
3. **Two-Hop Cryptographic Verification (`mTLS` + `DPoP`):**
   * **Agent -> Agent Gateway (`mTLS`):** The agent authenticates using mutual TLS with its SPIFFE X.509 certificate.
   * **Agent Gateway -> Destination (`DPoP`):** Uses **Demonstrating Proof of Possession (DPoP)** via Context-Aware Access so downstream resources verify the token is cryptographically bound to the agent *(targets rejecting certificate-bound tokens can opt out via [`auth-agent-own-identity#opt-out-caa`](https://docs.cloud.google.com/iam/docs/auth-agent-own-identity#opt-out-caa))*.
4. **Agent Identity Auth Manager (Secure Outbound Token Broker):**
   * Documented in [Agent Identity overview](https://docs.cloud.google.com/gemini-enterprise-agent-platform/govern/agent-identity-overview#agent-auth-manager), managing **User-delegated 3-legged OAuth (3LO)** and **Agent's own authority** (Agent Identity, 2LO, API keys, HTTP basic auth).
   * **End-to-End Token Encryption at the Gateway:**
     > *"When used with Agent Gateway and Gemini Enterprise, end-user credentials are encrypted by auth manager and decrypted at the gateway, so the agent never handles raw credentials."*

---

## 4. IAM Unified Access Policies (`egressViaIAP`)

Documented in [IAM Unified Access Policies overview](https://docs.cloud.google.com/gemini-enterprise-agent-platform/govern/policies/iam-overview-uap) and [Create IAM Unified Access Policies](https://docs.cloud.google.com/gemini-enterprise-agent-platform/govern/policies/configure-iam-policies-uap), Agent Gateway integrates with **IAM v3 Unified Access Policies** (Identity-Aware Proxy V2) for deterministic outbound authorization:

* **Permission, Role & Mandatory Extension Metadata:** Permission `iap.googleapis.com/resources.egressViaIAP` (predefined role **`roles/iap.egressor`**). Setting `metadata.iapPolicyVersion: "V2"` on the `iap.googleapis.com` `authzExtension` is **mandatory** ([`delegate-authorization#combine-iap-ma`](https://docs.cloud.google.com/gemini-enterprise-agent-platform/govern/gateways/delegate-authorization#combine-iap-ma)).
* **Allow + Deny + Dry-Run in One Policy:** Supports `"Effect": "ALLOW"` and `"Effect": "DENY"` inside the same policy plus **`iamEnforcementMode: "DRY_RUN"`** alongside `ENFORCE` for zero-downtime discovery in Cloud Audit Logs.
* **Org Policy Prerequisite:** For organizations created after March 4, 2026, disable `constraints/iam.managed.disableAccessPolicyBindings` before binding Unified Access Policies.

<details>
<summary>🔍 CEL Attribute Reference (Registered Agent Registry vs. Unregistered Endpoints)</summary>
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
<summary>📄 Verified Example: IAM Unified Access Policy Blocking Destructive MCP Tools (JSON)</summary>
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

Documented in [Delegate authorization with Service Extensions](https://docs.cloud.google.com/gemini-enterprise-agent-platform/govern/gateways/delegate-authorization), Agent Gateway supports **Network Security Authorization Policies (`networksecurity.authzPolicies`)** paired with **Service Extensions (`networkservices.authzExtensions`)** using Envoy's `ext_proc` protocol in `FULL_DUPLEX_STREAMED` mode:

1. **`REQUEST_AUTHZ` (Header & Method Inspection):** Evaluates HTTP headers and native MCP protocol operations (`httpRules.to.operations.mcp` with `baseProtocolMethodsOption: MATCH_BASE_PROTOCOL_METHODS`, `methods: ["tools/call"]`, `params.exact: "bigquery_query"`). Always include `MATCH_BASE_PROTOCOL_METHODS` on `ALLOW` rules so base MCP RPCs (`initialize`, `ping`, `notifications`) are not blocked.
2. **`CONTENT_AUTHZ` (Deep Payload & Prompt Inspection):** Streams request and response payloads to **Model Armor**, the **Semantic Governance Policy Engine**, the **Apigee Extension Processor** ([Topology 3](agent-gateway-comparison.md#topology-3-official-inline-authorization-extension-agent-gateway---apigee-extension-processor-verified)), or a custom/3P `ext_proc` service.

### Semantic Governance "Intent Gate": Multi-Provider Coverage & Streaming Caveats (`[VERIFIED]`)

Documented in [Semantic governance policies overview](https://docs.cloud.google.com/gemini-enterprise-agent-platform/govern/policies/semantic-governance-overview) and [GEAP release notes](https://docs.cloud.google.com/gemini-enterprise-agent-platform/release-notes#October_26_2026):
> *"Semantic governance policies use a large language model (LLM) to evaluate agent traffic against natural language rules at runtime... Semantic governance acts as an intent gate. It evaluates whether the proposed action aligns with the user's original prompt and complies with the defined natural language constraints."*

Inspects **five runtime inputs**: (1) **Current User Prompt**, (2) **Natural Language Constraints (NLC)** (e.g., *"Accept refund requests only where the amount is `$80` or less"*), (3) **Tools Manifest**, (4) **Chat History**, and (5) **Suggested Tool Invocations**, enforcing:
* **Check 1 (User Intent Alignment / Defeating Indirect Prompt Injection):** Blocks `gmail_send_email` when the user only asked *"Summarize my calendar for today"*, even if the agent holds IAM permission *(can optionally disable Check 1 while keeping NLC rules via `sgpUserIntentMatching: DISABLED` on `authzExtensions`, logged in `sgpUserIntentMatchingMode`, Oct 26, 2026)*.
* **Check 2 (Natural Language Business Compliance):** Blocks `issue_refund(amount=250)` against plain-English constraints (`$80` cap).
* **Supported Model Providers ([`#supported-providers`](https://docs.cloud.google.com/gemini-enterprise-agent-platform/govern/policies/semantic-governance-overview#supported-providers)):** **Gemini (`:generateContent`)**, **Anthropic Messages API (`/v1/messages`)**, **Claude on GEAP (`:rawPredict`)**, **OpenAI Chat Completions**, **Mistral AI**, **GEAP OpenAI-compatible endpoints (including Llama)**, and **self-hosted vLLM**.
* **VPC-SC Support:** Semantic Governance Policies **now support VPC Service Controls in Preview** ([`release-notes#September_25_2026`](https://docs.cloud.google.com/gemini-enterprise-agent-platform/release-notes#September_25_2026)).
* **Two Critical Guardrails (`[CAVEAT]`):**
  1. **Streamed Model Responses Are NOT Supported:** Calls using `:streamGenerateContent`, `:streamRawPredict`, or `"stream": true` are **not evaluated**—tool calls emitted inside streamed LLM responses bypass the intent gate unless unary calls are used.
  2. **Policy Leakage in Default Denial Rationales:** Default denials quote the violated NLC rule back to the caller (exposing thresholds like `$80`). Configure `agentResponseCustomization.denialMessage` (up to `1,000` characters, Sept 29, 2026) in production.

### Model Armor on Agent Gateway: Exact Payload & Token Boundaries

Documented in [`configure-model-armor#supported-unsupported-payloads`](https://docs.cloud.google.com/gemini-enterprise-agent-platform/govern/configure-model-armor#supported-unsupported-payloads):
* **Ingress (`Client-to-Agent`):** Sanitizes **only `reasoningEngines.streamQuery` for ADK agents**. Non-ADK frameworks (LangChain) and `asyncQuery` pass through **unsanitized**.
* **Egress (`Agent-to-Anywhere`):** Sanitizes **non-streaming** OpenAI API calls, **non-streaming** MCP `tools/call`, `prompts/get`, and tool error payloads, and A2A v1 `SendMessage` (JSON-RPC/REST). It **allows without sanitization**: MCP `tools/list`, MCP `resources/*`, **MCP Streamable HTTP / SSE streaming**, A2A `SendStreamingMessage`, and A2A gRPC protobuf.
* **Unary Token Limits (`EXECUTION_SKIPPED` Pass-Through):** Payloads exceeding **`65,536` tokens** for Prompt Injection / Jailbreak / RAI / CSAM (`130,000` tokens for SDP; `4 MB` max payload) return `EXECUTION_SKIPPED` and **pass through**. *(Direct Vertex AI `generateContent` Model Armor floor integration via [`model-armor-vertex-integration#limitations`](https://docs.cloud.google.com/model-armor/model-armor-vertex-integration#limitations) also **fails open** on internal errors and blocks rather than returning SDP redacted text).*

---

## 6. Scope Boundaries & Operational Considerations

From [Agent Gateway overview](https://docs.cloud.google.com/gemini-enterprise-agent-platform/govern/gateways/agent-gateway-overview#limitations), [Set up VPC connectivity](https://docs.cloud.google.com/gemini-enterprise-agent-platform/govern/gateways/set-up-vpc-connectivity#vpc-sc-compliance), and [Route Agent Runtime traffic](https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/runtime/agent-gateway-runtime-deploy#restrict-ae):

* **No Protocol Translation, API Products, or Per-Tool Rate Limits:** Cannot convert REST/OpenAPI backends into MCP tools, strip tools from `tools/list` JSON payloads, or enforce per-tool `<Quota>` / `<LLMTokenQuota>` budgets.
* **Default-Deny `HTTP 498` Startup Failure & Exact Hostname Matching (No Wildcards):** Because **100% of outbound traffic** routes through Agent Gateway, an empty IAM UAP blocks `logging.googleapis.com`, `monitoring.googleapis.com`, `telemetry.googleapis.com`, `storage.googleapis.com`, and `aiplatform.googleapis.com` with `HTTP 498`. Agent Registry matching is **exact** (`*.googleapis.com` wildcards unsupported): register **standard, `.mtls.`, and `.rep.` hostnames** (or start IAP in `iamEnforcementMode: "DRY_RUN"`; [`register-endpoints#google-apis-endpoint`](https://docs.cloud.google.com/agent-registry/register-endpoints#google-apis-endpoint)).
* **VPC-SC Cutoff & Requirements:** Enforces VPC-SC **only for gateways created after September 8, 2026** using `vpcEgress: ALL_TRAFFIC` + private DNS mapping `googleapis.com.` to `restricted.googleapis.com` (`199.36.153.4/30`) + Shared VPC host/DNS projects inside the same perimeter.
* **Agent Runtime Binding & Lifecycle Constraints:**
  * Cannot bind to Reasoning Engines created **before April 29, 2026**, or engines without `identity_type="AGENT_IDENTITY"`.
  * **Single Gateway Binding per Project & Region:** All `Agent Runtime` agents in one project and region must bind to the **exact same** egress/ingress Agent Gateways.
  * **Irreversible Revision Archiving:** Changing gateway bindings on an existing Reasoning Engine **irreversibly archives all prior revisions** (only allowed at 100% traffic on latest revision).
  * **SCC Threat Detection Mutual Exclusion:** Security Command Center *Agent Engine Threat Detection* is **unavailable** when Agent Gateway is enabled.
* **Gemini Enterprise Regional Registry Rule (Oct 28, 2026):** Connects to a **single regional Agent Registry** (`us-central1` for `global`/`us`; `europe-west1` for `eu`) with **no `Client-to-Agent` ingress**.
* **Scale, Policy & Network Quotas:** Max **5,000 registered resources** per gateway; max **4 `authzPolicies`** on egress (execution order across same-profile policies **not guaranteed**); max **1 `CONTENT_AUTHZ` policy** on ingress; **`1,500`-byte MTU** on PSC attachments; custom FQDN `authzExtensions` use TLS `:443` **without validating server certs** (keep custom extensions in private VPCs).

---

## 7. Verified Official Agent Gateway Documentation References

1. [Agent Gateway overview (`#governed-access-paths`, `#deployment-models`, `#limitations`)](https://docs.cloud.google.com/gemini-enterprise-agent-platform/govern/gateways/agent-gateway-overview)
2. [Set up Agent Gateway (`#choose-mode`, `#choose-runtime-region`, `#route-traffic`)](https://docs.cloud.google.com/gemini-enterprise-agent-platform/govern/gateways/set-up-agent-gateway)
3. [Set up Agent Gateway with VPC connectivity (`#vpc-egress-modes`, `#tls-certificate-requirements`, `#set-up-tls-trust-config`, `#vpc-sc-compliance`)](https://docs.cloud.google.com/gemini-enterprise-agent-platform/govern/gateways/set-up-vpc-connectivity)
4. [Route Agent Runtime traffic through Agent Gateway (`#essential_platform_endpoints`, `#configure-byoc`, `#restrict-ae`)](https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/runtime/agent-gateway-runtime-deploy)
5. [Delegate authorization with Service Extensions (`#combine-iap-ma`, `#mcp-attributes`, `#limitations`)](https://docs.cloud.google.com/gemini-enterprise-agent-platform/govern/gateways/delegate-authorization)
6. [Agent Gateway ISV partners (15 validated security & identity partners)](https://docs.cloud.google.com/gemini-enterprise-agent-platform/govern/gateways/agw-partners)
7. [Agent Identity overview (`#spiffe-identity`, `#agent-auth-manager`)](https://docs.cloud.google.com/gemini-enterprise-agent-platform/govern/agent-identity-overview) · [Authenticate using an agent's own identity (`#opt-out-caa`)](https://docs.cloud.google.com/iam/docs/auth-agent-own-identity) · [Agent Identity locations](https://docs.cloud.google.com/iam/docs/agent-identity-locations)
8. [Agent Registry overview](https://docs.cloud.google.com/gemini-enterprise-agent-platform/govern/agent-registry) · [Register endpoints (`#google-apis-endpoint`)](https://docs.cloud.google.com/agent-registry/register-endpoints)
9. [IAM Unified Access Policies overview (`#cel-attributes`)](https://docs.cloud.google.com/gemini-enterprise-agent-platform/govern/policies/iam-overview-uap) · [Create IAM Unified Access Policies](https://docs.cloud.google.com/gemini-enterprise-agent-platform/govern/policies/configure-iam-policies-uap)
10. [Semantic governance policies overview (`#supported-providers`, `#natural-language-constraints-nlc`)](https://docs.cloud.google.com/gemini-enterprise-agent-platform/govern/policies/semantic-governance-overview)
11. [Configure Model Armor on a gateway (`#supported-unsupported-payloads`, `#quotas-limits`)](https://docs.cloud.google.com/gemini-enterprise-agent-platform/govern/configure-model-armor) · [Integrate Model Armor with GEAP (`#configure-floor-settings`, `#limitations`)](https://docs.cloud.google.com/model-armor/model-armor-vertex-integration)
12. [Service Extensions callouts overview (`#limitations_with_body_processing`)](https://docs.cloud.google.com/service-extensions/docs/callouts-overview) · [Gemini Enterprise Agent Platform release notes](https://docs.cloud.google.com/gemini-enterprise-agent-platform/release-notes)

---

[← Back to Compare & Combine Guide](agent-gateway-comparison.md) · [Apigee AI Gateway Home ->](README.md)
