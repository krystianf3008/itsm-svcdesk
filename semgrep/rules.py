# ai-generated: 70% - Claude Code drafted the test cases, I reviewed them
"""Test file for semgrep/rules.yml (Semgrep pairs a config and a test file of the same name). Not run as code -
semgrep only parses it; the functions below do not need to import anything real."""


# --- svcdesk-error-via-error-response --------------------------------------------------------------------------

@app.exception_handler(ApiError)
async def handle_api_error(request, exc):
    # ruleid: svcdesk-error-via-error-response
    return error_response(exc.status, exc.code, exc.message)


@app.exception_handler(StarletteHTTPException)
async def handle_http_error(request, exc):
    # ruleid: svcdesk-error-via-error-response
    return error_response(exc.status_code, "not_found", str(exc.detail))


@app.exception_handler(TypeError)
async def handle_type_error(request, exc):
    # ok: svcdesk-error-via-error-response
    return JSONResponse({"error": {"code": "internal", "message": "bad type"}}, status_code=500)


def error_response(status, code, message):
    # ok: svcdesk-error-via-error-response
    return JSONResponse({"error": {"code": code, "message": message}}, status_code=status)


# --- svcdesk-opaque-id-via-uuid4 ---------------------------------------------------------------------------------

def create_ticket_id():
    # ruleid: svcdesk-opaque-id-via-uuid4
    return str(uuid.uuid4())


def legacy_id_from_time():
    # ok: svcdesk-opaque-id-via-uuid4
    return str(uuid.uuid1())


def sequential_id(counter):
    # ok: svcdesk-opaque-id-via-uuid4
    return str(counter + 1)
