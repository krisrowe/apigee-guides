# Troubleshooting Apigee Southbound 503 Errors (Trace Tool)

**Scenario:** You have configured an Apigee Southbound connection using Private Service Connect (PSC) or an Endpoint Attachment. You can reach the target, but the Apigee Trace tool reports a `503 Service Unavailable` error with the backend.

**Common Symptom:**
*   Target Server configured with an **IP Address** (e.g., `10.x.x.x`).
*   Backend Service (ILB/NGINX) presents a certificate for a **Hostname** (e.g., `api.internal.example.com`).
*   **Trace Error:** `"no subject alternative names match ip address"`

---

## 1. Root Cause Analysis
The error confirms an **SSL Handshake Failure** due to a Hostname Verification Mismatch.

*   **The Conflict:** Apigee connects to the IP address defined in the Target Server.
*   **The Behavior:** By default, the TLS client expects the server's certificate to match the address used to connect (the IP).
*   **The Mismatch:** The backend presents a valid certificate, but for a *DNS Hostname*, not the IP. Apigee rejects the connection to prevent Man-in-the-Middle (MITM) attacks.

---

## 2. Strategic Solution: Cloud DNS Peering (Recommended)
The architecturally correct fix is to decouple Apigee from the backend IP. Apigee should connect via **Hostname**, allowing the SSL handshake to validate naturally.

### Architecture
1.  **Cloud DNS Private Zone:** Created in a project peered with the Apigee Tenant (Consumer side).
2.  **DNS Peering:** Configured on the Apigee Organization to resolve names from that zone.
3.  **A-Record:** Maps `api.internal.example.com` → `Endpoint Attachment IP`.

### Implementation Details

#### Prerequisite: Disable VPC Peering
For many PSC patterns, Apigee DNS Peering requires that **Global VPC Peering** be disabled on the Apigee Organization to avoid routing conflicts.

**Check Configuration:**
```bash
curl -X GET -H "Authorization: Bearer $(gcloud auth print-access-token)" \
  "https://apigee.googleapis.com/v1/organizations/YOUR_ORG"
```
*   **Look for:** `"disableVpcPeering": true`
*   **Warning:** If this is false/missing, DNS Peering for PSC endpoints may not work without recreating the instance.

#### Manual Verification (curl)
To test the DNS Peering config:
```bash
curl -X POST -H "Authorization: Bearer $(gcloud auth print-access-token)" \
  -H "Content-Type:application/json" \
  "https://apigee.googleapis.com/v1/organizations/YOUR_ORG/dnsZones?dnsZoneId=peer-backend" \
  -d 
    {
        "domain": "internal.example.com",
        "description": "Peering for Southbound SSL",
        "peeringConfig": {
           "targetProjectId": "YOUR_NETWORKING_PROJECT",
           "targetNetworkId": "YOUR_VPC_NETWORK"
        }
    }
```

#### Production Automation (Terraform)
Use the `google_apigee_dns_zone` resource. Ideally, chain the output of your Endpoint Attachment to the input of your DNS Record.

```hcl
resource "google_apigee_dns_zone" "southbound_peering" {
  org_id      = google_apigee_organization.org.id
  dns_zone_id = "backend-peering"
  domain      = "internal.example.com"
  description = "Peering for Southbound SSL verification"

  peering_config {
    target_project_id = var.network_project_id
    target_network_id = google_compute_network.vpc.id
  }
}
```

---

## 3. Temporary "Debug" Workaround (Non-Prod Only)
If you need to unblock testing immediately while setting up DNS, you can force the connection to work by bypassing security checks.

**Note:** Simply setting the `Host` header is **not enough**. The TLS handshake happens *before* HTTP headers are sent. You must disable validation to get past the handshake.

**Configuration:**
1.  **Disable SSL Validation:** Update the Target Server to ignore errors.
    ```xml
    <SSLInfo>
        <Enabled>true</Enabled>
        <IgnoreValidationErrors>true</IgnoreValidationErrors>
    </SSLInfo>
    ```
2.  **Inject Host Header:** Use `AssignMessage` to satisfy the backend routing (e.g., Virtual Hosts).
    ```xml
    <AssignMessage name="AM-SetHost">
        <Set>
            <Headers>
                <Header name="Host">api.internal.example.com</Header>
            </Headers>
        </Set>
    </AssignMessage>
    ```

**Reference:** [Southbound networking patterns](https://docs.cloud.google.com/apigee/docs/api-platform/architecture/southbound-networking-patterns-endpoints)
