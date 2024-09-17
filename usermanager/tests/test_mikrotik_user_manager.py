# mpi_src/usermanager/tests/test_mikrotik_user_manager.py

from datetime import datetime, timedelta
import unittest
from unittest.mock import patch, MagicMock
from usermanager.mikrotik_user_manager import MikroTikUserManager

class TestMikroTikUserManager(unittest.TestCase):

    @patch('usermanager.mikrotik_user_manager.routeros_api.RouterOsApiPool')
    def setUp(self, MockRouterOsApiPool):
        self.mock_api_pool = MockRouterOsApiPool.return_value
        self.mock_api = self.mock_api_pool.get_api.return_value
        self.manager = MikroTikUserManager('192.168.88.1', 'admin', 'password')

    def test_connect_success(self):
        self.manager.connect()
        self.mock_api_pool.assert_called_with('192.168.88.1', username='admin', password='password')
        self.assertIsNotNone(self.manager.api)

    def test_connect_failure(self):
        self.mock_api_pool.side_effect = Exception("Connection failed")
        with self.assertRaises(Exception):
            self.manager.connect()

    def test_disconnect(self):
        self.manager.connect()
        self.manager.disconnect()
        self.mock_api_pool.disconnect.assert_called_once()

    def test_create_user_success(self):
        self.manager.connect()
        self.manager.create_user('testuser', 'testpass', 'default')
        self.mock_api.get_resource.return_value.add.assert_called_with(name='testuser', password='testpass', profile='default')

    def test_create_user_failure(self):
        self.manager.connect()
        self.mock_api.get_resource.return_value.add.side_effect = Exception("Creation failed")
        with self.assertRaises(Exception):
            self.manager.create_user('testuser', 'testpass', 'default')

    def test_top_up_user_success(self):
        self.manager.connect()
        mock_user_resource = self.mock_api.get_resource.return_value
        mock_user_resource.get.return_value = [{'name': 'testuser', 'expiration-date': 'Jan/01/2023', '.id': '*1'}]

        self.manager.top_up_user('testuser', 30)
        
        new_expiration_date = self.manager.calculate_new_expiration_date('Jan/01/2023', 30)
        mock_user_resource.set.assert_called_with(id='*1', **{'expiration-date': new_expiration_date})

    def test_top_up_user_user_not_found(self):
        self.manager.connect()
        mock_user_resource = self.mock_api.get_resource.return_value
        mock_user_resource.get.return_value = []

        with self.assertRaises(ValueError):
            self.manager.top_up_user('nonexistentuser', 30)

    def test_top_up_user_failure(self):
        self.manager.connect()
        mock_user_resource = self.mock_api.get_resource.return_value
        mock_user_resource.get.return_value = [{'name': 'testuser', 'expiration-date': 'Jan/01/2023', '.id': '*1'}]
        mock_user_resource.set.side_effect = Exception("Top-up failed")

        with self.assertRaises(Exception):
            self.manager.top_up_user('testuser', 30)

    def test_calculate_new_expiration_date(self):
        current_expiration_date = 'Jan/01/2023'
        days_to_add = 30
        new_expiration_date = self.manager.calculate_new_expiration_date(current_expiration_date, days_to_add)
        self.assertEqual(new_expiration_date, 'Jan/31/2023')

    def test_calculate_new_expiration_date_no_current_date(self):
        current_expiration_date = None
        days_to_add = 30
        new_expiration_date = self.manager.calculate_new_expiration_date(current_expiration_date, days_to_add)
        self.assertEqual(new_expiration_date, (datetime.now() + timedelta(days=days_to_add)).strftime('%b/%d/%Y'))

if __name__ == '__main__':
    unittest.main()
