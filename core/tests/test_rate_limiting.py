# core/tests/test_rate_limiting.py

from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.urls import reverse
from core.models import Plan
from cv.models import CVQuestionnaire
from unittest.mock import patch, Mock
from core.throttling import get_rate_limit_status

User = get_user_model()


class RateLimitStatusEndpointTest(APITestCase):
    """Test the rate limit status endpoint."""
    
    def setUp(self):
        cache.clear()
        
        # Create plans
        self.free_plan = Plan.objects.create(name='Free')
        self.basic_plan = Plan.objects.create(name='Basic')
        
        # Create user
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
            plan=self.free_plan
        )
        
        self.client.force_authenticate(user=self.user)
    
    def tearDown(self):
        cache.clear()
    
    def test_rate_limit_status_endpoint_exists(self):
        """Test that the rate limit status endpoint is accessible."""
        url = reverse('rate_limit_status')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_rate_limit_status_returns_correct_structure(self):
        """Test that the response has the correct structure."""
        url = reverse('rate_limit_status')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        data = response.json()
        
        # Check user info
        self.assertIn('user', data)
        self.assertEqual(data['user']['username'], 'testuser')
        self.assertEqual(data['user']['plan'], 'Free')
        
        # Check rate limits
        self.assertIn('rate_limits', data)
        self.assertIn('ai_responses', data['rate_limits'])
        self.assertIn('questionnaires', data['rate_limits'])
        self.assertIn('api_calls', data['rate_limits'])
        
        # Check structure of each rate limit
        for scope in ['ai_responses', 'questionnaires', 'api_calls']:
            limit_data = data['rate_limits'][scope]
            self.assertIn('limit', limit_data)
            self.assertIn('used', limit_data)
            self.assertIn('remaining', limit_data)
            self.assertIn('reset_at', limit_data)
            self.assertIn('percentage_used', limit_data)
            self.assertIn('status', limit_data)
        
        # Check upgrade recommendation
        self.assertIn('upgrade_recommendation', data)
        self.assertIn('should_upgrade', data['upgrade_recommendation'])
    
    def test_free_plan_shows_correct_limits(self):
        """Test that Free plan shows correct rate limits."""
        url = reverse('rate_limit_status')
        response = self.client.get(url)
        
        data = response.json()
        
        # Free plan limits
        self.assertEqual(data['rate_limits']['ai_responses']['limit'], 3)
        self.assertEqual(data['rate_limits']['questionnaires']['limit'], 5)
        self.assertEqual(data['rate_limits']['api_calls']['limit'], 100)
    
    def test_basic_plan_shows_higher_limits(self):
        """Test that Basic plan shows higher limits."""
        self.user.plan = self.basic_plan
        self.user.save()
        
        url = reverse('rate_limit_status')
        response = self.client.get(url)
        
        data = response.json()
        
        # Basic plan limits (higher than Free)
        self.assertEqual(data['rate_limits']['ai_responses']['limit'], 20)
        self.assertEqual(data['rate_limits']['questionnaires']['limit'], 50)
        self.assertEqual(data['rate_limits']['api_calls']['limit'], 300)
    
    def test_status_label_changes_with_usage(self):
        """Test that status labels change based on usage percentage."""
        url = reverse('rate_limit_status')
        
        # Initially should be 'healthy' (0% used)
        response = self.client.get(url)
        data = response.json()
        self.assertEqual(data['rate_limits']['ai_responses']['status'], 'healthy')
        
        # Simulate some usage by manipulating cache
        from core.throttling import AIResponseThrottle
        throttle = AIResponseThrottle()
        
        class MockRequest:
            def __init__(self, user):
                self.user = user
                self.META = {}
        
        mock_request = MockRequest(self.user)
        throttle.request = mock_request
        
        # Simulate 2 out of 3 requests (66.67% - should be 'moderate')
        cache_key = throttle.get_cache_key(mock_request, None)
        now = throttle.timer()
        history = [now - 100, now - 50]  # Two requests in history
        cache.set(cache_key, history, 86400)
        
        response = self.client.get(url)
        data = response.json()
        self.assertEqual(data['rate_limits']['ai_responses']['used'], 2)
        self.assertEqual(data['rate_limits']['ai_responses']['remaining'], 1)
        self.assertEqual(data['rate_limits']['ai_responses']['status'], 'moderate')
    
    def test_upgrade_recommendation_when_high_usage(self):
        """Test that upgrade is recommended when usage is high."""
        url = reverse('rate_limit_status')
        
        # Simulate high usage (90%+)
        from core.throttling import AIResponseThrottle
        throttle = AIResponseThrottle()
        
        class MockRequest:
            def __init__(self, user):
                self.user = user
                self.META = {}
        
        mock_request = MockRequest(self.user)
        throttle.request = mock_request
        
        cache_key = throttle.get_cache_key(mock_request, None)
        now = throttle.timer()
        # 3 out of 3 requests (100%)
        history = [now - 200, now - 100, now - 50]
        cache.set(cache_key, history, 86400)
        
        response = self.client.get(url)
        data = response.json()
        
        # Should recommend upgrade
        self.assertTrue(data['upgrade_recommendation']['should_upgrade'])
        self.assertEqual(data['upgrade_recommendation']['recommended_plan'], 'Basic')
        self.assertIn('ai_responses', data['upgrade_recommendation'].get('high_usage_scopes', []))
    
    def test_no_upgrade_recommendation_for_premium(self):
        """Test that Premium users don't get upgrade recommendations."""
        premium_plan = Plan.objects.create(name='Premium')
        self.user.plan = premium_plan
        self.user.save()
        
        url = reverse('rate_limit_status')
        response = self.client.get(url)
        
        data = response.json()
        
        # Even with high usage, Premium shouldn't get upgrade suggestion
        self.assertFalse(data['upgrade_recommendation']['should_upgrade'])
    
    def test_requires_authentication(self):
        """Test that endpoint requires authentication."""
        self.client.force_authenticate(user=None)
        
        url = reverse('rate_limit_status')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class AIResponseThrottleTest(APITestCase):
    """Test AI response throttling."""
    
    def setUp(self):
        cache.clear()
        
        self.free_plan = Plan.objects.create(name='Free')
        self.basic_plan = Plan.objects.create(name='Basic')
        
        self.free_user = User.objects.create_user(
            username='freeuser',
            email='free@example.com',
            password='testpass123',
            plan=self.free_plan
        )
        
        self.questionnaire = CVQuestionnaire.objects.create(
            user=self.free_user,
            position='Software Engineer',
            industry='Tech',
            experience_level='3-5',
            company_size='medium',
            application_timeline='1-3 months'
        )
        
        self.client.force_authenticate(user=self.free_user)
    
    def tearDown(self):
        cache.clear()
    
    @patch('cv.views.OpenAI')
    @patch('cv.views.os.getenv')
    def test_free_user_throttled_after_3_requests(self, mock_getenv, mock_openai):
        """Test that free users are throttled after 3 AI responses."""
        mock_getenv.return_value = "test-api-key"
        mock_client = Mock()
        mock_openai.return_value = mock_client
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "Improved CV"
        mock_client.chat.completions.create.return_value = mock_response
        
        url = reverse('ai-response-list')
        data = {
            'questionnaire': self.questionnaire.id,
            'prompt': 'Please improve my CV'
        }
        
        # First 3 requests should succeed
        for i in range(3):
            response = self.client.post(url, data, format='json')
            self.assertEqual(
                response.status_code,
                status.HTTP_201_CREATED,
                f"Request {i+1} should succeed"
            )
        
        # 4th request should be throttled
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        
        # Check error response structure
        error_data = response.json()
        self.assertIn('error', error_data)
        self.assertEqual(error_data['error'], 'rate_limit_exceeded')
    
    @patch('cv.views.OpenAI')
    @patch('cv.views.os.getenv')
    def test_throttle_response_includes_upgrade_suggestion(self, mock_getenv, mock_openai):
        """Test that throttle response includes upgrade suggestion."""
        mock_getenv.return_value = "test-api-key"
        mock_client = Mock()
        mock_openai.return_value = mock_client
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "Improved CV"
        mock_client.chat.completions.create.return_value = mock_response
        
        url = reverse('ai-response-list')
        data = {
            'questionnaire': self.questionnaire.id,
            'prompt': 'Please improve my CV'
        }
        
        # Exhaust the limit
        for _ in range(3):
            self.client.post(url, data, format='json')
        
        # Get throttled response
        response = self.client.post(url, data, format='json')
        error_data = response.json()
        
        # Check upgrade suggestion
        self.assertIn('upgrade_suggestion', error_data)
        self.assertEqual(error_data['upgrade_suggestion']['recommended_plan'], 'Basic')
        self.assertIn('upgrade_url', error_data['upgrade_suggestion'])
    
    @patch('cv.views.OpenAI')
    @patch('cv.views.os.getenv')
    def test_successful_response_includes_rate_limit_info(self, mock_getenv, mock_openai):
        """Test that successful responses include rate limit info."""
        mock_getenv.return_value = "test-api-key"
        mock_client = Mock()
        mock_openai.return_value = mock_client
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "Improved CV"
        mock_client.chat.completions.create.return_value = mock_response
        
        url = reverse('ai-response-list')
        data = {
            'questionnaire': self.questionnaire.id,
            'prompt': 'Please improve my CV'
        }
        
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        response_data = response.json()
        
        # Should include rate limit info
        self.assertIn('rate_limit_info', response_data)
        self.assertIn('remaining', response_data['rate_limit_info'])
        self.assertIn('limit', response_data['rate_limit_info'])
        self.assertEqual(response_data['rate_limit_info']['remaining'], 2)  # 1 used, 2 remaining


class QuestionnaireThrottleTest(APITestCase):
    """Test questionnaire creation throttling."""
    
    def setUp(self):
        cache.clear()
        
        self.free_plan = Plan.objects.create(name='Free')
        
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
            plan=self.free_plan
        )
        
        self.client.force_authenticate(user=self.user)
    
    def tearDown(self):
        cache.clear()
    
    def test_free_user_throttled_after_5_questionnaires(self):
        """Test that free users are throttled after 5 questionnaires."""
        url = reverse('questionnaire-list')
        data = {
            'position': 'Software Engineer',
            'industry': 'Tech',
            'experience_level': '3-5',
            'company_size': 'medium',
            'application_timeline': '1-3 months'
        }
        
        # First 5 should succeed
        for i in range(5):
            response = self.client.post(url, data, format='json')
            self.assertEqual(
                response.status_code,
                status.HTTP_201_CREATED,
                f"Questionnaire {i+1} should succeed"
            )
        
        # 6th should be throttled
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)


class GetRateLimitStatusHelperTest(APITestCase):
    """Test the get_rate_limit_status helper function."""
    
    def setUp(self):
        cache.clear()
        
        self.free_plan = Plan.objects.create(name='Free')
        
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
            plan=self.free_plan
        )
    
    def tearDown(self):
        cache.clear()
    
    def test_returns_none_for_unauthenticated_user(self):
        """Test that function returns None for unauthenticated users."""
        result = get_rate_limit_status(None, 'ai_responses')
        self.assertIsNone(result)
    
    def test_returns_correct_structure(self):
        """Test that function returns correct data structure."""
        result = get_rate_limit_status(self.user, 'ai_responses')
        
        self.assertIsNotNone(result)
        self.assertIn('scope', result)
        self.assertIn('limit', result)
        self.assertIn('used', result)
        self.assertIn('remaining', result)
        self.assertIn('reset_at', result)
        self.assertIn('plan', result)
    
    def test_shows_correct_plan_limits(self):
        """Test that function shows correct limits for user's plan."""
        result = get_rate_limit_status(self.user, 'ai_responses')
        
        self.assertEqual(result['limit'], 3)  # Free plan limit
        self.assertEqual(result['plan'], 'Free')
    
    def test_tracks_usage_correctly(self):
        """Test that function tracks usage correctly."""
        # Initially, no usage
        result = get_rate_limit_status(self.user, 'ai_responses')
        self.assertEqual(result['used'], 0)
        self.assertEqual(result['remaining'], 3)
        
        # Simulate usage
        from core.throttling import AIResponseThrottle
        throttle = AIResponseThrottle()
        
        class MockRequest:
            def __init__(self, user):
                self.user = user
                self.META = {}
        
        mock_request = MockRequest(self.user)
        throttle.request = mock_request
        
        cache_key = throttle.get_cache_key(mock_request, None)
        now = throttle.timer()
        history = [now - 100]  # 1 request
        cache.set(cache_key, history, 86400)
        
        # Check updated usage
        result = get_rate_limit_status(self.user, 'ai_responses')
        self.assertEqual(result['used'], 1)
        self.assertEqual(result['remaining'], 2)


class PlanBasedThrottleTest(APITestCase):
    """Test plan-based throttling across different plan tiers."""
    
    def setUp(self):
        cache.clear()
        
        # Create all plans
        self.free_plan = Plan.objects.create(name='Free')
        self.basic_plan = Plan.objects.create(name='Basic')
        self.pro_plan = Plan.objects.create(name='Pro')
        self.premium_plan = Plan.objects.create(name='Premium')
    
    def tearDown(self):
        cache.clear()
    
    @patch('cv.views.OpenAI')
    @patch('cv.views.os.getenv')
    def test_different_plans_have_different_limits(self, mock_getenv, mock_openai):
        """Test that different plans have appropriately different limits."""
        mock_getenv.return_value = "test-api-key"
        mock_client = Mock()
        mock_openai.return_value = mock_client
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "Improved CV"
        mock_client.chat.completions.create.return_value = mock_response
        
        test_cases = [
            ('Free', 3),
            ('Basic', 20),
            ('Pro', 100),
            ('Premium', 1000),
        ]
        
        for plan_name, expected_limit in test_cases:
            cache.clear()
            
            # Create user with specific plan
            plan = Plan.objects.get(name=plan_name)
            user = User.objects.create_user(
                username=f'{plan_name.lower()}user',
                email=f'{plan_name.lower()}@example.com',
                password='testpass123',
                plan=plan
            )
            
            # Check rate limit
            result = get_rate_limit_status(user, 'ai_responses')
            self.assertEqual(
                result['limit'],
                expected_limit,
                f"{plan_name} plan should have limit of {expected_limit}"
            )
            
            # Cleanup
            user.delete()


class CacheKeyTest(APITestCase):
    """Test that cache keys are properly generated and unique."""
    
    def setUp(self):
        cache.clear()
        
        self.plan = Plan.objects.create(name='Free')
        
        self.user1 = User.objects.create_user(
            username='user1',
            email='user1@example.com',
            password='testpass123',
            plan=self.plan
        )
        
        self.user2 = User.objects.create_user(
            username='user2',
            email='user2@example.com',
            password='testpass123',
            plan=self.plan
        )
    
    def tearDown(self):
        cache.clear()
    
    def test_different_users_have_different_cache_keys(self):
        """Test that different users get different cache keys."""
        from core.throttling import AIResponseThrottle
        
        throttle1 = AIResponseThrottle()
        throttle2 = AIResponseThrottle()
        
        class MockRequest:
            def __init__(self, user):
                self.user = user
                self.META = {}
        
        request1 = MockRequest(self.user1)
        request2 = MockRequest(self.user2)
        
        key1 = throttle1.get_cache_key(request1, None)
        key2 = throttle2.get_cache_key(request2, None)
        
        self.assertNotEqual(key1, key2, "Different users should have different cache keys")
    
    def test_same_user_different_scopes_have_different_keys(self):
        """Test that same user with different scopes gets different cache keys."""
        from core.throttling import AIResponseThrottle, QuestionnaireThrottle
        
        ai_throttle = AIResponseThrottle()
        quest_throttle = QuestionnaireThrottle()
        
        class MockRequest:
            def __init__(self, user):
                self.user = user
                self.META = {}
        
        request = MockRequest(self.user1)
        
        ai_key = ai_throttle.get_cache_key(request, None)
        quest_key = quest_throttle.get_cache_key(request, None)
        
        self.assertNotEqual(ai_key, quest_key, "Different scopes should have different cache keys")