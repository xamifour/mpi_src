# mpi_src/usermanager/views.py
import requests
import paystack
import datetime

from django.shortcuts import render, redirect, get_object_or_404
from django.conf import settings
from django.contrib.auth import login, logout
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy, reverse
from django.core.exceptions import ImproperlyConfigured
from django.views.generic import ListView, DetailView, FormView, RedirectView, View
from django.http import JsonResponse

from .forms import SignUpForm, SignInForm
from .models import User, Profile, UserProfile, Payment, Session
from .mikrotik_userman import init_mikrotik_manager

paystack.api_key = settings.PAYSTACK_SECRET_KEY
mikrotik_manager = init_mikrotik_manager()


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
        # Always return the current logged-in user
        return self.request.user

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Fetch the user profiles related to the current user from Django models
        user_profiles = UserProfile.objects.filter(user=self.request.user)
        # Sort profiles by 'end_time' and get the 5 most recent ones
        recent_user_profiles = user_profiles.order_by('-end_time')[:5]       
        # Filter running-active profiles
        running_active_profiles = user_profiles.filter(state='running-active')       
        # Get related profiles
        related_profiles = Profile.objects.filter(id__in=user_profiles.values('profile_id'))

        user_payments = Payment.objects.filter(user=self.request.user)
        recent_user_payments = user_payments.order_by('-trans_end')[:5]   

        # Fetch user sessions from the Session model
        user_sessions = Session.objects.filter(user=self.request.user).order_by('-session_id')
        # Filter active sessions (assuming 'ended' is a nullable field)
        active_sessions = user_sessions.filter(ended__isnull=True)

        context['running_active_profiles'] = running_active_profiles
        context['related_profiles'] = related_profiles
        context['recent_user_profiles'] = recent_user_profiles
        context['user_sessions'] = user_sessions
        context['recent_user_payments'] = recent_user_payments
        context['active_sessions'] = active_sessions

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

    # def get_context_data(self, **kwargs):
    #     context = super().get_context_data(**kwargs)
    #     context['payments'] = self.get_queryset()
    #     return context
    

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
        profile = get_object_or_404(Profile, id=profile_id)

        payment_data = {
            "email": request.user.email,
            "amount": int(profile.price * 100),  # Amount in kobo
            "reference": f"{request.user.id}-{profile_id}",
            "callback_url": request.build_absolute_uri(reverse('verify_payment'))
        }

        headers = {
            "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
            "Content-Type": "application/json"
        }

        # Send request to Paystack to initialize payment
        response = requests.post('https://api.paystack.co/transaction/initialize', json=payment_data, headers=headers)

        if response.status_code == 200:
            response_data = response.json()
            payment_url = response_data['data']['authorization_url']
            return redirect(payment_url)
        else:
            return JsonResponse({'error': 'Payment initiation failed'}, status=500)


# Verify payment and update Payment model
from usermanager.tasks import create_user_profile_in_mikrotik
import logging

logger = logging.getLogger(__name__)

class VerifyPaymentView(View):
    def get(self, request):
        reference = request.GET.get('reference')
        if not reference:
            return JsonResponse({'error': 'Reference is required'}, status=400)

        headers = {
            "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
            "Content-Type": "application/json"
        }

        try:
            # Verify the payment via Paystack API
            response = requests.get(f'https://api.paystack.co/transaction/verify/{reference}', headers=headers)
            response.raise_for_status()  # Raise an HTTPError for bad responses
            response_data = response.json()

            # Check if payment is successful
            if response_data.get('data', {}).get('status') == 'success':
                user_id, profile_id = reference.split('-')
                profile = get_object_or_404(Profile, id=profile_id)

                user_profile, created = UserProfile.objects.get_or_create(user_id=user_id, profile=profile)

                # Create a payment entry
                payment = Payment.objects.create(
                    user_profile=user_profile,
                    profile=profile,
                    method="ONLINE",
                    trans_start=datetime.datetime.now(),
                    trans_status="completed",
                    price=response_data['data']['amount'] / 100,  # Convert from kobo to Naira
                    paystack_reference=reference
                )

                # Once the payment is verified as successful, trigger the MikroTik synchronization for the user profile.
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


# '''
# If you want to trigger the sync_mikrotik_data task after a specific event.
# Example of triggering the sync after a successful payment:
# '''
# # In your view that handles payment success
# from usermanager.tasks import sync_mikrotik_data

# def payment_success(request):
#     # Process the successful payment

#     # Trigger the MikroTik data sync
#     sync_mikrotik_data.delay()

#     return HttpResponse("Payment successful and sync triggered.")

# # By calling sync_mikrotik_data.delay(), you ensure the task is queued in the 
# # background for execution.