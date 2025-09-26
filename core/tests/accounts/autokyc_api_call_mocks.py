NEW_ALPHA_LIVENESS_APICALL_RESPONSE_MOCK = {
    'success': {
        'verification_result': {
            'errorCode': '',
            'errorMessage': '',
            'data': {
                'result': True,
                'details': {'distance': 0.95465468484},
                'duration': 0.95465654654,
                'similarity': 100,
            },
        },
        'liveness_result': {
            'errorCode': '',
            'errorMessage': '',
            'data': {
                'FaceAnchor': '3 of 5 anchor completed',
                'Duration': 0.225465486,
                'Score': '0.001546848',
                'Guide': 'The score lower than threshold is live and higher that threshold is spoof',
                'State': 'true',
            },
        },
    },
    'invalid_data': {
        'errorCode': 103,
        'errorMessage': 'اطلاعات وارد شده نامعتبر است',
        'data': {'live_face': ['The live face must not be greater than 256 kilobytes.']},
    },
    'status_200_but_error': {
        'verification_result': {'errorCode': '104', 'errorMessage': 'تصویر واضح نیست', 'data': ''},
        'liveness_result': {
            'errorCode': '',
            'errorMessage': '',
            'data': {
                'FaceAnchor': '3 of 5 anchor completed',
                'Duration': 0.225465486,
                'Score': '0.001546848',
                'Guide': 'The score lower than threshold is live and higher that threshold is spoof',
                'State': 'true',
            },
        },
    },
    'status_200_but_liveness_error': {
        'verification_result': {
            'errorCode': '',
            'errorMessage': '',
            'data': {
                'result': True,
                'details': {'distance': 0.95465468484},
                'duration': 0.95465654654,
                'similarity': 100,
            },
        },
        'liveness_result': {
            'errorCode': '105',
            'errorMessage': 'چهره در فیلم دریافتی یافت نشد',
            'data': '',
        },
    },
    'not_verification': {
        'verification_result': {
            'errorCode': '',
            'errorMessage': '',
            'data': {
                'result': False,
                'details': {'distance': 0.95465468484},
                'duration': 0.95465654654,
                'similarity': 1,
            },
        },
        'liveness_result': {
            'errorCode': '',
            'errorMessage': '',
            'data': {
                'FaceAnchor': '3 of 5 anchor completed',
                'Duration': 0.225465486,
                'Score': '0.001546848',
                'Guide': 'The score lower than threshold is live and higher that threshold is spoof',
                'State': 'true',
            },
        },
    },
    'not_liveness': {
        'verification_result': {
            'errorCode': '',
            'errorMessage': '',
            'data': {
                'result': True,
                'details': {'distance': 0.95465468484},
                'duration': 0.95465654654,
                'similarity': 100,
            },
        },
        'liveness_result': {
            'errorCode': '',
            'errorMessage': '',
            'data': {
                'FaceAnchor': '3 of 5 anchor completed',
                'Duration': 0.225465486,
                'Score': '0.001546848',
                'Guide': 'The score lower than threshold is live and higher that threshold is spoof',
                'State': 'false',
            },
        },
    },
    'status_400': {'errorCode': 102, 'errorMessage': 'خطای تستی', 'data': ''},
    'no_verification_field': {
        'liveness_result': {
            'errorCode': '',
            'errorMessage': '',
            'data': {'State': False},
        }
    },
    'no_liveness_field': {
        'verification_result': {
            'errorCode': '',
            'errorMessage': '',
            'data': {
                'result': False,
                'details': {'distance': 0.95465468484},
                'duration': 0.95465654654,
                'similarity': 1,
            },
        }
    },
}
AUTOKYC_CLIENT_EXPECTED_RESPONSES = {
    'success': {
        'result': True,
        'message': 'ok',
        'confidence': 100,
        'apiresponse': {
            'liveness': {
                'verification_result': {
                    'errorCode': '',
                    'errorMessage': '',
                    'data': {
                        'result': True,
                        'details': {'distance': 0.95465468484},
                        'duration': 0.95465654654,
                        'similarity': 100,
                    },
                },
                'liveness_result': {
                    'errorCode': '',
                    'errorMessage': '',
                    'data': {
                        'FaceAnchor': '3 of 5 anchor completed',
                        'Duration': 0.225465486,
                        'Score': '0.001546848',
                        'Guide': 'The score lower than threshold is live and higher that threshold is spoof',
                        'State': 'true',
                    },
                },
            }
        },
    },
    'invalid_data': {
        'result': False,
        'message': 'اطلاعات وارد شده نامعتبر است.',
        'confidence': 100,
        'apiresponse': {
            'error': {
                'message': 'اطلاعات وارد شده نامعتبر است: live_face: The live face must not be greater than 256 kilobytes.,',
            },
        },
    },
    'status_200_but_error': {
        'result': False,
        'message': 'خطایی رخ داده است',
        'confidence': 50,
        'apiresponse': {
            'liveness': {
                'error': 'تصویر واضح نیست',
            }
        },
    },
    'status_200_but_liveness_error': {
        'result': False,
        'message': 'خطایی رخ داده است',
        'confidence': 50,
        'apiresponse': {
            'liveness': {
                'error': 'چهره در فیلم دریافتی یافت نشد',
            }
        },
    },
    'not_verification': {
        'result': False,
        'message': 'هویت کاربر مورد تائید نیست',
        'confidence': 50,
        'apiresponse': {
            'liveness': {
                'verification_result': {
                    'errorCode': '',
                    'errorMessage': '',
                    'data': {
                        'result': False,
                        'details': {'distance': 0.95465468484},
                        'duration': 0.95465654654,
                        'similarity': 1,
                    },
                },
                'liveness_result': {
                    'errorCode': '',
                    'errorMessage': '',
                    'data': {
                        'FaceAnchor': '3 of 5 anchor completed',
                        'Duration': 0.225465486,
                        'Score': '0.001546848',
                        'Guide': 'The score lower than threshold is live and higher that threshold is spoof',
                        'State': 'true',
                    },
                },
            }
        },
    },
    'not_liveness': {
        'result': False,
        'message': 'وضعیت حیات کاربر مورد تائید نیست',
        'confidence': 50,
        'apiresponse': {
            'liveness': {
                'verification_result': {
                    'errorCode': '',
                    'errorMessage': '',
                    'data': {
                        'result': True,
                        'details': {'distance': 0.95465468484},
                        'duration': 0.95465654654,
                        'similarity': 100,
                    },
                },
                'liveness_result': {
                    'errorCode': '',
                    'errorMessage': '',
                    'data': {
                        'FaceAnchor': '3 of 5 anchor completed',
                        'Duration': 0.225465486,
                        'Score': '0.001546848',
                        'Guide': 'The score lower than threshold is live and higher that threshold is spoof',
                        'State': 'false',
                    },
                },
            }
        },
    },
    'status_400': {
        'result': False,
        'message': 'خطایی رخ داده است',
        'confidence': 50,
        'apiresponse': {'liveness': {'error': 'خطای تستی'}},
    },
    'no_verification_field': {
        'result': False,
        'message': 'خطایی رخ داده است',
        'confidence': 50,
        'apiresponse': {
            'liveness': {
                'error': 'پاسخ مناسبی از سرور دریافت نشد - '
                "{'liveness_result': {'errorCode': '', "
                "'errorMessage': '', 'data': {'State': "
                'False}}}'
            }
        },
    },
    'no_liveness_field': {
        'result': False,
        'message': 'خطایی رخ داده است',
        'confidence': 50,
        'apiresponse': {
            'liveness': {
                'error': 'پاسخ مناسبی از سرور دریافت نشد - '
                "{'verification_result': {'errorCode': "
                "'', 'errorMessage': '', 'data': "
                "{'result': False, 'details': "
                "{'distance': 0.95465468484}, "
                "'duration': 0.95465654654, "
                "'similarity': 1}}}"
            }
        },
    },
}
