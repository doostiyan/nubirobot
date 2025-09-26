from dataclasses import dataclass, fields


@dataclass
class DTO:
    @classmethod
    def get_fields(cls):
        return fields(cls)

    def get_data(self):
        data = {}
        for field in self.get_fields():
            value = getattr(self, field.name)
            if isinstance(value, DTO):
                value = value.get_data()
            elif isinstance(value, list):
                for i in range(len(value)):
                    if isinstance(value[i], DTO):
                        value[i] = value[i].get_data()
            data[field.name] = value
        return data


class BaseDTOCreator:
    DTO_CLASS = None

    @classmethod
    def normalize_data(cls, data) -> dict:
        if isinstance(data, dict):
            return data
        else:
            return data.__dict__

    @classmethod
    def get_dto(cls, data=None, serialize=True, **kwargs):
        if data is None:
            data = {}
        normalized_data = cls.normalize_data(data)
        normalized_data.update(kwargs)
        _fields = cls.DTO_CLASS.get_fields()
        matched_data = {field.name: normalized_data.get(field.name) for field in _fields}
        if serialize:
            return cls.DTO_CLASS(**matched_data)
        return matched_data

    @classmethod
    def get_dtos(cls, data: list, serialize=True, **kwargs):
        return [cls.get_dto(dto_data, serialize=serialize, **kwargs) for dto_data in data]


# this is for those defined in app blockchain
def get_dto_data(dto):
    data = {}
    for field in dto.get_fields():
        value = getattr(dto, field.name)
        if isinstance(value, DTO):
            value = get_dto_data(value)
        elif isinstance(value, list):
            for i in range(len(value)):
                if isinstance(value[i], DTO):
                    value[i] = get_dto_data(value[i])
        data[field.name] = value
    return data
