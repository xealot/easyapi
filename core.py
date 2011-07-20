"""
This is the main file responsible for handing the request off to the 
proper handlers and invoking the class and method specified.
"""

import inspect
from functools import wraps
from exceptions import EAPIException, MethodNotFound, BadInvocation, APIFault
from validation.types import validate_parameters
from .interface.jsonrpc import JSONRPCInterface
from .translation.plain import PlainTranslator

#The container is loaded at each request, this avoids the penalty of inspection.
_public_methods_cache = {}


class MethodContainer(object):
    """
    This class is the base class for all user defined endpoints.
    """
    def __init__(self, **kw):
        self.__dict__.update(kw)

    def build_public_methods(self):
        """Returns a list of method descriptors for this object"""
        public_methods = []

        for func_name in dir(self):
            func = getattr(self, func_name)
            if callable(func) and hasattr(func, '_is_rpc'):
                descriptor = func(_method_descriptor=True, _class=self.__class__)
                public_methods.append(descriptor)

        return public_methods


class MethodDescriptor(object):
    """
    This is a container class for all methods contained inside of MethodContainer.
    """
    def __init__(self, _class, name, public_name, doc, params, argspec, faults, returns):
        self._class = _class
        self.name = name
        self.public_name = public_name
        self.doc = doc
        self.params = params
        self.argspec = argspec
        self.faults = faults
        self.returns = returns
        

class InvocationResult(object):
    def __init__(self, result):
        self.result = result

    
class RequestHandler(object):
    def __init__(self, services, interface=JSONRPCInterface, translator=PlainTranslator):
        self.interface = interface() if callable(interface) else interface
        self.translator = translator() if callable(translator) else translator
        self.build_invocation_map(services)

    def build_invocation_map(self, services):
        self.invocation_lookup = {} #Storage for finding the right method later.
        
        for service in services:
            methods = service().build_public_methods()
            for method in methods:
                self.invocation_lookup[self.create_invocation_name(method)] = method       

    def create_invocation_name(self, method):
        """
        This method is a hook to change the way 
        your methods are namespaced between services
        """
        return '%s.%s' % (method._class.__name__, method.public_name)
    
    def lookup_method(self, name):
        if name in self.invocation_lookup:
            return self.invocation_lookup[name]
        raise MethodNotFound('The method "%s" was not found.' % name)

    def handle_request(self, request_body, method, environ, **kw):
        """
        This is the request controller essentially. This method will 
        interface with the... interface, to receive invocation objects 
        and exceptions and call the appropriate methods to generate output
        """
        #It's possible to have an error in the parsing stage, before the invocations can be created.
        try:
            rpc_request = self.interface.parse(request_body, method, environ, **kw)
        except Exception as e:
            print 'uh oh'
            pass #:TODO:
            raise
        
        for invocation in rpc_request.unresolved():
            try:
                method_descriptor = self.lookup_method(invocation.method_name)

                method_container = method_descriptor._class(**kw)
                actual_method = getattr(method_container, method_descriptor.name)

                #If the args are list based instead of name based, convert to name based.
                if isinstance(invocation.parameters, (list, tuple)):
                    invocation.parameters = dict(zip(method_descriptor.argspec.args[1:], invocation.parameters))

                #Validate passed in parameters against defined parameters.
                clean_parameters = validate_parameters(method_descriptor.argspec, method_descriptor.params, invocation.parameters)

                result = actual_method(**clean_parameters)
                result = self.translator.resolve(result)

                invocation.result(result)
            except EAPIException as e:
                invocation.error(e)
            except Exception as e:
                invocation.error(EAPIException(str(e), orig=e))
        
        return self.interface.response(rpc_request, verbose_errors=True)
        

def rpc(*params, **kparams):
    """
    TODO: make this a callable class for customization purposes.
    This model is from rpclib, been changed drastically for this though. 
    
    This is a method decorator to flag a method as a remote procedure call.  It
    will behave like a normal python method on a class, and will only behave
    differently when the keyword '_method_descriptor' is passed in, returning a
    'MethodDescriptor' object.  This decorator does none of the soap/xml
    serialization, only flags a method as a soap method.  This decorator should
    only be used on member methods of an instance of ServiceBase.
    """
    def explain(f):
        @wraps(f)
        def explain_method(*args, **kwargs):
            if '_method_descriptor' not in kwargs :
                return f(*args, **kwargs)
            descparams = []
            for param in params:
                if callable(param):
                    param = param()
                if not hasattr(param, 'validate'):
                    raise TypeError('RPC Descriptors must have a validate method.')
                descparams.append(param)
            
            return MethodDescriptor(
                kwargs.get('_class'),
                f.func_name,
                kparams.get('_public_name', f.func_name),
                getattr(f, '__doc__'),
                descparams,
                inspect.getargspec(f),
                kparams.get('_faults', []),
                kparams.get('_returns', 'Unknown'),
            )

        explain_method._is_rpc = True
        return explain_method

    return explain