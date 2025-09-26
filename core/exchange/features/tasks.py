from celery import shared_task

from exchange.web_engage.events.features_events import FeatureEnabledWebEngageEvent


@shared_task(name='send_feature_web_engage')
def send_feature_web_engage(user_id: int, feature: int) -> None:
    """
    Send a WebEngage event for a feature being enabled for a user.

    Args:
        user_id: The ID of the user for whom the feature is enabled.
        feature: The feature identifier. Should correspond to one of the choices
                       defined in the 'FEATURES' field of the 'QueueItem' model.
    """
    from exchange.features.models import QueueItem, User

    # Exclude portfolio from reported features because it is automatically
    #  enabled for all users and is not a real feature.
    if feature == QueueItem.FEATURES.portfolio:
        return
    # Send WebEngage event
    user = User.objects.filter(id=user_id).first()
    if user and feature in QueueItem.FEATURES:
        FeatureEnabledWebEngageEvent(
            user=user,
            feature=QueueItem.FEATURES[feature],
        ).send()
