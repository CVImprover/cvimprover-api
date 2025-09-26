from django.test import TestCase
from rest_framework.test import APITestCase
from rest_framework import status
from unittest.mock import patch, MagicMock
from django.conf import settings
import os

from core.views import HealthCheckView


class HealthCheckViewTest(APITestCase):
    def setUp(self):
        self.url = '/core/health/'
        # Ensure no OpenAI key for some tests
        if 'OPENAI_API_KEY' in os.environ:
            del os.environ['OPENAI_API_KEY']

    @patch('core.views.connection.cursor')
    @patch('core.views.Redis.from_url')
    @patch('core.views.OpenAI')
    def test_health_check_all_healthy(self, mock_openai, mock_redis, mock_cursor):
        # Mock DB success
        mock_cursor_instance = MagicMock()
        mock_cursor.return_value.__enter__.return_value = mock_cursor_instance
        mock_cursor_instance.execute.return_value = None

        # Mock Redis success
        mock_redis_instance = MagicMock()
        mock_redis_instance.ping.return_value = True
        mock_redis.return_value = mock_redis_instance

        # Mock OpenAI success (key set)
        os.environ['OPENAI_API_KEY'] = 'test-key'
        mock_client = MagicMock()
        mock_client.models.list.return_value = MagicMock()
        mock_openai.return_value = mock_client

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data['overall'], 'healthy')
        self.assertEqual(data['services']['db'], 'healthy')
        self.assertEqual(data['services']['redis'], 'healthy')
        self.assertEqual(data['services']['openai'], 'healthy')

    @patch('core.views.connection.cursor')
    @patch('core.views.Redis.from_url')
    def test_health_check_openai_skipped(self, mock_redis, mock_cursor):
        # Mock DB and Redis success
        mock_cursor_instance = MagicMock()
        mock_cursor.return_value.__enter__.return_value = mock_cursor_instance
        mock_cursor_instance.execute.return_value = None

        mock_redis_instance = MagicMock()
        mock_redis_instance.ping.return_value = True
        mock_redis.return_value = mock_redis_instance

        # No OpenAI key
        if 'OPENAI_API_KEY' in os.environ:
            del os.environ['OPENAI_API_KEY']

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data['overall'], 'healthy')
        self.assertEqual(data['services']['db'], 'healthy')
        self.assertEqual(data['services']['redis'], 'healthy')
        self.assertEqual(data['services']['openai'], 'skipped')

    @patch('core.views.connection.cursor')
    @patch('core.views.Redis.from_url')
    @patch('core.views.OpenAI')
    def test_health_check_openai_unhealthy(self, mock_openai, mock_redis, mock_cursor):
        # Mock DB and Redis success
        mock_cursor_instance = MagicMock()
        mock_cursor.return_value.__enter__.return_value = mock_cursor_instance
        mock_cursor_instance.execute.return_value = None

        mock_redis_instance = MagicMock()
        mock_redis_instance.ping.return_value = True
        mock_redis.return_value = mock_redis_instance

        # Mock OpenAI failure
        os.environ['OPENAI_API_KEY'] = 'test-key'
        mock_openai.side_effect = Exception('API error')

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data['overall'], 'healthy')
        self.assertEqual(data['services']['db'], 'healthy')
        self.assertEqual(data['services']['redis'], 'healthy')
        self.assertEqual(data['services']['openai'], 'unhealthy')

    @patch('core.views.connection.cursor')
    @patch('core.views.Redis.from_url')
    def test_health_check_db_unhealthy(self, mock_redis, mock_cursor):
        # Mock DB failure
        mock_cursor.side_effect = Exception('DB error')

        # Mock Redis success
        mock_redis_instance = MagicMock()
        mock_redis_instance.ping.return_value = True
        mock_redis.return_value = mock_redis_instance

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        data = response.json()
        self.assertEqual(data['overall'], 'unhealthy')
        self.assertEqual(data['services']['db'], 'unhealthy')

    @patch('core.views.connection.cursor')
    @patch('core.views.Redis.from_url')
    def test_health_check_redis_unhealthy(self, mock_redis, mock_cursor):
        # Mock DB success
        mock_cursor_instance = MagicMock()
        mock_cursor.return_value.__enter__.return_value = mock_cursor_instance
        mock_cursor_instance.execute.return_value = None

        # Mock Redis failure
        mock_redis.side_effect = Exception('Redis error')

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        data = response.json()
        self.assertEqual(data['overall'], 'unhealthy')
        self.assertEqual(data['services']['redis'], 'unhealthy')
