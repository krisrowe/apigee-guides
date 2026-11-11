# Architecture & Security Guides for Apigee & Enterprise AI Gateways

Independent technical deep dives, architectural comparisons, and runnable open-source reference implementations covering **Apigee X**, **Apigee Hybrid**, **Model Context Protocol (MCP)** mediation, and **Enterprise AI Gateways**.

---

## Featured AI & Agentic Gateway Architecture

### Apigee as an Enterprise AI, LLM, MCP & Agentic Gateway

**[Read the Apigee AI Gateway Guide ->](ai-gateway/)** · **[Compare & Combine with Agent Gateway ->](ai-gateway/agent-gateway-comparison.md)**

An architectural and implementation guide to **Apigee X** and **Apigee Hybrid** as an Enterprise AI Gateway, paired with a side-by-side comparison and integration blueprint for **Gemini Enterprise Agent Gateway**:

- **[Apigee AI, LLM, MCP & A2A Gateway](ai-gateway/):** Multi-provider LLM routing with [Provisioned Throughput spillover](ai-gateway/README.md#21-multi-provider-routing-pt-spillover--schema-normalization), [semantic response caching](ai-gateway/README.md#22-semantic-response-caching), [real-time token quotas](ai-gateway/README.md#23-real-time-token-quotas--spike-smoothing), [streaming Model Armor and Cloud DLP guardrails](ai-gateway/README.md#24-prompt-tool--streaming-sse-guardrails), [REST-to-MCP conversion](ai-gateway/README.md#pattern-1-expose-rest-apis-as-mcp-tools), [per-tool API Product filtering and rate limits](ai-gateway/README.md#4-per-tool-productization-dynamic-toolslist-filtering--quotas), [outbound SaaS MCP token mediation](ai-gateway/README.md#pattern-3-broker-outbound-access-to-third-party-saas-mcp-servers), [semantic tool discovery](ai-gateway/README.md#pattern-4-search-then-invoke-semantic-tool-discovery), [A2A mediation](ai-gateway/README.md#pattern-5-cross-cloud--in-cluster-agent-to-agent-mediation), and [Apigee Hybrid hardening](ai-gateway/README.md#5-apigee-hybrid-1170-multi-cloud-execution-limits--network-hardening)
- **[Compare & Combine: Agent Gateway vs. Apigee](ai-gateway/agent-gateway-comparison.md):** End-to-end architecture, domain comparison matrices, decision framework, real-world integration scenarios, three dual-gateway topologies ([Private PSC Bridge](ai-gateway/agent-gateway-comparison.md#topology-1-southbound-private-psc-bridge), [North-South Fronting](ai-gateway/agent-gateway-comparison.md#topology-2-north-south-external--multi-cloud-fronting), and [inline Apigee Extension Processor](ai-gateway/agent-gateway-comparison.md#topology-3-inline-authorization-extension)), security partner integrations, FinOps attribution, and production readiness checklist
- **[Agent Gateway Architecture Deep Dive](ai-gateway/agent-gateway-architecture.md):** Underlying GCP control-plane APIs, [deployment models](ai-gateway/agent-gateway-architecture.md#deployment-models-1-ga-vs-3-early-preview), [private CA `TrustConfig` setup](ai-gateway/agent-gateway-architecture.md#private-cas--self-signed-certificates-via-trustconfig), [per-agent cryptographic identity (`SPIFFE`, mTLS, DPoP) and Auth Manager](ai-gateway/agent-gateway-architecture.md#3-cryptographic-agent-identity-spiffe-mtls-dpop--auth-manager), [IAM Unified Access Policies](ai-gateway/agent-gateway-architecture.md#4-iam-unified-access-policies), [Semantic Governance and Model Armor bounds](ai-gateway/agent-gateway-architecture.md#5-service-extensions-model-armor--semantic-governance), and scale limits

---

## Platform, Security & Networking Guides

### Apigee X Encryption Architecture: Google-Managed vs. CMEK (with Cloud HSM)

**[Read the full guide ->](encryption_hsm_vs_cmek.md)**

Technical overview of data-at-rest encryption models in Apigee X for regulated workloads, comparing Google-managed keys, Customer-Managed Encryption Keys (CMEK), and Cloud HSM hardware protection levels across runtime and control-plane storage layers.

### Troubleshooting Apigee Southbound 503 Errors & Private DNS Peering

**[Read the full guide ->](southbound-ssl-dns-peering.md)**

Step-by-step root-cause analysis and resolution guide for TLS SAN / SNI hostname verification mismatches (`503 Service Unavailable`) when connecting Apigee southbound over Private Service Connect (PSC) or Endpoint Attachments with Cloud DNS private zones.

### Apigee Edge vs X & Hybrid Comparison Guide

**[Read the full guide ->](edge-vs-x-hybrid.md)**

This guide helps organizations understand the advantages of upgrading from Apigee Edge to modern Apigee X and Hybrid platforms. It covers:

- Operational efficiency improvements
- Security enhancements
- Developer velocity and modernization features
- Platform comparison and upgrade considerations

### JWT-Based App Identification Guide

**[Read the full guide ->](app-dev-lookup-by-jwt.md)**

This technical guide demonstrates how to use JWT claims to identify developer applications in Apigee, enabling centralized identity provider integration while leveraging Apigee's API management features. It covers:

- Direct lookup patterns using JWT claims
- Indirect lookup patterns using Key-Value Maps
- Policy configurations for VerifyAPIKey and OAuthV2
- Complete proxy flow examples

---

## Companion Open-Source Reference Implementations

| Repository | Focus Area & Capabilities |
| :--- | :--- |
| **[apigee-mcp-token-exchange](https://github.com/krisrowe/apigee-mcp-token-exchange)** | Production-grade reference architecture and runnable test harness demonstrating how an Apigee Gateway mediates access between developer AI coding assistants and external SaaS MCP servers using **IETF RFC 8693 (OAuth 2.0 Token Exchange)** and **RFC 9728 (Protected Resource Metadata Discovery)**. |
| **[enterprise-mcp-starters](https://github.com/krisrowe/enterprise-mcp-starters)** | Security-hardened **Python (`FastMCP` / Starlette)** and **TypeScript (`@modelcontextprotocol/sdk` / Express)** starter templates for deploying custom Streamable HTTP / SSE MCP servers behind enterprise API gateways on Kubernetes or Cloud Run. |
| **[apigee-tf](https://github.com/krisrowe/apigee-tf)** | State-convergent Terraform provisioning framework (`apim`) for **Apigee X**, covering Private Service Connect (PSC) networking, Data Residency (DRZ), custom domains, existing-org import recovery, and modular AI Gateway extensions. |

---

## Target Audience

- Apigee platform users and administrators
- Enterprise architects and decision makers
- API platform administrators
- Development teams working with Apigee
- Technical teams implementing API management and AI gateway solutions

## Contributing

This repository contains independent educational content and architectural guides regarding Apigee and enterprise gateway capabilities. For official product documentation, refer to the official Apigee documentation on Google Cloud.
