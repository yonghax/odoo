from ...backend import prestashop
from ...unit.backend_adapter import GenericAdapter

try:
    from xml.etree import cElementTree as ElementTree
except ImportError, e:
    from xml.etree import ElementTree

@prestashop
class ProductTemplateAdapter(GenericAdapter):
    _model_name = 'prestashop.product.template'
    _prestashop_model = 'products'
    _export_node_name = 'product'

@prestashop
class StockAvailableAdapter(GenericAdapter):
    _model_name = '_import_stock_available'
    _prestashop_model = 'stock_availables'
    _export_node_name = 'stock_available'

    def get(self, options=None):
        api = self.connect()
        return api.get(self._prestashop_model, options=options)

    def export_quantity(self, filters, quantity):
        self.export_quantity_url(
            self.backend_record.location,
            self.backend_record.webservice_key,
            filters,
            quantity
        )

    def export_quantity_url(self, url, key, filters, quantity):
        response = self.search(filters)        
        for stock_id in response:
            stock = self.read(stock_id)
            stock['quantity'] = int(quantity)       
            try:
                self.write(stock['id'], stock)
            except ElementTree.ParseError:
                pass