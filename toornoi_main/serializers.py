import datetime
from rest_framework import serializers
from toornoi_user_management.models import User
from .models import  Claim, MatchChat, Notification, Prize, Tournament,Match, TournamentRegistration,Pool
from django.contrib.auth import get_user_model

# for admin panel 

#  user dashboard  /my_tournaments/my_tournaments
class MyTournamentUsersSerializer(serializers.ModelSerializer):
    pool_number = serializers.SerializerMethodField()
    total_pool = serializers.SerializerMethodField()
    class Meta:
        model = Tournament
        fields = '__all__'  # Include all tournament fields
        
    def get_pool_number(self, obj):
        """Get the latest (highest) pool_number for the tournament."""
        pool = Pool.objects.filter(tournament=obj).order_by('-pool_number').first()
        return pool.pool_number if pool else None

    def get_total_pool(self, obj):
        pool = Pool.objects.filter(tournament=obj).order_by('pool_number').first()
        return pool.total_pool if pool else 0  # Default to 0 if no pool exists    
        
 
        
class TournamentSerializer(serializers.ModelSerializer):
    
    class Meta:
        model = Tournament
        fields = '__all__'  # Include all tournament fields
    def validate(self, data):
        start_date = data.get("start_date")
        end_date = data.get("end_date")
        registration_deadline = data.get("registration_deadline")

        # Convert to date (to avoid TypeError)
        if start_date:
            start_date = start_date.date() if isinstance(start_date, datetime.datetime) else start_date
        if end_date:
            end_date = end_date.date() if isinstance(end_date, datetime.datetime) else end_date
        if registration_deadline:
            registration_deadline = registration_deadline.date() if isinstance(registration_deadline, datetime.datetime) else registration_deadline

        # Validate start_date < end_date
        if start_date and end_date:
            if start_date >= end_date:
                raise serializers.ValidationError({"start_date": "Start date must be before the end date."})

        # Validate registration_deadline < start_date
        if registration_deadline and start_date:
            if registration_deadline >= start_date:
                raise serializers.ValidationError({"registration_deadline": "Registration deadline must be before the start date."})

        return data
        
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



User = get_user_model()

class DisplayPoolSerializer(serializers.ModelSerializer):
    
    winner_players = serializers.SerializerMethodField()
    loser_players = serializers.SerializerMethodField()
    tournament = serializers.StringRelatedField()  # Display the tournament name
    all_players=serializers.SerializerMethodField()
    class Meta:
        model = Pool
        fields = ['id', 'tournament', 'pool_number', 'start_date', 'end_date', 'total_participants','total_pool','winner_players','loser_players', 'all_players'] 
           
    def get_winner_players(self, obj):
        """
        Returns a list of usernames for players who won their matches in this pool.
        Only matches with status "Completed" and a non-null winner are considered.
        """
        winners = []
        matches = obj.matches.filter(status="Completed")
        for match in matches:
            if match.winner:
                winners.append(match.winner.username)
        return winners

    def get_loser_players(self, obj):
        """
        Returns a list of usernames for players who lost their matches in this pool.
        For each completed match, the loser is the player who is not the winner.
        """
        losers = []
        matches = obj.matches.filter(status="Completed")
        for match in matches:
            if match.winner:
                # Determine the loser: if player_1 is the winner, then player_2 lost, and vice versa.
                if match.winner == match.player_1:
                    losers.append(match.player_2.username)
                else:
                    losers.append(match.player_1.username)
        return losers
    

    
    def get_all_players(self, obj):
        """
        Returns a list of all player usernames in this pool:
         - Includes players from all matches (both player_1 and player_2)
         - Also includes athletes who received a bye (stored in pool.result["bye"])
        """
        players_set = set()
        # Include players from matches.
        for match in obj.matches.all():
            if match.player_1:
                players_set.add(match.player_1.username)
            if match.player_2:
                players_set.add(match.player_2.username)
        # Also include bye players.
        if isinstance(obj.result, dict):
            bye_ids = obj.result.get("bye", [])
            if bye_ids:
                bye_users = User.objects.filter(id__in=bye_ids).values_list('username', flat=True)
                players_set.update(bye_users)
        # Return sorted list if desired.
        return sorted(list(players_set))
        
class PoolSerializer(serializers.ModelSerializer):
    # This field is read-only and can be used to display the total number of athletes/winners for the pool.
    # total_participants = serializers.IntegerField(read_only=True)

    class Meta:
        model = Pool
        # fields='__all__'
        fields = ['id', 'tournament', 'pool_number', 'start_date', 'end_date', 'total_participants','total_pool']
    def validate(self, data):
        start_date = data.get("start_date")
        end_date = data.get("end_date")
        if start_date and end_date:
            if start_date >= end_date:
                raise serializers.ValidationError({"start_date": "Start date must be before the end date."})
        return data


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
    player_1 = serializers.CharField(source='player_1.username')  # Display player 1's username
    player_2 = serializers.CharField(source='player_2.username')  # Display player 2's username
    player_1_photo = serializers.SerializerMethodField()
    player_2_photo = serializers.SerializerMethodField()
    admin_username = serializers.SerializerMethodField()
    pool = serializers.CharField(source='pool.pool_number', read_only=True)
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





   

#for admin  show all athletes and admin will have that ption to delete or manage any athlete profile….

class AthletesSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id','username','first_name','last_name','date_of_birth','email','password','phone_number','is_verified','is_active']
        
        
 
 
# for showing in user profile list  matches Achievements  ,lose and pending matches 
User = get_user_model()

# Create a nested serializer for Tournament to include the extra fields.
# class TournamentsNestedSerializer(serializers.ModelSerializer):
#     class Meta:
#         model = Tournament
#         fields = (
#             # 'id',
#             'cover_image',
             
#         )  
        
           

class UserMatchSerializer(serializers.ModelSerializer):
    tournament = serializers.StringRelatedField()  # Shows tournament name
    
    cover_image = serializers.ImageField(source='tournament.cover_image', read_only=True)
    player_1 = serializers.CharField(source='player_1.username')
    player_2 = serializers.CharField(source='player_2.username')
    winner = serializers.SerializerMethodField()  # Returns winner's username (if available)
    match_result = serializers.SerializerMethodField()  # "Win", "Lose", or "Pending"

    class Meta:
        model = Match
        fields = ('id', 'tournament', 'player_1', 'player_2','winner','cover_image', 'date', 'status', 'match_result')

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
# class MatchChatSerializer(serializers.ModelSerializer):
#     sender = serializers.ReadOnlyField(source='sender.username')
#     match = serializers.PrimaryKeyRelatedField(read_only=True)  # Mark match as read-only
    
#     class Meta:
#         model = MatchChat
#         fields = ['id', 'match', 'sender', 'message', 'timestamp']

class MatchChatSerializer(serializers.ModelSerializer):
    sender = serializers.ReadOnlyField(source='sender.username')
    sender_photo = serializers.SerializerMethodField()
    match = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = MatchChat
        fields = ['id', 'match', 'sender', 'sender_photo', 'message', 'timestamp']

    def get_sender_photo(self, obj):
        """
        Returns the absolute URL of the sender's photo if available.
        """
        request = self.context.get("request")
        if hasattr(obj.sender, 'photo') and obj.sender.photo:
            if request:
                return request.build_absolute_uri(obj.sender.photo.url)
            return obj.sender.photo.url
        return None
       

class ClaimSerializer(serializers.ModelSerializer):
    # The user field is read-only and displays the username.
    user = serializers.ReadOnlyField(source='user.username')

    class Meta:
        model = Claim
        fields = ['id', 'user', 'phone_number', 'subject', 'details','image', 'claim_status','created_at']
       
       
        
class UserTournamentCountSerializer(serializers.Serializer):
    total_tournaments=serializers.IntegerField()    
    

class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        # fields = '__all__'
        fields = ['id', 'title', 'message', 'created_at', 'is_read']        
        
        
#Contact Form submit Serializer     
class ContactFormSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255)
    email = serializers.EmailField()
    message = serializers.CharField()       


#prize serializer
class PrizeDisplaySerializer(serializers.ModelSerializer):
    tournament=serializers.StringRelatedField()
    winner=serializers.CharField(source='winner.username')
    class Meta:
        model=Prize   
        fields= '__all__'   
class PrizeSerializer(serializers.ModelSerializer):
    class Meta:
        model=Prize   
        fields= '__all__'     
        
        