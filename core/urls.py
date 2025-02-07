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
from  toornoi_main.views import MatchViewSet, StageViewSet, TournamentsViewSet, Tournamentviewset, stripe_webhook



router = DefaultRouter()
# for admin panel 
router.register('tournaments', Tournamentviewset, basename='tournament')
router.register('matches', MatchViewSet,basename='matches')
router.register('stages', StageViewSet, basename='stage')

#for user  show tournament list and resgister on it 
router.register('tournament_user', TournamentsViewSet, basename='tournament_user')




urlpatterns = [
    path('admin/', admin.site.urls),
    path('loge/', include('toornoi_user_management.urls')),
    path('webhook/', stripe_webhook, name='stripe-webhook'),
    path('', include(router.urls)),
    
]


# Serve media files during development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
