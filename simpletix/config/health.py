from django.http import HttpResponse


def health_check(request):
    """Health check response for Elastic Beanstalk."""
    return HttpResponse("OK")
