# mpi_src/usermanager/tasks.py
import logging
from django.db import transaction, IntegrityError
from celery import shared_task
from datetime import datetime
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

from usermanager.mikrotik_userman import init_mikrotik_manager
from usermanager.models import User, Profile, UserProfile, Session

logger = logging.getLogger(__name__)

# Initialize the MikroTik manager
mikrotik_manager = init_mikrotik_manager()


# ------------------------------- from MikroTik to Django
@shared_task
def sync_mikrotik_data():
    """Synchronizes MikroTik data (users, profiles, user profiles, and sessions) with Django."""
    logger.debug("Starting sync_mikrotik_data task")

    try:
        sync_users(mikrotik_manager)
        sync_profiles(mikrotik_manager)
        sync_user_profiles(mikrotik_manager)
        sync_sessions(mikrotik_manager)
    except Exception as e:
        logger.error(f"Error syncing data: {e}", exc_info=True)
    else:
        logger.info("MikroTik sync completed successfully")


def sync_users(mikrotik_manager):
    """Synchronizes users from MikroTik to the Django database."""
    try:
        with transaction.atomic():
            mikrotik_users = mikrotik_manager.get_users()
            for mt_user in mikrotik_users:
                user, created = User.objects.update_or_create(
                    username=mt_user['name'],
                    defaults={
                        'group': mt_user.get('group', ''),
                        'disabled': mt_user.get('disabled') == 'true',
                        'otp_secret': mt_user.get('otp-secret', ''),
                        'shared_users': int(mt_user.get('shared-users', 0)),
                        'plain_password': mt_user.get('password', ''),
                        'mikrotik_id': mt_user['.id'],  # Store MikroTik ID
                    }
                )
                if created:
                    logger.info(f'Created new user: {user.username}')
                else:
                    logger.info(f'Updated user: {user.username}')
    except Exception as e:
        logger.error(f"Error syncing users: {e}", exc_info=True)
        raise


def sync_profiles(mikrotik_manager):
    """Synchronizes profiles from MikroTik to the Django database."""
    try:
        with transaction.atomic():
            mikrotik_profiles = mikrotik_manager.get_profiles()
            for mt_profile in mikrotik_profiles:
                profile, created = Profile.objects.update_or_create(
                    name=mt_profile['name'],
                    defaults={
                        'name_for_users': mt_profile.get('name-for-users', ''),
                        'price': mt_profile.get('price', '0.00'),
                        'starts_when': mt_profile.get('starts-when', 'assigned'),
                        'validity': mt_profile.get('validity', '30d 00:00:00'),
                        'override_shared_users': mt_profile.get('override-shared-users', 'off'),
                        'mikrotik_id': mt_profile['.id'],  # Store MikroTik ID
                    }
                )
                if created:
                    logger.info(f'Created new profile: {profile.name}')
                else:
                    logger.info(f'Updated profile: {profile.name}')
    except Exception as e:
        logger.error(f"Error syncing profiles: {e}", exc_info=True)
        raise


# def sync_user_profiles(mikrotik_manager):
#     """Synchronizes user profiles from MikroTik to the Django database."""
#     try:
#         with transaction.atomic():
#             mikrotik_user_profiles = mikrotik_manager.get_user_profiles()
#             for mt_user_profile in mikrotik_user_profiles:
#                 user = User.objects.filter(username=mt_user_profile['user']).first()
#                 profile = Profile.objects.filter(name=mt_user_profile['profile']).first()

#                 if not user or not profile:
#                     logger.warning(f"Skipping user profile sync: user '{mt_user_profile['user']}' or profile '{mt_user_profile['profile']}' not found.")
#                     continue

#                 # Ensure 'end-time' is properly formatted as a DateTimeField
#                 end_time_str = mt_user_profile.get('end-time', None)
#                 end_time = datetime.strptime(end_time_str, '%Y-%m-%d %H:%M:%S') if end_time_str else None

#                 try:
#                     user_profile, created = UserProfile.objects.update_or_create(
#                         mikrotik_id=mt_user_profile['.id'],  # Use MikroTik ID
#                         defaults={
#                             'user': user,
#                             'profile': profile,
#                             'state': mt_user_profile.get('state'),
#                             'end_time': end_time,
#                         }
#                     )
#                     if created:
#                         logger.info(f'Created new user profile for user: {user.username} with profile: {profile.name}')
#                     else:
#                         logger.info(f'Updated user profile for user: {user.username} with profile: {profile.name}')

#                 except IntegrityError as e:
#                     logger.error(f"Failed to sync user profile for {user.username}: {e}")
#                     continue

#     except Exception as e:
#         logger.error(f"Error syncing user profiles: {e}", exc_info=True)
#         raise
def sync_user_profiles(mikrotik_manager):
    """Synchronizes user profiles from MikroTik to the Django database."""
    try:
        with transaction.atomic():
            mikrotik_user_profiles = mikrotik_manager.get_user_profiles()
            for mt_user_profile in mikrotik_user_profiles:
                user = User.objects.filter(username=mt_user_profile['user']).first()
                profile = Profile.objects.filter(name=mt_user_profile['profile']).first()

                if not user or not profile:
                    logger.warning(f"Skipping sync: User '{mt_user_profile['user']}' or Profile '{mt_user_profile['profile']}' not found.")
                    continue

                end_time = mt_user_profile.get('end-time', None)
                state = mt_user_profile.get('state')
                mikrotik_id = mt_user_profile['.id']

                # Attempt to get the existing UserProfile by MikroTik ID
                user_profile, created = UserProfile.objects.get_or_create(
                    mikrotik_id=mikrotik_id,
                    defaults={
                        'user': user,
                        'profile': profile,
                        'state': state,
                        'end_time': end_time
                    }
                )

                # If the record already exists, check if we need to update it
                if not created:
                    # Only update state and end_time if they have changed
                    update_needed = False
                    if user_profile.state != state:
                        user_profile.state = state
                        update_needed = True
                    if user_profile.end_time != end_time:
                        user_profile.end_time = end_time
                        update_needed = True

                    if update_needed:
                        user_profile.save()

    except Exception as e:
        logger.error(f"Error syncing user profiles: {e}", exc_info=True)
        raise


def sync_sessions(mikrotik_manager):
    """Synchronizes sessions from MikroTik to the Django database."""
    try:
        with transaction.atomic():
            mikrotik_sessions = mikrotik_manager.get_sessions()
            for mt_session in mikrotik_sessions:
                user = User.objects.filter(username=mt_session.get('user')).first()
                if not user:
                    logger.warning(f"User '{mt_session.get('user')}' not found. Skipping session '{mt_session.get('acct-session-id')}'")
                    continue

                # Convert naive datetime to aware datetime if time zone support is active
                from django.utils import timezone
                ended_str = mt_session.get('ended')
                ended = None
                if ended_str:
                    ended = datetime.strptime(ended_str, '%Y-%m-%d %H:%M:%S')
                    if timezone.is_naive(ended):
                        ended = timezone.make_aware(ended)

                session_defaults = {
                    'user': user,  # Ensure user is assigned here
                    'nas_ip_address': mt_session.get('nas-ip-address'),
                    'nas_port_id': mt_session.get('nas-port-id'),
                    'nas_port_type': mt_session.get('nas-port-type'),
                    'calling_station_id': mt_session.get('calling-station-id'),
                    'download': int(mt_session.get('download', 0)),
                    'upload': int(mt_session.get('upload', 0)),
                    'uptime': mt_session.get('uptime'),
                    'status': mt_session.get('status'),
                    'started': mt_session.get('started'),
                    'ended': mt_session.get('ended', None),
                    'terminate_cause': mt_session.get('terminate-cause', None),
                    'user_address': mt_session.get('user-address'),
                    'last_accounting_packet': mt_session.get('last-accounting-packet'),
                    'mikrotik_id': mt_session.get('.id')  # Store MikroTik ID here
                }

                session, created = Session.objects.update_or_create(
                    session_id=mt_session.get('acct-session-id'),
                    defaults=session_defaults
                )

                if created:
                    logger.info(f'Created new session: {session.session_id}')
                else:
                    logger.info(f'Updated session: {session.session_id}')

                # Notify WebSocket clients of new session data
                send_traffic_update_to_group(session.session_id, {
                    "download": session.download,
                    "upload": session.upload,
                    "uptime": session.uptime,
                })
    except Exception as e:
        logger.error(f"Error syncing sessions: {e}", exc_info=True)
        raise

# WebSocket notification
def send_traffic_update_to_group(session_id, traffic_data):
    """Sends session traffic updates to WebSocket clients."""
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f'session_{session_id}',  # Group name
        {
            'type': 'send_traffic_update',  # Method to call in the consumer
            'traffic_data': traffic_data  # Traffic data to send
        }
    )


# ------------------------------- from Django to MikroTik
# event-based tasks triggered by CRUD operations
# --- User
@shared_task
def create_user_in_mikrotik(user_id):
    """Create a new user in MikroTik."""
    try:
        user = User.objects.get(id=user_id)
        response = mikrotik_manager.create_user(
            username=user.username,
            group=user.group,
            disabled=str(user.disabled).lower(),
            # otp_secret=user.otp_secret,
            shared_users=user.shared_users,
            plain_password=user.plain_password
        )
        user.mikrotik_id = response['.id']  # Save MikroTik ID
        user.save()
        logger.info(f'Created user {user.username} in MikroTik.')
    except User.DoesNotExist:
        logger.error(f'User with ID {user_id} does not exist.')
    except Exception as e:
        logger.error(f"Error creating User {user_id} in MikroTik: {e}", exc_info=True)
        raise


@shared_task
def update_user_in_mikrotik(user_id):
    """Update an existing user in MikroTik."""
    try:
        user = User.objects.get(id=user_id)
        if user.mikrotik_id:
            mikrotik_manager.update_user(
                user_id=user.mikrotik_id,
                group=user.group,
                disabled=str(user.disabled).lower(),
                # otp_secret=user.otp_secret,
                shared_users=user.shared_users,
                plain_password=user.plain_password
            )
            logger.info(f'Updated user {user.username} in MikroTik.')
        else:
            logger.warning(f"User {user.username} does not have a MikroTik ID.")
    except User.DoesNotExist:
        logger.error(f'User with ID {user_id} does not exist.')
    except Exception as e:
        logger.error(f"Error updating User {user_id} in MikroTik: {e}", exc_info=True)
        raise


@shared_task
def delete_user_in_mikrotik(user_id):
    """Delete a user in MikroTik."""
    try:
        user = User.objects.get(id=user_id)
        if user.mikrotik_id:
            mikrotik_manager.delete_user(user_id=user.mikrotik_id)
            logger.info(f'Deleted user {user.username} in MikroTik.')
        else:
            logger.warning(f"User {user.username} does not have a MikroTik ID.")
    except User.DoesNotExist:
        logger.error(f'User with ID {user_id} does not exist.')
    except Exception as e:
        logger.error(f"Error deleting User {user_id} in MikroTik: {e}", exc_info=True)
        raise


# --- Profile
# @shared_task
# def create_profile_in_mikrotik(profile_id):
#     """Create a new profile in MikroTik."""
#     try:
#         profile = Profile.objects.get(id=profile_id)
#         response = mikrotik_manager.create_profile(
#             name=profile.name,
#             name_for_users=profile.name_for_users,
#             price=str(profile.price),
#             starts_when=profile.starts_when,
#             validity=profile.validity,
#             override_shared_users=profile.override_shared_users
#         )
#         profile.mikrotik_id = response['.id']  # Save MikroTik ID
#         profile.save()
#         logger.info(f'Created profile {profile.name} in MikroTik.')
#     except Profile.DoesNotExist:
#         logger.error(f'Profile with ID {profile_id} does not exist.')
#     except Exception as e:
#         logger.error(f"Error creating Profile {profile_id} in MikroTik: {e}", exc_info=True)
#         raise
@shared_task
def create_profile_in_mikrotik(profile_id):
    """Create a new profile in MikroTik."""
    try:
        profile = Profile.objects.get(id=profile_id)
        logger.info(f'Creating profile in MikroTik: {profile}')

        response = mikrotik_manager.create_profile(
            name=profile.name,
            name_for_users=profile.name_for_users,
            price=str(profile.price),
            starts_when=profile.starts_when,
            validity=profile.validity,
            override_shared_users=profile.override_shared_users
        )

        if response is not None:
            profile.mikrotik_id = response['.id']  # Save MikroTik ID
            profile.save()
            logger.info(f'Successfully created profile {profile.name} in MikroTik with ID {response[".id"]}.')
        else:
            logger.error(f'Failed to create profile {profile.name} in MikroTik: No response received.')

    except Profile.DoesNotExist:
        logger.error(f'Profile with ID {profile_id} does not exist.')
    except Exception as e:
        logger.error(f"Error creating Profile {profile_id} in MikroTik: {e}", exc_info=True)
        raise


@shared_task
def update_profile_in_mikrotik(profile_id):
    """Update an existing profile in MikroTik."""
    try:
        profile = Profile.objects.get(id=profile_id)
        if profile.mikrotik_id:
            mikrotik_manager.update_profile(
                profile_id=profile.mikrotik_id,
                name_for_users=profile.name_for_users,
                price=str(profile.price),
                starts_when=profile.starts_when,
                validity=profile.validity,
                override_shared_users=profile.override_shared_users
            )
            logger.info(f'Updated profile {profile.name} in MikroTik.')
        else:
            logger.warning(f"Profile {profile.name} does not have a MikroTik ID.")
    except Profile.DoesNotExist:
        logger.error(f'Profile with ID {profile_id} does not exist.')
    except Exception as e:
        logger.error(f"Error updating Profile {profile_id} in MikroTik: {e}", exc_info=True)
        raise


@shared_task
def delete_profile_in_mikrotik(profile_id):
    """Delete a profile in MikroTik."""
    try:
        profile = Profile.objects.get(id=profile_id)
        if profile.mikrotik_id:
            mikrotik_manager.delete_profile(profile_id=profile.mikrotik_id)
            logger.info(f'Deleted profile {profile.name} in MikroTik.')
        else:
            logger.warning(f"Profile {profile.name} does not have a MikroTik ID.")
    except Profile.DoesNotExist:
        logger.error(f'Profile with ID {profile_id} does not exist.')
    except Exception as e:
        logger.error(f"Error deleting Profile {profile_id} in MikroTik: {e}", exc_info=True)
        raise


# --- UserProfile
@shared_task
def create_user_profile_in_mikrotik(user_profile_id):
    """Create a user profile in MikroTik."""
    try:
        user_profile = UserProfile.objects.get(id=user_profile_id)
        response = mikrotik_manager.create_user_profile(
            user=user_profile.user.username,
            profile=user_profile.profile.name,
            # state=user_profile.state,
            # end_time=user_profile.end_time
        )
        user_profile.mikrotik_id = response['.id']  # Save MikroTik ID
        user_profile.save()
        logger.info(f'Created UserProfile {user_profile_id} for user {user_profile.user.username} in MikroTik.')
    except UserProfile.DoesNotExist:
        logger.error(f'UserProfile with ID {user_profile_id} does not exist.')
    except Exception as e:
        logger.error(f"Error creating UserProfile {user_profile_id} in MikroTik: {e}", exc_info=True)
        raise


@shared_task
def update_user_profile_in_mikrotik(user_profile_id):
    """Update a user profile in MikroTik."""
    try:
        user_profile = UserProfile.objects.get(id=user_profile_id)
        if user_profile.mikrotik_id:
            mikrotik_manager.update_user_profile(
                user_profile_id=user_profile.mikrotik_id,
                state=user_profile.state,
                end_time=user_profile.end_time
            )
            logger.info(f'Updated UserProfile {user_profile_id} in MikroTik.')
        else:
            logger.warning(f"UserProfile {user_profile_id} does not have a MikroTik ID.")
    except UserProfile.DoesNotExist:
        logger.error(f'UserProfile with ID {user_profile_id} does not exist.')
    except Exception as e:
        logger.error(f"Error updating UserProfile {user_profile_id} in MikroTik: {e}", exc_info=True)
        raise


@shared_task
def delete_user_profile_in_mikrotik(user_profile_id):
    """Delete a user profile in MikroTik."""
    try:
        user_profile = UserProfile.objects.get(id=user_profile_id)
        if user_profile.mikrotik_id:
            mikrotik_manager.delete_user_profile(user_profile_id=user_profile.mikrotik_id)
            logger.info(f'Deleted UserProfile {user_profile_id} in MikroTik.')
        else:
            logger.warning(f"UserProfile {user_profile_id} does not have a MikroTik ID.")
    except UserProfile.DoesNotExist:
        logger.error(f'UserProfile with ID {user_profile_id} does not exist.')
    except Exception as e:
        logger.error(f"Error deleting UserProfile {user_profile_id} in MikroTik: {e}", exc_info=True)
        raise
