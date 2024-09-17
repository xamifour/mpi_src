# mpi_src/
# │
# ├── usermanager/
# │   ├── models.py

# mpi_src/usermanager/models.py
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext_lazy as _

MAX_LEN = 67

class User(AbstractUser):
    group = models.CharField(_('group'), max_length=MAX_LEN, blank=True, null=True)
    name = models.CharField(_('name'), max_length=MAX_LEN, unique=True, blank=True, null=True)
    disabled = models.BooleanField(_('disabled'), default=False)
    otp_secret = models.CharField(_('otp-secret'), max_length=256, blank=True, null=True)
    shared_users = models.PositiveIntegerField(_('shared-users'), default=1)
    attributes = models.CharField(_('attributes'), max_length=MAX_LEN, blank=True, null=True)
    plain_password = models.CharField(_('plain password'), max_length=MAX_LEN, blank=True, null=True)
    phone = models.CharField(_('phone'), max_length=10, blank=True, null=True, help_text='0201234567')
    address = models.CharField(_('address'), max_length=256, blank=True, null=True)
    notes = models.CharField(_('notes'), max_length=1024, blank=True, null=True)
    mikrotik_id = models.CharField(max_length=20, unique=True, blank=True, null=True)  # Field to store MikroTik ID


    def save(self, *args, **kwargs):
        if self.password and not self.plain_password:
            self.plain_password = self.password  # Assuming you have the raw password available at creation time
        super().save(*args, **kwargs)

    class meta:
        ordering = '-mikrotik_id'

    def __str__(self):
        return self.username


class Profile(models.Model):
    name = models.CharField(_('name'), max_length=MAX_LEN, unique=True)
    name_for_users = models.CharField(_('name for users'), max_length=67, blank=True, null=True, 
                                help_text='Friendly name for user, eg Plan-100MB')
    price = models.DecimalField(_('price'), max_digits=10, decimal_places=2)
    starts_when = models.CharField(_('starts when'), max_length=MAX_LEN, default='assigned')
    validity = models.CharField(_('validity'), max_length=MAX_LEN, default='30d 00:00:00')
    override_shared_users = models.CharField(_('override shared users'), max_length=MAX_LEN, default='off')
    mikrotik_id = models.CharField(max_length=20, unique=True, blank=True, null=True)  # Field to store MikroTik ID

    class meta:
        ordering = '-mikrotik_id'

    def __str__(self):
        return f"{self.name_for_users} - {self.price} - {self.validity}"


class UserProfile(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    profile = models.ForeignKey(Profile, on_delete=models.CASCADE)
    state = models.CharField(_('state'), max_length=MAX_LEN, blank=True, null=True)
    end_time = models.DateTimeField(_('end time'), blank=True, null=True)
    mikrotik_id = models.CharField(max_length=20, unique=True, blank=True, null=True)  # Field to store MikroTik ID

    class Meta:
        unique_together = ('user', 'profile', 'state', 'end_time')
        ordering = ['-mikrotik_id']

    def __str__(self):
        return f"{self.user.username} - {self.profile.name} - {self.state} - {self.end_time}"
    
    def get_state(self):
        if self.state == 'used': # time has ended, may or may not have data
            return 'Time Elapsed'
        elif self.state == 'running':
            return 'Data Exhausted' # data has finished
        else:
            return 'Active' # time and data not finished


class Payment(models.Model):
    COPY_FROM_CHOICES = [
        ('manual', 'Manual'),
        ('auto', 'Auto'),
    ]

    TRANS_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]

    METHOD_CHOICES = [
        ('ONLINE', 'Online'),
        ('OFFLINE', 'Offline'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    user_profile = models.ForeignKey(UserProfile, on_delete=models.CASCADE)
    profile = models.ForeignKey(Profile, on_delete=models.SET_NULL, null=True, blank=True)
    copy_from = models.CharField(max_length=MAX_LEN, choices=COPY_FROM_CHOICES)
    method = models.CharField(max_length=MAX_LEN, choices=METHOD_CHOICES, default='OFFLINE')
    trans_start = models.DateTimeField()
    trans_end = models.DateTimeField(null=True, blank=True)
    trans_status = models.CharField(max_length=MAX_LEN, choices=TRANS_STATUS_CHOICES)
    user_message = models.TextField(null=True, blank=True)
    currency = models.CharField(max_length=MAX_LEN, default="GHS")
    price = models.DecimalField(max_digits=10, decimal_places=2)
    paystack_reference = models.CharField(max_length=100, null=True, blank=True)
    mikrotik_id = models.CharField(max_length=20, unique=True, blank=True, null=True)  # Field to store MikroTik ID

    class meta:
        ordering = '-trans_end'

    def __str__(self):
        return f"Payment for {self.user_profile} - {self.method} ({self.trans_status})"
    

class Session(models.Model):
    session_id = models.CharField(_('Session ID'), max_length=MAX_LEN, unique=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    nas_ip_address = models.GenericIPAddressField(_('NAS IP Address'), blank=True, null=True)
    nas_port_id = models.CharField(_('NAS Port ID'), max_length=MAX_LEN)
    nas_port_type = models.CharField(_('NAS Port Type'), max_length=MAX_LEN)
    calling_station_id = models.CharField(_('Calling Station ID'), max_length=MAX_LEN)
    download = models.BigIntegerField(_('Download'))
    upload = models.BigIntegerField(_('Upload'))
    uptime = models.CharField(_('Uptime'), max_length=MAX_LEN)
    status = models.CharField(_('Status'), max_length=MAX_LEN)
    started = models.DateTimeField(_('Started'))
    ended = models.DateTimeField(_('Ended'), null=True, blank=True)
    last_accounting_packet = models.DateTimeField(_('Last Accounting Packet'), null=True, blank=True)
    terminate_cause = models.CharField(_('Terminate Cause'), max_length=MAX_LEN, blank=True, null=True)
    user_address = models.GenericIPAddressField(_('User Address'))
    mikrotik_id = models.CharField(max_length=20, unique=True, blank=True, null=True)  # Field to store MikroTik ID

    class meta:
        ordering = '-session_id'

    def __str__(self):
        return f"Session {self.session_id} for {self.user.username}"

    def get_session_status(self):
        closed_statuses = {'stop', 'close-acked', 'expired'}
        # Split the status string by commas
        statuses = set(self.status.split(','))  # Convert to set for efficient membership testing
        if closed_statuses & statuses:  # Check if there is any intersection
            return 'Closed'
        else:
            return 'Running'
        
    def get_terminate_cause(self):
        if self.terminate_cause == 'Admin Reset':
            return 'Data finished'
        
    def session_traffic(self):
        return self.download + self.upload
    


# Avoid importing tasks at the top. Use signals or inline imports when needed.
def trigger_mikrotik_tasks(instance, created, **kwargs):
    # Import tasks locally to avoid circular import
    from usermanager.tasks import (
        create_user_in_mikrotik, update_user_in_mikrotik, delete_user_in_mikrotik,
        create_profile_in_mikrotik, update_profile_in_mikrotik, delete_profile_in_mikrotik,
        create_user_profile_in_mikrotik, update_user_profile_in_mikrotik, delete_user_profile_in_mikrotik
    )

    if isinstance(instance, User):
        if created:
            create_user_in_mikrotik.delay(instance.id)
        else:
            update_user_in_mikrotik.delay(instance.id)
    elif isinstance(instance, Profile):
        if created:
            create_profile_in_mikrotik.delay(instance.id)
        else:
            update_profile_in_mikrotik.delay(instance.id)
    elif isinstance(instance, UserProfile):
        if created:
            create_user_profile_in_mikrotik.delay(instance.id)
        else:
            update_user_profile_in_mikrotik.delay(instance.id)

# Example signal setup to trigger MikroTik tasks when models are saved
from django.db.models.signals import post_save
from django.dispatch import receiver

@receiver(post_save, sender=User)
def trigger_user_tasks(sender, instance, created, **kwargs):
    trigger_mikrotik_tasks(instance, created, **kwargs)

@receiver(post_save, sender=Profile)
def trigger_profile_tasks(sender, instance, created, **kwargs):
    trigger_mikrotik_tasks(instance, created, **kwargs)

@receiver(post_save, sender=UserProfile)
def trigger_user_profile_tasks(sender, instance, created, **kwargs):
    trigger_mikrotik_tasks(instance, created, **kwargs)