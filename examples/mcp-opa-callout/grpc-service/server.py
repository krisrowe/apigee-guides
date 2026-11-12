import json
import logging
import os
from concurrent import futures

import grpc

import external_callout_pb2
import external_callout_pb2_grpc

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("mcp-opa-callout")


def get_header(headers_map, name: str, default: str = "") -> str:
    target = name.lower()
    for k, v in headers_map.items():
        if k.lower() == target and v.strings:
            return v.strings[0]
    return default


def evaluate_mcp_opa(body_str: str, caller_role: str) -> tuple[str, str, str]:
    """Generic OPA-style ABAC evaluation for MCP JSON-RPC tools/call."""
    if not body_str.strip():
        return "DENY", "EMPTY_BODY", "Request body empty; cannot inspect MCP tool or intent"

    try:
        payload = json.loads(body_str)
    except json.JSONDecodeError as exc:
        return "DENY", "INVALID_JSON", f"Malformed JSON-RPC payload: {exc}"

    method = payload.get("method", "")
    if method in ("initialize", "notifications/initialized", "tools/list", "ping"):
        return "ALLOW", "OK", f"MCP lifecycle/discovery method '{method}' allowed"

    if method != "tools/call":
        return "DENY", "UNSUPPORTED_METHOD", f"MCP method '{method}' blocked by policy"

    params = payload.get("params") or {}
    tool_name = params.get("name", "")
    args = params.get("arguments") or {}

    if tool_name in ("get_order", "list_invoices"):
        return "ALLOW", "OK", f"Read tool '{tool_name}' permitted for role '{caller_role}'"

    if tool_name == "issue_refund":
        amount = float(args.get("amount", 0) or 0)
        if amount <= 250 or caller_role == "finance_approver":
            return (
                "ALLOW",
                "OK",
                f"Tool 'issue_refund' amount={amount} permitted for role '{caller_role}'",
            )
        return (
            "DENY",
            "INSUFFICIENT_ROLE_LIMIT",
            f"Tool 'issue_refund' amount={amount} exceeds 250 limit for role '{caller_role}'",
        )

    return "DENY", "UNKNOWN_TOOL", f"Tool '{tool_name}' is not allowlisted"


def get_flow_var(flow_vars, name: str, default: str = "") -> str:
    fv = flow_vars.get(name)
    if fv is None:
        return default
    kind = fv.WhichOneof("value")
    if kind == "string":
        return fv.string
    if kind in ("int32", "int64", "bool", "double"):
        return str(getattr(fv, kind))
    return default


class ExternalCalloutServicer(external_callout_pb2_grpc.ExternalCalloutServiceServicer):
    def ProcessMessage(self, request, context):
        default_mode = os.environ.get("CALLOUT_MODE", "partial").strip().lower() or "partial"
        override_mode = get_header(request.request.headers, "x-callout-mode").strip().lower()
        if not override_mode:
            override_mode = get_flow_var(request.additional_flow_variables, "opa.callout_mode").strip().lower()
        mode = override_mode or default_mode

        jwt_sub = get_flow_var(request.additional_flow_variables, "jwt.JWT-DecodeCaller.claim.sub") or get_flow_var(
            request.additional_flow_variables, "jwt.JWT-DecodeCaller.decoded.claim.sub"
        )
        jwt_role = get_flow_var(request.additional_flow_variables, "jwt.JWT-DecodeCaller.claim.role") or get_flow_var(
            request.additional_flow_variables, "jwt.JWT-DecodeCaller.decoded.claim.role"
        )
        header_role = get_header(request.request.headers, "x-caller-role")
        if jwt_role:
            caller_role = jwt_role
            identity_source = "jwt_flow_variable"
        elif header_role:
            caller_role = header_role
            identity_source = "header_fallback"
        else:
            caller_role = "support_agent"
            identity_source = "default"
        caller_sub = jwt_sub or "anonymous"
        body_len = len(request.request.content or "")

        decision, code, reason = evaluate_mcp_opa(request.request.content, caller_role)
        log.info(
            "mode=%s (env=%s override=%s) sub=%s role=%s source=%s flow_vars=%s body_len=%d incoming_copy_pathsuffix=%s decision=%s code=%s",
            mode,
            default_mode,
            override_mode or "-",
            caller_sub,
            caller_role,
            identity_source,
            list(request.additional_flow_variables.keys()),
            body_len,
            request.target.copy_path_suffix,
            decision,
            code,
        )

        flow_vars = {
            "opa.decision": external_callout_pb2.FlowVariable(string=decision),
            "opa.error_code": external_callout_pb2.FlowVariable(string=code),
            "opa.reason": external_callout_pb2.FlowVariable(string=reason),
            "opa.caller_sub": external_callout_pb2.FlowVariable(string=caller_sub),
            "opa.caller_role": external_callout_pb2.FlowVariable(string=caller_role),
            "opa.identity_source": external_callout_pb2.FlowVariable(string=identity_source),
            "opa.callout_mode": external_callout_pb2.FlowVariable(string=mode),
            "opa.seen_body_len": external_callout_pb2.FlowVariable(int32=body_len),
        }

        if mode == "echo":
            # Option A: Echo incoming request and target sub-messages so Apigee does not overwrite them with proto defaults
            return external_callout_pb2.MessageContext(
                request=request.request,
                target=request.target,
                additional_flow_variables=flow_vars,
            )

        # Default ("partial"): return ONLY additional_flow_variables (reproduces Apigee merge() overwrite)
        return external_callout_pb2.MessageContext(
            additional_flow_variables=flow_vars,
        )


def serve():
    port = os.environ.get("PORT", "8080")
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=8))
    external_callout_pb2_grpc.add_ExternalCalloutServiceServicer_to_server(
        ExternalCalloutServicer(), server
    )
    server.add_insecure_port(f"[::]:{port}")
    log.info("Starting Apigee ExternalCallout MCP/OPA gRPC server on h2c port %s", port)
    server.start()
    server.wait_for_termination()


if __name__ == "__main__":
    serve()
