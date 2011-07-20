"""
Handler that can speak JSON RPC



"""
import traceback, datetime, calendar
import urlparse
from . import BaseInterface, MethodInvocation, RPCRequest
from ..utils import LocalTimezone, UTC
from ..exceptions import InvalidPayloadException

try: 
    import simplejson as json
except ImportError: 
    import json

#How to get UTC (THIS DOES NOT HANDLE ALL CASES)
#datetime.datetime.now() + datetime.timedelta(seconds=time.timezone) - datetime.timedelta(hours=(1 if time.daylight != 0 else 0))

def datetime_json_default(obj):
    """
    The primary role of this function is to convert datetime instances
    into a JSON representation of a UTC datetime.
    """
    if type(obj) is datetime.date:
        #Convert to datetime
        obj = datetime.datetime.combine(obj, datetime.time())
    if type(obj) is datetime.datetime:
        #If object is naive, replace the lack of a timezone with the locally derived timezone.
        if obj.tzinfo is None or obj.tzinfo.utcoffset(obj) is None:
            obj = obj.replace(tzinfo=LocalTimezone(obj))
        utc_obj = obj.astimezone(UTC())
        return {'__complex__': 'datetime',
                'tz': 'UTC',
                'epoch': calendar.timegm(utc_obj.timetuple()),
                'iso8601': utc_obj.isoformat(' ')}
    raise TypeError()

def datetime_json_object_hook(obj):
    if '__complex__' in obj:
        return datetime.datetime.fromtimestamp(obj['epoch'], UTC())
    return obj


class JSONRPCInterface(BaseInterface):
    """
    JSONRPC 2.0 Interface.
    """
    content_type = 'application/json'
    
    def __init__(self, json_encoder=json):
        self.json = json_encoder
        
    def parse(self, content, method, environ, **kw):
        #This method really isn't very complex, except for the exception handling.
        invocations = []
        try:
            #Well, this should be JSON for starters.
            try:
                decoded_content = self._decode_json(content)
            except ValueError as e:
                return RPCRequest([MethodInvocation(
                    value=InvalidPayloadException('JSON request cannot be parsed.', orig=e, code=-32700),
                    exception=True
                )])

            #Turn request into a list of requests even if it's not, since it's the way we process everything.
            if not isinstance(decoded_content, (list, tuple)):
                decoded_content = [decoded_content]
        
            for request in decoded_content:
                #This is to verify that these keys exist, it is required in the JSON spec.
                if not all(map(lambda x: x in request, ('id', 'jsonrpc', 'method'))) or \
                    request.get('jsonrpc') != "2.0":
                    mi = MethodInvocation(
                        value=InvalidPayloadException("You must specify 'id', 'jsonrpc' and a 'method' attribute at the root and jsonrpc must equal '2.0'", code=-32600),
                        exception=True
                    )
                else:
                    mi = MethodInvocation(request.get('method'),
                                          request.get('params', ()), 
                                          request.get('id'))
                invocations.append(mi)
        except Exception as e:
            invocations.append(
                MethodInvocation(
                    value=InvalidPayloadException(str(e), orig=e),
                    exception=True
                )
            )

        jsonp_callback = None
        qs = kw.get('querystring_dict', urlparse.parse_qs(environ.get('QUERY_STRING')))
        if method == 'GET' and 'callback' in qs:
            jsonp_callback = qs.get('callback')

        return RPCRequest(invocations, jsonp_callback=jsonp_callback)
    
    def response(self, rpc_request, verbose_errors=False):
        try:
            if len(rpc_request.invocations) == 1:
                output = self._wrap_object(rpc_request.invocations[0], verbose_errors)
            else:
                output = [self._wrap_object(i, verbose_errors) for i in rpc_request.invocations]

            jsonp_callback = rpc_request.params.get('jsonp_callback', None)
            if jsonp_callback is not None:
                return '%s(%s);' % (jsonp_callback, self._encode_json(output)), \
                    {'Content-Type': 'application/x-javascript'}
            return self._encode_json(output)
        except Exception as e:
            mi = MethodInvocation(
                value=InvalidPayloadException(str(e), orig=e),
                exception=True
            )
            return self._encode_json(self._wrap_object(mi, verbose_errors))
            
    #Implementation Specific methods follow
    def _wrap_object(self, invocation, verbose_errors=False):
        if invocation.is_error:
            error = dict(
                code=getattr(invocation.value, 'code', None),
                reason=getattr(invocation.value, 'reason', None)
            )
            if verbose_errors is True:
                error['traceback'] = traceback.extract_tb(invocation.value.etrace)
            return dict(
                id=invocation.id,
                jsonrpc="2.0",
                error=error
            )
        return dict(
            id=invocation.id,
            jsonrpc="2.0",
            result=invocation.value
        )
    
    def _decode_json(self, raw):
        """
        Override me for specialized decoding of complex JSON
        """
        return self.json.loads(raw, object_hook=datetime_json_object_hook)
    
    def _encode_json(self, object):
        """
        Override me for specialize encoding of complex json
        """
        return self.json.dumps(object, default=datetime_json_default, indent=4)




