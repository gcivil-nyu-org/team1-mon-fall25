from django.urls import path
from . import views

app_name = "events"
urlpatterns = [
    path("", views.event_list, name="event_list"),  # this makes /events/ valid
    path("create/", views.create_event, name="create_event"),
    path("<int:event_id>/", views.event_detail, name="event_detail"),
    path("<int:event_id>/edit/", views.edit_event, name="edit_event"),
    path("<int:event_id>/delete/", views.delete_event, name="delete_event"),
    path(
        "manage/", views.event_management_dashboard, name="event_management_dashboard"
    ),
    path("<int:event_id>/cancel/", views.cancel_event, name="cancel_event"),
    path(
        "<int:event_id>/notify/subscribe/",
        views.subscribe_notification,
        name="subscribe_notification",
    ),
    path(
        "<int:event_id>/notify/subscribers/",
        views.notification_subscribers,
        name="notification_subscribers",
    ),
    path(
        "<int:event_id>/notify/subscribers/send/",
        views.notify_subscribers_tickets_available,
        name="notify_subscribers_send",
    ),
]
