# mpi_src/usermanager/views.py

import uuid
import logging
import requests
import paystack
import datetime

from django.shortcuts import render, redirect, get_object_or_404
from django.conf import settings
from django.contrib.auth import login, logout
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy, reverse
from django.views.generic import ListView, DetailView, FormView, RedirectView, View
from django.http import JsonResponse

from .forms import SignUpForm, SignInForm
from .models import User, Profile, UserProfile, Payment, Session
from .mikrotik_userman import init_mikrotik_manager

paystack.api_key = settings.PAYSTACK_SECRET_KEY
mikrotik_manager = init_mikrotik_manager()

logger = logging.getLogger(__name__)

class SignUpView(FormView):
    template_name = 'usermanager/sign_up.html'  # Template for sign-up
    form_class = SignUpForm  # Your custom sign-up form
    success_url = reverse_lazy('sign_in')  # Redirect to sign-in after successful sign-up

    def form_valid(self, form):
        form.save()  # Save the user form (this will call form's save() method)
        return super().form_valid(form)

class SignInView(FormView):
    template_name = 'usermanager/sign_in.html'  # Template for sign-in
    form_class = SignInForm  # Your custom sign-in form
    success_url = reverse_lazy('user_detail')  # Redirect to user detail after successful sign-in

    def form_valid(self, form):
        user = form.get_user()  # Authenticate user
        login(self.request, user)  # Log the user in
        return super().form_valid(form)

class SignOutView(LoginRequiredMixin, RedirectView):
    url = reverse_lazy('sign_in')  # Redirect to sign-in page after logging out

    def get(self, request, *args, **kwargs):
        logout(request)  # Log the user out
        return super().get(request, *args, **kwargs)

class UserDetailView(LoginRequiredMixin, DetailView):
    model = User
    template_name = 'usermanager/user_detail.html'
    context_object_name = 'user_detail'

    def get_object(self, queryset=None):
        return self.request.user

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Fetch the user profiles related to the current user
        user_profiles = UserProfile.objects.filter(user=self.request.user)

        # Filter profiles with state 'running-active'
        running_active_profiles = user_profiles.filter(state='running-active')

        # Sort profiles by 'end_time' and get the 5 most recent ones
        recent_user_profiles = user_profiles.order_by('-end_time')[:5]       

        # Fetch payments related to the user
        user_payments = Payment.objects.filter(user=self.request.user)
        recent_user_payments = user_payments.order_by('-trans_end')[:5]   

        # Fetch user sessions
        user_sessions = Session.objects.filter(user=self.request.user).order_by('-session_id')
        active_sessions = user_sessions.filter(ended__isnull=True)

        context['recent_user_profiles'] = recent_user_profiles
        context['user_sessions'] = user_sessions
        context['recent_user_payments'] = recent_user_payments
        context['active_sessions'] = active_sessions
        context['running_active_profiles'] = running_active_profiles

        return context


class ProfileListView(LoginRequiredMixin, ListView):
    model = Profile
    template_name = 'usermanager/profile_list.html'
    context_object_name = 'profiles'

    def get_queryset(self):
        # Fetch all profiles from Django model
        return Profile.objects.all()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['profiles'] = self.get_queryset()
        return context


class UserProfileListView(LoginRequiredMixin, ListView):
    model = UserProfile
    template_name = 'usermanager/user_profile_list.html'
    context_object_name = 'user_profiles'

    def get_queryset(self):
        # Superusers see all user profiles, regular users see only their own
        if self.request.user.is_superuser:
            return UserProfile.objects.all()
        return UserProfile.objects.filter(user=self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['user_profiles'] = self.get_queryset()
        return context


class PaymentListView(LoginRequiredMixin, ListView):
    model = Payment
    template_name = 'usermanager/payment_list.html'
    context_object_name = 'payments'

    def get_queryset(self):
        # Superusers see all user profiles, regular users see only their own
        if self.request.user.is_superuser:
            return Payment.objects.all()
        return Payment.objects.filter(user=self.request.user)
    

class SessionListView(LoginRequiredMixin, ListView):
    template_name = 'usermanager/sessions.html'
    context_object_name = 'user_sessions'

    def get_queryset(self):
        # Superusers see all sessions; regular users see only their own
        if self.request.user.is_superuser:
            return Session.objects.all()
        return Session.objects.filter(user=self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['user_sessions'] = self.get_queryset()
        return context


# Initialize payment with Paystack
class InitiatePaymentView(View):
    def get(self, request, profile_id):
        try:
            profile = get_object_or_404(Profile, id=profile_id)
            if not request.user.is_authenticated:
                return JsonResponse({'error': 'User not authenticated'}, status=401)

            if not request.user.email:
                return JsonResponse({'error': 'Email is required'}, status=400)

            # Generate a unique transaction reference using a UUID
            payment_reference = str(uuid.uuid4())

            payment_data = {
                "email": request.user.email,
                "amount": int(profile.price * 100),  # Amount in kobo
                "reference": payment_reference,
                "callback_url": request.build_absolute_uri(reverse('verify_payment')) + f"?user_id={request.user.id}&profile_id={profile.id}"
            }

            headers = {
                "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
                "Content-Type": "application/json"
            }

            logger.debug(f"Initiating payment with reference: {payment_reference}")

            # Send request to Paystack to initialize payment
            response = requests.post('https://api.paystack.co/transaction/initialize', json=payment_data, headers=headers)

            if response.status_code == 200:
                response_data = response.json()
                payment_url = response_data['data']['authorization_url']
                return redirect(payment_url)
            else:
                logger.error(f"Paystack response: {response.json()}")
                return JsonResponse({'error': 'Payment initiation failed', 'details': response.json()}, status=response.status_code)

        except Exception as e:
            logger.error(f"Error during payment initiation: {e}", exc_info=True)
            return JsonResponse({'error': 'An error occurred during payment initiation'}, status=500)


# Verify payment and update Payment with Paystack
class VerifyPaymentView(View):
    def get(self, request):
        reference = request.GET.get('reference')
        user_id = request.GET.get('user_id')
        profile_id = request.GET.get('profile_id')

        if not reference or not user_id or not profile_id:
            return JsonResponse({'error': 'Reference, user ID, and profile ID are required'}, status=400)

        headers = {
            "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
            "Content-Type": "application/json"
        }

        try:
            logger.debug(f"Received reference: {reference}")

            # Verify the payment via Paystack API
            response = requests.get(f'https://api.paystack.co/transaction/verify/{reference}', headers=headers)
            response.raise_for_status()  # Raise an HTTPError for bad responses
            response_data = response.json()

            if response_data.get('data', {}).get('status') == 'success':
                # Validate UUID format
                def is_valid_uuid(val):
                    try:
                        uuid.UUID(str(val))  # Ensure it's converted to string
                        return True
                    except ValueError:
                        return False

                if not is_valid_uuid(user_id) or not is_valid_uuid(profile_id):
                    return JsonResponse({'error': 'User ID or Profile ID is not a valid UUID'}, status=400)

                # Now safely query the Profile and User models
                profile = get_object_or_404(Profile, id=profile_id)
                user = get_object_or_404(User, id=user_id)

                user_profile, created = UserProfile.objects.get_or_create(user=user, profile=profile)

                # Create a payment entry
                payment = Payment.objects.create(
                    user=user,
                    user_profile=user_profile,
                    profile=profile,
                    method="ONLINE",
                    trans_start=datetime.datetime.now(),
                    trans_status="completed",
                    price=response_data['data']['amount'] / 100,
                    paystack_reference=reference
                )

                from usermanager.tasks import create_user_profile_in_mikrotik
                create_user_profile_in_mikrotik.delay(user_profile.id)

                return redirect('payment_success')

            else:
                logger.warning(f"Payment verification failed for reference: {reference}. Status: {response_data.get('data', {}).get('status')}")
                return redirect('payment_failed')

        except requests.RequestException as e:
            logger.error(f"Error verifying payment with Paystack: {e}", exc_info=True)
            return JsonResponse({'error': 'Payment verification failed'}, status=500)
        except Exception as e:
            logger.error(f"Unexpected error: {e}", exc_info=True)
            return JsonResponse({'error': 'An unexpected error occurred'}, status=500)


# Payment success view
def payment_success(request):
    return render(request, 'usermanager/payment_success.html')

# Payment failed view
def payment_failed(request):
    return render(request, 'usermanager/payment_failed.html')






# Querying directly from Mikrotik
# class UserDetailView(LoginRequiredMixin, DetailView):
#     model = User
#     template_name = 'usermanager/user_detail.html'
#     context_object_name = 'user_detail'

#     def get_object(self, queryset=None):
#         # Always return the current logged-in user
#         return self.request.user

#     def get_context_data(self, **kwargs):
#         context = super().get_context_data(**kwargs)

#         # Fetch all user profiles from MikroTik
#         all_profiles = mikrotik_manager.get_user_profiles()

#         # Filter profiles by the current user and 'running-active' state
#         running_active_profiles = [
#             profile for profile in all_profiles 
#             if profile.get('state') == 'running-active' and profile.get('user') == self.request.user.username
#         ]

#         # Retrieve related profiles from the Profile model based on the user's running-active profiles
#         related_profiles = Profile.objects.filter(name__in=[p.get('profile') for p in running_active_profiles])

#         # Filter profiles by the current user
#         user_profiles = [
#             profile for profile in all_profiles
#             if profile.get('user') == self.request.user.username
#         ]

#         # Sort profiles by the 'end_time' field (assuming it's formatted properly as date or datetime)
#         # Sort in descending order to get the most recent ones first
#         user_profiles_sorted = sorted(user_profiles, key=lambda p: p.get('end_time', ''), reverse=True)

#         # Get the 5 most recent profiles based on 'end_time'
#         recent_profiles = user_profiles_sorted[:5]

#         # Fetch the current user's sessions from MikroTik
#         user_sessions = mikrotik_manager.get_user_sessions(self.request.user.username)
   
#         # Filter sessions with the status 'start' (active sessions)
#         # active_sessions = [session for session in user_sessions if session.get('status') == 'start' or 'start,interim']
#         active_sessions = [session for session in user_sessions if session.get('ended') == None]

#         # Sort in descending order to get the most recent ones first
#         # user_profiles_sorted = sorted(user_sessions, key=lambda p: p.get('end_time', ''), reverse=True)

#         context['running_active_profiles'] = running_active_profiles
#         context['related_profiles'] = related_profiles
#         context['recent_profiles'] = recent_profiles
#         context['user_sessions'] = user_sessions
#         context['active_sessions'] = active_sessions

#         return context


# class UserProfileListView(LoginRequiredMixin, ListView):
#     model = User
#     template_name = 'usermanager/user_profile_list.html'
#     context_object_name = 'user_profiles'

#     def get_queryset(self):
#         queryset = super().get_queryset()

#         # Superusers see all profiles, regular users only see their own
#         if self.request.user.is_superuser:
#             return queryset
#         return queryset.filter(pk=self.request.user.pk)

#     def get_context_data(self, **kwargs):
#         context = super().get_context_data(**kwargs)
#         # Add user profiles to the context
#         if self.request.user.is_superuser:
#             context['user_profiles'] = mikrotik_manager.get_user_profiles()  # Superusers get all profiles
#         else:
#             all_profiles = mikrotik_manager.get_user_profiles()  # Fetch all profiles
#             user_profiles = [profile for profile in all_profiles if profile.get('user') == self.request.user.username]
#             context['user_profiles'] = user_profiles

#         return context


# class SessionListView(LoginRequiredMixin, ListView):
#     template_name = 'usermanager/sessions.html'
#     context_object_name = 'mikrotik_sessions'

#     def get_queryset(self):
#         # Superusers see all sessions; regular users see only their own
#         if self.request.user.is_superuser:
#             return mikrotik_manager.get_sessions()
#         else:
#             if hasattr(mikrotik_manager, 'get_user_sessions'):
#                 return mikrotik_manager.get_user_sessions(self.request.user.username)
#             else:
#                 raise ImproperlyConfigured("'MikroTikUserManager' must implement 'get_user_sessions' for regular users.")

#     def get_context_data(self, **kwargs):
#         context = super().get_context_data(**kwargs)
#         # Add profiles to the context
#         if self.request.user.is_superuser:
#             context['user_profiles'] = mikrotik_manager.get_user_profiles()  # Get all profiles for superusers
#         else:
#             all_profiles = mikrotik_manager.get_user_profiles()  # Fetch all profiles
#             user_profile = next((profile for profile in all_profiles if profile.get('user') == self.request.user.username), None)
#             context['user_profile'] = user_profile

#         return context