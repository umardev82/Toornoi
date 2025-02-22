
from rest_framework import viewsets,permissions
from toornoi_user_management.models import User
from .models import Stage, Tournament,Match,TournamentRegistration
from .serializers import DisplayMatchSerializer, DisplayStageSerializer, StageSerializer, TournamentRegistrationSerializer, TournamentSerializer,MatchSerializer,AthletesSerializer
import stripe
from rest_framework.decorators import action
from rest_framework.response import Response
from django.conf import settings
from rest_framework import status
import requests

from django.shortcuts import get_object_or_404
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
    
# For admin panel to show and update Registered Athletes 
class RegisterAthletesShowViewSet(viewsets.ModelViewSet):
    queryset = TournamentRegistration.objects.all()
    serializer_class = TournamentRegistrationSerializer
  
     
     

class MatchViewSet(viewsets.ModelViewSet):
    queryset = Match.objects.all()
    
    # Use DisplayMatchSerializer for listing matches
    def get_serializer_class(self):
        if self.action == 'list':
            return DisplayMatchSerializer
        return MatchSerializer

    def perform_create(self, serializer):
        # Any custom logic during creation (you can add extra logic here if needed)
        serializer.save()
 
 
class UserMatchesViewSet(viewsets.ViewSet):
    # permission_classes = [permissions.IsAuthenticated]

    @action(detail=False, methods=['get'])
    def my_matches(self, request):
        user = request.user
        
        # Get tournaments where the user is registered
        registered_tournaments = TournamentRegistration.objects.filter(user=user).values_list('tournament', flat=True)
        
        # Get matches for those tournaments
        matches = Match.objects.filter(tournament__id__in=registered_tournaments)
        
        serializer = DisplayMatchSerializer(matches, many=True)
        return Response(serializer.data) 
        
 
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

        # ✅ Corrected Query
        tournaments = Tournament.objects.filter(registrations__user=user).distinct()

        serializer = TournamentSerializer(tournaments, many=True)
        return Response(serializer.data, status=200)

 #StageViewSet       
class StageViewSet(viewsets.ModelViewSet):
    queryset = Stage.objects.all()

    def get_serializer_class(self):
        """ Use DisplayStageSerializer for listing, StageSerializer for create/update """
        if self.action == 'list' or self.action == 'retrieve':
            return DisplayStageSerializer
        return StageSerializer   
    

# user tournament show and register for user
# Set Stripe API key
stripe.api_key = settings.STRIPE_SECRET_KEY

class TournamentsViewSet(viewsets.ReadOnlyModelViewSet):  # Read-only for listing
    queryset = Tournament.objects.all()
    serializer_class = TournamentSerializer
    # permission_classes = [permissions.AllowAny]

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

stripe.api_key = settings.STRIPE_SECRET_KEY
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

        if event["type"] == "payment_intent.succeeded":
            payment_intent = event["data"]["object"]
            logger.info(f"PaymentIntent succeeded: {payment_intent['id']}")  # Log the PaymentIntent ID

            try:
                registration = TournamentRegistration.objects.get(
                    stripe_payment_intent_id=payment_intent["id"]
                )
                registration.payment_status = "Paid"
                registration.save()
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


          