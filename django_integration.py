"""
Django wrapper to integrate into the request object.
"""
import inspect, re
from core import RequestHandler
from django.core.exceptions import ObjectDoesNotExist, MultipleObjectsReturned
from django.shortcuts import _get_queryset
from easyrpc.core import MethodContainer
from easyrpc.exceptions import APIFault
from translation.plain import PlainTranslator
from django.http import HttpResponse
from django.db.models.query import QuerySet, ValuesListQuerySet, ValuesQuerySet
from django.db.models import Model


class DjangoContainer(MethodContainer):
    request = None #This is to provide a hook for the analysis in my IDE...

    def _find_models(self, model, start=0, limit=50, **kw):
        return _get_queryset(model).filter(**kw)[start:limit]

    def _get_model(self, model, **kw):
        try:
            return _get_queryset(model).get(**kw)
        except ObjectDoesNotExist:
            raise APIFault('Reference given does not match any data.', http_code=410)
        except MultipleObjectsReturned:
            raise APIFault('Your reference was bad, multiple records returned from lookup.', http_code=400)


class DjangoRequestHandler(RequestHandler):
    def __call__(self, request):
        payload = request.raw_post_data if request.method == 'POST' else request.GET.get('payload', '{}')
        content = self.handle_request(payload, method=request.method, environ=request.META,
                                      request=request, querystring_dict=request.GET)
        headers = {}
        if isinstance(content, (tuple, list)):
            headers = content[1]
            content = content[0]

        response = HttpResponse(content, content_type=self.interface.content_type)

        for header, value in headers.items():
            response[header] = value
        return response


class DjangoTranslator(PlainTranslator):
    """
    A special version of the tranlator that also includes querysets and models.
    ABCs might be able to avoid this special casing in the INIT
    """
    def __init__(self, *a, **kw):
        super(DjangoTranslator, self).__init__(*a, **kw)

        self.add_type((ValuesListQuerySet, ValuesQuerySet),
                      lambda x: [ self.resolve(v) for v in x ])
        self.add_type(Model, self._model)
        self.add_type(QuerySet, self._qs)

    def get_field_picks(self, model_class, typemapper):
        fields, exclude = (), ()
        for klass, rules in typemapper.iteritems():
            if klass == model_class:
                if 'fields' in rules:
                    fields = rules['fields']
                if 'exclude' in rules:
                    exclude = rules['exclude']
        return fields, exclude

    # MODELS are a bit more complex because of fields.
    def _qs(self, data, fields=(), exclude=()):
        """
        Querysets.
        """
        if (not fields and not exclude) and hasattr(data, 'typemapper'):
            fields, exclude = self.get_field_picks(data.model, data.typemapper)
        defer_plan = data.query.get_loaded_field_names()
        if data.model in defer_plan:
            fields = defer_plan[data.model]
        return [ self._model(v, fields, exclude) for v in data ]

    def _fk(self, data, field):
        """
        Foreign keys.
        """
        return self.resolve(getattr(data, field.name))

    def _related(self, data, fields=()):
        """
        Foreign keys.
        """
        return [ self._model(m, fields) for m in data.iterator() ]

    def _m2m(self, data, field, fields=()):
        """
        Many to many (re-route to `_model`.)
        """
        return [ self._model(m, fields) for m in getattr(data, field.name).iterator() ]

    def _model(self, data, fields=(), exclude=()):
        """
        Models. Will respect the `fields` and/or
        `exclude` on the handler (see `typemapper`.)
        """
        #handler = self.in_typemapper(type(data), self.anonymous)
        ret = { }

        if (not fields and not exclude) and hasattr(data, 'typemapper'):
            fields, exclude = self.get_field_picks(data.__class__, data.typemapper)

        v = lambda f: getattr(data, f.attname)

        if not fields:
            get_fields = set([ f.attname.replace("_id", "", 1) for f in data._meta.fields ])
        else:
            get_fields = set(fields)
            # Brute force version
            #for f in data._meta.fields:
            #    ret[f.attname] = _any(getattr(data, f.attname))

        exclude_fields = set(exclude).difference(fields)

        #get_absolute_uri = False
        #if 'absolute_uri' in get_fields:
        #    get_absolute_uri = True

        # sets can be negated.
        for exclude in exclude_fields:
            if isinstance(exclude, basestring):
                get_fields.discard(exclude)

            elif isinstance(exclude, re._pattern_type):
                for field in get_fields.copy():
                    if exclude.match(field):
                        get_fields.discard(field)

        #Method Fields; This was originally for calling methods on the handler.
        #met_fields = method_fields(handler, get_fields)
        met_fields = ()
        for f in data._meta.local_fields:
            if f.serialize and not any([ p in met_fields for p in [ f.attname, f.name ]]):
                if f.attname in get_fields and hasattr(data, 'get_%s_display' % f.attname):
                    ret['%s_display' % f.attname] = getattr(data, 'get_%s_display' % f.attname)()

                if not f.rel:
                    if f.attname in get_fields:
                        ret[f.attname] = self.resolve(v(f))
                        get_fields.remove(f.attname)
                else:
                    if f.attname[:-3] in get_fields:
                        ret[f.name] = self._fk(data, f)
                        get_fields.remove(f.name)

        for mf in data._meta.many_to_many:
            if mf.serialize and mf.attname not in met_fields:
                if mf.attname in get_fields:
                    ret[mf.name] = self._m2m(data, mf)
                    get_fields.remove(mf.name)

        # try to get the remainder of fields
        for maybe_field in get_fields:

            if isinstance(maybe_field, (list, tuple)):
                model, fields = maybe_field
                inst = getattr(data, model, None)

                if inst:
                    if hasattr(inst, 'all'):
                        ret[model] = self._related(inst, fields)
                    elif callable(inst):
                        if len(inspect.getargspec(inst)[0]) == 1:
                            ret[model] = self.resolve(inst())#, fields)
                    else:
                        ret[model] = self._model(inst, fields)

            elif maybe_field in met_fields:
                # Overriding normal field which has a "resource method"
                # so you can alter the contents of certain fields without
                # using different names.
                ret[maybe_field] = self.resolve(met_fields[maybe_field](data))

            else:
                maybe = getattr(data, maybe_field, None)
                if maybe:
                    if callable(maybe):
                        if len(inspect.getargspec(maybe)[0]) == 1:
                            ret[maybe_field] = self.resolve(maybe())
                    else:
                        ret[maybe_field] = self.resolve(maybe)

    #    else:
    #        for f in data._meta.fields:
    #            ret[f.attname] = Transformer.resolve(getattr(data, f.attname))
    #
    #        fields = dir(data.__class__) + ret.keys()
    #        add_ons = [k for k in dir(data) if k not in fields and not k.startswith('_')]
    #
    #        for k in add_ons:
    #            ret[k] = Transformer.resolve(getattr(data, k))

        #if hasattr(data, 'get_api_url') and 'resource_uri' not in ret:
        #    try:
        #        ret['resource_uri'] = data.get_api_url()
        #    except: pass

        # absolute uri
        #if hasattr(data, 'get_absolute_url') and get_absolute_uri:
        #    try:
        #        ret['absolute_uri'] = data.get_absolute_url()
        #    except: pass

        return ret
