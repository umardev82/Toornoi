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
    # sumup_link = models.URLField(max_length=500, null=True, blank=True) 
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
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    tournament = models.ForeignKey(Tournament, on_delete=models.CASCADE)
    payment_status = models.CharField(max_length=20, choices=[('Pending', 'Pending'), ('Paid', 'Paid')], default='Pending')
    registered_at = models.DateTimeField(auto_now_add=True,null=True, blank=True)

    def __str__(self):
        return f"{self.user.username} registered for {self.tournament.tournament_name}"
    
    
    
    
    
    #mathch model 
class Match(models.Model):
    STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Completed', 'Completed'),
    ]

    tournament = models.ForeignKey(Tournament, on_delete=models.CASCADE, related_name='matches')
    player_1 = models.ForeignKey(User, on_delete=models.CASCADE, related_name='player_1_matches')
    player_2 = models.ForeignKey(User, on_delete=models.CASCADE, related_name='player_2_matches')
    stage = models.IntegerField()
    date = models.DateTimeField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='Pending')
    result = models.JSONField(null=True, blank=True)
    winner = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='won_matches')
    screenshot = models.ImageField(upload_to='match_screenshots/', null=True, blank=True)

    def __str__(self):
        return f"Match: {self.player_1} vs {self.player_2} - Stage {self.stage}"
    
    
    
#stage model  for admin
class Stage(models.Model):
    tournament = models.ForeignKey('Tournament', on_delete=models.CASCADE, related_name='stages')
    stage_number = models.IntegerField()
    number_of_matches = models.IntegerField()
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()

    def __str__(self):
        return f"Stage {self.stage_number} - {self.tournament.name}"    