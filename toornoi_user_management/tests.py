from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase


class GoogleAuthTestCase(APITestCase):

    def setUp(self):
        self.urls = reverse('googleAuthentication')
        self.valid_payload = {'id_token': ""}
        self.invalid_payload = {'id_token': ""}
        self.expired_payload = {'id_token': ""}
        self.missing_payload = {'id_token': ""}

    def test_post_valid_token(self):
        response = self.client.post(self.urls, self.valid_payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)

    def test_post_invalid_token(self):
        response = self.client.post(self.urls, self.invalid_payload, format='json')
        print(response.data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Could not verify token signature', response.data['error'])

    def test_post_expired_token(self):
        response = self.client.post(self.urls, self.expired_payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Token expired', response.data['error'])

    def test_post_missing_id_token(self):
        response = self.client.post(self.urls, self.missing_payload, format='json')
        print(response.data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('This field may not be blank', response.data['id_token'][0])
