from django.urls import path

from . import views

app_name = "orders"
urlpatterns = [
    path("event/<int:event_id>", views.order, name="order"),
    path('payment/process/<int:order_id>/', views.process_payment, name='process_payment'),
    path('payment/success/<int:order_id>/', views.payment_success, name='payment_success'),
    path('payment/cancel/', views.payment_cancel, name='payment_cancel'),
    path('webhook/', views.stripe_webhook, name='stripe_webhook'),
]