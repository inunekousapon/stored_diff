from django.urls import path
from . import views


urlpatterns = [
    path('', views.IndexView.as_view()),
    path('sync', views.sync, name='sync'),
    path('<str:name>', views.DetailView.as_view(), name="detail"),
]