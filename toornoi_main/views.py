
from rest_framework import viewsets,permissions 
from rest_framework.views import APIView
from toornoi_user_management.models import User
from .models import  Claim, MatchChat, Notification, Prize, Tournament,Match,TournamentRegistration,Pool, TournamentType, category
from .serializers import CategorySerializer, ClaimSerializer, ContactFormSerializer, DisplayMatchSerializer, DisplayPoolSerializer, DisplayTournamentSerializer, GetTournamentSerializer, MatchChatSerializer, MyTournamentUsersSerializer, NotificationSerializer, PoolSerializer, PrizeDisplaySerializer, PrizeSerializer, TournamentRegistrationSerializer, TournamentSerializer,MatchSerializer,AthletesSerializer, TournamentTypeSerializer, UserMatchSerializer
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
from django.core.mail import send_mail
# for admin panel 
class CategoryViewSet(viewsets.ModelViewSet):
    queryset = category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [IsAuthenticated]


class TournamentTypeViewSet(viewsets.ModelViewSet):
    queryset = TournamentType.objects.all()
    serializer_class = TournamentTypeSerializer
    permission_classes = [IsAuthenticated]

    
    
    
class Tournamentviewset(viewsets.ModelViewSet):
    queryset=Tournament.objects.all()
    permission_classes = [IsAuthenticated]

    # serializer_class=TournamentSerializer
    def get_serializer_class(self):
       if self.action in ['list','retrieve']:
           return DisplayTournamentSerializer
       return TournamentSerializer
    
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
    permission_classes = [IsAuthenticated]

    
    
 # For admin panel show  total number of  Athletes    
class AthletesViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    def list(self, request):
        # Exclude the first user by ID and count the rest
        total_users = User.objects.exclude(is_superuser=1).count()
        
        # Return the total number of users as a response
        return Response({"total_users": total_users})   
    
    
 # For admin panel show  total number of  Athletes    
class TournamentAllViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    def list(self, request):
        # Exclude the first user by ID and count the rest
        total_tournaments = Tournament.objects.all().count()
        
        # Return the total number of users as a response
        return Response({"total_tournaments": total_tournaments})   
    
# For admin panel to show payments Registered Athletes  
class RegisterAthletesShowViewSet(viewsets.ModelViewSet):
    queryset = TournamentRegistration.objects.all()
    serializer_class = TournamentRegistrationSerializer
    permission_classes = [IsAuthenticated]

  
     


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
    If an odd number of athletes remains and this pool is not the final pool,
    award a bye by storing their user ID in pool.result.
    """
    # Check if the pool is not Final.
    if pool.pool_number != "Finale" and len(athletes) % 2 == 1:
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
            status='En attente',
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
    match.status = "Complété"
    match.save()
    return {"message": " Match terminé", "winner": match.winner.username}





from django.utils import timezone 
class MatchViewSet(viewsets.ModelViewSet):
    queryset = Match.objects.all()
    permission_classes = [IsAuthenticated]

    
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
        pending_total = self.get_queryset().filter(status='En attente').count()
        return Response({"Active_matches": pending_total})    

from django.conf import settings
from django.core.mail import send_mail
#pool Creations 
class PoolViewSet(viewsets.ModelViewSet):
    queryset = Pool.objects.all()
    permission_classes = [IsAuthenticated]


    def get_serializer_class(self):
        if self.action in ['list', 'retrieve']:
            return DisplayPoolSerializer
        return PoolSerializer

    @action(detail=False, methods=['get'], url_path='next-pool-number')
    def next_pool_number(self, request):
        tournament_id = request.query_params.get('tournament')
        if not tournament_id:
            return Response({"error": "Le paramètre du tournoi est requis."}, status=status.HTTP_400_BAD_REQUEST)
        tournament = get_object_or_404(Tournament, id=tournament_id)
        last_pool = Pool.objects.filter(tournament=tournament).order_by('-pool_number').first()
        # If last pool exists and its pool_number is not "Final", then next is numeric.
        if last_pool and last_pool.pool_number != "Finale":
            next_pool_number = int(last_pool.pool_number) + 1
        else:
            next_pool_number = 1
        return Response({
            "tournament": tournament.id,
            "next_pool_number": next_pool_number
        })

    def create(self, request, *args, **kwargs):
        data = request.data.copy()
        tournament_id = data.get('tournament')
        if not tournament_id:
            return Response({"error": " Le tournoi est requis."}, status=status.HTTP_400_BAD_REQUEST)
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
        if last_pool and last_pool.pool_number != "Finale":
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
                return Response({"error": "Tour précédent introuvable."}, status=status.HTTP_400_BAD_REQUEST)
            previous_matches = Match.objects.filter(pool=previous_pool, status='Completed')
            athletes = [m.winner for m in previous_matches if m.winner]
            if previous_pool.result and isinstance(previous_pool.result, dict):
                bye_ids = previous_pool.result.get("bye", [])
                if bye_ids:
                    bye_users = list(User.objects.filter(id__in=bye_ids))
                    athletes.extend(bye_users)
            total_participants = len(athletes)
            if total_participants < 2:
                return Response({"message": "Le tournoi est terminé ; aucun joueur disponible pour créer le tour suivant."}, status=status.HTTP_200_OK)
        
        # If exactly 2 athletes remain, this pool is the Final pool.
        if total_participants == 2:
            data['pool_number'] = "Finale"
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
        
        
            # **Create Notifications for each player with Match Time**
        for match in pool.matches.all():
            match_time_str = match.date.strftime("%y-%m-%d %H:%M")  # Format match date/time
        
            match_link = f"https://toornoi.com/my-account/match/{match.id}/"  # Generate match link
                # match_link = f"http://127.0.0.1:8000/matches/{match.id}/" 

            Notification.objects.create(
               user=match.player_1,
                title="Nouveau match créé",
               message=f"Votre match contre {match.player_2.username} est prévu le {match_time_str}. "
                         f"Voici le lien du match: {match_link}",
           )

            Notification.objects.create(
                user=match.player_2,
                title="Nouveau match créé",
                message=f"Votre match contre {match.player_1.username} est prévu le {match_time_str}. "
                        f"Voici le lien du match: {match_link}",
            )   
        # for match in pool.matches.all():
        #     match_time_str=match.date.strftime("%y-%m-%d %H:%M") # Format match date/time
        #     Notification.objects.create(
        #         user=match.player_1,
        #         title="Nouveau match créé",
        #         message=f"Votre match contre {match.player_2.username} est prévu le {match_time_str}.",
        #     )
        #     Notification.objects.create(
        #         user=match.player_2,
        #         title="Nouveau match créé",
        #         message=f"Votre match contre {match.player_1.username} est prévu le {match_time_str}.",
        #     )
        
        
        # Send email notifications for match creation.
        for match in pool.matches.all():
            match_time_str = match.date.strftime("%Y-%m-%d %H:%M")
            match_rules = match.tournament.rules_and_regulations if hasattr(match.tournament, "rules_and_regulations") else "Standard rules apply"
            
            # If this is the final pool, use a special final match email template.
            if pool.pool_number == "Finale":
                final_subject = " L'épreuve finale ���� Détails de votre match"
                # Email for player 1.
                final_message_p1 = f"""Cher {match.player_1.username},

Félicitations pour votre participation à la phase finale ! C'est maintenant votre chance de gagner le prix final.
- Match final contre: {match.player_2.username}
- Heure du match : {match_time_str}
- Prix final : €{match.tournament.positions_1}


Bonne chance - que le meilleur athlète gagne !

Cordialement, 
L'équipe de Toornoi.com

"""
                send_mail(final_subject, final_message_p1,"contact@toornoi.com",[match.player_1.email])
                # Email for player 2.
                final_message_p2 = f"""Cher {match.player_2.username},

Félicitations pour votre participation à la phase finale ! C'est maintenant votre chance de gagner le prix final.
- Match final contre: {match.player_1.username}
- Heure du match: {match_time_str}
- Prix final: €{match.tournament.positions_1}

Bonne chance - que le meilleur athlète gagne !

Cordialement, 
L'équipe de Toornoi.com
"""
                send_mail(final_subject, final_message_p2,"contact@toornoi.com",[match.player_2.email])
            else:
                # Regular pool match email.
                subject = " Poules de tournoi créées ���� Préparez-vous pour votre match !"
                email_message_p1 = f"""Cher {match.player_1.username},

Les poules du tournoi ont été créées ! Votre match est programmé comme suit:

-Adversaire: {match.player_2.username}
- Heure du match: {match_time_str}
- Règles du match: {match_rules}

Assurez-vous d'être prêt pour le match. Nous vous souhaitons bonne chance !


Cordialement,
L'équipe de Toornoi.com

"""
                send_mail(subject, email_message_p1,"contact@toornoi.com", [match.player_1.email])
                
                email_message_p2 = f"""Cher {match.player_2.username},

Les poules du tournoi ont été créées ! Votre match est programmé comme suit:

- Adversaire: {match.player_1.username}
- Heure du match: {match_time_str}
- Règles du match: {match_rules}

Assurez-vous d'être prêt pour le match. Nous vous souhaitons bonne chance !

Cordialement,
L'équipe de Toornoi.com
"""
                send_mail(subject, email_message_p2,"contact@toornoi.com", [match.player_2.email])
                
            headers = self.get_success_headers(serializer.data)
            return Response({
            "message": f"{total_participants} Les participants sont inclus dans cette poule , et le numéro de poule est.{data['pool_number']}.",
            "pool": serializer.data,
        }, status=status.HTTP_201_CREATED, headers=headers)
        
                #   Also send push notifications (if users are subscribed) as before.
#             match_players = set()
#             for match in pool.matches.all():
#                 match_players.add(str(match.player_1.id))
#                 match_players.add(str(match.player_2.id))
#             notif_title = "New Matches Scheduled"
#             notif_message = f"New matches for Tournament {tournament.tournament_name} have been scheduled on {pool.start_date.strftime('%Y-%m-%d %H:%M')}."
#             push_response = send_push_notification(list(match_players), notif_title, notif_message, additional_data={"pool_id": pool.id})
        
#         headers = self.get_success_headers(serializer.data)
#         return Response({
#  "message": f"{total_participants} Les participants sont inclus dans cette poule , et le numéro de poule est.{data['pool_number']}.",
#             "pool": serializer.data,
#             "push_response": push_response  # For debugging purposes.
#         }, status=status.HTTP_201_CREATED, headers=headers)
        # # (Optional: send push notifications as before)
      
    

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
        tournament = pool.tournament  # Define it at the beginning
        if timezone.now() < pool.end_date:
            return Response({"error": "La date limite du tour n’est pas encore dépassée."}, status=status.HTTP_400_BAD_REQUEST)
        
        pending_matches = pool.matches.filter(status="En attente")
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
                    
                match_time_str=match.date.strftime("%Y-%m-%d %H:%M")  # Format match time
                
                # Generate match link
                match_link = f"https://toornoi.com/my-account/match/{match.id}/"
                # ** Store Winner Notification**
                Notification.objects.create(
                    user=winner_player,
                    title="🎉 Victoire !",
                    message=f"Félicitations {winner_player.username} ! Vous avez remporté votre match contre {loser_player.username} "
                        f"le {match_time_str}. 🎊 {match_link}Voir les détails du match."
                )    
                 # ** Store Loser Notification**
                Notification.objects.create(
                    user=loser_player,
                    title="⚔️ Fin du tournoi",
                    message=f"Cher {loser_player.username}, malheureusement, vous avez perdu contre {winner_player.username} "
                       f"le {match_time_str}. Merci pour votre participation ! "
                       f"{match_link}Voir les détails du match."
                )
             



                    
                
                if pool.pool_number != "Finale":
                    win_subject = "Félicitations ! Vous avez gagné votre match"
                    win_message = f"""Cher {winner_player.username},

Excellente nouvelle ! Vous avez gagné votre match contre {loser_player.username}.
Vous êtes maintenant qualifié pour le prochain tour.

Continuez sur votre lancée et bonne chance pour le prochain tour !


Cordialement,
L'équipe de Toornoi.com

"""
                    lose_subject = f"Merci d'avoir participé à{match.tournament.tournament_name}"
                    lose_message = f"""Cher {loser_player.username},

Votre parcours dans le tournoi est terminé. Vous avez bien joué, mais malheureusement, vous avez perdu votre match contre  {winner_player.username}.
Nous apprécions votre participation et nous nous réjouissons de vous revoir dans les prochains tournois.
Continuez à vous entraîner et revenez plus fort !


Cordialement,
L'équipe de Toornoi.com

"""
                    send_mail(win_subject, win_message,"contact@toornoi.com",  [winner_player.email])
                    send_mail(lose_subject, lose_message,"contact@toornoi.com",  [loser_player.email])
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
                        position="Championne",
                        prize_value=pool.tournament.positions_1,
                        winner=champion
                    )
                    Prize.objects.create(
                        tournament=pool.tournament,
                        position="deuxième gagnant",
                        prize_value=pool.tournament.positions_2,
                        winner=runner_up
                    )
              
                     # Generate tournament link
                    # tournament_link = f"http://127.0.0.1:8000/tournaments/{tournament.id}/"
                    tournament_link = f"https://toornoi.com/my-account/my-tournaments/{tournament.id}/"

                    # **Store Tournament Winner Notification**
                    Notification.objects.create(
                        user=winner_player,
                        title="🏆 Champion du tournoi !",
                     message=f"Félicitations {winner_player.username} ! Vous êtes le champion de {tournament.tournament_name}. "
                             f"Vous remportez un prix de €{tournament.positions_1}. 🎉 "
                                f"{tournament_link}Voir les détails du tournoi."
                    )
                    # **Store Tournament Loser Notification**
                    Notification.objects.create(
                        user=loser_player,
                        title="🏁 Fin du tournoi",
                        message=f"Cher {loser_player.username}, malheureusement, vous n'avez pas remporté le tournoi {tournament.tournament_name}. "
                                 f"Merci pour votre participation et à bientôt pour un nouveau défi ! "
                                f"{tournament_link}Voir les résultats du tournoi."
                    )

                
                    announcement_subject = f"Félicitations ! Vous êtes le champion de {pool.tournament.tournament_name}"
                    announcement_message = f"""Cher {champion.username},

Vous avez réussi ! Vous êtes le champion de {pool.tournament.tournament_name}.
Prix :  €{pool.tournament.positions_1}

Nous vous contacterons prochainement pour vous communiquer les détails de la distribution du prix.
Encore félicitations pour votre incroyable performance !

Cordialement,
L'équipe de Toornoi.com
"""
                    send_mail(announcement_subject, announcement_message,"contact@toornoi.com",[champion.email])
        if pool.pool_number == "Finale":
            tournament = pool.tournament
            tournament.status = "Complété"
            tournament.save()
        
        return Response({
            "message": "Tous les matches en cours sont finalisés et les notifications sont envoyées.",
            "results": results
        }, status=status.HTTP_200_OK)






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





# for Atheles show  match listing   and submit result on it 
class UserMatchesViewSet(viewsets.ReadOnlyModelViewSet):  # Use ReadOnlyModelViewSet
    queryset = Match.objects.all()
    serializer_class = DisplayMatchSerializer
    permission_classes = [IsAuthenticated]

    
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
            return Response({"error": "Correspondance non trouvée"}, status=status.HTTP_404_NOT_FOUND)

        # Ensure the user is a participant in the match.
        if user not in [match.player_1, match.player_2]:
            return Response({"error": "Vous n'êtes pas autorisé à mettre à jour cette correspondance"}, status=status.HTTP_403_FORBIDDEN)

        # Get the score from the request data.
        score = request.data.get('score')
        if score is None:
            return Response({"error": "Le score est requis"}, status=status.HTTP_400_BAD_REQUEST)

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
                return Response({"error": "Vous avez déjà soumis votre score"}, status=status.HTTP_400_BAD_REQUEST)
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
                return Response({"error": "Vous avez déjà soumis votre score"}, status=status.HTTP_400_BAD_REQUEST)
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


   
    

# user tournament show and register for user

from django.core.mail import send_mail
from django.conf import settings

stripe.api_key = settings.STRIPE_SECRET_KEY

class TournamentsViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Tournament.objects.all()
    serializer_class = GetTournamentSerializer
    # permission_classes = [permissions.IsAuthenticated]
   


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
            
             # **Check if the tournament is full**
            current_registrations = TournamentRegistration.objects.filter(tournament=tournament).count()
            if current_registrations >= tournament.slots:
                return Response({"error": "Ce tournoi est complet. Il n'y a plus de places disponibles."}, status=400) 
             
    
            # Check if user is already registered
            if TournamentRegistration.objects.filter(user=user, tournament=tournament).exists():
                return Response({"error": "Vous êtes déjà inscrit à ce tournoi."}, status=400)

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
           

            # **Register user and create notification in a single transaction**
            # with transaction.atomic():
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
                    subject=f"Paiement reçu pour{tournament.tournament_name}",
                    message=f"Cher {user.username},\n\n"
                            f"Nous avons reçu les frais d'inscription au tournoi pour {tournament.tournament_name}. Thank you for your payment!\n\n"
                            f"- Montant payé: {tournament.registration_fee} EUR\n"
                            f"-  ID de la transaction: {intent.id}\n\n"
                            f"Vous êtes maintenant officiellement inscrit au tournoi. Nous vous informerons lorsque les poules seront créées.\n\n"
                            f"Meilleures salutations, l'équipe de Toornoi.com",
                    from_email="contact@toornoi.com",
                    recipient_list=[user.email],
                    fail_silently=False,
                )
                    # **Create Notification for Payment Success**
                Notification.objects.create(
                        user=user,
                        title="Paiement reçu",
                        message=f"Votre paiement de {tournament.registration_fee} EUR pour le tournoi '{tournament.tournament_name}' a été reçu avec succès. Vous êtes maintenant inscrit.",
                    )

            return Response({
                "message": "Enregistrement du tournoi initié.",
                "payment_status": payment_status,
                "payment_intent_id": intent.id,
                "client_secret": intent.client_secret
            }, status=201)

        except Tournament.DoesNotExist:
            return Response({"error": "Tournoi non trouvé."}, status=404)

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
            logger.info(f"Paiement réussi : {payment_intent['id']}")  # Log the PaymentIntent ID

            try:
                # Find the corresponding TournamentRegistration
                registration = TournamentRegistration.objects.get(
                    stripe_payment_intent_id=payment_intent["id"]
                )
                registration.payment_status = "Paid"
                registration.save()
                logger.info(f"Enregistrement mis à jour pour cette tentative de paiement: {payment_intent['id']}")
            except TournamentRegistration.DoesNotExist:
                logger.error(f"Enregistrement non trouvé pour cette tentative de paiement: {payment_intent['id']}")
                return JsonResponse({"error": "Enregistrement non trouvé"}, status=404)

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
    permission_classes = [IsAuthenticated]


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
    permission_classes = [IsAuthenticated]
    # permission_classes = [IsAuthenticated]


    def perform_create(self, serializer):
        # Save the claim with the authenticated user.
        claim = serializer.save(user=self.request.user)

        # --- Email to Admins ---
        admin_subject = f"Nouvelle réclamation soumise : {claim.subject}"
        admin_message = (
            f"Une nouvelle réclamation a été soumise par {claim.user.username}.\n\n"
            f"Numéro de téléphone: {claim.phone_number}\n"
            f"Sujet: {claim.subject}\n"
            f"Détails : {claim.details}\n\n"
            f"Voir la réclamation dans le panneau d'administration."
        )
        admin_emails = list(User.objects.filter(is_superuser=True).values_list('email', flat=True))
        if admin_emails:
            send_mail(admin_subject, admin_message, "contact@toornoi.com", admin_emails)

        # --- Confirmation Email to User ---
        support_email = admin_emails[0] if admin_emails else "contact@toornoi.com"
        user_subject = "Nous avons reçu votre demande de réclamation"
        user_message = f"""Cher {claim.user.username},

Nous avons bien reçu votre demande concernant "{claim.subject}". Notre équipe examinera votre demande et vous répondra dès que possible.


Pour les demandes urgentes, veuillez contacter le service d'assistance à l'adresse suivante {support_email}.

Cordialement,
L'équipe de toornoi.com

"""
        send_mail(user_subject, user_message,"contact@toornoi.com", [claim.user.email])
        
         # --- Create Notification for the User ---
        Notification.objects.create(
            user=claim.user,
            title="📢 Réclamation reçue",
            message=f"Votre réclamation sur \"{claim.subject}\" a été soumise avec succès. Nous la traiterons bientôt."
        )
        
        
        # Get the first superuser (admin)
        admin_user = User.objects.filter(is_superuser=True).first()

        if admin_user:  # Ensure an admin exists before creating the notification
            Notification.objects.create(
                user=admin_user,  # ✅ Use the User instance directly
                title="🛠 Nouvelle réclamation",
                message=f"{claim.user.username} a soumis une nouvelle réclamation : \"{claim.subject}\"."
            )

        

    @action(detail=True, methods=['post'], url_path='update-claim-status')
    def update_claim_status(self, request, pk=None):
        """
        Updates the claim_status from 'Pending' to 'Resolved' and notifies the user.
        """
        try:
            claim = self.get_object()

            # Check if claim is already resolved
            if claim.claim_status == "Résolu":
                return Response({"message": "La réclamation est déjà résolue."}, status=status.HTTP_400_BAD_REQUEST)

            # Update claim status
            claim.claim_status = "Résolu"
            claim.save()

            # Send resolution email to user
            subject = "Mise à jour de la résolution de la réclamation"
            message = f"""Cher {claim.user.username},

Votre réclamation concernant "{claim.subject}"  a été examinée.

Résolution: {claim.details}.

Si vous avez d'autres questions, n'hésitez pas à nous contacter.

Cordialement,  
L'équipe de Toornoi.com

"""
            send_mail(subject, message,"contact@toornoi.com", [claim.user.email])
            
             # --- Create a notification for the user ---
            Notification.objects.create(
                user=claim.user,
                title="✅ Réclamation Résolue",
                message=f"Votre réclamation sur \"{claim.subject}\" a été résolue. Consultez votre e-mail pour plus de détails."
            )

            return Response({"message": "L'état de la réclamation a été mis à jour et l'e-mail a été envoyé avec succès."}, status=status.HTTP_200_OK)

        except Claim.DoesNotExist:
            return Response({"error": "Réclamation non trouvée."}, status=status.HTTP_404_NOT_FOUND)
        

            
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
            raise PermissionDenied("Vous n'êtes pas autorisé à voir les chats de ce match.")
        return MatchChat.objects.filter(match=match).order_by('timestamp')

    def perform_create(self, serializer):
        match_id = self.kwargs.get('match_pk')
        match = get_object_or_404(Match, id=match_id)
        # Only allow message creation if the request user is a participant in the match.
        if self.request.user not in [match.player_1, match.player_2]:
            raise PermissionDenied("Vous n'êtes pas autorisé à envoyer des messages dans ce match.")
        message_instance = serializer.save(match=match, sender=self.request.user)
        
        # Optionally, notify the other participant.
        # Determine the "other" user:
        other_user = match.player_1 if self.request.user != match.player_1 else match.player_2
        
          # Create a notification for the recipient
        Notification.objects.create(
        user=other_user,
        title="📩 Nouveau message",
        message=f"Vous avez reçu un nouveau message de {self.request.user.username}."
    )
       
       
        # Mark all messages in a match as read
    @action(detail=False, methods=['post'], url_path='mark_as_read')
    def mark_as_read(self, request, match_pk=None):
        """Marks only the other user's messages as read."""
        match = get_object_or_404(Match, id=match_pk)

        # Ensure the user is a participant in the match
        if request.user not in [match.player_1, match.player_2]:
         return Response({"error": "Vous n'êtes pas un participant à ce match."}, status=status.HTTP_403_FORBIDDEN)

        # Use `exclude()` instead of an invalid '__ne' lookup
        updated_count = MatchChat.objects.filter(
        match=match, 
        is_read=False
        ).exclude(sender=request.user).update(is_read=True)

        return Response({"message": f"{updated_count} messages marqués comme lus."}, status=status.HTTP_200_OK)

          
        
        
        
        
 # For admin panel show  total number of  claim    
class TotalclaimViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]
    def list(self, request):
        # Exclude the first user by ID and count the rest
        total_claim = Claim.objects.all().count()
        
        # Return the total number of users as a response
        return Response({"total_claim": total_claim})     
  
 # for get user dashboard  get user claim list  
class UserclaimViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint that returns only the claims of the authenticated user.
    """
    serializer_class = ClaimSerializer
    permission_classes = [IsAuthenticated]
    # permission_classes = [permissions.IsAuthenticated]  # Ensures only logged-in users can access

    def get_queryset(self):
        """
        Return only the claims of the currently authenticated user.
        """
        return Claim.objects.filter(user=self.request.user)  # Assuming Claim model has a ForeignKey to User
  
#total number of tournaments a user has participated  in user profile list  
class UserTournamentCountView(APIView):
    permission_classes = [IsAuthenticated] 
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
    # permission_classes = [IsAuthenticated]
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
            final_match = Match.objects.filter(pool=final_pool, status="Complété").order_by('-id').first()
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
    
    @action(detail=True, methods=['post'])
    def mark_as_read(self, request, pk=None):
        """
        Mark a notification as read when clicked.
        """
        try:
            notification = self.get_object()
            notification.is_read = True
            notification.save()
            return Response({"message": "Notification marquée comme lue."}, status=status.HTTP_200_OK)
        except Notification.DoesNotExist:
            return Response({"error": "Notification introuvable."}, status=status.HTTP_404_NOT_FOUND)       
    
    
    
#only returns list  tournaments where is_publish=True
class PublishedTournamentViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint that returns only published tournaments (is_publish=True).
    """
    # Optionally add permission_classes = [IsAuthenticated]
    queryset = Tournament.objects.filter(is_publish=True)
    serializer_class = TournamentSerializer   
    # permission_classes = [IsAuthenticated] 
    
    
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
            
            subject = f"Nouveau formulaire de contact soumis par {name}"
            email_message = f"Name: {name}\nEmail: {email}\nMessage:\n{message}"
            
            # Retrieve admin email addresses.
            admin_emails = list(User.objects.filter(is_superuser=True).values_list('email', flat=True))
            if not admin_emails:
                logger.warning("Aucun administrateur n'a été trouvé pour envoyer l'email du formulaire de contact..")
                return Response({"error": "Aucun administrateur disponible."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
            try:
                send_mail(subject, email_message,"contact@toornoi.com", admin_emails)
                logger.info("Formulaire de contact envoyé à l'administrateur(s): %s", admin_emails)
            except Exception as e:
                logger.error("Erreur d'envoi du formulaire de contact: %s", e)
                return Response({"error": "Erreur lors de l'envoi de l'e-mail."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
            return Response({"message": "Votre message a été envoyé avec succès."}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)  
    
    
    
 
class PrizeViewSet(viewsets.ModelViewSet):
    queryset = Prize.objects.all()
    permission_classes = [IsAuthenticated]


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
            if prize.trans_payment_status == "payé":
                return Response({"message": "Le paiement est déjà effectué."}, status=status.HTTP_400_BAD_REQUEST)

            # Update status to 'paid'
            prize.trans_payment_status = "payé"
            prize.save()

            # Send email notification
            user_email = prize.winner.email  # Assuming 'winner' is a ForeignKey to User model
            subject = "Le paiement de votre prix a été effectué avec succès"
            message = "Nous vous félicitons ! Le paiement de votre prix a été transféré avec succès sur votre compte.."
            send_mail(subject, message, "contact@toornoi.com", [user_email])
            
            
              # **Create Notification**
            Notification.objects.create(
                user=prize.winner,
                title="💰 Paiement du prix reçu !",
                message=f"Félicitations {prize.winner.username} ! Votre paiement a été transféré avec succès sur votre compte. 🎉"
            )


            return Response({"message": "L'état du paiement a été mis à jour et l'e-mail a été envoyé avec succès.."}, status=status.HTTP_200_OK)

        except Prize.DoesNotExist:
            return Response({"error": "Le prix n'a pas été trouvé.."}, status=status.HTTP_404_NOT_FOUND)