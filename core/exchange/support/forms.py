from django import forms


class CallReasonForm(forms.Form):
    unique_id = forms.CharField(max_length=155, required=True)
    mobile = forms.CharField(max_length=20, required=False)
    caller_id = forms.CharField(max_length=20, required=False)
    national_code = forms.CharField(max_length=15, required=False)

    def clean(self):
        super(CallReasonForm, self).clean()
        if 'national_code' in self.cleaned_data.keys() and 'mobile' in self.cleaned_data.keys():
            mobile = self.cleaned_data['mobile']
            national_code = self.cleaned_data['national_code']
            if not any([mobile, national_code]):
                self.add_error('mobile', 'Both mobile and national_code should not be empty')
        return self.cleaned_data
