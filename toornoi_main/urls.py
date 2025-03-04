from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import  UserTournamentCountView


urlpatterns = [
   #  total number of tournaments a user has participated  in user profile list
# http://127.0.0.1:8000/api/user/tournaments/count/
    path('user/tournaments/count/', UserTournamentCountView.as_view(), name='user-tournament-count'),
]
