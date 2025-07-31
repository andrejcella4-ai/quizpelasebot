from rest_framework import exceptions
from rest_framework.authentication import TokenAuthentication
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