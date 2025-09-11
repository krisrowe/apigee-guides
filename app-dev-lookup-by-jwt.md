
**Subject: Apigee Technical Guide: Using a JWT Claim to Identify a Developer App**

This guide outlines how to use a claim from a JWT to identify the calling developer application in Apigee. This allows you to use a centralized identity provider (IdP) for authentication while still leveraging Apigee's features for API management, such as quotas, analytics, and passing client identity to the backend target.

### **Primary Pattern: Using the `VerifyAPIKey` Policy**

The `VerifyAPIKey` policy is a universal and straightforward tool for identifying a developer app based on its Client ID (also known as the Consumer Key or API Key). Once the policy runs, it populates the proxy with rich context about the app and its developer, which can then be used in subsequent policies.

Below are two scenarios for using this pattern.

#### **Scenario A: Direct Lookup (JWT contains the Client ID)**

Use this method when the JWT from your identity provider includes the Apigee **Client ID** as a claim (e.g., `client_id`).

**Flow Steps:**

1.  **VerifyJWT:** First, validate the JWT to ensure its integrity and extract its claims into flow variables.
    
2.  **VerifyAPIKey:** Use the `client_id` claim from the JWT to look up the application.
    
3.  **AssignMessage (Example Action):** Use the populated variables to add identifying information to the request sent to your backend target.
    

**Policy Configurations:**

**1. VerifyJWT Policy**

```
<VerifyJWT name="JWT-VerifyToken">
    <DisplayName>JWT-VerifyToken</DisplayName>
    <Algorithm>RS256</Algorithm>
    <Source>request.header.authorization</Source>
    <PublicKey>
        <JWKS uri="[https://your-idp.com/.well-known/jwks.json](https://your-idp.com/.well-known/jwks.json)"/>
    </PublicKey>
</VerifyJWT>

```

**2. VerifyAPIKey Policy**

```
<VerifyAPIKey name="VA-VerifyKeyFromJWTClaim">
    <DisplayName>VA-VerifyKeyFromJWTClaim</DisplayName>
    <!-- Use the Client ID extracted from the JWT claim -->
    <APIKey ref="jwt.claim.client_id"/>
</VerifyAPIKey>

```

**3. Post-Identification Actions (Examples)**

Once you've successfully identified and loaded the developer/app context, you can now take various actions. Here are two common examples:

**Example A: Pass App Info to Backend (Simple Confirmation)**

If all you need to do is confirm the app is registered and pass identifying information to your backend:

```
<AssignMessage name="AM-AddAppInfoToTarget">
    <DisplayName>AM-AddAppInfoToTarget</DisplayName>
    <AssignTo createNew="false" type="request"/>
    <Set>
        <Headers>
            <Header name="X-App-Name">{developer.app.name}</Header>
            <Header name="X-Developer-Email">{developer.email}</Header>
            <Header name="X-API-Product">{apiproduct.name}</Header>
        </Headers>
    </Set>
    <IgnoreUnresolvedVariables>true</IgnoreUnresolvedVariables>
</AssignMessage>
```

**Example B: Enforce Quota (Additional Validation)**

If you want to enforce additional policies like quota limits after identification:

```
<Quota name="QU-ProductQuota">
    <DisplayName>QU-ProductQuota</DisplayName>
    <Allow count="100" countRef="verifyapikey.VA-VerifyKeyFromJWTClaim.apiproduct.developer.quota.limit"/>
    <Interval ref="verifyapikey.VA-VerifyKeyFromJWTClaim.apiproduct.developer.quota.interval">1</Interval>
    <TimeUnit ref="verifyapikey.VA-VerifyKeyFromJWTClaim.apiproduct.developer.quota.timeunit">minute</TimeUnit>
    <Distributed>true</Distributed>
    <Synchronous>true</Synchronous>
</Quota>
```

**Complete Proxy Flow Configuration (Scenario A)**

Here's how to configure the proxy flow to execute these policies in the correct sequence:

```xml
<ProxyEndpoint name="default">
    <PreFlow name="PreFlow">
        <Request>
            <Step>
                <Name>JWT-VerifyToken</Name>
            </Step>
            <Step>
                <Name>VA-VerifyKeyFromJWTClaim</Name>
            </Step>
            <Step>
                <Name>AM-AddAppInfoToTarget</Name>
            </Step>
            <!-- Optional: Add quota enforcement -->
            <Step>
                <Name>QU-ProductQuota</Name>
            </Step>
        </Request>
    </PreFlow>
    <PostFlow name="PostFlow">
        <Response/>
    </PostFlow>
    <Flows>
        <Flow name="default">
            <Request/>
            <Response/>
        </Flow>
    </Flows>
    <HTTPProxyConnection>
        <BasePath>/api/v1</BasePath>
        <VirtualHost>default</VirtualHost>
    </HTTPProxyConnection>
    <RouteRule name="default">
        <TargetEndpoint>default</TargetEndpoint>
    </RouteRule>
</ProxyEndpoint>
```

#### **Scenario B: Indirect Lookup (Using a KVM)**

Use this method when the JWT contains a unique identifier (like a `user_id`) but **not** the Apigee Client ID. A Key-Value Map (KVM) is used to bridge the external ID to the internal Apigee Client ID.

**Flow Steps:**

1.  **VerifyJWT:** Validate the JWT and extract the custom identifier.
    
2.  **KeyValueMapOperations:** Look up the Apigee Client ID from the KVM.
    
3.  **VerifyAPIKey:** Use the retrieved Client ID to look up the application.
    
4.  **AssignMessage (Example Action):** The result is the same—the app context is loaded and can be used.
    

**Policy Configurations:**

**1. VerifyJWT Policy**

```
<VerifyJWT name="JWT-VerifyToken">
    <DisplayName>JWT-VerifyToken</DisplayName>
    <Algorithm>RS256</Algorithm>
    <Source>request.header.authorization</Source>
    <PublicKey>
        <JWKS uri="https://your-idp.com/.well-known/jwks.json"/>
    </PublicKey>
</VerifyJWT>
```

**2. KeyValueMapOperations Policy**

```
<KeyValueMapOperations name="KVM-GetConsumerKey">
    <DisplayName>KVM-GetConsumerKey</DisplayName>
    <Get assignTo="private.retrieved_client_id" index="1">
        <Key>
            <Parameter ref="jwt.claim.user_id"/>
        </Key>
    </Get>
    <Scope>environment</Scope>
    <MapIdentifier>user-to-client-mapping</MapIdentifier>
</KeyValueMapOperations>
```

**3. VerifyAPIKey Policy**

```
<VerifyAPIKey name="VA-VerifyKeyFromKVM">
    <DisplayName>VA-VerifyKeyFromKVM</DisplayName>
    <!-- Use the Client ID retrieved from the KVM lookup -->
    <APIKey ref="private.retrieved_client_id"/>
</VerifyAPIKey>

```

4. Post-Identification Actions

The same post-identification actions from Scenario A apply here—you can pass app info to the backend, enforce quotas, or implement any other policies you need. The VerifyAPIKey policy populates the same context variables regardless of how it got the key.

**Complete Proxy Flow Configuration (Scenario B)**

Here's the flow configuration for the KVM-based lookup:

```xml
<ProxyEndpoint name="default">
    <PreFlow name="PreFlow">
        <Request>
            <Step>
                <Name>JWT-VerifyToken</Name>
            </Step>
            <Step>
                <Name>KVM-GetConsumerKey</Name>
            </Step>
            <Step>
                <Name>VA-VerifyKeyFromKVM</Name>
            </Step>
            <Step>
                <Name>AM-AddAppInfoToTarget</Name>
            </Step>
            <!-- Optional: Add quota enforcement -->
            <Step>
                <Name>QU-ProductQuota</Name>
            </Step>
        </Request>
    </PreFlow>
    <!-- Rest of proxy configuration same as Scenario A -->
</ProxyEndpoint>
```

### **Alternative Pattern: Using the `OAuthV2` Policy**

For the specific case where the JWT contains the Client ID (Scenario A), you can use the `OAuthV2` policy as a more semantically correct alternative.

This policy, when configured for external authorization, is **purpose-built** for integrating with third-party identity systems.

**Flow Steps:**

1.  **VerifyJWT:** Same as before, validate the token and extract claims.
    
2.  **OAuthV2:** Use the policy in a special mode to look up the app context without validating a token in Apigee's store.
    

**Policy Configuration:**

```
<OAuthV2 name="OAuth-SetContextFromJWT">
    <Operation>VerifyAccessToken</Operation>
    
    <!-- This flag tells Apigee to trust external validation -->
    <ExternalAuthorization>true</ExternalAuthorization>

    <!-- Provide the Client ID from the JWT claim -->
    <ClientId ref="jwt.claim.client_id"/>
</OAuthV2>

```

After this policy runs, the same `developer.app.name`, `developer.email`, etc., variables are available, and you can use the same post-identification actions (passing app info to backend, enforcing quotas, etc.) as described in Scenario A.

### **Comparison: `VerifyAPIKey` vs. `OAuthV2`**

-   **`VerifyAPIKey` Advantage (Universality):** This policy is a simple, direct tool. You can use the same fundamental pattern (`VerifyAPIKey` -> `AssignMessage`) for both direct and indirect lookups, which can create consistency across your API proxies.
    
-   **`OAuthV2` Advantage (Clarity of Intent):** Using the `OAuthV2` policy with external authorization clearly communicates that you are integrating with an external token-based authentication system. It is the "purpose-built" tool for this specific job, which can make the proxy's logic easier to understand for someone familiar with OAuth patterns.
    

Both approaches are valid and achieve the same result. The choice often comes down to team preference and a desire for either universality (`VerifyAPIKey`) or semantic clarity (`OAuthV2`).