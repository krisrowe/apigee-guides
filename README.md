# Architecture & Security Guides for Apigee & Enterprise AI Gateways

Independent technical deep dives, architectural comparisons, and runnable open-source reference implementations covering **Apigee X**, **Apigee Hybrid**, **Model Context Protocol (MCP)** mediation, and **Enterprise AI Gateways**.

---

## Featured AI & Agentic Gateway Architecture

### Gemini Enterprise Agent Gateway vs. Apigee as an AI & MCP Gateway

**[Read the full architectural analysis ->](ai-gateway-vs-agent-gateway.md)**

An evidence-backed architectural comparison between **Gemini Enterprise Agent Platform: Agent Gateway** and **Apigee (`Apigee X` and `Apigee Hybrid`)** across AI-related workloads, validated against official documentation and release notes:

- **Agent-Side Perimeter vs. Producer-Side & Multi-LLM Mediation:** How `SPIFFE` workload identity, IAM Unified Access Policies (`egressViaIAP`), Auth Manager 3LO encryption, and Semantic Governance pair with Apigee API Products, `<ParsePayload>`, and Managed MCP Discovery Proxies
- **Enterprise Multi-LLM & Multimodal Gateway Patterns:** Provisioned Throughput (`PT`) to PayGo spillover, multi-provider routing and schema normalization, `<SemanticCacheLookup>`, `<LLMTokenQuota>`, Cloud DLP tokenization, and continuous SSE Model Armor scanning
- **Inbound, Outbound & Cross-Cloud MCP / A2A Topologies:** REST-to-MCP conversion, third-party SaaS MCP egress mediation (`RFC 8693` / `RFC 9728`), Search-then-Invoke semantic tool discovery, and the three documented dual-gateway integration topologies (`Private PSC Bridge`, `North-South Fronting`, and inline `Apigee Extension Processor`)
- **Requirements Quick Selector (`R1` to `R13`):** Side-by-side decision matrix mapping enterprise requirements to each gateway (and when to combine both)

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
