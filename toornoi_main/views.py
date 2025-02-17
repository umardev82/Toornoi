
from rest_framework import viewsets,permissions
from toornoi_user_management.models import User
from .models import Stage, Tournament,Match,TournamentRegistration
from .serializers import DisplayMatchSerializer, DisplayStageSerializer, StageSerializer, TournamentRegistrationSerializer, TournamentSerializer,MatchSerializer,AthletesSerializer
import stripe
from rest_framework.decorators import action
from rest_framework.response import Response
from django.conf import settings
from django.shortcuts import get_object_or_404
# for admin panel 
class Tournamentviewset(viewsets.ModelViewSet):
    queryset=Tournament.objects.all()
    serializer_class=TournamentSerializer


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
        
        serializer = MatchSerializer(matches, many=True)
        return Response(serializer.data) 
        
        
class StageViewSet(viewsets.ModelViewSet):
    queryset = Stage.objects.all()

    def get_serializer_class(self):
        """ Use DisplayStageSerializer for listing, StageSerializer for create/update """
        if self.action == 'list' or self.action == 'retrieve':
            return DisplayStageSerializer
        return StageSerializer   
    

# user tournament show and register for user
class TournamentsViewSet(viewsets.ReadOnlyModelViewSet):  
    queryset = Tournament.objects.all()
    serializer_class = TournamentSerializer
    permission_classes = [permissions.AllowAny]

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def register(self, request, pk=None):
        tournament = get_object_or_404(Tournament, pk=pk)
        user = request.user

        # Check if user is already registered
        if TournamentRegistration.objects.filter(user=user, tournament=tournament).exists():
            return Response({"error": "You are already registered for this tournament."}, status=400)

        # Create a registration record with Pending status
        registration = TournamentRegistration.objects.create(
            user=user,
            tournament=tournament,
            payment_status="Pending"
        )

        # Return the SumUp payment link
        return Response({
            "message": "Registration successful. Proceed to payment.",
            "sumup_link": tournament.sumup_link
        }, status=201)


          