from allauth.account.models import EmailAddress
from allauth.socialaccount.models import SocialAccount, SocialApp, SocialToken
from django.contrib import admin
from django.contrib.auth.models import Group
from django.contrib.sites.models import Site
from django_cron.models import CronJobLog
from django_otp.plugins.otp_static.models import StaticDevice
from django_otp.plugins.otp_totp.models import TOTPDevice
from oauth2_provider.admin import (
    access_token_model,
    application_model,
    grant_model,
    id_token_model,
    refresh_token_model,
)
from post_office.models import Attachment, Email, EmailTemplate, Log
from rest_framework.authtoken.models import TokenProxy

admin.site.unregister(Group)
admin.site.unregister(Site)
admin.site.unregister(Log)
admin.site.unregister(Email)
admin.site.unregister(EmailTemplate)
admin.site.unregister(Attachment)
admin.site.unregister(EmailAddress)
admin.site.unregister(CronJobLog)
admin.site.unregister(StaticDevice)
admin.site.unregister(TOTPDevice)
admin.site.unregister(SocialApp)
admin.site.unregister(SocialToken)
admin.site.unregister(SocialAccount)
admin.site.unregister(TokenProxy)
admin.site.unregister(application_model)
admin.site.unregister(grant_model)
admin.site.unregister(access_token_model)
admin.site.unregister(refresh_token_model)
admin.site.unregister(id_token_model)
