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
                "message": "Connexion réussie.",
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
            return Response({"detail": "Vous n'êtes pas autorisé(e) à voir ce profil."}, status=status.HTTP_403_FORBIDDEN)

        serializer = UserProfileSerializer(user)
        return Response(serializer.data)
    
    
    
# update  super user profile
class SuperAdminUpdateProfileView(APIView):
    authentication_classes = [TokenAuthentication]
      
    def put(self, request):
        user = request.user  # Assumes the user is already authenticated via token

        # Check if the user is a superadmin
        if not user.is_superuser:
            return Response({"detail": "Vous n'êtes pas autorisé à mettre à jour ce profil."}, status=status.HTTP_403_FORBIDDEN)

        # Deserialize and validate the incoming data
        serializer = UserProfileSerializer(user, data=request.data, partial=False)

        if serializer.is_valid():
            # Update the user profile
            serializer.save()
            return Response({"message": "Profil mis à jour avec succès."}, status=status.HTTP_200_OK)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    
# for user  Register
from django.core.mail import send_mail
from django.urls import reverse
from django.template.loader import render_to_string
from django.utils.html import strip_tags

class RegisterUserView(APIView):
    def post(self, request):
        serializer = UserRegistrationSerializer(data=request.data)
        if serializer.is_valid():
            email = serializer.validated_data['email']
            
            # Check if user is already registered but not verified
            user = User.objects.filter(email=email, is_active=False).first()
            if user:
                return Response(
                    {"message": "Utilisateur déjà enregistré, mais non vérifié. Redirection pour renvoyer l'e-mail"},
                    status=status.HTTP_302_FOUND
                )

            # Save the new user
            user = serializer.save()
            token = uuid.uuid4().hex
            cache.set(token, user.id, timeout=3600)

            # Construct the verification link
            verify_link = f"https://toornoi.com/verify-email/?token={token}"
            
            # Render email template
            context = {"username": user.username, "verify_link": verify_link}
            html_message = render_to_string("emails/verify_email.html", context)
            plain_message = strip_tags(html_message)  # Fallback for plain-text emails

            # Send email
            send_mail(
                subject="Bienvenue sur Toornoi.com – Confirmez votre inscription",
                message=plain_message,
                from_email="contact@toornoi.com",
                recipient_list=[user.email],
                html_message=html_message,  # This sends the HTML email
                fail_silently=False,
            )

            return Response({"message": "Vérifiez votre courrier électronique pour le lien de vérification."}, status=status.HTTP_201_CREATED)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
# class RegisterUserView(APIView):
#     def post(self, request):
#         serializer = UserRegistrationSerializer(data=request.data)
#         if serializer.is_valid():
#             email = serializer.validated_data['email']
#             # Check if the user is already registered but not verified
#             user = User.objects.filter(email=email, is_active=False).first()
#             if user:
#                 return Response(
#                     {"message": "User already registered but not verified. Redirecting to resend email."},
#                     status=status.HTTP_302_FOUND
#                 )

#             # Save the new user
#             user = serializer.save()
#             token = uuid.uuid4().hex
#             cache.set(token, user.id, timeout=3600)

#             # Construct the verification link
#             verify_link = f"https://toornoi.com/verify-email/?token={token}"
            
#             # Send the verification email
#             send_mail(
#                 'Verify Your Account',
#                 f'Click the link to verify your account: {verify_link}',
#                 'chumarlatif123@gmail.com',  
#                 [user.email],
#                 fail_silently=False,
#             )
            
#             return Response({"message": "Check your email for the verification link."}, status=status.HTTP_201_CREATED)
#         return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)



 #Get the custom user model
from django.contrib.auth import get_user_model
User = get_user_model()

class VerifyEmailView(APIView):
    def get(self, request):
        token = request.GET.get('token')
        
        if not token:
            return Response({"error": "Un jeton est requis"}, status=status.HTTP_400_BAD_REQUEST)

        # Get the user ID from the cache using the token
        user_id = cache.get(token)
        if not user_id:
            return Response({
                "error": "Jeton invalide ou expiré. Veuillez demander un nouvel e-mail de vérification."
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Find the user and mark them as active and verified
            user = User.objects.get(id=user_id)
            user.is_active = True
            user.is_verified = True  # Assuming you have a 'is_verified' field
            user.save()

            # Remove the token from the cache after successful verification
            cache.delete(token)

            return Response({"message": "Votre compte a été vérifié."}, status=status.HTTP_200_OK)
        except User.DoesNotExist:
            return Response({"error": "Utilisateur introuvable"}, status=status.HTTP_404_NOT_FOUND)


# Resend Email verification 

class ResendVerificationEmailView(APIView):
    def post(self, request):
        email = request.data.get('email')
        
        if not email:
            return Response({"error": "L'e-mail est requis"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = User.objects.get(email=email, is_active=False)

            # Generate a new token
            token = uuid.uuid4().hex
            cache.set(token, user.id, timeout=3600)

            # Construct the verification link
            verify_link = f"https://toornoi.com/verify-email/?token={token}"
            
            # Send the verification email
            send_mail(
                'Vérifiez votre compte - Renvoyer',
                f'Cliquez sur le lien pour vérifier votre compte: {verify_link}',
                 'contact@toornoi.com',
                [user.email],
                fail_silently=False,
            )

            return Response({"message": "L'e-mail de vérification a été renvoyé."}, status=status.HTTP_200_OK)
        except User.DoesNotExist:
            return Response({"error": "Utilisateur non trouvé ou déjà vérifié"}, status=status.HTTP_404_NOT_FOUND)





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
                "message": "Connexion réussie.",
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
            return Response({"detail": "Vous n'êtes pas autorisé à voir ce profil."}, status=status.HTTP_403_FORBIDDEN)

        serializer = UserProfileSerializer(user)
        return Response(serializer.data)
        
        
        
# update  All user profile
class UserUpdateProfileView(APIView):
    authentication_classes = [TokenAuthentication]

    def put(self, request):
        user = request.user  # Assumes the user is already authenticated via token

        # Check if the user is a superadmin
        if not user.is_verified:
            return Response({"detail": "Vous n'êtes pas autorisé à mettre à jour ce profil."}, status=status.HTTP_403_FORBIDDEN)

        # Deserialize and validate the incoming data
        serializer = UserProfileSerializer(user, data=request.data, partial=False)

        if serializer.is_valid():
            # Update the user profile
            serializer.save()
            return Response({"message": "Profil mis à jour avec succès."}, status=status.HTTP_200_OK)
        
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
                'Réinitialisez votre mot de passe',
                f'Cliquez sur le lien pour réinitialiser votre mot de passe: {reset_link}',
                'contact@toornoi.com',  # Change to your sender email
                [user.email],
                fail_silently=False,
            )

            return Response({"message": "Un lien de réinitialisation du mot de passe a été envoyé à votre adresse e-mail."}, status=status.HTTP_200_OK)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# Reset Password View
class ResetPasswordView(APIView):
    def post(self, request):
        token = request.GET.get('token')
        if not token:
            return Response({"error": "Un jeton est requis"}, status=status.HTTP_400_BAD_REQUEST)
        
        user_id = cache.get(token)
        if not user_id:
            return Response({"error": "Jeton invalide ou expiré"}, status=status.HTTP_400_BAD_REQUEST)

        serializer = ResetPasswordSerializer(data=request.data)
        if serializer.is_valid():
            try:
                user = User.objects.get(id=user_id)
                user.set_password(serializer.validated_data['new_password'])
                user.save()
                cache.delete(token)  # Clean up the token
                return Response({"message": "Votre mot de passe a été réinitialisé avec succès."}, status=status.HTTP_200_OK)
            except User.DoesNotExist:
                return Response({"error": "Utilisateur introuvable"}, status=status.HTTP_404_NOT_FOUND)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)            
    
    
    
 