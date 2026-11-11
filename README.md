# Architecture & Security Guides for Apigee & Enterprise AI Gateways

Independent technical deep dives, architectural comparisons, and runnable open-source reference implementations covering **Apigee X**, **Apigee Hybrid**, **Model Context Protocol (MCP)** mediation, and **Enterprise AI Gateways**.

---

## Featured AI & Agentic Gateway Architecture

### Apigee as an Enterprise AI, LLM, MCP & Agentic Gateway

**[Read the Apigee AI Gateway Guide ->](ai-gateway/)** · **[Compare & Combine with Agent Gateway (`R1`–`R13`) ->](ai-gateway/agent-gateway-comparison.md)**

An evidence-backed architectural guide to **Apigee (`Apigee X` and `Apigee Hybrid`) as an Enterprise AI Gateway**, paired with a complete comparison and integration guide for **Gemini Enterprise Agent Platform: Agent Gateway**, validated against official documentation and release notes:

- **[Apigee AI, LLM, MCP & A2A Gateway (`ai-gateway/`)](ai-gateway/):** Multi-LLM routing & Provisioned Throughput (`PT`) to PayGo spillover (`LiteLLM` replacement), `<SemanticCacheLookup>`, `<LLMTokenQuota>`, Cloud DLP `FPE`, continuous SSE Model Armor, Managed MCP Discovery Proxy (`1.17.0+`), `<ParsePayload>` `tools/list` filtering & per-tool `<Quota>`, outbound 3P SaaS MCP egress (`RFC 8693` / `RFC 9728` / KVM), Search-then-Invoke discovery, `A2A` mediation, and Hybrid `1.17.0+` hardening
- **[Compare & Combine: Agent Gateway vs. Apigee (`agent-gateway-comparison`)](ai-gateway/agent-gateway-comparison.md):** Visual end-to-end architecture, domain matrices, `R1`–`R13` requirements selector, concrete wire scenarios (`A`–`F`), three official dual-gateway topologies (`Private PSC Bridge`, `North-South Fronting`, inline `Apigee Extension Processor`), `15` ISV security partners, FinOps attribution, and production readiness checklist
- **[Agent Gateway Architecture Deep Dive (`agent-gateway-architecture`)](ai-gateway/agent-gateway-architecture.md):** Seven GCP subsystems, `4` deployment models (`1 GA`, `3 Early Preview`), Private CA `TrustConfig`, `SPIFFE` (`mTLS` / `DPoP`) & Auth Manager 3LO encryption, IAM Unified Access Policies (`egressViaIAP`), Semantic Governance intent gate, Model Armor payload limits, and scope quotas

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
