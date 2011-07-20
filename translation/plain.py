"""
THIS SHOULD BE PART OF THE JSON ENCODER or INTERFACE REALLY.


Translate types to serializable objects.
"""
import inspect, itertools, decimal, types
from datetime import datetime, date
from ..exceptions import NoTransformer

class PlainTranslator(object):
    """
    This transformer turns all objects into the most basic 
    representation we know how.
    """
    DEFAULT_TRANSFORMERS = list()
    TRANSFORMERS = list()
    
    def __init__(self, additional_types=()):
        for predicate, func in additional_types:
            self.add_type(predicate, func)
        self.add_defaults()

    def add_defaults(self):
        """
        Load up default handled types.
        Would love to do this based on ABCs but not sure the side effects yet or if it's possible.
        """
        self.add_default_type((bool, long, types.NoneType, basestring, int, float), 
                              None) #We add these anyway to short circuit the other checks, even though they are already primitive.
        self.add_default_type((datetime, date), 
                              None) #This is safe because of the JSON serializer we use.
        self.add_default_type(dict, 
                              lambda x: dict([ (k, self.resolve(v)) for k, v in x.iteritems() ]))
        self.add_default_type((tuple, list, types.GeneratorType), 
                              lambda x: [ self.resolve(v) for v in x ])
        self.add_default_type(lambda x: hasattr(x, '__emittable__'), 
                              lambda f: f.__emittable__())
        self.add_default_type(decimal.Decimal, 
                              lambda x: str(x))
        self.add_default_type((types.FunctionType, types.LambdaType), 
                              lambda x: x())
    
    def add_default_type(self, predicate, func):
        self.add_type(predicate, func, default=True)
    
    def add_type(self, predicate, func, default=False):
        """
        Register a type.
        
        Parameters::
         - `predicate`: Can be a callable with a single argument that returns true or false OR a type.
         - `func`: Is a callable that accepts a single argument which returns a plain value, sequence or dictionary.
        """
        storage = self.TRANSFORMERS if default is False else self.DEFAULT_TRANSFORMERS
        storage.append(
            (predicate if inspect.isfunction(predicate) else lambda x: isinstance(x, predicate), func)
        )
    
    def get_transformer(self, obj):
        for predicate, callback in itertools.chain(self.DEFAULT_TRANSFORMERS, self.TRANSFORMERS):
            if predicate(obj) is True:
                return callback
        raise NoTransformer('No transformer could be found for %s' % str(type(obj)))

    def resolve(self, obj):
        trans = self.get_transformer(obj)
        if trans is not None:
            return trans(obj)
        return obj




