# Apigee X Encryption Architecture: Google-Managed vs. CMEK (with HSM)

**Technical Advisory: Data-at-Rest Encryption for Financial Institutions**

## Executive Summary
This document provides a technical overview of encryption options for Apigee X. While Google Cloud provides robust encryption by default, financial institutions typically opt for Customer-Managed Encryption Keys (CMEK) to meet regulatory mandates. Hardware Security Module (HSM) is a specific protection level within the CMEK management model that provides hardware-backed key material.

---

## 1. Encryption Management Models

Google Cloud categorizes data-at-rest encryption into two primary management models. Within the Customer-Managed model, further granularity is provided via **Protection Levels**.

### A. Google-Managed Encryption (Default)
By default, all data stored within Google Cloud is automatically encrypted at rest using keys managed by Google.
> *"By default, Google Cloud automatically encrypts data when it is at rest using encryption keys that are owned and managed by Google."*
[Introduction to CMEK (Apigee X)](https://cloud.google.com/apigee/docs/api-platform/get-started/cmek-concepts)

- **Management:** Fully automated; no configuration or lifecycle management required by the customer.

### B. Customer-Managed Encryption Keys (CMEK)
CMEK allows customers to use their own cryptographic keys, managed via Cloud KMS, to protect data in Apigee X.
> *"If you have specific compliance or regulatory requirements related to the keys that protect your data, you can use customer-managed encryption keys (CMEK)."*
[Introduction to CMEK (Apigee X)](https://cloud.google.com/apigee/docs/api-platform/get-started/cmek-concepts)

- **Mechanics:** Apigee X uses **envelope encryption**. The Customer-Managed Key (administered in Cloud KMS) acts as a Key Encryption Key (KEK) which wraps a Data Encryption Key (DEK) used by the service.
- **Formally distinct?** YES. In banking, "Software-backed CMEK" and "HSM-backed CMEK" are treated as distinct security postures.

---

## 2. Cloud HSM Protection Level

HSM is a **Protection Level** for an encryption key within the Cloud KMS service, ensuring keys are hardware-backed.

> *"Cloud HSM keys with the HSM protection level are stored in a Google-owned Hardware Security Module (HSM)... You can use Cloud HSM keys the same way you use Cloud KMS keys."*
[Cloud KMS Protection Levels](https://cloud.google.com/kms/docs/protection-levels)

- **Security Standard:** Keys are generated and used within FIPS 140-2 Level 3 compliant hardware modules.
- **Application:** For Apigee, the `runtime_database_encryption_key_name` must reference a key with `protectionLevel: HSM`.

---

## 3. Technical Mechanics: Control Plane vs. Runtime

Apigee X partitions encryption between management data (Control Plane) and traffic data (Runtime).

### Control Plane Data (Data Residency / DRZ)
When Data Residency is enforced, the regionalized control plane requires **two distinct keys**.
> *"In the regionalized Apigee control plane, you select two encryption keys for your control plane. This is because some of the components underlying the Apigee control plane are always in a single-region within the control plane location."*
[Introduction to CMEK (Apigee X)](https://cloud.google.com/apigee/docs/api-platform/get-started/cmek-concepts)

1. **Control plane encryption key:** Protects proxy bundles, environment config, and analytics signals.
2. **API consumer data encryption key:** Protects sub-regional services.

### Runtime Data (Database vs. Disk)
Runtime data encryption is multi-layered and requires strict isolation.
1. **Runtime Database Key:** One key per organization, shared across all sessions.
2. **Disk Encryption Key:** Each unique instance/region combination maintains its own key.
> *"Each instance/region combination has its own disk encryption key."*
[About the Apigee encryption keys](https://docs.cloud.google.com/apigee/docs/api-platform/security/encryption-keys)

3. **Key Ring Separation:** Google mandates that different key types reside in separate key rings.
> *"Keys of different types must be in separate key rings; disk encryption keys cannot be in the same key ring as your runtime database encryption key."*
[About the Apigee encryption keys](https://docs.cloud.google.com/apigee/docs/api-platform/security/encryption-keys)

---

## 4. HSM vs. Software CMEK: Trade-offs

| Factor | Software-backed CMEK | Cloud HSM-backed CMEK |
| :--- | :--- | :--- |
| **Protection** | Software-based (KMS default) | **Hardware-backed (FIPS 140-2 L3)** |
| **Complexity** | Low (standard KMS) | Low (identical API, requires `HSM` flag) |
| **Cost (Key/Mo)** | **$0.06** | **$1.00** |
| **Throughput (QPM)**| **~60,000 (Default)** | **~3,000 (Default)** |
| **Latency** | Low (Internal Software) | Slightly Higher (HSM Cluster Routing) |

**Notes on "Expensiveness":**
Beyond the ~16x higher monthly key fee, HSM is considered "expensive" due to its **significantly lower throughput quotas**. Software keys typically scale to 60k Queries Per Minute (QPM), whereas HSM keys default to 3k QPM. For high-volume banking workloads, this may necessitate quota increase requests or multi-key architectures.
- **Source:** [Cloud KMS Pricing](https://cloud.google.com/kms/pricing), [Cloud KMS Quotas](https://cloud.google.com/kms/docs/quotas)

---

## 5. Implementation & Constraints

### Gcloud Configuration
CMEK is immutable; it must be assigned at Organization birth.
```bash
# Example for provisioning a new Org with CMEK
gcloud beta apigee organizations create \
    --project=PROJECT_ID \
    --runtime-database-encryption-key-name=projects/KMS_PROJECT_ID/locations/LOCATION/keyRings/RING_NAME/cryptoKeys/KEY_NAME
```
- **Source:** [gcloud apigee organizations create](https://cloud.google.com/sdk/gcloud/reference/beta/apigee/organizations/create)

### Terraform Implementation
```hcl
# Apigee Organization Resource
resource "google_apigee_organization" "apigee_org" {
  project_id                           = var.project_id
  runtime_database_encryption_key_name = google_kms_crypto_key.apigee_hsm_key.id
}

# KMS Key with HSM Protection
resource "google_kms_crypto_key" "apigee_hsm_key" {
  name     = "apigee-runtime-hsm-key"
  key_ring = google_kms_key_ring.key_ring.id
  version_template {
    algorithm        = "GOOGLE_SYMMETRIC_ENCRYPTION"
    protection_level = "HSM" # Hardware backing
  }
}
```
- **Source:** [Terraform google_apigee_organization](https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/apigee_organization)
- **Source:** [Terraform google_kms_crypto_key](https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/kms_crypto_key)

### Critical Constraints
1. **Key Deletion:** Keys cannot be deleted instantly. They can be scheduled for destruction or disabled. This is standard Cloud KMS behavior.
2. **Re-encryption:** Apigee X **does not automatically re-encrypt** existing data upon key rotation. Only new data or modified objects will utilize the primary (new) key version.
> *"Cloud KMS does not automatically re-encrypt data... Existing data continues to be decrypted using the version that was active when it was written."*
[Cloud KMS Key Rotation](https://cloud.google.com/kms/docs/key-rotation#automatic_rotation)

---
**Verified Links & Sources:**
- [Apigee X CMEK Concepts](https://cloud.google.com/apigee/docs/api-platform/get-started/cmek-concepts)
- [Cloud KMS Protection Levels](https://cloud.google.com/kms/docs/protection-levels)
- [Apigee Encryption Keys Detail](https://docs.cloud.google.com/apigee/docs/api-platform/security/encryption-keys)
- [Cloud KMS Quotas](https://cloud.google.com/kms/docs/quotas)
- [Cloud KMS Pricing](https://cloud.google.com/kms/pricing)
