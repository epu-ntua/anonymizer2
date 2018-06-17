import json

from decimal import Decimal
from django.utils.encoding import force_text
from django.utils.functional import Promise


class DefaultEncoder(json.JSONEncoder):

    def default(self, o):
        if isinstance(o, Decimal):
            return float(o)
        elif isinstance(o, Promise):
            return force_text(o)

        return super(DefaultEncoder, self).default(o)