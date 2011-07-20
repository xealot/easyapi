"""
The classes in this package essentially manage the protocol 
layer.
"""

class RPCRequest(object):
    """
    This is a container of the entire request.
    """
    def __init__(self, invocations, **params):
        self.invocations = invocations
        self.params = params

    def unresolved(self):
        for i in self.invocations:
            if i.resolved is False:
                yield i

    def resolved(self):
        for i in self.invocations:
            if i.resolved is True:
                yield i


class MethodInvocation(object):
    """
    Describes the method to invoke and with what parameters. This 
    class will also store a successful result or exception.
    """
    def __init__(self, method_name=None, parameters=(), id=None, value=None, exception=False, **additional):
        self.method_name = method_name
        self.parameters = parameters #Parameters can be a list or dictionary.
        self.id = id
        self.is_error = exception
        self.resolved = exception is not False
        self.value = value
        self.additional = additional
    
    def result(self, value):
        self.is_error = False
        self.resolved = True
        self.value = value
    
    def error(self, exception):
        self.is_error = True
        self.resolved = True
        self.value = exception


class BaseInterface(object):
    mime_type = 'text/plain'
    
    def parse(self, content, method, environ, **kw):
        """
        Parse the content and return an RPCRequest.
        """
        raise NotImplementedError()
    
    def response(self, rpc_request, verbose_errors=False):
        """
        Results is the completed rpc_request object plus additional headers (If applicable)
        """
        raise NotImplementedError()