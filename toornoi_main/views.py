
from rest_framework import viewsets,permissions 
from rest_framework.views import APIView
from toornoi_user_management.models import User
from .models import  Claim, MatchChat, Notification, Prize, Tournament,Match,TournamentRegistration,Pool
from .serializers import ClaimSerializer, ContactFormSerializer, DisplayMatchSerializer, DisplayPoolSerializer, GetTournamentSerializer, MatchChatSerializer, MyTournamentUsersSerializer, NotificationSerializer, PoolSerializer, PrizeDisplaySerializer, PrizeSerializer, TournamentRegistrationSerializer, TournamentSerializer,MatchSerializer,AthletesSerializer, UserMatchSerializer
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
import math
from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from django.db.models import Q
from .notifications import send_push_notification

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

# def generate_matches(athletes, pool):
#     """
#     Randomly pairs athletes and creates matches within the pool's time range.
#     If an odd number of athletes remains, award a bye:
#       - For the first pool, pick the last athlete.
#       - For subsequent pools, pick the athlete with the highest overall score (run rate).
#     """
#     # If odd number of athletes, assign a bye.
#     if len(athletes) % 2 == 1:
#         if pool.pool_number > 1:
#             # Sort athletes descending by overall score.
#             athletes = sorted(athletes, key=lambda u: get_total_score(u, pool.tournament), reverse=True)
#             bye_player = athletes.pop(0)  # highest scorer gets bye
#         else:
#             bye_player = athletes.pop()  # For first pool, simply pop the last athlete.
#         if not isinstance(pool.result, dict):
#             pool.result = {}
#         pool.result.setdefault("bye", [])
#         pool.result["bye"].append(bye_player.id)
#         pool.save()
    
#     # Shuffle remaining athletes and create matches.
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
#     return matches
def generate_matches(athletes, pool):
    """
    Randomly pairs athletes and creates matches within the pool's time range.
    If an odd number of athletes remains and this pool is not the final pool,
    award a bye by storing their user ID in pool.result.
    """
    # Check if the pool is not Final.
    if pool.pool_number != "Final" and len(athletes) % 2 == 1:
        bye_player = athletes.pop()
        if not isinstance(pool.result, dict):
            pool.result = {}
        pool.result.setdefault("bye", [])
        pool.result["bye"].append(bye_player.id)
        pool.save()
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


#pool Creations 
class PoolViewSet(viewsets.ModelViewSet):
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
        # If last pool exists and its pool_number is not "Final", then next is numeric.
        if last_pool and last_pool.pool_number != "Final":
            next_pool_number = int(last_pool.pool_number) + 1
        else:
            next_pool_number = 1
        return Response({
            "tournament": tournament.id,
            "next_pool_number": next_pool_number
        })

    # def create(self, request, *args, **kwargs):
    #     data = request.data.copy()
    #     tournament_id = data.get('tournament')
    #     if not tournament_id:
    #         return Response({"error": "Tournament is required."}, status=status.HTTP_400_BAD_REQUEST)
    #     tournament = get_object_or_404(Tournament, id=tournament_id)
        
    #     # Calculate next pool number.
    #     last_pool = Pool.objects.filter(tournament=tournament).order_by('-pool_number').first()
    #     if last_pool and last_pool.pool_number != "Final":
    #         next_pool_number = int(last_pool.pool_number) + 1
    #     else:
    #         next_pool_number = 1
        
    #     # Determine athletes.
    #     if next_pool_number == 1:
    #         registration_ids = TournamentRegistration.objects.filter(tournament=tournament).values_list('user', flat=True)
    #         athletes = list(User.objects.filter(id__in=registration_ids))
    #         total_participants = len(athletes)
    #     else:
    #         previous_pool = Pool.objects.filter(tournament=tournament, pool_number=last_pool.pool_number).first()
    #         if not previous_pool:
    #             return Response({"error": "Previous pool not found."}, status=status.HTTP_400_BAD_REQUEST)
    #         previous_matches = Match.objects.filter(pool=previous_pool, status='Completed')
    #         athletes = [m.winner for m in previous_matches if m.winner]
    #         if previous_pool.result and isinstance(previous_pool.result, dict):
    #             bye_ids = previous_pool.result.get("bye", [])
    #             if bye_ids:
    #                 bye_users = list(User.objects.filter(id__in=bye_ids))
    #                 athletes.extend(bye_users)
    #         total_participants = len(athletes)
    #         if total_participants < 2:
    #             return Response({"message": "Tournament is complete; no more users available to create the next pool."}, status=status.HTTP_200_OK)
        
    #     # If exactly 2 athletes remain, mark this pool as Final.
    #     if total_participants == 2:
    #         data['pool_number'] = "Final"
    #     else:
    #         data['pool_number'] = str(next_pool_number)
    #     data['total_participants'] = total_participants
        
    #     serializer = self.get_serializer(data=data)
    #     serializer.is_valid(raise_exception=True)
    #     pool = serializer.save()
    def create(self, request, *args, **kwargs):
        data = request.data.copy()
        tournament_id = data.get('tournament')
        if not tournament_id:
            return Response({"error": "Tournament is required."}, status=status.HTTP_400_BAD_REQUEST)
        tournament = get_object_or_404(Tournament, id=tournament_id)
        
        # Compute total number of paid registered users.
        registration_ids = TournamentRegistration.objects.filter(
            tournament=tournament, payment_status="paid"
        ).values_list('user', flat=True)
        athletes_initial = list(User.objects.filter(id__in=registration_ids))
        total_registered = len(athletes_initial)
        
        # Compute total pools (rounds) needed as ceil(log2(total_registered)).
        total_pool_value = math.ceil(math.log2(total_registered)) if total_registered > 0 else 0
        
        # Calculate next pool number.
        last_pool = Pool.objects.filter(tournament=tournament).order_by('-pool_number').first()
        if last_pool and last_pool.pool_number != "Final":
            next_pool_number = int(last_pool.pool_number) + 1
        else:
            next_pool_number = 1
        
        # Determine athletes for this pool.
        if next_pool_number == 1:
            athletes = athletes_initial
            total_participants = len(athletes)
        else:
            previous_pool = Pool.objects.filter(tournament=tournament, pool_number=last_pool.pool_number).first()
            if not previous_pool:
                return Response({"error": "Previous pool not found."}, status=status.HTTP_400_BAD_REQUEST)
            previous_matches = Match.objects.filter(pool=previous_pool, status='Completed')
            athletes = [m.winner for m in previous_matches if m.winner]
            if previous_pool.result and isinstance(previous_pool.result, dict):
                bye_ids = previous_pool.result.get("bye", [])
                if bye_ids:
                    bye_users = list(User.objects.filter(id__in=bye_ids))
                    athletes.extend(bye_users)
            total_participants = len(athletes)
            if total_participants < 2:
                return Response({"message": "Tournament is complete; no more users available to create the next pool."}, status=status.HTTP_200_OK)
        
        # If exactly 2 athletes remain, this pool is the Final pool.
        if total_participants == 2:
            data['pool_number'] = "Final"
        else:
            data['pool_number'] = str(next_pool_number)
        data['total_participants'] = total_participants
        # Also store the total number of pools for this tournament.
        data['total_pool'] = total_pool_value

        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        pool = serializer.save()
        
        if total_participants >= 2:
            generate_matches(athletes, pool)
        
        # Send email notifications for match creation.
        for match in pool.matches.all():
            match_time_str = match.date.strftime("%Y-%m-%d %H:%M")
            match_rules = match.tournament.rules_and_regulations if hasattr(match.tournament, "rules_and_regulations") else "Standard rules apply"
            
            # If this is the final pool, use a special final match email template.
            if pool.pool_number == "Final":
                final_subject = "The Final Showdown – Your Match Details"
                # Email for player 1.
                final_message_p1 = f"""Dear {match.player_1.username},

Congratulations on making it to the final round! This is your chance to win the grand prize.
- Final Match Against: {match.player_2.username}
- Match Time: {match_time_str}
- Prize Bond: €{match.tournament.positions_1}


Best of luck - may the best athlete win!

Best regards,
Toornoi.com Team
"""
                send_mail(final_subject, final_message_p1, settings.DEFAULT_FROM_EMAIL, [match.player_1.email])
                # Email for player 2.
                final_message_p2 = f"""Dear {match.player_2.username},

Congratulations on making it to the final round! This is your chance to win the grand prize.
- Final Match Against: {match.player_1.username}
- Match Time: {match_time_str}
- Prize Bond: €{match.tournament.positions_1}

Best of luck - may the best athlete win!

Best regards,
Toornoi.com Team
"""
                send_mail(final_subject, final_message_p2, settings.DEFAULT_FROM_EMAIL, [match.player_2.email])
            else:
                # Regular pool match email.
                subject = "Tournament Pools Created – Get Ready for Your Match!"
                email_message_p1 = f"""Dear {match.player_1.username},

The tournament pools have been created! Your match is scheduled as follows:

- Opponent: {match.player_2.username}
- Match Time: {match_time_str}
- Match Rules: {match_rules}

Make sure to be ready for the match. Best of luck!

Best regards,
Toornoi.com Team
"""
                send_mail(subject, email_message_p1, settings.DEFAULT_FROM_EMAIL, [match.player_1.email])
                
                email_message_p2 = f"""Dear {match.player_2.username},

The tournament pools have been created! Your match is scheduled as follows:

- Opponent: {match.player_1.username}
- Match Time: {match_time_str}
- Match Rules: {match_rules}

Make sure to be ready for the match. Best of luck!

Best regards,
Toornoi.com Team
"""
                send_mail(subject, email_message_p2, settings.DEFAULT_FROM_EMAIL, [match.player_2.email])
        
        # (Optional: send push notifications as before)
        headers = self.get_success_headers(serializer.data)
        return Response({
            "message": f"{total_participants} participants are included in this pool, and the pool number is {data['pool_number']}.",
            "pool": serializer.data,
        }, status=status.HTTP_201_CREATED, headers=headers)
    
#     @action(detail=True, methods=['post'], url_path='finalize-matches')
#     def finalize_matches(self, request, pk=None):
#         """
#         Finalize all pending matches in this pool.
#         For each match:
#          - Finalize the match (compare scores, etc.)
#          - Send a winning email to the winner and a losing email to the loser.
#         If this is the final pool ("Final"), after finalizing, send a winner announcement email.
#         """
#         pool = get_object_or_404(Pool, pk=pk)
#         if timezone.now() < pool.end_date:
#             return Response({"error": "Pool deadline has not yet passed."}, status=status.HTTP_400_BAD_REQUEST)
        
#         pending_matches = pool.matches.filter(status="Pending")
#         results = []
#         for match in pending_matches:
#             res = finalize_match(match)
#             results.append({"match_id": match.id, "result": res})
#             if match.winner:
#                 if match.winner == match.player_1:
#                     winner_player = match.player_1
#                     loser_player = match.player_2
#                 else:
#                     winner_player = match.player_2
#                     loser_player = match.player_1
                
#                 # For regular pools, send win/loss emails.
#                 if pool.pool_number != "Final":
#                     win_subject = "Congratulations! You Won Your Match"
#                     win_message = f"""Dear {winner_player.username},

# Great news! You have won your match against {loser_player.username}.
# You have now qualified for the next round.

# Keep up the momentum and best of luck in the next round!

# Best regards,
# Toornoi.com Team
# """
#                     lose_subject = f"Thank You for Competing in {match.tournament.tournament_name}"
#                     lose_message = f"""Dear {loser_player.username},

# Your tournament journey has come to an end. You played well, but unfortunately, you lost your match against {winner_player.username}.
# We appreciate your participation and look forward to seeing you in future tournaments.
# Keep training and come back stronger!

# Best regards,
# Toornoi.com Team
# """
#                     send_mail(win_subject, win_message, settings.DEFAULT_FROM_EMAIL, [winner_player.email])
#                     send_mail(lose_subject, lose_message, settings.DEFAULT_FROM_EMAIL, [loser_player.email])
#                 else:
#                     # For the final pool, after finalizing the match, send a winner announcement email.
#                     announcement_subject = f"Congratulations! You Are the Champion of {match.tournament.tournament_name}"
#                     announcement_message = f"""Dear {winner_player.username},

# You did it! You are the champion of {match.tournament.tournament_name}.
# Prize: €{match.tournament.positions_1}

# We will contact you shortly for prize distribution details.
# Thank you for your incredible performance!

# Best regards,
# Toornoi.com Team
# """
#                     send_mail(announcement_subject, announcement_message, settings.DEFAULT_FROM_EMAIL, [winner_player.email])
#         # If final pool, update tournament status to Completed.
#         if pool.pool_number == "Final":
#             tournament = pool.tournament
#             tournament.status = "Completed"
#             tournament.save()
        
#         return Response({
#             "message": "All pending matches finalized and notifications sent.",
#             "results": results
#         }, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='finalize-matches')
    def finalize_matches(self, request, pk=None):
        """
        Finalize all pending matches in this pool.
        For each match:
          - Finalize by comparing scores.
          - Send win/loss email notifications.
        If this is the final pool ("Final"), assign prizes and send a champion announcement email,
        then update the tournament status to "Completed".
        """
        pool = get_object_or_404(Pool, pk=pk)
        if timezone.now() < pool.end_date:
            return Response({"error": "Pool deadline has not yet passed."}, status=status.HTTP_400_BAD_REQUEST)
        
        pending_matches = pool.matches.filter(status="Pending")
        results = []
        for match in pending_matches:
            res = finalize_match(match)
            results.append({"match_id": match.id, "result": res})
            if match.winner:
                if match.winner == match.player_1:
                    winner_player = match.player_1
                    loser_player = match.player_2
                else:
                    winner_player = match.player_2
                    loser_player = match.player_1
                
                if pool.pool_number != "Final":
                    win_subject = "Congratulations! You Won Your Match"
                    win_message = f"""Dear {winner_player.username},

Great news! You have won your match against {loser_player.username}.
You have now qualified for the next round.

Keep up the momentum and best of luck in the next round!

Best regards,
Toornoi.com Team
"""
                    lose_subject = f"Thank You for Competing in {match.tournament.tournament_name}"
                    lose_message = f"""Dear {loser_player.username},

Your tournament journey has come to an end. You played well, but unfortunately, you lost your match against {winner_player.username}.
We appreciate your participation and look forward to seeing you in future tournaments.
Keep training and come back stronger!

Best regards,
Toornoi.com Team
"""
                    send_mail(win_subject, win_message, settings.DEFAULT_FROM_EMAIL, [winner_player.email])
                    send_mail(lose_subject, lose_message, settings.DEFAULT_FROM_EMAIL, [loser_player.email])
                else:
                    # For the final pool, prize assignment and champion announcement.
                    # Assume there's one final match.
                    champion = winner_player
                    runner_up = loser_player
                    # Determine third place from previous pool (for simplicity, choose the first completed match's winner).
                    # previous_pool = Pool.objects.filter(tournament=pool.tournament).exclude(pool_number="Final").order_by('-pool_number').first()
                    # third_place = None
                    # if previous_pool:
                    #     match_prev = previous_pool.matches.filter(status="Completed").first()
                    #     if match_prev:
                    #         third_place = match_prev.winner
                    
                    from .models import Prize
                    Prize.objects.create(
                        tournament=pool.tournament,
                        position="Champion",
                        prize_value=pool.tournament.positions_1,
                        winner=champion
                    )
                    Prize.objects.create(
                        tournament=pool.tournament,
                        position="second winner",
                        prize_value=pool.tournament.positions_2,
                        winner=runner_up
                    )
                    # if third_place:
                    #     Prize.objects.create(
                    #         tournament=pool.tournament,
                    #         position="Third Place",
                    #         prize_value=pool.tournament.positions_3,
                    #         winner=third_place
                    #     )
                    announcement_subject = f"Congratulations! You Are the Champion of {pool.tournament.tournament_name}"
                    announcement_message = f"""Dear {champion.username},

You did it! You are the champion of {pool.tournament.tournament_name}.
Prize: €{pool.tournament.positions_1}

We will contact you shortly for prize distribution details.
Thank you for your incredible performance!

Best regards,
Toornoi.com Team
"""
                    send_mail(announcement_subject, announcement_message, settings.DEFAULT_FROM_EMAIL, [champion.email])
        if pool.pool_number == "Final":
            tournament = pool.tournament
            tournament.status = "Completed"
            tournament.save()
        
        return Response({
            "message": "All pending matches finalized and notifications sent.",
            "results": results
        }, status=status.HTTP_200_OK)

# class PoolViewSet(viewsets.ModelViewSet):
#     """
#     Pool creation and management endpoint.
#     - Creates new pools.
#     - Generates matches.
#     - If exactly 2 athletes remain, the pool is labeled "Final".
#     - When final matches are finalized, sends win/loss email notifications.
#     """
#     queryset = Pool.objects.all()

#     def get_serializer_class(self):
#         if self.action in ['list', 'retrieve']:
#             return DisplayPoolSerializer
#         return PoolSerializer

#     @action(detail=False, methods=['get'], url_path='next-pool-number')
#     def next_pool_number(self, request):
#         tournament_id = request.query_params.get('tournament')
#         if not tournament_id:
#             return Response({"error": "Tournament parameter is required."}, status=status.HTTP_400_BAD_REQUEST)
#         tournament = get_object_or_404(Tournament, id=tournament_id)
#         last_pool = Pool.objects.filter(tournament=tournament).order_by('-pool_number').first()
#         if last_pool and last_pool.pool_number != "Final":
#             next_pool_number = int(last_pool.pool_number) + 1
#         else:
#             next_pool_number = 1
#         return Response({
#             "tournament": tournament.id,
#             "next_pool_number": next_pool_number
#         })

#     def create(self, request, *args, **kwargs):
#         data = request.data.copy()
#         tournament_id = data.get('tournament')
#         if not tournament_id:
#             return Response({"error": "Tournament is required."}, status=status.HTTP_400_BAD_REQUEST)
#         tournament = get_object_or_404(Tournament, id=tournament_id)
        
#         # Calculate next pool number.
#         last_pool = Pool.objects.filter(tournament=tournament).order_by('-pool_number').first()
#         if last_pool and last_pool.pool_number != "Final":
#             next_pool_number = int(last_pool.pool_number) + 1
#         else:
#             next_pool_number = 1

#         # Determine athletes based on pool number.
#         if next_pool_number == 1:
#             registration_ids = TournamentRegistration.objects.filter(tournament=tournament).values_list('user', flat=True)
#             athletes = list(User.objects.filter(id__in=registration_ids))
#             total_participants = len(athletes)
#         else:
#             previous_pool = Pool.objects.filter(tournament=tournament, pool_number=last_pool.pool_number).first()
#             if not previous_pool:
#                 return Response({"error": "Previous pool not found."}, status=status.HTTP_400_BAD_REQUEST)
#             previous_matches = Match.objects.filter(pool=previous_pool, status='Completed')
#             athletes = [m.winner for m in previous_matches if m.winner]
#             if previous_pool.result and isinstance(previous_pool.result, dict):
#                 bye_ids = previous_pool.result.get("bye", [])
#                 if bye_ids:
#                     bye_users = list(User.objects.filter(id__in=bye_ids))
#                     athletes.extend(bye_users)
#             total_participants = len(athletes)
#             if total_participants < 2:
#                 return Response({"message": "Tournament is complete; no more users available to create the next pool."}, status=status.HTTP_200_OK)
        
#         # If exactly 2 athletes remain, treat this pool as the final pool.
#         if total_participants == 2:
#             data['pool_number'] = "Final"
#         else:
#             data['pool_number'] = next_pool_number
        
#         data['total_participants'] = total_participants
#         serializer = self.get_serializer(data=data)
#         serializer.is_valid(raise_exception=True)
#         pool = serializer.save()

#         if total_participants >= 2:
#             generate_matches(athletes, pool)

#         # Send email notifications to each athlete for each match in this pool.
#         for match in pool.matches.all():
#             match_time_str = match.date.strftime("%Y-%m-%d %H:%M")
#             # Use tournament rules if available.
#             match_rules = match.tournament.rules_and_regulations if hasattr(match.tournament, "rules_and_regulations") else "Standard rules apply"
#             subject = "Tournament Pools Created – Get Ready for Your Match!"
#             # Email to player 1.
#             email_message_p1 = f"""Dear {match.player_1.username},

# The tournament pools have been created! Your match is scheduled as follows:

# - Opponent: {match.player_2.username}
# - Match Time: {match_time_str}
# - Match Rules: {match_rules}

# Make sure to be ready for the match. Best of luck!

# Best regards,
# Toornoi.com Team
# """
#             send_mail(subject, email_message_p1, settings.DEFAULT_FROM_EMAIL, [match.player_1.email])
#             # Email to player 2.
#             email_message_p2 = f"""Dear {match.player_2.username},

# The tournament pools have been created! Your match is scheduled as follows:

# - Opponent: {match.player_1.username}
# - Match Time: {match_time_str}
# - Match Rules: {match_rules}

# Make sure to be ready for the match. Best of luck!

# Best regards,
# Toornoi.com Team
# """
#             send_mail(subject, email_message_p2, settings.DEFAULT_FROM_EMAIL, [match.player_2.email])
        
#         # (Optional: send push notifications here as well.)
#         headers = self.get_success_headers(serializer.data)
#         return Response({
#             "message": f"{total_participants} participants are included in this pool, and the pool number is {data['pool_number']}.",
#             "pool": serializer.data,
#         }, status=status.HTTP_201_CREATED, headers=headers)

#     @action(detail=True, methods=['post'], url_path='finalize-matches')
#     def finalize_matches(self, request, pk=None):
#         """
#         Finalize all pending matches in this pool.
#         For each match:
#          - Compare scores and determine the winner.
#          - Send a winning email to the winner.
#          - Send a losing email to the loser.
#         If this is the final pool (pool_number == "Final"), update the tournament status to "Completed".
#         """
#         pool = get_object_or_404(Pool, pk=pk)
#         if timezone.now() < pool.end_date:
#             return Response({"error": "Pool deadline has not yet passed."}, status=status.HTTP_400_BAD_REQUEST)
#         pending_matches = pool.matches.filter(status="Pending")
#         results = []
#         for match in pending_matches:
#             res = finalize_match(match)
#             results.append({"match_id": match.id, "result": res})
#             # Determine winner and loser.
#             if match.winner:
#                 if match.winner == match.player_1:
#                     winner_player = match.player_1
#                     loser_player = match.player_2
#                 else:
#                     winner_player = match.player_2
#                     loser_player = match.player_1
#                 # Winning email.
#                 win_subject = "Congratulations! You Won Your Match"
#                 win_message = f"""Dear {winner_player.username},

# Great news! You have won your match against {loser_player.username}.
# You have now qualified for the next round.

# Keep up the momentum and best of luck in the next round!

# Best regards,
# Toornoi.com Team
# """
#                 # Losing email.
#                 lose_subject = f"Thank You for Competing in {match.tournament.tournament_name}"
#                 lose_message = f"""Dear {loser_player.username},

# Your tournament journey has come to an end. You played well, but unfortunately, you lost your match against {winner_player.username}.
# We appreciate your participation and look forward to seeing you in future tournaments.
# Keep training and come back stronger!

# Best regards,
# Toornoi.com Team
# """
#                 send_mail(win_subject, win_message, settings.DEFAULT_FROM_EMAIL, [winner_player.email])
#                 send_mail(lose_subject, lose_message, settings.DEFAULT_FROM_EMAIL, [loser_player.email])
        
#         # If this is the final pool, update the tournament status to "Completed".
#         if pool.pool_number == "Final":
#             tournament = pool.tournament
#             tournament.status = "Completed"
#             tournament.save()
        
#         return Response({
#             "message": "All pending matches finalized and notifications sent.",
#             "results": results
#         }, status=status.HTTP_200_OK)






# class PoolViewSet(viewsets.ModelViewSet):
#     queryset = Pool.objects.all()

#     def get_serializer_class(self):
#         if self.action in ['list', 'retrieve']:
#             return DisplayPoolSerializer
#         return PoolSerializer

#     @action(detail=False, methods=['get'], url_path='next-pool-number')
#     def next_pool_number(self, request):
#         tournament_id = request.query_params.get('tournament')
#         if not tournament_id:
#             return Response({"error": "Tournament parameter is required."}, status=status.HTTP_400_BAD_REQUEST)
#         tournament = get_object_or_404(Tournament, id=tournament_id)
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
#         tournament = get_object_or_404(Tournament, id=tournament_id)
        
#         # Calculate next pool number
#         last_pool = Pool.objects.filter(tournament=tournament).order_by('-pool_number').first()
#         next_pool_number = last_pool.pool_number + 1 if last_pool else 1
#         data['pool_number'] = next_pool_number

#         if next_pool_number == 1:
#             # For pool 1, use all registered athletes.
#             registration_ids = TournamentRegistration.objects.filter(tournament=tournament).values_list('user', flat=True)
#             athletes = list(User.objects.filter(id__in=registration_ids))
#             total_participants = len(athletes)
#         else:
#             # For subsequent pools, use winners from previous pool's completed matches.
#             previous_pool = Pool.objects.filter(tournament=tournament, pool_number=next_pool_number - 1).first()
#             if not previous_pool:
#                 return Response({"error": "Previous pool not found."}, status=status.HTTP_400_BAD_REQUEST)
#             previous_matches = Match.objects.filter(pool=previous_pool, status='Completed')
#             athletes = [m.winner for m in previous_matches if m.winner]
#             # Include bye athletes from previous pool.
#             if previous_pool.result and isinstance(previous_pool.result, dict):
#                 bye_ids = previous_pool.result.get("bye", [])
#                 if bye_ids:
#                     bye_users = list(User.objects.filter(id__in=bye_ids))
#                     athletes.extend(bye_users)
#             total_participants = len(athletes)
#             if total_participants < 2:
#                 return Response({"message": "Tournament is complete; no more users available to create the next pool."}, status=status.HTTP_200_OK)
        
#         data['total_participants'] = total_participants
#         serializer = self.get_serializer(data=data)
#         serializer.is_valid(raise_exception=True)
#         pool = serializer.save()

#         if total_participants >= 2:
#             generate_matches(athletes, pool)

#         # Now, send an email notification to every athlete included in this pool.
#         # Loop over each match and send personalized emails.
#         for match in pool.matches.all():
#             match_time_str = match.date.strftime("%Y-%m-%d %H:%M")
#             match_rules = match.tournament.rules_and_regulations  if hasattr(match.tournament, "rules_and_regulations") else "Standard rules apply"
            
#             # Email to player 1
#             subject = "Tournament Pools Created – Get Ready for Your Match!"
#             message = f"""Dear {match.player_1.username},

# The tournament pools have been created! Your first match is now scheduled.

# - Opponent: {match.player_2.username}
# - Match Time: {match_time_str}
# - Match Rules: {match_rules}

# Make sure to be ready for the match. Best of luck!

# Best regards,
# Toornoi.com Team
# """
#             send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [match.player_1.email])

#             # Email to player 2
#             message = f"""Dear {match.player_2.username},

# The tournament pools have been created! Your first match is now scheduled.

# - Opponent: {match.player_1.username}
# - Match Time: {match_time_str}
# - Match Rules: {match_rules}

# Make sure to be ready for the match. Best of luck!

# Best regards,
# Toornoi.com Team
# """
#             send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [match.player_2.email])
        
#         # Also send push notifications (if users are subscribed) as before.
#         match_players = set()
#         for match in pool.matches.all():
#             match_players.add(str(match.player_1.id))
#             match_players.add(str(match.player_2.id))
#         notif_title = "New Matches Scheduled"
#         notif_message = f"New matches for Tournament {tournament.tournament_name} have been scheduled on {pool.start_date.strftime('%Y-%m-%d %H:%M')}."
#         push_response = send_push_notification(list(match_players), notif_title, notif_message, additional_data={"pool_id": pool.id})
        
#         headers = self.get_success_headers(serializer.data)
#         return Response({
#             "message": f"{total_participants} participants are included in this pool, and the pool number is {next_pool_number}.",
#             "pool": serializer.data,
#             # "push_response": push_response  # For debugging purposes.
#         }, status=status.HTTP_201_CREATED, headers=headers)
#  # Finalize All Matches in a Pool:
#         # POST http://127.0.0.1:8000/pools/<pool_id>/finalize-matches/
        
#     @action(detail=True, methods=['post'], url_path='finalize-matches')
#     def finalize_matches(self, request, pk=None):
#         """
#         Finalize all pending matches in this pool. For each match, send email notifications:
#          - A winning email to the winner.
#          - A losing email to the loser.
#         This action should be called after the pool's end_date.
#         """
#         pool = get_object_or_404(Pool, pk=pk)
#         if timezone.now() < pool.end_date:
#             return Response({"error": "Pool deadline has not yet passed."}, status=status.HTTP_400_BAD_REQUEST)
        
#         pending_matches = pool.matches.filter(status="Pending")
#         results = []
#         for match in pending_matches:
#             res = finalize_match(match)
#             results.append({"match_id": match.id, "result": res})
            
#             # Determine winner and loser for email notifications.
#             if match.winner:
#                 if match.winner == match.player_1:
#                     winner_player = match.player_1
#                     loser_player = match.player_2
#                 else:
#                     winner_player = match.player_2
#                     loser_player = match.player_1

#                 # Winning Email Template
#                 win_subject = "Congratulations! You Won Your Match"
#                 win_message = f"""Dear {winner_player.username},

# Great news! You have won your match against {loser_player.username}.
# You have now qualified for the next round.
# Keep up the momentum and best of luck in the next round!

# Best regards,
# Toornoi.com Team
# """

#                 # Losing Email Template
#                 lose_subject = f"Thank You for Competing in {match.tournament.tournament_name}"
#                 lose_message = f"""Dear {loser_player.username},

# Your tournament journey has come to an end. You played well, but unfortunately, you lost your match against {winner_player.username}.
# We appreciate your participation and look forward to seeing you in future tournaments.
# Keep training and come back stronger!

# Best regards,
# Toornoi.com Team
# """

#                 send_mail(win_subject, win_message, settings.DEFAULT_FROM_EMAIL, [winner_player.email])
#                 send_mail(lose_subject, lose_message, settings.DEFAULT_FROM_EMAIL, [loser_player.email])
        
#         return Response({
#             "message": "All pending matches finalized and notifications sent.",
#             "results": results
#         }, status=status.HTTP_200_OK)    










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

        
 
 #Get a list of all tournaments the user is registered for.
from rest_framework.viewsets import ViewSet
class UserTournamentsViewSet(viewsets.ViewSet):
    permission_classes = [permissions.IsAuthenticated]

    @action(detail=False, methods=['get'])
    def my_tournaments(self, request):
        """
        Get a list of tournaments the user is registered for.
        """
        user = request.user
        tournaments = Tournament.objects.filter(registrations__user=user).distinct()
        serializer = MyTournamentUsersSerializer(tournaments, many=True)
        return Response(serializer.data, status=200)

    @action(detail=True, methods=['get'], url_path='tournament_details')
    def tournament_details(self, request, pk=None):
        """
        Get details of a specific tournament by ID.
        """
        tournament = get_object_or_404(Tournament, pk=pk)
        serializer = MyTournamentUsersSerializer(tournament)
        return Response(serializer.data, status=200)
# class UserTournamentsViewSet(viewsets.ViewSet):
#     permission_classes = [permissions.IsAuthenticated]

#     @action(detail=False, methods=['get'])
#     def my_tournaments(self, request):
#         """
#         Get a list of tournaments the user is registered for.
#         """
#         user = request.user
#         tournaments = Tournament.objects.filter(registrations__user=user).distinct()

#         serializer = MyTournamentUsersSerializer(tournaments, many=True)
#         return Response(serializer.data, status=200)

   
    

# user tournament show and register for user

from django.core.mail import send_mail
from django.conf import settings

stripe.api_key = settings.STRIPE_SECRET_KEY

class TournamentsViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Tournament.objects.all()
    serializer_class = GetTournamentSerializer

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
            amount = int(float(tournament.registration_fee) * 100)  # Convert to cents

            intent = stripe.PaymentIntent.create(
                amount=amount,
                currency="eur",
                customer=user.stripe_customer_id if hasattr(user, 'stripe_customer_id') else None,
                payment_method=request.data.get("payment_method_id"),
                confirm=True,
                automatic_payment_methods={"enabled": True, "allow_redirects": "never"},
                metadata={"tournament_id": tournament.id, "user_id": user.id}
            )

            # Determine payment status
            payment_status = "Paid" if intent.status == "succeeded" else "Pending"

            # Register user
            registration = TournamentRegistration.objects.create(
                user=user,
                email=user.email,
                amount=tournament.registration_fee,
                tournament=tournament,
                stripe_payment_intent_id=intent.id,
                payment_status=payment_status
            )

            # **Send Confirmation Email if Payment is Successful**
            if payment_status == "Paid":
                send_mail(
                    subject=f"Payment Received for {tournament.tournament_name}",
                    message=f"Dear {user.username},\n\n"
                            f"We have received your tournament registration fee for {tournament.tournament_name}. Thank you for your payment!\n\n"
                            f"- Amount Paid: {tournament.registration_fee} EUR\n"
                            f"- Transaction ID: {intent.id}\n\n"
                            f"You are now officially registered for the tournament. We will notify you when the pools are created.\n\n"
                            f"Best regards, Toornoi.com  Team",
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[user.email],
                    fail_silently=False,
                )

            return Response({
                "message": "Tournament registration initiated.",
                "payment_status": payment_status,
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
        sum_positions_2=Sum(Cast('positions_2', output_field=IntegerField()))
    )
    
    total = (
        (aggregated.get('sum_positions_1') or 0) +
        (aggregated.get('sum_positions_2') or 0) 
    )
    
    return Response({"total_positions": total})


from django.core.mail import send_mail
logger = logging.getLogger(__name__)

User = get_user_model()
class ClaimViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows authenticated users to submit and manage claims.
    """
    queryset = Claim.objects.all()
    serializer_class = ClaimSerializer

    def perform_create(self, serializer):
        # Save the claim with the authenticated user.
        claim = serializer.save(user=self.request.user)

        # --- Email to Admins ---
        admin_subject = f"New Claim Submitted: {claim.subject}"
        admin_message = (
            f"A new claim has been submitted by {claim.user.username}.\n\n"
            f"Phone Number: {claim.phone_number}\n"
            f"Subject: {claim.subject}\n"
            f"Details: {claim.details}\n\n"
            f"View the claim in the admin panel."
        )
        admin_emails = list(User.objects.filter(is_superuser=True).values_list('email', flat=True))
        if admin_emails:
            send_mail(admin_subject, admin_message, settings.EMAIL_HOST_USER, admin_emails)

        # --- Confirmation Email to User ---
        support_email = admin_emails[0] if admin_emails else "support@example.com"
        user_subject = "Your Claim Request Has Been Received"
        user_message = f"""Dear {claim.user.username},

We have received your claim regarding "{claim.subject}". Our team will review your request and respond as soon as possible.

For urgent inquiries, please contact support at {support_email}.

Best regards,
toornoi.com Team
"""
        send_mail(user_subject, user_message, settings.DEFAULT_FROM_EMAIL, [claim.user.email])

    @action(detail=True, methods=['post'], url_path='update-claim-status')
    def update_claim_status(self, request, pk=None):
        """
        Updates the claim_status from 'Pending' to 'Resolved' and notifies the user.
        """
        try:
            claim = self.get_object()

            # Check if claim is already resolved
            if claim.claim_status == "Resolved":
                return Response({"message": "Claim is already resolved."}, status=status.HTTP_400_BAD_REQUEST)

            # Update claim status
            claim.claim_status = "Resolved"
            claim.save()

            # Send resolution email to user
            subject = "Claim Resolution Update"
            message = f"""Dear {claim.user.username},

Your claim regarding "{claim.subject}" has been reviewed.

Resolution: {claim.details}.

If you have any further concerns, feel free to reach out.

Best regards,  
Toornoi.com Team
"""
            send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [claim.user.email])

            return Response({"message": "Claim status updated and email sent successfully."}, status=status.HTTP_200_OK)

        except Claim.DoesNotExist:
            return Response({"error": "Claim not found."}, status=status.HTTP_404_NOT_FOUND)
# class ClaimViewSet(viewsets.ModelViewSet):
#     """
#     API endpoint that allows authenticated users to submit claims.
#     When a claim is submitted, an email is sent to admin users and
#     a confirmation email is sent to the athlete.
#     """
#     queryset = Claim.objects.all()
#     serializer_class = ClaimSerializer
#     # permission_classes = [IsAuthenticated]  # Uncomment if using authentication

#     def perform_create(self, serializer):
#         # Save the claim with the authenticated user.
#         claim = serializer.save(user=self.request.user)
        
#         # --- Email to Admins ---
#         admin_subject = f"New Claim Submitted: {claim.subject}"
#         admin_message = (
#             f"A new claim has been submitted by {claim.user.username}.\n\n"
#             f"Phone Number: {claim.phone_number}\n"
#             f"Subject: {claim.subject}\n"
#             f"Details: {claim.details}\n\n"
#             f"View the claim in the admin panel."
#         )
#         admin_emails = list(User.objects.filter(is_superuser=True).values_list('email', flat=True))
#         if admin_emails:
#             try:
#                 send_mail(admin_subject, admin_message, settings.EMAIL_HOST_USER, admin_emails)
#                 logger.info("Email sent successfully to admin emails: %s", admin_emails)
#             except Exception as e:
#                 logger.error("Error sending email to admin: %s", e)
#         else:
#             logger.warning("No admin emails found to send claim notification.")
        
#         # --- Confirmation Email to the Claim Submitter ---
#         # Use the first admin email as the support contact if available.
#         support_email = admin_emails[0] if admin_emails else "support@example.com"
#         user_subject = "Your Claim Request Has Been Received"
#         user_message = f"""Dear {claim.user.username},

# We have received your claim regarding "{claim.subject}". Our team will review your request and respond as soon as possible.

# For urgent inquiries, please contact support at {support_email}.

# Best regards,
# Toornoi.com Team
# """
#         try:
#             send_mail(user_subject, user_message, settings.DEFAULT_FROM_EMAIL, [claim.user.email])
#             logger.info("Confirmation email sent successfully to user: %s", claim.user.email)
#         except Exception as e:
#             logger.error("Error sending confirmation email to user: %s", e)

            
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
        
class NotificationViewSet(viewsets.ReadOnlyModelViewSet):
    """
    List all notifications for the authenticated user.
    """
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Notification.objects.filter(user=self.request.user).order_by("-created_at")        
    
    
    
#only returns list  tournaments where is_publish=True
class PublishedTournamentViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint that returns only published tournaments (is_publish=True).
    """
    # Optionally add permission_classes = [IsAuthenticated]
    queryset = Tournament.objects.filter(is_publish=True)
    serializer_class = TournamentSerializer    
    
    
  # on Contact as form  sends an email to admin user:  
class ContactFormAPIView(APIView):
    """
    API endpoint for the contact form.
    Accepts POST requests with name, email, and message.
    On submission, an email is sent to admin users (is_superuser=True).
    """
    def post(self, request, format=None):
        serializer = ContactFormSerializer(data=request.data)
        if serializer.is_valid():
            name = serializer.validated_data.get('name')
            email = serializer.validated_data.get('email')
            message = serializer.validated_data.get('message')
            
            subject = f"New Contact Form Submission from {name}"
            email_message = f"Name: {name}\nEmail: {email}\nMessage:\n{message}"
            
            # Retrieve admin email addresses.
            admin_emails = list(User.objects.filter(is_superuser=True).values_list('email', flat=True))
            if not admin_emails:
                logger.warning("No admin users found to send contact form email.")
                return Response({"error": "No admin available."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
            try:
                send_mail(subject, email_message, settings.DEFAULT_FROM_EMAIL, admin_emails)
                logger.info("Contact form email sent to admin(s): %s", admin_emails)
            except Exception as e:
                logger.error("Error sending contact form email: %s", e)
                return Response({"error": "Error sending email."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
            return Response({"message": "Your message has been sent successfully."}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)  
    
    
    
 
class PrizeViewSet(viewsets.ModelViewSet):
    queryset = Prize.objects.all()

    def get_serializer_class(self):
        if self.action in ['list', 'retrieve']:
            return PrizeDisplaySerializer   
        return PrizeSerializer  

    @action(detail=True, methods=['post'])
    def update_payment_status(self, request, pk=None):
        """
        Update trans_payment_status from 'pending' to 'paid' and send an email notification.
        """
        try:
            prize = self.get_object()

            # Check if payment is already marked as paid
            if prize.trans_payment_status == "paid":
                return Response({"message": "Payment is already completed."}, status=status.HTTP_400_BAD_REQUEST)

            # Update status to 'paid'
            prize.trans_payment_status = "paid"
            prize.save()

            # Send email notification
            user_email = prize.winner.email  # Assuming 'winner' is a ForeignKey to User model
            subject = "Your Prize Payment is Successful"
            message = "Congratulations! Your prize payment has been successfully transferred to your account."
            send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [user_email])

            return Response({"message": "Payment status updated and email sent successfully."}, status=status.HTTP_200_OK)

        except Prize.DoesNotExist:
            return Response({"error": "Prize not found."}, status=status.HTTP_404_NOT_FOUND)