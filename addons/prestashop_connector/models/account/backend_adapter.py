from ...backend import prestashop
from ...unit.backend_adapter import GenericAdapter

@prestashop
class RefundAdapter(GenericAdapter):
    _model_name = 'prestashop.refund'
    _prestashop_model = 'order_slips'