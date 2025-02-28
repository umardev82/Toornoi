from google.auth.transport.requests import Request
from google.oauth2.id_token import verify_oauth2_token


class GoogleAuth:
    @staticmethod
    def verify_id_token(id_token):
        try:
            payload = verify_oauth2_token(id_token, Request(),
                                          audience='407408718192.apps.googleusercontent.com')
            return payload
        except Exception as e:
            raise e
