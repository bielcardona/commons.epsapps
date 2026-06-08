class ROL:
    PROFESSORAT = 'Professorat'
    DIRECCIO = 'Direccio'
    ALUMNE = 'Alumnat'
    PTGAS = 'PTGAS'


def remove_empty_values(d):
    new_dict = {}
    for key, value in d.items():
        if isinstance(value, dict):
            value = remove_empty_values(value)
        if value:
            new_dict[key] = value
    return new_dict


def get_full_name(user):
    return f"{user.last_name}, {user.first_name}".strip()
