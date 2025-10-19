# accounts/context_processors.py

def session_flags(request):
    """
    Injects session-based flags into every template:
    - is_guest: True if the user is browsing as a guest
    - desired_role: what role the user last picked (organizer/attendee)
    """
    return {
        "is_guest": bool(request.session.get("guest")),
        "desired_role": request.session.get("desired_role"),
    }
