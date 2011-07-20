"""
I put these in their own file to facilitate the lack 
of circular import errors
"""
import sys

class NoTransformer(Exception): 
    pass


class EAPIException(Exception):
    http_code = 500
    def __init__(self, reason, orig=None, **kw):
        self.etype, self.evalue, self.etrace = sys.exc_info()
        self.reason = reason
        self.orig = orig
        self.__dict__.update(kw)


class InvalidPayloadException(EAPIException):
    http_code = 400 #Bad Request


class MethodNotFound(EAPIException):
    http_code = 410


class MethodNotAllowed(EAPIException):
    http_code = 403


class BadInvocation(EAPIException):
    http_code = 500


class APIFault(EAPIException):
    http_code = 500


class InvalidParameters(EAPIException):
    http_code = 400