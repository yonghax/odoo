from ...backend import prestashop
from ...unit.backend_adapter import GenericAdapter

@prestashop
class SaleOrderAdapter(GenericAdapter):
    _model_name = 'prestashop.sale.order'
    _prestashop_model = 'orders'
    _export_node_name = 'order'

    def search(self, filters=None):
        result = super(SaleOrderAdapter, self).search(filters=filters)

        shop_ids = self.session.search('prestashop.shop', [
            ('backend_id', '=', self.backend_record.id)
        ])
        shops = self.session.browse('prestashop.shop', shop_ids)
        for shop in shops:
            if not shop.default_url:
                continue

            api = PrestaShopWebServiceDict(
                '%s/api' % shop.default_url, self.prestashop.webservice_key
            )
            result += api.search(self._prestashop_model, filters)
        return result    




@prestashop
class SaleOrderLineAdapter(GenericAdapter):
    _model_name = 'prestashop.sale.order.line'
    _prestashop_model = 'order_details'

@prestashop
class PaymentMethodAdapter(GenericAdapter):
    _model_name = 'account.payment.mode'
    _prestashop_model = 'orders'
    _export_node_name = 'order'
    
    def search(self, filters=None):
        api = self.connect()
        res = api.get(self._prestashop_model, options=filters)
        methods = res[self._prestashop_model][self._export_node_name]
        if isinstance(methods, dict):
            return [methods]
        return methods