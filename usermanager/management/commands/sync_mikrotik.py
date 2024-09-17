# mpi_src/usermanager/management/commands/sync_mikrotik.py

import logging
from django.core.management.base import BaseCommand
from django.conf import settings
from django.db import transaction

from usermanager.mikrotik_userman import MikroTikUserManager
from usermanager.models import User, Profile, UserProfile, Session
from usermanager.mikrotik_userman import init_mikrotik_manager

logger = logging.getLogger(__name__)

# Initialize the MikroTik manager
mikrotik_manager = init_mikrotik_manager()

class Command(BaseCommand):
    help = 'Sync users, profiles, user profiles, and sessions from MikroTik to Django'

    def handle(self, *args, **kwargs):
        """Handles the command to sync MikroTik data."""
        try:
            self.sync_users(mikrotik_manager)
            self.sync_profiles(mikrotik_manager)
            self.sync_user_profiles(mikrotik_manager)
            self.sync_sessions(mikrotik_manager)
        except Exception as e:
            logger.error(f"Error syncing data: {e}")
            self.stdout.write(self.style.ERROR(f"Error syncing data: {e}"))
        else:
            logger.info("MikroTik sync completed successfully")
            self.stdout.write(self.style.SUCCESS("MikroTik sync completed successfully"))

    def sync_users(self, mikrotik_manager):
        """Synchronizes users from MikroTik to the Django database."""
        try:
            with transaction.atomic():
                mikrotik_users = mikrotik_manager.get_users()
                for mt_user in mikrotik_users:
                    user, created = User.objects.update_or_create(
                        username=mt_user['name'],
                        defaults={
                            'group': mt_user['group'],
                            'disabled': mt_user['disabled'] == 'true',
                            'otp_secret': mt_user.get('otp-secret', ''),
                            'shared_users': int(mt_user['shared-users']),
                            'plain_password': mt_user['password'],
                        }
                    )
                    if created:
                        logger.info(f'Created new user: {user.username}')
                        self.stdout.write(self.style.SUCCESS(f'Created new user: {user.username}'))
                    else:
                        logger.info(f'Updated user: {user.username}')
                        self.stdout.write(self.style.SUCCESS(f'Updated user: {user.username}'))
        except Exception as e:
            logger.error(f"Error syncing users: {e}", exc_info=True)
            self.stdout.write(self.style.ERROR(f"Error syncing users: {e}"))
            raise

    def sync_profiles(self, mikrotik_manager):
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
                        }
                    )
                    if created:
                        logger.info(f'Created new profile: {profile.name}')
                        self.stdout.write(self.style.SUCCESS(f'Created new profile: {profile.name}'))
                    else:
                        logger.info(f'Updated profile: {profile.name}')
                        self.stdout.write(self.style.SUCCESS(f'Updated profile: {profile.name}'))
        except Exception as e:
            logger.error(f"Error syncing profiles: {e}", exc_info=True)
            self.stdout.write(self.style.ERROR(f"Error syncing profiles: {e}"))
            raise

    def sync_user_profiles(self, mikrotik_manager):
        """Synchronizes user profiles from MikroTik to the Django database."""
        try:
            with transaction.atomic():
                mikrotik_user_profiles = mikrotik_manager.get_user_profiles()
                for mt_user_profile in mikrotik_user_profiles:
                    user = User.objects.filter(username=mt_user_profile['user']).first()
                    profile = Profile.objects.filter(name=mt_user_profile['profile']).first()

                    if not user or not profile:
                        logger.warning(f"Skipping user profile sync: user '{mt_user_profile['user']}' or profile '{mt_user_profile['profile']}' not found.")
                        self.stdout.write(self.style.WARNING(f"Skipping user profile sync: user '{mt_user_profile['user']}' or profile '{mt_user_profile['profile']}' not found."))
                        continue

                    user_profile, created = UserProfile.objects.get_or_create(
                        user=user,
                        profile=profile,
                        state=mt_user_profile.get('state'),
                        end_time=mt_user_profile.get('end-time', 'unlimited')
                    )

                    if created:
                        logger.info(f'Created new user profile for user: {user.username} with profile: {profile.name}')
                        self.stdout.write(self.style.SUCCESS(f'Created new user profile for user: {user.username} with profile: {profile.name}'))
                    else:
                        user_profile.state = mt_user_profile.get('state')
                        user_profile.end_time = mt_user_profile.get('end-time', 'unlimited')
                        user_profile.save()
                        logger.info(f'Updated user profile for user: {user.username} with profile: {profile.name}')
                        self.stdout.write(self.style.SUCCESS(f'Updated user profile for user: {user.username} with profile: {profile.name}'))
        except Exception as e:
            logger.error(f"Error syncing user profiles: {e}", exc_info=True)
            self.stdout.write(self.style.ERROR(f"Error syncing user profiles: {e}"))
            raise

    def sync_sessions(self, mikrotik_manager):
        """Synchronizes sessions from MikroTik to the Django database."""
        try:
            with transaction.atomic():
                mikrotik_sessions = mikrotik_manager.get_sessions()
                for mt_session in mikrotik_sessions:
                    user = User.objects.filter(username=mt_session['user']).first()
                    if not user:
                        logger.warning(f"User '{mt_session['user']}' not found. Skipping session '{mt_session['acct-session-id']}'")
                        self.stdout.write(self.style.WARNING(f"User '{mt_session['user']}' not found. Skipping session '{mt_session['acct-session-id']}'"))
                        continue

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
                        'user_address': mt_session.get('user-address')
                    }

                    session, created = Session.objects.update_or_create(
                        session_id=mt_session['acct-session-id'],
                        defaults=session_defaults
                    )

                    if created:
                        logger.info(f'Created new session: {session.session_id}')
                        self.stdout.write(self.style.SUCCESS(f'Created new session: {session.session_id}'))
                    else:
                        logger.info(f'Updated session: {session.session_id}')
                        self.stdout.write(self.style.SUCCESS(f'Updated session: {session.session_id}'))
        except Exception as e:
            logger.error(f"Error syncing sessions: {e}", exc_info=True)
            self.stdout.write(self.style.ERROR(f"Error syncing sessions: {e}"))
            raise

