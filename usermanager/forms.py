# mpi_src/
# │
# ├── usermanager/
# │   ├── forms.py

# mpi_src/usermanager/forms.py

from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from .models import User

# Sign-Up Form
class SignUpForm(UserCreationForm):
    class Meta:
        model = User
        fields = ['username', 'name', 'password1', 'password2']  # Adjust the fields as per your model

# Sign-In Form (Inherits from AuthenticationForm)
class SignInForm(AuthenticationForm):
    class Meta:
        model = User
        fields = ['username', 'password']

