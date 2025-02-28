from django.db import models

from toornoi_user_management.models import User
from django.contrib.auth import get_user_model
from decimal import Decimal

# for admin panel 

    
class Tournament(models.Model):
    
    tournament_name = models.CharField(max_length=255)
    description = models.TextField(null=True, blank=True)
    cover_image = models.ImageField(upload_to='tournaments/cover_image/', null=True, blank=True)
    category = models.CharField(max_length=255,null=True, blank=True)
    registration_deadline = models.DateTimeField(null=True, blank=True)
    registration_fee = models.CharField(max_length=100,blank=True,null=True)
    slots = models.IntegerField(null=True, blank=True)
    status = models.CharField(max_length=255, default='Pending')
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    time = models.TimeField(null=True, blank=True)
    bracket_type = models.CharField(max_length=255,null=True, blank=True)
    eligibility_criteria = models.TextField(null=True, blank=True)
    country = models.CharField(max_length=255,null=True, blank=True)
    region = models.CharField(max_length=255,null=True, blank=True)
    rules_and_regulations = models.TextField(null=True, blank=True)
    code_of_conduct = models.FileField(upload_to='tournaments/conduct/', null=True, blank=True)
    match_rules = models.TextField(null=True, blank=True)
    prize_details =models.TextField(null=True, blank=True)
    dispute_resolution_Process = models.TextField(null=True, blank=True)
    prize_distribution = models.TextField(null=True, blank=True)
    positions_1 = models.TextField(null=True, blank=True)
    positions_2 = models.TextField(null=True, blank=True)
    positions_3 = models.TextField(null=True, blank=True)
    sponsorship_details = models.TextField(null=True, blank=True)
    sponsor_logos = models.ImageField(upload_to='tournaments/sponsors_logo/', null=True, blank=True)

    partnership_info = models.TextField(null=True, blank=True)
    refund_policy = models.TextField(null=True, blank=True)

    def __str__(self):
        return self.tournament_name
    
 #TournamentRegistration   
User = get_user_model()

class TournamentRegistration(models.Model):
    PAYMENT_STATUS_CHOICES = [
        ("Pending", "Pending"),
        ("Paid", "Paid"),
        ("Failed", "Failed"),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    tournament = models.ForeignKey(Tournament, on_delete=models.CASCADE,related_name="registrations",null=True, blank=True)
    stripe_payment_intent_id = models.CharField(max_length=255, null=True, blank=True)
    amount = models.CharField(max_length=255, null=True, blank=True)
    payment_status = models.CharField(max_length=10, choices=PAYMENT_STATUS_CHOICES, default="Pending")
    created_at = models.DateTimeField(auto_now_add=True,null=True, blank=True)

    class Meta:
        unique_together = ('user', 'tournament')

    def __str__(self):
        return f"{self.user.username} - {self.tournament.name}"
    
    
    
    

class Pool(models.Model):
    tournament = models.ForeignKey(Tournament, on_delete=models.CASCADE, related_name='pools')
    pool_number = models.IntegerField()  # e.g., 1 for Pool 1, 2 for Pool 2, etc.
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    
    result = models.JSONField(default=dict, blank=True)  # Added field for storing extra pool data (e.g., bye athletes)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Pool {self.pool_number} for {self.tournament}" 
        
    #mathch model 
    User = get_user_model()
class Match(models.Model):
    STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Completed', 'Completed'),
    ]

    tournament = models.ForeignKey(Tournament, on_delete=models.CASCADE, related_name='matches')
    player_1 = models.ForeignKey(User, on_delete=models.CASCADE, related_name='player_1_matches')
    player_2 = models.ForeignKey(User, on_delete=models.CASCADE, related_name='player_2_matches')
    pool = models.ForeignKey(Pool, on_delete=models.CASCADE, related_name='matches', null=True, blank=True)
    date = models.DateTimeField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='Pending')
    result = models.JSONField(default=dict, blank=True)
    winner = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='won_matches')
    
   
   
    def __str__(self):
        return f"Match {self.id} in {self.tournament}"
    
    
    
    

User = get_user_model()

class Claim(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='claims')
    phone_number = models.CharField(max_length=20)
    subject = models.CharField(max_length=255)
    details = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Claim {self.id} by {self.user.username}: {self.subject}"    
    
    
    
# New model: Chat messages for a match
class MatchChat(models.Model):
    match = models.ForeignKey(Match, on_delete=models.CASCADE, related_name='chats')
    sender = models.ForeignKey(User, on_delete=models.CASCADE)
    message = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Chat by {self.sender.username} in Match {self.match.id}"    
   