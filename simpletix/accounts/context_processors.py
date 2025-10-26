# accounts/context_processors.py

def session_flags(request):
    """
    Injects session-based flags into every template:
    - is_guest: True if the user is browsing as a guest
    - desired_role: what role the user last picked (organizer/attendee)
    """
    role = None
    if request.user.is_authenticated:
        role = getattr(getattr(request.user, "uprofile", None), "role", None)
    else:
        role = request.session.get("auth_role")    
    return {"auth_role": role}
