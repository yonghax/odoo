from openerp import api, fields, models, _

import openerp.addons.decimal_precision as dp

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
    
    total_sales = fields.Float(string=u'Total Sales',digits=dp.get_precision('Product Price'),compute="_compute_amount",default=0.0)
    total_margin = fields.Float(string=u'Total Margin',digits=dp.get_precision('Product Price'),compute="_compute_amount",default=0.0)
    total_paid = fields.Float(string=u'Total Paid',digits=dp.get_precision('Product Price'),compute="_compute_amount",default=0.0)
    claim_support_promo = fields.Float(string=u'Claim Promotion',digits=dp.get_precision('Product Price'),default=0.0)
    
    @api.multi
    def _compute_amount(self):
        for data in self:
            data.total_sales = sum([x['total_sales'] for x in data.sale_history_brands])
            for line_brand in data.sale_history_brands:
                for line_product in line_brand.sale_history_products:
                    data.total_margin = data.total_margin + (line_product.total_price * line_product.margin) / 100
            data.total_margin = - data.total_margin
            data.total_paid = data.total_sales + data.total_margin + data.claim_support_promo
    
    @api.multi
    def print_report(self, xlsx_report=False):
        self.ensure_one()
        if xlsx_report:
            report_name = 'sale_consignment.sale_consignment_history_xls'
        else:
            report_name = 'sale_consignment.sale_brand_report'
        return self.env['report'].get_action(records=self, report_name=report_name)


class sale_consignment_history_brand(models.TransientModel):
    _name = 'sale.consignment.history.brand'
    
    sale_history_id = fields.Many2one(string='Sale History', comodel_name='sale.consignment.history', ondelete='cascade')
    product_brand_id = fields.Many2one(
        string=u'Product Brand',
        comodel_name='product.brand',
    )
    sale_history_products = fields.One2many('sale.consignment.history.product', 'sale_history_brand_id')
    margin = fields.Float(string=u'Total Percentage',digits=dp.get_precision('Discount'),compute="_compute_amount",default=0.0)
    total_qty_sold = fields.Integer(string=u'Total Qty Out',compute="_compute_amount",default=0)
    total_sales = fields.Float(string=u'Total Sales',digits=dp.get_precision('Product Price'),compute="_compute_amount",default=0.0)
    total_percentage = fields.Float(string=u'Total Percentage',digits=dp.get_precision('Discount'),compute="_compute_amount",default=0.0)
    total_qty_init = fields.Integer(string=u'Total Qty Init',digits=dp.get_precision('Discount'),compute="_compute_amount",default=0)
    total_qty_in = fields.Integer(string=u'Total Qty In',compute="_compute_amount",default=0)
    total_qty_out = fields.Integer(string=u'Total Qty Out',compute="_compute_amount",default=0)
    total_qty_end = fields.Integer(string=u'End Qty',compute="_compute_amount",default=0)

    @api.multi
    @api.depends('sale_history_products')
    def _compute_amount(self):
        for data in self:
            data.total_qty_sold = data.total_qty_out = sum([x['qty_total_out'] for x in data.sale_history_products])
            data.total_sales = sum([x['total_price'] for x in data.sale_history_products])
            data.total_percentage = sum([x['total_percentage'] for x in data.sale_history_products])
            data.total_qty_init = sum([x['qty_initial'] for x in data.sale_history_products])
            data.total_qty_in = sum([x['qty_total_in'] for x in data.sale_history_products])
            data.total_qty_end = sum([x['qty_total'] for x in data.sale_history_products])

class sale_consignment_history_line(models.TransientModel):
    _name = 'sale.consignment.history.product'

    sale_history_brand_id = fields.Many2one(string='Sale History Brand', comodel_name='sale.consignment.history.brand', ondelete='cascade')
    product_id = fields.Many2one(string='Product ID', comodel_name='product.product')
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
    qty_purchase = fields.Integer(
        string=u'Qty Purchase',
        oldname='qty_in',
        default=0
    )
    qty_sold = fields.Integer(
        string=u'Qty Sold',
        oldname='qty_out',
        default=0
    )
    qty_return_in = fields.Integer(
        string=u'Qty Returned(Sale)',
        default=0,
    )
    qty_return_out = fields.Integer(
        string=u'Qty Returned(Purchase)',
        default=0,
    )
    qty_adj_in = fields.Integer(
        string=u'Qty Adjustment(IN)',
        default=0,
    )
    qty_adj_out = fields.Integer(
        string=u'Qty Adjustment(OUT)',
        default=0,
    )
    qty_total_brand_out = fields.Integer(string=u'Qty Total Brand Out',default=0.0)
    qty_initial = fields.Integer(string=u'Qty Initial Balance',default=0.0)
    qty_total_in = fields.Integer(string=u'Qty Total In',compute='_compute_amount',default=0.0)
    qty_total_out = fields.Integer(string=u'Qty Total Out',compute='_compute_amount',default=0.0)
    qty_total = fields.Integer(string=u'Qty Total',compute='_compute_amount',default=0.0)

    price = fields.Float(string=u'Price', digits=dp.get_precision('Product Price'), default=0.0)
    margin = fields.Float(string='Margin', digits=dp.get_precision('Discount'), default=0.0)
    total_price = fields.Float(string=u'Total Price', digits=dp.get_precision('Product Price'), default=0.0, compute='_compute_amount')
    total_percentage = fields.Float(string=u'Total %', digits=dp.get_precision('Discount'), compute='_compute_amount', default=0.0)
    
    @api.multi
    def _compute_amount(self):
        for line in self:
            line.qty_total_in = line.qty_purchase + line.qty_adj_in
            line.qty_total_out = line.qty_sold + line.qty_adj_out
            line.qty_total = line.qty_initial + line.qty_total_in - line.qty_total_out
            line.total_price = line.qty_total_out * line.price

            qty_total_out = float(line.qty_total_out)
            qty_total_brand_out = float(line.qty_total_brand_out)
            if qty_total_out > 0 and qty_total_brand_out > 0:
                line.total_percentage = qty_total_out / qty_total_brand_out * 100