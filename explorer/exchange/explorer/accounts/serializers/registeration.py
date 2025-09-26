from rest_framework import serializers
from django.core import validators
from django.utils.translation import gettext

from ..models import User


password_validator = [
    validators.MinLengthValidator(8, gettext("Password must be at least 8 characters long.")),
    validators.RegexValidator(
        regex=r'[A-Z]',
        message=gettext("Password must contain at least one uppercase letter."),
    ),
    validators.RegexValidator(
        regex=r'[a-z]',
        message=gettext("Password must contain at least one lowercase letter."),
    ),
    validators.RegexValidator(
        regex=r'[0-9]',
        message=gettext("Password must contain at least one digit."),
    ),
    validators.RegexValidator(
        regex=r'[!@#$%^&*(),.?":{}|<>]',
        message=gettext("Password must contain at least one special character."),
    ),
]


class RegistrationSerializer(serializers.ModelSerializer):
    password2 = serializers.CharField(style={"input_type": "password"}, write_only=True)

    class Meta:
        model = User
        fields = ['email', 'username', 'password', 'password2']
        extra_kwargs = {
            'password': {'write_only': True, 'validators': password_validator}
        }

    def save(self):
        password = self.validated_data['password']
        password2 = self.validated_data['password2']
        if password != password2:
            raise serializers.ValidationError({'password': 'Passwords must match.'})
        return User.objects.create_user(username=self.validated_data['username'],
                                        email=self.validated_data['email'],
                                        password=self.validated_data['password'])
