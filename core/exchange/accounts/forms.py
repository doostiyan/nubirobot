from django import forms


class UploadFileForm(forms.Form):
    file = forms.FileField()
    tp = forms.IntegerField(required=False)
