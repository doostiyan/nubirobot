CALCULATOR_JSON_SCHEMA = {
    'type': 'array',
    'minItems': 1,
    'maxItems': 1,
    'items': {
        'type': 'object',
        'properties': {
            'pledgeableCategoryName': {'type': 'string'},
            'loanPrincipalSupplierId': {'type': 'string'},
            'durations': {
                'minItems': 1,
                'type': 'array',
                'items': {
                    'type': 'object',
                    'properties': {
                        'installments': {
                            'type': 'array',
                            'items': {
                                'type': 'object',
                                'properties': {
                                    'dueDate': {'type': 'string'},
                                    'type': {'type': 'string'},
                                    'emiRials': {'type': 'number'},
                                },
                            },
                            'minItems': 1,
                        },
                        'loanPrincipalSupplyPlanId': {'type': 'string', 'format': 'uuid'},
                        'collaboratorLoanPlanId': {'type': 'string', 'format': 'uuid'},
                        'termMonth': {'type': 'number'},
                        'operationFee': {
                            'type': 'object',
                            'properties': {
                                'totalFeeRials': {'type': 'number'},
                                'totalFeePercent': {'type': 'number'},
                            },
                            'required': ['totalFeeRials', 'totalFeePercent'],
                        },
                        'installmentRials': {'type': 'number'},
                        'paymentRials': {'type': 'number'},
                    },
                    'required': [
                        'installments',
                        'loanPrincipalSupplyPlanId',
                        'collaboratorLoanPlanId',
                        'termMonth',
                        'operationFee',
                        'paymentRials',
                    ],
                },
            },
            'principalRials': {'type': 'number'},
            'interestRateAPR': {'type': 'number'},
        },
        'required': ['durations', 'principalRials', 'interestRateAPR'],
    },
}
