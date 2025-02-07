
from rest_framework import viewsets,permissions
from .models import Stage, Tournament,Match,TournamentRegistration
from .serializers import DisplayMatchSerializer, DisplayStageSerializer, StageSerializer, TournamentSerializer,MatchSerializer
import stripe
from rest_framework.decorators import action
from rest_framework.response import Response
from django.conf import settings

# for admin panel 
class Tournamentviewset(viewsets.ModelViewSet):
    """
    A ViewSet for viewing and editing tournament instances.
    """
    queryset=Tournament.objects.all()
    serializer_class=TournamentSerializer


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
        
        
class StageViewSet(viewsets.ModelViewSet):
    queryset = Stage.objects.all()

    def get_serializer_class(self):
        """ Use DisplayStageSerializer for listing, StageSerializer for create/update """
        if self.action == 'list' or self.action == 'retrieve':
            return DisplayStageSerializer
        return StageSerializer   
    

# user tournament show and register for user



stripe.api_key = settings.STRIPE_SECRET_KEY

class TournamentsViewSet(viewsets.ReadOnlyModelViewSet):  # Use ReadOnlyModelViewSet to disable create/update/delete
    queryset = Tournament.objects.all()
    serializer_class = TournamentSerializer
    permission_classes = [permissions.AllowAny]

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def register(self, request, pk=None):
        try:
            tournament = self.get_object()
            user = request.user

            # Check if user is already registered
            if TournamentRegistration.objects.filter(user=user, tournament=tournament).exists():
                return Response({"error": "You are already registered for this tournament."}, status=400)

            # Create Stripe payment intent
            
            amount = int(tournament.registration_fee * 100)  # Convert to cents
            intent = stripe.PaymentIntent.create(
            amount=amount,
            currency="usd",  # Change to your currency
            customer=user.stripe_customer_id if hasattr(user, 'stripe_customer_id') else None,
            payment_method=request.data.get("payment_method_id"),
            confirm=True,
            automatic_payment_methods={
                "enabled": True,
                "allow_redirects": "never",  # Optionally disable redirects
            },
            metadata={"tournament_id": tournament.id, "user_id": user.id}
            )


            # Register user in the tournament with "Pending" payment status
            registration = TournamentRegistration.objects.create(
                user=user,
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

import stripe
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from .models import TournamentRegistration  # Adjust the import if necessary

stripe.api_key = settings.STRIPE_SECRET_KEY

@csrf_exempt
def stripe_webhook(request):
    payload = request.body.decode('utf-8')
    sig_header = request.META['HTTP_STRIPE_SIGNATURE']
    event = None

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_ENDPOINT_SECRET
        )
    except ValueError as e:
        return JsonResponse({'error': str(e)}, status=400)
    except stripe.error.SignatureVerificationError as e:
        return JsonResponse({'error': 'Webhook signature verification failed.'}, status=400)

    # Handle the event
    if event['type'] == 'payment_intent.succeeded':
        payment_intent = event['data']['object']
        # Payment was successful, update registration status
        registration = TournamentRegistration.objects.get(
            stripe_payment_intent_id=payment_intent['id']
        )
        registration.payment_status = 'Paid'
        registration.save()

    return JsonResponse({'status': 'success'}, status=200)
