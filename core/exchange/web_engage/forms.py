from django import forms


class ESPDeliveryStatusForm(forms.Form):
    messageId = forms.CharField(max_length=500)
    event = forms.CharField(max_length=20)
    timestamp = forms.DateTimeField()
    email = forms.EmailField()
    hashedEmail = forms.CharField(max_length=100)
    statusCode = forms.IntegerField()
    message = forms.CharField(max_length=100)
    version = forms.CharField(max_length=10)
