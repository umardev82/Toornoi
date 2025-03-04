
from rest_framework import viewsets,permissions 
from rest_framework.views import APIView
from toornoi_user_management.models import User
from .models import  Claim, MatchChat, Tournament,Match,TournamentRegistration,Pool
from .serializers import ClaimSerializer, DisplayMatchSerializer, DisplayPoolSerializer, GetTournamentSerializer, MatchChatSerializer, PoolSerializer, TournamentRegistrationSerializer, TournamentSerializer,MatchSerializer,AthletesSerializer, UserMatchSerializer
import stripe
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action 
from rest_framework.decorators import api_view
from django.db.models import Sum
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from rest_framework.response import Response
from django.conf import settings
from rest_framework import status
import requests
import random
import datetime
from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from django.db.models import Q

# for admin panel 

class Tournamentviewset(viewsets.ModelViewSet):
    queryset=Tournament.objects.all()
    serializer_class=TournamentSerializer
    
    
    @action(detail=True, methods=['get'])
    def registered_users(self, request, pk=None):
        """
        Admin can view a list of users registered for a specific tournament.
        """
        tournament = self.get_object()
        registrations = TournamentRegistration.objects.filter(tournament=tournament)

        user_data = [
            {
                "id": reg.user.id,
                "username": reg.user.username,
                "email": reg.user.email,
                "payment_status": reg.payment_status,
                "registered_at": reg.created_at
            }
            for reg in registrations
        ]

        return Response({"registered_users": user_data}, status=200)


# For admin panel Athletes management
class AthleteViewSet(viewsets.ModelViewSet):
    queryset = User.objects.exclude(is_superuser=1)  # Exclude the first user by ID
    serializer_class = AthletesSerializer
    
    
 # For admin panel show  total number of  Athletes    
class AthletesViewSet(viewsets.ViewSet):
    def list(self, request):
        # Exclude the first user by ID and count the rest
        total_users = User.objects.exclude(is_superuser=1).count()
        
        # Return the total number of users as a response
        return Response({"total_users": total_users})   
    
    
 # For admin panel show  total number of  Athletes    
class TournamentAllViewSet(viewsets.ViewSet):
    def list(self, request):
        # Exclude the first user by ID and count the rest
        total_tournaments = Tournament.objects.all().count()
        
        # Return the total number of users as a response
        return Response({"total_tournaments": total_tournaments})   
    
# For admin panel to show payments Registered Athletes  
class RegisterAthletesShowViewSet(viewsets.ModelViewSet):
    queryset = TournamentRegistration.objects.all()
    serializer_class = TournamentRegistrationSerializer
  
     

 
# class MatchViewSet(viewsets.ModelViewSet):
#     queryset = Match.objects.all()
    
#     # Use DisplayMatchSerializer for listing matches
#     def get_serializer_class(self):
#         if self.action == 'list':
#             return DisplayMatchSerializer
#         return MatchSerializer

#     def perform_create(self, serializer):
#         # Any custom logic during creation (you can add extra logic here if needed)
#         serializer.save()
 


User = get_user_model()

def random_datetime(start, end):
    """Return a random datetime between start and end."""
    delta = end - start
    int_delta = delta.days * 24 * 3600 + delta.seconds
    random_second = random.randrange(int_delta)
    return start + datetime.timedelta(seconds=random_second)

def get_total_score(user, tournament):
    """
    Compute the total score for a user in the tournament across all completed matches.
    This serves as the user's overall run rate.
    """
    matches = Match.objects.filter(tournament=tournament, status="Completed")
    total = 0.0
    for m in matches:
        if m.player_1 == user:
            score = m.result.get("player_1_score")
            if score is not None:
                total += float(score)
        elif m.player_2 == user:
            score = m.result.get("player_2_score")
            if score is not None:
                total += float(score)
    return total

def generate_matches(athletes, pool):
    """
    Randomly pairs athletes and creates matches within the pool's time range.
    If an odd number of athletes remains, award a bye:
      - For the first pool, pick the last athlete.
      - For subsequent pools, pick the athlete with the highest overall score (run rate).
    """
    # If odd number of athletes, assign a bye.
    if len(athletes) % 2 == 1:
        if pool.pool_number > 1:
            # Sort athletes descending by overall score.
            athletes = sorted(athletes, key=lambda u: get_total_score(u, pool.tournament), reverse=True)
            bye_player = athletes.pop(0)  # highest scorer gets bye
        else:
            bye_player = athletes.pop()  # For first pool, simply pop the last athlete.
        if not isinstance(pool.result, dict):
            pool.result = {}
        pool.result.setdefault("bye", [])
        pool.result["bye"].append(bye_player.id)
        pool.save()
    
    # Shuffle remaining athletes and create matches.
    random.shuffle(athletes)
    matches = []
    while len(athletes) >= 2:
        player_1 = athletes.pop()
        player_2 = athletes.pop()
        match_date = random_datetime(pool.start_date, pool.end_date)
        match = Match.objects.create(
            tournament=pool.tournament,
            pool=pool,
            player_1=player_1,
            player_2=player_2,
            date=match_date,
            status='Pending',
            result={"player_1_score": None, "player_2_score": None, "submitted_by": {}}
        )
        matches.append(match)
    return matches

def finalize_match(match):
    """
    Finalize an individual match:
      - If both scores are submitted, the higher score wins.
      - If only one score is submitted, the missing score is set to 0 and the submitting athlete wins.
      - If neither score is submitted, the winner is determined by overall run rate.
    After finalization, the match status is set to "Completed".
    """
    result = match.result or {}
    score1 = result.get("player_1_score")
    score2 = result.get("player_2_score")
    
    if score1 is not None and score2 is not None:
        if float(score1) > float(score2):
            match.winner = match.player_1
        elif float(score2) > float(score1):
            match.winner = match.player_2
        else:
            # In case of a tie, default to player_1 (or apply additional logic)
            match.winner = match.player_1
    elif score1 is not None and score2 is None:
        result["player_2_score"] = 0
        match.winner = match.player_1
    elif score2 is not None and score1 is None:
        result["player_1_score"] = 0
        match.winner = match.player_2
    else:
        # Neither score submitted; use overall run rate.
        total1 = get_total_score(match.player_1, match.tournament)
        total2 = get_total_score(match.player_2, match.tournament)
        match.winner = match.player_1 if total1 >= total2 else match.player_2

    match.result = result
    match.status = "Completed"
    match.save()
    return {"message": "Match finalized", "winner": match.winner.username}





from django.utils import timezone 
class MatchViewSet(viewsets.ModelViewSet):
    queryset = Match.objects.all()
    
    def get_serializer_context(self):
        context = super().get_serializer_context()
        context.update({"request": self.request})
        return context

    def get_serializer_class(self):
        if self.action in ['list', 'retrieve']:
            return DisplayMatchSerializer
        return MatchSerializer

    def perform_create(self, serializer):
        serializer.save()
    
    @action(detail=True, methods=['post'], url_path='finalize')
    def finalize(self, request, pk=None):
        """
        Finalize an individual match if both players submitted their scores.
        """
        match = get_object_or_404(Match, pk=pk)
        if timezone.now() < match.pool.end_date:
            return Response({"error": "Pool deadline has not yet passed."}, status=status.HTTP_400_BAD_REQUEST)
        result = finalize_match(match)
        if "error" in result:
            return Response(result, status=status.HTTP_400_BAD_REQUEST)
        serializer = self.get_serializer(match)
        return Response(serializer.data, status=status.HTTP_200_OK)
    #  if you wnat to get total actiave matches  http://127.0.0.1:8000/matches/pending-count/ 
    @action(detail=False, methods=['get'], url_path='pending-count')
    def pending_count(self, request):
        """
        Custom action to return the total number of matches with status 'Pending'.
        """
        pending_total = self.get_queryset().filter(status='Pending').count()
        return Response({"Active_matches": pending_total})    

class PoolViewSet(viewsets.ModelViewSet):
    """
    A viewset for creating Pools and generating matches.
    For Pool 1, all registered athletes are used.
    For subsequent pools, winners (plus bye-advanced athletes) from the previous pool are used.
    If fewer than 2 athletes remain, a message is returned stating the tournament is complete.
    """
    queryset = Pool.objects.all()

    def get_serializer_class(self):
         if self.action in ['list', 'retrieve']:
             return DisplayPoolSerializer
         return PoolSerializer 

    @action(detail=False, methods=['get'], url_path='next-pool-number')
    def next_pool_number(self, request):
        tournament_id = request.query_params.get('tournament')
        if not tournament_id:
            return Response({"error": "Tournament parameter is required."}, status=status.HTTP_400_BAD_REQUEST)
        tournament = get_object_or_404(Tournament, id=tournament_id)
        last_pool = Pool.objects.filter(tournament=tournament).order_by('-pool_number').first()
        next_pool_number = last_pool.pool_number + 1 if last_pool else 1
        return Response({
            "tournament": tournament.id,
            "next_pool_number": next_pool_number
        })

    def create(self, request, *args, **kwargs):
        data = request.data.copy()
        tournament_id = data.get('tournament')
        if not tournament_id:
            return Response({"error": "Tournament is required."}, status=status.HTTP_400_BAD_REQUEST)
        tournament = get_object_or_404(Tournament, id=tournament_id)
        
        # Calculate the next pool number.
        last_pool = Pool.objects.filter(tournament=tournament).order_by('-pool_number').first()
        next_pool_number = last_pool.pool_number + 1 if last_pool else 1
        data['pool_number'] = next_pool_number

        if next_pool_number == 1:
            # First pool: use all registered athletes.
            registration_ids = TournamentRegistration.objects.filter(tournament=tournament).values_list('user', flat=True)
            athletes = list(User.objects.filter(id__in=registration_ids))
            total_participants = len(athletes)
        else:
            # Subsequent pools: use winners from the previous pool's completed matches.
            previous_pool = Pool.objects.filter(tournament=tournament, pool_number=next_pool_number - 1).first()
            if not previous_pool:
                return Response({"error": "Previous pool not found."}, status=status.HTTP_400_BAD_REQUEST)
            previous_matches = Match.objects.filter(pool=previous_pool, status='Completed')
            athletes = [m.winner for m in previous_matches if m.winner]
            # Also include bye-advanced athletes.
            if previous_pool.result and isinstance(previous_pool.result, dict):
                bye_ids = previous_pool.result.get("bye", [])
                if bye_ids:
                    bye_users = list(User.objects.filter(id__in=bye_ids))
                    athletes.extend(bye_users)
            total_participants = len(athletes)
            if total_participants < 2:
                return Response({"message": "Tournament is complete; no more users available to create the next pool."}, status=status.HTTP_200_OK)
        
        data['total_participants'] = total_participants
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        pool = serializer.save()

        if total_participants >= 2:
            generate_matches(athletes, pool)

        headers = self.get_success_headers(serializer.data)
        return Response({
            "message": f"{total_participants} participants are included in this pool, and the pool number is {next_pool_number}.",
            "pool": serializer.data
        }, status=status.HTTP_201_CREATED, headers=headers)
 # Finalize All Matches in a Pool:
        # POST http://127.0.0.1:8000/pools/<pool_id>/finalize-matches/
    @action(detail=True, methods=['post'], url_path='finalize-matches')
    def finalize_matches(self, request, pk=None):
        """
        Finalize all pending matches in this pool.
        This action should be called after the pool's end_date.
        """
        pool = get_object_or_404(Pool, pk=pk)
        if timezone.now() < pool.end_date:
            return Response({"error": "Pool deadline has not yet passed."}, status=status.HTTP_400_BAD_REQUEST)
        pending_matches = pool.matches.filter(status="Pending")
        results = []
        for match in pending_matches:
            res = finalize_match(match)
            results.append({"match_id": match.id, "result": res})
        return Response({
            "message": "All pending matches finalized.",
            "results": results
        }, status=status.HTTP_200_OK)







# User = get_user_model()

# def random_datetime(start, end):
#     delta = end - start
#     int_delta = delta.days * 24 * 3600 + delta.seconds
#     random_second = random.randrange(int_delta)
#     return start + datetime.timedelta(seconds=random_second)

# def generate_matches(athletes, pool):
#     random.shuffle(athletes)
#     matches = []
#     while len(athletes) >= 2:
#         player_1 = athletes.pop()
#         player_2 = athletes.pop()
#         match_date = random_datetime(pool.start_date, pool.end_date)
#         match = Match.objects.create(
#             tournament=pool.tournament,
#             pool=pool,
#             player_1=player_1,
#             player_2=player_2,
#             date=match_date,
#             status='Pending',
#             result={"player_1_score": None, "player_2_score": None, "submitted_by": {}}
#         )
#         matches.append(match)
#     if athletes:
#         bye_player = athletes.pop()
#         if not isinstance(pool.result, dict):
#             pool.result = {}
#         pool.result.setdefault("bye", [])
#         pool.result["bye"].append(bye_player.id)
#         pool.save()
#     return matches

# class PoolViewSet(viewsets.ModelViewSet):
#     queryset = Pool.objects.all()

#     def get_serializer_class(self):
#         if self.action == 'list':
#             return DisplayPoolSerializer
#         return PoolSerializer

#     @action(detail=False, methods=['get'], url_path='next-pool-number')
#     def next_pool_number(self, request):
#         tournament_id = request.query_params.get('tournament')
#         if not tournament_id:
#             return Response({"error": "Tournament parameter is required."}, status=status.HTTP_400_BAD_REQUEST)
#         try:
#             tournament = Tournament.objects.get(id=tournament_id)
#         except Tournament.DoesNotExist:
#             return Response({"error": "Tournament not found."}, status=status.HTTP_404_NOT_FOUND)
        
#         last_pool = Pool.objects.filter(tournament=tournament).order_by('-pool_number').first()
#         next_pool_number = last_pool.pool_number + 1 if last_pool else 1

#         return Response({
#             "tournament": tournament.id,
#             "next_pool_number": next_pool_number
#         })

#     def create(self, request, *args, **kwargs):
#         data = request.data.copy()
#         tournament_id = data.get('tournament')
#         if not tournament_id:
#             return Response({"error": "Tournament is required."}, status=status.HTTP_400_BAD_REQUEST)
        
#         try:
#             tournament = Tournament.objects.get(id=tournament_id)
#         except Tournament.DoesNotExist:
#             return Response({"error": "Tournament not found."}, status=status.HTTP_404_NOT_FOUND)
        
#         last_pool = Pool.objects.filter(tournament=tournament).order_by('-pool_number').first()
#         next_pool_number = last_pool.pool_number + 1 if last_pool else 1
#         data['pool_number'] = next_pool_number

#         if next_pool_number == 1:
#             registration_ids = TournamentRegistration.objects.filter(tournament=tournament).values_list('user', flat=True)
#             athletes = list(User.objects.filter(id__in=registration_ids))
#             total_participants = len(athletes)
#         else:
#             previous_pool = Pool.objects.filter(tournament=tournament, pool_number=next_pool_number - 1).first()
#             if not previous_pool:
#                 return Response({"error": "Previous pool not found."}, status=status.HTTP_400_BAD_REQUEST)
#             previous_matches = Match.objects.filter(pool=previous_pool, status='Completed')
#             athletes = [match.winner for match in previous_matches if match.winner]
#             if previous_pool.result and isinstance(previous_pool.result, dict):
#                 bye_ids = previous_pool.result.get("bye", [])
#                 if bye_ids:
#                     bye_users = list(User.objects.filter(id__in=bye_ids))
#                     athletes.extend(bye_users)
#             total_participants = len(athletes)
#             if total_participants < 2:
#                 return Response({"message": "Tournament is complete; no more users available to create the next pool."}, status=status.HTTP_200_OK)
        
#         # Pass total_participants in the data so it gets saved in the model.
#         data['total_participants'] = total_participants

#         serializer = self.get_serializer(data=data)
#         serializer.is_valid(raise_exception=True)
#         # Save the pool with the provided total_participants value.
#         pool = serializer.save()

#         if total_participants >= 2:
#             generate_matches(athletes, pool)

#         headers = self.get_success_headers(serializer.data)
#         return Response({
#             "message": f"{total_participants} participants are included in this pool, and the pool number is {next_pool_number}.",
#             "pool": serializer.data
#         }, status=status.HTTP_201_CREATED, headers=headers)



# for Atheles show  match listing   and submit result on it 
class UserMatchesViewSet(viewsets.ReadOnlyModelViewSet):  # Use ReadOnlyModelViewSet
    queryset = Match.objects.all()
    serializer_class = DisplayMatchSerializer
    
    def get_serializer_context(self):
        context = super().get_serializer_context()
        context.update({"request": self.request})
        return context
    
    def get_queryset(self):
        """Filter matches for the authenticated user."""
        user = self.request.user
        registered_tournaments = TournamentRegistration.objects.filter(user=user).values_list('tournament', flat=True)
        return Match.objects.filter(tournament__id__in=registered_tournaments)

    @action(detail=False, methods=['get'])
    def my_matches(self, request):
        """Get matches for the authenticated user."""
        matches = self.get_queryset()
        serializer = DisplayMatchSerializer(matches, many=True)
        return Response(serializer.data)
    @action(detail=True, methods=['post'])
    def update_match_result(self, request, pk=None):
        """Update match results and optionally upload screenshot for the result."""
        user = request.user

        try:
            match = Match.objects.get(pk=pk)
        except Match.DoesNotExist:
            return Response({"error": "Match not found"}, status=status.HTTP_404_NOT_FOUND)

        # Ensure the user is a participant in the match.
        if user not in [match.player_1, match.player_2]:
            return Response({"error": "You are not authorized to update this match"}, status=status.HTTP_403_FORBIDDEN)

        # Get the score from the request data.
        score = request.data.get('score')
        if score is None:
            return Response({"error": "Score is required"}, status=status.HTTP_400_BAD_REQUEST)

        # Get the screenshot file if provided.
        screenshot = request.FILES.get('screenshot')

        # Initialize the result field if necessary.
        if not isinstance(match.result, dict):
            match.result = {}
        match.result.setdefault("player_1_score", None)
        match.result.setdefault("player_2_score", None)
        match.result.setdefault("submitted_by", {})

        # Process based on which player is submitting.
        if user == match.player_1:
            if match.result["player_1_score"] is not None:
                return Response({"error": "You have already submitted your score"}, status=status.HTTP_400_BAD_REQUEST)
            match.result["player_1_score"] = score
            match.result["submitted_by"]["player_1"] = user.username

            # If a screenshot file is provided, save it and update the JSON field.
            if screenshot:
                filename = default_storage.save(
                    f"match_screenshots/{user.username}_{match.id}_{screenshot.name}",
                    ContentFile(screenshot.read())
                )
                file_url = default_storage.url(filename)
                match.result["player_1_screenshot"] = file_url

        elif user == match.player_2:
            if match.result["player_2_score"] is not None:
                return Response({"error": "You have already submitted your score"}, status=status.HTTP_400_BAD_REQUEST)
            match.result["player_2_score"] = score
            match.result["submitted_by"]["player_2"] = user.username

            if screenshot:
                filename = default_storage.save(
                    f"match_screenshots/{user.username}_{match.id}_{screenshot.name}",
                    ContentFile(screenshot.read())
                )
                file_url = default_storage.url(filename)
                match.result["player_2_screenshot"] = file_url

        match.save()
        serializer = DisplayMatchSerializer(match, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)
    # @action(detail=True, methods=['post'])
    # def update_match_result(self, request, pk=None):
    #     """Update match results."""
    #     user = request.user

    #     try:
    #         match = Match.objects.get(pk=pk)
    #     except Match.DoesNotExist:
    #         return Response({"error": "Match not found"}, status=404)

    #     # Check if the user is part of the match
    #     if user not in [match.player_1, match.player_2]:
    #         return Response({"error": "You are not authorized to update this match"}, status=403)

    #     score = request.data.get('score')
    #     if score is None:
    #         return Response({"error": "Score is required"}, status=400)

    #     # Ensure result is initialized
    #     if not isinstance(match.result, dict):
    #         match.result = {}

    #     match.result.setdefault("player_1_score", None)
    #     match.result.setdefault("player_2_score", None)
    #     match.result.setdefault("submitted_by", {})

    #     if user == match.player_1:
    #         if match.result["player_1_score"] is not None:
    #             return Response({"error": "You have already submitted your score"}, status=400)
    #         match.result["player_1_score"] = score
    #         match.result["submitted_by"]["player_1"] = user.username
    #     elif user == match.player_2:
    #         if match.result["player_2_score"] is not None:
    #             return Response({"error": "You have already submitted your score"}, status=400)
    #         match.result["player_2_score"] = score
    #         match.result["submitted_by"]["player_2"] = user.username

    #     match.save()
    #     serializer = DisplayMatchSerializer(match)
    #     return Response(serializer.data, status=200)

#update code  end

# class UserMatchesViewSet(viewsets.ViewSet):
#     # permission_classes = [permissions.IsAuthenticated]

#     @action(detail=False, methods=['get'])
#     def my_matches(self, request):
#         user = request.user
        
#         # Get tournaments where the user is registered
#         registered_tournaments = TournamentRegistration.objects.filter(user=user).values_list('tournament', flat=True)
        
#         # Get matches for those tournaments
#         matches = Match.objects.filter(tournament__id__in=registered_tournaments)
        
#         serializer = DisplayMatchSerializer(matches, many=True)
#         return Response(serializer.data) 
        
 
 #Get a list of all tournaments the user is registered for.
from rest_framework.viewsets import ViewSet
class UserTournamentsViewSet(ViewSet):
    permission_classes = [permissions.IsAuthenticated]

    @action(detail=False, methods=['get'])
    def my_tournaments(self, request):
        """
        Get a list of tournaments the user is registered for.
        """
        user = request.user

        
        tournaments = Tournament.objects.filter(registrations__user=user).distinct()

        serializer = TournamentSerializer(tournaments, many=True)
        return Response(serializer.data, status=200)

   
    

# user tournament show and register for user
# Set Stripe API key
stripe.api_key = settings.STRIPE_SECRET_KEY

class TournamentsViewSet(viewsets.ReadOnlyModelViewSet):  # Read-only for listing
    queryset = Tournament.objects.all()
    serializer_class = GetTournamentSerializer
    # permission_classes = [permissions.AllowAny]
    def get_serializer_context(self):
        """Pass request context to serializer to check user registration and payment status."""
        context = super().get_serializer_context()
        context.update({"request": self.request})
        return context
    
    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def register(self, request, pk=None):
        try:
            tournament = self.get_object()
            user = request.user

            # Check if user is already registered
            if TournamentRegistration.objects.filter(user=user, tournament=tournament).exists():
                return Response({"error": "You are already registered for this tournament."}, status=400)

            # Create Stripe PaymentIntent
            
            amount = int(float(tournament.registration_fee) * 100)  # Ensure it's a valid integer

            intent = stripe.PaymentIntent.create(
                  amount=amount,
                  currency="eur",
                  customer=user.stripe_customer_id if hasattr(user, 'stripe_customer_id') else None,
                  payment_method=request.data.get("payment_method_id"),
                  confirm=True,
                  automatic_payment_methods={"enabled": True, "allow_redirects": "never"},
                  metadata={"tournament_id": tournament.id, "user_id": user.id}  # Ensure metadata is added
            )



            # Register user with "Pending" payment status
            registration = TournamentRegistration.objects.create(
                user=user,
                amount=tournament.registration_fee,
                tournament=tournament,
                stripe_payment_intent_id=intent.id,
                payment_status="Pending"
            )

            return Response({
                "message": "Tournament registration initiated.",
                "payment_intent_id": intent.id,
                "client_secret": intent.client_secret
            }, status=201)

        except Tournament.DoesNotExist:
            return Response({"error": "Tournament not found."}, status=404)

        except stripe.error.StripeError as e:
            return Response({"error": str(e)}, status=400)

import stripe
import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from .models import TournamentRegistration
import logging

logger = logging.getLogger(__name__)

@csrf_exempt
def stripe_webhook(request):
    payload = request.body
    sig_header = request.META.get("HTTP_STRIPE_SIGNATURE", "")

    try:
        payload_str = payload.decode('utf-8')
        logger.info(f"Webhook payload: {payload_str}")  # Log the payload

        event = stripe.Webhook.construct_event(
            payload_str, sig_header, settings.STRIPE_ENDPOINT_SECRET
        )

        # Handle the event
        if event["type"] == "payment_intent.succeeded":
            payment_intent = event["data"]["object"]
            logger.info(f"PaymentIntent succeeded: {payment_intent['id']}")  # Log the PaymentIntent ID

            try:
                # Find the corresponding TournamentRegistration
                registration = TournamentRegistration.objects.get(
                    stripe_payment_intent_id=payment_intent["id"]
                )
                registration.payment_status = "Paid"
                registration.save()
                logger.info(f"Updated registration for PaymentIntent: {payment_intent['id']}")
            except TournamentRegistration.DoesNotExist:
                logger.error(f"Registration not found for PaymentIntent: {payment_intent['id']}")
                return JsonResponse({"error": "Registration not found"}, status=404)

        return JsonResponse({"status": "success"}, status=200)

    except stripe.error.SignatureVerificationError as e:
        logger.error(f"Invalid signature: {e}")
        return JsonResponse({"error": "Invalid signature"}, status=400)
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return JsonResponse({"error": str(e)}, status=400)
# import stripe
# import json
# from django.http import JsonResponse
# from django.views.decorators.csrf import csrf_exempt
# from django.conf import settings
# from .models import TournamentRegistration

# stripe.api_key = settings.STRIPE_SECRET_KEY
# import logging

# logger = logging.getLogger(__name__)

# @csrf_exempt
# def stripe_webhook(request):
#     payload = request.body
#     sig_header = request.META.get("HTTP_STRIPE_SIGNATURE", "")

#     try:
#         payload_str = payload.decode('utf-8')
#         logger.info(f"Webhook payload: {payload_str}")  # Log the payload

#         event = stripe.Webhook.construct_event(
#             payload_str, sig_header, settings.STRIPE_ENDPOINT_SECRET
#         )

#         if event["type"] == "payment_intent.succeeded":
#             payment_intent = event["data"]["object"]
#             logger.info(f"PaymentIntent succeeded: {payment_intent['id']}")  # Log the PaymentIntent ID

#             try:
#                 registration = TournamentRegistration.objects.get(
#                     stripe_payment_intent_id=payment_intent["id"]
#                 )
#                 registration.payment_status = "Paid"
#                 registration.save()
#             except TournamentRegistration.DoesNotExist:
#                 logger.error(f"Registration not found for PaymentIntent: {payment_intent['id']}")
#                 return JsonResponse({"error": "Registration not found"}, status=404)

#         return JsonResponse({"status": "success"}, status=200)

#     except stripe.error.SignatureVerificationError as e:
#         logger.error(f"Invalid signature: {e}")
#         return JsonResponse({"error": "Invalid signature"}, status=400)
#     except Exception as e:
#         logger.error(f"Webhook error: {e}")
#         return JsonResponse({"error": str(e)}, status=400)



# class TournamentsViewSet(viewsets.ReadOnlyModelViewSet):  
#     queryset = Tournament.objects.all()
#     serializer_class = TournamentSerializer
#     permission_classes = [permissions.AllowAny]

#     @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated])
#     def register(self, request, pk=None):
#         tournament = get_object_or_404(Tournament, pk=pk)
#         user = request.user

#         # Check if user is already registered
#         if TournamentRegistration.objects.filter(user=user, tournament=tournament).exists():
#             return Response({"error": "You are already registered for this tournament."}, status=400)

#         # Create a registration record with Pending status
#         registration = TournamentRegistration.objects.create(
#             user=user,
#             tournament=tournament,
#             payment_status="Pending"
#         )

#         # Return the SumUp payment link
#         return Response({
#             "message": "Registration successful. Proceed to payment.",
#             "sumup_link": tournament.sumup_link
#         }, status=201)



# for showing in user profile list  matches Achievements  ,lose and pending matches 
class UsersMatchesViewSet(viewsets.ReadOnlyModelViewSet):
    """
    List matches for the logged-in user along with the result
    (Win, Lose, or Pending) for each match.
    """
    serializer_class = UserMatchSerializer

    def get_queryset(self):
        user = self.request.user
        # Filter matches where the user is either player_1 or player_2.
        return Match.objects.filter(Q(player_1=user) | Q(player_2=user))


# calculates and returns the total amount from the
# TournamentRegistration model for all registrations whose payment_status is "paid."
@api_view(['GET'])
def total_paid_amount(request):
    """
    Returns the total amount for registrations where payment_status is 'paid'.
    Optionally, filter by tournament if the query parameter 'tournament' is provided.
    """
    tournament_id = request.query_params.get('tournament')
    if tournament_id:
        registrations = TournamentRegistration.objects.filter(
            tournament__id=tournament_id, payment_status="paid"
        )
    else:
        registrations = TournamentRegistration.objects.filter(payment_status="paid")
    
    total = registrations.aggregate(total_amount=Sum('amount'))['total_amount'] or 0
    total = int(total)
    return Response({"total_paid_amount": total})          

# calculates the total sum of three fields—positions_1, positions_2, and positions_3—from your Tournament model.
from django.db.models import Sum, IntegerField
from django.db.models.functions import Cast
@api_view(['GET'])
def total_positions(request):
    """
    Returns the total sum of positions_1, positions_2, and positions_3 across all Tournament records.
    The fields are cast to integers before summing.
    """
    aggregated = Tournament.objects.aggregate(
        sum_positions_1=Sum(Cast('positions_1', output_field=IntegerField())),
        sum_positions_2=Sum(Cast('positions_2', output_field=IntegerField())),
        sum_positions_3=Sum(Cast('positions_3', output_field=IntegerField()))
    )
    
    total = (
        (aggregated.get('sum_positions_1') or 0) +
        (aggregated.get('sum_positions_2') or 0) +
        (aggregated.get('sum_positions_3') or 0)
    )
    
    return Response({"total_positions": total})


from django.core.mail import send_mail
logger = logging.getLogger(__name__)

User = get_user_model()

class ClaimViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows authenticated users to submit claims.
    When a claim is submitted, an email is sent to admin users (is_superuser=True).
    """
    queryset = Claim.objects.all()
    serializer_class = ClaimSerializer
    # permission_classes = [IsAuthenticated]  # Ensure only logged-in users can submit

    def perform_create(self, serializer):
        # Save the claim with the authenticated user.
        claim = serializer.save(user=self.request.user)
        
        # Compose email details.
        subject = f"New Claim Submitted: {claim.subject}"
        message = (
            f"A new claim has been submitted by {claim.user.username}.\n\n"
            f"Phone Number: {claim.phone_number}\n"
            f"Subject: {claim.subject}\n"
            f"Details: {claim.details}\n\n"
            f"View the claim in the admin panel."
        )
        
        # Get admin email addresses from the database where is_superuser is True.
        admin_emails = list(User.objects.filter(is_superuser=True).values_list('email', flat=True))
        
        if admin_emails:
            try:
                send_mail(subject, message, settings.EMAIL_HOST_USER, admin_emails)
                logger.info("Email sent successfully to admin emails: %s", admin_emails)
            except Exception as e:
                logger.error("Error sending email: %s", e)
        else:
            logger.warning("No admin emails found to send claim notification.")
            
            
            
# ViewSet for chat messages for a specific match  
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated

class MatchChatViewSet(viewsets.ModelViewSet):
    serializer_class = MatchChatSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Retrieve the match using the URL parameter.
        match_id = self.kwargs.get('match_pk')
        match = get_object_or_404(Match, id=match_id)
        # Only allow access if the requesting user is one of the two players.
        if self.request.user not in [match.player_1, match.player_2]:
            raise PermissionDenied("You are not authorized to view this match's chats.")
        return MatchChat.objects.filter(match=match).order_by('timestamp')

    def perform_create(self, serializer):
        match_id = self.kwargs.get('match_pk')
        match = get_object_or_404(Match, id=match_id)
        # Only allow message creation if the request user is a participant in the match.
        if self.request.user not in [match.player_1, match.player_2]:
            raise PermissionDenied("You are not authorized to send messages in this match.")
        message_instance = serializer.save(match=match, sender=self.request.user)
        
        # Optionally, notify the other participant.
        # Determine the "other" user:
        other_user = match.player_1 if self.request.user != match.player_1 else match.player_2
        # Call your push notification service here to send the message to other_user.
        # For example:
        # send_push_notification(other_user, message_instance.message)          
        
        
        
 # For admin panel show  total number of  claim    
class TotalclaimViewSet(viewsets.ViewSet):
    def list(self, request):
        # Exclude the first user by ID and count the rest
        total_claim = Claim.objects.all().count()
        
        # Return the total number of users as a response
        return Response({"total_claim": total_claim})     
  
  
#total number of tournaments a user has participated  in user profile list  
class UserTournamentCountView(APIView):
    
    def get(self, request, format=None):
        # Count distinct tournaments for which the logged-in user is registered.
        total=TournamentRegistration.objects.filter(user=request.user).values('tournament').distinct().count()
        return Response ({"total_tournamnets_participated":total})
        

# the total number of tournaments the authenticated user has total won and total lost and total_prize
class UserTournamentResultsView(APIView):
    """
    API endpoint that returns the total number of tournaments the authenticated user 
    has won and lost, and also the total prize (from tournament.positions_1) they earned 
    from winning tournaments.
    
    A tournament is considered complete if its final pool (the one with the highest pool_number)
    contains at least one Completed match. The winner of that final match is considered the tournament winner.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, format=None):
        user = request.user
        
        # Get distinct tournament IDs where the user registered.
        tournament_ids = TournamentRegistration.objects.filter(user=user)\
                            .values_list('tournament', flat=True).distinct()
        
        tournaments_won = 0
        tournaments_lost = 0
        total_prize = 0

        for tid in tournament_ids:
            try:
                tournament = Tournament.objects.get(id=tid)
            except Tournament.DoesNotExist:
                continue
            
            # Get the final (last) pool of the tournament.
            final_pool = Pool.objects.filter(tournament=tournament).order_by('-pool_number').first()
            if not final_pool:
                continue
            
            # Get the final match in that pool that is Completed.
            final_match = Match.objects.filter(pool=final_pool, status="Completed").order_by('-id').first()
            if not final_match:
                continue

            # Check if the user participated in the tournament final.
            if final_match.winner == user:
                tournaments_won += 1
                # Add the tournament prize from positions_1 (if set)
                if tournament.positions_1:
                    try:
                        total_prize += int(tournament.positions_1)
                    except ValueError:
                        # If positions_1 is not a number, skip it.
                        pass
            else:
                tournaments_lost += 1

        return Response({
            "tournaments_won": tournaments_won,
            "tournaments_lost": tournaments_lost,
            "total_prize": total_prize
        })