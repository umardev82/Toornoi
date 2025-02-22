from rest_framework import serializers
from toornoi_user_management.models import User
from .models import Stage, Tournament,Match, TournamentRegistration


# for admin panel 


class TournamentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tournament
        fields = '__all__'  # Include all tournament fields



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


 #for admin panel  create match 
class DisplayMatchSerializer(serializers.ModelSerializer):
    tournament = serializers.StringRelatedField()  # Display the tournament name
    player_1 = serializers.CharField(source='player_1.username')  # Display player 1's username
    player_2 = serializers.CharField(source='player_2.username')  # Display player 2's username
    winner = serializers.CharField(source='winner.username', allow_null=True)  # Display winner's username (allow null if no winner)
    result = serializers.JSONField()               # Display the JSON result as is

    class Meta:
        model = Match
        fields = '__all__'
        
class MatchSerializer(serializers.ModelSerializer):
    class Meta:
        model=Match
        fields= '__all__'

    def validate(self, data):
        # Custom validation: Ensure player_1 and player_2 are not the same
        if data['player_1'] == data['player_2']:
            raise serializers.ValidationError("Player 1 and Player 2 cannot be the same.")
        return data



# for admin Stage Serializer
class StageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Stage
        fields = '__all__'

    def validate(self, data):
        """
        Ensure end_date is after start_date.
        """
        if data['end_date'] <= data['start_date']:
            raise serializers.ValidationError("End date must be after start date.")
        return data
    
# for admin DisplayStageSerializer
class DisplayStageSerializer(serializers.ModelSerializer):
    tournament = serializers.StringRelatedField()  # Show tournament name instead of ID

    class Meta:
        model = Stage
        fields = '__all__'


#for admin  show all athletes and admin will have that ption to delete or manage any athlete profile….

class AthletesSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id','username','first_name','last_name','date_of_birth','email','password','phone_number','is_verified','is_active']
        
        
        

