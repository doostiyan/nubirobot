from django.db import models


class StakingReward(models.Model):
    wallet_address = models.CharField(max_length=42, db_index=True)
    network = models.CharField(max_length=10)
    reward_date = models.DateField(db_index=True)
    staked_amount = models.CharField(max_length=100)
    reward_amount = models.CharField(max_length=100)
    reward_rate = models.CharField(max_length=50)
    validators = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('wallet_address', 'network', 'reward_date')
