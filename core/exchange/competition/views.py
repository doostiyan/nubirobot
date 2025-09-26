from decimal import Decimal

from django.shortcuts import get_object_or_404

from exchange.accounts.models import User
from exchange.base.api import api, public_post_api, get_user_by_token
from exchange.base.calendar import to_shamsi_date
from exchange.base.money import normalize
from exchange.base.parsers import parse_int
from exchange.wallet.models import Transaction
from .models import Competition


@api
def status(request):
    competition = request.g('competition')
    if competition:
        competition = get_object_or_404(Competition, pk=competition)
    else:
        competition = Competition.get_active_competition()

    if not competition:
        return {
            'error': 'There is not any active competition'
        }

    return {
        'status': 'ok',
        'isUserRegistered': competition.is_user_registered(request.user),
        'competition': competition,
    }


@api
def register(request):
    competition = request.g('competition')
    if competition:
        competition = get_object_or_404(Competition, pk=competition)
    else:
        competition = Competition.get_active_competition()

    if not competition:
        return {
            'error': 'There is not any active competition'
        }

    competition.register_user(request.user)

    return {
        'status': 'ok',
        'competition': competition,
    }


@api
def reset_funds(request):
    # Get competition
    competition = request.g('competition')
    if competition:
        competition = get_object_or_404(Competition, pk=competition)
    else:
        competition = Competition.get_active_competition()
    if not competition:
        return {
            'status': 'failed',
            'message': 'There is not any active competition',
        }

    # Get user registration in competition
    registration = competition.get_user_registration(request.user)
    if not registration:
        return {
            'status': 'failed',
            'error': 'User is not registred in any competition',
        }

    # Reset funds
    ok = registration.reset_funds()
    if not ok:
        return {
            'status': 'failed',
            'error': 'Cannot reset funds for this competition',
        }
    return {
        'status': 'ok',
    }


@public_post_api
def leaderboard(request):
    competition = request.g('competition')
    chat_id = request.g('chat_id')

    user = get_user_by_token(request)
    if not user.is_authenticated:
        user = User.objects.filter(telegram_conversation_id=chat_id).first() if chat_id else None

    if competition:
        competition = get_object_or_404(Competition, pk=competition)
    else:
        competition = Competition.get_active_competition()

    if not competition:
        return {
            'error': 'There is not any active competition'
        }

    leaderboard = competition.get_leaderboard()[:30]
    registered_user = competition.registrations.filter(is_active=True, user=user).first()
    if registered_user:
        user_score = competition.registrations.filter(is_active=True,
                                                      current_balance__gt=registered_user.current_balance).count() + 1

    return {
        'status': 'ok',
        'leaderboard': leaderboard,
        'user': {'registeration': registered_user, 'score': user_score} if registered_user else None
    }


@public_post_api
def results_details(request):
    competition = request.g('competition')
    user_rank = parse_int(request.g('rank'))

    if competition:
        competition = get_object_or_404(Competition, pk=competition)
    else:
        competition = Competition.get_active_competition()
    if not competition or not competition.is_finished:
        return {
            'status': 'failed',
            'error': 'Invalid competition'
        }

    if not user_rank or user_rank < 1 or user_rank > 10:
        return {
            'status': 'failed',
            'error': 'Invalid rank'
        }

    leaderboard = competition.get_leaderboard()
    try:
        user = leaderboard[user_rank - 1].user
    except IndexError:
        return {
            'status': 'failed',
            'error': 'Invalid rank'
        }
    user_nickname = user.nickname
    start, end = competition.get_date_range()
    transactions = Transaction.objects.filter(wallet__user=user, created_at__gte=start, created_at__lt=end)
    transactions = transactions.order_by('created_at').select_related('wallet')
    transactions = filter(lambda t: t.tp != Transaction.TYPE.manual or t.amount > 0, transactions)
    transactions = [{
        'timestamp': to_shamsi_date(tr.created_at),
        'currency': tr.wallet.get_currency_display(),
        'amount': normalize(tr.amount, exp=None),
        'description': tr.description,
    } for tr in transactions]

    return {
        'status': 'ok',
        'rank': user_rank,
        'user': user_nickname,
        'transactions': transactions,
    }
