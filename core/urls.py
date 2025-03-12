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
from  toornoi_main.views import AthletesViewSet, ClaimViewSet, ContactFormAPIView, MatchChatViewSet, MatchViewSet, NotificationViewSet, PoolViewSet, PrizeViewSet, PublishedTournamentViewSet, TotalclaimViewSet, TournamentAllViewSet, TournamentsViewSet, Tournamentviewset,AthleteViewSet,RegisterAthletesShowViewSet, UserMatchesViewSet, UserTournamentCountView, UserTournamentResultsView, UserTournamentsViewSet, UsersMatchesViewSet,stripe_webhook, total_paid_amount, total_positions



router = DefaultRouter()
# for admin panel 
#admin can manage tournaments view details   click on  button view Athletes Register list on each tournament /tournaments/tournament_id/registered_users/
router.register('tournaments', Tournamentviewset, basename='tournament')

router.register('users',AthleteViewSet,basename='users')
router.register('total_user',AthletesViewSet,basename='all_users')
router.register('total_tournaments', TournamentAllViewSet, basename='all_tournament')

  #  if you wnat to get total actiave matches  http://127.0.0.1:8000/matches/pending-count/ 
#   this url  for full crude control for admin on matches  http://127.0.0.1:8000/matches/
router.register('matches', MatchViewSet,basename='matches')
router.register('register_athletes_tournament',RegisterAthletesShowViewSet,basename='registerAthletesTournament')

#  Fetch tournaments where the user is registered   /my_tournaments/my_tournaments/
router.register('my_tournaments', UserTournamentsViewSet, basename='my_tournaments')


#Get mathod  http://127.0.0.1:8000/user/matches/my_matches/ for my matches
# Post mathod  http://127.0.0.1:8000/user/matches/3/update_match_result/
# Example {
#     "score": "80"
# }
router.register('user/matches', UserMatchesViewSet, basename='user-matches')
router.register('pools', PoolViewSet, basename='pool')

router.register('notifications', NotificationViewSet, basename='notifications')
#for user  show tournament list and resgister on it 
router.register('tournament_user', TournamentsViewSet, basename='tournament_user')

# in user profile list  matches Achievements win ,lose and pending matches 
router.register('profile-matches', UsersMatchesViewSet, basename='profile-matches')
#  total number of tournaments a user has participated  in user profile list
# http://127.0.0.1:8000/api/user/tournaments/count/
#update "claim_status": "Resolved"  and send email to user  POST Method  http://127.0.0.1:8000/claims/1/update-claim-status/
router.register('claims', ClaimViewSet, basename='claims')
router.register('total_claim',TotalclaimViewSet,basename='total_claim')

# update status is paid  and send email to user  POST Method http://127.0.0.1:8000/prize/1/update_payment_status/
router.register('prize',PrizeViewSet,basename='prize')
router.register('published-tournaments', PublishedTournamentViewSet, basename='published-tournaments')
# path('user/tournaments/count/', UserTournamentCountView.as_view(), name='user-tournament-count'),

    # For nested MatchChat endpoints, we define separate views.
match_chat_list = MatchChatViewSet.as_view({
    'get': 'list',
    'post': 'create'
})
match_chat_detail = MatchChatViewSet.as_view({
    'get': 'retrieve',
    'put': 'update',
    'patch': 'partial_update',
    'delete': 'destroy'
})
    


urlpatterns = [
    
    # on Contact as form  sends an email to admin user: 
     path('contact/', ContactFormAPIView.as_view(), name='contact-form'),
# GET /matches/<match_pk>/chats/: Retrieves the conversation (i.e., all chat messages) for the specified match.
# POST /matches/<match_pk>/chats/: Allows an authenticated user (one of the two players) to
    path('matches/<int:match_pk>/chats/', match_chat_list, name='match-chat-list'),
    
    # update ,DELETE http://127.0.0.1:8000/matches/2/chats/5/
    path('matches/<int:match_pk>/chats/<int:pk>/', match_chat_detail, name='match-chat-detail'),
    
    
    
    path('admin/', admin.site.urls),
    path('loge/', include('toornoi_user_management.urls')),
     path('api/', include('toornoi_main.urls')),
       
# calculates and returns the total amount from the
# TournamentRegistration model for all registrations whose payment_status is "paid." 
    path('total-paid-amount/', total_paid_amount, name='total-paid-amount'),
    
    # the total number of tournaments the authenticated user has total won and total lost and total_prize
     path('user/tournaments/results/', UserTournamentResultsView.as_view(), name='user-tournament-results'),
     
    # calculates the total sum of three fields—positions_1, positions_2, and positions_3—from your Tournament model.
    path('total-positions/', total_positions, name='total-positions'),
    path('webhook/', stripe_webhook, name='stripe-webhook'),
    path('', include(router.urls)),
    
]


# Serve media files during development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
