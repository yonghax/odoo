from ...backend import prestashop
from ...unit.mapper import PrestashopImportMapper, mapping

@prestashop
class ProductBrandMapper(PrestashopImportMapper):
    _model_name = 'prestashop.product.brand'

    @mapping
    def name(self, record):
        return {'name':record['name']}

    @mapping
    def active(self,record):
        return {'active': bool(int(record['active']))}

    @mapping
    def business_type(self, record):
        return {'business_type': 'b2c'}
    
    @mapping
    def backend_id(self, record):
        return {'backend_id': self.backend_record.id}