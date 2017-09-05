from openerp import api, fields, models, _

class sale_consignment_history(models.TransientModel):
    _name = 'sale.consignment.history'
    
    partner_id = fields.Many2one(
        string=u'Partner',
        comodel_name='res.partner',
    )
    date_from = fields.Date(
        string=u'Date From'
    )
    date_to = fields.Date(
        string=u'Date To'
    )
    sale_history_brands = fields.One2many('sale.consignment.history.brand', 'sale_history_id')

    @api.multi
    def print_report(self, xlsx_report=False):
        self.ensure_one()
        report_name = 'sale_consignment.sale_consignment_history_xls'
        return self.env['report'].get_action(records=self,report_name=report_name)

class sale_consignment_history_brand(models.TransientModel):
    _name = 'sale.consignment.history.brand'

    sale_history_id = fields.Many2one(string='Sale History',comodel_name='sale.consignment.history', ondelete='cascade')
    product_brand_id = fields.Many2one(
        string=u'Product Brand',
        comodel_name='product.brand',
    )
    sale_history_products = fields.One2many('sale.consignment.history.product', 'sale_history_brand_id')

class sale_consignment_history_line(models.TransientModel):
    _name = 'sale.consignment.history.product'
    
    sale_history_brand_id = fields.Many2one(string='Sale History Brand',comodel_name='sale.consignment.history.brand', ondelete='cascade')
    product_id = fields.Many2one(string='Product ID',comodel_name='product.product')
    product_reference = fields.Char(
        string=u'Reference',
    )
    product_barcode = fields.Char(
        string=u'Barcode',
    )
    product_name = fields.Char(
        string=u'Name',
    )
    product_attribute_value = fields.Char(
        string=u'Attribute Value',
    )
    qty_in = fields.Integer(
        string=u'Qty In',
    )
    qty_out = fields.Integer(
        string=u'Qty Out',
    )
    qty_return_in = fields.Integer(
        string=u'Qty Returned(Sale)',
    )
    qty_return_out = fields.Integer(
        string=u'Qty Returned(Purchase)',
    )
    qty_adj_in = fields.Integer(
        string=u'Qty Adjustment(IN)',
    )
    qty_adj_out = fields.Integer(
        string=u'Qty Adjustment(OUT)',
    )