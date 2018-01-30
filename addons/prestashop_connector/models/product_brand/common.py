from ...backend import prestashop
from ...unit.import_synchronizer import PrestashopImportSynchronizer, import_batch

@prestashop
class ProductBrandImport(PrestashopImportSynchronizer):
    _model_name = 'prestashop.product.brand'