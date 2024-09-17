# mpi_src/usermanager/urls.py

from django.urls import path
from .views import (
    SignUpView, SignInView, SignOutView, UserDetailView,
    ProfileListView, UserProfileListView, PaymentListView, SessionListView,
    InitiatePaymentView, VerifyPaymentView, payment_success, payment_failed
)

urlpatterns = [
    path('sign-up/', SignUpView.as_view(), name='sign_up'),
    path('sign-in/', SignInView.as_view(), name='sign_in'),
    path('sign-out/', SignOutView.as_view(), name='sign_out'),
    path('', UserDetailView.as_view(), name='user_detail'),
    path('plans/', ProfileListView.as_view(), name='profile_list'),
    path('user-profiles/', UserProfileListView.as_view(), name='user_profile_list'),
    path('payments/', PaymentListView.as_view(), name='payment_list'),
    path('sessions/', SessionListView.as_view(), name='session_list'),

    # Payment paths
    path('initiate-payment/<int:profile_id>/', InitiatePaymentView.as_view(), name='initiate_payment'),
    path('payment/verify/', VerifyPaymentView.as_view(), name='verify_payment'),
    path('payment/success/', payment_success, name='payment_success'),
    path('payment/failed/', payment_failed, name='payment_failed'),
]
