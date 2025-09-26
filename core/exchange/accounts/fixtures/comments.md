# system.json:
- Define system users by pks below 1000 in a descending order.
- primary keys 993, 995 should not be used for users As they are taken for staking system users. These users can be found in `load_once.json`.
- Primary keys 400 to 700 is reserved for pool managers, which are mapped to 400 + currency for each.