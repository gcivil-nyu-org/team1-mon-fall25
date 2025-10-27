from django.urls import path
from . import views

app_name = "events"
urlpatterns = [
    path("", views.event_list, name="event_list"),  # this makes /events/ valid
    path("create/", views.create_event, name="create_event"),
    path("<int:event_id>/", views.event_detail, name="event_detail"),
    path("<int:event_id>/edit/", views.edit_event, name="edit_event"),
    path("<int:event_id>/delete/", views.delete_event, name="delete_event"),
]
