from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import Contact, CustomUser
import re

PHONE_RE = re.compile(r'^\+?\d{7,15}$')

def normalize_phone(phone: str) -> str:
    if not phone: return ''
    cleaned = re.sub(r'[^\d+]', '', phone)
    return cleaned


class CustomUserCreationForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = CustomUser
        fields = ('username', 'email', 'image')  # no user_type here

    def save(self, commit=True):
        user = super().save(commit=False)
        # system assigns user_type automatically
        user.user_type = 'end_user'
        if commit:
            user.save()
        return user


class ContactForm(forms.ModelForm):
    class Meta:
        model = Contact
        fields = ['name', 'phone', 'profile_picture']

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

    def clean_phone(self):
        phone = normalize_phone(self.cleaned_data.get('phone', ''))
        if not phone:
            raise forms.ValidationError("Phone number is required.")
        if not PHONE_RE.match(phone):
            raise forms.ValidationError("Enter a valid phone number.")
        if self.user:
            qs = Contact.objects.filter(user=self.user, phone=phone)
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise forms.ValidationError(f"A contact with phone number {phone} already exists.")
        return phone


class UserProfileUpdateForm(forms.ModelForm):
    password = forms.CharField(label='Password', required=False, widget=forms.PasswordInput)

    class Meta:
        model = CustomUser
        fields = ['username', 'email', 'image']

    def save(self, commit=True):
        user = super().save(commit=False)
        pwd = self.cleaned_data.get('password')
        if pwd:
            user.set_password(pwd)
        if commit:
            user.save()
        return user
