# user_management/models.py
from django.contrib.auth.models import AbstractUser, UserManager as BaseUserManager
from django.db import models

class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('The  email must be set')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

class User(AbstractUser):
    # Adding custom fields
    email = models.EmailField(unique=True)
    is_verified = models.BooleanField(default=False)
    date_of_birth = models.DateField(null=True, blank=True)  # Date of birth
    phone_number = models.CharField(max_length=15, unique=True)  # Phone number
    photo=models.FileField(blank=True, null=True) 
    location=models.CharField(max_length=250,null=True, blank=True)
    google_user_id = models.CharField(max_length=255, unique=True,null=True, blank=True)  

    
    objects = UserManager()
    USERNAME_FIELD = 'email'  # Set email as the username field
    REQUIRED_FIELDS = ['username']  # Add other fields you require during creation

    def __str__(self):
        return self.email
