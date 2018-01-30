from ...backend import prestashop
from ...unit.backend_adapter import GenericAdapter

@prestashop
class ProductBrandAdapter(GenericAdapter):
    _model_name = 'prestashop.product.brand'
    _prestashop_model = 'manufacturers'