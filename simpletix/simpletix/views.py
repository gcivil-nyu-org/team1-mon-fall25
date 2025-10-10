from django.shortcuts import get_object_or_404, render
from django.http import HttpResponse, HttpResponseRedirect
from django.urls import reverse
from django.db.models import F



# Create your views here.

def index(request):
    return render(request, "simpletix/index.html", {'keyword': 'Homepage'})

def webpage(request, keyword):
    return render(request, "simpletix/index.html", {'keyword': keyword})
