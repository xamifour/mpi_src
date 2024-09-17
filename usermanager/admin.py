# mpi_src/usermanager/admin.py

import logging
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.conf import settings
from django.shortcuts import redirect, get_object_or_404
from django.utils.translation import gettext_lazy as _
from django.utils.html import format_html
from django.urls import path
from django.shortcuts import redirect
from django.utils.timezone import now

from .models import User, UserProfile, Profile, Payment, Session
from .mikrotik_userman import init_mikrotik_manager

logger = logging.getLogger(__name__)

# Initialize the MikroTikUserManager instance using the factory function
mikrotik_manager = init_mikrotik_manager()

class UserProfileInline(admin.TabularInline):
    model = UserProfile
    extra   = 1
    can_delete = False
    verbose_name_plural = 'User Profile'
    fk_name = 'user'
    readonly_fields = ['end_time', 'state']

# ------------------------------------------------ user
class UserAdmin(BaseUserAdmin):
    inlines = (UserProfileInline, )
    list_display = ('mikrotik_id', 'username', 'email', 'first_name', 'last_name', 'is_staff', 'group', 'disabled')
    search_fields = ('username', 'email')
    ordering = ('username',)
    filter_horizontal = ('groups', 'user_permissions')

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'password1', 'password2', 'group', 'shared_users', 'disabled', 'attributes', 'plain_password'),
        }),
    )
    
    fieldsets = (
        (None, {'fields': ('username', 'password', 'payment_button')}),
        (_('Personal info'), {'fields': ('first_name', 'last_name', 'email', 'phone', 'address', 'notes')}),
        (_('Mikrotik info'), {'fields': ('group', 'otp_secret', 'shared_users', 'attributes', 'plain_password')}),
        (_('Permissions'), {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        (_('Important dates'), {'fields': ('last_login', 'date_joined')}),
    )

    actions = [
        'delete_from_mikrotik',
        'sync_with_mikrotik',
        'sync_from_mikrotik'
    ]
    readonly_fields = ['payment_button', 'last_login', 'date_joined']

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                '<int:user_id>/create-payment/<int:user_profile_id>/',
                self.admin_site.admin_view(self.create_payment_view),
                name='create-payment',
            ),
        ]
        return custom_urls + urls

    def create_payment_view(self, request, user_id, user_profile_id):
        user = get_object_or_404(User, pk=user_id)
        user_profile = get_object_or_404(UserProfile, pk=user_profile_id)

        payment = Payment.objects.create(
            user_profile=user_profile,
            copy_from='manual',
            method='Credit Card',
            profile=user_profile.profile,
            trans_start=now(),
            trans_status='pending',
            user_message='Payment initiated.',
            currency='USD',
            price=user_profile.profile.price
        )

        payment.trans_status = 'completed'
        payment.trans_end = now()
        payment.save()

        self.message_user(request, f"Payment created for profile '{user_profile.profile.name}' assigned to user '{user.username}'.")
        return redirect(f"../../{user_id}/change/")

    def payment_button(self, obj):
        user_profiles = UserProfile.objects.filter(user=obj)
        if user_profiles.exists():
            buttons = []
            for user_profile in user_profiles:
                url = f"{obj.id}/create-payment/{user_profile.id}/"
                logger.debug(f"Generated payment URL: {url}")
                buttons.append(format_html(
                    '<a class="button" href="{}">Pay for {}</a>',
                    url,
                    f"{user_profile.profile.name} ({user_profile.state})"
                ))
            return format_html('<br>'.join(buttons))
        else:
            return "No profiles assigned"

    payment_button.short_description = 'Create Payment'
    payment_button.allow_tags = True

    def delete_from_mikrotik(self, request, queryset):
        """
        This action deletes selected users from MikroTik but not from Django.
        """
        for obj in queryset:
            try:
                users = mikrotik_manager.get_users()
                existing_user = next((u for u in users if u['name'] == obj.username), None)

                if existing_user:
                    mikrotik_manager.delete_user(user_id=existing_user['.id'])
                    self.message_user(request, f"User '{obj.username}' deleted from MikroTik UserManager.")
                else:
                    self.message_user(request, f"User '{obj.username}' does not exist in MikroTik UserManager.", level='warning')
            except Exception as e:
                self.message_user(request, f"Error deleting user '{obj.username}' from MikroTik UserManager: {e}", level='error')

    delete_from_mikrotik.short_description = "Delete selected users from MikroTik UserManager"

    def sync_with_mikrotik(self, request, queryset):
        """
        This action syncs selected users with MikroTik.
        """
        for obj in queryset:
            try:
                profile_name = obj.group or 'default'
                users = mikrotik_manager.get_users()
                existing_user = next((u for u in users if u['name'] == obj.username), None)

                if existing_user:
                    mikrotik_manager.update_user(
                        user_id=existing_user['.id'],
                        password=obj.plain_password,  # Use plain_password for syncing
                        group=profile_name,
                        shared_users=obj.shared_users,
                        disabled=obj.disabled,
                        attributes=obj.attributes
                    )
                    self.message_user(request, f"User '{obj.username}' updated in MikroTik UserManager.")
                else:
                    mikrotik_manager.create_user(
                        username=obj.username,
                        password=obj.plain_password,  # Use plain_password for syncing
                        group=profile_name,
                        shared_users=obj.shared_users,
                        disabled=obj.disabled,
                        attributes=obj.attributes
                    )
                    self.message_user(request, f"User '{obj.username}' created in MikroTik UserManager.")
            except Exception as e:
                self.message_user(request, f"Error syncing user '{obj.username}' with MikroTik UserManager: {e}", level='error')

    sync_with_mikrotik.short_description = "Sync selected users with MikroTik UserManager"

    def sync_from_mikrotik(self, request, queryset):
        """
        This action syncs users from MikroTik to Django.
        """
        try:
            users = mikrotik_manager.get_users()
            for user_data in users:
                username = user_data.get('name')
                defaults = {
                    'group': user_data.get('group'),
                    'password': user_data.get('password'),  # Normally, passwords would be hashed.
                    'shared_users': int(user_data.get('shared-users', 1)),
                    'disabled': user_data.get('disabled') == 'true',
                    'attributes': user_data.get('attributes'),
                }
                user, created = User.objects.update_or_create(username=username, defaults=defaults)
                if created:
                    self.message_user(request, f"User '{username}' created in Django.")
                else:
                    self.message_user(request, f"User '{username}' updated in Django.")
        except Exception as e:
            self.message_user(request, f"Error syncing users from MikroTik: {e}", level='error')

    sync_from_mikrotik.short_description = "Sync users from MikroTik to Django"


# ------------------------------------------------ profile
# from .signals import disable_signals  # Import the context manager

class ProfileAdmin(admin.ModelAdmin):
    list_display = ('mikrotik_id', 'name', 'price', 'validity')
    actions = ['sync_profiles_from_mikrotik', 'sync_profiles_to_mikrotik']

    def sync_profiles_from_mikrotik(self, request, queryset):
        """
        This action syncs profiles from MikroTik to Django.
        """
        try:
            mikrotik_manager = init_mikrotik_manager()
            profiles = mikrotik_manager.get_profiles()
            for profile_data in profiles:
                Profile.objects.update_or_create(
                    name=profile_data['name'],
                    defaults={
                        'name_for_users': profile_data['name-for-users'],
                        'price': profile_data['price'],
                        'starts_when': profile_data['starts-when'],
                        'validity': profile_data['validity'],
                        'override_shared_users': profile_data['override-shared-users'],
                    }
                )
            self.message_user(request, "Profiles successfully synced from MikroTik to Django.")
        except Exception as e:
            self.message_user(request, f"Error syncing profiles from MikroTik: {e}", level='error')

    def sync_profiles_to_mikrotik(self, request, queryset):
        """
        This action syncs profiles from Django to MikroTik.
        """
        try:
            mikrotik_manager = init_mikrotik_manager()
            for profile in queryset:
                mikrotik_manager.create_profile(
                    name=profile.name,
                    name_for_users=profile.name_for_users,
                    price=str(profile.price),
                    starts_when=profile.starts_when,
                    validity=profile.validity,
                    override_shared_users=profile.override_shared_users
                )
            self.message_user(request, "Profiles successfully synced to MikroTik.")
        except Exception as e:
            self.message_user(request, f"Error syncing profiles to MikroTik: {e}", level='error')

    sync_profiles_from_mikrotik.short_description = "Sync profiles from MikroTik to Django"
    sync_profiles_to_mikrotik.short_description = "Sync profiles to MikroTik"


class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('mikrotik_id', 'user', 'profile', 'state', 'end_time')
    actions = ['sync_user_profiles_from_mikrotik', 'sync_user_profiles_to_mikrotik']
    readonly_fields = ['end_time', 'state']

    def sync_user_profiles_from_mikrotik(self, request, queryset):
        """
        This action syncs user profiles from MikroTik to Django.
        """
        try:
            mikrotik_manager = init_mikrotik_manager()
            user_profiles = mikrotik_manager.get_user_profiles()
            for user_profile_data in user_profiles:
                try:
                    user = User.objects.get(username=user_profile_data['user'])
                    profile = Profile.objects.get(name=user_profile_data['profile'])
                    UserProfile.objects.update_or_create(
                        user=user,
                        profile=profile,
                        defaults={
                            'state': user_profile_data['state'],
                            'end_time': user_profile_data.get('end-time', 'unlimited')
                        }
                    )
                except User.DoesNotExist:
                    self.message_user(request, f"User '{user_profile_data['user']}' does not exist in Django.", level='error')
                except Profile.DoesNotExist:
                    self.message_user(request, f"Profile '{user_profile_data['profile']}' does not exist in Django.", level='error')
            self.message_user(request, "User profiles successfully synced from MikroTik to Django.")
        except Exception as e:
            self.message_user(request, f"Error syncing user profiles from MikroTik: {e}", level='error')

    def sync_user_profiles_to_mikrotik(self, request, queryset):
        """
        This action syncs user profiles from Django to MikroTik.
        """
        try:
            mikrotik_manager = init_mikrotik_manager()
            for user_profile in queryset:
                mikrotik_manager.create_user_profile(
                    user=user_profile.user.username,
                    profile=user_profile.profile.name
                )
            self.message_user(request, "User profiles successfully synced to MikroTik.")
        except Exception as e:
            self.message_user(request, f"Error syncing user profiles to MikroTik: {e}", level='error')

    sync_user_profiles_from_mikrotik.short_description = "Sync user profiles from MikroTik to Django"
    sync_user_profiles_to_mikrotik.short_description = "Sync user profiles to MikroTik"


class PaymentAdmin(admin.ModelAdmin):
    list_display = ('user_profile', 'method', 'price', 'trans_start', 'trans_end', 'trans_status')
    search_fields = ('user_profile__user__username', 'method', 'price')
    list_filter = ('method', 'trans_status')

    actions = ['sync_payments_to_mikrotik']

    def sync_payments_to_mikrotik(self, request, queryset):
        """
        Sync selected payments from Django to MikroTik.
        """
        try:
            mikrotik_manager = init_mikrotik_manager()
            for payment in queryset:
                # Create or update payment in MikroTik
                mikrotik_manager.create_payment(
                    user_profile=payment.user_profile.id,  # or use an appropriate identifier
                    profile=payment.profile.name if payment.profile else None,
                    copy_from=payment.copy_from,
                    method=payment.method,
                    trans_start=payment.trans_start,
                    trans_end=payment.trans_end,
                    trans_status=payment.trans_status,
                    user_message=payment.user_message,
                    currency=payment.currency,
                    price=str(payment.price),  # Ensure price is in the correct format for MikroTik
                    paystack_reference=payment.paystack_reference
                )
            self.message_user(request, "Payments successfully synced to MikroTik.")
        except Exception as e:
            self.message_user(request, f"Error syncing payments to MikroTik: {e}", level='error')

    sync_payments_to_mikrotik.short_description = "Sync selected payments to MikroTik"


# ------------------------------------------------ session
class SessionAdmin(admin.ModelAdmin):
    list_display = ('mikrotik_id', 'session_id', 'user', 'nas_ip_address', 'started', 'ended', 'terminate_cause')
    search_fields = ('session_id', 'user__username', 'nas_ip_address')
    list_filter = ('nas_ip_address', 'nas_port_type', 'status', 'terminate_cause')
    readonly_fields = [
        'mikrotik_id',
        'session_id',
        'user',
        'nas_ip_address',
        'nas_port_id',
        'nas_port_type',
        'calling_station_id',
        'download',
        'upload',
        'uptime',
        'status',
        'started',
        'ended',
        'terminate_cause',
        'user_address',
        'last_accounting_packet'
    ]

# Register your models here.
admin.site.register(User, UserAdmin)
admin.site.register(Profile, ProfileAdmin)
admin.site.register(UserProfile, UserProfileAdmin)
admin.site.register(Payment, PaymentAdmin)
admin.site.register(Session, SessionAdmin)
