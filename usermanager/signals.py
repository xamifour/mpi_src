# # mpi_src/usermanager/signals.py
# from django.db.models.signals import post_save, post_delete
# from django.dispatch import receiver
# from django.conf import settings
# from contextlib import contextmanager
# from django.utils.timezone import now

# from .mikrotik_userman import init_mikrotik_manager
# from .models import User, Profile, UserProfile, Payment

# # Initialize the MikroTik manager
# mikrotik_manager = init_mikrotik_manager()


# # # create the UserProfile automatically whenever a User is created
# # @receiver(post_save, sender=User)
# # def create_user_profile(sender, instance, created, **kwargs):
# #     if created:
# #         UserProfile.objects.get_or_create(user=instance)

# @contextmanager
# def disable_signals():
#     post_save.disconnect(sync_profile_to_mikrotik, sender=Profile)
#     post_save.disconnect(sync_user_profile_to_mikrotik, sender=UserProfile)
#     post_delete.disconnect(delete_profile_from_mikrotik, sender=Profile)
#     post_delete.disconnect(delete_user_profile_from_mikrotik, sender=UserProfile)
#     try:
#         yield
#     finally:
#         post_save.connect(sync_profile_to_mikrotik, sender=Profile)
#         post_save.connect(sync_user_profile_to_mikrotik, sender=UserProfile)
#         post_delete.connect(delete_profile_from_mikrotik, sender=Profile)
#         post_delete.connect(delete_user_profile_from_mikrotik, sender=UserProfile)

# # signal handlers for syncing and deleting objects in Mikrotik
# @receiver(post_save, sender=Profile)
# def sync_profile_to_mikrotik(sender, instance, created, **kwargs):
#     if created:
#         mikrotik_manager.create_profile(
#             name=instance.name,
#             name_for_users=instance.name_for_users,
#             price=str(instance.price),
#             starts_when=instance.starts_when,
#             validity=instance.validity,
#             override_shared_users=instance.override_shared_users
#         )
#     else:
#         profiles = mikrotik_manager.get_profiles()
#         existing_profile = next((p for p in profiles if p['name'] == instance.name), None)
#         if existing_profile:
#             mikrotik_manager.update_profile(
#                 profile_id=existing_profile['.id'],
#                 name_for_users=instance.name_for_users,
#                 price=str(instance.price),
#                 starts_when=instance.starts_when,
#                 validity=instance.validity,
#                 override_shared_users=instance.override_shared_users
#             )

# @receiver(post_delete, sender=Profile)
# def delete_profile_from_mikrotik(sender, instance, **kwargs):
#     profiles = mikrotik_manager.get_profiles()
#     existing_profile = next((p for p in profiles if p['name'] == instance.name), None)
#     if existing_profile:
#         mikrotik_manager.delete_profile(profile_id=existing_profile['.id'])

# @receiver(post_save, sender=UserProfile)
# def sync_user_profile_to_mikrotik(sender, instance, created, **kwargs):
#     if created:
#         mikrotik_manager.create_user_profile(
#             user=instance.user.username,
#             profile=instance.profile.name,
#         )
#     else:
#         user_profiles = mikrotik_manager.get_user_profiles()
#         existing_user_profile = next((up for up in user_profiles if up['user'] == instance.user.username and up['profile'] == instance.profile.name), None)
#         if existing_user_profile:
#             mikrotik_manager.update_user_profile(
#                 user_profile_id=existing_user_profile['.id'],
#                 state=instance.state,
#                 end_time=instance.end_time
#             )

# @receiver(post_delete, sender=UserProfile)
# def delete_user_profile_from_mikrotik(sender, instance, **kwargs):
#     user_profiles = mikrotik_manager.get_user_profiles()
#     existing_user_profile = next((up for up in user_profiles if up['user'] == instance.user.username and up['profile'] == instance.profile.name), None)
#     if existing_user_profile:
#         mikrotik_manager.delete_user_profile(user_profile_id=existing_user_profile['.id'])


# # # create payment object when user is assigned to a profile
# # @receiver(post_save, sender=UserProfile)
# # def create_payment_on_profile_assignment(sender, instance, created, **kwargs):
# #     # Only create a payment if a profile is assigned
# #     if instance.profile:
# #         # Check if this is the first time the profile is being assigned to the user
# #         if created or 'profile' in instance.get_dirty_fields():
# #             Payment.objects.create(
# #                 user_profile=instance,
# #                 copy_from='manual',  # or another method if needed
# #                 method='MoMo',  # or another method if needed
# #                 profile=instance.profile,
# #                 trans_start=now(),
# #                 trans_status='completed',  # Assuming the payment is processed successfully
# #                 user_message='Payment created upon profile assignment.',
# #                 currency='GHS',  # or use another currency if needed
# #                 price=instance.profile.price,
# #                 trans_end=now()
# #             )
