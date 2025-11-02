from django.shortcuts import render


# Create your views here.


def index(request):
    return render(request, "simpletix/index.html", {"keyword": "Homepage"})


def webpage(request, keyword):
    return render(request, "simpletix/index.html", {"keyword": keyword})


def permission_denied_view(request, exception):
    message = str(exception) or "You do not have permission to access this page."

    context = {"error_message": message}
    return render(request, "simpletix/403_redirect.html", context, status=403)
