from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.authentication import TokenAuthentication
from rest_framework import status
from rest_framework.authtoken.models import Token
from .serializers import ForgotPasswordSerializer, LoginSerializer, ResetPasswordSerializer, UserLoginSerializer, UserRegistrationSerializer
from .serializers import UserProfileSerializer
from django.contrib.auth.models import User
from django.core.cache import cache  # or use a database to store tokens
from django.conf import settings
import uuid
from django.contrib.auth import authenticate

class SuperAdminLoginView(APIView):
    def post(self, request):
        # Deserialize the request data
        serializer = LoginSerializer(data=request.data)
        
        if serializer.is_valid():
            user = serializer.validated_data['user']
            
            # Generate or retrieve the token for the authenticated user
            token, _ = Token.objects.get_or_create(user=user)
            
            # Respond with the token and a success message
            return Response({
                "token": token.key,
                "message": "Login successful.",
            }, status=status.HTTP_200_OK)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)




# Fetch   super user profile
class SuperAdminProfileView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        print(f"User: {user}, Superuser: {user.is_superuser}")

        if not user.is_superuser:
            return Response({"detail": "You are not authorized to view this profile."}, status=status.HTTP_403_FORBIDDEN)

        serializer = UserProfileSerializer(user)
        return Response(serializer.data)
    
    
    
# update  super user profile
class SuperAdminUpdateProfileView(APIView):
    authentication_classes = [TokenAuthentication]
      
    def put(self, request):
        user = request.user  # Assumes the user is already authenticated via token

        # Check if the user is a superadmin
        if not user.is_superuser:
            return Response({"detail": "You are not authorized to update this profile."}, status=status.HTTP_403_FORBIDDEN)

        # Deserialize and validate the incoming data
        serializer = UserProfileSerializer(user, data=request.data, partial=False)

        if serializer.is_valid():
            # Update the user profile
            serializer.save()
            return Response({"message": "Profile updated successfully."}, status=status.HTTP_200_OK)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    
# for user  Register
from django.core.mail import send_mail
from django.urls import reverse

class RegisterUserView(APIView):
    def post(self, request):
        serializer = UserRegistrationSerializer(data=request.data)
        if serializer.is_valid():
            email = serializer.validated_data['email']
            # Check if the user is already registered but not verified
            user = User.objects.filter(email=email, is_active=False).first()
            if user:
                return Response(
                    {"message": "User already registered but not verified. Redirecting to resend email."},
                    status=status.HTTP_302_FOUND
                )

            # Save the new user
            user = serializer.save()
            token = uuid.uuid4().hex
            cache.set(token, user.id, timeout=3600)

            # Construct the verification link
            verify_link = f"https://toornoi.com/verify-email/?token={token}"
            
            # Send the verification email
            send_mail(
                'Verify Your Account',
                f'Click the link to verify your account: {verify_link}',
                'chumarlatif123@gmail.com',  
                [user.email],
                fail_silently=False,
            )
            
            return Response({"message": "Check your email for the verification link."}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)



 #Get the custom user model
from django.contrib.auth import get_user_model
User = get_user_model()

class VerifyEmailView(APIView):
    def get(self, request):
        token = request.GET.get('token')
        
        if not token:
            return Response({"error": "Token is required"}, status=status.HTTP_400_BAD_REQUEST)

        # Get the user ID from the cache using the token
        user_id = cache.get(token)
        if not user_id:
            return Response({
                "error": "Invalid or expired token. Please request a new verification email."
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Find the user and mark them as active and verified
            user = User.objects.get(id=user_id)
            user.is_active = True
            user.is_verified = True  # Assuming you have a 'is_verified' field
            user.save()

            # Remove the token from the cache after successful verification
            cache.delete(token)

            return Response({"message": "Your account has been verified."}, status=status.HTTP_200_OK)
        except User.DoesNotExist:
            return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)


# Resend Email verification 

class ResendVerificationEmailView(APIView):
    def post(self, request):
        email = request.data.get('email')
        
        if not email:
            return Response({"error": "Email is required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = User.objects.get(email=email, is_active=False)

            # Generate a new token
            token = uuid.uuid4().hex
            cache.set(token, user.id, timeout=3600)

            # Construct the verification link
            verify_link = f"https://toornoi.com/verify-email/?token={token}"
            
            # Send the verification email
            send_mail(
                'Verify Your Account - Resend',
                f'Click the link to verify your account: {verify_link}',
                 'chumarlatif123@gmail.com',
                [user.email],
                fail_silently=False,
            )

            return Response({"message": "Verification email has been resent."}, status=status.HTTP_200_OK)
        except User.DoesNotExist:
            return Response({"error": "User not found or already verified"}, status=status.HTTP_404_NOT_FOUND)





# All user  login API  view
class UserLoginView(APIView):
    def post(self, request):
        serializer = UserLoginSerializer(data=request.data)

        if serializer.is_valid():
            user = serializer.validated_data['user']
            
            # Generate or retrieve the token for the authenticated user
            token, _ = Token.objects.get_or_create(user=user)

            # Respond with the token and a success message
            return Response({
                "token": token.key,
                "message": "Login successful.",
            }, status=status.HTTP_200_OK)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    
# Fetch   All  user profile
class UserProfileView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        print(f"User: {user}, user: {user.is_verified }")

        if not user.is_verified:
            return Response({"detail": "You are not authorized to view this profile."}, status=status.HTTP_403_FORBIDDEN)

        serializer = UserProfileSerializer(user)
        return Response(serializer.data)
        
        
        
# update  All user profile
class UserUpdateProfileView(APIView):
    authentication_classes = [TokenAuthentication]

    def put(self, request):
        user = request.user  # Assumes the user is already authenticated via token

        # Check if the user is a superadmin
        if not user.is_verified:
            return Response({"detail": "You are not authorized to update this profile."}, status=status.HTTP_403_FORBIDDEN)

        # Deserialize and validate the incoming data
        serializer = UserProfileSerializer(user, data=request.data, partial=False)

        if serializer.is_valid():
            # Update the user profile
            serializer.save()
            return Response({"message": "Profile updated successfully."}, status=status.HTTP_200_OK)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
            
            
            
# Forgot Password View
class ForgotPasswordView(APIView):
    def post(self, request):
        serializer = ForgotPasswordSerializer(data=request.data)
        if serializer.is_valid():
            email = serializer.validated_data['email']
            user = User.objects.get(email=email)
            token = uuid.uuid4().hex
            cache.set(token, user.id, timeout=3600)  # Token expires in 1 hour

            # Construct the reset password link
            reset_link = f"https://toornoi.com/reset-password/?token={token}"
            
            # Send the reset password email
            send_mail(
                'Reset Your Password',
                f'Click the link to reset your password: {reset_link}',
                'chumarlatif123@gmail.com',  # Change to your sender email
                [user.email],
                fail_silently=False,
            )

            return Response({"message": "A password reset link has been sent to your email."}, status=status.HTTP_200_OK)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# Reset Password View
class ResetPasswordView(APIView):
    def post(self, request):
        token = request.GET.get('token')
        if not token:
            return Response({"error": "Token is required"}, status=status.HTTP_400_BAD_REQUEST)
        
        user_id = cache.get(token)
        if not user_id:
            return Response({"error": "Invalid or expired token"}, status=status.HTTP_400_BAD_REQUEST)

        serializer = ResetPasswordSerializer(data=request.data)
        if serializer.is_valid():
            try:
                user = User.objects.get(id=user_id)
                user.set_password(serializer.validated_data['new_password'])
                user.save()
                cache.delete(token)  # Clean up the token
                return Response({"message": "Your password has been reset successfully."}, status=status.HTTP_200_OK)
            except User.DoesNotExist:
                return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)            
    
    
    
 