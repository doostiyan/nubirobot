import bleach
from django import forms

from ..accounts.models import User
from .models import Activity, Ticket
from .utils import escape


class TicketForm(forms.ModelForm):
    class Meta:
        model = Ticket
        fields = (
            'topic',
            'content',
        )

    def clean(self):
        super(TicketForm, self).clean()
        if 'content' in self.cleaned_data.keys():
            self.cleaned_data['content'] = escape(bleach.clean(self.cleaned_data['content']))
        return self.cleaned_data


class CommentActivityForm(forms.ModelForm):
    def __init__(self, user: User, *args, **kwargs):

        super().__init__(*args, **kwargs)
        self.user = user

    def clean(self):
        super(CommentActivityForm, self).clean()
        if 'ticket' in self.cleaned_data:
            ticket = self.cleaned_data['ticket']
            if self.user not in (ticket.related_user, ticket.created_by):
                self.add_error('ticket', 'ticket does not exists.')
            elif ticket.is_private:
                self.add_error('ticket', 'ticket does not exists.')
            elif ticket.state in {Ticket.STATE_CHOICES.spam, Ticket.STATE_CHOICES.closed}:
                self.add_error('ticket', 'comment on spam or closed tickets is impossible.')
        if 'content' in self.cleaned_data:
            self.cleaned_data['content'] = escape(bleach.clean(self.cleaned_data['content']))
        return self.cleaned_data

    class Meta:
        model = Activity
        fields = ('content', 'ticket', 'files',)
