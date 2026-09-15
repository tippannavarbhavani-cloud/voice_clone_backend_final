from django.contrib.auth.models import User
from rest_framework.test import APITestCase
from rest_framework import status


class RegisterTests(APITestCase):
    def test_can_register_a_new_user(self):
        """A new user should be able to sign up and get back JWT tokens."""
        response = self.client.post("/api/auth/register/", {
            "username": "testuser",
            "email": "test@example.com",
            "password": "TestPass123!",
            "password2": "TestPass123!",
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)
        self.assertTrue(User.objects.filter(username="testuser").exists())

    def test_passwords_must_match(self):
        """If password and password2 don't match, it should fail."""
        response = self.client.post("/api/auth/register/", {
            "username": "testuser2",
            "email": "test2@example.com",
            "password": "TestPass123!",
            "password2": "DifferentPass123!",
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class LoginTests(APITestCase):
    def setUp(self):
        # Create a user directly, so login tests don't depend on register working.
        User.objects.create_user(username="loginuser", password="TestPass123!")

    def test_can_login_with_correct_password(self):
        response = self.client.post("/api/auth/login/", {
            "username": "loginuser",
            "password": "TestPass123!",
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)

    def test_login_fails_with_wrong_password(self):
        response = self.client.post("/api/auth/login/", {
            "username": "loginuser",
            "password": "WrongPassword!",
        })
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
