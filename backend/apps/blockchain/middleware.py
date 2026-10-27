"""Request-wide RPC budget; integration settings must explicitly register this."""
from .rpc import rpc_budget, VERIFICATION_SECONDS


class BlockchainRPCBudgetMiddleware:
    def __init__(self,get_response):
        self.get_response=get_response

    def __call__(self,request):
        with rpc_budget(VERIFICATION_SECONDS):
            return self.get_response(request)
