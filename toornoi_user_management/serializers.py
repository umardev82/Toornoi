from rest_framework import serializers
from django.contrib.auth import authenticate
from .models import User  # Use the custom User model
from django.contrib.auth.password_validation import validate_password
from django.core.mail import send_mail
from django.conf import settings
from django.urls import reverse
import uuid




#admin login
class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    password = serializers.CharField(required=True, write_only=True)

    def validate(self, data):
        email = data.get('email')
        password = data.get('password')

        # Check if the email exists in the custom User model
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            raise serializers.ValidationError("Invalid email or password.")

        # Authenticate the user using the username (since the model has email, but authenticate uses username)
        user = authenticate(email=user.email, password=password)
        if user is None:
            raise serializers.ValidationError("Invalid email or password.")

        # Check if the user is a superuser
        if not user.is_superuser:
            raise serializers.ValidationError("User is not authorized as a superadmin.")

        # Return the validated user
        data['user'] = user
        return data


# super User Profile
class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['username', 'photo','first_name', 'last_name', 'email','password','location', 'date_of_birth', 'phone_number']

    def update(self, instance, validated_data):
        # Update fields with validated data
        instance.username = validated_data.get('username', instance.username)
        instance.photo = validated_data.get('photo', instance.photo)
        instance.first_name = validated_data.get('first_name', instance.first_name)
        instance.last_name = validated_data.get('last_name', instance.last_name)
        instance.email = validated_data.get('email', instance.email)
        instance.password = validated_data.get('password', instance.password)
        instance.location = validated_data.get('location', instance.location)
        instance.date_of_birth = validated_data.get('date_of_birth', instance.date_of_birth)
        instance.phone_number = validated_data.get('phone_number', instance.phone_number)

        
        # Save the updated instance
        instance.save()
        return instance



#user Registrations 
class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, validators=[validate_password])
    confirm_password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ['username', 'email', 'date_of_birth', 'phone_number', 'password', 'confirm_password']

    def validate(self, attrs):
        # Check if passwords match
        if attrs['password'] != attrs['confirm_password']:
            raise serializers.ValidationError({"password": "Password and Confirm Password are not  match."})
        return attrs

    def create(self, validated_data):
        # Remove confirm_password as it's not needed for user creation
        validated_data.pop('confirm_password')
        
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data['email'],
            date_of_birth=validated_data['date_of_birth'],
            phone_number=validated_data['phone_number'],
            password=validated_data['password'],
        )
        user.is_active = False  # Set to inactive until email is verified
        user.save()
        return user



from django.contrib.auth import authenticate, get_user_model
from rest_framework import serializers

User = get_user_model()

class UserLoginSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    password = serializers.CharField(required=True, write_only=True)

    def validate(self, data):
        email = data.get('email')
        password = data.get('password')

        # Check if the email exists in the custom User model
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            raise serializers.ValidationError("Invalid email or password.")

        # Authenticate the user using the email
        user = authenticate(email=user.email, password=password)
        if user is None:
            raise serializers.ValidationError("Invalid email or password.")

        # Check if the user is verified
        if not user.is_verified:
            raise serializers.ValidationError("User is not verified.")

        # Check if the user is active
        if not user.is_active:
            raise serializers.ValidationError("User is not active.")

        data['user'] = user
        return data

 
 
# Forgot Password Serializer
class ForgotPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, value):
        if not User.objects.filter(email=value).exists():
            raise serializers.ValidationError("User with this email does not exist.")
        return value


# Reset Password Serializer
class ResetPasswordSerializer(serializers.Serializer):
    new_password = serializers.CharField(write_only=True, validators=[validate_password])
    confirm_password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        if attrs['new_password'] != attrs['confirm_password']:
            raise serializers.ValidationError({"new_password": "Passwords do not match."})
        return attrs    
    

