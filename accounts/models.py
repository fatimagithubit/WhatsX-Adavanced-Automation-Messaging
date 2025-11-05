from django.contrib.auth.models import AbstractUser
from django.db import models
from django.conf import settings
from django.contrib.auth import get_user_model


# --- 1. User & Profile (Core) ---
class CustomUser(AbstractUser):
    USER_TYPE_CHOICES = (
        ('admin', 'Admin'),
        ('enduser', 'End User'),
    )
    user_type = models.CharField(max_length=10, choices=USER_TYPE_CHOICES, default='enduser')
    image = models.ImageField(upload_to='profile_images/', blank=True, null=True)
    
    # Message Quota retained for Admin management
    message_quota = models.IntegerField(default=1000, help_text="Monthly message sending limit.")

    def __str__(self):
        return f"{self.username} ({self.user_type})"

    def save(self, *args, **kwargs):
        if self.is_superuser:
            self.user_type = 'admin'
        super().save(*args, **kwargs)




# --- 3. Contact Management (Core) ---
class Contact(models.Model):
    user = models.ForeignKey(get_user_model(), on_delete=models.CASCADE, related_name='contacts')
    name = models.CharField(max_length=100)
    phone = models.CharField(max_length=20)
    profile_picture = models.ImageField(upload_to='contact_pics/', blank=True, null=True) 

    def __str__(self):
        return f"{self.name} ({self.phone})"


