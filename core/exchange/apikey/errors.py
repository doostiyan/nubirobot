import typing

import pydantic


def convert_pydantic_validation_error(
    e: pydantic.ValidationError,
) -> str:
    messages: typing.List[str] = []
    for error in e.errors():
        messages.append(f'{error.get("loc", ("-"))[0]}: {error.get("msg", "")}')
    return ','.join(messages)
