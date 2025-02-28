from rest_framework import serializers
from toornoi_user_management.models import User
from .models import  Claim, MatchChat, Tournament,Match, TournamentRegistration,Pool
from django.contrib.auth import get_user_model

# for admin panel 


class TournamentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tournament
        fields = '__all__'  # Include all tournament fields
from .models import Tournament, TournamentRegistration

class GetTournamentSerializer(serializers.ModelSerializer):
    payment_status = serializers.SerializerMethodField()
    is_registered = serializers.SerializerMethodField()

    class Meta:
        model = Tournament
        fields = '__all__'  # Include all tournament fields

    def get_payment_status(self, obj):
        """Fetch the payment status of the logged-in user for this tournament."""
        user = self.context.get('request').user
        if not user or not user.is_authenticated:
            return None

        registration = TournamentRegistration.objects.filter(user=user, tournament=obj).first()
        return registration.payment_status if registration else None

    def get_is_registered(self, obj):
        """Check if the user is registered for the tournament."""
        user = self.context.get('request').user
        if not user or not user.is_authenticated:
            return False

        return TournamentRegistration.objects.filter(user=user, tournament=obj).exists()



# for admin panel 

# class TournamentRegistrationSerializer(serializers.ModelSerializer):
#     class Meta:
#         model = TournamentRegistration
#         fields = '__all__'
class TournamentRegistrationSerializer(serializers.ModelSerializer):
    username = serializers.SerializerMethodField()
    tournament_name = serializers.SerializerMethodField()

    class Meta:
        model = TournamentRegistration
        fields= '__all__'
        # fields = ['id', 'payment_status', 'registered_at', 'username', 'tournament_name']

    def get_username(self, obj):
        return obj.user.username

    def get_tournament_name(self, obj):
        return obj.tournament.tournament_name



#update code  start
# Create a nested serializer for Tournament to include the extra fields.
class TournamentNestedSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tournament
        fields = (
            # 'id',
            'tournament_name',  # if you want to display the tournament name
            'sponsorship_details',
            'description',
            'region',
            'rules_and_regulations',
            'country',
            'bracket_type',
        )
     
 #for admin panel  create match 
User = get_user_model()

class DisplayMatchSerializer(serializers.ModelSerializer):
    tournament = TournamentNestedSerializer()  # Use the nested serializer
    # tournament = serializers.StringRelatedField()  # Display the tournament name
    player_1 = serializers.CharField(source='player_1.username')  # Display player 1's username
    player_2 = serializers.CharField(source='player_2.username')  # Display player 2's username
    player_1_photo = serializers.SerializerMethodField()
    player_2_photo = serializers.SerializerMethodField()
    admin_username = serializers.SerializerMethodField()
    winner = serializers.CharField(source='winner.username', allow_null=True)  # Display winner's username
    result = serializers.JSONField()  # Display the JSON result as is

    class Meta:
        model = Match
        fields = '__all__'
    
    def get_player_1_photo(self, obj):
        if hasattr(obj.player_1, 'photo') and obj.player_1.photo:
            request = self.context.get("request")
            if request:
                return request.build_absolute_uri(obj.player_1.photo.url)
            return obj.player_1.photo.url
        return None

    def get_player_2_photo(self, obj):
        if hasattr(obj.player_2, 'photo') and obj.player_2.photo:
            request = self.context.get("request")
            if request:
                return request.build_absolute_uri(obj.player_2.photo.url)
            return obj.player_2.photo.url
        return None    
    def get_admin_username(self, obj):
        # Fetch one admin (you could also return a list if needed)
        admin = User.objects.filter(is_superuser=True).first()
        return admin.username if admin else None
        
#update code  end  



class MatchSerializer(serializers.ModelSerializer):
    class Meta:
        model = Match
        fields = '__all__'
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Only adjust the queryset for write operations (POST, PUT, PATCH)
        request = self.context.get("request")
        if request and request.method in ['POST', 'PUT', 'PATCH']:
            # Check if initial_data exists (it will for write operations)
            if hasattr(self, 'initial_data') and self.initial_data:
                tournament_id = self.initial_data.get("tournament")
                if tournament_id:
                    try:
                        tournament = Tournament.objects.get(id=tournament_id)
                        # Get only the registered users with payment_status set to "paid"
                        reg_ids = TournamentRegistration.objects.filter(
                            tournament=tournament, payment_status="paid"
                        ).values_list("user", flat=True)
                        registered_users = User.objects.filter(id__in=reg_ids)
                        
                        # Restrict the queryset for player and winner fields
                        self.fields["player_1"].queryset = registered_users
                        self.fields["player_2"].queryset = registered_users
                        self.fields["winner"].queryset = registered_users
                    except Tournament.DoesNotExist:
                        pass

    def validate(self, data):
        # Custom validation: Ensure player_1 and player_2 are not the same
        if data["player_1"] == data["player_2"]:
            raise serializers.ValidationError("Player 1 and Player 2 cannot be the same.")
        return data
# class DisplayMatchSerializer(serializers.ModelSerializer):
#     tournament = serializers.StringRelatedField()  # Display the tournament name
#     player_1 = serializers.CharField(source='player_1.username')  # Display player 1's username
#     player_2 = serializers.CharField(source='player_2.username')  # Display player 2's username
#     winner = serializers.CharField(source='winner.username', allow_null=True)  # Display winner's username (allow null if no winner)
#     result = serializers.JSONField()               # Display the JSON result as is

#     class Meta:
#         model = Match
#         fields = '__all__'
        
# class MatchSerializer(serializers.ModelSerializer):
    
#     class Meta:
#         model=Match
#         fields= '__all__'
#     def validate(self, data):
#         # Custom validation: Ensure player_1 and player_2 are not the same
#         if data['player_1'] == data['player_2']:
#             raise serializers.ValidationError("Player 1 and Player 2 cannot be the same.")
#         return data



class DisplayPoolSerializer(serializers.ModelSerializer):
     # This field is read-only and can be used to display the total number of athletes/winners for the pool.
    total_participants = serializers.IntegerField(read_only=True)
    tournament = serializers.StringRelatedField()  # Display the tournament name
    class Meta:
        model = Pool
        fields = ['id', 'tournament', 'pool_number', 'start_date', 'end_date', 'total_participants']
        
class PoolSerializer(serializers.ModelSerializer):
    # This field is read-only and can be used to display the total number of athletes/winners for the pool.
    total_participants = serializers.IntegerField(read_only=True)

    class Meta:
        model = Pool
        fields = ['id', 'tournament', 'pool_number', 'start_date', 'end_date', 'total_participants']


   

#for admin  show all athletes and admin will have that ption to delete or manage any athlete profile….

class AthletesSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id','username','first_name','last_name','date_of_birth','email','password','phone_number','is_verified','is_active']
        
        
 
 
# for showing in user profile list  matches Achievements  ,lose and pending matches 
User = get_user_model()

class UserMatchSerializer(serializers.ModelSerializer):
    tournament = serializers.StringRelatedField()  # Shows tournament name
    player_1 = serializers.CharField(source='player_1.username')
    player_2 = serializers.CharField(source='player_2.username')
    winner = serializers.SerializerMethodField()  # Returns winner's username (if available)
    match_result = serializers.SerializerMethodField()  # "Win", "Lose", or "Pending"

    class Meta:
        model = Match
        fields = ('id', 'tournament', 'player_1', 'player_2', 'winner', 'date', 'status', 'match_result')

    def get_winner(self, obj):
        return obj.winner.username if obj.winner else None

    def get_match_result(self, obj):
        """
        Determine the match result for the current (logged-in) user:
          - If match is not complete, return "Pending"
          - If complete, return "Win" if the current user is the winner; otherwise "Lose"
        """
        request = self.context.get("request")
        if not request:
            return None
        user = request.user
        # Ensure that the user is a participant in this match.
        if user != obj.player_1 and user != obj.player_2:
            return "Not Participating"
        if obj.status != "Completed":
            return "Pending"
        return "Win" if obj.winner and obj.winner == user else "Lose"
 
 
 
 
# Serializer for chat messages in a match
class MatchChatSerializer(serializers.ModelSerializer):
    sender = serializers.ReadOnlyField(source='sender.username')
    match = serializers.PrimaryKeyRelatedField(read_only=True)  # Mark match as read-only
    
    class Meta:
        model = MatchChat
        fields = ['id', 'match', 'sender', 'message', 'timestamp']
       

class ClaimSerializer(serializers.ModelSerializer):
    # The user field is read-only and displays the username.
    user = serializers.ReadOnlyField(source='user.username')

    class Meta:
        model = Claim
        fields = ['id', 'user', 'phone_number', 'subject', 'details', 'created_at']