import os
from rest_framework import exceptions
from rest_framework.authentication import TokenAuthentication, BaseAuthentication, get_authorization_header
from types import SimpleNamespace
from .models import PlayerToken

class PlayerTokenAuthentication(TokenAuthentication):
    model = PlayerToken

    def authenticate_credentials(self, key):
        model = self.get_model()
        try:
            token = model.objects.select_related('player').get(key=key)
        except model.DoesNotExist:
            raise exceptions.AuthenticationFailed('Invalid token.')
        return (token.player, token) 


class SystemTokenAuthentication(BaseAuthentication):
    """Authenticates requests made by the bot using a single system token.

    Expects header: Authorization: Token <BOT_SYSTEM_TOKEN>
    """

    def authenticate(self, request):
        auth = get_authorization_header(request).split()
        if not auth or auth[0].lower() != b'token' or len(auth) != 2:
            raise exceptions.AuthenticationFailed('No system token provided')

        provided = auth[1].decode('utf-8')
        expected = os.getenv('BOT_SYSTEM_TOKEN') or os.getenv('BOT_TOKEN')
        if not expected or provided != expected:
            raise exceptions.AuthenticationFailed('Invalid system token')

        # Minimal user-like object with is_authenticated = True
        system_user = SimpleNamespace(is_authenticated=True, username='system')
        return (system_user, None)