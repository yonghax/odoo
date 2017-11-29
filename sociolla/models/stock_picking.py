from openerp import api, fields, models, SUPERUSER_ID, _

class stock_pack_operation(models.Model):
    _inherit = ['stock.pack.operation']
    
    barcode = fields.Char(string=u'Barcode',compute='_get_barcode')
    warehouse_location = fields.Char(string=u'Location',compute='_get_barcode')
    is_free_product = fields.Boolean(string=u'Free Product',)

    def _get_barcode(self):
        for data in self:
            if data.product_id:
                data.barcode = data.product_id.barcode
                data.warehouse_location = data.product_id.product_tmpl_id.warehouse_location