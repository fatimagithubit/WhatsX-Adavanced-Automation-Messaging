# Create you# accounts/views.py
from rest_framework import generics
from .models import CustomUser
from .serializers import RegisterSerializer
from rest_framework.permissions import AllowAny
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.core.mail import send_mail
from rest_framework.response import Response
from rest_framework import status
from .models import CustomUser
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from .models import Contact
from rest_framework import serializers
from django.http import HttpResponse
import csv

class RegisterView(generics.CreateAPIView):
    queryset = CustomUser.objects.all()
    permission_classes = [AllowAny]
    serializer_class = RegisterSerializer

class ForgotPasswordView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get('email')
        user = CustomUser.objects.filter(email=email).first()
        if user:
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = default_token_generator.make_token(user)
            reset_link = f"http://localhost:3000/reset-password/{uid}/{token}"  # frontend route
            print("🔑 RESET LINK:", reset_link)  # You can also send it via email later

        return Response({"message": "If the email exists, a reset link was sent."}) 

class ResetPasswordView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, uidb64, token):
        try:
            uid = force_str(urlsafe_base64_decode(uidb64))
            user = CustomUser.objects.get(pk=uid)
        except:
            return Response({"error": "Invalid link"}, status=400)

        if default_token_generator.check_token(user, token):
            new_password = request.data.get("password")
            user.set_password(new_password)
            user.save()
            return Response({"message": "Password has been reset."})
        return Response({"error": "Token expired or invalid"}, status=400)

class ProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        return Response({
            "username": user.username,
            "email": user.email,
            "user_type": user.user_type,
        })

    def patch(self, request):
        user = request.user
        user.username = request.data.get("username", user.username)
        user.email = request.data.get("email", user.email)
        user.save()
        return Response({"message": "Profile updated."})

class DeleteUserView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request):
        user = request.user
        user.delete()
        return Response({"message": "Account deleted."})

class ContactSerializer(serializers.ModelSerializer):
    class Meta:
        model = Contact
        fields = ['id', 'name', 'phone']

class IsEndUser(IsAuthenticated):
    def has_permission(self, request, view):
        return super().has_permission(request, view) and getattr(request.user, 'user_type', None) != 'admin'

class ContactListCreateView(generics.ListCreateAPIView):
    serializer_class = ContactSerializer
    permission_classes = [IsEndUser]

    def get_queryset(self):
        return Contact.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

class ContactDeleteView(generics.DestroyAPIView):
    serializer_class = ContactSerializer
    permission_classes = [IsEndUser]

    def get_queryset(self):
        return Contact.objects.filter(user=self.request.user)

class ContactCSVExportView(APIView):
    permission_classes = [IsEndUser]

    def get(self, request):
        contacts = Contact.objects.filter(user=request.user)
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="contacts.csv"'
        writer = csv.writer(response)
        writer.writerow(['Name', 'Phone'])
        for contact in contacts:
            writer.writerow([contact.name, contact.phone])
        return response            