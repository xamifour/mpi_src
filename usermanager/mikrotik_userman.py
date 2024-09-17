# mpi_src/
# │
# ├── usermanager/
# │   ├── mikrotik_userman.py

# mpi_src/usermanager/mikrotik_userman.py
import requests
from typing import Optional, List, Dict, Any
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MikroTikUserManager:
    def __init__(self, router_ip: str, router_username: str, router_password: str):
        self.router_ip = router_ip.rstrip('/')
        self.router_username = router_username
        self.router_password = router_password
        self.session = requests.Session()
        self.session.auth = (self.router_username, self.router_password)
        self.session.headers.update({'Content-Type': 'application/json'})

    def _request(self, method: str, endpoint: str, data: Optional[Dict[str, Any]] = None) -> Any:
        url = f"{self.router_ip}/{endpoint.lstrip('/')}"
        try:
            response = self.session.request(method=method.upper(), url=url, json=data, timeout=10)
            response.raise_for_status()
            if response.content:
                return response.json()
            return None
        except requests.exceptions.HTTPError as http_err:
            logger.error(f"HTTP error occurred: {http_err} - Response: {response.text}")
            raise RuntimeError(f"HTTP error occurred: {http_err} - {response.text}")
        except requests.exceptions.RequestException as req_err:
            logger.error(f"Request exception: {req_err}")
            raise RuntimeError(f"Request exception: {req_err}")

    # ------------------------------------------------ users
    def get_users(self) -> List[Dict[str, Any]]:
        return self._request('GET', 'rest/user-manager/user') or []

    def get_user(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a user by their .id (preferred) or name.
        """
        try:
            return self._request('GET', f'rest/user-manager/user/{user_id}')
        except Exception as e:
            logger.error(f"Error retrieving user '{user_id}': {e}")
            raise RuntimeError(f"Error retrieving user '{user_id}': {e}")

    def create_user(self, username: str, plain_password: str, group: str, shared_users: int = 1, disabled: bool = False, attributes: str = ""):
        data = {
            'name': username,
            # 'password': password,
            # 'otp-secret': str(otp_secret),
            'group': group,
            'shared-users': str(shared_users),
            'disabled': 'true' if disabled else 'false',
            'attributes': attributes,
            'password': plain_password
        }

        # API might require a specific format for boolean values or other fields
        data = {k: v for k, v in data.items() if v}  # Remove empty values

        try:
            return self._request('PUT', 'rest/user-manager/user', data=data)
        except Exception as e:
            logger.error(f"Error creating user '{username}': {e}")
            raise RuntimeError(f"Error creating user '{username}': {e}")

    def update_user(self, user_id: str, **kwargs: Optional[str]):
        """
        Update user by .id.
        """
        field_map = {
            # 'password': 'password',
            # 'otp_secret': 'otp-secret',
            'group': 'group',
            'shared_users': 'shared-users',
            'disabled': 'disabled',
            'attributes': 'attributes',
            'plain_password': 'password'
        }
        data = {field_map[k]: v for k, v in kwargs.items() if v is not None}

        if not data:
            raise ValueError("No data provided to update.")

        try:
            return self._request('PATCH', f"rest/user-manager/user/{user_id}", data=data)
        except Exception as e:
            logger.error(f"Error updating user '{user_id}': {e}")
            raise RuntimeError(f"Error updating user '{user_id}': {e}")

    def delete_user(self, user_id: str):
        return self._request('DELETE', f"rest/user-manager/user/{user_id}")

    # ------------------------------------------------ profiles
    def get_profiles(self) -> List[Dict[str, Any]]:
        return self._request('GET', 'rest/user-manager/profile') or []
    
    def get_profile(self, profile_id: str) -> Optional[Dict[str, Any]]:
        try:
            return self._request('GET', f'rest/user-manager/profile/{profile_id}')
        except Exception as e:
            logger.error(f"Error retrieving profile '{profile_id}': {e}")
            raise RuntimeError(f"Error retrieving profile '{profile_id}': {e}")

    def create_profile(self, name: str, name_for_users: str, price: str, starts_when: str, validity: str, override_shared_users: str = 'off'):
        data = {
            'name': name,
            'name-for-users': name_for_users,
            'price': price,
            'starts-when': starts_when,
            'validity': validity,
            'override-shared-users': override_shared_users
        }
        return self._request('PUT', 'rest/user-manager/profile', data=data)

    def update_profile(self, profile_id: str, **kwargs: Optional[str]):
        data = {k.replace('_', '-'): v for k, v in kwargs.items() if v}
        return self._request('PATCH', f'rest/user-manager/profile/{profile_id}', data=data)

    def delete_profile(self, profile_id: str):
        return self._request('DELETE', f'rest/user-manager/profile/{profile_id}')

    # ------------------------------------------------ user profiles
    def get_user_profiles(self) -> List[Dict[str, Any]]:
        return self._request('GET', 'rest/user-manager/user-profile') or []
    
    def get_user_profile(self, user_profile_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a user profile by its .id.
        """
        try:
            return self._request('GET', f'rest/user-manager/user-profile/{user_profile_id}')
        except Exception as e:
            logger.error(f"Error retrieving user profile '{user_profile_id}': {e}")
            raise RuntimeError(f"Error retrieving user profile '{user_profile_id}': {e}")
        
    def get_user_user_profiles(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Retrieve all user profiles associated with a specific user by filtering the user profiles 
        returned by get_user_profiles. The filtering is done based on the user's .id.
        """
        user_profiles = self.get_user_profiles()  # Fetch all user profiles
        return [profile for profile in user_profiles if profile.get('user') == user_id]  # Filter by user_id

    def create_user_profile(self, user: str, profile: str):
        data = {
            'user': user,
            'profile': profile,
        }
        return self._request('PUT', 'rest/user-manager/user-profile', data=data)

    def update_user_profile(self, user_profile_id: str, **kwargs: Optional[Any]):
        # Check if the user profile exists before updating
        existing_profile = self.get_user_profile(user_profile_id)
        if not existing_profile:
            raise ValueError(f"User profile with ID {user_profile_id} does not exist")
        
        # Debug: print the kwargs to see what fields are being passed
        print(f"Updating UserProfile {user_profile_id} with data: {kwargs}")
        
        # Replace underscores with dashes in field names, and filter out None values
        data = {k.replace('_', '-'): v for k, v in kwargs.items() if v is not None}

        # Debug: print the data being sent
        print(f"Data being sent in PUT request: {data}")
        
        return self._request('PUT', f'rest/user-manager/user-profile/{user_profile_id}', data=data)

    def delete_user_profile(self, user_profile_id: str):
        return self._request('DELETE', f'rest/user-manager/user-profile/{user_profile_id}')

    # ------------------------------------------------ payments
    def get_payments(self) -> List[Dict[str, Any]]:
        """
        Retrieve all payment records from MikroTik.
        """
        try:
            return self._request('GET', 'rest/user-manager/payment')
        except Exception as e:
            logger.error(f"Error retrieving payments: {e}")
            raise RuntimeError(f"Error retrieving payments: {e}")

    def get_payment(self, payment_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a single payment by its .id.
        """
        try:
            return self._request('GET', f'rest/user-manager/payment/{payment_id}')
        except Exception as e:
            logger.error(f"Error retrieving payment '{payment_id}': {e}")
            raise RuntimeError(f"Error retrieving payment '{payment_id}': {e}")

    def get_user_payments(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Retrieve all payments for a specific user by their ID.
        """
        try:
            all_payments = self.get_payments()  # Retrieve all payments
            user_payments = [payment for payment in all_payments if payment.get('user_profile') == user_id]
            return user_payments
        except Exception as e:
            logger.error(f"Error retrieving payments for user '{user_id}': {e}")
            raise RuntimeError(f"Error retrieving payments for user '{user_id}': {e}")

    def create_payment(self, payment_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new payment record on MikroTik.
        """
        try:
            return self._request('PUT', 'rest/user-manager/payment', json=payment_data)
        except Exception as e:
            logger.error(f"Error creating payment: {e}")
            raise RuntimeError(f"Error creating payment: {e}")

    def update_payment(self, payment_id: str, update_data: Dict[str, Any]) -> Dict[str, Any]:
        try:
            return self._request('PATCH', f'rest/user-manager/payment/{payment_id}', json=update_data)
        except Exception as e:
            logger.error(f"Error updating payment '{payment_id}': {e}")
            raise RuntimeError(f"Error updating payment '{payment_id}': {e}")

    def delete_payment(self, payment_id: str) -> None:
        try:
            self._request('DELETE', f'rest/user-manager/payment/{payment_id}')
        except Exception as e:
            logger.error(f"Error deleting payment '{payment_id}': {e}")
            raise RuntimeError(f"Error deleting payment '{payment_id}': {e}")

    # ------------------------------------------------ session
    def get_sessions(self) -> List[Dict[str, Any]]:
        return self._request('GET', 'rest/user-manager/session') or []

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a session by its .id.
        """
        try:
            return self._request('GET', f'rest/user-manager/session/{session_id}')
        except Exception as e:
            logger.error(f"Error retrieving session '{session_id}': {e}")
            raise RuntimeError(f"Error retrieving session '{session_id}': {e}")

    def get_user_sessions(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Retrieve sessions for a specific user by filtering the sessions returned by get_sessions.
        The filtering is done based on the user's .id.
        """
        sessions = self.get_sessions()  # Fetch all sessions
        return [session for session in sessions if session.get('user') == user_id]  # Filter by user_id
    


from django.conf import settings
def init_mikrotik_manager():
    return MikroTikUserManager(
        router_ip=settings.ROUTER_IP,
        router_username=settings.ROUTER_USERNAME,
        router_password=settings.ROUTER_PASSWORD
    )

