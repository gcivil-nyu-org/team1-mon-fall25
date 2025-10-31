# simpletix/simpletix/middleware/multi_session_middleware.py
from django.conf import settings

class MultiSessionMiddleware:
    """
    Allows multiple parallel Django sessions in the same browser by
    namespacing the session cookie per "sid".

    Usage:
      - /events/?sid=org   → uses cookie "sessionid_org"
      - /events/?sid=att   → uses cookie "sessionid_att"
    If no sid is given → falls back to normal SESSION_COOKIE_NAME.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.base_cookie = settings.SESSION_COOKIE_NAME

    def __call__(self, request):
        sid = request.GET.get("sid") or request.headers.get("X-Session-Slot")
        if sid:
            # stash it so later middleware & views can see it
            request._session_slot = sid
            # temporarily tell Django to read from a different cookie
            request.COOKIES[self.base_cookie] = request.COOKIES.get(
                f"{self.base_cookie}_{sid}", ""
            )

        response = self.get_response(request)

        # if we had a slot, write back to the slot-cookie
        if hasattr(request, "_session_slot"):
            slot = request._session_slot
            normal_val = response.cookies.get(self.base_cookie)
            if normal_val:
                # copy the regular session cookie to a slot-specific one
                response.set_cookie(
                    key=f"{self.base_cookie}_{slot}",
                    value=normal_val.value,
                    max_age=normal_val["max-age"],
                    expires=normal_val["expires"],
                    path=normal_val["path"],
                    domain=normal_val["domain"],
                    secure=normal_val["secure"],
                    httponly=normal_val["httponly"],
                    samesite=normal_val["samesite"],
                )
                # and DON'T overwrite the global one
        return response
