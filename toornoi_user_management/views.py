from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.authentication import TokenAuthentication
from rest_framework import status
from rest_framework.authtoken.models import Token
from .serializers import LoginSerializer, UserLoginSerializer, UserRegistrationSerializer
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
    
    
# for user
# class RegisterUserView(APIView):
#     def post(self, request):
#         serializer = UserRegistrationSerializer(data=request.data)
#         if serializer.is_valid():
#             user = serializer.save()
#             token = uuid.uuid4().hex
#             cache.set(token, user.id, timeout=86400)
#             print(f"Generated token: {token}, User ID: {user.id}")
#             return Response({"message": "Check your email for the verification link."}, status=status.HTTP_201_CREATED)
#         return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


from django.core.mail import send_mail
from django.urls import reverse

class RegisterUserView(APIView):
    def post(self, request):
        serializer = UserRegistrationSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            token = uuid.uuid4().hex
            cache.set(token, user.id, timeout=60)
            
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
            return Response({"error": "Invalid or expired token. Please request a new verification email."},
                             status=status.HTTP_400_BAD_REQUEST)

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
            