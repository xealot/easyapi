"""
from django.core.exceptions import ObjectDoesNotExist, MultipleObjectsReturned
from easyrpc.core import MethodContainer, rpc
from easyrpc.exceptions import APIFault
from easyrpc.validation.types import String, Dict

class APIBase(MethodContainer):
    request = None #This is to provide a hook for the analysic in my IDE...

    def _find_models(self, model, start=0, limit=50, **kw):
        return _get_queryset(model).filter(**kw)[start:limit]

    def _get_model(self, model, **kw):
        try:
            return _get_queryset(model).get(**kw)
        except ObjectDoesNotExist:
            raise APIFault('Reference given does not match any data.', http_code=410)
        except MultipleObjectsReturned:
            raise APIFault('Your reference was bad, multiple records returned from lookup.', http_code=400)

class customdata(APIBase):
    @rpc(String)
    def userData(self, user_ref, _returns=Dict):
        return QUERY_OF_DATA

    @rpc(String, String, _returns=Dict)
    def websiteData(self, website_slug, user_site_slug):
        return QUEYR_OF_WEBSITE_DATA


easyrpc = DjangoRequestHandler([customdata], translator=DjangoTranslator)

url(r'^api/v3/rpc/?', easyrpc),
"""