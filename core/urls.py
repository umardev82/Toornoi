"""
URL configuration for Toornoi project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from rest_framework.routers import DefaultRouter
from  toornoi_main.views import AthletesViewSet, MatchViewSet, StageViewSet, TournamentAllViewSet, TournamentsViewSet, Tournamentviewset,AthleteViewSet,RegisterAthletesShowViewSet, UserMatchesViewSet, UserTournamentsViewSet, stripe_webhook



router = DefaultRouter()
# for admin panel 
#admin can manage tournaments view details   click on  button view Athletes Register list on each tournament /tournaments/tournament_id/registered_users/
router.register('tournaments', Tournamentviewset, basename='tournament')

router.register('users',AthleteViewSet,basename='users')
router.register('total_user',AthletesViewSet,basename='all_users')
router.register('total_tournaments', TournamentAllViewSet, basename='all_tournament')
router.register('matches', MatchViewSet,basename='matches')
router.register('register_athletes_tournament',RegisterAthletesShowViewSet,basename='registerAthletesTournament')
router.register('stages', StageViewSet, basename='stage')
#  Fetch tournaments where the user is registered   /my_tournaments/my_tournaments/
router.register('my_tournaments', UserTournamentsViewSet, basename='my_tournaments')


#for user  show tournament list and resgister on it 
router.register('tournament_user', TournamentsViewSet, basename='tournament_user')




urlpatterns = [
    path('admin/', admin.site.urls),
    path('loge/', include('toornoi_user_management.urls')),
    path('user/matches/', UserMatchesViewSet.as_view({'get': 'my_matches'}), name='user-matches'),   

    path('webhook/', stripe_webhook, name='stripe-webhook'),
    path('', include(router.urls)),
    
]


# Serve media files during development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
