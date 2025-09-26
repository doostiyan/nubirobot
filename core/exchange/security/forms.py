from django import forms


class EmergencyCancelWithdrawForm(forms.Form):
    code = forms.CharField(required=True, max_length=10)
