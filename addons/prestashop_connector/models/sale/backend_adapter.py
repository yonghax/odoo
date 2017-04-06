from prestapyt import PrestaShopWebServiceDict

from ...backend import prestashop
from ...unit.backend_adapter import GenericAdapter

@prestashop
class PrestashopOrderStateAdapter(GenericAdapter):
    _model_name = 'prestashop.order.state'
    _prestashop_model = 'order_states'

@prestashop
class SalesOrderHistoryAdapter(GenericAdapter):
    _model_name = 'order.histories'
    _prestashop_model = 'order_histories'

@prestashop
class SaleOrderAdapter(GenericAdapter):
    _model_name = 'prestashop.sale.order'
    _prestashop_model = 'orders'
    _export_node_name = 'order'

    # def search(self, filters=None):
    #     result = super(SaleOrderAdapter, self).search(filters=filters)

    #     shops = self.env['prestashop.shop'].search([
    #         ('backend_id', '=', self.backend_record.id)
    #     ])
    #     for shop in shops:
    #         if not shop.default_url:
    #             continue

    #         api = PrestaShopWebServiceDict(
    #             '%s/api' % shop.default_url, self.prestashop.webservice_key
    #         )
    #         result += api.search(self._prestashop_model, filters)
    #     return result    

@prestashop
class SaleOrderLineAdapter(GenericAdapter):
    _model_name = 'prestashop.sale.order.line'
    _prestashop_model = 'order_details'

@prestashop
class SaleOrderLineDiscountAdapter(GenericAdapter):
    _model_name = 'prestashop.sale.order.line.discount'
    _prestashop_model = 'order_discounts'