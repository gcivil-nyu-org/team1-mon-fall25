from django.shortcuts import render

# Create your views here.

def index(request):
    return render(request, "simpletix/index.html", {"keyword": "Homepage"})

def webpage(request, keyword):
    return render(request, "simpletix/index.html", {"keyword": keyword})
